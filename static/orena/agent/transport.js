/* Where a turn goes. Until the human says the intelligence lane is integrated, every turn goes to
   the contract mock (D-086; the human's migration brief item 5) and nothing calls /api/agent/*.
   The live path is written - so switching is one reviewed change - but AGENT_LIVE is false and no
   code path can turn it on at runtime. */
import { parseEvents, bodyChunks } from './sse.js';
import { mockTurn } from './mock.js';

export const AGENT_LIVE = false;

function forcedStream() {
  try {
    return new URLSearchParams(location.hash.split('?')[1] || '').get('agent') || '';
  } catch {
    return '';
  }
}

/* One turn → an async iterable of { event, data } (AGENT_CONTRACT §4). */
export function turn(request, { signal } = {}) {
  if (!AGENT_LIVE) return mockTurn(request, { signal, forced: forcedStream() });
  return liveTurn(request, { signal });
}

async function* liveTurn(request, { signal }) {
  const response = await fetch('/api/agent/turn', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(request),
    signal,
  });
  if (!response.ok || !response.body) {
    yield { event: 'error', data: { class: 'transport', message: '', fallback: 'retry', status: response.status } };
    return;
  }
  yield* parseEvents(bodyChunks(response.body));
}
