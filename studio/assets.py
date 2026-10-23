import hashlib
import io
import wave
from .paths import contained

def import_audio(store,data):
    if len(data)>24*1024*1024:raise ValueError('WAV is limited to 24 MiB')
    try:
        opened=wave.open(io.BytesIO(data),'rb')
    except (wave.Error,EOFError) as error:
        raise ValueError('WAV must be a valid uncompressed PCM file') from error
    with opened as audio:
        frames=audio.getnframes();rate=audio.getframerate();duration=frames/rate
        if not 1<=duration<=120 or audio.getnchannels() not in (1,2) or not 8000<=rate<=96000:
            raise ValueError('WAV must be 1–120 seconds, mono/stereo, 8–96 kHz')
        if len(audio.readframes(frames))!=frames*audio.getnchannels()*audio.getsampwidth():
            raise ValueError('WAV data is truncated')
    key=hashlib.sha256(data).hexdigest()+'.wav'
    root=store.root/'assets';root.mkdir(exist_ok=True)
    path=contained(root,key)
    if not path.exists():
        import uuid
        temp=root/(uuid.uuid4().hex+'.tmp');temp.write_bytes(data);temp.replace(path)
    return {'asset':key,'duration_s':duration,'bytes':len(data)}
