import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';

export function makeViewer(container,manifest,{glbUrl=null,glbData=null,manual=false}={}) {
  const scene=new THREE.Scene();scene.background=new THREE.Color(manifest.brand.paper);
  const camera=new THREE.PerspectiveCamera(34,1,0.1,10000);camera.up.set(0,0,1);
  const renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,preserveDrawingBuffer:true});
  renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
  renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.55;
  container.replaceChildren(renderer.domElement);
  const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=!manual;controls.minDistance=20;controls.maxDistance=3500;
  scene.add(new THREE.HemisphereLight(0xffffff,0x898174,2.6));
  const sun=new THREE.DirectionalLight(0xfff4dd,4);sun.position.set(-250,-350,600);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);sun.shadow.camera.left=-450;sun.shadow.camera.right=450;sun.shadow.camera.top=450;sun.shadow.camera.bottom=-450;sun.shadow.bias=-.0003;scene.add(sun);
  const fill=new THREE.DirectionalLight(0xdce7ff,1.5);fill.position.set(300,250,300);scene.add(fill);
  let group=new THREE.Group();scene.add(group);let elements=[],destroyed=false;
  const minZ=manifest.solids.length?Math.min(...manifest.solids.map(s=>s.position[2]-s.size[2]/2)):0;
  const ground=new THREE.Mesh(new THREE.PlaneGeometry(3000,3000),new THREE.ShadowMaterial({opacity:.14}));ground.position.z=minZ-.25;ground.receiveShadow=true;scene.add(ground);
  for(const s of manifest.solids){
    const [w,d,h]=s.size;let geo;
    if(s.kind==='box'){
      const shape=new THREE.Shape();shape.moveTo(-w/2,-d/2);shape.lineTo(w/2,-d/2);shape.lineTo(w/2,d/2);shape.lineTo(-w/2,d/2);shape.closePath();
      if(s.bore){const hole=new THREE.Path();hole.absarc(0,0,s.bore/2,0,Math.PI*2,true);shape.holes.push(hole);}
      geo=new THREE.ExtrudeGeometry(shape,{depth:h,bevelEnabled:false,curveSegments:64});geo.translate(0,0,-h/2);
    } else {
      const shape=new THREE.Shape();shape.absarc(0,0,w/2,0,Math.PI*2,false);
      if(s.bore){const hole=new THREE.Path();hole.absarc(0,0,s.bore/2,0,Math.PI*2,true);shape.holes.push(hole);}
      geo=new THREE.ExtrudeGeometry(shape,{depth:h,bevelEnabled:false,curveSegments:64});geo.translate(0,0,-h/2);
    }
    const material=new THREE.MeshStandardMaterial({color:s.color,roughness:.65,metalness:.12});
    const mesh=new THREE.Mesh(geo,material);mesh.position.fromArray(s.position);mesh.castShadow=true;mesh.receiveShadow=true;mesh.name=s.id;mesh.userData.base=mesh.position.clone();group.add(mesh);elements.push(mesh);
    const edges=new THREE.LineSegments(new THREE.EdgesGeometry(geo,35),new THREE.LineBasicMaterial({color:manifest.brand.ink,transparent:true,opacity:.16}));mesh.add(edges);
  }
  const box=new THREE.Box3().setFromObject(group), center=box.getCenter(new THREE.Vector3());const size=box.isEmpty()?100:box.getSize(new THREE.Vector3()).length();
  controls.target.copy(center);camera.position.copy(center).add(new THREE.Vector3(size*1.05,-size*1.5,size*.85));controls.update();
  const state={mode:'parametric-preview',exploded:false};
  function loadGLB(url,onLoad,onError){const loader=new GLTFLoader();if(glbData){try{loader.parse(Uint8Array.from(atob(glbData),c=>c.charCodeAt(0)).buffer,'',onLoad,onError);}catch(e){onError(e);}}else loader.load(url,onLoad,undefined,onError);}
  const ready=(glbUrl||glbData)?new Promise((resolve,reject)=>loadGLB(glbUrl,gltf=>{
    if(destroyed){reject(Error('Viewer disposed'));return;}
    const actual=gltf.scene;actual.rotation.x=Math.PI/2;actual.scale.setScalar(1000);actual.updateMatrixWorld(true);
    const meshes=[];actual.traverse(o=>{if(o.isMesh)meshes.push(o);});
    if(meshes.length!==manifest.solids.length){reject(Error('CAD part count mismatch'));return;}
    const used=new Set(),replacement=new THREE.Group();scene.add(replacement);
    for(const mesh of meshes){
      const meshBounds=new THREE.Box3().setFromObject(mesh),midpoint=meshBounds.getCenter(new THREE.Vector3()),extent=meshBounds.getSize(new THREE.Vector3());
      const error=s=>midpoint.distanceTo(new THREE.Vector3(...s.position))+extent.distanceTo(new THREE.Vector3(...s.size));
      const match=manifest.solids.filter(s=>!used.has(s.id)).sort((a,b)=>error(a)-error(b))[0];
      if(!match||error(match)>.1){reject(Error('CAD part positions mismatch'));return;}
      used.add(match.id);replacement.attach(mesh);mesh.name=match.id;mesh.userData.base=mesh.position.clone();mesh.castShadow=true;mesh.receiveShadow=true;
      mesh.material=new THREE.MeshStandardMaterial({color:match.color,roughness:.65,metalness:.12});
    }
    scene.remove(group);group.traverse(o=>{o.geometry?.dispose();o.material?.dispose();});group=replacement;elements=meshes;state.mode='cad-glb';resolve(state);
  },reject)):Promise.resolve(state);
  const resize=()=>{const w=container.clientWidth||600,h=container.clientHeight||450;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();};const observer=new ResizeObserver(resize);observer.observe(container);resize();
  let raf;function loop(){if(destroyed)return;raf=requestAnimationFrame(loop);controls.update();renderer.render(scene,camera);}if(!manual)loop();
  function renderFrame(mode,progress){
    const t=Math.max(0,Math.min(1,progress)),explode=mode==='explode'?Math.sin(Math.PI*t):0;
    const ordered=[...elements].sort((a,b)=>a.userData.base.z-b.userData.base.z||a.name.localeCompare(b.name));
    ordered.forEach((o,i)=>{o.position.copy(o.userData.base);o.position.z+=i*size*.22*explode;});
    const target=center.clone();if(mode==='explode')target.z+=Math.max(0,elements.length-1)*size*.11;
    const angle=-.96+(mode==='orbit'?t*Math.PI*2:0),distance=size*(mode==='explode'?3.7:2.4);
    camera.position.copy(target).add(new THREE.Vector3(Math.cos(angle)*distance,Math.sin(angle)*distance,distance*.6));controls.target.copy(target);camera.lookAt(target);camera.updateMatrixWorld();
    renderer.render(scene,camera);
    const bounds=new THREE.Box3().setFromObject(group),points=[];
    if(!bounds.isEmpty())for(const x of [bounds.min.x,bounds.max.x])for(const y of [bounds.min.y,bounds.max.y])for(const z of [bounds.min.z,bounds.max.z])points.push(new THREE.Vector3(x,y,z).project(camera).toArray());
    return {progress:t,mode,camera:camera.position.toArray(),target:target.toArray(),explode,inside:points.every(p=>Math.abs(p[0])<.98&&Math.abs(p[1])<.98&&Math.abs(p[2])<1),parts:elements.map(o=>({id:o.name,position:o.position.toArray(),size:new THREE.Box3().setFromObject(o).getSize(new THREE.Vector3()).toArray(),color:'#'+o.material.color.getHexString()}))};
  }
  return {state,ready,renderFrame,setExploded(value){state.exploded=value;elements.forEach((o,i)=>{o.position.copy(o.userData.base);if(value)o.position.z+=i*45;});},focus(ids){elements.forEach(o=>{o.material.opacity=ids.length&&!ids.includes(o.name)?.22:1;o.material.transparent=o.material.opacity<1;});},dispose(){destroyed=true;cancelAnimationFrame(raf);observer.disconnect();controls.dispose();scene.traverse(o=>{o.geometry?.dispose();o.material?.dispose();});renderer.dispose();}};
}
window.makeStudioViewer=makeViewer;
const data=document.getElementById('project-data');
if(data){const m=JSON.parse(data.textContent);const mount=document.getElementById('viewer'),state=document.getElementById('renderer-state');
 try{const viewer=makeViewer(mount,m,{glbData:document.getElementById('project-glb')?.textContent.trim()||null});window.studioViewer=viewer;state.textContent='mm · 參數幾何預覽';document.getElementById('explode').onclick=()=>viewer.setExploded(!viewer.state.exploded);document.querySelectorAll('[data-motion]').forEach(button=>button.onclick=async()=>{await viewer.ready;const started=performance.now(),mode=button.dataset.motion;function animate(now){viewer.renderFrame(mode,Math.min(1,(now-started)/5000));if(now-started<5000)requestAnimationFrame(animate);}requestAnimationFrame(animate);});}
 catch(e){mount.replaceChildren(Object.assign(document.createElement('img'),{src:'anatomy.svg',alt:m.title}));state.textContent='SVG · 此瀏覽器未啟用 3D';}}
