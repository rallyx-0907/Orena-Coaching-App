function words(text){
  return String(text||'').trim().split(/\s+/).filter(Boolean);
}

function joinedText(parts){
  const accepted=[];
  for(const raw of parts){
    const part=String(raw||'').trim();
    if(!part)continue;
    if(!accepted.length){
      accepted.push(part);
      continue;
    }

    const priorWords=words(accepted.join(' '));
    const nextWords=words(part);
    let overlap=0;
    const max=Math.min(8,priorWords.length,nextWords.length);
    for(let size=max;size>=1;size-=1){
      const left=priorWords.slice(-size).join(' ').toLowerCase();
      const right=nextWords.slice(0,size).join(' ').toLowerCase();
      if(left===right){
        overlap=size;
        break;
      }
    }
    accepted.push(nextWords.slice(overlap).join(' '));
  }
  return accepted.filter(Boolean).join(' ').replace(/\s+/g,' ').trim();
}

const ENGLISH_NON_TERMINAL_TOKENS=new Set([
  'a','an','the','and','or','but','so','to','of','in','on','at','for','with','from','by',
  'is','are','was','were','be','been','being','do','does','did','have','has','had',
  'can','could','will','would','should','may','might','must','i','you','we','they','he','she','it','this','that','these','those',
]);

function groupingLanguage(text){
  return /\p{Script=Han}/u.test(String(text||''))?'zh':'en';
}

function englishPlausibleBoundary(text){
  const tail=String(text||'').trim().match(/[\p{L}]+(?:['’][\p{L}]+)?$/u)?.[0]?.toLocaleLowerCase();
  return Boolean(tail)&&!ENGLISH_NON_TERMINAL_TOKENS.has(tail);
}

function boundaryFor(text,language){
  const value=String(text||'').trim();
  if(language==='zh'){
    return {
      strong:/[。！？；][”’」』）)]?$/.test(value),
      clause:/[，、][”’」』）)]?$/.test(value),
      plausible:!/[，、]$/.test(value),
    };
  }
  return {
    strong:/[.!?]["'”’)]?$/.test(value),
    clause:false,
    plausible:englishPlausibleBoundary(value),
  };
}

function unitFrom(group,endMs){
  const first=group[0];
  return {
    segment_id:first.segment_id,
    canonical_segment_ids:group.map(item=>item.segment_id),
    order:first.order,
    start_ms:first.start_ms,
    end_ms:Math.max(first.start_ms+1,endMs),
    original_text:joinedText(group.map(item=>item.original_text)),
  };
}

export function buildTranscriptDisplayUnits(
  input,
  {maxDurationMs=6000,maxWords=18,maxChars=110,pauseBreakMs=550}={}
){
  const segments=(Array.isArray(input)?input:[])
    .filter(item=>item&&typeof item.segment_id==='string'
      &&Number.isFinite(Number(item.start_ms))
      &&Number.isFinite(Number(item.end_ms))
      &&typeof item.original_text==='string')
    .map(item=>({...item,start_ms:Number(item.start_ms),end_ms:Number(item.end_ms)}))
    .sort((a,b)=>a.start_ms-b.start_ms||Number(a.order)-Number(b.order));

  if(!segments.length)return [];

  const units=[];
  let group=[segments[0]];

  for(let index=1;index<segments.length;index+=1){
    const next=segments[index];
    const current=group[group.length-1];
    const currentText=joinedText(group.map(item=>item.original_text));
    const durationToNext=next.start_ms-group[0].start_ms;
    const rawGap=next.start_ms-current.end_ms;

    const language=groupingLanguage(currentText);
    const boundary=boundaryFor(current.original_text,language);
    const accumulated=boundaryFor(currentText,language);
    const pressure=durationToNext>=maxDurationMs||words(currentText).length>=maxWords||currentText.length>=maxChars;
    const pauseBoundary=rawGap>=pauseBreakMs&&(language==='zh'||accumulated.plausible);
    const pressureBoundary=language==='zh'?accumulated.clause:accumulated.plausible;
    const safeBreak=boundary.strong
      ||pauseBoundary
      ||(pressure&&pressureBoundary);
    const hardSafety=(durationToNext>=maxDurationMs*2
      ||words(currentText).length>=maxWords*2
      ||currentText.length>=maxChars*2);
    const shouldBreak=safeBreak||hardSafety;

    if(shouldBreak){
      units.push(unitFrom(group,Math.max(group[0].start_ms+1,next.start_ms)));
      group=[next];
    }else{
      group.push(next);
    }
  }

  const last=group[group.length-1];
  units.push(unitFrom(group,Math.max(last.end_ms,last.start_ms+1)));
  return units;
}

export function displayUnitContains(unit,segmentId){
  return Array.isArray(unit?.canonical_segment_ids)
    &&unit.canonical_segment_ids.includes(segmentId);
}

export function displayUnitMeaning(unit,translations){
  if(!(translations instanceof Map))return '';
  return (unit?.canonical_segment_ids||[])
    .map(id=>translations.get(id))
    .filter(value=>typeof value==='string'&&value.trim())
    .map(value=>value.trim())
    .join(' ')
    .replace(/\s+/g,' ')
    .trim();
}
