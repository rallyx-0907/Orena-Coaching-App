/* Gate for the Reader's sentence cut (D-201): a full stop inside a number or an abbreviation does not end a
   sentence, "I." / "B." / a domain at a sentence end does, and a note or highlight saved under the OLD cut
   still shows on the sentence that now holds its text (read-side only; nothing stored is rewritten). */
import assert from 'node:assert/strict';

const { sentencesOf, segmentId } = await import('../static/orena/screens/reader/model.js');
const { sentenceSpans, legacySentenceSpans } = await import('../static/orena/product/reader-text.js');
const { legacyAliases } = await import('../static/orena/screens/reader/legacy-sentences.js');
const { noteKeyFor, noteKeysFor, loadNotesAcross, noteKeyHolding, addNote, deleteNote } = await import('../static/orena/screens/quick-sheet/model.js');
const { isHighlighted, toggleHighlight, loadHighlights } = await import('../static/orena/screens/reader/highlights.js');

const memoryStorage = () => {
  const map = new Map();
  return { getItem: (k) => (map.has(k) ? map.get(k) : null), setItem: (k, v) => void map.set(k, String(v)), removeItem: (k) => void map.delete(k) };
};

// 1. Splitting.
const cases = [
  ['The award is USD 4.77 billion, later USD 50.47 million. Next.', ['The award is USD 4.77 billion, later USD 50.47 million.', 'Next.']],
  ['Mr. Smith met Dr. Lee at 5 p.m. They left.', ['Mr. Smith met Dr. Lee at 5 p.m.', 'They left.']],
  ['The U.S. Army, e.g. the Navy, left. See No. 5.', ['The U.S. Army, e.g. the Navy, left.', 'See No. 5.']],
  ['Wait... what? Yes.', ['Wait... what?', 'Yes.']],
  ['So do I. He left.', ['So do I.', 'He left.']],
  ['Plan B. Next. Take vitamin C. It helps.', ['Plan B.', 'Next.', 'Take vitamin C.', 'It helps.']],
  ['J. Smith and John F. Kennedy spoke.', ['J. Smith and John F. Kennedy spoke.']],
  ['Visit nasa.gov. Next sentence. Open report.pdf. Then go.', ['Visit nasa.gov.', 'Next sentence.', 'Open report.pdf.', 'Then go.']],
  ['We left the U.S. The end. Back in the U.S. Army camp.', ['We left the U.S.', 'The end.', 'Back in the U.S. Army camp.']],
  ['Version 2.0. Next. In 2020. He left.', ['Version 2.0.', 'Next.', 'In 2020.', 'He left.']],
  ['预算为4.77亿美元，约５０．４７万元。完了！', ['预算为4.77亿美元，约５０．４７万元。', '完了！']],
  ['他走了。她留下！', ['他走了。', '她留下！']],
];
for (const [text, want] of cases) assert.deepEqual(sentencesOf(text), want, text);
assert.equal(sentencesOf('USD 4.77 billion').join(''), 'USD 4.77 billion', 'no space inserted');
assert.equal(legacySentenceSpans('USD 4.77 billion').length, 2, 'the legacy cut stays what it was');

// 2. Legacy aliases: each old sentence maps onto the new sentence that contains it.
const para = 'Intro sentence. The deal is USD 4.77 billion today. Last one.';
assert.deepEqual(sentencesOf(para), ['Intro sentence.', 'The deal is USD 4.77 billion today.', 'Last one.']);
const aliases = legacyAliases(para, 0);
assert.deepEqual(aliases[0], [], 'a sentence cut the same way has nothing extra');
assert.deepEqual(aliases[1], [{ segment: 'p0s1', sentence: 'The deal is USD 4.' }, { segment: 'p0s2', sentence: '77 billion today.' }].filter((a) => a.segment !== 'p0s1' || a.sentence !== 'The deal is USD 4.77 billion today.'));
assert.deepEqual(aliases[2], [{ segment: 'p0s3', sentence: 'Last one.' }], 'a later sentence had a higher index');
for (const text of ['Mr. Smith left. Done.', 'It left the U.S. Army. Done.']) {
  const now = sentencesOf(text);
  const al = legacyAliases(text, 2);
  assert.equal(al.length, now.length);
  assert.ok(al.some((a) => a.length), `${text}: something to look up`);
}
assert.deepEqual(legacyAliases('Nothing odd here. Really.', 0), [[], []]);

