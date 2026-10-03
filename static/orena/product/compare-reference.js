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
    const reading=readingFor(word.text,reference,source.language,positions[index]?.start) || word.pinyin || '';
    return {...word,reading,...(source.language === 'zh' && reading ? {pinyin:reading,toneTarget:reading.split(/\s+/).map(toneOf).filter(n=>n!=null)} : {})};
  });
  const intervals=(reference?.words || []).filter(timed);
  const modelMs=intervals.length ? Math.max(...intervals.map(w=>w.offsetMs+w.durationMs))-Math.min(...intervals.map(w=>w.offsetMs)) : null;
  const timing=view.timing && modelMs > 0 ? {...view.timing,modelMs,deltaMs:Math.round((view.timing.learnerMs-modelMs)/100)*100} : view.timing;
  return {...view,words,timing};
}

export async function loadComparisonReference(source, {api,support='en',fetchImpl=globalThis.fetch,decode=decodeAudio,analyse:measure=analyse,onUpdate=()=>{}}) {
  const state={readings:{},positionReadings:[],words:[],model:null,readingState:'processing',audioState:source.hasModelAudio?'processing':'unavailable',alignmentState:source.hasModelAudio?'processing':'unavailable'};
  const units=lineUnits(source.line.text,source.language).filter(unit=>unit.unit);
  const authored=String(source.line.reading || '').split(/\s+/).filter(Boolean);
  if (source.language==='zh' && authored.length===units.length) units.forEach((unit,at)=>{state.positionReadings.push({...unit,reading:authored[at]});});
  const unique=[...new Set(units.map(unit=>unit.text))];
  const readingWork=(async()=>{
    if (source.language==='zh' && !state.positionReadings.length && api.annotateMediaText) {
      try {
        const tagged=await api.annotateMediaText({text:source.line.text,source_language:'zh'});
        if (tagged.text === source.line.text) {
          const chars=[...source.line.text];
          for (const token of tagged.annotations || []) {
            if (!Number.isInteger(token.start) || !Number.isInteger(token.end) || token.start<0 || token.end>chars.length) continue;
            const segment=chars.slice(token.start,token.end), readings=String(token.pronunciation || '').split(/\s+/).filter(Boolean);
            if (segment.length!==readings.length) continue;
            let offset=chars.slice(0,token.start).join('').length;
            segment.forEach((ch,at)=>{state.positionReadings.push({start:offset,end:offset+ch.length,reading:readings[at]});offset+=ch.length;});
          }
          onUpdate(state);
        }
      } catch { /* the existing dictionary remains available */ }
    }
    let next=0;
    await Promise.all(Array.from({length:Math.min(4,unique.length)},async()=>{
      while(next<unique.length) {
        const word=unique[next++];
        if (state.readings[keyOf(word)] || units.filter(unit=>unit.text===word).every(unit=>state.positionReadings.some(p=>p.start===unit.start && p.end===unit.end))) continue;
        try {
          const detail=await api.wordDetail({text:word,context:source.line.text,source_language:source.language,target_language:support,depth:'sheet',contextual:false});
          const reading=source.language==='zh' ? detail?.pinyin : detail?.ipa;
          if (reading) state.readings[keyOf(word)]=String(reading);
        } catch { /* one absent dictionary entry does not erase other readings */ }
        onUpdate(state);
      }
    }));
    state.readingState=Object.keys(state.readings).length || state.positionReadings.length?'ready':'unavailable';onUpdate(state);
  })();
  const audioWork=(async()=>{
    if (!source.hasModelAudio) return;
    try {
      const response=await fetchImpl(source.modelAudioUrl(source.line.lineId),{credentials:'same-origin'});
      if (!response.ok) throw Error('model_audio_unavailable');
      const blob=await response.blob();
      const decoded=await decode(blob);
      state.model=measure(decoded);state.audioState='ready';onUpdate(state);
      const canonical=(source.line.wordTimings || []).filter(timed);
      if (canonical.length) state.words=canonical;
      else if (decoded.duration > 0 && decoded.duration <= 30) {
        const result=await api.speakingModelReference(source.lessonId,source.line.lineId);
        if (result.score_kind === 'measured') {
          state.words=(result.words || []).filter(w=>String(w.error_type || '').toLowerCase()!=='insertion').map(w=>({text:w.word || w.text,ipa:w.ipa || '',offsetMs:w.offset_ms,durationMs:w.duration_ms,offsetKnown:finite(w.offset_ms)&&finite(w.duration_ms)&&w.duration_ms>0}));
          if (source.language === 'en') {
            const positions=placeWords(source.line.text,state.words,'en');
            state.words.forEach((word,at)=>{
              if (word.ipa && positions[at] && timed(word)) state.positionReadings.push({...positions[at],reading:word.ipa});
            });
          }
        }
      }
      state.alignmentState=state.words.some(timed)?'ready':'unavailable';
    } catch {
      if (!state.model) state.audioState='unavailable';
      state.alignmentState='unavailable';
    }
    onUpdate(state);
  })();
  await Promise.all([readingWork,audioWork]);
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
