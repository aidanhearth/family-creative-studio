// Load geometry, skins and animations with the browser's actual glTF loader.
// Texture decoding is already validated in Python; omit materials only in this
// disposable inspection copy so Node never needs browser image/network APIs.
import fs from 'node:fs';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {Box3, Vector3} from 'three';
const bytes = fs.readFileSync(process.argv[2]);
const jsonLength = bytes.readUInt32LE(12);
const doc = JSON.parse(bytes.subarray(20, 20 + jsonLength).toString());
for (const mesh of doc.meshes || []) for (const primitive of mesh.primitives) delete primitive.material;
doc.materials = []; doc.textures = []; doc.images = [];
const json = Buffer.from(JSON.stringify(doc));
const padded = Buffer.concat([json, Buffer.alloc((4 - json.length % 4) % 4, 32)]);
const remainder = bytes.subarray(20 + jsonLength);
const header = Buffer.alloc(20); header.write('glTF'); header.writeUInt32LE(2, 4); header.writeUInt32LE(20 + padded.length + remainder.length, 8); header.writeUInt32LE(padded.length, 12); header.writeUInt32LE(0x4e4f534a, 16);
const input = Buffer.concat([header, padded, remainder]);
const gltf = await new Promise((resolve, reject) => new GLTFLoader().parse(input.buffer.slice(input.byteOffset, input.byteOffset + input.byteLength), '', resolve, reject));
gltf.scene.updateMatrixWorld(true);
const meshes = [], ids = new Set();
gltf.scene.traverse(mesh => {
  if (!mesh.isMesh) return;
  let owner = mesh, nodeIndex;
  while (owner && nodeIndex === undefined) { nodeIndex = gltf.parser.associations.get(owner)?.nodes; owner = owner.parent; }
  if (nodeIndex === undefined) throw new Error('Imported mesh has no glTF node identity');
  const positions = mesh.geometry.getAttribute('position'), indices = mesh.geometry.index;
  for (let i = 0; i < positions.count; i++) if (![positions.getX(i), positions.getY(i), positions.getZ(i)].every(Number.isFinite)) throw new Error('Non-finite scene vertex');
  if (indices) for (let i = 0; i < indices.count; i++) if (indices.getX(i) >= positions.count) throw new Error('Scene triangle index exceeds vertex array');
  if (mesh.isSkinnedMesh) mesh.skeleton.update();
  const bounds = new Box3().setFromObject(mesh, true);
  if (bounds.isEmpty() || !bounds.min.toArray().concat(bounds.max.toArray()).every(Number.isFinite)) throw new Error('Scene mesh has invalid bounds');
  const id = `node-${nodeIndex}`; ids.add(id);
  meshes.push({id, node: nodeIndex, name: doc.nodes[nodeIndex].name || id, vertices: positions.count, skinned: !!mesh.isSkinnedMesh,
    morph_targets: mesh.morphTargetInfluences?.length || 0, bounds_m: {min: bounds.min.toArray(), max: bounds.max.toArray()}});
});
if (!meshes.length) throw new Error('Default scene contains no mesh surfaces');
const animations = gltf.animations.map((clip, index) => {
  if (!Number.isFinite(clip.duration) || clip.duration < 0 || clip.duration > 7200) throw new Error('Scene animation exceeds 7200 seconds');
  for (const track of clip.tracks) {
    if (![...track.times, ...track.values].every(Number.isFinite)) throw new Error('Non-finite scene animation data');
    if (track.times.some((v, i) => v < 0 || i > 0 && v <= track.times[i - 1])) throw new Error('Scene animation keyframes must increase');
  }
  return {index, name: clip.name || `animation-${index}`, duration_s: clip.duration, tracks: clip.tracks.length};
});
const bounds = new Box3().setFromObject(gltf.scene, true);
const size = bounds.getSize(new Vector3());
if (size.length() <= 0 || size.length() > 1e6) throw new Error('Scene has empty or unbounded dimensions');
fs.writeFileSync(process.argv[3], JSON.stringify({kind: 'scene', format: 'GLB', coordinates: 'right-handed-y-up-metres', bounds_kind: 'default pose; animation envelopes are not inferred',
  bounds_m: {min: bounds.min.toArray(), max: bounds.max.toArray()}, size_m: size.toArray(),
  nodes: doc.nodes.length, meshes: meshes.length, part_count: ids.size, part_ids: [...ids], mesh_nodes: meshes, animations}, null, 2));
