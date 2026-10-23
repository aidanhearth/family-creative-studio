import test from 'node:test';
import assert from 'node:assert/strict';
import {canonical,clampIndex} from '../web/state.mjs';
test('server key order does not create an unsaved draft',()=>{
 assert.equal(canonical({brand:{z:2,a:1},beats:[{b:2,a:1}]}),canonical({beats:[{a:1,b:2}],brand:{a:1,z:2}}));
});
test('selection survives removal of chapters and parts',()=>{
 assert.equal(clampIndex(2,[{}]),0);assert.equal(clampIndex(0,[{},{}]),0);
});
