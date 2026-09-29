/* AGENT_CONTRACT §2.1 409 (`target_language_mismatch`): the learner's learning language changed in
   another tab or on another device after this UI built its request. "The UI re-reads the learner's
   learning language and applies it as any change of learning language" - read the way the shell's
   own boot reads it (GET /api/session/bootstrap), applied the way Settings applies a change of
   learning language (the device learner memory for the new language, the counts), and nothing is
   resent: the message is back in the composer for the learner to send. Shared by Orena Home and the
   Contextual panel. */
import { api } from '../../infrastructure/api.js';
import { learningLanguage } from '../../product/languages.js';
import { learnerMemory } from '../../product/memory.js';
import { context as shellContext, updateContext, refreshCounts } from '../../shell/context.js';
import { safeStorage } from './memory-store.js';

export async function refreshLearningLanguage() {
  try {
    const bootstrap = await api.sessionBootstrap();
    const language = learningLanguage(bootstrap?.language?.active);
    const state = shellContext();
    if (language === state.language) return;
    updateContext({ language, memory: learnerMemory(safeStorage(), state.owner, language) });
    refreshCounts().catch(() => {});
  } catch {
    /* The learner can still retry by hand; nothing here is a reason to fail the turn louder. */
  }
}
