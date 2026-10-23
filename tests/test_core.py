import json
from pathlib import Path
import pytest
from studio.schema import Manifest
from studio.seed import demo
from studio.store import Store,Conflict
from studio.paths import contained,sha256

def test_dimension_changes_flow_to_all_text():
    doc=demo();doc.solids[2].bore=64
    resolved=doc.resolved()
    assert '64mm' in resolved.beats[1].body
    assert '64毫米' in resolved.beats[1].narration
    assert '{{' not in resolved.canonical()

@pytest.mark.parametrize('path',['../../escape','/tmp/escape','child/../../../escape'])
def test_paths_are_contained(tmp_path,path):
    with pytest.raises(ValueError):contained(tmp_path,path)

def test_symlink_escape(tmp_path):
    (tmp_path/'link').symlink_to(tmp_path.parent,target_is_directory=True)
    with pytest.raises(ValueError):contained(tmp_path,'link/escape')

def test_revisions_and_immutable_retry(tmp_path):
    store=Store(tmp_path);doc=demo();store.save(doc)
    job=store.enqueue(doc.id,['web']);doc.title='Changed'
    with pytest.raises(Conflict):store.save(doc)
    store.save(doc,1)
    with pytest.raises(Conflict):store.save(doc,1)
    assert store.job(job['id'])['snapshot']['title']!='Changed'
    store.claim();store.update(job['id'],state='failed',error='controlled')
    retry=store.retry(job['id'])
    assert retry['snapshot']==job['snapshot'] and retry['revision']==1

def test_cache_verifies_bytes_not_names(tmp_path):
    store=Store(tmp_path);doc=demo();store.save(doc);job=store.enqueue(doc.id,['web'])
    out=store.artifact_root(job);out.mkdir(parents=True);(out/'index.html').write_text('good')
    store.claim();store.update(job['id'],state='succeeded',artifacts=[{'path':'index.html','sha256':sha256(out/'index.html'),'bytes':4}])
    cached=store.enqueue(doc.id,['web']);assert cached['reused_from']==job['id']
    twice=store.enqueue(doc.id,['web']);assert twice['reused_from']==job['id']
    assert store.valid_artifacts(twice)
    (out/'index.html').write_text('tampered')
    assert store.enqueue(doc.id,['web'])['state']=='queued'

def test_queued_cancel_and_recovery(tmp_path):
    store=Store(tmp_path);doc=demo();store.save(doc)
    cancelled=store.enqueue(doc.id,['web']);store.cancel(cancelled['id']);assert store.claim() is None
    active=store.enqueue(doc.id,['web']);assert store.claim()['id']==active['id'];store.recover()
    assert store.job(active['id'])['state']=='interrupted'

@pytest.mark.parametrize('change',[{'size':[float('nan'),20,12]},{'bore':90},{'kind':'cylinder','size':[50,60,10]}])
def test_bad_geometry_rejected(change):
    raw=demo().model_dump();raw['solids'][2].update(change)
    with pytest.raises(ValueError):Manifest.model_validate(raw)


def test_concurrent_duplicate_and_publication_cancel(tmp_path):
    store=Store(tmp_path);doc=demo();store.save(doc)
    first=store.enqueue(doc.id,['web']);second=store.enqueue(doc.id,['web'])
    assert first['id']==second['id']
    store.claim();store.cancel(first['id'])
    assert not store.publish(first['id'],[{'path':'unexpected'}])
    assert store.job(first['id'])['state']!='succeeded'

def test_terminal_publication_survives_shutdown(tmp_path):
    store=Store(tmp_path);doc=demo();store.save(doc);job=store.enqueue(doc.id,['web']);store.claim()
    assert store.publish(job['id'],[{'path':'index.html','sha256':'verified'}])
    for state in ('interrupted','failed','cancelled'):
        store.update(job['id'],state=state,error='late signal')
        assert store.job(job['id'])['state']=='succeeded'

def test_private_state_permissions(tmp_path):
    tmp_path.chmod(0o755);store=Store(tmp_path)
    assert (tmp_path.stat().st_mode&0o777)==0o700
    assert (store.db.stat().st_mode&0o777)==0o600

def test_sources_drift_is_rejected(tmp_path,monkeypatch):
    import studio.provenance as p
    entries=p.sources();entries[2]['commit']='0'*40
    monkeypatch.setattr(p,'sources',lambda:entries)
    store=Store(tmp_path);doc=demo();store.save(doc)
    with pytest.raises(ValueError,match='sources_drift'):store.enqueue(doc.id,['web'])

def test_caption_paragraphs_do_not_break_srt():
    from studio.pipeline import caption_text
    assert caption_text('第一行\n\n第二行\r\n第三行')=='第一行 第二行 第三行'

def test_runner_environment_is_minimal(tmp_path,monkeypatch):
    from studio.runner import Runner
    monkeypatch.setenv('TEST_PROVIDER_SECRET','never-forward')
    runner=Runner(Store(tmp_path),{'id':'fake'},tmp_path)
    assert 'TEST_PROVIDER_SECRET' not in runner.env
    assert runner.env['ARCHIFY_UPDATE_CHECK_DISABLED']=='1'
    assert runner.env['CADGEN_UPDATE_CHECK']=='0'


def test_long_cjk_title_does_not_overlap_diagram():
    from studio.content import slide_svg
    import cairosvg,io
    from PIL import Image
    doc=demo().resolved();doc.beats[0].title='讓每一段設計都能完整清楚展現原本尺寸與結構的細節與美好'
    svg=slide_svg(doc,doc.beats[0],0,'')
    image=Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode()))).convert('RGB')
    from PIL import ImageColor
    paper=ImageColor.getrgb(doc.brand.paper)
    assert image.crop((510,175,800,290)).getextrema()==tuple((v,v) for v in paper)

def test_queued_job_rejects_converter_change(tmp_path,monkeypatch):
    import studio.pipeline as p
    store=Store(tmp_path);doc=demo();store.save(doc);job=store.enqueue(doc.id,['web']);store.claim()
    monkeypatch.setattr(p,'engine_fingerprint',lambda:'changed-converter')
    with pytest.raises(p.EngineChanged,match='engine_changed'):p.build(store,job)
    assert not (store.root/'runs').exists()

def test_runtime_sources_reject_untracked_shadow(monkeypatch):
    import studio.provenance as p
    original=p.subprocess.check_output
    def call(args,**kwargs):
        if 'ls-files' in args:return 'skills/ppt-master/scripts/pptx/__init__.py\n'
        return original(args,**kwargs)
    monkeypatch.setattr(p.subprocess,'check_output',call)
    with pytest.raises(ValueError,match='sources_drift'):p.runtime_sources()
