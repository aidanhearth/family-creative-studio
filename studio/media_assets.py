"""Bounded local media inspection; the content-addressed upload is preserved verbatim."""
import io
import json
import math
from fractions import Fraction
from pathlib import Path
import shutil
import tempfile
import warnings
from PIL import Image
from .paths import contained, atomic_json, sha256
from .runner import Runner

LIMIT = 512 * 1024 * 1024
IMAGE_PIXELS = 64_000_000


class ImportStore:
    def __init__(self, root): self.root = root
    def job(self, _): return {'cancel': False}


def _rate(value):
    try:
        result = Fraction(str(value))
        return result if result > 0 else None
    except (ValueError, ZeroDivisionError):
        return None


def _video_metadata(info):
    streams = info.get('streams', [])
    videos = [s for s in streams if s.get('codec_type') == 'video' and not s.get('disposition', {}).get('attached_pic')]
    if len(videos) != 1 or len(streams) > 16:
        raise ValueError('Video must contain exactly one picture track and at most 16 tracks')
    v = videos[0]
    duration = float(v.get('duration') or info.get('format', {}).get('duration') or 0)
    width, height = int(v.get('width', 0)), int(v.get('height', 0))
    fps = _rate(v.get('avg_frame_rate')) or _rate(v.get('r_frame_rate'))
    if not math.isfinite(duration) or not .1 <= duration <= 7200 or not 16 <= width <= 8192 or not 16 <= height <= 8192 or width * height > IMAGE_PIXELS or not fps or fps > 120 or fps.numerator > 2_000_000_000:
        raise ValueError('Video limits: 0.1–7200 seconds, 8192 pixels per side, 64 megapixels, 120 fps')
    sar = _rate(str(v.get('sample_aspect_ratio', '1:1')).replace(':', '/')) or Fraction(1)
    display_width = round(width * sar)
    rotation = next((s.get('rotation', 0) for s in v.get('side_data_list', []) if 'rotation' in s), v.get('tags', {}).get('rotate', 0))
    rotation = float(rotation)
    if not math.isfinite(rotation) or abs(rotation / 90 - round(rotation / 90)) > .001:
        raise ValueError('Video display rotation must be a multiple of 90 degrees')
    display_height = height
    if round(rotation) % 180: display_width, display_height = display_height, display_width
    if not 16 <= display_width <= 8192 or not 16 <= display_height <= 8192:
        raise ValueError('Video display geometry exceeds 8192 pixels')
    color = {k: v[k] for k in ('color_space', 'color_transfer', 'color_primaries', 'color_range', 'pix_fmt', 'bits_per_raw_sample') if k in v}
    return {'kind': 'clip', 'duration_s': duration, 'audio': any(s.get('codec_type') == 'audio' for s in streams),
            'width': width, 'height': height, 'display_width': display_width, 'display_height': display_height,
            'fps': str(fps), 'codec': v.get('codec_name'), 'sample_aspect_ratio': str(sar), 'rotation': rotation,
            'color': color, 'hdr': v.get('color_transfer') in ('smpte2084', 'arib-std-b67'), 'transcoded': False}


