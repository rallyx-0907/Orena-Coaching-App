/* Progress screen (D-091): pure data mapping, DOM-free so scripts/test_orena_screen_progress.mjs
   can exercise it without a browser. screen.js fetches, this module shapes, screen.js paints.

   Backend reality this maps to real numbers, never invents (Design Contract rule 40):
   - GET /api/learner-summary?window= (writing_coach/learner_summary.py) never claims a trend
     (every domain's growth.status is "unavailable" - no domain has a comparable measurement
     today) and tracks no daily time, no streak, no per-skill proficiency percentage. Overview's
     hero time/streak, the Skills rows' percentage+delta, the whole Trends tab and the whole
     Knowing->Using funnel have no real source anywhere in this codebase (confirmed by reading
     writing_coach/learner_summary.py and grepping for study_time/streak/minutes_studied - no
     hits). Each renders its rule-40 zero or an honest empty state; see the surface report.
   - GET /api/library/vocabulary/summary, read through product/rank.js, is the one real ladder
     position (rank/band/rankName) and real progress-to-next (mastered words vs. nextRankWords) -
     the design's "gems" is relabelled to real "words mastered", never invented.
   - Evidence/History reuse essays()/readingEvidence()/speakingAttempts() (per the brief) plus
     learner-summary's own listening observations (dated, real) to cover the one domain those
     three do not. GET /api/practice-outcomes is NOT a listening/dictation feed (confirmed by
     reading writing_coach/becoming_outcomes.py: it is grammar re-practice on an essay) - unlike
     ui/history.js, this module files it under writing rather than mislabelling it dictation. */
import { withinWindow, sortByRecency, groupByDay } from '../../product/activity-log.js';

/* Six tabs (Overview, Trends, Knowing -> Using, Evidence, Rank, History), the design's own `pgTab`
   values (orena-script.js `nav()`), as local UI state on one route - not six routes. Profile's own
   links land here with a lowercase `?tab=` (`ctx.href('progress', {}, { tab: 'history' })`,
   screens/profile/screen.js `actionHref`), matching the same lowercase-query convention Settings'
   own `tabFromQuery` already establishes. */
export const TABS = Object.freeze(['Overview', 'Trends', 'KU', 'Evidence', 'Rank', 'History']);

export function tabFromQuery(raw) {
  const value = String(raw || '').trim().toLowerCase();
  return TABS.find((tab) => tab.toLowerCase() === value) || TABS[0];
}

/* Design order: Listening, Vocabulary / Recall, Reading, Speaking, Writing (17-Progress.html). */
export const SKILL_ROWS = [
  { key: 'listening', domain: 'listening' },
  { key: 'vocabulary', domain: 'language' },
  { key: 'reading', domain: 'reading' },
  { key: 'speaking', domain: 'speaking' },
  { key: 'writing', domain: 'writing' },
];

/* No proficiency-percentage or trend-delta measure exists for any domain (learner_summary's
   growth.status is always "unavailable") - only whether the domain has recorded any activity at
   all in the window, which is real. pct/delta are always the rule-40 zero. */
export function buildSkillRows(summary) {
  const domains = summary && typeof summary === 'object' ? summary.domains || {} : {};
  return SKILL_ROWS.map(({ key, domain }) => {
    const d = domains[domain];
    const activity = d && d.activity ? d.activity : null;
    const activityCount = activity ? Number(activity.count || 0) + Number(activity.undated || 0) : 0;
    return { key, domain, activityCount, hasActivity: activityCount > 0, pct: 0, delta: null };
  });
}

/* Recognized / Recalled / Used / Transferred / Fast retrieval (P3, ORENA_DESIGN_SPEC.md
   §22/§996-3009). No owner in this codebase computes any of the five - not a partial measure,
   zero. Kept as a function (not a constant) so a future real source has one place to plug in. */
export const KU_STAGE_KEYS = ['recognized', 'recalled', 'used', 'transferred', 'fastRetrieval'];
export function buildKuStages() {
  return KU_STAGE_KEYS.map((key) => ({ key, count: 0 }));
}

/* product/rank.js's own shape, re-exposed with the "words to next rank" number the design's
   "gems" is relabelled to - never a gem count, since nothing tracks one. */
export function buildRank(rankState) {
  if (!rankState || !rankState.known || !rankState.rank) {
    return { known: false, rankName: '', band: '', mastered: 0, nextRankWords: null, nextRankName: '', progressPct: 0 };
  }
  const progressPct = !rankState.nextRankWords
    ? 100
    : Math.max(0, Math.min(100, Math.round((rankState.mastered / rankState.nextRankWords) * 100)));
  return {
    known: true,
    rankName: rankState.rankName,
    band: rankState.band,
    mastered: rankState.mastered,
    nextRankWords: rankState.nextRankWords,
    nextRankName: rankState.nextRankName,
    progressPct,
  };
}

