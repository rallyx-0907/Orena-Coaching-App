/* Reference preparation for Compare, never a learner attempt. Audio and word
   boundaries come from the real source; dictionary readings are deterministic.
   Ephemeral projections reuse existing domain APIs, not a second data authority. */
import { lineUnits, placeWords } from './speaking-line.js';
import { decodeAudio, analyse } from '../capabilities/audio-analysis.js';
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
    /* English: IPA is only what the assessment provider returned for this word (D-139 HD-5), never a
       dictionary's; nothing returned, nothing shown. Chinese: the lesson's own pinyin. */
    const reading=source.language === 'en' ? (word.phonemes || []).map(unit=>unit.label).join('')
      : readingFor(word.text,reference,source.language,positions[index]?.start) || word.pinyin || '';
    return {...word,reading,...(source.language === 'zh' && reading ? {pinyin:reading,toneTarget:reading.split(/\s+/).map(toneOf).filter(n=>n!=null)} : {})};
  });
  const intervals=(reference?.words || []).filter(timed);
  const modelMs=intervals.length ? Math.max(...intervals.map(w=>w.offsetMs+w.durationMs))-Math.min(...intervals.map(w=>w.offsetMs)) : null;
  const timing=view.timing && modelMs > 0 ? {...view.timing,modelMs,deltaMs:Math.round((view.timing.learnerMs-modelMs)/100)*100} : view.timing;
  return {...view,words,timing};
}

/* Where a model's words sit when no verified word timing exists (D-140, labelled "est." - D-137 L-13):
   the voiced span of the measured contour, shared out by how much each word has to say - its letters
   (English), one share per Han character and a Latin run by its letters (Chinese). A guess, flagged as
   one, and only ever made when the contour has at least two voiced points. */
export function estimateModelWords(text, language, model) {
  const voiced=(model?.contour || []).filter(point=>point?.st!=null && finite(point.t));
  if (voiced.length<2) return [];
  const hop=model.contour.length>1 ? Math.max(0,model.contour[1].t-model.contour[0].t) : 0.01;
  const from=voiced[0].t, to=voiced.at(-1).t+hop;
  const units=lineUnits(text,language).filter(unit=>unit.unit);
  const weight=unit=>language==='zh' && /^\p{Script=Han}$/u.test(unit.text) ? 1 : [...unit.text].filter(ch=>/[\p{L}\p{N}]/u.test(ch)).length;
  const total=units.reduce((sum,unit)=>sum+weight(unit),0);
  if (!units.length || total<=0 || to<=from) return [];
  const span=(to-from)*1000;
  let used=0;
  return units.map(unit=>{
    const offsetMs=Math.round(from*1000+span*used/total);
    used+=weight(unit);
    const end=Math.round(from*1000+span*used/total);
    return {text:unit.text,offsetKnown:true,offsetMs,durationMs:Math.max(1,end-offsetMs),estimated:true};
  });
}

export async function loadComparisonReference(source, {onUpdate=()=>{},fetchImpl=globalThis.fetch,decode=decodeAudio,analyse:measure=analyse} = {}) {
  // A workspace projects admitted source artifacts. It never prepares a source.
  const words=(source.line.wordTimings || []).filter(timed);
  const state={readings:{},positionReadings:[...(source.line.positionReadings || [])],words,model:null,timingEstimated:false,
    readingState:'unavailable',audioState:source.hasModelAudio?'ready':'unavailable',
    alignmentState:words.length?'ready':'unavailable'};
  // An authored Chinese reading has one syllable per Han character; a Latin word in the line has none (LEX-031).
  const units=lineUnits(source.line.text,source.language).filter(unit=>unit.unit&&(source.language!=='zh'||/\p{Script=Han}/u.test(unit.text)));
  const authored=String(source.line.reading || '').split(/\s+/).filter(Boolean);
  if (authored.length===units.length) units.forEach((unit,at)=>{
    state.positionReadings.push({...unit,reading:authored[at]});
  });
  for (const word of words) if (word.ipa) state.readings[keyOf(word.text)]=word.ipa;
  state.readingState=state.positionReadings.length || Object.keys(state.readings).length?'ready':'unavailable';
  // The one network read a reference makes: the clip prepared at content readiness, and only when the lesson
  // says it exists (D-140). Absent a prepared clip nothing is fetched and the model plot is unavailable.
  if (source.line.modelClipUrl) {
    try {
      const response=await fetchImpl(source.line.modelClipUrl,{credentials:'same-origin'});
      if (!response.ok) throw Error('model_clip_unavailable');
      state.model=measure(await decode(await response.blob()));
      if (!words.length) {
        const estimated=estimateModelWords(source.line.text,source.language,state.model);
        if (estimated.length) {
          state.words=estimated;
          state.timingEstimated=true;
          state.alignmentState='ready';
        }
      }
    } catch {
      state.model=null;
      state.audioState='unavailable';
    }
  }
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
