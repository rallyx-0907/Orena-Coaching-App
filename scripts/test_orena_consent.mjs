/* Light consent, client side (D-229 clause 5, D-233): the consent state module, the Settings voice row, the two sheets'
   source contracts and the copy parity of EN / VI / ZH. The server half is tests/test_consent_evidence.py. Browser
   behaviour of the sheets is checked by hand in a browser (no DOM here). */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  setConsentState, consentRequired, voiceConsent, clearConsentState, acceptConsent, readVoiceConsent, writeVoiceConsent,
} from '../static/orena/product/consent.js';
import { privacyRows } from '../static/orena/screens/settings/model.js';

const source = (path) => readFileSync(fileURLToPath(new URL(path, import.meta.url)), 'utf8');
const answer = (body, status = 200) => async (url, options) => {
  answer.calls.push({ url, method: options?.method || 'GET', body: options?.body });
  if (status !== 200) throw Object.assign(new Error('x'), { status });
  return body;
};
answer.calls = [];

/* --- the state the bootstrap gives: quiet unless the server keeps a record ---------------------- */
{
  assert.equal(consentRequired(), false);
  assert.equal(voiceConsent(), null, 'unknown until the server says');
  setConsentState({ stored: true, consent_required: true, consent_version: '', voice_consent: false });
  assert.equal(consentRequired(), true, 'an account with no record is asked once');
  assert.equal(voiceConsent(), false);
  setConsentState({ stored: false, consent_required: true, voice_consent: false });
  assert.equal(consentRequired(), false, 'a server that keeps no record asks nothing, whatever else it says');
  assert.equal(voiceConsent(), null, 'and gates nothing');
  for (const junk of [undefined, null, 'x', 5, {}]) {
    setConsentState(junk);
    assert.equal(consentRequired(), false);
    assert.equal(voiceConsent(), null);
  }
  clearConsentState();
}

/* --- the three calls -------------------------------------------------------------------------------- */
{
  setConsentState({ stored: true, consent_required: true, voice_consent: false });
  answer.calls = [];
  await acceptConsent('vi', answer({ stored: true, consent_required: false, consent_version: '2026-10-20', voice_consent: false }));
  assert.deepEqual(answer.calls.map((c) => [c.url, c.method, c.body]), [['/api/account-settings/consent', 'POST', '{"language":"vi"}']]);
  assert.equal(consentRequired(), false, 'after "I agree" the sheet is not due again');

  answer.calls = [];
  assert.equal(await writeVoiceConsent(true, answer({ stored: true, consent_required: false, voice_consent: true })), true);
  assert.deepEqual([answer.calls[0].url, answer.calls[0].body], ['/api/account-settings/voice-consent', '{"granted":true}']);
  assert.equal(voiceConsent(), true);
  assert.equal(await writeVoiceConsent(false, answer({ stored: false })), null, 'a server that cannot keep it: null, not a refusal');
  assert.equal(voiceConsent(), null);

  await assert.rejects(() => writeVoiceConsent(true, answer({}, 500)), 'a failed save throws so the switch is put back');
  assert.equal(await readVoiceConsent(answer({}, 503)), null, 'unreadable: null');
  await assert.rejects(() => readVoiceConsent(answer({}, 401)), 'a 401 is not hidden');
  assert.equal(await readVoiceConsent(answer({ stored: true, voice_consent: true })), true);
  clearConsentState();
}

/* --- the Settings row: drawn only when the server keeps an answer ------------------------------------ */
{
  const ids = (inputs) => privacyRows(inputs).map((r) => r.id);
  assert.ok(!ids({ lang: 'en' }).includes('voice'), 'no answer: not drawn');
  assert.ok(!ids({ lang: 'en', voiceOn: null }).includes('voice'));
  assert.deepEqual(ids({ lang: 'en', memoryOn: true, voiceOn: false }).slice(0, 3), ['mic', 'memory', 'voice'], 'beside the memory switch');
  const row = privacyRows({ voiceOn: false }).find((r) => r.id === 'voice');
  assert.deepEqual([row.kind, row.value, row.disabled], ['toggle', false, false]);
  assert.equal(privacyRows({ voiceOn: true }).find((r) => r.id === 'voice').value, true);
}

