"""Actual skin deformation and scale animation must stay framed, including portrait."""
import base64
import os
import struct
import pytest
from test_scene_import import scene_fixture,glb_bytes
from test_scene_import import two_clip_fixture

pytestmark=pytest.mark.skipif(os.environ.get('STUDIO_BROWSER_TESTS')!='1',reason='explicit browser journey')


def animated_fixture(kind):
    doc,binary=scene_fixture()
    if kind=='skin':
        data=struct.pack('<12H',*([0]*12));padding=b'\0'*(-len(binary)%4);binary+=padding
        offset=len(binary);binary+=data
        doc['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':len(data)})
        doc['accessors'].append({'bufferView':4,'componentType':5123,'count':3,'type':'VEC4'})
        data=struct.pack('<12f',*([1,0,0,0]*3));offset=len(binary);binary+=data
        doc['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':len(data)})
        doc['accessors'].append({'bufferView':5,'componentType':5126,'count':3,'type':'VEC4'})
        doc['meshes'][0]['primitives'][0]['attributes'].update(JOINTS_0=3,WEIGHTS_0=4)
        doc['nodes'][0]['skin']=0;doc['nodes'].append({'name':'Moving bone'})
        doc['scenes'][0]['nodes'].append(1);doc['skins']=[{'joints':[1]}]
        doc['animations'][0]['channels'][0]['target']['node']=1
    else:
        binary=binary[:44]+struct.pack('<6f',100,100,100,.0001,.0001,.0001)+binary[68:]
        doc['nodes'][0]['scale']=[100,100,100]
        doc['animations'][0]['channels'][0]['target']['path']='scale'
    doc['buffers'][0]['byteLength']=len(binary)
    return base64.b64encode(glb_bytes(doc,binary)).decode()


@pytest.mark.parametrize('kind',['skin','scale'])
def test_evaluated_animation_bounds_frame_all_poses(kind):
    from playwright.sync_api import sync_playwright
    from studio.paths import ROOT
    from studio.runtime import browser_executable
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=browser_executable(),headless=True,
            args=['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-background-networking'])
        page=browser.new_page(viewport={'width':700,'height':1000})
        page.route('**/*',lambda route:route.abort())
        page.set_content('<div id="v" style="width:650px;height:950px"></div>')
        page.add_script_tag(path=str(ROOT/'dist/viewer.js'))
        result=page.evaluate('''async(data)=>{
          const v=makeStudioViewer(document.getElementById('v'),{brand:{paper:'#ffffff',ink:'#222222'},solids:[],beats:[],scene_asset:'test.glb'},{manual:true,glbData:data});
          await v.ready;const states=[0,.5,1,0].map(t=>v.renderFrame('orbit',t));v.dispose();return states;
        }''',animated_fixture(kind))
        assert all(state['inside'] for state in result)
        assert result[0]['parts']==result[-1]['parts']
        if kind=='skin':
            assert result[2]['parts'][0]['position'][2]-result[0]['parts'][0]['position'][2]>1999
        else:
            assert result[0]['parts'][0]['size'][0]>99999
            assert result[2]['parts'][0]['size'][0]<1
        browser.close()


def test_selected_second_clip_evaluates_its_actual_channel():
    from playwright.sync_api import sync_playwright
    from studio.paths import ROOT
    from studio.runtime import browser_executable
    doc,binary=two_clip_fixture()
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=browser_executable(),headless=True,
            args=['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-background-networking'])
        page=browser.new_page(viewport={'width':700,'height':700})
        page.route('**/*',lambda route:route.abort())
        page.set_content('<div id="v" style="width:650px;height:650px"></div>')
        page.add_script_tag(path=str(ROOT/'dist/viewer.js'))
        result=page.evaluate('''async(data)=>{
          const v=makeStudioViewer(document.getElementById('v'),{brand:{paper:'#ffffff',ink:'#222222'},solids:[],beats:[],scene_asset:'test.glb',scene_animation:1},{manual:true,glbData:data});
          await v.ready;const result={index:v.state.animationIndex,states:[0,1,0].map(t=>v.renderFrame('orbit',t))};v.dispose();return result;
        }''',base64.b64encode(glb_bytes(doc,binary)).decode())
        assert result['index']==1
        a,b,c=result['states'];assert a['parts']==c['parts']
        assert b['parts'][0]['position'][0]-a['parts'][0]['position'][0]>2999
        assert abs(b['parts'][0]['position'][2]-a['parts'][0]['position'][2])<.001
        assert all(s['inside'] for s in result['states'])
        browser.close()
