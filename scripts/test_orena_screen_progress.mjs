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
  latestMeasure,
  weekStrip,
  storyFacts,
  KU_STAGE_KEYS,
  buildRank,
  buildWritingEvidence,
  buildReadingEvidence,
  buildSpeakingEvidence,
  buildListeningEvidence,
  mergeEvidence,
  filterEvidence,
  historyGroups,
  resolveMediaEvidence,
} from '../static/orena/screens/progress/model.js';

{
  const history = [{ domain: 'listening', assetId: 'asset-a', segmentId: 'asset-a:000' }, { domain: 'speaking', assetId: 'deleted' }];
  const resolved = resolveMediaEvidence(history, { items: [{ media_object_id: 'asset-a', lesson_id: 'lesson-a' }] });
  assert.equal(resolved[0].lessonId, 'lesson-a', 'source routes use the live catalogue lesson identity');
  assert.equal(resolved[1].lessonId, null, 'missing sources are not reconstructed from history');
}
import { withinWindow, sortByRecency, dayBucket, groupByDay } from '../static/orena/product/activity-log.js';

{
  const attempts = [
    { created_at: '2026-10-01T12:00:00Z', evidence: { pronunciation: { score_kind: 'measured' } }, provenance: { pronunciation: 'stub-for-verification' }, dimensions: { pronunciation: 99 } },
    { created_at: '2026-09-29T12:00:00Z', evidence: { pronunciation: { score_kind: 'measured' } }, provenance: { pronunciation: 'provider' }, dimensions: { pronunciation: 71 } },
  ];
  assert.equal(buildSkillRows({ domains: { speaking: {} } }, attempts).find(r => r.key === 'speaking').score, 71,
    'a bounded summary must not hide an older verified server attempt');
  assert.equal(buildKuStages({ domains: { language: { activity: { countKind: 'at_least' }, observations: [{ measure: 'successful_recalls_all_time', value: 526 }] } } }).find(r => r.key === 'recalled').countLabel, '526+');
}

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

/* ---- Skills: the real recorded activity and the latest VERIFIED measure; no trend, no invented figure (D-103.4, D-108.3) ---- */
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
    assert.equal(row.score, null, `${row.key}: nothing verified recorded, so no figure`);
    assert.equal(row.pct, 0);
    assert.equal(row.delta, null, `${row.key}: no trend delta is measured`);
  }
  const empty = buildSkillRows(null);
  assert.equal(empty.length, 5, 'a failed read still renders all five rows, never fewer');
  assert.ok(empty.every((r) => r.activityCount === 0));
}
{
  // The latest verified measure per domain, from what the server holds (a real learner-summary shape).
  const obs = (measure, value, extra = {}) => ({ measure, value, synthetic: false, assisted: null, ...extra });
  const summary = {
    domains: {
      writing: { activity: { count: 28 }, observations: [obs('overall', 69.2), obs('overall', 41.8)] },
      reading: { activity: { count: 2 }, observations: [obs('comprehension_matched', { correct: 1, total: 4 }), obs('comprehension_matched', { correct: 4, total: 4 })] },
      listening: { activity: { count: 5 }, observations: [obs('dictation_best_match', 55, { assisted: true }), obs('dictation_best_match', 100, { assisted: false })] },
      speaking: { activity: { count: 50 }, observations: [obs('speaking_dimensions', { pronunciation: 84, fluency: 80 }, { producer: { pronunciation: 'stub-for-verification' } }), obs('speaking_dimensions', { pronunciation: 71, fluency: 82 }, { producer: { pronunciation: 'azure' } })] },
      language: { activity: { count: 200 }, observations: [obs('successful_recalls_all_time', 526)] },
    },
  };
  const rows = Object.fromEntries(buildSkillRows(summary).map((row) => [row.key, row]));
  assert.equal(rows.writing.score, 69, 'the newest scored review');
  assert.equal(rows.reading.score, 25, 'the newest check, correct over total');
  assert.equal(rows.listening.score, null, 'client-reported Dictation matches are activity, not verified scores');
  assert.equal(rows.speaking.score, 71, 'a stub take is not a measure: the newest one the provider measured');
  assert.equal(rows.vocabulary.score, null, 'no per-skill score exists for vocabulary');
  assert.equal(rows.vocabulary.activityCount, 200);
  const bounded = buildSkillRows({ domains: { speaking: { activity: { count: 50, countKind: 'at_least' } } } });
  assert.equal(bounded.find((row) => row.key === 'speaking').countLabel, '50+', 'a bounded scan is never presented as an exact total');
  assert.equal(rows.writing.pct, 69);
  assert.equal(latestMeasure('writing', [{ measure: 'overall', value: 90, synthetic: true }]), null, 'a synthetic observation is never shown');
  assert.equal(latestMeasure('reading', [{ measure: 'comprehension_matched', value: { correct: 0, total: 0 } }]), null);
  assert.equal(latestMeasure('speaking', [{ measure: 'speaking_dimensions', value: { pronunciation: 80 }, producer: {} }]), null, 'no producer, no verification');
  const ku = buildKuStages(summary);
  assert.equal(ku.find((s) => s.key === 'recalled').count, 526, 'the one recorded source: successful recalls');
  assert.ok(ku.filter((s) => s.key !== 'recalled').every((s) => s.count === null), 'the rest have no owner: a dash, not a zero');
}
{
  const week = weekStrip({ week: { days: [{ date: '2026-09-28', active: true, future: false }, { date: '2026-10-02', active: false, future: true }], done_days: 1 } });
  assert.deepEqual(week, [{ date: '2026-09-28', active: true, future: false }, { date: '2026-10-02', active: false, future: true }]);
  assert.deepEqual(weekStrip(null), []);
  const facts = storyFacts({ streak: { days: 3 }, week: { done_days: 2 } }, [{ key: 'writing', hasActivity: true, activityCount: 28 }, { key: 'reading', hasActivity: false, activityCount: 0 }]);
  assert.deepEqual(facts, { streak: 3, activeDays: 2, counts: [{ key: 'writing', count: 28 }] });
  assert.deepEqual(storyFacts(null, []), { streak: null, activeDays: null, counts: [] }, 'nothing recorded: nothing claimed');
}