def _import_media(store, data, name=None):
    if not data or len(data) > LIMIT: raise ValueError('Media must be PNG/JPEG/MP4/MOV, at most 512 MiB')
    assets = store.root / 'assets'; assets.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='import-', dir=store.root) as folder:
        work = Path(folder); runner = Runner(ImportStore(work), {'id': 'import'}, work)
        if data.startswith((b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff')):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('error', Image.DecompressionBombWarning)
                    with Image.open(io.BytesIO(data)) as img:
                        if img.width * img.height > IMAGE_PIXELS or getattr(img, 'n_frames', 1) != 1:
                            raise ValueError('Image must be a single frame of at most 64 megapixels')
                        img.load()
                        orientation = img.getexif().get(274, 1)
                        w, h = img.size
                        if orientation in (5, 6, 7, 8): w, h = h, w
                        suffix = '.png' if img.format == 'PNG' else '.jpg'
                        meta = {'kind': 'image', 'width': img.width, 'height': img.height, 'display_width': w, 'display_height': h,
                                'mode': img.mode, 'alpha': 'A' in img.getbands() or 'transparency' in img.info,
                                'icc_profile': bool(img.info.get('icc_profile')), 'orientation': orientation, 'transcoded': False}
            except (OSError, Warning, Image.DecompressionBombError) as error:
                raise ValueError('Image could not be decoded safely') from error
            original = work / ('input' + suffix); original.write_bytes(data)
        elif len(data) > 12 and data[4:8] == b'ftyp':
            original = work / 'input.mp4'; original.write_bytes(data)
            probe = runner.run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-f', 'mov', '-show_streams', '-show_format', '-of', 'json', original], label='probe', timeout=30)
            meta = _video_metadata(json.loads(probe.read_text()))
        else:
            raise ValueError('Media must be a real PNG/JPEG image or an MP4/MOV video')
        key = sha256(original) + original.suffix; target = contained(assets, key)
        if not target.exists() or sha256(target) != key.rsplit('.', 1)[0]:
            import uuid
            temporary = assets / (uuid.uuid4().hex + '.tmp')
            shutil.copy2(original, temporary); temporary.replace(target)
        meta.update(asset=key, bytes=target.stat().st_size, original_preserved=True,
                    label=''.join(c for c in Path(name or key).name[:120] if c.isprintable()))
        atomic_json(assets / (key + '.json'), meta)
        return meta


def asset_info(store, key):
    path = contained(store.root / 'assets', key)
    if not path.is_file() or sha256(path) != key.rsplit('.', 1)[0]: raise ValueError('Media asset missing or changed: ' + key)
    metadata = path.with_name(path.name + '.json')
    # Previously imported WAV files did not have metadata. Inspect them without modifying them.
    if key.endswith('.wav') and not metadata.exists():
        from .assets import audio_metadata
        info = dict(audio_metadata(path.read_bytes()), asset=key, bytes=path.stat().st_size)
    else: info = json.loads(metadata.read_text())
    if info.get('asset') != key: raise ValueError('Media metadata does not match asset')
    return path, info


def preflight(store, m, targets):
    if 'cad' in targets and not m.solids: raise ValueError('CAD output needs at least one solid; choose other outputs for media-only stories')
    assets = {}; offset = 0
    if m.scene_asset:
        _,meta=asset_info(store,m.scene_asset)
        if meta.get('kind')!='scene':raise ValueError('Scene asset is not an inspected GLB')
        if m.scene_animation and m.scene_animation>=len(meta.get('animations',[])):raise ValueError('Selected scene animation does not exist')
        if any(b.visual.mode=='explode' for b in m.beats) and meta.get('part_count',0)<2:raise ValueError('Imported scene needs at least two parts for explosion')
        assets[m.scene_asset]=meta
    for solid in m.solids:
        if solid.asset:
            _,meta=asset_info(store,solid.asset)
            if meta.get('kind')!='cad':raise ValueError('STEP asset is not a valid CAD import')
            assets[solid.asset]=meta
    for beat in m.beats:
        if beat.svg_asset:
            _,meta=asset_info(store,beat.svg_asset)
            if meta.get('kind')!='svg':raise ValueError('Slide source must be an imported editable SVG')
            assets[beat.svg_asset]=meta
        if beat.visual.asset:
            _, meta = asset_info(store, beat.visual.asset); assets[beat.visual.asset] = meta
            if meta['kind'] != beat.visual.mode: raise ValueError('Scene does not match imported asset')
            if beat.visual.mode == 'clip':
                if beat.visual.start + beat.duration > meta['duration_s'] + .04: raise ValueError('Clip trim exceeds source duration: ' + beat.id)
                if beat.visual.audio in ('source', 'mix') and not meta['audio']: raise ValueError('Clip has no source audio: ' + beat.id)
        narration = getattr(beat, 'narration_asset', None) or m.narration_asset
        if narration and beat.visual.audio in ('voice', 'mix'):
            _, meta = asset_info(store, narration); assets[narration] = meta
            begin = 0 if getattr(beat, 'narration_asset', None) else offset
            if meta['kind'] != 'audio' or (begin + beat.duration > meta['duration_s'] + .04 and not getattr(beat, 'narration_asset', None)):
                raise ValueError('Narration WAV does not cover authored interval: ' + beat.id)
            if beat.visual.mode == 'clip' and getattr(beat, 'narration_asset', None) and meta['duration_s'] > beat.duration + .04:
                raise ValueError('Narration exceeds trimmed clip: ' + beat.id)
        offset += beat.duration
    return {'ready': True, 'targets': targets, 'assets': list(assets.values()), 'moving_beats': [b.id for b in m.beats if b.visual.mode in ('orbit', 'explode')]}


def import_media(store, data, name=None):
    try: return _import_media(store, data, name)
    except (RuntimeError, TimeoutError, ZeroDivisionError, KeyError, json.JSONDecodeError) as error:
        raise ValueError('Media could not be inspected within local limits; check the container and source metadata') from error
