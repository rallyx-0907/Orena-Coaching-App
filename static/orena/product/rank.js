/* Where a learner stands on the rank ladder.

   Two design sources speak about ranks and they do not agree, so this module
   holds the join between them and nothing else:

   - **"Orena Rank Frame Master v2"** is the rank *system*: thirty-two ranks in
     eight bands, and the crystal each one is made of. It states no thresholds -
     it is a material specification.
   - **The Progress frame** draws a ladder of *twenty* tiles and states a word
     count on each one. Its first sixteen names are the master's first sixteen,
     and its last four (Archivist, Aurora, Celestial, Paragon) are the master's
     25th, 28th, 29th and 32nd.

   So the thresholds are kept **by name**, not by position: a number the design
   states for Archivist is Archivist's number wherever Archivist sits. A rank
   the design gives no number to has none here either - it is drawn as a rank
   nobody can reach by counting, rather than given an invented threshold.
   `docs/project/UI_BACKEND_GAPS.md` records both the disagreement and the
   fourteen numbers the product still owes.

   The measure is the learner's own mastered words, which Orena really does
   count. Nothing here invents a rank, and the two screens that show one -
   Progress and Hồ sơ - read it from here so they cannot disagree. */
import { RANK_NAMES } from '../ui/rank-frame.js';

/* The Progress frame's own tiles, name to words. */
export const RANK_THRESHOLDS = {
  Initiate: 50,
  Apprentice: 150,
  Scribe: 300,
  Reader: 500,
  Cantor: 700,
  Artisan: 950,
  Adept: 1200,
  Voyager: 1450,
  Linguist: 1600,
  Luminary: 3000,
  Oracle: 4500,
  Sage: 6000,
  Maestro: 8000,
  Herald: 10000,
  Polyglot: 13000,
  Archivist: 16000,
  Aurora: 20000,
  Celestial: 25000,
  Paragon: 30000,
};

export const RANK_LADDER = RANK_NAMES.map((name, index) => ({
  tier: index + 1,
  name,
  /* Virtuoso is the one the frame draws "BẬC HIỆN TẠI" over instead of a
     number, so it carries none. */
  words: Object.prototype.hasOwnProperty.call(RANK_THRESHOLDS, name) ? RANK_THRESHOLDS[name] : null,
}));

/* The highest rank whose stated threshold the learner has passed. A rank with
   no stated threshold cannot be reached by counting, so it is stepped over
   rather than guessed at. Zero means they hold no rank yet. */
export function tierOf(known) {
  const words = Number(known) || 0;
  let tier = 0;
  RANK_LADDER.forEach((entry) => {
    if (entry.words !== null && words >= entry.words) tier = entry.tier;
  });
  return tier;
}

/* The next rank the learner can actually reach, or null at the top of what the
   design has numbered. */
export function nextTier(known) {
  const words = Number(known) || 0;
  const current = tierOf(known);
  return RANK_LADDER.find((entry) => entry.tier > current && entry.words !== null && words < entry.words) || null;
}

export function tierEntry(tier) {
  return RANK_LADDER[Math.max(0, Math.min(RANK_LADDER.length, Math.round(Number(tier) || 0))) - 1] || null;
}

export const RANK_TOTAL = RANK_LADDER.length;

/* What "mastered" counts, in one place: a saved word the learner has carried
   past the third review stage. Progress shows the same number on its own
   panel, so the rank and that panel can never tell two different stories. */
export function masteredCount(items) {
  if (!Array.isArray(items)) return null;
  return items.filter((item) => (Number(item && item.review_stage) || 0) >= 3).length;
}
