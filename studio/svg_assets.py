"""Bounded native vectors, with separate import/generated limits and no URL fetches."""
import hashlib
import math
import re
from pathlib import Path
from xml.etree import ElementTree as ET

import tinycss2
from defusedxml import ElementTree as SafeET

from .paths import atomic_json, contained, sha256

SVG_LIMIT = 2 * 1024 * 1024
SVG_NODE_LIMIT = 50_000
GENERATED_SVG_LIMIT = 128 * 1024 * 1024
GENERATED_SVG_NODE_LIMIT = 1_500_000
SVG_DEPTH_LIMIT = 128
FRAGMENT = re.compile(r'#[A-Za-z_][\w:.-]*')
ALLOWED = {'svg', 'g', 'defs', 'path', 'rect', 'circle', 'ellipse', 'polygon', 'polyline', 'line',
           'text', 'tspan', 'linearGradient', 'radialGradient', 'stop', 'clipPath', 'mask', 'use',
           'symbol', 'title', 'desc'}


def check_css(tokens) -> None:
    """Inspect decoded CSS tokens, including escaped function names and quoted URLs."""
    pending = [(token, 0) for token in tokens]
    while pending:
        token, depth = pending.pop()
        if depth > 64 or token.type in ('error', 'at-keyword'):
            raise ValueError('Invalid, active or excessively nested SVG CSS')
        if token.type == 'url' and not FRAGMENT.fullmatch(token.value):
            raise ValueError('SVG CSS references must be local fragment IDs')
        if token.type == 'function' and token.lower_name == 'url':
            values = [part for part in token.arguments if part.type not in ('whitespace', 'comment')]
            if len(values) != 1 or values[0].type != 'string' or not FRAGMENT.fullmatch(values[0].value):
                raise ValueError('SVG CSS references must be local fragment IDs')
        children = getattr(token, 'arguments', getattr(token, 'content', []))
        pending.extend((child, depth + 1) for child in children)


def _check_node(node) -> None:
    name = node.tag.rsplit('}', 1)[-1]
    if name not in ALLOWED or not node.tag.startswith('{http://www.w3.org/2000/svg}'):
        raise ValueError('SVG must contain native vector shapes and text')
    for key, value in node.attrib.items():
        key = key.rsplit('}', 1)[-1]
        if (key.lower().startswith('on') or key.lower() in ('base', 'src')
                or key.lower() == 'href' and not FRAGMENT.fullmatch(value)):
            raise ValueError('SVG active or external references are not allowed')
        if re.search(r'@import|javascript:', value, re.I):
            raise ValueError('SVG active CSS is not allowed')
        if key == 'style' or '\\' in value or 'url' in value.lower():
            check_css(tinycss2.parse_component_value_list(value))


def inspect_svg(data: bytes, *, generated: bool = False) -> tuple[ET.Element, list[float]]:
    """Validate vectors; generated=True is reserved for trusted local CAD/slide output."""
    byte_limit = GENERATED_SVG_LIMIT if generated else SVG_LIMIT
    node_limit = GENERATED_SVG_NODE_LIMIT if generated else SVG_NODE_LIMIT
    if not data or len(data) > byte_limit:
        kind = 'Generated' if generated else 'Editable'
        raise ValueError(f'{kind} SVG is limited to {byte_limit // (1024 * 1024)} MiB')
    text = data.decode('utf-8')
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('SVG external declarations are not allowed')
    root = SafeET.fromstring(text, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    if root.tag != '{http://www.w3.org/2000/svg}svg':
        raise ValueError('Expected an SVG document with its XML namespace')
    pending = [(root, 0)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if count > node_limit or depth > SVG_DEPTH_LIMIT:
            raise ValueError('SVG exceeds its vector element or nesting limit')
        _check_node(node)
        pending.extend((child, depth + 1) for child in node)
    view = root.get('viewBox')
    values = ([float(n) for n in re.split(r'[\s,]+', view.strip())] if view else
              [0., 0., float(root.get('width', '0').removesuffix('px')),
               float(root.get('height', '0').removesuffix('px'))])
    if (len(values) != 4 or not all(math.isfinite(n) for n in values)
            or not 0 < values[2] <= 100000 or not 0 < values[3] <= 100000):
        raise ValueError('SVG needs a finite positive viewBox')
    return root, values


def rasterize(svg: bytes, output: Path, width: int, height: int, *, generated: bool = False) -> None:
    """Rasterize validated vectors with external-resource retrieval disabled."""
    from cairosvg.surface import PNGSurface
    inspect_svg(svg, generated=generated)
    if (any(isinstance(n, bool) or not isinstance(n, int) or not 0 < n <= 8192 for n in (width, height))
            or width * height > 64_000_000):
        raise ValueError('SVG raster output exceeds the 8192-side / 64-megapixel limit')

    def deny_fetch(url, resource_type):
        raise ValueError('External SVG resources are disabled')

    PNGSurface.convert(bytestring=svg, write_to=str(output), output_width=width,
                              output_height=height, url_fetcher=deny_fetch)


def normalized_svg(data: bytes) -> str:
    """Normalize an imported document only after enforcing strict import limits."""
    root, (x, y, w, h) = inspect_svg(data)
    scale = min(1280/w, 720/h)
    canvas = ET.Element('{http://www.w3.org/2000/svg}svg', {'width': '1280', 'height': '720', 'viewBox': '0 0 1280 720'})
    group = ET.SubElement(canvas, '{http://www.w3.org/2000/svg}g', {
        'transform': f'translate({(1280-w*scale)/2:g} {(720-h*scale)/2:g}) scale({scale:g}) translate({-x:g} {-y:g})'})
    inherited = ET.SubElement(group, '{http://www.w3.org/2000/svg}g', {
        k: v for k, v in root.attrib.items() if k not in ('width', 'height', 'viewBox', 'preserveAspectRatio', 'x', 'y')})
    for child in root:
        inherited.append(child)
    return ET.tostring(canvas, encoding='unicode')


def import_svg(store, data: bytes, name: str | None = None) -> dict:
    """Preserve original imported SVG bytes after validation."""
    try:
        root, view = inspect_svg(data)
    except (ET.ParseError, UnicodeError, OverflowError) as error:
        raise ValueError('Invalid editable SVG') from error
    key = hashlib.sha256(data).hexdigest() + '.svg'
    folder = store.root / 'assets'
    folder.mkdir(exist_ok=True)
    path = contained(folder, key)
    if not path.is_file() or sha256(path) != key.split('.')[0]:
        import uuid
        temporary = folder / (uuid.uuid4().hex + '.tmp')
        temporary.write_bytes(data)
        temporary.replace(path)
    meta = {'asset': key, 'kind': 'svg', 'bytes': len(data), 'view_box': view,
            'native_elements': sum(1 for _ in root.iter()), 'original_preserved': True,
            'label': Path(name or key).name[:120]}
    atomic_json(folder / (key + '.json'), meta)
    return meta
