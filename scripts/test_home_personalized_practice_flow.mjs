import assert from 'node:assert/strict';
import {api} from '../static/becoming/api.js';
import {state} from '../static/becoming/store.js';
import {renderHome} from '../static/becoming/screens/home.js';
import {renderWrite} from '../static/becoming/screens/write.js';

class FakeElement{
  constructor(){
    this.dataset={};
    this.listeners={};
    this.innerHTML='';
    this.innerText='';
    this.textContent='';
    this.disabled=false;
    this.classList={toggle:()=>{},add:()=>{},remove:()=>{}};
  }
  addEventListener(name,listener){this.listeners[name]=listener;}
  removeAttribute(){}
  setAttribute(){}
  async click(){return this.listeners.click?.({currentTarget:this});}
  contains(){return false;}
  focus(){}
  querySelector(){return null;}
}

const root={
  innerHTML:'',
  nodes:new Map(),
  querySelector(selector){
    if(!this.nodes.has(selector))this.nodes.set(selector,new FakeElement());
    return this.nodes.get(selector);
  },
  querySelectorAll(selector){
    const attribute=selector.includes('home-practice-grammar')
      ?'home-practice-grammar':'home-open-review';
    if(!selector.includes(attribute))return [];
    const match=this.innerHTML.match(new RegExp(`data-${attribute}="([^"]+)"`));
    if(!match)return [];
    const button=this.nodes.get(selector)||new FakeElement();
    if(attribute==='home-practice-grammar'){
      button.dataset.homePracticeGrammar=match[1];
      button.dataset.homePracticeEvidence=(this.innerHTML.match(new RegExp(`data-home-practice-grammar="${match[1]}"[^>]*data-home-practice-evidence="([^"]*)"`))||[])[1]||'';
      button.dataset.homePracticeEssay=(this.innerHTML.match(new RegExp(`data-home-practice-grammar="${match[1]}"[^>]*data-home-practice-essay="([^"]*)"`))||[])[1]||'';
    }else button.dataset.homeOpenReview=match[1];
    this.nodes.set(selector,button);
    return [button];
  },
};

globalThis.document={
  querySelector:()=>null,
  querySelectorAll:()=>[],
  addEventListener:()=>{},
  removeEventListener:()=>{},
  execCommand:()=>{},
  body:{style:{},classList:{add:()=>{},remove:()=>{}}},
};
globalThis.window={dispatchEvent:()=>{},getSelection:()=>null,setInterval:()=>1,clearInterval:()=>{}};
globalThis.location={hash:'#/home'};
globalThis.HashChangeEvent=class {};
const writeIds=[
  '#writingEditor','#editorCount','#savedStamp','#lookupSelection','#blockFormat',
  '#practiceMode','#practiceLevel','#practiceLength','#practiceTopic','#practiceAudience',
  '#clearDraft','#reviewDraft','#reviewDraftMobile','#viewRubric','#generateBrief',
];
const writeNodes=new Map(writeIds.map(id=>[id,new FakeElement()]));
const writeRoot={
  innerHTML:'',
  querySelector:selector=>writeNodes.get(selector)||null,
  querySelectorAll:()=>[],
};
const storage=new Map();
globalThis.localStorage={
  getItem:key=>storage.get(key)??null,
  setItem:(key,value)=>storage.set(key,String(value)),
  removeItem:key=>storage.delete(key),
};

const original={
  dashboard:api.dashboard,
  essays:api.essays,
  learningMemory:api.learningMemory,
  practiceRecommendation:api.practiceRecommendation,
  practiceOutcomes:api.practiceOutcomes,
  libraryVocabulary:api.libraryVocabulary,
  nextPractice:api.nextPractice,
  grammarPractice:api.grammarPractice,
  essay:api.essay,
  evaluate:api.evaluate,
  practiceOutcome:api.practiceOutcome,
};

const fixtures={
  en:{
    profile:{native_language:'en'},
    recommendation:{
      language:'en',intent:'repair',focus_category:'article',focus_family:'grammar',
      focus_label:'Articles',focus_status:'watch',target_level:'B2',
      task_type:'story',topic:'daily life',word_target:150,
      focus_instruction:'Practice articles in your next draft.',
      reason:'Repeated article evidence in recent writing.',
    },
    task:{
      task_type:'story',topic:'daily life',target_level:'B2',word_target:150,
      prompt:'Write about a daily routine using clear articles.',
    },
  },
  zh:{
    profile:{native_language:'zh'},
    recommendation:{
      language:'zh',intent:'repair',focus_category:'grammar',focus_family:'grammar',
      focus_label:'语法与句子结构',focus_status:'watch',target_level:'HSK4',
      task_type:'story',topic:'日常生活',word_target:80,
      focus_instruction:'下一篇写作先检查句子结构。',
      reason:'近期写作中反复出现语法问题。',
    },
    task:{
      task_type:'story',topic:'日常生活',target_level:'HSK4',word_target:80,
      prompt:'请写一段关于日常生活的短文，注意句子结构。',
    },
  },
};

