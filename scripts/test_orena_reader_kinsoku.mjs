/* Gate for CJK line breaking in the Reader (kinsoku). With pinyin on every Hanzi is an atomic column and a
   line may break between any two of them, so the render model must say where it may not: never before a closing
   mark, never after an opening one. Checked on real VOA Chinese sentences, segmented the way the Reader does. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const { kinsoku, mayBreakBetween, segmentSentence } = await import('../static/orena/screens/reader/model.js');
const css = readFileSync(new URL('../static/orena/screens/reader/reader.css', import.meta.url), 'utf8');
const screen = readFileSync(new URL('../static/orena/screens/reader/screen.js', import.meta.url), 'utf8');

// 1. The classes.
for (const ch of '，。、；：？！）」』》】〕”') assert.equal(kinsoku(ch), 'close', `${ch} closes`);
for (const ch of '（「『《【〔“') assert.equal(kinsoku(ch), 'open', `${ch} opens`);
for (const ch of '中a1 ·—') assert.equal(kinsoku(ch), '', `${JSON.stringify(ch)} is neither`);

// 2. Real sentences from the VOA 中文 fixtures.
const fixtures = ['staff_article', 'wire_derived_article', 'wire_derived_article_ap'].map((n) =>
  readFileSync(new URL(`../tests/fixtures/voa_zh/${n}.html`, import.meta.url), 'utf8'));
fixtures.push(readFileSync(new URL('../tests/fixtures/reading_quality/voa_zh_article_8208799.html', import.meta.url), 'utf8'));
const paragraphs = fixtures.flatMap((html) => [...html.matchAll(/<p[^>]*>([^<]{12,})/g)].map((m) => m[1].trim()));
assert.ok(paragraphs.length >= 10, `real paragraphs found (${paragraphs.length})`);

let closing = 0;
let opening = 0;
for (const para of paragraphs) {
  const sentences = para.split(/(?<=[。！？])/u).filter(Boolean);
  for (const sentence of sentences) {
    // Pieces as the Reader cuts them; the characters, in order, are what it stacks.
    const chars = Array.from(segmentSentence(sentence, null).map((p) => p.text).join(''));
    assert.equal(chars.join(''), sentence, 'segmentation is lossless');
    for (let i = 1; i < chars.length; i += 1) {
      if (kinsoku(chars[i]) === 'close') {
        closing += 1;
        assert.equal(mayBreakBetween(chars[i - 1], chars[i]), false, `no break before ${chars[i]} in ${sentence}`);
      }
      if (kinsoku(chars[i - 1]) === 'open') {
        opening += 1;
        assert.equal(mayBreakBetween(chars[i - 1], chars[i]), false, `no break after ${chars[i - 1]} in ${sentence}`);
      }
    }
  }
}
assert.ok(closing > 50 && opening > 5, `the fixtures exercise both (${closing} closing, ${opening} opening)`);

// 3. Punctuation is not part of the looked-up word: the joiner is outside the word span and carries no text.
assert.match(screen, /s-reader__nb/, 'the screen draws the joiner');
assert.match(css, /\.s-reader__nb::before\s*\{\s*content:\s*'\2060'/, 'the joiner is generated content, not text');
assert.match(css, /\[data-tl="zh"\][^{]*\{\s*line-break:\s*strict/, 'Chinese running text is set with strict line breaking');

// 4. English is untouched: plain words, no joiner logic reaches them.
const en = segmentSentence('Hello, world.', null).map((p) => p.text).join('');
assert.equal(en, 'Hello, world.');
console.log('reader kinsoku gate: ok');
