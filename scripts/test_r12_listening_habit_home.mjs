import assert from 'node:assert/strict';
import {api} from '../static/becoming/api.js';
import {state} from '../static/becoming/store.js';
import {renderHome} from '../static/becoming/screens/home.js';
import {esc} from '../static/becoming/components/primitives.js';
import {t} from '../static/becoming/domain/i18n.js';
import {LISTEN_GOAL_KEY,LISTEN_TIME_KEY,listeningHabitSnapshot} from '../static/becoming/domain/listening-habit.js';

class FakeElement{
  constructor(){this.dataset={};this.listeners={};this.classList={add(){},remove(){},toggle(){}};this.style={};}
  addEventListener(name,listener){this.listeners[name]=listener;}
  removeEventListener(){}
  async click(){return this.listeners.click?.({currentTarget:this});}
}

function homeRoot(){
  const root={innerHTML:'',nodes:new Map(),querySelector(selector){
    if(!this.nodes.has(selector))this.nodes.set(selector,new FakeElement());
    return this.nodes.get(selector);
  },querySelectorAll(){return [];}};
  return root;
}


const storage=new Map();
let storageAvailable=true;
globalThis.localStorage={
  getItem:key=>{
    if(!storageAvailable)throw new Error('storage unavailable');
    return storage.get(key)??null;
  },
  setItem:(key,value)=>{
    if(!storageAvailable)throw new Error('storage unavailable');
    storage.set(key,String(value));
  },
  removeItem:key=>storage.delete(key),
};
globalThis.document={querySelector:()=>null,querySelectorAll:()=>[],addEventListener(){},removeEventListener(){},body:{classList:{add(){},remove(){}}}};
globalThis.window={dispatchEvent(){}};
globalThis.sessionStorage={getItem:()=>null,setItem(){},removeItem(){}};
globalThis.location={hash:'#/home'};
globalThis.HashChangeEvent=class {};
if(!globalThis.Element)globalThis.Element=Object;
if(!globalThis.HTMLIFrameElement)globalThis.HTMLIFrameElement=class {};

const original={dashboard:api.dashboard,essays:api.essays,learningMemory:api.learningMemory,practiceRecommendation:api.practiceRecommendation,practiceOutcomes:api.practiceOutcomes,libraryVocabulary:api.libraryVocabulary};
const today=new Date();
const day=(date)=>`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
const yesterday=new Date(today);yesterday.setDate(yesterday.getDate()-1);

try{
  api.dashboard=async()=>({});
  api.essays=async()=>[];
  api.learningMemory=async()=>({strengths:[],revision_wins:[]});
  api.practiceRecommendation=async()=>null;
  api.practiceOutcomes=async()=>({items:[],latest:null});
  api.libraryVocabulary=async()=>[];

  storage.clear();storageAvailable=true;
  state.language='en';state.supportLanguage='en';state.me={id:'habit-en'};
  storage.set(LISTEN_TIME_KEY,JSON.stringify({[day(today)]:1500,[day(yesterday)]:600}));
  storage.set(LISTEN_GOAL_KEY,JSON.stringify({daily:30}));
  const enSnapshot=listeningHabitSnapshot(today);
  assert.equal(enSnapshot.status,'ok');
  assert.equal(enSnapshot.today_seconds,1500);
  assert.equal(enSnapshot.week_seconds,2100);
  const enRoot=homeRoot();
  await renderHome(enRoot);
  assert.match(enRoot.innerHTML,/data-home-listening-habit[^>]*data-state="ok"/);
  assert.match(enRoot.innerHTML,/25 min today/);
  assert.match(enRoot.innerHTML,/30 min daily goal/);
  assert.match(enRoot.innerHTML,/This week: 35 min/);
  assert.match(enRoot.innerHTML,/Adjust Listening goal/);
  const enGoal=enRoot.querySelector('[data-home-listening-goal]');
  await enGoal.click();
  assert.equal(globalThis.location.hash,'#/listen');
  /* The other half of this handoff - that the Listening screen then exposes
     its goal editor - lives in test_r12_listening_goal_editor.mjs. It was
     split out because it fails on a Listening-screen harness gap that predates
     the Home migration, and keeping it here would have blocked the Home
     contract from entering CI. */

  storage.clear();storageAvailable=true;
  state.language='zh';state.supportLanguage='zh';state.me={id:'habit-zh'};
  storage.set(LISTEN_TIME_KEY,JSON.stringify({}));
  storage.set(LISTEN_GOAL_KEY,JSON.stringify({daily:40}));
  const zhRoot=homeRoot();
  await renderHome(zhRoot);
  assert.match(zhRoot.innerHTML,/data-home-listening-habit[^>]*data-state="ok"/);
  assert.ok(zhRoot.innerHTML.includes(t('home.listening_habit_title')));
  assert.ok(zhRoot.innerHTML.includes(t('home.listening_habit_action')));
  assert.match(zhRoot.innerHTML,/0[^<]*分钟/);

  storage.clear();storageAvailable=true;
  state.language='en';state.supportLanguage='en';state.me={id:'habit-malformed'};
  storage.set(LISTEN_TIME_KEY,JSON.stringify({today:'not-a-number'}));
  storage.set(LISTEN_GOAL_KEY,JSON.stringify({daily:40}));
  const malformedRoot=homeRoot();
  await renderHome(malformedRoot);
  assert.match(malformedRoot.innerHTML,/data-home-listening-habit[^>]*data-state="malformed"/);
  assert.ok(malformedRoot.innerHTML.includes(esc(t('home.listening_habit_malformed'))));
  assert.doesNotMatch(malformedRoot.innerHTML,/0 min today/);

  storage.clear();storageAvailable=true;
  state.language='zh';state.supportLanguage='zh';state.me={id:'habit-malformed-json'};
  storage.set(LISTEN_TIME_KEY,'not-json');
  const malformedJsonRoot=homeRoot();
  await renderHome(malformedJsonRoot);
  assert.match(malformedJsonRoot.innerHTML,/data-home-listening-habit[^>]*data-state="malformed"/);
  assert.ok(malformedJsonRoot.innerHTML.includes(esc(t('home.listening_habit_malformed'))));

  storage.clear();storageAvailable=false;
  state.language='zh';state.supportLanguage='zh';state.me={id:'habit-unavailable'};
  const unavailableRoot=homeRoot();
  await renderHome(unavailableRoot);
  assert.match(unavailableRoot.innerHTML,/data-home-listening-habit[^>]*data-state="unavailable"/);
  assert.ok(unavailableRoot.innerHTML.includes(esc(t('home.listening_habit_unavailable'))));
}finally{
  Object.assign(api,original);
}

console.log('R12 EN/ZH Listening habit Home snapshot: PASS');
