/* Gate for the Reading source line (D-189): the learner list and detail payloads carry a `provenance`
   object (writing_coach/reading_provenance.py), and the three places the design draws a source draw its
   publisher - the Discover card's muted line (`c.source`), the Content Detail hero meta and the Reader
   toolbar's meta line. An older payload with no provenance falls back to the author, or to nothing. */
import assert from 'node:assert/strict';

const { publisherOf, sourceLine } = await import('../static/orena/product/provenance.js');
const { entryFromArticle, presentCard } = await import('../static/orena/screens/discover/model.js');
const { normalizeArticle, relatednessScore } = await import('../static/orena/screens/content/model.js');
const { toolbarMeta } = await import('../static/orena/screens/reader/model.js');

const provenance = {
  publisher: 'Global Voices',
  url: 'https://globalvoices.org/2026/10/rain',
  author: 'Peace News',
  license: { name: 'CC BY 3.0', url: 'https://creativecommons.org/licenses/by/3.0/' },
  attribution_required: 'required',
  text: 'Originally published by Global Voices (by Peace News), CC BY 3.0.',
};

// 1. The helpers.
assert.equal(publisherOf({ provenance }), 'Global Voices');
assert.equal(publisherOf({ provenance: { publisher: '  ' } }), '');
assert.equal(publisherOf({}), '');
assert.equal(publisherOf(null), '');
assert.equal(sourceLine({ provenance, attribution: { author: 'Someone' } }), 'Global Voices', 'the publisher wins over the author');
assert.equal(sourceLine({ attribution: { author: 'Aesop' } }), 'Aesop', 'an older payload keeps its author');
assert.equal(sourceLine({}), '', 'no source is shown rather than invented');

// 2. The Discover card: the muted source line is the publisher, in English, Vietnamese and Chinese
// payloads alike (the publisher is a name, not translated copy).
for (const language of ['en', 'zh']) {
  const entry = entryFromArticle({ id: 'a1', title: 'T', language, level: 'B2', provenance }, []);
  assert.equal(entry.author, 'Global Voices');
  const card = presentCard(entry, Object.assign((key) => key, { plural: (key) => key }));
  assert.equal(card.meta, 'Global Voices', 'the card draws the publisher as its source line');
}
assert.equal(entryFromArticle({ id: 'a2', title: 'T' }, []).author, '', 'no provenance, no source line');

// 3. Content Detail hero meta source, and the related-by-source score.
assert.equal(normalizeArticle({ title: 'T', provenance, attribution: { author: 'Peace News' } }).source, 'Global Voices');
assert.equal(normalizeArticle({ title: 'T', attribution: { author: 'Aesop' } }).source, 'Aesop');
assert.ok(relatednessScore({ source: 'Global Voices' }, { provenance }) > 0, 'two articles of one publisher are related');
assert.ok(relatednessScore({ source: 'Global Voices' }, { author: 'Someone Else', provenance }) > 0, 'the candidate publisher is compared before any author field');
assert.ok(relatednessScore({ source: 'M. Okafor' }, { author: 'M. Okafor' }) > 0, 'a book candidate still matches on its author');

// 4. The Reader toolbar draws the publisher where the frame draws `rdDocMeta`.
assert.equal(
  toolbarMeta({ isBook: false, author: sourceLine({ provenance }), kindLabel: 'Article', level: 'C1', pageLabel: 'p. 1 of 3' }),
  'Global Voices · Article · C1 · p. 1 of 3',
);

console.log('reading provenance gate: ok');
