/* Gate for D-240 (every learner-visible item has a thumbnail): a card with a stored typographic cover draws it as the
   artwork with the title as its accessible name (alt) and without the generated poster; a Reading cover needs no
   credit but only our own same-origin address counts; a vocabulary collection's thumbnail is only its own cover route. */
import assert from 'node:assert/strict';

const { mediaCard } = await import('../static/orena/kit/components.js');
const { imageOf } = await import('../static/orena/product/provenance.js');
const { collectionViewModel } = await import('../static/orena/screens/collection/model.js');
const { entryFromCollection } = await import('../static/orena/screens/discover/model.js');

const ID = '0a52e5d0-0000-4000-8000-000000000001';
const cover = { url: `/api/reading/articles/${ID}/image?v=3`, credit: '', typographic: true, alt: 'Why the sea is salty' };
const picture = imageOf({ image: cover });
assert.equal(picture.credit, '', 'a typographic cover has no credit');
assert.equal(imageOf({ image: { ...cover, typographic: false } }), null, 'only the backend-flagged cover goes without a credit');
assert.equal(imageOf({ image: { ...cover, url: 'https://media.example.org/x.svg' } }), null, 'never a third party address');

const TITLE = 'Why the sea is salty <b>&</b>';
const card = String(mediaCard({ title: TITLE, image: picture.cssUrl, cover: { icon: 'book-open', tint: 'var(--skill-read)' } }));
assert.ok(card.includes(cover.url), 'the cover is the artwork');
assert.match(card, /<span class="c-media__alt" role="img" aria-label="Why the sea is salty &lt;b&gt;&amp;&lt;\/b&gt;"><\/span>/, 'alt is the escaped title');
assert.ok(!card.includes('c-poster__glyph') && !card.includes('c-media__img--blank'), 'a picture replaces the generated poster');
const bare = String(mediaCard({ title: 'No picture', cover: { icon: 'book-open', tint: 'var(--skill-read)' } }));
assert.ok(bare.includes('c-poster') && !bare.includes('c-media__alt'), 'the poster fallback is unchanged and carries no alt box');

// Vocabulary collections: the thumbnail is the collection's own cover route (D-240), nothing else.
const route = '/api/vocabulary/library/collections/common-3000/cover?v=abc123def456';
assert.equal(collectionViewModel({ id: 'common-3000', title: 'T', thumbnail: { url: route, alt: 'T' } }).image, route);
for (const bad of ['https://i.example.org/c.png', '/api/other/cover', 'javascript:alert(1)', '/api/vocabulary/library/collections/x/cover?v=1&y=2', '']) {
  assert.equal(collectionViewModel({ id: 'x', title: 'T', thumbnail: { url: bad } }).image, '', `no picture for ${bad}`);
}
assert.equal(entryFromCollection({ id: 'common-3000', title: 'T', item_count: 3, thumbnail: { url: route } }).image, `url("${route}")`);
assert.equal(entryFromCollection({ id: 'common-3000', title: 'T', item_count: 3 }).image, '', 'no thumbnail in the payload: the poster fallback');

console.log('thumbnail cards gate: ok');
