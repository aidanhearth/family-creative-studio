"""Actual CAD export/reimport checks, isolated to temporary project directories."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

import pytest
from cadgen import build123d as bd
from studio.paths import ROOT
from studio.schema import Manifest


def test_all_shapes_export_with_stable_ids_and_actual_measurements(tmp_path):
    specs = [
        dict(id='rotated',name='Rotated',size=[10,20,30],rotation=[0,0,45],fillet=1),
        dict(id='sphere',name='Sphere',kind='sphere',size=[12,12,12],position=[30,0,0]),
        dict(id='cone',name='Cone',kind='cone',size=[16,16,20],top_diameter=6,position=[50,0,0]),
        dict(id='torus',name='Torus',kind='torus',size=[24,24,5],position=[80,0,0]),
        dict(id='extruded',name='Extruded',kind='extrusion',size=[12,18,10],position=[0,40,0],profile=[[-.5,-.5],[.5,-.5],[.5,0],[0,0],[0,.5],[-.5,.5]]),
        dict(id='cutter',name='Cutter',kind='cylinder',size=[5,5,30],position=[30,40,0],construction=True),
        dict(id='bored',name='Bored',size=[20,20,10],position=[30,40,0],booleans=[dict(operation='subtract',tool='cutter')]),
    ]
    # A multi-solid STEP becomes one stable semantic part with multiple meshes.
    imported = bd.Compound(children=[bd.Box(5,5,5).moved(bd.Location((-5,0,0))), bd.Sphere(2).moved(bd.Location((5,0,0)))])
    source = tmp_path / 'input.step'
    bd.export_step(imported, source)
    key = hashlib.sha256(source.read_bytes()).hexdigest() + '.step'
    assets = tmp_path / 'cad-assets'; assets.mkdir(); source.rename(assets / key)
    specs.append(dict(id='imported',name='Imported',kind='step',asset=key,size=list(imported.bounding_box().size),position=[60,40,0],rotation=[20,0,30]))
    m = Manifest.model_validate(dict(id='geometry',title='Geometry',subtitle='Geometry',solids=specs,beats=[dict(id='chapter',title='Chapter',body='Body',narration='Narration')]))
    manifest = tmp_path / 'manifest.json'; manifest.write_text(m.canonical())
    subprocess.run([sys.executable,'-m','studio.cad_worker',manifest,tmp_path],cwd=ROOT,check=True,timeout=120,env=dict(os.environ,CADGEN_TELEMETRY='0',CADGEN_UPDATE_CHECK='0'))
    check = json.loads((tmp_path / 'cad-check.json').read_text())
    assert check['valid'] and check['solids'] == 8
    assert len(check['parts']) == 7 and 'cutter' not in check['part_ids']
    assert check['stl']['volume_mm3'] == pytest.approx(check['volume_mm3'],rel=.003)
    geometry = json.loads((tmp_path / 'geometry.json').read_text())
    assert geometry['units'] == 'mm'
    assert all(p['valid'] and p['triangles'] for p in geometry['parts'])
    glb = json.loads(subprocess.check_output(['node',ROOT/'scripts/glb-check.mjs',tmp_path/'model.glb'],cwd=ROOT,text=True,timeout=30))
    assert set(glb['names']) == set(check['part_ids'])
    assert glb['volume_m3'] * 1e9 == pytest.approx(check['volume_mm3'],rel=.003)
    by_id = {p['id']:p for p in check['parts']}
    for part in glb['parts']:
        assert part['volume_m3'] * 1e9 == pytest.approx(by_id[part['id']]['volume_mm3'],rel=.003)
    subprocess.run(['node',ROOT/'scripts/anatomy.mjs',manifest,tmp_path/'focus.svg',tmp_path/'geometry.json','["torus"]'],cwd=ROOT,check=True,timeout=30)
    svg = (tmp_path/'focus.svg').read_text()
    assert 'data-part-id="torus"' in svg and 'data-focus-state="muted"' in svg
    assert 'data-part-id="cutter"' not in svg


def test_imported_step_metadata_and_size_mismatch(tmp_path):
    from studio.geometry_kernel import imported_step
    from studio.cad_inspect import inspect
    source = tmp_path/'input.step'; bd.export_step(bd.Box(10,20,30),source)
    key = hashlib.sha256(source.read_bytes()).hexdigest()+'.step'; target = tmp_path/key; source.rename(target)
    assert inspect(target)['size_mm'] == pytest.approx([10,20,30])
    with pytest.raises(ValueError,match='declared size'):
        imported_step(target,[10,20,10])
    target.write_bytes(target.read_bytes()+b'\n')
    with pytest.raises(ValueError,match='identifier'):
        imported_step(target,[10,20,30])