const clip = (text, n = 90) => {
  const value = String(text || '').trim();
  return value.length > n ? `${value.slice(0, n - 1)}…` : value;
};
const firstLine = (text) => String(text || '').split('\n')[0].trim();
const roundOrNull = (value) => (Number.isFinite(Number(value)) ? Math.round(Number(value)) : null);

/* `essays` = GET /api/essays (array); `outcomes` = GET /api/practice-outcomes's `.items`. Both
   are essay-grounded, so both file under domain "writing" - the mislabel this fixes is filing
   `outcomes` as dictation/listening (see the module doc comment).

   `e.text` is never read here: GET /api/essays is the LIST route, and app.py's row_to_dict()
   unconditionally pops `text` in its non-detail branch (the only branch this route ever takes) -
   confirmed against writing_coach/persistence/learning_repository.py's _essay_payload(), which
   proves the field exists on the raw row and is stripped only at this route's serialization step.
   Only GET /api/essays/{id} (detail=True) carries it, and fetching that per row would mean one
   request per essay just to fill a list. responseText is the honest empty for essay rows, same as
   the outcomes rows two lines below already are - never a guess at text this endpoint can't send. */
export function buildWritingEvidence(essays, outcomes) {
  const fromEssays = (Array.isArray(essays) ? essays : []).map((e) => ({
    id: `essay:${e.id}`,
    at: e.created_at || null,
    domain: 'writing',
    kind: 'essay',
    essayId: e.id,
    sourceText: clip(firstLine(e.prompt)),
    responseText: '',
    score: roundOrNull(e.overall),
  }));
  const fromOutcomes = (Array.isArray(outcomes) ? outcomes : []).map((o) => ({
    id: `practice:${o.essay_id}`,
    at: o.created_at || null,
    domain: 'writing',
    kind: 'practice',
    essayId: o.essay_id,
    sourceText: clip(o.grammar_title || o.focus_label || ''),
    responseText: '',
    score: roundOrNull(o.overall),
  }));
  return [...fromEssays, ...fromOutcomes];
}

/* `reading` = GET /api/reading/practice/evidence's `.items` (writing_coach/learner_summary.py's
   own `_reading` reader confirms the field names: article_id/title/correct_count/total). Only
   attempts with at least one question answered (`total > 0`) are evidence, matching the read
   model this mirrors. */
export function buildReadingEvidence(reading) {
  return (Array.isArray(reading) ? reading : [])
    .filter((row) => Number(row.total || 0) > 0)
    .map((row) => ({
      id: `reading:${row.article_id || row.id || row.created_at}`,
      at: row.created_at || null,
      domain: 'reading',
      articleId: row.article_id || null,
      sourceText: clip(row.title),
      correct: Number(row.correct_count || 0),
      total: Number(row.total || 0),
    }));
}

/* `speaking` = GET /api/speaking/attempts's `.items`. */
export function buildSpeakingEvidence(speaking) {
  return (Array.isArray(speaking) ? speaking : []).map((a, index) => ({
    id: `speaking:${a.id || a.take_id || index}`,
    at: a.created_at || null,
    domain: 'speaking',
    assetId: a.asset_id || null,
    responseText: clip(a.transcript_text),
    score: roundOrNull(a?.dimensions?.pronunciation),
  }));
}

/* The one real, dated, per-event listening/dictation source in this codebase: learner-summary's
   own listening domain (up to 3 latest `dictation_best_match` observations, GAP-021's discipline
   already applied there - `assisted` distinguishes a revealed-then-matched line honestly). */
export function buildListeningEvidence(summary) {
  const observations = summary?.domains?.listening?.observations;
  return (Array.isArray(observations) ? observations : []).map((o, index) => ({
    id: `listening:${o.ref?.id || index}`,
    at: o.observedAt || null,
    domain: 'listening',
    score: roundOrNull(o.value),
    assisted: Boolean(o.assisted),
  }));
}

export function mergeEvidence({ writing = [], reading = [], speaking = [], listening = [] } = {}) {
  return sortByRecency([...writing, ...reading, ...speaking, ...listening]);
}

/* 'All' | 'listening' | 'speaking' | 'review' | 'reading' | 'writing' (the design's own evFilters
   order). 'review' (vocabulary recall) always empties: the backend has one lifetime aggregate
   recall count (learner-summary's `language` domain) and no dated per-event log to list - the
   honest empty state, not a fabricated row. */
export function filterEvidence(items, filter) {
  if (!filter || filter === 'All') return items;
  if (filter === 'review') return [];
  return items.filter((item) => item.domain === filter);
}

/* History tab: the same merged evidence, windowed to 30 days and grouped by day - exactly what
   the design nests Progress's History tab as (D8: "reusing the same grouped-by-day row list"). */
export function historyGroups(items, windowDays = 30, now = new Date()) {
  return groupByDay(sortByRecency(withinWindow(items, windowDays, now)), now);
}
