import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {paperEffect} from './shader.js';

export function primitiveGeometry(solid){
 const [width,depth,height]=solid.size;
 if(solid.kind==='sphere')return new THREE.SphereGeometry(width/2,64,32);
 if(solid.kind==='cone'){
  const geometry=new THREE.CylinderGeometry((solid.top_diameter||0)/2,width/2,height,64);
  geometry.rotateX(Math.PI/2);return geometry;
 }
 if(solid.kind==='torus')return new THREE.TorusGeometry((width-height)/2,height/2,32,96);
 const shape=new THREE.Shape();
 if(solid.kind==='box'){
  shape.moveTo(-width/2,-depth/2);shape.lineTo(width/2,-depth/2);shape.lineTo(width/2,depth/2);shape.lineTo(-width/2,depth/2);shape.closePath();
 }else if(solid.kind==='cylinder')shape.absarc(0,0,width/2,0,Math.PI*2,false);
 else if(solid.kind==='extrusion'){
  const points=solid.profile||[];if(points.length<3)throw Error('擠出輪廓需要至少三個點');
  points.forEach(([x,y],i)=>shape[i?'lineTo':'moveTo'](x*width,y*depth));shape.closePath();
 }else throw Error(`此零件需要實體 CAD：${solid.id}`);
 if(solid.bore){const hole=new THREE.Path();hole.absarc(0,0,solid.bore/2,0,Math.PI*2,true);shape.holes.push(hole);}
 const geometry=new THREE.ExtrudeGeometry(shape,{depth:height,bevelEnabled:false,curveSegments:64});geometry.translate(0,0,-height/2);return geometry;
}
export const requiresExactGeometry=solid=>solid.kind==='step'||!!solid.fillet||!!solid.chamfer||!!solid.booleans?.length||(!!solid.bore&&!['box','cylinder'].includes(solid.kind));
function release(root){root.traverse(object=>{object.geometry?.dispose();for(const material of [object.material].flat().filter(Boolean)){for(const value of Object.values(material))if(value?.isTexture)value.dispose();material.dispose();}});}
function eachMaterial(root,callback){root.traverse(object=>{if(object.isMesh)for(const material of [object.material].flat())callback(material);});}

