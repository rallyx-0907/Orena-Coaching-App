/* What kind of recall a kept phrase deserves.

   A queue of identical cards teaches one thing: how to recognise a card. What
   a learner actually needs back depends on how the phrase entered their life -
   a word met while reading is recalled in a sentence, something they said is
   recalled by saying it, a phrase from their own writing is recalled by using
   it again.

   The shape is derived from provenance the learner's own actions produced. It
   is not a difficulty estimate and it is not a claim about mastery: it only
   decides which question is worth asking. */

export const RECALL_SHAPES = ['in_context', 'say', 'reuse', 'meaning'];

/* A phrase can only be recalled inside a sentence if that sentence genuinely
   contains it. Fragments recorded before the phrase was normalised, or a
   context that has drifted, fall back rather than showing a blank that hides
   nothing. */
export function blankContext(context, term) {
  const passage = String(context || '');
  const phrase = String(term || '');
  if (!phrase || !passage.includes(phrase)) return null;
  const [before, ...rest] = passage.split(phrase);
  return { before, after: rest.join(phrase), phrase };
}

export function recallShape(item, kept) {
  const context = blankContext(item?.source_fragment, item?.word);
  // Something the learner said comes back by saying it.
  if (kept?.why === 'from_speaking') return 'say';
  // Language from their own writing comes back by using it again.
  if (kept?.why === 'from_writing') return 'reuse';
  // Anything met inside a sentence comes back inside that sentence.
  if (context) return 'in_context';
  return 'meaning';
}

/* Whether this attempt is worth recording as evidence at all. Seeing a card is
   not recall, and the product must not turn a glance into a success - the
   learner has to have committed to an answer first. */
export function gradable(revealed) {
  return revealed === true;
}
