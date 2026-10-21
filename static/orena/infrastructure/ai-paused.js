/* Orena's AI paused for the learner, as the server says it: the agent's 429 `daily_ai_limit` (AGENT_CONTRACT §2.1, v10).
   Since D-251 the system's daily AI spend is a monitor that refuses nothing, so the `X-Orena-AI-Paused` header is no longer
   sent and no longer read; `daily_ai_limit` stays (the agent's own cap, `scope: "agent"`, until it is made per learner).
   The sentence is screens/plan/quota-notice.js's (`pausedMessage`), shown in the place a surface already shows a failed
   request, never with a retry. */

/* What an error from `request()` (or a voice call) says about the pause: `{ resetsAt }` or null. */
export function aiPauseOf(error) {
  if (!error) return null;
  if (error.status === 429 && error.category === 'daily_ai_limit') return { resetsAt: String(error.context?.resets_at || '') };
  return null;
}
