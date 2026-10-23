import fs from 'node:fs';
import path from 'node:path';
import {fitProjection, depthOf, iso, pathOf} from '../vendor/wheresryan22--anatomy/iso-kit.mjs';

// Geometry is the actual post-boolean, post-fillet CAD tessellation. Never
// substitute primitive boxes for STEP imports, curved shapes or rotations.
const [manifestPath, output, geometryPath, focusJSON = '[]'] = process.argv.slice(2);
const m = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const focus = new Set(JSON.parse(focusJSON));
const visible = m.solids.filter(s => !s.construction);
const geometry = visible.length ? JSON.parse(fs.readFileSync(geometryPath || path.join(path.dirname(manifestPath), 'geometry.json'), 'utf8')) : {parts: []};
if (geometry.parts.length !== visible.length || visible.some(s => !geometry.parts.some(p => p.id === s.id))) throw new Error('CAD projection part identity does not match document');
const esc = s => String(s).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
const points = geometry.parts.flatMap(p => p.vertices);
const proj = fitProjection(points.length ? points : [[0, 0, 0], [100, 100, 100]], 760, 560, {pad: 60});
const subtract = (a, b) => a.map((x, i) => x - b[i]);
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const dot = (a, b) => a.reduce((sum, x, i) => sum + x * b[i], 0);
const camera = [Math.sqrt(3 / 8), Math.sqrt(3 / 8), .5];
const light = [-.25, -.4, .88];
const faces = [];
for (const part of geometry.parts) {
  const base = [1, 3, 5].map(i => parseInt(part.color.slice(i, i + 2), 16));
  const paper = [1, 3, 5].map(i => parseInt(m.brand.paper.slice(i, i + 2), 16));
  for (const tri of part.triangles) {
    const vertices = tri.map(i => part.vertices[i]);
    if (vertices.some(v => !v || v.length !== 3 || !v.every(Number.isFinite))) throw new Error('Invalid CAD tessellation vertices');
    const normal = cross(subtract(vertices[1], vertices[0]), subtract(vertices[2], vertices[0]));
    const length = Math.hypot(...normal);
    if (!length || dot(normal, camera) <= 0) continue;
    const shade = .76 + .24 * Math.max(0, dot(normal.map(v => v / length), light));
    const muted = focus.size && !focus.has(part.id);
    const color = '#' + base.map((c, i) => Math.round(muted ? c * shade * .22 + paper[i] * .78 : c * shade).toString(16).padStart(2, '0')).join('');
    const center = [0, 1, 2].map(i => vertices.reduce((sum, v) => sum + v[i], 0) / 3);
    faces.push({part, color, points: vertices.map(v => iso(v, proj)), depth: depthOf(center, proj)});
  }
}
faces.sort((a, b) => a.depth - b.depth);
const body = faces.map(f => `<path data-part-id="${esc(f.part.id)}" d="${pathOf(f.points, true)}" fill="${f.color}" stroke="${f.color}" stroke-width="0.25" stroke-linejoin="round"${focus.size && !focus.has(f.part.id) ? ' data-focus-state="muted"' : ''}/>`).join('');
fs.writeFileSync(output, `<svg xmlns="http://www.w3.org/2000/svg" width="760" height="560" viewBox="0 0 760 560" role="img" aria-label="${esc(m.title)}"><title>${esc(m.title)} — CAD tessellation projection</title><desc>Millimetre geometry projected from the validated CAD model. Focus: ${esc([...focus].join(', ') || 'all parts')}.</desc><rect width="760" height="560" fill="${m.brand.paper}"/><g id="cad-projection">${body}</g></svg>`);
