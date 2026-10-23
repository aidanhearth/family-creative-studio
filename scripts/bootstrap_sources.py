"""Download immutable public runtime checkouts; never overwrite an existing checkout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = {'tt-a1i--archify', 'hugohe3--ppt-master'}

def run(args: list[str]) -> str:
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all', action='store_true', help='Also download the ten research-only upstreams; no models or Git LFS assets')
    args = parser.parse_args()
    sources = Path(os.environ.get('STUDIO_SOURCES', str(ROOT / '.sources'))).resolve()
    sources.mkdir(parents=True, exist_ok=True)
    entries = json.loads((ROOT / 'vendor/sources.lock.json').read_text())
    for entry in entries:
        for item in entry['files']:
            actual = hashlib.sha256((ROOT / item['vendored']).read_bytes()).hexdigest()
            if actual != item['sha256']:
                raise ValueError('Vendored hash differs: ' + item['vendored'])
        if not args.all and entry['slug'] not in RUNTIME:
            continue
        slug, commit, url = entry['slug'], entry['commit'], entry['repository']
        if not re.fullmatch(r'[\w.-]+--[\w.-]+', slug) or not re.fullmatch(r'[0-9a-f]{40}', commit):
            raise ValueError('Invalid source identity')
        if not re.fullmatch(r'https://github.com/[\w.-]+/[\w.-]+', url):
            raise ValueError('Expected a public GitHub HTTPS source')
        target = sources / slug
        if not target.exists():
            # A failed download remains in its uniquely named directory for diagnosis.
            pending = Path(tempfile.mkdtemp(prefix='.download-', dir=sources))
            run(['git', 'init', '-q', str(pending)])
            run(['git', '-C', str(pending), 'remote', 'add', 'origin', url + '.git'])
            run(['git', '-C', str(pending), 'fetch', '--depth=1', 'origin', commit])
            env = dict(os.environ, GIT_LFS_SKIP_SMUDGE='1')
            subprocess.run(['git', '-C', str(pending), 'checkout', '-q', '--detach', 'FETCH_HEAD'], env=env, check=True)
            pending.rename(target)
        head = run(['git', '-C', str(target), 'rev-parse', 'HEAD'])
        dirty = run(['git', '-C', str(target), 'status', '--porcelain'])
        if head != commit or dirty:
            raise ValueError('Existing checkout differs; preserve it and choose another STUDIO_SOURCES: ' + slug)
        print(slug + ' ' + commit)
    print('Pinned sources and vendored checksums verified.')

if __name__ == '__main__':
    main()
