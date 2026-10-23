"""One edit timeline for moving CAD, normalized source clips, slides, and voice."""
import json
import math
import shutil
import sys
import wave
from PIL import Image,ImageOps
from .paths import ROOT,atomic_json,contained,sha256
from .media_assets import asset_info


def audio_track(m,out,runner,cache):
    durations=[];chunks=[];(out/'audio').mkdir(exist_ok=True)
    imported=out/'narration-input.wav'
    if m.narration_asset:
        source=contained(runner.store.root/'assets',m.narration_asset)
        if not source.is_file() or sha256(source)!=m.narration_asset[:-4]:raise ValueError('Narration asset missing or changed')
        shutil.copy2(source,imported)
        with wave.open(str(imported),'rb') as w:length=w.getnframes()/w.getframerate()
        if abs(length-sum(b.duration for b in m.beats))>.5:raise ValueError('Imported narration duration must match total beat duration within 0.5 seconds')
    offset=0
    for i,beat in enumerate(m.beats):
        name=f'audio/{i:02d}.wav';path=out/name;v=beat.visual
        engine='imported WAV' if m.narration_asset and v.audio=='voice' else v.audio
        def generate():
            args=['ffmpeg','-v','error','-y']
            if engine=='imported WAV':args+=['-ss',str(offset),'-i',imported]
            elif v.audio=='source':args+=['-ss',str(v.start),'-i',out/'assets'/v.asset,'-vn']
            elif v.audio=='silent':args+=['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
            else:
                text=out/'audio'/f'{i:02d}.txt';text.write_text(beat.narration)
                runner.run(['espeak-ng','-v','cmn','-s','175','-f',text,'-w',path],label=f'voice-{i}',timeout=30)
                return
            runner.run(args+['-t',str(beat.duration),'-ar','48000','-ac','2',path],label=f'audio-{i}',timeout=45)
        cache.run('audio',{'narration':beat.narration,'mode':engine,'duration':beat.duration,'asset':m.narration_asset or v.asset,'offset':offset if m.narration_asset else v.start},out,[name],generate)
        with wave.open(str(path),'rb') as w:actual=w.getnframes()/w.getframerate()
        duration=beat.duration
        if engine=='voice':
            if v.mode=='clip' and actual+.5>duration:raise ValueError('Narration exceeds this trimmed clip; shorten narration or extend the clip: '+beat.id)
            duration=duration if v.mode=='clip' else max(duration,actual+.5)
        duration=math.ceil(duration*24)/24
        if duration>30:raise ValueError('Narration segment exceeds 30 seconds')
        durations.append(duration);offset+=beat.duration
        chunks.append({'beat':beat.id,'wav':name,'duration_s':duration,'engine':'eSpeak NG / cmn draft' if engine=='voice' else engine,'timing':'authored beat timing, not word alignment'})
    if sum(durations)>120:raise ValueError('Narration makes the video longer than 120 seconds')
    atomic_json(out/'narration.json',{'engine':'per-scene audio','chunks':chunks})
    return durations


def prepare_visuals(m,out,runner,durations,cache):
    (out/'assets').mkdir(exist_ok=True);(out/'posters').mkdir(exist_ok=True)
    records={}
    for i,b in enumerate(m.beats):
        v=b.visual;poster=out/'posters'/f'{i:02d}.png'
        if v.mode in ('orbit','explode'):
            names=[f'motion/{i:02d}.{ext}' for ext in ('mp4','png','json')]
            cache.run('scene',{'glb':sha256(out/'model.glb'),'solids':[s.model_dump() for s in m.solids],'brand':m.brand.model_dump(),'mode':v.mode,'duration':durations[i]},out,names,lambda:runner.run([sys.executable,'-m','studio.scene_worker',out,str(i),str(durations[i])],label=f'scene-{i}',timeout=900,cwd=ROOT))
            shutil.copy2(out/f'motion/{i:02d}.png',poster)
            records[str(i)]={'video':f'motion/{i:02d}.mp4','poster':str(poster.relative_to(out)),'mode':v.mode}
        elif v.asset:
            path,_=asset_info(runner.store,v.asset);shutil.copy2(path,out/'assets'/v.asset)
            if v.mode=='clip':
                runner.run(['ffmpeg','-v','error','-y','-ss',str(v.start),'-i',path,'-frames:v','1',poster],label=f'poster-{i}',timeout=30)
            else:shutil.copy2(path,poster)
            records[str(i)]={'video':'assets/'+v.asset if v.mode=='clip' else None,'poster':str(poster.relative_to(out)),'mode':v.mode}
    atomic_json(out/'visuals.json',records)
    return records


def composite_posters(m,out,visuals):
    for key,item in visuals.items():
        target=out/'slides'/f'{int(key):02d}.png'
        with Image.open(target) as base,Image.open(out/item['poster']) as picture:
            fitted=ImageOps.contain(picture.convert('RGB'),(720,420));base=base.convert('RGB')
            base.paste(fitted,(510+(720-fitted.width)//2,90+(420-fitted.height)//2));base.save(target)


def render_video(m,source,out,runner,durations,visuals):
    from .pipeline import srt_time,caption_text
    from .content import dimension_rows
    clips=out/'clips';clips.mkdir();segments=[];cues=[];start=0
    for i,(beat,duration) in enumerate(zip(m.beats,durations)):
        args=['ffmpeg','-v','error','-y'];visual=visuals.get(str(i));v=beat.visual
        if visual and visual['video']:
            if v.mode=='clip':args+=['-ss',str(v.start)]
            args+=['-i',out/visual['video'],'-loop','1','-framerate','24','-i',out/'slides'/f'{i:02d}.png','-i',out/'audio'/f'{i:02d}.wav',
                '-filter_complex',f'[0:v]scale=720:420:force_original_aspect_ratio=decrease,pad=720:420:(ow-iw)/2:(oh-ih)/2:color={m.brand.paper},setsar=1[scene];[1:v][scene]overlay=510:90:shortest=1[v]', '-map','[v]','-map','2:a:0']
        else:
            args+=['-loop','1','-framerate','24','-i',out/'slides'/f'{i:02d}.png','-i',out/'audio'/f'{i:02d}.wav','-map','0:v:0','-map','1:a:0']
        args+=['-af','apad','-t',f'{duration:.6f}','-r','24','-c:v','libx264','-threads','2','-filter_complex_threads','2','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-ac','2',clips/f'{i:02d}.mp4']
        runner.run(args,label=f'video-{i}',timeout=150)
        if beat.narration.strip():cues.append(f'{len(cues)+1}\n{srt_time(start)} --> {srt_time(start+duration)}\n{caption_text(beat.narration)}\n')
        segments.append({'beat':beat.id,'mode':v.mode,'source':visual['video'] or visual['poster'] if visual else f'slides/{i:02d}.png','asset':v.asset,'source_start':v.start if v.mode=='clip' else 0,'audio_mode':'imported WAV' if m.narration_asset and v.audio=='voice' else v.audio,'audio':f'audio/{i:02d}.wav','start':round(start,6),'end':round(start+duration,6),'dimensions':dimension_rows(m)})
        start+=duration
    (out/'captions.srt').write_text('\n'.join(cues))
    atomic_json(out/'edit.edl.json',{'schema_version':2,'manifest_sha256':source.digest(),'duration_s':round(start,6),'fps':'24/1','width':1280,'height':720,'segments':segments,'caption_timing':'authored beat timing; not ASR word alignment'})
    runner.run([sys.executable,'-m','studio.media_worker',out],label='video-use-concat',timeout=90,cwd=ROOT)
    args=['ffmpeg','-v','error','-y','-i',out/'base.mp4']
    if cues:args+=['-vf',"setpts=PTS-STARTPTS,subtitles=captions.srt:force_style='FontName=Noto Sans CJK TC,FontSize=17,Outline=1,MarginV=34'"]
    if not cues:args+=['-vf','setpts=PTS-STARTPTS']
    args+=['-af','loudnorm=I=-16:TP=-1.5:LRA=11,apad','-t',f'{start:.6f}','-c:v','libx264','-threads','2','-preset','fast','-crf','20','-c:a','aac','-ar','48000','-ac','2','-pix_fmt','yuv420p','-movflags','+faststart',out/'film.mp4']
    runner.run(args,label='final-video',timeout=240,cwd=out)
