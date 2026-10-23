"""Bounded, content-addressed agent uploads; never accept arbitrary host paths."""
import base64
import binascii
import re
from .paths import contained, sha256

INLINE_LIMIT = 8 * 1024 * 1024


def import_inline(store, kind, encoded, name=None):
    if len(encoded) > (INLINE_LIMIT + 2) // 3 * 4:
        raise ValueError('Inline uploads are limited to 8 MiB; use HTTP or CLI for larger files')
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError('Upload must be valid base64') from None
    if len(data) > INLINE_LIMIT:
        raise ValueError('Inline uploads are limited to 8 MiB')
    if kind == 'audio':
        from .assets import import_audio as importer
    elif kind == 'cad':
        from .cad_assets import import_cad as importer
    elif kind == 'scene':
        from .scene_assets import import_scene as importer
    elif kind == 'svg':
        from .svg_assets import import_svg as importer
    elif kind == 'media':
        from .media_assets import import_media as importer
    else:
        raise ValueError('Choose audio, media, cad, scene or svg')
    return importer(store, data, name)


def asset_path(store, name):
    if not re.fullmatch(r'[a-f0-9]{64}\.(png|jpg|mp4|wav|step|glb|svg)', name):
        raise ValueError('Invalid asset ID')
    path = contained(store.root / 'assets', name)
    if not path.is_file():
        raise KeyError(name)
    if sha256(path) != name.split('.')[0]:
        raise ValueError('Asset hash mismatch')
    return path
