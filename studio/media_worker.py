"""Use the vendored video-use concat engine with its apostrophe-path fix."""
from pathlib import Path
import importlib.util
import sys
from .paths import ROOT

out=Path(sys.argv[1]).resolve()
spec=importlib.util.spec_from_file_location('video_use_render',ROOT/'vendor/browser-use--video-use/video_render.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
paths=sorted((out/'clips').glob('*.mp4'))
if not paths:
    raise ValueError('No clips to concatenate')
module.concat_segments(paths,out/'base.mp4',out)
