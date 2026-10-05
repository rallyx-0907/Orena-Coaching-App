/* Check Understanding (design route `checku`, frame 20, D-091). One question at a time from the
   canonical Reading practice set (writing_coach/reading_practice_api.py): pick an option, get
   immediate per-question feedback (`POST .../grade`), move on; once every question is answered the
   whole answer sheet is submitted once (`POST /attempts`, idempotent by `operation_id`) and a
   done card with a real score and one summary chip per question shows, followed by the shared Lesson Complete
   celebration (E3 §7: its two real trigger points in the source are a finished due-review queue and
   a finished Check Understanding quiz - this screen is the second one).

   Not drawn here (rule 43/44): a confirm-answer step (the frame's options have no separate
   "Answer" button - tapping an option grades it immediately, like React/Reuse's Understand step);
   "Exit practice"/a next-item preview (`cuIsPractice`) - no real entry point in this build passes a
   practice-queue context (only Content Detail's "Practice this text" link does, with none), so it
   never renders (rule 40); a `next chapter`/`review saved words` deeper chip - no real per-document
   next-chapter or saved-word-count signal is available to this screen without a book-chapter
   endpoint out of this pass's scope (recorded in docs/project/UI_BACKEND_GAPS.md). */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { emptyMarkup } from '../../kit/states.js';
import { toast } from '../../kit/toast.js';
import { langAttr } from '../../kit/lang.js';
import { shellCopy } from '../../copy/shell.js';
import { api } from '../../infrastructure/api.js';
import { openLessonComplete } from '../lesson-complete/sheet.js';
import { loadReadable, loadSavedFromText } from '../reader/source.js';
import { t } from './copy.js';
import {
  parseContentId,
  typeLabel,
  optionStyle,
  markFor,
  progressLabel,
  progressPercent,
  scoreSummary,
  nextLabel,
} from './model.js';

function newOperationId() {
  return crypto?.randomUUID ? crypto.randomUUID() : `op${Date.now()}${Math.random().toString(16).slice(2)}`;
}

function headerMarkup(meta) {
  return html`<div class="s-check__head">
    <button type="button" class="o-iconbtn o-iconbtn--back" data-back aria-label="${shellCopy('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
    <div class="s-check__head-body">
      <div class="s-check__title">${shellCopy('checkUnderstanding')}</div>
      ${meta ? html`<div class="s-check__meta">${meta}</div>` : ''}
    </div>
  </div>`;
}

function progressBarMarkup(pct) {
  return html`<div class="s-check__bar"><span style="width:${pct}%"></span></div>`;
}

function optionMarkup(question, index, text, result, supportLang) {
  const chosen = result ? result.selected_index : null;
  const graded = Boolean(result);
  const style = optionStyle({ index, graded, correctIndex: result?.correct_index, selectedIndex: chosen });
  const mark = markFor({ index, graded, correctIndex: result?.correct_index, selectedIndex: chosen });
  /* Once graded an option is inert but stays a normal button: `disabled` would hand it the kit's
     global disabled look (`button:disabled !important`), which erases the very green/red verdict
     colours the frame draws on it. grade() ignores a tap on a question that already has a result. */
  return html`<button type="button" class="s-check__option" data-option="${index}"${graded ? ' aria-disabled="true"' : ''} style="border-color:${style.border};background:${style.bg};color:${style.color}">
    <span class="s-check__mark" style="background:${style.markBg};color:${style.markColor};border-color:${style.border}">${mark}</span><span lang="${langAttr(supportLang)}">${text}</span>
  </button>`;
}

function verdictMarkup(result, index, total, supportLang) {
  const ok = Boolean(result.correct);
  return html`<div class="s-check__verdict">
    <div class="s-check__verdict-line" style="color:${ok ? 'var(--green)' : 'var(--red)'}">${ok ? t('verdictCorrect') : t('verdictIncorrect')}</div>
    ${result.evidence_fragment
      ? html`<div class="s-check__evidence-label">${t('evidenceLabel')}</div><div class="s-check__evidence" lang="${langAttr(supportLang)}">“${result.evidence_fragment}”</div>`
      : ''}
    ${result.explanation ? html`<div class="s-check__explain" lang="${langAttr(supportLang)}">${result.explanation}</div>` : ''}
    <div class="s-check__verdict-actions">
      ${result.evidence_fragment ? html`<button type="button" class="s-check__show" data-show-in-text>${t('showInText')}</button>` : ''}
      <span class="s-check__spacer"></span>
      <button type="button" class="s-check__next" data-next>${nextLabel(index, total, t)}</button>
    </div>
  </div>`;
}

