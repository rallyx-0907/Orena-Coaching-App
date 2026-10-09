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
import { newIdempotencyKey, quotaHeaders } from '../infrastructure/quota-headers.js';

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

/* The plan-limit refusals (D-161) answer 429 / 409 with the canonical envelope - `detail` an object with a
   `category` - where the contract's own 429 (`rate_limited`) and 409 (`target_language_mismatch`) carry a plain
   string. The body is read only to tell them apart; a response that cannot be read as an envelope is the contract's. */
async function readRefusal(response) {
  try {
    if (typeof response.json !== 'function') return null;
    const detail = (await (typeof response.clone === 'function' ? response.clone() : response).json())?.detail;
    return detail && typeof detail === 'object' && typeof detail.category === 'string'
      ? { category: detail.category, context: detail.context && typeof detail.context === 'object' ? detail.context : {} }
      : null;
  } catch {
    return null;
  }
}

function pause(ms, signal) {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => {
      clearTimeout(timer);
      resolve();
    }, { once: true });
  });
}

/* How long a turn may go without a word from the server - before its response starts, or between two events -
   before the client gives the learner a retry instead of an idle panel (LEX-028). Generous: a turn can hold
   several tool calls, and a slow local model takes tens of seconds per call. */
export const TURN_IDLE_MS = 90000;
const IDLE = Symbol('idle');

function idleAfter(ms) {
  let timer = 0;
  const promise = new Promise((resolve) => {
    timer = setTimeout(() => resolve(IDLE), ms);
  });
  return { promise, clear: () => clearTimeout(timer) };
}

/* The live path. Exported with its fetch and clock injectable so the gate can drive every §2.1
   status. */
export async function* liveTurn(request, { signal, fetchImpl = globalThis.fetch, sleep = pause, signedOut = () => location.assign('/#/welcome'), log = console.error, idleMs = TURN_IDLE_MS } = {}) {
  // One key for this learner message, kept through a rate-limit resend: the server never counts it twice (D-161).
  const idempotencyKey = newIdempotencyKey();
  for (;;) {
    let response;
    // The request is the client's own to stop: the caller's stop, or a server that goes quiet (LEX-028).
    const local = new AbortController();
    const forward = () => local.abort();
    signal?.addEventListener('abort', forward, { once: true });
    try {
      const idle = idleAfter(idleMs);
      const asked = fetchImpl('/api/agent/turn', {
        method: 'POST',
        credentials: 'same-origin',
        headers: quotaHeaders({ 'Content-Type': 'application/json', Accept: 'text/event-stream' }, idempotencyKey),
        body: JSON.stringify(request),
        signal: local.signal,
      });
      // If the wait runs out first, the request is aborted and rejects later: that is expected, not an error.
      asked.catch(() => {});
      response = await Promise.race([asked, idle.promise]);
      idle.clear();
      if (response === IDLE) {
        local.abort();
        if (!signal?.aborted) yield transportError();
        return;
      }
    } catch {
      if (!signal?.aborted) yield transportError();
      return;
    }
    if (response.status === 429 || response.status === 409) {
      const refusal = await readRefusal(response);
      if (refusal?.category === 'quota_exhausted') {
        // The plan's limit of Orena messages: never waited out or resent. The learner is told, with the server's own
        // figures (screens/orena/model.js `errorText`) and the way to the plans.
        yield { event: 'error', data: { class: 'quota_exhausted', message: '', fallback: 'none', quota: refusal.context } };
        return;
      }
      if (refusal?.category?.startsWith('operation_')) {
        yield transportError('retry'); // this message is being processed, or was: a new send is a new key
        return;
      }
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
    const events = parseEvents(bodyChunks(response.body))[Symbol.asyncIterator]();
    for (;;) {
      const idle = idleAfter(idleMs);
      const next = await Promise.race([events.next(), idle.promise]);
      idle.clear();
      if (next === IDLE) {
        // The server went quiet mid-turn: stop it (aborting the request ends its body too), and give the learner
        // a retry. The pending read then settles on its own; nothing waits for it.
        local.abort();
        break;
      }
      if (next.done) break;
      yield next.value;
      if (next.value.event === 'done' || next.value.event === 'error') {
        ended = true;
        break;
      }
    }
    if (!ended && !signal?.aborted) yield transportError();
    return;
  }
}
