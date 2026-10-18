/* Orena Memory's one switch (D-226): account-wide, default ON, kept by the server
   (`GET /api/agent/memory`, `PUT /api/agent/memory/settings`). This module reads and writes it and keeps
   the last known value, per account, so a request can leave device coach notes out when the learner
   turned memory off. The server enforces OFF itself (it withholds notes and refuses to remember); the
   client gate is hygiene only. A server without memory (503 memory_unavailable), or one that does not
   answer in time, gives `null`: the Settings row is not drawn at all. */
import { request } from '../infrastructure/api.js';
import { toContractLang } from './contract.js';

const KEY = 'orena.agent.memory-on';
const READ_TIMEOUT_MS = 4000;
let owner = 'local';
let known = null;
let refreshed = '';

function store() {
  try {
    return globalThis.localStorage || null;
  } catch {
    return null;
  }
}

const keyOf = () => `${KEY}:${encodeURIComponent(owner)}`;

/* The shell tells us whose device this is (the same owner as the device memory). A different account
   inherits nothing: the cached value and the "already refreshed" mark are dropped. */
export function setMemoryOwner(next) {
  const value = String(next || 'local');
  if (value === owner) return;
  owner = value;
  known = null;
  refreshed = '';
}

/* The last known state: true until the learner is known to have turned it off. */
export function memoryOn() {
  if (known === null) {
    try {
      known = store()?.getItem(keyOf()) !== '0';
    } catch {
      known = true;
    }
  }
  return known;
}

function remember(enabled) {
  known = enabled;
  try {
    store()?.setItem(keyOf(), enabled ? '1' : '0');
  } catch {
    // The in-memory value above still holds.
  }
}

/* Sign-out: nothing of this account's switch stays on the device. */
export function clearMemoryState() {
  known = null;
  refreshed = '';
  try {
    store()?.removeItem(keyOf());
  } catch {
    // Nothing to clear.
  }
}

const raced = (promise, ms) => new Promise((resolve, reject) => {
  const timer = setTimeout(() => resolve(undefined), ms);
  promise.then((value) => { clearTimeout(timer); resolve(value); }, (error) => { clearTimeout(timer); reject(error); });
});

/* true / false from the server, or null when memory is unavailable (503), slow (no answer within the
   timeout) or cannot be read. A 401 is rethrown so the signed-out handling is not hidden. */
export async function readMemoryEnabled(language, fetcher = request, timeoutMs = READ_TIMEOUT_MS) {
  try {
    const body = await raced(fetcher(`/api/agent/memory?language=${encodeURIComponent(toContractLang(language))}`), timeoutMs);
    if (typeof body?.enabled !== 'boolean') return null;
    remember(body.enabled);
    return body.enabled;
  } catch (error) {
    if (error?.status === 401) throw error;
    return null;
  }
}

/* At the start of an agent turn: read the server's state once per account and language so a switch changed
   on another device is honoured, not only when Settings opens. Never throws. */
export async function refreshMemoryEnabled(language, fetcher = request, timeoutMs = READ_TIMEOUT_MS) {
  const mark = `${owner}|${language}`;
  if (refreshed === mark) return memoryOn();
  refreshed = mark;
  try {
    await readMemoryEnabled(language, fetcher, timeoutMs);
  } catch {
    // Signed out or unreadable: the cached value stands.
  }
  return memoryOn();
}

/* One PUT for the whole account (never per language). Throws on any failure; the caller reverts. */
export async function writeMemoryEnabled(enabled, fetcher = request) {
  const body = await fetcher('/api/agent/memory/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: Boolean(enabled) }),
  });
  const next = typeof body?.enabled === 'boolean' ? body.enabled : Boolean(enabled);
  remember(next);
  return next;
}

export const __reset = () => { owner = 'local'; known = null; refreshed = ''; };
