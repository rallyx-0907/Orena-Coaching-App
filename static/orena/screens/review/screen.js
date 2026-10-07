/* Review Session (frame 13, `#/review`; D-091). A spaced-repetition drill over the learner's real
   due vocabulary: `GET /api/library/vocabulary?status=due&order=due` by default, one word when
   `?word=` names it (a forced single-card session), or a curated collection's own saved words when
   `?collection=` names one (Collection Detail's "Start review"). `route.focus` + `route.lesson`
   (shell/routes.js): the router paints the loading skeleton while this awaits and the load-error
   state if it throws, so this never paints its own.

   The revealed card is the same Word Card content Word Detail draws (D7 §4: "byte-identical inner
   content, only the outer wrapper differs") - this screen's own `model.js#reviewCard` wraps
   `screens/word/model.js#mapWordCard` (and backfills a real catalogue meaning/example when the
   saved item's own fields are empty - see that function's header), reuses its save/restore payload
   helpers directly rather than re-deriving the shape, and reuses
   `screens/word/stroke-sheet.js#mountStrokeSheet` for "Practise strokes", exactly as Word Detail and
   the Wave B overlays already do. "Mark known" is not built here either, for the same reason Word
   Detail leaves it out (no real backend action - see that screen's own header). */
import { html, mount, raw, cls } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { emptyMarkup } from '../../kit/states.js';
import { toast } from '../../kit/toast.js';
import { openSheet } from '../../kit/overlay.js';
import { openLessonComplete } from '../lesson-complete/sheet.js';
import { masteryBars } from '../../kit/components.js';
import { langAttr } from '../../kit/lang.js';
import { shellCopy } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { meaningLanguageLabel } from '../../product/vocabulary-meaning.js';
import { api } from '../../infrastructure/api.js';
import { readCollection } from '../collection/actions.js';
import { flushQueue, withWaiting } from '../../product/review-queue.js';
import { t } from './copy.js';
import {
  cardLanguage,
  posLabel,
  restorePayload,
  savePayload,
} from '../word/model.js';
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
  reviewCard,
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

function posMarkup(pos) {
  if (!pos) return '';
  const label = posLabel(pos, t);
  return html`<span class="o-tag"${label.known ? '' : raw(` lang="${langAttr('en')}"`)}>${label.text}</span>`;
}

/* `n of total · mode`, the eyebrow the frame draws on the card in both of its states. */
function eyebrowOf(row, counts) {
  return `${t('progress', counts)} · ${t(cardMode(row) === 'cloze' ? 'modeCloze' : 'modeTarget')}`;
}

/* The revealed card: the eyebrow, then the same content Word Detail draws (D7 §4), review-scoped
   classes. The scroll region is the card's own, so a long definition or example scrolls in the card
   and the grades below it stay in view (rule 49). */
function wordCardMarkup(card, eyebrow) {
  const cardLang = cardLanguage(card.script);
  const meta = [
    card.ipa ? html`<span class="s-review-card__ipa">${card.ipa}</span>` : '',
    posMarkup(card.pos),
    card.hasLevel ? html`<span class="o-tag s-review-card__level">${card.level}</span>` : '',
  ];
  const footer = [];
  if (card.hasSchedule) {
    footer.push(html`<span class="s-review-card__bars">${masteryBars({ filled: card.filled, total: 4 })}</span>`);
    if (card.stageKey) footer.push(html`<span class="s-review-card__stage">${t(card.stageKey)}</span>`);
    if (card.due) footer.push(html`<span class="s-review-card__due">· ${card.due.key === 'dueToday' ? t('dueToday') : t.plural('dueInDays', card.due.n)}</span>`);
  }
  return html`<div class="s-review-face s-review-face--revealed">
    <span class="s-review-face__blob" aria-hidden="true"></span>
    <div class="s-review-face__scroll" data-scroll-region>
    <span class="s-review-eyebrow">${eyebrow}</span>
    <div class="s-review-card">
    <div class="s-review-card__top">
      <div class="s-review-card__id">
        <div class="s-review-card__word" lang="${langAttr(cardLang)}">${card.word}</div>
        <div class="s-review-card__meta">${meta}</div>
      </div>
      <div class="s-review-card__actions">
        <button type="button" class="s-review-icon s-review-icon--play" data-play aria-label="${t('playWord')}">${raw(icon('volume-2', { size: 19 }))}</button>
        <button type="button" class="s-review-icon" data-save style="background:${card.savedBg};color:${card.savedColor}" aria-label="${t(card.saved ? 'unsaveWord' : 'saveWord')}" aria-pressed="${card.saved ? 'true' : 'false'}">${raw(icon('bookmark-check', { size: 19 }))}</button>
      </div>
    </div>
    ${card.hasMeaning ? html`<div class="s-review-card__meaning"><div class="s-review-card__meaning-text">${card.meaning}${meaningTag(card.meaningLanguage)}</div>${card.hasSupport ? html`<div class="s-review-card__support">${card.support}</div>` : ''}</div>` : ''}
    ${card.hasExample ? html`<div class="s-review-card__example" lang="${langAttr(cardLang)}">“${card.exampleParts.map((part) => html`<span class="${cls(part.hit && 's-review-card__hit')}">${part.value}</span>`)}”</div>` : ''}
    ${card.script === 'hanzi' ? strokesMarkup({ word: card.word, prefix: 's-review', label: t('strokeOrder'), buttonLabel: t('practiseStrokes'), buttonAttr: 'data-practise-strokes', buttonClass: 's-review-strokes-btn' }) : ''}
    ${footer.length ? html`<div class="s-review-card__footer">${footer}</div>` : ''}
    </div>
    </div>
  </div>`;
}

