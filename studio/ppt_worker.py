"""Execute the fixed upstream SVG-to-DrawingML engine in an isolated child."""
from pathlib import Path
import json
import sys
from .paths import SOURCES

out=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(SOURCES/'hugohe3--ppt-master/skills/ppt-master/scripts'))
from svg_to_pptx.pptx_package.builder import create_pptx_with_native_svg
from svg_to_pptx.drawingml.theme_fonts import MasterTextStyleSpec
from pptx import Presentation
from xml.etree import ElementTree as ET
from .presentation_svg import native_presentation_svg
from .paths import contained

manifest=json.loads((out/'manifest.json').read_text())
svg_dir=out/'ppt-svg';svg_dir.mkdir(exist_ok=True)
ET.register_namespace('','http://www.w3.org/2000/svg')
svgs=[]
backgrounds={}
for i in range(len(manifest['beats'])):
    svg_asset=manifest['beats'][i].get('svg_asset')
    root=(native_presentation_svg(contained(out/'assets',svg_asset).read_bytes()) if svg_asset
          else ET.fromstring((out/'slides'/f'{i:02d}.svg').read_bytes()))
    root.set('data-pptx-master','studio');root.set('data-pptx-master-name','Studio Brand')
    root.set('data-pptx-layout','content');root.set('data-pptx-layout-name','Editable Content')
    # Only our generated slides have a known opaque full-canvas rectangle.
    # Imported rectangles may have transforms, strokes or inherited opacity;
    # retain them as native shapes. Their normalized transforms also prevent
    # upstream background promotion from leaving a dangling animation spTgt.
    for element in ([] if svg_asset else list(root)):
        if element.tag.rsplit('}',1)[-1] in ('title','desc','defs'):continue
        if (element.tag.rsplit('}',1)[-1]=='rect' and element.get('x','0')=='0' and element.get('y','0')=='0'
            and element.get('width')=='1280' and element.get('height')=='720'
            and element.get('opacity','1')=='1' and element.get('fill-opacity','1')=='1'
            and len(element.get('fill',''))==7 and element.get('fill','').startswith('#')):
            backgrounds[i]=element.get('fill');root.remove(element)
        break
    used={element.get('id') for element in root.iter()}
    for n,element in enumerate(root):
        if not element.get('id'):
            identity=f'studio-slide-{i}-shape-{n}'
            while identity in used:identity+='-x'
            element.set('id',identity);used.add(identity)
    path=svg_dir/f'{i:02d}.svg';path.write_text(ET.tostring(root,encoding='unicode'));svgs.append(path)
notes={p.stem:manifest['beats'][i]['narration'] for i,p in enumerate(svgs)}
settings=manifest['slides']
audio={p.stem:out/'audio'/f'{i:02d}.wav' for i,p in enumerate(svgs) if settings['narration'] and (out/'audio'/f'{i:02d}.wav').is_file()}
ok=create_pptx_with_native_svg(svgs,out/'presentation.pptx',resource_root=out,
    verbose=False,use_native_shapes=True,pptx_structure='structured',notes=notes,workers=1,
    transition=None if settings['transition']=='none' else settings['transition'],
    animation=None if settings['animation']=='none' else settings['animation'],
    narration_audio=audio,use_narration_timings=settings['autoplay'] and bool(audio),narration_padding=0,
    master_text_style_spec=MasterTextStyleSpec(3000,1800),
    conversion_trace_path=out/'pptx-trace.json',expected_viewbox='0 0 1280 720',
    doc_metadata={'title':manifest['title'],'creator':'Family Creative Studio'},primary_language='zh-TW')
if not ok:
    raise RuntimeError('PPT Master rejected native conversion')
from pptx.opc.package import PartFactory
from pptx.parts.media import MediaPart
# PPT Master packages WAV narration with media relationships; python-pptx
# otherwise loads those as generic Parts and cannot deduplicate added movies.
PartFactory.part_type_for.update({kind:MediaPart for kind in ('audio/wav','audio/x-wav','audio/mpeg','audio/mp4')})
presentation=Presentation(out/'presentation.pptx')
from pptx.oxml.xmlchemy import OxmlElement
from pptx.dml.color import RGBColor
from PIL import Image
from .media_layout import visual_rect
visuals=json.loads((out/'visuals.json').read_text()) if (out/'visuals.json').exists() else {}
for index,color in backgrounds.items():
    fill=presentation.slides[index].background.fill;fill.solid();fill.fore_color.rgb=RGBColor.from_string(color.lstrip('#'))
for index,item in visuals.items():
    poster=out/item['poster']
    with Image.open(poster) as img:w,h=img.size
    x,y,rw,rh=visual_rect(item.get('layout','editorial'),1280,720)
    scale=min(rw/w,rh/h);w*=scale;h*=scale
    slide=presentation.slides[int(index)]
    left=int((x+(rw-w)/2)/1280*presentation.slide_width);top=int((y+(rh-h)/2)/720*presentation.slide_height)
    width=int(w/1280*presentation.slide_width);height=int(h/720*presentation.slide_height)
    if item.get('ppt_video'):
        shape=slide.shapes.add_movie(str(out/item['ppt_video']),left,top,width,height,poster_frame_image=str(poster),mime_type='video/mp4')
        if settings['autoplay']:
            for video in slide._element.xpath('.//p:video'):
                ids=video.xpath('.//p:spTgt/@spid')
                if str(shape.shape_id) in ids:
                    for condition in video.xpath('.//p:stCondLst/p:cond'):condition.set('delay','0')
    else:
        shape=slide.shapes.add_picture(str(poster),left,top,width=width,height=height)
    if item.get('layout')=='full':
        tree=slide.shapes._spTree;tree.remove(shape._element);tree.insert(2,shape._element)
durations=json.loads((out/'slide-timings.json').read_text()) if (out/'slide-timings.json').is_file() else [b['duration'] for b in manifest['beats']]
for slide,duration in zip(presentation.slides,durations):
    transitions=slide._element.xpath('./p:transition')
    if settings['autoplay']:
        transition=transitions[0] if transitions else OxmlElement('p:transition')
        if not transitions:slide._element.insert_element_before(transition,'p:timing','p:extLst')
        transition.set('advTm',str(round(duration*1000)));transition.set('advClick','1')
    elif transitions:
        transitions[0].attrib.pop('advTm',None)
presentation.save(out/'presentation.pptx')
from pptx_animations import validate_pptx_animation_package
validate_pptx_animation_package(out/'presentation.pptx',require_supported_effects=False)
def walk(shapes):
    for shape in shapes:
        yield shape
        if hasattr(shape,'shapes'):
            yield from walk(shape.shapes)
all_shapes=[shape for slide in presentation.slides for shape in walk(slide.shapes)]
counts={'slides':len(presentation.slides),'editable_shapes':sum(1 for s in all_shapes if s.shape_type!=13),
        'text_frames':sum(bool(s.has_text_frame) for s in all_shapes),
        'pictures':sum(s.shape_type==13 for s in all_shapes),'native_paths':sum(bool(s._element.xpath('.//a:custGeom')) for s in all_shapes),
        'embedded_movies':sum(bool(v.get('ppt_video')) for v in visuals.values()),'narration_tracks':len(audio),
        'animation':settings['animation'],'autoplay':settings['autoplay'],'transition':settings['transition']}
if counts['slides']!=len(svgs) or counts['text_frames']<sum(not b.get('svg_asset') for b in manifest['beats'])*2:
    raise RuntimeError('Editable slide content missing')
(out/'pptx-check.json').write_text(json.dumps(counts,indent=2))