/* ---- Knowing -> Using: only Recalled has a recorded source; fixed order ---- */
{
  assert.deepEqual(KU_STAGE_KEYS, ['recognized', 'recalled', 'used', 'transferred', 'fastRetrieval']);
  const stages = buildKuStages();
  assert.equal(stages.length, 5);
  assert.ok(stages.every((s) => s.count === null), 'with no summary no stage has a figure');
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
  const essays = [{ id: 9, created_at: '2026-09-20T10:00:00Z', prompt: 'Describe your ideal weekend\nmore', excerpt: 'Some long essay excerpt that the list route derived for the row.', language_code: 'en', overall: 82.4 }];
  const outcomes = [{ essay_id: 9, created_at: '2026-09-21T10:00:00Z', grammar_title: 'Present perfect', overall: 70 }];
  const writing = buildWritingEvidence(essays, outcomes);
  assert.equal(writing.length, 2);
  assert.ok(writing.every((w) => w.domain === 'writing'), 'practice-outcomes never mislabelled as dictation/listening');
  assert.equal(writing[0].sourceText, 'Describe your ideal weekend', 'first line only, clipped');
  assert.equal(writing[0].score, 82, 'overall rounded, not truncated to an int by chance');
  assert.equal(writing[0].responseText, 'Some long essay excerpt that the list route derived for the row.', 'the list route\'s own `excerpt` field (N-36 point 1) reaches the row, not a guess');
  assert.equal(writing[0].responseLanguage, 'en', 'the essay\'s own `language_code` reaches the row, for kit/lang.js to mark');
  assert.equal(writing[1].kind, 'practice');
  assert.equal(writing[1].responseText, '', 'GET /api/practice-outcomes carries no excerpt-worthy field - honest blank, not a guess');
  assert.equal(buildWritingEvidence(null, null).length, 0, 'a failed read is an empty list, not a crash');
}

