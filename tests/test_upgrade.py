import io
import json
from pathlib import Path
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from studio.schema import Manifest
from studio.seed import demo
from studio.store import Store,Conflict
from studio.operations import patch_project
from studio.stage_cache import StageCache
from studio.media_assets import import_media,preflight


def test_stage_cache_integrity_and_copy_isolation(tmp_path):
    out=tmp_path/'out';out.mkdir();calls=[]
    def make():calls.append(1);(out/'model.step').write_text('verified geometry')
    c=StageCache(tmp_path,'engine');one=c.run('cad',{'solids':[1]},out,['model.step'],make)
    assert not one['reused']
    (out/'model.step').write_text('changed output')
    two=c.run('cad',{'solids':[1]},out,['model.step'],make)
    assert two['reused'] and (out/'model.step').read_text()=='verified geometry'
    (tmp_path/'stages'/'cad'/one['key']/'0.step').write_text('tampered')
    assert not c.run('cad',{'solids':[1]},out,['model.step'],make)['reused']
    assert len(calls)==2
    assert not c.run('cad',{'solids':[2]},out,['model.step'],make)['reused']


def test_image_import_and_tamper_preflight(tmp_path):
    store=Store(tmp_path);data=io.BytesIO();Image.new('RGB',(64,32),'red').save(data,format='JPEG')
    meta=import_media(store,data.getvalue());assert meta['asset'].endswith('.png')
    m=demo().model_dump();m['beats'][0]['visual']={'mode':'image','asset':meta['asset']}
    assert preflight(store,Manifest.model_validate(m),['video'])['ready']
    (tmp_path/'assets'/meta['asset']).write_bytes(b'bad')
    with pytest.raises(ValueError,match='changed'):preflight(store,Manifest.model_validate(m),['video'])
    with pytest.raises(ValueError):import_media(store,b'<svg onload="x"/>')


def test_media_schema_conflicts_and_bounds():
    m=demo().model_dump();m['beats'][0]['visual']={'mode':'orbit','start':float('nan')}
    with pytest.raises(ValueError):Manifest.model_validate(m)
    m['beats'][0]['visual']={'mode':'image','asset':'a'*64+'.mp4'}
    with pytest.raises(ValueError):Manifest.model_validate(m)
    m['beats'][0]['visual']={'mode':'clip','asset':'a'*64+'.mp4','audio':'source'};m['narration_asset']='b'*64+'.wav'
    with pytest.raises(ValueError):Manifest.model_validate(m)


def test_revision_compare_and_race(tmp_path):
    store=Store(tmp_path);p=store.save(demo())
    ops=[{'op':'set','target':'solid','id':'tray','values':{'bore':64}}]
    changed=patch_project(store,p['id'],1,ops)
    assert changed['revision']==2
    with pytest.raises(Conflict):patch_project(store,p['id'],1,ops)
    diff=store.compare(p['id'],1)
    assert diff['geometry_changed'] and diff['changes']==[{'path':'solids.tray.bore','before':60.0,'after':64.0}]


def test_http_recipe_patch_and_preflight(tmp_path,monkeypatch):
    monkeypatch.setenv('STUDIO_DATA',str(tmp_path))
    from studio.server import create_app
    client=TestClient(create_app(),base_url='http://127.0.0.1')
    headers={'x-studio-token':client.get('/api/session').json()['token']}
    assert client.get('/api/schema').status_code==200
    recipes=client.get('/api/recipes').json();assert len(recipes)==3
    for r in recipes:
        p=client.post('/api/create',json={'recipe_id':r['id'],'project_id':r['id'].replace('_','-')},headers=headers)
        assert p.status_code==200,p.text
    pid='product-explainer'
    p=client.post('/api/projects/'+pid+'/patch',json={'expected_revision':1,'operations':[{'op':'set','target':'solid','id':'tray','values':{'bore':64}}]},headers=headers)
    assert p.status_code==200,p.text
    assert client.get('/api/projects/'+pid+'/preflight').json()['ready']
    assert client.post('/api/projects/'+pid+'/patch',json={'expected_revision':1,'operations':[{'op':'set','target':'solid','id':'tray','values':{'bore':65}}]},headers=headers).status_code==409
    assert client.get('/api/projects/'+pid+'/compare?before=1').json()['geometry_changed']


def test_identical_stage_with_different_output_names_reuses_once(tmp_path):
    out=tmp_path/'out';out.mkdir();cache=StageCache(tmp_path,'engine');calls=[]
    for i in range(3):
        name=f'{i:02d}.wav'
        def create():calls.append(name);(out/name).write_bytes(b'identical sound')
        result=cache.run('audio',{'text':'same'},out,[name],create)
        assert result['reused']==(i>0)
    assert len(calls)==1
    assert not list((tmp_path/'stages'/'audio').glob('*.invalid-*'))


def test_single_part_explode_rejected_early():
    m=demo().model_dump();m['solids']=m['solids'][:1]
    for beat in m['beats']:beat['focus']=[];beat['visual']={'mode':'explode'}
    with pytest.raises(ValueError,match='at least two'):Manifest.model_validate(m)


def test_clip_voice_cannot_extend_authored_trim(tmp_path):
    import wave
    from studio.video import audio_track
    m=demo().model_dump();m['beats']=m['beats'][:1]
    m['beats'][0].update(duration=5,visual={'mode':'clip','asset':'a'*64+'.mp4','audio':'voice'})
    class Runner:
        def run(self,args,**kwargs):
            with wave.open(str(args[-1]),'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b'\0\0'*39200)
    with pytest.raises(ValueError,match='Narration exceeds this trimmed clip'):
        audio_track(Manifest.model_validate(m),tmp_path,Runner(),StageCache(tmp_path,'engine'))
