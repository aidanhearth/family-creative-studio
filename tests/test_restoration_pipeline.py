"""Actual cross-format output checks using synthetic inputs, enabled explicitly."""
import io
import json
import os
from pathlib import Path
import wave
import zipfile
import pytest
from studio.schema import Manifest
from studio.store import Store
from studio.assets import import_audio
from studio.pipeline import build

pytestmark=pytest.mark.skipif(not os.environ.get('STUDIO_PIPELINE_INTEGRATION'),reason='explicit multi-format synthetic render')


def short_wav():
    import math,struct
    data=io.BytesIO()
    with wave.open(data,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000)
        w.writeframes(b''.join(struct.pack('<h',int(6000*math.sin(i*440*2*math.pi/48000))) for i in range(24000)))
    return data.getvalue()


def test_full_pipeline_actual_cad_motion_audio_and_editable_ppt(tmp_path):
    store=Store(tmp_path/'data');audio=import_audio(store,short_wav())['asset']
    m=Manifest.model_validate({'id':'upgrade','title':'Geometry story','subtitle':'Synthetic restoration check',
        'video':{'resolution':'720p','fps':24},'slides':{'layout':'full','animation':'fade'},
        'solids':[{'id':'block','name':'Block','size':[18,12,10],'rotation':[0,0,25]},
                  {'id':'ring','name':'Ring','kind':'cylinder','size':[12,12,6],'bore':5,'position':[25,0,0]}],
        'beats':[{'id':'intro','title':'Native vectors','body':'Editable shapes and exact dimensions','narration':'Original narration','narration_asset':audio,'duration':.5,'layout':'editorial'},
                 {'id':'orbit','title':'Moving CAD','body':'Actual exported geometry','narration':'Retained motion','narration_asset':audio,'duration':.5,'focus':['ring'],'visual':{'mode':'orbit'}}]})
    store.save(m);job=store.enqueue(m.id);store.claim();build(store,job)
    completed=store.job(job['id']);assert completed['state']=='succeeded',completed
    out=store.artifact_root(completed)
    assert json.loads((out/'quality.json').read_text())['passed']
    assert json.loads((out/'motion/01.json').read_text())['focus']==['ring']
    assert json.loads((out/'edit.edl.json').read_text())['video_generations']['composition']==1
    ppt=json.loads((out/'pptx-check.json').read_text())
    assert ppt['narration_tracks']==2 and ppt['embedded_movies']==1 and ppt['native_paths']>0
    with zipfile.ZipFile(out/'presentation.pptx') as archive:
        assert any(n.endswith('.mp4') and n.startswith('ppt/media/') for n in archive.namelist())
        assert len([n for n in archive.namelist() if n.startswith('ppt/media/') and n.endswith('.wav')])==2
        slide=archive.read('ppt/slides/slide2.xml').decode()
        assert 'videoFile' in slide and 'advTm="500"' in slide
    assert len(json.loads((out/'cad-check.json').read_text())['part_ids'])==2


def test_original_scene_and_custom_vectors_reach_real_outputs(tmp_path):
    from test_scene_import import scene_fixture,glb_bytes
    from studio.scene_assets import import_scene
    from studio.svg_assets import import_svg
    store=Store(tmp_path/'data');doc,binary=scene_fixture();original=glb_bytes(doc,binary)
    scene=import_scene(store,original,'original.glb')['asset']
    svg=import_svg(store,b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600"><rect width="800" height="600" fill="#FFFFFF"/><circle cx="400" cy="300" r="180" fill="#114488"/><path d="M100 450 C250 350 550 550 700 450" fill="none" stroke="#222222" stroke-width="8"/><text x="250" y="300">Custom vector</text></svg>')['asset']
    m=Manifest.model_validate({'id':'imports','title':'Original scene','subtitle':'Preserve creative assets',
        'scene_asset':scene,'video':{'resolution':'720p','fps':24},'slides':{'narration':False,'autoplay':True,'animation':'fade'},
        'output_targets':['web','slides','video'],
        'beats':[{'id':'vector','title':'Editable vector','body':'Original SVG','narration':'','duration':.25,'svg_asset':svg,'visual':{'mode':'diagram','audio':'silent'}},
                 {'id':'scene','title':'Original animation','body':'Materials and animation','narration':'','duration':.25,'layout':'full','visual':{'mode':'orbit','audio':'silent'}}]})
    store.save(m);job=store.enqueue(m.id);store.claim();build(store,job)
    out=store.artifact_root(store.job(job['id']))
    assert (out/'scene.glb').read_bytes()==original
    assert not (out/'model.step').exists()
    assert 'separate CAD assembly' in (out/'index.html').read_text()
    check=json.loads((out/'pptx-check.json').read_text())
    assert check['narration_tracks']==0 and check['embedded_movies']==1 and check['native_paths']>0
    with zipfile.ZipFile(out/'presentation.pptx') as archive:
        assert not any(n.endswith('.wav') for n in archive.namelist())
        assert 'advTm="250"' in archive.read('ppt/slides/slide2.xml').decode()
    assert json.loads((out/'quality.json').read_text())['passed']


def test_source_4k60_video_has_no_forced_720p_or_24fps(tmp_path):
    import subprocess
    from studio.media_assets import import_media
    source=tmp_path/'source.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=3840x2160:r=60',
        '-t','0.1','-an','-c:v','libx264','-preset','ultrafast','-threads','2','-crf','18',str(source)],check=True,timeout=45)
    original=source.read_bytes();store=Store(tmp_path/'data');asset=import_media(store,original,'source.mp4')['asset']
    m=Manifest.model_validate({'id':'source-4k','title':'4K60 source','subtitle':'Synthetic six-frame video',
       'output_targets':['video'],'beats':[{'id':'clip','title':'Original canvas','body':'Preserved source dimensions and frame rate',
       'duration':.1,'narration':'','layout':'full','visual':{'mode':'clip','asset':asset,'audio':'silent'}}]})
    store.save(m);job=store.enqueue(m.id);store.claim();build(store,job)
    out=store.artifact_root(store.job(job['id']))
    assert (out/'assets'/asset).read_bytes()==original
    settings=json.loads((out/'output-settings.json').read_text())
    assert (settings['width'],settings['height'],settings['fps'])==(3840,2160,'60')
    edl=json.loads((out/'edit.edl.json').read_text())
    assert edl['video_generations']['composition']==1
    assert json.loads((out/'quality.json').read_text())['passed']


