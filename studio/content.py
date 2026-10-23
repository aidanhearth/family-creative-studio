"""Generate SVG/HTML from one manifest; only escaped text and bounded numbers enter markup."""
import html
import json
import re
import unicodedata
from pathlib import Path
from .paths import ROOT

def esc(s): return html.escape(str(s),quote=True)

def text_lines(text,width):
    tokens=re.findall(r'[A-Za-z0-9][A-Za-z0-9×Ø./_-]*|[^\s]|\s+',text)
    lines=[];line='';units=0;limit=width*2
    for token in tokens:
        token=' ' if token.isspace() else token
        length=sum(2 if unicodedata.east_asian_width(c) in ('W','F') else 1 for c in token)
        if line and units+length>limit and token not in '，。；：！？、）』」':
            lines.append(line.rstrip());line='';units=0
        if not line and token==' ':continue
        line+=token;units+=length
    if line:lines.append(line.rstrip())
    if not lines:lines=['']
    return lines

def text_block(text,x,y,*,size=26,color='#18181B',width=22,line_height=None,weight=400,max_lines=None):
    lines=text_lines(text,width)
    if max_lines and len(lines)>max_lines:
        lines=lines[:max_lines];lines[-1]=lines[-1].rstrip(' .…')+'…'
    gap=line_height or size*1.55
    return ''.join(f'<text x="{x}" y="{y+i*gap}" fill="{color}" font-family="Noto Sans CJK TC" font-size="{size}" font-weight="{weight}">{esc(line)}</text>' for i,line in enumerate(lines))

def dimension_rows(m):
    return [{'id':s.id,'name':s.name,'kind':s.kind,'size_mm':list(s.size),'bore_mm':s.bore,'position_mm':list(s.position),'rotation_degrees':list(s.rotation),'construction':s.construction,'fillet_mm':s.fillet,'chamfer_mm':s.chamfer,'booleans':[b.model_dump() for b in s.booleans]} for s in m.solids]

def size_text(s):
    return ' × '.join(f'{v:g}' for v in s.size)+' mm'+(f' · Ø {s.bore:g}' if s.bore else '')

def slide_svg(m,beat,index,anatomy_body,*,width=1280,height=720):
    if width*720!=height*1280:
        return canvas_slide_svg(m,beat,index,anatomy_body,width,height)
    from .media_layout import beat_layout
    layout=beat_layout(m,beat)
    if layout=='full':
        overlay=slide_overlay(m,beat,index)
        drawing=f'<g transform="translate(260 100) scale(1)">{anatomy_body}</g>' if anatomy_body else ''
        return overlay.replace('<title>',f'<rect width="1280" height="720" fill="{m.brand.paper}"/>{drawing}<title>',1)
    b=m.brand
    head=f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"><title>{esc(m.title)} / {esc(beat.title)}</title><rect width="1280" height="720" fill="{b.paper}"/><rect x="48" y="54" width="30" height="4" fill="{b.accent}"/>'
    body=text_block(m.title,94,65,size=18,color=b.muted,width=48)
    body+=text_block(f'{index+1:02d}',48,152,size=20,color=b.accent,width=20)
    body+=text_block(beat.title,48,215,size=30 if len(beat.title)>22 else 38,color=b.ink,width=14 if len(beat.title)>22 else 11,weight=600)
    body+=text_block(beat.body,48,330,size=24,color=b.muted,width=18)
    if anatomy_body:
        if beat.focus:
            from xml.etree import ElementTree as ET
            group=ET.fromstring('<g>'+anatomy_body+'</g>')
            for element in group.iter():
                identity=element.attrib.get('data-part-id')
                if identity and identity not in beat.focus:
                    # Blend against paper rather than alpha-compositing thousands
                    # of overlapping triangles into a dark tessellation grid.
                    fill=element.get('fill','')
                    if re.fullmatch(r'#[0-9a-fA-F]{6}',fill):
                        muted='#'+''.join(f'{round(int(fill[j:j+2],16)*.22+int(b.paper[j:j+2],16)*.78):02x}' for j in (1,3,5))
                        element.set('fill',muted);element.set('stroke',muted)
            anatomy_body=''.join(ET.tostring(child,encoding='unicode') for child in group)
        transform='translate(585 108) scale(.83)' if layout=='split' else 'translate(510 72) scale(.94)'
        body+=f'<g transform="{transform}">{anatomy_body}</g>'
    focused=[s for s in m.solids if not s.construction and (not beat.focus or s.id in beat.focus)][:3 if layout=='split' else 4]
    for i,s in enumerate(focused):
        yy=(490+i*50) if layout=='split' else 525+i*33
        body+=text_block(s.name,48,yy,size=18,color=b.ink,width=14,weight=500)
        if layout=='split':
            body+=text_block(size_text(s),48,yy+20,size=14,color=b.muted,width=34)
        else:body+=text_block(size_text(s),230,yy,size=18,color=b.muted,width=64)
    body+=f'<line x1="48" y1="668" x2="1232" y2="668" stroke="{b.muted}" stroke-opacity=".3"/>'
    body+=text_block('CAD PARAMETERS / mm',48,698,size=14,color=b.muted,width=40)
    body+=text_block(f'{index+1:02d} / {len(m.beats):02d}',1152,698,size=14,color=b.muted,width=12)
    return head+body+'</svg>'


