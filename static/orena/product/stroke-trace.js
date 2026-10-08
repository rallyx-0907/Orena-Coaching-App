/* Whether a traced stroke is the stroke that was asked for.
 *
 * The canonical frame's own note (26, "NÉT CHỮ"): "Tô theo: sai hướng hoặc sai
 * thứ tự thì nét rung nhẹ và hiện nét đúng mờ." So the judgement has to be
 * about *direction* and *order*, not about how neat the line is - a learner
 * writing 一 right-to-left has made the mistake the note is about, and one
 * whose line wobbles has not.
 *
 * The evidence is the median: the vendored stroke data carries, for every
 * stroke, the line through its middle from where it starts to where it ends.
 * Comparing against that is why this needs no new data at all.
 *
 * Pure, and in the glyph's own coordinates, so the surface converts pointer
 * positions once and this never knows about the screen.
 */

/* How far from the median's ends a stroke may start and finish, as a share of
   the glyph box. Generous, because a finger is not a pen: what is being
   judged is which stroke was meant and which way it was drawn. */
export const NEAR = 0.28;
/* How much of the median's direction the trace must agree with. A stroke drawn
   backwards scores about -1, one drawn correctly about 1. */
export const WITH_THE_STROKE = 0.35;

function distance(a, b) {
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

/* The direction from the first point to the last, as a unit vector, or null
   when the trace has no length worth a direction. */
export function heading(points) {
  if (!points || points.length < 2) return null;
  const from = points[0];
  const to = points[points.length - 1];
  const dx = to[0] - from[0];
  const dy = to[1] - from[1];
  const length = Math.hypot(dx, dy);
  if (!length) return null;
  return [dx / length, dy / length];
}

export function agreement(points, median) {
  const drawn = heading(points);
  const meant = heading(median);
  if (!drawn || !meant) return 0;
  return drawn[0] * meant[0] + drawn[1] * meant[1];
}

/* Did this trace draw this stroke?
 *
 * Three questions, in the order they can fail: was it drawn near where the
 * stroke starts, did it end near where the stroke ends, and did it run the way
 * the stroke runs. A trace that fails any of them is the frame's "sai hướng
 * hoặc sai thứ tự", and the surface answers by shaking it and showing the
 * right stroke faintly.
 */
export function tracedStroke(points, median, { size = 1024 } = {}) {
  if (!points || points.length < 2 || !median || median.length < 2)
    return { ok: false, reason: 'too-short' };
  const near = NEAR * size;
  if (distance(points[0], median[0]) > near) return { ok: false, reason: 'wrong-start' };
  if (distance(points[points.length - 1], median[median.length - 1]) > near)
    return { ok: false, reason: 'wrong-end' };
  const along = agreement(points, median);
  if (along < WITH_THE_STROKE) return { ok: false, reason: 'wrong-direction' };
  return { ok: true, reason: '', along };
}

/* Which stroke the learner *did* draw, when they did not draw the one asked
   for. Used only to tell "wrong order" from "wrong stroke entirely": a trace
   that matches a later stroke is the learner writing out of order, which is
   worth saying differently from a scribble.
 */
export function strokeTraced(points, medians, { size = 1024 } = {}) {
  for (let at = 0; at < (medians || []).length; at += 1) {
    if (tracedStroke(points, medians[at], { size }).ok) return at;
  }
  return -1;
}
