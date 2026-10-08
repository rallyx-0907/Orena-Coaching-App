/* From Your Errors (frame 50, `#/from-your-errors`; D-091). Real evidence only: targeted-practice outcomes AND the learner's own reviews
   (2026-09-28 human decision: Grammar Lab, not R5, owns grammar content - this screen reads no
   `/api/library/grammar*`/`/api/grammar/*` route). Each drill item is the learner's own flagged
   sentence from a targeted Writing practice attempt (`GET /api/practice-outcomes`) joined with that
   essay's real correction and explanation (`GET /api/essays/{id}`'s `issues[]`) - see
   `screens/errors/model.js`'s header for exactly how, and why a fragment with no real match never
   becomes a drill card.

   The frame's states, as drawn: a sentence to edit (Show answer / Check), the result of a check or
   of asking for the answer (the sentence as it was, the correction, why; Try again unless the answer
   was shown; Next sentence / See results), and the finished drill (score, one row per sentence,
   Run again / Finish). The card's body is its own scroll region so a long sentence or explanation
   scrolls inside the card and the buttons stay in view (rule 49). */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { emptyMarkup } from '../../kit/states.js';
import { shellCopy } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { langAttr } from '../../kit/lang.js';
import { api } from '../../infrastructure/api.js';
import { t } from './copy.js';
import { t as writingCopy } from '../writing/copy.js';
import {
  outcomesWithIssues,
  essayIdsOf,
  buildDrillItems,
  buildEssayDrillItems,
  mergeDrillItems,
  isCorrect,
  initialResults,
  recordCheck,
  recordReveal,
  score,
  summaryRows,
} from './model.js';

function dateLabel(iso) {
  const parsed = Date.parse(iso);
  if (!Number.isFinite(parsed)) return '';
  return new Date(parsed).toLocaleDateString(languages().ui);
}

/* The result box's three looks (`efRes`): the correction shown on request, right, not yet. */
const RESULT_LOOK = {
  shown: { key: 'resultRevealed', tone: 'amber' },
  ok: { key: 'resultCorrect', tone: 'green' },
  bad: { key: 'resultIncorrect', tone: 'red' },
};

/* The summary row's dot (`efRows`): green cleared, amber fixed after a retry, red keep practising. */
const ROW_LOOK = {
  cleared: { tone: 'green', glyph: '✓', key: 'stateCleared' },
  later: { tone: 'amber', glyph: '✓', key: 'stateLater' },
  keep: { tone: 'red', glyph: '!', key: 'stateKeep' },
};

