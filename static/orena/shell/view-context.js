/* What the learner is looking at, in AGENT_CONTRACT §3 terms (surface id, content/essay/take ids, the selected
   line or word), for an Orena conversation that is already running (§9 R30: live voice keeps a session open
   across routes and is told when the view changes). The router sets the screen's baseline on every route; a
   screen adds what the learner selects inside it. Screens never know whether anyone is listening. */
const listeners = new Set();
let current = {};

const ROUTE_CONTENT = {
  'reading.workspace': (params) => ({ content_id: String(params.id || '') }),
  'listening.workspace': (params) => ({ content_id: params.id ? `media:${params.id}` : '' }),
  'listening.dictation': (params) => ({ content_id: params.id ? `media:${params.id}` : '' }),
  'speaking.workspace': (params) => ({ content_id: String(params.id || '') }),
  'writing.review': (params) => ({ essay_id: String(params.id || '') }),
  'writing.revision': (params) => ({ essay_id: String(params.id || '') }),
};

function emit() {
  for (const listener of listeners) listener(current);
}

function clean(context) {
  return Object.fromEntries(Object.entries(context).filter(([, value]) => value !== '' && value != null));
}

/* The router, after a screen mounts: the route's §6.1 id is the surface, with the ids its path carries. */
export function setRouteView(route, params = {}) {
  const surface = route?.intent || 'home';
  current = clean({ surface, ...(ROUTE_CONTENT[surface]?.(params) || {}) });
  emit();
}

/* A screen, when the learner selects something inside it (a line, a word): merged over the route's baseline. */
export function setViewSelection(selectedItem) {
  const next = { ...current };
  if (selectedItem && String(selectedItem.text || '').trim()) next.selected_item = selectedItem;
  else delete next.selected_item;
  current = next;
  emit();
}

export function viewContext() {
  return current;
}

export function onViewContext(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
