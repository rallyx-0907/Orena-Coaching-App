import assert from 'node:assert/strict';
import {api} from '../static/becoming/api.js';
import {state} from '../static/becoming/store.js';
import {renderHome} from '../static/becoming/screens/home.js';

globalThis.document={querySelector:()=>null};
const root={
  innerHTML:'',
  querySelector:()=>null,
  querySelectorAll:()=>[],
};

api.dashboard=async()=>({essay_count:0,streak:0,metrics:{}});
api.essays=async()=>[];
let latestMemory={patterns:[],strengths:[],focus:null,revision_wins:[]};
api.learningMemory=async()=>latestMemory;
api.practiceRecommendation=async()=>null;
api.libraryVocabulary=async()=>[];

let latestOutcome={
  status:'improved',
  previous_issue_count:2,
  issue_count:0,
  focus_label:'Agreement practice',
  revision_no:2,
};
api.practiceOutcomes=async()=>({latest:latestOutcome});

state.language='en';
state.profile={native_language:'en'};

for(const locale of ['en','vi','zh']){
  state.supportLanguage=locale;
  await renderHome(root);
  assert.match(
    root.innerHTML,
    /data-practice-outcome-status=/,
    `Home ${locale.toUpperCase()} should render a valid practice outcome`,
  );
  assert.doesNotMatch(root.innerHTML,/\[object Object\]/);
}

for(const locale of ['en','vi','zh']){
  state.supportLanguage=locale;
  for(const {value,rendered} of [
    {value:null,rendered:false},
    {value:{},rendered:false},
    {value:{status:{},focus_label:{},previous_issue_count:{},issue_count:{},revision_no:{}},rendered:false},
    {value:{status:'unknown',focus_label:'Agreement practice'},rendered:false},
    {value:{status:'improved',previous_issue_count:2,issue_count:-1,revision_no:2},rendered:false},
    {value:{status:'improved',previous_issue_count:2,issue_count:0.5,revision_no:2},rendered:false},
    {value:{status:'improved',previous_issue_count:2,issue_count:0,revision_no:0},rendered:false},
    {value:{status:'improved',previous_issue_count:2,issue_count:0,revision_no:1.5},rendered:false},
    {value:{status:'improved',focus_label:{},previous_issue_count:null,issue_count:0,revision_no:2},rendered:true},
  ]){
    latestOutcome=value;
    await renderHome(root);
    if(rendered){
      assert.match(root.innerHTML,/data-practice-outcome-status=/,
        `Home ${locale.toUpperCase()} should retain a safe outcome shell`);
    }else{
      assert.doesNotMatch(root.innerHTML,/data-practice-outcome-status=/,
        `Home ${locale.toUpperCase()} must omit malformed practice outcomes`);
    }
    assert.doesNotMatch(
      root.innerHTML,
      /\[object Object\]/,
      `Home ${locale.toUpperCase()} must not render malformed outcome fields`,
    );
  }
}

const focusStatusCopy={
  en:'Improving',
  vi:'\u0110ang c\u1ea3i thi\u1ec7n',
  zh:'\u6b63\u5728\u6539\u5584',
};
/* RETIRED, not lost. Home used to render the Writing dashboard and the
 * localized learning-memory focus status. Both moved off this screen by
 * accepted product direction: Home is motivation, discovery and continuation,
 * and learning analytics belong to Progress/Journey
 * (PRODUCT_CONSTITUTION "Home and Progress boundary"; H1 brief §8).
 *
 * Journey still fetches /api/dashboard and /api/learning-memory and renders
 * them, so no backend data or learner value was removed - only this screen's
 * ownership of it. The assertions below are inverted deliberately: what used
 * to be required on Home is now forbidden on Home. */
latestMemory={
  patterns:[],
  strengths:[],
  focus:{category:'grammar',status:'improving',total:3,series_count:2},
  revision_wins:[],
};
for(const locale of ['en','vi','zh']){
  state.supportLanguage=locale;
  await renderHome(root);
  assert.doesNotMatch(root.innerHTML,/class="writing-dashboard/,
    `Home ${locale.toUpperCase()} must not render a Writing dashboard`);
  assert.doesNotMatch(root.innerHTML,new RegExp(focusStatusCopy[locale]),
    `Home ${locale.toUpperCase()} must not render learning-memory analytics`);
  assert.doesNotMatch(root.innerHTML,/\bimproving\b/,
    `Home ${locale.toUpperCase()} must not leak the raw focus status enum`);
}

for(const locale of ['en','vi','zh']){
  state.supportLanguage=locale;
  const beforeNowCopy={en:'Before and now',vi:'Trước và nay',zh:'之前与现在'};
  for(const malformed of [
    {strengths:null,revision_wins:null},
    {strengths:[null,{}],revision_wins:[null,{}]},
    {strengths:[{category:{},stage:{},evidence_count:{},series_count:1}],revision_wins:[]},
    {strengths:[{category:'grammar',stage:'Stable',evidence_count:-1,series_count:1}],revision_wins:[]},
    {strengths:[{category:'grammar',stage:'Stable',evidence_count:1.5,series_count:1}],revision_wins:[]},
    {strengths:[],revision_wins:[{overall_delta:{},error_delta:0,revisions:1}]},
    {strengths:[],revision_wins:[{overall_delta:1,error_delta:-1,revisions:0}]},
    {strengths:[],revision_wins:[{overall_delta:1,error_delta:-1,revisions:1}]},
  ]){
    latestMemory=malformed;
    await renderHome(root);
    assert.doesNotMatch(root.innerHTML,/\[object Object\]/,
      `Home ${locale.toUpperCase()} must not render malformed learning-memory records`);
    assert.doesNotMatch(root.innerHTML,/undefined/,
      `Home ${locale.toUpperCase()} must not render undefined memory values`);
    assert.doesNotMatch(root.innerHTML,new RegExp(beforeNowCopy[locale]),
      `Home ${locale.toUpperCase()} must omit revision wins with fewer than two revisions`);
  }
}

console.log('Home practice outcome shape contract: PASS');
