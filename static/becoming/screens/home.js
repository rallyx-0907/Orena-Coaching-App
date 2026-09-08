/* Orena Home — the Orena Product UI System (H1, corrected by the H1.1 audit).
 *
 * Home's job is motivation, discovery and real continuation. It is not a
 * dashboard, and the analytics that used to live here - the Writing cycle, the
 * latest score, learning-memory cards, the streak block, recent drafts - have
 * been removed from this screen. None of that data was deleted: Journey and
 * Review still read `/api/dashboard` and `/api/learning-memory`, and Home still
 * fetches the dashboard for one reason only, which is that the global chrome's
 * streak cue reads `state.dashboard`.
 *
 * Composition recipe: Hero + Mosaic + Rail (ORENA_COMPONENT_CONTRACT §8).
 *
 *   JourneyHero -> Continue -> Explore Worlds -> For You Today
 *   -> Challenge -> Continue Exploring
 *
 * Four rules run through the whole file.
 *
 * Nothing is invented. Every card is backed by a real record. There is
 * deliberately no completion percentage on the continuation card: the D-049
 * resume contract carries a lesson and a segment, not a ratio.
 *
 * A section with nothing to say says nothing. A learner with no history gets
 * discovery - real starter lessons from the catalog - not a wall of cards
 * explaining what they have not done yet. An absent card IS the empty state.
 *
 * Nothing is offered twice. One set of surfaced lesson ids is threaded through
 * the continuation, For You and Continue Exploring in that order.
 *
 * Sections load independently. The first paint happens before any request
 * resolves, and each group of requests repaints only what it owns, so one slow
 * or failing provider cannot hold the page.
 */

import {api} from '../api.js';
import {state,saveDraft} from '../store.js';
import {go} from '../router.js';
import {requestLessonAutostart,resumableLesson} from '../domain/media-lesson-history.js';
import {listeningHabitSnapshot} from '../domain/listening-habit.js';
import {selectSharedMediaSegment,getSharedMediaSession} from '../domain/shared-media-session.js';
import {difficultyAdjustment} from '../domain/adaptive.js';
import {normalizeCrossSkillCue} from '../domain/cross-skill.js';
import {errorBlock,loadingBlock,runBusy} from '../components/primitives.js';
import {t,categoryLabel,statusLabel,uiLocale,uiHtmlLang} from '../domain/i18n.js';
import {
  availableWorlds,
  discoveryItems,
  durationMinutes,
  homeContinuation,
} from '../domain/home-model.js';
import {
  challengeCard,
  continueJourneyCard,
  discoveryCard,
  discoveryRail,
  journeyHero,
  productSection,
  recommendationRail,
  recommendationTile,
  worldCard,
  worldRail,
} from '../orena/product-components.js';

/* ------------------------------------------------------------ language --- */

/* Two different languages live on this screen and they must not be conflated.
 *
 * `uiLang` is the language of the INTERFACE - headings, buttons, explanations -
 * and follows the learner's interface locale. `contentLang` is the language of
 * the material being learned - lesson titles, the learner's own sentences - and
 * follows the learning language.
 *
 * Treating "either one is Chinese" as a single CJK flag, which is what H1 did,
 * gives an English interface Chinese typography as soon as somebody studies
 * Chinese, and leaves a Chinese lesson title in Latin metrics whenever the
 * interface is English. They are independent, so they are computed separately
 * and travel to the components attached to the specific string. */
const uiLang=()=>uiHtmlLang();
const contentLang=()=>(state.language==='zh'?'zh-Hans':String(state.language||'en'));

/* An optional data source. Home renders whatever succeeded, so a rejection is
   a section state rather than a page state. */
async function optional(load){
  try{ return await load(); }
  catch{ return null; }
}

function greeting(){
  const hour=new Date().getHours();
  const key=hour<12?'home.greet_morning':hour<18?'home.greet_afternoon':'home.greet_evening';
  const name=String(state.me?.name||'').trim().split(/\s+/)[0]||'';
  return name?`${t(key)}, ${name}.`:`${t(key)}.`;
}

function hasLocalWritingDraft(draft=state.draft){
  if(!draft||typeof draft!=='object')return false;
  const text=value=>typeof value==='string'&&value.trim()!=='';
  return text(draft.text)||text(draft.html)||text(draft.prompt)
    ||Boolean(draft.generatedTask&&typeof draft.generatedTask==='object'&&!Array.isArray(draft.generatedTask));
}

/* ===================================================== validated records == */

/* The canonical practice-outcome statuses, read from the only thing that emits
 * them: `derive_practice_outcome` in writing_coach/becoming_outcomes.py.
 *
 * This list is not a matter of taste. Home inherited a set of four invented
 * statuses - partial, regressed, unchanged - that no backend has ever produced
 * and which excluded six of the seven real ones. The visible cost was that a
 * learner whose revision came back `still_working` or `needs_attention` lost
 * the Grammar practice handoff entirely and silently, because the tile refused
 * to render. Every value here is a status the backend can actually return. */
const PRACTICE_OUTCOME_STATUSES=new Set([
  'improved',
  'transferred',
  'held',
  'still_working',
  'needs_attention',
  'not_observed',
  'needs_more_evidence',
]);

/* A practice outcome is only shown when every field it renders is well formed.
   A malformed record produces nothing at all - never "[object Object]" and
   never a half-claim about the learner's revision. */
