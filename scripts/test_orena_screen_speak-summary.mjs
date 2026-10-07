/* Gate for Speaking Summary's pure data mapping (static/orena/screens/speak-summary/model.js).
   No seed session data anywhere: an empty ledger is the real, drawn empty state (rule 40). */
import assert from 'node:assert/strict';
import { setSpeakingSessionScope, logSpeakingTask, readSpeakingSession } from '../static/orena/product/speaking-session.js';

{
  const saved = new Map();
  globalThis.window = { sessionStorage: { getItem: (key) => saved.get(key), setItem: (key, value) => saved.set(key, value) } };
  setSpeakingSessionScope('account-a:en');
  logSpeakingTask({ kind: 'free_talk', contentId: 'one' });
  assert.equal(readSpeakingSession().length, 1);
  setSpeakingSessionScope('account-a:zh');
  assert.equal(readSpeakingSession().length, 0, 'a learning-language switch must not carry the English session');
  setSpeakingSessionScope('account-b:en');
  assert.equal(readSpeakingSession().length, 0, 'a different account must not inherit the first account\'s ledger');
  setSpeakingSessionScope('account-a:en');
  assert.equal(readSpeakingSession().length, 1);
  delete globalThis.window;
}
import { tasksFor, keyImprovement } from '../static/orena/screens/speak-summary/model.js';

/* --- empty session: nothing invented --- */
assert.deepEqual(tasksFor([]), []);
assert.equal(keyImprovement([]), null);

/* --- tasksFor: real facts, joined for the row's note --- */
{
  const session = [
    { kind: 'scripted_pronunciation', contentId: 'speak:x', at: 1000, facts: [{ label: 'Pronunciation', value: 82 }, { label: 'Fluency', value: 88 }] },
  ];
  const tasks = tasksFor(session);
  assert.equal(tasks.length, 1);
  assert.equal(tasks[0].kind, 'scripted_pronunciation');
  assert.equal(tasks[0].note, '', 'local facts without server verification are not quoted as scores');
}

/* --- keyImprovement: the lowest real fact across the session, only when genuinely low --- */
{
  const session = [
    { facts: [{ label: 'Pronunciation', value: 82 }, { label: 'Fluency', value: 88 }] },
    { facts: [{ label: 'Pronunciation', value: 60 }, { label: 'Fluency', value: 0 }] },
  ];
  const worst = keyImprovement(session);
  assert.equal(worst.label, 'Fluency');
  assert.equal(worst.value, 0, 'a real, measured 0 (not fluencyMeasured) is still the honest worst score');
}
{
  // Every fact this session is already strong: nothing to flag, not a forced compliment (rule 50).
  const session = [{ facts: [{ label: 'Pronunciation', value: 92 }, { label: 'Fluency', value: 95 }] }];
  assert.equal(keyImprovement(session), null);
}
{
  // A task with no facts at all (a future writer that logs none) never crashes the reducer.
  assert.equal(keyImprovement([{ facts: [] }, { facts: undefined }]), null);
}