export function makeViewer(container,manifest,{glbUrl=null,glbData=null,manual=false,cad=false}={}) {
 const scene=new THREE.Scene();scene.background=new THREE.Color(manifest.brand.paper);
 const camera=new THREE.PerspectiveCamera(34,1,.1,100000);camera.up.set(0,0,1);
 const renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,preserveDrawingBuffer:true});
 renderer.setPixelRatio(manual?1:Math.min(globalThis.devicePixelRatio||1,2));renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
 renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.55;
 container.replaceChildren(renderer.domElement);
 const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=!manual;controls.minDistance=.1;controls.maxDistance=50000;
 scene.add(new THREE.HemisphereLight(0xffffff,0x898174,2.6));
 const sun=new THREE.DirectionalLight(0xfff4dd,4);sun.position.set(-250,-350,600);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);sun.shadow.camera.left=-450;sun.shadow.camera.right=450;sun.shadow.camera.top=450;sun.shadow.camera.bottom=-450;sun.shadow.bias=-.0003;scene.add(sun);
 const fill=new THREE.DirectionalLight(0xdce7ff,1.5);fill.position.set(300,250,300);scene.add(fill);
 let group=new THREE.Group();scene.add(group);let elements=[],destroyed=false,pendingFocus=[],size=100,center=new THREE.Vector3(),raf;
 const importedScene=!!manifest.scene_asset&&!cad;
 let mixer=null,animationClip=null;
 const parts=manifest.solids.filter(s=>!s.construction),needsExact=importedScene||parts.some(requiresExactGeometry);
 const state={mode:needsExact?'exact-required':'parametric-preview',exploded:false,focused:[],warnings:[]};
 const ground=new THREE.Mesh(new THREE.PlaneGeometry(30000,30000),new THREE.ShadowMaterial({opacity:.14}));ground.receiveShadow=true;scene.add(ground);
 let pendingNotice;
 if(needsExact&&!glbUrl&&!glbData){
  pendingNotice=document.createElement('div');pendingNotice.className='geometry-pending';pendingNotice.textContent='此草稿包含精確 CAD 幾何。點選「更新實體預覽」，檢視圓角、布林與匯入零件的實際形狀。';container.append(pendingNotice);
 }else if(!needsExact){
  for(const solid of parts){
   const geometry=primitiveGeometry(solid),mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:solid.color,roughness:.65,metalness:.12}));
   mesh.position.fromArray(solid.position);mesh.rotation.set(...(solid.rotation||[0,0,0]).map(THREE.MathUtils.degToRad),'XYZ');mesh.castShadow=true;mesh.receiveShadow=true;mesh.name=solid.id;mesh.userData.base=mesh.position.clone();group.add(mesh);elements.push(mesh);
   mesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry,35),new THREE.LineBasicMaterial({color:manifest.brand.ink,transparent:true,opacity:.16})));
  }
 }
 function fit(){
  const box=new THREE.Box3().setFromObject(group);center=box.isEmpty()?new THREE.Vector3():box.getCenter(new THREE.Vector3());size=box.isEmpty()?100:Math.max(1,box.getSize(new THREE.Vector3()).length());
  ground.position.z=box.isEmpty()?-.25:box.min.z-.25;controls.target.copy(center);controls.maxDistance=Math.max(50000,size*10);camera.position.copy(center).add(new THREE.Vector3(size*1.05,-size*1.5,size*.85));camera.near=Math.max(.01,size/10000);camera.far=Math.max(10000,size*100);camera.updateProjectionMatrix();controls.update();
 }
 function focus(ids=[]){pendingFocus=[...ids];state.focused=[...ids];if(importedScene)return;for(const object of elements)eachMaterial(object,material=>{material.opacity=ids.length&&!ids.includes(object.name)?.22:1;material.transparent=material.opacity<1;material.depthWrite=material.opacity===1;});}
 fit();
 function loadGLB(onLoad,onError){
  const loader=new GLTFLoader();
  if(glbData){try{loader.parse(Uint8Array.from(atob(glbData),c=>c.charCodeAt(0)).buffer,'',onLoad,onError);}catch(error){onError(error);}}
  else loader.load(glbUrl,onLoad,undefined,onError);
 }
 const ready=(glbUrl||glbData)?new Promise((resolve,reject)=>loadGLB(gltf=>{
  if(destroyed){release(gltf.scene);resolve(state);return;}
  const actual=gltf.scene;actual.rotation.x=Math.PI/2;actual.scale.setScalar(1000);actual.updateMatrixWorld(true);
  if(importedScene){
   scene.remove(group);release(group);group=actual;scene.add(group);const sceneNodes=new Map();
   actual.traverse(mesh=>{if(!mesh.isMesh)return;for(let node=mesh;node&&node!==actual;node=node.parent){const nodeId=gltf.parser.associations.get(node)?.nodes;if(nodeId!==undefined){if(!sceneNodes.has(nodeId))sceneNodes.set(nodeId,node);break;}}});
   elements=[...sceneNodes.entries()].sort((a,b)=>a[0]-b[0]).map(([id,object])=>{object.userData.studioSceneId='node-'+id;object.userData.base=object.position.clone();return object;});
   actual.traverse(object=>{if(object.isMesh){object.castShadow=true;object.receiveShadow=true;}});
   const clipIndex=manifest.scene_animation||0;
   if(clipIndex>=gltf.animations.length&&clipIndex!==0){reject(Error('選定的動畫不在此 GLB 場景中'));return;}
   if(gltf.animations.length){mixer=new THREE.AnimationMixer(actual);animationClip=gltf.animations[clipIndex];mixer.clipAction(animationClip).play();mixer.setTime(0);state.animationIndex=clipIndex;}
   state.mode='scene-glb';state.animations=gltf.animations.map(clip=>({name:clip.name,duration:clip.duration}));pendingNotice?.remove();fit();resolve(state);return;
  }
  const meshes=[];actual.traverse(object=>{if(object.isMesh)meshes.push(object);});
  const known=new Map(parts.map(part=>[part.id,part])),byId=new Map(),meshIds=new Map();
  try{
   for(const mesh of meshes){
    let id=null;
    for(let node=mesh;node&&!id;node=node.parent){const candidate=node.userData?.studio_part_id||node.userData?.part_id||node.name;if(known.has(candidate))id=candidate;}
    if(!id)throw Error(`CAD 網格缺少固定零件代號：${mesh.name||'未命名'}`);meshIds.set(mesh,id);
    if(!byId.has(id)){const partGroup=new THREE.Group();partGroup.name=id;partGroup.userData.base=new THREE.Vector3();byId.set(id,partGroup);}
   }
   if(parts.some(part=>!byId.has(part.id)))throw Error('CAD 預覽缺少母本中的零件');
   const replacement=new THREE.Group();scene.add(replacement);for(const partGroup of byId.values())replacement.add(partGroup);
   for(const mesh of meshes){
    const id=meshIds.get(mesh);
    byId.get(id).attach(mesh);for(const material of [mesh.material].flat().filter(Boolean))material.dispose();mesh.material=new THREE.MeshStandardMaterial({color:known.get(id).color,roughness:.65,metalness:.12});mesh.castShadow=true;mesh.receiveShadow=true;
   }
   scene.remove(group);release(group);group=replacement;elements=[...byId.values()];state.mode='cad-glb';pendingNotice?.remove();fit();focus(pendingFocus);resolve(state);
  }catch(error){release(actual);reject(error);}
 },reject)):Promise.resolve(state);
 const resize=()=>{const width=container.clientWidth||600,height=container.clientHeight||450;renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();};const observer=new ResizeObserver(resize);observer.observe(container);resize();
 function loop(){if(destroyed)return;raf=requestAnimationFrame(loop);controls.update();renderer.render(scene,camera);}if(!manual)loop();
 function renderFrame(mode,progress){
  if(state.mode==='exact-required')throw Error('此鏡頭需要先產生實體 CAD 預覽');
  const damping=controls.enableDamping;controls.enableDamping=false;controls.update();controls.enableDamping=damping;
  const t=Math.max(0,Math.min(1,progress)),explode=mode==='explode'?Math.sin(Math.PI*t):0;
  if(importedScene){elements.forEach(object=>object.position.copy(object.userData.base));if(mixer)mixer.setTime(Math.min(t*animationClip.duration,Math.max(0,animationClip.duration-1e-7)));}
  const ordered=importedScene?elements:[...elements].sort((a,b)=>{const pa=parts.find(part=>part.id===a.name),pb=parts.find(part=>part.id===b.name);return pa.position[2]-pb.position[2]||a.name.localeCompare(b.name);});
  if(importedScene){
   group.updateMatrixWorld(true);const targets=ordered.map((object,index)=>object.getWorldPosition(new THREE.Vector3()).add(new THREE.Vector3(0,0,index*size*.22*explode)));
   ordered.forEach((object,index)=>{object.parent.updateWorldMatrix(true,false);object.position.copy(object.parent.worldToLocal(targets[index]));object.updateWorldMatrix(false,true);});
  }else ordered.forEach((object,index)=>{object.position.copy(object.userData.base);object.position.z+=index*size*.22*explode;});
  // Fit the evaluated pose, including imported animation and exploded parts.
  // Rest-pose bounds alone crop translating meshes and tall assemblies.
  group.updateMatrixWorld(true);
  const bounds=new THREE.Box3().setFromObject(group,true);
  const target=bounds.isEmpty()?center.clone():bounds.getCenter(new THREE.Vector3());
  const frameSize=bounds.isEmpty()?size:Math.max(1,bounds.getSize(new THREE.Vector3()).length());
  const angle=-.96+(mode==='orbit'?t*Math.PI*2:0);
  const distance=Math.max(size,frameSize)*.65/(Math.tan(THREE.MathUtils.degToRad(camera.fov/2))*Math.min(1,camera.aspect));
  controls.maxDistance=Math.max(50000,distance*4,frameSize*10);
  camera.near=Math.max(.01,Math.min(size,frameSize)/10000);camera.far=Math.max(10000,frameSize*100,distance*2+frameSize);camera.updateProjectionMatrix();
  camera.position.copy(target).add(new THREE.Vector3(Math.cos(angle)*distance,Math.sin(angle)*distance,distance*.6));controls.target.copy(target);camera.lookAt(target);camera.updateMatrixWorld();renderer.render(scene,camera);
  const points=[];
  if(!bounds.isEmpty())for(const x of [bounds.min.x,bounds.max.x])for(const y of [bounds.min.y,bounds.max.y])for(const z of [bounds.min.z,bounds.max.z])points.push(new THREE.Vector3(x,y,z).project(camera).toArray());
  return {progress:t,mode,camera:camera.position.toArray(),target:target.toArray(),explode,inside:points.every(point=>Math.abs(point[0])<.98&&Math.abs(point[1])<.98&&Math.abs(point[2])<1),parts:elements.map(object=>{const box=new THREE.Box3().setFromObject(object,true),materials=[];eachMaterial(object,material=>materials.push({name:material.name,color:material.color?'#'+material.color.getHexString():null,opacity:material.opacity,texture:!!material.map}));return {id:importedScene?object.userData.studioSceneId:object.name,position:box.getCenter(new THREE.Vector3()).toArray(),size:box.getSize(new THREE.Vector3()).toArray(),color:importedScene?null:parts.find(part=>part.id===object.name).color,opacity:materials[0]?.opacity??null,materials};})};
 }
 return {state,ready,renderFrame,focus,setExploded(value){state.exploded=value;return renderFrame(value?'explode':'orbit',value?.5:0);},dispose(){destroyed=true;cancelAnimationFrame(raf);observer.disconnect();controls.dispose();mixer?.stopAllAction();release(scene);renderer.dispose();renderer.forceContextLoss();}};
}
if(typeof window!=='undefined')window.makeStudioViewer=makeViewer;
const data=typeof document!=='undefined'?document.getElementById('project-data'):null;
if(data){
 const manifest=JSON.parse(data.textContent),mount=document.getElementById('viewer'),status=document.getElementById('renderer-state');
 let animation;
 const report=message=>{if(status)status.textContent=message;};
 try{
  const viewer=makeViewer(mount,manifest,{glbData:document.getElementById('project-glb')?.textContent.trim()||null});window.studioViewer=viewer;
  report('mm · 幾何載入中');viewer.focus(manifest.beats[0]?.focus||[]);
  viewer.ready.then(()=>report(viewer.state.mode==='scene-glb'?'3D · 原始材質與動畫':viewer.state.mode==='cad-glb'?'mm · 實體 CAD 幾何':viewer.state.mode==='exact-required'?'mm · 此作品需附實體 CAD 幾何':'mm · 參數幾何預覽')).catch(error=>report('幾何載入：'+error.message));
  const explode=document.getElementById('explode');if(explode)explode.onclick=()=>viewer.setExploded(!viewer.state.exploded);
  document.querySelectorAll('[data-motion]').forEach(button=>button.onclick=async()=>{
   try{
    await viewer.ready;const beat=manifest.beats.find(beat=>beat.id===button.dataset.beat)||manifest.beats[Number(button.dataset.index)];viewer.focus(beat?.focus||[]);
    cancelAnimationFrame(animation);const started=performance.now(),mode=button.dataset.motion;
    function animate(now){viewer.renderFrame(mode,Math.min(1,(now-started)/5000));if(now-started<5000)animation=requestAnimationFrame(animate);}animation=requestAnimationFrame(animate);
   }catch(error){report('鏡頭預覽：'+error.message);}
  });
 }catch(error){mount.replaceChildren(Object.assign(document.createElement('img'),{src:'anatomy.svg',alt:manifest.title}));report('SVG · 此瀏覽器使用靜態圖解');}
 if(manifest.effect?.enabled){
  let canvas=document.getElementById('paper-effect');if(!canvas){canvas=document.createElement('canvas');canvas.id='paper-effect';canvas.setAttribute('aria-hidden','true');Object.assign(canvas.style,{position:'absolute',inset:'0',width:'100%',height:'100%',pointerEvents:'none'});mount.parentElement.style.position='relative';mount.parentElement.append(canvas);}
  paperEffect(canvas,manifest.effect).then(effect=>{window.studioEffect=effect;}).catch(error=>report('光影：'+error.message));
 }
}
