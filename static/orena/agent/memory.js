/* Orena's device memory (AGENT_CONTRACT §5.4, §10): the Orena Home conversation and the learner's
   coach notes live on this device, per learner, never in the account (D-085/D-086; an account store
   needs its own architecture review). DOM-free apart from the Storage it is given. Bounded:
   20 coach notes and 2 KB of them in a request; the conversation keeps its last 40 messages. */
import { LIMITS } from './contract.js';

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

    /* Coach notes, weighted and decaying; the agent proposes, the device stores (§5.4). */
    notes: (now = Date.now()) => live(value.notes, now),
    applyUpdate(update, now = Date.now()) {
      if (!update || typeof update !== 'object') return false;
      if (update.op === 'remove' && update.note?.id) {
        value.notes = value.notes.filter((note) => note.id !== update.note.id);
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
    /* The notes a request carries: at most 20, most weighted first, within 2 KB (§3). */
    requestNotes(now = Date.now()) {
      const out = [];
      let bytes = 2;
      for (const note of live(value.notes, now).sort((a, b) => b.weight - a.weight)) {
        const size = new TextEncoder().encode(JSON.stringify(note)).length + 1;
        if (out.length >= LIMITS.coachNotes || bytes + size > LIMITS.coachNotesBytes) break;
        out.push(note);
        bytes += size;
      }
      return out;
    },
  };
}

function validNote(note) {
  return (
    note &&
    typeof note.id === 'string' &&
    ['preference', 'goal', 'plan'].includes(note.kind) &&
    typeof note.text === 'string' &&
    note.text.length <= 400 &&
    Number.isFinite(Number(note.weight))
  );
}

/* Weight decays with time since the note was last reinforced; expired or faded notes drop. */
function live(notes, now) {
  return notes
    .map((note) => {
      const since = Date.parse(note.last_reinforced || '') || now;
      const days = Math.max(0, (now - since) / 86400000);
      return { ...note, weight: Math.max(0, Math.min(1, Number(note.weight) - days * DECAY_PER_DAY)) };
    })
    .filter((note) => note.weight >= DROP_BELOW && !(note.expires_at && Date.parse(note.expires_at) <= now));
}
