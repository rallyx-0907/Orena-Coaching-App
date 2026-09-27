/* The Reader's own display preferences: text size, typeface, line spacing, measure. Kept as one
   device key ("orena.reader"), the way the whole app keeps a preference it owns (recall-modes.js,
   memory.js) - clamped on the way in, never trusted raw off the device.

   Moved out of static/orena/ui/reading-room.js (old presentation, D-091) so the new Settings
   screen (static/orena/screens/settings/) can read and write the exact preference the Reader
   itself renders with, without importing old UI (the surface-agent brief's hard limit). Nothing
   about the values or the clamping changed in the move; static/orena/ui/reading-room.js re-exports
   these same names unchanged for its own existing callers (ui/reader.js, ui/lexical.js,
   scripts/test_orena_reading_room.mjs). */

export const READER_DEFAULTS = Object.freeze({
  size: 1,
  font: 'serif',
  spacing: 'normal',
  width: 'medium',
});

export const CHOICES = Object.freeze({
  font: ['serif', 'sans'],
  spacing: ['compact', 'normal', 'relaxed'],
  width: ['narrow', 'medium', 'wide'],
});

export const READER_SIZE = Object.freeze({ min: 0.85, max: 1.4, step: 0.05 });
export const LEADING = Object.freeze({ compact: 1.55, normal: 1.75, relaxed: 2 });
export const MEASURE = Object.freeze({ narrow: '36rem', medium: '44rem', wide: '50rem' });

export function readerSettings(raw) {
  const value = raw && typeof raw === 'object' ? raw : {};
  const settings = { ...READER_DEFAULTS };
  const size = Number(value.size);
  if (Number.isFinite(size))
    settings.size = Math.round(Math.min(READER_SIZE.max, Math.max(READER_SIZE.min, size)) * 100) / 100;
  for (const [key, allowed] of Object.entries(CHOICES))
    if (allowed.includes(value[key])) settings[key] = value[key];
  return settings;
}

export function readerPresentation(settings) {
  const s = readerSettings(settings);
  return {
    style: `--reader-scale: ${s.size}; --reader-leading: ${LEADING[s.spacing]}; --reader-measure: ${MEASURE[s.width]};`,
    font: s.font,
  };
}

/* Settings' Learning-tab "Reader text size" row draws a 3-way choice (S/M/L, the design's own
   shape for that row) over this same continuous `size` field - not a second setting the Reader
   would have to reconcile. S/M/L bucket to the field's own min/default/max, so a learner who picks
   "L" in Settings sees exactly the size the Reader's own A+/A- stepper would land on at its
   maximum. */
export const SIZE_BUCKETS = Object.freeze({ S: READER_SIZE.min, M: READER_DEFAULTS.size, L: READER_SIZE.max });

export function sizeBucketOf(size) {
  const value = Number(size);
  if (!Number.isFinite(value)) return 'M';
  const lowMid = (READER_SIZE.min + READER_DEFAULTS.size) / 2;
  const highMid = (READER_DEFAULTS.size + READER_SIZE.max) / 2;
  if (value <= lowMid) return 'S';
  if (value >= highMid) return 'L';
  return 'M';
}

/* The device key the Reader itself uses (static/orena/ui/reader.js's own `loadSettings`/
   `saveSettings`, unchanged): kept here too so Settings reads and writes the exact same stored
   preference rather than a second copy of the key string. */
export const READER_STORAGE_KEY = 'orena.reader';

export function readReaderSettings(storage = window.localStorage) {
  try {
    return readerSettings(JSON.parse(storage.getItem(READER_STORAGE_KEY) || 'null'));
  } catch {
    return readerSettings(null);
  }
}

export function writeReaderSettings(settings, storage = window.localStorage) {
  try {
    storage.setItem(READER_STORAGE_KEY, JSON.stringify(settings));
    return true;
  } catch {
    return false;
  }
}
