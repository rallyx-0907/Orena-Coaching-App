/* Reference preparation for Compare, never a learner attempt. Audio and word
   boundaries come from the real source; dictionary readings are deterministic.
   Ephemeral projections reuse existing domain APIs, not a second data authority. */
import { lineUnits, placeWords } from './speaking-line.js';
import { toneOf } from '../capabilities/pronunciation-result.js';
import { isRemovedContent, removedImportError, onRemovedImports } from './import-removed.js';

const finite = value => typeof value === 'number' && Number.isFinite(value);
const keyOf = text => String(text || '').toLocaleLowerCase();
const timed = word => word.offsetKnown && finite(word.offsetMs) && finite(word.durationMs) && word.offsetMs >= 0 && word.durationMs > 0;

export function pairWord(text, learnerWords, index, modelWords, language) {
  const wanted = placeWords(text, learnerWords, language)[index];
  if (!wanted) return null;
  const positions = placeWords(text, modelWords || [], language);
  const parts = (modelWords || []).flatMap((word, at) => {
    const position = positions[at];
    return position && position.start >= wanted.start && position.end <= wanted.end ? [{word,position}] : [];
  });
  if (!parts.length || parts[0].position.start !== wanted.start || parts.at(-1).position.end !== wanted.end || parts.some(part=>!timed(part.word))) return null;
  for (let at=1;at<parts.length;at++) {
    if (parts[at].position.start !== parts[at-1].position.end || parts[at].word.offsetMs < parts[at-1].word.offsetMs) return null;
  }
  const from=parts[0].word.offsetMs, last=parts.at(-1).word;
  return {text:text.slice(wanted.start,wanted.end),offsetKnown:true,offsetMs:from,durationMs:last.offsetMs+last.durationMs-from};
}

export function readingFor(text, reference, language, start = null) {
  if (start != null) {
    const parts=(reference?.positionReadings || []).filter(p=>p.start>=start && p.end<=start+text.length);
    if (parts.length && parts[0].start===start && parts.at(-1).end===start+text.length) return parts.map(p=>p.reading).join(language==='zh'?' ':'');
  }
  const direct = reference?.readings?.[keyOf(text)] || '';
  if (direct || language !== 'zh') return direct;
  const chars=[...text].filter(ch=>/\p{Script=Han}/u.test(ch));
  const readings=chars.map(ch=>reference?.readings?.[ch] || '');
  return readings.length && readings.every(Boolean) ? readings.join(' ') : '';
}

export function pairedTiming(youWord, modelWord, youWords, modelWords) {
  const base=words=>Math.min(...(words || []).filter(timed).map(word=>word.offsetMs));
  const span=words=>{
    const valid=(words || []).filter(timed);
    return valid.length ? (Math.max(...valid.map(w=>w.offsetMs+w.durationMs))-base(valid))/1000 : 0;
  };
  const row=(word,words)=>timed(word || {}) ? {from:(word.offsetMs-base(words))/1000,to:(word.offsetMs+word.durationMs-base(words))/1000} : null;
  return {you:row(youWord,youWords),model:row(modelWord,modelWords),total:Math.max(span(youWords),span(modelWords)),
    deltaMs:timed(youWord || {}) && timed(modelWord || {}) ? youWord.durationMs-modelWord.durationMs : null};
}

export function decorateComparison(view, source, reference) {
  if (!view) return view;
  const positions=placeWords(source.line.text,view.words || [],source.language);
  const words=(view.words || []).map((word,index)=>{
    const reading=readingFor(word.text,reference,source.language,positions[index]?.start) || word.pinyin || '';
    return {...word,reading,...(source.language === 'zh' && reading ? {pinyin:reading,toneTarget:reading.split(/\s+/).map(toneOf).filter(n=>n!=null)} : {})};
  });
  const intervals=(reference?.words || []).filter(timed);
  const modelMs=intervals.length ? Math.max(...intervals.map(w=>w.offsetMs+w.durationMs))-Math.min(...intervals.map(w=>w.offsetMs)) : null;
  const timing=view.timing && modelMs > 0 ? {...view.timing,modelMs,deltaMs:Math.round((view.timing.learnerMs-modelMs)/100)*100} : view.timing;
  return {...view,words,timing};
}

export async function loadComparisonReference(source, {onUpdate=()=>{}} = {}) {
  // A workspace projects admitted source artifacts. It never prepares a source.
  const words=(source.line.wordTimings || []).filter(timed);
  const state={readings:{},positionReadings:[...(source.line.positionReadings || [])],words,model:null,
    readingState:'unavailable',audioState:source.hasModelAudio?'ready':'unavailable',
    alignmentState:words.length?'ready':'unavailable'};
  const units=lineUnits(source.line.text,source.language).filter(unit=>unit.unit);
  const authored=String(source.line.reading || '').split(/\s+/).filter(Boolean);
  if (authored.length===units.length) units.forEach((unit,at)=>{
    state.positionReadings.push({...unit,reading:authored[at]});
  });
  for (const word of words) if (word.ipa) state.readings[keyOf(word.text)]=word.ipa;
  state.readingState=state.positionReadings.length || Object.keys(state.readings).length?'ready':'unavailable';
  onUpdate(state);
  return state;
}

const references=new Map();
const sourceContentId=source=>source.lessonId || source.sourceId?.replace(/^media:/,'') || '';
function removeReference(key) {
  clearTimeout(references.get(key)?.timer);
  references.delete(key);
}
onRemovedImports(scope=>{
  for (const [key,entry] of references) {
    if (entry.scope !== scope || isRemovedContent(entry.contentId)) removeReference(key);
  }
});
export async function comparisonReference(source, options) {
  const contentId=sourceContentId(source);
  if (isRemovedContent(contentId)) throw removedImportError();
  const key=JSON.stringify([options.owner,source.language,options.support,source.sourceId,source.line]);
  const cached=references.get(key);
  if (!options.fresh && cached && cached.expires > Date.now()) return cached.promise;
  if (cached) removeReference(key);
  const promise=loadComparisonReference(source,{...options,onUpdate(value){
    if (!isRemovedContent(contentId)) options.onUpdate?.(value);
  }}).then(value=>{
    if (isRemovedContent(contentId)) throw removedImportError();
    return value;
  });
  const timer=setTimeout(()=>removeReference(key),5*60*1000);
  timer.unref?.();
  references.set(key,{promise,timer,contentId,scope:`${options.owner}:${source.language}`,expires:Date.now()+5*60*1000});
  if (references.size>24) removeReference(references.keys().next().value);
  return promise;
}
