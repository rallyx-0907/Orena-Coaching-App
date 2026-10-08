/* Gate for Attempt History's pure data mapping (static/orena/screens/attempts/model.js). Imports
   only the DOM-free module - no seed data anywhere: an empty take list is the real, drawn empty
   state (rule 40), never a fixed 2-row demo. */
import assert from 'node:assert/strict';
import { chronological, statsFor, deltaLabel, rowsFor } from '../static/orena/screens/attempts/model.js';

/* Take-store shape (`product/take-store.js#recordTake`'s own stored fields), newest first. */
const TAKES = [
  { id: 'c', at: 3000, overall: 91, accuracy: 91, fluency: 94, flagged: 0 },
  { id: 'b', at: 2000, overall: 68, accuracy: 68, fluency: null, flagged: 2 },
  { id: 'a', at: 1000, overall: 60, accuracy: 60, fluency: 70, flagged: 3 },
];

/* --- empty: no seed rows, ever --- */
assert.deepEqual(statsFor([]), { count: 0, best: null, delta: null }, 'no attempt, no best (never a zero without a source)');
assert.deepEqual(rowsFor([]), []);
assert.equal(deltaLabel(null), '—', 'nothing to change from reads as the dash');

/* --- one attempt: nothing to change from --- */
assert.deepEqual(statsFor([TAKES[0]]), { count: 1, best: 91, delta: null });

/* --- chronological: newest-first store order -> oldest-first --- */
assert.deepEqual(chronological(TAKES).map((x) => x.id), ['a', 'b', 'c']);

/* --- statsFor: best is the highest of any attempt; delta is last-minus-first, not clamped --- */
{
  const stats = statsFor(TAKES);
  assert.equal(stats.count, 3);
  assert.equal(stats.best, 91);
  assert.equal(stats.delta, 91 - 60);
  assert.equal(deltaLabel(stats.delta), '+31');
}
{
  // A real regression: the change reads as a bare negative number (D5 §6 - no clamping, no colour
  // change of its own; the caller's fixed --accent tone is unconditional here, matching the
  // source's own binding).
  const regressed = [{ id: 'y', at: 2000, overall: 40, accuracy: 40 }, { id: 'x', at: 1000, overall: 70, accuracy: 70 }];
  assert.equal(deltaLabel(statsFor(regressed).delta), '-30');
}

/* --- rowsFor: newest first for display, "Attempt N" counts from the oldest, isBest/isCurrent --- */
{
  const rows = rowsFor(TAKES, 'b');
  assert.deepEqual(rows.map((r) => r.id), ['c', 'b', 'a'], 'display order is newest first');
  assert.equal(rows.find((r) => r.id === 'a').n, 1, 'the oldest attempt is Attempt 1');
  assert.equal(rows.find((r) => r.id === 'c').n, 3);
  assert.equal(rows.find((r) => r.id === 'c').isBest, true, 'attempt c scored 91, the highest');
  assert.equal(rows.find((r) => r.id === 'a').isBest, false);
  assert.equal(rows.find((r) => r.id === 'b').isCurrent, true, 'the id the caller names is marked current');
  assert.equal(rows.find((r) => r.id === 'a').isCurrent, false);
  assert.equal(rows.find((r) => r.id === 'b').hasFluency, false, 'fluency was never measured for this take (rule 40 - not a guessed 0 presented as real)');
  assert.equal(rows.find((r) => r.id === 'c').hasFluency, true);
  assert.equal(rows.find((r) => r.id === 'c').fluency, 94);
  const tone = rows.find((r) => r.id === 'a').tileColor;
  assert.equal(tone, 'var(--amber)', 'overall 60 is the weak band');
}
{
  // "Best" needs more than one attempt to be best of, and marks one row even on a tie (the newest,
  // the same attempt Scripted Pronunciation's own badge names).
  assert.ok(rowsFor([TAKES[0]]).every((r) => r.isBest === false), 'a lone attempt is not "best"');
  const tie = [{ id: 'n', at: 2, overall: 80, accuracy: 80 }, { id: 'o', at: 1, overall: 80, accuracy: 80 }];
  assert.deepEqual(rowsFor(tie).filter((r) => r.isBest).map((r) => r.id), ['n']);
  // A reopened attempt kept no accuracy: unknown, not the overall score standing in for it.
  const reopened = rowsFor([{ id: 'k', at: 1, overall: 77 }])[0];
  assert.equal(reopened.accuracy, null);
  assert.equal(reopened.overall, 77);
}
{
  // No `currentRef` given: nothing is marked current, never a guessed "first row" default.
  const rows = rowsFor(TAKES);
  assert.ok(rows.every((r) => r.isCurrent === false));
}

