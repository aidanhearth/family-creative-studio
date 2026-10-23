"""Self-contained GLB validation and actual loader inspection."""
import copy
import io
import json
import struct
import subprocess

import pytest
from PIL import Image
from studio.paths import ROOT
from studio.scene_document import validate_document, read_document
from studio.schema import Manifest


def scene_fixture():
    positions = struct.pack('<9f',0,0,0,1,0,0,0,1,0)
    times = struct.pack('<2f',0,1)
    translations = struct.pack('<6f',0,0,0,0,2,0)
    texture = io.BytesIO(); Image.new('RGBA',(1,1),(20,100,180,120)).save(texture,format='PNG'); pixels=texture.getvalue()
    binary=positions+times+translations+pixels
    doc={'asset':{'version':'2.0'},'buffers':[{'byteLength':len(binary)}],
         'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':36},{'buffer':0,'byteOffset':36,'byteLength':8},{'buffer':0,'byteOffset':44,'byteLength':24},{'buffer':0,'byteOffset':68,'byteLength':len(pixels)}],
         'accessors':[{'bufferView':0,'componentType':5126,'count':3,'type':'VEC3','min':[0,0,0],'max':[1,1,0]}, {'bufferView':1,'componentType':5126,'count':2,'type':'SCALAR'}, {'bufferView':2,'componentType':5126,'count':2,'type':'VEC3'}],
         'images':[{'bufferView':3,'mimeType':'image/png'}],'textures':[{'source':0}],
         'materials':[{'name':'Original material','pbrMetallicRoughness':{'baseColorFactor':[.2,.4,.6,1],'baseColorTexture':{'index':0}},'alphaMode':'BLEND'}],
         'meshes':[{'primitives':[{'attributes':{'POSITION':0},'material':0}]}],
         'nodes':[{'name':'Original node','mesh':0}], 'scenes':[{'nodes':[0]}],'scene':0,
         'animations':[{'name':'Rise','samplers':[{'input':1,'output':2}],'channels':[{'sampler':0,'target':{'node':0,'path':'translation'}}]}]}
    return doc,binary


def glb_bytes(doc,binary):
    encoded=json.dumps(doc,separators=(',',':')).encode(); encoded+=b' '*(-len(encoded)%4)
    binary+=b'\0'*(-len(binary)%4)
    body=struct.pack('<II',len(encoded),0x4E4F534A)+encoded+struct.pack('<II',len(binary),0x004E4942)+binary
    return struct.pack('<4sII',b'glTF',2,len(body)+12)+body


def two_clip_fixture():
    doc,binary=scene_fixture()
    binary+=b'\0'*(-len(binary)%4)
    offset=len(binary);binary+=struct.pack('<6f',0,0,0,3,0,0)
    doc['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':24})
    doc['accessors'].append({'bufferView':4,'componentType':5126,'count':2,'type':'VEC3'})
    doc['animations'].append({'name':'Slide','samplers':[{'input':1,'output':3}],
        'channels':[{'sampler':0,'target':{'node':0,'path':'translation'}}]})
    doc['buffers'][0]['byteLength']=len(binary)
    return doc,binary


def test_scene_animation_preflight_rejects_missing_clip(monkeypatch):
    from studio import media_assets
    monkeypatch.setattr(media_assets,'asset_info',lambda *_:(None,{'kind':'scene','animations':[{'name':'Rise'},{'name':'Slide'}]}))
    manifest=Manifest.model_validate({'id':'selection','title':'Scene','subtitle':'Scene','scene_asset':'a'*64+'.glb','scene_animation':1,
        'beats':[{'id':'view','title':'View','body':'View','narration':'','visual':{'mode':'orbit','audio':'silent'}}]})
    assert media_assets.preflight(None,manifest,['web'])['ready']
    manifest.scene_animation=2
    with pytest.raises(ValueError,match='animation does not exist'):media_assets.preflight(None,manifest,['web'])


def test_valid_original_material_animation_and_embedded_texture(tmp_path):
    doc,binary=scene_fixture(); path=tmp_path/'source.glb';path.write_bytes(glb_bytes(doc,binary))
    read,_,metadata=read_document(path)
    assert metadata['materials']==1 and metadata['textures']==1
    assert read['materials'][0]['name']=='Original material' and read['animations'][0]['name']=='Rise'
    subprocess.run(['node',ROOT/'scripts/scene-inspect.mjs',path,tmp_path/'metadata.json'],check=True,cwd=ROOT,timeout=20)
    actual=json.loads((tmp_path/'metadata.json').read_text())
    assert actual['part_ids']==['node-0'] and actual['animations'][0]['duration_s']==1
    assert actual['bounds_m']=={'min':[0,0,0],'max':[1,1,0]}
    assert path.read_bytes()==glb_bytes(doc,binary)


@pytest.mark.parametrize('mutate',[
    lambda d:d['buffers'][0].update(uri='https://example.invalid/data.bin'),
    lambda d:d['images'][0].update(uri='file:///etc/passwd'),
    lambda d:d['bufferViews'][0].update(byteLength=100000),
    lambda d:d['accessors'][0].update(count=100000),
    lambda d:d['nodes'][0].update(children=[0]),
    lambda d:d.update(extensionsRequired=['KHR_draco_mesh_compression']),
    lambda d:d['meshes'][0]['primitives'][0].update(extensions={'KHR_draco_mesh_compression':{}}),
    lambda d:d['nodes'][0].update(matrix=[float('nan')]*16),
])
def test_invalid_or_external_scene_resources_rejected(mutate):
    doc,binary=scene_fixture(); mutate(doc)
    with pytest.raises(ValueError):validate_document(doc,binary)


def test_scene_only_manifest_can_orbit_without_fake_cad():
    manifest=Manifest.model_validate({'id':'scene','title':'Scene','subtitle':'Scene','scene_asset':'a'*64+'.glb',
        'beats':[{'id':'view','title':'View','body':'View','narration':'View','visual':{'mode':'orbit'}}]})
    assert not manifest.solids and manifest.scene_asset
