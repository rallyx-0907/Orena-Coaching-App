/* Request policy for `POST /api/media-learning/annotate` (the local tagger: word roles, pinyin, key words).

   The tagger is an aid, never a requirement: a failure leaves the text plain. So the policy is small:

   - A 4xx answer is final. The request is wrong for this learner right now (the usual one is 409, the
     text's language is not the learner's current learning language) and sending it again cannot help.
     The first 4xx for a (scope, language) closes that pair for the session, so the 86 paragraphs of one
     article do not each fetch their own identical refusal, and opening the article again asks nothing.
   - A 5xx or a network failure is the moment, not the request: at most two more tries, backed off.
   - Success is passed through untouched. */
import { isTransientRequestError } from './retry.js';

export const ANNOTATE_BACKOFF_MS = Object.freeze([400, 1200]);

const refused = new Map(); // `${scope}|${language}` -> the refusing status

const keyOf = (scope, language) => `${scope || ''}|${String(language || '').toLowerCase()}`;
const retryable = (error) => {
  const status = Number(error?.status);
  return Number.isFinite(status) ? status >= 500 : isTransientRequestError(error);
};
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/* Whether this (scope, language) has already been refused, so a caller can stop scheduling work. */
export function annotateRefused(scope, language) {
  return refused.has(keyOf(scope, language));
}

export function resetAnnotatePolicy() {
  refused.clear();
}

/* `send(payload)` performs the request. `scope` names the text (its content id). Rejects with the original
   error, or with `{ status, skipped: true }` when the pair is already closed (no request is made). */
export async function annotateWithPolicy(send, payload, { scope = '', sleep = wait } = {}) {
  const key = keyOf(scope, payload?.source_language);
  if (refused.has(key)) {
    const skipped = new Error('annotate refused for this text and language');
    skipped.status = refused.get(key);
    skipped.skipped = true;
    throw skipped;
  }
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await send(payload);
    } catch (error) {
      const status = Number(error?.status);
      if (Number.isFinite(status) && status >= 400 && status < 500) refused.set(key, status);
      if (!retryable(error) || attempt >= ANNOTATE_BACKOFF_MS.length) throw error;
      await sleep(ANNOTATE_BACKOFF_MS[attempt]);
    }
  }
}
