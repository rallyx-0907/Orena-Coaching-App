/* Progress (D-059, D-060): the approved composition, over the learner's own
   evidence.

   The design draws a week panel (study time this week, a streak, words due),
   a seven-day chart, and six domain cards each with a line and a bar. Every
   one of those components keeps its place and shape here. Where Orena records
   the measure, it is shown; where it does not yet - study time, streak, the
   daily chart, most per-domain progress - the component says "not measured"
   in the design system's unavailable state, and the missing measure is a
   tracked gap (docs/project/UI_BACKEND_GAPS.md GAP-001..GAP-003, GAP-007..10),
   never an invented number. LearnerSummary's rule stands: unknown is not zero.

   Measured today:
   - words due, words saved and mastered: the learner's saved vocabulary;
   - reading, dictation, speaking and writing activity: LearnerSummary, worded
     by `growthDomainRow` so this page and the settings sheet cannot disagree. */
import { esc } from './html.js';
import { icon } from './phosphor.js';
import { growthDomainRow } from './growth-summary.js';
import { referenceCopy } from './reference.js';
import { link } from '../product/intent.js';
import { RANK_NAMES } from './rank-frame.js';

/* The six approved domain cards, in the design's order, and the evidence each
   one reads. Listening's own measure (episodes, minutes) is not recorded; the
   dictation lines LearnerSummary files under "listening" belong to Dictation. */
const DOMAINS = [
  { key: 'reading', domain: 'reading', icon: 'book-open', evidence: 'reading', href: () => link('practice', { intent: 'reading' }) },
  { key: 'listening', domain: 'listening', icon: 'headphones', evidence: null, href: () => link('practice', { intent: 'follow' }) },
  { key: 'speaking', domain: 'speaking', icon: 'microphone', evidence: 'speaking', href: () => link('practice', { intent: 'speaking' }) },
  { key: 'dictation', domain: 'dictation', icon: 'keyboard', evidence: 'listening', href: () => link('practice', { intent: 'dictation' }) },
  { key: 'writing', domain: 'writing', icon: 'pencil-simple', evidence: 'writing', href: () => link('expression') },
  { key: 'vocabulary', domain: 'vocabulary', icon: 'cards', evidence: 'vocabulary', href: () => link('language') },
];

const unavailableBar = '<span class="progress-bar" data-unavailable aria-hidden="true"></span>';
const measuredBar = (fraction, label) => {
  const percent = Math.max(0, Math.min(100, Math.round(fraction * 100)));
  return `<span class="progress-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent}" aria-label="${esc(label)}"><span style="width:${percent}%"></span></span>`;
};

function dayLabels(ui) {
  // Monday first, narrow form, in the support language.
  const locale = ui === 'zh' ? 'zh-CN' : ui === 'vi' ? 'vi-VN' : 'en-GB';
  const monday = new Date(Date.UTC(2024, 0, 1));
  const format = new Intl.DateTimeFormat(locale, { weekday: 'narrow', timeZone: 'UTC' });
  return Array.from({ length: 7 }, (_, n) => format.format(new Date(monday.getTime() + n * 86400000)));
}

function domainLine(c, r, entry, summary, words) {
  if (entry.evidence === 'vocabulary') {
    if (!words) return { text: r.progressNotMeasured, bar: unavailableBar, measured: false };
    const text = r.progressWordsLine.replace('{saved}', words.saved).replace('{mastered}', words.mastered);
    return { text, bar: words.saved ? measuredBar(words.mastered / words.saved, text) : unavailableBar, measured: true };
  }
  if (!entry.evidence || !summary) return { text: r.progressNotMeasured, bar: unavailableBar, measured: false };
  const row = growthDomainRow(c, entry.evidence, summary.domains?.[entry.evidence]);
  return { text: row.value, label: row.label, bar: unavailableBar, measured: true };
}

