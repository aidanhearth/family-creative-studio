import fs from 'node:fs';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {Box3, Vector3} from 'three';

const b = fs.readFileSync(process.argv[2]);
const scene = await new Promise((resolve, reject) => new GLTFLoader().parse(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength), '', v => resolve(v.scene), reject));
scene.updateMatrixWorld(true);
const parts = new Map();
let volume = 0, triangleCount = 0;
scene.traverse(o => {
  if (!o.isMesh) return;
  let owner = o;
  while (owner && !owner.userData?.studio_part_id) owner = owner.parent;
  const id = owner?.userData?.studio_part_id;
  if (!id) throw new Error('GLB mesh is missing a stable CAD part ID');
  const position = o.geometry.attributes.position, index = o.geometry.index;
  let signed = 0;
  const box = new Box3();
  for (let i = 0; i < (index ? index.count : position.count); i += 3) {
    const v = [0, 1, 2].map(j => new Vector3().fromBufferAttribute(position, index ? index.getX(i + j) : i + j).applyMatrix4(o.matrixWorld));
    if (v.some(p => !p.toArray().every(Number.isFinite))) throw new Error('Non-finite GLB geometry');
    v.forEach(p => box.expandByPoint(p));
    signed += v[0].dot(v[1].clone().cross(v[2])) / 6;
    triangleCount++;
  }
  // Mesh primitives may represent open face patches, so accumulate signed
  // contributions by semantic part before taking the absolute volume.
  const part = parts.get(id) || {id, signed: 0, bounds: new Box3(), meshes: 0};
  part.signed += signed; part.bounds.union(box); part.meshes++;
  parts.set(id, part);
});
const result = [...parts.values()].map(p => ({id: p.id, volume_m3: Math.abs(p.signed), min: p.bounds.min.toArray(), max: p.bounds.max.toArray(), meshes: p.meshes}));
volume = result.reduce((sum, p) => sum + p.volume_m3, 0);
const box = new Box3().setFromObject(scene);
if (box.isEmpty() || !volume || !Number.isFinite(volume)) throw new Error('Empty or invalid GLB solid');
console.log(JSON.stringify({volume_m3: volume, min: box.min.toArray(), max: box.max.toArray(), size: box.getSize(new Vector3()).toArray(), names: result.map(p => p.id), parts: result, triangles: triangleCount}));
