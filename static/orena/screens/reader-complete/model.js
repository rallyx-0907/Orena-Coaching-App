/* Reading Complete (design route `rcomplete`, frame 40): pure data mapping, DOM-free so
   scripts/test_orena_screen_reader-complete.mjs can test it without a browser. */
import { contentIdFor } from '../reader/model.js';

/* The shell's own place titles (copy/shell.js shellCopy) for the six primary routes
   (shell/routes.js PRIMARY) - the real navigation-origin id the router remembers in
   sessionStorage, mapped to the shellCopy key that names it. An origin this screen does not
   recognise (or none at all) falls back to Discover, never a blank label. */
const PLACE_KEY = Object.freeze({
  today: 'today',
  discover: 'discover',
  orena: 'orena',
  practice: 'practiceHub',
  library: 'myLibrary',
  progress: 'progress',
});

export function originPlaceKey(origin) {
  return PLACE_KEY[origin] || 'discover';
}

/* The route to go back to for an origin: the place itself, or Discover for an unknown one. */
export function originRouteId(origin) {
  return Object.prototype.hasOwnProperty.call(PLACE_KEY, origin) ? origin : 'discover';
}

/* The comprehension stat: the learner's latest real attempt at THIS article's approved question set
   (`GET /api/reading/practice/evidence`, newest first: `{ article_id, correct_count, total }`),
   as "correct/total". Never attempted (or no attempt readable) is the em dash the frame's own
   `rcStats.cu` uses for an unmeasured value. */
export function comprehensionLabel(evidence, articleId) {
  const list = Array.isArray(evidence) ? evidence : [];
  const attempt = list.find((item) => String(item?.article_id) === String(articleId));
  const correct = Number(attempt?.correct_count);
  const total = Number(attempt?.total);
  if (!attempt || !Number.isFinite(correct) || !Number.isFinite(total) || total <= 0) return '—';
  return `${correct}/${total}`;
}

/* The "Next" row's target. Real things only: a book chapter's own next chapter; else another
   published article of the same language the learner has not finished (the catalogue's own order -
   the backend has no relatedness signal, so the frame's "same theme" claim is not made); else the
   frame's own row, which sends the learner to Discover to choose. */
export function nextPick({ doc, articles, continuation }) {
  if (doc.isBook && doc.neighbours?.next) {
    const next = doc.neighbours.next;
    return { kind: 'chapter', title: String(next.title || ''), id: contentIdFor('book', `${doc.bookId}:${next.id}`) };
  }
  if (doc.kind === 'article') {
    const done = (id) => {
      const entry = (Array.isArray(continuation) ? continuation : []).find((item) => item?.id === contentIdFor('article', id));
      return Number.isFinite(entry?.place?.within) && entry.place.within >= 100;
    };
    const open = (Array.isArray(articles) ? articles : []).filter((item) => item?.id && String(item.id) !== String(doc.id) && item.title && !done(item.id));
    // The frame offers the next text "· same theme": one on the same topic first, any other after.
    const sameTheme = doc.topic ? open.find((item) => item.topic === doc.topic) : null;
    const pick = sameTheme || open[0];
    if (pick) return { kind: 'article', title: String(pick.title), id: contentIdFor('article', pick.id), sameTheme: Boolean(sameTheme) };
  }
  return { kind: 'discover', title: '', id: '' };
}
