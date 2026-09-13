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
    return task();
  }
}
