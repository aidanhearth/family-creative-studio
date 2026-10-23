"""Stream-copy the composition clips in their declared edit order."""
import importlib.util
import json
from pathlib import Path
import sys
from .paths import ROOT, contained


def ordered_segments(out):
    """Lexical sorting is wrong for timelines exceeding 99 clips."""
    edl = json.loads((out / 'edit.edl.json').read_text())
    paths = [contained(out, segment['video']) for segment in edl['segments']]
    if not paths or len(paths) > 256 or len(set(paths)) != len(paths):
        raise ValueError('Timeline requires 1–256 unique composition clips')
    if any(not path.is_file() or path.suffix != '.mp4' or path.parent != out / 'clips' for path in paths):
        raise ValueError('Timeline composition clip is missing or outside the clips directory')
    return paths


def main(out):
    out = Path(out).resolve()
    spec = importlib.util.spec_from_file_location('video_use_render', ROOT / 'vendor/browser-use--video-use/video_render.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.concat_segments(ordered_segments(out), out / 'base.mp4', out)


if __name__ == '__main__':
    main(sys.argv[1])
