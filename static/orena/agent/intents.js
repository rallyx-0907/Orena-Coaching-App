/* Surface ids and navigation intents (AGENT_CONTRACT §6.1) → the new UI's routes. The agent names
   intents, never routes; this is the one place the UI maps them (D-086). An intent is supported
   only while the screen it opens is built (shell/screens.js), so `client.supported_intents` is
   always the truth (§3.1). */
import { SURFACES, fromContractLang } from './contract.js';
import { byId, href } from '../shell/routes.js';

/* §6.1 (F-9): a Listening `content_id` is `media:<id>`; the Listening routes take the bare id. A bare
   id from an older server is passed through unchanged. */
export function mediaRouteId(contentId) {
  const value = String(contentId || '');
  return value.startsWith('media:') ? value.slice('media:'.length) : value;
}

/* §6.1 (F-3): `grammar.point` carries a Grammar Lab point id. Until the canonical Grammar API serves
   points (grammar-source.js reads no live store yet), the intent is not offered, so the agent never
   navigates to a grammar point it cannot name in the store's ids. */
const AWAITING_CANONICAL_STORE = new Set(['grammar.point']);

/* intent → [route id, params from payload, query from payload] */
const MAP = {
  home: (p) => ['today'],
  'orena.home': () => ['orena'],
  library: () => ['discover'],
  'reading.library': () => ['discover', {}, { tab: 'read' }],
  'reading.workspace': (p) => ['reader', { id: p.content_id }],
  'listening.library': () => ['discover', {}, { tab: 'listen' }],
  'listening.workspace': (p) => ['listening', { id: mediaRouteId(p.content_id) }],
  'listening.dictation': (p) => ['dictation', { id: mediaRouteId(p.content_id) }],
  'speaking.library': () => ['skillhub', { skill: 'speak' }],
  'speaking.workspace': (p) => ['speak', { id: p.content_id }],
  'speaking.free_talk': () => ['freetalk'],
  'speaking.word_detail': (p) => ['compare', { id: p.take_ref }, { item: p.item_id, view: 'word' }],
  'speaking.compare': (p) => ['compare', { id: p.take_ref }, { item: p.item_id }],
  'writing.workspace': () => ['writing'],
  'writing.review': (p) => ['writingDraft', { id: p.essay_id }],
  'writing.revision': (p) => ['wrcompare', { id: p.essay_id }],
  'vocabulary.my_language': () => ['library', {}, { tab: 'language' }],
  'vocabulary.word': (p) => ['word', { id: p.text }],
  'vocabulary.review_due': () => ['review'],
  'grammar.catalog': () => ['grammarlib'],
  'grammar.point': (p) => ['gconcept', { id: p.grammar_id }],
  progress: () => ['progress'],
  preferences: () => ['settings'],
  'preferences.agent_memory': () => ['settings', {}, { tab: 'privacy', section: 'orena' }],
};

export function intentRoute(intent) {
  const build = MAP[intent];
  return build ? build({})[0] : null;
}

/* The address an intent opens, or null when a required parameter is missing. */
export function intentHref(intent, payload = {}) {
  const build = MAP[intent];
  if (!build) return null;
  for (const name of SURFACES[intent] || []) if (payload[name] == null || payload[name] === '') return null;
  const [id, params = {}, query = {}] = build(payload);
  if (!byId(id)) return null;
  try {
    return href(id, params, query);
  } catch {
    return null;
  }
}

/* Intents whose screen is built. `built` is the set of screen folders in shell/screens.js. */
export function supportedIntents(built) {
  return Object.keys(MAP).filter((intent) => {
    if (AWAITING_CANONICAL_STORE.has(intent)) return false;
    const route = byId(intentRoute(intent));
    return route && built.has(route.screen);
  });
}

/* The `lang` of a word payload as the product's language code. */
export function productLang(lang) {
  return fromContractLang(lang);
}

export const INTENTS = Object.freeze(Object.keys(MAP));
