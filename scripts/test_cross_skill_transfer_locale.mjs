import assert from 'node:assert/strict';
import {api} from '../static/becoming/api.js';
import {state} from '../static/becoming/store.js';
import {renderHome} from '../static/becoming/screens/home.js';
import {renderJourney} from '../static/becoming/screens/journey.js';
import {crossSkillCueMarkup} from '../static/becoming/domain/cross-skill.js';
import {t} from '../static/becoming/domain/i18n.js';
import {setSharedMediaSession,clearSharedMediaSession} from '../static/becoming/domain/shared-media-session.js';

const rootFactory=()=>({innerHTML:'',insertAdjacentHTML(_p,html){this.innerHTML=html+this.innerHTML;},querySelector(){return null;},querySelectorAll(){return [];}});
globalThis.document={querySelector:()=>null,querySelectorAll:()=>[],body:{classList:{add(){},remove(){}},style:{}},documentElement:{dataset:{},classList:{add(){},remove(){}}}};
globalThis.window={requestAnimationFrame:fn=>fn(),setInterval:()=>1,clearInterval(){},dispatchEvent(){},getSelection:()=>null};
globalThis.requestAnimationFrame=fn=>fn();
globalThis.localStorage={getItem:()=>null,setItem(){},removeItem(){}};
globalThis.location={hash:'#/home'};

api.dashboard=async()=>({essay_count:1,streak:0,metrics:{}});
api.essays=async()=>[{id:9,text:'A sentence',prompt:'Write',created_at:'2026-01-01T00:00:00Z',revision_no:1}];
api.learningMemory=async()=>({patterns:[],strengths:[],focus:null,revision_wins:[]});
api.practiceRecommendation=async()=>null;
api.practiceOutcomes=async()=>({items:[],latest:null});
api.readingSessions=async()=>({items:[]});
api.speakingAttempts=async()=>({items:[]});
api.libraryVocabulary=async()=>[];

const cues={
  writing:{available:true,state:'transfer',source:'writing',evidence:'I has a book',action:{kind:'review',essay_id:42}},
  reading:{available:true,state:'transfer',source:'reading',evidence:'Travel article',action:{kind:'reading',session_id:7}},
  listening:{available:true,state:'transfer',source:'listening',evidence:'Segment one',action:{kind:'listening',asset_id:'asset-1',segment_id:'seg-1',source_url:'https://example.test/audio',title:'Lesson'}},
  speaking:{available:true,state:'transfer',source:'speaking',evidence:'Hello there',action:{kind:'speaking',asset_id:'asset-1',segment_id:'seg-1'}},
};

state.language='en'; state.profile={native_language:'en'};
for(const locale of ['en','vi','zh']){
  state.supportLanguage=locale;
  for(const [source,cue] of Object.entries(cues)){
    if(source==='listening'||source==='speaking')setSharedMediaSession({learning_language:'en',payload:{asset:{asset_id:'asset-1'},transcript:{segments:[{segment_id:'seg-1'}]}}});
    else clearSharedMediaSession('en');
    api.crossSkillCue=async()=>cue;
    const home=rootFactory(); await renderHome(home);
    assert.match(home.innerHTML,new RegExp(`data-cross-skill-source="${source}"`));
    assert.ok(home.innerHTML.includes(t(`cross_skill.source_${source}`)));
    assert.doesNotMatch(home.innerHTML,/proficiency|mastery|completion/i);
    const journey=rootFactory(); await renderJourney(journey);
    assert.match(journey.innerHTML,new RegExp(`data-cross-skill-source="${source}"`));
    assert.ok(journey.innerHTML.includes(t(`cross_skill.action_${source}`)));
  }
  clearSharedMediaSession('en');
  api.crossSkillCue=async()=>({available:true,state:'transfer',source:'reading',evidence:{},action:{kind:'reading',session_id:7}});
  /* H1.1: on Home an invalid cue is simply not rendered - absence is the empty
     state. Journey keeps the explicit "none" card, asserted below, and both
     screens still share one validator (normalizeCrossSkillCue). */
  const empty=rootFactory(); await renderHome(empty); assert.doesNotMatch(empty.innerHTML,/data-cross-skill-state/);
  api.crossSkillCue=async()=>({available:true,state:'transfer',source:'reading',evidence:'stale',action:{kind:'speaking',asset_id:{},segment_id:'x'}});
  const malformed=rootFactory(); await renderJourney(malformed); assert.match(malformed.innerHTML,/data-cross-skill-state="none"/);
  api.crossSkillCue=async()=>cues.speaking;
  clearSharedMediaSession('en');
  const noSession=rootFactory(); await renderHome(noSession); assert.doesNotMatch(noSession.innerHTML,/data-cross-skill-state/);
  setSharedMediaSession({learning_language:'en',payload:{asset:{asset_id:'unrelated'},transcript:{segments:[{segment_id:'seg-1'}]}}});
  const unrelated=rootFactory(); await renderJourney(unrelated); assert.match(unrelated.innerHTML,/data-cross-skill-state="none"/);
  clearSharedMediaSession('en');
}
console.log('Cross-skill transfer Home/Journey EN/VI/ZH contract: PASS');