/* --- The rank ladder (D-067, the reworked Progress frame) ---------------
   The frame that used to carry "BẰNG CHỨNG GẦN NHẤT" now carries the twenty
   tiers, so the evidence list is deleted with it (rule 44) rather than kept
   beside the thing that replaced it.

   The thresholds are the frame's own, read off its tiles: they are what makes
   a tier mean anything, and they are the product's numbers, not this lane's.
   Tier 10 is the one the frame does not state - it draws "BẬC HIỆN TẠI" over
   its own number - so that tier shows a dash and the gap is recorded rather
   than filled in with a guess. */
const RANK_THRESHOLDS = [
  50, 150, 300, 500, 700, 950, 1200, 1450, 1600, null,
  3000, 4500, 6000, 8000, 10000, 13000, 16000, 20000, 25000, 30000,
];

/* The highest tier whose threshold the learner has passed. A tier with no
   stated threshold cannot be reached by counting, so it is skipped rather than
   guessed at. */
function tierOf(known) {
  let tier = 0;
  RANK_THRESHOLDS.forEach((threshold, index) => {
    if (threshold !== null && known >= threshold) tier = index + 1;
  });
  return tier;
}

function ladderHtml(r, known) {
  const current = tierOf(known);
  const unlocked = RANK_THRESHOLDS.filter((t) => t !== null && known >= t).length;
  const tiles = RANK_NAMES.map((name, index) => {
    const tier = index + 1;
    const threshold = RANK_THRESHOLDS[index];
    const isCurrent = tier === current;
    const isOpen = threshold !== null && known >= threshold;
    const state = isCurrent ? 'current' : isOpen ? 'open' : 'locked';
    const note = isCurrent
      ? esc(r.progressTierCurrent)
      : threshold === null
        ? '—'
        : esc(`${threshold.toLocaleString()} ${r.progressTierWords}${isOpen ? ` · ${r.progressTierOpen}` : ''}`);
    return `<li class="tier" data-state="${state}">`
      + `<span class="tier__no ds-data">${isOpen || isCurrent ? String(tier).padStart(2, '0') : icon('lock-simple', { size: 13 })}</span>`
      + `<span class="tier__text"><span class="tier__name">${esc(name)}</span><span class="tier__note ds-data">${note}</span></span>`
      + `</li>`;
  }).join('');
  const head = String(r.progressLadder).replace('{n}', String(RANK_NAMES.length));
  const opened = String(r.progressTierOpened).replace('{n}', String(unlocked)).replace('{t}', String(RANK_NAMES.length));
  return `<section class="ladder" aria-label="${esc(head)}">`
    + `<div class="ladder__head"><span class="ds-label">${esc(head)}</span><span class="ds-data ladder__open">${esc(opened)}</span></div>`
    + `<ol class="ladder__grid">${tiles}</ol>`
    + `</section>`;
}

/* The card under the ladder: which tier the learner is on and how far to the
   next one. The avatar is drawn plain until the human finishes the rank frame
   they are revising. */
function rankCardHtml(r, known) {
  const current = tierOf(known);
  const nextIndex = RANK_THRESHOLDS.findIndex((t, i) => i >= current && t !== null && known < t);
  const next = nextIndex >= 0 ? { name: RANK_NAMES[nextIndex], at: RANK_THRESHOLDS[nextIndex] } : null;
  const name = current ? RANK_NAMES[current - 1] : r.progressTierNone;
  const percent = next ? Math.max(0, Math.min(100, Math.round((known / next.at) * 100))) : 100;
  const line = next
    ? `${known.toLocaleString()} / ${next.at.toLocaleString()} → ${next.name}`
    : r.progressTierTop;
  const title = current
    ? `${name} · ${String(r.progressTierOf).replace('{n}', String(current)).replace('{t}', String(RANK_NAMES.length))}`
    : name;
  return `<section class="rank-card">`
    + `<span class="rank-card__avatar">${icon('user', { size: 26 })}</span>`
    + `<div class="rank-card__text"><span class="ds-label">${esc(r.progressTierLabel)}</span>`
    + `<span class="rank-card__name">${esc(title)}</span></div>`
    + `<span class="progress-bar rank-card__track"${percent ? '' : ' data-unavailable'}><span style="width:${percent}%"></span></span>`
    + `<span class="rank-card__to ds-data">${esc(line)}</span>`
    + `</section>`;
}

