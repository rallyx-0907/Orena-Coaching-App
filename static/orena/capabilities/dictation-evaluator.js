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
  /* A missing expected word and an extra written one are the same event when
     the learner was reaching for that word and mistyped it. Pairing only
     immediate neighbours gets this wrong as soon as two words in a row are
     misspelt: the run reorders and later words pair with the wrong partners,
     which then shifts every anchor after them. So a run of unmatched entries is
     paired by position within the run, and only where the two words genuinely
     resemble each other - "stars"/"stors" is one attempt, "the"/"safely" is a
     missing word and a different extra one. */
  const aligned=[];
  for(let index=0;index<raw.length;){
    if(!['missing','extra'].includes(raw[index].status)){aligned.push(raw[index]);index+=1;continue;}
    let end=index;
    while(end<raw.length&&['missing','extra'].includes(raw[end].status))end+=1;
    const run=raw.slice(index,end);
    const missing=run.filter(item=>item.status==='missing');
    const extra=run.filter(item=>item.status==='extra');
    const pairedExtra=new Set();
    const pairs=new Map();
    missing.forEach((item,position)=>{
      const candidate=extra[position];
      if(candidate&&!pairedExtra.has(candidate)&&wordsResemble(item.expected,candidate.actual)){
        pairs.set(item,candidate);pairedExtra.add(candidate);
      }
    });
    for(const item of run){
      if(item.status==='missing'){
        const partner=pairs.get(item);
        aligned.push(partner
          ?{status:'wrong',expected:item.expected,actual:partner.actual}
          :item);
      }else if(!pairedExtra.has(item))aligned.push(item);
    }
    index=end;
  }
  return aligned;
}

/* Two words are the same attempt when most of one survives in the other. Below
   that they are separate events, and calling them one correction would tell the
   learner they mistyped a word they never reached for. */
export function wordsResemble(expected,actual){
  const a=[...String(expected||'').toLowerCase()],b=[...String(actual||'').toLowerCase()];
  if(!a.length||!b.length)return false;
  const grid=Array.from({length:a.length+1},()=>new Uint16Array(b.length+1));
  for(let row=a.length-1;row>=0;row-=1)
    for(let column=b.length-1;column>=0;column-=1)
      grid[row][column]=a[row]===b[column]
        ?grid[row+1][column+1]+1
        :Math.max(grid[row+1][column],grid[row][column+1]);
  return grid[0][0]/Math.max(a.length,b.length)>=0.5;
}

