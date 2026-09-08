import assert from 'node:assert/strict';
import {api} from '../static/becoming/api.js';
import {state,activateLanguage} from '../static/becoming/store.js';
import {renderHome} from '../static/becoming/screens/home.js';
import {renderLibrary} from '../static/becoming/screens/library.js';
import {t} from '../static/becoming/domain/i18n.js';

class FakeElement{
  constructor(){this.listeners={};this.dataset={};this.classList={add(){},remove(){},toggle(){}};this.style={};this.disabled=false;this.innerHTML='';}
  addEventListener(name,listener){this.listeners[name]=listener;}
  removeAttribute(){}
  setAttribute(){}
  async click(){return this.listeners.click?.({currentTarget:this});}
  scrollIntoView(){}
  focus(){}
}
function root(){
  return {innerHTML:'',nodes:new Map(),querySelector(selector){
    if(!this.nodes.has(selector))this.nodes.set(selector,new FakeElement());
    return this.nodes.get(selector);
  },querySelectorAll(){return [];},insertAdjacentHTML(_position,html){this.innerHTML+=String(html||'');}};
}

globalThis.document={querySelector:()=>null,querySelectorAll:()=>[],addEventListener(){},removeEventListener(){},body:{classList:{add(){},remove(){}}}};
globalThis.window={dispatchEvent(){},setInterval:()=>1,clearInterval(){}};
globalThis.location={hash:'#/home'};
globalThis.HashChangeEvent=class {};
const original={
  dashboard:api.dashboard,essays:api.essays,learningMemory:api.learningMemory,
  practiceRecommendation:api.practiceRecommendation,practiceOutcomes:api.practiceOutcomes,
  readingSessions:api.readingSessions,speakingAttempts:api.speakingAttempts,
  crossSkillCue:api.crossSkillCue,libraryVocabulary:api.libraryVocabulary,
};

const dueItems={items:[
  {word:'older',due:true,next_review_at:'2026-01-01T00:00:00+00:00',review_stage:1},
  {word:'earliest',due:true,next_review_at:'2025-01-01T00:00:00+00:00',review_stage:2},
],summary:{total:2,due:2,available:0}};
try{
  api.dashboard=async()=>({essay_count:0,streak:0,metrics:{}});
  api.essays=async()=>[];
  api.learningMemory=async()=>({strengths:[],revision_wins:[]});
  api.practiceRecommendation=async()=>({intent:'repair',focus_category:'grammar',focus_family:'grammar',target_level:'B2',task_type:'story',topic:'daily life',word_target:120});
  api.practiceOutcomes=async()=>({items:[],latest:null});
  api.readingSessions=async()=>({items:[]});
  api.speakingAttempts=async()=>({items:[]});
  api.crossSkillCue=async()=>null;
  api.libraryVocabulary=async()=>dueItems;
  state.me={id:'home-library-review'};
  state.dashboard={};
  for(const locale of ['en','zh']){
    state.language=locale;state.supportLanguage=locale;state.libraryReviewWord=null;
    const home=root();
    await renderHome(home);
    assert.match(home.innerHTML,/data-home-library-review-state="due"/,
      `${locale.toUpperCase()} Home should show a due Library review cue`);
    assert.match(home.innerHTML,/data-home-next-plan[^>]*data-plan-kind="writing"/,
      `${locale.toUpperCase()} due cue must not displace the R12 writing priority`);
    assert.match(home.innerHTML,/data-home-library-review-word="earliest"/,
      `${locale.toUpperCase()} Home should identify the earliest due item`);
    assert.ok(home.innerHTML.includes(t('home.library_review_due')),
      `${locale.toUpperCase()} Home should localize the due-review heading`);
    const expectedBody=t('home.library_review_body',{word:'earliest'}).replaceAll('"','&quot;');
    assert.ok(home.innerHTML.includes(expectedBody),
      `${locale.toUpperCase()} Home should localize the due-review body`);
    await home.querySelector('[data-home-library-review-action]').click();
    assert.equal(location.hash,'#/library',`${locale.toUpperCase()} cue should open Library`);
    assert.equal(state.libraryReviewWord,'earliest',`${locale.toUpperCase()} cue should hand off the earliest word`);
    assert.equal(state.libraryReviewLanguage,locale,`${locale.toUpperCase()} cue should retain its originating language`);

    const library=root();
    await renderLibrary(library);
    assert.match(library.innerHTML,/class="o-recall-slot [^"]*"/,
      `${locale.toUpperCase()} Library should render its existing recall slot`);
    assert.doesNotMatch(library.innerHTML,/id="recallSlot" class="o-recall-slot hidden"/,
      `${locale.toUpperCase()} handoff should open recall instead of leaving it hidden`);
    assert.match(library.innerHTML,/data-review-word="earliest"/,
      `${locale.toUpperCase()} handoff should target the linked due word`);
  }

  state.language='en';state.supportLanguage='en';state.libraryReviewWord='earliest';state.libraryReviewLanguage='en';
  activateLanguage('zh');
  assert.equal(state.libraryReviewWord,null,'changing language should clear a pending Library handoff word');
  assert.equal(state.libraryReviewLanguage,null,'changing language should clear a pending Library handoff locale');

  state.language='en';state.supportLanguage='en';state.libraryReviewWord='earliest';state.libraryReviewLanguage='en';
  api.libraryVocabulary=async()=>({items:[{word:'other',due:true,next_review_at:'2025-01-01T00:00:00+00:00',review_stage:1}],summary:{total:1,due:1,available:0}});
  const changed=root();
  await renderLibrary(changed);
  assert.match(changed.innerHTML,/id="recallSlot" class="o-recall-slot hidden"/,
    'a changed Library response should not auto-open a different due word');
  assert.equal(state.libraryReviewWord,null,'changed response should consume the stale handoff word');
  assert.equal(state.libraryReviewLanguage,null,'changed response should consume the stale handoff locale');

  for(const payload of [null,{items:{bad:true}},{items:[null,{},
    {word:'bad-date',due:true,next_review_at:'not-a-date'},
    {word:'future',due:false,next_review_at:'2020-01-01T00:00:00+00:00'}]}]){
    state.language='en';state.supportLanguage='en';state.libraryReviewWord=null;
    api.libraryVocabulary=async()=>payload;
    const home=root();
    await renderHome(home);
    /* H1.1: Home is discovery-first. Nothing due means no review card at all,
       which is both the truthful answer and the one that leaves the space to
       real content. What must never happen is a claim, and that is asserted. */
    assert.doesNotMatch(home.innerHTML,/data-home-library-review-state/,'invalid Library data should produce no review card');
    assert.doesNotMatch(home.innerHTML,/data-home-library-review-word|items due|items completed|due review count/i,
      'invalid Library data must not make a due-count or completion claim');
  }
  api.libraryVocabulary=async()=>{throw new Error('library unavailable');};
  const unavailable=root();
  await renderHome(unavailable);
  assert.doesNotMatch(unavailable.innerHTML,/data-home-library-review-state/,'unavailable Library data should produce no review card');
  assert.doesNotMatch(unavailable.innerHTML,/data-home-library-review-word|items due|items completed|due review count/i,
    'unavailable Library data must not make a due-count or completion claim');
  console.log('Home scheduled Library review handoff contract OK');
}finally{
  Object.assign(api,original);
}
