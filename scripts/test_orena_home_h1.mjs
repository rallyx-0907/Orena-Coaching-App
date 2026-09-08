/* Orena Golden Home H1 contract.
 *
 * The eight things H1 has to be able to prove (H1 brief §14):
 *
 *   1. server Continue Learning wins over the local Listening resume
 *   2. nothing on Home is fabricated - no invented progress or counts
 *   3. World availability and counts come from real content mapping
 *   4. one failing optional section does not blank Home
 *   5. Home renders in EN and ZH
 *   6. Home no longer contains Writing dashboard analytics
 *   7. product components receive semantic data, not page markup
 *   8. the 390 composition contract holds and nothing is desktop-only
 */

import assert from 'node:assert/strict';
import fs from 'node:fs';
import {api} from '../static/becoming/api.js';
import {state} from '../static/becoming/store.js';
import {renderHome} from '../static/becoming/screens/home.js';
import {rememberMediaLesson} from '../static/becoming/domain/media-lesson-history.js';
import {availableWorlds, durationMinutes, homeContinuation, serverListeningContinuation} from '../static/becoming/domain/home-model.js';
import {challengeCard, worldCard, journeyHero, recommendationTile} from '../static/becoming/orena/product-components.js';

/* ------------------------------------------------------------ fake DOM --- */

class FakeElement{
  constructor(){this.dataset={};this.listeners={};this.classList={add(){},remove(){},toggle(){}};this.style={};}
  addEventListener(name,listener){this.listeners[name]=listener;}
  removeEventListener(){}
  async click(){return this.listeners.click?.({currentTarget:this});}
  querySelector(){return null;}
}

function homeRoot(){
  return {
    innerHTML:'',
    nodes:new Map(),
    querySelector(selector){
      if(!this.nodes.has(selector))this.nodes.set(selector,new FakeElement());
      return this.nodes.get(selector);
    },
    querySelectorAll(selector){
      const name=selector.replace(/^\[|\]$/g,'').split('=')[0];
      if(!this.innerHTML.includes(name))return [];
      const button=this.nodes.get(selector)||new FakeElement();
      this.nodes.set(selector,button);
      return [button];
    },
    insertAdjacentHTML(_position,html){this.innerHTML+=String(html||'');},
  };
}

const storage=new Map();
globalThis.localStorage={getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,String(value)),removeItem:key=>storage.delete(key)};
const session=new Map();
globalThis.sessionStorage={getItem:key=>session.get(key)??null,setItem:(key,value)=>session.set(key,String(value)),removeItem:key=>session.delete(key)};
globalThis.document={querySelector:()=>null,querySelectorAll:()=>[],addEventListener(){},removeEventListener(){},body:{classList:{add(){},remove(){}}}};
globalThis.window={dispatchEvent(){},setInterval(){return 1;},clearInterval(){}};
globalThis.location={hash:'#/home'};
globalThis.HashChangeEvent=class {};

/* ----------------------------------------------------------- fixtures --- */

const LESSON={
  lesson_id:'en-daily-pen-in-my-bag',
  title:'A pen in my bag',
  description:'A quick everyday exchange about finding a pen.',
  duration_ms:8547,
  artwork:'daily-life',
  poster_url:'',
  source:{source_url:'https://example.invalid/pen'},
};
const OTHER_LESSON={
  lesson_id:'en-travel-rainy-day-taxi',
  title:'A rainy day taxi',
  description:'Getting a taxi in the rain.',
  duration_ms:41000,
  artwork:'travel',
  poster_url:'',
  source:{source_url:'https://example.invalid/taxi'},
};

const LIBRARY={
  items:[LESSON,OTHER_LESSON],
  sections:[
    {id:'continue-learning',item_ids:['en-daily-pen-in-my-bag']},
    {id:'recommended',item_ids:['en-travel-rainy-day-taxi','en-daily-pen-in-my-bag']},
  ],
  resume:{'en-daily-pen-in-my-bag':{lesson_id:'en-daily-pen-in-my-bag',segment_id:'segment-002',presentation:'checked',checked_attempt_count:3,best_exact:false}},
};

const WORLDS={
  language:'en',
  worlds:[
    {world_id:'en-daily-life',learning_language:'en',title:{en:'Daily Life',zh:'日常生活',vi:'Đời sống'},description:{en:'Ordinary days.',zh:'平常的日子。',vi:'Ngày thường.'},artwork:'daily-life',accent_family:'listening',topics:['daily-life'],available:true,lesson_count:1,lead_lesson_id:'en-daily-pen-in-my-bag',lead_lesson_title:'A pen in my bag',lead_lesson_source_url:'https://example.invalid/pen',lead_lesson_poster_url:''},
    {world_id:'en-stories-media',learning_language:'en',title:{en:'Stories & Media',zh:'故事',vi:'Chuyện'},description:{en:'Scenes.',zh:'场景。',vi:'Cảnh.'},artwork:'stories',accent_family:'speaking',topics:['stories'],available:false,lesson_count:0,lead_lesson_id:'',lead_lesson_title:'',lead_lesson_source_url:'',lead_lesson_poster_url:''},
  ],
  available_count:1,
};

const original={...api};

