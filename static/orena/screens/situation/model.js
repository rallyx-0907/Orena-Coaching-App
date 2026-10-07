/* Situation Reaction (frame 31-Situation-Reaction.html, route 'situation'; E2 §4). Pure, DOM-free
   data mapping so scripts/test_orena_screen_situation.mjs can prove it without a browser.

   The frame's own `SITUATIONS` (2 fixed scenarios), their regex `must[]` checkpoints and its
   word-count "clarity" bucket are prototype scoring with no real backend behind them at all (E2
   §4: "not a real clarity judgement" - the source's own words). Real, in both learning languages:
   the same Orena-authored situation bank Free Talk and Conversation already draw from
   (`content/voice-invitations.js`, 3 items, not 2), reused here as what the learner reacts to "in
   their own words, no model sentence"; and real coaching on the real answer,
   `POST /api/dictionary/spoken-response` (the same endpoint and shape as Free Talk/Conversation).
   The frame's own Intent-achieved / Clarity result grid has no real measurement to bind - dropped
   (rule 40/D-076), not reproduced with a client-side word-count or regex heuristic. It is drawn only
   when the coaching response carries those judgements (D-139 HD-13); today's `spoken-response` shape
   never does (UI_BACKEND_GAPS). Each scenario carries an authored `context`, the chip above it. */
import { voiceInvitations } from '../../content/voice-invitations.js';

export function scenarios(language) {
  return voiceInvitations(language).map((item) => ({ key: item.key, title: item.title, scenario: item.prompt, context: item.context }));
}

/* The frame's header subtitle states the mode's defining constraint and a real position in the
   bank ("scenario N of {total}") - functional, spec-required copy (E2 §4 "Copy audit"), kept. */
export function progressLabel(index, total) {
  return { index: Math.min(total, index + 1), total };
}

/* "Natural alternative" (the frame's accent-soft row): the coaching's own suggested line to say
   instead, preferring the concrete `say_again` line over the looser `another_way` prose. */
export function naturalAlternative(coaching) {
  return String(coaching?.say_again || coaching?.another_way || '').trim();
}
