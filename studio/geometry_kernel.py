"""CAD construction and measurements. Import only in isolated CAD processes."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from cadgen import build123d as bd


def bounds(shape):
    box = shape.bounding_box()
    return {"min": list(box.min), "max": list(box.max)}


def check_shape(shape, label):
    volume = shape.volume
    if not shape.is_valid or not shape.solids() or not math.isfinite(volume) or volume <= 1e-8:
        raise ValueError(f"Part {label}: CAD operation produced empty or invalid solid geometry")
    if len(shape.solids()) > 512:
        raise ValueError(f"Part {label}: CAD operation exceeds 512 connected solids")
    return shape


def imported_step(asset_path: Path, expected_size):
    if asset_path.is_symlink() or not asset_path.is_file() or asset_path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("STEP input must be a regular imported file up to 50 MiB")
    if hashlib.sha256(asset_path.read_bytes()).hexdigest() != asset_path.stem:
        raise ValueError("STEP asset content does not match its identifier")
    part = check_shape(bd.import_step(asset_path), "import")
    box = part.bounding_box()
    dimensions = list(box.size)
    if any(not math.isclose(a, b, abs_tol=.01, rel_tol=1e-7) for a, b in zip(dimensions, expected_size)):
        raise ValueError(f"Imported STEP size {dimensions} does not match declared size {list(expected_size)}; inspect the asset before authoring")
    center = box.center()
    return part.moved(bd.Location(tuple(-v for v in center)))


def build_parts(solids, asset_dir: Path):
    """Build in document order; booleans refer to earlier world-space geometry."""
    built, delivered = {}, []
    for spec in solids:
        s = spec.model_dump() if hasattr(spec, "model_dump") else spec
        w, d, h = s["size"]
        kind = s["kind"]
        if kind == "box":
            part = bd.Box(w, d, h)
        elif kind == "cylinder":
            part = bd.Cylinder(w / 2, h)
        elif kind == "sphere":
            part = bd.Sphere(w / 2)
        elif kind == "cone":
            top = s.get("top_diameter", 0)
            part = bd.Cylinder(w / 2, h) if top == w else bd.Cone(w / 2, top / 2, h)
        elif kind == "torus":
            part = bd.Torus((w - h) / 2, h / 2)
        elif kind == "extrusion":
            profile = bd.Polygon(*[(x * w, y * d) for x, y in s["profile"]], align=None)
            part = bd.extrude(profile, amount=h, dir=(0, 0, 1)).moved(bd.Location((0, 0, -h / 2)))
        elif kind == "step":
            part = imported_step(asset_dir / s["asset"], s["size"])
        else:
            raise ValueError(f"Unsupported solid kind: {kind}")
        if s.get("bore", 0):
            part = part - bd.Cylinder(s["bore"] / 2, h + 2)
        check_shape(part, s["id"])
        part = part.moved(bd.Location(tuple(s["position"]), tuple(s.get("rotation", (0, 0, 0)))))
        for op in s.get("booleans", []):
            if op["tool"] not in built:
                raise ValueError(f"Part {s['id']}: boolean tool must precede the part")
            tool = built[op["tool"]]
            if op["operation"] == "union":
                part = part + tool
            elif op["operation"] == "subtract":
                part = part - tool
            elif op["operation"] == "intersect":
                part = part & tool
            else:
                raise ValueError("Unknown boolean operation")
            if isinstance(part, list):
                part = bd.Compound(children=list(part))
            check_shape(part, s["id"])
        try:
            if s.get("fillet", 0):
                part = part.fillet(s["fillet"], part.edges())
            if s.get("chamfer", 0):
                part = part.chamfer(s["chamfer"], None, part.edges())
        except (ValueError, RuntimeError) as exc:
            raise ValueError(f"Part {s['id']}: edge treatment cannot be built on these edges; reduce the radius/distance or change the geometry") from exc
        check_shape(part, s["id"])
        part.label = s["id"]
        part.color = bd.Color(s["color"])
        built[s["id"]] = part
        if not s.get("construction", False):
            delivered.append((s, part))
    return delivered


def geometry_document(parts):
    """Real post-operation tessellation for preview and vector projection, in mm."""
    result, triangle_count = [], 0
    for spec, part in parts:
        box = part.bounding_box()
        tolerance = max(.001, min(.1, box.diagonal * .0005))
        vertices, triangles = part.tessellate(tolerance, .12)
        triangle_count += len(triangles)
        if triangle_count > 1_000_000:
            raise ValueError("CAD projection exceeds one million triangles; simplify or split the assembly")
        result.append({
            "id": spec["id"], "name": spec["name"], "kind": spec["kind"],
            "color": spec["color"], "bounds_mm": bounds(part),
            "center_mm": list(box.center()), "volume_mm3": part.volume,
            "solid_count": len(part.solids()), "valid": bool(part.is_valid),
            "vertices": [list(v) for v in vertices],
            "triangles": [list(t) for t in triangles],
            "mesh_tolerance_mm": tolerance,
        })
    return {"schema_version": 1, "units": "mm", "coordinates": "right-handed-z-up-world", "parts": result, "triangle_count": triangle_count}
