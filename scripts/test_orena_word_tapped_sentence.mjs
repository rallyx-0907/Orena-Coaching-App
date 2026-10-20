/* Gate for issue #463: the sentence a word was tapped in (`#/word/:id?ctx=`) is shown on Word Detail.
   The design's context list (`wdClips`) is every real occurrence of the word in the learner's sources,
   read sentences as well as listening moments, and the word card's example is the first of them. The
   sentence comes from the URL, so it is untrusted: plain text only, capped, kept only when it holds the
   word, and always rendered through the escaping html`` template. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { tappedSentence, withTappedSentence, TAPPED_SENTENCE_MAX, mapClips } from '../static/orena/screens/word/model.js';
import { html } from '../static/orena/kit/html.js';

/* --- tappedSentence: clean, capped, holds the word --- */
assert.equal(tappedSentence('adopted', 'They adopted a dog.'), 'They adopted a dog.');
assert.equal(tappedSentence('adopted', '  They\n\tadopted\u0000 a  dog.  '), 'They adopted a dog.', 'control characters and runs of space collapse');
assert.equal(tappedSentence('adopted', 'Nothing here.'), '', 'a sentence without the word is not shown');
assert.equal(tappedSentence('adopted', ''), '');
assert.equal(tappedSentence('adopted', null), '');
assert.equal(tappedSentence('', 'They adopted a dog.'), '');
assert.equal(tappedSentence('Adopted', 'they ADOPTED a dog'), 'they ADOPTED a dog', 'case does not hide the word');
assert.equal(tappedSentence('领养', '他们领养了一只狗。'), '他们领养了一只狗。', 'Chinese sentences pass');
assert.equal(tappedSentence('x', '\u202ex is here'), 'x is here', 'bidi overrides are dropped');
{
  const long = `adopted ${'a'.repeat(5000)}`;
  const capped = tappedSentence('adopted', long);
  assert.equal(Array.from(capped).length, TAPPED_SENTENCE_MAX, 'capped');
  assert.ok(TAPPED_SENTENCE_MAX <= 600, 'the cap is no more than the sheet sends');
}
{
  // Characters outside the BMP are never split in half by the cap.
  const capped = tappedSentence('word', `word ${'😀'.repeat(700)}`);
  assert.ok(!/[\ud800-\udbff]$/.test(capped), 'no lone surrogate at the cut');
}

/* --- withTappedSentence: the tapped sentence counts as a context and leads the list --- */
const clips = mapClips({ clips: [{ text: 'We adopted it last year.', title: 'Podcast', at: '0:12', lessonId: 'l1', url: '/a.mp3' }] });
{
  const list = withTappedSentence(clips, 'They adopted a dog.');
  assert.equal(list.length, 2, 'the count includes the tapped sentence');
  assert.equal(list[0].text, 'They adopted a dog.');
  assert.equal(list[0].url, '', 'no invented audio');
  assert.equal(list[0].lessonId, '', 'no invented source to open');
  assert.equal(list[0].source, '', 'no invented source line');
}
assert.equal(withTappedSentence([], 'They adopted a dog.').length, 1, 'an empty clips answer is no longer "no context yet"');
assert.equal(withTappedSentence(clips, '').length, 1, 'no tapped sentence, the clips alone');
assert.equal(withTappedSentence(clips, 'we adopted  it last year.').length, 1, 'a clip that already says it is not repeated');
assert.deepEqual(withTappedSentence(null, ''), []);

/* --- escaping: the sentence is text, never markup --- */
{
  const hostile = tappedSentence('adopted', '<img src=x onerror=alert(1)> adopted "<script>"');
  assert.ok(hostile.includes('<img'), 'kept as the text it is');
  const out = String(html`<div class="s-word-clip__text">${hostile}</div>`);
  assert.doesNotMatch(out, /<img|<script/, 'escaped on render');
  assert.match(out, /&lt;img src=x onerror=alert\(1\)&gt;/);
}
{
  const screen = readFileSync(new URL('../static/orena/screens/word/screen.js', import.meta.url), 'utf8');
  assert.match(screen, /const tapped = tappedSentence\(word, ctx\.query\?\.get\?\.\('ctx'\)\)/, 'the page reads ?ctx= only through tappedSentence');
  assert.equal((screen.match(/ctx\.query\?\.get\?\.\('ctx'\)/g) || []).length, 1, 'no other raw read of ?ctx=');
  assert.match(screen, /withTappedSentence\(mapClips\(clipsPayload\), tapped\)/, 'the context list includes it');
  assert.match(screen, /state\.context \? state : \{ \.\.\.state, context: tapped \}/, 'the card shows it when no saved sentence exists');
  assert.match(screen, /<div class="s-word-clip__text">\$\{clip\.text\}<\/div>/, 'clip text through html``');
  assert.doesNotMatch(screen, /raw\(\s*(tapped|clip\.text)/, 'never raw()');
  assert.match(screen, /clip\.lessonId \? html`<button type="button" class="s-word-clip__open"/, 'Open only where there is a place to open');
  assert.match(screen, /toast\(t\('noClipAudio'\)\)/, 'a sentence without audio says so');
}
{
  const copy = readFileSync(new URL('../static/orena/screens/word/copy.js', import.meta.url), 'utf8');
  for (const line of ["noClipAudio: 'No audio for this sentence'", "noClipAudio: 'Câu này chưa có âm thanh'", "noClipAudio: '这句话暂时没有音频'"]) {
    assert.ok(copy.includes(line), `copy: ${line}`);
  }
}
console.log('test_orena_word_tapped_sentence.mjs: the tapped sentence is a context on Word Detail, as text: PASS');