/* --- The three figures the source leads with (D-067) ---------------------
   507x123 panels: a mono label, the figure at Nunito 34/800, and a line under
   it saying what the figure counts. Orena measures one of the three today, so
   the other two render as the baseline's rule requires - the canonical
   component with nothing in it, saying so - and never as a number nobody
   counted (D-066 rule 4). */
function statPanel(label, value, note, { measured = true } = {}) {
  return `<div class="progress-figure"${measured ? '' : ' data-unmeasured'}>
    <span class="ds-label progress-figure__label">${esc(label)}</span>
    <strong class="progress-figure__value${measured ? '' : ' metric-unavailable'}">${esc(measured ? value : '0')}</strong>
    <span class="progress-figure__note">${esc(note)}</span>
  </div>`;
}

/* Eighteen weeks of days, the source's own grid: 126 cells of 18px with a 5px
   gap. Orena records no daily activity, so every cell is the empty one - which
   is the honest picture of a thing that is not counted, not an empty div. */
const HEAT_WEEKS = 18;
const HEAT_DAYS = 7;
function heatmap(r, days) {
  const cells = Array.from({ length: HEAT_WEEKS * HEAT_DAYS }, (_, i) => {
    const level = days && days[i] ? Math.max(0, Math.min(3, Number(days[i]) || 0)) : 0;
    return `<span class="heat-cell" data-level="${level}"></span>`;
  }).join('');
  return `<div class="heat">
    <div class="heat__head"><span class="heat__title">${esc(String(r.progressActivityWeeks).replace('{n}', String(HEAT_WEEKS)))}</span><span class="ds-data heat__legend">${esc(r.progressHeatLegend)}</span></div>
    <div class="heat__grid" role="img" aria-label="${esc(r.progressHeatUnavailable)}">${cells}</div>
  </div>`;
}

/* The five the frame lists - Reading, Listening, Speaking, Writing,
   Vocabulary. There is no Dictation row: the frame's own label says
   "CHÉP CHÍNH TẢ TÍNH VÀO LISTENING", so dictation is counted into Listening
   rather than given a row of its own.

   Every row is one geometry - name 104, track 356x10, value 60 - so the bars
   are all the same length, which is what makes them comparable. Letting the
   value push the track about, as this did, is the thing that made them look
   ragged.

   The column measures seven days of time. Orena records no time at all, so
   every track is the unavailable one and every value is a dash: a length or a
   number here would be reading as time nobody counted (D-066 rule 4). What
   each skill does record is not shown under a heading that says time. */
const TIME_SKILLS = ['reading', 'listening', 'speaking', 'writing', 'vocabulary'];

function skillRows(c, r, summary, words) {
  const rows = TIME_SKILLS.map((key) => {
    const entry = DOMAINS.find((d) => d.key === key);
    return `<a class="skill-row" href="${entry.href()}" data-domain="${entry.domain}">`
      + `<span class="skill-row__name ds-data">${esc(r[key])}</span>`
      + `<span class="progress-bar skill-row__bar" data-unavailable aria-hidden="true"></span>`
      + `<span class="skill-row__value ds-data metric-unavailable">&mdash;</span>`
      + `</a>`;
  }).join('');
  return `<div class="skill-time">`
    + `<span class="ds-label skill-time__label">${esc(r.progressBySkill)}</span>`
    + `<div class="skill-time__rows">${rows}</div>`
    + `</div>`;
}

