/* Feedback: pure data mapping (Design Contract rule 40). No DOM, no network.

   The backend takes and lists a learner's reviews (D-156: POST /api/feedback, GET /api/feedback/mine),
   so Send works. The form (stars, areas, text) is the design's; the history is the learner's own
   reviews, newest first. */
export const SEND_AVAILABLE = true;

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

/* The reviews already sent, as the card draws them: the server's rows, newest first, nothing invented. */
export function history(items = []) {
  return (Array.isArray(items) ? items : []).map((item) => ({
    id: String(item.id ?? ''),
    stars: Math.max(0, Math.min(STAR_COUNT, Math.round(Number(item.stars) || 0))),
    areas: (Array.isArray(item.areas) ? item.areas : []).filter((area) => AREAS.includes(area)),
    text: String(item.text ?? '').trim(),
    createdAt: item.created_at || '',
  }));
}

/* "★★★☆☆", as the frame draws a card's stars. */
export function starsText(stars) {
  const count = Math.max(0, Math.min(STAR_COUNT, Math.round(Number(stars) || 0)));
  return '★'.repeat(count) + '☆'.repeat(STAR_COUNT - count);
}

/* What the body of a send is: the rating, the areas, the text, and the two languages. */
export function sendBody({ stars, areas, text }, { language, interfaceLanguage }) {
  return { stars: Number(stars), areas: [...areas], text: String(text ?? '').trim(), language, interface: interfaceLanguage };
}

/* The copy key for a refused or failed send, by the status the server answered. */
export function errorKey(status) {
  if (status === 429) return 'errTooMany';
  if (status === 503) return 'errUnavailable';
  if (status === 422) return 'errInvalid';
  return 'errFailed';
}

/* The reviews after a successful send: the new one first. */
export function prepend(items, review) {
  return [review, ...(Array.isArray(items) ? items : []).filter((item) => item.id !== review.id)];
}
