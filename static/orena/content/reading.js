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
  // Ends at the same gate every other source ends at.
  return readable({
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
    latest_attempt: session.latest_attempt || null,
    source: session.source,
  });
}

// The library list carries less than a full session; it is enough to return to
// one, and never enough to pretend the passage has been read.
export function readingEntry(item, language) {
  return {
    // Whether a check is waiting, known without fetching the whole session.
    question_count: Number.isInteger(item.question_count)
      ? item.question_count
      : null,
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

/* ---------------------------------------------------------------------------
   The readable contract.

   Three sources of text already converge on one encounter: passages the
   learner asks for, the authored collection, and text they bring in
   themselves. Books, public-domain works, articles and dialogues are more of
   the same kind of thing, and the point of naming the shape here is that
   adding one should mean writing an adapter, not redesigning the experience.

   A readable item carries:

     id          `<source>:<identifier>`, the prefix routing the encounter
     title       what the learner sees in a list and at the top of the text
     language    the learning language it is written in
     paragraphs  the paragraphs the text actually has, never invented ones
     kind        'text' unless the encounter should treat it differently
                 ('conversation' lays a dialogue out line by line)

   and may carry:

     subtitle    one line of orientation
     level       only when the source genuinely states one
     topic       what it is about, when the source actually chose a subject
     material    the form it takes - an article, a book excerpt, a report
     phrases     prepared language notes, for authored texts that have them
     questions   optional comprehension, each with an evidence fragment. Pure
                 reading is valid: a text with none says so, rather than having
                 questions invented for it so every text looks alike
     source      where it came from and on what terms - see `readableSource`
     generation_mode  'generated' | 'built-in', for text a model produced

   Anything a source cannot honestly supply is left out rather than filled in.
   The surface asks whether a field is there; it never invents a default that
   would read as a claim.
   --------------------------------------------------------------------------- */

/* Provenance and rights, in the same shape media already uses. A second
   vocabulary for the same question would mean the encounter had to learn both,
   and a licence recorded in two shapes is a licence that gets one of them
   wrong. Nothing here is defaulted: an unknown licence stays unknown. */
export function readableSource(raw) {
  if (!raw) return null;
  const creator = String(raw.creator || '').trim();
  const license = String(raw.license || '').trim();
  const url = String(raw.provenance_url || '').trim();
  if (!creator && !license && !url) return null;
  return {
    creator: creator.slice(0, 240),
    license: license.slice(0, 240),
    provenance_url: url.slice(0, 1000),
  };
}

/* Normalises anything readable into the contract above, dropping what a source
   could not supply. An adapter for a new source should end by calling this, so
   every text reaches the encounter having been through one gate. */
export function readable(item) {
  const paragraphs = (item?.paragraphs || [])
    .map((part) => String(part || '').trim())
    .filter(Boolean);
  if (!item?.id || !item.title || !paragraphs.length) return null;
  const shaped = {
    id: String(item.id),
    title: String(item.title).slice(0, 240),
    language: item.language,
    kind: item.kind === 'conversation' ? 'conversation' : 'text',
    paragraphs,
    phrases: Array.isArray(item.phrases) ? item.phrases : [],
  };
  for (const key of [
    'subtitle',
    'level',
    'topic',
    'material',
    'art',
    'origin',
    'generation_mode',
  ])
    if (item[key]) shaped[key] = item[key];
  if (Array.isArray(item.questions) && item.questions.length)
    shaped.questions = item.questions;
  if (item.latest_attempt) shaped.latest_attempt = item.latest_attempt;
  const source = readableSource(item.source);
  if (source) shaped.source = source;
  return shaped;
}
