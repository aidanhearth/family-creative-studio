"""Behavior contracts for preserved media and the one-generation film pipeline."""
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import wave

import pytest
from PIL import Image, ImageCms
from studio.assets import import_audio
from studio.media_assets import import_media, asset_info, preflight, _video_metadata
from studio.media_layout import output_settings, visual_rect
from studio.schema import Manifest
from studio.stage_cache import StageCache
from studio.video import audio_track, prepare_visuals, composite_posters, render_video


def manifest(**values):
    data = {'id': 'media', 'title': 'Media', 'subtitle': 'Preserved source',
            'beats': [{'id': 'scene', 'title': 'Scene', 'body': 'Source media', 'narration': '', 'duration': .6, 'visual': {'audio': 'silent'}}]}
    data.update(values)
    return Manifest.model_validate(data)


def store_at(root):
    root.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(root=root, job=lambda _: {'cancel': False})


def wav_data(seconds=.6):
    import math
    import struct
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(48000)
        audio.writeframes(b''.join(struct.pack('<h', int(5000 * math.sin(2 * math.pi * 440 * i / 48000))) for i in range(round(seconds * 48000))))
    return buffer.getvalue()


def test_png_alpha_icc_and_jpeg_uploads_are_byte_identical(tmp_path):
    store = store_at(tmp_path)
    image = Image.new('RGBA', (3101, 10), (220, 30, 50, 64))
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    buffer = io.BytesIO(); image.save(buffer, format='PNG', icc_profile=profile)
    data = buffer.getvalue(); meta = import_media(store, data)
    assert meta['alpha'] and meta['icc_profile'] and meta['width'] == 3101
    assert meta['asset'] == hashlib.sha256(data).hexdigest() + '.png'
    assert (tmp_path / 'assets' / meta['asset']).read_bytes() == data
    buffer = io.BytesIO(); image.convert('RGB').save(buffer, format='JPEG')
    data = buffer.getvalue(); meta = import_media(store, data)
    assert meta['asset'].endswith('.jpg') and (tmp_path / 'assets' / meta['asset']).read_bytes() == data


def test_video_import_probes_but_never_transcodes(tmp_path, monkeypatch):
    from studio import media_assets
    calls = []
    def probe(self, args, **kwargs):
        calls.append(args)
        target = self.work / 'probe.log'
        target.write_text(json.dumps({'streams': [{'codec_type': 'video', 'width': 3840, 'height': 2160,
            'duration': '301.0', 'avg_frame_rate': '60000/1001', 'color_transfer': 'smpte2084', 'pix_fmt': 'yuv420p10le'}, {'codec_type': 'audio'}]}))
        return target
    monkeypatch.setattr(media_assets.Runner, 'run', probe)
    data = b'\0\0\0\x20ftypisom' + b'synthetic metadata-only fixture'
    meta = import_media(store_at(tmp_path), data)
    assert [args[0] for args in calls] == ['ffprobe']
    assert meta['fps'] == '60000/1001' and meta['hdr'] and meta['width'] == 3840
    assert meta['duration_s'] == 301 and not meta['transcoded']
    assert (tmp_path / 'assets' / meta['asset']).read_bytes() == data


def test_resolution_fps_and_rotation_are_explicit():
    meta = _video_metadata({'streams': [{'codec_type': 'video', 'width': 3840, 'height': 2160, 'duration': '10',
        'avg_frame_rate': '60000/1001', 'side_data_list': [{'rotation': -90}]}]})
    settings = output_settings(manifest(), [meta])
    assert (settings['width'], settings['height'], settings['fps']) == (2160, 3840, '60000/1001')
    settings = output_settings(manifest(video={'resolution': '2160p', 'fps': 50}), [meta])
    assert (settings['width'], settings['height'], settings['fps']) == (3840, 2160, '50')
    assert visual_rect('full', 2160, 3840) == (0, 0, 2160, 3840)
    assert visual_rect('split', 1000, 600) == (450, 0, 550, 600)


