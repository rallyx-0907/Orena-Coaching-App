/* Request policy for `POST /api/media-learning/annotate` (the local tagger: word roles, pinyin, key words).

   The tagger is an aid, never a requirement: a failure leaves the text plain. So the policy is small:

   - 409 (the text's language is not the learner's current learning language), 403 and 401 are about the
     learner and the text, not the paragraph: the first one closes that (scope, language) pair for the
     session. Calls already in flight finish, so at most the worker count (6 in the Reader) is sent.
   - Any other 4xx (400, 413, 422) is about that one payload: it fails once, never retried, and the
     other paragraphs still ask.
   - 408, 425, 429, 5xx and network failures are the moment: at most two more tries, backed off (a
     Retry-After longer than the backoff wins).
   - A circuit breaker: after BREAKER_LIMIT consecutive failed calls of that last kind the pair is closed, so a
     dead tagger does not cost three requests for every paragraph.
   - Success is passed through untouched and resets the count. */
import { isTransientRequestError } from './retry.js';

export const ANNOTATE_BACKOFF_MS = Object.freeze([400, 1200]);

const refused = new Map(); // `${scope}|${language}` -> the status that closed it (0: breaker)
const failures = new Map(); // same key -> consecutive failed calls
export const BREAKER_LIMIT = 3;
const CLOSING = new Set([401, 403, 409]);

const keyOf = (scope, language) => `${scope || ''}|${String(language || '').toLowerCase()}`;
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/* Whether this (scope, language) has already been closed, so a caller can stop scheduling work. */
export function annotateRefused(scope, language) {
  return refused.has(keyOf(scope, language));
}

export function resetAnnotatePolicy() {
  refused.clear();
  failures.clear();
}

/* `send(payload)` performs the request. `scope` names the text (its content id). Rejects with the original
   error, or with `{ status, skipped: true }` when the pair is already closed (no request is made). */
export async function annotateWithPolicy(send, payload, { scope = '', sleep = wait } = {}) {
  const key = keyOf(scope, payload?.source_language);
  if (refused.has(key)) {
    const skipped = new Error('annotate closed for this text and language');
    skipped.status = refused.get(key);
    skipped.skipped = true;
    throw skipped;
  }
  for (let attempt = 0; ; attempt += 1) {
    try {
      const value = await send(payload);
      failures.delete(key);
      return value;
    } catch (error) {
      const status = Number(error?.status);
      if (CLOSING.has(status)) refused.set(key, status);
      if (!isTransientRequestError(error)) throw error;
      if (attempt >= ANNOTATE_BACKOFF_MS.length) {
        const count = (failures.get(key) || 0) + 1;
        failures.set(key, count);
        if (count >= BREAKER_LIMIT) refused.set(key, 0);
        throw error;
      }
      await sleep(Math.min(5000, Math.max(ANNOTATE_BACKOFF_MS[attempt], Number(error?.retryAfterMs) || 0)));
    }
  }
}