/* --- D-110: the account's attempts (product/speaking-history.js), only a server-verified score is shown --- */
{
  const { attemptRow, mergeAttempts } = await import('../static/orena/product/speaking-history.js');
  const server = (id, at, pronunciation, provenance, accuracy = 80) => ({
    id, take_id: `t-${id}`, created_at: new Date(at).toISOString(), asset_id: 'asset', segment_id: 'asset:000', language: 'en',
    transcript_text: 'hello', dimensions: { pronunciation, fluency: 75 },
    provenance: { pronunciation: provenance, fluency: provenance },
    evidence: { pronunciation: { score_kind: 'measured', accuracy_score: accuracy } },
  });
  const verified = attemptRow(server('v', 5000, 84.4, 'azure', 86.2));
  assert.equal(verified.verified, true);
  assert.deepEqual([verified.overall, verified.accuracy, verified.fluency], [84, 86, 75]);
  const stub = attemptRow(server('s', 4000, 84, 'stub-for-verification'));
  assert.equal(stub.verified, false);
  assert.deepEqual([stub.overall, stub.accuracy, stub.fluency], [null, null, null], 'an unverified attempt is listed, never scored');
  const notMeasured = attemptRow({ ...server('n', 3000, 70, 'azure'), evidence: { pronunciation: { score_kind: 'unmeasured' } } });
  assert.equal(notMeasured.overall, null);
  // a fresh browser has no take of its own: the account's attempts are the history
  const history = mergeAttempts([], [verified, stub]);
  assert.deepEqual(history.map((row) => row.id), ['v', 's']);
  const stats = statsFor(history);
  assert.deepEqual([stats.count, stats.best, stats.delta], [2, 84, null], 'the unverified one counts as an attempt but takes no part in best or change');
  const rows = rowsFor(history);
  assert.equal(rows.find((row) => row.id === 's').overall, null);
  assert.equal(rows.find((row) => row.id === 's').tileColor, 'var(--muted)', 'no band colour without a score');
  assert.equal(rows.find((row) => row.id === 'v').server, true);
  // a take this tab made is also stored on the server a moment later: listed once, the tab's richer copy standing
  const tab = [{ id: 'take-1', attemptId: 'v', at: 5200, overall: 90, accuracy: 90, fluency: 80 }];
  assert.deepEqual(mergeAttempts(tab, [verified]).map((row) => row.id), ['take-1']);
  assert.equal(mergeAttempts(tab, [verified])[0].overall, 84, 'server verified score takes precedence over local score');
  assert.equal(mergeAttempts([{ ...tab[0], attemptId: 's' }], [stub])[0].overall, null, 'a local score cannot override server stub provenance');
  assert.equal(mergeAttempts(tab, [])[0].overall, null, 'without server verification a local recording remains unscored in History');
  assert.equal(mergeAttempts([{ ...tab[0], attemptId: 'another' }], [verified]).length, 2, 'two quick takes must not be collapsed by their timestamps');
  assert.equal(mergeAttempts(tab, [attemptRow(server('later', 500000, 70, 'azure'))]).length, 2, 'a different attempt is another row');
}

console.log('test_orena_screen_attempts.mjs: Attempt History data mapping - rule 40 throughout (no seed rows, no guessed fluency): PASS');
