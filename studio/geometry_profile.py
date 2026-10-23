"""Validate bounded simple extrusion polygons without loading a CAD kernel."""
from __future__ import annotations


def validate_profile(points):
    if len(points) < 3 or len(set(points)) != len(points):
        raise ValueError("Extrusions require at least three unique polygon vertices")
    for axis in (0, 1):
        values = [p[axis] for p in points]
        if abs(min(values) + .5) > 1e-9 or abs(max(values) - .5) > 1e-9:
            raise ValueError("Polygon coordinates must span -.5 to .5 in both axes")
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1]))
    if abs(area) < 1e-9:
        raise ValueError("Polygon area must be nonzero")

    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def on_segment(a, b, p):
        return min(a[0], b[0]) - 1e-10 <= p[0] <= max(a[0], b[0]) + 1e-10 and min(a[1], b[1]) - 1e-10 <= p[1] <= max(a[1], b[1]) + 1e-10

    edges = list(zip(points, points[1:] + points[:1]))
    for i, (a, b) in enumerate(edges):
        for j in range(i + 1, len(edges)):
            if j == i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            c, d = edges[j]
            o = (orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b))
            if o[0] * o[1] < 0 and o[2] * o[3] < 0 or any(abs(t) < 1e-10 and on_segment(x, y, p) for t, x, y, p in ((o[0], a, b, c), (o[1], a, b, d), (o[2], c, d, a), (o[3], c, d, b))):
                raise ValueError("Polygon edges must not intersect or overlap")
