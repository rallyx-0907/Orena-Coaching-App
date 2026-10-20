import assert from 'node:assert/strict';
globalThis.window = { localStorage: { getItem: () => null } };
Object.defineProperty(globalThis, 'navigator', { value: { language: 'en', languages: ['en'] } });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };
const { controlPage, issueHref } = await import('../static/orena/screens/admin/control-pages.js');
const { href } = await import('../static/orena/shell/routes.js');
const { mediaProcessingOutcome } = await import('../static/orena/capabilities/admin-imports.js');
const { mediaPage } = await import('../static/orena/screens/admin/imports-pages.js');
const { t } = await import('../static/orena/screens/admin/copy.js');
const heldImport = mediaPage({ media: { language: 'en', items: [{ title: 'Held media', state: 'review', contentId: 'held-media', has_transcript: true }] }, t, ui: 'en', href });
assert.ok(String(heldImport.markup).includes('1 of 1 imported'), 'an imported item awaiting rights review is not a failed import');
assert.equal(mediaProcessingOutcome({ record: { status: 'processing', processing: { state: 'running', stage: 'transcribe' } }, transcript: { segment_count: 0 } }).state, 'processing');
assert.equal(mediaProcessingOutcome({ record: { status: 'review', processing: { state: 'held' } }, transcript: { segment_count: 6 } }).state, 'review');
assert.equal(mediaProcessingOutcome({ record: { status: 'published', processing: { state: 'ready' } }, transcript: { segment_count: 6 } }).has_transcript, true);
assert.equal(mediaProcessingOutcome({ record: { status: 'published' }, transcript: { segment_count: 0 } }).state, 'published');
assert.equal(mediaProcessingOutcome({ record: { status: 'archived' } }).state, 'archived');
assert.equal(issueHref({ kind: 'transcript_missing' }, href), href('adminMedia'));
assert.equal(issueHref({ kind: 'import_failed' }, href), href('adminJobs', {}, { status: 'failed' }));
assert.equal(issueHref({ section: 'ai', subject: 'writing_evaluate' }, href), href('adminCapability', { id: 'writing_evaluate' }));
const overview = controlPage('adminOverview', {
  overview: { accounts: { available: false, total: 99 }, activity: { available: true, active_7d: 4 }, content: { published: 3 }, attention: [] },
}, { href });
assert.ok(String(overview.markup).includes('Unavailable'));
assert.ok(!String(overview.markup).includes('>99<'), 'unavailable account data must not be presented as known');
const detail = controlPage('adminUser', { detail: { display_name: '<unsafe>', email_masked: 'a***@example.org', profiles: [], activity: [] } }, { href });
assert.ok(String(detail.markup).includes('&lt;unsafe&gt;'));
assert.ok(String(detail.markup).includes('Private learner content'));
const operations = controlPage('adminOperations', { runtime: { ai: { learner_runtime_mode: 'legacy' } }, telemetry: { has_data: false } }, { href });
assert.ok(String(operations.markup).includes('not active'));
assert.ok(!String(operations.markup).includes('24 h'));
const errors = controlPage('adminErrors', { overview: { available: false } }, { href });
assert.ok(String(errors.markup).includes('Unavailable'));
console.log('Admin control-center rendering and truthful state checks passed');

