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
import { rankFrame } from './rank-frame.js';
import { ladderTiles, openTierCount, rankProgress, rankSummary } from '../product/rank.js';

/* What "vừa học xong" shows: three words, so three words are asked for. */
const RECENT_WORDS = 3;

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

/* --- The head the phone draws (D-067) -----------------------------------
   The desktop bar carries the destination, the two tabs and the window its
   numbers cover; on the phone that bar is not drawn at all, so the page draws
   the frame's own head instead: the name at 24/800 (22 on Xu hướng), the
   window beside it, and the two tabs as a full-width row of 38 with radius 13.
   Without it the phone could see Tổng quan and never reach Xu hướng. */
function pageHead(ctx, r, current) {
  const trends = current === 'trends';
  const tab = (id, label) => `<a class="ptab" href="${esc(link('progress', id === 'overview' ? {} : { tab: id }))}"`
    + `${current === id ? ' aria-current="page"' : ''}>${esc(label)}</a>`;
  return `<div class="progress-head">`
    + `<h1 class="progress-title">${esc(trends ? r.progressTabTrends : r.progress)}</h1>`
    + `<span class="progress-head__meta ds-data">${esc(trends ? r.progressWindowTrends : r.progressWindowOverview)}</span>`
    + `</div>`
    + `<nav class="ptabs ptabs--page" aria-label="${esc(r.progress)}">`
    + tab('overview', r.progressTabOverview) + tab('trends', r.progressTabTrends)
    + `</nav>`;
}

/* --- The second row the frame draws (D-067) ------------------------------
   Four panels of 375x147, 16/18 padding, radius 18, gap 20 between them: what
   was just learned, what is being reviewed, comprehension, and recall. The
   figure is Nunito 26/800 over a 13.5 line that says what it counts.

   Orena measures the first two from the learner's own vocabulary; the other
   two need review and comprehension figures nothing serves yet, so they render
   0 in the canonical component and say what they would count (D-066 rule 4).
   The panel is built either way - a component the backend cannot fill yet is
   still the component. */
function panel(label, glyph, figure, note, extra = '', { measured = true } = {}) {
  return `<section class="pstat"${measured ? '' : ' data-unmeasured'}>`
    + `<span class="ds-label pstat__label">${icon(glyph, { size: 14 })}${esc(label)}</span>`
    + `<strong class="pstat__figure${measured ? '' : ' metric-unavailable'}">${esc(figure)}</strong>`
    + `<span class="pstat__note">${esc(note)}</span>`
    + (extra ? `<div class="pstat__extra">${extra}</div>` : '')
    + `</section>`;
}

function overviewPanels(r, words, recent) {
  const saved = Number(words?.saved || 0);
  const due = Number(words?.due || 0);
  const chips = (recent || []).slice(0, 3)
    .map((w) => `<span class="pstat__chip" lang="${esc(w.language || '')}">${esc(w.word)}</span>`).join('');
  const reviewing = Math.max(0, saved - Number(words?.mastered || 0));
  const reviewed = Math.max(0, reviewing - due);
  return [
    panel(r.progressJustLearned, 'sparkle', `${(recent || []).length}`, r.progressJustLearnedNote, chips,
      { measured: Boolean(words) }),
    panel(r.progressReviewing, 'cards', `${reviewing}`, String(r.progressDueToday).replace('{n}', String(due)),
      `<span class="progress-bar pstat__bar"><span style="width:${reviewing ? Math.round((reviewed / reviewing) * 100) : 0}%"></span></span>`
      + `<span class="pstat__ratio ds-data">${reviewed}/${reviewing}</span>`,
      { measured: Boolean(words) }),
    panel(r.progressComprehension, 'check-square-offset', '0', r.progressComprehensionNote, '', { measured: false }),
    panel(r.progressRecall, 'arrow-counter-clockwise', '0', r.progressRecallNote,
      `<div class="pstat__split ds-data"><span>${esc(String(r.progressRecallGot).replace('{n}', '0'))}</span>`
      + `<span>${esc(String(r.progressRecallUnsure).replace('{n}', '0'))}</span>`
      + `<span>${esc(String(r.progressRecallForgot).replace('{n}', '0'))}</span></div>`,
      { measured: false }),
  ].join('');
}

