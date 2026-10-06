/* The one way a screen asks for Orena (D-086): "Ask Orena" on a word, a sentence, a finding, a
   grammar point; the voice button. Screens describe what the learner is looking at in the terms of
   AGENT_CONTRACT §3 (`surface` id, `selected_item`, ids) and never know how the agent is drawn.

   The Contextual Orena panel (screens/orena/panel.js) registers itself with setAgentHandler() as
   a side effect of being imported; the dynamic import at the bottom starts that as soon as this
   module - imported by every screen that offers "Ask Orena" - itself loads, so the handler is in
   place before a learner's first click without a static import cycle between the shell and a screen
   folder. A click in the first moments, while the panel is still loading, waits for it; only when
   the panel could not load does asking open Orena Home instead.

   §2.1 404 "the agent is off": every Orena entry point hides (shell/frame.js gates the rail card,
   its mic, and the phone bar's centre action off `orenaPresent()`); asking becomes a no-op here so
   a control this build failed to hide is still inert, never a dead navigation. */
import { orenaPresent } from '../agent/presence.js';

let handler = null;

export function setAgentHandler(fn) {
  handler = typeof fn === 'function' ? fn : null;
}

/* context: { surface, activity_type?, content_id?, attempt_id?, essay_id?, lesson_id?,
              selected_item?: { type, id?, text }, voice?: boolean, label?: string, ask?: string }
   `ask`: a control that is itself a question ("Ask Orena why") opens Orena on that question, sent as the
   learner's first message, instead of on a greeting (LEX-022). */
export function askOrena(context = {}) {
  if (!orenaPresent()) return null;
  if (handler) return handler(context);
  return panelReady.then(() => {
    if (handler) return handler(context);
    location.hash = context.voice ? '#/orena?voice=1' : '#/orena';
    return null;
  });
}

const panelReady = import('../screens/orena/panel.js').catch((error) => console.error('[Orena] the panel could not load', error));
