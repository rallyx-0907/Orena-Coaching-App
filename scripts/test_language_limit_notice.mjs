/* Target languages (D-170, D-17Q), the client's part: the server refuses a language the plan's count does not allow (403
   `language_limit_reached`); the client only says so - it opens the plans at once with the reason, in the interface
   language, from the server's own figures. It enforces nothing: it never counts languages and never decides what may be picked. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

const copy = await import('../static/orena/copy/index.js');
const { isLanguageLimit, isQuotaExhausted } = await import('../static/orena/screens/plan/quota-notice.js');

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

/* The refusal opens Plans at once, with the reason (D-17Q): a toast was too small and gone too soon. What is said comes
   from the server's own figures; the client counts and decides nothing. */
const { showLanguageLimitNotice } = await import('../static/orena/screens/plan/quota-notice.js');
const { heldReason, releaseReason } = await import('../static/orena/screens/plan/reason.js');
const { languageReasonFacts, pricingPlans } = await import('../static/orena/screens/plan/model.js');
const { languageReasonText } = await import('../static/orena/screens/plan/reason-text.js');
const { pricingMarkup } = (await import('../static/orena/screens/plan/pricing.js')).__internal;
const { href, match } = await import('../static/orena/shell/routes.js');

const PRICES = { monthly: { USD: 0, VND: 0 }, yearly: { USD: 0, VND: 0 } };
const plan = (id, rank, languagesLimit, enabled = true) => ({
  id, name: id[0].toUpperCase() + id.slice(1), description: '', rank, prices: PRICES,
  entitlements: [{ key: 'languages.target', enabled, limit: languagesLimit, window: null, unit: 'language', display_unit: 'language', scale: 1 }],
});
const PLANS = [plan('free', 0, 1), plan('plus', 1, 2), plan('pro', 2, 2)];
const commerce = (id) => ({ available: true, plan: { id, name: id } });
const list = (current) => pricingPlans({ plans: PLANS, commerce: commerce(current) });

