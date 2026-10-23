"""Independent regression fixtures for restored imports, previews and PPT media."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest
from PIL import Image

from studio.geometry_preview import PREVIEW_OUTPUTS, preview_file_path, preview_geometry
from studio.presentation_media import prepare_movies
from studio.schema import Manifest
from studio.seed import demo
from studio.svg_assets import inspect_svg, normalized_svg, rasterize


def fake_preview_builder(monkeypatch):
    calls = []

    def build(self, args, **kwargs):
        calls.append(args)
        output = Path(args[-1])
        for name in PREVIEW_OUTPUTS:
            (output / name).write_bytes(b'synthetic ' + name.encode())
        (output / 'geometry.json').write_text('{"parts":[]}')
        (output / 'cad-check.json').write_text('{"valid":true}')

    monkeypatch.setattr('studio.provenance.engine_fingerprint', lambda: 'review-test-engine')
    monkeypatch.setattr('studio.geometry_preview.Runner.run', build)
    return calls


@pytest.mark.parametrize('damaged', ['model.glb', 'geometry.json', 'receipt.json'])
def test_preview_integrity_rebuilds_changed_or_missing_outputs(tmp_path, monkeypatch, damaged):
    calls = fake_preview_builder(monkeypatch)
    store = SimpleNamespace(root=tmp_path)
    first = preview_geometry(store, demo())
    destination = tmp_path / 'previews' / first['key']
    assert preview_file_path(store, first['key'], 'model.glb').read_bytes() == b'synthetic model.glb'
    (destination / damaged).write_bytes(b'corrupted')
    with pytest.raises(ValueError, match='missing or changed'):
        preview_file_path(store, first['key'], 'model.glb')
    second = preview_geometry(store, demo())
    assert second['key'] == first['key'] and second['validation']['valid']
    assert len(calls) == 2
    assert preview_file_path(store, first['key'], 'model.glb').read_bytes() == b'synthetic model.glb'
    assert len(list(destination.parent.glob(first['key'] + '.invalid-*'))) == 1
    preview_geometry(store, demo())
    assert len(calls) == 2


def test_preview_cache_hit_rechecks_original_step(tmp_path, monkeypatch):
    calls = fake_preview_builder(monkeypatch)
    data = b'ISO-10303-21; synthetic hash-only fixture'
    key = hashlib.sha256(data).hexdigest() + '.step'
    assets = tmp_path / 'assets'
    assets.mkdir()
    (assets / key).write_bytes(data)
    manifest = Manifest.model_validate({'id': 'step-preview', 'title': 'Step', 'subtitle': 'Step',
        'solids': [{'id': 'part', 'name': 'Part', 'kind': 'step', 'size': [10, 10, 10], 'asset': key}],
        'beats': [{'id': 'view', 'title': 'View', 'body': 'View', 'narration': 'View'}]})
    store = SimpleNamespace(root=tmp_path)
    preview_geometry(store, manifest)
    (assets / key).write_bytes(b'changed')
    with pytest.raises(ValueError, match='Missing or changed STEP'):
        preview_geometry(store, manifest)
    assert len(calls) == 1


@pytest.mark.parametrize('name', ['../model.glb', '/etc/passwd', 'cad-check.json'])
def test_preview_serving_rejects_unapproved_names(tmp_path, name):
    with pytest.raises(ValueError):
        preview_file_path(SimpleNamespace(root=tmp_path), 'a' * 64, name)


def movie_manifest(mode, narration=False):
    return Manifest.model_validate({'id': 'review', 'title': 'Review', 'subtitle': 'Review',
        'slides': {'narration': narration}, 'beats': [{'id': 'one', 'title': 'One', 'body': 'One',
        'narration': 'Voice only', 'duration': .6, 'visual': {'mode': 'clip', 'asset': 'a' * 64 + '.mp4',
        'audio': mode, 'start': .2, 'source_gain': .25}}]})


@pytest.mark.parametrize('narration', [False, True])
@pytest.mark.parametrize('mode', ['voice', 'source', 'mix', 'silent'])
def test_ppt_movie_audio_obeys_mode_and_narration_switch(tmp_path, mode, narration):
    (tmp_path / 'output-settings.json').write_text('{"fps":"30","crf":18}')
    calls = []
    visuals = {'0': {'video': 'source.mp4', 'poster': 'poster.png'}}
    prepare_movies(movie_manifest(mode, narration), tmp_path,
                   SimpleNamespace(run=lambda args, **kwargs: calls.append(args)), visuals, [.6])
    command = calls[0]
    audible = not narration and mode in ('source', 'mix')
    assert ('-an' not in command) == audible
    if audible:
        audio_filter = command[command.index('-af') + 1]
        assert 'volume=0.25' in audio_filter
        assert 'afade=t=in' in audio_filter and 'afade=t=out' in audio_filter
        assert 'alimiter=' in audio_filter and '0:a:0' in command
        assert visuals['0']['ppt_audio_mode'] == 'source'
    else:
        assert '-af' not in command


def test_generated_svg_has_explicit_larger_byte_and_node_limits(monkeypatch):
    import studio.svg_assets as svg_assets
    large = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><desc>'
             + b'x' * (2 * 1024 * 1024) + b'</desc></svg>')
    with pytest.raises(ValueError, match='2 MiB'):
        inspect_svg(large)
    inspect_svg(large, generated=True)
    with pytest.raises(ValueError, match='2 MiB'):
        normalized_svg(large)
    many = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
            + b'<rect/>' * 50_000 + b'</svg>')
    with pytest.raises(ValueError, match='element'):
        inspect_svg(many)
    inspect_svg(many, generated=True)
    monkeypatch.setattr(svg_assets, 'GENERATED_SVG_LIMIT', len(large) - 1)
    with pytest.raises(ValueError, match='Generated SVG'):
        inspect_svg(large, generated=True)
    monkeypatch.setattr(svg_assets, 'GENERATED_SVG_NODE_LIMIT', 10)
    with pytest.raises(ValueError, match='element'):
        inspect_svg(many, generated=True)


@pytest.mark.parametrize('style', [
    r'fill:u\72l(https://example.invalid/a.svg#x)',
    r'fill:u\72l("file:///synthetic.svg#x")',
    r'fill:URL(//example.invalid/a.svg#x)',
])
def test_svg_decoded_css_cannot_hide_external_resources(style):
    from xml.sax.saxutils import quoteattr
    data = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect style='
            + quoteattr(style) + '/></svg>').encode()
    with pytest.raises(ValueError, match='local fragment'):
        inspect_svg(data)
    with pytest.raises(ValueError, match='local fragment'):
        inspect_svg(data, generated=True)


def test_quoted_local_gradient_rasterizes_without_external_fetch(tmp_path):
    data = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 10">
      <defs><linearGradient id="gradient"><stop stop-color="#ff0000"/>
      <stop offset="1" stop-color="#0000ff"/></linearGradient></defs>
      <rect width="20" height="10" style="fill:url(&quot;#gradient&quot;)"/></svg>'''
    inspect_svg(data)
    output = tmp_path / 'gradient.png'
    rasterize(data, output, 20, 10)
    with Image.open(output) as image:
        assert image.getpixel((2, 5)) != image.getpixel((17, 5))


def test_rasterizer_rejects_resource_fetch_even_after_validation(tmp_path, monkeypatch):
    def convert(**kwargs):
        return kwargs['url_fetcher']('file:///synthetic-not-accessed', 'image/svg+xml')
    monkeypatch.setattr('cairosvg.surface.PNGSurface.convert', convert)
    valid = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><rect/></svg>'
    with pytest.raises(ValueError, match='External SVG resources'):
        rasterize(valid, tmp_path / 'never-created.png', 10, 10, generated=True)


@pytest.mark.skipif(not os.environ.get('STUDIO_MEDIA_INTEGRATION'), reason='explicit bounded FFmpeg integration')
def test_real_ppt_audio_mutes_voice_and_preserves_source_gain_and_fades(tmp_path):
    import numpy as np
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=size=160x90:rate=30',
        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-t', '1', '-c:v', 'libx264',
        '-threads', '2', '-preset', 'ultrafast', '-c:a', 'aac', tmp_path / 'source.mp4'], check=True, timeout=30)
    (tmp_path / 'output-settings.json').write_text('{"fps":"30","crf":18}')

    def run(args, **kwargs):
        subprocess.run(args, check=True, timeout=30)

    def samples(path):
        raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', path, '-map', '0:a:0',
            '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'], timeout=20)
        return np.frombuffer(raw, dtype='<f4')

    original = samples(tmp_path / 'source.mp4')
    reference = float(np.sqrt(np.mean(original[12000:24000] ** 2)))
    for mode in ('voice', 'silent', 'source', 'mix'):
        visuals = {'0': {'video': 'source.mp4', 'poster': 'poster.png'}}
        prepare_movies(movie_manifest(mode), tmp_path, SimpleNamespace(run=run), visuals, [.6])
        result = tmp_path / visuals['0']['ppt_video']
        streams = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
            '-of', 'json', result], timeout=20))['streams']
        assert any(s['codec_type'] == 'audio' for s in streams) == (mode in ('source', 'mix'))
        if mode in ('source', 'mix'):
            audio = samples(result)
            middle = float(np.sqrt(np.mean(audio[12000:24000] ** 2)))
            assert .20 < middle / reference < .30
            assert float(np.sqrt(np.mean(audio[:480] ** 2))) < middle * .7
