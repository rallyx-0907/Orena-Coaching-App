import assert from 'node:assert/strict';
import { pairWord, pairedTiming, readingFor, decorateComparison, loadComparisonReference, comparisonReference, estimateModelWords } from '../static/orena/product/compare-reference.js';
import { setRemovedImports } from '../static/orena/product/import-removed.js';

const source = { language:'en', hasModelAudio:true, sourceId:'media:a', lessonId:'a', modelAudioUrl:()=>'/model',
  line:{lineId:'s',text:'the year and the year',startMs:1000,endMs:6000} };
const modelWords = [ ['the',0,100], ['year',100,400], ['and',500,200], ['the',800,100], ['year',900,400] ]
  .map(([text,offsetMs,durationMs])=>({text,offsetMs,durationMs,offsetKnown:true}));
const view = { measured:true, words:modelWords.map((w,index)=>({...w,index,offsetMs:w.offsetMs+300,score:80})) };
const ref={words:modelWords,readings:{the:'/ðə/',year:'/jɪr/',and:'/ænd/'},model:{duration:1.4}};
assert.equal(pairWord(source.line.text,view.words,4,ref.words,'en').offsetMs,900,'repeated words match by reference position');
assert.equal(decorateComparison(view,source,ref).words[1].reading,'','D-139 HD-5: English IPA is never taken from a dictionary - no provider sounds, no reading');
const sounded={...view,words:view.words.map(w=>w.index===1?{...w,phonemes:[{label:'j',score:90},{label:'ɪ',score:80},{label:'r',score:70}]}:w)};
assert.equal(decorateComparison(sounded,source,ref).words[1].reading,'jɪr','IPA is the provider own sounds for the word, in order');
assert.equal(view.words[1].reading,undefined,'never mutate learner evidence');
assert.equal(pairWord('你好你好',[{text:'你好'},{text:'你好'}],1,[
  {text:'你',offsetKnown:true,offsetMs:0,durationMs:100}, {text:'好',offsetKnown:true,offsetMs:100,durationMs:100},
  {text:'你',offsetKnown:true,offsetMs:250,durationMs:100}, {text:'好',offsetKnown:true,offsetMs:350,durationMs:100},
],'zh').durationMs,200,'a multi-Han learner word joins its matching model characters');
assert.equal(pairWord('the year',view.words,0,[{text:'the',offsetKnown:false}],'en'),null);
assert.equal(pairWord('the year',[{text:'the'}],0,[{text:'year',offsetKnown:true,offsetMs:0,durationMs:100}],'en'),null);
const timing=pairedTiming(view.words[4],modelWords[4],view.words,modelWords);
assert.equal(timing.you.from,0.9,'leading microphone wait is not a timing error');
assert.equal(timing.model.from,0.9);assert.equal(timing.deltaMs,0);
assert.equal(pairedTiming(view.words[4],null,view.words,[]).model,null);

let assessments=0, saves=0, lookups=0;
const api={
  wordDetail:async p=>{lookups++;assert.equal(p.contextual,false);return {ipa:ref.readings[p.text]};},
  speakingModelReference:async (lesson,line)=>{assert.equal(lesson,'a');assert.equal(line,'s');assessments++;return {score_kind:'measured',words:modelWords.map(w=>({word:w.text,offset_ms:w.offsetMs,duration_ms:w.durationMs,error_type:'None',ipa:w.text==='and'?'/ənd/':null}))};},
  saveSpeakingAttempt:()=>{saves++;throw Error('reference is not a learner attempt');},
};
const options={api,support:'vi',fetchImpl:async()=>({ok:true,blob:async()=>new Blob(['real source'])}),
  decode:async()=>({duration:1.4}),analyse:()=>({duration:1.4,contour:[]})};
