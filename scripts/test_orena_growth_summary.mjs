/* Your growth: LearnerSummary's honest states, rendered without inventing a
 * new one. Two halves, because either alone is useless: a backend that names
 * a reason nobody translates, or a frontend that renders a state the backend
 * never actually returns.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { GROWTH_DOMAINS, growthDomainRow, growthSummarySection } from '../static/orena/ui/growth-summary.js';
import { copy } from '../static/orena/ui/copy.js';
import { esc } from '../static/orena/ui/html.js';

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');

/* ---- backend: every domain, activity label and growth reason this renders
   from must actually exist in writing_coach/learner_summary.py, and every
   one of those must have a translation - in both directions. */

const backend = read('../writing_coach/learner_summary.py');
const domainsLine = /DOMAINS = \(([^)]+)\)/.exec(backend);
assert.ok(domainsLine, 'learner_summary.py must define DOMAINS');
const backendDomains = [...domainsLine[1].matchAll(/'([a-z]+)'/g)].map((m) => m[1]);
assert.deepEqual([...GROWTH_DOMAINS].sort(), [...backendDomains].sort(), 'growth-summary.js must render exactly the domains the backend reports');

const activityLabels = [...backend.matchAll(/tally\.activity\('([a-z_]+)'\)/g)].map((m) => m[1]);
assert.ok(activityLabels.length >= backendDomains.length, 'one activity label per domain reader');

// GROWTH_UNAVAILABLE is `{ domain: 'reason', ... }`; pair each key to its
// value rather than collecting every quoted word in the block, so a domain
// name that happened to also read like a reason could never be miscounted.
const reasonBlock = /GROWTH_UNAVAILABLE = \{([\s\S]*?)\}/.exec(backend)[1];
const pairs = [...reasonBlock.matchAll(/'([a-z_]+)':\s*'([a-z_]+)'/g)];
assert.equal(pairs.length, backendDomains.length, 'GROWTH_UNAVAILABLE must name a reason for every domain');
const backendReasons = [...new Set(pairs.map(([, , reason]) => reason))];

for (const ui of ['en', 'zh']) {
  const c = copy[ui];
  for (const domain of backendDomains)
    assert.ok(c['growthDomain_' + domain], `${ui}: growthDomain_${domain}`);
  for (const label of activityLabels)
    assert.ok(c['growthActivity_' + label], `${ui}: growthActivity_${label}`);
  for (const reason of backendReasons)
    assert.ok(c['growthReason_' + reason], `${ui}: growthReason_${reason}`);
  for (const key of [
    'growthTitle', 'growthNote', 'growthUnavailable', 'growthPartialNote', 'growthEmptyDomain',
    'growthAtLeast', 'growthNoTrendYet', 'growthAchievements', 'growthAchievementsUnavailable',
    'growthDomainUnavailable',
  ])
    assert.ok(c[key], `${ui}: ${key}`);
}

// The achievement catalogue's own reason, named in the module docstring and
// returned literally by learner_summary(): 'no_approved_policy'. Nothing here
// invents an achievement catalogue - the copy exists, the surface never
// renders a list of items.
assert.ok(backend.includes("'no_approved_policy'"), 'the achievement reason this renders must be the real one');
assert.ok(!/achievementItems|achievementList/.test(read('../static/orena/ui/growth-summary.js')), 'no invented achievement list rendering');

/* ---- frontend: every state the backend can actually return, honestly ----- */

const en = copy.en;

// An owner read that failed: distinguished from "nothing happened yet".
{
  const { label, value } = growthDomainRow(en, 'writing', { status: 'unavailable' });
  assert.equal(label, 'Writing');
  assert.equal(value, esc(en.growthDomainUnavailable));
}
assert.deepEqual(growthDomainRow(en, 'writing', undefined), growthDomainRow(en, 'writing', { status: 'unavailable' }),
  'a domain absent from the response reads exactly as unavailable, never as empty');

// A domain with genuinely nothing recorded.
{
  const { value } = growthDomainRow(en, 'reading', {
    status: 'empty', activity: { count: 0, undated: 0, countKind: 'exact', label: 'checks_answered' },
    growth: { status: 'unavailable', reason: 'assistance_mode_unrecorded' },
  });
  assert.equal(value, esc(en.growthEmptyDomain));
}

// Ordinary activity, exact count.
{
  const { value } = growthDomainRow(en, 'writing', {
    status: 'current', activity: { count: 35, undated: 0, countKind: 'exact', label: 'submitted_versions' },
    growth: { status: 'unavailable', reason: 'assistance_mode_unrecorded' },
  });
  assert.equal(value, '35 versions submitted');
}

// A single record inflects correctly in English ("1 check answered"), and a
// count word that does not inflect (Chinese) is unaffected either way.
{
  const domain = {
    status: 'current', activity: { count: 1, undated: 0, countKind: 'exact', label: 'checks_answered' },
    growth: { status: 'unavailable', reason: 'assistance_mode_unrecorded' },
  };
  assert.equal(growthDomainRow(en, 'reading', domain).value, esc('1 check answered'));
  assert.equal(growthDomainRow(copy.zh, 'reading', domain).value, esc('1 次完成的检测'));
}

