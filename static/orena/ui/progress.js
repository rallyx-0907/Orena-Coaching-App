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

/* --- The evidence the learner actually left (D-067) ----------------------
   The source draws "BẰNG CHỨNG GẦN NHẤT" as a short list of what was last
   judged: the piece, a mono line about it, the figure, and which measure that
   figure is. Every one of those comes from LearnerSummary's observations -
   nothing here averages, estimates or invents.

   A writing observation can be titled, because the essay list carries the task
   the learner answered, the version and the word count - the frame's own meta
   line. The other domains have no title in the read model yet, so the row says
   which practice it was, which is what it is, rather than a made-up name. */
const MEASURE_KEYS = {
  overall: 'evidenceOverall',
  naturalness: 'evidenceNaturalness',
  grammar: 'evidenceGrammar',
  vocabulary: 'evidenceVocabulary',
  coherence: 'evidenceCoherence',
  task_achievement: 'evidenceTask',
  accuracy: 'evidenceAccuracy',
  pronunciation: 'evidencePronunciation',
  dictation_best_match: 'evidenceAccuracy',
};

function whenWord(r, iso) {
  const at = Date.parse(iso || '');
  if (!Number.isFinite(at)) return '';
  const days = Math.floor((Date.now() - at) / 86400000);
  if (days <= 0) return r.evidenceToday;
  if (days === 1) return r.evidenceYesterday;
  return String(r.evidenceDaysAgo).replace('{n}', String(days));
}

function evidenceRows(r, summary, essays) {
  if (!summary?.domains) return [];
  const byId = new Map((essays || []).map((essay) => [String(essay.id), essay]));
  const rows = [];
  for (const [domain, block] of Object.entries(summary.domains)) {
    for (const observation of block?.observations || []) {
      const value = Number(observation?.value);
      if (!Number.isFinite(value)) continue;
      const essay = domain === 'writing' ? byId.get(String(observation?.ref?.id ?? '')) : null;
      const meta = [
        essay && Number(essay.revision_no) > 1 ? String(r.evidenceVersion).replace('{n}', String(essay.revision_no)) : '',
        essay && Number(essay.word_count) > 0 ? String(r.evidenceWords).replace('{n}', Number(essay.word_count).toLocaleString()) : '',
        whenWord(r, observation.observedAt),
      ].filter(Boolean).join(' · ');
      rows.push({
        title: essay?.prompt || r[domain] || domain,
        meta,
        value: Math.round(value),
        /* A measure the interface has no word for is left blank rather than
           printed as the read model's own key. */
        measure: r[MEASURE_KEYS[observation.measure] || ''] || '',
        at: Date.parse(observation.observedAt || '') || 0,
      });
    }
  }
  return rows.sort((a, b) => b.at - a.at).slice(0, 4);
}

const evidenceHtml = (r, rows) =>
  rows.length
    ? `<section class="evidence" aria-label="${esc(r.evidenceRecent)}"><span class="ds-label evidence__label">${esc(r.evidenceRecent)}</span><ol class="evidence-list">${rows
        .map(
          (row) => `<li class="evidence-row"><span class="evidence-row__text"><span class="evidence-row__title">${esc(row.title)}</span>${
            row.meta ? `<span class="evidence-row__meta ds-data">${esc(row.meta)}</span>` : ''
          }</span><span class="evidence-row__score"><strong>${esc(String(row.value))}</strong><span class="ds-label">${esc(row.measure)}</span></span></li>`,
        )
        .join('')}</ol></section>`
    : '';

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

/* The per-skill rows the source puts under the heatmap. It draws seven days of
   time; Orena records no time at all, so each row carries what it does record
   for that skill - the same words the settings sheet uses, through
   growthDomainRow - and says "not measured" where it records nothing. */
function skillRows(c, r, summary, words) {
  const rows = DOMAINS.map((entry) => {
    const line = domainLine(c, r, entry, summary, words);
    const value = line.measured ? line.text : r.progressNotMeasured;
    return `<a class="skill-row" href="${entry.href()}" data-domain="${entry.domain}">
      <span class="skill-row__name ds-data">${esc(r[entry.key])}</span>
      <span class="skill-row__value ds-data${line.measured ? '' : ' metric-unavailable'}">${line.measured && entry.evidence !== 'vocabulary' ? value : esc(value)}</span>
    </a>`;
  }).join('');
  return `<div class="skill-time">
    <span class="ds-label skill-time__label">${esc(r.progressBySkill)}</span>
    <div class="skill-time__rows">${rows}</div>
  </div>`;
}

/* The source closes the column with the one thing to do next. Orena knows this
   only when something is actually due; with nothing due it says so rather than
   inventing an errand. */
function nextAction(r, words) {
  const due = Number(words?.due || 0);
  const detail = due > 0
    ? String(r.progressNextDue).replace('{n}', String(due))
    : r.progressNextNothing;
  return `<div class="next-action">
    <span class="next-action__title">${esc(r.progressNextTitle)}</span>
    <p class="next-action__detail">${esc(detail)}</p>
  </div>`;
}

function view(ctx, { summary, words, summaryFailed, essays }) {
  const c = ctx.c;
  const r = referenceCopy[ctx.ui] || referenceCopy.en;
  const degraded = summaryFailed
    ? `<div class="state-panel" data-tone="error" role="alert">${icon('warning-circle', { size: 20 })}<div><strong>${esc(c.growthUnavailable)}</strong></div><button class="outline" type="button" data-progress-retry>${icon('arrow-counter-clockwise', { size: 16 })}<span>${esc(c.retry)}</span></button></div>`
    : '';

  /* Nothing counts days in a row or time spent (GAP-001, GAP-002). Words that
     have passed the remembering threshold are counted, so that figure is real. */
  const figures = [
    statPanel(r.progressStreak, '', r.progressStreakNote, { measured: false }),
    statPanel(r.progressStudyTime, '', r.progressStudyNote, { measured: false }),
    statPanel(
      r.progressWordsMastered,
      words ? Number(words.mastered).toLocaleString() : '0',
      r.progressWordsMasteredNote,
      { measured: Boolean(words) },
    ),
  ].join('');

  return `<section class="progress-page">
  <h1 class="progress-title">${esc(r.progress)}</h1>
  ${degraded}
  <div class="progress-figures">${figures}</div>
  <div class="progress-columns">
    <div class="progress-column progress-column--evidence">
      ${evidenceHtml(r, evidenceRows(r, summary, essays))}
    </div>
    <aside class="progress-column progress-column--side">
      ${heatmap(r, null)}
      ${skillRows(c, r, summary, words)}
      ${nextAction(r, words)}
    </aside>
  </div>
</section>`;
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
    const [summaryResult, wordsResult, essayResult] = await Promise.allSettled([
      ctx.growth ? Promise.resolve(ctx.growth) : ctx.api.learnerSummary('all'),
      ctx.api.libraryVocabulary(),
      /* Only to title a writing row with the task it answered; a failure here
         costs the title, never the evidence. */
      ctx.api.essays(),
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
    const essays = essayResult.status === 'fulfilled' ? essayResult.value || [] : [];
    paint(view(ctx, { summary, words, summaryFailed: !summary, essays }));
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
