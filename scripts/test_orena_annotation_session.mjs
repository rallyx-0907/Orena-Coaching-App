import assert from 'node:assert/strict';
import { annotationSession } from '../static/orena/product/annotation-session.js';
import { annotatedLine } from '../static/orena/ui/annotated-line.js';
for (const language of ['en', 'zh']) {
  const text = language === 'en' ? 'A quiet street.' : '安静的街道。';
  const calls = [];
  let resolve;
  const session = annotationSession({ language, request: (input) => {
    calls.push(input); return new Promise(r => resolve = r);
  }});
  const segment = {segment_id:'line1',original_text:text};
  const loading = session.load(segment);
  await session.load(segment);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].source_language, language);
  assert(session.pending.has('line1'));
  resolve({text, annotations:[]}); await loading;
  assert.equal(session.values.get('line1').text, text);
  assert.equal(session.pending.size, 0);
  assert.equal(annotatedLine(segment, session.values.get('line1')), null);
}
let resolveOld, resolveNew;
const stale = annotationSession({language:'en',request: ({text}) => new Promise(r => {
  if(text==='old') resolveOld=r; else resolveNew=r;
})});
const old = stale.load({segment_id:'s',original_text:'old'});
const current = stale.load({segment_id:'s',original_text:'new'});
resolveOld({text:'old'}); await old;
assert.equal(stale.values.size,0); assert(stale.pending.has('s'));
resolveNew({text:'wrong source'}); await current;
assert.equal(stale.values.get('s'),null);
let alive = true, resolveGone;
const gone=annotationSession({language:'zh',alive:()=>alive,request:()=>new Promise(r=>resolveGone=r)});
const request=gone.load({segment_id:'s',original_text:'中文'});
alive=false; resolveGone({text:'中文'}); await request;
assert.equal(gone.values.size,0);
let attempts=0;
const retry=annotationSession({language:'en',request:async()=>{
  attempts++; if(attempts===1) throw Error('unavailable'); return {text:'word',annotations:[]};
}});
const word={segment_id:'w',original_text:'word'};
await retry.load(word); assert.equal(retry.values.get('w'),null);
retry.retry('w'); await retry.load(word); assert.equal(attempts,2);
const untimed=annotatedLine(word,{text:'word',annotations:[{start:0,end:4,fragment:'word',pos:'noun'}]});
assert(untimed.includes('data-token="word"'));
assert(!untimed.includes('data-word='));
assert(!untimed.includes('data-reading='));
console.log('Annotation session: EN/ZH, deduplication, source race, invalid result, unmount, retry and untimed tokens PASS');
