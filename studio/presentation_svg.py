"""Lower imported SVG similarity transforms to editable DrawingML geometry.

The pinned PPT converter accepts affine transforms on vectors, but only
translation/rotation on text. Resolve inherited text metrics before distributing
group transforms, so a viewBox fit does not become a bitmap or shrink its text.
This module runs inside the PPT worker, after its pinned upstream is on sys.path.
"""
from __future__ import annotations

import math
from xml.etree import ElementTree as ET

from .svg_assets import inspect_svg

SVG = '{http://www.w3.org/2000/svg}'


def _decimal(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError('Non-finite SVG presentation coordinate')
    return f'{value:.10f}'.rstrip('0').rstrip('.') or '0'


def native_presentation_svg(data: bytes) -> ET.Element:
    """Fit an original SVG into 1280×720, preserving native vectors and text.

    Positive uniform text scales (including nested rotations/translations) are
    baked into coordinates, font sizes and tracking. Text shear, reflection or
    anisotropic scaling raises an actionable error instead of changing artwork.
    Definition coordinates stay local: the accumulated transform remains on the
    referencing vector. Existing groups, styles and paint order are retained.
    """
    from svg_to_pptx.drawingml.text_properties import (
        resolve_project_font_sizes, resolve_project_letter_spacings,
    )
    from svg_to_pptx.drawingml.utils import (
        _extract_inheritable_styles, matrix_multiply,
        parse_svg_length, parse_transform_matrix,
    )

    root, (x, y, width, height) = inspect_svg(data)
    fonts = resolve_project_font_sizes(root)
    tracking = resolve_project_letter_spacings(root, fonts)
    scale = min(1280 / width, 720 / height)
    fit = f'translate({_decimal((1280-width*scale)/2)} {_decimal((720-height*scale)/2)}) scale({_decimal(scale)}) translate({_decimal(-x)} {_decimal(-y)})'

    def set_metric(node: ET.Element, name: str, value: float) -> None:
        # Inline style wins over presentation attributes. Replace both copies.
        node.set(name, _decimal(value))
        style = node.get('style')
        if style:
            retained = [part for part in style.split(';')
                        if part.split(':', 1)[0].strip().lower() != name]
            node.set('style', ';'.join(retained))

    def bake_text(node: ET.Element, amount: float, inherited: dict[str, str]) -> None:
        local_styles = inherited | _extract_inheritable_styles(node)
        for attribute in ('x', 'y', 'dx', 'dy', 'textLength'):
            raw = node.get(attribute)
            if raw is not None:
                axis = height if attribute in ('y', 'dy') else width
                node.set(attribute, _decimal(amount * parse_svg_length(
                    raw, percent_base=axis, font_size=fonts[id(node)])))
        set_metric(node, 'font-size', amount * fonts[id(node)])
        set_metric(node, 'letter-spacing', amount * tracking[id(node)])
        if 'stroke-width' in local_styles or local_styles.get('stroke', 'none') != 'none':
            set_metric(node, 'stroke-width', amount * parse_svg_length(
                local_styles.get('stroke-width', '1'), font_size=fonts[id(node)]))
        for child in node:
            if child.tag == SVG + 'tspan':
                bake_text(child, amount, local_styles)

    def lower(node: ET.Element, matrix, chain: str, inherited: dict[str, str]) -> ET.Element:
        tag = node.tag.removeprefix(SVG)
        if tag in ('defs', 'title', 'desc'):
            return node
        own = node.get('transform', '')
        current = matrix_multiply(matrix, parse_transform_matrix(own)) if own else matrix
        transforms = ' '.join(value for value in (chain, own) if value)
        styles = inherited | _extract_inheritable_styles(node)
        if tag in ('g', 'svg'):
            node.attrib.pop('transform', None)
            for index, child in enumerate(list(node)):
                node[index] = lower(child, current, transforms, styles)
        elif tag == 'text':
            a, b, c, d, e, f = current
            amount = math.hypot(a, b)
            if (amount <= 1e-12 or not math.isclose(a, d, abs_tol=1e-8, rel_tol=1e-8)
                    or not math.isclose(b, -c, abs_tol=1e-8, rel_tol=1e-8)):
                raise ValueError('Editable SVG text requires uniform scale and rotation; '
                                 'remove text shear, reflection or non-uniform scaling')
            bake_text(node, amount, inherited)
            angle = math.degrees(math.atan2(b, a))
            node.attrib.pop('transform', None)
            if abs(angle) > 1e-10:
                node.set('transform', f'rotate({_decimal(angle)})')
            wrapper = ET.Element(SVG + 'g', {'transform': f'translate({_decimal(e)} {_decimal(f)})'})
            wrapper.append(node)
            return wrapper
        elif transforms:
            # Keep the actual operation list; rounded rectangles accept a
            # translate/rotate/scale list but deliberately reject a matrix.
            node.set('transform', transforms)
        return node

    lower(root, parse_transform_matrix(fit), fit, {})
    root.set('width', '1280'); root.set('height', '720')
    root.set('viewBox', '0 0 1280 720')
    root.attrib.pop('preserveAspectRatio', None)
    root.attrib.pop('x', None); root.attrib.pop('y', None)
    return root