function normalizedPracticeOutcome(outcome){
  if(!outcome||typeof outcome!=='object'||Array.isArray(outcome))return null;
  const status=typeof outcome.status==='string'?outcome.status.trim().toLowerCase():'';
  if(!PRACTICE_OUTCOME_STATUSES.has(status))return null;
  const numberValue=value=>{
    if(typeof value==='number'&&Number.isFinite(value))return value;
    if(typeof value==='string'&&value.trim()!==''){
      const parsed=Number(value);
      if(Number.isFinite(parsed))return parsed;
    }
    return null;
  };
  const issueCount=numberValue(outcome.issue_count);
  const revisionNo=numberValue(outcome.revision_no);
  const essayId=numberValue(outcome.essay_id);
  if(
    issueCount===null||!Number.isInteger(issueCount)||issueCount<0
    ||revisionNo===null||!Number.isInteger(revisionNo)||revisionNo<1
  )return null;
  let previous=null;
  if(outcome.previous_issue_count!=null){
    previous=numberValue(outcome.previous_issue_count);
    if(previous===null||!Number.isInteger(previous)||previous<0)return null;
  }
  return {
    ...outcome,
    status,
    focus_label:typeof outcome.focus_label==='string'?outcome.focus_label.trim():'',
    previous_issue_count:previous,
    issue_count:issueCount,
    revision_no:revisionNo,
    essay_id:essayId!==null&&Number.isInteger(essayId)&&essayId>0?essayId:null,
    error_evidence:Array.isArray(outcome.error_evidence)
      ?outcome.error_evidence.filter(item=>typeof item==='string'&&item.trim()).map(item=>item.trim().slice(0,260)).slice(0,3)
      :[],
  };
}

const REVIEW_CUE_STATUSES=new Set(['recurring','new','watch','still_working','needs_attention']);
function normalizedReviewCue(value){
  if(!value||typeof value!=='object'||Array.isArray(value))return null;
  const available=value.available===true;
  const cueState=typeof value.state==='string'?value.state.trim().toLowerCase():'';
  const source=typeof value.source==='string'?value.source.trim().toLowerCase():'';
  const status=typeof value.status==='string'?value.status.trim().toLowerCase():'';
  const evidence=typeof value.evidence==='string'?value.evidence.trim().slice(0,260):'';
  const essayId=typeof value.essay_id==='number'&&Number.isInteger(value.essay_id)&&value.essay_id>0?value.essay_id:null;
  if(!available||!['recurring','unresolved'].includes(cueState)||!['error_memory','practice_outcome'].includes(source)
    ||!REVIEW_CUE_STATUSES.has(status)||!evidence)return null;
  return {...value,available:true,state:cueState,source,status,evidence,essay_id:essayId,
    category:typeof value.category==='string'?value.category.trim():'',
    suggestion:typeof value.suggestion==='string'?value.suggestion.trim().slice(0,320):''};
}

function dueLibraryReview(payload){
  const items=Array.isArray(payload)
    ?payload
    :payload&&typeof payload==='object'&&!Array.isArray(payload)&&Array.isArray(payload.items)
      ?payload.items:[];
  return items
    .map((item,index)=>{
      if(!item||typeof item!=='object'||Array.isArray(item)||item.due!==true||typeof item.word!=='string')return null;
      const word=item.word.trim();
      const next=typeof item.next_review_at==='string'?item.next_review_at.trim():'';
      const timestamp=next?Date.parse(next):NaN;
      if(!word||!next||!Number.isFinite(timestamp))return null;
      return {word,next,timestamp,index};
    })
    .filter(Boolean)
    .sort((a,b)=>a.timestamp-b.timestamp||a.index-b.index)[0]||null;
}

function readingReturnEvidence(history){
  const items=Array.isArray(history)?history:(Array.isArray(history?.items)?history.items:[]);
  return items.find(item=>item&&Number.isInteger(Number(item.id))&&item.latest_attempt==null)||null;
}

function speakingReturnEvidence(history,session){
  const items=Array.isArray(history)?history:(Array.isArray(history?.items)?history.items:[]);
  const assetId=session?.payload?.asset?.asset_id;
  const segments=Array.isArray(session?.payload?.transcript?.segments)
    ?session.payload.transcript.segments
      .map(segment=>segment?.segment_id)
      .filter(value=>typeof value==='string'&&value)
    :[];
  if(assetId==null||segments.length===0)return null;
  return items.find(item=>item&&String(item.asset_id)===String(assetId)
    &&item.segment_id!=null&&segments.includes(String(item.segment_id)))||null;
}

/* The single most useful next practice, chosen from real evidence in a fixed
   order. Unchanged from R12: this is a stable learner contract, and only its
   presentation has moved into a product component. */
function nextPracticePlan({recommendation,readingHistory,speakingHistory,listeningResume}){
  if(hasLocalWritingDraft())return {kind:'writing-draft'};
  if(recommendation&&recommendation.intent!=='baseline')return {kind:'writing'};
  const reading=readingReturnEvidence(readingHistory);
  if(reading)return {kind:'reading',sessionId:reading.id};
  if(listeningResume)return {kind:'listening',lesson:listeningResume};
  const speakingSession=getSharedMediaSession(state.language);
  const speaking=speakingReturnEvidence(speakingHistory,speakingSession);
  if(speaking)return {kind:'speaking',segmentId:String(speaking.segment_id)};
  if(recommendation?.intent==='baseline')return {kind:'baseline'};
  return null;
}

/* ============================================================ For You ===== */

function practiceDifficultyNote(recommendation){
  const difficulty=difficultyAdjustment(recommendation);
  return difficulty
    ?{text:t(difficulty.key,{delta:difficulty.delta}),attributes:{'data-practice-difficulty':''}}
    :null;
}

/* No plan means no tile. There is nothing actionable to say, and a card that
   says "nothing yet" is a placeholder occupying the space discovery should
   have. */
