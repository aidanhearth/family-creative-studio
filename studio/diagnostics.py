import importlib.util
import subprocess
from pathlib import Path
import shutil
from .paths import ROOT,SOURCES,data_root

def namespace_available() -> bool:
    try:
        result = subprocess.run(['bwrap','--unshare-net','--unshare-pid','--die-with-parent',
            '--ro-bind','/','/','--dev','/dev','--proc','/proc','--','/bin/true'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False

def doctor():
    checks={name:bool(shutil.which(name)) for name in ('node','ffmpeg','ffprobe','espeak-ng','bwrap')}
    from .runtime import browser_executable
    try: browser_executable(); checks['browser'] = True
    except FileNotFoundError: checks['browser'] = False
    checks['namespace_isolation'] = namespace_available()
    checks['cjk_font'] = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc').is_file()
    checks.update({name:importlib.util.find_spec(name) is not None for name in ('cadgen','pptx','cairosvg','playwright','mcp')})
    checks['ui_bundle']=(ROOT/'dist/app.js').is_file()
    checks['archify']=(SOURCES/'tt-a1i--archify/archify/bin/archify.mjs').is_file()
    checks['ppt_master']=(SOURCES/'hugohe3--ppt-master/skills/ppt-master/scripts/svg_to_pptx/pptx_package/builder.py').is_file()
    from .provenance import runtime_sources
    try: runtime_sources();checks['sources_pinned']=True;source_error=None
    except ValueError as error: checks['sources_pinned']=False;source_error=str(error)
    from .worker import worker_alive
    usage=shutil.disk_usage(data_root())
    return {'version':'0.3.0','ready':all(checks.values()),'checks':checks,'free_gib':round(usage.free/2**30,2),
        'sources_status':source_error or 'pinned and clean','worker_alive':worker_alive(data_root()),
        'network':'Render subprocesses use Linux network/PID namespaces; updates and telemetry disabled. No paid model calls.',
        'audio':'Per chapter: imported WAV / eSpeak draft, original audio, mixing or silence; gains, cut fades and two-pass whole-film loudness. VoiceStudio models and ASR are separate engines.',
        'video':'Original PNG/JPEG/MP4/MOV bytes retained; source or 720p/1080p/2160p canvas, source or 24/25/30/50/60 fps; SDR composition with explicit HDR tone mapping.',
        'editing':'Three recipes, local drafts and undo; 2048-operation atomic revisions; exact CAD previews, asset import, editable timelines and verified stage reuse.',
        'geometry':'Box/cylinder/sphere/cone/torus/polygon extrusion, STEP import, XYZ rotation, booleans, fillet/chamfer. Independent original GLB scene import preserves materials and animations; no image-to-3D generator.',
        'artistic_quality':'Not scored automatically; no claim of superiority to every upstream tool.'}
