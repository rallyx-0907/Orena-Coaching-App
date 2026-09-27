/* The Listening room's transcript display defaults: whether the panel follows the current line
   (autoscroll) and whether a line's translated meaning shows under it without being asked
   (meaning). One device key ("orena.stage"), kept the way the Reader keeps its own
   (product/reader-settings.js) - try/catch, defaulting on when the key is absent so a first visit
   behaves like the design's own default-on toggles.

   Word-class colour (`colors`) is deliberately never part of this persisted shape: the baseline's
   transcript has no switch for it yet, so a stored "on" would be a preference nobody could turn
   back off (see static/orena/ui/encounter.js).

   Moved out of static/orena/ui/encounter.js (old presentation, D-091) so the new Settings screen
   (static/orena/screens/settings/) can read and write the same real preference the Listening
   room's own toolbar sets, without importing old UI. encounter.js keeps its own local `stage`
   object (which also carries the un-persisted `colors` field) and now reads/writes it through the
   two functions below instead of two inline localStorage calls; the persisted shape and the
   default-on behaviour are unchanged. */

export const STAGE_KEY = 'orena.stage';

export function readStage(storage = window.localStorage) {
  try {
    const raw = JSON.parse(storage.getItem(STAGE_KEY) || 'null');
    return raw && typeof raw === 'object' ? raw : {};
  } catch {
    return {};
  }
}

export function writeStage(stage, storage = window.localStorage) {
  try {
    storage.setItem(STAGE_KEY, JSON.stringify(stage));
    return true;
  } catch {
    return false;
  }
}

/* The two fields Settings' Learning tab actually exposes ("Transcript auto-scroll", "Translation
   under transcript"), booleaned the way every other stored preference in this app is: a stored
   value is only ever true or false, and an absent key defaults on - never anything read raw off
   the device. `pinyin` (the transcript's own reading toggle, distinct from the account's pinyin
   preference in learner-profile) stays outside this function; Settings draws no row for it. */
export function transcriptDefaults(raw) {
  const value = raw && typeof raw === 'object' ? raw : {};
  return {
    autoscroll: value.autoscroll !== false,
    meaning: value.meaning !== false,
  };
}
