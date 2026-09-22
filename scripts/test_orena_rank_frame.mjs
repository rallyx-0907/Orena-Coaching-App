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
import { RANK_LADDER, RANK_TOTAL, masteredCount, nextTier, tierOf } from '../static/orena/product/rank.js';

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

/* --- The ladder: the design's own thresholds, joined by name ------------ */

assert.equal(RANK_TOTAL, 32, 'the ladder is the master ladder');
assert.equal(RANK_LADDER[0].words, 50, 'Initiate is fifty words');
assert.equal(RANK_LADDER.find((e) => e.name === 'Archivist').words, 16000,
  'a threshold follows its name, not its position');
assert.equal(RANK_LADDER.find((e) => e.name === 'Virtuoso').words, null,
  'the frame states no number for Virtuoso, so neither do we');
assert.equal(RANK_LADDER.find((e) => e.name === 'Navigator').words, null,
  'and none for the ranks it never drew');

/* Nobody holds a rank they have not passed the stated threshold for. */
assert.equal(tierOf(0), 0, 'no words, no rank');
assert.equal(tierOf(49), 0);
assert.equal(tierOf(50), 1, 'the first rank is earned at fifty');
assert.equal(tierOf(1600), 9, 'Linguist at 1 600');
assert.equal(tierOf(2999), 9, 'and Virtuoso cannot be counted into');
assert.equal(tierOf(3000), 11, 'Luminary is the next one the design numbers');
assert.equal(nextTier(0).name, 'Initiate');
assert.equal(nextTier(30000), null, 'nothing beyond the last stated threshold');

/* One rule for "mastered", so the rank and the panel that shows the same
   number cannot disagree. */
assert.equal(masteredCount(null), null, 'an unreadable library is not zero');
assert.equal(masteredCount([{ review_stage: 3 }, { review_stage: 1 }, {}]), 1);

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
