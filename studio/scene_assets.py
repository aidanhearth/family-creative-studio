"""Content-addressed, self-contained GLB scene imports, with original bytes kept."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from .cad_assets import ImportStore
from .paths import ROOT, atomic_json, contained
from .runner import Runner
from .scene_document import read_document

SCENE_LIMIT = 50 * 1024 * 1024


def import_scene(store, data, name=None):
    if not data or len(data) > SCENE_LIMIT or not data.startswith(b'glTF'):
        raise ValueError('Scene import accepts a self-contained GLB up to 50 MiB')
    key = hashlib.sha256(data).hexdigest() + '.glb'
    assets = store.root / 'assets'; assets.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='scene-import-', dir=store.root) as folder:
        work = Path(folder); original = work / key; original.write_bytes(data)
        try:
            _, _, structure = read_document(original)
            runner = Runner(ImportStore(work), {'id': 'scene-import'}, work)
            runner.run(['node', ROOT / 'scripts/scene-inspect.mjs', original, work / 'metadata.json'], label='scene-inspect', timeout=60, cwd=ROOT)
            meta = dict(json.loads((work / 'metadata.json').read_text()), **structure)
        except (ValueError, RuntimeError, TimeoutError, KeyError, IndexError, TypeError, AttributeError, RecursionError, OSError, Warning) as exc:
            raise ValueError(f'GLB inspection failed: {exc}') from exc
        shutil.copy2(original, contained(assets,key))
        meta.update(asset=key, bytes=len(data), original_preserved=True, materials_preserved=True, animations_preserved=True,
                    label=''.join(c for c in Path(name or key).name[:120] if c.isprintable()))
        atomic_json(assets / (key + '.json'), meta)
        return meta
