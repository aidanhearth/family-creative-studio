"""Geometry contracts and exact kernel results; no external process or export."""
import math
from pathlib import Path

import pytest
from pydantic import ValidationError
from studio.schema import Solid, Manifest, DiagramSpec, EffectSettings
from studio.geometry_profile import validate_profile


def solid(**changes):
    return Solid.model_validate(dict(id='part', name='Part', size=[10, 20, 30], **changes)) if 'size' not in changes else Solid.model_validate(dict(id='part', name='Part', **changes))


def document(solids, **changes):
    return Manifest.model_validate(dict(id='demo', title='Demo', subtitle='Demo', solids=solids,
        beats=[dict(id='chapter', title='Chapter', body='Body', narration='Narration')], **changes))


@pytest.mark.parametrize('spec', [
    {'kind': 'sphere', 'size': [10, 10, 12]},
    {'kind': 'cone', 'size': [10, 10, 12], 'top_diameter': 11},
    {'kind': 'torus', 'size': [20, 20, 10]},
    {'fillet': 1, 'chamfer': 1},
    {'kind': 'step'},
    {'rotation': [0, float('nan'), 0]},
])
def test_invalid_geometry_contract(spec):
    with pytest.raises(ValidationError):
        solid(**spec)


def test_polygon_rejects_crossings_and_accepts_concave():
    validate_profile([(-.5,-.5),(.5,-.5),(.5,0),(0,0),(0,.5),(-.5,.5)])
    with pytest.raises(ValueError):
        validate_profile([(-.5,-.5),(.5,.5),(-.5,.5),(.5,-.5)])
    with pytest.raises(ValueError):
        validate_profile([(-.5,-.5),(.5,-.5),(0,0)])


def test_boolean_references_are_acyclic_by_document_order():
    tool = solid(construction=True).model_dump()
    target = solid().model_dump(); target['id'] = 'target'
    target['booleans'] = [{'operation': 'subtract', 'tool': 'part'}]
    assert len(document([tool, target]).solids) == 2
    with pytest.raises(ValidationError, match='preceding'):
        document([target, tool])
    with pytest.raises(ValidationError, match='deliverable'):
        document([tool])


def test_shared_media_contract_and_limits():
    data = document([]).model_dump()
    data['beats'][0].update(narration='', narration_asset='a'*64+'.wav', duration=.1)
    data['narration_asset'] = 'b'*64+'.wav'
    data['beats'].append(dict(id='clip', title='Clip', body='Clip', narration='', duration=600,
        visual=dict(mode='clip',asset='c'*64+'.mp4',audio='source',start=1000)))
    result = Manifest.model_validate(data)
    assert result.video.resolution == 'source' and result.video.fps == 'source'
    assert result.slides.narration and result.slides.autoplay
    data['beats'][1]['visual']['audio'] = 'mix'
    assert Manifest.model_validate(data).beats[1].visual.source_gain == 1
    data['beats'][1]['visual']['voice_gain'] = float('inf')
    with pytest.raises(ValidationError):
        Manifest.model_validate(data)


def test_diagram_and_effect_bounds():
    assert DiagramSpec(kind='architecture', document={'nodes': []}).kind == 'architecture'
    nested = {}; target = nested
    for _ in range(22):
        target['next'] = {}; target = target['next']
    with pytest.raises(ValidationError, match='nesting'):
        DiagramSpec(kind='architecture', document=nested)
    with pytest.raises(ValidationError):
        EffectSettings(opacity=float('nan'))


def test_glb_annotation_preserves_binary_buffers_and_nested_identity(tmp_path):
    import json
    import struct
    from studio.geometry_glb import annotate_parts
    doc = {'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [
        {'name': 'assembly', 'children': [1]}, {'name': 'part', 'children': [2]}, {'name': 'internal', 'mesh': 0}]}
    js = json.dumps(doc).encode(); js += b' ' * (-len(js) % 4)
    binary = b'fixed binary mesh buffer'
    body = struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(binary),0x004E4942)+binary
    target = tmp_path/'model.glb'; target.write_bytes(struct.pack('<4sII',b'glTF',2,len(body)+12)+body)
    annotate_parts(target,['part'])
    data = target.read_bytes(); length = struct.unpack_from('<I',data,12)[0]
    result = json.loads(data[20:20+length])
    assert result['nodes'][1]['extras']['studio_part_id'] == 'part'
    assert data[-len(binary):] == binary
    with pytest.raises(ValueError,match='identities'):
        annotate_parts(target,['missing'])


def test_rotated_geometry_uses_actual_bounds():
    from studio.geometry_kernel import build_parts, bounds
    part = build_parts([solid(rotation=[0,0,90])], Path('/tmp'))[0][1]
    b = bounds(part)
    assert part.volume == pytest.approx(6000)
    assert b['max'] == pytest.approx([10,5,15])
    assert b['min'] == pytest.approx([-10,-5,-15])


@pytest.mark.parametrize('spec,volume', [
    ({'kind':'sphere','size':[20,20,20]}, 4/3*math.pi*10**3),
    ({'kind':'cone','size':[20,20,30]}, math.pi*10**2*30/3),
    ({'kind':'cone','size':[20,20,30],'top_diameter':20}, math.pi*10**2*30),
    ({'kind':'torus','size':[30,30,6]}, 2*math.pi**2*12*3**2),
    ({'kind':'extrusion','size':[10,20,30],'profile':[[-.5,-.5],[.5,-.5],[.5,0],[0,0],[0,.5],[-.5,.5]]}, 4500),
])
def test_curved_and_concave_shapes_are_real_geometry(spec, volume):
    from studio.geometry_kernel import build_parts
    part = build_parts([solid(**spec)], Path('/tmp'))[0][1]
    assert part.is_valid and part.volume == pytest.approx(volume, rel=1e-7)


@pytest.mark.parametrize('operation,volume', [('subtract', 3000), ('union',9000), ('intersect',3000)])
def test_boolean_operations_use_world_coordinates(operation,volume):
    from studio.geometry_kernel import build_parts
    tool = solid(construction=True, position=[5,0,0])
    body = solid(booleans=[{'operation':operation,'tool':'part'}]).model_dump(); body['id']='body'
    parts = build_parts([tool, Solid.model_validate(body)], Path('/tmp'))
    assert len(parts) == 1 and parts[0][0]['id'] == 'body'
    assert parts[0][1].volume == pytest.approx(volume)


@pytest.mark.parametrize('operation', ['fillet', 'chamfer'])
def test_edge_treatment_changes_actual_topology(operation):
    from studio.geometry_kernel import build_parts
    part = build_parts([solid(**{operation:1})], Path('/tmp'))[0][1]
    assert part.is_valid and 5000 < part.volume < 6000
    assert len(part.faces()) > 6


def test_clockwise_profile_keeps_centered_positive_extrusion():
    from studio.geometry_kernel import build_parts, bounds
    profile=[[-.5,-.5],[-.5,.5],[.5,.5],[.5,-.5]]
    part=build_parts([solid(kind='extrusion',profile=profile)],Path('/tmp'))[0][1]
    assert bounds(part)['min']==pytest.approx([-5,-10,-15])
    assert bounds(part)['max']==pytest.approx([5,10,15])
