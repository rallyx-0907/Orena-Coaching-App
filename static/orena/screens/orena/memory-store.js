/* Orena's device memory, opened once per learner and shared by everything on this page that reads or
   writes it: Home's thread, the Contextual panel's coach-note updates, the coach-notes sheet. Each
   `agentMemory()` keeps its own copy of what it read from storage and writes that whole copy back,
   so two instances of the same learner's memory would overwrite each other - a note deleted in the
   sheet would come back the next time Home saved a message. One instance per learner (`owner`)
   means there is one copy to change. */
import { agentMemory } from '../../agent/memory.js';
import { context as shellContext } from '../../shell/context.js';

let shared = null;

/* Shared with language-sync.js - both read the same device storage the same defensive way. */
export function safeStorage() {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function sharedMemory() {
  const owner = shellContext().owner || 'local';
  if (!shared || shared.owner !== owner) shared = { owner, memory: agentMemory(safeStorage(), owner) };
  return shared.memory;
}