// 3. Notes saved under the old cut still show; new writes use the new key; no duplicates.
const storage = memoryStorage();
const source = { kind: 'reading', content_id: 'art-1' };
const oldKeyA = noteKeyFor('77 billion today.', { ...source, segment: 'p0s2' });
const oldKeyB = noteKeyFor('Last one.', { ...source, segment: 'p0s3' });
const a = addNote(storage, 'me', oldKeyA, { type: 'factual', text: 'old note on the deal', content: 'art-1' });
const b = addNote(storage, 'me', oldKeyB, { type: 'question', text: 'old note on the last one', content: 'art-1' });
const sentences = sentencesOf(para);
const keysFor = (si) => noteKeysFor(sentences[si], { ...source, segment: segmentId(0, si), legacy: aliases[si] });
assert.equal(keysFor(1)[0], noteKeyFor(sentences[1], { ...source, segment: 'p0s1' }), 'the first key is the new one');
assert.deepEqual(loadNotesAcross(storage, 'me', keysFor(1)).map((n) => n.id), [a.id]);
assert.deepEqual(loadNotesAcross(storage, 'me', keysFor(2)).map((n) => n.id), [b.id]);
assert.deepEqual(loadNotesAcross(storage, 'me', keysFor(0)), [], 'the intro has no note');
const fresh = addNote(storage, 'me', keysFor(1)[0], { type: 'reflection', text: 'new note', content: 'art-1' });
assert.deepEqual(loadNotesAcross(storage, 'me', keysFor(1)).map((n) => n.id), [fresh.id, a.id]);
assert.equal(loadNotesAcross(storage, 'me', [keysFor(1)[0], keysFor(1)[0]]).length, 1, 'a key listed twice shows each note once');
assert.equal(noteKeyHolding(storage, 'me', keysFor(1), a.id), oldKeyA, 'edit/delete lands on the stored key');
deleteNote(storage, 'me', noteKeyHolding(storage, 'me', keysFor(1), a.id), a.id);
assert.deepEqual(loadNotesAcross(storage, 'me', keysFor(1)).map((n) => n.id), [fresh.id]);
// A sentence whose cut did not change keeps its key exactly.
assert.equal(keysFor(0).length, 1);

// 4. Highlights saved under the old cut.
const hs = memoryStorage();
toggleHighlight(hs, 'me', 'art-1', { segment: 'p0s3', sentence: 'Last one.' }); // saved before D-201
toggleHighlight(hs, 'me', 'art-1', { segment: 'p0s2', sentence: '77 billion today.' });
let list = loadHighlights(hs, 'me', 'art-1');
assert.equal(isHighlighted(list, 'p0s2', 'Last one.', aliases[2]), true, 'old highlight shows on the new sentence');
assert.equal(isHighlighted(list, 'p0s2', 'Last one.'), false, 'without the alias it would not (the bug being compensated)');
assert.equal(isHighlighted(list, 'p0s1', sentences[1], aliases[1]), true);
assert.equal(isHighlighted(list, 'p0s0', sentences[0], aliases[0]), false);
const off = toggleHighlight(hs, 'me', 'art-1', { segment: 'p0s2', sentence: 'Last one.', legacy: aliases[2] });
assert.equal(off.on, false, 'toggling a legacy highlight takes it off');
assert.equal(isHighlighted(off.list, 'p0s2', 'Last one.', aliases[2]), false);
const on = toggleHighlight(hs, 'me', 'art-1', { segment: 'p0s0', sentence: sentences[0], legacy: aliases[0] });
assert.equal(on.on, true);
assert.ok(on.list.some((h) => h.segment === 'p0s0'), 'new highlights use the new key');
console.log('reader sentences: ok');
