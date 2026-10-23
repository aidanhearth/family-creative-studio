"""Validate self-contained glTF binary documents before any renderer sees them."""
from __future__ import annotations

import importlib.util
import io
import math
from pathlib import Path
import struct
import warnings

from PIL import Image
from .paths import ROOT

SUPPORTED_EXTENSIONS = {
    'KHR_lights_punctual', 'KHR_materials_clearcoat', 'KHR_materials_dispersion',
    'KHR_materials_ior', 'KHR_materials_sheen', 'KHR_materials_specular',
    'KHR_materials_transmission', 'KHR_materials_iridescence', 'KHR_materials_anisotropy',
    'KHR_materials_unlit', 'KHR_materials_volume', 'KHR_texture_transform',
    'KHR_mesh_quantization', 'KHR_materials_emissive_strength', 'EXT_texture_webp', 'EXT_mesh_gpu_instancing',
}
EXTERNAL_DECODERS = {'KHR_draco_mesh_compression', 'EXT_meshopt_compression', 'KHR_texture_basisu'}
COMPONENT_BYTES = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
TYPE_COUNTS = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT2': 4, 'MAT3': 9, 'MAT4': 16}


def _index(items, value, label):
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < len(items):
        raise ValueError(f'Invalid {label} reference')
    return items[value]


def _integer(value, minimum=0, maximum=2_000_000):
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise ValueError('GLB integer is outside its resource bounds')
    return value


def _finite(values, count, label):
    if not isinstance(values, list) or len(values) != count or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in values):
        raise ValueError(f'Invalid GLB {label}')


def read_document(path):
    spec = importlib.util.spec_from_file_location('studio_scene_glb_container', ROOT / 'vendor/img2threejs--img2threejs/glb_container.py')
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    doc, binary, _ = parser.parse_glb(Path(path))
    metadata = validate_document(doc, binary)
    return doc, binary, metadata