function nextPlanTile(plan,recommendation){
  if(!plan?.kind)return '';
  const kind=plan.kind;
  return recommendationTile({
    contentKind:'next-plan',
    // A plan that names a real lesson carries its id, so the same lesson-dedup
    // set that tracks Hero/For You/Continue Exploring can also see it here.
    contentId:kind==='listening'?String(plan.lesson?.lesson_id||''):'',
    reason:t('home.next_plan_title'),
    title:t(`home.next_plan_${kind}_title`),
    subtitle:t(`home.next_plan_${kind}_body`),
    lang:uiLang(),
    note:practiceDifficultyNote(recommendation),
    accentFamily:kind==='listening'?'listening':kind==='reading'?'reading':kind==='speaking'?'speaking':'writing',
    actionLabel:t('home.next_plan_action'),
    actionAttributes:{'data-home-next-plan-action':''},
    attributes:{'data-home-next-plan':'','data-plan-kind':kind},
  });
}

/* The Grammar handoff carried by the latest practice outcome. Evidence and
   parent-essay lineage travel on the button exactly as before, so Write still
   receives the sentence the learner actually got wrong - for every canonical
   status, not only the one Home happened to recognise. */
function practiceOutcomeTile(rawOutcome){
  const outcome=normalizedPracticeOutcome(rawOutcome);
  if(!outcome)return '';
  const key=outcome.status;
  const grammarId=typeof outcome.grammar_id==='string'?outcome.grammar_id.trim():'';
  const links=[];
  if(grammarId){
    links.push({label:t('review.open_grammar'),attributes:{'data-home-open-grammar':grammarId}});
  }
  if(outcome.essay_id!==null){
    links.push({label:t('home.open_review'),attributes:{'data-home-open-review':outcome.essay_id}});
  }
  return recommendationTile({
    contentKind:'practice-outcome',
    contentId:grammarId,
    reason:t('home.h1_reason_grammar'),
    title:t(`outcome.${key}.title`),
    subtitle:t(`outcome.${key}.body`,{
      previous:outcome.previous_issue_count??'—',
      count:outcome.issue_count??0,
      focus:outcome.focus_label||t('common.current_focus'),
    }),
    lang:uiLang(),
    // The learner's own sentence is in the language they are learning.
    quote:outcome.error_evidence[0]||'',
    quoteLang:contentLang(),
    meta:`${outcome.focus_label||t('common.current_focus')} · ${t('outcome.revision')} ${outcome.revision_no||1}`,
    accentFamily:'grammar',
    actionLabel:grammarId?t('review.practice_grammar'):'',
    actionAttributes:grammarId?{
      'data-home-practice-grammar':grammarId,
      'data-home-practice-evidence':outcome.error_evidence[0]||'',
      'data-home-practice-essay':outcome.essay_id||'',
    }:null,
    links,
    attributes:{'data-practice-outcome-status':key},
  });
}

/* A recurring issue worth another look. This is a handoff into the learner's
   own work, not an analytics readout: it shows the exact sentence and opens
   the review that contains it. No cue means no tile. */
function reviewCueTile(value){
  const cue=normalizedReviewCue(value);
  if(!cue)return '';
  return recommendationTile({
    contentKind:'review-cue',
    reason:t('home.review_cue_kicker'),
    title:t(`home.review_cue_title_${cue.state}`),
    subtitle:t('home.review_cue_body',{
      category:categoryLabel(cue.category||'expression'),
      status:statusLabel(cue.status),
      source:t(`home.review_cue_source_${cue.source}`),
    }),
    lang:uiLang(),
    quote:cue.evidence,
    quoteLang:contentLang(),
    accentFamily:'review',
    links:cue.essay_id
      ?[{label:t('home.review_cue_open'),attributes:{'data-open-review-cue':cue.essay_id}}]
      :[],
    attributes:{'data-review-cue-state':cue.state},
  });
}

/* Cross-skill transfer, rendered as an Orena recommendation.
 *
 * The business logic is NOT forked: `normalizeCrossSkillCue` is the same
 * validator Journey uses, including its shared-media session check. Only the
 * representation is Home's, which is what lets Home drop the legacy card
 * markup without Journey changing at all. */
function crossSkillTile(value){
  const cue=normalizeCrossSkillCue(value,{learningLanguage:state.language});
  if(!cue)return '';
  const action=cue.action;
  const attributes={
    review:()=>({'data-cross-skill-kind':'review','data-cross-skill-essay':action.essay_id}),
    reading:()=>({'data-cross-skill-kind':'reading','data-cross-skill-session':action.session_id}),
    listening:()=>({
      'data-cross-skill-kind':'listening',
      'data-cross-skill-asset':action.asset_id,
      'data-cross-skill-segment':action.segment_id,
      'data-cross-skill-url':action.source_url||'',
      'data-cross-skill-title':action.title||'',
    }),
    speaking:()=>({
      'data-cross-skill-kind':'speaking',
      'data-cross-skill-asset':action.asset_id,
      'data-cross-skill-segment':action.segment_id,
    }),
  }[action.kind]();
  return recommendationTile({
    contentKind:'cross-skill',
    reason:t('cross_skill.kicker'),
    title:t('cross_skill.title'),
    subtitle:t('cross_skill.body',{source:t(`cross_skill.source_${cue.source}`)}),
    lang:uiLang(),
    quote:cue.evidence,
    quoteLang:contentLang(),
    accentFamily:'speaking',
    actionLabel:t(`cross_skill.action_${cue.source}`),
    actionAttributes:attributes,
    attributes:{'data-cross-skill-state':'transfer','data-cross-skill-source':cue.source},
  });
}

/* A short listening entry point drawn from the real catalog. */
function listeningTile(item,{reason=''}={}){
  if(!item)return '';
  const minutes=durationMinutes(item);
  return recommendationTile({
    contentKind:'listening-lesson',
    contentId:String(item.lesson_id||''),
    reason:reason||t('home.h1_reason_listening'),
    title:String(item.title||''),
    subtitle:String(item.description||''),
    // A lesson title is content, so it carries the learning language whatever
    // the interface happens to be.
    lang:contentLang(),
    meta:minutes?t('home.h1_minutes',{count:minutes}):'',
    accentFamily:'listening',
    actionLabel:t('home.h1_open_lesson'),
    actionAttributes:{
      'data-home-open-lesson':String(item.lesson_id||''),
      'data-home-open-lesson-url':String(item.source?.source_url||''),
    },
  });
}

