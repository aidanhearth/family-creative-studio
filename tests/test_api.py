from fastapi.testclient import TestClient
from studio.server import create_app

def test_local_guard_and_revision_api(tmp_path,monkeypatch):
    monkeypatch.setenv('STUDIO_DATA',str(tmp_path));client=TestClient(create_app(),base_url='http://localhost')
    assert client.get('/api/projects',headers={'Host':'evil.example'}).status_code==403
    assert client.get('/api/session',headers={'Origin':'https://evil.example'}).status_code==403
    assert client.post('/api/demo',json={}).status_code==403
    token=client.get('/api/session').json()['token'];headers={'x-studio-token':token}
    project=client.post('/api/demo',json={},headers=headers).json()
    assert project['revision']==1
    manifest=project['manifest'];manifest['title']='Revised'
    body={'manifest':manifest,'expected_revision':1}
    assert client.post('/api/projects',json=body,headers=headers).status_code==200
    assert client.post('/api/projects',json=body,headers=headers).status_code==409
    assert client.get('/artifacts/unknown/../../studio.sqlite3').status_code in (404,422)

def test_invalid_audio_is_a_validation_error(tmp_path,monkeypatch):
    monkeypatch.setenv('STUDIO_DATA',str(tmp_path));client=TestClient(create_app(),base_url='http://localhost')
    token=client.get('/api/session').json()['token']
    response=client.post('/api/audio',content=b'not-a-wave',headers={'x-studio-token':token})
    assert response.status_code==422

def test_streamed_body_is_bounded(tmp_path,monkeypatch):
    monkeypatch.setenv('STUDIO_DATA',str(tmp_path));client=TestClient(create_app(),base_url='http://localhost')
    token=client.get('/api/session').json()['token']
    response=client.post('/api/validate',content=iter([b' '*(16*1024*1024),b'over']),headers={'x-studio-token':token,'content-type':'application/json'})
    assert response.status_code==413

def test_extensible_wav_is_validation_error(tmp_path,monkeypatch):
    import struct
    monkeypatch.setenv('STUDIO_DATA',str(tmp_path));client=TestClient(create_app(),base_url='http://localhost')
    token=client.get('/api/session').json()['token']
    fmt=struct.pack('<HHIIHH',65534,1,48000,144000,3,24)+b'\0'*24
    data=b'WAVEfmt '+struct.pack('<I',len(fmt))+fmt+b'data'+struct.pack('<I',0)
    response=client.post('/api/audio',content=b'RIFF'+struct.pack('<I',len(data))+data,headers={'x-studio-token':token})
    assert response.status_code==422


def test_full_256_chapter_patch_is_atomic(tmp_path,monkeypatch):
    from studio.schema import Manifest
    from studio.store import Store
    monkeypatch.setenv('STUDIO_DATA',str(tmp_path));client=TestClient(create_app(),base_url='http://localhost')
    token=client.get('/api/session').json()['token'];headers={'x-studio-token':token}
    m=Manifest.model_validate({'id':'bulk','title':'Bulk edit','subtitle':'All chapters',
       'beats':[{'id':f'b{i}','title':'Before','body':'Before','duration':.1,'narration':'Voice'} for i in range(256)]})
    Store().save(m)
    ops=[{'op':'set','target':'beat','id':f'b{i}','values':{'title':'After'}} for i in range(256)]
    bad=ops+[{'op':'set','target':'beat','id':'b255','values':{'duration':-1}}]
    assert client.post('/api/projects/bulk/patch',json={'expected_revision':1,'operations':bad},headers=headers).status_code==422
    assert Store().project('bulk')['revision']==1
    response=client.post('/api/projects/bulk/patch',json={'expected_revision':1,'operations':ops},headers=headers)
    assert response.status_code==200,response.text
    assert Store().project('bulk')['revision']==2
    assert all(b['title']=='After' for b in Store().project('bulk')['manifest']['beats'])
