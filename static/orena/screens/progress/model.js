/* Progress maps existing server evidence into the pinned six-tab surface. Activity and streak use learner-activity; latest verified checks/reviews use learner-summary and speech attempts. Rank uses the vocabulary ladder. Time, comparable trends and unmeasured transfer stages remain explicitly unavailable. */
import { withinWindow, sortByRecency, groupByDay } from '../../product/activity-log.js';
import { attemptRow } from '../../product/speaking-history.js';

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

const isNumber = (value) => typeof value === 'number' && Number.isFinite(value);
const unverifiedProducer = (producer) => !producer || /stub|synthetic|unverified/i.test(String(producer));

/* The latest REAL, server-verified measure of one domain on a 0-100 scale, or null: the figure the Skills bar shows.
   It is a latest value, never a trend (every domain's `growth.status` is "unavailable": no comparable measure exists),
   and a domain with nothing verified has no figure at all (D-103.4, D-108.3).
   - writing: the newest scored review (`overall`);
   - listening: no verified score; client-reported Dictation accuracy is activity only;
   - reading: the newest check, correct / total;
   - speaking: the newest take whose pronunciation was measured by the provider (a stub is not a measure);
   - vocabulary: no per-skill score exists. */
export function latestMeasure(domain, observations) {
  const list = Array.isArray(observations) ? observations : [];
  for (const o of list) {
    if (o?.synthetic) continue;
    if (domain === 'writing' && o.measure === 'overall' && isNumber(o.value)) return Math.round(o.value);
    // Dictation accuracy is reported by the browser, not recomputed/verified by the server.
    // Keep the recorded activity, but never turn that value into a proficiency measure.
    if (domain === 'reading' && o.measure === 'comprehension_matched' && Number(o.value?.total) > 0) {
      return Math.round((Number(o.value.correct || 0) / Number(o.value.total)) * 100);
    }
    if (domain === 'speaking' && o.measure === 'speaking_dimensions' && isNumber(o.value?.pronunciation) && !unverifiedProducer(o.producer?.pronunciation)) {
      return Math.round(o.value.pronunciation);
    }
  }
  return null;
}

/* Per skill: the real recorded activity in the window (`activityCount`) and the latest verified measure (`score`,
   null when there is none). `pct` is the bar - the score, else 0 - and `delta` stays null: no trend is measured. */
export function buildSkillRows(summary, speakingAttempts = []) {
  const domains = summary && typeof summary === 'object' ? summary.domains || {} : {};
  return SKILL_ROWS.map(({ key, domain }) => {
    const d = domains[domain];
    const activity = d && d.activity ? d.activity : null;
    const activityCount = activity ? Number(activity.count || 0) + Number(activity.undated || 0) : 0;
    const verifiedSpeaking = domain === 'speaking' ? speakingAttempts.map(attemptRow).sort((a, b) => b.at - a.at).find(row => row.overall != null) : null;
    const score = verifiedSpeaking?.overall ?? latestMeasure(domain, d?.observations);
    const countLabel = `${activityCount}${activity?.countKind === 'at_least' ? '+' : ''}`;
    return { key, domain, activityCount, countLabel, hasActivity: activityCount > 0, score, pct: score ?? 0, delta: null };
  });
}

/* Recognized / Recalled / Used / Transferred / Fast retrieval (P3, ORENA_DESIGN_SPEC.md §22). Only "Recalled" has a
   recorded source: the learner's successful vocabulary recalls (`language` domain, `successful_recalls_all_time`). The
   other four have no owner anywhere, so their count is null - drawn as a dash, not as a zero that looks measured. */
export const KU_STAGE_KEYS = ['recognized', 'recalled', 'used', 'transferred', 'fastRetrieval'];
export function buildKuStages(summary) {
  const recalls = (summary?.domains?.language?.observations || []).find((o) => o?.measure === 'successful_recalls_all_time' && isNumber(o.value));
  return KU_STAGE_KEYS.map((key) => {
    const count = key === 'recalled' && recalls ? Math.round(recalls.value) : null;
    const bounded = summary?.domains?.language?.activity?.countKind === 'at_least';
    return { key, count, countLabel: count == null ? null : `${count}${bounded ? '+' : ''}` };
  });
}

/* The seven days of this week as the account recorded them (`GET /api/learner-activity`): a day with recorded
   activity or not - the only per-day fact that exists; no minutes. */
export function weekStrip(activity) {
  const days = Array.isArray(activity?.week?.days) ? activity.week.days : [];
  return days.map((day) => ({ date: day.date, active: Boolean(day.active), future: Boolean(day.future) }));
}