def test_audio_inspection_and_global_offsets_coexist_with_source_audio(tmp_path):
    store = store_at(tmp_path); meta = import_audio(store, wav_data(1.2))
    assert asset_info(store, meta['asset'])[1]['kind'] == 'audio'
    key = 'a' * 64 + '.mp4'
    m = manifest(narration_asset=meta['asset'], beats=[
        {'id': 'source', 'title': 'Source', 'body': 'Source', 'narration': '', 'duration': .6, 'visual': {'mode': 'clip', 'asset': key, 'audio': 'source'}},
        {'id': 'voice', 'title': 'Voice', 'body': 'Voice', 'narration': '', 'duration': .6, 'visual': {'audio': 'voice'}}])
    assert m.beats[0].visual.audio == 'source' and m.beats[1].visual.audio == 'voice'


def test_one_video_generation_caption_and_stream_copy_contract(tmp_path, monkeypatch):
    from studio import video
    m = manifest(beats=[{'id': 'scene', 'title': 'Scene', 'body': 'Text', 'narration': 'Caption', 'duration': .6, 'visual': {'audio': 'silent'}}])
    calls = []
    runner = SimpleNamespace(store=store_at(tmp_path / 'store'), run=lambda args, **kw: calls.append((args, kw)))
    monkeypatch.setattr(video, '_master_audio', lambda *args: None)
    render_video(m, m, tmp_path, runner, [.6], {})
    encodes = [args for args, _ in calls if 'libx264' in args]
    assert len(encodes) == 1 and '-an' in encodes[0]
    assert 'subtitles=caption-00.srt' in encodes[0][encodes[0].index('-filter_complex') + 1]
    final = calls[-1][0]
    assert final[final.index('-c:v') + 1] == 'copy' and final[final.index('-c:a') + 1] == 'copy'
    edl = json.loads((tmp_path / 'edit.edl.json').read_text())
    assert edl['video_generations'] == {'import': 0, 'composition': 1, 'concat': 0, 'final_mux': 0}
    assert edl['width'] == 1920 and edl['height'] == 1080


def test_poster_full_resolution_alpha_and_icc_composite(tmp_path):
    store = store_at(tmp_path / 'store'); out = tmp_path / 'out'; out.mkdir(); (out / 'slides').mkdir()
    buffer = io.BytesIO(); Image.new('RGBA', (3001, 10), (255, 0, 0, 0)).save(buffer, format='PNG')
    meta = import_media(store, buffer.getvalue())
    m = manifest(beats=[{'id': 'scene', 'title': 'Scene', 'body': 'Text', 'narration': '', 'duration': .6,
        'layout': 'full', 'visual': {'mode': 'image', 'asset': meta['asset'], 'audio': 'silent'}}])
    runner = SimpleNamespace(store=store)
    visuals = prepare_visuals(m, out, runner, [.6], StageCache(store.root, 'test'))
    with Image.open(out / 'posters/00.png') as image:
        assert image.size == (3001, 10) and image.mode == 'RGBA'
    Image.new('RGB', (3002, 10), 'black').save(out / 'slides/00.png')
    composite_posters(m, out, visuals)
    with Image.open(out / 'slides/00.png') as image: assert image.getpixel((1500, 5)) == (246, 244, 239)


