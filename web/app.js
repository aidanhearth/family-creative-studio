import {canonical,semanticOperations,resolveText as resolveTemplate,applyLocalOperations,selectionIndex,auditFindings} from './state.mjs';
import {makeViewer} from './viewer.js';
import {paperEffect} from './shader.js';
import {HistoryManager} from '../vendor/storytold--artcraft/HistoryManager.ts';
const $=id=>document.getElementById(id), clone=o=>structuredClone(o);
let session,project,draft,selected=0,solidIndex=0,viewer,view='3d',job,published,dirty=false,saving=false,effect,assets=[],recipes=[],motionRequest,formPending=false,previewGeneration=0,effectGeneration=0,formVersion=0,capturePromise=null,previewGeometry=null;
const history=new HistoryManager({onChange:({canUndo,canRedo})=>{$('undo').disabled=!canUndo;$('redo').disabled=!canRedo;}});
function friendly(message){const match=Object.values(session?.copy.ui?.friendlyErrors||{}).find(e=>message.includes(e.match));return match?match.title+'。'+match.message:message;}
function notice(message=''){ $('notice').textContent=friendly(message); }
async function api(path,{method='GET',body,raw=false}={}){
 const response=await fetch(path,{method,headers:{'X-Studio-Token':session?.token||'',...(raw?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:raw?body:JSON.stringify(body)});
 const result=await response.json();if(!response.ok)throw Error(typeof result.error==='string'?result.error:JSON.stringify(result.detail||result));return result;
}
function resolveText(text){return resolveTemplate(text,draft.solids);}
function updateDirty(){
 $('draft-status').textContent=dirty||formPending?'尚未儲存的修改':'尺寸母本已儲存';
 $('revision').textContent=`v${project.revision}${dirty||formPending?' · 草稿':''}`;$('undo').disabled=!formPending&&!history.canUndo();$('redo').disabled=formPending||!history.canRedo();
}
function apply(next,selection={beat:draft?.beats[selected]?.id,solid:draft?.solids[solidIndex]?.id}){
 draft=clone(next);selected=selectionIndex(selection.beat,draft.beats,selected);solidIndex=selectionIndex(selection.solid,draft.solids,solidIndex);
 dirty=canonical(draft)!==canonical(project.manifest);formPending=false;renderProject();
}
function edit(next,label,selection){
 if(canonical(next)===canonical(draft)){formPending=false;updateDirty();return;}
 const before=clone(draft),oldSelection={beat:draft.beats[selected]?.id,solid:draft.solids[solidIndex]?.id};
 apply(next,selection||oldSelection);const after=clone(draft),newSelection={beat:draft.beats[selected]?.id,solid:draft.solids[solidIndex]?.id};
 history.record({label,apply:()=>apply(after,newSelection),revert:()=>apply(before,oldSelection)});
}
function updateExpressionPreview(){
 const solids=clone(draft.solids),solid=solids[solidIndex];
 if(solid){solid.size=[0,1,2].map(i=>Number($('dim-'+i).value));solid.bore=Number($('bore').value);}
 $('body-preview').textContent=resolveTemplate($('beat-body').value,solids);
 $('narration-preview').textContent=resolveTemplate($('beat-narration').value,solids);
}
function applySceneSelection(next,asset,{selecting=false}={}){
 const changed=next.scene_asset!==asset;
 next.scene_asset=asset;
 if(changed)next.scene_animation=0;
 if(asset){
  for(const beat of next.beats)beat.focus=[];
  if(changed||selecting){
   for(const beat of next.beats)if(beat.visual.mode==='diagram'&&!beat.svg_asset)beat.visual={...beat.visual,mode:'orbit'};
   next.output_targets=next.output_targets.filter(target=>target!=='cad');
   if(!next.output_targets.length)next.output_targets=['web'];
  }
 }else if(changed){
  const count=next.solids.filter(solid=>!solid.construction).length;
  for(const beat of next.beats){
   if(!count&&['orbit','explode'].includes(beat.visual.mode))beat.visual={...beat.visual,mode:'diagram'};
   else if(count===1&&beat.visual.mode==='explode')beat.visual={...beat.visual,mode:'orbit'};
  }
 }
 return next;
}
function renderSceneAnimations(asset,selectedAnimation=0){
 const select=$('scene-animation'),animations=assets.find(item=>item.asset===asset)?.animations||[];
 select.dataset.sceneAsset=asset||'';select.disabled=!animations.length;
 select.replaceChildren(...(animations.length?animations.map(animation=>new Option(`${animation.name||`動畫 ${animation.index+1}`} · ${Number(animation.duration_s).toFixed(1)} 秒`,String(animation.index),false,animation.index===selectedAnimation)):[new Option('無動畫','0')]));
}
function validateDimensions(){
 for(const index of [0,1,2]){
  const input=$('dim-'+index);
  input.setCustomValidity(input.value!==''&&Number(input.value)>0?'':'尺寸必須大於 0 mm');
 }
}
function readForm(){
 const next=clone(draft),beat=next.beats[selected],solid=next.solids[solidIndex];
 applySceneSelection(next,$('imported-scene').value||null);
 next.scene_animation=next.scene_asset&&$('scene-animation').dataset.sceneAsset===next.scene_asset?Number($('scene-animation').value||0):0;
 next.title=$('title').value;next.subtitle=$('subtitle').value;
 Object.assign(beat,{title:$('beat-title').value,body:$('beat-body').value,narration:$('beat-narration').value,duration:Number($('duration').value),
  focus:next.scene_asset?[]:[...document.querySelectorAll('[data-focus]:checked')].map(input=>input.dataset.focus),layout:$('beat-layout').value||null,narration_asset:$('beat-audio-asset').value||null});
 if(solid){
  Object.assign(solid,{size:[0,1,2].map(i=>Number($('dim-'+i).value)),bore:Number($('bore').value),position:[0,1,2].map(i=>Number($('pos-'+i).value)),
   rotation:[0,1,2].map(i=>Number($('rot-'+i).value)),kind:$('solid-kind').value,name:$('solid-name').value,color:$('solid-color').value,
   fillet:Number($('fillet').value),chamfer:Number($('chamfer').value),top_diameter:$('solid-kind').value==='cone'?Number($('top-diameter').value):0,construction:$('construction').checked,
   profile:$('solid-kind').value==='extrusion'?JSON.parse($('solid-profile').value||'[]'):[],booleans:$('solid-booleans').value.trim()?JSON.parse($('solid-booleans').value):[]});
 }
 if(solid&&solid.kind!=='step')solid.asset=null;
 const selectedMode=$('visual-mode').value;const sceneChanged=next.scene_asset!==draft.scene_asset;
 const count=next.solids.filter(solid=>!solid.construction).length;
 const mode=sceneChanged&&next.scene_asset&&selectedMode==='diagram'&&!beat.svg_asset?'orbit':sceneChanged&&!next.scene_asset&&count===0&&['orbit','explode'].includes(selectedMode)?'diagram':sceneChanged&&!next.scene_asset&&count===1&&selectedMode==='explode'?'orbit':selectedMode;beat.svg_asset=mode==='diagram'?$('beat-svg-asset').value||null:null;
 beat.visual={...beat.visual,mode,asset:['image','clip'].includes(mode)?$('scene-asset').value||null:null,start:mode==='clip'?Number($('trim-start').value):0,audio:$('scene-audio').value,voice_gain:Number($('voice-gain').value),source_gain:Number($('source-gain').value)};
 next.video={resolution:$('video-resolution').value,fps:$('video-fps').value==='source'?'source':Number($('video-fps').value),crf:Number($('video-crf').value),captions:$('video-captions').checked,normalize_audio:$('video-normalize').checked};
 next.slides={layout:$('slides-layout').value,narration:$('slides-narration').checked,autoplay:$('slides-autoplay').checked,transition:$('slides-transition').value,animation:$('slides-animation').value};
 next.diagram=$('diagram-kind').value?{kind:$('diagram-kind').value,document:JSON.parse($('diagram-document').value||'{}')}:null;
 next.effect={enabled:$('fx').checked,type:$('effect-type').value,color:$('effect-color').value,secondary:$('effect-secondary').value,radius:Number($('effect-radius').value),softness:Number($('effect-softness').value),angle:Number($('effect-angle').value),opacity:Number($('effect-opacity').value)};
 return next;
}
async function captureForm(){
 if(capturePromise)return capturePromise;
 capturePromise=(async()=>{
  while(formPending){
   const version=formVersion,next=readForm(),validated=await api('/api/validate',{method:'POST',body:next});
   if(version!==formVersion)continue;
   edit(validated,'Edit draft');
  }
 })();
 try{await capturePromise;}finally{capturePromise=null;}
}
async function renderEffect(){
 const generation=++effectGeneration;effect?.destroy();effect=null;
 const settings=draft.effect||{};
 if(!settings.enabled){$('fx-status').textContent='';return;}
 const rendered=await paperEffect($('paper-effect'),settings);
 if(generation!==effectGeneration){rendered.destroy();return;}
 effect=rendered;$('fx-status').textContent=effect.state==='active'?'WebGPU':effect.state==='disabled'?'':'靜態效果 · WebGPU 未就緒';
}
function showShapeFields(){
 $('cone-settings').hidden=$('solid-kind').value!=='cone';$('profile-settings').hidden=$('solid-kind').value!=='extrusion';
}
function renderProject(){
 const b=draft.beats[selected],s=draft.solids[solidIndex];
 document.documentElement.style.setProperty('--paper',draft.brand.paper);document.documentElement.style.setProperty('--ink',draft.brand.ink);document.documentElement.style.setProperty('--accent',draft.brand.accent);document.documentElement.style.setProperty('--muted',draft.brand.muted);
 $('project-name').textContent=resolveText(draft.title);$('title').value=draft.title;$('subtitle').value=draft.subtitle;$('beat-heading').textContent=resolveText(b.title);$('beat-title').value=b.title;$('beat-body').value=b.body;$('beat-narration').value=b.narration;$('caption-text').textContent=resolveText(b.narration);
 $('beats').replaceChildren(...draft.beats.map((beat,i)=>{const button=document.createElement('button');button.className=i===selected?'active':'';const number=document.createElement('span');number.textContent=String(i+1).padStart(2,'0');button.append(number,document.createTextNode(beat.title));button.onclick=async()=>{try{await captureForm();selected=i;renderProject();}catch(error){notice(error.message);}};return button;}));
 $('solid').replaceChildren(...draft.solids.map((s,i)=>new Option(s.name,String(i),false,i===solidIndex)));
 for(const id of ['solid-name','solid-kind','solid-color','bore','fillet','chamfer','top-diameter','solid-profile','solid-booleans','construction',...['dim-','pos-','rot-'].flatMap(p=>[0,1,2].map(i=>p+i))])$(id).disabled=!s;
 if(s){s.size.forEach((n,i)=>$('dim-'+i).value=n);$('bore').value=s.bore||0;s.position.forEach((n,i)=>$('pos-'+i).value=n);$('solid-name').value=s.name;$('solid-kind').value=s.kind;(s.rotation||[0,0,0]).forEach((n,i)=>$('rot-'+i).value=n);$('solid-color').value=s.color;$('fillet').value=s.fillet||0;$('chamfer').value=s.chamfer||0;$('top-diameter').value=s.top_diameter||0;$('solid-profile').value=JSON.stringify(s.profile||[]);$('solid-booleans').value=JSON.stringify(s.booleans||[]);$('construction').checked=!!s.construction;}showShapeFields();validateDimensions();
 $('duration').value=b.duration;$('visual-mode').value=b.visual.mode;$('trim-start').value=b.visual.start;$('scene-audio').value=b.visual.audio;$('voice-gain').value=b.visual.voice_gain??1;$('source-gain').value=b.visual.source_gain??1;$('beat-layout').value=b.layout||'';
 $('scene-asset').replaceChildren(new Option('尚未選取素材',''),...assets.filter(a=>a.kind==='image'||a.kind==='clip').map(a=>new Option(`${a.label?.slice(0,25)||a.asset.slice(0,8)} · ${a.duration_s?.toFixed(1)||a.width+'×'+a.height}${a.duration_s?' 秒':''}`,a.asset,false,a.asset===b.visual.asset)));
 $('image-style').value=draft.style_id||'';
 $('source-scope').textContent=draft.scene_asset?'運鏡與互動舞台使用匯入 GLB；參數圖解、尺寸表與 CAD 檔使用保留的 CAD 零件。原生 SVG 章節沿用原圖。':'參數預覽、圖解與 CAD 檔共用目前 CAD 零件；原生 SVG 章節沿用匯入原圖。';
 $('scene-import-state').textContent=draft.scene_asset?'目前的運鏡與互動舞台使用 GLB 場景。CAD 零件仍保留；需要它們的 STEP／STL／GLB 時可另勾 CAD 輸出。':'目前使用參數 CAD 零件。選用 GLB 會保留零件並預設關閉 CAD 輸出。';
 $('imported-scene').replaceChildren(new Option('使用參數 CAD 零件',''),...assets.filter(a=>a.asset.endsWith('.glb')).map(a=>new Option(a.label||a.asset.slice(0,12),a.asset,false,a.asset===draft.scene_asset)));
 renderSceneAnimations(draft.scene_asset,draft.scene_animation||0);
 $('beat-focus').closest('fieldset').hidden=!!draft.scene_asset;
 $('beat-svg-asset').replaceChildren(new Option('使用產生的圖解',''),...assets.filter(a=>a.asset.endsWith('.svg')).map(a=>new Option(a.label||a.asset.slice(0,12),a.asset,false,a.asset===b.svg_asset)));
 $('beat-audio-asset').replaceChildren(new Option('沿用整體旁白／草稿配音',''),...assets.filter(a=>a.asset.endsWith('.wav')).map(a=>new Option(a.label||a.asset.slice(0,12),a.asset,false,a.asset===b.narration_asset)));
 $('beat-focus').replaceChildren(...draft.solids.filter(s=>!s.construction).map(s=>{const label=document.createElement('label');label.className='check';const input=document.createElement('input');input.type='checkbox';input.dataset.focus=s.id;input.checked=b.focus.includes(s.id);label.append(input,document.createTextNode(s.name));return label;}));
 $('solid-up').disabled=!s||solidIndex===0;$('solid-down').disabled=!s||solidIndex===draft.solids.length-1;
 const v=draft.video||{resolution:'source',fps:'source',crf:18,captions:true,normalize_audio:true},ppt=draft.slides||{layout:'editorial',narration:true,autoplay:true,transition:'fade',animation:'none'},fx=draft.effect||{enabled:false,type:'Circle',color:'#d8cbb8',secondary:'#F6F4EF',radius:.4,softness:.1,angle:0,opacity:.35};
 for(const name of ['resolution','fps','crf'])$('video-'+name).value=v[name];$('video-captions').checked=v.captions;$('video-normalize').checked=v.normalize_audio;
 for(const name of ['layout','transition','animation'])$('slides-'+name).value=ppt[name];for(const name of ['narration','autoplay'])$('slides-'+name).checked=ppt[name];
 $('diagram-kind').value=draft.diagram?.kind||'';$('diagram-document').value=JSON.stringify(draft.diagram?.document||{},null,2);
 $('fx').checked=fx.enabled;for(const name of ['type','color','secondary','radius','softness','angle','opacity'])$('effect-'+name).value=fx[name];
 updateExpressionPreview();renderEffect().catch(e=>notice(e.message));
 $('remove-beat').disabled=draft.beats.length===1;$('beat-up').disabled=selected===0;$('beat-down').disabled=selected===draft.beats.length-1;$('remove-solid').disabled=!s;
 $('json-editor').value=JSON.stringify(draft,null,2);$('audio-state').textContent=draft.narration_asset?'已選取正式旁白':'eSpeak NG · 本機草稿配音';
 for(const input of document.querySelectorAll('[data-target]')){input.checked=draft.output_targets.includes(input.dataset.target);input.disabled=input.dataset.target==='cad'&&!draft.solids.length;}
 updateDirty();const generation=++previewGeneration;cancelAnimationFrame(motionRequest);viewer?.dispose();viewer=null;
 if(b.svg_asset){$('viewer').replaceChildren(Object.assign(document.createElement('img'),{src:'/api/assets/'+b.svg_asset,alt:resolveText(b.title)}));}
 else if(b.visual.asset){const el=document.createElement(b.visual.mode==='clip'?'video':'img');el.src='/api/assets/'+b.visual.asset;if(el.tagName==='VIDEO'){el.controls=true;el.onloadedmetadata=()=>{el.currentTime=b.visual.start;};}else el.alt=resolveText(b.title);$('viewer').replaceChildren(el);}
 else if(draft.solids.length||draft.scene_asset){try{const glbUrl=draft.scene_asset?'/api/assets/'+draft.scene_asset:previewGeometry?.signature===canonical(draft.solids)?previewGeometry.url:!dirty&&!formPending&&published?.revision===project.revision&&published.artifacts.some(a=>a.path==='model.glb')?artifact('model.glb'):null;viewer=makeViewer($('viewer'),draft,{glbUrl});viewer.focus(b.focus);const activeViewer=viewer;activeViewer.ready.then(()=>{if(generation!==previewGeneration)return;activeViewer.focus(b.focus);if(b.visual.mode!=='diagram'&&activeViewer.state.mode!=='exact-required')activeViewer.renderFrame(b.visual.mode,.15);$('stage-label').textContent=activeViewer.state.mode==='scene-glb'?'3D · 原始材質與動畫':activeViewer.state.mode==='cad-glb'?'CAD · mm':activeViewer.state.mode==='exact-required'?'實體 CAD · 請更新預覽':'PARAMETRIC · mm';}).catch(error=>{if(generation===previewGeneration)notice('幾何預覽：'+error.message);});}catch(error){notice('3D 預覽：'+error.message);}}
 else{$('viewer').textContent=resolveText(b.body);}
 renderPreview();
}
async function save(){
 if(saving)throw Error('儲存進行中，請稍候。');
 saving=true;$('save').disabled=true;
 try{
  await captureForm();if(!dirty)return project;const sent=clone(draft);
  const saved=await api(`/api/projects/${project.id}/patch`,{method:'POST',body:{operations:semanticOperations(project.manifest,sent),expected_revision:project.revision}});
  project=saved;dirty=canonical(draft)!==canonical(saved.manifest);updateDirty();await listProjects();notice();return saved;
 }finally{saving=false;$('save').disabled=false;}
}
function artifact(path){return `/artifacts/${published.id}/${path.split('/').map(encodeURIComponent).join('/')}`;}
function renderPreview(){
 document.querySelector('.stage-meta').hidden=view==='video'||(view==='3d'&&!!(draft.beats[selected].visual.asset||draft.beats[selected].svg_asset));
 $('viewer').hidden=view!=='3d';$('preview').hidden=view==='3d';$('explode').hidden=view!=='3d';$('paper-effect').hidden=view!=='3d';$('geometry-refresh').hidden=view!=='3d'||!draft.solids.length||!!draft.beats[selected].visual.asset||!!draft.beats[selected].svg_asset;
 for(const tab of document.querySelectorAll('[data-view]')){tab.classList.toggle('active',tab.dataset.view===view);tab.setAttribute('aria-selected',String(tab.dataset.view===view));}
 if(view==='3d'){$('stage-label').textContent=viewer?.state.mode==='scene-glb'?'3D · 原始材質與動畫':viewer?.state.mode==='cad-glb'?'CAD · mm':viewer?.state.mode==='exact-required'?'實體 CAD · 請更新預覽':'PARAMETRIC · mm';return;}
 const mount=$('preview');mount.replaceChildren();
 if(!published){const p=document.createElement('p');p.textContent='同步更新五種輸出後，即可預覽作品。';mount.append(p);return;}
 const path={diagram:'anatomy.svg',web:'index.html',slides:`slides/${String(selected).padStart(2,'0')}.png`,video:'film.mp4'}[view];
 if(!published.artifacts.some(a=>a.path===path)){mount.textContent='這個版本未選擇此輸出格式。';return;}
 let element;
 if(view==='web'){element=document.createElement('iframe');element.title='互動專題預覽';element.setAttribute('sandbox','allow-scripts');}
 else if(view==='video'){element=document.createElement('video');element.controls=true;element.preload='metadata';}
 else{element=document.createElement('img');element.alt=draft.title+' · '+view;}
 element.src=artifact(path);mount.append(element);
 $('stage-label').textContent=`OUTPUT v${published.revision}${published.revision!==project.revision||dirty?' · 較早版本':''}`;
}
const outputs=[['project.zip','完整作品包','ZIP'],['index.html','暖紙互動專題','HTML'],['scene.glb','匯入的原始 3D 場景','GLB'],['model.glb','CAD 零件網格','GLB'],['model.step','實體幾何','STEP'],['model.stl','網格幾何','STL'],['anatomy.svg','圖解','SVG'],['workflow.html','敘事流程','ARCHIFY'],['presentation.pptx','可編輯簡報','PPTX'],['film.mp4','敘事短片','MP4'],['captions.srt','字幕','SRT'],['image-prompt.txt','影像創作提示詞','TXT']];
async function refreshJobs(){
 if(!project)return;
 const requested=project.id;const jobs=await api('/api/jobs?project_id='+encodeURIComponent(requested));if(project.id!==requested)return;job=jobs[0];const done=jobs.find(j=>j.state==='succeeded');
 const changed=done?.id!==published?.id;published=done;
 $('job-state').textContent=job?`${session.copy.ui?.status[job.state]||job.state} · v${job.revision} · ${session.copy.ui?.stage[job.stage]||job.stage}${job.error?' · '+friendly(job.error):''}`:'尚未輸出作品';
 $('cancel').hidden=!job||!['queued','running'].includes(job.state);$('retry').hidden=!job||!['failed','interrupted','cancelled'].includes(job.state);
 $('render').disabled=!!job&&['queued','running'].includes(job.state);
 if(changed&&published){
  $('artifact-list').replaceChildren(...outputs.filter(([path])=>published.artifacts.some(a=>a.path===path)).map(([path,label,format])=>{const a=document.createElement('a');a.className='artifact';a.href=artifact(path);a.target='_blank';a.rel='noopener';if(!path.endsWith('.html'))a.download=path;const arrow=document.createElement('b');arrow.textContent='↗';const small=document.createElement('span');const record=published.artifacts.find(a=>a.path===path);small.textContent=`${format} · ${record.bytes<1024?record.bytes+' B':(record.bytes/1024).toFixed(0)+' KB'} · v${published.revision}`;a.append(arrow,document.createTextNode(label),small);return a;}));
  const stages=published.artifacts.some(a=>a.path==='build-stages.json')?await(await fetch(artifact('build-stages.json'))).json():null;$('reuse-state').textContent=stages?.stages.some(s=>s.stage==='cad'&&s.reused)?session.upgrade.actions.reuseCadNotice:'';const completedId=published.id;const quality=await (await fetch(artifact('quality.json'))).json();if(project.id!==requested||published?.id!==completedId)return;$('quality').replaceChildren(...quality.checks.map(c=>{const p=document.createElement('div');p.className='quality-row';const mark=document.createElement('span');mark.textContent=c.pass?'✓':'·';p.append(mark,document.createTextNode(session.copy.ui?.qualityChecks[c.check]||c.check));return p;}));if(!dirty&&!formPending&&view==='3d')renderProject();else renderPreview();
 }
}
$('editor').onsubmit=async e=>{e.preventDefault();try{formPending=true;formVersion++;await captureForm();notice();}catch(e){notice(e.message);}};
$('solid').onchange=async()=>{const index=Number($('solid').value);try{await captureForm();solidIndex=index;renderProject();}catch(e){notice(e.message);}};
$('imported-scene').onchange=()=>{const asset=$('imported-scene').value||null;if((asset||'')!==$('scene-animation').dataset.sceneAsset)renderSceneAnimations(asset,0);};
for(const container of [$('editor'),$('video-settings'),$('slides-settings'),$('effect-settings'),$('diagram-settings'),$('scene-import-settings')])container.addEventListener('input',event=>{
 if(event.target.type==='file'||event.target.id==='solid')return;
 formPending=true;formVersion++;if(event.target.id==='solid-kind'){const kind=$('solid-kind').value,width=Number($('dim-0').value);if(['sphere','cylinder','cone','torus'].includes(kind))$('dim-1').value=width;if(kind==='sphere')$('dim-2').value=width;if(kind==='torus'&&Number($('dim-2').value)>=width/2)$('dim-2').value=width/4;if(kind==='extrusion'&&['','[]'].includes($('solid-profile').value))$('solid-profile').value='[[-0.5,-0.5],[0.5,-0.5],[0.5,0.5],[-0.5,0.5]]';showShapeFields();}validateDimensions();updateDirty();updateExpressionPreview();
});
$('preset').onchange=async()=>{await captureForm();const p=session.copy.presets.find(p=>p.id===$('preset').value);const next=clone(draft);Object.assign(next.brand,{name:p.name,paper:p.colors.canvasBg,ink:p.colors.textPrimary,accent:p.colors.accentPrimary,muted:p.colors.textSecondary});edit(next,'Brand preset');};
$('save').onclick=()=>save().catch(e=>notice(e.message));
$('render').onclick=async()=>{try{await save();if(dirty||formPending)throw Error('儲存期間內容已變更，請再次儲存。');await api(`/api/projects/${project.id}/render`,{method:'POST',body:{targets:draft.output_targets,expected_revision:project.revision}});await refreshJobs();notice();}catch(e){notice(e.message);}};
$('undo').onclick=async()=>{try{await captureForm();await history.undo();}catch(e){notice(e.message);}};$('redo').onclick=()=>history.redo().catch(e=>notice(e.message));
$('apply-json').onclick=async()=>{try{const next=JSON.parse($('json-editor').value);if(next.id!==draft.id)throw Error('此處編輯保留同一個專案 ID');edit(await api('/api/validate',{method:'POST',body:next}),'JSON edit');}catch(e){notice(e.message);}};
$('explode').onclick=()=>viewer?.setExploded(!viewer.state.exploded);
for(const tab of document.querySelectorAll('[data-view]'))tab.onclick=()=>{view=tab.dataset.view;renderPreview();};
$('cancel').onclick=async()=>{try{await api(`/api/jobs/${job.id}/cancel`,{method:'POST',body:{}});await refreshJobs();}catch(e){notice(e.message);}};
$('retry').onclick=async()=>{try{await api(`/api/jobs/${job.id}/retry`,{method:'POST',body:{}});await refreshJobs();}catch(e){notice(e.message);}};
$('audio').onchange=async()=>{try{await captureForm();const file=$('audio').files[0];if(!file)return;const result=await api('/api/audio',{method:'POST',body:await file.arrayBuffer(),raw:true});assets=await api('/api/assets');const next=clone(draft);next.narration_asset=result.asset;edit(next,'Narration import');notice(`已匯入 ${result.duration_s.toFixed(1)} 秒旁白。`);}catch(e){notice(e.message);}};
$('fx').onchange=async()=>{try{formPending=true;formVersion++;await captureForm();}catch(e){notice(e.message);}};
$('audit').onclick=async()=>{
 try{
  $('audit').disabled=true;
  if(!window.impeccableDetectFromSnapshot){await new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='/static/impeccable.js';script.onload=resolve;script.onerror=()=>reject(Error('巡檢程式載入失敗'));document.head.append(script);});}
  const result=await window.impeccableDetectFromSnapshot({}),findings=auditFindings(result);window.lastStudioAudit=result;
  const summary=document.createElement('p');summary.textContent=`${findings.length} 項視覺建議 · 點選項目可定位畫面元素`;
  const list=document.createElement('ol');
  for(const finding of findings){
   const item=document.createElement('li'),button=document.createElement('button'),detail=document.createElement('p');button.className='quiet';
   button.textContent=`${finding.severity||'建議'} · ${finding.name||finding.type}`;detail.textContent=finding.detail||finding.description||'';
   button.onclick=()=>{document.querySelectorAll('.audit-highlight').forEach(el=>el.classList.remove('audit-highlight'));try{const target=document.querySelector(finding.selector);if(!target){notice('該元素已變更，請重新巡檢。');return;}for(let parent=target.parentElement;parent;parent=parent.parentElement)if(parent.tagName==='DETAILS')parent.open=true;target.classList.add('audit-highlight');target.scrollIntoView({block:'center',behavior:'smooth'});setTimeout(()=>target.classList.remove('audit-highlight'),6000);}catch(error){notice('巡檢定位：'+error.message);}};
   item.append(button,detail);list.append(item);
  }
  $('audit-result').replaceChildren(summary,list);
 }catch(e){notice('視覺巡檢：'+e.message);}finally{$('audit').disabled=false;}
};
$('beat-audio').onchange=async()=>{try{await captureForm();const file=$('beat-audio').files[0];if(!file)return;const result=await api('/api/audio',{method:'POST',body:await file.arrayBuffer(),raw:true});assets=await api('/api/assets');const next=clone(draft);next.beats[selected].narration_asset=result.asset;edit(next,'Chapter narration');notice(`本章旁白已匯入 · ${result.duration_s.toFixed(1)} 秒`);}catch(error){notice(error.message);}};
$('scene-import').onchange=async()=>{try{await captureForm();const file=$('scene-import').files[0];if(!file)return;$('scene-import-state').textContent='檢查完整 GLB 場景…';const result=await api('/api/scene?name='+encodeURIComponent(file.name),{method:'POST',body:file,raw:true});assets=await api('/api/assets');const next=applySceneSelection(clone(draft),result.asset,{selecting:true});edit(await api('/api/validate',{method:'POST',body:next}),'Import 3D scene');$('scene-import-state').textContent='GLB 場景已套用；預設關閉 CAD 輸出，原 CAD 零件保留供切回或另行輸出。';}catch(error){notice(error.message);}finally{$('scene-import').value='';}};
$('beat-svg-asset').onchange=()=>{if($('beat-svg-asset').value){$('visual-mode').value='diagram';$('scene-asset').value='';if(['source','mix'].includes($('scene-audio').value))$('scene-audio').value=$('beat-narration').value.trim()?'voice':'silent';}formPending=true;formVersion++;updateDirty();};
$('svg-import').onchange=async()=>{try{await captureForm();const file=$('svg-import').files[0];if(!file)return;const result=await api('/api/svg?name='+encodeURIComponent(file.name),{method:'POST',body:file,raw:true});assets=await api('/api/assets');const next=clone(draft),beat=next.beats[selected];beat.svg_asset=result.asset;beat.visual={...beat.visual,mode:'diagram',asset:null,start:0,audio:['source','mix'].includes(beat.visual.audio)?(beat.narration.trim()?'voice':'silent'):beat.visual.audio};edit(await api('/api/validate',{method:'POST',body:next}),'Import editable SVG');notice('原生 SVG 已套用至本章草稿。');}catch(error){notice(error.message);}finally{$('svg-import').value='';}};
$('cad-import').onchange=async()=>{try{await captureForm();const file=$('cad-import').files[0];if(!file)return;$('cad-state').textContent='檢查 STEP 實體幾何…';const result=await api('/api/cad?name='+encodeURIComponent(file.name),{method:'POST',body:file,raw:true});const part={id:'part-'+Date.now().toString(36),name:file.name.slice(0,190),kind:'step',asset:result.asset,size:result.size_mm||result.size,position:[0,0,0],color:'#B37B52'};await localPatch([{op:'add',target:'solid',values:part}],'Import CAD');$('cad-state').textContent='STEP 原始尺寸已保留';}catch(error){$('cad-state').textContent='';notice(error.message);}finally{$('cad-import').value='';}};
async function listProjects(){const items=await api('/api/projects');$('projects').replaceChildren(...items.map(p=>new Option(p.title,p.id,false,p.id===project?.id)));}
async function openProject(id){project=await api('/api/projects/'+encodeURIComponent(id));draft=clone(project.manifest);selected=0;solidIndex=0;dirty=false;formPending=false;previewGeometry=null;job=null;published=null;$('artifact-list').replaceChildren();$('quality').replaceChildren();history.clear();renderProject();await listProjects();await refreshJobs();}
$('projects').onchange=async()=>{try{if(dirty||formPending||saving){$('projects').value=project.id;throw Error('請先儲存目前的修改，再切換作品。');}await openProject($('projects').value);}catch(e){notice(e.message);}};
$('new-project').onclick=()=>{if(dirty||formPending||saving){notice('請先儲存目前的修改，再建立作品。');return;}$('create-id').value='project-'+Date.now().toString(36);$('recipe').onchange();$('create-dialog').showModal();};
$('close-create').onclick=()=>$('create-dialog').close();
$('recipe').onchange=()=>{const r=recipes.find(r=>r.id===$('recipe').value);$('recipe-description').textContent=r.description;$('create-title').value=r.defaultTitle;};
$('create-form').onsubmit=async e=>{e.preventDefault();try{const p=await api('/api/create',{method:'POST',body:{recipe_id:$('recipe').value,project_id:$('create-id').value,title:$('create-title').value}});$('create-dialog').close();await openProject(p.id);}catch(e){notice(e.message);}};
async function localPatch(operations,label){await captureForm();const result=await api('/api/validate',{method:'POST',body:applyLocalOperations(draft,operations)});const added=operations.find(o=>o.op==='add');edit(result,label,added?{beat:added.target==='beat'?added.values.id:draft.beats[selected]?.id,solid:added.target==='solid'?added.values.id:draft.solids[solidIndex]?.id}:undefined);}
function action(id,run){$(id).onclick=async()=>{try{await captureForm();await run();notice();}catch(e){notice(e.message);}};}
action('add-solid',()=>localPatch([{op:'add',target:'solid',values:{id:'part-'+Date.now().toString(36),name:'新增零件',kind:'box',size:[40,40,20],position:[0,0,10]}}],'Add part'));
action('remove-solid',()=>{const ops=[{op:'remove',target:'solid',id:draft.solids[solidIndex].id}];if(draft.solids.length===1){ops.push({op:'set',target:'project',values:{output_targets:draft.output_targets.filter(t=>t!=='cad').length?draft.output_targets.filter(t=>t!=='cad'):['web']}});for(const b of draft.beats)if(['orbit','explode'].includes(b.visual.mode))ops.push({op:'set',target:'beat',id:b.id,values:{visual:{...b.visual,mode:'diagram'}}});}if(draft.solids.length===2)for(const b of draft.beats)if(b.visual.mode==='explode')ops.push({op:'set',target:'beat',id:b.id,values:{visual:{...b.visual,mode:'orbit'}}});return localPatch(ops,'Remove part');});
action('add-beat',()=>localPatch([{op:'add',target:'beat',values:{...draft.beats[selected],id:'chapter-'+Date.now().toString(36),title:'新增章節'}}],'Add chapter'));
action('remove-beat',()=>localPatch([{op:'remove',target:'beat',id:draft.beats[selected].id}],'Remove chapter'));
for(const [id,direction] of [['beat-up',-1],['beat-down',1]])action(id,()=>localPatch([{op:'move',target:'beat',id:draft.beats[selected].id,index:selected+direction}],'Move chapter'));
for(const [id,direction] of [['solid-up',-1],['solid-down',1]])action(id,()=>localPatch([{op:'move',target:'solid',id:draft.solids[solidIndex].id,index:solidIndex+direction}],'Move part'));
$('media').onchange=async()=>{const file=$('media').files[0];if(!file)return;try{await captureForm();if(file.size>512*1024*1024)throw Error(session.upgrade.errors.mediaFormatUnsupported);$('media-state').textContent='保留原檔並檢查素材…';const result=await api('/api/media?name='+encodeURIComponent(file.name),{method:'POST',body:file,raw:true});assets=await api('/api/assets');const next=clone(draft),b=next.beats[selected];b.svg_asset=null;b.visual={mode:result.kind,asset:result.asset,start:0,audio:result.kind==='clip'&&result.audio?'source':'voice'};if(result.kind==='clip'){if(result.duration_s<.1)throw Error('影片需至少 0.1 秒。');b.duration=Math.min(b.duration,result.duration_s);}edit(await api('/api/validate',{method:'POST',body:next}),'Import scene media');$('media-state').textContent='素材已匯入 · '+(result.bytes/1024/1024).toFixed(1)+' MiB';notice();}catch(e){$('media-state').textContent='素材未套用';notice(e.message);}finally{$('media').value='';}};
action('compare',async()=>{if(project.revision<2)throw Error(session.upgrade.emptyStates.noRevisionDiff);const result=await api(`/api/projects/${project.id}/compare?before=${project.revision-1}`);$('comparison').hidden=false;$('comparison').textContent=`v${result.before} → v${result.after}\n`+result.changes.map(c=>`${c.path}\n${JSON.stringify(c.before)} → ${JSON.stringify(c.after)}`).join('\n\n');});
for(const input of document.querySelectorAll('[data-target]'))input.onchange=async()=>{try{const targets=[...document.querySelectorAll('[data-target]:checked')].map(i=>i.dataset.target);await captureForm();const next=clone(draft);next.output_targets=targets;edit(await api('/api/validate',{method:'POST',body:next}),'Output formats');}catch(e){notice(e.message);renderProject();}};
$('geometry-refresh').onclick=async()=>{
 try{await captureForm();$('geometry-refresh').disabled=true;const snapshot=canonical(draft),generation=previewGeneration;notice('正在建立實體 CAD 預覽…');const result=await api('/api/geometry/preview',{method:'POST',body:{manifest:draft}});if(snapshot!==canonical(draft)||generation!==previewGeneration){notice('草稿已變更，請再更新目前的幾何預覽。');return;}previewGeometry={signature:canonical(draft.solids),url:result.url};viewer?.dispose();viewer=makeViewer($('viewer'),draft,{glbUrl:result.url,cad:true});const current=viewer;await current.ready;if(snapshot!==canonical(draft)||current!==viewer)return;viewer.focus(draft.beats[selected].focus);$('stage-label').textContent='CAD · mm';notice();}catch(error){notice(error.message);}finally{$('geometry-refresh').disabled=false;}
};
$('export-timeline').onclick=async()=>{try{await captureForm();if(dirty)throw Error('請先按儲存，再下載此版本的時間軸。');const result=await api(`/api/projects/${project.id}/timeline`),blob=new Blob([JSON.stringify(result,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=project.id+'-timeline.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(error){notice(error.message);}};
$('import-timeline').onchange=async()=>{try{await captureForm();if(dirty)throw Error('請先儲存目前草稿，再匯入時間軸。');const file=$('import-timeline').files[0];if(!file)return;if(file.size>16*1024*1024)throw Error('時間軸 JSON 上限 16 MiB');const document=JSON.parse(await file.text()),result=await api(`/api/projects/${project.id}/timeline`,{method:'PUT',body:{timeline:document.timeline||document,expected_revision:project.revision,dry_run:true}});edit(result.manifest,'Import timeline');notice('時間軸已套用至草稿；按儲存可更新作品版本。');}catch(error){notice(error.message);}finally{$('import-timeline').value='';}};
$('scene-play').onclick=async()=>{if(!viewer)return;try{await viewer.ready;if(viewer.state.mode==='exact-required')throw Error('請先更新實體 CAD 預覽。');}catch(error){notice(error.message);return;}cancelAnimationFrame(motionRequest);const start=performance.now(),mode=draft.beats[selected].visual.mode==='explode'?'explode':'orbit';function tick(now){viewer?.renderFrame(mode,Math.min(1,(now-start)/5000));if(now-start<5000)motionRequest=requestAnimationFrame(tick);}motionRequest=requestAnimationFrame(tick);};
window.addEventListener('beforeunload' ,e=>{if(dirty||formPending){e.preventDefault();e.returnValue='';}});
async function start(){session=await api('/api/session');assets=await api('/api/assets');recipes=await api('/api/recipes');$('recipe').replaceChildren(...recipes.map(r=>new Option(r.title,r.id)));$('scope').textContent=session.copy.disclaimer;$('footnote').textContent='Local studio · '+session.capabilities.free_gib+' GiB available';$('capabilities').textContent=JSON.stringify(session.capabilities,null,2);$('preset').replaceChildren(...session.copy.presets.map(p=>new Option(p.name,p.id)));
 const requestedProject=new URLSearchParams(location.search).get('project');const projects=await api('/api/projects');project=projects.length?await api('/api/projects/'+(projects.find(p=>p.id===requestedProject)||projects.find(p=>p.id==='pour-over-stand')||projects[0]).id):await api('/api/demo',{method:'POST',body:{}});draft=clone(project.manifest);renderProject();history.clear();await listProjects();await refreshJobs();
 const catalog=await api('/api/styles');const styles=catalog.styles||[];$('image-style').replaceChildren(new Option('選擇影像風格',''),...styles.map(s=>new Option(s.title?.zh||s.name?.zh||s.label||s.id,s.id)));$('image-style').value=draft.style_id||'';$('image-style').onchange=async()=>{const chosen=$('image-style').value;try{await captureForm();const style=styles.find(s=>s.id===chosen);$('style-description').textContent=style?JSON.stringify(style.description||style.prompt||style.title):'';const next=clone(draft);next.style_id=style?.id||null;edit(next,'Reference style');}catch(error){$('image-style').value=draft.style_id||'';notice(error.message);}};
 setInterval(()=>refreshJobs().catch(e=>notice(e.message)),2000);}
start().catch(e=>notice(e.message));
