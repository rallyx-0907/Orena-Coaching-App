/* Orena Memory's one switch (D-226): account-wide, default ON, kept by the server
   (`GET /api/agent/memory`, `PUT /api/agent/memory/settings`). This module reads and writes it and keeps
   the last known value for the session, so a request can leave device coach notes out when the learner
   turned memory off. The server enforces OFF itself (it withholds notes and refuses to remember); the
   client gate is hygiene only. A server without memory (503 memory_unavailable) answers `null`: the row
   is not drawn at all. */
import { request } from '../infrastructure/api.js';
import { toContractLang } from './contract.js';

const KEY = 'orena.agent.memory-on';
let known = null;

function store() {
  try {
    return globalThis.localStorage || null;
  } catch {
    return null;
  }
}

/* The last known state: true until the learner is known to have turned it off. */
export function memoryOn() {
  if (known === null) {
    try {
      known = store()?.getItem(KEY) !== '0';
    } catch {
      known = true;
    }
  }
  return known;
}

function remember(enabled) {
  known = enabled;
  try {
    store()?.setItem(KEY, enabled ? '1' : '0');
  } catch {
    // The session value above still holds.
  }
}

/* true / false from the server, or null when memory is unavailable (503) or cannot be read. */
export async function readMemoryEnabled(language, fetcher = request) {
  try {
    const body = await fetcher(`/api/agent/memory?language=${encodeURIComponent(toContractLang(language))}`);
    if (typeof body?.enabled !== 'boolean') return null;
    remember(body.enabled);
    return body.enabled;
  } catch (error) {
    if (error?.status === 401) throw error;
    return null;
  }
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

export const __reset = () => { known = null; };