def slide_overlay(m,beat,index,*,width=1280,height=720):
    """Transparent full-bleed title layer shared by native PPT and raster composition."""
    if width*720!=height*1280:
        return canvas_overlay(m,beat,index,width,height)
    b=m.brand
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"><title>{esc(beat.title)}</title>'
            f'<rect x="32" y="32" width="680" height="154" rx="12" fill="{b.paper}" fill-opacity=".93"/>'
            +text_block(m.title,56,66,size=17,color=b.muted,width=55)
            +text_block(beat.title,56,118,size=30,color=b.ink,width=31,weight=600)
            +f'<rect x="32" y="560" width="1216" height="128" rx="12" fill="{b.paper}" fill-opacity=".93"/>'
            +text_block(beat.body,56,598,size=22,color=b.ink,width=50)
            +text_block(f'{index+1:02d} / {len(m.beats):02d}',1138,662,size=15,color=b.muted,width=15)+'</svg>')


def boxed_text(text,x,y,width,height,*,size,color,weight=400):
    """Fit readable lines inside a reserved region; long copy ends with an ellipsis."""
    while size>14 and len(text_lines(text,width/size))*size*1.45>height:
        size-=1
    return text_block(text,x,y+size,size=size,color=color,width=width/size,
                      line_height=size*1.45,weight=weight,max_lines=max(1,int(height/(size*1.45))))


def canvas_head(width,height):
    from .media_layout import canvas_space
    cw,ch,_,_=canvas_space(width,height)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {cw:g} {ch:g}">'


def canvas_overlay(m,beat,index,width,height):
    """Full-frame titles anchored to the actual canvas, without 16:9 letterboxing."""
    from .media_layout import canvas_space
    cw,ch,_,_=canvas_space(width,height);b=m.brand
    title_width=min(680,cw-64)
    return (canvas_head(width,height)+f'<title>{esc(beat.title)}</title>'
        +f'<rect x="32" y="32" width="{title_width:g}" height="154" rx="12" fill="{b.paper}" fill-opacity=".93"/>'
        +boxed_text(m.title,56,46,title_width-48,30,size=17,color=b.muted)
        +boxed_text(beat.title,56,88,title_width-48,80,size=30,color=b.ink,weight=600)
        +f'<rect x="32" y="{ch-160:g}" width="{cw-64:g}" height="128" rx="12" fill="{b.paper}" fill-opacity=".93"/>'
        +boxed_text(beat.body,56,ch-145,cw-112,75,size=22,color=b.ink)
        +text_block(f'{index+1:02d} / {len(m.beats):02d}',cw-142,ch-48,size=15,color=b.muted,width=15)+'</svg>')


def canvas_slide_svg(m,beat,index,anatomy_body,width,height):
    from .media_layout import beat_layout,canvas_space,visual_rect
    from xml.etree import ElementTree as ET
    cw,ch,scale,stacked=canvas_space(width,height);layout=beat_layout(m,beat);b=m.brand
    vx,vy,vw,vh=(value/scale for value in visual_rect(layout,width,height))
    if layout=='full':
        vx,vy,vw,vh=32,202,cw-64,max(1,ch-380)
    drawing=''
    if anatomy_body:
        if beat.focus:
            group=ET.fromstring('<g>'+anatomy_body+'</g>')
            for element in group.iter():
                if element.get('data-part-id') and element.get('data-part-id') not in beat.focus:
                    fill=element.get('fill','')
                    if re.fullmatch(r'#[0-9a-fA-F]{6}',fill):
                        muted='#'+''.join(f'{round(int(fill[j:j+2],16)*.22+int(b.paper[j:j+2],16)*.78):02x}' for j in (1,3,5))
                        element.set('fill',muted);element.set('stroke',muted)
            anatomy_body=''.join(ET.tostring(child,encoding='unicode') for child in group)
        fit=min(vw/760,vh/560)
        drawing=f'<g transform="translate({vx+(vw-760*fit)/2:g} {vy+(vh-560*fit)/2:g}) scale({fit:g})">{anatomy_body}</g>'
    background=f'<rect width="{cw:g}" height="{ch:g}" fill="{b.paper}"/>'
    if layout=='full':
        return canvas_overlay(m,beat,index,width,height).replace('<title>',background+drawing+'<title>',1)
    left=32 if stacked else 48
    text_width=cw-2*left if stacked else max(1,vx-left-36)
    body=(canvas_head(width,height)+f'<title>{esc(beat.title)}</title>'+background
          +boxed_text(m.title,left,32,text_width,32,size=18,color=b.muted)
          +text_block(f'{index+1:02d}',left,94,size=18,color=b.accent,width=12)
          +boxed_text(beat.title,left,108,text_width,92,size=38,color=b.ink,weight=600)
          +boxed_text(beat.body,left,218,text_width,(vy-238 if stacked else 190),size=24,color=b.muted)+drawing)
    focused=[s for s in m.solids if not s.construction and (not beat.focus or s.id in beat.focus)][:3]
    for i,solid in enumerate(focused):
        top=ch-136+i*29 if stacked else 486+i*48
        line=solid.name+' · '+size_text(solid)
        body+=boxed_text(line,left,top,text_width,27 if stacked else 43,size=17,color=b.muted)
    footer_width=cw-2*left if stacked or layout=='editorial' else text_width
    body+=f'<line x1="{left:g}" y1="{ch-40:g}" x2="{left+footer_width:g}" y2="{ch-40:g}" stroke="{b.muted}" stroke-opacity=".3"/>'
    body+=text_block(f'{index+1:02d} / {len(m.beats):02d}',left,ch-16,size=14,color=b.muted,width=15)
    return body+'</svg>'


