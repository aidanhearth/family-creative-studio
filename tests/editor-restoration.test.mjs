import test from 'node:test';
import assert from 'node:assert/strict';
import {applyLocalOperations,resolveText,semanticOperations,selectionIndex,auditFindings} from '../web/state.mjs';
import {primitiveGeometry,requiresExactGeometry} from '../web/viewer.js';
import {Vector3} from 'three';

const makeManifest=()=>({id:'test',title:'基座 {{base.width}}',subtitle:'{{base.size}} 與 {{other.width}}',brand:{paper:'#ffffff'},solids:[{id:'base',size:[180,130,12],position:[0,0,6],bore:10},{id:'other',size:[20,20,30],position:[0,0,30],bore:0}],beats:[{id:'one',title:'{{base.width}}',body:'寬 {{base.width}}、另 {{other.width}}',narration:'{{base.size}}',focus:['base','other']},{id:'two',title:'二',body:'第二章',narration:'二',focus:[]}],output_targets:['web']});

test('ordinary punctuation edit preserves raw dimension expressions through subsequent dimension change',()=>{
 const original=makeManifest(),edited=applyLocalOperations(original,[{op:'set',target:'beat',id:'one',values:{body:original.beats[0].body+'。'}}]);
 const resized=applyLocalOperations(edited,[{op:'set',target:'solid',id:'base',values:{size:[240,130,12]}}]);
 assert.equal(resized.beats[0].body,'寬 {{base.width}}、另 {{other.width}}。');
 assert.equal(resolveText(resized.beats[0].body,resized.solids),'寬 240、另 20。');
 assert.equal(original.solids[0].size[0],180);
});
test('local structural edits preserve draft text, order and selection without mutating saved object',()=>{
 const before=makeManifest();before.beats[0].body='未儲存 {{base.width}}';
 const added=applyLocalOperations(before,[{op:'add',target:'beat',values:{id:'three',title:'三',body:'三',narration:'三',focus:[]}},{op:'move',target:'beat',id:'three',index:0}]);
 assert.deepEqual(added.beats.map(b=>b.id),['three','one','two']);assert.equal(added.beats[1].body,'未儲存 {{base.width}}');
 assert.equal(selectionIndex('one',added.beats),1);assert.equal(before.beats.length,2);
 assert.deepEqual(applyLocalOperations(before,semanticOperations(before,added)),added);
});
test('removal freezes only removed part expressions and drops only its focus ID',()=>{
 const removed=applyLocalOperations(makeManifest(),[{op:'remove',target:'solid',id:'base'}]);
 assert.equal(removed.subtitle,'180×130×12 與 {{other.width}}');
 assert.equal(removed.beats[0].body,'寬 180、另 {{other.width}}');assert.deepEqual(removed.beats[0].focus,['other']);
});
test('export settings are included in stable-ID semantic save',()=>{
 const before=makeManifest(),after={...before,video:{resolution:'2160p',fps:60,crf:16,captions:true,normalize_audio:true},slides:{layout:'full',narration:true,autoplay:false},effect:{enabled:true,type:'LinearGradient'},diagram:{kind:'tree',document:{}}};
 assert.deepEqual(applyLocalOperations(before,semanticOperations(before,after)),after);
});
test('selected scene animation persists through semantic saves and resets explicitly with the source',()=>{
 const before={...makeManifest(),scene_asset:'a'.repeat(64)+'.glb',scene_animation:0};
 const selected={...before,scene_animation:1};
 const operations=semanticOperations(before,selected);
 assert.deepEqual(operations,[{op:'set',target:'project',values:{scene_animation:1}}]);
 assert.deepEqual(applyLocalOperations(before,operations),selected);
 const switched={...selected,scene_asset:'b'.repeat(64)+'.glb',scene_animation:0};
 assert.deepEqual(applyLocalOperations(selected,semanticOperations(selected,switched)),switched);
});
test('nested audit findings retain each detail and locator; unknown data cannot become zero findings',()=>{
 const result=auditFindings({findings:[{selector:'#title',findings:[{type:'contrast',detail:'Low contrast'},{type:'size',detail:'Small text'}]}]});
 assert.equal(result.length,2);assert.equal(result[1].selector,'#title');assert.equal(result[0].detail,'Low contrast');
 assert.throws(()=>auditFindings({}),/格式不符/);assert.throws(()=>auditFindings({findings:[{}]}),/findings/);
});
for(const [kind,size,extra] of [['box',[40,30,20],{}],['cylinder',[40,40,20],{}],['sphere',[40,40,40],{}],['cone',[40,40,20],{top_diameter:12}],['torus',[40,40,8],{}],['extrusion',[40,30,20],{profile:[[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]]}]]){
 test(`${kind} browser geometry has the declared millimetre bounds`,()=>{
  const geometry=primitiveGeometry({id:'part',kind,size,bore:0,...extra});geometry.computeBoundingBox();const actual=geometry.boundingBox.getSize(new Vector3()).toArray();
  actual.forEach((value,index)=>assert.ok(Math.abs(value-size[index])<.001,`${kind} dimension ${index}: ${value} != ${size[index]}`));geometry.dispose();
 });
}
test('unsupported exact geometry is never approximated as a box or cylinder',()=>{
 for(const part of [{kind:'step'},{kind:'box',fillet:2},{kind:'box',chamfer:1},{kind:'sphere',bore:2},{kind:'box',booleans:[{tool:'cut',operation:'subtract'}]}])assert.equal(requiresExactGeometry(part),true);
 assert.throws(()=>primitiveGeometry({kind:'step',size:[10,10,10],id:'cad'}),/實體 CAD/);
});