def test_portrait_source_video_reflows_all_layouts_and_preserves_native_ppt(tmp_path):
    import numpy as np
    from PIL import Image
    from types import SimpleNamespace
    from xml.etree import ElementTree as ET
    from studio.media_assets import import_media
    from studio.media_layout import visual_rect
    from studio.runner import Runner
    from studio.svg_assets import import_svg
    store=Store(tmp_path/'data')
    runner=Runner(SimpleNamespace(root=store.root,job=lambda _:{'cancel':False}),{'id':'portrait-fixture'},tmp_path)
    clip=tmp_path/'portrait.mp4'
    runner.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=0x2878c8:s=360x640:r=30',
        '-t','0.2','-an','-c:v','libx264','-preset','ultrafast','-threads','2',clip],label='portrait-fixture')
    original=clip.read_bytes();asset=import_media(store,original,'portrait.mp4')['asset']
    artwork=import_svg(store,b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="10 20 100 100"><circle cx="60" cy="70" r="40" fill="#00FF00"/></svg>')['asset']
    beats=[{'id':layout,'title':'Portrait title','body':'A clear description','narration':'','duration':.2,
        'layout':layout,'visual':{'mode':'clip','asset':asset,'audio':'silent'}} for layout in ('full','editorial','split')]
    beats.append({'id':'art','title':'Original vector','body':'Uniform fit','narration':'','duration':.2,'svg_asset':artwork,'visual':{'audio':'silent'}})
    m=Manifest.model_validate({'id':'portrait','title':'Portrait study','subtitle':'Source aspect ratio',
        'output_targets':['video','slides'],'video':{'captions':False,'normalize_audio':False},
        'slides':{'narration':False,'animation':'fade'},'beats':beats})
    store.save(m);job=store.enqueue(m.id);store.claim();build(store,job)
    out=store.artifact_root(store.job(job['id']))
    assert (out/'assets'/asset).read_bytes()==original
    settings=json.loads((out/'output-settings.json').read_text())
    assert (settings['width'],settings['height'],settings['fps'])==(360,640,'30')
    for i,layout in enumerate(('full','editorial','split','art')):
        frame=tmp_path/f'portrait-frame-{i}.png'
        runner.run(['ffmpeg','-v','error','-y','-ss',str(i*.2+.05),'-i',out/'film.mp4',
                    '-frames:v','1','-threads','2',frame],label=f'portrait-frame-{i}')
        with Image.open(frame) as image:
            assert image.size==(360,640)
            pixels=np.asarray(image).astype(int)
            def close(x,y,color,tolerance=12):
                assert np.abs(pixels[y,x]-color).max()<=tolerance
            if layout=='full':
                close(180,320,[40,120,200])
                # These panels were misplaced into the middle by the old 16:9 meet.
                close(20,20,[232,235,236],18)
                close(20,570,[232,235,236],18)
            elif layout in ('editorial','split'):
                x,y,w,h=visual_rect(layout,360,640)
                close(x+w//2,y+h//2,[40,120,200])
                close(0,0,[246,244,239]);close(0,639,[246,244,239])
                with Image.open(out/'slides'/f'{i:02d}.png') as poster:
                    # Moving-video placement agrees with the independently composed poster.
                    assert np.abs(pixels-np.asarray(poster).astype(int)).mean()<3
            else:
                ys,xs=np.where((pixels[:,:,1]>220)&(pixels[:,:,0]<30)&(pixels[:,:,2]<30))
                assert abs((xs.max()-xs.min())-(ys.max()-ys.min()))<=3
                assert 280<=xs.max()-xs.min()<=290
        assert ET.fromstring((out/'slides'/f'{i:02d}.svg').read_bytes()).get('viewBox')=='0 0 1280 720'
    with zipfile.ZipFile(out/'presentation.pptx') as package:
        doc=ET.fromstring(package.read('ppt/presentation.xml'))
        size=doc.find('{http://schemas.openxmlformats.org/presentationml/2006/main}sldSz')
        assert int(size.get('cx'))*9==int(size.get('cy'))*16
    assert json.loads((out/'quality.json').read_text())['passed']