function resetApis({library=LIBRARY,worlds=WORLDS}={}){
  api.dashboard=async()=>({essay_count:0,streak:0,metrics:{}});
  api.essays=async()=>[];
  api.learningMemory=async()=>({strengths:[],revision_wins:[]});
  api.practiceRecommendation=async()=>null;
  api.practiceOutcomes=async()=>({items:[],latest:null});
  api.readingSessions=async()=>({items:[]});
  api.speakingAttempts=async()=>({items:[]});
  api.crossSkillCue=async()=>null;
  api.libraryVocabulary=async()=>({items:[]});
  api.listeningLibrary=async()=>{ if(library instanceof Error)throw library; return library; };
  api.worlds=async()=>{ if(worlds instanceof Error)throw worlds; return worlds; };
}

function cleanState(language='en'){
  state.language=language;
  state.supportLanguage=language;
  state.me={id:`h1-${language}`};
  state.draft={mode:'free',topic:'random',level:'B2',length:150,prompt:'',text:'',html:'',generatedTask:null,practiceContext:null,parentEssayId:null,savedAt:null};
  storage.clear();
  session.clear();
}

try{

/* 1 — server Continue Learning wins over the local Listening resume -------- */
{
  resetApis();
  cleanState('en');
  // A local resume exists and points somewhere ELSE. The durable server signal
  // must win, because it is the one that survives a different device.
  rememberMediaLesson({learning_language:'en',source_url:'https://example.invalid/local-only',lesson_id:'en-travel-rainy-day-taxi',title:'A local-only lesson',selected_segment_id:'segment-009',mode:'shadowing'});
  const root=homeRoot();
  await renderHome(root);
  assert.match(root.innerHTML,/data-home-continue-source="server"/,
    'the durable server continuation must own the continue card');
  assert.doesNotMatch(root.innerHTML,/data-home-continue-source="local"/,
    'the local resume must not also render a competing continuation');
  assert.match(root.innerHTML,/data-journey-id="en-daily-pen-in-my-bag"/,
    'the continue card must name the lesson the server says was in progress');
  assert.doesNotMatch(root.innerHTML,/A local-only lesson/,
    'the local guess must not appear once the server has a real answer');

  // With no server progress, the local resume is still a true statement and
  // remains the fallback rather than being deleted.
  resetApis({library:{items:[],sections:[],resume:{}}});
  const fallback=homeRoot();
  await renderHome(fallback);
  assert.match(fallback.innerHTML,/data-home-continue-source="local"/,
    'without server progress the local resume is the honest fallback');

  // Model level, independent of any rendering.
  assert.equal(serverListeningContinuation(LIBRARY)?.lessonId,'en-daily-pen-in-my-bag');
  assert.equal(serverListeningContinuation({items:[],sections:[],resume:{}}),null);
  assert.equal(homeContinuation({library:null,hasWritingDraft:false}),null,
    'no data means no continuation, not an invented one');
}

/* 2 — nothing fabricated -------------------------------------------------- */
{
  resetApis();
  cleanState('en');
  const root=homeRoot();
  await renderHome(root);

  /* The continuation is the one place a fake "62%" would be most tempting. The
     resume contract carries a lesson and a segment, so the card carries a
     lesson and a segment. The listening-goal meter elsewhere on the page is a
     different thing: the learner set that goal and the minutes are recorded. */
  const continueCard=root.innerHTML.slice(
    root.innerHTML.indexOf('data-oc-component="continue-journey"'),
    root.innerHTML.indexOf('</article>'));
  assert.ok(continueCard.length>0,'the continuation card should be present for this fixture');
  assert.doesNotMatch(continueCard,/%/,
    'the continuation must not claim a completion percentage: no contract supplies one');
  assert.doesNotMatch(continueCard,/oc-meter/,
    'the continuation must not render a progress meter it cannot fill truthfully');
  assert.doesNotMatch(root.innerHTML,/Episode \d+/i,
    'Home must not invent episode numbers');
  assert.doesNotMatch(root.innerHTML,/\[object Object\]|undefined|NaN/,
    'Home must never render a malformed value');

  // A lesson with no real duration gets no duration, not a plausible zero.
  assert.equal(durationMinutes({duration_ms:0}),null);
  assert.equal(durationMinutes({}),null);
  resetApis({library:{items:[{...LESSON,duration_ms:0}],sections:[{id:'recommended',item_ids:[LESSON.lesson_id]}],resume:{}}});
  const noDuration=homeRoot();
  await renderHome(noDuration);
  const card=noDuration.innerHTML.slice(
    noDuration.innerHTML.indexOf('data-oc-component="discovery-card"'),
    noDuration.innerHTML.indexOf('data-oc-component="discovery-card"')+1200);
  assert.doesNotMatch(card,/min</,'an unknown duration renders no duration at all');

  // A resume record whose lesson is not in the payload is not renderable.
  assert.equal(serverListeningContinuation({items:[],sections:[{id:'continue-learning',item_ids:['ghost']}],resume:{ghost:{segment_id:'s1'}}}),null,
    'a continue id with no matching item must not become a card');
}

/* 3 — world availability and counts come from real content mapping --------- */
{
  const worlds=availableWorlds(WORLDS,{locale:'en'});
  assert.equal(worlds.length,1,'only worlds the server measured as available are shown');
  assert.equal(worlds[0].worldId,'en-daily-life');
  assert.equal(worlds[0].lessonCount,1,'the count is the measured one');
  assert.equal(worlds[0].leadLessonId,'en-daily-pen-in-my-bag');
  assert.deepEqual(
    availableWorlds({worlds:[{world_id:'x',available:true,lesson_count:0,title:{en:'X'},description:{en:''}}]},{locale:'en'}),
    [],
    'available with a zero count is a contradiction and must render nothing');

  resetApis();
  cleanState('en');
  const root=homeRoot();
  await renderHome(root);
  assert.match(root.innerHTML,/data-world-id="en-daily-life"/,'the available world renders');
  assert.doesNotMatch(root.innerHTML,/data-world-id="en-stories-media"/,
    'an editorial world with no real lesson must not be offered');
  assert.match(root.innerHTML,/data-world-lesson="en-daily-pen-in-my-bag"/,
    'entering a world must hand off to a real lesson');
}

/* 4 — one failing section does not blank Home ------------------------------ */
{
  for(const failure of ['worlds','listening','both']){
    resetApis({
      worlds:failure==='listening'?WORLDS:new Error('worlds down'),
      library:failure==='worlds'?LIBRARY:new Error('library down'),
    });
    cleanState('en');
    // A real local draft must survive every remote failure.
    state.draft={...state.draft,html:'<p>Real unsaved work.</p>'};
    const root=homeRoot();
    await renderHome(root);
    assert.match(root.innerHTML,/data-oc-component="journey-hero"/,
      `${failure}: the hero must survive`);
    if(failure==='worlds'){
      // The listening library answered, so its durable progress rightly owns
      // the continuation; what matters is that Worlds failing changed nothing.
      assert.match(root.innerHTML,/data-home-continue-source="server"/,
        `${failure}: a Worlds failure must not disturb the real continuation`);
    }else{
      assert.match(root.innerHTML,/data-home-continue-source="draft"/,
        `${failure}: a real writing draft must survive a network failure`);
    }
    assert.match(root.innerHTML,/data-oc-section="for-you"/,
      `${failure}: For You must still render`);
    assert.match(root.innerHTML,/data-home-listening-habit/,
      `${failure}: the Challenge section must still offer its local-state action`);
    if(failure!=='worlds'){
      assert.match(root.innerHTML,/data-oc-section="worlds"/,
        `${failure}: a failed Worlds section keeps its own scoped state`);
    }
  }
}

/* 5 — EN and ZH both render ------------------------------------------------ */
{
  for(const language of ['en','zh']){
    resetApis();
    cleanState(language);
    const root=homeRoot();
    await renderHome(root);
    assert.match(root.innerHTML,/data-oc-component="journey-hero"/,`${language} hero renders`);
    assert.match(root.innerHTML,/data-oc-section="worlds"/,`${language} worlds render`);
    assert.match(root.innerHTML,/data-oc-section="continue-exploring"/,`${language} discovery renders`);
    assert.doesNotMatch(root.innerHTML,/\[object Object\]|undefined/,`${language} renders no malformed value`);
    if(language==='zh'){
      // CJK gets its own typography class rather than Latin display tricks.
      assert.match(root.innerHTML,/class="oc-hero-title cjk"/,'ZH hero uses CJK typography');
    }
  }
}

/* 6 — Home is not a dashboard --------------------------------------------- */
{
  resetApis();
  cleanState('en');
  const root=homeRoot();
  await renderHome(root);
  for(const forbidden of [
    /class="writing-dashboard/,
    /o-stages/,
    /home\.latest_score|Latest score/,
    /Insight of the day/,
    /Recent drafts/,
    /skill radar|Weekly chart|Monthly trend/i,
  ]){
    assert.doesNotMatch(root.innerHTML,forbidden,`Home must not contain ${forbidden}`);
  }
  const source=fs.readFileSync(new URL('../static/becoming/screens/home.js',import.meta.url),'utf8');
  assert.doesNotMatch(source,/metricOverview|writingDashboardMarkup|streakCard/,
    'the dashboard renderers must be gone from Home, not merely hidden');
}

/* 7 — product components take semantic data -------------------------------- */
{
  // No component accepts a layout decision, and none emits one.
  const world=worldCard({worldId:'w',title:'T',description:'D',artwork:'a',accentFamily:'listening',countLabel:'1 lesson',variant:'featured'});
  const hero=journeyHero({title:'T',supportingText:'S',primaryAction:{id:'homePrimary',label:'Go'}});
  const tile=recommendationTile({contentKind:'k',title:'T',subtitle:'S',actionLabel:'Go',actionAttributes:{'data-x':'1'}});
  for(const [name,markup] of [['worldCard',world],['journeyHero',hero],['recommendationTile',tile]]){
    assert.doesNotMatch(markup,/style="[^"]*(?:width|grid-template|column|flex-basis)/,
      `${name} must not emit layout decisions; composition belongs to CSS`);
    assert.doesNotMatch(markup,/\d+px/,`${name} must not emit pixel values`);
  }
  // A component escapes what it is given rather than trusting a fragment.
  assert.doesNotMatch(worldCard({worldId:'w',title:'<img src=x onerror=1>'}),/<img src=x/,
    'semantic text props must be escaped');
  // Attribute pass-through only accepts data attributes.
  assert.doesNotMatch(recommendationTile({title:'T',attributes:{onclick:'alert(1)'}}),/onclick/,
    'only data-* attributes may pass through a component');
  // The backend contract carries no layout keys.
  const worldKeys=Object.keys(WORLDS.worlds[0]);
  for(const key of worldKeys){
    assert.doesNotMatch(key,/column|width|pixel|span|layout/i,
      `the world contract must stay semantic, found ${key}`);
  }
}

