"""Bounded STEP metadata reader; invoked only as an isolated child."""
import json
import math
from pathlib import Path
import sys

from cadgen import build123d as bd
from .geometry_kernel import check_shape, bounds


def inspect(path):
    part = check_shape(bd.import_step(path), 'import')
    size = list(part.bounding_box().size)
    if any(not math.isfinite(x) or x <= 0 or x > 1000.01 for x in size):
        raise ValueError('STEP dimensions must be nonzero and at most 1000 mm per axis')
    return {'kind': 'cad', 'format': 'STEP', 'size': size, 'size_mm': size, 'bounds_mm': bounds(part),
            'volume_mm3': part.volume, 'solid_count': len(part.solids()), 'valid': bool(part.is_valid)}


if __name__ == '__main__':
    Path(sys.argv[2]).write_text(json.dumps(inspect(Path(sys.argv[1])), allow_nan=False))
