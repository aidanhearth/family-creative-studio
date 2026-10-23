"""Preserved source media, editable timing and one-generation video composition."""
import io
import json
import math
import shutil
import sys
import wave
from fractions import Fraction
from PIL import Image, ImageCms, ImageOps
from .paths import ROOT, atomic_json, sha256
from .media_assets import asset_info
from .media_layout import output_settings, beat_layout, visual_rect

# Same HDR-to-SDR operation used by pinned video-use; applied before composition.
TONEMAP = ('zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,'
           'tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,')


def _metadata(m, store):
    return {b.visual.asset: asset_info(store, b.visual.asset)[1] for b in m.beats if b.visual.asset}


def _duration(path):
    with wave.open(str(path), 'rb') as audio: return audio.getnframes() / audio.getframerate()


def _timeout(duration, multiplier=5):
    return max(60, min(14400, math.ceil(duration * multiplier + 30)))


def audio_track(m, out, runner, cache):
    """Render per-beat PCM tracks; mix and fade without changing the authored offsets."""
    (out / 'audio').mkdir(exist_ok=True); (out / 'assets').mkdir(exist_ok=True)
    settings = output_settings(m, _metadata(m, runner.store)); fps = float(Fraction(settings['fps']))
    atomic_json(out / 'output-settings.json', settings)
    durations = []; chunks = []; offset = 0
    for i, beat in enumerate(m.beats):
        v = beat.visual; uses_voice = v.audio in ('voice', 'mix')
        narration = getattr(beat, 'narration_asset', None) or m.narration_asset
        single = bool(getattr(beat, 'narration_asset', None))
        name = f'audio/{i:02d}.wav'; voice_name = f'audio/{i:02d}.voice.wav'; record_name = f'audio/{i:02d}.json'
        if narration and uses_voice:
            path, _ = asset_info(runner.store, narration); shutil.copy2(path, out / 'assets' / narration)
        if v.asset and v.audio in ('source', 'mix'):
            path, _ = asset_info(runner.store, v.asset); shutil.copy2(path, out / 'assets' / v.asset)
        engine = 'imported WAV' if uses_voice and narration else 'eSpeak NG / cmn draft' if uses_voice else v.audio

        def generate():
            duration = beat.duration; voice = out / voice_name
            if uses_voice:
                if narration:
                    command = ['ffmpeg', '-v', 'error', '-y', '-ss', '0' if single else str(offset), '-i', out / 'assets' / narration]
                    if not single: command += ['-t', str(beat.duration)]
                    runner.run(command + ['-vn', '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s16le', voice], label=f'voice-{i}', timeout=_timeout(duration))
                else:
                    text = out / 'audio' / f'{i:02d}.txt'; text.write_text(beat.narration)
                    runner.run(['espeak-ng', '-v', 'cmn', '-s', '175', '-f', text, '-w', voice], label=f'voice-{i}', timeout=_timeout(duration))
                length = _duration(voice)
                if length > duration + .04:
                    if v.mode == 'clip': raise ValueError('Narration exceeds this trimmed clip; extend it or shorten narration: ' + beat.id)
                    duration = length + (.25 if not narration else 0)
            duration = math.ceil(duration * fps - 1e-9) / fps
            if duration > 600: raise ValueError('Narration segment exceeds 600 seconds: ' + beat.id)
            args = ['ffmpeg', '-v', 'error', '-y']; filters = []; inputs = []
            if uses_voice:
                args += ['-i', voice]
                filters += [f'[0:a]aresample=48000,aformat=channel_layouts=stereo,volume={v.voice_gain},apad,atrim=duration={duration}[voice]']
                inputs.append('[voice]')
            if v.audio in ('source', 'mix'):
                index = len(inputs)
                args += ['-ss', str(v.start), '-i', out / 'assets' / v.asset]
                gain = v.source_gain
                filters += [f'[{index}:a:0]aresample=48000,aformat=channel_layouts=stereo,volume={gain},apad,atrim=duration={duration}[source]']
                inputs.append('[source]')
            if not inputs:
                args += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
                filters += [f'[0:a]atrim=duration={duration}[silent]']; inputs.append('[silent]')
            if len(inputs) > 1:
                filters += [''.join(inputs) + f'amix=inputs={len(inputs)}:duration=longest:normalize=0[mixed]']; signal = '[mixed]'
            else: signal = inputs[0]
            fade = min(.03, duration / 4)
            filters += [signal + f'afade=t=in:st=0:d={fade},afade=t=out:st={max(0,duration-fade)}:d={fade},alimiter=limit=0.98:level=false:latency=true[a]']
            runner.run(args + ['-filter_complex', ';'.join(filters), '-map', '[a]', '-t', str(duration), '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s16le', out / name], label=f'audio-{i}', timeout=_timeout(duration))
            atomic_json(out / record_name, {'beat': beat.id, 'wav': name, 'voice_wav': voice_name if uses_voice else None,
                'duration_s': duration, 'authored_start_s': offset, 'engine': engine, 'mode': v.audio,
                'narration_asset': narration, 'voice_gain': v.voice_gain, 'source_gain': v.source_gain,
                'cut_fade_s': fade, 'timing': 'authored beat timing, not word alignment'})

        names = [name, record_name] + ([voice_name] if uses_voice else [])
        cache.run('audio', {'version': 3, 'beat': beat.id, 'index': i, 'narration': beat.narration, 'mode': v.audio, 'engine': engine,
            'duration': beat.duration, 'asset': v.asset, 'narration_asset': narration, 'single': single,
            'offset': offset, 'source_start': v.start, 'voice_gain': v.voice_gain, 'source_gain': v.source_gain,
            'visual_mode': v.mode, 'fps': settings['fps']}, out, names, generate)
        chunk = json.loads((out / record_name).read_text()); durations.append(chunk['duration_s']); chunks.append(chunk)
        offset += beat.duration
    if sum(durations) > 7200: raise ValueError('Narration makes the timeline longer than 7200 seconds')
    atomic_json(out / 'narration.json', {'engine': 'per-scene PCM audio', 'chunks': chunks, 'normalization': 'whole-film two-pass loudness at video export' if settings['normalize_audio'] else 'disabled'})
    return durations


