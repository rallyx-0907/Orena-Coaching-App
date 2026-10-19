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
export async function* turn(request, { signal, fetchImpl = globalThis.fetch, idempotencyKey = '' } = {}) {
  const forced = forcedStream();
  let source;
  if (forced) {
    source = mockTurn(request, { signal, forced });
  } else {
    const present = await probe({ interfaceLang: request?.context?.locale?.interface, fetchImpl });
    source = present ? liveTurn(request, { signal, fetchImpl, idempotencyKey }) : (async function* absent() { yield { event: 'absent', data: {} }; })();
  }
  for await (const item of source) {
    if (item.event === 'absent') markOrenaAbsent();
    yield item;
  }
}

/* `key` is the idempotency key the turn was sent under; `status` / `category` are present only when the server ANSWERED
   (a refusal). The session keeps them so a manual Retry can tell an unknown outcome (reuse the key, #338) from an answered
   refusal (a new key): infrastructure/quota-headers.js `nextIdempotencyKey`. */
const transportError = (fallback = 'retry', extra = {}) => ({ event: 'error', data: { class: 'transport', message: '', fallback, ...extra } });

/* A 429 `rate_limited` is waited out a bounded number of times, and never for longer than this per wait: past either, the
   learner is told (class `rate_limited`, with Retry) instead of an endless silent loop. */
export const MAX_RATE_WAITS = 3;
export const MAX_RATE_WAIT_SECONDS = 30;

/* The plan-limit refusals (D-163) answer 429 / 409 with the canonical envelope - `detail` an object with a
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
export async function* liveTurn(request, { signal, fetchImpl = globalThis.fetch, sleep = pause, signedOut = () => location.assign('/#/welcome'), log = console.error, idleMs = TURN_IDLE_MS, idempotencyKey: reuseKey = '' } = {}) {
  // One key for this learner message, kept through a rate-limit resend: the server never counts it twice (D-163). A manual
  // Retry after an unknown outcome hands the earlier key back in (`reuseKey`), so a turn the server did process is not counted twice.
  const idempotencyKey = reuseKey || newIdempotencyKey();
  const unanswered = { key: idempotencyKey };
  let waits = 0;
  for (;;) {
    let response;
    // The request is the client's own to stop: the caller's stop, or a server that goes quiet (LEX-028).
    const local = new AbortController();
    const forward = () => local.abort();
    signal?.addEventListener('abort', forward, { once: true });
    let idle = null;
    try {
      idle = idleAfter(idleMs);
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
        if (!signal?.aborted) yield transportError('retry', unanswered);
        return;
      }
    } catch {
      // A request that failed outright leaves the idle timer running; clear it so nothing waits for it.
      idle?.clear();
      if (!signal?.aborted) yield transportError('retry', unanswered);
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
      if (refusal?.category === 'daily_ai_limit') {
        // Orena's AI is paused for everyone until `resets_at` (v10, §2.1): never waited out or resent, whatever
        // `Retry-After` says. The learner's message stays; the room says it in one line (screens/orena/model.js).
        yield { event: 'error', data: { class: 'daily_ai_limit', message: '', fallback: 'none', paused: { scope: refusal.context?.scope, resets_at: refusal.context?.resets_at } } };
        return;
      }
      if (response.status === 409 && refusal) {
        // operation_* (this message is being processed, or was: a new send is a new key) or account_not_ready: the
        // envelope's 409s are never a change of learning language, which is the plain string.
        // An answered refusal. `operation_in_progress` is the first request still running: the room says so (not "check your
        // connection"), and Retry keeps the key.
        const answered = { key: idempotencyKey, status: response.status, category: refusal.category };
        if (refusal.category === 'operation_in_progress') yield { event: 'error', data: { class: 'operation_in_progress', message: '', fallback: 'retry', ...answered } };
        else yield transportError('retry', answered);
        return;
      }
    }
    const status = readStatus(response.status, response.headers?.get?.('Retry-After'));
    if (status.kind === 'wait') {
      // Bounded: a few short waits, then the learner is told (never an endless silent loop). The refusal is answered,
      // nothing was processed, so Retry mints a new key.
      if (waits >= MAX_RATE_WAITS || status.seconds > MAX_RATE_WAIT_SECONDS) {
        yield { event: 'error', data: { class: 'rate_limited', message: '', fallback: 'retry', retryAfter: status.seconds, key: idempotencyKey, status: 429, category: 'rate_limited' } };
        return;
      }
      waits += 1;
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
      // The provider behind Orena answered 503 `provider_unavailable`: that is not the learner's network, and the room says so.
      const refused = response.status === 503 ? await readRefusal(response) : null;
      const answered = { key: idempotencyKey, status: response.status, ...(refused ? { category: refused.category } : {}) };
      if (refused?.category === 'provider_unavailable') {
        yield { event: 'error', data: { class: 'provider_unavailable', message: '', fallback: status.fallback, ...answered } };
        return;
      }
      // The plan could not be read, so the turn failed closed (503 `quota_unavailable`): the room says so.
      if (refused?.category === 'quota_unavailable') {
        yield { event: 'error', data: { class: 'quota_unavailable', message: '', fallback: status.fallback, ...answered } };
        return;
      }
      yield transportError(status.fallback, answered);
      return;
    }
    if (!response.body) {
      yield transportError('retry', unanswered);
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
    if (!ended && !signal?.aborted) yield transportError('retry', unanswered);
    return;
  }
}
