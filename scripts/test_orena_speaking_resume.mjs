import assert from 'node:assert/strict';
import { continuationTarget, speakModes } from '../static/orena/screens/practice/model.js';
import { mapContinuationEntry } from '../static/orena/screens/today/model.js';
import { placeBody } from '../static/orena/product/continue-sync.js';

for (const id of ['media:lesson-en', 'media:upload:source-zh']) {
  const entry = {id, title:'Actual source', intent:'speaking_compare', segment:'line-7'};
  const expected = {kind:'speak',routeId:'compare',params:{id},query:{segment:'line-7'}};
  assert.deepEqual(continuationTarget(entry),expected,'Continue must reopen Compare and the exact sentence');
  const today=mapContinuationEntry(entry,key=>key);
  assert.equal(today.routeId,'compare');
  assert.deepEqual(today.routeParams,{id});
  assert.deepEqual(today.routeQuery,{segment:'line-7'});
  assert.equal(placeBody(entry).place.segment,'line-7','existing account continuation retains the sentence');
  assert.equal(placeBody(entry).place.intent,'speaking_compare');
  assert.deepEqual(continuationTarget({...entry,intent:'speaking'}),{...expected,routeId:'speak'});
}
assert.equal(continuationTarget({id:'media:',intent:'speaking_compare'}),null);
assert.equal(continuationTarget({id:'unresolvable',intent:'speaking_compare'}),null);
assert.deepEqual(speakModes([{id:'media:lesson-en',practice_type:'clip',level:'B2'}]).find(mode=>mode.routeId==='speak')?.params,
  {id:'media:lesson-en'},'a real transcript-backed clip supports the Pronunciation entry too');
console.log('Speaking resume: exact source/sentence/Compare, Today/Practice and existing account continuation: PASS');
