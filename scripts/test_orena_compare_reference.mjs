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
const prepared=await loadComparisonReference(source,options);
assert.equal(prepared.words.length,5);
assert.equal(prepared.readings.year,'/jɪr/');
assert.equal(readingFor('and',prepared,'en',9),'/ənd/','IPA from the source reference stays tied to its word position');
assert.equal(lookups,3,'look up unique words, not each repeat');
assert.equal(assessments,1);assert.equal(saves,0);
const canonical={...source,line:{...source.line,wordTimings:modelWords}};
await loadComparisonReference(canonical,options);
assert.equal(assessments,1,'canonical model word intervals avoid paid re-analysis');
const rejected=await loadComparisonReference(source,{...options,api:{...api,speakingModelReference:async()=>({score_kind:'synthetic_demo',words:[]})}});
assert.equal(rejected.words.length,0,'demo measurements never become model evidence');
assert.equal(rejected.alignmentState,'unavailable');
const chinese=await loadComparisonReference({language:'zh',hasModelAudio:false,line:{text:'银行行走'}},{api:{
  annotateMediaText:async()=>({text:'银行行走',annotations:[{start:0,end:2,pronunciation:'yín háng'},{start:2,end:4,pronunciation:'xíng zǒu'}]}),
  wordDetail:async()=>{throw Error('position readings should avoid extra dictionary requests');},
}});
assert.equal(readingFor('行',chinese,'zh',1),'háng');
assert.equal(readingFor('行',chinese,'zh',2),'xíng','heteronyms follow their actual phrase position');
setRemovedImports([], 'tester:en');
await comparisonReference(source,{...options,owner:'tester'});
setRemovedImports(['upload:a'], 'tester:en');
await assert.rejects(()=>comparisonReference(source,{...options,owner:'tester'}),{category:'media_not_found'},'a deleted import never returns cached reference context');
console.log('Compare reference: real timing, repeated/Chinese words, deterministic readings, no learner attempts: PASS');
