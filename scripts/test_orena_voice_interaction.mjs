// Interaction effects under deterministic audio/API adapters. This is not
// browser or microphone acceptance; the recorder has its own platform tests.
import assert from 'node:assert/strict';
import {mountVoiceResponse} from '../static/orena/ui/voice-response.js';
import {learnerMemory} from '../static/orena/product/memory.js';
import {copy} from '../static/orena/ui/copy.js';
import {route} from '../static/orena/product/intent.js';

function view() {
  const nodes=new Map();
  const node=key=>{
    if(!nodes.has(key))nodes.set(key,{isConnected:true,innerHTML:'',textContent:'',disabled:false,setAttribute(){},focus(){},querySelector:node});
    return nodes.get(key);
  };
  return {root:node('root'),node};
}
for(const language of ['en','zh']) {
  const {root,node}=view();
  const memory=learnerMemory({getItem:()=>null,setItem(){}},`voice-interaction-${language}`,language);
  let saved=[],captures=0,cleaned=0;
  const heard=language==='en'?'I would like to show you the park.':'我想带你去公园看看。';
  const api={speakingAttempts:async()=>({items:[]}),transcribeSpeech:async()=>({text:heard}),evaluateSpeaking:async()=>({dimensions:{content_match:null,proficiency:null}}),saveSpeakingAttempt:async x=>{saved.push(x);}};
  const ctx={c:copy[language],ui:language,language,memory,api,alive:()=>true,mutate:fn=>fn()};
  const cleanup=mountVoiceResponse(root,ctx,{id:'voice:invitation',title:'Invitation',prompt:'Invite a friend.',recorder:{start:async()=>{captures++;return true;},stop:async()=>({blob:new Blob(['test audio']),url:'blob:test'}),cleanup(){cleaned++;}}});
  await node('[data-record]').onclick();
  assert.equal(captures,1);assert.equal(saved.length,0,'Recording is not evidence submission');
  await node('[data-record]').onclick();
  assert.match(node('[data-take]').innerHTML,/audio controls/);
  assert.equal(saved.length,0,'Listening to a take does not silently upload it');
  await node('[data-feedback]').onclick();
  assert.equal(saved.length,1);assert.equal(saved[0].reference_text,'');
  assert.match(node('[data-voice-result]').innerHTML,new RegExp(heard));
  assert.equal(Object.keys(memory.value.expressions).length,0,'A recognized take must not overwrite writing');
  globalThis.window={location:{hash:''}};
  node('[data-develop]').onclick();
  const draft=route(window.location.hash);
  assert.equal(draft.page,'expression');assert.equal(memory.value.expressions[draft.id],heard);
  memory.write(draft.id,'An edit I want to keep');
  node('[data-develop]').onclick();
  assert.equal(memory.value.expressions[draft.id],'An edit I want to keep');
  cleanup();assert.equal(cleaned,1);
}
// A permission request resolving after navigation cannot turn the abandoned
// surface into a recording, or leave capture running.
{
  const {root,node}=view();let finish, cleaned=0;
  const recorder={start:()=>new Promise(resolve=>{finish=resolve;}),cleanup(){cleaned++;}};
  const cleanup=mountVoiceResponse(root,{c:copy.en,language:'en',api:{speakingAttempts:async()=>({items:[]})},memory:{value:{},enter(){}},alive:()=>true},{id:'voice:test',title:'Test',prompt:'Test',recorder});
  const pending=node('[data-record]').onclick();cleanup();finish(true);await pending;
  assert.ok(cleaned>=2);assert.equal(node('[data-record]').textContent,'');
}
console.log('Voice interaction: explicit upload, playback, account evidence, draft preservation, late-permission cleanup EN/ZH PASS');
