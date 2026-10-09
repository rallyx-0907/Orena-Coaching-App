/* One Orena conversation as data: build a turn request (AGENT_CONTRACT §3) and fold the events of
   its stream (§4) into what the panel draws. DOM-free; the panel renders `state()`.

   The client shows Orena as thinking from sending a turn until the first event, and a tool's
   learner-safe label while it runs (§4). Unknown events are ignored and logged.

   The transport's own events (§2.1) fold in too: `wait` keeps Orena thinking through a rate-limit
   pause (`waiting` holds the seconds); `language_mismatch` hands the learner's message back unsent
   (`unsent`), for the panel to return to the composer once the learning language is re-read;
   `absent` means Orena is off (`absent`), which the panel answers by closing, not by an error. */
import { CONTRACT_VERSION, EVENTS, CLIENT_EVENTS, fallbackOf, toContractLang, SELECTED_ITEM_TYPES, normalizeAddress } from './contract.js';

const CONTEXT_FIELDS = ['surface', 'activity_type', 'lesson_id', 'content_id', 'attempt_id', 'take_ref', 'essay_id', 'client_evidence'];

/* §3: omit what does not apply; locale in contract codes (zh → zh-CN, matching every locale field,
   not only `target`); a word by { text, lang }. `address` (§5.6) is the caller's own read of
   agent/memory.js's stored address for the current support language - never derived from the
   message, the selected item or anything else - normalised here and sent only when it is for this
   very request's support language; no stored address, or one for a different language, is omitted. */
export function buildRequest({ trigger = 'message', message = '', context = {}, languages = {}, sessionId = '', client = {}, notes = [], address = null }) {
  const request = { contract_version: CONTRACT_VERSION };
  if (sessionId) request.session_id = sessionId;
  request.trigger = trigger === 'open' ? 'open' : 'message';
  if (request.trigger === 'message') request.message = String(message || '').trim();
  request.client = {
    ui_version: client.ui_version || 'orena-next',
    supported_actions: [...(client.supported_actions || [])],
    supported_intents: [...(client.supported_intents || [])],
  };
  const ctx = {};
  // An id is a string on the wire (contract §3, the server's `_ID` pattern); a surface that holds one as a number
  // (an essay from /api/evaluate) must not have its turn refused as malformed (LEX-022).
  for (const field of CONTEXT_FIELDS) {
    const value = context[field];
    if (value == null || value === '') continue;
    ctx[field] = typeof value === 'number' ? String(value) : value;
  }
  const support = toContractLang(languages.support);
  const target = toContractLang(languages.target);
  ctx.locale = {
    interface: toContractLang(languages.interface),
    support,
    target,
    content: toContractLang(context.content_lang || languages.target),
  };
  const item = context.selected_item;
  if (item && SELECTED_ITEM_TYPES.includes(item.type) && String(item.text || '').trim()) {
    ctx.selected_item =
      item.type === 'word'
        ? {
            type: 'word',
            text: String(item.text).trim(),
            lang: toContractLang(item.lang || languages.target),
            // The sentence the word was selected in, so "here" can be answered (contract §3, LEX-006).
            ...(String(item.sentence || '').trim() ? { sentence: String(item.sentence).trim().slice(0, 500) } : {}),
          }
        : { type: item.type, ...(item.id ? { id: String(item.id) } : {}), text: String(item.text).trim() };
  }
  if (address && address.lang === support) {
    const normalized = normalizeAddress(address, support);
    if (normalized) ctx.address = normalized;
  }
  request.context = ctx;
  if (notes.length) request.coach_notes = notes;
  return request;
}

