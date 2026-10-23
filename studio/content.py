"""Generate SVG/HTML from one manifest; only escaped text and bounded numbers enter markup."""
import html
import json
import re
import unicodedata
from pathlib import Path
from .paths import ROOT

def esc(s): return html.escape(str(s),quote=True)

def text_block(text,x,y,*,size=26,color='#18181B',width=22,line_height=None,weight=400):
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
    gap=line_height or size*1.55
    return ''.join(f'<text x="{x}" y="{y+i*gap}" fill="{color}" font-family="Noto Sans CJK TC" font-size="{size}" font-weight="{weight}">{esc(line)}</text>' for i,line in enumerate(lines))

def dimension_rows(m):
    return [{'id':s.id,'name':s.name,'size_mm':list(s.size),'bore_mm':s.bore,'position_mm':list(s.position)} for s in m.solids]

def size_text(s):
    return ' × '.join(f'{v:g}' for v in s.size)+' mm'+(f' · Ø {s.bore:g}' if s.bore else '')

def slide_svg(m,beat,index,anatomy_body):
    b=m.brand
    head=f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"><title>{esc(m.title)} / {esc(beat.title)}</title><rect width="1280" height="720" fill="{b.paper}"/><rect x="48" y="54" width="30" height="4" fill="{b.accent}"/>'
    body=text_block(m.title,94,65,size=18,color=b.muted,width=48)
    body+=text_block(f'{index+1:02d}',48,152,size=20,color=b.accent,width=20)
    body+=text_block(beat.title,48,215,size=30 if len(beat.title)>22 else 38,color=b.ink,width=14 if len(beat.title)>22 else 11,weight=600)
    body+=text_block(beat.body,48,330,size=24,color=b.muted,width=18)
    if anatomy_body:body+=f'<g transform="translate(510 72) scale(.94)">{anatomy_body}</g>'
    focused=[s for s in m.solids if not beat.focus or s.id in beat.focus][:4]
    for i,s in enumerate(focused):
        yy=525+i*33
        body+=text_block(s.name,48,yy,size=18,color=b.ink,width=14,weight=500)
        body+=text_block(size_text(s),230,yy,size=18,color=b.muted,width=64)
    body+=f'<line x1="48" y1="668" x2="1232" y2="668" stroke="{b.muted}" stroke-opacity=".3"/>'
    body+=text_block('CONCEPT / mm',48,698,size=14,color=b.muted,width=40)
    body+=text_block(f'{index+1:02d} / {len(m.beats):02d}',1152,698,size=14,color=b.muted,width=12)
    return head+body+'</svg>'

def web_page(m,copy,glb_bytes=None):
    rows=''.join(f'<tr><th scope="row">{esc(s.name)}</th><td>{esc(size_text(s))}</td></tr>' for s in m.solids)
    beats=''
    for i,b in enumerate(m.beats):
        visual=''
        if b.visual.mode in ('orbit','explode'):visual=f'<button data-motion="{b.visual.mode}">▶ {esc(b.title)}</button>'
        elif b.visual.asset:
            visual=f'<video controls preload="metadata" src="assets/{b.visual.asset}#t={b.visual.start},{b.visual.start+b.duration}"></video>' if b.visual.mode=='clip' else f'<img src="assets/{b.visual.asset}" alt="{esc(b.title)}">'
        beats+=f'<article><span>{i+1:02d}</span><h2>{esc(b.title)}</h2><p>{esc(b.body)}</p>{visual}</article>'
    import base64
    geometry=base64.b64encode(glb_bytes).decode() if glb_bytes else ''
    embedded=m.canonical().replace('<','\\u003c')
    css=(ROOT/'web/published.css').read_text()
    return f'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(m.title)}</title><style>:root{{--paper:{m.brand.paper};--ink:{m.brand.ink};--accent:{m.brand.accent};--muted:{m.brand.muted}}}{css}</style><body><header><span>FAMILY CREATIVE STUDIO</span><a href="manifest.json">JSON ↗</a></header><main><section class="hero"><div><p class="eyebrow">CONCEPT STUDY · 01</p><h1>{esc(m.title)}</h1><p class="subtitle">{esc(m.subtitle)}</p><p class="note">{esc(copy.get('disclaimer',''))}</p></div><div class="stage"><div id="viewer" aria-label="3D preview"></div><button id="explode">{esc(copy['actions']['toggleExploded'])}</button><p id="renderer-state" role="status"></p></div></section><section class="chapters">{beats}</section><section class="details"><div><p class="eyebrow">DIMENSION REGISTER</p><h2>{esc(copy['actions']['validateGeometry'])}</h2></div><table><tbody>{rows}</tbody></table></section><footer>{esc(copy['appName'])} · {esc(m.digest()[:12])}</footer></main><script id="project-data" type="application/json">{embedded}</script><script id="project-glb" type="application/octet-stream">{geometry}</script><script src="viewer.js"></script></body></html>'''
