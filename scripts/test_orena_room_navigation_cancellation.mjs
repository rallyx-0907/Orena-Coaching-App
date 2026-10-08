import assert from 'node:assert/strict';
import { beginNavigation, navigationSignal } from '../static/orena/infrastructure/navigation.js';
import { api } from '../static/orena/infrastructure/api.js';

/* Root cause, recorded in docs/project/CURRENT_HANDOFF.md as OPEN P1:
   `#/language` rendered "temporarily unavailable" only inside long
   multi-room sweeps at short dwell, never in isolation, and self-recovered.
   Leaving a room never cancelled its fetches, so a fast sweep piled up
   requests no one was reading any more, contending with the current room's
   own fetch for the same origin's connection budget - and `#/language` is
   the one room whose read is not wrapped in `Promise.allSettled`, so any
   contention-caused rejection reached the learner as a fully failed room
   instead of a degraded section. `beginNavigation()` cancels the previous
   room's requests the moment a new one starts, which removes the pileup
   these tests reproduce and assert against. */

// 1. The navigation contract itself: starting the next room's navigation
// aborts whatever signal the previous room was handed.
{
  const first = navigationSignal();
  assert.equal(first.aborted, false);
  const second = beginNavigation();
  assert.equal(first.aborted, true, 'leaving a room aborts its own signal');
  assert.equal(second.aborted, false, 'the new room starts with a live signal');
  assert.notEqual(first, second);
}

// 2. api.js wires every request to the current navigation signal, so a
// request left behind by a room the learner already left is cancelled
// rather than left pending to compete with the current room's own fetch.
{
  let fetchCalls = 0;
  const realFetch = globalThis.fetch;
  globalThis.fetch = (_url, options) =>
    new Promise((resolve, reject) => {
      fetchCalls += 1;
      const { signal } = options;
      if (signal.aborted) {
        reject(new DOMException('aborted', 'AbortError'));
        return;
      }
      // Deliberately never resolves on its own - this models a slow endpoint
      // still being awaited by a room the learner has already left.
      signal.addEventListener('abort', () =>
        reject(new DOMException('aborted', 'AbortError')),
      );
    });
  try {
    const leftBehindRoom = api.libraryVocabulary();
    // The learner moves on to a second room before the first one answered -
    // the short-dwell sweep that reproduced the flake.
    beginNavigation();
    await assert.rejects(leftBehindRoom, /AbortError|aborted/);
    assert.equal(fetchCalls, 1, 'the abandoned request is cancelled, not retried into a second call');
  } finally {
    globalThis.fetch = realFetch;
  }
}

// 3. The reported reproduction shape: many rooms, short dwell, EN/ZH
// alternating. Without cancellation this piles up concurrent requests one
// deep per room visited; with it, at most one request is ever in flight no
// matter how fast the sweep moves.
{
  let inFlight = 0;
  let maxConcurrent = 0;
  let cancelledCount = 0;
  const SERVER_LATENCY_MS = 20;
  const fakeRoomFetch = (signal) =>
    new Promise((resolve, reject) => {
      inFlight += 1;
      maxConcurrent = Math.max(maxConcurrent, inFlight);
      const timer = setTimeout(() => {
        inFlight -= 1;
        resolve({ ok: true });
      }, SERVER_LATENCY_MS);
      signal.addEventListener('abort', () => {
        clearTimeout(timer);
        inFlight -= 1;
        cancelledCount += 1;
        reject(new DOMException('aborted', 'AbortError'));
      });
    });

  const ROOMS = 13;
  const DWELL_MS = 5; // far shorter than SERVER_LATENCY_MS, as in the recorded repro
  const languages = ['en', 'zh'];
  const visits = [];
  for (let i = 0; i < ROOMS; i++) {
    // render() calls beginNavigation() unconditionally at the top of every
    // room render, including the first - mirrored here rather than special-
    // cased, so this sweep exercises the same contract app.js does.
    const signal = beginNavigation();
    const language = languages[i % languages.length];
    visits.push(
      fakeRoomFetch(signal).catch((error) => ({ language, aborted: error.name === 'AbortError' })),
    );
    await new Promise((resolve) => setTimeout(resolve, DWELL_MS));
  }
  const settled = await Promise.all(visits);

  assert.equal(maxConcurrent, 1, 'no two rooms ever hold a connection at the same time during the sweep');
  assert.equal(inFlight, 0, 'every request has settled - none left dangling past the sweep');
  assert.equal(cancelledCount, ROOMS - 1, 'every superseded room in the EN/ZH sweep was cancelled, not left pending');
  assert.equal(
    settled.slice(0, -1).every((entry) => entry.aborted),
    true,
    'every room but the last resolves as an expected cancellation, not a failure',
  );
}

console.log('Orena room-navigation cancellation (rapid EN/ZH sweep recovery): PASS');
