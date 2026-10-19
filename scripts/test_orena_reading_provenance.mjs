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

// 5. The Reader's source footnote (READER_SOURCE_LINE_2026-10-14): creditOf and its copy.
const { creditOf, safeHttpUrl } = await import('../static/orena/product/provenance.js');
const { readFileSync } = await import('node:fs');

const credit = creditOf({ provenance });
assert.equal(credit.publisher, 'Global Voices');
assert.equal(credit.url, 'https://globalvoices.org/2026/10/rain');
assert.equal(credit.author, 'Peace News', 'an author distinct from the publisher is kept');
assert.deepEqual(credit.license, { name: 'CC BY 3.0', url: 'https://creativecommons.org/licenses/by/3.0/' }, 'licence linked');
assert.equal(creditOf({ provenance: { ...provenance, author: ' global voices ' } }).author, '', 'author equal to the publisher is not repeated');
assert.deepEqual(creditOf({ provenance: { ...provenance, license: { name: 'Public domain', url: '' } } }).license, { name: 'Public domain', url: '' }, 'licence name alone is plain text');
assert.equal(creditOf({ provenance: { ...provenance, license: null } }).license, null, 'no licence determined, none shown');
assert.equal(creditOf({ provenance: { ...provenance, license: { name: 'unknown', url: '' } } }).license, null);
assert.equal(creditOf({}), null);
assert.equal(creditOf({ provenance: { publisher: '', url: '' } }), null, 'nothing to credit, nothing drawn');
assert.equal(creditOf({ provenance: { publisher: 'Unknown', url: '' } }), null, 'the word unknown is never a credit');
assert.equal(creditOf({ provenance: { publisher: 'VOA', author: 'Unknown', url: 'https://x.org/a' } }).author, '');

// URL safety: only http(s) is ever a link.
for (const bad of ['javascript:alert(1)', 'JaVaScript:alert(1)', 'data:text/html,x', 'vbscript:x', '//evil.test', 'not a url', '', null]) {
  assert.equal(safeHttpUrl(bad), '', `rejects ${bad}`);
}
assert.equal(safeHttpUrl('http://a.org/x'), 'http://a.org/x');
assert.equal(creditOf({ provenance: { publisher: 'A', url: 'javascript:alert(1)' } }).url, '');
assert.equal(creditOf({ provenance: { publisher: 'A', url: 'https://a.org', license: { name: 'CC BY 4.0', url: 'javascript:1' } } }).license.url, '');

// Copy, three languages (Original article / Bài gốc / 原文); no 'unknown' anywhere in the footnote copy.
const keys = ['srcLabel', 'srcBy', 'srcOriginal'];
const expected = { en: 'Original article', vi: 'Bài gốc', zh: '原文' };
const seen = new Set();
const copySource = readFileSync(new URL('../static/orena/screens/reader/copy.js', import.meta.url), 'utf8');
for (const [lang, original] of Object.entries(expected)) {
  assert.ok(copySource.includes(`srcOriginal: '${original}'`), `${lang} srcOriginal`);
  seen.add(lang);
}
assert.equal(seen.size, 3);
for (const key of keys) assert.equal((copySource.match(new RegExp(`${key}:`, 'g')) || []).length, 3, `${key} in en, vi, zh`);
assert.ok(!/src\w+: '[^']*unknown/i.test(copySource), 'no unknown in the source copy');

// The Reader renders it as a new-tab link with rel=noopener noreferrer, from the safe credit only.
const screenSource = readFileSync(new URL('../static/orena/screens/reader/screen.js', import.meta.url), 'utf8');
assert.ok(/rel="noopener noreferrer"/.test(screenSource) && /target="_blank"/.test(screenSource));
assert.ok(/doc\.credit/.test(screenSource), 'the footnote reads the sanitised credit, not the raw payload');
const readerSource = readFileSync(new URL('../static/orena/screens/reader/source.js', import.meta.url), 'utf8');
assert.ok(/credit: creditOf\(article\)/.test(readerSource) && !/credit:.*kind === 'book'/.test(readerSource), 'only a published article carries a credit');

// 6. D-194 thumbnails: imageOf trusts only our own same-origin copy with a credit; the Reader footnote carries the credit.
const { imageOf } = await import('../static/orena/product/provenance.js');
const ID = '0a52e5d0-0000-4000-8000-000000000001';
const own = { url: `/api/reading/articles/${ID}/image?v=4`, credit: 'Photo: A. Tran', alt: 'A flooded field' };
assert.deepEqual(imageOf({ image: own }), { url: own.url, cssUrl: `url("${own.url}")`, credit: 'Photo: A. Tran', alt: 'A flooded field' });
for (const bad of [
  { ...own, url: 'https://media.example.org/a.jpg' }, { ...own, url: '//media.example.org/a.jpg' }, { ...own, url: `/api/reading/articles/${ID}/image?v=1&x=2` },
  { ...own, url: `javascript:alert(1)` }, { ...own, url: `/api/reading/articles/../../etc/image` }, { ...own, url: `/api/reading/articles/${ID}/image")` },
  { ...own, credit: '' }, { ...own, credit: '   ' }, null, 'x', {},
]) assert.equal(imageOf({ image: bad }), null, `no picture for ${JSON.stringify(bad)}`);
assert.equal(imageOf({}), null);
assert.equal(imageOf({ image: { ...own, credit: '', typographic: true } }).credit, '', 'a typographic cover needs no credit (D-240)');
assert.equal(creditOf({ provenance, image: { ...own, credit: '', typographic: true } }).image, '');
assert.equal(creditOf({ provenance, image: own }).image, 'Photo: A. Tran', 'the picture credit joins the footnote');
assert.equal(creditOf({ provenance }).image, '', 'no picture, no picture credit');
assert.equal(creditOf({ provenance: { publisher: '', url: '' }, image: own }).image, 'Photo: A. Tran');
for (const [lang, label] of Object.entries({ en: 'Image: {name}', vi: 'Ảnh: {name}', zh: '图片：{name}' })) {
  assert.ok(copySource.includes(`srcImage: '${label}'`), `${lang} srcImage`);
}
assert.ok(/c\.image \? sep\(t\('srcImage'/.test(screenSource), 'the footnote draws the picture credit');

console.log('reading provenance gate: ok');
