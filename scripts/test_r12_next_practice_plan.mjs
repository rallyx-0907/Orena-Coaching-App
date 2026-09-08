import assert from 'node:assert/strict';
import {api} from '../static/becoming/api.js';
import {state} from '../static/becoming/store.js';
import {renderHome} from '../static/becoming/screens/home.js';
import {t} from '../static/becoming/domain/i18n.js';
import {rememberMediaLesson} from '../static/becoming/domain/media-lesson-history.js';
import {clearSharedMediaSession,getSharedMediaSession,setSharedMediaSession} from '../static/becoming/domain/shared-media-session.js';
import {MEDIA_LEARNING_FIXTURE} from '../tests/fixtures/media-learning.js';

class FakeElement{
  constructor(){this.dataset={};this.listeners={};this.classList={add(){},remove(){},toggle(){}};this.style={};this.disabled=false;this.innerHTML='';this.textContent='';}
  addEventListener(name,listener){this.listeners[name]=listener;}
  removeAttribute(){}
  setAttribute(){}
  async click(){return this.listeners.click?.({currentTarget:this});}
}

function homeRoot(){
  const root={innerHTML:'',nodes:new Map(),querySelector(selector){
    if(!this.nodes.has(selector))this.nodes.set(selector,new FakeElement());
    return this.nodes.get(selector);
  },querySelectorAll(){return [];},insertAdjacentHTML(_position,html){this.innerHTML+=String(html||'');}};
  return root;
}

const storage=new Map();
globalThis.localStorage={getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,String(value)),removeItem:key=>storage.delete(key)};
globalThis.document={querySelector:()=>null,querySelectorAll:()=>[],addEventListener(){},removeEventListener(){},body:{classList:{add(){},remove(){}}}};
globalThis.window={dispatchEvent(){}};
globalThis.location={hash:'#/home'};
globalThis.HashChangeEvent=class {};

const original={dashboard:api.dashboard,essays:api.essays,learningMemory:api.learningMemory,practiceRecommendation:api.practiceRecommendation,practiceOutcomes:api.practiceOutcomes,libraryVocabulary:api.libraryVocabulary,nextPractice:api.nextPractice,readingSessions:api.readingSessions,readingSession:api.readingSession,speakingAttempts:api.speakingAttempts};
const baseReading={items:[{id:22,latest_attempt:{correct_count:4,total:4}}]};

async function renderPlan(language,{recommendation=null,reading=baseReading,speaking={items:[]}}={}){
  state.language=language;state.supportLanguage=language;state.me={id:`plan-${language}`};
  api.practiceRecommendation=typeof recommendation==='function'?recommendation:async()=>recommendation;
  api.readingSessions=typeof reading==='function'?reading:async()=>reading;
  api.speakingAttempts=typeof speaking==='function'?speaking:async()=>speaking;
  const root=homeRoot();
  await renderHome(root);
  return root;
}

