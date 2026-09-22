/* The rank frame is generated, not drawn twenty times.
 *
 * "Orena Rank Frame Master v2" specifies one generator: a rank in, the whole
 * geometry out. These assertions pin what that means, so a later hand cannot
 * quietly replace a band's colour with a picture, flatten the five bands into
 * one, or let a 40px avatar carry the full twenty-layer crystal.
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
  LITE_SIZE,
} from '../static/orena/ui/rank-frame.js';

/* --- Twenty ranks in five bands of four -------------------------------- */

assert.equal(RANK_COUNT, 20, 'twenty ranks');
assert.equal(RANK_NAMES.length, 20);
assert.equal(new Set(RANK_NAMES).size, 20, 'no rank name repeats');
assert.equal(RANK_BANDS.length, 5, 'five bands');
assert.deepEqual(
  RANK_BANDS.map((b) => b.name),
  ['Amethyst', 'Sapphire', 'Orchid', 'Amber', 'Prismatic'],
);
for (const band of RANK_BANDS) {
  assert.equal(band.to - band.from, 3, `${band.name} covers four ranks`);
}
assert.equal(bandOf(1).name, 'Amethyst');
assert.equal(bandOf(4).name, 'Amethyst');
assert.equal(bandOf(5).name, 'Sapphire');
assert.equal(bandOf(10).name, 'Orchid');
assert.equal(bandOf(20).name, 'Prismatic');
assert.equal(rankName(10), 'Virtuoso');

/* A rank outside the scale is clamped, never rendered as a gap. */
assert.equal(clampRank(0), 1);
assert.equal(clampRank(99), 20);
assert.equal(clampRank('nonsense'), 1);

/* --- The crystal grows with the rank ----------------------------------- */

let previousFacets = 0;
for (let rank = 1; rank <= RANK_COUNT; rank += 1) {
  const { shape } = rankGeometry(rank);
  assert.ok(shape.facets >= previousFacets, `facets never go backwards at rank ${rank}`);
  previousFacets = shape.facets;
}
assert.equal(rankGeometry(1).shape.facets, 8, 'the first rank is the plainest');
assert.equal(rankGeometry(20).shape.facets, 36, 'the last rank is the most cut');

/* Layers appear where the master says they appear, and not before. */
assert.equal(rankGeometry(3).shape.petals, 0, 'no petals below rank 4');
assert.ok(rankGeometry(4).shape.petals > 0, 'petals from rank 4');
assert.equal(rankGeometry(8).shape.orbit, 0, 'no orbit below rank 9');
assert.equal(rankGeometry(9).shape.orbit, 1, 'the orbit arrives with Orchid');
assert.equal(rankGeometry(14).shape.prism, 0, 'no dispersion below rank 15');
assert.ok(rankGeometry(15).shape.prism > 0, 'dispersion from rank 15');
assert.equal(rankGeometry(16).shape.star2, 0, 'one star below rank 17');
assert.ok(rankGeometry(17).shape.star2 > 0, 'the second star is Prismatic only');

/* --- Small sizes drop layers, not quality ------------------------------ */

const bigTwenty = rankGeometry(20);
const smallTwenty = rankGeometry(20, { lite: true });
assert.equal(smallTwenty.shape.petals, 0, 'a small frame drops the petals');
assert.equal(smallTwenty.shape.shards, 0, 'and the shards');
assert.equal(smallTwenty.shape.orbit, 0, 'and the orbit');
assert.ok(smallTwenty.shape.ticks <= 24, 'and thins the engraved ring');
assert.equal(
  smallTwenty.shape.facets,
  bigTwenty.shape.facets,
  'but never the girdle: the facets are the rank',
);

/* The size alone decides it, so no caller has to remember. */
assert.ok(rankFrame({ rank: 20, size: LITE_SIZE, uid: 'a' }).length
  < rankFrame({ rank: 20, size: LITE_SIZE + 1, uid: 'b' }).length,
  'at and below 96px the frame is the lighter one');

/* --- One SVG, no pictures ---------------------------------------------- */

for (const rank of [1, 5, 9, 13, 17, 20]) {
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
