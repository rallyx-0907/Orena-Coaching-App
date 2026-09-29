/* Pure data/logic for Orena Home, the Contextual Orena panel, full-screen voice and the coach-
   notes sheet (D1 §6, E5 §6-7). No DOM: scripts/test_orena_screen_orena.mjs exercises every
   export directly. */
import { intentRoute } from '../../agent/intents.js';
import { ACTIONS } from '../../agent/contract.js';
import { byId } from '../../shell/routes.js';
import { shellCopy } from '../../copy/shell.js';

/* The route title a §6.1 surface id opens, in the live interface language - the same name
   AGENT_CONTRACT §6.2 publishes (static/orena/copy/surfaces.json), read straight from the shell's
   own copy rather than that generated file: the client already holds the source it was built
   from, and the JSON exists for the server (§6.2 "The server reads names ... and keeps no copies
   of its own"). '' when the id has no route or the route's title is missing. */
export function surfaceTitle(surfaceId) {
  const route = byId(intentRoute(surfaceId));
  return route ? shellCopy(route.crumb) : '';
}

const ITEM_KIND_KEY = Object.freeze({
  word: 'kindWord',
  sentence: 'kindSentence',
  grammar_point: 'kindGrammarPoint',
  feedback_item: 'kindFeedback',
});

/* One formatter for "what is Orena attached to" - the context pill in the Contextual panel and
   the subtitle in full-screen voice. The source draws two independently hand-written versions of
   this for the same context object (E5 §6.6 open question 7); this build has one. `context` is
   the shape shell/agent-bridge.js's askOrena() takes. `t` is this folder's own copy(). Real data
   only: a context with neither a caller label, a selected item nor a resolvable surface title
   renders '' (rule 40) - the caller then draws no pill rather than an invented one. */
export function contextLabel(context = {}, t) {
  const { text, kind } = contextParts(context, t);
  if (text && kind) return `${text} · ${kind}`;
  return text || kind || '';
}

/* The same label in its two parts, for a caller that marks the learning-language text with its own
   `lang`: `text` is the caller's label or the selected item's own text (`lang`: the contract code
   the item declares, '' for none), `kind` the item's kind or the surface's title. */
export function contextParts(context = {}, t) {
  const label = String(context.label || '').trim();
  if (label) return { text: label, lang: '', kind: '' };
  const item = context.selected_item;
  const kindKey = item && ITEM_KIND_KEY[item.type];
  const kind = kindKey ? t(kindKey) : surfaceTitle(context.surface);
  const text = String(item?.text || '').trim();
  return { text, lang: text ? String(item?.lang || '') : '', kind };
}

/* The suggestion chips under the composer: the most recent Orena turn's own `suggestion` events
   (AGENT_CONTRACT §4 - a suggestion is a prompt intent, tapping it sends its label as the next
   message). No suggestions on the latest turn -> no chips; never a static/invented starter list
   (rule 40). `messages` is `session.state().messages`. */
export function latestSuggestions(messages = []) {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message.role === 'orena') return message.suggestions || [];
  }
  return [];
}

/* voice.js's phase machine (idle -> listening -> thinking -> speaking -> idle, or -> error) maps
   to the mark the design draws for each phase (`voiceMark` in the source: idle ol-intel, listening
   ol-intel-listen, thinking ol-intel-think, speaking ol-intel-speak - kit/brand.js's `INTEL_STATES`).
   AGENT_CONTRACT's `voice_state` enum (listening/thinking/speaking/interrupted) has no "idle"
   value; this client's phases are its own local reducer (no live provider session exists yet, §9
   "provisional"), and a failed turn is not a mascot state the design names, so it reads as idle. */
const PHASE_MARK_STATE = Object.freeze({ idle: 'idle', listening: 'listening', thinking: 'thinking', speaking: 'speaking', error: 'idle' });
const PHASE_STATUS_KEY = Object.freeze({ idle: 'voiceStatusIdle', listening: 'voiceStatusListening', thinking: 'voiceStatusThinking', speaking: 'voiceStatusSpeaking', error: 'voiceStatusIdle' });
const PHASE_HINT_KEY = Object.freeze({ idle: 'voiceHintIdle', listening: 'voiceHintListening', thinking: 'voiceHintThinking', speaking: 'voiceHintSpeaking', error: '' });

export function voicePhaseMarkState(phase) {
  return PHASE_MARK_STATE[phase] || PHASE_MARK_STATE.idle;
}
export function voicePhaseStatusKey(phase) {
  return PHASE_STATUS_KEY[phase] || PHASE_STATUS_KEY.idle;
}
export function voicePhaseHintKey(phase) {
  return PHASE_HINT_KEY[phase] ?? '';
}

