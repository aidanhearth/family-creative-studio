"""Portable PowerPoint movies with authored trims and explicit audio semantics."""
import json
from pathlib import Path

from .paths import atomic_json


def _audio_options(beat, duration: float, separate_track: bool) -> list[str]:
    """Disabling narration removes voice, without silently substituting source audio."""
    if separate_track or beat.visual.audio in ('voice', 'silent'):
        return ['-an']
    # With narration disabled, source and mix retain only their source component.
    # Apply the same source gain, cut fades and limiter as the film audio path.
    fade = min(.03, duration / 4)
    filters = (f'aresample=48000,aformat=channel_layouts=stereo,volume={beat.visual.source_gain},'
               f'apad,atrim=duration={duration},afade=t=in:st=0:d={fade},'
               f'afade=t=out:st={max(0, duration-fade)}:d={fade},'
               'alimiter=limit=0.98:level=false:latency=true')
    return ['-map', '0:a:0', '-af', filters, '-c:a', 'aac', '-ar', '48000', '-ac', '2']


def prepare_movies(manifest, out: Path, runner, visuals: dict, durations: list[float]) -> None:
    """Embed muted video beside separate narration, or the requested source component."""
    folder = out / 'ppt-media'
    folder.mkdir(exist_ok=True)
    settings = json.loads((out / 'output-settings.json').read_text())
    for key, visual in visuals.items():
        if not visual.get('video'):
            continue
        index = int(key)
        beat = manifest.beats[index]
        args = ['ffmpeg', '-v', 'error', '-y']
        if beat.visual.mode == 'clip':
            args += ['-ss', str(beat.visual.start)]
        args += ['-i', out / visual['video'], '-map', '0:v:0']
        from .video import TONEMAP
        tone = TONEMAP if visual.get('metadata', {}).get('hdr') else ''
        args += ['-t', str(durations[index]), '-vf', tone + f'scale=trunc(iw*sar/2)*2:trunc(ih/2)*2,setsar=1,fps={settings["fps"]}',
                 '-c:v', 'libx264', '-crf', str(settings['crf']), '-pix_fmt', 'yuv420p', '-threads', '2']
        args += _audio_options(beat, durations[index], manifest.slides.narration)
        target = folder / f'{index:02d}.mp4'
        runner.run(args + ['-movflags', '+faststart', target], label=f'ppt-movie-{index}',
                   timeout=max(90, durations[index]*20))
        visual['ppt_video'] = str(target.relative_to(out))
        visual['ppt_audio_mode'] = ('separate-track' if manifest.slides.narration else
                                    'source' if beat.visual.audio in ('source', 'mix') else 'silent')
        if visual['ppt_audio_mode'] == 'source':
            visual['ppt_source_gain'] = beat.visual.source_gain
    atomic_json(out / 'visuals.json', visuals)
