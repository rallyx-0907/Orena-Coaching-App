/* Where a turn goes. Until the human says the intelligence lane is integrated, every turn goes to
   the contract mock (D-086; the human's migration brief item 5) and nothing calls /api/agent/*.
   The live path is written - so switching is one reviewed change - but AGENT_LIVE is false and no
   code path can turn it on at runtime.

   Both paths yield the same thing: the §4 events of one turn, plus the client's own events for a
   status (§2.1: `wait` before a resend, `absent`, `language_mismatch`) and its own `transport`
   error (§4.1). */
import { parseEvents, bodyChunks } from './sse.js';
import { mockTurn } from './mock.js';
import { readStatus } from './contract.js';
import { markOrenaAbsent } from './presence.js';

export const AGENT_LIVE = false;

function forcedStream() {
  try {
    return new URLSearchParams(location.hash.split('?')[1] || '').get('agent') || '';
  } catch {
    return '';
  }
}

/* One turn → an async iterable of { event, data } (AGENT_CONTRACT §4, §2.1). */
export async function* turn(request, { signal } = {}) {
  const source = AGENT_LIVE ? liveTurn(request, { signal }) : mockTurn(request, { signal, forced: forcedStream() });
  for await (const item of source) {
    if (item.event === 'absent') markOrenaAbsent();
    yield item;
  }
}

/* Is Orena on for this visit? Asked once when the UI starts (§2.1): a 404 hides every entry point.
   The mock is always on. */
export async function probe({ interfaceLang = 'en', fetchImpl = globalThis.fetch } = {}) {
  if (!AGENT_LIVE) return true;
  try {
    const response = await fetchImpl(`/api/agent/capabilities?interface=${encodeURIComponent(interfaceLang)}`, { credentials: 'same-origin' });
    if (response.status === 404) {
      markOrenaAbsent();
      return false;
    }
  } catch {
    /* unreachable now says nothing about whether the agent is on; a turn will tell */
  }
  return true;
}

const transportError = (fallback = 'retry') => ({ event: 'error', data: { class: 'transport', message: '', fallback } });

function pause(ms, signal) {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => {
      clearTimeout(timer);
      resolve();
    }, { once: true });
  });
}

/* The live path. Exported with its fetch and clock injectable so the gate can drive every §2.1
   status; nothing in the UI calls it while AGENT_LIVE is false. */
export async function* liveTurn(request, { signal, fetchImpl = globalThis.fetch, sleep = pause, signedOut = () => location.assign('/login'), log = console.error } = {}) {
  for (;;) {
    let response;
    try {
      response = await fetchImpl('/api/agent/turn', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify(request),
        signal,
      });
    } catch {
      if (!signal?.aborted) yield transportError();
      return;
    }
    const status = readStatus(response.status, response.headers?.get?.('Retry-After'));
    if (status.kind === 'wait') {
      yield { event: 'wait', data: { seconds: status.seconds } };
      await sleep(status.seconds * 1000, signal);
      if (signal?.aborted) return;
      continue;
    }
    if (status.kind === 'absent' || status.kind === 'language_mismatch') {
      yield { event: status.kind, data: {} };
      return;
    }
    if (status.kind === 'signed_out') {
      signedOut();
      return;
    }
    if (status.kind === 'error') {
      if (response.status === 422) log('[Orena agent] the server refused the request as malformed (422)');
      yield transportError(status.fallback);
      return;
    }
    if (!response.body) {
      yield transportError();
      return;
    }
    let ended = false;
    for await (const item of parseEvents(bodyChunks(response.body))) {
      yield item;
      if (item.event === 'done' || item.event === 'error') {
        ended = true;
        break;
      }
    }
    if (!ended && !signal?.aborted) yield transportError();
    return;
  }
}