export function createSession({ log = console.warn } = {}) {
  let sessionId = '';
  const messages = [];
  let thinking = false;
  let tool = null;
  let waiting = null;
  let unsent = null;
  let unsentWhy = '';
  let absent = false;

  const current = () => {
    const last = messages[messages.length - 1];
    if (last?.role === 'orena' && !last.done) return last;
    const reply = { role: 'orena', segments: [], actions: [], evidence: [], suggestions: [], error: null, metered: null, done: false };
    messages.push(reply);
    return reply;
  };

  return {
    state: () => ({ sessionId, messages: messages.map((m) => ({ ...m })), thinking, tool, waiting, unsent, unsentWhy, absent }),
    sessionId: () => sessionId,
    /* The learner's own message (not added for an opening turn). */
    learner(text) {
      messages.push({ role: 'learner', text: String(text) });
      thinking = true;
      unsent = null;
      unsentWhy = '';
    },
    opening() {
      thinking = true;
      unsent = null;
      unsentWhy = '';
    },
    /* §4.1 `retry`: the same turn goes again as a new request. The reply that ended in an error
       goes; the learner's own message stays where it is. */
    retry() {
      const last = messages[messages.length - 1];
      if (last?.role === 'orena' && last.error) messages.pop();
      thinking = true;
      unsent = null;
      unsentWhy = '';
    },
    /* The learner's own stop (§2.1 429 "the learner may cancel the wait"): nothing more will
       arrive for the turn in flight. The question they asked comes back unsent, like any other
       turn that did not get an answer - but the reason is theirs, not a changed language. */
    cancel() {
      thinking = false;
      waiting = null;
      tool = null;
      const last = messages[messages.length - 1];
      if (last?.role === 'learner') {
        messages.pop();
        unsent = last.text;
        unsentWhy = 'cancel';
      }
    },
    restore(saved) {
      for (const message of saved || []) messages.push({ ...message, done: true });
    },
    apply({ event, data = {} }) {
      if (CLIENT_EVENTS.includes(event)) {
        if (event === 'wait') {
          waiting = Number(data.seconds) || 1;
          thinking = true;
          return;
        }
        thinking = false;
        waiting = null;
        tool = null;
        const last = messages[messages.length - 1];
        if (last?.role === 'learner') {
          messages.pop();
          unsent = last.text;
          unsentWhy = event === 'language_mismatch' ? 'language' : '';
        }
        if (event === 'absent') absent = true;
        return;
      }
      if (!EVENTS.includes(event)) {
        log('[Orena agent] ignored unknown event', event);
        return;
      }
      // `session` and `metered` are bookkeeping that come first: Orena is still thinking until the reply itself
      // (or a tool, an error, the end) arrives - otherwise a slow model left an idle panel (LEX-028).
      if (event === 'session') {
        sessionId = data.session_id || sessionId;
        return;
      }
      if (event === 'metered') {
        current().metered = data.budget_state || null;
        return;
      }
      thinking = false;
      waiting = null;
      if (event === 'tool_call') {
        tool = { name: data.name, label: String(data.label || '') };
        thinking = true;
        return;
      }
      if (event === 'tool_result') {
        tool = null;
        return;
      }
      const reply = current();
      if (event === 'segment_delta') {
        const seg = reply.segments.find((s) => s.index === data.index) || reply.segments[reply.segments.push({ index: data.index, lang: data.lang, text: '', partial: true }) - 1];
        seg.text += String(data.text_delta || '');
      } else if (event === 'segment_end') {
        const seg = reply.segments.find((s) => s.index === data.index);
        const done = { index: data.index, lang: data.lang, text: String(data.text || ''), voice_style: data.voice_style, partial: false };
        if (seg) Object.assign(seg, done);
        else reply.segments.push(done);
        reply.segments.sort((a, b) => a.index - b.index);
      } else if (event === 'evidence') {
        reply.evidence.push(data);
      } else if (event === 'action') {
        reply.actions.push(data);
      } else if (event === 'suggestion') {
        reply.suggestions.push(data);
      } else if (event === 'error') {
        // `quota` is the transport's own: the plan-limit refusal's figures (D-16X), never a server stream event.
        reply.error = { class: data.class, message: String(data.message || ''), fallback: fallbackOf(data.fallback), ...(data.quota ? { quota: data.quota } : {}) };
        reply.done = true;
        tool = null;
      } else if (event === 'done') {
        reply.done = true;
        tool = null;
        // A turn that ended with nothing to show - no words, no action, no suggestion - is not an answer: the
        // learner gets the client's own retry instead of silence (LEX-028).
        if (!reply.segments.some((s) => String(s.text || '').trim()) && !reply.actions.length && !reply.suggestions.length && !reply.error) {
          reply.error = { class: 'transport', message: '', fallback: 'retry' };
        }
      }
      // memory_update, voice_state and audio_chunk are handled by the panel and voice mode.
    },
    /* The finished reply, for device memory (text and actions only; evidence stays with the turn). */
    lastReply() {
      const last = messages[messages.length - 1];
      return last?.role === 'orena' ? last : null;
    },
  };
}
