/* Conversation (frame 30-Conversation.html, route 'conv'; E2 §3). Pure, DOM-free data mapping so
   scripts/test_orena_screen_conversation.mjs can prove it without a browser.

   The frame's own 4 scenarios (Café/Colleague/Hotel/Interview, each a fixed 4-line partner
   script) and its B1/B2/C1 difficulty picker are prototype content with no real backend - the
   difficulty selector is cosmetic even in the source itself (E2 §3: "nothing in cvSend/CONV
   branches on diff"), and a Chinese learner has no scenario at all under that scheme (E2 §3
   "Language specifics"). Real, in both learning languages: `content/voice-invitations.js`'s
   Orena-authored situations (the same bank Free Talk draws from), handed to the real AI partner,
   `POST /api/dictionary/conversation-turn`
   (`writing_coach/conversation.py`), through `product/conversation.js`'s own turn state machine,
   reused whole (not duplicated: it is already DOM-free and already owns the real contract's
   validation). */
import { voiceInvitations } from '../../content/voice-invitations.js';

export function situations(language) {
  return voiceInvitations(language).map((item) => ({ key: item.key, title: item.title, prompt: item.prompt, cue: item.cue }));
}

/* The context a per-turn "How did that land?" coaching call needs: what the learner was
   answering, so an ordinary reply to the partner's question is not read as an incomplete thought -
   exactly the current Conversation's own reasoning (ui/conversation.js:110-118), reimplemented
   here against the same real turns array (that module is old-UI presentation, never imported by
   the new UI). */
export function turnSituation(situation, turns, index) {
  const previous = turns[index - 1]?.text || '';
  return [situation, previous].filter(Boolean).join('\n').slice(0, 1200);
}

/* How many turns the learner has spoken - what "Conversation complete" counts and what Finish writes
   to the session's speaking ledger. */
export function learnerTurnCount(turns) {
  return (Array.isArray(turns) ? turns : []).filter((turn) => turn?.role === 'learner').length;
}

export function fixesOf(coaching) {
  return (coaching?.landed_differently || []).filter((item) => item?.quote).slice(0, 3);
}
export function strengthsOf(coaching) {
  return (coaching?.carried || []).filter((item) => item?.quote).slice(0, 3);
}