/* The source closes the column with the one thing to do next. Orena knows this
   only when something is actually due; with nothing due it says so rather than
   inventing an errand. */
function nextAction(r, words) {
  const due = Number(words?.due || 0);
  const detail = due > 0
    ? String(r.progressNextDue).replace('{n}', String(due))
    : r.progressNextNothing;
  const href = due > 0 ? link('practice', { intent: 'recall' }) : link('practice', { intent: 'reading' });
  return `<a class="next-action" href="${esc(href)}">`
    + `<span class="next-action__go">${icon('arrow-right', { size: 18 })}</span>`
    + `<span class="next-action__text"><span class="next-action__title">${esc(r.progressNextTitle)}</span>`
    + `<span class="next-action__detail">${esc(detail)}</span></span>`
    + `</a>`;
}

function view(ctx, { summary, words, summaryFailed }) {
  const c = ctx.c;
  const r = referenceCopy[ctx.ui] || referenceCopy.en;
  const degraded = summaryFailed
    ? `<div class="state-panel" data-tone="error" role="alert">${icon('warning-circle', { size: 20 })}<div><strong>${esc(c.growthUnavailable)}</strong></div><button class="outline" type="button" data-progress-retry>${icon('arrow-counter-clockwise', { size: 16 })}<span>${esc(c.retry)}</span></button></div>`
    : '';
  const known = Number(words?.mastered || 0);

  const figures = [
    statPanel(r.progressStreak, '', r.progressStreakNote, { measured: false }),
    statPanel(r.progressStudyTime, '', r.progressStudyNote, { measured: false }),
    statPanel(r.progressWordsMastered, known.toLocaleString(), r.progressWordsMasteredNote, { measured: Boolean(words) }),
  ].join('');

  return `<section class="progress-page">`
    + `<h1 class="progress-title">${esc(r.progress)}</h1>`
    + degraded
    + `<div class="progress-figures">${figures}</div>`
    + `<div class="progress-columns">`
    + `<div class="progress-column progress-column--main">${ladderHtml(r, known)}${rankCardHtml(r, known)}</div>`
    + `<aside class="progress-column progress-column--side">${heatmap(r, null)}${skillRows(c, r, summary, words)}${nextAction(r, words)}</aside>`
    + `</div>`
    + `</section>`;
}

function skeleton(ctx) {
  const r = referenceCopy[ctx.ui] || referenceCopy.en;
  return `<section class="progress-page" aria-busy="true"><h1 class="progress-title">${esc(r.progress)}</h1><div class="progress-panel"><span class="skeleton skeleton--line" style="inline-size:40%"></span><span class="skeleton" style="block-size:120px"></span><div class="progress-domains">${DOMAINS.map(() => '<span class="skeleton skeleton--card"></span>').join('')}</div></div></section>`;
}

export async function renderProgress(root, ctx) {
  let released = false;
  const paint = (html) => {
    if (!released && ctx.alive()) root.innerHTML = html;
  };
  async function load() {
    paint(skeleton(ctx));
    const [summaryResult, wordsResult] = await Promise.allSettled([
      ctx.growth ? Promise.resolve(ctx.growth) : ctx.api.learnerSummary('all'),
      ctx.api.libraryVocabulary(),
    ]);
    const summary = summaryResult.status === 'fulfilled' ? summaryResult.value : null;
    const items = wordsResult.status === 'fulfilled' ? wordsResult.value.items || [] : null;
    const words = items
      ? {
          saved: items.length,
          due: items.filter((item) => item.due).length,
          mastered: items.filter((item) => (Number(item.review_stage) || 0) >= 3).length,
        }
      : null;
    paint(view(ctx, { summary, words, summaryFailed: !summary }));
    root.querySelector('[data-progress-retry]')?.addEventListener('click', () => {
      ctx.growth = null;
      load();
    });
  }
  await load();
  return () => {
    released = true;
  };
}
