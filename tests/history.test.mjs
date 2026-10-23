import {test} from 'node:test';
import assert from 'node:assert/strict';
import {HistoryManager} from '../dist/history.mjs';
test('failed undo preserves action and does not poison later commands',async()=>{
 const history=new HistoryManager();let attempts=0,healthy=0;
 history.record({label:'first',apply(){},revert(){healthy++;}});
 history.record({label:'flaky',apply(){},revert(){if(++attempts===1)throw Error('temporary');}});
 await assert.rejects(history.undo(),/temporary/);assert.equal(history.canUndo(),true);
 await history.undo();await history.undo();assert.equal(healthy,1);assert.equal(attempts,2);
 await history.redo();assert.equal(history.canUndo(),true);
});
test('concurrent undo calls serialize',async()=>{
 const history=new HistoryManager();let active=0,max=0,count=0;
 for(let i=0;i<3;i++)history.record({label:'x',apply(){},async revert(){active++;max=Math.max(max,active);await new Promise(r=>setTimeout(r,3));count++;active--;}});
 await Promise.all([history.undo(),history.undo(),history.undo()]);assert.equal(max,1);assert.equal(count,3);
});
test('clearing during an asynchronous replay does not resurrect stale history',async()=>{
 const history=new HistoryManager();let finish,start;
 const started=new Promise(resolve=>start=resolve),pending=new Promise(resolve=>finish=resolve);
 history.record({label:'old project',apply(){},async revert(){start();await pending;}});
 const undo=history.undo(),queued=history.undo();await started;history.clear();finish();
 await Promise.all([undo,queued]);assert.equal(history.canUndo(),false);assert.equal(history.canRedo(),false);
 history.record({label:'new project',apply(){},revert(){}});await history.undo();assert.equal(history.canRedo(),true);
});
