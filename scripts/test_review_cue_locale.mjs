import assert from 'node:assert/strict';
import {api} from '../static/becoming/api.js';
import {state} from '../static/becoming/store.js';
import {renderHome} from '../static/becoming/screens/home.js';
import {renderReview} from '../static/becoming/screens/review.js';
import {categoryLabel,statusLabel} from '../static/becoming/domain/i18n.js';

class FakeElement{
  constructor(){this.dataset={};this.listeners={};this.classList={add(){},remove(){},toggle(){}};this.innerHTML='';}
  addEventListener(name,fn){this.listeners[name]=fn;}
  removeEventListener(){}
  setAttribute(){}
  removeAttribute(){}
  focus(){}
  contains(){return false;}
  querySelector(){return null;}
}

function fakeRoot(){
  const root={innerHTML:'',nodes:new Map(),cueButtons:new Map(),insertAdjacentHTML(_where,html){this.innerHTML=html+this.innerHTML;}};
  root.querySelector=selector=>{
    if(!root.nodes.has(selector))root.nodes.set(selector,new FakeElement());
    return root.nodes.get(selector);
  };
  root.querySelectorAll=selector=>{
    if(selector==='[data-open-review-cue]'){
      const match=root.innerHTML.match(/data-open-review-cue="([^"]+)"/);
      if(!match)return [];
      if(!root.cueButtons.has(match[1])){
        const button=new FakeElement();button.dataset.openReviewCue=match[1];root.cueButtons.set(match[1],button);
      }
      return [root.cueButtons.get(match[1])];
    }
    return [];
  };
  return root;
}

globalThis.document={
  querySelector:()=>null,querySelectorAll:()=>[],addEventListener(){},removeEventListener(){},
  body:{classList:{add(){},remove(){}},style:{}},documentElement:{dataset:{},classList:{add(){},remove(){}}},
};
globalThis.window={getSelection:()=>null,requestAnimationFrame:fn=>fn(),setInterval:()=>1,clearInterval(){},dispatchEvent(){}};
globalThis.requestAnimationFrame=fn=>fn();
globalThis.localStorage={getItem:()=>null,setItem(){},removeItem(){}};
globalThis.location={hash:'#/home'};

api.dashboard=async()=>({essay_count:1,streak:0,metrics:{}});
api.essays=async()=>[{id:42,text:'I has a book',prompt:'Write a sentence',overall:60,revision_no:1,created_at:'2026-08-01T00:00:00+00:00'}];
api.libraryVocabulary=async()=>[];
api.practiceRecommendation=async()=>null;
api.practiceOutcomes=async()=>({items:[],latest:null});
api.essay=async()=>({id:42,text:'I has a book',html:'',prompt:'Write a sentence',overall:60,errors:[],strength_evidence:[]});
api.practiceOutcome=async()=>({outcome:null});

state.language='en';
state.profile={native_language:'en'};
for(const locale of ['en','vi','zh']){
  state.supportLanguage=locale;
  api.learningMemory=async()=>({patterns:[],strengths:[],focus:null,revision_wins:[],review_cue:{
    available:true,state:'unresolved',source:'error_memory',status:'watch',category:'grammar',
    evidence:'I has a book',essay_id:42,suggestion:'I am a book',total:2,
  }});
  const home=fakeRoot();
  await renderHome(home);
  assert.match(home.innerHTML,/data-review-cue-state="unresolved"/);
  assert.match(home.innerHTML,/I has a book/);
  assert.ok(home.innerHTML.includes(categoryLabel('grammar')));
  assert.ok(home.innerHTML.includes(statusLabel('watch')));
  assert.doesNotMatch(home.innerHTML,/\bwatch\b/,
    `Home ${locale.toUpperCase()} must localize the review-cue status`);
  const cueButton=home.querySelectorAll('[data-open-review-cue]')[0];
  assert.equal(cueButton?.dataset.openReviewCue,'42');
  await cueButton.listeners.click();
  assert.equal(state.lastEvaluation.id,42);

  state.lastEvaluation={id:42,text:'I has a book',prompt:'Write a sentence',target_cefr:'B2',overall:60,
    errors:[],strength_evidence:[],practice_outcome:null};
  api.reviewCue=async()=>({available:true,state:'unresolved',source:'practice_outcome',status:'needs_attention',
    category:'grammar',evidence:'I has a book',essay_id:42,grammar_id:''});
  const review=fakeRoot();
  await renderReview(review);
  assert.match(review.innerHTML,/class="o-card o-panel review-cue"/);
  assert.match(review.innerHTML,/I has a book/);
  assert.ok(review.innerHTML.includes(categoryLabel('grammar')));
  assert.ok(review.innerHTML.includes(statusLabel('needs_attention')));
  assert.doesNotMatch(review.innerHTML,/\bneeds_attention\b/,
    `Review ${locale.toUpperCase()} must localize the review-cue status`);

  for(const malformed of [null,{},
    {available:true,state:'recurring',source:'error_memory',status:'watch',category:{},evidence:{}},
    {available:true,state:'recurring',source:'unknown',status:'watch',category:'grammar',evidence:'bad'},
  ]){
    api.reviewCue=async()=>malformed;
    const malformedReview=fakeRoot();
    await renderReview(malformedReview);
    assert.doesNotMatch(malformedReview.innerHTML,/class="o-card o-panel review-cue"/,
      `Review ${locale.toUpperCase()} must suppress malformed review cues`);
    assert.doesNotMatch(malformedReview.innerHTML,/\[object Object\]/);
  }
}

api.learningMemory=async()=>({patterns:[],strengths:[],focus:null,revision_wins:[],review_cue:{available:false,state:'none',source:'none'}});
for(const locale of ['en','vi','zh']){
  state.supportLanguage=locale;
  const empty=fakeRoot();
  await renderHome(empty);
  /* H1.1: Home is discovery-first. An unavailable cue renders no tile at all
     rather than a card explaining that there is nothing to review. Review
     itself still renders its own empty state, asserted above. */
  assert.doesNotMatch(empty.innerHTML,/data-review-cue-state/);
  assert.doesNotMatch(empty.innerHTML,new RegExp(locale==='en'?'No actionable':locale==='vi'?'Chưa có đủ':'目前还没有足够'));
}

console.log('Review cue EN/VI/ZH contract: PASS');