/* 8 — 390 composition, and nothing desktop-only ---------------------------- */
{
  resetApis();
  cleanState('en');
  const root=homeRoot();
  await renderHome(root);
  // Source order IS the mobile order: the narrow layout is the stacked default
  // and wider viewports opt into simultaneous visibility.
  const order=['journey-hero','continue-journey','data-oc-section="worlds"','data-oc-section="for-you"','data-oc-section="challenge"','data-oc-section="continue-exploring"'];
  let cursor=-1;
  for(const marker of order){
    const at=root.innerHTML.indexOf(marker);
    assert.ok(at>cursor,`390 order broken at ${marker}`);
    cursor=at;
  }
  const css=fs.readFileSync(new URL('../static/becoming/orena/product-components.css',import.meta.url),'utf8');
  assert.match(css,/@media \(max-width:639px\)/,'a deliberate mobile composition must exist');
  assert.match(css,/--oc-touch-min:44px/,'touch targets must meet the 44px minimum');
  assert.match(css,/overflow-x:auto/,'wide rails must scroll inside themselves, not the page');
  assert.match(css,/@media \(prefers-reduced-motion:reduce\)/,'reduced motion must be honoured');
  assert.match(css,/@media \(hover:hover\)/,'hover affordances must not be required on touch');
  // The v2 namespace must not leak onto screens that have not migrated.
  const leaked=css.split('\n').filter(line=>/^[.#a-zA-Z\[]/.test(line)&&!line.includes('[data-orena-ui="v2"]')&&!line.startsWith('@')&&!line.startsWith('html[data-theme'));
  assert.deepEqual(leaked,[],`every v2 rule must stay inside the namespace, found: ${leaked.join(' | ')}`);
}

console.log('Orena Golden Home H1 contract: PASS');

/* ================================================================ H1.1 ==== */

/* 9 — every canonical practice-outcome status renders, with its handoffs ---- */
{
  /* The authority is derive_practice_outcome() in
     writing_coach/becoming_outcomes.py. If that function grows a status, this
     list is where the frontend finds out. */
  const CANONICAL=['improved','transferred','held','still_working','needs_attention','not_observed','needs_more_evidence'];
  for(const status of CANONICAL){
    resetApis();
    cleanState('en');
    api.practiceOutcomes=async()=>({items:[],latest:{
      status,
      issue_count:1,
      previous_issue_count:2,
      revision_no:2,
      essay_id:412,
      focus_label:'Agreement practice',
      grammar_id:'a1-complete-sentences-and-basic-word-order',
      error_evidence:['I has a book'],
    }});
    const root=homeRoot();
    await renderHome(root);
    assert.match(root.innerHTML,new RegExp(`data-practice-outcome-status="${status}"`),
      `${status} is a real backend status and must render on Home`);
    // The Grammar handoff must survive every status, with its lineage intact.
    assert.match(root.innerHTML,/data-home-practice-grammar="a1-complete-sentences-and-basic-word-order"/,
      `${status} must keep the Grammar practice handoff`);
    assert.match(root.innerHTML,/data-home-practice-evidence="I has a book"/,
      `${status} must carry the learner's own sentence into Write`);
    assert.match(root.innerHTML,/data-home-practice-essay="412"/,
      `${status} must preserve the parent essay lineage`);
    assert.match(root.innerHTML,/data-home-open-review="412"/,
      `${status} must still link to the review it came from`);
    assert.doesNotMatch(root.innerHTML,new RegExp(`outcome\\.${status}\\.`),
      `${status} must have real copy, not a raw translation key`);
    assert.doesNotMatch(root.innerHTML,/\[object Object\]|undefined/);
  }

  // A status no backend emits is still refused.
  for(const invented of ['partial','regressed','unchanged','mastered']){
    resetApis();
    cleanState('en');
    api.practiceOutcomes=async()=>({items:[],latest:{
      status:invented,issue_count:0,revision_no:2,essay_id:412,grammar_id:'g1',error_evidence:['x'],
    }});
    const root=homeRoot();
    await renderHome(root);
    assert.doesNotMatch(root.innerHTML,/data-practice-outcome-status/,
      `${invented} is not a backend status and must not render`);
  }

  // An outcome with no grammar link keeps the review link and loses only the
  // action it cannot perform.
  resetApis();
  cleanState('en');
  api.practiceOutcomes=async()=>({items:[],latest:{
    status:'held',issue_count:0,revision_no:2,essay_id:99,focus_label:'Tone',error_evidence:[],
  }});
  const noGrammar=homeRoot();
  await renderHome(noGrammar);
  assert.match(noGrammar.innerHTML,/data-practice-outcome-status="held"/);
  assert.doesNotMatch(noGrammar.innerHTML,/data-home-practice-grammar/);
  assert.match(noGrammar.innerHTML,/data-home-open-review="99"/);
}

/* 10 — an empty learner gets discovery, not a wall of placeholders --------- */
{
  resetApis();
  cleanState('en');
  const root=homeRoot();
  await renderHome(root);

  for(const placeholder of [
    /data-home-next-plan/,
    /data-review-cue-state/,
    /data-cross-skill-state/,
    /data-home-library-review-state/,
  ]){
    assert.doesNotMatch(root.innerHTML,placeholder,
      `a learner with no history must not be shown ${placeholder}`);
  }
  // ...and gets real content to start on instead.
  assert.match(root.innerHTML,/data-content-kind="listening-lesson"/,
    'an empty For You must offer real starter lessons');
  assert.match(root.innerHTML,/A pen in my bag|A rainy day taxi/,
    'the starters must be real catalog lessons, not invented ones');
  // If the Challenge section is on the page at all, it holds a real challenge.
  const challengeAt=root.innerHTML.indexOf('data-oc-section="challenge"');
  if(challengeAt>=0){
    const challenge=root.innerHTML.slice(challengeAt,root.innerHTML.indexOf('</section>',challengeAt));
    assert.match(challenge,/data-oc-component="challenge-card"/,
      'a rendered Challenge section must contain a real challenge, not an empty box');
  }

  // With no catalog either, Home says so once rather than in five cards.
  resetApis({library:new Error('down'),worlds:new Error('down')});
  cleanState('en');
  const bare=homeRoot();
  await renderHome(bare);
  assert.doesNotMatch(bare.innerHTML,/data-home-next-plan|data-review-cue-state|data-cross-skill-state/,
    'no data still means no placeholder cards');
}

/* 11 — a lesson is never offered twice ------------------------------------- */
{
  resetApis();
  cleanState('en');
  const root=homeRoot();
  await renderHome(root);
  /* One id per rendered card: the continuation carries `data-journey-id`, and
     every tile and discovery card carries `data-content-id`. */
  const ids=[...root.innerHTML.matchAll(/data-(?:content|journey)-id="([^"]+)"/g)]
    .map(match=>match[1])
    .filter(id=>id&&id!=='writing-draft');
  const seen=new Set();
  for(const id of ids){
    assert.ok(!seen.has(id),`lesson ${id} was surfaced twice on Home`);
    seen.add(id);
  }
  assert.ok(seen.size>0,'this fixture should surface at least one lesson');
  assert.ok(seen.has('en-daily-pen-in-my-bag'),'the continuation lesson should be one of them');

  /* The continuation's lesson must not reappear as a tile or a discovery card
     below it, and neither must whatever For You suggested. */
  const cardCount=id=>(root.innerHTML.match(new RegExp(`data-(?:content|journey)-id="${id}"`,'g'))||[]).length;
  assert.equal(cardCount('en-daily-pen-in-my-bag'),1,
    'the continuation lesson must appear on exactly one card');
  assert.equal(cardCount('en-travel-rainy-day-taxi'),1,
    'the For You suggestion must not reappear in Continue Exploring');
}

/* 12 — sections load independently ----------------------------------------- */
{
  // The listening library never settles. Everything else must still render,
  // and the first paint must not have waited for it.
  resetApis();
  cleanState('en');
  let painted='';
  api.listeningLibrary=()=>new Promise(()=>{});
  const root=homeRoot();
  // A short budget so this deliberately-unresolved request does not leave a
  // live timer running for the rest of the test process; renderHome's own
  // section-budget race (H1.2) is what makes that timer bounded at all.
  const pending=renderHome(root,{sectionBudgetMs:50});
  await new Promise(resolve=>setTimeout(resolve,0));
  painted=root.innerHTML;
  assert.match(painted,/data-oc-component="journey-hero"/,
    'the hero must paint before any request resolves');
  assert.match(painted,/data-oc-section="continue-exploring"[^>]*data-section-state="loading"/,
    'a section still waiting must say so rather than claim to be empty');

  // Let the other groups settle; the stalled one stays in its own loading state.
  await new Promise(resolve=>setTimeout(resolve,20));
  assert.match(root.innerHTML,/data-oc-section="worlds"[^>]*data-section-state="ready"/,
    'Worlds must not wait for the listening library');
  assert.match(root.innerHTML,/data-world-id="en-daily-life"/);
  assert.match(root.innerHTML,/data-oc-section="continue-exploring"[^>]*data-section-state="loading"/,
    'the stalled section keeps its own state');
  void pending;

  // A section that fails says it failed; a section that succeeds with nothing
  // says it is empty. Those are different states.
  resetApis({library:new Error('library down')});
  cleanState('en');
  const failed=homeRoot();
  await renderHome(failed);
  assert.match(failed.innerHTML,/data-oc-section="continue-exploring"[^>]*data-section-state="error"/);
  resetApis({library:{items:[],sections:[],resume:{}}});
  cleanState('en');
  const emptyLibrary=homeRoot();
  await renderHome(emptyLibrary);
  assert.match(emptyLibrary.innerHTML,/data-oc-section="continue-exploring"[^>]*data-section-state="ready"/);
}

/* 13 — interface language and content language are separate ---------------- */
{
  // English interface, Chinese learning language. The interface must stay
  // Latin; the lesson title must be Chinese.
  resetApis({library:{
    items:[{lesson_id:'zh-daily-what-is-this',title:'这是什么？',description:'一段简短的日常对话。',duration_ms:9000,artwork:'conversations',poster_url:'',source:{source_url:'https://example.invalid/zh'}}],
    sections:[{id:'recommended',item_ids:['zh-daily-what-is-this']}],
    resume:{},
  }});
  cleanState('zh');
  state.supportLanguage='en';
  const mixed=homeRoot();
  await renderHome(mixed);
  const heroTitle=mixed.innerHTML.match(/<h1 class="oc-hero-title([^"]*)"/)?.[1]||'';
  assert.doesNotMatch(heroTitle,/cjk/,
    'an English interface must not take CJK typography because the learner studies Chinese');
  assert.match(mixed.innerHTML,/<h3 class="oc-tile-title cjk" lang="zh-Hans">这是什么？/,
    'a Chinese lesson title must carry its own language inside an English interface');

  // Chinese interface, English learning language: the mirror image.
  resetApis();
  cleanState('en');
  state.supportLanguage='zh';
  const zhUi=homeRoot();
  await renderHome(zhUi);
  assert.match(zhUi.innerHTML,/<h1 class="oc-hero-title cjk">/,
    'a Chinese interface takes CJK typography for interface copy');
  assert.match(zhUi.innerHTML,/class="oc-tile-title" lang="en"/,
    'an English lesson title stays English inside a Chinese interface');
  state.supportLanguage='en';
}

/* 14 — the component API is semantic, with no raw-markup escape hatch ------ */
{
  /* Behavioural, not textual: raw markup handed to a component must not reach
     the page, whatever the prop is called. */
  for(const hatch of ['bodyHtml','secondaryActions','innerHtml','html']){
    const injected=recommendationTile({title:'T',[hatch]:'<b data-injected>x</b>'});
    assert.doesNotMatch(injected,/data-injected/,
      `${hatch} must not be an accepted raw-markup escape hatch`);
    const injectedChallenge=challengeCard({title:'T',[hatch]:'<b data-injected>x</b>'});
    assert.doesNotMatch(injectedChallenge,/data-injected/,
      `${hatch} must not be an accepted raw-markup escape hatch on a challenge`);
  }
  const homeSource=fs.readFileSync(new URL('../static/becoming/screens/home.js',import.meta.url),'utf8');
  assert.ok(!homeSource.includes('crossSkillCueMarkup'),
    'Home must render cross-skill through Orena components, not legacy card markup');
  assert.ok(homeSource.includes('normalizeCrossSkillCue'),
    'Home must reuse the shared cross-skill validator rather than fork its logic');
  assert.ok(!homeSource.includes('oc-legacy-slot'),
    'the legacy markup slot must be gone');

  // Semantic quote/note/link props render, and escape.
  const tile=recommendationTile({
    contentKind:'k', title:'T', quote:'<script>x</script>',
    note:{text:'n', attributes:{'data-practice-difficulty':''}},
    links:[{label:'L', attributes:{'data-home-open-review':'7'}}],
  });
  assert.match(tile,/<blockquote class="oc-quote"/);
  assert.doesNotMatch(tile,/<script>/,'a quote is text, and is escaped as text');
  assert.match(tile,/data-practice-difficulty/);
  assert.match(tile,/class="oc-link" data-home-open-review="7"/);
  assert.doesNotMatch(recommendationTile({title:'T',links:[{label:'L',attributes:{onclick:'alert(1)'}}]}),/onclick/,
    'a link may only carry data attributes');
}

console.log('Orena Home H1.1 audit contract: PASS');

/* ================================================================ H1.2 ==== */

/* 15 — a local resume must not compete with the server's Listening continuation */
{
  resetApis();
  cleanState('en');
  // The server owns the continuation (LESSON, via LIBRARY's continue-learning
  // section). A DIFFERENT lesson is also sitting in the per-device resume -
  // the exact shape that used to leak into Next Practice as a second,
  // competing "resume listening" card.
  rememberMediaLesson({learning_language:'en',source_url:OTHER_LESSON.source.source_url,lesson_id:OTHER_LESSON.lesson_id,title:OTHER_LESSON.title,selected_segment_id:'segment-001',mode:'follow'});
  const root=homeRoot();
  await renderHome(root);

  assert.match(root.innerHTML,/data-home-continue-source="server"/,
    'the server continuation must still own the Hero card');
  assert.doesNotMatch(root.innerHTML,/data-home-continue-source="local"/,
    'a local resume must not create a second continuation once the server owns one');
  assert.equal((root.innerHTML.match(/data-oc-component="continue-journey"/g)||[]).length,1,
    'exactly one continuation card may render, never two');
  assert.doesNotMatch(root.innerHTML,/data-home-next-plan/,
    'a local Listening resume must not surface as Next Practice once the server continuation owns Listening');

  // The local-resume lesson is still a real catalog lesson, so ordinary
  // discovery may still offer it - once, not as a disguised second resume.
  const localLessonCount=(root.innerHTML.match(new RegExp(`data-(?:content|journey)-id="${OTHER_LESSON.lesson_id}"`,'g'))||[]).length;
  assert.equal(localLessonCount,1,
    'the local-resume lesson still appears once through ordinary discovery, never as a competing continuation');
  assert.equal((root.innerHTML.match(new RegExp(`data-(?:content|journey)-id="${LESSON.lesson_id}"`,'g'))||[]).length,1,
    'the server continuation lesson must still appear exactly once');

  // Without any server continuation, the local resume remains the honest
  // fallback and next-plan is free to reach for it again.
  resetApis({library:{items:[],sections:[],resume:{}}});
  cleanState('en');
  rememberMediaLesson({learning_language:'en',source_url:OTHER_LESSON.source.source_url,lesson_id:OTHER_LESSON.lesson_id,title:OTHER_LESSON.title,selected_segment_id:'segment-001',mode:'follow'});
  const fallback=homeRoot();
  await renderHome(fallback);
  assert.match(fallback.innerHTML,/data-home-continue-source="local"/,
    'with no server progress the local resume is still the honest continuation');
}

/* 16 — Home stops repainting once it is no longer the active screen -------- */
{
  resetApis();
  cleanState('en');
  let resolveLibrary;
  api.listeningLibrary=()=>new Promise(resolve=>{resolveLibrary=resolve;});
  const root=homeRoot();
  const pending=renderHome(root,{sectionBudgetMs:30});
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.match(root.innerHTML,/data-oc-component="journey-hero"/,
    'Home paints normally while it is still the active screen');
  assert.equal(typeof root._cleanupScreen,'function',
    'Home must register the standard app.js screen-cleanup hook');

  // The learner navigates away. This is exactly what app.js's renderCurrent()
  // does: call the outgoing screen's cleanup, then render the next screen
  // into the SAME root.
  root._cleanupScreen();
  root.innerHTML='<section class="page" data-other-screen="write">Write</section>';

  // Home's deferred request now resolves, long after the navigation away.
  resolveLibrary(LIBRARY);
  await pending;
  await new Promise(resolve=>setTimeout(resolve,20));
  assert.equal(root.innerHTML,'<section class="page" data-other-screen="write">Write</section>',
    'a stale Home repaint must not overwrite the screen the learner navigated to');
}

/* 17 — renderHome resolves on its own budget, even if a provider never answers */
{
  resetApis();
  cleanState('en');
  api.listeningLibrary=()=>new Promise(()=>{}); // never settles, ever
  const root=homeRoot();
  const start=Date.now();
  await renderHome(root,{sectionBudgetMs:30});
  assert.ok(Date.now()-start<2000,
    'renderHome must resolve on a bounded budget rather than hang the render lifecycle on a provider that never answers');
}

/* 18 — For You separates "still loading" from "unavailable" from "empty" --- */
{
  // Personal and the rest settle with nothing to say; the listening library
  // has not answered yet. For You must say it is loading - the library could
  // still supply starter lessons - never that it is already empty.
  resetApis();
  cleanState('en');
  let resolveLibrary;
  api.listeningLibrary=()=>new Promise(resolve=>{resolveLibrary=resolve;});
  const root=homeRoot();
  const pending=renderHome(root,{sectionBudgetMs:5000});
  await new Promise(resolve=>setTimeout(resolve,10));
  assert.match(root.innerHTML,/data-oc-section="for-you"[^>]*data-section-state="loading"/,
    'For You must not claim to be empty while the listening library might still supply starters');
  resolveLibrary({items:[],sections:[],resume:{}});
  await pending;
  assert.match(root.innerHTML,/data-oc-section="for-you"[^>]*data-section-state="ready"/,
    'once both providers have genuinely answered with nothing, For You is a real empty state');

  // A real personal-provider outage is a different claim from a genuine empty
  // state, and must render as such - isolated here with an equally empty
  // library, since real starter content from the library would legitimately
  // fill For You regardless of the personal outage.
  resetApis({library:{items:[],sections:[],resume:{}}});
  cleanState('en');
  api.practiceRecommendation=async()=>{throw new Error('down');};
  api.practiceOutcomes=async()=>{throw new Error('down');};
  api.learningMemory=async()=>{throw new Error('down');};
  api.readingSessions=async()=>{throw new Error('down');};
  api.speakingAttempts=async()=>{throw new Error('down');};
  api.crossSkillCue=async()=>{throw new Error('down');};
  const failedRoot=homeRoot();
  await renderHome(failedRoot);
  assert.match(failedRoot.innerHTML,/data-oc-section="for-you"[^>]*data-section-state="error"/,
    'a total personal-provider outage must not read as "nothing personal yet"');
  assert.doesNotMatch(failedRoot.innerHTML,/data-oc-section="for-you"[^>]*data-section-state="ready"/,
    'an outage is not a ready state');

  // One of the six personal calls failing is still a partial answer, not an
  // outage: whatever the others returned is real and renders.
  resetApis();
  cleanState('en');
  api.crossSkillCue=async()=>{throw new Error('down');};
  api.practiceOutcomes=async()=>({items:[],latest:{status:'held',issue_count:0,revision_no:2,essay_id:5,focus_label:'Tone',error_evidence:[]}});
  const partial=homeRoot();
  await renderHome(partial);
  assert.match(partial.innerHTML,/data-practice-outcome-status="held"/,
    'one failing personal sub-request must not cost the others their real data');
}

/* 19 — a World's lead label keeps interface copy and content title apart --- */
{
  resetApis();
  cleanState('en');
  const root=homeRoot();
  await renderHome(root);
  const worldAt=root.innerHTML.indexOf('data-world-id="en-daily-life"');
  const world=root.innerHTML.slice(worldAt,root.innerHTML.indexOf('</article>',worldAt));
  assert.match(world,/<span class="oc-lead-prefix" lang="en">Start with<\/span>/,
    'the lead label\'s UI-language prefix must render as interface copy');
  assert.match(world,/<span class="oc-lead-title" lang="en">A pen in my bag<\/span>/,
    'the lead label\'s lesson title must carry its own content-language lang attribute');

  resetApis({library:{
    items:[{lesson_id:'zh-daily-what-is-this',title:'这是什么？',description:'一段简短的日常对话。',duration_ms:9000,artwork:'conversations',poster_url:'',source:{source_url:'https://example.invalid/zh'}}],
    sections:[{id:'recommended',item_ids:['zh-daily-what-is-this']}],
    resume:{},
  },worlds:{language:'en',worlds:[{...WORLDS.worlds[0],lead_lesson_id:'zh-daily-what-is-this',lead_lesson_title:'这是什么？',lead_lesson_source_url:'https://example.invalid/zh'}],available_count:1}});
  cleanState('zh');
  state.supportLanguage='en';
  const mixed=homeRoot();
  await renderHome(mixed);
  const mixedAt=mixed.innerHTML.indexOf('data-world-id="en-daily-life"');
  const mixedWorld=mixed.innerHTML.slice(mixedAt,mixed.innerHTML.indexOf('</article>',mixedAt));
  // An English interface studying Chinese: the prefix must not go CJK just
  // because the lesson title next to it is Chinese.
  assert.doesNotMatch(mixedWorld,/class="oc-lead-prefix[^"]*cjk/,
    'the UI-language prefix must never take on the content title\'s language');
  assert.match(mixedWorld,/class="oc-lead-title cjk" lang="zh-Hans">这是什么？/,
    'the lesson title keeps its own Chinese lang attribute inside an English interface');
  state.supportLanguage='en';
}

