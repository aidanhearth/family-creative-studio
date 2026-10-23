import {canonical,clampIndex,semanticOperations} from './state.mjs';
import {makeViewer} from './viewer.js';
import {paperEffect} from './shader.js';
import {HistoryManager} from '../vendor/storytold--artcraft/HistoryManager.ts';
const $=id=>document.getElementById(id), clone=o=>structuredClone(o);
let session,project,draft,selected=0,solidIndex=0,viewer,view='3d',job,published,dirty=false,saving=false,effect,assets=[],recipes=[],motionRequest;
const history=new HistoryManager({onChange:({canUndo,canRedo})=>{$('undo').disabled=!canUndo;$('redo').disabled=!canRedo;}});
function friendly(message){const match=Object.values(session?.copy.ui?.friendlyErrors||{}).find(e=>message.includes(e.match));return match?match.title+'。'+match.message:message;}
function notice(message=''){ $('notice').textContent=friendly(message); }
async function api(path,{method='GET',body,raw=false}={}){
 const response=await fetch(path,{method,headers:{'X-Studio-Token':session?.token||'',...(raw?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:raw?body:JSON.stringify(body)});
 const result=await response.json();if(!response.ok)throw Error(typeof result.error==='string'?result.error:JSON.stringify(result.detail||result));return result;
}
function resolveText(text){return text.replace(/\{\{([a-z0-9_-]+)\.(size|width|depth|height|bore)\}\}/g,(_,id,key)=>{
 const s=draft.solids.find(s=>s.id===id);if(!s)return '?';return key==='size'?s.size.join('×'):key==='bore'?s.bore:s.size[{width:0,depth:1,height:2}[key]];});}
function updateDirty(){ $('draft-status').textContent=dirty?'尚未儲存的修改':'尺寸母本已儲存';$('revision').textContent=`v${project.revision}${dirty?' · 草稿':''}`; }
function apply(next){draft=clone(next);selected=clampIndex(selected,draft.beats);solidIndex=clampIndex(solidIndex,draft.solids);dirty=canonical(draft)!==canonical(project.manifest);renderProject();}
function edit(next,label){const before=clone(draft);apply(next);history.record({label,apply:()=>apply(next),revert:()=>apply(before)});}
function renderProject(){
 const b=draft.beats[selected],s=draft.solids[solidIndex];
 document.documentElement.style.setProperty('--paper',draft.brand.paper);document.documentElement.style.setProperty('--ink',draft.brand.ink);document.documentElement.style.setProperty('--accent',draft.brand.accent);document.documentElement.style.setProperty('--muted',draft.brand.muted);
 $('project-name').textContent=draft.title;$('title').value=draft.title;$('beat-heading').textContent=resolveText(b.title);$('beat-title').value=b.title;$('beat-body').value=resolveText(b.body);$('beat-narration').value=resolveText(b.narration);$('caption-text').textContent=resolveText(b.narration);
 $('beats').replaceChildren(...draft.beats.map((beat,i)=>{const button=document.createElement('button');button.className=i===selected?'active':'';const number=document.createElement('span');number.textContent=String(i+1).padStart(2,'0');button.append(number,document.createTextNode(beat.title));button.onclick=()=>{selected=i;renderProject();};return button;}));
 $('solid').replaceChildren(...draft.solids.map((s,i)=>new Option(s.name,String(i),false,i===solidIndex)));
 for(const id of ['solid-name','solid-kind','bore',...['dim-','pos-'].flatMap(p=>[0,1,2].map(i=>p+i))])$(id).disabled=!s;
 if(s){s.size.forEach((n,i)=>$('dim-'+i).value=n);$('bore').value=s.bore||0;s.position.forEach((n,i)=>$('pos-'+i).value=n);$('solid-name').value=s.name;$('solid-kind').value=s.kind;}
 $('duration').value=b.duration;$('visual-mode').value=b.visual.mode;$('trim-start').value=b.visual.start;$('scene-audio').value=b.visual.audio;
 $('scene-asset').replaceChildren(new Option('尚未選取素材',''),...assets.map(a=>new Option(`${a.label?.slice(0,25)||a.asset.slice(0,8)} · ${a.duration_s?.toFixed(1)||a.width+'×'+a.height}${a.duration_s?' 秒':''}`,a.asset,false,a.asset===b.visual.asset)));
 $('remove-beat').disabled=draft.beats.length===1;$('beat-up').disabled=selected===0;$('beat-down').disabled=selected===draft.beats.length-1;$('remove-solid').disabled=!s;
 $('json-editor').value=JSON.stringify(draft,null,2);$('audio-state').textContent=draft.narration_asset?'已選取正式旁白':'eSpeak NG · 本機草稿配音';
 for(const input of document.querySelectorAll('[data-target]')){input.checked=draft.output_targets.includes(input.dataset.target);input.disabled=input.dataset.target==='cad'&&!draft.solids.length;}
 updateDirty();cancelAnimationFrame(motionRequest);viewer?.dispose();viewer=null;
 if(b.visual.asset){const el=document.createElement(b.visual.mode==='clip'?'video':'img');el.src='/api/assets/'+b.visual.asset;if(el.tagName==='VIDEO'){el.controls=true;el.onloadedmetadata=()=>{el.currentTime=b.visual.start;};}else el.alt=resolveText(b.title);$('viewer').replaceChildren(el);}
 else if(draft.solids.length){try{viewer=makeViewer($('viewer'),draft);viewer.focus(b.focus);if(b.visual.mode!=='diagram')viewer.renderFrame(b.visual.mode,.15);}catch(error){notice('3D 預覽尚未就緒：'+error.message);}}
 else{$('viewer').textContent=resolveText(b.body);}
 renderPreview();
}
async function save(){
 if(saving)throw Error('儲存進行中，請稍候。');if(!dirty)return project;
 saving=true;$('save').disabled=true;const sent=clone(draft);
 try{const saved=await api(`/api/projects/${project.id}/patch`,{method:'POST',body:{operations:semanticOperations(project.manifest,sent),expected_revision:project.revision}});project=saved;dirty=canonical(draft)!==canonical(sent);updateDirty();await listProjects();notice();return saved;}
 finally{saving=false;$('save').disabled=false;}
}
function artifact(path){return `/artifacts/${published.id}/${path.split('/').map(encodeURIComponent).join('/')}`;}
function renderPreview(){
 document.querySelector('.stage-meta').hidden=view==='video'||(view==='3d'&&!!draft.beats[selected].visual.asset);
 $('viewer').hidden=view!=='3d';$('preview').hidden=view==='3d';$('explode').hidden=view!=='3d';$('paper-effect').hidden=view!=='3d';
 for(const tab of document.querySelectorAll('[data-view]')){tab.classList.toggle('active',tab.dataset.view===view);tab.setAttribute('aria-selected',String(tab.dataset.view===view));}
 if(view==='3d'){$('stage-label').textContent='PARAMETRIC / mm';return;}
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
const outputs=[['project.zip','完整作品包','ZIP'],['index.html','暖紙互動專題','HTML'],['model.glb','3D 場景','GLB'],['model.step','實體幾何','STEP'],['model.stl','網格幾何','STL'],['anatomy.svg','圖解','SVG'],['workflow.html','敘事流程','ARCHIFY'],['presentation.pptx','可編輯簡報','PPTX'],['film.mp4','敘事短片','MP4'],['captions.srt','字幕','SRT'],['image-prompt.txt','影像創作提示詞','TXT']];
async function refreshJobs(){
 if(!project)return;
 const requested=project.id;const jobs=await api('/api/jobs?project_id='+encodeURIComponent(requested));if(project.id!==requested)return;job=jobs[0];const done=jobs.find(j=>j.state==='succeeded');
 const changed=done?.id!==published?.id;published=done;
 $('job-state').textContent=job?`${session.copy.ui?.status[job.state]||job.state} · v${job.revision} · ${session.copy.ui?.stage[job.stage]||job.stage}${job.error?' · '+friendly(job.error):''}`:'尚未輸出作品';
 $('cancel').hidden=!job||!['queued','running'].includes(job.state);$('retry').hidden=!job||!['failed','interrupted','cancelled'].includes(job.state);
 $('render').disabled=!!job&&['queued','running'].includes(job.state);
 if(changed&&published){
  $('artifact-list').replaceChildren(...outputs.filter(([path])=>published.artifacts.some(a=>a.path===path)).map(([path,label,format])=>{const a=document.createElement('a');a.className='artifact';a.href=artifact(path);a.target='_blank';a.rel='noopener';if(!path.endsWith('.html'))a.download=path;const arrow=document.createElement('b');arrow.textContent='↗';const small=document.createElement('span');const record=published.artifacts.find(a=>a.path===path);small.textContent=`${format} · ${record.bytes<1024?record.bytes+' B':(record.bytes/1024).toFixed(0)+' KB'} · v${published.revision}`;a.append(arrow,document.createTextNode(label),small);return a;}));
  const stages=published.artifacts.some(a=>a.path==='build-stages.json')?await(await fetch(artifact('build-stages.json'))).json():null;$('reuse-state').textContent=stages?.stages.some(s=>s.stage==='cad'&&s.reused)?session.upgrade.actions.reuseCadNotice:'';const completedId=published.id;const quality=await (await fetch(artifact('quality.json'))).json();if(project.id!==requested||published?.id!==completedId)return;$('quality').replaceChildren(...quality.checks.map(c=>{const p=document.createElement('div');p.className='quality-row';const mark=document.createElement('span');mark.textContent=c.pass?'✓':'·';p.append(mark,document.createTextNode(session.copy.ui?.qualityChecks[c.check]||c.check));return p;}));renderPreview();
 }
}
$('editor').onsubmit=async e=>{e.preventDefault();try{
 const next=clone(draft),beat=next.beats[selected],solid=next.solids[solidIndex];next.title=$('title').value;
 Object.assign(beat,{title:$('beat-title').value,body:$('beat-body').value===resolveText(draft.beats[selected].body)?draft.beats[selected].body:$('beat-body').value,narration:$('beat-narration').value===resolveText(draft.beats[selected].narration)?draft.beats[selected].narration:$('beat-narration').value,duration:Number($('duration').value)});
 if(solid)Object.assign(solid,{size:[0,1,2].map(i=>Number($('dim-'+i).value)),bore:Number($('bore').value),position:[0,1,2].map(i=>Number($('pos-'+i).value)),kind:$('solid-kind').value,name:$('solid-name').value});
 const mode=$('visual-mode').value;beat.visual={mode,asset:['image','clip'].includes(mode)?$('scene-asset').value||null:null,start:mode==='clip'?Number($('trim-start').value):0,audio:$('scene-audio').value};
 edit(await api('/api/validate',{method:'POST',body:next}),'Edit manifest');notice();
 }catch(e){notice(e.message);}};
$('solid').onchange=()=>{solidIndex=Number($('solid').value);renderProject();};
$('preset').onchange=()=>{const p=session.copy.presets.find(p=>p.id===$('preset').value);const next=clone(draft);Object.assign(next.brand,{name:p.name,paper:p.colors.canvasBg,ink:p.colors.textPrimary,accent:p.colors.accentPrimary,muted:p.colors.textSecondary});edit(next,'Brand preset');};
$('save').onclick=()=>save().catch(e=>notice(e.message));
$('render').onclick=async()=>{try{await save();if(dirty)throw Error('儲存期間內容已變更，請再次儲存。');await api(`/api/projects/${project.id}/render`,{method:'POST',body:{targets:draft.output_targets,expected_revision:project.revision}});await refreshJobs();notice();}catch(e){notice(e.message);}};
$('undo').onclick=()=>history.undo().catch(e=>notice(e.message));$('redo').onclick=()=>history.redo().catch(e=>notice(e.message));
$('apply-json').onclick=async()=>{try{const next=JSON.parse($('json-editor').value);if(next.id!==draft.id)throw Error('此處編輯保留同一個專案 ID');edit(await api('/api/validate',{method:'POST',body:next}),'JSON edit');}catch(e){notice(e.message);}};
$('explode').onclick=()=>viewer?.setExploded(!viewer.state.exploded);
for(const tab of document.querySelectorAll('[data-view]'))tab.onclick=()=>{view=tab.dataset.view;renderPreview();};
$('cancel').onclick=async()=>{try{await api(`/api/jobs/${job.id}/cancel`,{method:'POST',body:{}});await refreshJobs();}catch(e){notice(e.message);}};
$('retry').onclick=async()=>{try{await api(`/api/jobs/${job.id}/retry`,{method:'POST',body:{}});await refreshJobs();}catch(e){notice(e.message);}};
$('audio').onchange=async()=>{try{const file=$('audio').files[0];if(!file)return;const result=await api('/api/audio',{method:'POST',body:await file.arrayBuffer(),raw:true});const next=clone(draft);next.narration_asset=result.asset;edit(next,'Narration import');notice(`已匯入 ${result.duration_s.toFixed(1)} 秒旁白。`);}catch(e){notice(e.message);}};
$('fx').onchange=async()=>{effect?.destroy();effect=null;if($('fx').checked){effect=await paperEffect($('paper-effect'));$('fx-status').textContent=effect.state==='active'?'WebGPU':'靜態背景 · WebGPU 未就緒';}else $('fx-status').textContent='';};
$('audit').onclick=async()=>{try{$('audit').disabled=true;if(!window.impeccableDetectFromSnapshot){await new Promise((resolve,reject)=>{const s=document.createElement('script');s.src='/static/impeccable.js';s.onload=resolve;s.onerror=reject;document.head.append(s);});}const result=await window.impeccableDetectFromSnapshot({});window.lastStudioAudit=result;$('audit-result').textContent=`已巡檢 ${result.stats?.elements||0} 個畫面元件 · ${result.findings?.length??0} 項建議。暖紙底色屬本作採用的視覺風格。`;}catch(e){notice('視覺巡檢：'+e.message);}finally{$('audit').disabled=false;}};
async function listProjects(){const items=await api('/api/projects');$('projects').replaceChildren(...items.map(p=>new Option(p.title,p.id,false,p.id===project?.id)));}
async function openProject(id){project=await api('/api/projects/'+encodeURIComponent(id));draft=clone(project.manifest);selected=0;solidIndex=0;dirty=false;job=null;published=null;$('artifact-list').replaceChildren();$('quality').replaceChildren();history.clear();renderProject();await listProjects();await refreshJobs();}
$('projects').onchange=async()=>{try{if(dirty||saving){$('projects').value=project.id;throw Error('請先儲存目前的修改，再切換作品。');}await openProject($('projects').value);}catch(e){notice(e.message);}};
$('new-project').onclick=()=>{if(dirty||saving){notice('請先儲存目前的修改，再建立作品。');return;}$('create-id').value='project-'+Date.now().toString(36);$('recipe').onchange();$('create-dialog').showModal();};
$('close-create').onclick=()=>$('create-dialog').close();
$('recipe').onchange=()=>{const r=recipes.find(r=>r.id===$('recipe').value);$('recipe-description').textContent=r.description;$('create-title').value=r.defaultTitle;};
$('create-form').onsubmit=async e=>{e.preventDefault();try{const p=await api('/api/create',{method:'POST',body:{recipe_id:$('recipe').value,project_id:$('create-id').value,title:$('create-title').value}});$('create-dialog').close();await openProject(p.id);}catch(e){notice(e.message);}};
async function localPatch(operations,label){await save();const result=await api(`/api/projects/${project.id}/patch`,{method:'POST',body:{expected_revision:project.revision,operations,dry_run:true}});edit(result.manifest,label);}
function action(id,run){$(id).onclick=async()=>{try{await run();notice();}catch(e){notice(e.message);}};}
action('add-solid',()=>localPatch([{op:'add',target:'solid',values:{id:'part-'+Date.now().toString(36),name:'新增零件',kind:'box',size:[40,40,20],position:[0,0,10]}}],'Add part'));
action('remove-solid',()=>{const ops=[{op:'remove',target:'solid',id:draft.solids[solidIndex].id}];if(draft.solids.length===1){ops.push({op:'set',target:'project',values:{output_targets:draft.output_targets.filter(t=>t!=='cad').length?draft.output_targets.filter(t=>t!=='cad'):['web']}});for(const b of draft.beats)if(['orbit','explode'].includes(b.visual.mode))ops.push({op:'set',target:'beat',id:b.id,values:{visual:{...b.visual,mode:'diagram'}}});}if(draft.solids.length===2)for(const b of draft.beats)if(b.visual.mode==='explode')ops.push({op:'set',target:'beat',id:b.id,values:{visual:{...b.visual,mode:'orbit'}}});return localPatch(ops,'Remove part');});
action('add-beat',()=>localPatch([{op:'add',target:'beat',values:{...draft.beats[selected],id:'chapter-'+Date.now().toString(36),title:'新增章節'}}],'Add chapter'));
action('remove-beat',()=>localPatch([{op:'remove',target:'beat',id:draft.beats[selected].id}],'Remove chapter'));
for(const [id,direction] of [['beat-up',-1],['beat-down',1]])action(id,()=>localPatch([{op:'move',target:'beat',id:draft.beats[selected].id,index:selected+direction}],'Move chapter'));
$('media').onchange=async()=>{const file=$('media').files[0];if(!file)return;try{if(file.size>50*1024*1024)throw Error(session.upgrade.errors.mediaFormatUnsupported);$('media-state').textContent='素材驗證與轉檔中…';const result=await api('/api/media?name='+encodeURIComponent(file.name),{method:'POST',body:file,raw:true});assets=await api('/api/assets');const next=clone(draft),b=next.beats[selected];b.visual={mode:result.kind,asset:result.asset,start:0,audio:result.kind==='clip'&&result.audio?'source':'voice'};if(result.kind==='clip'){if(result.duration_s<3)throw Error('章節最短 3 秒，請選擇較長影片。');b.duration=Math.min(b.duration,Math.floor(result.duration_s*24)/24);}edit(await api('/api/validate',{method:'POST',body:next}),'Import scene media');$('media-state').textContent='素材已匯入 · '+(result.bytes/1024/1024).toFixed(1)+' MiB';notice();}catch(e){$('media-state').textContent='素材未套用';notice(e.message);}finally{$('media').value='';}};
action('compare',async()=>{await save();if(project.revision<2)throw Error(session.upgrade.emptyStates.noRevisionDiff);const result=await api(`/api/projects/${project.id}/compare?before=${project.revision-1}`);$('comparison').hidden=false;$('comparison').textContent=`v${result.before} → v${result.after}\n`+result.changes.map(c=>`${c.path}\n${JSON.stringify(c.before)} → ${JSON.stringify(c.after)}`).join('\n\n');});
for(const input of document.querySelectorAll('[data-target]'))input.onchange=async()=>{try{const next=clone(draft);next.output_targets=[...document.querySelectorAll('[data-target]:checked')].map(i=>i.dataset.target);edit(await api('/api/validate',{method:'POST',body:next}),'Output formats');}catch(e){notice(e.message);renderProject();}};
$('scene-play').onclick=()=>{if(!viewer)return;cancelAnimationFrame(motionRequest);const start=performance.now(),mode=draft.beats[selected].visual.mode==='explode'?'explode':'orbit';function tick(now){viewer?.renderFrame(mode,Math.min(1,(now-start)/5000));if(now-start<5000)motionRequest=requestAnimationFrame(tick);}motionRequest=requestAnimationFrame(tick);};
window.addEventListener('beforeunload' ,e=>{if(dirty){e.preventDefault();e.returnValue='';}});
async function start(){session=await api('/api/session');assets=await api('/api/assets');recipes=await api('/api/recipes');$('recipe').replaceChildren(...recipes.map(r=>new Option(r.title,r.id)));$('scope').textContent=session.copy.disclaimer;$('footnote').textContent='Local studio · '+session.capabilities.free_gib+' GiB available';$('capabilities').textContent=JSON.stringify(session.capabilities,null,2);$('preset').replaceChildren(...session.copy.presets.map(p=>new Option(p.name,p.id)));
 const requestedProject=new URLSearchParams(location.search).get('project');const projects=await api('/api/projects');project=projects.length?await api('/api/projects/'+(projects.find(p=>p.id===requestedProject)||projects.find(p=>p.id==='pour-over-stand')||projects[0]).id):await api('/api/demo',{method:'POST',body:{}});draft=clone(project.manifest);renderProject();history.clear();await listProjects();await refreshJobs();
 const catalog=await api('/api/styles');const styles=catalog.styles||[];$('image-style').replaceChildren(new Option('選擇影像風格',''),...styles.map(s=>new Option(s.title?.zh||s.name?.zh||s.label||s.id,s.id)));$('image-style').onchange=()=>{const style=styles.find(s=>s.id===$('image-style').value);$('style-description').textContent=style?JSON.stringify(style.description||style.prompt||style.title):'';if(style){const next=clone(draft);next.style_id=style.id;edit(next,'Reference style');}};
 setInterval(()=>refreshJobs().catch(e=>notice(e.message)),2000);}
start().catch(e=>notice(e.message));
