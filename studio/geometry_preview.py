"""Exact draft CAD previews with verified source and output identities."""
import fcntl
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import uuid

from .paths import ROOT, atomic_json, contained, sha256
from .runner import Runner

PREVIEW_OUTPUTS = ('model.step', 'model.stl', 'model.glb', 'geometry.json', 'cad-check.json')


def checked_cad_assets(store, manifest) -> dict[str, Path]:
    """Verify each original STEP even when a previously rendered preview exists."""
    assets = {}
    for solid in manifest.solids:
        if not solid.asset or solid.asset in assets:
            continue
        source = contained(store.root / 'assets', solid.asset)
        if not source.is_file() or sha256(source) != solid.asset.split('.')[0]:
            raise ValueError('Missing or changed STEP asset: ' + solid.asset)
        assets[solid.asset] = source
    return assets


def copy_cad_assets(store, manifest, output: Path) -> None:
    """Copy verified STEP inputs into the isolated CAD worker's input folder."""
    folder = output / 'cad-assets'
    folder.mkdir(exist_ok=True)
    for name, source in checked_cad_assets(store, manifest).items():
        shutil.copy2(source, folder / name)


def preview_valid(destination: Path, key: str) -> bool:
    """Check every required output against the receipt before reusing a preview."""
    if destination.is_symlink() or not destination.is_dir():
        return False
    try:
        receipt_path = destination / 'receipt.json'
        if receipt_path.is_symlink():
            return False
        receipt = json.loads(receipt_path.read_text())
        outputs = receipt['outputs']
        if receipt['version'] != 1 or receipt['key'] != key or set(outputs) != set(PREVIEW_OUTPUTS):
            return False
        for name in PREVIEW_OUTPUTS:
            path = destination / name
            if path.is_symlink() or not path.is_file() or sha256(path) != outputs[name]:
                return False
        return json.loads((destination / 'cad-check.json').read_text()).get('valid') is True
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False


def preview_file_path(store, key: str, name: str) -> Path:
    """Return only a verified public preview artifact, never arbitrary paths."""
    if not re.fullmatch(r'[a-f0-9]{64}', key) or name not in ('model.glb', 'geometry.json'):
        raise ValueError('Invalid geometry preview identifier')
    destination = contained(store.root / 'previews', key)
    if not preview_valid(destination, key):
        raise ValueError('Geometry preview is missing or changed; rebuild the preview')
    return contained(destination, name)


class PreviewStore:
    def __init__(self, root: Path):
        self.root = root

    def job(self, _) -> dict[str, bool]:
        return {'cancel': False}


def _build_preview(store, manifest, destination: Path, key: str) -> None:
    with tempfile.TemporaryDirectory(prefix='preview-', dir=destination.parent) as temporary:
        work = Path(temporary)
        copy_cad_assets(store, manifest, work)
        (work / 'manifest.json').write_text(manifest.canonical())
        runner = Runner(PreviewStore(store.root), {'id': 'draft-preview'}, work)
        runner.run([sys.executable, '-m', 'studio.cad_worker', work / 'manifest.json', work],
                   label='preview-cad', timeout=180, cwd=ROOT)
        atomic_json(work / 'receipt.json', {'version': 1, 'key': key,
                    'outputs': {name: sha256(work / name) for name in PREVIEW_OUTPUTS}})
        if not preview_valid(work, key):
            raise ValueError('CAD preview did not produce a complete verified output set')
        # Preserve damaged caches for diagnosis; no published directory is partial.
        if destination.exists() or destination.is_symlink():
            destination.rename(destination.with_name(key + '.invalid-' + uuid.uuid4().hex))
        work.rename(destination)


def preview_geometry(store, manifest) -> dict:
    """Build or reuse exact draft CAD without changing project revisions."""
    if not manifest.solids:
        raise ValueError('Add at least one CAD part')
    manifest = manifest.resolved()
    from .provenance import engine_fingerprint
    key = hashlib.sha256((json.dumps([s.model_dump() for s in manifest.solids], sort_keys=True)
                          + engine_fingerprint()).encode()).hexdigest()
    root = store.root / 'previews'
    root.mkdir(exist_ok=True)
    destination = root / key
    with (root / 'preview.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('A geometry preview is already running; retry when it completes') from None
        checked_cad_assets(store, manifest)
        if not preview_valid(destination, key):
            _build_preview(store, manifest, destination, key)
        geometry = json.loads((destination / 'geometry.json').read_text())
        validation = json.loads((destination / 'cad-check.json').read_text())
    return {'url': f'/api/previews/{key}/model.glb', 'key': key, 'geometry': geometry,
            'saved': False, 'validation': validation}
