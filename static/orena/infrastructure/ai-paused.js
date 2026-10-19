/* The system's daily AI pause as the server signals it on ANY response (AGENT_CONTRACT §2.1, v11, D-235): a request refused
   because the system's daily AI ceiling is reached carries `X-Orena-AI-Paused: <resets_at ISO UTC>`, whatever the route, the
   status or the body (Reading 503, Listening 200 with its translation unavailable, a writing room's error, the agent's 429
   `daily_ai_limit`). A fault carries no header, so a surface never shows "paused" for something that is merely broken.

   This module only reads and remembers the signal, in one place; the sentence is screens/plan/quota-notice.js's
   (`pausedMessage`), shown by each surface in the place it already shows a failed request, never with a retry. */

export const AI_PAUSED_HEADER = 'X-Orena-AI-Paused';

/* A 200 that was refused in part (Listening's meaning, a lookup's gloss) has no error to carry the signal, so the newest
   one is kept for a minute: long enough for the surface that made the call to ask, short enough never to outlive the
   cause. Past the reset time it is void whatever its age. */
const REMEMBER_MS = 60000;
let latest = null;

/* The header's value from a fetch Response: the reset time (an ISO string, possibly empty when the server gave none),
   or null when the response is not an AI-pause refusal. */
export function aiPausedFromResponse(response) {
  const headers = response && response.headers;
  if (!headers || typeof headers.get !== 'function') return null;
  const value = headers.get(AI_PAUSED_HEADER);
  return value == null ? null : String(value).trim();
}

export function noteAiPaused(resetsAt, now = Date.now()) {
  latest = { resetsAt: String(resetsAt || ''), at: now };
}

/* The pause in force for a call that has just returned, or null: `resetsAt` is '' when the server sent no time. */
export function recentAiPause(now = Date.now()) {
  if (!latest || now - latest.at > REMEMBER_MS) return null;
  const end = Date.parse(latest.resetsAt);
  if (Number.isFinite(end) && end <= now) return null;
  return { resetsAt: latest.resetsAt };
}

export function clearAiPause() {
  latest = null;
}

/* What an error from `request()` (or a voice call) says about the pause: `{ resetsAt }` or null. The header is the
   signal; the agent's own `daily_ai_limit` body (v10) is the same fact for a server that has not sent the header. */
export function aiPauseOf(error) {
  if (!error) return null;
  if (typeof error.aiPaused === 'string') return { resetsAt: error.aiPaused };
  if (error.status === 429 && error.category === 'daily_ai_limit') return { resetsAt: String(error.context?.resets_at || '') };
  return null;
}