/* --- Xu hướng (D-067, "Progress trends") --------------------------------
   Four measures against four weeks ago, what each one is drawn from, the
   mistakes that keep coming back, and the one thing to do next.

   None of it is served: there is no trend model, no repeated-error model, and
   no per-measure history. Every figure is therefore 0 in its canonical
   component and every list says it has nothing yet, which is the honest
   picture of a screen whose data has not been built. */
function trendsView(ctx) {
  const r = referenceCopy[ctx.ui] || referenceCopy.en;
  const measures = [
    r.evidenceNaturalness, r.evidencePronunciation, r.progressRecall, r.progressListening,
  ].map((label) => `<div class="trend-row">`
    /* The frame draws a name and the move it made - "72 → 88" - and no bar at
       all. Nothing measures either end of that move yet, so the row keeps its
       place and says nothing rather than drawing a length or an arrow that
       would stand for a direction nobody knows. */
    + `<span class="trend-row__name">${esc(label)}</span>`
    + `<span class="trend-row__value ds-data metric-unavailable">&mdash;</span>`
    + `</div>`).join('');
  const sources = [r.progressSourceCards, r.progressSourceWriting, r.progressSourceQuestions,
    r.progressSourceSpeaking, r.progressSourceReading]
    .map((label) => `<span class="trend-chip ds-data">${esc(String(label).replace('{n}', '0'))}</span>`).join('');
  return `<section class="progress-page">`
    + pageHead(ctx, r, 'trends')
    + `<section class="trend-block">`
    + `<span class="ds-label">${esc(r.progressImproving)}</span>`
    + `<div class="trend-rows">${measures}</div>`
    + `</section>`
    + `<section class="trend-block">`
    + `<span class="ds-label">${esc(r.progressBasedOn)}</span>`
    + `<p class="trend-note">${esc(r.progressBasedOnNote)}</p>`
    + `<div class="trend-chips">${sources}</div>`
    + `</section>`
    + `<section class="trend-block">`
    + `<span class="ds-label">${esc(r.progressRepeated)}</span>`
    + `<p class="trend-note">${esc(r.progressRepeatedNone)}</p>`
    + `</section>`
    /* The frame closes Xu hướng with the same "what to do next" card the
       overview ends on, so it is drawn here too. */
    + nextAction(r, null)
    + `</section>`;
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
/* --- The ladder, on the master's thirty-two ranks ------------------------
   The rank system is "Orena Rank Frame Master v2": thirty-two ranks in eight
   bands. The thresholds are the Progress frame's own, joined to it by name -
   see static/orena/product/rank.js, which both this screen and Hồ sơ read, so
   they cannot disagree about where the learner stands.

   A rank the design gives no word count to shows a dash. There are fourteen of
   them, and that is a gap recorded for the human, not a licence to invent
   numbers. */
function ladderHtml(r, state) {
  const tiles = ladderTiles(state);
  const total = state.rankTotal || tiles.length;
  const rungs = tiles.map((tile) => {
    const shown = tile.current ? 'current' : tile.open ? 'open' : 'locked';
    const note = tile.current
      ? esc(r.progressTierCurrent)
      : tile.words === null
        ? '&mdash;'
        : esc(`${tile.words.toLocaleString()} ${r.progressTierWords}${tile.open ? ` · ${r.progressTierOpen}` : ''}`);
    return `<li class="tier" data-state="${shown}" data-band="${esc(tile.band)}">`
      + `<span class="tier__no ds-data">${tile.open || tile.current ? String(tile.tier).padStart(2, '0') : icon('lock-simple', { size: 13 })}</span>`
      + `<span class="tier__text"><span class="tier__name">${esc(tile.name)}</span><span class="tier__note ds-data">${note}</span></span>`
      + `</li>`;
  }).join('');
  const head = String(r.progressLadder).replace('{n}', String(total));
  const opened = String(r.progressTierOpened)
    .replace('{n}', String(openTierCount(state)))
    .replace('{t}', String(total));
  return `<section class="ladder" aria-label="${esc(head)}">`
    + `<div class="ladder__head"><span class="ds-label">${esc(head)}</span><span class="ds-data ladder__open">${esc(opened)}</span></div>`
    + `<ol class="ladder__grid">${rungs}</ol>`
    + `</section>`;
}

/* The card under the ladder: which rank the learner holds and how far to the
   next one. The crystal is the master's, at the `mid` level of detail this
   size asks for; before the first rank there is no crystal to draw, so the
   well is plain. */
function rankCardHtml(r, state) {
  const current = state.rank;
  const name = current ? state.rankName : r.progressTierNone;
  const percent = rankProgress(state);
  const line = state.nextRankName
    ? `${state.mastered.toLocaleString()} / ${Number(state.nextRankWords).toLocaleString()} → ${state.nextRankName}`
    : r.progressTierTop;
  const title = current
    ? `${name} · ${String(r.progressTierOf).replace('{n}', String(current)).replace('{t}', String(state.rankTotal))}`
    : name;
  const face = `<span class="rank-card__face">${icon('user', { size: 26 })}</span>`;
  const avatar = current
    ? rankFrame({ rank: current, size: 62, uid: 'progress-rank', avatar: face })
    : `<span class="rank-card__avatar">${icon('user', { size: 26 })}</span>`;
  return `<section class="rank-card">`
    + avatar
    + `<div class="rank-card__text"><span class="ds-label">${esc(r.progressTierLabel)}${current ? ` · ${esc(state.band)}` : ''}</span>`
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

function view(ctx, { summary, vocabulary, summaryFailed, recent }) {
  const c = ctx.c;
  const r = referenceCopy[ctx.ui] || referenceCopy.en;
  const degraded = summaryFailed
    ? `<div class="state-panel" data-tone="error" role="alert">${icon('warning-circle', { size: 20 })}<div><strong>${esc(c.growthUnavailable)}</strong></div><button class="outline" type="button" data-progress-retry>${icon('arrow-counter-clockwise', { size: 16 })}<span>${esc(c.retry)}</span></button></div>`
    : '';
  /* Counted by the database, read here. The words themselves are not on this
     screen and are not fetched for it. */
  const state = rankSummary(vocabulary);
  const words = state.known
    ? { saved: state.saved, due: state.due, mastered: state.mastered }
    : null;

  const figures = [
    statPanel(r.progressStreak, '', r.progressStreakNote, { measured: false }),
    statPanel(r.progressStudyTime, '', r.progressStudyNote, { measured: false }),
    statPanel(r.progressWordsMastered, state.mastered.toLocaleString(), r.progressWordsMasteredNote, { measured: state.known }),
  ].join('');

  return `<section class="progress-page">`
    + pageHead(ctx, r, 'overview')
    + degraded
    + `<div class="progress-figures">${figures}</div>`
    + `<div class="progress-panels">${overviewPanels(r, words, recent)}</div>`
    + `<div class="progress-columns">`
    + `<div class="progress-column progress-column--main">${ladderHtml(r, state)}${rankCardHtml(r, state)}</div>`
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
  /* Xu hướng needs nothing from the account: every figure on it is unserved,
     so it paints at once rather than waiting on two requests to tell the
     learner the same nothing. */
  if (ctx.location?.tab === 'trends') {
    if (ctx.alive()) root.innerHTML = trendsView(ctx);
    return () => {};
  }
  const paint = (html) => {
    if (!released && ctx.alive()) root.innerHTML = html;
  };
  async function load() {
    paint(skeleton(ctx));
    /* Three requests, each for what it is actually for: the growth summary,
       the vocabulary counts and rank, and the three words "vừa học xong"
       names. None of them reads the learner's library. */
    const [summaryResult, countsResult, recentResult] = await Promise.allSettled([
      ctx.growth ? Promise.resolve(ctx.growth) : ctx.api.learnerSummary('all'),
      ctx.api.libraryVocabularySummary(),
      ctx.api.libraryVocabulary({ limit: RECENT_WORDS, order: 'recent' }),
    ]);
    const summary = summaryResult.status === 'fulfilled' ? summaryResult.value : null;
    const vocabulary = countsResult.status === 'fulfilled' ? countsResult.value : null;
    const recent = recentResult.status === 'fulfilled'
      ? (recentResult.value.items || []).map((item) => ({ word: item.word, language: item.language_code }))
      : [];
    paint(view(ctx, { summary, vocabulary, summaryFailed: !summary, recent }));
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
