// Interaction effects under deterministic audio/API adapters. This is not
// browser or microphone acceptance; the recorder has its own platform tests.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
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
/* --- The room says a take is impossible before asking for one ---

   The transcription endpoint has always answered 503 when no speech provider is
   attached, but the learner only met that after granting a microphone,
   speaking, and waiting. The same answer is now asked for up front. */
const {speechConfigured} = await import('../static/orena/ui/voice-response.js');
const readSrc = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

{
  // Unconfigured: the room is told, once, and can act on it.
  let calls = 0;
  const api = {speechStatus: async () => { calls += 1; return {configured: false, provider: null}; }};
  assert.equal(await speechConfigured(api), false);
  // Cached: a composer that repaints must not put a request behind every redraw.
  assert.equal(await speechConfigured(api), false);
  assert.equal(calls, 1, 'the answer is asked for once, not once per paint');
}

/* Failing open is the deliberate direction. Being wrongly hopeful costs one
   take; being wrongly discouraging would hide a capability that works. */
{
  const {speechConfigured: fresh} = await import(
    `../static/orena/ui/voice-response.js?probe=${Date.now()}`
  );
  const api = {speechStatus: async () => { throw new Error('offline'); }};
  assert.equal(await fresh(api), true, 'an unreadable check must not disable a working recorder');
}
// A caller that cannot answer at all is the same case, and must not throw
// inside the mount and take the recorder down with it.
assert.equal(await speechConfigured({}), true);
assert.equal(await speechConfigured(undefined), true);

// Both rooms that invite a take consult it, and both say the same thing.
for (const path of ['static/orena/ui/voice-response.js', 'static/orena/ui/conversation.js'])
  assert.ok(
    readSrc(path).includes('speechConfigured(api)'),
    `${path} invites a take without asking whether one is possible`,
  );
for (const ui of ['en', 'zh'])
  assert.ok(copy[ui].voiceUnavailable, `${ui}: no truthful line for an absent speech service`);

console.log('Voice interaction: explicit upload, playback, account evidence, draft preservation, late-permission cleanup, and a stated speech boundary EN/ZH PASS');