/* ========================================================== Challenge ===== */

/* The due-review challenge. The word, the handoff and the language scoping are
   the R14 contract; only the surface changed. Nothing due means no card. */
function libraryReviewChallenge(item){
  if(!item)return '';
  return challengeCard({
    challengeId:'library-review',
    kicker:t('home.library_review_title'),
    title:t('home.library_review_due'),
    description:t('home.library_review_body',{word:item.word}),
    lang:uiLang(),
    accentFamily:'review',
    actionLabel:t('home.library_review_action'),
    actionAttributes:{'data-home-library-review-action':''},
    attributes:{
      'data-home-library-review-state':'due',
      'data-home-library-review-word':item.word,
    },
  });
}

/* The listening goal, as an action rather than a statistic. Minutes appear
   because the learner set the goal and the time is really recorded; an
   unavailable or malformed snapshot says so, and still offers the action that
   fixes it, which is what keeps it a challenge rather than a placeholder. */
function listeningHabitChallenge(snapshot){
  if(!snapshot)return '';
  const status=snapshot.status==='unavailable'||snapshot.status==='malformed'?snapshot.status:'ok';
  if(status!=='ok'){
    return challengeCard({
      challengeId:'listening-habit',
      kicker:t('home.listening_habit_title'),
      title:t(`home.listening_habit_${status}`),
      lang:uiLang(),
      accentFamily:'listening',
      actionLabel:t('home.listening_habit_action'),
      actionAttributes:{'data-home-listening-goal':''},
      attributes:{'data-home-listening-habit':'','data-state':status},
    });
  }
  const minutes=value=>Math.max(0,Math.floor(Number(value||0)/60));
  const today=minutes(snapshot.today_seconds);
  const goal=Number(snapshot.daily_goal_minutes);
  return challengeCard({
    challengeId:'listening-habit',
    kicker:t('home.listening_habit_title'),
    title:t('home.listening_habit_body',{today,goal:snapshot.daily_goal_minutes}),
    description:t('home.listening_habit_week',{week:minutes(snapshot.week_seconds)}),
    lang:uiLang(),
    current:today,
    target:Number.isFinite(goal)&&goal>0?goal:null,
    accentFamily:'listening',
    actionLabel:t('home.listening_habit_action'),
    actionAttributes:{'data-home-listening-goal':''},
    attributes:{'data-home-listening-habit':'','data-state':'ok'},
  });
}

/* ============================================================= Worlds ===== */

function worldsSection(section){
  const shell=(cards,empty,sectionState)=>worldRail({
    id:'worlds',
    title:t('home.h1_worlds_title'),
    description:t('home.h1_worlds_lede'),
    cards,
    empty,
    state:sectionState,
  });
  if(section.status==='loading')return shell([],t('home.h1_loading'),'loading');
  if(section.status==='error')return shell([],t('home.h1_worlds_unavailable'),'error');

  const worlds=availableWorlds(section.data,{locale:uiLocale()});
  const cards=worlds.map((world,index)=>worldCard({
    worldId:world.worldId,
    title:world.title,
    description:world.description,
    // World copy is editorial interface text, localized per interface locale.
    lang:uiLang(),
    artwork:world.artwork,
    posterUrl:world.posterUrl,
    accentFamily:world.accentFamily,
    // Both are measured server-side against the real catalog.
    countLabel:world.lessonCount===1
      ?t('home.h1_world_count',{count:world.lessonCount})
      :t('home.h1_world_count_plural',{count:world.lessonCount}),
    // The lead label reads as one phrase but is two languages: the prefix is
    // interface copy, the lesson title is content. They travel separately so
    // neither is forced into the other's typography.
    leadPrefix:world.leadLessonTitle?t('home.h1_world_lead_prefix'):'',
    leadTitle:world.leadLessonTitle,
    leadSuffix:world.leadLessonTitle?t('home.h1_world_lead_suffix'):'',
    leadLang:contentLang(),
    variant:index===0?'featured':'standard',
    openAttributes:{
      'data-world-lesson':world.leadLessonId,
      'data-world-url':world.leadLessonSourceUrl,
    },
  }));
  return shell(cards,t('home.h1_worlds_empty'),'ready');
}

/* ========================================================== Discovery ===== */

function discoverySection(section,surfaced){
  const shell=(cards,empty,sectionState)=>discoveryRail({
    id:'continue-exploring',
    title:t('home.h1_discovery_title'),
    description:t('home.h1_discovery_lede'),
    cards,
    empty,
    state:sectionState,
  });
  if(section.status==='loading')return shell([],t('home.h1_loading'),'loading');
  if(section.status==='error')return shell([],t('home.h1_listening_unavailable'),'error');

  const cards=discoveryItems(section.data,{exclude:[...surfaced]}).map(item=>{
    const minutes=durationMinutes(item);
    return discoveryCard({
      contentId:String(item.lesson_id||''),
      title:String(item.title||''),
      description:String(item.description||''),
      lang:contentLang(),
      meta:minutes?t('home.h1_minutes',{count:minutes}):'',
      artwork:String(item.artwork||''),
      posterUrl:String(item.poster_url||''),
      accentFamily:'listening',
      openAttributes:{
        'data-home-open-lesson':String(item.lesson_id||''),
        'data-home-open-lesson-url':String(item.source?.source_url||''),
      },
    });
  });
  return shell(cards,t('home.h1_discovery_empty'),'ready');
}

/* ======================================================== continuation ==== */

/* Priority: durable server-backed Listening progress, then a real local
 * Writing draft, then the per-device Listening resume. The server signal wins
 * because it is the only one that survives a different device, which is
 * exactly why D-049 built it; the local resume stays as the fallback rather
 * than being deleted, because for a learner with no persisted progress it is
 * still a true statement about what they were doing.
 */