def validate_document(doc, binary):
    if doc.get('asset', {}).get('version') != '2.0':
        raise ValueError('Only glTF 2.0 scenes are supported')
    buffers = doc.get('buffers', [])
    if len(buffers) != 1 or 'uri' in buffers[0]:
        raise ValueError('GLB must use one embedded binary buffer; external/data URIs are not accepted')
    length = _integer(buffers[0].get('byteLength'), 1, 50 * 1024 * 1024)
    if not length <= len(binary) <= length + 3:
        raise ValueError('GLB buffer byte length does not match embedded data')
    used, required = set(doc.get('extensionsUsed', [])), set(doc.get('extensionsRequired', []))
    if used & EXTERNAL_DECODERS or required & EXTERNAL_DECODERS:
        raise ValueError('Export an uncompressed GLB: Draco, Meshopt and BasisU require external decoders')
    if required - SUPPORTED_EXTENSIONS:
        raise ValueError('Required GLB extension is unsupported: ' + ', '.join(sorted(required - SUPPORTED_EXTENSIONS)))
    # Check actual extension locations too, not only a declarative extension list.
    stack = [(doc, 0)]
    while stack:
        value, depth = stack.pop()
        if depth > 32:
            raise ValueError('GLB document nesting exceeds 32 levels')
        if isinstance(value, dict):
            if set(value.get('extensions', {})) & EXTERNAL_DECODERS:
                raise ValueError('Compressed GLB extension requires an external decoder')
            stack.extend((child, depth + 1) for child in value.values())
        elif isinstance(value, list):
            stack.extend((child, depth + 1) for child in value)
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError('GLB contains a non-finite number')
    views = doc.get('bufferViews', [])
    accessors = doc.get('accessors', [])
    if len(views) > 16384 or len(accessors) > 16384:
        raise ValueError('GLB exceeds 16384 buffer views or accessors')
    for view in views:
        if view.get('buffer') != 0:
            raise ValueError('GLB buffer view references an external buffer')
        offset = _integer(view.get('byteOffset', 0), maximum=length)
        count = _integer(view.get('byteLength'), 1, length)
        if offset + count > length:
            raise ValueError('GLB buffer view runs past binary data')
        if 'byteStride' in view and (not 4 <= view['byteStride'] <= 252 or view['byteStride'] % 4):
            raise ValueError('Invalid interleaved GLB stride')
    total_elements = 0
    for accessor in accessors:
        count = _integer(accessor.get('count'), 1)
        total_elements += count
        if total_elements > 12_000_000:
            raise ValueError('GLB exceeds twelve million accessor elements')
        component = accessor.get('componentType'); kind = accessor.get('type')
        if component not in COMPONENT_BYTES or kind not in TYPE_COUNTS:
            raise ValueError('Unsupported GLB accessor component/type')
        width = COMPONENT_BYTES[component]
        element = width * TYPE_COUNTS[kind]
        if kind.startswith('MAT'):
            side = int(kind[-1]); element = ((side * width + 3) // 4) * 4 * side
        offset = _integer(accessor.get('byteOffset', 0), maximum=length)
        if offset % width:
            raise ValueError('Misaligned GLB accessor')
        if 'bufferView' in accessor:
            view = _index(views, accessor['bufferView'], 'accessor buffer')
            stride = view.get('byteStride', element)
            if stride < element or stride % width or offset + (count - 1) * stride + element > view['byteLength']:
                raise ValueError('GLB accessor overruns its buffer view')
        elif offset or 'sparse' not in accessor:
            raise ValueError('GLB accessor requires data or sparse values')
        if 'sparse' in accessor:
            sparse = accessor['sparse']; n = _integer(sparse.get('count'), 1, count)
            indices, values = sparse['indices'], sparse['values']
            index_type = indices.get('componentType')
            if index_type not in (5121,5123,5125):
                raise ValueError('Invalid sparse GLB index type')
            index_width = COMPONENT_BYTES[index_type]
            iv = _index(views, indices.get('bufferView'), 'sparse index buffer')
            vv = _index(views, values.get('bufferView'), 'sparse value buffer')
            index_offset = _integer(indices.get('byteOffset',0),maximum=length)
            vo = _integer(values.get('byteOffset',0),maximum=length)
            if index_offset + n * index_width > iv['byteLength'] or vo + n * element > vv['byteLength'] or index_offset % index_width or vo % width:
                raise ValueError('Sparse GLB accessor exceeds its data')
            fmt = {5121:'B',5123:'H',5125:'I'}[index_type]
            previous = -1
            for i in range(n):
                value = struct.unpack_from('<'+fmt,binary,iv.get('byteOffset',0)+index_offset+i*index_width)[0]
                if not previous < value < count:
                    raise ValueError('Sparse GLB indices must be increasing and within bounds')
                previous = value
    nodes, meshes, skins = doc.get('nodes', []), doc.get('meshes', []), doc.get('skins', [])
    materials, textures, images = doc.get('materials', []), doc.get('textures', []), doc.get('images', [])
    animations, scenes = doc.get('animations', []), doc.get('scenes', [])
    if not nodes or not meshes or not scenes or len(nodes)>4096 or len(meshes)>1024 or len(animations)>128 or len(materials)>1024 or len(images)>128 or len(skins)>128:
        raise ValueError('GLB scene exceeds supported node, mesh, animation, material or texture bounds')
    parents = {}
    for i,node in enumerate(nodes):
        if 'matrix' in node:
            _finite(node['matrix'],16,'node matrix')
            if any(k in node for k in ('translation','rotation','scale')):
                raise ValueError('GLB node must use matrix or TRS, not both')
        for key,n in (('translation',3),('rotation',4),('scale',3)):
            if key in node: _finite(node[key],n,'node '+key)
        if 'mesh' in node: _index(meshes,node['mesh'],'mesh')
        if 'skin' in node: _index(skins,node['skin'],'skin')
        for child in node.get('children',[]):
            _index(nodes,child,'child node')
            if child in parents: raise ValueError('GLB nodes cannot have multiple parents')
            parents[child]=i
    for start in range(len(nodes)):
        seen=set(); node=start
        while node in parents:
            if node in seen or len(seen)>128: raise ValueError('GLB hierarchy has a cycle or exceeds 128 levels')
            seen.add(node); node=parents[node]
    for scene in scenes:
        for index in scene.get('nodes',[]):
            _index(nodes,index,'scene root')
            if index in parents: raise ValueError('Scene root has a parent node')
    scene = _index(scenes,doc.get('scene',0),'default scene')
    if not scene.get('nodes'): raise ValueError('Default GLB scene is empty')
    primitive_count = 0
    for mesh in meshes:
        if not mesh.get('primitives'): raise ValueError('GLB mesh is empty')
        for primitive in mesh['primitives']:
            primitive_count += 1
            if primitive_count>4096: raise ValueError('GLB exceeds 4096 mesh primitives')
            if primitive.get('mode',4) not in (4,5,6): raise ValueError('GLB imports require triangle surfaces')
            attributes = primitive.get('attributes',{})
            position = _index(accessors,attributes.get('POSITION'),'position accessor')
            if position['type']!='VEC3': raise ValueError('GLB positions require VEC3')
            for key,index in attributes.items():
                accessor = _index(accessors,index,'vertex attribute')
                if accessor['count']!=position['count']: raise ValueError('GLB vertex attribute counts differ')
            for target in primitive.get('targets',[]):
                for index in target.values():
                    if _index(accessors,index,'morph target')['count']!=position['count']: raise ValueError('GLB morph target size differs')
            if 'indices' in primitive:
                accessor=_index(accessors,primitive['indices'],'triangle indices')
                if accessor['type']!='SCALAR' or accessor['componentType'] not in (5121,5123,5125): raise ValueError('Invalid GLB triangle indices')
            if 'material' in primitive: _index(materials,primitive['material'],'material')
    for skin in skins:
        if not skin.get('joints') or len(skin['joints'])>512: raise ValueError('GLB skin must contain 1–512 joints')
        for joint in skin['joints']: _index(nodes,joint,'joint')
        if 'inverseBindMatrices' in skin:
            a=_index(accessors,skin['inverseBindMatrices'],'bind matrix')
            if a['type']!='MAT4' or a['componentType']!=5126 or a['count']!=len(skin['joints']): raise ValueError('Invalid GLB inverse bind matrices')
    for animation in animations:
        for sampler in animation.get('samplers',[]):
            a=_index(accessors,sampler.get('input'),'animation time')
            if a['type']!='SCALAR' or a['componentType']!=5126: raise ValueError('Animation times require float scalars')
            _index(accessors,sampler.get('output'),'animation values')
            if sampler.get('interpolation','LINEAR') not in ('LINEAR','STEP','CUBICSPLINE'): raise ValueError('Unsupported animation interpolation')
        for channel in animation.get('channels',[]):
            sampler=_index(animation.get('samplers',[]),channel.get('sampler'),'animation sampler')
            target=channel.get('target',{});node=_index(nodes,target.get('node'),'animation node')
            if target.get('path') not in ('translation','rotation','scale','weights'): raise ValueError('Unsupported animation channel')
            values=accessors[sampler['output']]; keys=accessors[sampler['input']]['count']
            multiplier=3 if sampler.get('interpolation')=='CUBICSPLINE' else 1
            expected_type='VEC4' if target['path']=='rotation' else 'VEC3'
            if target['path']=='weights':
                mesh=_index(meshes,node.get('mesh'),'morph animation mesh')
                target_counts={len(p.get('targets',[])) for p in mesh['primitives']}
                if len(target_counts)!=1 or 0 in target_counts: raise ValueError('Morph animation requires matching morph targets')
                multiplier*=target_counts.pop(); expected_type='SCALAR'
            if values['type']!=expected_type or values['componentType']!=5126 or values['count']!=keys*multiplier:
                raise ValueError('GLB animation values do not match their target or key count')
    pixel_count=0
    for image in images:
        if 'uri' in image or image.get('mimeType') not in ('image/png','image/jpeg','image/webp'):
            raise ValueError('GLB images must be embedded PNG/JPEG/WebP buffer views')
        view=_index(views,image.get('bufferView'),'image buffer')
        payload=binary[view.get('byteOffset',0):view.get('byteOffset',0)+view['byteLength']]
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(payload)) as img:
                pixel_count += img.width*img.height
                if pixel_count>64_000_000 or getattr(img,'n_frames',1)!=1: raise ValueError('GLB texture total exceeds 64 megapixels or contains animation')
                if {'PNG':'image/png','JPEG':'image/jpeg','WEBP':'image/webp'}.get(img.format)!=image['mimeType']:
                    raise ValueError('GLB image content does not match its MIME type')
                img.verify()
    for texture in textures:
        source=texture.get('extensions',{}).get('EXT_texture_webp',{}).get('source',texture.get('source'))
        _index(images,source,'texture image')
    for material in materials:
        remaining=[material]
        while remaining:
            value=remaining.pop()
            if isinstance(value,dict):
                for key,child in value.items():
                    if key.endswith('Texture') and isinstance(child,dict):
                        _index(textures,child.get('index'),'material texture')
                    remaining.append(child)
            elif isinstance(value,list): remaining.extend(value)
    return {'materials':len(materials),'textures':len(textures),'skins':len(skins),'mesh_definitions':len(meshes),
            'primitives':primitive_count,'extensions':sorted(used),'unsupported_optional_extensions':sorted(used-SUPPORTED_EXTENSIONS)}
