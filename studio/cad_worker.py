"""Separate CAD process: build, export and re-open actual resulting geometry."""
import json
import math
import os
from pathlib import Path
import sys

from cadgen import build123d as bd
from studio.geometry_kernel import bounds, build_parts, geometry_document
from studio.geometry_glb import annotate_parts
from studio.geometry_stl import inspect_stl
from studio.schema import Manifest

if len(sys.argv) > 2:
    os.environ['STUDIO_CAD_MANIFEST'] = sys.argv[1]
    os.environ['STUDIO_CAD_OUTPUT'] = sys.argv[2]
manifest_path = Path(os.environ['STUDIO_CAD_MANIFEST']).resolve()
out = Path(os.environ['STUDIO_CAD_OUTPUT']).resolve()
manifest = Manifest.model_validate_json(manifest_path.read_text())
parts = build_parts(manifest.solids, out / 'cad-assets')
if not parts:
    raise ValueError('CAD export requires at least one deliverable solid')
assembly = bd.Compound(children=[part for _, part in parts], label=manifest.id)
mesh_tolerance = max(.00001, min(.01, min(min(s['size']) for s, _ in parts) / 10000))
if __name__ == '__main__':
    if not bd.export_step(assembly, out / 'model.step'):
        raise RuntimeError('STEP export failed')
    if not bd.export_stl(assembly, out / 'model.stl', tolerance=mesh_tolerance, angular_tolerance=.1):
        raise RuntimeError('STL export failed')
    if not bd.export_gltf(assembly, out / 'model.glb', binary=True, linear_deflection=mesh_tolerance, angular_deflection=.1):
        raise RuntimeError('GLB export failed')
    annotate_parts(out / 'model.glb', [s['id'] for s, _ in parts])
    saved = bd.import_step(out / 'model.step')
    expected = bounds(assembly)
    actual = bounds(saved)
    if not math.isclose(saved.volume, assembly.volume, rel_tol=1e-7, abs_tol=.01):
        raise RuntimeError('STEP round-trip volume differs from constructed CAD')
    if any(abs(a - b) > .01 for a, b in zip(actual['min'] + actual['max'], expected['min'] + expected['max'])):
        raise RuntimeError('STEP round-trip bounds differ from constructed CAD')
    if not saved.is_valid or len(saved.solids()) != len(assembly.solids()) or saved.volume <= 0:
        raise RuntimeError('Exported STEP failed topology checks')
    stl_check = inspect_stl(out / 'model.stl')
    if not math.isclose(stl_check['volume_mm3'], assembly.volume, rel_tol=.003, abs_tol=.001):
        raise RuntimeError('STL mesh volume differs from constructed CAD')
    if any(abs(a - b) > max(.02, mesh_tolerance * 3) for a, b in zip(stl_check['bounds_mm']['min'] + stl_check['bounds_mm']['max'], expected['min'] + expected['max'])):
        raise RuntimeError('STL mesh bounds differ from constructed CAD')
    geometry = geometry_document(parts)
    result = {
        'expected_volume_mm3': assembly.volume, 'volume_error_mm3': saved.volume - assembly.volume,
        'valid': bool(saved.is_valid), 'solids': len(saved.solids()), 'volume_mm3': saved.volume,
        'bounds_mm': actual, 'part_ids': [s['id'] for s, _ in parts],
        'source_dimensions': [{k: s[k] for k in ('id', 'size', 'position', 'rotation', 'bore')} for s, _ in parts],
        'parts': [{k: p[k] for k in ('id', 'kind', 'bounds_mm', 'volume_mm3', 'solid_count', 'valid')} for p in geometry['parts']],
        'validation_basis': 'constructed post-operation CAD and exported STEP re-import',
        'stl': stl_check, 'mesh_tolerance_mm': mesh_tolerance,
    }
    (out / 'geometry.json').write_text(json.dumps(geometry, separators=(',', ':'), allow_nan=False))
    (out / 'cad-check.json').write_text(json.dumps(result, indent=2, allow_nan=False))
