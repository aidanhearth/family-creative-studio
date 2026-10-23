"""Offline, bounded media import. Only decoded PNG/JPEG and MOV-family MP4 containers."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import warnings
from PIL import Image, ImageOps
from .paths import contained, atomic_json, sha256
from .runner import Runner

LIMIT=50*1024*1024

class ImportStore:
    def __init__(self,root):self.root=root
    def job(self,_):return {'cancel':False}

def _import_media(store,data,name=None):
    if not data or len(data)>LIMIT:raise ValueError('Media must be PNG/JPEG/MP4, at most 50 MiB')
    assets=store.root/'assets';assets.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='import-',dir=store.root) as folder:
        work=Path(folder);runner=Runner(ImportStore(work),{'id':'import'},work)
        if data.startswith((b'\x89PNG\r\n\x1a\n',b'\xff\xd8\xff')):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('error',Image.DecompressionBombWarning)
                    with Image.open(io.BytesIO(data)) as img:
                        if img.width*img.height>20_000_000 or getattr(img,'n_frames',1)!=1:raise ValueError('Image must be a single frame of at most 20 megapixels')
                        img.load();clean=ImageOps.exif_transpose(img).convert('RGB');clean.thumbnail((2560,2560))
                        normalized=work/'clean.png';clean.save(normalized,format='PNG')
                        meta={'kind':'image','width':clean.width,'height':clean.height}
            except (OSError,Warning,Image.DecompressionBombError) as error:raise ValueError('Image could not be decoded safely') from error
        elif len(data)>12 and data[4:8]==b'ftyp':
            original=work/'input.mp4';original.write_bytes(data)
            probe=runner.run(['ffprobe','-v','error','-protocol_whitelist','file,pipe','-f','mov','-show_streams','-show_format','-of','json',original],label='probe',timeout=15)
            info=json.loads(probe.read_text());streams=info.get('streams',[]);videos=[s for s in streams if s.get('codec_type')=='video']
            if not videos or len(streams)>4:raise ValueError('MP4 must contain one usable video track')
            v=videos[0];duration=float(v.get('duration',info['format']['duration']))
            from fractions import Fraction
            if not 1<=duration<=120 or not 16<=v['width']<=4096 or not 16<=v['height']<=2160 or Fraction(v.get('avg_frame_rate','0/1'))>60:
                raise ValueError('MP4 must be 1–120 seconds, at most 4096×2160 and 60 fps')
            normalized=work/'clean.mp4'
            runner.run(['ffmpeg','-v','error','-y','-protocol_whitelist','file,pipe','-f','mov','-i',original,'-map','0:v:0','-map','0:a:0?','-map_metadata','-1','-sn','-dn','-vf','scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1','-r','24','-t',str(duration),'-c:v','libx264','-threads','2','-preset','veryfast','-crf','19','-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-ac','2','-movflags','+faststart',normalized],label='normalize',timeout=180)
            normalized_probe=runner.run(['ffprobe','-v','error','-show_streams','-of','json',normalized],label='normalized-probe',timeout=15)
            normalized_streams=json.loads(normalized_probe.read_text())['streams']
            duration=float(next(s for s in normalized_streams if s['codec_type']=='video')['duration'])
            meta={'kind':'clip','duration_s':duration,'audio':any(s.get('codec_type')=='audio' for s in normalized_streams),'fps':24}
        else:raise ValueError('Media must be a real PNG/JPEG image or MP4 video')
        key=sha256(normalized)+normalized.suffix;target=contained(assets,key)
        # Normalized bytes, never the unchecked upload, are the render input.
        shutil.copy2(normalized,target)
        meta.update(asset=key,bytes=target.stat().st_size,label=''.join(c for c in Path(name or key).name[:120] if c.isprintable()))
        atomic_json(assets/(key+'.json'),meta)
        return meta

def asset_info(store,key):
    path=contained(store.root/'assets',key)
    if not path.is_file() or sha256(path)!=key.rsplit('.',1)[0]:raise ValueError('Media asset missing or changed: '+key)
    info=json.loads(path.with_name(path.name+'.json').read_text())
    if info.get('asset')!=key:raise ValueError('Media metadata does not match asset')
    return path,info

def preflight(store,m,targets):
    if 'cad' in targets and not m.solids:raise ValueError('CAD output needs at least one solid; choose other outputs for media-only stories')
    assets={}
    for beat in m.beats:
        if beat.visual.asset:
            path,meta=asset_info(store,beat.visual.asset);assets[beat.visual.asset]=meta
            if meta['kind']!=beat.visual.mode:raise ValueError('Scene does not match imported asset')
            if beat.visual.mode=='clip':
                if beat.visual.start+beat.duration>meta['duration_s']+.04:raise ValueError('Clip trim exceeds source duration: '+beat.id)
                if beat.visual.audio=='source' and not meta['audio']:raise ValueError('Clip has no source audio: '+beat.id)
    return {'ready':True,'targets':targets,'assets':list(assets.values()),'moving_beats':[b.id for b in m.beats if b.visual.mode in ('orbit','explode')]}


def import_media(store,data,name=None):
    try:return _import_media(store,data,name)
    except (RuntimeError,TimeoutError,ZeroDivisionError) as error:
        raise ValueError('Media could not be decoded within local limits; use a standard PNG/JPEG or a shorter H264 MP4') from error