function activeCardMarkup(question, index, total, result, supportLang) {
  return html`<div class="s-check__card" data-scroll-region>
    <span class="s-check__type">${typeLabel(question.question_type, t)}</span>
    <div class="s-check__question" lang="${langAttr(supportLang)}">${question.prompt}</div>
    <div class="s-check__options">${question.options.map((text, i) => optionMarkup(question, i, text, result, supportLang))}</div>
    ${result ? verdictMarkup(result, index, total, supportLang) : ''}
  </div>`;
}

function doneCardMarkup(summary, deeper, practice = null) {
  return html`<div class="s-check__done" data-scroll-region>
    <span class="s-check__blob s-check__blob--a"></span><span class="s-check__blob s-check__blob--b"></span>
    <div class="s-check__result-label">${t('resultLabel')}</div>
    <div class="s-check__score">${t('resultHeadline', { correct: summary.correctCount, total: summary.total })}</div>
    <div class="s-check__chips">${summary.chips.map((chip) => html`<span class="${chip.ok ? 's-check__chip' : 's-check__chip s-check__chip--bad'}">${chip.label} · ${chip.result}</span>`)}</div>
    <div class="s-check__cta"><button type="button" class="s-check__continue" data-continue>${practice ? t('nextReading') : t('continueLabel')}</button>${
      practice ? html`<button type="button" class="s-check__exit" data-exit-practice>${t('exitPractice')}</button>` : ''
    }</div>
    ${practice?.preview ? html`<div class="s-check__upnext">${practice.preview}</div>` : ''}
    ${deeper.length
      ? html`<div class="s-check__deeper">
          <div class="s-check__deeper-head">${t('deeperHeading')}</div>
          <div class="s-check__deeper-row">${deeper.map((chip) => html`<button type="button" class="s-check__deeper-chip" data-deeper="${chip.key}">${chip.label}</button>`)}</div>
        </div>`
      : ''}
  </div>`;
}

function renderEmpty(element, ctx, title, message) {
  mount(
    element,
    html`<div class="s-check">
      ${headerMarkup(title)}
      <div class="s-check__empty">${emptyMarkup({ text: message, actionLabel: t('backToReading'), iconName: 'book-open' })}</div>
    </div>`,
  );
  element.querySelector('[data-back]').addEventListener('click', () => ctx.back());
  element.querySelector('[data-empty-action]')?.addEventListener('click', () => ctx.back());
}

