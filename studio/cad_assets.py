"""Original STEP intake, inspected by an isolated CAD child process."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

from .paths import ROOT, atomic_json, contained
from .runner import Runner

CAD_LIMIT = 50 * 1024 * 1024


class ImportStore:
    def __init__(self, root):
        self.root = root

    def job(self, _):
        return {'cancel': False}


def import_cad(store, data, name=None):
    if not data or len(data) > CAD_LIMIT or not data.lstrip().startswith(b'ISO-10303-21;'):
        raise ValueError('CAD import accepts ISO-10303-21 STEP files up to 50 MiB')
    key = hashlib.sha256(data).hexdigest() + '.step'
    assets = store.root / 'assets'
    assets.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cad-import-', dir=store.root) as folder:
        work = Path(folder)
        original = work / key
        original.write_bytes(data)
        runner = Runner(ImportStore(work), {'id': 'cad-import'}, work)
        try:
            runner.run([sys.executable, '-m', 'studio.cad_inspect', original, work / 'metadata.json'], label='cad-inspect', timeout=90, cwd=ROOT)
        except (RuntimeError, TimeoutError) as exc:
            raise ValueError('STEP inspection failed; the file must contain valid bounded solid CAD') from exc
        meta = json.loads((work / 'metadata.json').read_text())
        target = contained(assets, key)
        shutil.copy2(original, target)
        meta.update(asset=key, bytes=len(data), original_preserved=True,
                    label=''.join(c for c in Path(name or key).name[:120] if c.isprintable()))
        atomic_json(assets / (key + '.json'), meta)
        return meta
