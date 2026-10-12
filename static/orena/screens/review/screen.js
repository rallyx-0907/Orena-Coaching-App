/* Review Session (frame 13, `#/review`; D-091). A spaced-repetition drill over the learner's real
   due vocabulary: `GET /api/library/vocabulary?status=due&order=due` by default, one word when
   `?word=` names it (a forced single-card session), or a curated collection's own saved words when
   `?collection=` names one (Collection Detail's "Start review"). `route.focus` + `route.lesson`
   (shell/routes.js): the router paints the loading skeleton while this awaits and the load-error
   state if it throws, so this never paints its own.

   Both faces are the shared VocabularyCard (kit/vocabulary-card.js, D-17W): `review-front` asks the
   word - its reading, part of speech, level and audio, nothing that answers it - and Reveal turns it
   to `review-back`, the same content Word Detail draws (D7 §4), from the same pure mapper
   (product/vocabulary-card.js). Two grades: "Not yet" (`again`) and "Got it" (`got_it`); `unsure`
   stays in the API and is not drawn. Only saved words are ever in the queue. It reuses
   `screens/word/stroke-sheet.js#mountStrokeSheet` for "Practise strokes", exactly as Word Detail and
   the Wave B overlays already do. "Mark known" is not built here either, for the same reason Word
   Detail leaves it out (no real backend action - see that screen's own header). */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { emptyMarkup } from '../../kit/states.js';
import { toast } from '../../kit/toast.js';
import { openSheet } from '../../kit/overlay.js';
import { openLessonComplete } from '../lesson-complete/sheet.js';
import { langAttr } from '../../kit/lang.js';
import { vocabularyCard, bindVocabularyCards } from '../../kit/vocabulary-card.js';
import { toVocabularyModel, learnerState } from '../../product/vocabulary-card.js';
import { shellCopy } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { meaningLanguageLabel } from '../../product/vocabulary-meaning.js';
import { api } from '../../infrastructure/api.js';
import { readCollection } from '../collection/actions.js';
import { flushQueue, withWaiting } from '../../product/review-queue.js';
import { t } from './copy.js';
import { stageCopyKey } from '../word/model.js';
import { mountStrokeSheet } from '../word/stroke-sheet.js';
import { strokesMarkup, hydrateStrokes } from './strokes.js';
import {
  filterByWordSet,
  queueScope,
  buildQueue,
  progressCounts,
  progressPercent,
  scheduleLabel,
  initialStats,
  tally,
  REVIEW_BUTTONS,
  cardMode,
  clozeFor,
  hintFor,
  sourceLabelKey,
  gradeOutcome,
  countsForSession,
  nextDueLabel,
} from './model.js';

/* The kit's small tag naming a meaning's language when it is not the support language (D-124). */
function meaningTag(language) {
  const label = meaningLanguageLabel(language, languages().support, languages().ui);
  return label ? html` <span class="o-tag">${label}</span>` : '';
}

/* The task the card asks, in plain words. The position in the session is shown once, in the header (LEX-064). */
function eyebrowOf(row) {
  return t(cardMode(row) === 'cloze' ? 'modeCloze' : 'modeTarget');
}

/* The revealed face: the two-face card (`review-back`, no Save). Each face scrolls inside its own body
   and keeps its turn action in view; the grades are below the card, outside it (rule 49). */
function backFaceMarkup(model, learner, row) {
  const stageKey = stageCopyKey(learner.saved ? row : null);
  const footer = {
    stage: stageKey ? t(stageKey) : '',
    due: learner.due ? (learner.due.key === 'dueToday' ? t('dueToday') : t.plural('dueInDays', learner.due.n)) : '',
  };
  const strokes = model.script === 'hanzi'
    ? strokesMarkup({ word: model.word, prefix: 's-review', label: t('strokeOrder'), buttonLabel: t('practiseStrokes'), buttonAttr: 'data-practise-strokes', buttonClass: 's-review-strokes-btn' })
    : '';
  // No corner disc here: every corner of the turned card holds text or a control (UI_BACKEND_GAPS VC-12).
  return html`<div class="s-review-face s-review-face--revealed">
    ${vocabularyCard(model, { mode: 'review-back', learner, slots: { strokes, footer, meaningTag } })}
  </div>`;
}

/* The hidden face (`rvHidden`). Target -> meaning: the card's `review-front` - the word, its reading,
   part of speech, level and audio; nothing that answers it. A source-aware card asks the sentence the
   learner met the word in, the word taken out, cued with where it came from (model.js#cardMode) - no
   audio there, which would say the answer. Tapping the face (not one of its buttons) reveals. */
