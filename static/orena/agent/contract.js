/* The agent contract as data (docs/project/AGENT_CONTRACT.md, contract_version 5, D-092, D-094,
   D-095, D-096).

   Everything the new UI needs to speak the contract lives here: the version, the closed enums, the
   action allowlist with its fixed risk, the surface / intent id space, the locale mapping at the
   UI's boundary, and the §5.6 address rules (how Orena says "I" and "you"). DOM-free, so
   scripts/test_orena_agent.mjs checks it against the contract text. */

export const CONTRACT_VERSION = 7;

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

/* §4.1: the classes a server sends and the fallback each carries. The UI acts on the fallback. */
export const ERROR_CLASSES = Object.freeze({ provider_unavailable: 'retry', internal_error: 'retry', voice_unavailable: 'text_only' });
export const FALLBACKS = Object.freeze(['retry', 'text_only', 'none']);

export function fallbackOf(value) {
  return FALLBACKS.includes(value) ? value : 'none';
}

/* §2.1: what a response's status means before any stream is read. `wait` carries the seconds
   Retry-After gives (whole seconds, at least 1; an HTTP date is read too). */
export function readStatus(status, retryAfter = null, now = Date.now()) {
  if (status >= 200 && status < 300) return { kind: 'stream' };
  if (status === 401) return { kind: 'signed_out' };
  if (status === 404) return { kind: 'absent' };
  if (status === 403) return { kind: 'error', class: 'transport', fallback: 'none' }; // v7: account deleted / not in the plan
  if (status === 409) return { kind: 'language_mismatch' };
  if (status === 429) return { kind: 'wait', seconds: retrySeconds(retryAfter, now) };
  return { kind: 'error', class: 'transport', fallback: status === 422 ? 'none' : 'retry' };
}

function retrySeconds(value, now) {
  const text = String(value ?? '').trim();
  if (/^\d+$/.test(text)) return Math.max(1, Number(text));
  const at = Date.parse(text);
  return Number.isFinite(at) ? Math.max(1, Math.ceil((at - now) / 1000)) : 1;
}

/* What the transport tells the conversation about a status (§2.1). The client makes these
   itself; a server never sends them, so they are not §4 events. */
export const CLIENT_EVENTS = Object.freeze(['wait', 'absent', 'language_mismatch']);

export const LIMITS = Object.freeze({
  coachNotes: 20,
  coachNotesBytes: 2048,
  actionLabel: 24,
  displayReason: 90,
  openingSegment: 240,
  addressTerm: 24,
  addressTermWords: 3,
  surfacePurpose: 90,
});

/* §5.4/§5.6: coach note kinds, plus `address`, which follows its own rules below and is never sent
   in coach_notes (§3, §5.6). */
export const NOTE_KINDS = Object.freeze(['preference', 'goal', 'plan', 'address']);

/* §5.6: which fields of `context.address` each support language takes, and that language's default
   pair - the object an upsert carries to go back to the default. A support language with no row
   here takes no address at all: its own ordinary first/second person, never the English pair. */
export const ADDRESS_FIELDS = Object.freeze({
  en: Object.freeze(['user']),
  vi: Object.freeze(['self', 'user']),
  'zh-CN': Object.freeze(['self', 'user', 'register']),
});

export const ADDRESS_DEFAULTS = Object.freeze({
  en: Object.freeze({ user: 'you' }),
  vi: Object.freeze({ self: 'mình', user: 'bạn' }),
  'zh-CN': Object.freeze({ self: '我', user: '你', register: 'plain' }),
});

/* §5.6 term validator: 1-24 characters, at most 3 words, only Unicode letters with their combining
   marks (\p{L}\p{M} - any script: Vietnamese with diacritics, Han characters) and single spaces
   between words. No digits, punctuation, symbols, line breaks or markup. \p{M} on its own covers a
   combining mark wherever Unicode places it, so an NFC term ("Nguyễn") and its NFD decomposition
   read the same: both letters. A word starts with a letter: a combining mark alone is not one.
   Length counts characters (code points), so a Han character outside the basic plane counts once.
   The word count is LIMITS.addressTermWords (one word already matched, so `{0, addressTermWords - 1}`
   more) - a single source, not a hardcoded duplicate of the same "3 words" rule. */
const ADDRESS_TERM_RE = new RegExp(`^\\p{L}[\\p{L}\\p{M}]*(?: \\p{L}[\\p{L}\\p{M}]*){0,${LIMITS.addressTermWords - 1}}$`, 'u');

export function isValidAddressTerm(value) {
  if (typeof value !== 'string') return false;
  const length = [...value].length;
  if (length < 1 || length > LIMITS.addressTerm) return false;
  return ADDRESS_TERM_RE.test(value);
}

/* The learner reads a term sentence-initial with a capital, stored otherwise as they gave it (§5.6
   "Casing"). Uppercasing only the first code point is enough for every script this validator takes. */
export function capitalizeTerm(term) {
  const text = String(term || '');
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

export function addressNoteId(lang) {
  return `address-${lang}`;
}

/* Normalises a raw address object for a support language (contract code: vi | zh-CN | en, or a
   language with no §5.6 row): drops any field that language ignores, resolves zh-CN's `register` to
   plain|polite (always present, defaulting to plain), and returns null when a term is invalid or the
   language takes no address at all - the caller falls back to that language's default for the whole
   object (§5.6 "if anything is invalid, uses the default for the whole object"). A field the learner
   left unset is simply absent from the result; only an explicitly invalid term nulls the object. */
export function normalizeAddress(address, lang) {
  const fields = ADDRESS_FIELDS[lang];
  if (!fields || !address || typeof address !== 'object') return null;
  const out = { lang };
  for (const field of fields) {
    if (field === 'register') {
      out.register = address.register === 'polite' ? 'polite' : 'plain';
      continue;
    }
    const value = address[field];
    if (value == null) continue;
    if (!isValidAddressTerm(value)) return null;
    out[field] = value;
  }
  // §5.6: `lang` and at least one of self, user, register - an object that carries nothing is none.
  return Object.keys(out).length > 1 ? out : null;
}

/* The fully-resolved pair for filling {self}/{user} template slots: every field the language takes,
   the learner's own term where valid, that language's default otherwise (zh-CN's `user` falls back
   to 你/您 by `register` when no name or form of address was given, never a hardcoded default that
   ignores register). Null for a language with no §5.6 row - callers use that language's own copy
   unaddressed. */
export function resolveAddress(address, lang) {
  const fields = ADDRESS_FIELDS[lang];
  const defaults = ADDRESS_DEFAULTS[lang];
  if (!fields || !defaults) return null;
  const chosen = normalizeAddress(address, lang) || { lang };
  if (lang === 'zh-CN') {
    const register = chosen.register === 'polite' ? 'polite' : 'plain';
    return { lang, self: chosen.self || defaults.self, user: chosen.user || (register === 'polite' ? '您' : '你'), register };
  }
  const out = { lang, user: chosen.user || defaults.user };
  if (fields.includes('self')) out.self = chosen.self || defaults.self;
  return out;
}
