/* Reading Transfer (design route `rtransfer`, frame 39, D-091, D-088). An active-use drill on the
   text the learner is reading: pick a mode (Paraphrase / Inference / Context Shift), get one real
   sentence of the text and the mode's prompt, answer by typing or by voice, get coaching, then
   Retry, move to another sentence, or Finish.

   The coaching is the real `POST /api/dictionary/spoken-response` (see model.js for why it, and
   not the frame's client-side heuristic, is what this screen stands on). Consequences the frame
   does not draw, recorded in docs/project/UI_BACKEND_GAPS.md:
   - the result's two tiles hold the endpoint's two real lists ("What carried", "What would land
     differently"), each item a quotation of the learner's own words with its reason; the frame's
     "Meaning preserved?" / "Missing important idea?" verdicts are not measured by anything real
     and are not drawn (rule 40);
   - nothing is written to the learner's record - there is no Reading Transfer evidence contract -
     so "Finish" only leaves;
   - a failed check keeps the learner on the answer with their text intact (the toast is the
     app's drawn mechanism for a transient failure); the frame draws no error visual.

   Not drawn here (rule 43/44): the frame's header suffix "active use of what you read" (rule 50 -
   restates the place's name), a loading visual beyond the button's own "Checking…" label, a
   celebration, the agent panel. No agent action applies (there is no model to play and no take to
   replay), so none is registered. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { emptyMarkup } from '../../kit/states.js';
import { toast } from '../../kit/toast.js';
import { langAttr } from '../../kit/lang.js';
import { shellCopy } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { api } from '../../infrastructure/api.js';
import { createLocalAudioRecorder, localAudioRecordingSupported } from '../../capabilities/audio-recorder.js';
import { parseContentId } from '../content/model.js';
import { micGate, openMicState } from '../mic/sheet.js';
import { t } from './copy.js';
import {
  READABLE_KINDS, COACH_LIMITS, MODES, paragraphsOf, workableSentences, nextIndex, canMoveOn, canCheck, coachRequest, mapCoaching,
} from './model.js';

const MODE_COPY = {
  paraphrase: { chip: () => t('modeParaphrase'), prompt: () => t('promptParaphrase') },
  inference: { chip: () => t('modeInference'), prompt: () => t('promptInference') },
  context_shift: { chip: () => t('modeContextShift'), prompt: () => t('promptContextShift') },
};

const RECORD_LIMIT_MS = 30000;

/* The text being read: the same three sources the Reader opens (article, a book chapter, the
   learner's own import held on this device). A id that is not one of them throws, and the router
   shows the design's load error (Back / Retry). */
async function loadDoc(parsed, ctx) {
  const { kind, id, chapterId } = parsed;
  if (!READABLE_KINDS.includes(kind)) throw new Error('Reading Transfer: this is not a text.');
  if (kind === 'article') {
    const article = await api.readingArticle(id);
    return { title: String(article?.title || ''), language: String(article?.language || ''), paragraphs: paragraphsOf('article', article) };
  }
  if (kind === 'book') {
    const book = await api.libraryBook(id);
    const ordered = [...(book?.chapters || [])].sort((a, b) => (a.position ?? 0) - (b.position ?? 0));
    const targetChapterId = chapterId || ordered[0]?.id;
    if (!targetChapterId) throw new Error('This book has no chapters.');
    const chapter = await api.libraryBookChapter(id, targetChapterId);
    return {
      title: String(chapter?.title || book?.title || ''),
      language: String(chapter?.language || book?.learning_language || ''),
      paragraphs: paragraphsOf('book', chapter),
    };
  }
  const record = ctx.context.memory.value.imports.find((item) => item.id === `text:${id}`);
  if (!record) throw new Error('This text is not on this device.');
  return { title: String(record.title || ''), language: String(record.language || ''), paragraphs: paragraphsOf('text', record) };
}

function headerMarkup(title) {
  return html`<div class="s-reading-transfer__head">
    <button type="button" class="o-iconbtn o-iconbtn--back" data-back aria-label="${shellCopy('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
    <div class="s-reading-transfer__head-body">
      <div class="s-reading-transfer__title">${shellCopy('readingTransfer')}</div>
      ${title ? html`<div class="s-reading-transfer__meta">${title}</div>` : ''}
    </div>
  </div>`;
}

