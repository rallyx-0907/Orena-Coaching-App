/* What a metered call tells the server so the plan quota counts it truthfully (D-161). Shared by the API client and
   the agent's turn transport, which does not go through `request()`.

   The learner's own timezone decides when a day or month of use resets, so a metered call and the usage read say
   which zone this device is in. One idempotency key per learner action (a Review press, an Orena message), reused
   only if that same action is sent again, so the server never charges one action twice. */

export function deviceTimezone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

export function newIdempotencyKey() {
  try {
    if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  } catch {
    /* fall through */
  }
  return `k-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

export function quotaHeaders(base, idempotencyKey) {
  return { ...base, 'X-Orena-Timezone': deviceTimezone(), ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}) };
}

/* The key a manual Retry sends (the discussion's `retryPlan`, #338, and Orena's turn follow this one rule). An
   unanswered request (network, timeout, a stream that died) may have been processed, so the same key goes again and
   the server answers from what it stored. An answered refusal settled or released the operation, so Retry is a new
   action with a new key. `operation_in_progress` means the first request is still running: its key is kept, so
   nothing is stored or charged twice. */
export function nextIdempotencyKey(error, key, makeId = newIdempotencyKey) {
  const answered = Boolean(error?.status);
  const inProgress = error?.category === 'operation_in_progress';
  return answered && !inProgress ? makeId() : key;
}