def prepare_visuals(m, out, runner, durations, cache):
    (out / 'assets').mkdir(exist_ok=True); (out / 'posters').mkdir(exist_ok=True)
    metadata = _metadata(m, runner.store); settings = output_settings(m, metadata)
    atomic_json(out / 'output-settings.json', settings)
    atomic_json(out / 'source-media.json', list(metadata.values()))
    records = {}
    for i, beat in enumerate(m.beats):
        v = beat.visual; poster = out / 'posters' / f'{i:02d}.png'; layout = beat_layout(m, beat)
        if v.mode in ('orbit', 'explode'):
            names = [f'motion/{i:02d}.{ext}' for ext in ('mp4', 'png', 'json')]
            cache.run('scene', {'glb': sha256(out / ('scene.glb' if m.scene_asset else 'model.glb')), 'imported':bool(m.scene_asset), 'solids': [s.model_dump() for s in m.solids],
                'brand': m.brand.model_dump(), 'mode': v.mode, 'focus': list(beat.focus), 'animation':m.scene_animation, 'duration': durations[i], 'output': settings}, out, names,
                lambda: runner.run([sys.executable, '-m', 'studio.scene_worker', out, str(i), str(durations[i])], label=f'scene-{i}', timeout=_timeout(durations[i], 30), cwd=ROOT))
            shutil.copy2(out / f'motion/{i:02d}.png', poster)
            records[str(i)] = {'video': f'motion/{i:02d}.mp4', 'poster': str(poster.relative_to(out)), 'mode': v.mode, 'layout': layout}
        elif v.asset:
            path, meta = asset_info(runner.store, v.asset); shutil.copy2(path, out / 'assets' / v.asset)
            if v.mode == 'clip':
                args = ['ffmpeg', '-v', 'error', '-y', '-ss', str(v.start), '-i', path]
                if meta.get('hdr'): args += ['-vf', TONEMAP.rstrip(',')]
                runner.run(args + ['-frames:v', '1', '-threads', '2', poster], label=f'poster-{i}', timeout=60)
            else:
                with Image.open(path) as image:
                    icc = image.info.get('icc_profile'); image = ImageOps.exif_transpose(image)
                    if image.mode not in ('RGB', 'RGBA', 'L', 'LA', 'P'):
                        image = _srgb(image)
                        icc = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes() if icc else None
                    image.save(poster, icc_profile=icc)
            records[str(i)] = {'video': 'assets/' + v.asset if v.mode == 'clip' else None,
                'poster': str(poster.relative_to(out)), 'mode': v.mode, 'layout': layout, 'metadata': meta}
    atomic_json(out / 'visuals.json', records)
    return records


