/* Feedback: pure data mapping (Design Contract rule 40). No DOM, no network.

   There is no feedback endpoint anywhere in the backend (app.py and writing_coach/ carry none) and
   no store for a learner's reviews, so nothing can be sent or listed: `SEND_AVAILABLE` is false, the
   history is empty and the count reads zero. The form itself (stars, areas, text) is the design's
   and stays usable as a draft in memory; Send is inert. Recorded in docs/project/
   UI_BACKEND_GAPS.md ("New export frames"). */
export const SEND_AVAILABLE = false;

export const STAR_COUNT = 5;
export const TEXT_LIMIT = 600;

/* The seven areas the frame offers, as copy keys. */
export const AREAS = Object.freeze(['listening', 'speaking', 'reading', 'writing', 'vocabulary', 'orena', 'bugs']); // D-152 skill order

/* The label next to the stars: nothing chosen, or the rating's word. */
export function ratingKey(stars) {
  const value = Math.max(0, Math.min(STAR_COUNT, Math.round(Number(stars) || 0)));
  return `rate${value}`;
}

export function toggleArea(selected, area) {
  if (!AREAS.includes(area)) return [...selected];
  return selected.includes(area) ? selected.filter((item) => item !== area) : [...selected, area];
}

export function clampText(text) {
  return String(text ?? '').slice(0, TEXT_LIMIT);
}

/* Whether the draft could be sent: a rating, and a way to send it. */
export function canSend({ stars = 0, available = SEND_AVAILABLE } = {}) {
  return available === true && Number(stars) > 0;
}

/* The reviews already sent: none can exist without an endpoint. */
export function history() {
  return [];
}
