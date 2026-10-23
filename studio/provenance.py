"""Content identity of the code and native runtimes actually used to render."""
import hashlib
import json
import subprocess
from pathlib import Path
from functools import lru_cache
from .paths import ROOT,SOURCES
from .runtime import browser_executable

RUNTIME_SLUGS=('tt-a1i--archify','hugohe3--ppt-master')

def sources():
    return json.loads((ROOT/'vendor/sources.lock.json').read_text(encoding='utf-8'))

def runtime_sources():
    verified={}
    for entry in sources():
        if entry['slug'] not in RUNTIME_SLUGS:continue
        path=SOURCES/entry['slug']
        try:
            head=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True,stderr=subprocess.DEVNULL,timeout=10).strip()
            clean=subprocess.run(['git','-C',str(path),'diff','--quiet','HEAD','--'],timeout=10).returncode==0
            untracked=subprocess.check_output(['git','-C',str(path),'ls-files','--others','--exclude-standard'],text=True,timeout=10).strip()
        except (OSError,subprocess.SubprocessError):
            raise ValueError('sources_drift: missing or unreadable '+entry['slug']) from None
        if head!=entry['commit'] or not clean or untracked:
            raise ValueError('sources_drift: runtime checkout differs from the source lock: '+entry['slug'])
        verified[entry['slug']]=head
    if set(verified)!=set(RUNTIME_SLUGS):raise ValueError('sources_drift: runtime lock entry missing')
    return verified

@lru_cache(maxsize=1)
def native_versions():
    results={}
    for command in (['ffmpeg','-version'],['espeak-ng','--version'],['node','--version'],['bwrap','--version'],[browser_executable(),'--version']):
        results[command[0]]=subprocess.check_output(command,text=True,stderr=subprocess.STDOUT,timeout=10).splitlines()[0]
    return results

def engine_fingerprint():
    h=hashlib.sha256()
    h.update(json.dumps(runtime_sources(),sort_keys=True).encode())
    h.update(json.dumps(native_versions(),sort_keys=True).encode())
    from importlib.metadata import version
    for package in ('cadgen','build123d','cadquery-ocp-novtk','python-pptx','cairosvg','pillow','playwright'):
        h.update((package+'='+version(package)).encode())
    names=('vendor/sources.lock.json','requirements.lock.txt','package-lock.json',
           'studio/pipeline.py','studio/content.py','studio/schema.py','studio/cad_worker.py',
           'studio/ppt_worker.py','studio/media_worker.py','studio/stage_cache.py','studio/media_assets.py','studio/scene_worker.py','studio/video.py','studio/runner.py','studio/provenance.py','studio/paths.py','studio/runtime.py',
           'scripts/anatomy.mjs','scripts/glb-check.mjs','web/published.css','web/copy.json','dist/viewer.js')
    paths=sorted(set([ROOT/name for name in names]+list((ROOT/'studio').glob('*.py'))+list((ROOT/'scripts').glob('*.mjs'))+[ROOT/f['vendored'] for source in sources() for f in source['files']]))
    for path in paths:
        h.update(str(path.relative_to(ROOT)).encode());h.update(path.read_bytes())
    font=Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
    if font.is_file():h.update(font.read_bytes())
    return h.hexdigest()
