import fs from 'node:fs';
import {fitProjection,boxCorners,roundedPlan,extrude,circleRing,depthOf,iso,pathOf} from '../vendor/wheresryan22--anatomy/iso-kit.mjs';
const [manifestPath, output] = process.argv.slice(2);
const m=JSON.parse(fs.readFileSync(manifestPath,'utf8'));
const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const parts=m.solids;
const points=parts.flatMap(s=>{let [w,d,h]=s.size,[x,y,z]=s.position; return boxCorners({x:x-w/2,y:y-d/2,w,d},z-h/2,z+h/2);});
const proj=fitProjection(points.length?points:[[0,0,0],[100,100,100]],760,560,{pad:60});
let body='';
for(const s of [...parts].sort((a,b)=>depthOf(a.position,proj)-depthOf(b.position,proj))){
 const [w,d,h]=s.size,[x,y,z]=s.position;
 const ring=s.kind==='cylinder'?circleRing(x,y,w/2,64):roundedPlan({x:x-w/2,y:y-d/2,w,d,r:0});
 const p=extrude(ring,z-h/2,h,proj);
 body+=`<g id="solid-${esc(s.id)}"><path d="${p.fill}" fill="${s.color}" stroke="${m.brand.ink}" stroke-width="1.3"/>`;
 p.shades.forEach((d,i)=>{if(d)body+=`<path d="${d}" fill="#000000" opacity="${.04+i*.055}"/>`;});
 body+=`<path d="${p.top}" fill="#ffffff" opacity="0.16"/><path d="${p.crease}" fill="none" stroke="${m.brand.ink}" stroke-width="0.7" opacity="0.55"/>`;
 if(s.bore){ const p2=circleRing(x,y,s.bore/2,64).map(([a,b])=>iso([a,b,z+h/2+.01],proj));body+=`<path d="${pathOf(p2,true)}" fill="${m.brand.paper}" stroke="${m.brand.ink}" stroke-width="1"/>`; }
 body+='</g>';
}
fs.writeFileSync(output,`<svg xmlns="http://www.w3.org/2000/svg" width="760" height="560" viewBox="0 0 760 560" role="img" aria-label="${esc(m.title)}"><title>${esc(m.title)} — Anatomy projection</title><rect width="760" height="560" fill="${m.brand.paper}"/>${body}</svg>`);
