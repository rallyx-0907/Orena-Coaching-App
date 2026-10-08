/* Runs the agent's actions (AGENT_CONTRACT §7) through the app's existing APIs with the learner's
   session. The agent backend never mutates learner data; this does, only on the learner's tap.

   - `risk` is the contract's for the type, never the event's (§7);
   - an unknown type, or one this client does not support, is ignored and logged;
   - CONFIRM actions need the UI's own confirmation first;
   - word actions run only in the session's active learning language;
   - take_ref / content ids are used only as received;
   - a call that throws (the network, a 4xx) is a failed action - `{ ok: false, reason: 'failed' }` -
     never an unhandled rejection, so the caller can tell the learner and leave the button usable.

   `api` is the app's own `infrastructure/api.js` object: the methods called below are the real
   ones (scripts/test_orena_agent.mjs reads this file and that one and fails when a name here is
   not exported there), so a hand-written fake in a test can no longer agree with a name the app
   does not have.

   Actions that belong to a workspace (play_model, play_user, say_again, compare_with_model,
   start_targeted_drill) are supported only while a screen registers a handler for them - so
   `client.supported_actions` never claims what the UI cannot do right now. */
import { ACTIONS, fromContractLang } from './contract.js';
import { intentHref } from './intents.js';

const handlers = new Map();

/* Core actions this UI can always execute, given the services they need. */
export function createDispatcher({ api, go, learningLanguage, confirm, log = console.warn, hasRoute = () => true, canPickCollection = () => false }) {
  const core = {
    navigate: async (payload) => {
      const target = intentHref(payload.intent, payload);
      if (!target) return { ok: false, reason: 'unknown_intent' };
      go(target);
      return { ok: true };
    },
    save_word: async (payload) => {
      const word = wordOf(payload, learningLanguage());
      if (!word.ok) return word;
      await api.saveLibraryVocabulary({ word: word.text });
      return { ok: true };
    },
    unsave_word: async (payload) => {
      const word = wordOf(payload, learningLanguage());
      if (!word.ok) return word;
      await api.deleteLibraryVocabulary(word.text);
      return { ok: true };
    },
    start_review: async (payload) => {
      if (payload.scope === 'due') {
        go(intentHref('vocabulary.review_due'));
        return { ok: true };
      }
      if (payload.scope === 'word') {
        const word = wordOf(payload, learningLanguage());
        if (!word.ok) return word;
        go(`${intentHref('vocabulary.review_due')}?word=${encodeURIComponent(word.text)}`);
        return { ok: true };
      }
      return { ok: false, reason: 'bad_scope' };
    },
    add_word_to_collection: async (payload) => {
      const word = wordOf(payload, learningLanguage());
      if (!word.ok) return word;
      const target = payload.target;
      if (!target) {
        // No target named: the UI's own add-to sheet lets the learner choose (§7).
        const picker = handlers.get('add_word_to_collection:pick');
        return picker ? picker({ text: word.text }) : { ok: false, reason: 'no_target' };
      }
      if (!['deck', 'library'].includes(target.system) || !target.id) return { ok: false, reason: 'bad_target' };
      await api.saveLibraryVocabulary({ word: word.text }).catch(() => null); // already saved is fine; filing needs it saved
      if (target.system === 'deck') await api.vocabularyDeckAdd(target.id, word.text);
      else {
        const kept = await api.libraryKeep({ kind: 'word', word: word.text });
        const itemId = kept?.item?.id || kept?.id;
        if (!itemId) return { ok: false, reason: 'not_kept' };
        await api.libraryCollectionAdd(target.id, itemId);
      }
      return { ok: true };
    },
  };

  const supported = () => {
    const out = ['navigate', 'save_word', 'unsave_word'];
    // Filing needs the add-to sheet for the case the agent names no target.
    if (canPickCollection() || handlers.has('add_word_to_collection:pick')) out.push('add_word_to_collection');
    if (hasRoute('review')) out.push('start_review');
    for (const type of handlers.keys()) if (type in ACTIONS && !out.includes(type)) out.push(type);
    return out.filter((type) => type in ACTIONS);
  };

  async function run(action, { confirmed = false } = {}) {
    const type = action?.type;
    if (!(type in ACTIONS)) {
      log('[Orena agent] ignored action of unknown type', type);
      return { ok: false, reason: 'unknown_type' };
    }
    if (!supported().includes(type)) {
      log('[Orena agent] ignored unsupported action', type);
      return { ok: false, reason: 'unsupported' };
    }
    if (ACTIONS[type] === 'CONFIRM' && !confirmed) {
      const yes = await confirm(action);
      if (!yes) return { ok: false, reason: 'declined' };
    }
    const payload = action.payload || {};
    const handler = handlers.get(type) || core[type];
    try {
      return await handler(payload, action);
    } catch (error) {
      log('[Orena agent] the action failed', type, error);
      return { ok: false, reason: 'failed' };
    }
  }

  return { run, supported };
}

/* A workspace offers an action while it is mounted; the cleanup it returns withdraws it. */
export function registerActionHandler(type, handler) {
  if (!(type in ACTIONS) && type !== 'add_word_to_collection:pick') throw new Error(`Not a contract action: ${type}`);
  handlers.set(type, handler);
  return () => {
    if (handlers.get(type) === handler) handlers.delete(type);
  };
}

function wordOf(payload, active) {
  const text = String(payload?.text || '').trim();
  if (!text) return { ok: false, reason: 'no_word' };
  if (fromContractLang(payload.lang) !== active) return { ok: false, reason: 'other_language' };
  return { ok: true, text };
}
