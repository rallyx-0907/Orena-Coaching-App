/* Small request policy shared by idempotent learner reads.

   A transient failure may be the moment, not the request. Retry exactly once
   at this boundary; callers still receive the original failure when the retry
   also fails. Non-transient errors remain single-shot so malformed requests
   are never hammered. */
export function isTransientRequestError(error) {
  const status = Number(error?.status);
  if (Number.isFinite(status))
    return status === 408 || status === 425 || status === 429 || status >= 500;
  return error?.name === 'TypeError';
}

export async function retryOnce(task, shouldRetry = isTransientRequestError) {
  try {
    return await task();
  } catch (error) {
    if (!shouldRetry(error)) throw error;
    // A 429 is the server's brake and names its own wait (Retry-After): an immediate second request would only spend the
    // same window twice, so it is never re-sent here. The caller shows the slow-down line instead.
    if (Number(error?.status) === 429) throw error;
    return task();
  }
}