function continuationModel(library,localListening){
  const resolved=homeContinuation({library,hasWritingDraft:hasLocalWritingDraft()});
  if(resolved)return resolved;
  if(localListening)return {kind:'listening-local',lesson:localListening};
  return null;
}

function continuationMarkup(continuation){
  if(!continuation)return '';
  if(continuation.kind==='listening'){
    return continueJourneyCard({
      journeyId:continuation.lessonId,
      kicker:t('home.h1_continue_kicker'),
      title:continuation.title,
      titleLang:contentLang(),
      subtitle:continuation.segmentId?t('home.h1_continue_segment'):t('home.h1_continue_start'),
      artwork:continuation.artwork,
      posterUrl:continuation.posterUrl,
      accentFamily:'listening',
      resumeLabel:t('home.h1_continue_action'),
      actionAttributes:{'data-home-continue':'listening'},
      attributes:{'data-home-continue-source':'server'},
    });
  }
  if(continuation.kind==='writing'){
    return continueJourneyCard({
      journeyId:'writing-draft',
      kicker:t('home.h1_continue_kicker'),
      // This title is interface copy about the learner's draft, not content.
      title:t('home.h1_continue_writing_title'),
      titleLang:uiLang(),
      subtitle:t('home.h1_continue_writing_sub'),
      artwork:'writing',
      accentFamily:'writing',
      resumeLabel:t('home.h1_continue_action'),
      actionAttributes:{'data-home-continue':'writing'},
      attributes:{'data-home-continue-source':'draft'},
    });
  }
  return continueJourneyCard({
    journeyId:continuation.lesson.lesson_id||'',
    kicker:t('home.listening_resume_title'),
    title:continuation.lesson.title||t('title.listen'),
    titleLang:contentLang(),
    subtitle:t('home.listening_resume_body'),
    artwork:'listening',
    accentFamily:'listening',
    resumeLabel:t('home.listening_resume_action'),
    actionAttributes:{'data-home-resume-listening':''},
    attributes:{'data-home-continue-source':'local'},
  });
}

/* ============================================================== render ==== */

/* How long renderHome's returned promise will wait on its optional sections
   before giving up on them. Requests that are still outstanding keep running
   and still repaint through settle()'s own `.then(paint)` when/if they
   resolve - subject to the screen-lifecycle guard below - but the app-level
   render lifecycle (aria-busy, the rail refresh, focus) must not hang forever
   behind one provider that never answers at all. */
const HOME_SECTION_BUDGET_MS=6000;

