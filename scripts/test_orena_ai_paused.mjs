/* Gate for contract v11 (D-235): the system AI pause reaches every surface through one header, and voice chat is a Plus and Pro
   benefit. Pure parts are driven; each surface is pinned at its source, as the other gates here do for DOM-heavy screens. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

globalThis.document ??= { addEventListener() {}, removeEventListener() {} };
globalThis.window ??= { addEventListener() {}, removeEventListener() {}, location: { hash: '' } };

const src = (path) => readFileSync(path, 'utf8');
const RESETS = '2026-10-20T00:00:00Z';

const answer = (status, body, headers = {}) => ({
  ok: status >= 200 && status < 300,
  status,
  headers: { get: (name) => { const key = Object.keys(headers).find((k) => k.toLowerCase() === String(name).toLowerCase()); return key ? headers[key] : (String(name).toLowerCase() === 'content-type' ? 'application/json' : null); } },
  json: async () => body,
  text: async () => JSON.stringify(body),
});

// 1. The shared fetch layer reads the header once, for any route, status and body.
{
  const { request } = await import('../static/orena/infrastructure/api.js');
  const { aiPauseOf, recentAiPause, clearAiPause } = await import('../static/orena/infrastructure/ai-paused.js');
  const { pausedLineOf, pausedLineNow, isAiPaused, pausedMessage } = await import('../static/orena/screens/plan/quota-notice.js');
  const reply = (response) => { globalThis.fetch = async () => response; };

  // Reading: a 503 with the header.
  reply(answer(503, { detail: 'unavailable' }, { 'X-Orena-AI-Paused': RESETS }));
  const reading = await request('/api/reading/translate').catch((error) => error);
  assert.equal(reading.aiPaused, RESETS, 'a refused request carries the reset time on its error');
  assert.deepEqual(aiPauseOf(reading), { resetsAt: RESETS });
  assert.equal(isAiPaused(reading), true);
  assert.equal(pausedLineOf(reading), pausedMessage(RESETS), 'the line is the interface-language sentence with the time');
  assert.ok(!pausedLineOf(reading).includes('{time}'));

  // A fault: no header, no pause.
  reply(answer(503, { detail: 'unavailable' }));
  const fault = await request('/api/reading/translate').catch((error) => error);
  assert.equal(fault.aiPaused, undefined);
  assert.equal(pausedLineOf(fault), '', 'a fault is never told as a pause');

  // Listening: a 200 with the header has no error to read; the newest signal is kept for the surface that asked.
  clearAiPause();
  assert.equal(pausedLineNow(), '');
  reply(answer(200, { asset: {}, translation: 'unavailable' }, { 'X-Orena-AI-Paused': RESETS }));
  await request('/api/media/my/1');
  assert.deepEqual(recentAiPause(['/api/media/'], Date.now())?.resetsAt, RESETS);
  clearAiPause();
  reply(answer(200, { ok: true }, { 'X-Orena-AI-Paused': RESETS }));
  await request('/api/x');
  assert.equal(pausedLineNow('/api/x') !== '' || Date.now() > Date.parse(RESETS), true, 'a 200 with the header is remembered for the route that received it');
  // Keyed to the route: another surface's "unavailable" 200 is a fault, not a pause.
  clearAiPause();
  reply(answer(200, { ok: true }, { 'X-Orena-AI-Paused': RESETS }));
  await request('/api/reading/translate?x=1');
  assert.equal(recentAiPause(['/api/dictionary/word-detail']), null, 'a different route reads no pause');
  assert.equal(pausedLineNow('/api/dictionary/sentence-sheet'), '');
  assert.ok(recentAiPause('/api/reading/translate'), 'the route that carried the header does');
  // And only briefly: a pause seen ten seconds ago is not today's news for this call.
  assert.equal(recentAiPause('/api/reading/translate', Date.now() + 11000), null, 'the window is about ten seconds');
  // A fault after a pause (no header) does not erase the route rule: it simply is not asked for another route.
  reply(answer(200, { available: false }));
  await request('/api/dictionary/word-detail');
  assert.equal(recentAiPause(['/api/dictionary/word-detail']), null, 'a fault on its own route carries no header: no pause');

  // The header without a time still pauses: the line has no time to promise.
  reply(answer(429, { detail: 'x' }, { 'X-Orena-AI-Paused': '' }));
  const noTime = await request('/api/writing/review').catch((error) => error);
  assert.equal(noTime.aiPaused, '');
  assert.equal(pausedLineOf(noTime), pausedMessage(''));
  assert.ok(pausedMessage('').includes('paused for today') && !pausedMessage('').includes('{time}'));

  // The agent's own body (v10) is the same fact without the header.
  const agent = Object.assign(new Error('x'), { status: 429, category: 'daily_ai_limit', context: { resets_at: RESETS } });
  assert.equal(pausedLineOf(agent), pausedMessage(RESETS));
  // A plan limit is not a pause.
  assert.equal(pausedLineOf(Object.assign(new Error('x'), { status: 429, category: 'quota_exhausted' })), '');
  assert.equal(pausedLineOf(null), '');
}

// 2. Each surface shows the line in its own failed-request place, with no retry (pinned at the source).
{
  const reader = src('static/orena/screens/reader/screen.js');
  assert.ok(/pausedLineOf\(error\)/.test(reader) && /translationState === 'failed' && translationPause\) return html`[^`]*\$\{translationPause\}<\/p>`/.test(reader), 'Reader: the translation says the pause, with no Retry button');
  assert.ok(/summary\.state === 'failed' && summaryPause\) return html`[^`]*\$\{summaryPause\}<\/div>`/.test(reader), 'Reader: the summary says the pause, with no Retry button');
  const listening = src('static/orena/screens/listening/screen.js');
  assert.ok(/const meaningPause = pausedLineNow\(\['\/api\/media\/', '\/api\/listening'\]\)/.test(listening) && /toast\(meaningPause \|\| t\('meaningUnavailable'\)\)/.test(listening), 'Listening: a 200 with its meaning unavailable says the pause');
  const vocab = src('static/orena/screens/listening/vocab-sheet.js');
  assert.ok(/paused = pausedLineOf\(error\)/.test(vocab) && /pauseLine \? html`<div class="s-vocab__empty" role="status">/.test(vocab), 'Vocabulary Focus: the pause is said once above the terms');
  const sheet = src('static/orena/screens/quick-sheet/sheet.js');
  assert.ok(/aiPause = pausedLineOf\(error\)/.test(sheet) && /\$\{aiPause \|\| t\('noGlossNotice'\)\}/.test(sheet), 'word sheet: the pause replaces the no-gloss notice');
  assert.ok(/contextualFailed && aiPause\) return html`[^`]*\$\{aiPause\}/.test(sheet), 'word sheet: "Why here?" says the pause with no Retry');
  assert.ok(/if \(aiPause\) return html`<div class="s-qs__panel" role="status">\$\{aiPause\}<\/div>`/.test(sheet), 'sentence sheet: the Translation tab says the pause with no Retry');
  assert.ok(/sheetPause && !sheetData\.structure\.length/.test(sheet) && /sheetPause && !sheetData\.vocabulary\.length/.test(sheet), 'sentence sheet: Structure and Vocabulary say the pause');
  const writing = src('static/orena/screens/writing/screen.js');
  assert.ok(/const paused = pausedLineOf\(error\);\s+failed = paused \? \{ retry: false, paused \}/.test(writing) && /\$\{failed\.paused \|\| failed\.quota/.test(writing), 'Writing room: the pause is the review failure line, with neither retry nor plans');
  for (const room of ['respond', 'discussion', 'situation', 'free-talk', 'reading-transfer']) assert.ok(/pausedLine(Of|Now)\(/.test(src(`static/orena/screens/${room}/screen.js`)), `${room} says the pause in its own error place`);
  const react = src('static/orena/screens/react/screen.js');
  assert.ok(/resultPause = pausedLineOf\(error\)/.test(react) && /\$\{resultPause \|\| t\('coachingError'\)\}/.test(react), 'React: the pause replaces the coaching error line');
  const conversation = src('static/orena/screens/conversation/screen.js');
  assert.ok(/if \(turnPause\) return html`[^`]*\$\{turnPause\}<\/span>\$\{endButton\(\)\}<\/div>`/.test(conversation), 'Conversation: the pause replaces the reply-failed line and its retry button');
  assert.ok(/paused: pausedLineOf\(error\)/.test(conversation) && /\$\{card\.paused \|\| t\('coachingUnavailable'\)\}/.test(conversation), 'Conversation: the coaching card says the pause');
  const word = src('static/orena/screens/word/screen.js');
  assert.ok(/wordPause = pausedLineOf\(error\)/.test(word) && /s-word-empty" role="status">\$\{wordPause\}/.test(word), 'Word deep screen: the deep panel says the pause');
  const planCopy = src('static/orena/screens/plan/copy.js');
  for (const line of ['Every plan includes all reading, listening, speaking practice,', 'Mọi gói đều gồm đầy đủ luyện đọc, nghe, luyện nói,', '每个套餐都包含全部阅读、听力、口语练习、']) assert.ok(planCopy.includes(line), line);
  const api = src('static/orena/infrastructure/api.js');
  assert.ok(/aiPausedFromResponse\(response\)/.test(api) && /error\.aiPaused=aiPaused/.test(api), 'one place reads the header: the shared fetch layer');
}

// 3. Voice chat is Plus and Pro: the entitlement read, the refusal, the sheet and the copy.
{
  const { listVoices, voiceEntitled, noteVoiceEntitled } = await import('../static/orena/agent/live-voice.js');
  const { isVoiceNotInPlan } = await import('../static/orena/screens/plan/quota-notice.js');
  const voices = (body) => async () => ({ ok: true, json: async () => body });
  noteVoiceEntitled(null, 0);
  assert.equal(voiceEntitled(), null, 'unknown until read');
  const free = await listVoices('en', { fetchImpl: voices({ default: 'f-clear', voices: [], entitled: false }) });
  assert.equal(free.entitled, false);
  assert.equal(voiceEntitled(), false, 'a Free learner is known before the tap');
  const plus = await listVoices('en', { fetchImpl: voices({ default: 'f-clear', voices: [{ id: 'f-clear', gender: 'female', label: 'Clear' }], entitled: true }) });
  assert.equal(plus.entitled, true);
  assert.equal(voiceEntitled(), true);
  const older = await listVoices('en', { fetchImpl: voices({ default: 'f-clear', voices: [{ id: 'f-clear', gender: 'female', label: 'Clear' }] }) });
  assert.equal(older.entitled, null, 'a server that sends no field says nothing about the plan');
  assert.equal(voiceEntitled(), null, 'and nothing is claimed about the plan');
  const unreadable = await listVoices('en', { fetchImpl: voices({ default: 'f-clear', voices: [{ id: 'f-clear', gender: 'female', label: 'Clear' }], entitled: null }) });
  assert.equal(unreadable.entitled, null, 'null: the plan cannot be read right now - no upsell, the button stays and the answer of the server decides');
  assert.equal(voiceEntitled(), null);
  assert.equal(await listVoices('en', { fetchImpl: voices({ voices: [] }) }), null, 'voice off: no voices, no claim');
  assert.equal(voiceEntitled(Date.now() + 301000), null, 'the answer is kept for five minutes');

  // A cached `false` is confirmed with a fresh read first: a learner who has just upgraded is not shown the upsell.
  {
    const { stillNotEntitled } = await import('../static/orena/agent/live-voice.js');
    const reads = [];
    const serve = (body) => async (url) => { reads.push(url); return { ok: true, json: async () => body }; };
    noteVoiceEntitled(false);
    assert.equal(await stillNotEntitled('en', { fetchImpl: serve({ default: 'f-clear', voices: [{ id: 'f-clear', gender: 'female', label: 'Clear' }], entitled: true }) }), false, 'upgraded: no upsell');
    assert.equal(voiceEntitled(), true);
    assert.equal(reads.length, 1, 'the tap re-read GET /api/agent/voice/voices');
    noteVoiceEntitled(false);
    assert.equal(await stillNotEntitled('en', { fetchImpl: serve({ default: 'f-clear', voices: [], entitled: false }) }), true, 'still Free: the upsell');
    noteVoiceEntitled(false);
    assert.equal(await stillNotEntitled('en', { fetchImpl: serve({ default: 'f-clear', voices: [{ id: 'f-clear', gender: 'female', label: 'Clear' }], entitled: null }) }), false, 'unreadable plan: no upsell');
    noteVoiceEntitled(false);
    assert.equal(await stillNotEntitled('en', { fetchImpl: async () => { throw new Error('offline'); } }), false, 'a failed read is not "Free"');
    noteVoiceEntitled(true);
    assert.equal(await stillNotEntitled('en', { fetchImpl: async () => { throw new Error('unused'); } }), false, 'entitled: no read at all');
    // Settings draws no voice picker for the Free shape.
    const { learningRows } = await import('../static/orena/screens/settings/model.js');
    const free = await listVoices('en', { fetchImpl: serve({ default: 'f-clear', voices: [], entitled: false }) });
    assert.deepEqual(free, { default: 'f-clear', voices: [], entitled: false });
    assert.equal(learningRows({ sizeBucket: 'M', autoscroll: false, meaning: false, theme: 'system', palette: 'indigo', voices: { ...free, chosen: '' } }).some((row) => row.id === 'orenaVoice'), false, 'Settings: {entitled:false, voices:[]} shows no voice row');
  }

  const refusal = Object.assign(new Error('x'), { status: 403, category: 'feature_not_in_plan', context: { feature: 'orena.voice', plan: 'free', upgrade: '/pricing' } });
  assert.equal(isVoiceNotInPlan(refusal), true);
  assert.equal(isVoiceNotInPlan(Object.assign(new Error('x'), { status: 403, category: 'feature_not_in_plan', context: { feature: 'languages.target' } })), false, 'another feature is another notice');
  assert.equal(isVoiceNotInPlan(Object.assign(new Error('x'), { status: 403, category: 'account_deleted' })), false);
  const { VoiceSessionError, openVoiceSession } = await import('../static/orena/agent/live-voice.js');
  const refused = async () => ({ ok: false, status: 403, headers: { get: () => null }, json: async () => ({ detail: { category: 'feature_not_in_plan', retryable: false, context: { feature: 'orena.voice', plan: 'free', upgrade: '/pricing' } } }) });
  await assert.rejects(openVoiceSession({}, { fetchImpl: refused }), (error) => error instanceof VoiceSessionError && isVoiceNotInPlan(error), 'the session refusal reads as the voice-plan notice');

  const voice = src('static/orena/screens/orena/voice.js');
  assert.ok(/if \(voiceEntitled\(\) === false\) \{[\s\S]*?stillNotEntitled\([\s\S]*?showVoiceUpsell\(\)[\s\S]*?return;\s+\}\s+if \(!liveOff && startLive\(\)\) return;/.test(voice), 'every voice trigger (rows, panel, full-screen) passes the engine\'s main(): a Free learner gets the sheet before any session or cascade');
  assert.ok(/voiceEntitled\(\) === true \? false : await refreshVoiceEntitlement\(\) === false\)\) \{\s+showVoiceUpsell\(\);\s+return null;/.test(voice), 'the rail\'s mic opens the sheet, not the full-screen mode');
  assert.ok(/if \(isVoiceNotInPlan\(error\)\) \{\s+setPhase\('idle'\);\s+showVoiceUpsell\(\);/.test(voice), 'a 403 on the session opens the sheet and does not fall back to the cascade');
  assert.ok(/else if \(isVoiceNotInPlan\(error\)\) showVoiceUpsell\(\)/.test(voice), 'a 403 on a renewal opens the sheet once; the held token plays out and the session ends when it dies');
  const sheet = src('static/orena/screens/plan/voice-upsell.js');
  assert.ok(/s-mic__action--primary/.test(sheet) && /href\('pricing'\)/.test(sheet), 'the existing sheet shape, and the existing plans route');

  const copy = src('static/orena/screens/plan/copy.js');
  for (const line of [
    'Voice chat with Orena is included in Plus and Pro.', 'Trò chuyện bằng giọng nói với Orena có trong gói Plus và Pro.', '与 Orena 语音聊天包含在 Plus 和 Pro 套餐中。',
    'See plans', 'Xem các gói', '查看套餐',
    "feature_orena_voice: 'Voice chat with Orena'", "feature_orena_voice: 'Trò chuyện bằng giọng nói với Orena'", "feature_orena_voice: '与 Orena 语音聊天'",
  ]) assert.ok(copy.includes(line), line);
}

// 4. Pricing: the benefit follows the catalogue's `orena.voice` entitlement (data, not a hard-coded plan list).
{
  const { pricingPlans, compareRows, FEATURE_ORDER } = await import('../static/orena/screens/plan/model.js');
  assert.ok(FEATURE_ORDER.includes('orena.voice'));
  const entitlement = (key, extra = {}) => ({ key, enabled: true, limit: null, ...extra });
  const plans = [
    { id: 'free', rank: 0, entitlements: [entitlement('orena.message', { limit: 20 }), entitlement('orena.voice', { enabled: false })] },
    { id: 'plus', rank: 1, entitlements: [entitlement('orena.message', { limit: 200 }), entitlement('orena.voice', { limit: 1 })] },
    { id: 'pro', rank: 2, entitlements: [entitlement('orena.message', { limit: 1000 }), entitlement('orena.voice')] },
  ];
  const list = pricingPlans({ plans });
  const has = (id) => list.find((plan) => plan.id === id).features.some((feature) => feature.key === 'orena.voice');
  assert.deepEqual([has('free'), has('plus'), has('pro')], [false, true, true], 'listed for Plus and Pro, not Free');
  assert.equal(list[1].features.find((feature) => feature.key === 'orena.voice').limit, null, 'on/off with a stored limit of 1 is never drawn as a count');
  const row = compareRows(list).find((item) => item.key === 'orena.voice');
  assert.deepEqual(row.cells.map((cell) => cell.kind), ['no', 'yes', 'yes']);
  // A catalogue that does not carry it draws nothing extra.
  const bare = pricingPlans({ plans: plans.map((plan) => ({ ...plan, entitlements: plan.entitlements.filter((item) => item.key !== 'orena.voice') })) });
  assert.ok(bare.every((plan) => !plan.features.some((feature) => feature.key === 'orena.voice')));
  assert.equal(compareRows(bare).some((item) => item.key === 'orena.voice'), false);
  const copy = src('static/orena/screens/plan/copy.js');
  for (const line of ["compare_orena_voice: 'Voice chat with Orena'", "compare_orena_voice: 'Trò chuyện bằng giọng nói với Orena'", "compare_orena_voice: '与 Orena 语音聊天'"]) assert.ok(copy.includes(line), line);
}

// 4b. Admin plan editor: orena.voice is toggle-only; its stored limit of 1 is kept, never edited.
{
  const { draftOf, plansPayload } = await import('../static/orena/screens/admin/plans.js');
  const plan = { id: 'plus', prices: {}, entitlements: [
    { key: 'orena.voice', enabled: true, limit: 1, params: {} },
    { key: 'orena.message', enabled: true, limit: 200, params: {} },
  ] };
  const draft = draftOf(plan);
  const [voice, message] = draft.entitlements;
  assert.equal(voice.metered, false, 'no limit field for an on/off entitlement');
  assert.equal(message.metered, true);
  voice.enabled = false;
  const sent = plansPayload([draft]).plans[0].entitlements;
  assert.deepEqual([sent[0].enabled, sent[0].limit], [false, 1], 'the toggle is saved with its limit as the catalogue held it');
  assert.equal(sent[1].limit, 200);
}

// 5. The contract text and the code constant agree on v11.
{
  const { CONTRACT_VERSION } = await import('../static/orena/agent/contract.js');
  const text = src('docs/project/AGENT_CONTRACT.md');
  assert.equal(CONTRACT_VERSION, 11);
  assert.ok(text.includes('`contract_version: 11`'));
  assert.ok(text.includes('X-Orena-AI-Paused') && text.includes('`orena.voice`') && text.includes('"entitled": false'));
}

console.log('AI pause and voice-plan gate: ok');
