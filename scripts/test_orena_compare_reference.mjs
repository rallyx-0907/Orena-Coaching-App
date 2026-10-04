import assert from 'node:assert/strict';
import { pairWord, pairedTiming, readingFor, decorateComparison, loadComparisonReference, comparisonReference } from '../static/orena/product/compare-reference.js';
import { setRemovedImports } from '../static/orena/product/import-removed.js';

const source = { language:'en', hasModelAudio:true, sourceId:'media:a', lessonId:'a', modelAudioUrl:()=>'/model',
  line:{lineId:'s',text:'the year and the year',startMs:1000,endMs:6000} };
const modelWords = [ ['the',0,100], ['year',100,400], ['and',500,200], ['the',800,100], ['year',900,400] ]
  .map(([text,offsetMs,durationMs])=>({text,offsetMs,durationMs,offsetKnown:true}));
const view = { measured:true, words:modelWords.map((w,index)=>({...w,index,offsetMs:w.offsetMs+300,score:80})) };
const ref={words:modelWords,readings:{the:'/ðə/',year:'/jɪr/',and:'/ænd/'},model:{duration:1.4}};
assert.equal(pairWord(source.line.text,view.words,4,ref.words,'en').offsetMs,900,'repeated words match by reference position');
assert.equal(decorateComparison(view,source,ref).words[1].reading,'/jɪr/');
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
console.log('Compare reference: real timing, repeated/Chinese words, deterministic readings, no learner attempts: PASS');
