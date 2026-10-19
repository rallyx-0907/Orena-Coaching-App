/* Gate for the media source credit (D-239): the channel and the link to the original video come
   from the payload's provider metadata, are shared by the Listening room and Content detail, and
   the link opens safely (new tab, noopener noreferrer). */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const { mediaCredit } = await import('../static/orena/product/media-credit.js');
const { normalizeMedia } = await import('../static/orena/screens/content/model.js');
const { mapLesson } = await import('../static/orena/screens/listening/model.js');

const yt = "https://www.youtube.com/watch?v=abc123";
const curated = { asset: { source_url: 'https://example.com/asset' }, catalog: { source: { creator: 'Everyday English', provenance_url: yt, source_url: 'https://example.com/s' } } };
assert.deepEqual(mediaCredit(curated), { channel: 'Everyday English', url: yt }, 'provenance_url wins; the channel is the creator');
assert.deepEqual(mediaCredit({ catalog: { source: { creator: ' X ', source_url: yt } } }), { channel: 'X', url: yt });
assert.deepEqual(mediaCredit({ asset: { source_url: yt } }), { channel: '', url: yt }, 'no stored channel: the link alone, nothing invented');
assert.equal(mediaCredit(curated).url, yt);
for (const bad of ['javascript:alert(1)', 'http://www.youtube.com/watch?v=abc123', 'https://evil.example/watch?v=abc123', 'https://youtube.com.evil.example/x']) {
  assert.deepEqual(mediaCredit({ catalog: { source: { creator: 'A', provenance_url: bad } } }), { channel: 'A', url: '' }, `${bad}: no link, channel text kept`);
}
for (const good of ['https://youtube.com/watch?v=1', 'https://m.youtube.com/watch?v=1', 'https://youtu.be/1']) {
  assert.equal(mediaCredit({ catalog: { source: { creator: 'A', provenance_url: good } } }).url, good);
}
assert.equal(mediaCredit({ catalog: { source: { provenance_url: 'https://evil.example/x' } } }), null, 'nothing to show: no credit');
assert.equal(mediaCredit({ catalog: { source: { creator: 'A' } } }).url, '', 'no address: channel text only');
assert.equal(mediaCredit(null), null);

assert.deepEqual(normalizeMedia(curated).credit, { channel: 'Everyday English', url: yt });
assert.deepEqual(mapLesson(curated).credit, { channel: 'Everyday English', url: yt });

for (const file of ['listening', 'content']) {
  const source = readFileSync(new URL(`../static/orena/screens/${file}/screen.js`, import.meta.url), 'utf8');
  const link = source.match(/<a [^>]*href="\$\{(?:lesson|detail)\.credit\.url\}"[^>]*>/);
  assert.ok(link, `${file} draws the credit link`);
  assert.match(link[0], /target="_blank"/);
  assert.match(link[0], /rel="noopener noreferrer"/);
  const copy = readFileSync(new URL(`../static/orena/screens/${file}/copy.js`, import.meta.url), 'utf8');
  for (const label of ['Watch the original', 'Xem video gốc', '观看原视频']) assert.ok(copy.includes(label), `${file} copy has ${label}`);
}
console.log('media credit ok');
