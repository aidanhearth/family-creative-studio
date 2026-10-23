import base64
import copy
import pytest
from studio.seed import demo
from studio.store import Store, Conflict
from studio.svg_assets import import_svg, normalized_svg
from studio.agent_assets import import_inline, asset_path
from studio.timeline import export_timeline, import_timeline

SVG=b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="10 20 800 600" fill="#123456"><rect x="10" y="20" width="800" height="600"/><text x="50" y="100">Editable</text></svg>'


def test_svg_preserves_source_and_inherited_vector_style(tmp_path):
    store=Store(tmp_path)
    result=import_inline(store,'svg',base64.b64encode(SVG).decode(),'art.svg')
    assert asset_path(store,result['asset']).read_bytes()==SVG
    normalized=normalized_svg(SVG)
    assert '0 0 1280 720' in normalized and '#123456' in normalized and 'Editable' in normalized


@pytest.mark.parametrize('attack',[
    b'<script>alert(1)</script>',b'<image href="file:///etc/passwd"/>',b'<use href="https://example.org/x.svg#x"/>',
    b'<rect onload="alert(1)"/>',b'<style>@import "https://example.org/";</style>',b'<rect fill="url(file:///etc/passwd)"/>'
    ,br'<rect style="fill:u\72l(https://example.invalid/p.svg#x)"/>'
])
def test_svg_import_rejects_active_or_external_content(tmp_path,attack):
    with pytest.raises(ValueError):import_svg(Store(tmp_path),b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'+attack+b'</svg>')


def test_timeline_roundtrip_keeps_tokens_and_cas(tmp_path):
    store=Store(tmp_path);original=demo();store.save(original)
    document=export_timeline(store,original.id)['timeline']
    document['segments'].reverse();document['segments'][0]['duration']=4
    document['video']['resolution']='2160p'
    preview=import_timeline(store,original.id,1,document,True)
    assert not preview['saved'] and store.project(original.id)['revision']==1
    result=import_timeline(store,original.id,1,document)
    assert result['revision']==2 and '{{tray.bore}}' in str(result['manifest'])
    with pytest.raises(Conflict):import_timeline(store,original.id,1,document)
    with pytest.raises(Conflict):import_timeline(store,original.id,2,document)


def test_early_contrast_failure_does_not_start_engine_inspection(tmp_path,monkeypatch):
    store=Store(tmp_path);m=demo();m.brand.ink=m.brand.paper;store.save(m)
    monkeypatch.setattr('studio.provenance.engine_fingerprint',lambda:pytest.fail('Expensive inspection should not start'))
    with pytest.raises(ValueError,match='contrast'):store.enqueue(m.id)


def test_asset_paths_cannot_escape(tmp_path):
    store=Store(tmp_path)
    for name in ('../secret','a'*64+'.html','/etc/passwd'):
        with pytest.raises(ValueError):asset_path(store,name)
