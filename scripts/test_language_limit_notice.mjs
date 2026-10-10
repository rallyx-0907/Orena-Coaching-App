/* Target languages (D-16R), the client's part: the server refuses a language the plan's count does not allow (403
   `language_limit_reached`); the client only says so, in the interface language, from the server's own figures, with the
   way to the plans. It enforces nothing: it never counts languages and never decides what may be picked. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

const copy = await import('../static/orena/copy/index.js');
const { isLanguageLimit, languageLimitMessage, isQuotaExhausted } = await import('../static/orena/screens/plan/quota-notice.js');

const refusal = (limit, owned) => Object.assign(new Error('x'), {
  status: 403, category: 'language_limit_reached',
  context: { feature: 'languages.target', limit, owned, languages: ['en', 'zh'].slice(0, owned), plan: 'free', upgrade: '#/plan/pricing' },
});

/* What is a language-limit refusal, and what is not. */
assert.equal(isLanguageLimit(refusal(1, 1)), true);
assert.equal(isLanguageLimit(Object.assign(new Error('x'), { status: 403, category: 'feature_not_in_plan', context: { feature: 'languages.target' } })), true, 'a plan without the entitlement');
assert.equal(isLanguageLimit(Object.assign(new Error('x'), { status: 403, category: 'feature_not_in_plan', context: { feature: 'media.import' } })), false, 'another feature is not this');
assert.equal(isLanguageLimit(Object.assign(new Error('x'), { status: 429, category: 'quota_exhausted' })), false);
assert.equal(isLanguageLimit(Object.assign(new Error('x'), { status: 503, category: 'quota_unavailable' })), false, 'an unreadable limit is a failure to retry, not a refusal');
assert.equal(isLanguageLimit(Object.assign(new Error('x'), { status: 409 })), false, 'a version conflict is the settings token, not the plan');
assert.equal(isLanguageLimit(null), false);
assert.equal(isQuotaExhausted(refusal(1, 1)), false, 'it is not a usage bucket running out');

/* Said in each language from the server's figures. */
const said = {};
for (const ui of ['en', 'vi', 'zh']) {
  copy.setLanguages({ ui, support: 'en' });
  said[ui] = [languageLimitMessage(refusal(1, 1)), languageLimitMessage(refusal(2, 2))];
}
assert.match(said.en[0], /includes 1 target language, and you already have 1\b/);
assert.match(said.en[1], /includes 2 target languages, and you already have 2\b/, 'the noun follows the limit');
for (const ui of ['en', 'vi', 'zh']) {
  for (const text of said[ui]) assert.ok(!/[{}]/.test(text), `${ui}: every placeholder is filled`);
  assert.match(said[ui][1], /2/);
}
assert.equal(new Set([said.en[0], said.vi[0], said.zh[0]]).size, 3, 'three languages');
assert.match(said.vi[0], /ngôn ngữ/);
assert.match(said.zh[0], /学习语言/);

/* No figures from the server: the sentence that needs none, never an invented number. */
copy.setLanguages({ ui: 'en', support: 'en' });
const bare = Object.assign(new Error('x'), { status: 403, category: 'feature_not_in_plan', context: { feature: 'languages.target' } });
assert.equal(languageLimitMessage(bare), 'Your plan does not include adding a target language.');
for (const ui of ['vi', 'zh']) {
  copy.setLanguages({ ui, support: 'en' });
  assert.notEqual(languageLimitMessage(bare), 'Your plan does not include adding a target language.');
}
copy.setLanguages({ ui: 'en', support: 'en' });