/* The coach-notes sheet (preferences.agent_memory, the privacy exit, AGENT_CONTRACT §10): the
   address note first (it is the learner's identity choice, distinct from an ordinary coach note),
   then the rest by weight, heaviest first - matching session.buildRequest's own `requestNotes()`
   ordering for everything that is not the address note. `notes` is agent/memory.js's `notes()`. */
export function sortedMemoryNotes(notes = []) {
  const address = notes.filter((note) => note.kind === 'address');
  const rest = notes.filter((note) => note.kind !== 'address').sort((a, b) => b.weight - a.weight);
  return [...address, ...rest];
}

const KIND_LABEL_KEY = Object.freeze({ preference: 'memoryKindPreference', goal: 'memoryKindGoal', plan: 'memoryKindPlan', address: 'memoryKindAddress' });

export function noteKindLabel(kind, t) {
  return t(KIND_LABEL_KEY[kind] || 'memoryKindPreference');
}

/* Today's greeting card in the shell reads a real device clock and a real learner name; Orena
   Home's own header has no per-time-of-day content to build, only the target-language label. The
   frame's own "last active: Listening, 2 h ago" clause has no backing data anywhere in this build
   - product/memory.js's `continuation` entries carry no timestamp at all - so it is dropped
   entirely rather than shown with an invented time (rule 40; D1 §6 copy audit already flags this
   exact clause as unresolved). `languageLabel` is the shell's own `{{ tlLabel }}` equivalent
   (learning language name, plus level when the learner has declared one). */
export function homeSubtitle(languageLabel, t) {
  const label = String(languageLabel || '').trim();
  return label ? t('subtitle', { language: label }) : '';
}

/* What voice mode speaks aloud: the finished reply's segments, in reading order, skipping any
   `reference` segment (§5.2 - that text is the app's own reference/word audio, played through the
   accompanying `play_model` action, never read out in Orena's conversational voice). '' when the
   reply is not done, carries no segments, or errored (voice.js shows the error state instead). */
export function speakableText(reply) {
  // S12: a soft-limited (metered) turn is a short text answer with no voice (AGENT_CONTRACT §12).
  if (!reply?.done || reply.error || reply.metered === 'soft_limited' || !Array.isArray(reply.segments)) return '';
  return reply.segments
    .filter((segment) => segment.voice_style !== 'reference')
    .map((segment) => String(segment.text || '').trim())
    .filter(Boolean)
    .join(' ');
}

/* A stable per-context key for the Contextual panel: two asks about the very same selection are
   the same conversation topic for this session's purposes (AGENT_CONTRACT §3.2 "the client may
   reuse [the opening turn] for the same surface + selected_item within a session"). Home has no
   such key (it is always the one ambient thread). */
export function contextKey(context = {}) {
  const item = context.selected_item;
  const parts = [context.surface || '', item?.type || '', item?.id || '', item?.text || ''];
  return parts.join('\u0001');
}

/* AGENT_CONTRACT §7: "An action with an unknown `type`, or not in `supported_actions`, is ignored
   and logged by the client." Ignored means never drawn - a button that does nothing when tapped is
   worse than no button. `supported` is `dispatcher.supported()` read at paint time, so an action a
   workspace registered while the panel is open (play_model, say_again ...) appears, and is gone
   again when the workspace unmounts. Each ignored action is logged once, by its id. */
const loggedIgnored = new Set();

export function offerableActions(actions = [], supported = [], log = console.warn) {
  return (actions || []).filter((action) => {
    const type = action?.type;
    if (type in ACTIONS && supported.includes(type)) return true;
    if (action?.id && !loggedIgnored.has(action.id)) {
      loggedIgnored.add(action.id);
      log('[Orena agent] ignored an action this client cannot run', type);
    }
    return false;
  });
}

/* What a tap that did not run says (§7 "the client says so in its own words and does nothing
   else"): a word outside the learning language is named; every other failure is one short line.
   A refused confirmation is the learner's own answer and says nothing. '' = say nothing. */
export function actionFailureKey(result) {
  if (result?.ok) return '';
  if (result?.reason === 'declined') return '';
  if (result?.reason === 'other_language') return 'actionOtherLanguage';
  return 'actionFailed';
}

/* §4: "shows `tool_call.label` while a tool runs" - the learner-safe line the server sent, else the
   generic "Orena is thinking…". */
export function thinkingText(tool, fallback) {
  const label = String(tool?.label || '').trim();
  return label || fallback;
}

/* §4.1: the client's own `transport` error has no message from a server - the message is the
   client's own copy, in the support language (`fallbackText`); every other class shows the
   server's. */
export function errorText(error, fallbackText) {
  return String(error?.message || '').trim() || fallbackText;
}

/* §4.1 `text_only`: the voice session ended - voice mode closes and the conversation continues in
   text. True when a finished reply says so. */
export function endsVoice(reply) {
  return reply?.error?.fallback === 'text_only';
}
