/* Node gate for the Progress screen's pure logic (Design Contract rule 40, D-091). Imports only
   DOM-free modules (screens/progress/model.js, product/activity-log.js) - no browser, no copy
   rendering. Covers: the rule-40 zero fallbacks (Skills percentage/delta, Knowing->Using stages),
   the writing/outcomes-under-writing mapping (not the dictation mislabel ui/history.js's own
   `outcomes` handling would produce), the Evidence "review" filter's honest empty result, and the
   day-grouping/windowing moved into product/activity-log.js. */
import assert from 'node:assert/strict';
import {
  TABS,
  tabFromQuery,
  SKILL_ROWS,
  buildSkillRows,
  buildKuStages,
  KU_STAGE_KEYS,
  buildRank,
  buildWritingEvidence,
  buildReadingEvidence,
  buildSpeakingEvidence,
  buildListeningEvidence,
  mergeEvidence,
  filterEvidence,
  historyGroups,
} from '../static/orena/screens/progress/model.js';
import { withinWindow, sortByRecency, dayBucket, groupByDay } from '../static/orena/product/activity-log.js';

/* ---- tabFromQuery: Profile's own `?tab=history` link (screens/profile/screen.js
   `actionHref`) must land on the matching tab, case-insensitively, the same convention
   Settings' own tabFromQuery already establishes ---- */
{
  assert.deepEqual(TABS, ['Overview', 'Trends', 'KU', 'Evidence', 'Rank', 'History']);
  assert.equal(tabFromQuery('history'), 'History', 'Profile\'s lowercase query resolves to the design\'s cased tab value');
  assert.equal(tabFromQuery('HISTORY'), 'History', 'case-insensitive');
  assert.equal(tabFromQuery(' evidence '), 'Evidence', 'trims');
  assert.equal(tabFromQuery(''), TABS[0], 'empty falls back to Overview');
  assert.equal(tabFromQuery('nope'), TABS[0], 'an unknown slug falls back, never throws');
  assert.equal(tabFromQuery(undefined), TABS[0]);
  assert.equal(tabFromQuery(null), TABS[0]);
}

/* ---- activity-log.js ---- */
{
  const now = new Date('2026-09-27T12:00:00Z');
  assert.equal(dayBucket('2026-09-27T08:00:00Z', now), 'today');
  assert.equal(dayBucket('2026-09-26T08:00:00Z', now), 'yesterday');
  assert.equal(dayBucket('2026-09-01T08:00:00Z', now), '2026-09-01');

  const items = [{ at: '2026-09-27T08:00:00Z' }, { at: '2026-09-01T08:00:00Z' }, { at: null }];
  const windowed = withinWindow(items, 7, now.getTime());
  assert.equal(windowed.length, 1, 'undated and out-of-window items are dropped');

  const unsorted = [{ at: '2026-09-01T00:00:00Z', id: 'old' }, { at: '2026-09-27T00:00:00Z', id: 'new' }];
  assert.deepEqual(sortByRecency(unsorted).map((i) => i.id), ['new', 'old']);

  const grouped = groupByDay(sortByRecency([{ at: '2026-09-27T09:00:00Z' }, { at: '2026-09-27T08:00:00Z' }, { at: '2026-09-25T08:00:00Z' }]), now);
  assert.equal(grouped.length, 2, 'two consecutive same-day items merge into one group');
  assert.equal(grouped[0].items.length, 2);
}

/* ---- Skills: rule 40 - real activity count, zero percentage/delta always ---- */
{
  assert.equal(SKILL_ROWS.length, 5, 'exactly the five skills the design draws');
  const summary = { domains: { listening: { activity: { count: 3, undated: 1 } }, writing: { activity: { count: 0, undated: 0 } } } };
  const rows = buildSkillRows(summary);
  const listening = rows.find((r) => r.key === 'listening');
  const writing = rows.find((r) => r.key === 'writing');
  assert.equal(listening.activityCount, 4, 'real count+undated from learner-summary');
  assert.equal(listening.hasActivity, true);
  assert.equal(writing.hasActivity, false);
  for (const row of rows) {
    assert.equal(row.pct, 0, `${row.key}: no proficiency percentage is measured, so 0`);
    assert.equal(row.delta, null, `${row.key}: no trend delta is measured`);
  }
  const empty = buildSkillRows(null);
  assert.equal(empty.length, 5, 'a failed read still renders all five rows at zero, never fewer');
  assert.ok(empty.every((r) => r.activityCount === 0));
}

/* ---- Knowing -> Using: no owner computes any stage; always zero, fixed order ---- */
{
  assert.deepEqual(KU_STAGE_KEYS, ['recognized', 'recalled', 'used', 'transferred', 'fastRetrieval']);
  const stages = buildKuStages();
  assert.equal(stages.length, 5);
  assert.ok(stages.every((s) => s.count === 0), 'every stage is the rule-40 zero, none invented');
}