export async function renderHome(root,{sectionBudgetMs=HOME_SECTION_BUDGET_MS}={}){
  document.querySelector('#primaryNav')?.classList.remove('hidden');
  root.innerHTML=`<section class="page">${loadingBlock(5)}</section>`;

  /* Screen lifecycle: app.js calls this exactly once, then reuses the SAME
     root element for whatever screen the learner navigates to next. Home's
     own requests are progressive and can still be outstanding at that point,
     so a stale settle()->paint() arriving after the learner has left Home
     must not overwrite whatever screen is on the page now. app.js already
     runs `root._cleanupScreen` before rendering the next screen (ORENA
     screen-cleanup contract); Home hooks into that same contract rather than
     inventing a second one.

     Disposal has to reach past paint(), too: `state.memory`,
     `state.practiceRecommendation`, `state.latestPracticeOutcome` and
     `state.dashboard` are shared learner state, not local to this render, and
     a request that resolves after cleanup can still write into them even
     though it can no longer paint. `renderLanguage` is a second, independent
     check on top of `disposed`: a stale result must not apply even in the
     (currently unreachable, but not contract-guaranteed) case where the
     learning language changed without a full screen cleanup. */
  let disposed=false;
  let resolveDisposal;
  const disposal=new Promise(resolve=>{ resolveDisposal=resolve; });
  const renderLanguage=state.language;
  const stale=()=>disposed||state.language!==renderLanguage;
  root._cleanupScreen=()=>{ disposed=true; resolveDisposal(); };

  /* Four independent groups. Nothing here is awaited together, so the first
     paint waits for none of them and a stalled group costs one section rather
     than the screen. */
  const sections={
    worlds:{status:'loading',data:null},
    library:{status:'loading',data:null},
    personal:{status:'loading',data:null},
    vocabulary:{status:'loading',data:null},
  };

  let handlers={continuation:null,nextPlan:null,dueReview:null,recommendation:null,localListening:null};

  function compose(){
    const localListening=resumableLesson(state.language);
    const listeningHabit=listeningHabitSnapshot();
    const library=sections.library.status==='ready'?sections.library.data:null;
    const personal=sections.personal.status==='ready'?sections.personal.data:null;
    const continuation=continuationModel(library,localListening);
    /* The continuation already owns Listening the moment it exists, server or
       local: D-049's server signal wins when both exist, and a per-device
       local resume becomes the continuation itself when the server has none.
       Either way, offering the SAME (or a different, competing) local resume
       again through Next Plan would be a second continuation, so Next Plan is
       only allowed to reach for a local resume when nothing has claimed
       Listening yet. */
    const continuationOwnsListening=continuation?.kind==='listening'||continuation?.kind==='listening-local';

    const nextPlan=personal?nextPracticePlan({
      recommendation:personal.recommendation,
      readingHistory:personal.readingHistory,
      speakingHistory:personal.speakingHistory,
      listeningResume:continuationOwnsListening?null:localListening,
    }):null;
    const dueReview=sections.vocabulary.status==='ready'
      ?dueLibraryReview(sections.vocabulary.data):null;

    /* One set of ids, threaded through every rail in render order, so nothing
       Home has already offered can be offered again below it. */
    const surfaced=new Set();
    if(continuation?.kind==='listening')surfaced.add(continuation.lessonId);
    if(continuation?.kind==='listening-local'&&continuation.lesson.lesson_id){
      surfaced.add(continuation.lesson.lesson_id);
    }
    if(nextPlan?.kind==='listening'&&nextPlan.lesson?.lesson_id){
      surfaced.add(String(nextPlan.lesson.lesson_id));
    }

    const personalTiles=personal?[
      nextPlanTile(nextPlan,personal.recommendation),
      practiceOutcomeTile(personal.outcomes?.latest),
      reviewCueTile(personal.memory?.review_cue),
      crossSkillTile(personal.crossCue),
    ].filter(Boolean):[];

    let forYou=personalTiles;
    if(library){
      if(personalTiles.length){
        // One real lesson alongside the learner's own work.
        const suggestion=discoveryItems(library,{exclude:[...surfaced],limit:1})[0]||null;
        if(suggestion){
          forYou=[...personalTiles,listeningTile(suggestion)];
          surfaced.add(String(suggestion.lesson_id||''));
        }
      }else{
        /* A learner with no history gets real content to start on, not a card
           explaining that they have no history. */
        const starters=discoveryItems(library,{exclude:[...surfaced],limit:2});
        forYou=starters.map(item=>listeningTile(item,{reason:t('home.h1_reason_starter')}));
        for(const item of starters)surfaced.add(String(item.lesson_id||''));
      }
    }

    const challenges=[
      libraryReviewChallenge(dueReview),
      listeningHabitChallenge(listeningHabit),
    ].filter(Boolean);

    /* Either provider can still fill For You: personal evidence supplies the
       personalized tiles, and the listening library alone can supply the
       starter lessons a learner with no history gets instead. So the section
       only leaves "loading" once BOTH have answered - claiming "empty" while
       either one might still deliver content would be a false negative. And a
       real provider failure is not a genuine empty state: an empty result
       Home measured and a result Home never got are different claims, so they
       get different copy rather than one collapsing into the other. */
    const forYouSettled=sections.personal.status!=='loading'&&sections.library.status!=='loading';
    const forYouFailed=sections.personal.status==='error'||sections.library.status==='error';
    const forYouState=forYou.length?'ready':!forYouSettled?'loading':forYouFailed?'error':'ready';
    const forYouEmpty=forYouState==='loading'
      ?t('home.h1_loading')
      :forYouState==='error'
        ?t('home.h1_foryou_unavailable')
        :t('home.h1_foryou_empty');
    const forYouSection=recommendationRail({
      id:'for-you',
      title:t('home.h1_foryou_title'),
      description:t('home.h1_foryou_lede'),
      tiles:forYou,
      empty:forYouEmpty,
      state:forYouState,
    });
    /* No challenge worth making is no Challenge section. An empty box would be
       the placeholder wall this audit removed. */
    const challengeSection=challenges.length
      ?productSection({
        id:'challenge',
        title:t('home.h1_challenge_title'),
        description:t('home.h1_challenge_lede'),
        variant:'challenge',
        items:challenges,
      })
      :'';

    handlers={continuation,nextPlan,dueReview,recommendation:personal?.recommendation||null,localListening};

    return `<div class="o-page">
      <div class="o-home-v2" data-orena-ui="v2" data-home-composition="hero-mosaic-rail">
        ${journeyHero({
          eyebrow:greeting(),
          title:t('home.h1_hero_title'),
          supportingText:t('home.h1_hero_lede'),
          // Hero copy is interface text: it follows the interface locale, not
          // the language being studied.
          lang:uiLang(),
          artwork:'orena-home',
          artworkLabel:'',
          accentFamily:'listening',
          primaryAction:{
            id:'homePrimary',
            label:continuation?t('home.h1_hero_continue'):t('home.h1_hero_explore'),
          },
          continuation:continuationMarkup(continuation),
        })}

        ${worldsSection(sections.worlds)}

        <div class="oc-home-row" data-columns="${challengeSection?'2':'1'}">
          ${forYouSection}
          ${challengeSection}
        </div>

        ${discoverySection(sections.library,surfaced)}
      </div>
    </div>`;
  }

  /* --------------------------------------------------------- behaviour --- */

  const openLesson=(lessonId,sourceUrl,segmentId='',mode='')=>{
    if(!lessonId&&!sourceUrl)return;
    requestLessonAutostart(state.language,sourceUrl||'',{
      lesson_id:lessonId||'',
      selected_segment_id:segmentId||'',
      mode:mode||'',
    });
    go('listen');
  };

  async function openEssay(id){
    try{
      const essay=await api.essay(id);
      state.lastEvaluation=essay;
      state.draft={
        ...state.draft,
        text:essay.text||'',
        html:essay.html||'',
        prompt:essay.prompt||'',
        parentEssayId:essay.id,
        level:essay.target_cefr||state.draft.level,
        practiceContext:essay.practice_context||null,
      };
      go('review');
    }catch(error){
      root.insertAdjacentHTML('afterbegin',errorBlock(error.message));
    }
  }

  const startRecommendedPractice=async(button,recommendation)=>{
    await runBusy(button,async()=>{
      const task=await api.nextPractice({target_level:recommendation?.target_level||state.draft.level||''});
      const personalization=task.personalization||recommendation;
      saveDraft({
        mode:task.task_type||personalization.task_type||'opinion',
        topic:task.topic||personalization.topic||'random',
        level:personalization.target_level||state.draft.level,
        length:Number(task.word_target||personalization.word_target||state.draft.length),
        prompt:task.prompt||'',
        generatedTask:task,
        practiceContext:personalization,
        text:'',
        html:'',
        savedAt:null,
        parentEssayId:null,
      });
      state.practiceRecommendation=personalization;
      go('write');
    },{label:t('busy.creating')});
  };

  function bind(){
    const {continuation,nextPlan,dueReview,recommendation,localListening}=handlers;

    /* The hero's single action follows the continuation it was rendered with,
       so the button never promises something the page cannot deliver. */
    root.querySelector('#homePrimary')?.addEventListener('click',()=>{
      if(continuation?.kind==='listening'){
        openLesson(continuation.lessonId,continuation.sourceUrl,continuation.segmentId);
        return;
      }
      if(continuation?.kind==='listening-local'){
        openLesson(continuation.lesson.lesson_id,continuation.lesson.source_url,continuation.lesson.selected_segment_id,continuation.lesson.mode);
        return;
      }
      if(continuation?.kind==='writing'){
        go('write');
        return;
      }
      go('listen');
    });

    root.querySelector('[data-home-continue="listening"]')?.addEventListener('click',()=>{
      if(continuation?.kind!=='listening')return;
      openLesson(continuation.lessonId,continuation.sourceUrl,continuation.segmentId);
    });
    root.querySelector('[data-home-continue="writing"]')?.addEventListener('click',()=>go('write'));
    root.querySelector('[data-home-resume-listening]')?.addEventListener('click',()=>{
      const lesson=continuation?.lesson||localListening;
      if(!lesson)return;
      openLesson(lesson.lesson_id,lesson.source_url,lesson.selected_segment_id,lesson.mode);
    });

    /* Entering a World opens the lesson that leads it. There is no Explore
       route yet and inventing one would be a fake destination, so the card
       hands off through the existing lesson autostart contract. */
    root.querySelectorAll('[data-world-open]').forEach(button=>button.addEventListener('click',()=>{
      openLesson(button.dataset?.worldLesson||'',button.dataset?.worldUrl||'');
    }));

    root.querySelectorAll('[data-home-open-lesson]').forEach(button=>button.addEventListener('click',()=>{
      openLesson(button.dataset.homeOpenLesson||'',button.dataset.homeOpenLessonUrl||'');
    }));

    root.querySelector('[data-home-listening-goal]')?.addEventListener('click',()=>go('listen'));

    root.querySelector('[data-home-library-review-action]')?.addEventListener('click',()=>{
      if(!dueReview)return;
      state.libraryReviewWord=dueReview.word;
      state.libraryReviewLanguage=state.language;
      go('library');
    });

    root.querySelector('[data-home-next-plan-action]')?.addEventListener('click',async()=>{
      if(!nextPlan)return;
      if(nextPlan.kind==='writing-draft'){
        go('write');
      }else if(nextPlan.kind==='writing'||nextPlan.kind==='baseline'){
        const button=root.querySelector('[data-home-next-plan-action]');
        try{
          await startRecommendedPractice(button,recommendation);
        }catch(error){
          root.insertAdjacentHTML('afterbegin',errorBlock(error.message||t('busy.working')));
        }
      }else if(nextPlan.kind==='listening'&&(nextPlan.lesson?.source_url||nextPlan.lesson?.lesson_id)){
        openLesson(nextPlan.lesson.lesson_id,nextPlan.lesson.source_url,nextPlan.lesson.selected_segment_id,nextPlan.lesson.mode);
      }else if(nextPlan.kind==='reading'){
        try{
          const loaded=await api.readingSession(nextPlan.sessionId);
          if(loaded?.found&&loaded.session){
            state.readingSession=loaded.session;
            state.readingResult=null;
            go('read');
            return;
          }
        }catch{}
        state.readingSession=null;
        state.readingResult=null;
        go('read');
      }else if(nextPlan.kind==='speaking'){
        selectSharedMediaSegment(state.language,nextPlan.segmentId);
        go('speak');
      }
    });

    root.querySelectorAll('[data-home-open-grammar]').forEach(button=>button.addEventListener('click',()=>{
      const id=button.dataset.homeOpenGrammar;
      if(!id)return;
      try{ localStorage.setItem('becoming.grammar-focus',id); }catch{}
      go('grammar');
    }));
    root.querySelectorAll('[data-home-open-review]').forEach(button=>button.addEventListener('click',()=>openEssay(button.dataset.homeOpenReview)));
    root.querySelectorAll('[data-home-practice-grammar]').forEach(button=>button.addEventListener('click',async()=>{
      const id=button.dataset.homePracticeGrammar;
      if(!id)return;
      try{
        await runBusy(button,async()=>{
          const task=await api.grammarPractice(id,button.dataset.homePracticeEvidence||'');
          if(!task||typeof task!=='object'||typeof task.prompt!=='string'||!task.prompt.trim()){
            throw new Error(t('review.practice_failed'));
          }
          const context=task.practice_context&&typeof task.practice_context==='object'
            ?task.practice_context:null;
          saveDraft({
            prompt:task.prompt.trim(),text:'',html:'',
            savedAt:null,
            mode:context?.task_type||state.draft.mode,
            topic:context?.topic||state.draft.topic,
            level:task.target_level||context?.target_level||state.draft.level,
            practiceContext:context,generatedTask:null,
            parentEssayId:Number(button.dataset.homePracticeEssay||0)>0
              &&Number.isInteger(Number(button.dataset.homePracticeEssay))
              ?Number(button.dataset.homePracticeEssay):null,
          });
          go('write');
        },{label:t('busy.creating')});
      }catch(error){ root.insertAdjacentHTML('afterbegin',errorBlock(error.message||t('review.practice_failed'))); }
    }));

    root.querySelectorAll('[data-open-review-cue]').forEach(button=>{
      button.addEventListener('click',()=>openEssay(button.dataset.openReviewCue));
    });

    root.querySelector('[data-cross-skill-kind]')?.addEventListener('click',async event=>{
      const button=event.currentTarget;
      const kind=button.dataset.crossSkillKind;
      if(kind==='review')return openEssay(button.dataset.crossSkillEssay);
      if(kind==='reading'){
        try{const loaded=await api.readingSession(button.dataset.crossSkillSession); if(loaded?.found&&loaded.session)state.readingSession=loaded.session;}catch{}
        state.readingResult=null; go('read'); return;
      }
      if(kind==='listening'){
        if(button.dataset.crossSkillUrl)requestLessonAutostart(state.language,button.dataset.crossSkillUrl,{source_url:button.dataset.crossSkillUrl,title:button.dataset.crossSkillTitle,selected_segment_id:button.dataset.crossSkillSegment});
        selectSharedMediaSegment(state.language,button.dataset.crossSkillSegment||''); go('listen'); return;
      }
      if(kind==='speaking'&&button.dataset.crossSkillAsset&&button.dataset.crossSkillSegment){
        selectSharedMediaSegment(state.language,button.dataset.crossSkillSegment); go('speak');
      }
    });
  }

  function paint(){
    // Home is no longer the active screen: this root belongs to whatever the
    // learner navigated to, and a late repaint would clobber it.
    if(disposed)return;
    try{
      root.innerHTML=compose();
      bind();
    }catch(error){
      root.innerHTML=`<section class="page">${errorBlock(error.message)}</section>`;
    }
  }

  // First paint: hero, the local continuation and per-section loading states,
  // before a single request has resolved.
  paint();

  /* A rejection is an error state; a successful empty answer is a ready state
     with nothing in it. Those are different things to a learner - "we could
     not load this" versus "there is nothing here yet" - so they are kept
     apart rather than collapsed into one null. */
  const settle=(key,load)=>Promise.resolve()
    .then(load)
    .then(
      data=>{ sections[key]={status:'ready',data}; },
      ()=>{ sections[key]={status:'error',data:null}; },
    )
    .then(paint);

  /* The global chrome shows a streak cue from state.dashboard. Home renders no
     analytics itself; it just keeps that shared state populated, and nothing on
     this screen waits for it. */
  const chrome=optional(()=>api.dashboard()).then(dashboard=>{
    // Checked here, not at call time: staleness is a property of the moment
    // this resolves, not the moment it was requested.
    if(dashboard&&!stale())state.dashboard=dashboard;
  });

  /* Six independent sub-requests, each free to fail on its own without taking
     the others down - a missing reading history must not cost the learner
     their practice outcome. But `optional()`'s per-call swallow, used
     everywhere else on this screen, would erase the difference between "every
     one of these failed" and "every one of these truthfully has nothing to
     say", and personal is the one section where that difference matters: the
     first is a provider outage, the second is a genuine new-learner state.
     `Promise.allSettled` keeps the per-call resilience and still lets a total
     failure surface as one, by rejecting only when NOTHING came back. Each
     call is invoked inside its own try, not just awaited: a call that throws
     synchronously rather than returning a rejected promise (an unconfigured
     endpoint, say) must still cost only its own slot, not abort the batch
     before `allSettled` ever sees the other five. */
  const safeCall=load=>{
    try{ return Promise.resolve(load()); }
    catch(error){ return Promise.reject(error); }
  };
  const personal=async()=>{
    const results=await Promise.allSettled([
      safeCall(()=>api.practiceRecommendation()),
      safeCall(()=>api.practiceOutcomes(1)),
      safeCall(()=>api.learningMemory()),
      safeCall(()=>api.readingSessions(8)),
      safeCall(()=>api.speakingAttempts(1)),
      safeCall(()=>api.crossSkillCue()),
    ]);
    if(results.every(result=>result.status==='rejected')){
      throw new Error('personal recommendations unavailable');
    }
    const [recommendation,outcomes,memory,readingHistory,speakingHistory,crossCue]=results.map(
      result=>result.status==='fulfilled'?result.value:null,
    );
    // Checked here, at the moment this batch actually resolves, not at the
    // moment it was requested - a request fired while Home was current can
    // still land after cleanup, or after the learning language changed.
    if(!stale()){
      if(memory)state.memory=memory;
      state.practiceRecommendation=recommendation;
      state.latestPracticeOutcome=outcomes?.latest||null;
    }
    return {recommendation,outcomes,memory,readingHistory,speakingHistory,crossCue};
  };

  const settled=Promise.all([
    chrome,
    settle('library',()=>api.listeningLibrary(state.language)),
    settle('worlds',()=>api.worlds(state.language)),
    settle('vocabulary',()=>api.libraryVocabulary()),
    settle('personal',personal),
  ]);

  /* Every one of those already resolves on its own - `optional()` and
     `settle()` both turn a rejection into a state rather than letting it
     propagate - so this budget is not a timeout for a slow request. It exists
     for the one case neither of those helpers can catch: a request that never
     settles at all. Without a ceiling here, renderCurrent()'s `await
     screen(root)` in app.js would never proceed past this call, leaving
     aria-busy stuck at "true" for the rest of the session. Racing against a
     bound lets the render lifecycle move on while the real request keeps
     running in the background and still paints through settle() if it ever
     answers.

     `disposal` races alongside it for a narrower reason: cleanup can happen
     well inside the budget, once the learner has already navigated on to
     another screen. Without `disposal` in this race, THIS render's own
     lifecycle - the one that already stopped mattering the moment
     `root._cleanupScreen` ran - would still hold app.js's `await
     screen(root)` open for whatever's left of the budget, even though
     nothing it does from here can reach the page. Disposal lets it resolve
     immediately instead. */
  let budgetTimer=null;
  const budget=new Promise(resolve=>{ budgetTimer=setTimeout(resolve,sectionBudgetMs); });
  await Promise.race([settled,budget,disposal]);
  // The common case is `settled` winning well inside the budget; clearing the
  // timer then means an outstanding request does not leave a live timer
  // behind it for the rest of the session (or, in a test process, for the
  // rest of the run).
  clearTimeout(budgetTimer);
}
