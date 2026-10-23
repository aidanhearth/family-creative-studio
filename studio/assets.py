"""Content-addressed original PCM WAV imports."""
import hashlib
import io
import wave
from pathlib import Path
from .paths import contained, atomic_json

AUDIO_LIMIT = 512 * 1024 * 1024


def audio_metadata(data):
    if not data or len(data) > AUDIO_LIMIT: raise ValueError('WAV is limited to 512 MiB')
    try:
        with wave.open(io.BytesIO(data), 'rb') as audio:
            frames, rate, channels = audio.getnframes(), audio.getframerate(), audio.getnchannels()
            width = audio.getsampwidth(); duration = frames / rate
            if not .1 <= duration <= 7200 or channels not in (1, 2) or not 8000 <= rate <= 192000 or width not in (1, 2, 3, 4):
                raise ValueError('WAV must be 0.1–7200 seconds, mono/stereo PCM, 8–192 kHz')
            remaining = frames
            while remaining:
                count = min(remaining, 65536)
                if len(audio.readframes(count)) != count * channels * width: raise ValueError('WAV data is truncated')
                remaining -= count
    except (wave.Error, EOFError, ZeroDivisionError) as error:
        raise ValueError('WAV must be a valid uncompressed PCM file') from error
    return {'kind': 'audio', 'duration_s': duration, 'sample_rate': rate, 'channels': channels,
            'sample_width': width, 'original_preserved': True, 'transcoded': False}


def import_audio(store, data, name=None):
    meta = audio_metadata(data)
    key = hashlib.sha256(data).hexdigest() + '.wav'
    root = store.root / 'assets'; root.mkdir(exist_ok=True)
    path = contained(root, key)
    if not path.exists():
        import uuid
        temp = root / (uuid.uuid4().hex + '.tmp'); temp.write_bytes(data); temp.replace(path)
    meta.update(asset=key, bytes=len(data), label=''.join(c for c in Path(name or key).name[:120] if c.isprintable()))
    atomic_json(root / (key + '.json'), meta)
    return meta
