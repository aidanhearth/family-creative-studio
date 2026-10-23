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
   const keys=target==='project'?['title','subtitle','style_id','narration_asset','output_targets']:Object.keys(b);
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
