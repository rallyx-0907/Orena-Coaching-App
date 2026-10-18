/* Orena's device memory (AGENT_CONTRACT §5.4, §5.6, §10): the Orena Home conversation, the
   learner's coach notes and the address note (how Orena says "I" and "you") live on this device,
   per learner, never in the account (D-085/D-086; an account store needs its own architecture
   review). DOM-free apart from the Storage it is given. Bounded: 20 coach notes and 2 KB of them in
   a request; the conversation keeps its last 40 messages. The address note is different from a coach
   note (§5.6): one per support language (`address-<lang>`), never decays or expires, is never among
   the notes a request sends, and is read back for the current support language. */
import { LIMITS, NOTE_KINDS, addressNoteId, normalizeAddress } from './contract.js';

const MESSAGES_KEPT = 40;
const DECAY_PER_DAY = 0.02;
const DROP_BELOW = 0.15;

export function agentMemory(storage, owner) {
  const key = `orena.agent.v1:${encodeURIComponent(owner || 'local')}`;
  let value = { thread: [], notes: [] };
  try {
    const parsed = JSON.parse(storage.getItem(key) || 'null');
    if (parsed && typeof parsed === 'object') {
      value.thread = Array.isArray(parsed.thread) ? parsed.thread.slice(-MESSAGES_KEPT) : [];
      value.notes = Array.isArray(parsed.notes) ? parsed.notes.filter(validNote) : [];
    }
  } catch {
    value = { thread: [], notes: [] };
  }
  const save = () => {
    try {
      storage.setItem(key, JSON.stringify(value));
      return true;
    } catch {
      return false;
    }
  };

  return {
    thread: () => value.thread.slice(),
    appendMessage(message) {
      value.thread = [...value.thread, message].slice(-MESSAGES_KEPT);
      return save();
    },
    replaceLast(message) {
      value.thread = [...value.thread.slice(0, -1), message];
      return save();
    },
    clearThread() {
      value.thread = [];
      return save();
    },

    /* Coach notes and the address note, weighted and decaying (address never does); the agent
       proposes, the device stores (§5.4). The full list, for the privacy screen (§10). */
    notes: (now = Date.now()) => live(value.notes, now),
    applyUpdate(update, now = Date.now()) {
      if (!update || typeof update !== 'object') return false;
      /* §5.4 `stored` (v9): "server" means the account already applied it, so nothing is stored here; a
         remove drops a device copy only when id AND text match (a server id could collide with an
         unrelated device note's id). Absent or "device" is the v8 behaviour. */
      if (update.stored === 'server' && update.op !== 'remove') return false;
      if (update.op === 'remove' && update.note?.id) {
        const same = (note) => (update.stored === 'server'
          ? note.id === update.note.id && note.kind !== 'address'
            && typeof update.note.text === 'string' && note.text === update.note.text
          : note.id === update.note.id);
        value.notes = value.notes.filter((note) => !same(note));
        return save();
      }
      if (update.op === 'upsert' && validNote(update.note)) {
        const note = { ...update.note, last_reinforced: update.note.last_reinforced || new Date(now).toISOString() };
        const kept = new Set(live([...value.notes.filter((n) => n.id !== note.id), note], now).map((n) => n.id));
        // Stored as given; the weight decays only when read, from last_reinforced.
        value.notes = [...value.notes.filter((n) => n.id !== note.id), note].filter((n) => kept.has(n.id));
        return save();
      }
      return false;
    },
    removeNote(id) {
      value.notes = value.notes.filter((note) => note.id !== id);
      return save();
    },
    /* The notes a request carries: at most 20, most weighted first, within 2 KB (§3). The address
       note is never among them - it travels as `context.address` instead (§5.6). */
    requestNotes(now = Date.now()) {
      const out = [];
      let bytes = 2;
      for (const note of live(value.notes, now)
        .filter((note) => note.kind !== 'address')
        .sort((a, b) => b.weight - a.weight)) {
        const size = serverNoteBytes(note) + 1;
        if (out.length >= LIMITS.coachNotes || bytes + size + NOTES_MARGIN > LIMITS.coachNotesBytes) break;
        out.push(note);
        bytes += size;
      }
      return out;
    },
    /* The stored address for a support language (contract code), or null when none is stored - the
       caller then uses that language's default (§5.6). Read back, never re-derived. */
    addressFor(lang, now = Date.now()) {
      const id = addressNoteId(lang);
      const note = live(value.notes, now).find((n) => n.kind === 'address' && n.id === id);
      return note ? note.address : null;
    },
  };
}

/* The server refuses the WHOLE turn (422, no retry) when its measure of coach_notes passes 2048 bytes. That
   measure (writing_coach/agent/schemas.py `coach_notes_bytes`) is the compact UTF-8 JSON of the VALIDATED
   notes dumped by pydantic: every field present in model order, `expires_at` and `address` as explicit
   nulls, `weight` as a Python float (`1.0`, never `1`), `last_reinforced` as pydantic's datetime text
   (`2026-10-18T07:30:15.123000Z`, or the offset form `+00:00`, 6 chars for the zone). Measure the same shape,
   with the datetime at its longest rendering. NOTES_MARGIN is a small slack for whatever the two
   serialisers still disagree on; it is on the whole list, not per note. The 20 / 2048 limits are unchanged. */
const NOTES_MARGIN = 16;
const DATETIME_LONGEST = '2026-10-18T07:30:15.123456+00:00';

export function serverNoteBytes(note) {
  const longest = (text) => (String(text).length > DATETIME_LONGEST.length ? String(text) : DATETIME_LONGEST);
  const shaped = {
    id: note.id,
    kind: note.kind,
    text: note.text,
    weight: note.weight,
    last_reinforced: longest(note.last_reinforced ?? ''),
    expires_at: note.expires_at ? longest(note.expires_at) : null,
    address: note.address ?? null,
  };
  let json = JSON.stringify(shaped);
  // Python renders a whole-number float as `1.0`; JSON.stringify gives `1`.
  if (Number.isInteger(Number(note.weight))) json = json.replace(/"weight":(-?\d+)(?=,)/, '"weight":$1.0');
  return new TextEncoder().encode(json).length;
}

function validNote(note) {
  if (!note || typeof note.id !== 'string') return false;
  if (note.kind === 'address') return validAddressNote(note);
  return (
    NOTE_KINDS.includes(note.kind) &&
    note.kind !== 'address' &&
    typeof note.text === 'string' &&
    note.text.length <= 400 &&
    Number.isFinite(Number(note.weight))
  );
}

/* §5.6: id is address-<lang> in contract codes, and the address itself must normalise for that
   language (drops what the language ignores; an invalid term refuses the whole note). */
function validAddressNote(note) {
  const lang = note.address && note.address.lang;
  if (!lang || note.id !== addressNoteId(lang)) return false;
  return Boolean(normalizeAddress(note.address, lang));
}

/* Weight decays with time since the note was last reinforced; expired or faded notes drop. The
   address note is different (§5.6): it never decays and has no expiry, so it always stays live. */
function live(notes, now) {
  return notes
    .map((note) => {
      if (note.kind === 'address') return { ...note, weight: 1 };
      const since = Date.parse(note.last_reinforced || '') || now;
      const days = Math.max(0, (now - since) / 86400000);
      return { ...note, weight: Math.max(0, Math.min(1, Number(note.weight) - days * DECAY_PER_DAY)) };
    })
    .filter((note) => (note.kind === 'address' ? true : note.weight >= DROP_BELOW && !(note.expires_at && Date.parse(note.expires_at) <= now)));
}