export default async function mountCheck(element, ctx) {
  await useStyles('screens/check/check.css');
  const contentId = String(ctx.params?.id || '');
  const { kind, id } = parseContentId(contentId);

  const title = kind === 'article' ? (await api.readingArticle(id).catch(() => null))?.title || '' : '';
  if (!ctx.isCurrent()) return undefined;

  let setPayload = null;
  let notice = '';
  if (kind !== 'article') {
    notice = t('noPracticeTitle');
  } else {
    try {
      setPayload = await api.readingPracticeSet(id);
    } catch (error) {
      if (error?.status === 404) notice = t('noPracticeTitle');
      else throw error;
    }
  }
  if (!ctx.isCurrent()) return undefined;

  const questions = (setPayload?.set?.questions || []).slice().sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0));
  if (!notice && !questions.length) notice = t('noPracticeTitle');
  if (!notice && !setPayload.submit_enabled) notice = t('practiceOffTitle');

  if (notice) {
    renderEmpty(element, ctx, title, notice);
    return undefined;
  }

  const setId = setPayload.set.id;
  const supportLang = setPayload.support_language || '';
  let operationId = newOperationId();
  const startedAt = Date.now();
  /* Practice mode (the frame's cuIsPractice): reached from the Reader's practice session. The next
     reading is the server's own choice (GET /api/reading/practice/next); its preview line shows once
     it is known, and nothing is shown when there is none. */
  const practiceMode = ctx.query?.get?.('mode') === 'practice';
  let practice = practiceMode ? { next: null, preview: '' } : null;
  async function loadNextReading() {
    try {
      const value = await api.readingPracticeNext();
      const nextId = value?.available ? value?.next?.article_id : '';
      if (!nextId || nextId === id) return;
      const article = await api.readingArticle(nextId).catch(() => null);
      const minutes = Number.isFinite(article?.reading_time_seconds) && article.reading_time_seconds > 0 ? Math.max(1, Math.round(article.reading_time_seconds / 60)) : 0;
      const title = [article?.title, article?.level, minutes ? t('minutes', { n: minutes }) : ''].filter(Boolean).join(' · ');
      practice = { next: nextId, preview: title ? t('upNext', { title }) : '' };
      if (done) paint();
    } catch {
      /* No next reading known: Next reading ends the session at Reading Complete. */
    }
  }
  if (practiceMode) loadNextReading();

  /* Words the learner kept from this text (the Reader's own "saved from this text" read); unknown
     when the library cannot be read, and then the figure is left out rather than guessed. */
  let keptWords = null; // the words kept from this text, once read
  async function keptFromText() {
    try {
      const doc = await loadReadable({ kind, id }, ctx.context.memory);
      const saved = await loadSavedFromText(doc);
      keptWords = saved ? saved.words : null;
      return saved ? saved.count : null;
    } catch {
      return null;
    }
  }
  const graded = {}; // question id -> grade result
  let index = 0;
  let busy = false;
  let done = false;

  /* The check keeps its place for this visit (LEX-024): "Show in text", practising this text's words or any
     other side trip comes back to the same question, its verdict, or the result - not to question 1. Kept per
     set in the tab's session; Retry clears it. */
  const placeKey = `orena.check.v1:${setId}`;
  const session = (() => {
    try {
      return window.sessionStorage;
    } catch {
      return null;
    }
  })();
  function savePlace() {
    try {
      session?.setItem(placeKey, JSON.stringify({ graded, index, done, operationId, startedAt }));
    } catch {
      /* A session that cannot keep it just starts over next time. */
    }
  }
  (() => {
    try {
      const kept = JSON.parse(session?.getItem(placeKey) || 'null');
      if (!kept || typeof kept !== 'object') return;
      for (const question of questions) if (kept.graded?.[question.id]) graded[question.id] = kept.graded[question.id];
      index = Math.min(Math.max(0, Number(kept.index) || 0), questions.length - 1);
      done = kept.done === true;
      if (kept.operationId) operationId = String(kept.operationId);
    } catch {
      /* Unreadable: start at the first question. */
    }
  })();

  /* The card scrolls in itself (rule 49). A repaint for the same question - grading it - keeps the
     place the learner had scrolled to; the next question starts at the top. */
  let shownIndex = -1;
  function paint() {
    if (!ctx.isCurrent()) return;
    savePlace();
    const previous = element.querySelector('.s-check__card');
    const keep = previous && shownIndex === index ? previous.scrollTop : 0;
    shownIndex = index;
    const question = questions[Math.min(index, questions.length - 1)];
    const meta = [title, done ? t('progressDone') : progressLabel(Math.min(index, questions.length - 1), questions.length, t)].filter(Boolean).join(' · ');
    if (done) {
      const summary = scoreSummary(questions, graded, t);
      // The frame's "Go deeper" row, in its order (cuDeeper).
      const deeper = [
        { key: 'retry', label: t('retryQuestions') },
        // This text's kept words (LEX-024); none kept, nothing of this text to practise, so no chip.
        ...(keptWords?.length ? [{ key: 'words', label: t('practiceVocabulary') }] : []),
        { key: 'rtransfer', label: shellCopy('readingTransfer') },
        { key: 'discussion', label: t('discussThisText') },
        { key: 'respond', label: t('writeResponse') },
      ];
      mount(element, html`<div class="s-check">${headerMarkup(meta)}${progressBarMarkup(progressPercent(questions.length, questions.length))}${doneCardMarkup(summary, deeper, practice)}</div>`);
    } else {
      const pct = progressPercent(index, questions.length);
      mount(element, html`<div class="s-check">${headerMarkup(meta)}${progressBarMarkup(pct)}${activeCardMarkup(question, index, questions.length, graded[question.id], supportLang)}</div>`);
    }
    const card = element.querySelector('.s-check__card');
    if (card) {
      card.scrollTop = keep;
      // A verdict that has just appeared below the fold is brought into view - by scrolling this
      // card only (scrollIntoView would also move the shell's own overflow:hidden column) - as far
      // as shows all of it, or, if it is taller than the card, until its top is at the card's top.
      const verdict = card.querySelector('.s-check__verdict');
      if (verdict) {
        const box = card.getBoundingClientRect();
        const at = verdict.getBoundingClientRect();
        const reveal = at.bottom - box.bottom + 26;
        const room = at.top - box.top - 12;
        card.scrollTop += Math.max(0, Math.min(reveal, room));
      }
    }
    bind();
  }

  async function grade(question, selectedIndex) {
    if (busy || graded[question.id]) return;
    busy = true;
    try {
      const { result } = await api.gradeReadingPracticeQuestion(setId, question.id, selectedIndex);
      if (!ctx.isCurrent()) return;
      graded[question.id] = result;
      paint();
    } catch (error) {
      if (ctx.isCurrent()) toast(error?.message || t('practiceOffTitle'), { iconName: 'circle-alert' });
    } finally {
      busy = false;
    }
  }

  async function advance() {
    if (index + 1 < questions.length) {
      index += 1;
      paint();
      return;
    }
    busy = true;
    let attempt = null;
    try {
      const answers = {};
      for (const question of questions) if (graded[question.id]) answers[question.id] = graded[question.id].selected_index;
      attempt = (await api.submitReadingPractice(setId, operationId, answers))?.attempt || null;
    } catch (error) {
      if (ctx.isCurrent()) toast(error?.message || t('practiceOffTitle'), { iconName: 'circle-alert' });
    } finally {
      busy = false;
    }
    if (!ctx.isCurrent()) return;
    done = true;
    paint();
    /* Only what the server measured (D-098): the committed attempt's own counts. Without an
       attempt (the submit failed) the per-question grades - each answered by the grade endpoint -
       still give correct / answered; the percentage is drawn only from the attempt. */
    const summary = scoreSummary(questions, graded, t);
    const measured = attempt ? { correct: attempt.correct_count, total: attempt.total } : null;
    const answered = questions.filter((question) => graded[question.id]).length;
    const fraction = measured && Number.isInteger(measured.correct) && Number.isInteger(measured.total)
      ? `${measured.correct}/${measured.total}`
      : answered ? `${summary.correctCount}/${answered}` : '';
    /* The frame's three figures, from what was measured (D-130: no XP): the score, the words kept
       from this text, and the minutes this check took. */
    const minutes = Math.max(1, Math.round((Date.now() - startedAt) / 60000));
    const kept = await keptFromText();
    openLessonComplete(ctx, {
      title: shellCopy('checkUnderstanding'),
      measured,
      facts: [
        { label: t('correctLabel'), value: fraction },
        ...(kept == null ? [] : [{ label: t('newWordsLabel'), value: String(kept) }]),
        { label: t('minutesLabel'), value: String(minutes) },
      ],
    });
  }

  function bind() {
    element.querySelector('[data-back]')?.addEventListener('click', () => ctx.back());
    element.querySelectorAll('[data-option]').forEach((button) => {
      button.addEventListener('click', () => {
        const question = questions[index];
        grade(question, Number(button.dataset.option));
      });
    });
    /* "Show in text" opens the Reader at the evidence sentence with its Sentence Quick Sheet, as the
       frame does (cuShowInText). */
    element.querySelector('[data-show-in-text]')?.addEventListener('click', () => {
      const result = graded[questions[index]?.id];
      ctx.go(ctx.href('reader', { id: contentId }, { evidence: result?.evidence_fragment || '' }));
    });
    element.querySelector('[data-next]')?.addEventListener('click', () => advance());
    // Continue ends the check where the frame does (cuContinue): Reading Complete, or in practice the
    // next reading.
    element.querySelector('[data-continue]')?.addEventListener('click', () => {
      if (practice?.next) ctx.go(ctx.href('reader', { id: `article:${practice.next}` }, { mode: 'practice' }));
      else ctx.go(ctx.href('rcomplete', { id: contentId }));
    });
    element.querySelector('[data-exit-practice]')?.addEventListener('click', () => ctx.go(ctx.href('practice')));
    element.querySelectorAll('[data-deeper]').forEach((button) => {
      button.addEventListener('click', () => {
        const key = button.dataset.deeper;
        if (key === 'retry') {
          // The same set again, from its first question, as a new attempt.
          for (const question of questions) delete graded[question.id];
          index = 0;
          done = false;
          operationId = newOperationId();
          paint();
        } else if (key === 'words') ctx.go(ctx.href('review', {}, { words: keptWords.join(',') }));
        else ctx.go(ctx.href(key, { id: contentId }));
      });
    });
  }

  paint();
  // The result's "Practice vocabulary" names this text's kept words; read them once, then redraw if it shows.
  keptFromText().then(() => {
    if (done && keptWords?.length && ctx.isCurrent()) paint();
  });
  return undefined;
}