@pytest.mark.skipif(not __import__('os').environ.get('STUDIO_MEDIA_INTEGRATION'), reason='explicit bounded FFmpeg integration')
def test_real_preserved_1080p_mix_two_pass_and_copy_mux(tmp_path):
    from studio.runner import Runner
    store = store_at(tmp_path / 'store'); work = tmp_path / 'work'; work.mkdir()
    runner = Runner(store, {'id': 'media-test'}, work)
    source = work / 'original.mp4'
    runner.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=1920x1080:rate=30',
        '-f', 'lavfi', '-i', 'sine=frequency=220:sample_rate=48000', '-t', '1.2', '-c:v', 'libx264', '-threads', '2',
        '-preset', 'ultrafast', '-crf', '18', '-c:a', 'aac', source], label='fixture', timeout=60)
    original = source.read_bytes(); clip = import_media(store, original)
    assert (store.root / 'assets' / clip['asset']).read_bytes() == original
    voice = import_audio(store, wav_data(.6))
    m = manifest(beats=[{'id': 'scene', 'title': 'Scene', 'body': 'Text', 'narration': 'Caption', 'duration': .6,
        'narration_asset': voice['asset'], 'layout': 'full',
        'visual': {'mode': 'clip', 'asset': clip['asset'], 'start': .2, 'audio': 'mix', 'source_gain': .1}}])
    assert preflight(store, m, ['video'])['ready']
    out = work / 'out'; out.mkdir(); (out / 'slides').mkdir()
    cache = StageCache(store.root, 'media-integration')
    durations = audio_track(m, out, runner, cache)
    visuals = prepare_visuals(m, out, runner, durations, cache)
    Image.new('RGB', (1920, 1080), 'white').save(out / 'slides/00.png')
    overlay = Image.new('RGBA', (1920, 1080), (0, 0, 0, 0))
    from PIL import ImageDraw
    ImageDraw.Draw(overlay).rectangle((20, 20, 300, 90), fill=(255, 255, 255, 200))
    overlay.save(out / 'slides/00.overlay.png')
    composite_posters(m, out, visuals)
    render_video(m, m, out, runner, durations, visuals)
    log = runner.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', out / 'film.mp4'], label='result', timeout=20)
    probe = json.loads(log.read_text()); stream = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    assert (stream['width'], stream['height'], stream['r_frame_rate']) == (1920, 1080, '30/1')
    assert abs(float(probe['format']['duration']) - .6) < .05
    assert json.loads((out / 'loudness.json').read_text())['method'] == 'two-pass'
    assert json.loads((out / 'edit.edl.json').read_text())['segments'][0]['audio_mode'] == 'mix'
    # Concat may insert H264 SPS/PPS headers, but decoded picture bytes stay exact.
    hashes = []
    for label, path in [('segment-pixels', out / 'clips/00.mp4'), ('final-pixels', out / 'film.mp4')]:
        log = runner.run(['ffmpeg', '-v', 'error', '-i', path, '-map', '0:v:0', '-f', 'hash', '-hash', 'sha256', '-'], label=label, timeout=20)
        hashes.append(log.read_text().strip())
    assert hashes[0] == hashes[1]
    # Final mux must preserve compressed packets exactly, including headers.
    packet_hashes = []
    for label, path in [('base-packets', out / 'base.mp4'), ('final-packets', out / 'film.mp4')]:
        log = runner.run(['ffmpeg', '-v', 'error', '-i', path, '-map', '0:v:0', '-c', 'copy', '-f', 'hash', '-hash', 'sha256', '-'], label=label, timeout=20)
        packet_hashes.append(log.read_text().strip())
    assert packet_hashes[0] == packet_hashes[1]


def test_concat_follows_edl_not_lexical_names_past_99(tmp_path):
    from studio.media_worker import ordered_segments
    (tmp_path / 'clips').mkdir()
    names = ['02', '10', '99', '100', '101']
    for name in names: (tmp_path / 'clips' / (name + '.mp4')).write_bytes(b'fixture')
    (tmp_path / 'edit.edl.json').write_text(json.dumps({'segments': [{'video': 'clips/' + name + '.mp4'} for name in names]}))
    assert [p.stem for p in ordered_segments(tmp_path)] == names


