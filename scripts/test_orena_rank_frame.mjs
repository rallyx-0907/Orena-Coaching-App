/* The rank frame is generated, not drawn thirty-two times.
 *
 * "Orena Rank Frame Master v2" specifies one generator: a rank in, the whole
 * geometry out. These assertions pin what that means, so a later hand cannot
 * quietly replace a band's colour with a picture, flatten the eight bands into
 * one, or let a 40px avatar carry the full crystal.
 */
import assert from 'node:assert/strict';
import {
  RANK_BANDS,
  RANK_COUNT,
  RANK_NAMES,
  bandOf,
  clampRank,
  rankFrame,
  rankGeometry,
  rankName,
  detailFor,
  LITE_SIZE,
  MID_SIZE,
} from '../static/orena/ui/rank-frame.js';
import { ladderTiles, openTierCount, rankProgress, rankSummary } from '../static/orena/product/rank.js';

/* --- Thirty-two ranks in eight bands of four --------------------------- */

assert.equal(RANK_COUNT, 32, 'thirty-two ranks');
assert.equal(RANK_NAMES.length, 32);
assert.equal(new Set(RANK_NAMES).size, 32, 'no rank name repeats');
assert.equal(RANK_BANDS.length, 8, 'eight bands');
assert.deepEqual(
  RANK_BANDS.map((b) => b.name),
  ['Amethyst', 'Sapphire', 'Orchid', 'Amber', 'Aquamarine', 'Carnelian', 'Moonstone', 'Prismatic'],
);
for (const band of RANK_BANDS) {
  assert.equal(band.to - band.from, 3, `${band.name} covers four ranks`);
}
assert.equal(bandOf(1).name, 'Amethyst');
assert.equal(bandOf(4).name, 'Amethyst');
assert.equal(bandOf(5).name, 'Sapphire');
assert.equal(bandOf(10).name, 'Orchid');
assert.equal(bandOf(20).name, 'Aquamarine');
assert.equal(bandOf(32).name, 'Prismatic');
assert.equal(rankName(10), 'Virtuoso', 'the master puts Virtuoso at ten');
assert.equal(rankName(32), 'Paragon', 'and Paragon at the top');

/* A rank outside the scale is clamped, never rendered as a gap. */
assert.equal(clampRank(0), 1);
assert.equal(clampRank(99), 32);
assert.equal(clampRank('nonsense'), 1);

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

/* --- The crystal grows with the rank ----------------------------------- */

let previousFacets = 0;
for (let rank = 1; rank <= RANK_COUNT; rank += 1) {
  const { shape } = rankGeometry(rank);
  assert.ok(shape.facets >= previousFacets, `facets never go backwards at rank ${rank}`);
  previousFacets = shape.facets;
}
assert.equal(rankGeometry(1).shape.facets, 8, 'the first rank is the plainest');
assert.equal(rankGeometry(32).shape.facets, 48, 'the last rank is the most cut');

/* Layers appear where the master says they appear, and not before. */
assert.equal(rankGeometry(3).shape.petals, 0, 'no petals below rank 4');
assert.ok(rankGeometry(4).shape.petals > 0, 'petals from rank 4');
assert.equal(rankGeometry(8).shape.orbit, 0, 'no orbit below rank 9');
assert.equal(rankGeometry(9).shape.orbit, 1, 'the orbit arrives with Orchid');
assert.equal(rankGeometry(14).shape.prism, 0, 'no dispersion below rank 15');
assert.ok(rankGeometry(15).shape.prism > 0, 'dispersion from rank 15');
assert.equal(rankGeometry(16).shape.star2, 0, 'one star below rank 17');
assert.ok(rankGeometry(17).shape.star2 > 0, 'the second star arrives with Aquamarine');

/* --- Three levels of detail, and the size alone decides ---------------- */

assert.equal(detailFor(64), 'min');
assert.equal(detailFor(LITE_SIZE), 'min');
assert.equal(detailFor(LITE_SIZE + 1), 'mid');
assert.equal(detailFor(MID_SIZE), 'mid');
assert.equal(detailFor(MID_SIZE + 1), false, 'the profile carries the full crystal');

const full = rankGeometry(32);
const mid = rankGeometry(32, { lite: 'mid' });
const min = rankGeometry(32, { lite: 'min' });
assert.ok(mid.shape.petals > 0 && mid.shape.orbit === 1, 'mid keeps the ornaments and the orbit');
assert.equal(mid.shape.sparks, 0, 'but not the sparks');
assert.ok(mid.shape.facets <= 20 && mid.shape.facets < full.shape.facets, 'and caps the girdle');
assert.equal(min.shape.petals, 0, 'min drops the petals');
assert.equal(min.shape.shards, 0, 'and the shards');
assert.equal(min.shape.orbit, 0, 'and the orbit');
assert.equal(min.shape.ticks, 0, 'and the engraved ring');
assert.ok(min.shape.facets > 0 && min.shape.facets <= 14, 'but never the girdle: the facets are the rank');

/* The same rank, drawn smaller, is never the heavier document. */
assert.ok(rankFrame({ rank: 32, size: LITE_SIZE, uid: 'a' }).length
  < rankFrame({ rank: 32, size: MID_SIZE, uid: 'b' }).length,
  'min is lighter than mid');
assert.ok(rankFrame({ rank: 32, size: MID_SIZE, uid: 'c' }).length
  < rankFrame({ rank: 32, size: MID_SIZE + 1, uid: 'd' }).length,
  'mid is lighter than the full crystal');

/* --- One SVG, no pictures ---------------------------------------------- */

for (const rank of [1, 5, 9, 13, 17, 21, 25, 29, 32]) {
  const html = rankFrame({ rank, size: 152, uid: `r${rank}` });
  assert.match(html, /<svg [^>]*viewBox="0 0 400 400"/, `rank ${rank} is one 400x400 svg`);
  assert.doesNotMatch(html, /<img\b/, `rank ${rank} uses no raster`);
  assert.doesNotMatch(html, /url\((?!#)/, `rank ${rank} fetches no image`);
  assert.match(html, /gradientUnits="userSpaceOnUse"/, `rank ${rank} lights every facet from one source`);
  assert.match(html, new RegExp(`data-rank="${rank}"`), 'the rank is on the element');
}

/* Two frames on one page must not share gradient ids, or the second would
   repaint the first. */
const a = rankFrame({ rank: 10, size: 152, uid: 'one' });
const b = rankFrame({ rank: 10, size: 152, uid: 'two' });
const idsOf = (html) => [...html.matchAll(/id="([^"]+)"/g)].map((m) => m[1]);
const shared = idsOf(a).filter((id) => idsOf(b).includes(id));
assert.deepEqual(shared, [], 'gradient ids are scoped to the instance');

/* An untrusted uid cannot escape the attribute. */
const injected = rankFrame({ rank: 3, size: 120, uid: '"><script>x</script>' });
assert.doesNotMatch(injected, /<script>/, 'the uid is sanitised');

console.log('test_orena_rank_frame.mjs: all assertions passed');
