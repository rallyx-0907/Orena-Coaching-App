/* Gate for CJK line breaking in the Reader (kinsoku). With pinyin on every Hanzi is an atomic column and a
   line may break between any two of them, so the render model must say where it may not: never before a closing
   mark, never after an opening one. Checked on real VOA Chinese sentences, segmented the way the Reader does. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const { kinsoku, mayBreakBetween, kinGroups, segmentSentence } = await import('../static/orena/screens/reader/model.js');
const css = readFileSync(new URL('../static/orena/screens/reader/reader.css', import.meta.url), 'utf8');
const screen = readFileSync(new URL('../static/orena/screens/reader/screen.js', import.meta.url), 'utf8');

// 1. The classes.
for (const ch of '，。、；：？！）」』》】〕”') assert.equal(kinsoku(ch), 'close', `${ch} closes`);
for (const ch of '（「『《【〔“') assert.equal(kinsoku(ch), 'open', `${ch} opens`);
for (const ch of '中a1 ·—,.;:?!)]%(') assert.equal(kinsoku(ch), '', `${JSON.stringify(ch)} is neither`);

// 2. Real sentences from the VOA 中文 fixtures.
const fixtures = ['staff_article', 'wire_derived_article', 'wire_derived_article_ap'].map((n) =>
  readFileSync(new URL(`../tests/fixtures/voa_zh/${n}.html`, import.meta.url), 'utf8'));
fixtures.push(readFileSync(new URL('../tests/fixtures/reading_quality/voa_zh_article_8208799.html', import.meta.url), 'utf8'));
const paragraphs = fixtures.flatMap((html) => [...html.matchAll(/<p[^>]*>([^<]{12,})/g)].map((m) => m[1].trim()));
assert.ok(paragraphs.length >= 10, `real paragraphs found (${paragraphs.length})`);

let closing = 0;
let opening = 0;
let grouped = 0;
for (const para of paragraphs) {
  const sentences = para.split(/(?<=[。！？])/u).filter(Boolean);
  for (const sentence of sentences) {
    // The Reader's atoms with pinyin on: a tagged word, or one character of a plain run.
    const chars = Array.from(segmentSentence(sentence, null).map((p) => p.text).join(''));
    assert.equal(chars.join(''), sentence, 'segmentation is lossless');
    const atoms = chars.map((ch) => ({ first: ch, last: ch }));
    const groups = kinGroups(atoms);
    assert.deepEqual(groups.flat(), atoms.map((_, i) => i), 'every atom is in exactly one group, in order');
    for (let g = 1; g < groups.length; g += 1) {
      const prev = atoms[groups[g - 1].at(-1)];
      const next = atoms[groups[g][0]];
      assert.equal(mayBreakBetween(prev.last, next.first), true, `a group boundary is breakable in ${sentence}`);
      assert.notEqual(kinsoku(next.first), 'close', `no group starts with a closing mark in ${sentence}`);
      assert.notEqual(kinsoku(prev.last), 'open', `no group ends with an opening mark in ${sentence}`);
    }
    for (const group of groups) if (group.length > 1) grouped += 1;
    for (let i = 1; i < chars.length; i += 1) {
      if (kinsoku(chars[i]) === 'close') closing += 1;
      if (kinsoku(chars[i - 1]) === 'open') opening += 1;
    }
  }
}
assert.ok(closing > 50 && opening > 5 && grouped > 50, `the fixtures exercise both (${closing} closing, ${opening} opening, ${grouped} groups)`);

// A word atom: a tagged word followed by a comma, and a quote followed by a word.
assert.deepEqual(kinGroups([{ first: '国', last: '会' }, { first: '，', last: '，' }, { first: '“', last: '“' }, { first: '美', last: '国' }]), [[0, 1], [2, 3]]);
assert.deepEqual(kinGroups([{ first: '他', last: '他' }, { first: '说', last: '说' }]), [[0], [1]]);

// 3. Wiring: groups become one no-wrap unit; no joiner character is used; no control characters in the served files.
assert.match(screen, /kinGroups\(atoms\)/, 'the screen groups its atoms');
assert.match(css, /\.s-reader__kin\s*\{\s*white-space:\s*nowrap/, 'a group is one no-wrap unit');
assert.match(css, /\[data-tl="zh"\][^{]*\{\s*line-break:\s*strict/, 'Chinese running text is set with strict line breaking');
// C0/C1 controls (except tab, LF, CR) and the word joiner.
const hasControl = (text) => Array.from(text).some((ch) => { const c = ch.codePointAt(0); return (c < 32 && ![9, 10, 13].includes(c)) || (c >= 127 && c <= 159) || c === 0x2060; });
for (const [name, text] of [['reader.css', css], ['screen.js', screen]]) {
  assert.equal(hasControl(text), false, `${name} holds no control characters`);
}

// 4. English is untouched: plain words, no joiner logic reaches them.
const en = segmentSentence('Hello, world.', null).map((p) => p.text).join('');
assert.equal(en, 'Hello, world.');
console.log('reader kinsoku gate: ok');