/* ---- Rank: real ladder position and "words to next rank", never a fabricated gem count ---- */
{
  const known = buildRank({ known: true, rank: 4, rankName: 'Steady Walker', band: 'Explorer', mastered: 340, nextRankWords: 500, nextRankName: 'Explorer' });
  assert.equal(known.known, true);
  assert.equal(known.progressPct, 68, '340/500 -> 68%, arithmetic on real numbers, not a sample');
  const unknown = buildRank({ known: false, rank: 0 });
  assert.equal(unknown.known, false);
  assert.equal(unknown.progressPct, 0);
  const noNext = buildRank({ known: true, rank: 32, rankName: 'Top', band: 'Top', mastered: 900, nextRankWords: null, nextRankName: '' });
  assert.equal(noNext.progressPct, 100, 'no next rank above the top one means the bar reads full');
}

/* ---- Evidence: essays vs. practice-outcomes, both filed under writing (not the dictation
   mislabel: GET /api/practice-outcomes is grammar re-practice on an essay, confirmed against
   writing_coach/becoming_outcomes.py, never listening) ---- */
{
  const essays = [{ id: 9, created_at: '2026-09-20T10:00:00Z', prompt: 'Describe your ideal weekend\nmore', text: 'Some long essay text that should be clipped eventually for the row.', overall: 82.4 }];
  const outcomes = [{ essay_id: 9, created_at: '2026-09-21T10:00:00Z', grammar_title: 'Present perfect', overall: 70 }];
  const writing = buildWritingEvidence(essays, outcomes);
  assert.equal(writing.length, 2);
  assert.ok(writing.every((w) => w.domain === 'writing'), 'practice-outcomes never mislabelled as dictation/listening');
  assert.equal(writing[0].sourceText, 'Describe your ideal weekend', 'first line only, clipped');
  assert.equal(writing[0].score, 82, 'overall rounded, not truncated to an int by chance');
  assert.equal(writing[1].kind, 'practice');
  assert.equal(buildWritingEvidence(null, null).length, 0, 'a failed read is an empty list, not a crash');
}

{
  const reading = [{ article_id: 'a1', title: 'A Morning in the City', correct_count: 3, total: 5, created_at: '2026-09-19T00:00:00Z' }, { article_id: 'a2', title: 'Zero questions', correct_count: 0, total: 0, created_at: '2026-09-19T00:00:00Z' }];
  const items = buildReadingEvidence(reading);
  assert.equal(items.length, 1, 'a session with total=0 answered nothing and is not evidence');
  assert.equal(items[0].correct, 3);
}

{
  const speaking = [{ id: 1, created_at: '2026-09-18T00:00:00Z', transcript_text: 'the tram stop', dimensions: { pronunciation: 81.2 }, asset_id: 'asset-1' }, { id: 2, created_at: '2026-09-18T00:00:00Z', transcript_text: '', dimensions: {} }];
  const items = buildSpeakingEvidence(speaking);
  assert.equal(items[0].score, 81);
  assert.equal(items[1].score, null, 'an unmeasured dimension is null, never a fabricated number');
}

{
  const summary = { domains: { listening: { observations: [{ ref: { id: 'x#1' }, value: 74, assisted: true, observedAt: '2026-09-17T00:00:00Z' }] } } };
  const items = buildListeningEvidence(summary);
  assert.equal(items.length, 1);
  assert.equal(items[0].assisted, true);
  assert.equal(buildListeningEvidence(null).length, 0);
}

/* ---- Merge, filter, and the honest "review" empty (no dated per-event recall log exists) ---- */
{
  const merged = mergeEvidence({
    writing: [{ id: 'w', at: '2026-09-10T00:00:00Z', domain: 'writing' }],
    reading: [{ id: 'r', at: '2026-09-20T00:00:00Z', domain: 'reading' }],
  });
  assert.deepEqual(merged.map((i) => i.id), ['r', 'w'], 'merged and sorted most-recent-first');
  assert.equal(filterEvidence(merged, 'All').length, 2);
  assert.equal(filterEvidence(merged, 'reading').length, 1);
  assert.equal(filterEvidence(merged, 'review').length, 0, 'review always empties honestly - no fabricated row');
}

/* ---- History: 30-day window, grouped by day, reusing product/activity-log.js ---- */
{
  const now = new Date('2026-09-27T12:00:00Z');
  const items = [
    { id: 'a', at: '2026-09-27T09:00:00Z', domain: 'writing' },
    { id: 'b', at: '2026-07-01T09:00:00Z', domain: 'reading' },
  ];
  const groups = historyGroups(items, 30, now);
  assert.equal(groups.length, 1, 'the 30-day-old item falls outside the window');
  assert.equal(groups[0].key, 'today');
}

console.log('PASS Progress screen: rule-40 zero fallbacks, real rank/skills mapping, evidence/history grouping — screens/progress/model.js + product/activity-log.js');