def test_global_narration_keeps_authored_offset_after_source_only_beat(tmp_path):
    store = store_at(tmp_path / 'store'); out = tmp_path / 'out'; out.mkdir()
    narration = import_audio(store, wav_data(1.2))
    data = b'local synthetic clip fixture'; key = hashlib.sha256(data).hexdigest() + '.mp4'
    (store.root / 'assets' / key).write_bytes(data)
    (store.root / 'assets' / (key + '.json')).write_text(json.dumps({'asset': key, 'kind': 'clip', 'width': 640, 'height': 360, 'fps': '30', 'duration_s': 2, 'audio': True}))
    m = manifest(narration_asset=narration['asset'], beats=[
        {'id': 'source', 'title': 'Source', 'body': 'Source', 'narration': '', 'duration': .6, 'visual': {'mode': 'clip', 'asset': key, 'audio': 'source'}},
        {'id': 'voice', 'title': 'Voice', 'body': 'Voice', 'narration': '', 'duration': .6, 'visual': {'audio': 'voice'}}])
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs))
        Path(args[-1]).write_bytes(wav_data(.6))
    runner = SimpleNamespace(store=store, run=run)
    audio_track(m, out, runner, StageCache(store.root, 'test'))
    args = next(args for args, kw in calls if kw['label'] == 'voice-1')
    assert args[args.index('-ss') + 1] == '0.6'
    chunks = json.loads((out / 'narration.json').read_text())['chunks']
    assert chunks[1]['authored_start_s'] == .6 and chunks[0]['mode'] == 'source'


def test_full_movie_text_overlay_survives_final_composition(tmp_path, monkeypatch):
    from studio import video
    m = manifest(beats=[{'id': 'scene', 'title': 'Title survives', 'body': 'Body', 'narration': '', 'duration': .6,
        'layout': 'full', 'visual': {'mode': 'orbit', 'audio': 'silent'}}],
        solids=[{'id': 'part', 'name': 'Part', 'size': [10, 10, 10]}])
    (tmp_path / 'slides').mkdir()
    Image.new('RGBA', (1920, 1080), (255, 0, 0, 128)).save(tmp_path / 'slides/00.overlay.png')
    calls = []; runner = SimpleNamespace(store=store_at(tmp_path / 'store'), run=lambda args, **kw: calls.append((args, kw)))
    monkeypatch.setattr(video, '_master_audio', lambda *args: None)
    render_video(m, m, tmp_path, runner, [.6], {'0': {'video': 'motion/00.mp4', 'poster': 'posters/00.png'}})
    args = calls[0][0]; filters = args[args.index('-filter_complex') + 1]
    assert '[composite][textlayer]overlay' in filters and '[withtext]setpts' in filters


