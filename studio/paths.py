from pathlib import Path
import hashlib
import os

ROOT = Path(__file__).resolve().parent.parent
SOURCES = Path(os.environ.get("STUDIO_SOURCES", str(ROOT / ".sources"))).resolve()

def data_root() -> Path:
    path = Path(os.environ.get("STUDIO_DATA", str(ROOT / ".state"))).resolve()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path

def contained(root: Path, name: str) -> Path:
    if Path(name).is_absolute():
        raise ValueError("Absolute artifact paths are not accepted")
    candidate = (root / name).resolve()
    if not candidate.is_relative_to(root.resolve()) or candidate == root.resolve():
        raise ValueError("Path leaves its artifact directory")
    return candidate

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def atomic_json(path: Path, value) -> None:
    import json
    import uuid
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with tmp.open('w',encoding='utf-8') as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
            stream.flush(); os.fsync(stream.fileno())
        tmp.replace(path)
        fd=os.open(path.parent,os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        tmp.unlink(missing_ok=True)
