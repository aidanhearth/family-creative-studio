"""Concrete cross-format build, followed by content checks and atomic publication."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import zipfile
from .paths import ROOT, SOURCES, atomic_json, sha256, contained
from .schema import Manifest
from .runner import Runner
from .content import slide_svg, web_page, dimension_rows, size_text
from .provenance import sources, runtime_sources, engine_fingerprint


def module_file(name, relative):
    spec=importlib.util.spec_from_file_location(name, ROOT/relative)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def caption_text(text):
    return ' '.join(text.split())

def srt_time(seconds):
    ms=round(seconds*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def verify(out,m,targets,runner):
    from .preflight import contrast_checks
    checks=contrast_checks(m)
    if 'cad' in targets:
        glb=module_file('glb_container','vendor/img2threejs--img2threejs/glb_container.py')
        document,_,meta=glb.parse_glb(out/'model.glb')
        if not document.get('meshes') or not document.get('nodes'):
            raise ValueError('GLB is missing geometry')
        for buffer in document.get('buffers',[]):
            if buffer.get('uri'):
                raise ValueError('GLB is not self-contained')
        log=runner.run(['node',ROOT/'scripts/glb-check.mjs',out/'model.glb'],label='glb-three-check')
        glb_bounds=json.loads(log.read_text())
        cad_check=json.loads((out/'cad-check.json').read_text())
        expected=[cad_check['bounds_mm']['max'][i]-cad_check['bounds_mm']['min'][i] for i in (0,2,1)]
        if any(abs(a*1000-b)>.05 for a,b in zip(glb_bounds['size'],expected)):
            raise ValueError('GLB bounds differ from the resulting CAD geometry')
        cad_volume=json.loads((out/'cad-check.json').read_text())['volume_mm3']
        if set(glb_bounds['names'])!=set(cad_check['part_ids']):raise ValueError('GLB semantic part IDs differ from CAD parts')
        if abs(glb_bounds['volume_m3']*1e9-cad_volume)>max(1,cad_volume*.003):
            raise ValueError('GLB mesh volume differs from the STEP solid')
        checks.append({'check':'glb-dimensions','pass':True,'bounds_m':glb_bounds})
        checks.append({'check':'glb-container','pass':True,'meshes':len(document['meshes']),'bytes':meta['declaredLength'],'engine':'img2threejs'})
        check=json.loads((out/'cad-check.json').read_text());checks.append({'check':'step-reimport','pass':check['valid'],**check})
    if 'slides' in targets:
        with zipfile.ZipFile(out/'presentation.pptx') as archive:
            if archive.testzip(): raise ValueError('PPTX failed CRC check')
            slides=[n for n in archive.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')]
            if len(slides)!=len(m.beats): raise ValueError('Slide count mismatch')
            from xml.etree import ElementTree as ET
            for name in slides:
                root=ET.fromstring(archive.read(name))
                ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
                index=int(Path(name).stem.removeprefix('slide'))-1
                if (not m.beats[index].svg_asset and not root.findall('.//a:t',ns)) or not root.findall('.//p:sp',ns):
                    raise ValueError('Slide is not native editable text and shapes')
        checks.append({'check':'pptx-native-shapes','pass':True,**json.loads((out/'pptx-check.json').read_text())})
    if 'video' in targets:
        log=runner.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',out/'film.mp4'],label='ffprobe',timeout=20)
        probe=json.loads(log.read_text());streams=probe['streams'];v=next((s for s in streams if s['codec_type']=='video'),None)
        a=next((s for s in streams if s['codec_type']=='audio'),None)
        cues=(out/'captions.srt').read_text().count(' --> ')
        settings=json.loads((out/'output-settings.json').read_text())
        from fractions import Fraction
        if not v or not a or (v['width'],v['height'])!=(settings['width'],settings['height']) or cues!=sum(bool(b.narration.strip()) for b in m.beats):
            raise ValueError('Video is missing valid picture, audio or complete captions')
        if Fraction(v['r_frame_rate'])!=Fraction(settings['fps']):raise ValueError('Video frame rate differs from the requested timeline')
        if a.get('sample_rate')!='48000' or a.get('channels')!=2:
            raise ValueError('Video audio must be 48 kHz stereo')
        expected=json.loads((out/'edit.edl.json').read_text())['duration_s']
        if abs(float(probe['format']['duration'])-expected)>.2:
            raise ValueError('Video duration differs from its edit timeline')
        checks.append({'check':'video-streams-captions','pass':True,'width':v['width'],'height':v['height'],'fps':v['r_frame_rate'],'duration_s':float(probe['format']['duration']),'caption_cues':cues,'audio_codec':a['codec_name'],'audio_sample_rate':int(a['sample_rate']),'audio_channels':a['channels']})
    from .svg_assets import inspect_svg
    for file in out.rglob('*.svg'):
        inspect_svg(file.read_bytes(),generated=True)
    return checks


class EngineChanged(ValueError):
    pass

def build(store,job,loaded_engine=None):
    import hashlib
    engine=engine_fingerprint()
    expected=hashlib.sha256((Manifest.model_validate(job['snapshot']).canonical()+json.dumps(job['targets'])+engine).encode()).hexdigest()
    if expected!=job['fingerprint'] or (loaded_engine is not None and loaded_engine!=engine):
        raise EngineChanged('engine_changed: converters changed after queueing or worker start; retry after the worker restarts')
    run=store.root/'runs'/job['id'];run.mkdir(parents=True,exist_ok=False)
    out=run/'staging';out.mkdir()
    runner=Runner(store,job,run)
    source=Manifest.model_validate(job['snapshot']);m=source.resolved();targets=job['targets']
    from .media_assets import preflight,asset_info
    from .stage_cache import StageCache
    from .video import audio_track,prepare_visuals,composite_posters,render_video
    preflight(store,m,targets);cache=StageCache(store.root,engine)
    from .preflight import contrast_checks
    contrast_checks(m)
    from .media_layout import output_settings,beat_layout
    metadata=[asset_info(store,b.visual.asset)[1] for b in m.beats if b.visual.asset]
    settings=output_settings(m,metadata)
    atomic_json(out/'output-settings.json',settings)
    (out/'assets').mkdir()
    if m.scene_asset:
        asset,_=asset_info(store,m.scene_asset)
        shutil.copy2(asset,out/'scene.glb');shutil.copy2(asset,out/'assets'/m.scene_asset)
    for b in m.beats:
        if b.visual.asset:
            asset,_=asset_info(store,b.visual.asset);shutil.copy2(asset,out/'assets'/b.visual.asset)
    atomic_json(out/'source-manifest.json',source.model_dump());atomic_json(out/'manifest.json',m.model_dump())
    atomic_json(out/'dimensions.json',dimension_rows(m))
    atomic_json(out/'geometry-sources.json',{'viewer': 'imported-scene' if m.scene_asset else 'parametric-cad', 'scene_asset':m.scene_asset,'scene_animation':m.scene_animation,'cad_source':'manifest.solids','cad_files':['model.step','model.stl','model.glb'] if m.solids else [],'cad_diagrams':'anatomy.svg and diagram-mode chapters','independent_sources':bool(m.scene_asset and m.solids),'scene_to_cad_conversion':False})
    atomic_json(out/'sources.json',sources())
    # The canonical CAD is also the source for vector diagrams, previews and slides.
    need_cad=bool(m.solids)
    if need_cad:
        from .geometry_preview import copy_cad_assets
        copy_cad_assets(store,m,out)
        runner.stage('cad')
        cache.run('cad',{'id':m.id,'solids':[s.model_dump() for s in m.solids]},out,['model.step','model.stl','model.glb','cad-check.json','geometry.json'],lambda:runner.run([sys.executable,'-m','studio.cad_worker',out/'manifest.json',out],label='cad',timeout=300,cwd=ROOT))
    catalog=json.loads((ROOT/'vendor/freestylefly--awesome-gpt-image-2/styles.json').read_text())
    chosen=next((style for style in catalog['styles'] if style['id']==m.style_id),None)
    templates=[t for t in catalog['templates'] if not chosen or chosen['value'] in t.get('styles',[])]
    selected_template=(templates or catalog['templates'])[0]
    prompt={'title':m.title,'brief':m.subtitle,'brand':m.brand.model_dump(),'dimensions':dimension_rows(m),
            'style':chosen,'template':selected_template,'source':catalog['repository'],
            'provider_status':'Reference brief only. No image provider was invoked.'}
    atomic_json(out/'image-brief.json',prompt)
    (out/'image-prompt.txt').write_text('Subject: '+m.title+'\nBrief: '+m.subtitle+'\nPalette: '+m.brand.paper+' / '+m.brand.ink+' / '+m.brand.accent+'\nStyle: '+(chosen['value'] if chosen else 'Editorial product study')+'\n'+ '\n'.join(selected_template['guidance']['en'])+'\nExact dimensions (mm):\n'+json.dumps(dimension_rows(m),ensure_ascii=False,indent=2)+'\nKeep all visible dimension text exact; do not invent performance claims.\n')
    copy=json.loads((ROOT/'web/copy.json').read_text())
    runner.stage('diagram')
    runner.run(['node',ROOT/'scripts/anatomy.mjs',out/'manifest.json',out/'anatomy.svg',out/'geometry.json'],label='anatomy')
    from xml.etree import ElementTree as ET
    anatomy=ET.fromstring((out/'anatomy.svg').read_text())
    anatomy_body=''.join(ET.tostring(child,encoding='unicode') for child in anatomy if child.tag.rsplit('}',1)[-1] not in ('title','rect'))
    (out/'slides').mkdir()
    from .svg_assets import rasterize
    for i,beat in enumerate(m.beats):
        svg=out/'slides'/f'{i:02d}.svg'
        if beat.svg_asset:
            from .svg_assets import normalized_svg
            from .content import fitted_artwork_svg
            asset,_=asset_info(store,beat.svg_asset);shutil.copy2(asset,out/'assets'/beat.svg_asset)
            svg.write_text(normalized_svg(asset.read_bytes()))
            video_svg=fitted_artwork_svg(asset.read_bytes(),settings['width'],settings['height'],m.brand.paper)
        else:
            drawing=anatomy_body if beat.visual.mode=='diagram' else ''
            svg.write_text(slide_svg(m,beat,i,drawing))
            video_svg=slide_svg(m,beat,i,drawing,width=settings['width'],height=settings['height'])
        (out/'slides'/f'{i:02d}.video.svg').write_text(video_svg)
        rasterize(video_svg.encode(),svg.with_suffix('.png'),settings['width'],settings['height'],generated=True)
        if beat_layout(m,beat)=='full' and not beat.svg_asset:
            from .content import slide_overlay
            overlay=slide_overlay(m,beat,i,width=settings['width'],height=settings['height'])
            (out/'slides'/f'{i:02d}.overlay.svg').write_text(overlay)
            rasterize(overlay.encode(),out/'slides'/f'{i:02d}.overlay.png',settings['width'],settings['height'],generated=True)
    if 'diagram' in targets:
        graph={'schema_version':2,'diagram_type':'workflow','meta':{'title':m.title,'animation':'none','quality_profile':'standard','output':'workflow.html'},
            'lanes':[{'id':'story','label':m.title}],
            'nodes':[{'id':b.id,'lane':'story','col':i,'type':'backend','label':b.title,'width':170} for i,b in enumerate(m.beats)],
            'edges':[{'id':f'e{i}','from':m.beats[i].id,'to':m.beats[i+1].id} for i in range(len(m.beats)-1)]}
        kind='workflow'
        if m.diagram:
            kind=m.diagram.kind;graph=json.loads(json.dumps(m.diagram.document))
            graph.setdefault('meta',{})['output']='workflow.html'
        atomic_json(out/'workflow.json',graph)
        runner.run(['node',SOURCES/'tt-a1i--archify/archify/bin/archify.mjs','render',kind,out/'workflow.json',out/'workflow.html','--quality','standard'],label='archify',cwd=out)
    durations=audio_track(m,out,runner,cache) if 'video' in targets or ('slides' in targets and m.slides.narration) else [b.duration for b in m.beats]
    atomic_json(out/'slide-timings.json',durations)
    visuals=prepare_visuals(m,out,runner,durations,cache)
    composite_posters(m,out,visuals)
    if 'video' in targets:
        runner.stage('video');render_video(m,source,out,runner,durations,visuals)
    if 'slides' in targets:
        runner.stage('slides')
        from .presentation_media import prepare_movies
        prepare_movies(m,out,runner,visuals,durations)
        runner.run([sys.executable,'-m','studio.ppt_worker',out],label='ppt',timeout=300,cwd=ROOT)
    if 'web' in targets:
        runner.stage('web')
        display_glb=out/('scene.glb' if m.scene_asset else 'model.glb')
        (out/'index.html').write_text(web_page(m,copy,display_glb.read_bytes() if display_glb.exists() else None))
        shutil.copy2(ROOT/'dist/viewer.js',out/'viewer.js')
        if (ROOT/'dist/viewer.js.LEGAL.txt').exists():shutil.copy2(ROOT/'dist/viewer.js.LEGAL.txt',out/'viewer.js.LEGAL.txt')
    atomic_json(out/'build-stages.json',{'stages':cache.records,'stages_reused':[r['stage'] for r in cache.records if r['reused']],'stages_executed':[r['stage'] for r in cache.records if not r['reused']],'reused_bytes':sum(r['bytes'] for r in cache.records if r['reused'])})
    runner.stage('verify')
    checks=verify(out,m,list(set(targets)|({'cad'} if need_cad else set())),runner)
    for item in sorted((out/'motion').glob('*.json')) if (out/'motion').exists() else []:
        motion=json.loads(item.read_text());checks.append({'check':'deterministic-cad-motion','pass':True,'frames':motion['frames'],'moving_fraction':motion['moving_fraction'],'repeat_first_frame_equal':motion['repeat_first_frame_equal']})
    atomic_json(out/'quality.json',{'passed':True,'checks':checks,'scope':'format integrity and declared numeric checks; visual taste is reviewed separately','source_sha256':source.digest(),'fingerprint':job['fingerprint']})
    atomic_json(out/'artifact-manifest.json',[{'path':str(f.relative_to(out)),'sha256':sha256(f),'bytes':f.stat().st_size} for f in sorted(out.rglob('*')) if f.is_file()])
    # A distributable bundle carries its dependent files, provenance and notices.
    with zipfile.ZipFile(out/'project.zip','w',compression=zipfile.ZIP_DEFLATED) as bundle:
        for file in sorted(out.rglob('*')):
            if file.is_file() and file.name!='project.zip' and not file.is_relative_to(out/'clips') and file.name!='base.mp4':
                bundle.write(file,str(file.relative_to(out)))
        for notice in (ROOT/'vendor').rglob('*'):
            if notice.is_file() and notice.name.upper().startswith(('LICENSE','NOTICE','COPYING')):
                bundle.write(notice,'THIRD_PARTY/'+str(notice.relative_to(ROOT/'vendor')))
    artifacts=[{'path':str(file.relative_to(out)),'bytes':file.stat().st_size,'sha256':sha256(file)} for file in sorted(out.rglob('*')) if file.is_file()]
    runner.check()
    out.replace(run/'output')
    # Terminal database state is last; any crash before it remains interrupted.
    if not store.publish(job['id'],artifacts):
        from .runner import Cancelled
        raise Cancelled('Cancelled before publication')