/* The frame's hidden face (`rvHidden`): `n of total · mode`, the prompt, a cue line, the hint once
   asked for, and "Tap to reveal". Target -> meaning asks the word and cues it with its reading and
   part of speech; a source-aware card asks the sentence the learner met the word in, the word taken
   out, and cues it with where the sentence came from (model.js#cardMode). */
function hiddenFaceMarkup(card, row, counts, hintOn) {
  const cloze = cardMode(row) === 'cloze' ? clozeFor(row) : null;
  const lang = langAttr(cardLanguage(card.script));
  const sourceKey = cloze ? sourceLabelKey(row.source_kind) : '';
  const cue = cloze
    ? [t('cueCloze'), sourceKey ? t(sourceKey) : ''].filter(Boolean).join(' · ')
    : [card.ipa, card.pos ? posLabel(card.pos, t).text : ''].filter(Boolean).join(' · ');
  const hint = hintOn ? hintFor(cloze ? 'cloze' : 'typing', card) : '';
  const promptText = cloze ? cloze.text : card.word;
  const size = promptText.length > 220 ? ' s-review-prompt--longest' : promptText.length > 90 ? ' s-review-prompt--long' : '';
  return html`<button type="button" class="s-review-face s-review-face--hidden" data-card-tap>
    <span class="s-review-face__blob" aria-hidden="true"></span>
    <span class="s-review-eyebrow">${eyebrowOf(row, counts)}</span>
    <span class="s-review-prompt${size}" lang="${lang}"${cloze ? raw(' data-scroll-region') : ''}>${cloze ? cloze.parts.map((part) => (part.blank ? html`<span class="s-review-blank">${part.value}</span>` : part.value)) : promptText}</span>
    ${cue ? html`<span class="s-review-cue">${cue}</span>` : ''}
    ${hint ? html`<span class="s-review-hint"${cloze ? raw(` lang="${lang}"`) : ''}>${hint}</span>` : ''}
    <span class="s-review-affordance">${raw(icon('eye', { size: 16 }))}${t('tapToReveal')}</span>
  </button>`;
}

const GRADE_CSS_SUFFIX = { again: 'again', unsure: 'unsure', got_it: 'gotit' };

function gradeButton(grade, key, schedule) {
  const label = scheduleLabel(schedule, grade, t);
  return html`<button type="button" class="s-review-grade s-review-grade--${GRADE_CSS_SUFFIX[grade]}" data-grade="${grade}">
    <span>${t(key)}</span>${label ? html`<b>${label}</b>` : ''}
  </button>`;
}

function statTile(key, n, tone) {
  return html`<div class="s-review-stat"><div class="s-review-stat__n s-review-stat__n--${tone}">${n}</div><div class="s-review-stat__label">${t(key)}</div></div>`;
}

