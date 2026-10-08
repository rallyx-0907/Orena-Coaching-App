/* Answers given with no network, kept until there is one.
 *
 * The canonical frame "Review offline mobile" says it plainly: "Kết quả lưu
 * trên máy và đồng bộ khi có mạng" - results are kept on the device and sync
 * when there is a connection, and it draws the count of what is waiting. So a
 * grade that cannot reach the server is not lost and is not silently dropped:
 * it waits here, in the learner's own device memory, and goes up in the order
 * it was given.
 *
 * Order matters. Two answers to the same word are two events in a schedule,
 * and sending the later one first would leave the card on the wrong footing.
 */

export const MAX_WAITING = 200;

export function readQueue(raw) {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter(
      (item) =>
        item &&
        typeof item.word === 'string' &&
        item.word &&
        ['again', 'unsure', 'got_it'].includes(item.grade) &&
        typeof item.at === 'string',
    )
    .slice(-MAX_WAITING)
    .map((item) => ({ word: item.word, grade: item.grade, at: item.at }));
}

/* Whether an answer failed to arrive because there is no network, or because
   the server refused it. Only the first is worth keeping: a refusal will be
   refused again in an hour, and a queue that retries it forever never drains.
   A fetch that never reached a server throws rather than answering, so a
   thrown error with no status is the offline case. */
export function worthKeeping(error) {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return true;
  const status = Number(error?.status || error?.response?.status || 0);
  if (!status) return true;
  return status >= 500;
}

export function withWaiting(queue, word, grade, at) {
  return [...(queue || []), { word: String(word), grade: String(grade), at: String(at) }].slice(
    -MAX_WAITING,
  );
}

/* Send what is waiting, oldest first, and stop at the first one that will not
   go: the rest are behind it in the same schedule. Returns what is still
   waiting, so the caller writes back one value rather than mutating. */
export async function flushQueue(queue, send) {
  const waiting = [...(queue || [])];
  while (waiting.length) {
    const next = waiting[0];
    try {
      await send(next);
    } catch (error) {
      if (worthKeeping(error)) return waiting;
      // The server refused this one; it will refuse it again. Drop it rather
      // than blocking every answer behind it forever.
      waiting.shift();
      continue;
    }
    waiting.shift();
  }
  return waiting;
}
