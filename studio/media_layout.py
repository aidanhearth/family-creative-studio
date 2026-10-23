"""Shared, deterministic display geometry for posters, films and slide adapters."""
from fractions import Fraction


def output_settings(m, metadata=()):
    video = getattr(m, 'video', None)
    records = list(metadata.values()) if isinstance(metadata, dict) else list(metadata)
    clips = [r for r in records if r.get('kind') == 'clip']
    pictures = [r for r in records if r.get('kind') in ('clip', 'image')]
    resolution = getattr(video, 'resolution', 'source')
    if resolution == 'source' and pictures:
        largest = max(pictures, key=lambda r: r.get('display_width', r.get('width', 0)) * r.get('display_height', r.get('height', 0)))
        width = int(largest.get('display_width', largest.get('width', 1920)))
        height = int(largest.get('display_height', largest.get('height', 1080)))
        width += width % 2; height += height % 2
        if width > 8192 or height > 8192: raise ValueError('Source canvas exceeds 8192 pixels; choose an explicit video resolution')
    else:
        width, height = {'720p': (1280, 720), '1080p': (1920, 1080), '2160p': (3840, 2160), 'source': (1920, 1080)}[resolution]
    requested_fps = getattr(video, 'fps', 'source')
    fps = max((Fraction(str(r['fps'])) for r in clips), default=Fraction(30)) if requested_fps == 'source' else Fraction(requested_fps)
    if not 0 < fps <= 120: raise ValueError('Output fps must be positive and at most 120')
    return {'width': width, 'height': height, 'fps': str(fps), 'resolution': resolution,
            'crf': getattr(video, 'crf', 18), 'captions': getattr(video, 'captions', True),
            'normalize_audio': getattr(video, 'normalize_audio', True),
            'color_space': 'bt709', 'dynamic_range': 'SDR', 'hdr_policy': 'preserve original; Hable tone-map HDR sources for SDR composition'}


def beat_layout(m, beat):
    return getattr(beat, 'layout', None) or getattr(getattr(m, 'slides', None), 'layout', 'editorial')


def canvas_space(width, height):
    """One isotropic design space for text, diagrams, posters and film overlays."""
    stacked = width / height < 4 / 3
    scale = width / 720 if stacked else height / 720
    return width / scale, height / scale, scale, stacked


def visual_rect(layout, width, height):
    if layout == 'full': return 0, 0, width, height
    cw, ch, scale, stacked = canvas_space(width, height)
    if stacked:
        # Portrait/square frames put text above media, with a parameter/footer
        # band below. Shared by SVG generation and both image/video compositors.
        x = 0 if layout == 'split' else 32
        y = min(360, ch * .45)
        right = cw if layout == 'split' else cw - 32
        bottom = ch - 150
        return (round(x * scale), round(y * scale),
                round(right * scale) - round(x * scale),
                max(1, round(bottom * scale) - round(y * scale)))
    if layout == 'split': return round(width * .45), 0, width - round(width * .45), height
    return round(width * 510 / 1280), round(height * 90 / 720), round(width * 720 / 1280), round(height * 420 / 720)
