export function canonical(value) {
 if (Array.isArray(value)) return '['+value.map(canonical).join(',')+']';
 if (value && typeof value==='object') return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';
 return JSON.stringify(value);
}
export const clampIndex=(index,items)=>Math.max(0,Math.min(index,items.length-1));

export function semanticOperations(before,after){
 const ops=[];
 for(const target of ['project','brand']){
   const a=target==='project'?before:before.brand,b=target==='project'?after:after.brand;
   const keys=target==='project'?['title','subtitle','style_id','narration_asset','output_targets','video','slides','effect','diagram','scene_asset','scene_animation']:Object.keys(b);
   const values=Object.fromEntries(keys.filter(k=>canonical(a[k])!==canonical(b[k])).map(k=>[k,b[k]]));
   if(Object.keys(values).length)ops.push({op:'set',target,values});
 }
 for(const [key,target] of [['solids','solid'],['beats','beat']]){
   const a=before[key],b=after[key],working=a.map(x=>x.id).filter(id=>b.some(x=>x.id===id));
   for(const item of a)if(!b.some(x=>x.id===item.id))ops.push({op:'remove',target,id:item.id});
   for(const item of b){
     const old=a.find(x=>x.id===item.id);
     if(!old){ops.push({op:'add',target,values:item});working.push(item.id);}
     else {const values=Object.fromEntries(Object.keys(item).filter(k=>k!=='id'&&canonical(old[k])!==canonical(item[k])).map(k=>[k,item[k]]));if(Object.keys(values).length)ops.push({op:'set',target,id:item.id,values});}
   }
   b.forEach((item,index)=>{const old=working.indexOf(item.id);if(old!==index){ops.push({op:'move',target,id:item.id,index});working.splice(index,0,...working.splice(old,1));}});
 }
 return ops;
}

// Templates remain the editable source of truth. Resolution is only presentation.
export function resolveText(text, solids) {
 return String(text??'').replace(/\{\{([a-z0-9_-]+)\.(size|width|depth|height|bore)\}\}/g,(_,id,key)=>{
   const solid=solids.find(s=>s.id===id);if(!solid)return `{{${id}.${key}}}`;
   return key==='size'?solid.size.join('×'):key==='bore'?(solid.bore||0):solid.size[{width:0,depth:1,height:2}[key]];
 });
}

export function selectionIndex(id, items, fallback=0) {
 const index=items.findIndex(item=>item.id===id);
 return index<0?clampIndex(fallback,items):index;
}

// Local operations never persist. The full result is validated once by /api/validate.
export function applyLocalOperations(manifest,operations) {
 const next=structuredClone(manifest);
 for(const operation of operations){
   const {op,target,id,values={},index}=operation;
   if(target==='project'||target==='brand'){
     if(op!=='set')throw Error('作品與色票只接受欄位修改');
     Object.assign(target==='project'?next:next.brand,structuredClone(values));continue;
   }
   const items=next[target==='solid'?'solids':'beats'];
   if(!items)throw Error('未知的修改目標');
   if(op==='add'){
     if(items.some(item=>item.id===values.id))throw Error('代號已存在');
     const at=index??items.length;if(at<0||at>items.length)throw Error('新增位置超出範圍');
     items.splice(at,0,structuredClone(values));continue;
   }
   const at=items.findIndex(item=>item.id===id);if(at<0)throw Error('修改的項目已不存在');
   if(op==='set'){
     if('id' in values)throw Error('修改時保留固定代號');
     Object.assign(items[at],structuredClone(values));
   }else if(op==='move'){
     if(!Number.isInteger(index)||index<0||index>=items.length)throw Error('移動位置超出範圍');
     items.splice(index,0,...items.splice(at,1));
   }else if(op==='remove'){
     if(target==='solid'){
       const removed=items[at],freeze=text=>resolveText(text,[removed]);
       next.title=freeze(next.title);next.subtitle=freeze(next.subtitle);
       for(const beat of next.beats){
         beat.focus=(beat.focus||[]).filter(focus=>focus!==id);
         for(const key of ['title','body','narration'])beat[key]=freeze(beat[key]);
       }
     }
     items.splice(at,1);
   }else throw Error('未知的修改操作');
 }
 return next;
}

// The pinned Impeccable serializer returns groups, each with nested findings.
export function auditFindings(result) {
 if(!Array.isArray(result?.findings))throw Error('視覺巡檢傳回的格式不符，未將未知結果計為零項');
 return result.findings.flatMap(group=>{
   if(!Array.isArray(group.findings))throw Error('視覺巡檢項目缺少 findings');
   return group.findings.map(finding=>({...finding,selector:group.selector,isPageLevel:group.isPageLevel}));
 });
}
