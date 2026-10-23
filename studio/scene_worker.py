"""Fixed-timestamp actual CAD rendering; isolated by Runner, frames streamed into FFmpeg."""
import base64
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from fractions import Fraction
from playwright.sync_api import sync_playwright
from .paths import ROOT,atomic_json,sha256
from .runtime import browser_executable

out=Path(sys.argv[1]);index=int(sys.argv[2]);duration=float(sys.argv[3])
m=json.loads((out/'manifest.json').read_text());beat=m['beats'][index];mode=beat['visual']['mode']
settings=json.loads((out/'output-settings.json').read_text())
width,height=settings['width'],settings['height'];fps=settings['fps']
frames=max(1,math.ceil(duration*float(Fraction(fps))));video=out/'motion'/f'{index:02d}.mp4';video.parent.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=browser_executable(),headless=True,args=['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-background-networking'])
    page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
    page.route('**/*',lambda route:route.abort())
    page.set_content(f'<html><body style="margin:0"><div id="scene" style="width:{width}px;height:{height}px"></div></body></html>')
    page.add_script_tag(path=str(ROOT/'dist/viewer.js'))
    scene_path=out/('scene.glb' if m.get('scene_asset') else 'model.glb')
    glb='data:model/gltf-binary;base64,'+base64.b64encode(scene_path.read_bytes()).decode()
    page.evaluate('async ({m,glb})=>{window.v=makeStudioViewer(document.getElementById("scene"),m,{glbUrl:glb,manual:true});await v.ready;if(!["cad-glb","scene-glb"].includes(v.state.mode))throw Error("Actual geometry unavailable");}',{'m':m,'glb':glb})
    page.evaluate('(focus)=>v.focus(focus)',beat.get('focus',[]))
    process=subprocess.Popen(['ffmpeg','-v','error','-y','-f','image2pipe','-vcodec','png','-framerate',fps,'-i','pipe:0','-an','-c:v','libx264','-threads','2','-preset','veryfast','-crf','0','-pix_fmt','yuv444p',str(video)],stdin=subprocess.PIPE)
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
# Thin/backface-culled or rotationally symmetric source meshes may legitimately
# share pixels between camera poses. Record motion evidence, do not reject them
# against a percentage chosen for the original three-box fixture.
atomic_json(out/'motion'/f'{index:02d}.json',{'source_glb_sha256':sha256(scene_path),'mode':mode,'animation':m.get('scene_animation',0),'focus':beat.get('focus',[]),'frames':frames,'fps':fps,'width':width,'height':height,'intermediate':'lossless H264 4:4:4','moving_fraction':ratio,'visible_motion_detected':len(set(hashes))>1,'repeat_first_frame_equal':repeat==hashes[0],'frame_hashes':hashes,'sampled_states':sampled,'determinism_scope':'same host / Chrome / SwiftShader / fonts'})
