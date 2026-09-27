/* The one way a screen asks for Orena (D-086): "Ask Orena" on a word, a sentence, a finding, a
   grammar point; the voice button. Screens describe what the learner is looking at in the terms of
   AGENT_CONTRACT §3 (`surface` id, `selected_item`, ids) and never know how the agent is drawn.

   The agent panel (agent/, a later slice) registers itself with setAgentHandler(); until it does,
   asking opens Orena Home. */
let handler = null;

export function setAgentHandler(fn) {
  handler = typeof fn === 'function' ? fn : null;
}

/* context: { surface, activity_type?, content_id?, attempt_id?, essay_id?, lesson_id?,
              selected_item?: { type, id?, text }, voice?: boolean, label?: string } */
export function askOrena(context = {}) {
  if (handler) return handler(context);
  location.hash = context.voice ? '#/orena?voice=1' : '#/orena';
  return null;
}