console.log('Orena Home H1.2 audit contract: PASS');

/* ================================================================ H1.3 ==== */

/* 20 — cleanup resolves renderHome immediately, and a stale result can never
   mutate shared learner state --------------------------------------------- */
{
  resetApis();
  cleanState('en');
  let resolveRecommendation;
  api.practiceRecommendation=()=>new Promise(resolve=>{resolveRecommendation=resolve;});
  state.memory=null;
  state.practiceRecommendation=null;
  state.latestPracticeOutcome=null;

  const root=homeRoot();
  const pending=renderHome(root,{sectionBudgetMs:5000});
  await new Promise(resolve=>setTimeout(resolve,10));
  assert.equal(typeof root._cleanupScreen,'function',
    'Home must register the standard app.js screen-cleanup hook');

  // The learner navigates away, and switches their learning language, before
  // the deferred personal request has answered at all.
  root._cleanupScreen();
  state.language='zh';
  root.innerHTML='<section class="page" data-other-screen="write">Write</section>';

  const disposalStart=Date.now();
  await pending;
  assert.ok(Date.now()-disposalStart<200,
    'cleanup must resolve renderHome immediately, not leave app.js waiting out the section budget');

  // The stale request resolves only now, long after cleanup and the language
  // switch.
  resolveRecommendation({
    language:'en',intent:'repair',focus_category:'grammar',focus_family:'grammar',
    target_level:'B2',task_type:'story',topic:'a real task',word_target:120,
  });
  await new Promise(resolve=>setTimeout(resolve,20));

  assert.equal(root.innerHTML,'<section class="page" data-other-screen="write">Write</section>',
    'a stale Home repaint must not overwrite the screen the learner navigated to');
  assert.equal(state.practiceRecommendation,null,
    'a stale personal result must not overwrite state.practiceRecommendation after cleanup');
  assert.equal(state.latestPracticeOutcome,null,
    'a stale personal result must not overwrite state.latestPracticeOutcome after cleanup');
  assert.equal(state.memory,null,
    'a stale personal result must not overwrite state.memory after cleanup');

  state.language='en';
}

