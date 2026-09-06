const pick=(object,keys)=>Object.fromEntries(keys.filter(key=>object[key]!==undefined).map(key=>[key,object[key]]));
export function translationRequest(payload,target_language) {
  return {target_language,asset:pick(payload.asset,['asset_id','source_url','source_provider','source_type','title','source_language','processing_state','duration_ms','transcript_available']),transcript:{asset_id:payload.transcript.asset_id,source_language:payload.transcript.source_language,segments:payload.transcript.segments.map(x=>pick(x,['segment_id','order','start_ms','end_ms','original_text']))}};
}
export async function acquireMedia({api,url,target,owner,language,alive=()=>true,onProgress=()=>{},storage}) {
  if(!storage){try{storage=globalThis.localStorage;}catch{storage={getItem(){return null;},setItem(){},removeItem(){}};}}
  const key=`orena.acquisition.v1:${encodeURIComponent(owner)}:${language}:${encodeURIComponent(url)}`;
  let handle=null;try{handle=JSON.parse(storage.getItem(key)||'null');}catch{}
  let result;
  if(handle?.job_id&&handle.target===target) {
    try{result=await api.mediaImportStatus({job_id:handle.job_id});}
    catch(error){if(error.status===404){try{storage.removeItem(key);}catch{}}throw error;}
  }else result=await api.importMedia({source_url:url,target_language:target,include_translation:true,include_word_timing:true});
  if(alive())onProgress(result);
  for(let attempt=0;alive()&&result?.import_job?.resumable&&attempt<40;attempt++) {
    try{storage.setItem(key,JSON.stringify({job_id:result.import_job.job_id,target}));}catch{}
    await new Promise(resolve=>setTimeout(resolve,1000));if(!alive())return null;
    result=await api.mediaImportStatus({job_id:result.import_job.job_id});
    if(alive())onProgress(result);
  }
  if(result?.transcript?.segments?.length){try{storage.removeItem(key);}catch{}}
  return result;
}