/* D-154: an account's role and plan, set by hand. */
{
  const { membershipBlock } = await import('../static/orena/screens/admin/control-pages.js');
  const plans = [{ id: 'free', name: 'Free', rank: 0 }, { id: 'plus', name: 'Plus', rank: 1 }, { id: 'pro', name: 'Pro', rank: 2 }];
  const account = { id: 'u1', user_key: 'k', email: 'a@example.org', role: 'user', plan_id: 'plus', status: 'active', provider: 'manual', until: '2026-12-31T23:59:59+00:00' };
  const view = { account, plans, draft: { role: 'user', plan_id: 'plus', until: '2026-12-31' }, error: '', status: '', busy: false, self: false };
  const markup = String(membershipBlock(view));
  assert.ok(markup.includes('data-field="mbRole"') && markup.includes('data-field="mbPlan"'), 'role and plan choices are drawn');
  assert.equal((markup.match(/data-field="mbPlan"/g) || []).length, 3, 'the three plans');
  assert.ok(markup.includes('type="date"') && markup.includes('value="2026-12-31"'), 'a paid plan offers an end date');
  assert.ok(markup.includes('data-a="membership-save"'));
  assert.ok(!String(membershipBlock({ ...view, draft: { ...view.draft, plan_id: 'free' } })).includes('type="date"'), 'Free has no end date');
  assert.ok(String(membershipBlock({ ...view, self: true })).match(/data-field="mbRole"[^>]*disabled/), 'your own role is not editable');
  assert.equal(membershipBlock(null), '', 'no membership read draws nothing');
  const { membershipChange } = await import('../static/orena/screens/admin/control.js');
  assert.deepEqual(membershipChange(view), {}, 'nothing changed sends nothing');
  assert.deepEqual(membershipChange({ ...view, draft: { role: 'admin', plan_id: 'pro', until: '' } }), { role: 'admin', plan_id: 'pro' });
  assert.deepEqual(membershipChange({ ...view, draft: { role: 'user', plan_id: 'pro', until: '2027-01-15' } }), { plan_id: 'pro', until: '2027-01-15T23:59:59Z' });
  assert.deepEqual(membershipChange({ ...view, draft: { role: 'user', plan_id: 'free', until: '2027-01-15' } }), { plan_id: 'free' });
  console.log('Admin account role and plan: PASS');
}

/* Review fixes: an ended manual plan reads as Free, a stored "premium" as Pro. */
{
  const { membershipBlock } = await import('../static/orena/screens/admin/control-pages.js');
  const plans = [{ id: 'free', name: 'Free', rank: 0 }, { id: 'plus', name: 'Plus', rank: 1 }, { id: 'pro', name: 'Pro', rank: 2 }];
  const base = { id: 'u1', user_key: 'k', email: 'a@example.org', role: 'user', status: 'active' };
  const ended = String(membershipBlock({ account: { ...base, plan_id: 'plus', provider: 'manual', until: '2020-01-01T00:00:00+00:00' }, plans, draft: { role: 'user', plan_id: 'free', until: '' } }));
  assert.match(ended, /manual plan ended/);
  assert.doesNotMatch(ended, /until /, 'an ended plan shows no end date');
  const legacy = String(membershipBlock({ account: { ...base, plan_id: 'premium', provider: 'polar' }, plans, draft: { role: 'user', plan_id: 'pro', until: '' } }));
  assert.match(legacy, /Now: Pro/);
  console.log('Admin account plan: ended and legacy plans read as the server applies them: PASS');
}

/* The system AI ceiling's notice on the overview: nothing below the warning, a warning strip at it, paused at 100%. */
{
  const base = { overview: { accounts: { available: true, total: 3 }, activity: { available: true, active_7d: 1 }, content: {}, attention: [] } };
  const ceiling = { ceiling_usd: 5, spent_usd: 0, ratio: 0, warned: false, reached: false, readable: true, resets_at: '2026-10-20T00:00:00+00:00' };
  const page = (system) => String(controlPage('adminOverview', { ...base, spend: system ? { system, agent: { cap_usd: null } } : null }, { href }).markup);
  for (const none of [page(null), page(ceiling), page({ ...ceiling, spent_usd: 3.9, ratio: 0.78 }), page({ ceiling_usd: null })]) {
    assert.ok(!none.includes('a-banner'), 'below the warning ratio (or with no ceiling) the overview draws no spend notice');
  }
  const warned = page({ ...ceiling, spent_usd: 4.0, ratio: 0.8, warned: true });
  assert.ok(warned.includes('data-tone="warn"') && warned.includes('AI spend today $4.00 of $5.00 - 80% reached'), 'the warning at 80%');
  const paused = page({ ...ceiling, spent_usd: 5.01, ratio: 1.002, warned: true, reached: true });
  assert.ok(paused.includes('data-tone="err"') && paused.includes('AI spend alert: $5.01 of $5.00 today') && !paused.includes('80% reached'), 'a high-severity alert at 100%');
  assert.ok(paused.includes('AI keeps running') && !paused.includes('AI paused'), 'D-250: the monitor never says AI is paused');
  assert.ok(!paused.includes('Invalid Date'));
  console.log('Admin AI spend ceiling notice checks passed');
}