function hiddenFaceMarkup(model, row, hintOn) {
  const cloze = cardMode(row) === 'cloze' ? clozeFor(row) : null;
  const lang = langAttr(model.language);
  const hint = hintOn ? hintFor(cloze ? 'cloze' : 'typing', { word: model.word, support: model.support }) : '';
  if (!cloze) {
    return html`<div class="s-review-face s-review-face--hidden" data-card-tap>
      <span class="s-review-face__blob" aria-hidden="true"></span>
      <span class="s-review-eyebrow">${eyebrowOf(row)}</span>
      ${vocabularyCard(model, { mode: 'review-front' })}
      ${hint ? html`<span class="s-review-hint">${hint}</span>` : ''}
    </div>`;
  }
  const sourceKey = sourceLabelKey(row.source_kind);
  const size = cloze.text.length > 220 ? ' s-review-prompt--longest' : cloze.text.length > 90 ? ' s-review-prompt--long' : '';
  return html`<div class="s-review-face s-review-face--hidden" data-card-tap>
    <span class="s-review-face__blob" aria-hidden="true"></span>
    <span class="s-review-eyebrow">${eyebrowOf(row)}</span>
    <span class="s-review-prompt${size}" lang="${lang}" data-scroll-region>${cloze.parts.map((part) => (part.blank ? html`<span class="s-review-blank">${part.value}</span>` : part.value))}</span>
    ${sourceKey ? html`<span class="s-review-cue">${t(sourceKey)}</span>` : ''}
    ${hint ? html`<span class="s-review-hint" lang="${lang}">${hint}</span>` : ''}
  </div>`;
}

const GRADE_COPY = { again: 'gradeNotYet', got_it: 'gradeGotIt' };
const GRADE_CSS_SUFFIX = { again: 'again', got_it: 'gotit' };

function gradeButton(grade, schedule) {
  const label = scheduleLabel(schedule, grade, t);
  return html`<button type="button" class="s-review-grade s-review-grade--${GRADE_CSS_SUFFIX[grade]}" data-grade="${grade}">
    <span>${t(GRADE_COPY[grade])}</span>${label ? html`<b>${label}</b>` : ''}
  </button>`;
}

function statTile(key, n, tone) {
  return html`<div class="s-review-stat"><div class="s-review-stat__n s-review-stat__n--${tone}">${n}</div><div class="s-review-stat__label">${t(key)}</div></div>`;
}