/* The notice itself: what the learner is told, the label of the way out, and where it leads (the plans). */
{
  const { showLanguageLimitNotice } = await import('../static/orena/screens/plan/quota-notice.js');
  const { href } = await import('../static/orena/shell/routes.js');
  const told = [];
  const went = [];
  const ctx = { href, go: (target) => went.push(target) };
  copy.setLanguages({ ui: 'vi', support: 'en' });
  showLanguageLimitNotice(ctx, refusal(2, 2), (text, options) => told.push({ text, options }));
  assert.equal(told.length, 1);
  assert.equal(told[0].text, languageLimitMessage(refusal(2, 2)));
  assert.match(told[0].text, /2/);
  assert.equal(told[0].options.undoLabel, 'Xem tất cả gói', 'the way out is worded in the interface language');
  assert.equal(went.length, 0, 'telling the refusal navigates nowhere by itself');
  told[0].options.undo();
  assert.deepEqual(went, ['#/plan/pricing'], '"See all plans" leads to the plans');
  copy.setLanguages({ ui: 'en', support: 'en' });
}

/* Onboarding's order while the account has no learning language (D-16R, review F8): the language is stored before
   anything is written to a profile, and a support pick made first is written only after that. */
{
  const { createTargetFirst } = await import('../static/orena/screens/onboarding/target-first.js');
  const run = (account) => {
    const calls = [];
    const row = { value: account };
    const gate = createTargetFirst({
      account: () => row.value,
      storeTarget: async (code) => { calls.push(`store:${code}`); row.value = { stored: true, learning_language: code }; },
      writeSupport: async (code) => { calls.push(`support:${code}`); },
    });
    return { calls, gate, row };
  };

  /* A Free learner taps a support language first, then Chinese: English is never stored, the pick follows Chinese. */
  {
    const { calls, gate } = run({ stored: true, learning_language: '' });
    assert.equal(gate.stage('vi'), true, 'the support pick is held, not written');
    assert.deepEqual(calls, []);
    assert.equal(gate.pending(), 'vi');
    await gate.store('zh');
    await gate.flush();
    assert.deepEqual(calls, ['store:zh', 'support:vi'], 'the language first, then the support language');
    assert.equal(gate.pending(), '');
    assert.equal(gate.stage('en'), false, 'once a language is stored a support pick is written at once');
  }

  /* An English learner taps a support language and goes on: English is stored first, then the pick. */
  {
    const { calls, gate } = run({ stored: true, learning_language: '' });
    gate.stage('vi');
    await gate.ensure('en');
    assert.deepEqual(calls, ['store:en', 'support:vi']);
    await gate.ensure('en');
    assert.deepEqual(calls, ['store:en', 'support:vi'], 'nothing more to store');
  }

  /* Nothing is held for an account that already has a language, or that has no settings row to keep one in. */
  for (const account of [{ stored: true, learning_language: 'zh' }, { stored: false, learning_language: '' }, null]) {
    const { calls, gate } = run(account);
    assert.equal(gate.stage('vi'), false);
    await gate.ensure('en');
    assert.deepEqual(calls, []);
  }

  /* A refused store (the plan's count) leaves the pick waiting and writes nothing. */
  {
    const calls = [];
    const gate = createTargetFirst({
      account: () => ({ stored: true, learning_language: '' }),
      storeTarget: async () => { throw refusal(1, 1); },
      writeSupport: async (code) => { calls.push(code); },
    });
    gate.stage('vi');
    await assert.rejects(() => gate.ensure('en'), (error) => isLanguageLimit(error));
    assert.deepEqual(calls, []);
    assert.equal(gate.pending(), 'vi');
  }
}

/* The two places a learner picks a target language tell the refusal and change nothing themselves. */
for (const screen of ['onboarding', 'settings']) {
  const source = readFileSync(new URL(`../static/orena/screens/${screen}/screen.js`, import.meta.url), 'utf8');
  assert.ok(source.includes("isLanguageLimit, showLanguageLimitNotice } from '../plan/quota-notice.js'"), `${screen}: imports the notice`);
  assert.ok(/(catch \(error\) \{|function reportTargetFailure\(error\) \{)[\s\S]{0,400}isLanguageLimit\(error\)\) showLanguageLimitNotice\(ctx, error\)/.test(source), `${screen}: tells the refusal`);
}

console.log('test_language_limit_notice.mjs: the language-limit refusal is told in EN/VI/ZH from the server figures; nothing is counted on the client: PASS');