def fitted_artwork_svg(data,width,height,paper):
    """Fit the original SVG uniformly on an opaque video canvas, never stretch it."""
    from .svg_assets import inspect_svg
    from xml.etree import ElementTree as ET
    root,(x,y,w,h)=inspect_svg(data);scale=min(width/w,height/h)
    namespace='{http://www.w3.org/2000/svg}'
    canvas=ET.Element(namespace+'svg',{'width':str(width),'height':str(height),'viewBox':f'0 0 {width} {height}'})
    ET.SubElement(canvas,namespace+'rect',{'width':str(width),'height':str(height),'fill':paper})
    transform=ET.SubElement(canvas,namespace+'g',{'transform':f'translate({(width-w*scale)/2:g} {(height-h*scale)/2:g}) scale({scale:g}) translate({-x:g} {-y:g})'})
    inherited=ET.SubElement(transform,namespace+'g',{k:v for k,v in root.attrib.items() if k not in ('width','height','viewBox','preserveAspectRatio','x','y')})
    for child in root:inherited.append(child)
    return ET.tostring(canvas,encoding='unicode')

def web_page(m,copy,glb_bytes=None):
    rows=''.join(f'<tr><th scope="row">{esc(s.name)}</th><td>{esc(size_text(s))}</td></tr>' for s in m.solids)
    beats=''
    for i,b in enumerate(m.beats):
        visual=''
        if b.visual.mode in ('orbit','explode'):visual=f'<button data-motion="{b.visual.mode}" data-beat="{esc(b.id)}">▶ {esc(b.title)}</button>'
        elif b.visual.asset:
            visual=f'<video controls preload="metadata" src="assets/{b.visual.asset}#t={b.visual.start},{b.visual.start+b.duration}"></video>' if b.visual.mode=='clip' else f'<img src="assets/{b.visual.asset}" alt="{esc(b.title)}">'
        beats+=f'<article><span>{i+1:02d}</span><h2>{esc(b.title)}</h2><p>{esc(b.body)}</p>{visual}</article>'
    import base64
    geometry=base64.b64encode(glb_bytes).decode() if glb_bytes else ''
    geometry_note=('Imported GLB scene. The parameter table and STEP/STL downloads describe the separate CAD assembly; the GLB has not been converted to CAD.' if m.scene_asset else 'The viewer and STEP/STL exports share the validated CAD geometry. The table lists authored parameters before boolean operations.')
    embedded=m.canonical().replace('<','\\u003c')
    css=(ROOT/'web/published.css').read_text()
    return f'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(m.title)}</title><style>:root{{--paper:{m.brand.paper};--ink:{m.brand.ink};--accent:{m.brand.accent};--muted:{m.brand.muted}}}{css}</style><body><header><span>FAMILY CREATIVE STUDIO</span><a href="manifest.json">JSON ↗</a></header><main><section class="hero"><div><p class="eyebrow">CONCEPT STUDY · 01</p><h1>{esc(m.title)}</h1><p class="subtitle">{esc(m.subtitle)}</p><p class="note">{esc(copy.get('disclaimer',''))}</p></div><div class="stage"><div id="viewer" aria-label="3D preview"></div><button id="explode">{esc(copy['actions']['toggleExploded'])}</button><p id="renderer-state" role="status"></p></div></section><section class="chapters">{beats}</section><section class="details"><div><p class="eyebrow">CAD PARAMETER REGISTER</p><p>{esc(geometry_note)}</p><h2>{esc(copy['actions']['validateGeometry'])}</h2></div><table><tbody>{rows}</tbody></table></section><footer>{esc(copy['appName'])} · {esc(m.digest()[:12])}</footer></main><script id="project-data" type="application/json">{embedded}</script><script id="project-glb" type="application/octet-stream">{geometry}</script><script src="viewer.js"></script></body></html>'''
