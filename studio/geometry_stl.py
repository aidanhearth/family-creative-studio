"""Measure a binary STL independently of its source CAD representation."""
import math
from pathlib import Path
import struct


def inspect_stl(path: Path):
    size = path.stat().st_size
    with path.open('rb') as stream:
        header = stream.read(84)
        if len(header) != 84:
            raise ValueError('STL header is truncated')
        count = struct.unpack_from('<I', header, 80)[0]
        if not count or count > 2_000_000 or size != 84 + count * 50:
            raise ValueError('STL triangle count is invalid or exceeds two million')
        low, high, signed = [math.inf] * 3, [-math.inf] * 3, 0.0
        for _ in range(count):
            values = struct.unpack('<12fH', stream.read(50))
            points = (values[3:6], values[6:9], values[9:12])
            if not all(math.isfinite(x) for p in points for x in p):
                raise ValueError('STL contains non-finite coordinates')
            for p in points:
                low = [min(a, b) for a, b in zip(low, p)]
                high = [max(a, b) for a, b in zip(high, p)]
            a, b, c = points
            signed += (a[0] * (b[1] * c[2] - b[2] * c[1]) + a[1] * (b[2] * c[0] - b[0] * c[2]) + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
    return {'triangles': count, 'volume_mm3': abs(signed), 'bounds_mm': {'min': low, 'max': high}}
