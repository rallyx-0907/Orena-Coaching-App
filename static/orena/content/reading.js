/* Reading content adapters. Every text source - a published corpus article, a
   book chapter, an authored story, a text the learner brought in - ends at the
   one readable contract below, and is read in the same encounter with the same
   selection, the same shared explanation and the same collection.

   The generated-passage adapters that used to live here are gone with the
   generator (D-082): no internal AI writes a source passage. */

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
