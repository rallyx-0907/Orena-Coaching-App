/* Where the learner is in reading and listening content, kept on the server (D4 I4; D-104 H-12).

   The place is navigation state on the learner's `started` relationship to a piece of content, not
   learning evidence. The device's continuation list stays the cache and the fallback, and a device
   value the server does not hold stays readable (D-104 H-6: nothing is uploaded in bulk; a place is
   written when the learner next opens that content). The server answers `coalesced` to a write it
   already has, so this never throttles on its own.

   Only reading, listening and books have a place: a conversation, a piece of writing or a grammar
   point is not synced (product/intent.js `continuationExperience` is the one classifier). */
import { request } from '../infrastructure/api.js';
import { continuationExperience } from './intent.js';

const JSON_HEADERS = { 'Content-Type': 'application/json' };

/* The server's kind for a continuation entry, or '' when it has none. */
export function placeKind(entry) {
  const id = String(entry?.id || '');
  if (!id || id.length > 255) return '';
  // Speaking over media keeps its position on the same existing content relationship.
  if (id.startsWith('media:') && ['speaking', 'speaking_compare'].includes(entry?.intent)) return 'listening';
  const experience = continuationExperience(entry);
  if (id.startsWith('book:')) return 'book';
  if (experience === 'reading') return 'reading';
  if (experience === 'listening' || experience === 'practice') return 'listening';
  return '';
}

/* The device entry -> the request body, or null when there is nothing to send. */
export function placeBody(entry) {
  const kind = placeKind(entry);
  if (!kind) return null;
  const place = entry?.place;
  const within = Number.isFinite(place?.within) ? place.within : undefined;
  const body = {
    title: String(entry.title || '').slice(0, 240),
    intent: entry.intent || null,
    segment: String(entry.segment || '').slice(0, 255),
    context: String(entry.context || '').slice(0, 240),
  };
  if (place && Number.isInteger(place.index) && Number.isInteger(place.total)) {
    body.index = place.index;
    body.total = place.total;
  } else if (kind !== 'listening') {
    return null; // a text with no position is not a place worth keeping
  } else {
    body.index = 1;
    body.total = 1;
  }
  if (within !== undefined) body.within = within;
  body.finished = within !== undefined && within >= 100;
  if (entry.settle) body.settle = true;
  return { kind, place: body };
}

/* What was last sent for each id, so a reader moving within a paragraph is not a request per event.
   The server coalesces the same way (30 s, no boundary crossed); this only saves the round trip. */
const THROTTLE_MS = 30000;
const sent = new Map();
/* Places this page let go of (removed, or content that is gone: #446). Until the learner opens one again, a
   server list that still carries it - a clear that has not landed, or failed - does not bring it back, so no
   screen asks for a retired lesson on every visit. */
const LET_GO_KEY = 'orena.continue.letGo.v2';
const LET_GO_LIMIT = 50;
/* `{ owner, ids }`: the hold belongs to one account; another account (or a sign-out) starts with none. */
function readLetGo() {
  try {
    const stored = JSON.parse(globalThis.localStorage?.getItem(LET_GO_KEY) || '{}');
    const ids = Array.isArray(stored?.ids) ? stored.ids.filter((id) => typeof id === 'string' && id.length <= 255) : [];
    return { owner: typeof stored?.owner === 'string' ? stored.owner : '', ids: ids.slice(-LET_GO_LIMIT) };
  } catch {
    return { owner: '', ids: [] };
  }
}
/* Kept on this device too, so a reload against a server that still lists the place (its clear answered 404 before
   the server accepted clears of unavailable media) does not ask for the gone lesson again. */
const letGo = new Set();
let letGoOwner = '';
function keepLetGo() {
  try {
    globalThis.localStorage?.setItem(LET_GO_KEY, JSON.stringify({ owner: letGoOwner, ids: [...letGo].slice(-LET_GO_LIMIT) }));
  } catch {
    /* private mode or storage full: the in-page hold still applies */
  }
}

