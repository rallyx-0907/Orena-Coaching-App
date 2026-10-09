import { isTransientRequestError, retryOnce } from './retry.js';
import { navigationSignal } from './navigation.js';

const JSON_HEADERS = {'Content-Type':'application/json'};

/* What a 401 does: main.js installs its own (Welcome). Before it has, the learner goes to Welcome too. */
let onUnauthorized=()=>{location.href='/#/welcome';};
export function setUnauthorizedHandler(handler){onUnauthorized=typeof handler==='function'?handler:()=>{};}

export async function request(url, options={}){
  const response = await fetch(url,{
    credentials:'same-origin',
    cache:'no-store',
    signal: navigationSignal(),
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
    if(response.status===401)onUnauthorized();
    const detail=payload && typeof payload==='object' ? payload.detail : payload;
    const structured=detail && typeof detail==='object';
    const rawMessage=structured ? detail.message : detail;
    const looksLikeHtml=typeof rawMessage==='string'&&/(<!doctype|<html[\s>])/i.test(rawMessage);
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
  conversationTurn:payload=>request('/api/dictionary/conversation-turn',{method:'POST',headers:JSON_HEADERS,body:JSON.stringify(payload)}),
  me:()=>request('/api/me'),
  sessionBootstrap:()=>request('/api/session/bootstrap'),
  productMe:()=>request('/api/product/me'),
  // Canonical read (accountCommerce): full subscription-state vocabulary,
  // web-only. /me stays byte-for-byte for the frozen mobile contract.
  productCommerce:()=>request('/api/product/commerce'),
  // The plan catalogue (Free, Premium and their entitlements); `billing_ready` is false.
  productPlans:()=>request('/api/product/plans'),
  adminProductAccount:()=>request('/api/product/admin/account'),
  adminReadinessSummary:()=>request('/api/admin/readiness-summary'),
  adminVocabularyPreview:(files)=>{
    const form=new FormData();
    [...(files||[])].forEach((file)=>form.append('files',file,file.name));
    return request('/api/admin/vocabulary/preview',{method:'POST',body:form});
  },
  adminVocabularyImport:(files,metadata={},mappings={})=>{
    const form=new FormData();
    [...(files||[])].forEach((file)=>form.append('files',file,file.name));
    form.append('metadata',JSON.stringify(metadata));
    form.append('mappings',JSON.stringify(mappings));
    return request('/api/admin/vocabulary/import',{method:'POST',body:form});
  },
  health:()=>request('/api/health'),
  /* Learner feedback (D-156): one review per send; the learner's own are read newest first. */
  feedbackSend:(body)=>request('/api/feedback',{method:'POST',headers:JSON_HEADERS,body:JSON.stringify(body)}),
  feedbackMine:()=>request('/api/feedback/mine'),
  languages:()=>request('/api/platform/languages'),
  skills:()=>request('/api/platform/skills'),
  /* `settingsVersion` is the opaque token read from accountSettings(), echoed verbatim (D-104 H-17).
     Omitted, the session still switches and the account stores only a first-ever choice. */
  setLanguage:(language,settingsVersion)=>request('/api/platform/language',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(settingsVersion==null?{language}:{language,settings_version:settingsVersion}),
  }),
  accountSettings:()=>request('/api/account-settings'),
  /* Account-wide choices (learning language, interface language, weekly goal), versioned by
     `expected_settings_version`, the opaque string the server last served. */
  patchAccountSettings:(payload)=>request('/api/account-settings',{
    method:'PATCH',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload),
  }),
  dashboard:()=>request('/api/dashboard'),
  learnerProfile:()=>request('/api/learner-profile'),
  /* Change only the settings named, against the version that was read.

     The whole-profile PUT this replaces carried a default for every field, so
     saving one preference rewrote the rest - and two devices editing
     preferences quietly overwrote each other. `expected_version` makes the
     second writer visible instead. PUT remains for the frozen native client. */
  patchLearnerProfile:(payload)=>request('/api/learner-profile',{
    method:'PATCH',
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
  /* The Quick Sheet's two contracts (D-066): a word in its sentence, and a whole
     sentence. The lookup below stays the deterministic first answer. */
  wordDetail:(payload)=>request('/api/dictionary/word-detail',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload||{}),
  }),
  sentenceSheet:(payload)=>request('/api/dictionary/sentence-sheet',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload||{}),
  }),
  readingLookup:(payload)=>request('/api/reading/lookup',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload||{}),
  }),
  readingTranslate:(payload)=>request('/api/reading/translate',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload||{}),
  }),
  spokenResponseCoaching:(payload)=>request('/api/dictionary/spoken-response',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload||{}),
  }),
  registerComparison:(payload)=>request('/api/dictionary/registers',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload||{}),
  }),
  chineseStrokeOrder:(word)=>request(`/api/chinese/stroke-order?word=${encodeURIComponent(word)}`),
  /* The learner's saved words, a page at a time. `limit`, `cursor`, `query`,
     `status` ('learning' | 'mastered' | 'due') and `order` ('recent' | 'due' |
     'word') are the server's work: no screen may read the whole vocabulary to
     count, search or filter it. Every page carries `summary` and the rank with
     it.

     `query` matches the word, its definition and the translation kept with it.
     A `cursor` is only valid for the query, status, order and focus it came
     from; change any of them and the server starts from the first page rather
     than reading a cursor against a different ordering. */
  libraryVocabulary:(params={})=>{
    const query=new URLSearchParams();
    if(params.limit!=null)query.set('limit',String(params.limit));
    if(params.cursor)query.set('cursor',String(params.cursor));
    if(params.query)query.set('query',String(params.query));
    if(params.status)query.set('status',String(params.status));
    if(params.order)query.set('order',String(params.order));
    for(const note of params.focus||[])if(note)query.append('focus',String(note));
    const suffix=query.toString()?`?${query.toString()}`:'';
    return retryOnce(
      ()=>request(`/api/library/vocabulary${suffix}`),
      isTransientRequestError,
    );
  },
  /* Thư viện của tôi: one typed read over every owner the learner already has,
     a page at a time. The room asks for a kind and a page; it never holds a
     copy of what an owner owns. */
  collection:(params={})=>{
    const query=new URLSearchParams();
    if(params.limit!=null)query.set('limit',String(params.limit));
    if(params.cursor)query.set('cursor',String(params.cursor));
    if(params.query)query.set('query',String(params.query));
    if(params.kinds&&params.kinds.length)query.set('kinds',params.kinds.join(','));
    if(params.domains&&params.domains.length)query.set('domains',params.domains.join(','));
    const suffix=query.toString()?`?${query.toString()}`:'';
    return retryOnce(
      ()=>request(`/api/collection${suffix}`),
      isTransientRequestError,
    );
  },
  /* How a word sounds, at the reading it was kept at. The answer says what
     it may be played under - the licence and who recorded it - because that
     is the condition a Commons clip is available on at all. */
  wordAudio:(word,reading='',lookup=false)=>retryOnce(
    ()=>request(`/api/library/vocabulary/${encodeURIComponent(word)}/audio?reading=${encodeURIComponent(reading)}${lookup?'&lookup=true':''}`),
    isTransientRequestError,
  ),
  /* The learner's own study sets. A Deck is Vocabulary's - a set to review
     from - and is not a My Library Collection, which organises what the
     learner has. Two domains, two contracts. */
  vocabularyDecks:(word='')=>retryOnce(
    ()=>request(`/api/vocabulary/decks${word?`?word=${encodeURIComponent(word)}`:''}`),
    isTransientRequestError,
  ),
  vocabularyDeckCreate:(payload)=>request('/api/vocabulary/decks',{method:'POST',headers:JSON_HEADERS,body:JSON.stringify(payload)}),
  vocabularyDeckPatch:(id,payload)=>request(`/api/vocabulary/decks/${encodeURIComponent(id)}`,{method:'PATCH',headers:JSON_HEADERS,body:JSON.stringify(payload)}),
  vocabularyDeckWords:(id)=>retryOnce(()=>request(`/api/vocabulary/decks/${encodeURIComponent(id)}/words`),isTransientRequestError),
  vocabularyDeckAdd:(id,word)=>request(`/api/vocabulary/decks/${encodeURIComponent(id)}/words`,{method:'POST',headers:JSON_HEADERS,body:JSON.stringify({word})}),
  /* One word, opened all the way: what the canonical deep frames draw, in
     one read. A section the app has nothing for is absent from the answer
     rather than empty in it. */
  wordDeep:(word,reading='')=>retryOnce(
    ()=>request(`/api/library/vocabulary/${encodeURIComponent(word)}/deep${reading?`?reading=${encodeURIComponent(reading)}`:''}`),
    isTransientRequestError,
  ),
  /* Where a word is actually said: timestamped moments in the listening
     catalogue whose own transcript contains it. Nothing generated. */
  wordClips:(word,limit=6)=>retryOnce(
    ()=>request(`/api/library/vocabulary/${encodeURIComponent(word)}/clips?limit=${Number(limit)||6}`),
    isTransientRequestError,
  ),
  /* The learner's own state over what a listing is drawing: kept, marked,
     filed. One call for a page of rows, never one per row. */
  libraryItems:({kind='',words=[],sources=[]}={})=>{
    const query=new URLSearchParams();
    if(kind)query.set('kind',kind);
    if(words.length)query.set('words',words.join(','));
    if(sources.length)query.set('sources',sources.join(','));
    const suffix=query.toString()?`?${query.toString()}`:'';
    return retryOnce(()=>request(`/api/library/items${suffix}`),isTransientRequestError);
  },
  libraryKeep:(payload)=>request('/api/library/items',{method:'POST',headers:JSON_HEADERS,body:JSON.stringify(payload)}),
  /* Every change carries the version it was made against, so two tabs cannot
     overwrite each other without one of them being told. */
  libraryItemPatch:(id,payload)=>request(`/api/library/items/${encodeURIComponent(id)}`,{method:'PATCH',headers:JSON_HEADERS,body:JSON.stringify(payload)}),
  libraryItem:(id)=>retryOnce(()=>request(`/api/library/items/${encodeURIComponent(id)}`),isTransientRequestError),
  libraryReviewQueue:()=>retryOnce(()=>request('/api/library/review-queue'),isTransientRequestError),
  libraryCollections:(kind='')=>retryOnce(()=>request(`/api/library/collections${kind?`?kind=${encodeURIComponent(kind)}`:''}`),isTransientRequestError),
  libraryCollectionCreate:(payload)=>request('/api/library/collections',{method:'POST',headers:JSON_HEADERS,body:JSON.stringify(payload)}),
  libraryItemDelete:(id)=>request(`/api/library/items/${encodeURIComponent(id)}`,{method:'DELETE'}),
  /* Undo, within the ten seconds the surface offers it: the word exactly as it
     was, schedule included - not a fresh save wearing the same spelling. */
  restoreLibraryVocabulary:(payload)=>request('/api/library/vocabulary/restore',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload),
  }),
  /* What is in one of the learner's sets. The room filters itself to these
     refs rather than fetching a second listing. */
  libraryCollectionItems:(collectionId)=>retryOnce(
    ()=>request(`/api/library/collections/${encodeURIComponent(collectionId)}/items`),
    isTransientRequestError,
  ),
  libraryCollectionAdd:(collectionId,itemId)=>request(`/api/library/collections/${encodeURIComponent(collectionId)}/items`,{method:'POST',headers:JSON_HEADERS,body:JSON.stringify({item_id:itemId})}),
  /* The counts and the rank alone - what Hồ sơ, Tiến độ and Home need, with no
     saved word crossing the wire. */
  libraryVocabularySummary:()=>retryOnce(
    ()=>request('/api/library/vocabulary/summary'),
    isTransientRequestError,
  ),
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
  // The curated Vocabulary Library catalog and Daily Feed (Discover surface):
  // read-only, distinct from the saved/review state above. "Keep" from either
  // reuses saveLibraryVocabulary with source_kind 'collection' or 'feed'.
  /* The catalogue's half of the room's search. Bounded by the server, which
     names its own limit, so a one-letter query costs what a long one does. */
  vocabularyCatalogueSearch:(query,languageCode,limit=20)=>retryOnce(
    ()=>request(`/api/vocabulary/catalogue/search?q=${encodeURIComponent(query)}&language_code=${encodeURIComponent(languageCode)}&limit=${Number(limit)||20}`),
    isTransientRequestError,
  ),
  vocabularyLibraryCollections:(languageCode)=>request(`/api/vocabulary/library/collections?language_code=${encodeURIComponent(languageCode)}`),
  vocabularyLibraryCollection:(collectionId,params={})=>{
    const query=new URLSearchParams();
    if(params.search)query.set('search',String(params.search));
    if(params.level)query.set('level',String(params.level));
    if(params.limit!=null)query.set('limit',String(params.limit));
    if(params.offset!=null)query.set('offset',String(params.offset));
    if(params.includeReview)query.set('include_review','true');
    const suffix=query.toString()?`?${query.toString()}`:'';
    return request(`/api/vocabulary/library/collections/${encodeURIComponent(collectionId)}${suffix}`);
  },
  dailyVocabularyFeed:(languageCode,targetLevel)=>request(`/api/vocabulary/feed?language_code=${encodeURIComponent(languageCode)}${targetLevel?`&target_level=${encodeURIComponent(targetLevel)}`:''}`),
  // Shared Reading Library: admin-imported books, open to every learner.
  // libraryBookChapter backs the `book:<id>/<chapterId>` encounter locator
  // in ui/encounter.js; adminImportLibraryBooks is admin-gated server-side.
  /* Published Reading articles - what the Admin Reading engine admitted. The
     list is a page of lightweight cards and the detail is one article; neither
     says anything about review, ingestion or a candidate, because a learner
     has no business with any of that. */
  readingArticles:(languageCode,cursor)=>request(`/api/reading/articles?language=${encodeURIComponent(languageCode)}${cursor?`&cursor=${encodeURIComponent(cursor)}`:''}`),
  readingArticle:(articleId)=>request(`/api/reading/articles/${encodeURIComponent(articleId)}`),
  readingSummary:(payload)=>request('/api/reading/summary',{method:'POST',headers:JSON_HEADERS,body:JSON.stringify(payload||{})}),
  libraryBooks:(languageCode,cursor)=>request(`/api/reading/library/books?learning_language=${encodeURIComponent(languageCode)}${cursor?`&cursor=${encodeURIComponent(cursor)}`:''}`),
  libraryBook:(bookId)=>request(`/api/reading/library/books/${encodeURIComponent(bookId)}`),
  libraryBookChapter:(bookId,chapterId)=>request(`/api/reading/library/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`),
  adminImportLibraryBooks:(files,languageCode)=>{
    const form=new FormData();
    for(const file of files)form.append('files',file,file.name);
    form.append('learning_language',languageCode);
    return request('/api/reading/library/import',{method:'POST',body:form});
  },
  grammarLibrary:()=>request('/api/library/grammar'),
  grammarLesson:(id)=>request(`/api/library/grammar/${encodeURIComponent(id)}`),
  grammarReference:(id)=>request(`/api/library/grammar/${encodeURIComponent(id)}/reference`),
  completeGrammar:(id)=>request(`/api/library/grammar/${encodeURIComponent(id)}/complete`,{method:'POST'}),
  uncompleteGrammar:(id)=>request(`/api/library/grammar/${encodeURIComponent(id)}/complete`,{method:'DELETE'}),
  // Canonical Reading (D-082): practice on the published corpus. The
  // generated-passage session routes are retired.
  readingPracticeNext:()=>request('/api/reading/practice/next'),
  readingPracticeSet:(articleId)=>request(`/api/reading/practice/articles/${encodeURIComponent(articleId)}`),
  gradeReadingPracticeQuestion:(setId,questionId,selectedIndex)=>request(`/api/reading/practice/sets/${encodeURIComponent(setId)}/questions/${encodeURIComponent(questionId)}/grade`,{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify({selected_index:selectedIndex}),
  }),
  // `operationId` names one logical submit and is reused by every retry of it.
  // `recommendation` is what /next issued, passed back untouched when the
  // learner came from it; the server verifies it and records the provenance.
  submitReadingPractice:(setId,operationId,answers,recommendation=null)=>request('/api/reading/practice/attempts',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify({set_id:setId,operation_id:operationId,answers,...(recommendation?{recommendation}:{})}),
  }),
  readingEvidence:(limit=20)=>request(`/api/reading/practice/evidence?limit=${encodeURIComponent(limit)}`),
  // A learner's persistent Q&A thread about one text (D-072.2). `sourceKind` is one of
  // story/media/reading_session/book_chapter (writing_coach/persistence/discussion_repository.py
  // SOURCE_KINDS); the GET is a safe read even before any thread exists (an empty shape, never
  // a 404). `sendDiscussionTurn`'s `request_id` makes a retry of the same submission idempotent
  // server-side - the caller supplies one per attempt, not per keystroke.
  textDiscussion:(sourceKind,sourceId)=>request(`/api/texts/discussion?source_kind=${encodeURIComponent(sourceKind)}&source_id=${encodeURIComponent(sourceId)}`),
  sendDiscussionTurn:(payload)=>request('/api/texts/discussion/turns',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(payload),
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
  // Shared Listening Library. `my` resolves one stored media identity - an
  // administrator's import or a learner's own file - into the same acquisition
  // payload `/import` answers with, so the encounter has one shape to render.
  // The admin routes are admin-gated server-side, not here.
  mediaMy:(mediaId,support='')=>request(`/api/media/my/${encodeURIComponent(mediaId)}${support?`?target_language=${encodeURIComponent(support)}`:''}`),
  prepareMedia:(payload)=>request('/api/media-learning/source',{method:'POST',headers:JSON_HEADERS,body:JSON.stringify(payload)}),
  mediaSource:(url,target)=>request(`/api/media/source?source_url=${encodeURIComponent(url)}&target_language=${encodeURIComponent(target||'')}`),
  /* The owner-scoped delete of a learner's own stored upload (404 for anything else); idempotent. */
  deleteMyMedia:(mediaId)=>request(`/api/media/my/${encodeURIComponent(mediaId)}`,{method:'DELETE'}),
  mediaUpload:(file,language)=>{
    const form=new FormData();
    form.append('file',file,file.name);
    form.append('language',String(language||'en'));
    return request('/api/media-learning/upload',{method:'POST',body:form});
  },
  adminMediaPreview:(urls,language)=>request('/api/media/admin/preview',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify({urls,language}),
  }),
  adminMediaImport:(items,language)=>request('/api/media/admin/import',{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify({items,language}),
  }),
  adminMediaUpload:(files,language)=>{
    const form=new FormData();
    for(const file of files)form.append('file',file,file.name);
    form.append('language',String(language||'en'));
    return request('/api/media/admin/upload',{method:'POST',body:form});
  },
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
  // Whether a speech provider is attached at all. Asked before the learner is
  // invited to record, so the room can be honest up front instead of after a
  // take they already made.
  speechStatus:()=>request('/api/speech/status'),
  speakingModelReference:(lessonId,segmentId)=>request(`/api/speaking/model-reference/${encodeURIComponent(lessonId)}/${encodeURIComponent(segmentId)}`,{method:'POST'}),
  transcribeSpeech:(blob,language,filename='')=>{
    const form=new FormData();
    // The file's name follows what the device actually recorded (iPhone Safari records mp4, not webm).
    const type=String(blob?.type||'');
    const ext=/mp4|m4a|aac/.test(type)?'m4a':/ogg/.test(type)?'ogg':/wav/.test(type)?'wav':'webm';
    const name=`${String(filename||'recording').replace(/\.[a-z0-9]+$/i,'')}.${ext}`;
    form.append('file',blob,name);
    if(language)form.append('language',language);
    return request('/api/speech/transcribe',{
      method:'POST',
      body:form,
    });
  },
  // The Speaking library: the Speaking catalogue plus Listening lessons that can be shadowed.
  speakingLibrary:(language)=>request(`/api/speaking/library?language=${encodeURIComponent(language||'')}`),
  speakingItem:(itemId)=>request(`/api/speaking/items/${encodeURIComponent(itemId)}`),
  // mode 'scripted' assesses a line against its reference; 'unscripted' assesses free speech.
  assessPronunciation:(blob,language,referenceText,mode='scripted',filename='recording.webm')=>{
    const form=new FormData();
    form.append('file',blob,filename);
    form.append('language',language||'');
    form.append('reference_text',referenceText||'');
    form.append('mode',mode||'scripted');
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
  speakingAttempts:(limit=20,assetId='',segmentId='',since='')=>{
    const params=new URLSearchParams({limit:String(limit)});
    if(assetId)params.set('asset_id',String(assetId));
    if(segmentId)params.set('segment_id',String(segmentId));
    if(since)params.set('since',String(since));
    return request(`/api/speech/attempts?${params.toString()}`);
  },
  /* D-142: the learner's live practice session as the server keeps it (404 while ORENA_PRACTICE_SESSION is off). */
  speakingCurrentSession:(limit=100)=>request(`/api/speech/attempts?session=current&limit=${encodeURIComponent(String(limit))}`),
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
  /* The review and the revision in the Writing room's canonical shapes (D-066). */
  essayReview:(id)=>request(`/api/essays/${encodeURIComponent(id)}/review`),
  /* Re-grade one old essay under the current evaluator contract if its stored pair is affected
     (D-103.7). The server decides; an essay that is current costs no provider call. */
  refreshEssayReview:(id)=>request(`/api/essays/${encodeURIComponent(id)}/review/refresh`,{method:'POST'}),
  essayRevision:(id)=>request(`/api/essays/${encodeURIComponent(id)}/revision`),
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
  logout:(next)=>request(next?`/auth/logout?next=${encodeURIComponent(next)}`:'/auth/logout',{method:'POST'}),
  // Whether this deployment keeps work with the account (I2): active,
  // disabled or unavailable. Drafts stay on the device unless active.
  accountBackbone:()=>request('/api/account-backbone'),
  draft:(key)=>request(`/api/drafts/${encodeURIComponent(key)}`),
  saveDraft:(key,body)=>request(`/api/drafts/${encodeURIComponent(key)}`,{
    method:'PUT',
    headers:JSON_HEADERS,
    body:JSON.stringify(body),
  }),
  // Records kept with the account while the backbone is active (D4): conversation turns, notes and
  // highlights, private imports, typed and Reading Transfer responses, and where a kept word was met.
  conversationRecord:(key)=>request(`/api/conversations/${encodeURIComponent(key)}`),
  appendConversationTurn:(key,body)=>request(`/api/conversations/${encodeURIComponent(key)}/turns`,{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(body),
  }),
  annotations:(contentId)=>request(`/api/annotations/${encodeURIComponent(contentId)}`),
  saveAnnotations:(contentId,body)=>request(`/api/annotations/${encodeURIComponent(contentId)}`,{
    method:'PUT',
    headers:JSON_HEADERS,
    body:JSON.stringify(body),
  }),
  /* One page of the learner's imports and of the deleted ones' tombstones (cursor = change sequence of the last row
     of the page before; `include` asks only for the list that still has pages). Callers page until both cursors end. */
  imports:({cursor=null,deletedCursor=null,include='both'}={})=>request(`/api/imports?limit=50&include=${include}${cursor!=null?`&cursor=${cursor}`:''}${deletedCursor!=null?`&deletedCursor=${deletedCursor}`:''}`),
  saveImport:(id,body)=>request(`/api/imports/${encodeURIComponent(id)}`,{
    method:'PUT',
    headers:JSON_HEADERS,
    body:JSON.stringify(body),
  }),
  deleteImport:(id,operationId,expectedVersion)=>request(`/api/imports/${encodeURIComponent(id)}?operationId=${encodeURIComponent(operationId)}&expectedVersion=${encodeURIComponent(expectedVersion)}`,{method:'DELETE'}),
  saveResponse:(key,body)=>request(`/api/responses/${encodeURIComponent(key)}`,{
    method:'PUT',
    headers:JSON_HEADERS,
    body:JSON.stringify(body),
  }),
  attachProvenance:(word,body)=>request(`/api/library/vocabulary/${encodeURIComponent(word)}/provenance`,{
    method:'POST',
    headers:JSON_HEADERS,
    body:JSON.stringify(body),
  }),
  // A read-only glance at the learner's own recorded evidence (I6). `window`
  // is one of 7d/30d/90d/all; the caller decides which, this never guesses.
  // The streak and this week's active days, derived from server records (D4 I14). `tz` is the learner's own
  // IANA timezone: a day is a calendar day in it.
  learnerActivity:(tz)=>request(`/api/learner-activity?tz=${encodeURIComponent(tz||'UTC')}`),
  // Licences and data sources for Settings (datasets, content credits, each word recording).
  licences:()=>request('/api/licences'),
  learnerSummary:(window)=>request(`/api/learner-summary?window=${encodeURIComponent(window)}`),
};
