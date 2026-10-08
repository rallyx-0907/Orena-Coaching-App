/* Whether Orena exists on this server for this visit (AGENT_CONTRACT §2.1). A 404 on any
   /api/agent/* route means the agent is off (AGENT_ENABLED unset) - and then every Orena entry
   point is hidden. That is not an error: nothing is shown and nothing is retried. A new visit asks
   again. */
let present = true;
const listeners = new Set();

export function orenaPresent() {
  return present;
}

export function markOrenaAbsent() {
  if (!present) return;
  present = false;
  for (const listener of listeners) listener(false);
}

export function onOrenaPresence(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
