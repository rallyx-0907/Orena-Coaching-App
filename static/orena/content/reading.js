/* Reading material the learner asked for. A reading session is not a separate
   kind of screen: it is a text that arrived, and it is read in the same
   encounter, with the same selection, the same shared explanation and the same
   collection as everything else in the world.

   This layer only adapts the session payload into the content shape. It adds
   nothing the passage did not carry - no invented paragraph breaks, no level
   the session did not state, no claim about where the words came from. */

// What a passage can be about, and the form it takes. A book excerpt, a news
// report and a short quotation are read differently, so the learner chooses
// both. These mirror the values the API accepts.
export const READING_SUBJECTS = [
  'random',
  'daily_life',
  'work',
  'science',
  'culture',
  'community',
];
export const READING_FORMS = ['article', 'book', 'news', 'quote'];

export const readingId = (id) => `reading:${id}`;

// Only a session id this product minted, so a hand-typed route cannot send an
// arbitrary path fragment to the API.
export function readingSessionId(id) {
  const match = /^reading:([1-9][0-9]{0,11})$/.exec(String(id || ''));
  return match ? Number(match[1]) : null;
}

/* Paragraphs are the ones the passage actually has. Prose without blank lines
   is shown whole rather than broken up at invented boundaries: where a text
   pauses is part of how it reads. */
function paragraphsOf(passage) {
  return String(passage || '')
    .split(/\n\s*\n/)
    .map((part) => part.trim())
    .filter(Boolean);
}

export function readingText(session, language) {
  const paragraphs = paragraphsOf(session?.passage);
  if (
    !session ||
    !readingSessionId(readingId(session.id)) ||
    !paragraphs.length
  )
    return null;
  if (session.language_code && session.language_code !== language) return null;
  const mode =
    session.generation_mode === 'generated' ? 'generated' : 'built-in';
  return {
    id: readingId(session.id),
    title: String(session.title || '').slice(0, 240),
    kind: 'text',
    art: 'reading',
    language,
    paragraphs,
    phrases: [],
    // How this passage came to exist, so the surface can say so rather than
    // implying every text was written for the learner who asked.
    generation_mode: mode,
    // The request is only worth repeating back when it was actually honoured.
    // The built-in passage answers every subject and form with the same words.
    topic: mode === 'generated' ? session.topic || '' : '',
    material: mode === 'generated' ? session.material || '' : '',
    level: String(session.target_level || ''),
    questions: (session.questions || []).filter(
      (item) => item && item.question && (item.options || []).length,
    ),
    recycled_words: session.recycled_words || [],
    latest_attempt: session.latest_attempt || null,
  };
}

// The library list carries less than a full session; it is enough to return to
// one, and never enough to pretend the passage has been read.
export function readingEntry(item, language) {
  return {
    id: readingId(item.id),
    title: String(item.title || '').slice(0, 240),
    kind: 'text',
    art: 'reading',
    language,
    generation_mode:
      item.generation_mode === 'generated' ? 'generated' : 'built-in',
    level: String(item.target_level || ''),
    attempted: Boolean(item.latest_attempt),
  };
}