export default async function mountReview(element, ctx) {
  await useStyles('screens/review/review.css');
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

  const state = { index: 0, revealed: false, hintOn: false, stats: initialStats(), grading: false, unsaved: new Set(), nextTimes: [] };
  let audio = null;

  function currentRow() {
    return queue[state.index] || null;
  }

  function reset() {
    state.index = 0;
    state.revealed = false;
    state.hintOn = false;
    state.stats = initialStats();
    state.unsaved = new Set();
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
  function finishSession() {
    const given = state.stats.again + state.stats.unsure + state.stats.got_it;
    if (!given) return;
    const next = nextDueLabel(state.nextTimes, Date.now(), t);
    setTimeout(() => {
      if (!ctx.isCurrent()) return;
      openLessonComplete(ctx, {
        title: shellCopy('review'),
        measured: { correct: state.stats.got_it, total: given },
        facts: [
          { label: t.plural('lessonCards', given), value: given },
          { label: t('statGotIt'), value: state.stats.got_it },
          { label: t('statUnsure'), value: state.stats.unsure },
          { label: t('statAgain'), value: state.stats.again },
          { label: t('lessonNext'), value: next },
        ],
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
            ${statTile('statUnsure', state.stats.unsure, 'unsure')}
            ${statTile('statAgain', state.stats.again, 'again')}
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
      element.querySelector('[data-to-library]').addEventListener('click', () => ctx.go(ctx.href('library')));
      return;
    }

    const row = currentRow();
    const card = reviewCard(row.word, state.unsaved.has(state.index) ? null : row, support);
    const canHint = Boolean(hintFor(cardMode(row), card));

    mount(
      element,
      html`${header}${bar}
      <div class="s-review-body">
        <div class="s-review-stack">
          <div class="s-review-stack__back" aria-hidden="true"></div>
          ${state.revealed ? wordCardMarkup(card, eyebrowOf(row, counts)) : hiddenFaceMarkup(card, row, counts, state.hintOn)}
        </div>
        ${
          state.revealed
            ? html`<div class="s-review-grades">${gradeButton('again', 'gradeAgain', row.schedule)}${gradeButton('unsure', 'gradeUnsure', row.schedule)}${gradeButton('got_it', 'gradeGotIt', row.schedule)}</div>`
            : html`<div class="s-review-hidden-actions">
                ${canHint ? html`<button type="button" class="s-review-btn s-review-btn--secondary" data-hint>${t('hintLabel')}</button>` : ''}
                <button type="button" class="s-review-btn s-review-btn--primary" data-reveal>${t('revealLabel')}</button>
              </div>`
        }
      </div>`,
    );
    bindHeader();

    if (!state.revealed) {
      element.querySelector('[data-card-tap]')?.addEventListener('click', () => {
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

    element.querySelector('[data-play]')?.addEventListener('click', async () => {
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
    });

    element.querySelector('[data-save]')?.addEventListener('click', async () => {
      const button = element.querySelector('[data-save]');
      const savedIndex = state.index;
      button.disabled = true;
      try {
        if (card.saved) {
          const payload = restorePayload(row);
          await api.deleteLibraryVocabulary(row.word);
          state.unsaved.add(savedIndex);
          toast(
            t('removedToast'),
            payload
              ? {
                  undo: async () => {
                    const restored = await api.restoreLibraryVocabulary(payload).catch(() => null);
                    if (restored?.item) queue[savedIndex] = restored.item;
                    state.unsaved.delete(savedIndex);
                    paint();
                  },
                  undoLabel: shellCopy('undo'),
                }
              : {},
          );
        } else {
          const saved = await api.saveLibraryVocabulary(savePayload(card)).catch(() => null);
          if (saved?.item) queue[savedIndex] = saved.item;
          state.unsaved.delete(savedIndex);
          toast(t('savedToast'));
        }
      } finally {
        paint();
      }
    });

    element.querySelector('[data-practise-strokes]')?.addEventListener('click', async () => {
      // The sheet's own rules (.s-word-*) live in word.css, which only the Word screen loads (V-09).
      await useStyles('screens/word/word.css');
      const titleWord = card.ipa ? `${card.word} · ${card.ipa}` : card.word;
      openSheet({
        label: t('strokePracticeTitle', { word: titleWord }),
        render: (sheetEl, handle) =>
          mountStrokeSheet(sheetEl, handle, {
            word: card.word,
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