/* --- copy: three languages, interface layer, in their own writing system ------------------------------ */
{
  await import('../static/orena/screens/consent/copy.js');
  await import('../static/orena/screens/settings/copy.js');
  const copy = await import('../static/orena/copy/index.js');
  const tables = copy.registeredCopy();
  const sheet = tables.get('consent');
  const keys = Object.keys(sheet.layers);
  assert.ok(keys.length >= 10);
  for (const key of keys) {
    assert.equal(sheet.layers[key], 'interface', key);
    for (const lang of ['en', 'vi', 'zh']) assert.ok(String(sheet.packs[lang][key] || '').trim(), `${lang}.${key} present`);
  }
  assert.equal(sheet.packs.vi.consentAgree, 'Đồng ý');
  assert.equal(sheet.packs.en.consentAgree, 'I agree');
  assert.equal(sheet.packs.zh.consentAgree, '我同意');
  assert.equal(sheet.packs.vi.voiceTitle, 'Cho phép Orena nghe giọng bạn?');
  assert.equal(sheet.packs.vi.voiceBody, 'Để luyện nói, giọng của bạn được ghi lại và gửi tới dịch vụ AI để nhận xét. Bạn có thể tắt bất cứ lúc nào trong Cài đặt.');
  assert.deepEqual([sheet.packs.vi.voiceAllow, sheet.packs.vi.voiceLater], ['Cho phép', 'Để sau']);
  assert.match(sheet.packs.zh.voiceBody, /[一-鿿]/);
  assert.match(sheet.packs.vi.consentBody, /Điều khoản sử dụng và Chính sách quyền riêng tư/, 'the wording of D-229 clause 1');
  const settings = tables.get('settings');
  for (const key of ['voiceLabel', 'voiceSub']) {
    assert.equal(settings.layers[key], 'interface');
    for (const lang of ['en', 'vi', 'zh']) assert.ok(String(settings.packs[lang][key] || '').trim(), `${lang}.${key} present`);
  }
  assert.equal(settings.packs.vi.voiceLabel, 'Ghi âm giọng nói');
  assert.match(settings.packs.zh.voiceLabel, /[一-鿿]/);
}

/* --- a 403 voice_consent_required asks at once, and the refusal still reaches the room ---------------- */
{
  const { request, setVoiceConsentRequiredHandler } = await import('../static/orena/infrastructure/api.js');
  const { markVoiceRefused } = await import('../static/orena/product/consent.js');
  const reply = (status, body) => async () => ({
    ok: status < 400, status, headers: { get: (name) => (name.toLowerCase() === 'content-type' ? 'application/json' : null) }, json: async () => body,
  });
  const realFetch = globalThis.fetch;
  let asked = 0;
  setVoiceConsentRequiredHandler(() => { asked += 1; markVoiceRefused(); });
  try {
    globalThis.fetch = reply(403, { detail: { category: 'voice_consent_required', message: 'x', retryable: false, context: {} } });
    await assert.rejects(() => request('/api/speech/transcribe', { method: 'POST' }), (error) => error.status === 403 && error.category === 'voice_consent_required');
    assert.equal(asked, 1, 'the consent question is asked');
    assert.equal(voiceConsent(), false, 'and the next recording asks too');
    globalThis.fetch = reply(403, { detail: { category: 'forbidden', message: 'x' } });
    await assert.rejects(() => request('/api/x'));
    assert.equal(asked, 1, 'another 403 asks nothing');
  } finally {
    globalThis.fetch = realFetch;
    setVoiceConsentRequiredHandler(null);
    clearConsentState();
  }
}

/* --- the wiring, in source: one gate for every recording room; the sheet at boot; the bootstrap read --- */
{
  assert.match(source('../static/orena/screens/mic/sheet.js'), /if \(!\(await ensureVoiceConsent\(ctx\)\)\) return;\n\s*if \(granted\)/, 'micGate asks before anything else');
  assert.match(source('../static/orena/shell/context.js'), /setConsentState\(bootstrap\?\.consent\)/);
  assert.match(source('../static/orena/main.js'), /openConsentSheet/);
  assert.match(source('../static/orena/main.js'), /setVoiceConsentRequiredHandler\(\(\) => void module\.onVoiceConsentRefused/);
  const sheet = source('../static/orena/screens/consent/sheet.js');
  assert.match(sheet, /className: 's-mic'/, 'the Mic state sheet\'s own shape, no new visual');
  assert.match(sheet, /onClose: \(\) => settle\(false\)/, 'the scrim or Escape never allows recording');
  assert.match(sheet, /legalHref\('\/terms'\)/);
  assert.match(sheet, /legalHref\('\/privacy'\)/);
  assert.match(sheet, /label: t\('consentTerms'\) \}/, 'the Terms link is its translated name, no "(English)" note (#437)');
  assert.match(sheet, /label: t\('consentPrivacy'\) \}/);
  assert.doesNotMatch(sheet, /localStorage/, 'the answer lives on the server, not the device');
}

console.log('Consent: state, calls, Settings row, copy parity EN/VI/ZH, wiring: PASS');
