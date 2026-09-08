/* What happened when an experience asked a capability for something.

   Three different facts kept arriving at the same place and leaving as one
   sentence: this content has nothing to offer, the provider that would answer
   is not configured, and the request failed on the way. A learner meeting all
   three as "unavailable" cannot tell which of them is worth trying again, and
   the one that is worth retrying is the one that looks identical to the two
   that are not.

   These are presentation outcomes at the orchestration boundary. They do not
   replace the backend envelopes - adapters keep the domain fields their
   capability already returns - and nothing here may turn an existing failure
   into a ready answer. */

export const READY = 'ready';
export const PENDING = 'pending';
export const UNAVAILABLE = 'unavailable';
export const FAILED = 'failed';

export const ready = (value) => ({ state: READY, value });
export const pending = () => ({ state: PENDING });
/* Nothing is coming: the capability is not configured here, or this content
   has nothing of that kind. Offering a retry would be a lie about what waiting
   can achieve. */
export const unavailable = (reason = '') => ({ state: UNAVAILABLE, reason });
/* Something went wrong on the way. Whether the learner should try again is the
   capability's answer, not a guess made at the surface. */
export const failed = (reason = '', retryable = true) => ({
  state: FAILED,
  reason,
  retryable,
});

export const isReady = (outcome) => outcome?.state === READY;
export const canRetry = (outcome) =>
  outcome?.state === FAILED && outcome.retryable === true;

/* Run a capability call and classify what came back.

   `read` decides whether a returned payload is genuinely an answer. A payload
   that says `available: false` is a real response carrying real news, not a
   failure - so it becomes unavailable rather than failed, and no retry is
   offered for a provider that is simply not there. A thrown request is failed,
   because trying again can plausibly help. */
export async function attempt(call, { read, unavailableReason = '', failedReason = '' } = {}) {
  try {
    const value = await call();
    const verdict = read ? read(value) : { ok: true };
    if (verdict?.ok) return ready(value);
    return unavailable(verdict?.reason || unavailableReason);
  } catch (error) {
    // A capability may say a failure is permanent; the default is that a
    // learner is allowed to try again.
    return failed(failedReason, error?.retryable !== false);
  }
}