/* 21 — a stale dashboard result is held to the same rule -------------------- */
{
  resetApis();
  cleanState('en');
  let resolveDashboard;
  api.dashboard=()=>new Promise(resolve=>{resolveDashboard=resolve;});
  state.dashboard=null;

  const root=homeRoot();
  const pending=renderHome(root,{sectionBudgetMs:5000});
  await new Promise(resolve=>setTimeout(resolve,10));
  root._cleanupScreen();
  root.innerHTML='<section class="page" data-other-screen="listen">Listen</section>';
  await pending;

  resolveDashboard({essay_count:9,streak:9,metrics:{}});
  await new Promise(resolve=>setTimeout(resolve,20));

  assert.equal(state.dashboard,null,
    'a stale dashboard result must not overwrite state.dashboard after cleanup');
}

/* 22 — the bounded provider budget still applies while Home stays active --- */
{
  resetApis();
  cleanState('en');
  api.listeningLibrary=()=>new Promise(()=>{}); // never settles, ever
  const root=homeRoot();
  const start=Date.now();
  await renderHome(root,{sectionBudgetMs:30});
  assert.ok(Date.now()-start<2000,
    'renderHome must still resolve on its own budget when Home never gets cleaned up at all');
}

console.log('Orena Home H1.3 audit contract: PASS');
}finally{
  Object.assign(api,original);
}
