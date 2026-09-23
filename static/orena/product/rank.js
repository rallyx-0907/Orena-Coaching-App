/* Where a learner stands on the rank ladder - read, not recomputed.

   The ladder is the product's, and the product states it:
   `writing_coach/product/rank_ladder.py` owns the thirty-two ranks, the eight
   bands and the word counts the design gives them, and answers with the
   learner's rank on `GET /api/library/vocabulary/summary`. Every screen that
   shows a rank reads that one answer, so Hồ sơ and Tiến độ cannot tell two
   different stories, and no screen counts words in the browser to work it out.

   What is left here is the shape of that answer: small readers that a room can
   use without knowing the payload's field names, and the one number a
   component needs when the server has not answered yet.

   The crystal itself is still drawn in the browser - see `ui/rank-frame.js`,
   which needs only the rank number. */

const EMPTY_LADDER = [];

/* The summary payload, or a safe empty one. A room that failed to read the
   account still renders; it simply has no rank to show. */
export function rankSummary(payload) {
  const data = payload && typeof payload === 'object' ? payload : {};
  const counts = data.summary && typeof data.summary === 'object' ? data.summary : {};
  return {
    saved: Number(counts.saved || 0),
    mastered: Number(counts.mastered || 0),
    learning: Number(counts.learning || 0),
    due: Number(counts.due || 0),
    rank: Number(data.rank || 0),
    rankTotal: Number(data.rank_total || 0),
    rankName: String(data.rank_name || ''),
    band: String(data.band || ''),
    nextRankName: String(data.next_rank_name || ''),
    nextRankWords: data.next_rank_words == null ? null : Number(data.next_rank_words),
    nextRankRemaining: Number(data.next_rank_remaining || 0),
    ladder: Array.isArray(data.ladder) ? data.ladder : EMPTY_LADDER,
    known: Boolean(data.summary),
  };
}

/* How far along the learner is towards the next rank, as a percentage. Without
   a next rank there is nothing above them, so the bar is full. */
export function rankProgress(state) {
  if (!state || !state.nextRankWords) return state && state.rank ? 100 : 0;
  return Math.max(0, Math.min(100, Math.round((state.mastered / state.nextRankWords) * 100)));
}

/* The ladder as the tiles want it: which rung is open, which one the learner
   is standing on, and which have no number to reach at all. */
export function ladderTiles(state) {
  const current = state ? state.rank : 0;
  const mastered = state ? state.mastered : 0;
  return (state && state.ladder ? state.ladder : EMPTY_LADDER).map((entry) => {
    const words = entry.words == null ? null : Number(entry.words);
    const open = words !== null && mastered >= words;
    return {
      tier: Number(entry.tier || 0),
      name: String(entry.name || ''),
      band: String(entry.band || ''),
      words,
      open,
      current: Number(entry.tier || 0) === current,
    };
  });
}

export function openTierCount(state) {
  return ladderTiles(state).filter((tile) => tile.open).length;
}
