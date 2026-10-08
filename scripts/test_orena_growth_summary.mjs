/* Your growth: LearnerSummary's honest states. The backend names every domain,
 * activity label and unavailable-growth reason; the learner UI's Progress screen (test_orena_screen_progress.mjs)
 * renders the latest real measure per domain and never a trend.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { SKILL_ROWS } from '../static/orena/screens/progress/model.js';

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');

/* ---- backend: every domain, activity label and growth reason in writing_coach/learner_summary.py. */

const backend = read('../writing_coach/learner_summary.py');
const domainsLine = /DOMAINS = \(([^)]+)\)/.exec(backend);
assert.ok(domainsLine, 'learner_summary.py must define DOMAINS');
const backendDomains = [...domainsLine[1].matchAll(/'([a-z]+)'/g)].map((m) => m[1]);
assert.ok(backendDomains.length >= 5, 'the backend reports the skill domains');

const activityLabels = [...backend.matchAll(/tally\.activity\('([a-z_]+)'\)/g)].map((m) => m[1]);
assert.ok(activityLabels.length >= backendDomains.length, 'one activity label per domain reader');

// GROWTH_UNAVAILABLE is `{ domain: 'reason', ... }`; pair each key to its
// value rather than collecting every quoted word in the block, so a domain
// name that happened to also read like a reason could never be miscounted.
const reasonBlock = /GROWTH_UNAVAILABLE = \{([\s\S]*?)\}/.exec(backend)[1];
const pairs = [...reasonBlock.matchAll(/'([a-z_]+)':\s*'([a-z_]+)'/g)];
assert.equal(pairs.length, backendDomains.length, 'GROWTH_UNAVAILABLE must name a reason for every domain');
const backendReasons = [...new Set(pairs.map(([, , reason]) => reason))];

// Every domain the Progress screen reads a skill from is one the backend reports.
for (const { domain } of SKILL_ROWS) assert.ok(backendDomains.includes(domain), `Progress reads "${domain}", which learner_summary.py must report`);
assert.ok(backendReasons.length >= 1 && backendReasons.every((reason) => /^[a-z_]+$/.test(reason)), 'every unavailable-growth reason is a code, not prose');

// The achievement catalogue's own reason, named in the module docstring and
// returned literally by learner_summary(): 'no_approved_policy'. Nothing invents
// an achievement catalogue.
assert.ok(backend.includes("'no_approved_policy'"), 'the achievement reason is the real one');
console.log('growth summary: the backend names a domain, an activity label and an unavailable reason for each, and Progress reads only real domains');
