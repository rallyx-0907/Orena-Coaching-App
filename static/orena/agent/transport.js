/* Where a turn goes. The server decides (AGENT_CONTRACT §2.1): `AGENT_ENABLED` turns the agent on for
   one runtime, and its `GET /api/agent/capabilities` answer is what this client reads when the UI
   starts. A 404 means the agent is off on this server - every Orena entry point hides for the visit.
   Anything else means it is there, and every turn goes to the live server. The contract mock (§11)
   serves only when the address asks for it (`?agent=...`), so a status or a stream can still be
   reviewed with no backend; it never answers in place of a live server.

   Both paths yield the same thing: the §4 events of one turn, plus the client's own events for a
   status (§2.1: `wait` before a resend, `absent`, `language_mismatch`) and its own `transport`
   error (§4.1). */
import { parseEvents, bodyChunks } from './sse.js';
import { mockTurn } from './mock.js';
import { readStatus, toContractLang } from './contract.js';
import { markOrenaAbsent } from './presence.js';

function forcedStream() {
  try {
    return new URLSearchParams(location.hash.split('?')[1] || '').get('agent') || '';
  } catch {
    return '';
  }
}

let probing = null;

/* Is Orena on for this visit? Asked once when the UI starts (§2.1); a turn waits for the answer, so
   no turn is ever served by the mock while the server is being asked. A 404 hides every entry point;
   an unreachable server says nothing about whether the agent is on - a turn will tell. */
export function probe({ interfaceLang = 'en', fetchImpl = globalThis.fetch } = {}) {
  if (forcedStream()) return Promise.resolve(true);
  if (!probing) {
    probing = (async () => {
      try {
        const response = await fetchImpl(`/api/agent/capabilities?interface=${encodeURIComponent(toContractLang(interfaceLang))}`, { credentials: 'same-origin' });
        if (response.status === 404) {
          markOrenaAbsent();
          return false;
        }
      } catch {
        /* unreachable now: the turn decides */
      }
      return true;
    })();
  }
  return probing;
}

/* For the gate: forget the visit's answer. */
export function resetProbe() {
  probing = null;
}

/* One turn → an async iterable of { event, data } (AGENT_CONTRACT §4, §2.1). */
export async function* turn(request, { signal, fetchImpl = globalThis.fetch } = {}) {
  const forced = forcedStream();
  let source;
  if (forced) {
    source = mockTurn(request, { signal, forced });
  } else {
    const present = await probe({ interfaceLang: request?.context?.locale?.interface, fetchImpl });
    source = present ? liveTurn(request, { signal, fetchImpl }) : (async function* absent() { yield { event: 'absent', data: {} }; })();
  }
  for await (const item of source) {
    if (item.event === 'absent') markOrenaAbsent();
    yield item;
  }
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
   status. */
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