def _srgb(image):
    profile = image.info.get('icc_profile')
    rgba = image.convert('RGBA')
    if profile:
        try:
            source_profile = ImageCms.ImageCmsProfile(io.BytesIO(profile))
            source_mode = {'RGB': 'RGB', 'CMYK': 'CMYK', 'GRAY': 'L', 'Lab': 'LAB'}.get(source_profile.profile.xcolor_space.strip(), image.mode)
            rgb = ImageCms.profileToProfile(image.convert(source_mode), source_profile, ImageCms.createProfile('sRGB'), outputMode='RGB')
            rgba = rgb.convert('RGBA'); rgba.putalpha(image.convert('RGBA').getchannel('A'))
        except (ImageCms.PyCMSError, OSError) as error:
            raise ValueError('Embedded image color profile could not be converted; original asset is retained') from error
    return rgba


def composite_posters(m, out, visuals):
    for key, item in visuals.items():
        target = out / 'slides' / f'{int(key):02d}.png'
        with Image.open(target) as source, Image.open(out / item['poster']) as picture:
            base = source.convert('RGBA'); x, y, width, height = visual_rect(item.get('layout', 'editorial'), *base.size)
            # One alpha-aware composite; keep the original-resolution oriented poster separately.
            base.paste(m.brand.paper, (x, y, x + width, y + height))
            fitted = ImageOps.contain(_srgb(picture), (width, height), Image.Resampling.LANCZOS)
            base.alpha_composite(fitted, (x + (width - fitted.width) // 2, y + (height - fitted.height) // 2))
            overlay_path = out / 'slides' / f'{int(key):02d}.overlay.png'
            if item.get('layout') == 'full' and overlay_path.is_file():
                with Image.open(overlay_path) as overlay:
                    layer = overlay.convert('RGBA')
                    if layer.size != base.size: layer = layer.resize(base.size, Image.Resampling.LANCZOS)
                    base.alpha_composite(layer)
            base.convert('RGB').save(target)


def _concat_quote(path):
    value = str(path.resolve())
    if '\n' in value or '\r' in value: raise ValueError('Newline in concat path')
    return "'" + value.replace("'", "'\\''") + "'"


def _master_audio(out, runner, durations, normalize):
    listing = out / 'audio-concat.txt'
    listing.write_text(''.join('file ' + _concat_quote(out / 'audio' / f'{i:02d}.wav') + '\n' for i in range(len(durations))))
    duration = sum(durations)
    runner.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', listing, '-c:a', 'copy', out / 'mix.wav'], label='audio-assemble', timeout=_timeout(duration))
    filters = []; report = {'enabled': normalize, 'method': 'disabled'}
    # EBU R128 integration uses 400 ms blocks. Pad only the measurement window
    # for shorter programmes, then trim the mastered delivery to its real length.
    analysis_window = max(duration, .4)
    analysis_prefix = f'apad=whole_dur={analysis_window},atrim=duration={analysis_window},'
    if normalize:
        log = runner.run(['ffmpeg', '-hide_banner', '-nostats', '-i', out / 'mix.wav', '-af', analysis_prefix + 'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json', '-vn', '-f', 'null', '-'], label='loudness-measure', timeout=_timeout(duration))
        text = log.read_text(); begin = text.rfind('{'); end = text.rfind('}')
        if begin < 0 or end < begin: raise ValueError('Loudness measurement did not return a result')
        measured = json.loads(text[begin:end + 1]); fields = ('input_i', 'input_tp', 'input_lra', 'input_thresh', 'target_offset')
        if not all(field in measured for field in fields): raise ValueError('Loudness measurement is incomplete')
        values = {field: float(measured[field]) for field in fields}
        if all(math.isfinite(value) for value in values.values()):
            filters = [analysis_prefix + 'loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={input_i}:measured_TP={input_tp}:measured_LRA={input_lra}:measured_thresh={input_thresh}:offset={target_offset}:linear=true:print_format=json'.format(**values)]
            report = {'enabled': True, 'method': 'two-pass', 'measurement': measured, 'target_lufs': -16, 'true_peak_dbtp': -1.5, 'analysis_window_s': analysis_window}
        elif values['input_i'] == -math.inf and values['input_tp'] == -math.inf:
            report = {'enabled': True, 'method': 'silence-preserved', 'measurement': measured}
        else: raise ValueError('Loudness measurement is non-finite for non-silent audio')
    args = ['ffmpeg', '-hide_banner', '-nostats', '-y', '-i', out / 'mix.wav']
    if filters: args += ['-af', ','.join(filters)]
    log = runner.run(args + ['-t', str(duration), '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-ac', '2', out / 'mastered.m4a'], label='loudness-apply', timeout=_timeout(duration))
    if filters:
        text = log.read_text(); begin = text.rfind('{'); end = text.rfind('}')
        if begin >= 0 and end > begin: report['result'] = json.loads(text[begin:end + 1])
    atomic_json(out / 'loudness.json', report)


def render_video(m, source, out, runner, durations, visuals):
    from .pipeline import srt_time, caption_text
    from .content import dimension_rows
    settings = output_settings(m, _metadata(m, runner.store)); atomic_json(out / 'output-settings.json', settings)
    width, height, fps = settings['width'], settings['height'], settings['fps']
    clips = out / 'clips'; clips.mkdir(exist_ok=True)
    segments = []; cues = []; start = 0
    for i, (beat, duration) in enumerate(zip(m.beats, durations)):
        visual = visuals.get(str(i)); v = beat.visual; layout = beat_layout(m, beat)
        args = ['ffmpeg', '-v', 'error', '-y']; filters = []
        # Captions are composed in the segment's sole video encoding generation.
        local_caption = f'caption-{i:02d}.srt'
        if beat.narration.strip():
            cue = caption_text(beat.narration)
            (out / local_caption).write_text(f'1\n{srt_time(0)} --> {srt_time(duration)}\n{cue}\n')
            cues.append(f'{len(cues)+1}\n{srt_time(start)} --> {srt_time(start+duration)}\n{cue}\n')
        if visual and visual.get('video'):
            if v.mode == 'clip': args += ['-ss', str(v.start)]
            args += ['-i', out / visual['video'], '-loop', '1', '-framerate', fps, '-i', out / 'slides' / f'{i:02d}.png']
            x, y, rw, rh = visual_rect(layout, width, height)
            tone = TONEMAP if visual.get('metadata', {}).get('hdr') else ''
            # Compose in RGBA so odd-sized/positioned portrait media boxes are
            # not truncated to chroma-subsampling boundaries by scale or pad.
            filters += [f'[0:v]setpts=PTS-STARTPTS,{tone}format=rgba,scale=iw*sar:ih,setsar=1,scale={rw}:{rh}:force_original_aspect_ratio=decrease,pad={rw}:{rh}:(ow-iw)/2:(oh-ih)/2:color={m.brand.paper},setsar=1,fps={fps},tpad=stop_mode=clone:stop_duration=1[scene]',
                        f'[1:v]scale={width}:{height},setsar=1[base]', f'[base][scene]overlay={x}:{y}:shortest=1:format=auto[composite]']
        else:
            args += ['-loop', '1', '-framerate', fps, '-i', out / 'slides' / f'{i:02d}.png']
            filters += [f'[0:v]scale={width}:{height},setsar=1,fps={fps}[composite]']
        caption = f",subtitles={local_caption}:force_style='FontName=Noto Sans CJK TC,FontSize=17,Outline=1,MarginV=34'" if beat.narration.strip() and settings['captions'] else ''
        final_input = 'composite'
        overlay = out / 'slides' / f'{i:02d}.overlay.png'
        if layout == 'full' and visual and visual.get('video') and overlay.is_file():
            args += ['-loop', '1', '-framerate', fps, '-i', overlay]
            filters += [f'[2:v]scale={width}:{height},format=rgba[textlayer]', '[composite][textlayer]overlay=0:0:shortest=1:format=auto[withtext]']
            final_input = 'withtext'
        # Match RGB composition to the BT.709 metadata written below, rather
        # than letting FFmpeg's default RGB conversion choose a BT.601 matrix.
        filters += [f'[{final_input}]setpts=PTS-STARTPTS{caption},scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[v]']
        frames = round(duration * float(Fraction(fps)))
        runner.run(args + ['-filter_complex', ';'.join(filters), '-map', '[v]', '-an', '-frames:v', str(frames), '-r', fps,
            '-c:v', 'libx264', '-threads', '2', '-filter_complex_threads', '2', '-preset', 'fast', '-crf', str(settings['crf']),
            '-pix_fmt', 'yuv420p', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
            '-video_track_timescale', str(Fraction(fps).numerator), clips / f'{i:02d}.mp4'], label=f'video-{i}', timeout=_timeout(duration, 30), cwd=out)
        segments.append({'beat': beat.id, 'mode': v.mode, 'layout': layout,
            'source': (visual.get('video') or visual['poster']) if visual else f'slides/{i:02d}.png',
            'asset': v.asset, 'source_start': v.start if v.mode == 'clip' else 0, 'audio_mode': v.audio,
            'narration_asset': getattr(beat, 'narration_asset', None) or m.narration_asset,
            'audio': f'audio/{i:02d}.wav', 'video': f'clips/{i:02d}.mp4', 'start': round(start, 6), 'end': round(start + duration, 6),
            'frames': frames, 'dimensions': dimension_rows(m), 'source_metadata': visual.get('metadata') if visual else None})
        start += duration
    (out / 'captions.srt').write_text('\n'.join(cues))
    atomic_json(out / 'edit.edl.json', {'schema_version': 3, 'manifest_sha256': source.digest(), 'duration_s': round(start, 6),
        **settings, 'segments': segments, 'caption_timing': 'authored beat timing; not ASR word alignment',
        'video_generations': {'import': 0, 'composition': 1, 'concat': 0, 'final_mux': 0}, 'original_media_preserved': True})
    runner.run([sys.executable, '-m', 'studio.media_worker', out], label='video-use-concat', timeout=_timeout(start), cwd=ROOT)
    _master_audio(out, runner, durations, settings['normalize_audio'])
    runner.run(['ffmpeg', '-v', 'error', '-y', '-i', out / 'base.mp4', '-i', out / 'mastered.m4a', '-map', '0:v:0', '-map', '1:a:0',
        '-c:v', 'copy', '-c:a', 'copy', '-t', str(start), '-movflags', '+faststart', out / 'film.mp4'], label='final-video', timeout=_timeout(start), cwd=out)