fixtures.en.recommendation.difficulty={state:'stretch',word_target:180,length_delta:30,provenance:{source:'practice_outcome',evidence_count:1,status:'improved',revision_no:2}};
fixtures.zh.recommendation.difficulty={state:'stretch',word_target:120,length_delta:40,provenance:{source:'practice_outcome',evidence_count:1,status:'improved',revision_no:2}};

try{
  api.dashboard=async()=>({essay_count:0,streak:0,metrics:{}});
  api.essays=async()=>[];
  api.learningMemory=async()=>({patterns:[],strengths:[],focus:null,revision_wins:[]});
  api.practiceOutcomes=async()=>({latest:{
    status:'improved',previous_issue_count:2,issue_count:0,revision_no:2,
    focus_label:'Grammar transfer',
    grammar_id:state.language==='zh'?'zh-hsk1-1-svo-c-b-n':'a1-complete-sentences-and-basic-word-order',
    essay_id:412,
    error_evidence:['I has a book'],
  }});
  api.libraryVocabulary=async()=>[];

  for(const locale of ['en','zh']){
    const fixture=fixtures[locale];
    state.language=locale;
    state.supportLanguage=locale;
    state.profile=fixture.profile;
    const staleLevel=locale==='zh'?'HSK1':'A1';
    state.draft={
      ...state.draft,
      mode:'free',topic:'random',level:staleLevel,
      length:locale==='zh'?80:150,prompt:'',generatedTask:null,
      practiceContext:null,text:'',html:'<p>Stale persisted writing.</p>',
      savedAt:1700000000000,parentEssayId:null,
    };
    let nextPayload=null;
    api.practiceRecommendation=async()=>fixture.recommendation;
    api.nextPractice=async payload=>{
      nextPayload=payload;
      return {...fixture.task,personalization:fixture.recommendation};
    };
    globalThis.location.hash='#/home';
    root.nodes.clear();
    await renderHome(root);
    assert.match(root.innerHTML,/data-practice-difficulty/,
      `${locale.toUpperCase()} Home must render the evidence-based difficulty rationale`);
    const grammarButton=root.querySelectorAll('[data-home-practice-grammar]')[0];
    assert.ok(grammarButton,
      `${locale.toUpperCase()} Home must render Grammar practice from the latest outcome`);
    assert.ok(root.innerHTML.includes(locale==='zh'?'立即练习':'Practice now'),
      `${locale.toUpperCase()} Home must localize the Grammar practice action`);
    const reviewButton=root.querySelectorAll('[data-home-open-review]')[0];
    assert.equal(reviewButton?.dataset.homeOpenReview,'412',
      `${locale.toUpperCase()} Home must link the latest outcome to its essay`);
    api.essay=async id=>({id:Number(id),text:'A reviewed Grammar sentence.',html:'<p>A reviewed Grammar sentence.</p>',prompt:'Grammar practice'});
    await reviewButton.click();
    assert.equal(state.lastEvaluation.id,412,
      `${locale.toUpperCase()} Home outcome must open the linked essay in Review`);
    assert.equal(state.draft.html,'<p>A reviewed Grammar sentence.</p>',
      `${locale.toUpperCase()} Home Review handoff must replace stale rich-text content`);
    assert.equal(globalThis.location.hash,'#/review',
      `${locale.toUpperCase()} Home outcome review action must open Review`);
    globalThis.location.hash='#/home';
    let grammarPracticeId=null;
    let grammarPracticeEvidence=null;
    api.grammarPractice=async (id,evidence)=>{
      grammarPracticeId=id;
      grammarPracticeEvidence=evidence;
      return {
        prompt:locale==='zh'?'请使用本课语法重点写三句话。':'Write three sentences using this grammar focus.',
        target_level:locale==='zh'?'HSK1':'A1',
        practice_context:{intent:'repair',focus_family:'grammar',focus_category:'grammar',
          task_type:'story',topic:'grammar transfer',target_level:locale==='zh'?'HSK1':'A1',
          action_label:locale==='zh'?'练习这个语法':'Practice this grammar',
          reason:locale==='zh'?'根据你的 Writing 发现和静态 Grammar 课程选择的针对性练习。':'Targeted practice selected from a Writing finding and the static Grammar curriculum.',
          evidence:'I has a book',
          focus_instruction:locale==='zh'?'请写 3-5 句，使用本课的语法重点。':'Write 3–5 sentences using the grammar focus from this lesson.',
          grammar_id:id,grammar_title:locale==='zh'?'语法练习':'Grammar practice'},
      };
    };
    await grammarButton.click();
    assert.equal(grammarPracticeId,locale==='zh'?'zh-hsk1-1-svo-c-b-n':'a1-complete-sentences-and-basic-word-order',
      `${locale.toUpperCase()} Home must request the linked Grammar lesson practice`);
    assert.equal(grammarPracticeEvidence,'I has a book',
      `${locale.toUpperCase()} Home must carry exact learner evidence into Grammar practice`);
    assert.equal(state.draft.practiceContext?.grammar_id,grammarPracticeId,
      `${locale.toUpperCase()} Home must preserve Grammar practice context`);
    assert.equal(state.draft.parentEssayId,412,
      `${locale.toUpperCase()} Home Grammar practice must preserve the source essay lineage`);
    assert.equal(globalThis.location.hash,'#/write',
      `${locale.toUpperCase()} Home Grammar practice must open Write`);
    let homeGrammarPayload=null;
    const beforeHomeEvaluate=api.evaluate;
    const beforeHomeOutcome=api.practiceOutcome;
    api.evaluate=async payload=>{
      homeGrammarPayload=payload;
      return {id:413,evaluator:'ollama:writing-evaluator'};
    };
    api.practiceOutcome=async()=>({outcome:null});
    globalThis.location.hash='#/write';
    await renderWrite(writeRoot);
    assert.match(writeRoot.innerHTML,/data-practice-difficulty/,
      `${locale.toUpperCase()} Write must carry the difficulty rationale into the handoff`);
    writeNodes.get('#writingEditor').innerText=locale==='zh'
      ?'我每天写一段清楚的练习句子。'
      :'I write a clear practice sentence every day.';
    await writeNodes.get('#reviewDraft').listeners.click({
      currentTarget:writeNodes.get('#reviewDraft'),
    });
    assert.equal(homeGrammarPayload.parent_essay_id,412,
      `${locale.toUpperCase()} Home Grammar practice must send the source essay as the evaluation parent`);
    assert.equal(homeGrammarPayload.learning_language,locale);
    assert.equal(homeGrammarPayload.practice_context.grammar_id,grammarPracticeId);
    assert.equal(homeGrammarPayload.practice_context.evidence,'I has a book');
    api.evaluate=beforeHomeEvaluate;
    api.practiceOutcome=beforeHomeOutcome;
    assert.equal(state.draft.savedAt,null,
      `${locale.toUpperCase()} Home Grammar practice must clear stale saved-state`);
    assert.equal(globalThis.location.hash,'#/review',
      `${locale.toUpperCase()} Home Grammar practice must submit into Review`);
    /* H1: personalized Writing practice is a recommendation, not the Home hero
       (ORENA_HOME_H1_IMPLEMENTATION_BRIEF §7). The hero's one action follows
       the learner's real continuation; the practice handoff itself - the
       payload, the level and everything transferred into Write - is unchanged
       and is asserted below against the recommendation tile that now owns it. */
    state.draft={...state.draft,prompt:'',generatedTask:null,practiceContext:null,text:'',html:''};
    globalThis.location.hash='#/home';
    root.nodes.clear();
    await renderHome(root);
    assert.match(root.innerHTML,/id="homePrimary"/,
      `${locale.toUpperCase()} Home must still render one primary hero action`);
    assert.match(root.innerHTML,/data-home-next-plan[^>]*data-plan-kind="writing"/,
      `${locale.toUpperCase()} Home must offer personalized Practice as a recommendation`);
    const primary=root.querySelector('[data-home-next-plan-action]');
    assert.ok(primary.listeners.click,`${locale.toUpperCase()} Home should bind personalized practice`);
    await primary.listeners.click({currentTarget:primary});

    assert.deepEqual(nextPayload,{target_level:fixture.recommendation.target_level},
      `${locale.toUpperCase()} Home must request practice at the recommendation level`);
    assert.equal(state.draft.prompt,fixture.task.prompt,
      `${locale.toUpperCase()} Home must transfer the generated prompt to Write`);
    assert.equal(state.draft.text,'');
    assert.equal(state.draft.html,'',
      `${locale.toUpperCase()} Home must clear stale rich-text before new Practice`);
    assert.equal(state.draft.savedAt,null,
      `${locale.toUpperCase()} Home must clear stale saved-state before new Practice`);
    assert.equal(state.draft.generatedTask.prompt,fixture.task.prompt);
    assert.equal(state.draft.mode,fixture.task.task_type);
    assert.equal(state.draft.topic,fixture.task.topic);
    assert.equal(state.draft.level,fixture.recommendation.target_level);
    assert.equal(state.draft.length,fixture.task.word_target);
    assert.deepEqual(state.draft.practiceContext,fixture.recommendation,
      `${locale.toUpperCase()} Home must preserve the backend recommendation context`);
    assert.equal(state.draft.parentEssayId,null);
    assert.equal(globalThis.location.hash,'#/write',
      `${locale.toUpperCase()} personalized practice must open Write`);
  }
}finally{
  Object.assign(api,original);
}

console.log('Home personalized Practice flow EN/ZH: PASS');
