/* Gate for Speaking Summary's pure data mapping (static/orena/screens/speak-summary/model.js).
   No seed session data anywhere: an empty ledger is the real, drawn empty state (rule 40). */
import assert from 'node:assert/strict';
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
  assert.equal(tasks[0].note, 'Pronunciation 82 · Fluency 88');
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