{
  /* Where it leads, and that it navigates (no toast, nothing stored on the server). */
  const went = [];
  const ctx = { href, go: (target) => went.push(target) };
  copy.setLanguages({ ui: 'vi', support: 'en' });
  showLanguageLimitNotice(ctx, refusal(1, 1), 'zh');
  assert.deepEqual(went, ['#/plan/pricing?reason=language'], 'the refusal opens the plans with the reason in the address');
  assert.equal(match(went[0]).route.id, 'pricing');
  assert.equal(match(went[0]).query.get('reason'), 'language');
  const held = heldReason();
  assert.deepEqual([held.limit, held.owned, held.languages, held.plan, held.requested], [1, 1, ['en'], 'free', 'zh'], 'the server context, kept for the screen');

  /* Said in each language, from the server's figures: the plan and its limit, what the learner holds, what they tried to
     add, the plan that allows it. */
  const said = {};
  for (const ui of ['en', 'vi', 'zh']) {
    copy.setLanguages({ ui, support: 'en' });
    const text = languageReasonText(languageReasonFacts({ reason: held, list: list('free') }));
    said[ui] = text;
    assert.ok(!/[{}]|undefined|NaN/.test(text.title + text.text), `${ui}: every placeholder is filled`);
    assert.match(text.title, /1/, `${ui}: and its limit`);
    assert.match(text.text, /Plus/, `${ui}: names the plan that allows it`);
  }
  assert.equal(said.en.title, 'Free includes 1 target language.');
  assert.equal(said.en.text, "You're learning English. To add Chinese, upgrade to Plus. Nothing was changed.");
  assert.equal(said.vi.title, 'Gói Miễn phí gồm 1 ngôn ngữ học.');
  assert.equal(said.vi.text, 'Bạn đang học tiếng Anh. Để học thêm tiếng Trung, hãy nâng cấp lên Plus. Chưa có gì thay đổi.');
  assert.equal(said.zh.title, '免费版包含 1 种学习语言。');
  assert.equal(said.zh.text, '你正在学习英语。要加学中文，请升级到Plus。没有任何更改。');
  assert.equal(new Set([said.en.text, said.vi.text, said.zh.text]).size, 3, 'three languages');

  /* The count follows the server: a limit of 2 is plural, the nearest plan above that allows more is named, and no plan
     above says so instead of promising one. */
  copy.setLanguages({ ui: 'en', support: 'en' });
  const two = { ...held, limit: 2, owned: 2, languages: ['en', 'zh'], plan: 'plus', requested: 'vi' };
  assert.equal(languageReasonText(languageReasonFacts({ reason: two, list: list('plus') })).title, 'Plus includes 2 target languages.');
  assert.match(languageReasonText(languageReasonFacts({ reason: two, list: list('plus') })).text, /^You're learning English and Chinese\. No plan includes more target languages right now\./, 'Pro also holds 2: nothing to upgrade to');
  const roomy = pricingPlans({ plans: [PLANS[0], PLANS[1], plan('pro', 2, 5)], commerce: commerce('plus') });
  assert.match(languageReasonText(languageReasonFacts({ reason: two, list: roomy })).text, /To add Vietnamese, upgrade to Pro\./, 'the lowest plan that allows more');

  /* A plan without the entitlement (`feature_not_in_plan`): the sentence that needs no figure. */
  const notIncluded = { category: 'feature_not_in_plan', limit: null, owned: null, languages: [], plan: 'free', requested: '' };
  const none = languageReasonText(languageReasonFacts({ reason: notIncluded, list: pricingPlans({ plans: [plan('free', 0, null, false), PLANS[1]], commerce: commerce('free') }) }));
  assert.equal(none.title, "Free doesn't include adding a target language.");
  assert.match(none.text, /To add another language, upgrade to Plus\. Nothing was changed\.$/);

  /* After a reload nothing is held: the address still says why and the explanation comes from the plans alone. */
  releaseReason();
  assert.equal(heldReason(), null);
  const bare = languageReasonText(languageReasonFacts({ reason: null, list: list('free') }));
  assert.equal(bare.title, 'Free includes 1 target language.');
  assert.equal(bare.text, 'To add another language, upgrade to Plus. Nothing was changed.', 'no language is named that the server did not name');

  /* The explanation sits on top of the plans, dismissible, and only when there is one. */
  const markup = String(pricingMarkup({ plans: PLANS, commerce: commerce('free'), reason: said.en }));
  assert.ok(markup.indexOf('o-banner') < markup.indexOf('s-pricing__hero'), 'on top of the hero');
  assert.match(markup, /data-banner-close/);
  assert.ok(markup.includes(said.en.title) && markup.includes('upgrade to Plus'));
  assert.doesNotMatch(String(pricingMarkup({ plans: PLANS, commerce: commerce('free') })), /o-banner/, 'no reason, no banner');
  copy.setLanguages({ ui: 'en', support: 'en' });
}

/* Onboarding's order while the account has no learning language (D-170, review F8): the language is stored before
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

/* The two places a learner picks a target language open the plans with the reason and change nothing themselves. */
for (const screen of ['onboarding', 'settings']) {
  const source = readFileSync(new URL(`../static/orena/screens/${screen}/screen.js`, import.meta.url), 'utf8');
  assert.ok(source.includes("isLanguageLimit, showLanguageLimitNotice } from '../plan/quota-notice.js'"), `${screen}: imports the notice`);
  assert.ok(/(catch \(error\) \{|function reportTargetFailure\(error, requested = ''\) \{)[\s\S]{0,400}isLanguageLimit\(error\)\) showLanguageLimitNotice\(ctx, error, (requested|code)\)/.test(source), `${screen}: opens the plans with the reason, naming the language that was refused`);
}

console.log('test_language_limit_notice.mjs: a refused language opens the plans with the reason in EN/VI/ZH from the server figures; nothing is counted on the client: PASS');
