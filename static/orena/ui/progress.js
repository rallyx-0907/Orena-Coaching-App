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

function view(ctx, { summary, words, summaryFailed, essays }) {
  const c = ctx.c;
  const r = referenceCopy[ctx.ui] || referenceCopy.en;
  const dueValue = words ? String(words.due) : '—';
  const cards = DOMAINS.map((entry) => {
    const line = domainLine(c, r, entry, summary, words);
    const name = r[entry.key];
    return `<a class="progress-domain" href="${entry.href()}" data-domain="${entry.domain}"><span class="progress-domain__head">${icon(entry.icon, { size: 18 })}<span>${esc(name)}</span></span><span class="progress-domain__line${line.measured ? '' : ' metric-unavailable'}">${line.measured && entry.evidence !== 'vocabulary' ? line.text : esc(line.text)}</span>${line.bar}</a>`;
  }).join('');
  const days = dayLabels(ctx.ui)
    .map((day) => `<span class="progress-day"><span class="progress-day__bar" aria-hidden="true"></span><span class="progress-day__label">${esc(day)}</span></span>`)
    .join('');
  const degraded = summaryFailed
    ? `<div class="state-panel" data-tone="error" role="alert">${icon('warning-circle', { size: 20 })}<div><strong>${esc(c.growthUnavailable)}</strong></div><button class="outline" type="button" data-progress-retry>${icon('arrow-counter-clockwise', { size: 16 })}<span>${esc(c.retry)}</span></button></div>`
    : '';
  return `<section class="progress-page"><h1 class="progress-title">${esc(r.progress)}</h1><div class="progress-panel"><div class="progress-week"><div class="progress-week__time"><span class="progress-label">${esc(r.progressThisWeek)}</span><strong class="progress-week__value metric-unavailable" aria-describedby="progressTimeNote">—</strong><span class="progress-week__note" id="progressTimeNote">${esc(r.progressStudyUnavailable)}</span></div><div class="progress-stats"><div class="progress-stat progress-stat--streak"><span class="progress-label">${esc(r.progressStreak)}</span><strong class="metric-unavailable" aria-label="${esc(r.progressNotMeasured)}">—</strong></div><div class="progress-stat"><span class="progress-label">${esc(r.progressWordsDue)}</span><strong>${esc(dueValue)}</strong></div><div class="progress-stat progress-stat--words"><span class="progress-label">${esc(r.progressWords)}</span><strong>${esc(words ? String(words.saved) : '—')}</strong></div></div></div><div class="progress-chart" role="img" aria-label="${esc(r.progressChartUnavailable)}">${days}</div><span class="progress-label progress-by-domain">${esc(r.progressByDomain)}</span>${degraded}<div class="progress-domains">${cards}</div></div>${evidenceHtml(r, evidenceRows(r, summary, essays))}</section>`;
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
