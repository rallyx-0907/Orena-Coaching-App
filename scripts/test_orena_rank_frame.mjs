/* The rank ladder is read, not recomputed.
 *
 * The crystal renderer (rank-frame) went with the retired UI (D-143);
 * the ladder reading in product/rank.js is still used by the Profile and
 * Progress screens, and its assertions stay here.
 */
import assert from 'node:assert/strict';
import { ladderTiles, openTierCount, rankProgress, rankSummary } from '../static/orena/product/rank.js';

/* --- The ladder is read, not recomputed -------------------------------- */

/* `writing_coach/product/rank_ladder.py` owns the thresholds and answers with
   the learner's rank on the vocabulary summary. What the browser owns is the
   reading of that answer: no screen counts words to find a rank, and a screen
   with no answer yet shows no rank rather than a wrong one. */
const summaryPayload = {
  summary: { saved: 1612, mastered: 1600, learning: 12, due: 3 },
  rank: 9,
  rank_total: 32,
  rank_name: 'Linguist',
  band: 'Orchid',
  next_rank_name: 'Luminary',
  next_rank_words: 3000,
  next_rank_remaining: 1400,
  ladder: [
    { tier: 1, name: 'Initiate', band: 'Amethyst', words: 50 },
    { tier: 9, name: 'Linguist', band: 'Orchid', words: 1600 },
    { tier: 10, name: 'Virtuoso', band: 'Orchid', words: null },
    { tier: 11, name: 'Luminary', band: 'Orchid', words: 3000 },
  ],
};

const state = rankSummary(summaryPayload);
assert.equal(state.rank, 9, 'the rank is the server\'s');
assert.equal(state.rankName, 'Linguist');
assert.equal(state.band, 'Orchid');
assert.equal(state.mastered, 1600);
assert.equal(state.nextRankRemaining, 1400);
assert.equal(rankProgress(state), 53, 'and so is how far along it is');

const tiles = ladderTiles(state);
assert.equal(tiles.length, 4, 'the ladder is the one that arrived');
assert.deepEqual(tiles.map((tile) => tile.open), [true, true, false, false]);
assert.deepEqual(tiles.map((tile) => tile.current), [false, true, false, false]);
assert.equal(tiles[2].words, null, 'a rank the design gives no number to stays without one');
assert.equal(openTierCount(state), 2);

/* Nothing read means nothing shown - never a rank nobody earned. */
const empty = rankSummary(null);
assert.equal(empty.known, false);
assert.equal(empty.rank, 0);
assert.deepEqual(ladderTiles(empty), []);
assert.equal(rankProgress(empty), 0);

console.log('test_orena_rank_frame.mjs: all assertions passed');