/* The story card's real figures: the streak, the days active this week, and what each skill recorded in the window. */
export function storyFacts(activity, skills) {
  return {
    streak: Number.isFinite(activity?.streak?.days) ? activity.streak.days : null,
    activeDays: Number.isFinite(activity?.week?.done_days) ? activity.week.done_days : null,
    counts: (skills || []).filter((row) => row.hasActivity).map((row) => ({ key: row.key, count: row.countLabel ?? row.activityCount })),
  };
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

   `e.excerpt` (N-36 point 1, resolved): GET /api/essays is the LIST route, and app.py's
   row_to_dict() used to pop `text` in its non-detail branch with nothing put in its place, so a
   list row carried a title only. row_to_dict()'s non-detail branch now derives a short, bounded
   `excerpt` from the stored text at serialization time (never the full text - only
   GET /api/essays/{id}, detail=True, carries that) and this is the one place this screen reads it.
   `e.language_code` is the essay's own per-row language field (present on the list item too,
   confirmed against the captured fixture) - used to mark this text's `lang` (kit/lang.js), rather
   than the screen's generic active learning language, since a kept essay could in principle predate
   a learner's current language, the same reasoning Word Detail's saved-word fallback already
   documents. Practice-outcome rows have no comparable text source (GET /api/practice-outcomes
   carries no excerpt-worthy field) and keep the honest empty (rule 40). */
export function buildWritingEvidence(essays, outcomes) {
  const fromEssays = (Array.isArray(essays) ? essays : []).map((e) => ({
    id: `essay:${e.id}`,
    at: e.created_at || null,
    domain: 'writing',
    kind: 'essay',
    essayId: e.id,
    sourceText: clip(firstLine(e.prompt)),
    responseText: e.excerpt || '',
    responseLanguage: e.language_code || '',
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
    responseLanguage: '',
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
    segmentId: a.segment_id || null,
    responseText: clip(a.transcript_text),
    // Only a server-verified score is shown (D-108.3): a stub-measured attempt is listed with no figure.
    score: attemptRow(a).overall,
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
    score: null,
    assetId: String(o.ref?.id || '').split('#')[0] || null,
    segmentId: String(o.ref?.id || '').split('#').slice(1).join('#') || null,
    assisted: Boolean(o.assisted),
  }));
}

export function mergeEvidence({ writing = [], reading = [], speaking = [], listening = [] } = {}) {
  return sortByRecency([...writing, ...reading, ...speaking, ...listening]);
}

/* History keeps the attempt. Only the current, accessible catalogue can provide its source route. */
export function resolveMediaEvidence(items, library) {
  const lessons = Array.isArray(library?.items) ? library.items : [];
  return items.map((item) => {
    if (!['speaking', 'listening'].includes(item.domain)) return item;
    const source = lessons.find((lesson) => lesson.media_object_id === item.assetId);
    return { ...item, lessonId: source?.lesson_id || null };
  });
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

/* Overview's "Next, based on evidence": the same order the agent's coaching recommendations use
   (writing_coach/agent/coaching.py `recommendations`) - due words first, then the app's one
   cross-skill cue - read from the records, never a model. A row is kept only when it can open its
   place: a listening cue names a media asset, not a lesson the app opens, so it is not listed. The
   design's duration slot stays empty: no study time is measured (rule 40). */
export function buildNextRows(vocabularySummary, cue, library) {
  const rows = [];
  const due = Number(vocabularySummary?.summary?.due) || 0;
  if (due > 0) rows.push({ key: 'review', count: due, route: 'review', params: {}, query: {} });
  const action = cue?.available === true && cue.action && typeof cue.action === 'object' ? cue.action : null;
  const evidence = typeof cue?.evidence === 'string' ? cue.evidence.trim() : '';
  if (!action) return rows;
  if (action.kind === 'review' && action.essay_id) {
    rows.push({ key: 'writing', text: evidence, route: 'writingDraft', params: { id: String(action.essay_id) }, query: {} });
  } else if (action.kind === 'reading' && action.article_id) {
    rows.push({ key: 'reading', text: evidence, route: 'reader', params: { id: `article:${action.article_id}` }, query: {} });
  } else if (action.kind === 'speaking' && action.asset_id) {
    const lessons = Array.isArray(library?.items) ? library.items : [];
    const lesson = lessons.find((item) => item.media_object_id === action.asset_id);
    if (lesson?.lesson_id) {
      rows.push({ key: 'speaking', text: evidence, route: 'attempts', params: { id: `media:${lesson.lesson_id}` }, query: action.segment_id ? { segment: action.segment_id } : {} });
    }
  }
  return rows;
}