export default async function mountErrors(element, ctx) {
  await useStyles('screens/errors/errors.css');
  element.classList.add('s-errors-root');

  const outcomesPayload = await api.practiceOutcomes(20).catch(() => null);
  if (!ctx.isCurrent()) return undefined;
  if (outcomesPayload === null) throw new Error('writing_history_unavailable');
  const outcomes = outcomesWithIssues(outcomesPayload, 10);
  const essayIds = essayIdsOf(outcomes);
  const readEssay = id => api.essay(id).catch(error => {
    if (error.status === 404 || error.status === 410) return null;
    throw error;
  });
  const essays = await Promise.all(essayIds.map(readEssay));
  if (!ctx.isCurrent()) return undefined;
  const issuesByEssay = {};
  essayIds.forEach((id, i) => {
    issuesByEssay[id] = Array.isArray(essays[i]?.issues) ? essays[i].issues : [];
  });
  const fromOutcomes = buildDrillItems(outcomes, issuesByEssay);
  /* The learner's own recent reviews, newest first: a review with fixes is a source of drills even when no targeted
     practice was run on it. Only essays in the language being learned. */
  const reviewed = await api.essays().catch(() => null);
  if (!ctx.isCurrent()) return undefined;
  if (reviewed === null) throw new Error('writing_history_unavailable');
  const recent = (Array.isArray(reviewed) ? reviewed : [])
    .filter((row) => row && row.overall != null && (!row.language_code || row.language_code === (ctx.context?.language || 'en')))
    .slice(0, 6);
  const recentEssays = (await Promise.all(recent.map((row) => (essays.find((e) => e && Number(e.id) === Number(row.id)) ? essays.find((e) => e && Number(e.id) === Number(row.id)) : readEssay(row.id))))).filter(Boolean);
  if (!ctx.isCurrent()) return undefined;
  const label = (category) => {
    const key = `cat_${category}`;
    return writingCopy.has?.(key) ? writingCopy(key) : category.replace(/_/g, ' ');
  };
  const items = mergeDrillItems(fromOutcomes, buildEssayDrillItems(recentEssays, { labelOf: label }));
  const essayLanguage = new Map([...essays, ...recentEssays].filter(Boolean).map((e) => [Number(e.id), e.language_code]));
  /* The learner's Writing is in the language they are learning; each sentence is marked with the
     language its essay declares (`GET /api/essays/{id}` `language_code`), else the active one. */
  const languageOf = (item) => langAttr(essayLanguage.get(item.essayId) || item.language || ctx.context?.language || 'en');

  const state = { index: 0, text: items[0]?.bad || '', result: null, wrongBefore: 0, results: initialResults(items) };

  function header(progress) {
    return html`<div class="s-errors-head">
      <button type="button" class="s-errors-back" data-back aria-label="${shellCopy('back')}">${raw(icon('arrow-left', { size: 19 }))}</button>
      <div class="s-errors-head__title">
        <div class="s-errors-head__name">${shellCopy('fromYourErrors')}</div>
        ${progress ? html`<div class="s-errors-head__sub">${progress}</div>` : ''}
      </div>
    </div>`;
  }

  function begin(index) {
    state.index = index;
    state.text = items[index]?.bad || '';
    state.result = null;
    state.wrongBefore = 0;
  }

  function paint() {
    const total = items.length;

    if (!total) {
      mount(element, html`${header('')}${emptyMarkup({ text: t('emptyTitle'), iconName: 'target' })}`);
      bindHeader();
      return;
    }

    if (state.index >= total) {
      const tally = score(state.results);
      const rows = summaryRows(items, state.results);
      mount(
        element,
        html`${header(t('done'))}
        <div class="s-errors-done">
          <div class="s-errors-eyebrow">${t('drillComplete')}</div>
          <div class="s-errors-score">${t('scoreLine', { firstTry: tally.firstTry, total: tally.total })}</div>
          <div class="s-errors-rows" data-scroll-region>
            ${rows.map((row) => {
              const look = ROW_LOOK[row.state];
              return html`<div class="s-errors-row">
                <span class="s-errors-row__dot s-errors-row__dot--${look.tone}" aria-hidden="true">${look.glyph}</span>
                <span class="s-errors-row__pattern">${row.pattern}</span>
                <span class="s-errors-row__state">${t(look.key)}</span>
              </div>`;
            })}
          </div>
          <div class="s-errors-actions">
            <button type="button" class="s-errors-btn s-errors-btn--secondary" data-restart>${t('runAgain')}</button>
            <span class="s-errors-spacer"></span>
            <button type="button" class="s-errors-btn s-errors-btn--primary" data-finish>${t('finish')}</button>
          </div>
        </div>`,
      );
      bindHeader();
      element.querySelector('[data-restart]').addEventListener('click', () => {
        state.results = initialResults(items);
        begin(0);
        paint();
      });
      element.querySelector('[data-finish]').addEventListener('click', () => ctx.go(ctx.href('practice')));
      return;
    }

    const item = items[state.index];
    const last = state.index === total - 1;
    const look = state.result ? RESULT_LOOK[state.result.shown ? 'shown' : state.result.ok ? 'ok' : 'bad'] : null;

    mount(
      element,
      html`${header(t('progress', { n: state.index + 1, total }))}
      <div class="s-errors-bar"><span style="width:${Math.round((state.index / total) * 100)}%"></span></div>
      <div class="s-errors-card">
        <div class="s-errors-card__body" data-scroll-region>
          <div class="s-errors-card__head">
            <span class="s-errors-pattern-pill">${item.pattern}</span>
            <span class="s-errors-source">${[t('sourceLabel'), dateLabel(item.createdAt)].filter(Boolean).join(' · ')}</span>
          </div>
          <div class="s-errors-instruction">${t('instruction')}</div>
          <textarea class="s-errors-input" rows="2" lang="${languageOf(item)}" aria-label="${t('instruction')}">${state.text}</textarea>
          ${
            look
              ? html`<div class="s-errors-result s-errors-result--${look.tone}">
                  <div class="s-errors-result__label">${t(look.key)}</div>
                  <div class="s-errors-result__bad" lang="${languageOf(item)}"><s>${item.bad}</s></div>
                  <div class="s-errors-result__good" lang="${languageOf(item)}">${item.good}</div>
                  ${item.why ? html`<div class="s-errors-result__why">${item.why}</div>` : ''}
                </div>`
              : ''
          }
        </div>
        ${
          !look
            ? html`<div class="s-errors-actions">
                <button type="button" class="s-errors-btn s-errors-btn--secondary" data-show-answer>${t('showAnswer')}</button>
                <span class="s-errors-spacer"></span>
                <button type="button" class="s-errors-btn s-errors-btn--primary" data-check>${t('check')}</button>
              </div>`
            : html`<div class="s-errors-actions">
                ${!state.result.ok && !state.result.shown ? html`<button type="button" class="s-errors-btn s-errors-btn--secondary" data-retry>${t('tryAgain')}</button>` : ''}
                <span class="s-errors-spacer"></span>
                <button type="button" class="s-errors-btn s-errors-btn--primary" data-next>${t(last ? 'seeResults' : 'nextSentence')}</button>
              </div>`
        }
      </div>`,
    );
    bindHeader();

    const textarea = element.querySelector('.s-errors-input');
    textarea?.addEventListener('input', () => {
      state.text = textarea.value;
    });

    element.querySelector('[data-check]')?.addEventListener('click', () => {
      const correct = isCorrect(state.text, item.good);
      state.results[state.index] = recordCheck(state.results[state.index], { correct, wrongBefore: state.wrongBefore });
      if (!correct) state.wrongBefore += 1;
      state.result = { ok: correct, shown: false };
      paint();
    });

    element.querySelector('[data-show-answer]')?.addEventListener('click', () => {
      state.results[state.index] = recordReveal(state.results[state.index]);
      state.text = item.good;
      state.result = { ok: false, shown: true };
      paint();
    });

    element.querySelector('[data-retry]')?.addEventListener('click', () => {
      state.result = null;
      paint();
      element.querySelector('.s-errors-input')?.focus();
    });

    element.querySelector('[data-next]')?.addEventListener('click', () => {
      begin(state.index + 1);
      paint();
    });
  }

  function bindHeader() {
    element.querySelector('[data-back]').addEventListener('click', () => ctx.back());
  }

  paint();
  return undefined;
}