@pytest.mark.parametrize('layout', ['full', 'editorial', 'split'])
@pytest.mark.parametrize('size', [(540, 960), (600, 600), (1000, 600)])
def test_source_canvas_text_and_media_share_coordinates_without_transparent_bands(tmp_path,layout,size):
    from xml.etree import ElementTree as ET
    from studio.content import slide_svg, slide_overlay
    from studio.media_layout import canvas_space
    from studio.svg_assets import rasterize
    width,height=size
    store=store_at(tmp_path/'store');out=tmp_path/'out';out.mkdir();(out/'slides').mkdir()
    buffer=io.BytesIO();Image.new('RGB',size,(40,120,200)).save(buffer,format='PNG')
    asset=import_media(store,buffer.getvalue())['asset']
    m=manifest(beats=[{'id':'portrait','title':'Portrait title','body':'A clear description',
        'narration':'','duration':.2,'layout':layout,'visual':{'mode':'image','asset':asset,'audio':'silent'}}])
    svg=slide_svg(m,m.beats[0],0,'',width=width,height=height)
    target=out/'slides/00.png';rasterize(svg.encode(),target,width,height,generated=True)
    with Image.open(target) as image:
        assert image.size==size and image.convert('RGBA').getchannel('A').getextrema()==(255,255)
    visuals=prepare_visuals(m,out,SimpleNamespace(store=store),[.2],StageCache(store.root,'canvas'))
    if layout=='full':
        rasterize(slide_overlay(m,m.beats[0],0,width=width,height=height).encode(),
                  out/'slides/00.overlay.png',width,height,generated=True)
    else:
        _,_,scale,_=canvas_space(width,height)
        x,y,w,h=visual_rect(layout,width,height)
        for node in ET.fromstring(svg).iter('{http://www.w3.org/2000/svg}text'):
            tx,ty,font=(float(node.get(key))*scale for key in ('x','y','font-size'))
            # Reserved text rows must stay outside the media rectangle.
            assert tx<x or tx>=x+w or ty+font*.25<y or ty-font>=y+h
    composite_posters(m,out,visuals)
    with Image.open(target) as image:
        if layout=='full':
            _,_,scale,_=canvas_space(width,height)
            assert image.getpixel((round(40*scale),round(40*scale)))!=(40,120,200)
            assert image.getpixel((round(40*scale),height-round(120*scale)))!=(40,120,200)
            assert image.getpixel((width//2,height//2))==(40,120,200)
        else:
            x,y,w,h=visual_rect(layout,width,height)
            assert image.getpixel((x+w//2,y+h//2))==(40,120,200)
            assert image.getpixel((0,0))==(246,244,239)


def test_original_square_svg_fits_portrait_uniformly_on_opaque_paper(tmp_path):
    import numpy as np
    from studio.content import fitted_artwork_svg
    from studio.svg_assets import rasterize
    original=b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="10 20 100 100"><circle cx="60" cy="70" r="40" fill="#00FF00"/></svg>'
    output=tmp_path/'art.png'
    rasterize(fitted_artwork_svg(original,360,640,'#F6F4EF').encode(),output,360,640,generated=True)
    with Image.open(output) as image:
        pixels=np.asarray(image.convert('RGBA'))
        assert pixels[:,:,3].min()==255
        ys,xs=np.where((pixels[:,:,1]>250)&(pixels[:,:,0]<10)&(pixels[:,:,2]<10))
        assert abs((xs.max()-xs.min())-(ys.max()-ys.min()))<=1
        assert 284<=xs.max()-xs.min()<=288
        assert (xs.min()+xs.max())/2==pytest.approx(179.5,abs=1)
        assert (ys.min()+ys.max())/2==pytest.approx(319.5,abs=1)


@pytest.mark.skipif(not __import__('os').environ.get('STUDIO_MEDIA_INTEGRATION'), reason='explicit bounded FFmpeg integration')
def test_real_short_hdr_source_has_explicit_sdr_conversion(tmp_path):
    from studio.runner import Runner
    store = store_at(tmp_path / 'store'); work = tmp_path / 'work'; work.mkdir()
    runner = Runner(store, {'id': 'hdr-test'}, work)
    source = work / 'hdr.mp4'
    runner.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=30',
        '-f', 'lavfi', '-i', 'sine=frequency=300:sample_rate=48000', '-t', '0.6', '-c:v', 'libx264', '-threads', '2',
        '-preset', 'ultrafast', '-pix_fmt', 'yuv420p10le', '-color_primaries', 'bt2020', '-color_trc', 'smpte2084',
        '-colorspace', 'bt2020nc', '-c:a', 'aac', source], label='hdr-fixture', timeout=60)
    meta = import_media(store, source.read_bytes()); assert meta['hdr'] and meta['color']['pix_fmt'] == 'yuv420p10le'
    m = manifest(beats=[{'id': 'short', 'title': 'HDR source', 'body': 'Explicit conversion', 'narration': '',
        'duration': .1, 'layout': 'split', 'visual': {'mode': 'clip', 'asset': meta['asset'], 'audio': 'source'}}])
    out = work / 'out'; out.mkdir(); (out / 'slides').mkdir()
    cache = StageCache(store.root, 'hdr-integration')
    durations = audio_track(m, out, runner, cache)
    visuals = prepare_visuals(m, out, runner, durations, cache)
    Image.new('RGB', (320, 180), 'white').save(out / 'slides/00.png')
    composite_posters(m, out, visuals)
    render_video(m, m, out, runner, durations, visuals)
    probe = runner.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_streams', '-of', 'json', out / 'film.mp4'], label='hdr-result', timeout=20)
    stream = json.loads(probe.read_text())['streams'][0]
    assert stream['color_transfer'] == 'bt709' and stream['pix_fmt'] == 'yuv420p'
    assert json.loads((out / 'edit.edl.json').read_text())['dynamic_range'] == 'SDR'
    assert json.loads((out / 'loudness.json').read_text())['method'] == 'two-pass'