// A read that filled its bound: shown as a lower bound, never as the exact
// count the domain happens to report - the caller cannot know whether there
// is more.
{
  const { value } = growthDomainRow(en, 'listening', {
    status: 'current', activity: { count: 100, undated: 0, countKind: 'at_least', label: 'lines_reconstructed' },
    growth: { status: 'unavailable', reason: 'no_repeated_comparable_measure' },
  });
  assert.equal(value, 'at least 100 lines reconstructed');
}

// Grammar completion carries no timestamp at all (learner_summary.py's
// `_grammar` calls `tally.add(None)` for every completed pattern) - the count
// is always 0 and the total lives entirely in `undated`. This must still be
// shown as real activity, not as "nothing yet".
{
  const { value } = growthDomainRow(en, 'grammar', {
    status: 'current', activity: { count: 0, undated: 12, countKind: 'exact', label: 'patterns_marked_complete' },
    growth: { status: 'unavailable', reason: 'no_measure' },
  });
  assert.equal(value, '12 patterns marked complete', 'undated activity must not be dropped');
}

// The reason a domain has no trend is shown as a hint on the label, in the
// domain's own words - never a bare, untranslated code leaking through.
{
  const { label } = growthDomainRow(en, 'speaking', {
    status: 'current', activity: { count: 8, undated: 0, countKind: 'exact', label: 'takes' },
    growth: { status: 'unavailable', reason: 'assistance_mode_unrecorded' },
  });
  assert.ok(label.includes('Speaking'));
  assert.ok(label.includes(esc(en.growthReason_assistance_mode_unrecorded)), 'the reason must be human words, not a code');
  assert.ok(!label.includes('assistance_mode_unrecorded'), 'the raw reason code must never reach the learner');
}

/* ---- the whole section: never claims more than LearnerSummary said ------ */

// No fetch, or the read failed entirely: distinguished from every domain
// individually failing (which is `outcome: partial`).
{
  const html = growthSummarySection({ c: en, growth: null });
  assert.ok(html.includes(en.growthUnavailable));
  assert.ok(!html.includes(en.growthAchievements), 'nothing else is claimed when the read itself failed');
}

const fixture = (outcome, overrides = {}) => ({
  policyVersion: 'learner-summary/1',
  outcome,
  unavailableDomains: [],
  truncatedDomains: [],
  domains: {
    writing: { status: 'current', activity: { count: 35, undated: 0, countKind: 'exact', label: 'submitted_versions' }, growth: { status: 'unavailable', reason: 'assistance_mode_unrecorded' } },
    reading: { status: 'empty', activity: { count: 0, undated: 0, countKind: 'exact', label: 'checks_answered' }, growth: { status: 'unavailable', reason: 'assistance_mode_unrecorded' } },
    listening: { status: 'current', activity: { count: 5, undated: 0, countKind: 'exact', label: 'lines_reconstructed' }, growth: { status: 'unavailable', reason: 'no_repeated_comparable_measure' } },
    speaking: { status: 'current', activity: { count: 8, undated: 0, countKind: 'exact', label: 'takes' }, growth: { status: 'unavailable', reason: 'assistance_mode_unrecorded' } },
    grammar: { status: 'empty', activity: { count: 0, undated: 0, countKind: 'exact', label: 'patterns_marked_complete' }, growth: { status: 'unavailable', reason: 'no_measure' } },
    language: { status: 'empty', activity: { count: 0, undated: 0, countKind: 'exact', label: 'phrases_kept' }, growth: { status: 'unavailable', reason: 'no_measure' } },
    ...overrides,
  },
  achievements: { status: 'unavailable', reason: 'no_approved_policy', items: [] },
});

// Everything read cleanly: no partial-read note.
{
  const html = growthSummarySection({ c: en, growth: fixture('current') });
  assert.ok(!html.includes(en.growthPartialNote));
  assert.ok(html.includes('35 versions submitted'));
  assert.ok(html.includes(en.growthAchievementsUnavailable), 'achievements must always say unavailable - there is no approved policy');
}

// One or more owners failed: the note is shown, and the domain that failed
// says so specifically rather than looking like zero activity.
{
  const html = growthSummarySection({
    c: en,
    growth: fixture('partial', { speaking: { status: 'unavailable' } }),
  });
  assert.ok(html.includes(en.growthPartialNote));
  assert.ok(html.includes(esc(en.growthDomainUnavailable)));
}

// EN and ZH both render without a raw domain/reason key leaking through, for
// every real state the backend can produce.
for (const ui of ['en', 'zh']) {
  const html = growthSummarySection({ c: copy[ui], growth: fixture('current') });
  for (const domain of backendDomains) assert.ok(!html.includes(`growthDomain_${domain}`));
  for (const reason of backendReasons) assert.ok(!html.includes(reason), `${ui}: raw reason "${reason}" leaked`);
}

console.log('growth summary: LearnerSummary states rendered honestly, EN/ZH complete, no invented achievement list');