try{
  api.dashboard=async()=>({});
  api.essays=async()=>[];
  api.learningMemory=async()=>({strengths:[],revision_wins:[]});
  api.practiceOutcomes=async()=>({items:[],latest:null});
  api.libraryVocabulary=async()=>[];
  storage.clear();clearSharedMediaSession('en');clearSharedMediaSession('zh');

  let generated=false;
  api.nextPractice=async payload=>{generated=payload;return {task_type:'story',topic:'a real task',target_level:'B2',word_target:120,prompt:'Write a real task.',personalization:{...recommendationEn,target_level:'B2'}};};
  const recommendationEn={language:'en',intent:'repair',focus_category:'grammar',focus_family:'grammar',target_level:'B2',task_type:'story',topic:'a real task',word_target:120};
  let root=await renderPlan('en',{recommendation:recommendationEn,reading:{items:[{id:22,latest_attempt:null}]},speaking:{items:[{asset_id:'asset-1',segment_id:'segment-1'}]}});
  assert.match(root.innerHTML,/data-home-next-plan[^>]*data-plan-kind="writing"/);
  await root.querySelector('[data-home-next-plan-action]').click();
  assert.equal(globalThis.location.hash,'#/write');
  assert.equal(generated.target_level,'B2');
  state.draft={...state.draft,text:'',html:'',prompt:'',generatedTask:null,savedAt:null};

  storage.clear();clearSharedMediaSession('zh');
  api.readingSession=async id=>({found:true,session:{id:Number(id),title:'A waiting reading',questions:[],passage:'',target_level:'B2'}});
  root=await renderPlan('zh',{recommendation:null,reading:{items:[{id:22,latest_attempt:null}]}});
  assert.match(root.innerHTML,/data-home-next-plan[^>]*data-plan-kind="reading"/);
  assert.ok(root.innerHTML.includes(t('home.next_plan_reading_title')));
  await root.querySelector('[data-home-next-plan-action]').click();
  assert.equal(globalThis.location.hash,'#/read');
  assert.equal(state.readingSession.id,22);

  storage.clear();clearSharedMediaSession('en');
  rememberMediaLesson({learning_language:'en',source_url:MEDIA_LEARNING_FIXTURE.asset.source_url,title:'Recent lesson',selected_segment_id:'segment-001',mode:'follow'});
  root=await renderPlan('en',{recommendation:null});
  /* H1.2: with no server continuation, the local resume becomes the Hero's
     own continuation card. It must not ALSO surface as a Next Practice tile
     for the same lesson - that would be a second, competing continuation. */
  assert.doesNotMatch(root.innerHTML,/data-home-next-plan/,
    'a local Listening resume is the continuation itself, not a second Next Practice tile');
  assert.match(root.innerHTML,/data-home-continue-source="local"/);
  await root.querySelector('[data-home-resume-listening]').click();
  assert.equal(globalThis.location.hash,'#/listen');

  storage.clear();clearSharedMediaSession('zh');
  setSharedMediaSession({learning_language:'zh',payload:{...MEDIA_LEARNING_FIXTURE,asset:{...MEDIA_LEARNING_FIXTURE.asset,asset_id:'asset-zh'}},selected_segment_id:'segment-002'});
  root=await renderPlan('zh',{recommendation:null,speaking:{items:[{asset_id:'asset-zh',segment_id:'segment-001'}]}});
  assert.match(root.innerHTML,/data-home-next-plan[^>]*data-plan-kind="speaking"/);
  await root.querySelector('[data-home-next-plan-action]').click();
  assert.equal(globalThis.location.hash,'#/speak');
  assert.equal(getSharedMediaSession('zh').selected_segment_id,'segment-001');

  clearSharedMediaSession('zh');
  setSharedMediaSession({learning_language:'zh',payload:{...MEDIA_LEARNING_FIXTURE,asset:{...MEDIA_LEARNING_FIXTURE.asset,asset_id:'asset-current'}},selected_segment_id:'segment-001'});
  root=await renderPlan('zh',{recommendation:null,speaking:{items:[{asset_id:'asset-other',segment_id:'segment-001'}]}});
  assert.doesNotMatch(root.innerHTML,/data-home-next-plan/,
    'no usable plan means no plan tile at all (H1.1: no placeholder cards)');
  assert.doesNotMatch(root.innerHTML,/data-home-next-plan-action/);

  state.readingSession={id:999,title:'Stale reading'};
  state.readingResult={score:100};
  api.readingSession=async()=>({found:false,session:null});
  root=await renderPlan('en',{recommendation:null,reading:{items:[{id:77,latest_attempt:null}]}});
  assert.match(root.innerHTML,/data-home-next-plan[^>]*data-plan-kind="reading"/);
  await root.querySelector('[data-home-next-plan-action]').click();
  assert.equal(state.readingSession,null);
  assert.equal(state.readingResult,null);
  assert.equal(globalThis.location.hash,'#/read');

  for(const language of ['en','zh']){
    storage.clear();clearSharedMediaSession(language);
    root=await renderPlan(language,{
      recommendation:null,
      reading:()=>{throw new Error('reading unavailable');},
      speaking:()=>Promise.reject(new Error('speaking unavailable')),
    });
    /* H1.1: Home is discovery-first when there is nothing to recommend. The
       plan tile is absent rather than present-and-empty, and nothing invents a
       number to fill the space. */
    assert.doesNotMatch(root.innerHTML,/data-home-next-plan/);
    assert.doesNotMatch(root.innerHTML,/data-home-next-plan-action/);
    assert.doesNotMatch(root.innerHTML,/100%|completed|streak/i);
  }

  for(const language of ['en','zh']){
    storage.clear();
    clearSharedMediaSession(language);
    api.practiceRecommendation=async()=>{throw new Error('recommendation unavailable');};
    root=await renderPlan(language,{recommendation:()=>{throw new Error('unused');},reading:{items:[{id:22,latest_attempt:{correct_count:4,total:4}}]},speaking:{items:[]}});
    assert.doesNotMatch(root.innerHTML,/data-home-next-plan/);
    assert.doesNotMatch(root.innerHTML,/data-home-next-plan-action/);

    storage.clear();
    clearSharedMediaSession(language);
    state.draft={...state.draft,text:'',html:'',prompt:'',generatedTask:null,savedAt:null};
    const recommendation={
      language,
      intent:'baseline',
      focus_category:'expression',
      focus_family:'expression',
      target_level:language==='zh'?'HSK4':'B2',
      task_type:language==='zh'?'hsk':'story',
      topic:language==='zh'?'random':'daily life',
      word_target:language==='zh'?80:150,
      goal:language==='zh'?'travel':'work',
      guidance_style:'guided',
      action_label:language==='zh'?'开始一次基线写作':'Create a baseline',
    };
    let baselinePayload=null;
    api.practiceRecommendation=async()=>recommendation;
    api.nextPractice=async payload=>{
      baselinePayload=payload;
      return {
        task_type:recommendation.task_type,
        topic:recommendation.topic,
        target_level:recommendation.target_level,
        word_target:recommendation.word_target,
        prompt:language==='zh'?'请写一段关于旅行计划的短文。':'Write a short draft about a useful everyday plan.',
        personalization:recommendation,
      };
    };
    globalThis.location.hash='#/home';
    root=await renderPlan(language,{recommendation,reading:{items:[{id:22,latest_attempt:{correct_count:4,total:4}}]},speaking:{items:[]}});
    assert.match(root.innerHTML,/data-home-next-plan[^>]*data-plan-kind="baseline"/);
    assert.ok(root.innerHTML.includes(t('home.next_plan_baseline_title')));
    assert.ok(root.innerHTML.includes(t('home.next_plan_baseline_body')));
    await root.querySelector('[data-home-next-plan-action]').click();
    assert.deepEqual(baselinePayload,{target_level:recommendation.target_level});
    assert.equal(state.draft.text,'');
    assert.equal(state.draft.html,'');
    assert.equal(state.draft.savedAt,null);
    assert.equal(state.draft.prompt,language==='zh'?'请写一段关于旅行计划的短文。':'Write a short draft about a useful everyday plan.');
    assert.equal(state.draft.practiceContext.goal,recommendation.goal);
    assert.equal(state.draft.practiceContext.guidance_style,'guided');
    assert.equal(globalThis.location.hash,'#/write');

    state.draft={...state.draft,text:'An unfinished learner draft.',html:'<p>An unfinished learner draft.</p>',prompt:'Keep writing this draft.',generatedTask:null,savedAt:1700000000000};
    let draftPayload=null;
    api.nextPractice=async payload=>{draftPayload=payload;throw new Error('must not generate over a draft');};
    globalThis.location.hash='#/home';
    root=await renderPlan(language,{recommendation,reading:{items:[{id:22,latest_attempt:{correct_count:4,total:4}}]},speaking:{items:[]}});
    assert.match(root.innerHTML,/data-home-next-plan[^>]*data-plan-kind="writing-draft"/);
    assert.ok(root.innerHTML.includes(t('home.next_plan_writing-draft_title')));
    await root.querySelector('[data-home-next-plan-action]').click();
    assert.equal(draftPayload,null);
    assert.equal(state.draft.text,'An unfinished learner draft.');
    assert.equal(state.draft.html,'<p>An unfinished learner draft.</p>');
    assert.equal(state.draft.prompt,'Keep writing this draft.');
    assert.equal(state.draft.savedAt,1700000000000);
    assert.equal(globalThis.location.hash,'#/write');

    state.draft={...state.draft,text:'',html:'',prompt:'',generatedTask:null,savedAt:null};
    api.nextPractice=async()=>{throw new Error('generation unavailable');};
    globalThis.location.hash='#/home';
    root=await renderPlan(language,{recommendation,reading:{items:[{id:22,latest_attempt:{correct_count:4,total:4}}]},speaking:{items:[]}});
    await root.querySelector('[data-home-next-plan-action]').click();
    assert.equal(globalThis.location.hash,'#/home');
    assert.match(root.innerHTML,/generation unavailable/);
  }
}finally{
  Object.assign(api,original);
}

console.log('R12 EN/ZH Home next-practice plan: PASS');