const canonical={...source,line:{...source.line,wordTimings:modelWords}};
const prepared=await loadComparisonReference(canonical,options);
assert.equal(prepared.words.length,5);
assert.equal(lookups,0,'opening a line does not recreate dictionary derivatives');
assert.equal(assessments,0,'canonical source words require no paid assessment');
assert.equal(saves,0);
const missing=await loadComparisonReference(source,options);
assert.equal(missing.words.length,0,'missing optional source timing does not trigger generation');
assert.equal(missing.alignmentState,'unavailable');
assert.equal(assessments,0);
const chinese=await loadComparisonReference({language:'zh',hasModelAudio:false,line:{text:'银行行走',reading:'yín háng xíng zǒu'}},options);
assert.equal(readingFor('行',chinese,'zh',1),'háng');
assert.equal(readingFor('行',chinese,'zh',2),'xíng','heteronyms follow persisted phrase positions');
setRemovedImports([], 'tester:en');
await comparisonReference(source,{...options,owner:'tester'});
setRemovedImports(['upload:a'], 'tester:en');
await assert.rejects(()=>comparisonReference(source,{...options,owner:'tester'}),{category:'media_not_found'},'a deleted import never returns cached reference context');
/* D-140: the model clip prepared at content readiness is measured here; its words are estimated only without verified timing. */
const contourOf=(from,to)=>Array.from({length:Math.round(to*100)},(_,at)=>({t:at/100,st:at/100>=from&&at/100<to?1:null}));
const model={duration:2,bars:[],contour:contourOf(0.4,1.6)};
const clipSource=(overrides={},line={})=>({...source,...overrides,line:{...source.line,modelClipUrl:'/api/speaking/model-clip/a/s',...line}});
const urls=[];
const clipOptions={...options,fetchImpl:async url=>{urls.push(url);return {ok:true,blob:async()=>new Blob(['clip'])};},decode:async()=>({duration:2}),analyse:()=>model};
const measured=await loadComparisonReference(clipSource(),clipOptions);
assert.deepEqual(urls,['/api/speaking/model-clip/a/s']);
assert.equal(measured.model,model,'the model pitch comes from the prepared clip');
assert.equal(measured.timingEstimated,true);
assert.equal(measured.alignmentState,'ready');
assert.ok(measured.words.length===5 && measured.words.every(w=>w.estimated && w.offsetKnown));
assert.equal(measured.words[0].offsetMs,400);
const lastEstimated=measured.words.at(-1);
assert.ok(Math.abs(lastEstimated.offsetMs+lastEstimated.durationMs-1600)<=20,'estimated words fill the voiced span');
const letters=measured.words.map(w=>w.durationMs/(w.text.length));
assert.ok(Math.max(...letters)-Math.min(...letters)<4,'English words are weighted by their letters');
assert.equal(assessments,0);
const verified=await loadComparisonReference(clipSource({}, {wordTimings:modelWords}),clipOptions);
assert.equal(verified.timingEstimated,false,'verified word timing always wins');
assert.deepEqual(verified.words,modelWords);
assert.equal(verified.model,model,'a verified line still measures the model pitch');
const han=estimateModelWords('你好 Vector',  'zh',model);
assert.deepEqual(han.map(w=>w.text),['你','好','Vector']);
assert.deepEqual(han.map(w=>Math.round(w.durationMs/1200*8)),[1,1,6],'one share per Han character, a Latin run by its letters');
const zh=await loadComparisonReference(clipSource({language:'zh'},{text:'你好吗',reading:''}),clipOptions);
assert.equal(zh.timingEstimated,true);assert.equal(zh.words.length,3);
assert.deepEqual(estimateModelWords('hello','en',{contour:[{t:0,st:1},{t:0.01,st:null}]}),[],'fewer than two voiced points: no estimate');
for (const failing of [async()=>({ok:false}),async()=>{throw Error('offline');}]) {
  const failed=await loadComparisonReference(clipSource(),{...clipOptions,fetchImpl:failing});
  assert.equal(failed.model,null);assert.equal(failed.timingEstimated,false);assert.equal(failed.words.length,0);
  assert.equal(failed.audioState,'unavailable','a failed clip is model unavailable, never a retry or a fallback source');
}
const undecodable=await loadComparisonReference(clipSource(),{...clipOptions,decode:async()=>{throw Error('decode');}});
assert.equal(undecodable.model,null);
assert.ok(urls.every(url=>url==='/api/speaking/model-clip/a/s'),'no other URL is ever requested');
const before=urls.length;
const bare=await loadComparisonReference(source,clipOptions);
assert.equal(urls.length,before,'a line with no prepared clip fetches nothing');
assert.equal(bare.model,null);
console.log('Compare reference: real timing, repeated/Chinese words, deterministic readings, no learner attempts: PASS');
