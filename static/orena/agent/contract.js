/* The agent contract as data (docs/project/AGENT_CONTRACT.md, contract_version 2, D-092).

   Everything the new UI needs to speak the contract lives here: the version, the closed enums, the
   action allowlist with its fixed risk, the surface / intent id space, and the locale mapping at
   the UI's boundary. DOM-free, so scripts/test_orena_agent.mjs checks it against the contract text. */

export const CONTRACT_VERSION = 2;

export const EVENTS = Object.freeze([
  'session', 'segment_delta', 'segment_end', 'tool_call', 'tool_result', 'evidence', 'action',
  'suggestion', 'memory_update', 'voice_state', 'audio_chunk', 'metered', 'error', 'done',
]);

export const VOICE_STYLES = Object.freeze(['neutral_explain', 'encouraging', 'gentle_correction', 'celebrate', 'brief_ack', 'reference']);
export const VOICE_STATES = Object.freeze(['listening', 'thinking', 'speaking', 'interrupted']);
export const EVIDENCE_SOURCES = Object.freeze([
  'speech.pronunciation', 'writing.evaluation', 'reading.comprehension', 'listening.dictation',
  'vocabulary.review', 'grammar.catalog', 'learner_summary',
]);
export const ACTIVITY_TYPES = Object.freeze([
  'app_help', 'coaching', 'review', 'reading', 'listening', 'pronunciation_practice', 'free_talk',
  'conversation_practice', 'writing', 'grammar', 'vocabulary',
]);
export const SELECTED_ITEM_TYPES = Object.freeze(['word', 'sentence', 'feedback_item', 'grammar_point']);

/* §7: the allowlist and the risk each type carries - fixed here, never taken from the model. */
export const ACTIONS = Object.freeze({
  navigate: 'LOW',
  play_model: 'LOW',
  play_user: 'LOW',
  say_again: 'LOW',
  compare_with_model: 'LOW',
  save_word: 'LOW',
  add_word_to_collection: 'LOW',
  start_review: 'LOW',
  start_targeted_drill: 'LOW',
  unsave_word: 'CONFIRM',
});

/* §6.1, with the parameters each id requires. */
export const SURFACES = Object.freeze({
  home: [],
  'orena.home': [],
  library: [],
  'reading.library': [],
  'reading.workspace': ['content_id'],
  'listening.library': [],
  'listening.workspace': ['content_id'],
  'listening.dictation': ['content_id'],
  'speaking.library': [],
  'speaking.workspace': ['content_id'],
  'speaking.free_talk': [],
  'speaking.word_detail': ['take_ref', 'item_id'],
  'speaking.compare': ['take_ref', 'item_id'],
  'writing.workspace': [],
  'writing.review': ['essay_id'],
  'writing.revision': ['essay_id'],
  'vocabulary.my_language': [],
  'vocabulary.word': ['text', 'lang'],
  'vocabulary.review_due': [],
  'grammar.catalog': [],
  'grammar.point': ['grammar_id'],
  progress: [],
  preferences: [],
  'preferences.agent_memory': [],
});

/* §3 locale: the contract says zh-CN, the product says zh. Each side maps at its own boundary. */
export function toContractLang(code) {
  const value = String(code || '').trim().toLowerCase();
  if (value === 'zh' || value.startsWith('zh-')) return 'zh-CN';
  return value || 'en';
}

export function fromContractLang(code) {
  const value = String(code || '').trim().toLowerCase();
  if (value === 'zh-cn' || value === 'zh' || value.startsWith('zh-')) return 'zh';
  return value || 'en';
}

export const LIMITS = Object.freeze({
  coachNotes: 20,
  coachNotesBytes: 2048,
  actionLabel: 24,
  displayReason: 90,
  openingSegment: 240,
});