/* --- D-110: a fresh browser still has the day's attempts from the account --- */
{
  const row = (id, at, line, accuracy, fluency) => ({ id, at, assetId: 'asset', segmentId: `asset:${line}`, accuracy, fluency, verified: accuracy != null });
  const server = [row('a', 1000, '000', 70, 60), row('b', 2000, '000', 82, 88), row('c', 3000, '001', null, null)];
  const tasks = tasksFor([], server, { accuracy: 'Accuracy', fluency: 'Fluency' });
  assert.equal(tasks.length, 3, 'each recorded attempt is a task in both the recording tab and a fresh browser');
  assert.equal(tasks[1].note, 'Accuracy 82 · Fluency 88');
  assert.equal(tasks[2].note, '', 'an unverified attempt is a task done with no figure');
  assert.deepEqual(keyImprovement(tasks), { label: 'Fluency', value: 60 });
  const weak = tasksFor([], [row('w', 1, '000', 55, 90)], { accuracy: 'Accuracy', fluency: 'Fluency' });
  assert.deepEqual(keyImprovement(weak), { label: 'Accuracy', value: 55 });
  // the tab's own ledger entry for the same task is not counted twice
  const ledger = [{ kind: 'scripted_pronunciation', attemptId: 'b', at: 2050, facts: [{ label: 'Accuracy', value: 82 }] }];
  assert.equal(tasksFor(ledger, [row('b', 2000, '000', 82, 88)]).length, 1);
  assert.equal(tasksFor([{ ...ledger[0], attemptId: '', takeRef: 'take-b' }], [{ ...row('b', 2000, '000', 82, 88), takeId: 'take-b' }]).length, 1, 'persisted take identity deduplicates after missed notification');
  assert.equal(tasksFor([{ ...ledger[0], facts: [{ label: 'Accuracy', value: 99 }] }], [row('b', 2000, '000', null, null)])[0].note, '', 'server unverified verdict suppresses local score');
  assert.equal(tasksFor(ledger, [row('b', 2000, '000', 70, 88)])[0].note, 'Accuracy 70 · Fluency 88', 'server verified facts replace local facts');
  assert.equal(tasksFor([{ ...ledger[0], attemptId: 'different' }], [row('b', 2000, '000', 82, 88)]).length, 2, 'distinct attempts are not merged just because they happened close together');
  // another room's task stays beside it
  assert.equal(tasksFor([{ kind: 'free_talk', at: 5000, facts: [] }], [row('b', 2000, '000', 82, 88)]).length, 2);
}

/* --- D-139 HD-8: while the session has tasks only those are listed; the account's other attempts of the window are not --- */
{
  const row = (id, at, accuracy, fluency) => ({ id, at, assetId: 'asset', segmentId: 'asset:000', accuracy, fluency, verified: true });
  const ledger = [{ kind: 'scripted_pronunciation', attemptId: 'b', at: 2050, facts: [] }];
  const server = [row('a', 1000, 70, 60), row('b', 2000, 82, 88)];
  const session = tasksFor(ledger, server, undefined, { sessionOnly: true });
  assert.equal(session.length, 1, 'an earlier attempt of the window is not this session');
  assert.equal(session[0].note, 'Accuracy 82 · Fluency 88', 'the session task still takes the verified facts of the account');
  assert.equal(tasksFor([], server, undefined, { sessionOnly: true }).length, 0);
  assert.equal(tasksFor(ledger, server).length, 2, 'without the session scope the window lists every attempt');
}

/* --- every room that logs to the ledger is named, never shown as its raw kind --- */
{
  const { readFileSync, readdirSync } = await import('node:fs');
  const screens = new URL('../static/orena/screens/', import.meta.url);
  const logged = new Set();
  for (const folder of readdirSync(screens, { withFileTypes: true }).filter((entry) => entry.isDirectory())) {
    for (const file of readdirSync(new URL(`${folder.name}/`, screens)).filter((name) => name.endsWith('.js'))) {
      const source = readFileSync(new URL(`${folder.name}/${file}`, screens), 'utf8');
      for (const call of source.matchAll(/logSpeakingTask\(\{\s*kind:\s*'([a-z_]+)'/g)) logged.add(call[1]);
    }
  }
  assert.ok(logged.has('free_talk') && logged.has('situation_reaction'), `the ledger's writers are found (${[...logged]})`);
  const summary = readFileSync(new URL('speak-summary/screen.js', screens), 'utf8');
  const labelled = new Set([...summary.matchAll(/^\s+([a-z_]+): \(\) =>/gm)].map((match) => match[1]));
  for (const kind of logged) assert.ok(labelled.has(kind), `Speaking Summary names the "${kind}" task instead of showing its key`);
}

console.log('test_orena_screen_speak-summary.mjs: Speaking Summary data mapping - real session ledger, rule 40 and rule 50 throughout (no fabricated evidence split, no forced compliment): PASS');
