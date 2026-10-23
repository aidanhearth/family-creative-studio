"""Optional real-browser editor journey. No render workers or media processing run.

Run STUDIO_BROWSER_TESTS=1 .venv/bin/python -m pytest tests/test_browser_editor.py -q
with Chromium available and npm run build already completed.
"""
import os
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(os.environ.get('STUDIO_BROWSER_TESTS') != '1', reason='explicit browser journey')


def test_editor_draft_tokens_structure_settings_and_audit(tmp_path, monkeypatch):
    from playwright.sync_api import sync_playwright, expect
    from studio.server import create_app
    from studio.runtime import browser_executable

    monkeypatch.setenv('STUDIO_DATA', str(tmp_path))
    # TestClient without a lifespan context deliberately starts no render worker.
    client = TestClient(create_app(), base_url='http://localhost')
    calls = []

    def serve(route):
        request = route.request
        url = urlsplit(request.url)
        path = url.path + ('?' + url.query if url.query else '')
        calls.append((request.method, path))
        headers = {key: value for key, value in request.headers.items() if key not in ('host', 'content-length', 'accept-encoding')}
        response = client.request(request.method, path, headers=headers, content=request.post_data_buffer)
        response_headers = {key: value for key, value in response.headers.items() if key not in ('content-length', 'content-encoding')}
        route.fulfill(status=response.status_code, headers=response_headers, body=response.content)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=browser_executable(), headless=True,
            args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--disable-background-networking'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1000})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route('http://localhost/**', serve)
        page.goto('http://localhost/')
        expect(page.locator('#revision')).to_have_text('v1')
        expect(page.locator('#projects')).not_to_have_value('')
        project_id = page.locator('#projects').input_value()
        original = client.get('/api/projects/' + project_id).json()
        raw_body = original['manifest']['beats'][0]['body']
        assert '{{' in raw_body
        expect(page.locator('#beat-body')).to_have_value(raw_body)
        page.locator('#beat-body').fill(raw_body + '。')
        expect(page.locator('#body-preview')).not_to_contain_text('{{')
        # Structural edits capture typed text but do not save a database revision.
        original_count = page.locator('#beats button').count()
        page.locator('#add-beat').click()
        expect(page.locator('#beats button')).to_have_count(original_count + 1)
        assert client.get('/api/projects/' + project_id).json()['revision'] == 1
        page.locator('#undo').click()
        expect(page.locator('#beats button')).to_have_count(original_count)
        expect(page.locator('#beat-body')).to_have_value(raw_body + '。')
        page.locator('#redo').click()
        expect(page.locator('#beats button')).to_have_count(original_count + 1)
        page.locator('#beats button').first.click()
        page.locator('#part-settings summary').click()
        page.locator('#dim-0').fill('200')
        page.locator('#dim-1').fill('200')
        page.locator('#solid-color').fill('#5276b3')
        page.locator('#editor button[type=submit]').click()
        expect(page.locator('#beat-body')).to_have_value(raw_body + '。')
        assert '200' in page.locator('#body-preview').inner_text()
        page.locator('#video-settings summary').click()
        page.locator('#video-resolution').select_option('2160p')
        page.locator('#video-fps').select_option('60')
        page.locator('#slides-settings summary').click()
        page.locator('#slides-layout').select_option('full')
        page.locator('#save').click()
        expect(page.locator('#revision')).to_have_text('v2')
        stored = client.get('/api/projects/' + project_id).json()['manifest']
        assert stored['beats'][0]['body'] == raw_body + '。'
        assert stored['solids'][0]['size'][0] == 200
        assert stored['solids'][0]['color'] == '#5276b3'
        assert stored['video']['resolution'] == '2160p' and stored['video']['fps'] == 60
        assert stored['slides']['layout'] == 'full'
        assert len([call for call in calls if call[0] == 'POST' and call[1].endswith('/patch')]) == 1
        page.screenshot(path=str(tmp_path / 'editor-restored.png'), full_page=True)
        print('Editor screenshot:', tmp_path / 'editor-restored.png')
        # Native SVG intake applies to the local draft and can be cleared without a save.
        page.locator('#svg-import').set_input_files({'name': 'own-vector.svg', 'mimeType': 'image/svg+xml',
            'buffer': b'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"><rect width="1280" height="720" fill="#ffffff"/><text x="80" y="100">Editable vector</text></svg>'})
        expect(page.locator('#beat-svg-asset')).not_to_have_value('')
        assert client.get('/api/projects/' + project_id).json()['revision'] == 2
        page.locator('#scene-settings').evaluate('(element)=>element.open=true')
        page.locator('#beat-svg-asset').select_option('')
        page.locator('#editor button[type=submit]').click()
        expect(page.locator('#beat-svg-asset')).to_have_value('')
        # Exercise actual pinned WASM serializer and our nested findings UI.
        page.locator('#audit').click()
        expect(page.locator('#audit-result')).to_contain_text('項視覺建議', timeout=30000)
        result = page.evaluate('window.lastStudioAudit')
        expected = sum(len(group['findings']) for group in result['findings'])
        assert page.locator('#audit-result li').count() == expected
        if expected:
            page.locator('#audit-result li button').first.click()
            expect(page.locator('.audit-highlight')).to_have_count(1)
        assert not errors, errors
        assert not any(path.endswith('/render') for _, path in calls)
        browser.close()


