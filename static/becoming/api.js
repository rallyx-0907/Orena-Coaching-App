const JSON_HEADERS = {'Content-Type':'application/json'};

async function request(url, options={}){
  const response = await fetch(url,{
    credentials:'same-origin',
    cache:'no-store',
    ...options,
  });

  let payload=null;
  const type=response.headers.get('content-type')||'';
  if(type.includes('application/json')){
    payload=await response.json();
  }else{
    payload=await response.text();
  }

  if(!response.ok){
    if(response.status===401)location.href='/login';
    const detail=payload && typeof payload==='object' ? payload.detail : payload;
    const structured=detail && typeof detail==='object';
    const rawMessage=structured ? detail.message : detail;
    const looksLikeHtml=typeof rawMessage==='string'&&/(<!doctype|<html[\\s>])/i.test(rawMessage);
    const message=looksLikeHtml ? `Request failed (${response.status}). Please try again.` : rawMessage;
    const error=new Error(typeof message==='string'&&message ? message : `Request failed (${response.status})`);
    /* The canonical envelope, §2.6: a stable category the caller can branch on,
       an explicit answer to whether retrying is worth anything, and a context
       bag for anything a screen needs beyond the sentence. Screens must not
       have to read the human text to decide what happened. */
    if(structured&&typeof detail.category==='string')error.category=detail.category;
    if(structured&&typeof detail.retryable==='boolean')error.retryable=detail.retryable;
    if(structured&&detail.context&&typeof detail.context==='object')error.context=detail.context;
    error.status=response.status;
    throw error;
  }
  return payload;
}

export const api={
  me:()=>request('/api/me'),
  sessionBootstrap:()=>request('/api/session/bootstrap'),
  productMe:()=>request('/api/product/me'),
  adminProductAccount:()=>request('/api/product/admin/account'),
  health:()=>request('/api/health'),
  languages:()=>request('/api/platform/languages'),
  skills:()=>request('/api/platform/skills'),
  setLanguage:(language)=>request('/api/platform/language',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify({language}),
  }),
  dashboard:()=>request('/api/dashboard'),
  learnerProfile:()=>request('/api/learner-profile'),
  saveLearnerProfile:(payload)=>request('/api/learner-profile',{
    method:'PUT',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload),
  }),
  learningMemory:()=>request('/api/learning-memory'),
  reviewCue:(essayId)=>request(`/api/review-cue${essayId!=null?`?essay_id=${encodeURIComponent(essayId)}`:''}`),
  crossSkillCue:()=>request('/api/cross-skill-cue'),
  practiceRecommendation:()=>request('/api/practice-recommendation'),
  nextPractice:(payload)=>request('/api/practice/next',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload||{}),
  }),
  grammarPractice:(id,evidence='')=>{
    const value=typeof evidence==='string'?evidence.trim():'';
    const suffix=value?`?evidence=${encodeURIComponent(value)}`:'';
    return request(`/api/grammar/${encodeURIComponent(id)}/practice${suffix}`);
  },
  practiceOutcome:(id)=>request(`/api/practice-outcome/${encodeURIComponent(id)}`),
  practiceOutcomes:(limit=20)=>request(`/api/practice-outcomes?limit=${encodeURIComponent(limit)}`),
  dictionary:(word)=>request(`/api/dictionary?word=${encodeURIComponent(word)}`),
  contextualDictionary:(payload)=>request('/api/dictionary/contextual',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload||{}),
  }),
  chineseStrokeOrder:(word)=>request(`/api/chinese/stroke-order?word=${encodeURIComponent(word)}`),
  libraryVocabulary:()=>request('/api/library/vocabulary'),
  saveLibraryVocabulary:(payload)=>request('/api/library/vocabulary',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload),
  }),
  reviewLibraryVocabulary:(word,result)=>request(`/api/library/vocabulary/${encodeURIComponent(word)}/review`,{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify({result}),
  }),
  deleteLibraryVocabulary:(word)=>request(`/api/library/vocabulary/${encodeURIComponent(word)}`,{
    method:'DELETE',
  }),
  grammarLibrary:()=>request('/api/library/grammar'),
  grammarLesson:(id)=>request(`/api/library/grammar/${encodeURIComponent(id)}`),
  grammarReference:(id)=>request(`/api/library/grammar/${encodeURIComponent(id)}/reference`),
  completeGrammar:(id)=>request(`/api/library/grammar/${encodeURIComponent(id)}/complete`,{method:'POST'}),
  uncompleteGrammar:(id)=>request(`/api/library/grammar/${encodeURIComponent(id)}/complete`,{method:'DELETE'}),
  readingSessions:(limit=8)=>request(`/api/reading/sessions?limit=${encodeURIComponent(limit)}`),
  readingSession:(id)=>request(`/api/reading/session/${encodeURIComponent(id)}`),
  createReadingSession:(payload)=>request('/api/reading/session',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload||{}),
  }),
  submitReadingAnswers:(id,answers)=>request(`/api/reading/session/${encodeURIComponent(id)}/answer`,{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify({answers}),
  }),
  importMedia:(payload)=>request('/api/media-learning/import',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload),
  }),
  translateMedia:(payload)=>request('/api/media-learning/translate',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload),
  }),
  mediaImportStatus:(payload)=>request('/api/media-learning/import/status',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload),
  }),
  mediaImportStatusCompact:(payload)=>request('/api/media-learning/import/status',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify({...payload,compact:true}),
  }),
  // Worlds are the discovery layer above lessons. Availability and counts are
  // measured server-side against the real catalog; the client never derives them.
  worlds:(language)=>request(`/api/worlds?language=${encodeURIComponent(language||'')}`),
  listeningLibrary:(language,filters={})=>{
    const params=new URLSearchParams({language:String(language||'')});
    if(filters.level)params.set('level',String(filters.level));
    if(filters.topic)params.set('topic',String(filters.topic));
    if(filters.tag)params.set('tag',String(filters.tag));
    return request(`/api/listening/library?${params.toString()}`);
  },
  // An omitted target language is resolved by the server from the learner's
