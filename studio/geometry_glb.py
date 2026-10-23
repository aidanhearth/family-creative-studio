"""Attach semantic part identities without changing the exported mesh buffers."""
import json
from pathlib import Path
import struct


def annotate_parts(path: Path, part_ids):
    data = path.read_bytes()
    if len(data) < 20 or struct.unpack_from('<4sII', data) != (b'glTF', 2, len(data)):
        raise ValueError('Invalid exported GLB header')
    chunks, offset = [], 12
    while offset < len(data):
        size, kind = struct.unpack_from('<II', data, offset)
        offset += 8
        payload = data[offset:offset + size]
        if len(payload) != size:
            raise ValueError('Truncated exported GLB chunk')
        chunks.append((kind, payload))
        offset += size
    if not chunks or chunks[0][0] != 0x4E4F534A:
        raise ValueError('Exported GLB is missing its JSON document')
    doc = json.loads(chunks[0][1])
    nodes = doc['nodes']
    roots = doc['scenes'][doc.get('scene', 0)]['nodes']
    # The exporter receives one explicit assembly whose direct children are
    # semantic parts. Nested STEP meshes inherit the outer child identity.
    if len(roots) != 1:
        raise ValueError('Exported CAD must have one assembly root')
    children = [nodes[i] for i in nodes[roots[0]].get('children', [])]
    if len(children) != len(part_ids) or sorted(n.get('name') for n in children) != sorted(part_ids):
        raise ValueError('GLB assembly lost stable CAD part identities')
    for node in children:
        node.setdefault('extras', {})['studio_part_id'] = node['name']
    payload = json.dumps(doc, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    payload += b' ' * (-len(payload) % 4)
    chunks[0] = (0x4E4F534A, payload)
    body = b''.join(struct.pack('<II', len(payload), kind) + payload for kind, payload in chunks)
    path.write_bytes(struct.pack('<4sII', b'glTF', 2, 12 + len(body)) + body)