export default async function mountReadingTransfer(element, ctx) {
  await useStyles('screens/reading-transfer/reading-transfer.css');
  const parsed = parseContentId(ctx.params?.id);
  const doc = await loadDoc(parsed, ctx);
  if (!ctx.isCurrent()) return undefined;

  /* `language` is the learner's learning language - the one their answer is written in and the only
     one the coaching endpoint accepts. The text's own language (what its sentences are counted and
     marked in) is what the text declares, falling back to it. */
  const language = ctx.context.language;
  const textLanguage = doc.language || language;
  const support = languages().support;
  const sentences = workableSentences(doc.paragraphs, textLanguage);

  if (!sentences.length) {
    mount(
      element,
      html`<div class="s-reading-transfer">
        ${headerMarkup(doc.title)}
        <div class="s-reading-transfer__blank">${emptyMarkup({ text: t('noSentence'), actionLabel: t('backToReading'), iconName: 'book-open' })}</div>
      </div>`,
    );
    element.querySelector('[data-back]').addEventListener('click', () => ctx.back());
    element.querySelector('[data-empty-action]')?.addEventListener('click', () => ctx.back());
    return undefined;
  }

  let mode = MODES[0].key;
  let index = 0;
  let answer = '';
  let phase = 'input'; // 'input' | 'result'
  let result = null;
  let checking = false;
  let recording = false;
  let transcribing = false;
  let micUnsupported = !localAudioRecordingSupported();
  let recorder = null;
  let stopTimer = 0;
  /* Bumped whenever the attempt a pending request belongs to is left (a new mode, another
     sentence, Retry): a late answer for an attempt that is gone is never painted. */
  let attempt = 0;

  const busy = () => checking || transcribing || recording;

  mount(
    element,
    html`<div class="s-reading-transfer">
      ${headerMarkup(doc.title)}
      <div class="s-reading-transfer__modes" data-modes>${MODES.map((item) => html`<button type="button" class="s-reading-transfer__mode" data-mode="${item.key}" aria-pressed="${item.key === mode ? 'true' : 'false'}">${MODE_COPY[item.key].chip()}</button>`)}</div>
      <div class="s-reading-transfer__card">
        <div class="s-reading-transfer__body" data-scroll-region data-body tabindex="-1"></div>
        <div class="s-reading-transfer__foot" data-foot></div>
      </div>
    </div>`,
  );
  const body = element.querySelector('[data-body]');
  const foot = element.querySelector('[data-foot]');
  element.querySelector('[data-back]').addEventListener('click', () => ctx.back());

  function sourceMarkup() {
    return html`<div class="s-reading-transfer__label">${t('sourceLabel')}</div>
      <div class="s-reading-transfer__sentence" lang="${langAttr(textLanguage)}">${sentences[index]}</div>
      <div class="s-reading-transfer__prompt">${MODE_COPY[mode].prompt()}</div>`;
  }

  function pointMarkup(point, withInstead) {
    return html`<div class="s-reading-transfer__point">
      <div class="s-reading-transfer__quote" lang="${langAttr(language)}">“${point.quote}”</div>
      <div class="s-reading-transfer__why" lang="${langAttr(support)}">${point.why}</div>
      ${withInstead && point.instead ? html`<div class="s-reading-transfer__instead"><b>${t('insteadLabel')}</b> · <span lang="${langAttr(language)}">${point.instead}</span></div>` : ''}
    </div>`;
  }

  function tileMarkup(kind, label, points, withInstead) {
    return html`<div class="${`s-reading-transfer__tile s-reading-transfer__tile--${kind}`}">
      <div class="s-reading-transfer__tile-label">${label}</div>
      ${points.map((point) => pointMarkup(point, withInstead))}
    </div>`;
  }

  function resultMarkup() {
    const tiles = [];
    if (result.carried.length) tiles.push(tileMarkup('carried', t('carriedLabel'), result.carried, false));
    if (result.landed.length) tiles.push(tileMarkup('landed', t('landedLabel'), result.landed, true));
    const nothing = !tiles.length && !result.improvement;
    return html`<div class="s-reading-transfer__echo" lang="${langAttr(language)}">“${answer.trim()}”</div>
      ${tiles.length ? html`<div class="${tiles.length === 1 ? 's-reading-transfer__tiles s-reading-transfer__tiles--single' : 's-reading-transfer__tiles'}">${tiles}</div>` : ''}
      ${result.improvement ? html`<div class="s-reading-transfer__callout"><b>${t('improvementLabel')}</b> · <span lang="${langAttr(support)}">${result.improvement}</span></div>` : ''}
      ${nothing ? html`<div class="s-reading-transfer__empty">${t('notPrepared')}</div>` : ''}`;
  }

  function paintBody({ focus = false } = {}) {
    if (phase === 'result') {
      mount(body, html`${sourceMarkup()}${resultMarkup()}`);
    } else {
      mount(
        body,
        html`${sourceMarkup()}<textarea class="s-reading-transfer__textarea" rows="3" maxlength="${COACH_LIMITS.transcript}" lang="${langAttr(language)}" aria-label="${t('answerLabel')}" placeholder="${t('placeholder')}" data-answer></textarea>`,
      );
      const field = body.querySelector('[data-answer]');
      field.value = answer;
      field.addEventListener('input', () => {
        answer = field.value;
        syncCheck();
      });
    }
    /* The body is one element whose content is replaced, so it would keep the place the learner had
       scrolled to (typing into a long answer). A new state starts at the top - except a result,
       which starts at the learner's own answer so the coaching is what they see first (the source
       sentence stays one scroll above). */
    body.scrollTop = 0;
    if (phase === 'result' && body.scrollHeight > body.clientHeight) {
      const echo = body.querySelector('.s-reading-transfer__echo');
      if (echo) body.scrollTop = Math.max(0, echo.getBoundingClientRect().top - body.getBoundingClientRect().top - 4);
    }
    if (focus) body.focus({ preventScroll: true });
  }

  function micLabel() {
    if (recording) return t('listening');
    if (transcribing) return t('transcribing');
    return t('speak');
  }

  function paintFoot() {
    if (phase === 'result') {
      foot.classList.add('s-reading-transfer__foot--result');
      mount(
        foot,
        html`<button type="button" class="s-reading-transfer__secondary" data-retry>${shellCopy('retry')}</button>
          ${canMoveOn(sentences.length) ? html`<button type="button" class="s-reading-transfer__secondary" data-another>${t('anotherSentence')}</button>` : ''}
          <span class="s-reading-transfer__spacer"></span>
          <button type="button" class="s-reading-transfer__primary s-reading-transfer__primary--finish" data-finish>${t('finishLabel')}</button>`,
      );
      foot.querySelector('[data-retry]').addEventListener('click', () => resetAttempt());
      foot.querySelector('[data-another]')?.addEventListener('click', () => {
        index = nextIndex(index, sentences.length);
        resetAttempt();
      });
      foot.querySelector('[data-finish]').addEventListener('click', () => ctx.back());
      return;
    }
    foot.classList.remove('s-reading-transfer__foot--result');
    /* The frame draws Check filled whether or not there is an answer (its handler simply returns on an
       empty one), so an empty answer is not styled as disabled: `aria-disabled` tells assistive
       technology, a tap on an empty answer does nothing, as in the frame, and only real work in
       flight (a check, a transcription, a recording) disables the button. */
    mount(
      foot,
      html`${micUnsupported ? '' : html`<button type="button" class="s-reading-transfer__mic" data-mic aria-pressed="${recording ? 'true' : 'false'}"${transcribing || checking ? ' disabled' : ''}>${raw(icon('mic', { size: 16 }))}${micLabel()}</button>`}
        <span class="s-reading-transfer__spacer"></span>
        <button type="button" class="s-reading-transfer__primary" data-check aria-disabled="${canCheck(answer, false) ? 'false' : 'true'}"${busy() ? ' disabled' : ''}>${checking ? t('checking') : t('checkLabel')}</button>`,
    );
    foot.querySelector('[data-mic]')?.addEventListener('click', onMicTap);
    foot.querySelector('[data-check]').addEventListener('click', onCheck);
  }

  function syncCheck() {
    foot.querySelector('[data-check]')?.setAttribute('aria-disabled', canCheck(answer, false) ? 'false' : 'true');
  }

  function paintModes() {
    element.querySelectorAll('[data-mode]').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.mode === mode)));
  }

  function paint(options) {
    paintBody(options);
    paintFoot();
  }

  /* Leaving the current attempt - Retry, another sentence or another mode - discards the answer
     (the frame clears the shared answer box in every one of them) and whatever is still pending. */
  function resetAttempt() {
    attempt += 1;
    clearTimeout(stopTimer);
    if (recording || transcribing) recorder?.stop().catch(() => {});
    recording = false;
    transcribing = false;
    checking = false;
    answer = '';
    result = null;
    phase = 'input';
    paint();
  }

  element.querySelectorAll('[data-mode]').forEach((button) => {
    button.addEventListener('click', () => {
      if (button.dataset.mode === mode) return;
      mode = button.dataset.mode;
      paintModes();
      resetAttempt();
    });
  });

  /* ------------------------------------------------------------------ voice ---- */
  async function onMicTap() {
    if (recording) return stopRecording();
    if (transcribing || checking) return undefined;
    return micGate(ctx, startRecording);
  }

  async function startRecording() {
    const mine = attempt;
    recorder = createLocalAudioRecorder();
    const ok = await recorder.start();
    if (!ctx.isCurrent() || mine !== attempt) return;
    if (!ok) {
      micUnsupported = true;
      paintFoot();
      return;
    }
    recording = true;
    paintFoot();
    stopTimer = setTimeout(() => stopRecording(), RECORD_LIMIT_MS);
  }

  async function stopRecording() {
    const mine = attempt;
    clearTimeout(stopTimer);
    recording = false;
    const captured = await recorder?.stop();
    if (!ctx.isCurrent() || mine !== attempt) return;
    if (!captured) {
      paintFoot();
      return;
    }
    transcribing = true;
    paintFoot();
    let text = '';
    try {
      const res = await api.transcribeSpeech(captured.blob, language);
      text = String(res?.text || '').trim();
    } catch {
      if (!ctx.isCurrent() || mine !== attempt) return;
      transcribing = false;
      paintFoot();
      openMicState(ctx, {
        state: navigator.onLine === false ? 'offline' : 'provider',
        onAction: (key) => {
          if (key === 'retry') micGate(ctx, startRecording);
        },
      });
      return;
    }
    if (!ctx.isCurrent() || mine !== attempt) return;
    transcribing = false;
    if (!text) {
      paintFoot();
      openMicState(ctx, {
        state: 'notheard',
        onAction: (key) => {
          if (key === 'tryagain') micGate(ctx, startRecording);
        },
      });
      return;
    }
    answer = (answer.trim() ? `${answer.trim()} ${text}` : text).slice(0, COACH_LIMITS.transcript);
    const field = body.querySelector('[data-answer]');
    if (field) field.value = answer;
    paintFoot();
  }

  /* ------------------------------------------------------------------ check ---- */
  async function onCheck() {
    // The frame's handler returns on an empty answer and does nothing else (rule 44).
    if (busy() || !canCheck(answer, false)) return;
    const mine = attempt;
    checking = true;
    paintFoot();
    try {
      const raw = await api.spokenResponseCoaching(coachRequest({ answer, mode, sentence: sentences[index], language, support }));
      if (!ctx.isCurrent() || mine !== attempt) return;
      result = mapCoaching(raw);
      phase = 'result';
      checking = false;
      paint({ focus: true });
    } catch (error) {
      if (!ctx.isCurrent() || mine !== attempt || error?.name === 'AbortError') return;
      checking = false;
      paintFoot();
      toast(t('coachingError'), { iconName: 'circle-alert' });
    }
  }

  paint();

  return () => {
    attempt += 1;
    clearTimeout(stopTimer);
    if (recorder) recorder.stop().catch(() => {});
  };
}
