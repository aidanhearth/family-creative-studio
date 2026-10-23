import pytest
from studio.seed import demo
from studio.operations import apply_operations,patch_project
from studio.store import Store,Conflict

def test_atomic_stable_id_edit_and_noop(tmp_path):
    s=Store(tmp_path);d=demo();s.save(d)
    p=patch_project(s,d.id,1,[{'op':'set','target':'solid','id':'tray','values':{'bore':64}}])
    assert p['revision']==2 and p['changes'][0]['path']=='solids.tray.bore'
    assert patch_project(s,d.id,2,[{'op':'set','target':'solid','id':'tray','values':{'bore':64}}])['revision']==2
    with pytest.raises(Conflict):patch_project(s,d.id,1,[{'op':'set','target':'project','values':{'title':'stale'}}])

def test_invalid_batch_never_partially_saves(tmp_path):
    s=Store(tmp_path);d=demo();s.save(d)
    with pytest.raises(ValueError):patch_project(s,d.id,1,[{'op':'set','target':'project','values':{'title':'changed'}},{'op':'set','target':'solid','id':'tray','values':{'bore':500}}])
    assert s.project(d.id)['revision']==1 and s.project(d.id)['manifest']['title']==d.title

def test_remove_freezes_only_removed_dimension_links():
    d=demo();out=apply_operations(d,[{'op':'remove','target':'solid','id':'tray'}])
    assert len(out.solids)==2 and '{{tray.' not in out.canonical()
    assert '{{base.size}}' in out.canonical() and '60毫米' in out.beats[1].narration

def test_add_move_and_reject_missing_object():
    d=demo();new=d.beats[0].model_dump();new['id']='chapter-four'
    out=apply_operations(d,[{'op':'add','target':'beat','values':new},{'op':'move','target':'beat','id':'chapter-four','index':0}])
    assert out.beats[0].id=='chapter-four'
    with pytest.raises(ValueError):apply_operations(d,[{'op':'set','target':'beat','id':'missing','values':{'title':'no'}}])

def test_dry_run_does_not_save(tmp_path):
    s=Store(tmp_path);d=demo();s.save(d)
    out=patch_project(s,d.id,1,[{'op':'set','target':'project','values':{'title':'proposal'}}],dry_run=True)
    assert not out['saved'] and out['changes'] and s.project(d.id)['revision']==1