// ---- Field-shape gate: GET /api/essays is the LIST route. app.py's row_to_dict() still pops
// `text` unconditionally in its non-detail branch (only GET /api/essays/{id}, detail=True,
// carries the full text) but now derives a short, bounded `excerpt` from it at serialization time
// (N-36 point 1, docs/project/UI_BACKEND_GAPS.md, resolved) - confirmed against
// writing_coach/persistence/learning_repository.py's _essay_payload(), which proves `text` exists
// on the raw row and is stripped, replaced by `excerpt`, only at this route's serialization step.
// This sandbox cannot capture a non-empty GET /api/essays (essays.json is `[]` - creating one
// needs the AI evaluator, which fails closed here; see fixtures/api/README.md "Not captured"), so
// fixtures/api/progress_essays_list.json is a synthetic fixture built field-for-field from
// row_to_dict's non-detail branch / _essay_payload(): every key that route actually returns
// (including the new `excerpt`), none of the keys it strips (no `text`, no `summary_vi`, no
// `*_json`).
{
  const { readFileSync } = await import('node:fs');
  const realEssays = JSON.parse(readFileSync(new URL('./fixtures/api/progress_essays_list.json', import.meta.url)));
  assert.ok(!Object.prototype.hasOwnProperty.call(realEssays[0], 'text'), 'fixture matches the real list route: GET /api/essays never sends a `text` key');
  assert.ok(Object.prototype.hasOwnProperty.call(realEssays[0], 'excerpt'), 'fixture matches the real list route: GET /api/essays now sends a bounded `excerpt` key');
  assert.notEqual(realEssays[0].excerpt, '', 'the excerpt is real derived text, not an empty placeholder');
  const writing = buildWritingEvidence(realEssays, []);
  assert.equal(writing.length, 1);
  assert.equal(writing[0].sourceText, 'Describe a challenge you overcame', 'the real `prompt` field still reaches the row title');
  assert.equal(writing[0].score, 78, 'the real `overall` field still reaches the row score');
  assert.equal(writing[0].responseText, realEssays[0].excerpt, 'the row reads the list route\'s own excerpt field, verbatim');
  assert.equal(writing[0].responseLanguage, realEssays[0].language_code, 'the row reads the essay\'s own per-item language field, verbatim');
  const modelSrc = readFileSync(new URL('../static/orena/screens/progress/model.js', import.meta.url), 'utf8');
  assert.doesNotMatch(modelSrc, /clip\(e\.text\)|e\.text\b/, 'buildWritingEvidence must not read `e.text` - the list route this screen calls never returns it (row_to_dict\'s non-detail branch pops it; only GET /api/essays/{id} carries it) - it reads `e.excerpt` instead');
  assert.match(modelSrc, /e\.excerpt/, 'buildWritingEvidence reads the list route\'s own excerpt field');
}

{
  const reading = [{ article_id: 'a1', title: 'A Morning in the City', correct_count: 3, total: 5, created_at: '2026-09-19T00:00:00Z' }, { article_id: 'a2', title: 'Zero questions', correct_count: 0, total: 0, created_at: '2026-09-19T00:00:00Z' }];
  const items = buildReadingEvidence(reading);
  assert.equal(items.length, 1, 'a session with total=0 answered nothing and is not evidence');
  assert.equal(items[0].correct, 3);
}

{
  const measured = { score_kind: 'measured', accuracy_score: 80 };
  const speaking = [
    { id: 1, created_at: '2026-09-18T00:00:00Z', transcript_text: 'the tram stop', dimensions: { pronunciation: 81.2 }, provenance: { pronunciation: 'azure' }, evidence: { pronunciation: measured }, asset_id: 'asset-1' },
    { id: 2, created_at: '2026-09-18T00:00:00Z', transcript_text: '', dimensions: {} },
    { id: 3, created_at: '2026-09-18T00:00:00Z', transcript_text: 'stub', dimensions: { pronunciation: 84 }, provenance: { pronunciation: 'stub-for-verification' }, evidence: { pronunciation: measured } },
  ];
  const items = buildSpeakingEvidence(speaking);
  assert.equal(items[0].score, 81);
  assert.equal(items[2].score, null, 'a stub-measured attempt is listed with no figure (D-108.3)');
  assert.equal(items[1].score, null, 'an unmeasured dimension is null, never a fabricated number');
}

{
  const summary = { domains: { listening: { observations: [{ ref: { id: 'x#1' }, value: 74, assisted: true, observedAt: '2026-09-17T00:00:00Z' }] } } };
  const items = buildListeningEvidence(summary);
  assert.equal(items.length, 1);
  assert.equal(items[0].assisted, true);
  assert.equal(items[0].score, null, 'the retained client-reported match must never be quoted as a real score');
  assert.equal(items[0].assetId, 'x');
  assert.equal(items[0].segmentId, '1');
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

// languages-5 / finding A: screen.js marks a writing prompt/draft, a read article's title and a
// spoken attempt's transcript with the active learning language via the shared kit/lang.js helper.
{
  const { readFileSync } = await import('node:fs');
  const screenSrc = readFileSync(new URL('../static/orena/screens/progress/screen.js', import.meta.url), 'utf8');
  assert.match(screenSrc, /import\s*\{\s*langSpan\s*\}\s*from\s*'\.\.\/\.\.\/kit\/lang\.js'/, 'imports the shared lang helper from kit/lang.js');
  assert.match(screenSrc, /langSpan\(sourceText,\s*sourceLang\)/, 'Evidence rows wrap the real source text with its own language');
  assert.match(screenSrc, /langSpan\(title,\s*titleLang\)/, 'History rows wrap the real title text with its own language');
  assert.match(screenSrc, /responseLang\s*=\s*item\.responseLanguage\s*\|\|\s*language/, 'the writing Evidence row marks its excerpt from the essay\'s own language field (N-36 point 1), falling back to the active learning language only when the essay carries none');
}

console.log('PASS Progress screen: rule-40 zero fallbacks, real rank/skills mapping, evidence/history grouping — screens/progress/model.js + product/activity-log.js');
