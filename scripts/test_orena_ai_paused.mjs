/* Gate for contract v11 (D-235): the system AI pause reaches every surface through one header, and voice chat is a Plus and Pro
   benefit. Pure parts are driven; each surface is pinned at its source, as the other gates here do for DOM-heavy screens. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

globalThis.document ??= { addEventListener() {}, removeEventListener() {} };
globalThis.window ??= { addEventListener() {}, removeEventListener() {}, location: { hash: '' } };

const src = (path) => readFileSync(path, 'utf8');
// The next UTC midnight, so the reset time is always in the future (a fixed date expired on 2026-10-20 and broke CI).
const RESETS = (() => { const d = new Date(); d.setUTCHours(24, 0, 0, 0); return d.toISOString().replace('.000Z', 'Z'); })();

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

// 1b. PR-MON-7B2a: a sheet or reading room whose AI help is a plan meter says the meter's own sentence, in the same place
// and with no Retry, when the allowance is spent; the pause still wins; a fault is still nothing.
{
  const { refusalLineOf, pausedMessage } = await import('../static/orena/screens/plan/quota-notice.js');
  const spent = (feature) => Object.assign(new Error('x'), { status: 429, category: 'quota_exhausted', context: { feature, used: 30, limit: 30 } });
  assert.equal(refusalLineOf(spent('word.assist')), 'You have used 30 of 30 word explanations today.');
  assert.equal(refusalLineOf(spent('reading.assist')), 'You have used 30 of 30 reading helps today.');
  assert.equal(refusalLineOf(spent('writing.task')), 'You have used 30 of 30 writing prompts today.');
  const paused = Object.assign(spent('word.assist'), { aiPaused: RESETS });
  assert.equal(refusalLineOf(paused), pausedMessage(RESETS), 'the system pause is told first');
  assert.equal(refusalLineOf(Object.assign(new Error('x'), { status: 503 })), '', 'a fault is never a plan line');
  assert.equal(refusalLineOf(null), '');
}

// 2. Each surface shows the line in its own failed-request place, with no retry (pinned at the source).
{
  const reader = src('static/orena/screens/reader/screen.js');
  assert.ok(/refusalLineOf\(error\)/.test(reader) && /translationState === 'failed' && translationPause\) return html`[^`]*\$\{translationPause\}<\/p>`/.test(reader), 'Reader: the translation says the pause, with no Retry button');
  assert.ok(/summary\.state === 'failed' && summaryPause\) return html`[^`]*\$\{summaryPause\}<\/div>`/.test(reader), 'Reader: the summary says the pause, with no Retry button');
  const listening = src('static/orena/screens/listening/screen.js');
  assert.ok(/const meaningPause = pausedLineNow\(\['\/api\/media\/', '\/api\/listening'\]\)/.test(listening) && /toast\(meaningPause \|\| t\('meaningUnavailable'\)\)/.test(listening), 'Listening: a 200 with its meaning unavailable says the pause');
  const vocab = src('static/orena/screens/listening/vocab-sheet.js');
  assert.ok(/paused = refusalLineOf\(error\)/.test(vocab) && /pauseLine \? html`<div class="s-vocab__empty" role="status">/.test(vocab), 'Vocabulary Focus: the pause is said once above the terms');
  const sheet = src('static/orena/screens/quick-sheet/sheet.js');
  assert.ok(/aiPause = refusalLineOf\(error\)/.test(sheet) && /sheetPause = refusalLineOf\(error\)/.test(sheet) && /\$\{aiPause \|\| t\('noGlossNotice'\)\}/.test(sheet), 'word sheet: the pause replaces the no-gloss notice');
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
  assert.ok(/wordPause = refusalLineOf\(error\)/.test(word) && /s-word-empty" role="status">\$\{wordPause\}/.test(word), 'Word deep screen: the deep panel says the pause');
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
  const model = await import('../static/orena/screens/plan/model.js');
  const { pricingPlans, compareRows, FEATURE_ORDER } = model;
  assert.ok(FEATURE_ORDER.includes('orena.voice'));
  const entitlement = (key, extra = {}) => ({ key, enabled: true, limit: null, ...extra });
  const plans = [
    { id: 'free', rank: 0, entitlements: [entitlement('orena.message', { limit: 20 }), entitlement('orena.voice', { enabled: false })] },
    { id: 'plus', rank: 1, entitlements: [entitlement('orena.message', { limit: 200 }), entitlement('orena.voice', { limit: 900, unit: 'second', display_unit: 'minute', scale: 60, window: 'day' })] },
    { id: 'pro', rank: 2, entitlements: [entitlement('orena.message', { limit: 1000 }), entitlement('orena.voice', { limit: 900, unit: 'second', display_unit: 'minute', scale: 60, window: 'day' })] },
  ];
  const list = pricingPlans({ plans });
  const has = (id) => list.find((plan) => plan.id === id).features.some((feature) => feature.key === 'orena.voice');
  assert.deepEqual([has('free'), has('plus'), has('pro')], [false, true, true], 'listed for Plus and Pro, not Free');
  assert.equal(list[1].features.find((feature) => feature.key === 'orena.voice').limit, 15, 'D-237: a metered benefit, 900 stored seconds shown as 15 minutes');
  const row = compareRows(list).find((item) => item.key === 'orena.voice');
  assert.deepEqual(row.cells.map((cell) => cell.kind), ['no', 'limit', 'limit'], 'a figure, not a tick');
  assert.deepEqual([row.cells[1].value, row.cells[1].unit], [15, 'minute']);
  assert.equal(model.BOOLEAN_FEATURES, undefined, 'no on/off allowlist is left');
  // The plan line, in the three languages.
  const copy4 = src('static/orena/screens/plan/copy.js');
  for (const line of ["line_orena_voice_day: '{n} min a day of voice chat with Orena'", "line_orena_voice_day: '{n} phút/ngày trò chuyện bằng giọng nói với Orena'", "line_orena_voice_day: '每天 {n} 分钟与 Orena 语音聊天'",
    "line_orena_voice_month: '{n} min a month of voice chat with Orena'", "line_orena_voice_month: '{n} phút/tháng trò chuyện bằng giọng nói với Orena'", "line_orena_voice_month: '每月 {n} 分钟与 Orena 语音聊天'"]) assert.ok(copy4.includes(line), line);
  // D-248 (MV2-6a): the plan line's window is the catalogue's, carried on each feature.
  assert.equal(list[1].features.find((feature) => feature.key === 'orena.voice').window, 'day');
  const monthly = pricingPlans({ plans: [{ id: 'plus', rank: 1, entitlements: [entitlement('orena.voice', { limit: 6000, scale: 60, display_unit: 'minute', window: 'month' })] }] });
  assert.deepEqual(monthly[0].features[0], { key: 'orena.voice', limit: 100, window: 'month' });
  const pricingSource = src('static/orena/screens/plan/pricing.js');
  assert.ok(/windowedKey\(`line_\$\{suffix\}`, feature\.window\)/.test(pricingSource), 'Plans reads the window from the feature');
  // Plan & usage draws a voice meter in minutes when the commerce read reports it.
  const usage = model.usageRows({ features: { 'orena.voice': { limit: 900, used: 300, scale: 60, display_unit: 'minute', window: 'day', usage_state: 'known', entitlement_state: 'known', resets_at: '2026-10-20T00:00:00Z' } } });
  assert.deepEqual([usage[0].key, usage[0].used, usage[0].limit, usage[0].unit], ['orena.voice', 5, 15, 'minute']);
  // A catalogue that does not carry it draws nothing extra.
  const bare = pricingPlans({ plans: plans.map((plan) => ({ ...plan, entitlements: plan.entitlements.filter((item) => item.key !== 'orena.voice') })) });
  assert.ok(bare.every((plan) => !plan.features.some((feature) => feature.key === 'orena.voice')));
  assert.equal(compareRows(bare).some((item) => item.key === 'orena.voice'), false);
  const copy = src('static/orena/screens/plan/copy.js');
  for (const line of ["compare_orena_voice: 'Voice chat with Orena'", "compare_orena_voice: 'Trò chuyện bằng giọng nói với Orena'", "compare_orena_voice: '与 Orena 语音聊天'"]) assert.ok(copy.includes(line), line);
}

// 4b. Admin plan editor: orena.voice is a normal metered row in minutes; the stored seconds round-trip.
{
  const { draftOf, plansPayload } = await import('../static/orena/screens/admin/plans.js');
  const plan = { id: 'plus', prices: {}, entitlements: [
    { key: 'orena.voice', enabled: true, limit: 900, window: 'day', unit: 'second', display_unit: 'minute', scale: 60, params: {} },
    { key: 'orena.message', enabled: true, limit: 200, params: {} },
  ] };
  const draft = draftOf(plan);
  const [voice, message] = draft.entitlements;
  assert.equal(voice.metered, true, 'a limit field like any metered row');
  assert.equal(voice.limit, '15', 'shown in minutes');
  assert.equal(message.limit, '200');
  assert.equal(plansPayload([draft]).plans[0].entitlements[0].limit, 900, 'unedited: the stored seconds come back');
  voice.limit = '20';
  assert.equal(plansPayload([draft]).plans[0].entitlements[0].limit, 1200, 'typed minutes are stored as seconds');
  voice.limit = '7.5';
  assert.equal(plansPayload([draft]).plans[0].entitlements[0].limit, 450);
  voice.enabled = false;
  assert.equal(plansPayload([draft]).plans[0].entitlements[0].enabled, false, 'the toggle still saves');
  // A stored voice limit under one minute (the old on/off 1) is read as the plan's default by the server's catalogue
  // itself (catalog._stored_limit, D-248), so the editor shows exactly the figure it is sent - no client constant.
  const voiceOf = (entitlement) => draftOf({ id: 'plus', prices: {}, entitlements: [{ key: 'orena.voice', params: {}, ...entitlement }] }).entitlements[0];
  const savedLimit = (entry) => plansPayload([{ id: 'plus', prices: {}, entitlements: [entry] }]).plans[0].entitlements[0].limit;
  const sent = voiceOf({ enabled: true, limit: 6000, scale: 60, window: 'month' });
  assert.equal(sent.limit, '100', 'the server figure in minutes');
  assert.equal(savedLimit(sent), 6000, 'and saved back unchanged');
  assert.ok(!/\b900\b/.test(src('static/orena/screens/admin/plans.js')), 'no hard-coded voice default in the editor');
  // Review of #477, P1: a voice limit saved per day is not applied once the meter is monthly; the page says so.
  const { staleLine } = await import('../static/orena/screens/admin/plans.js');
  assert.equal(staleLine({ stale_limits: [] }), '');
  const stale = staleLine({ stale_limits: [
    { plan: 'plus', key: 'orena.voice', limit: 900, saved_window: 'day', window: 'month' },
    { plan: 'pro', key: 'orena.voice', limit: 900, saved_window: 'day', window: 'month' }] });
  assert.ok(stale.includes('Voice chat with Orena') && stale.includes('per day') && stale.includes('per month') && stale.includes('until you save'), stale);
  assert.ok(/plansStale/.test(src('static/orena/screens/admin/copy-plans.js')) && (src('static/orena/screens/admin/copy-plans.js').match(/plansStale:/g) || []).length === 3, 'EN/VI/ZH');
  // No stored limit is UNCAPPED on the server: it stays null, shown as an unlimited meter, and a plain save writes no cap.
  for (const stored of [null, undefined]) {
    const open = voiceOf({ enabled: true, ...(stored === undefined ? {} : { limit: stored }) });
    assert.equal(open.metered, false, 'unlimited: no minutes field');
    assert.equal(open.limit, null);
    assert.equal(savedLimit(open), null, 'null stays null on save');
  }
  // A plan without voice (Free) is left exactly as stored.
  const off = voiceOf({ enabled: false, limit: 1, scale: 60 });
  assert.equal(savedLimit(off), 1, 'a disabled plan keeps its stored value');
  assert.equal(savedLimit(voiceOf({ enabled: false })), null);
  assert.equal(savedLimit(voiceOf({ enabled: true, limit: 900, scale: 60 })), 900);
  // Plan & usage: no voice row while the commerce read does not report orena.voice.
  const model = await import('../static/orena/screens/plan/model.js');
  assert.equal(model.usageRows({ features: { 'orena.message': { limit: 20, used: 1, usage_state: 'known', entitlement_state: 'known' } } }).some((row) => row.key === 'orena.voice'), false);
  assert.equal(model.usageRows({ features: {} }).length, 0);
  // The voice 429 carries no `upgrade` and no `options`: no way to the plans.
  const { quotaOffersPlans } = await import('../static/orena/screens/plan/quota-notice.js');
  assert.equal(quotaOffersPlans({ status: 429, category: 'quota_exhausted', context: { feature: 'orena.voice', used: 900, limit: 900, scale: 60 } }), false, 'no options, no link');
}

// D-237: at the daily voice-minute cap (429 quota_exhausted, orena.voice) a line, text chat stays, no upsell for a paid learner.
{
  const { isQuotaExhausted, quotaMessage, quotaOffersPlans, isVoiceNotInPlan } = await import('../static/orena/screens/plan/quota-notice.js');
  const cap = (extra = {}) => Object.assign(new Error('x'), { status: 429, category: 'quota_exhausted', context: { feature: 'orena.voice', used: 900, limit: 900, unit: 'second', display_unit: 'minute', scale: 60, window: 'day', plan: 'plus', upgrade: '/pricing', ...extra } });
  assert.equal(isQuotaExhausted(cap()), true);
  assert.equal(isVoiceNotInPlan(cap()), false, 'a 429 cap is not the 403 Free upsell');
  assert.equal(isVoiceNotInPlan(Object.assign(new Error('x'), { status: 403, category: 'feature_not_in_plan', context: { feature: 'orena.voice' } })), true, '403 is unchanged');
  assert.equal(quotaOffersPlans(cap()), false, 'a paid learner at the cap is offered no plans');
  assert.equal(quotaOffersPlans(cap({ options: [] })), false);
  assert.equal(quotaOffersPlans(cap({ options: ['upgrade'] })), true, 'only when the server says a higher plan holds more');
  assert.equal(quotaOffersPlans(Object.assign(new Error('x'), { status: 429, category: 'quota_exhausted', context: { feature: 'orena.message' } })), true, 'other meters keep their link');
  const sentence = quotaMessage(cap());
  assert.ok(/15/.test(sentence) && !/900/.test(sentence), 'n = limit / scale');
  const copy = src('static/orena/screens/plan/copy.js');
  for (const line of [
    "exhausted_orena_voice_day: 'You have used all {limit} minutes of voice chat today. You can still message Orena.'",
    "exhausted_orena_voice_day: 'Hôm nay bạn đã dùng hết {limit} phút trò chuyện bằng giọng nói. Bạn vẫn có thể nhắn tin với Orena.'",
    "exhausted_orena_voice_day: '今天的 {limit} 分钟语音聊天已用完。你仍可以给 Orena 发消息。'",
    "exhausted_orena_voice_month: 'You have used all {limit} minutes of voice chat this month. You can still message Orena.'",
    "exhausted_orena_voice_month: 'Bạn đã dùng hết {limit} phút trò chuyện bằng giọng nói của tháng này. Bạn vẫn có thể nhắn tin với Orena.'",
    "exhausted_orena_voice_month: '本月的 {limit} 分钟语音聊天已用完。你仍可以给 Orena 发消息。'",
  ]) assert.ok(copy.includes(line), line);
  assert.ok(sentence.includes('today'), 'window day: today');
  assert.ok(quotaMessage(cap({ window: 'month', used: 6000, limit: 6000 })).includes('100 minutes of voice chat this month'), 'window month: this month');
  const voice = src('static/orena/screens/orena/voice.js');
  assert.ok(/if \(isQuotaExhausted\(error\)\) \{[^}]*setPhase\('idle'\);\s+showPlanLimit\(error\);\s+return;/.test(voice), 'session 429: the line, no device cascade, no retry; text chat is a different surface and stays');
  assert.ok(/if \(isQuotaExhausted\(error\)\) showPlanLimit\(error\)/.test(voice), 'extend 429: told once, the held token plays out');
  assert.ok(/if \(!quotaOffersPlans\(error\)\)/.test(voice));
  // The extend 429 does not end the held session: only the learner's end, a 404 or the token's death does.
  const live = src('static/orena/agent/live-voice.js');
  assert.ok(/onLimit\(error\);\s+return;/.test(live) && !/onLimit\(error\);\s+return end/.test(live));
}

// 5. The contract text and the code constant agree on v14.
{
  const { CONTRACT_VERSION } = await import('../static/orena/agent/contract.js');
  const text = src('docs/project/AGENT_CONTRACT.md');
  assert.equal(CONTRACT_VERSION, 14);
  assert.ok(text.includes('`contract_version: 14`'));
  for (const route of ['GET /api/agent/voice/allowance', 'GET /api/agent/progress/weekly', 'POST /api/agent/band/writing']) assert.ok(text.includes(route), route);
  assert.ok(text.includes('X-Orena-AI-Paused') && text.includes('`orena.voice`') && text.includes('"entitled": false'));
}

console.log('AI pause and voice-plan gate: ok');