// profile; the client must not substitute a language of its own.
  listeningLibraryLesson:(lessonId,targetLanguage)=>request(`/api/listening/library/${encodeURIComponent(lessonId)}?target_language=${encodeURIComponent(targetLanguage||'')}`),
  annotateMediaText:(payload)=>request('/api/media-learning/annotate',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload),
  }),
  explainMediaText:(payload)=>request('/api/media-learning/explain',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload),
  }),
  transcribeSpeech:(blob,language,filename='recording.webm')=>{
    const form=new FormData();
    form.append('file',blob,filename);
    if(language)form.append('language',language);
    return request('/api/speech/transcribe',{
      method:'POST',
      body:form,
    });
  },
  assessPronunciation:(blob,language,referenceText,filename='recording.webm')=>{
    const form=new FormData();
    form.append('file',blob,filename);
    form.append('language',language||'');
    form.append('reference_text',referenceText||'');
    return request('/api/speech/pronunciation',{
      method:'POST',
      body:form,
    });
  },
  evaluateSpeaking:(payload)=>request('/api/speech/evaluation',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload||{}),
  }),
  saveSpeakingAttempt:(payload)=>request('/api/speech/attempts',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload||{}),
  }),
  speakingAttempts:(limit=20,assetId='',segmentId='')=>{
    const params=new URLSearchParams({limit:String(limit)});
    if(assetId)params.set('asset_id',String(assetId));
    if(segmentId)params.set('segment_id',String(segmentId));
    return request(`/api/speech/attempts?${params.toString()}`);
  },
  listeningProgress:(assetId)=>request(`/api/listening/progress?asset_id=${encodeURIComponent(assetId||'')}`),
  saveListeningProgress:(payload)=>request('/api/listening/progress',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload||{}),
  }),
  shadowingProgress:(assetId)=>request(`/api/listening/shadowing-progress?asset_id=${encodeURIComponent(assetId||'')}`),
  saveShadowingProgress:(payload)=>request('/api/listening/shadowing-progress',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload||{}),
  }),
  essays:()=>request('/api/essays'),
  essay:(id)=>request(`/api/essays/${encodeURIComponent(id)}`),
  linguisticAnnotations:(id)=>request(`/api/essays/${encodeURIComponent(id)}/linguistic-annotations`,{
    method:'POST',
  }),
  generateTask:(payload)=>request('/api/tasks/generate',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload),
  }),
  evaluate:(payload)=>request('/api/evaluate',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload),
  }),
  improve:(payload)=>request('/api/improve',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload),
  }),
  logout:()=>request('/auth/logout',{method:'POST'}),
};