/* The signed-in account (shell/context.js): its own hold is read back; another account's is dropped. */
export function setPlaceOwner(owner) {
  const next = String(owner || '');
  if (next === letGoOwner && letGo.size) return;
  letGo.clear();
  letGoOwner = next;
  const stored = readLetGo();
  if (stored.owner === next) stored.ids.forEach((id) => letGo.add(id));
  else forgetStoredLetGo();
}

function forgetStoredLetGo() {
  try {
    globalThis.localStorage?.removeItem(LET_GO_KEY);
  } catch {
    /* nothing stored, or storage unavailable */
  }
}

/* Sign-out: nothing of this account's hold stays for the next one. */
export function forgetLetGo() {
  letGo.clear();
  letGoOwner = '';
  forgetStoredLetGo();
}

function crosses(previous, body) {
  return ['index', 'total', 'finished', 'segment', 'intent', 'title', 'context'].some((key) => previous.place[key] !== body.place[key]);
}

/* Best effort: the device already holds the place, so a failed write costs nothing the learner can see. */
export function sendPlace(entry, now = Date.now()) {
  const body = placeBody(entry);
  if (!body) return Promise.resolve(null);
  if (letGo.delete(entry.id)) keepLetGo();
  const previous = sent.get(entry.id);
  if (previous && !entry.settle && now - previous.at < THROTTLE_MS && !crosses(previous, body)) return Promise.resolve(null);
  sent.set(entry.id, { at: now, place: body.place });
  return request(`/api/continue/${encodeURIComponent(entry.id)}`, { method: 'PUT', headers: JSON_HEADERS, body: JSON.stringify(body) }).catch(() => null);
}

export function clearPlace(id) {
  const kind = placeKind({ id });
  if (!kind) return Promise.resolve(null);
  sent.delete(id);
  letGo.delete(id);
  letGo.add(id);
  keepLetGo();
  return request(`/api/continue/${encodeURIComponent(id)}`, {
    method: 'PUT',
    headers: JSON_HEADERS,
    body: JSON.stringify({ kind, place: { cleared: true } }),
  }).catch((error) => (error?.status === 404 ? { status: 'gone' } : null)); // 404: nothing left to clear - done
}

/* A server item -> the device's continuation entry shape. */
export function entryFromServer(item) {
  const place = item?.place || {};
  return {
    id: String(item.content_id),
    title: String(place.title || ''),
    segment: String(place.segment || ''),
    intent: place.intent || null,
    source_url: '',
    excerpt: '',
    context: String(place.context || ''),
    // When the server last saw this place; the Notifications row shows it (a device-made entry has none).
    at: typeof item.place_at === 'string' ? item.place_at.slice(0, 40) : '',
    place: Number.isInteger(place.index) && Number.isInteger(place.total)
      ? { index: place.index, total: place.total, ...(Number.isFinite(place.within) ? { within: place.within } : {}) }
      : null,
  };
}

/* The server's places first (newest first), then the device's own that the server does not hold. */
export function mergeContinuation(serverItems, deviceEntries) {
  const fromServer = (Array.isArray(serverItems) ? serverItems : []).map(entryFromServer).filter((entry) => !letGo.has(entry.id));
  const seen = new Set(fromServer.map((entry) => entry.id));
  const legacy = (Array.isArray(deviceEntries) ? deviceEntries : []).filter((entry) => entry && !seen.has(entry.id));
  return [...fromServer, ...legacy].slice(0, 20);
}

export async function loadServerContinuation() {
  const result = await request('/api/continue?limit=20').catch(() => null);
  return Array.isArray(result?.items) ? result.items : null;
}

/* Read the server's places into this memory (a failed read leaves the device list as it was). */
export async function syncContinuation(memory) {
  if (!memory) return false;
  const items = await loadServerContinuation();
  if (!items) return false;
  memory.replaceContinuation(mergeContinuation(items, memory.value.continuation));
  return true;
}
