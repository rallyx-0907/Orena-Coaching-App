/* Attempt History (frame 41, `#/speak/:id/attempts`) - pure data shaping over this line's own
   take list (`product/take-store.js`, D-076: this tab's session, plus IndexedDB retention the
   learner opted into). No seed data, no fixed count: an empty list is the frame with nothing in
   it (rule 40), not a bug. */
import { ringTone as bandTokens } from '../speak/model.js';
import { bestTake } from '../../product/take-store.js';

/* Newest first (`listTakes`'s own order) -> oldest first, so "Attempt 1" is the first one made. */
export function chronological(takes) {
  return [...takes].reverse();
}

/* `count`/`best`/`delta`. `delta` is the plain change from the first attempt to the last
   (D5 §6: "a plain last.overall - first.overall diff... not clamped"), formatted with a leading
   "+" only when positive - a real regression still reads as a bare negative number, not hidden.
   With fewer than two attempts there is nothing to change from, and the frame reads "—". */
export function statsFor(takes) {
  if (!takes.length) return { count: 0, best: 0, delta: null };
  const ordered = chronological(takes);
  if (ordered.length < 2) return { count: 1, best: ordered[0].overall ?? 0, delta: null };
  const best = Math.max(...ordered.map((item) => item.overall ?? 0));
  const delta = (ordered[ordered.length - 1].overall ?? 0) - (ordered[0].overall ?? 0);
  return { count: ordered.length, best, delta };
}

export function deltaLabel(delta) {
  if (delta == null) return '—';
  return delta > 0 ? `+${delta}` : String(delta);
}

/* One row per attempt, oldest first (`n` counts up from 1, matching `screens/speak/model.js`'s
   own `attemptOrdinal`), tinted by the ring's own 3-band convention (`ringTone`). "Best" is the
   same attempt every Speaking screen calls best (`product/take-store.js#bestTake`: the highest
   overall score, the newest of equals) and only when there is more than one attempt to be best
   of. A number a reopened attempt did not keep (D-076) is unknown, never the overall score
   standing in for it. */
export function rowsFor(takes, currentRef = '') {
  const ordered = chronological(takes);
  const best = takes.length > 1 ? bestTake(takes) : null;
  return ordered.map((item, at) => {
    const overall = item.overall ?? 0;
    const tone = bandTokens(overall);
    return {
      id: item.id,
      n: at + 1,
      overall,
      tileBg: tone.bg,
      tileColor: tone.ink,
      isBest: Boolean(best) && item.id === best.id,
      isCurrent: Boolean(currentRef) && item.id === currentRef,
      at: item.at,
      accuracy: item.accuracy ?? null,
      fluency: item.fluency,
      hasFluency: item.fluency != null,
    };
  }).reverse(); // newest first for display (D5 §6: "ahRows reversed (newest first)")
}
