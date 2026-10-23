"""Fixed-timestamp actual CAD rendering; isolated by Runner, frames streamed into FFmpeg."""
import base64
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from playwright.sync_api import sync_playwright
from .paths import ROOT,atomic_json,sha256
from .runtime import browser_executable

out=Path(sys.argv[1]);index=int(sys.argv[2]);duration=float(sys.argv[3])
m=json.loads((out/'manifest.json').read_text());beat=m['beats'][index];mode=beat['visual']['mode']
frames=math.ceil(duration*24);video=out/'motion'/f'{index:02d}.mp4';video.parent.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=browser_executable(),headless=True,args=['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-background-networking'])
    page=browser.new_page(viewport={'width':720,'height':420},device_scale_factor=1)
    page.route('**/*',lambda route:route.abort())
    page.set_content('<html><body style="margin:0"><div id="scene" style="width:720px;height:420px"></div></body></html>')
    page.add_script_tag(path=str(ROOT/'dist/viewer.js'))
    glb='data:model/gltf-binary;base64,'+base64.b64encode((out/'model.glb').read_bytes()).decode()
    page.evaluate('async ({m,glb})=>{window.v=makeStudioViewer(document.getElementById("scene"),m,{glbUrl:glb,manual:true});await v.ready;if(v.state.mode!=="cad-glb")throw Error("Actual CAD unavailable");}',{'m':m,'glb':glb})
    process=subprocess.Popen(['ffmpeg','-v','error','-y','-f','image2pipe','-vcodec','png','-framerate','24','-i','pipe:0','-an','-c:v','libx264','-threads','2','-preset','veryfast','-crf','18','-pix_fmt','yuv420p',str(video)],stdin=subprocess.PIPE)
    hashes=[];sampled=[]
    try:
        for i in range(frames):
            state=page.evaluate('({mode,t})=>v.renderFrame(mode,t)',{'mode':mode,'t':i/max(1,frames-1)})
            if not state['inside']:raise ValueError('Animated geometry leaves the camera frame')
            png=page.screenshot(type='png',animations='disabled');hashes.append(hashlib.sha256(png).hexdigest())
            if i==0:(out/'motion'/f'{index:02d}.png').write_bytes(png)
            if i in (0,frames//2,frames-1):sampled.append(state)
            process.stdin.write(png)
        process.stdin.close()
        if process.wait(timeout=30):raise RuntimeError('Scene encoder failed')
        page.evaluate('({mode})=>v.renderFrame(mode,0)',{'mode':mode})
        repeat=hashlib.sha256(page.screenshot(type='png',animations='disabled')).hexdigest()
        if repeat!=hashes[0]:raise ValueError('Scene seek is not deterministic on this renderer')
    finally:
        if process.poll() is None:process.kill();process.wait()
        browser.close()
ratio=sum(a!=b for a,b in zip(hashes,hashes[1:]))/max(1,frames-1)
if ratio<.9:raise ValueError('Animated scene did not produce real frame motion')
atomic_json(out/'motion'/f'{index:02d}.json',{'source_glb_sha256':sha256(out/'model.glb'),'mode':mode,'frames':frames,'fps':24,'moving_fraction':ratio,'repeat_first_frame_equal':repeat==hashes[0],'frame_hashes':hashes,'sampled_states':sampled,'determinism_scope':'same host / Chrome / SwiftShader / fonts'})
