/* The action card (OA3, D1 §6.2) and the source card (OA4) - shared between Orena Home's thread and
   the Contextual panel's, because both must let the learner actually run an offered action
   (AGENT_CONTRACT §7 "An action is shown as a button"), even though the panel's own frame (55)
   draws no card for either (E5 §6.6/§9: "no action-handoff... component exists" / "no evidence-
   card component exists anywhere in these six frames" - a named, undrawn gap, not a reason to
   leave an offered action untappable). Reusing Home's one measured shapes here, rather than
   inventing second ones for the panel, is the conservative fill (Design Contract rule 7).

   Everything a card says is a real field of the event (AGENT_CONTRACT §5.5 `display`, §7 `label`,
   §5.3 `source`), in the interface language: `display.kind` is an enum (reading | listening | ...)
   and is written out in the learner's language, never shown raw; `duration_s` is shown as whole
   minutes; a field the server did not send is absent, never estimated (rule 40). */
import { html, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { t } from './copy.js';

const EVIDENCE_SOURCE_KEY = Object.freeze({
  'speech.pronunciation': 'kindPronunciation',
  'writing.evaluation': 'kindWritingEvaluation',
  'reading.comprehension': 'kindReadingComprehension',
  'listening.dictation': 'kindListeningDictation',
  'vocabulary.review': 'kindVocabularyReview',
  'grammar.catalog': 'kindGrammarCatalog',
  learner_summary: 'kindLearnerSummary',
});

const DISPLAY_KIND_KEY = Object.freeze({
  reading: 'displayKindReading',
  listening: 'displayKindListening',
  speaking: 'displayKindSpeaking',
  writing: 'displayKindWriting',
  vocabulary: 'displayKindVocabulary',
  grammar: 'displayKindGrammar',
  review: 'displayKindReview',
});

/* '' for a kind this build has no word for - never the raw enum. */
export function displayKindLabel(kind) {
  const key = DISPLAY_KIND_KEY[kind];
  return key ? t(key) : '';
}

/* `duration_s` as the frame writes it ("~4 min"), whole minutes, at least one; '' when absent. */
export function durationLabel(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value <= 0) return '';
  return t('durationMinutes', { n: Math.max(1, Math.round(value / 60)) });
}

/* The card's first line, "{kind} · {duration}" - only the parts the server sent. */
export function actionMeta(display) {
  return [displayKindLabel(display?.kind), durationLabel(display?.duration_s)].filter(Boolean).join(' · ');
}

export function hasCard(display) {
  return Boolean(display && (actionMeta(display) || display.title || display.reason));
}

/* A `display` with something to draw is the frame's card (kind · duration, title, reason, the
   button); an action with none is the button alone - the card's own button, not an empty card
   around it. `done` disables it once the learner has run it (§7 never describes a "run again"
   gesture). */
export function actionCardMarkup(action, { done = false } = {}) {
  const display = action.display;
  const disabled = done ? raw('disabled aria-disabled="true"') : '';
  const cta = html`<span class="s-orena-action__cta">${action.label}</span>`;
  if (!hasCard(display)) {
    return html`<button type="button" class="s-orena-action s-orena-action--bare" data-action-id="${action.id}" ${disabled}>${cta}</button>`;
  }
  const meta = actionMeta(display);
  return html`<button type="button" class="s-orena-action" data-action-id="${action.id}" ${disabled}>
    <span class="s-orena-action__body">${meta ? html`<span class="s-orena-action__eyebrow">${meta}</span>` : ''}${display.title ? html`<span class="s-orena-action__title">${display.title}</span>` : ''}${display.reason ? html`<span class="s-orena-action__reason">${display.reason}</span>` : ''}</span>
    ${cta}
  </button>`;
}

/* A source (evidence) the reply cites: the frame's OA4 card (kind, title) when the server sent
   `display.title`, else the source's own name as a small note. Not a link: `evidence.ref` is an
   evaluation locator, not a place the app can open (docs/project/UI_BACKEND_GAPS.md N-37), and the
   `excerpt` is data the frames never draw. '' for a source this build has no name for. */
export function evidenceMarkup(evidence) {
  const key = EVIDENCE_SOURCE_KEY[evidence?.source];
  const source = key ? t(key) : '';
  const display = evidence?.display;
  const kind = displayKindLabel(display?.kind) || source;
  if (display?.title) {
    return html`<div class="s-orena-source"><div class="s-orena-source__body"><div class="s-orena-source__kind">${kind}</div><div class="s-orena-source__title">${display.title}</div></div></div>`;
  }
  if (!source) return '';
  return html`<div class="s-orena-evidence">${raw(icon('quote', { size: 14 }))}<span class="s-orena-evidence__label">${source}</span></div>`;
}