def _tiny_glb(*, animated=False, cad=False, second_animation=False):
    """Own two-triangle fixture, not downloaded media; both CAD parts coincide."""
    import base64
    import json
    import struct

    positions = struct.pack('<9f', 0, 0, 0, .1, 0, 0, 0, .1, 0)
    binary = positions
    document = {
        'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0, 1]}],
        'nodes': [{'name': 'original-left', 'mesh': 0}, {'name': 'original-right', 'mesh': 1}],
        'meshes': [{'primitives': [{'attributes': {'POSITION': 0}, 'material': 0}]},
                   {'primitives': [{'attributes': {'POSITION': 0}, 'material': 1}]}],
        'materials': [{'name': 'Red original', 'pbrMetallicRoughness': {'baseColorFactor': [1, 0, 0, 1]}},
                      {'name': 'Blue original', 'pbrMetallicRoughness': {'baseColorFactor': [0, 0, 1, 1]}}],
        'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': len(positions)}],
        'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3', 'min': [0, 0, 0], 'max': [.1, .1, 0]}],
    }
    if cad:
        for node, name in zip(document['nodes'], ['left', 'right']):
            node['extras'] = {'studio_part_id': name}
    if animated:
        times = struct.pack('<2f', 0, 1)
        translation = struct.pack('<6f', .2, 0, 0, .4, 0, 0)
        document['nodes'][1]['translation'] = [.2, 0, 0]
        document['bufferViews'] += [{'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(times)},
                                    {'buffer': 0, 'byteOffset': len(binary) + len(times), 'byteLength': len(translation)}]
        document['accessors'] += [{'bufferView': 1, 'componentType': 5126, 'count': 2, 'type': 'SCALAR', 'min': [0], 'max': [1]},
                                  {'bufferView': 2, 'componentType': 5126, 'count': 2, 'type': 'VEC3'}]
        document['animations'] = [{'name': 'Original motion', 'samplers': [{'input': 1, 'output': 2, 'interpolation': 'LINEAR'}],
                                   'channels': [{'sampler': 0, 'target': {'node': 1, 'path': 'translation'}}]}]
        if second_animation:
            document['animations'].append({'name': 'Second motion', 'samplers': [{'input': 1, 'output': 2, 'interpolation': 'LINEAR'}],
                                           'channels': [{'sampler': 0, 'target': {'node': 0, 'path': 'translation'}}]})
        binary += times + translation
    document['buffers'] = [{'byteLength': len(binary)}]
    encoded = json.dumps(document).encode()
    encoded += b' ' * ((-len(encoded)) % 4)
    binary += b'\0' * ((-len(binary)) % 4)
    total = 12 + 8 + len(encoded) + 8 + len(binary)
    glb = struct.pack('<III', 0x46546C67, 2, total) + struct.pack('<II', len(encoded), 0x4E4F534A) + encoded
    glb += struct.pack('<II', len(binary), 0x004E4942) + binary
    return base64.b64encode(glb).decode()


def test_viewer_cad_identity_and_original_scene_animation():
    from playwright.sync_api import sync_playwright
    from studio.paths import ROOT
    from studio.runtime import browser_executable

    base = {'brand': {'paper': '#ffffff', 'ink': '#222222'}, 'beats': []}
    cad = {**base, 'solids': [{'id': name, 'kind': 'box', 'size': [100, 100, 10], 'position': [0, 0, 0], 'color': color}
                            for name, color in [('left', '#526374'), ('right', '#d48742')]]}
    imported = {**base, 'solids': [], 'scene_asset': 'a' * 64 + '.glb'}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=browser_executable(), headless=True,
            args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--disable-background-networking'])
        page = browser.new_page()
        page.route('**/*', lambda route: route.abort())
        page.set_content('<div id="viewer" style="width:800px;height:600px"></div>')
        page.add_script_tag(path=str(ROOT / 'dist/viewer.js'))
        result = page.evaluate('''async ({manifest,data})=>{
            window.testViewer=window.makeStudioViewer(document.getElementById('viewer'),manifest,{glbData:data,manual:true});
            testViewer.focus(['right']); await testViewer.ready;
            return {mode:testViewer.state.mode,frame:testViewer.renderFrame('orbit',0)};
        }''', {'manifest': cad, 'data': _tiny_glb(cad=True)})
        assert result['mode'] == 'cad-glb'
        parts = {part['id']: part for part in result['frame']['parts']}
        assert parts['left']['opacity'] == .22 and parts['right']['opacity'] == 1
        assert parts['left']['materials'][0]['color'] == '#526374'
        result = page.evaluate('''async ({manifest,data})=>{
            testViewer.dispose();
            window.testViewer=window.makeStudioViewer(document.getElementById('viewer'),manifest,{glbData:data,manual:true});
            testViewer.focus(['not-a-cad-part']); await testViewer.ready;
            const start=testViewer.renderFrame('orbit',0),middle=testViewer.renderFrame('orbit',.5),end=testViewer.renderFrame('orbit',1),reset=testViewer.renderFrame('orbit',0);
            return {mode:testViewer.state.mode,animations:testViewer.state.animations,start,middle,end,reset};
        }''', {'manifest': imported, 'data': _tiny_glb(animated=True)})
        assert result['mode'] == 'scene-glb'
        assert result['animations'][0]['name'] == 'Original motion'
        positions = [next(part for part in result[frame]['parts'] if part['id'] == 'node-1')['position'][0]
                     for frame in ['start', 'middle', 'end', 'reset']]
        assert abs(positions[1] - positions[0] - 100) < .01
        assert abs(positions[2] - positions[0] - 200) < .01
        assert abs(positions[3] - positions[0]) < .01
        assert result['start']['parts'][0]['materials'][0]['name'] == 'Red original'
        assert result['start']['parts'][0]['materials'][0]['color'] == '#ff0000'
        assert result['start']['parts'][0]['opacity'] == 1
        browser.close()


def test_review_regressions_style_scene_fractional_cad_and_large_timeline(tmp_path, monkeypatch):
    import base64
    import json
    from playwright.sync_api import sync_playwright, expect
    from studio.server import create_app
    from studio.runtime import browser_executable

    monkeypatch.setenv('STUDIO_DATA', str(tmp_path))
    client = TestClient(create_app(), base_url='http://localhost')
    calls = []

    def serve(route):
        request = route.request
        url = urlsplit(request.url)
        path = url.path + ('?' + url.query if url.query else '')
        calls.append((request.method, path))
        headers = {key: value for key, value in request.headers.items() if key not in ('host', 'content-length', 'accept-encoding')}
        response = client.request(request.method, path, headers=headers, content=request.post_data_buffer)
        route.fulfill(status=response.status_code,
                      headers={key: value for key, value in response.headers.items() if key not in ('content-length', 'content-encoding')},
                      body=response.content)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=browser_executable(), headless=True,
            args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--disable-background-networking'])
        page = browser.new_page(viewport={'width': 1500, 'height': 1000})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route('http://localhost/**', serve)
        page.goto('http://localhost/')
        expect(page.locator('#projects')).not_to_have_value('')
        page.wait_for_function("()=>document.querySelectorAll('#image-style option').length > 1")
        project_id = page.locator('#projects').input_value()
        raw_body = page.locator('#beat-body').input_value()
        style = page.locator('#image-style option').nth(1).get_attribute('value')
        page.locator('#image-style').evaluate('(element)=>element.closest("details").open=true')
        page.locator('#beat-body').fill(raw_body + '。')
        page.locator('#image-style').select_option(style)
        page.wait_for_function('(style)=>JSON.parse(document.getElementById("json-editor").value).style_id===style', arg=style)
        expect(page.locator('#beat-body')).to_have_value(raw_body + '。')
        page.locator('#beat-body').fill(raw_body + '。！')
        # Even reselecting the existing style must capture, not discard, pending text.
        page.locator('#image-style').dispatch_event('change')
        page.wait_for_function('(text)=>JSON.parse(document.getElementById("json-editor").value).beats[0].body===text', arg=raw_body + '。！')
        expect(page.locator('#beat-body')).to_have_value(raw_body + '。！')
        assert client.get('/api/projects/' + project_id).json()['revision'] == 1

        page.locator('#part-settings').evaluate('(element)=>element.open=true')
        page.locator('#solid-kind').select_option('box')
        page.locator('#dim-0').fill('0')
        assert not page.locator('#dim-0').evaluate('(element)=>element.checkValidity()')
        for index, value in enumerate(['0.125', '0.25', '0.0625']):
            page.locator('#dim-' + str(index)).fill(value)
            assert page.locator('#dim-' + str(index)).evaluate('(element)=>element.checkValidity()')
        page.locator('#pos-0').fill('0.375')
        page.locator('#rot-0').fill('15.125')
        page.locator('#bore').fill('0')
        page.locator('#editor button[type=submit]').click()
        page.wait_for_function('()=>JSON.parse(document.getElementById("json-editor").value).solids[0].size[0]===.125')
        fractional = json.loads(page.locator('#json-editor').input_value())
        assert fractional['solids'][0]['size'] == [.125, .25, .0625]
        assert fractional['solids'][0]['position'][0] == .375
        assert fractional['solids'][0]['rotation'][0] == 15.125
        preserved_solids = fractional['solids']

        page.locator('#scene-import').set_input_files({'name': 'own-scene.glb', 'mimeType': 'model/gltf-binary',
                                                      'buffer': base64.b64decode(_tiny_glb(animated=True, second_animation=True))})
        expect(page.locator('#imported-scene')).not_to_have_value('', timeout=30000)
        imported = json.loads(page.locator('#json-editor').input_value())
        asset = imported['scene_asset']
        assert all(not beat['focus'] for beat in imported['beats'])
        assert 'cad' not in imported['output_targets']
        assert imported['solids'] == preserved_solids
        assert imported['beats'][0]['visual']['mode'] == 'orbit'
        expect(page.locator('#scene-animation')).to_be_enabled()
        expect(page.locator('#scene-animation option')).to_have_count(2)
        expect(page.locator('#scene-animation option').nth(1)).to_have_text('Second motion · 1.0 秒')
        expect(page.locator('#source-scope')).to_contain_text('參數圖解、尺寸表與 CAD 檔')
        assert client.get('/api/projects/' + project_id).json()['revision'] == 1

        # A saved asset selected through the dropdown must clear every chapter's CAD focus too.
        restored = imported.copy()
        restored['scene_asset'] = None
        restored['output_targets'] = ['web', 'cad']
        for beat in restored['beats']:
            beat['focus'] = [preserved_solids[0]['id']]
        page.locator('#json-editor').evaluate('(element)=>element.closest("details").open=true')
        page.locator('#json-editor').fill(json.dumps(restored))
        page.locator('#apply-json').click()
        expect(page.locator('#imported-scene')).to_have_value('')
        page.locator('#scene-import-settings').evaluate('(element)=>element.open=true')
        page.locator('#imported-scene').select_option(asset)
        page.locator('#editor button[type=submit]').click()
        page.wait_for_function('(asset)=>JSON.parse(document.getElementById("json-editor").value).scene_asset===asset', arg=asset)
        selected = json.loads(page.locator('#json-editor').input_value())
        assert all(not beat['focus'] for beat in selected['beats'])
        assert 'cad' not in selected['output_targets']
        assert selected['solids'] == preserved_solids
        expect(page.locator('#scene-animation')).to_have_value('0')
        page.locator('#scene-animation').select_option('1')

        # An explicit later request for separate CAD output survives ordinary editing.
        page.locator('#output-settings').evaluate('(element)=>element.open=true')
        page.locator('[data-target="cad"]').check()
        page.wait_for_function('()=>JSON.parse(document.getElementById("json-editor").value).output_targets.includes("cad")')
        page.locator('#subtitle').fill('獨立保留的 CAD 與 GLB 場景')
        page.locator('#editor button[type=submit]').click()
        page.wait_for_function('()=>JSON.parse(document.getElementById("json-editor").value).subtitle==="獨立保留的 CAD 與 GLB 場景"')
        assert 'cad' in json.loads(page.locator('#json-editor').input_value())['output_targets']
        page.locator('#save').click()
        expect(page.locator('#revision')).to_have_text('v2')
        assert client.get('/api/projects/' + project_id).json()['manifest']['scene_animation'] == 1
        page.reload()
        expect(page.locator('#projects')).to_have_value(project_id)
        expect(page.locator('#scene-animation')).to_have_value('1')

        # Valid interchange above the previous 2 MiB ceiling reaches the revision-protected API.
        timeline = client.get('/api/projects/' + project_id + '/timeline').json()
        timeline['timeline']['segments'][0]['title'] = '大型時間軸匯入'
        payload = json.dumps(timeline).encode() + b' ' * (3 * 1024 * 1024)
        page.locator('#import-timeline').set_input_files({'name': 'large-timeline.json', 'mimeType': 'application/json', 'buffer': payload})
        expect(page.locator('#beat-title')).to_have_value('大型時間軸匯入', timeout=30000)
        assert ('PUT', '/api/projects/' + project_id + '/timeline') in calls
        assert client.get('/api/projects/' + project_id).json()['revision'] == 2
        page.locator('#scene-import').set_input_files({'name': 'static-scene.glb', 'mimeType': 'model/gltf-binary',
                                                      'buffer': base64.b64decode(_tiny_glb())})
        expect(page.locator('#scene-animation')).to_be_disabled()
        expect(page.locator('#scene-animation option')).to_have_text('無動畫')
        static = json.loads(page.locator('#json-editor').input_value())
        assert static['scene_asset'] != asset
        assert static['scene_animation'] == 0
        assert client.get('/api/projects/' + project_id).json()['revision'] == 2
        assert not errors, errors
        assert not any(path.endswith('/render') for _, path in calls)
        browser.close()
