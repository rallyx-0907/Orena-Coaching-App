// The UI's own live client (static/orena/agent/transport.js liveTurn) against the throwaway stack, over real HTTP.
// No model is reached: only what the server answers by rule - identity (S15, fixed copy), 409, 429, 404 when off.
// AGENT_LIVE stays false in the source; liveTurn is called directly with an injected fetch.
//
//   node scripts/agent_e2e/transport_check.mjs http://127.0.0.1:8013 [--agent-off]
// Prints one JSON object; exit 0 when every check passed.

import { liveTurn } from '../../static/orena/agent/transport.js';

const base = process.argv[2];
const agentOff = process.argv.includes('--agent-off');
let cookie = '';
const results = [];
const check = (name, ok, detail = {}) => results.push({ check: name, ok: Boolean(ok), ...detail });

async function fetchImpl(path, init = {}) {
  const headers = { ...(init.headers || {}), ...(cookie ? { Cookie: cookie } : {}) };
  const response = await fetch(base + path, { ...init, headers });
  const set = response.headers.get('set-cookie');
  if (set) cookie = set.split(';')[0];
  return response;
}

function request(target, message, extra = {}) {
  return {
    contract_version: 5,
    trigger: 'message',
    message,
    client: { ui_version: 'agent-e2e-node', supported_actions: ['navigate'], supported_intents: [] },
    context: { surface: 'home', locale: { interface: 'vi', support: 'vi', target, content: target }, ...extra },
  };
}

async function collect(req, { maxWaits = 0 } = {}) {
  const events = [];
  let waits = 0;
  for await (const item of liveTurn(req, { fetchImpl, sleep: async () => {}, signedOut: () => events.push({ event: 'signed_out' }), log: () => {} })) {
    events.push(item);
    if (item.event === 'wait' && ++waits > maxWaits) break;
  }
  return events;
}

async function setLanguage(language) {
  await fetchImpl('/api/platform/language', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ language }) });
}

try {
  const capabilities = await fetchImpl('/api/agent/capabilities?interface=vi');
  if (agentOff) {
    check('off.capabilities_404', capabilities.status === 404, { status: capabilities.status });
    const events = await collect(request('en', 'Bạn là ai?'));
    check('off.turn_is_absent', events.some((e) => e.event === 'absent'), { events: events.map((e) => e.event) });
  } else {
    check('on.capabilities_200', capabilities.status === 200, { status: capabilities.status });
    for (const [language, target] of [['en', 'en'], ['zh', 'zh-CN']]) {
      await setLanguage(language);
      const events = await collect(request(target, 'Bạn là ai?', { address: { self: 'chị', user: 'em', lang: 'vi' } }));
      const names = events.map((e) => e.event);
      const text = events.find((e) => e.event === 'segment_end')?.data?.text || '';
      check(`on.${language}.S15_identity_stream`, names[0] === 'session' && names.at(-1) === 'done' && text.startsWith('Chị là Orena'), { names, text });
    }
    await setLanguage('en');
    const mismatch = await collect(request('zh-CN', 'Bạn là ai?'));
    check('on.409_language_mismatch', mismatch.some((e) => e.event === 'language_mismatch'), { events: mismatch.map((e) => e.event) });
    let waited = false;
    for (let i = 0; i < 60 && !waited; i += 1) {
      const events = await collect(request('en', 'Bạn là ai?'));
      waited = events.some((e) => e.event === 'wait');
    }
    check('on.429_wait_then_resend', waited);
  }
} catch (error) {
  check('transport_check', false, { error: String(error) });
}
const failed = results.filter((r) => !r.ok).map((r) => r.check);
console.log(JSON.stringify({ agentOff, failed, results }));
// exitCode, not process.exit(): exiting while fetch still holds a socket crashes Node on Windows (0xC0000409)
process.exitCode = failed.length ? 1 : 0;
setTimeout(() => process.exit(process.exitCode), 2000).unref();
