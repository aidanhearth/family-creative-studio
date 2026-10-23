"""A separate process imports cadgen/OCP; the API process never loads CAD kernels."""
import json
from pathlib import Path
import sys
import os
import math
from cadgen import step, glb, stl, build123d as bd

if len(sys.argv)>2:
    os.environ['STUDIO_CAD_MANIFEST']=sys.argv[1]
    os.environ['STUDIO_CAD_OUTPUT']=sys.argv[2]
manifest=Path(os.environ['STUDIO_CAD_MANIFEST']).resolve()
out=Path(os.environ['STUDIO_CAD_OUTPUT']).resolve()
data=json.loads(manifest.read_text())
# cadgen's source-program entry parses its own optional flags. Adapter arguments are consumed.
sys.argv=[sys.argv[0], '--force']

@glb(out=str(out/'model.glb'))
@stl(out=str(out/'model.stl'))
@step(out=str(out/'model.step'))
def model():
    parts=[]
    for s in data['solids']:
        w,d,h=s['size']
        part=bd.Box(w,d,h) if s['kind']=='box' else bd.Cylinder(w/2,h)
        if s['bore']:
            part=part-bd.Cylinder(s['bore']/2,h+2)
        part=part.moved(bd.Location(tuple(s['position'])))
        part.label=s['id'];part.color=bd.Color(s['color'])
        parts.append(part)
    return bd.Compound(children=parts,label=data['id'])

if __name__=='__main__':
    model()
    # Re-open the actual exported STEP; do not validate only the source shape.
    saved=bd.import_step(out/'model.step')
    box=saved.bounding_box()
    expected_volume=sum((s['size'][0]*s['size'][1] if s['kind']=='box' else math.pi*(s['size'][0]/2)**2)*s['size'][2] - math.pi*(s['bore']/2)**2*s['size'][2] for s in data['solids'])
    expected_min=[min(s['position'][axis]-s['size'][axis]/2 for s in data['solids']) for axis in range(3)]
    expected_max=[max(s['position'][axis]+s['size'][axis]/2 for s in data['solids']) for axis in range(3)]
    if not math.isclose(saved.volume,expected_volume,rel_tol=1e-7,abs_tol=.01):
        raise RuntimeError('STEP volume does not match declared primitives and bores')
    if any(abs(a-b)>.01 for a,b in zip(list(box.min)+list(box.max),expected_min+expected_max)):
        raise RuntimeError('STEP bounds do not match declared dimensions')
    result={'expected_volume_mm3':expected_volume,'volume_error_mm3':saved.volume-expected_volume,'valid':bool(saved.is_valid),'solids':len(saved.solids()),'volume_mm3':saved.volume,
            'bounds_mm':{'min':list(box.min),'max':list(box.max)},'source_dimensions':[{k:s[k] for k in ('id','size','position','bore')} for s in data['solids']]}
    if not result['valid'] or result['solids']!=len(data['solids']) or result['volume_mm3']<=0:
        raise RuntimeError('Exported STEP failed topology checks')
    (out/'cad-check.json').write_text(json.dumps(result,indent=2,allow_nan=False))