export default async function mountReview(element, ctx) {
  await Promise.all([useStyles('screens/review/review.css'), useStyles('kit/vocabulary-card.css')]);
  element.classList.add('s-review-root');

  const support = languages().support;
  const scope = queueScope(ctx.query || {});

  /* Answers given with no network wait in the device's review queue (`product/review-queue.js`,
     `memory.reviewQueue`) and go up, oldest first, as soon as there is a connection - so the queue
     below is read after what is waiting has been sent, and a word the learner already graded is not
     asked twice. */
  const memory = ctx.context?.memory || null;
  let waiting = [...(memory?.value?.reviewQueue || [])];
  let draining = false;

  async function drain() {
    if (draining || !waiting.length) return;
    draining = true;
    const sent = waiting;
    try {
      const left = await flushQueue(sent, (item) => api.reviewLibraryVocabulary(item.word, item.grade));
      waiting = [...left, ...waiting.slice(sent.length)];
      memory?.setReviewQueue?.(waiting);
    } finally {
      draining = false;
    }
  }

  if (waiting.length && navigator.onLine !== false) await drain().catch(() => {});
  if (!ctx.isCurrent()) return undefined;

  let queue;
  if (scope.mode === 'word') {
    const page = await api.libraryVocabulary({ query: scope.word, limit: 5, order: 'word' }).catch(() => null);
    const target = String(scope.word).trim().toLowerCase();
    const row = (page?.items || []).find((r) => String(r.word || '').trim().toLowerCase() === target);
    queue = buildQueue(row ? [row] : []);
  } else if (scope.mode === 'words') {
    const page = await api.libraryVocabulary({ limit: 100, order: 'recent' }).catch(() => null);
    queue = buildQueue(filterByWordSet(page?.items, new Set(scope.words)));
  } else if (scope.mode === 'collection') {
    const collectionPayload = await readCollection(scope.collection,
      api.vocabularyLibraryCollection, { includeReview: true });
    if (collectionPayload.language_code !== ctx.context.language) throw new Error('Collection language changed');
    queue = buildQueue(collectionPayload.review_items);
  } else {
    const page = await api.libraryVocabulary({ status: 'due', order: 'due', limit: 50 }).catch(() => null);
    queue = buildQueue(page?.items);
  }
  if (!ctx.isCurrent()) return undefined;

  const state = { index: 0, revealed: false, hintOn: false, stats: initialStats(), grading: false, nextTimes: [] };
  let audio = null;

  function currentRow() {
    return queue[state.index] || null;
  }

  function reset() {
    state.index = 0;
    state.revealed = false;
    state.hintOn = false;
    state.stats = initialStats();
    state.nextTimes = [];
  }

  /* One place a grade goes. The outcome (model.js#gradeOutcome) says whether it counts toward the
     summary and what, if anything, the learner is told. */
  async function submitGrade(word, grade) {
    let result = null;
    let error = null;
    try {
      result = await api.reviewLibraryVocabulary(word, grade);
    } catch (caught) {
      error = caught;
    }
    const outcome = gradeOutcome({ result, error });
    if (outcome === 'saved' && result?.item?.next_review_at) state.nextTimes.push(result.item.next_review_at);
    if (outcome === 'kept') {
      waiting = withWaiting(waiting, word, grade, new Date().toISOString());
      memory?.setReviewQueue?.(waiting);
    } else if (outcome === 'saved' && waiting.length) {
      drain().catch(() => {});
    }
    return outcome;
  }

  /* The design's Lesson complete modal after the last grade (V-04, HV-2 B), with measured facts only: the cards
     reviewed, how each was graded, when the soonest comes back, and the Got it share. No XP, no minutes. */
  /* Continue: the next batch when more cards are due, else back where the session began (LEX-065). A cleared
     due list returns to Library's Due Review; a collection or a single word returns to its own page. */
  async function continueAfter() {
    if (scope.mode === 'due') {
      const page = await api.libraryVocabulary({ status: 'due', order: 'due', limit: 50 }).catch(() => null);
      if (!ctx.isCurrent()) return;
      const more = buildQueue(page?.items);
      if (more.length) {
        reset();
        queue = more;
        paint();
        return;
      }
      ctx.go(ctx.href('library', {}, { tab: 'due' }));
    } else {
      ctx.back();
    }
  }

  function finishSession() {
    const given = state.stats.again + state.stats.unsure + state.stats.got_it;
    if (!given) return;
    const next = nextDueLabel(state.nextTimes, Date.now(), t);
    setTimeout(() => {
      if (!ctx.isCurrent()) return;
      openLessonComplete(ctx, {
        title: shellCopy('review'),
        measured: { correct: state.stats.got_it, total: given },
        // The page behind carries the Got it / Unsure / Again tiles; the sheet says what was done and what is next.
        facts: [
          { label: t.plural('lessonCards', given), value: given },
          { label: t('statGotIt'), value: state.stats.got_it },
          { label: t('lessonNext'), value: next },
        ],
        next: continueAfter,
      });
    }, 350);
  }

  function paint() {
    const total = queue.length;
    const counts = progressCounts(state.index, total);
    const header = html`<div class="s-review-head">
      <button type="button" class="o-iconbtn o-iconbtn--back" data-back aria-label="${shellCopy('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
      <div class="s-review-head__title">
        <div class="s-review-head__name">${shellCopy('review')}</div>
        ${counts ? html`<div class="s-review-head__sub">${t('progress', counts)}</div>` : ''}
      </div>
    </div>`;
    const bar = html`<div class="s-review-bar"><span style="width:${progressPercent(state.index, total)}%"></span></div>`;

    if (!total) {
      mount(element, html`${header}${emptyMarkup({ text: t('emptyTitle'), iconName: 'circle-check' })}`);
      bindHeader();
      return;
    }

    if (state.index >= total) {
      mount(
        element,
        html`${header}${bar}
        <div class="s-review-done">
          <span class="s-review-done__blob s-review-done__blob--a" aria-hidden="true"></span>
          <span class="s-review-done__blob s-review-done__blob--b" aria-hidden="true"></span>
          <div class="s-review-eyebrow">${t('sessionCompleteTitle')}</div>
          <div class="s-review-stats">
            ${statTile('statGotIt', state.stats.got_it, 'good')}
            ${statTile('statNotYet', state.stats.again, 'again')}
          </div>
          <div class="s-review-done__actions">
            <button type="button" class="o-btn o-btn--secondary" data-restart>${t('reviewAgainAction')}</button>
            <button type="button" class="o-btn o-btn--primary" data-to-library>${t('backToLibrary')}</button>
          </div>
        </div>`,
      );
      bindHeader();
      element.querySelector('[data-restart]').addEventListener('click', async () => {
        reset();
        if (scope.mode === 'due') {
          const page = await api.libraryVocabulary({ status: 'due', order: 'due', limit: 50 }).catch(() => null);
          if (!ctx.isCurrent()) return;
          queue = buildQueue(page?.items);
        }
        paint();
      });
      element.querySelector('[data-to-library]').addEventListener('click', () => ctx.go(ctx.href('library', {}, { tab: 'due' })));
      return;
    }

    const row = currentRow();
    const model = toVocabularyModel(row, { word: row.word, supportLanguage: support });
    const learner = learnerState(row);
    const canHint = Boolean(hintFor(cardMode(row), { word: model.word, support: model.support }));

    mount(
      element,
      html`${header}${bar}
      <div class="s-review-body">
        <div class="s-review-stack">
          <div class="s-review-stack__back" aria-hidden="true"></div>
          ${state.revealed ? backFaceMarkup(model, learner, row) : hiddenFaceMarkup(model, row, state.hintOn)}
        </div>
        ${
          state.revealed
            ? html`<div class="s-review-grades">${REVIEW_BUTTONS.map((grade) => gradeButton(grade, row.schedule))}</div>`
            : html`<div class="s-review-hidden-actions">
                ${canHint ? html`<button type="button" class="s-review-btn s-review-btn--secondary" data-hint>${t('hintLabel')}</button>` : ''}
                <button type="button" class="s-review-btn s-review-btn--primary" data-reveal>${t('revealLabel')}</button>
              </div>`
        }
      </div>`,
    );
    bindHeader();

    async function play() {
      try {
        const info = await api.wordAudio(row.word);
        if (info?.available && info.url) {
          audio?.pause();
          audio = new Audio(info.url);
          audio.play().catch(() => {});
        } else {
          toast(t('noAudio'));
        }
      } catch {
        toast(t('noAudio'));
      }
    }
    element.querySelectorAll('[data-play]').forEach((button) => button.addEventListener('click', (event) => {
      event.stopPropagation();
      play();
    }));
    bindVocabularyCards(element);

    if (!state.revealed) {
      element.querySelector('[data-card-tap]')?.addEventListener('click', (event) => {
        if (event.target.closest('button')) return;
        state.revealed = true;
        paint();
      });
      element.querySelector('[data-hint]')?.addEventListener('click', () => {
        state.hintOn = true;
        paint();
      });
      element.querySelector('[data-reveal]')?.addEventListener('click', () => {
        state.revealed = true;
        paint();
      });
      return;
    }

    hydrateStrokes(element, api.chineseStrokeOrder, ctx.isCurrent).catch(() => {});

    element.querySelectorAll('[data-grade]').forEach((button) => {
      button.addEventListener('click', async () => {
        if (state.grading) return;
        state.grading = true;
        const grade = button.dataset.grade;
        const outcome = await submitGrade(row.word, grade);
        if (!ctx.isCurrent() || outcome === 'aborted') return;
        if (countsForSession(outcome)) state.stats = tally(state.stats, grade);
        if (outcome === 'kept') toast(t('reviewKept'));
        else if (outcome === 'failed' || outcome === 'missing') toast(t('reviewSaveFailed'));
        state.index += 1;
        state.revealed = false;
        state.hintOn = false;
        state.grading = false;
        paint();
        if (state.index >= total) finishSession();
      });
    });

    element.querySelector('[data-practise-strokes]')?.addEventListener('click', async () => {
      // The sheet's own rules (.s-word-*) live in word.css, which only the Word screen loads (V-09).
      await useStyles('screens/word/word.css');
      const titleWord = model.pronunciation.text ? `${model.word} · ${model.pronunciation.text}` : model.word;
      openSheet({
        label: t('strokePracticeTitle', { word: titleWord }),
        render: (sheetEl, handle) =>
          mountStrokeSheet(sheetEl, handle, {
            word: model.word,
            titleWord,
            chineseStrokeOrder: api.chineseStrokeOrder,
            t,
            closeLabel: shellCopy('close'),
          }),
      });
    });
  }

  function bindHeader() {
    element.querySelector('[data-back]').addEventListener('click', () => ctx.back());
  }

  const onOnline = () => {
    drain().catch(() => {});
  };
  window.addEventListener('online', onOnline);

  paint();

  return () => {
    window.removeEventListener('online', onOnline);
    audio?.pause();
  };
}
