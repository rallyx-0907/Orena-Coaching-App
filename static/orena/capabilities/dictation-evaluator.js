export const MAX_LISTENING_RECONSTRUCTION_CHARS=2000;
export const MAX_LISTENING_EVALUATION_UNITS=500;

export class ListeningPracticeError extends Error{
  constructor(code,message){super(message);this.name='ListeningPracticeError';this.code=code;}
}

function normalizedText(value){
  return String(value??'')
    .normalize('NFKC')
    .replace(/[\u2018\u2019\u02bc]/g,"'")
    .replace(/[\u2010-\u2015\u2212]/g,'-')
    .replace(/\s+/gu,' ')
    .trim();
}

export function listeningUnits(value,sourceLanguage){
  const normalized=normalizedText(value);
  if(sourceLanguage==='zh'){
    return (normalized.match(/\p{Script=Han}|[\p{L}\p{N}]+(?:['-][\p{L}\p{N}]+)*/gu)||[])
      .map(unit=>/^\p{Script=Han}$/u.test(unit)?unit:unit.toLocaleLowerCase('en'));
  }
  return (normalized.toLocaleLowerCase('en').match(/[\p{L}\p{N}]+(?:['-][\p{L}\p{N}]+)*/gu)||[]);
}

export function listeningEditDistance(expectedUnits,answerUnits){
  let previous=Array.from({length:answerUnits.length+1},(_,index)=>index);
  for(let row=1;row<=expectedUnits.length;row+=1){
    const current=[row];
    for(let column=1;column<=answerUnits.length;column+=1){
      const substitution=previous[column-1]+(expectedUnits[row-1]===answerUnits[column-1]?0:1);
      current[column]=Math.min(previous[column]+1,current[column-1]+1,substitution);
    }
    previous=current;
  }
  return previous[answerUnits.length];
}

export function evaluateListeningReconstruction({source_language,expected,answer}){
  const expectedText=normalizedText(expected);
  const answerText=normalizedText(answer);
  if(!expectedText)throw new ListeningPracticeError('canonical_empty','The canonical transcript segment is empty.');
  if(!answerText)throw new ListeningPracticeError('answer_empty','Type what you heard before checking.');
  if(answerText.length>MAX_LISTENING_RECONSTRUCTION_CHARS){
    throw new ListeningPracticeError('answer_too_large','Your reconstruction is too long to check safely.');
  }
  const expectedUnits=listeningUnits(expectedText,source_language);
  const answerUnits=listeningUnits(answerText,source_language);
  if(!expectedUnits.length)throw new ListeningPracticeError('canonical_empty','The canonical transcript segment has no comparable text.');
  if(!answerUnits.length)throw new ListeningPracticeError('answer_empty','Type what you heard before checking.');
  if(expectedUnits.length>MAX_LISTENING_EVALUATION_UNITS||answerUnits.length>MAX_LISTENING_EVALUATION_UNITS){
    throw new ListeningPracticeError('evaluation_too_large','This segment is too large to check safely.');
  }
  const edit_distance=listeningEditDistance(expectedUnits,answerUnits);
  const denominator=Math.max(expectedUnits.length,answerUnits.length);
  const accuracy_percent=Math.round(Math.max(0,Math.min(1,1-edit_distance/denominator))*100);
  return {
    accuracy_percent,
    exact:edit_distance===0,
    expected_unit_count:expectedUnits.length,
    answer_unit_count:answerUnits.length,
    edit_distance,
  };
}

/* A learner-facing alignment over the same normalized units used for scoring.
   This is intentionally deterministic and language-aware: punctuation and
   harmless spacing never appear as mistakes, while Hanzi remain character
   units. */
export function listeningReconstructionDiff({source_language,expected,answer}){
  const expectedUnits=listeningUnits(expected,source_language);
  const answerUnits=listeningUnits(answer,source_language);
  const common=Array.from({length:expectedUnits.length+1},()=>Array(answerUnits.length+1).fill(0));
  for(let row=expectedUnits.length-1;row>=0;row-=1){
    for(let column=answerUnits.length-1;column>=0;column-=1){
      common[row][column]=expectedUnits[row]===answerUnits[column]
        ?common[row+1][column+1]+1
        :Math.max(common[row+1][column],common[row][column+1]);
    }
  }
  const raw=[];
  let row=0,column=0;
  while(row<expectedUnits.length||column<answerUnits.length){
    if(row<expectedUnits.length&&column<answerUnits.length&&expectedUnits[row]===answerUnits[column]){
      raw.push({status:'correct',expected:expectedUnits[row],actual:answerUnits[column]});row+=1;column+=1;continue;
    }
    if(row<expectedUnits.length&&(column>=answerUnits.length||common[row+1][column]>=common[row][column+1])){
      raw.push({status:'missing',expected:expectedUnits[row],actual:''});row+=1;continue;
    }
    raw.push({status:'extra',expected:'',actual:answerUnits[column]});column+=1;
  }
  const aligned=[];
  for(let index=0;index<raw.length;index+=1){
    const current=raw[index],next=raw[index+1];
    if(next&&current.status!==next.status&&['missing','extra'].includes(current.status)&&['missing','extra'].includes(next.status)){
      const missing=current.status==='missing'?current:next;
      const extra=current.status==='extra'?current:next;
      aligned.push({status:'wrong',expected:missing.expected,actual:extra.actual});index+=1;
    }else aligned.push(current);
  }
  return aligned;
}

