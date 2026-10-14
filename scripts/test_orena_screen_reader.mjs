/* Gate for the Reader screen's DOM-free logic (design route `reader`, frame 14,
   static/orena/screens/reader/model.js + highlights.js). Checks paragraph/sentence shaping, the
   design's six word roles against the tagger's real label set, the word/pinyin pieces a sentence
   is drawn from, the end-of-content decision (real quiz/chapter state only, never invented),
   reading-percent math, the place() shape product/memory.js#enter requires, the translation turns
   the backend accepts, the words-kept-from-this-text join, and the device-memory highlight store.

   Also loads the real captured payloads (scripts/fixtures/api/: reading_article_detail[.zh].json -
   `GET /api/reading/articles/{id}`; reading_library_book_chapter.json - `GET
   /api/reading/library/books/{id}/chapters/{chapterId}`; media_annotate.{en,zh}.json - `POST
   /api/media-learning/annotate`; reading_translate.json - `POST /api/reading/translate`;
   library_vocabulary.json - `GET /api/library/vocabulary`), so a field name this module assumes
   that the real backend does not actually return fails this gate, not just a silent empty Reader. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

function fixture(name) {
  return JSON.parse(readFileSync(new URL(`./fixtures/api/${name}`, import.meta.url), 'utf8'));
}

const model = await import('../static/orena/screens/reader/model.js');
const {
  paragraphsFromText,
  blocksForSource,
  pageBlocks,
  sentencesOf,
  segmentId,
  paragraphsOf,
  ROLES,
  roleOf,
  aidsCount,
  segmentSentence,
  pinyinStack,
  roleToast,
  endOfContent,
  percentFromScroll,
  scrollTopFor,
  placeFor2,
  furthest,
  excerptFrom,
  readerSizePx,
  steppedSize,
  toolbarMeta,
  pageOf,
  translationTurns,
  translationsFrom,
  savedFromSentences,
  squash,
  parseContentId,
  contentIdFor,
  chapterNeighbours,
  selectionKind,
  sentenceAround,
} = model;
const { readerSettings, READER_SIZE } = await import('../static/orena/product/reader-settings.js');
const { loadHighlights, isHighlighted, toggleHighlight, highlightKey, MAX_PER_TEXT } = await import('../static/orena/screens/reader/highlights.js');

// 1. Paragraphs split on a real blank line only; a text with none is one paragraph, not split
// mid-sentence; blank input is no paragraphs at all.
assert.deepEqual(paragraphsFromText('One.\n\nTwo.\n\n\nThree.'), ['One.', 'Two.', 'Three.']);
assert.deepEqual(paragraphsFromText('Only one line, no blank break.'), ['Only one line, no blank break.']);
assert.deepEqual(paragraphsFromText('   '), []);
assert.deepEqual(paragraphsFromText(''), []);

// 2. blocksForSource: a book chapter keeps its own structured blocks; an article/text source is
// shaped from its own body/text string, split into paragraphs first.
assert.deepEqual(
  blocksForSource('book', { blocks: [{ type: 'heading', level: 2, text: 'I' }, { type: 'paragraph', text: 'Body.' }] }),
  [{ type: 'heading', level: 2, text: 'I' }, { type: 'paragraph', text: 'Body.' }],
);
assert.deepEqual(blocksForSource('article', { body: 'A.\n\nB.' }), [
  { type: 'paragraph', text: 'A.' },
  { type: 'paragraph', text: 'B.' },
]);
assert.deepEqual(blocksForSource('text', { text: 'Imported.' }), [{ type: 'paragraph', text: 'Imported.' }]);

// 3. sentencesOf splits a paragraph into the spans the frame renders one span per; whitespace-only
// remainders are dropped; the segment id is the (paragraph, sentence) pair a note is keyed by.
assert.deepEqual(sentencesOf('She left. He stayed!'), ['She left.', 'He stayed!']);
assert.deepEqual(sentencesOf('One sentence only'), ['One sentence only']);
assert.deepEqual(sentencesOf('   '), []);
assert.deepEqual(sentencesOf('他走了。她留下！'), ['他走了。', '她留下！']);
assert.equal(segmentId(3, 1), 'p3s1');

// 4. pageBlocks: a chapter that opens by repeating its own title (heading or plain line) does not
// print it twice, and a paragraph's `pi` counts PARAGRAPHS only, so a heading never renumbers a
// saved note. A break and a heading stay what they are.
{
  const blocks = [
    { type: 'heading', level: 2, text: 'CHAPTER I.\nDown the Rabbit-Hole' },
    { type: 'paragraph', text: 'First.' },
    { type: 'break' },
    { type: 'heading', level: 3, text: 'Part two' },
    { type: 'paragraph', text: 'Second.' },
  ];
  const page = pageBlocks(blocks, 'CHAPTER I. Down the Rabbit-Hole');
  assert.deepEqual(page.map((b) => b.type), ['paragraph', 'break', 'heading', 'paragraph']);
  assert.deepEqual(paragraphsOf(page).map((b) => [b.pi, b.text]), [[0, 'First.'], [1, 'Second.']]);
  const plainFirst = pageBlocks([{ type: 'paragraph', text: 'The Fox' }, { type: 'paragraph', text: 'Body.' }], 'The Fox');
  assert.deepEqual(paragraphsOf(plainFirst).map((b) => [b.pi, b.text]), [[1, 'Body.']], 'a repeated title line is dropped and the index still counts it');
  assert.equal(pageBlocks(blocks, 'Something else').length, 5, 'a heading that is not the title stays');
}

// 5. Word roles: the design's six, and the tagger's real label set mapped onto them. Every `pos`
// the captured tagger answers (English and Chinese) is either mapped or one the frame leaves
// untinted - a label this module has never heard of fails here.
{
  assert.deepEqual([...ROLES], ['noun', 'verb', 'modifier', 'connector', 'pronoun', 'number']);
  const UNTINTED = new Set(['determiner', 'preposition', 'particle', 'interjection', 'other']);
  for (const name of ['media_annotate.en.json', 'media_annotate.zh.json']) {
    const payload = fixture(name);
    assert.ok(Array.isArray(payload.annotations) && payload.annotations.length > 0, `${name}: real tokens`);
    for (const token of payload.annotations) {
      for (const field of ['fragment', 'start', 'end', 'pos', 'pronunciation']) assert.ok(field in token, `${name}: token carries ${field}`);
      assert.ok(roleOf(token.pos) || UNTINTED.has(token.pos), `${name}: "${token.pos}" is a role or a knowingly untinted label`);
    }
  }
  assert.equal(roleOf('noun'), 'noun');
  assert.equal(roleOf('proper_noun'), 'noun');
  assert.equal(roleOf('auxiliary'), 'verb');
  assert.equal(roleOf('adverb'), 'modifier');
  assert.equal(roleOf('adjective'), 'modifier');
  assert.equal(roleOf('conjunction'), 'connector');
  assert.equal(roleOf('numeral'), 'number');
  assert.equal(roleOf('determiner'), '');
  assert.equal(roleOf(undefined), '');
  assert.equal(roleToast(' famished ', 'modifier'), 'famished · modifier');
  assert.equal(roleToast('famished', 'modifier', 'describes or qualifies'), 'famished · modifier — describes or qualifies');
}

// 6. aidsCount: the chip counts translation, the vocabulary lens and word roles (frame 14), not
// pinyin.
assert.equal(aidsCount({ translation: false, vocabLens: false, posLens: false }), 0);
assert.equal(aidsCount({ translation: true, vocabLens: false, posLens: true }), 2);
assert.equal(aidsCount({ translation: true, vocabLens: true, posLens: true }), 3);

// 7. segmentSentence against the real tagger answers: the pieces always rebuild the sentence
// exactly (nothing dropped, nothing invented), words carry their role, Chinese words carry one
// pinyin syllable per character.
{
  const en = fixture('media_annotate.en.json');
  const pieces = segmentSentence(en.text, en.annotations);
  assert.equal(pieces.map((p) => p.text).join(''), en.text);
  const noun = pieces.find((p) => p.word && p.text === 'tricks');
  assert.equal(noun.role, 'noun');
  assert.equal(pieces.find((p) => p.word && p.text === 'three').role, 'number');
  assert.equal(pieces.find((p) => p.word && p.text === 'but').role, 'connector');
  assert.ok(pieces.filter((p) => !p.word).every((p) => !/[\p{L}\p{N}]/u.test(p.text)), 'plain runs are punctuation/space only');

  const zh = fixture('media_annotate.zh.json');
  const zhPieces = segmentSentence(zh.text, zh.annotations);
  assert.equal(zhPieces.map((p) => p.text).join(''), zh.text);
  const yanhan = zhPieces.find((p) => p.word && p.text === '严寒');
  assert.deepEqual(yanhan.pinyin, [{ h: '严', p: 'yán' }, { h: '寒', p: 'hán' }]);
  assert.equal(yanhan.role, 'modifier');
  assert.equal(zhPieces.find((p) => p.word && p.text === '我').role, 'pronoun');

  // No tagger answer: an alphabet is still split into tappable words; a script written without
  // spaces stays one plain run (a guessed boundary would hand a lookup something not pointed at).
  const plain = segmentSentence("It isn't a well-known fact, 3 times.", null);
  assert.equal(plain.map((p) => p.text).join(''), "It isn't a well-known fact, 3 times.");
  assert.deepEqual(plain.filter((p) => p.word).map((p) => p.text), ['It', "isn't", 'a', 'well-known', 'fact', '3', 'times']);
  assert.deepEqual(segmentSentence('我冒了严寒。', null), [{ text: '我冒了严寒。' }]);
  assert.deepEqual(segmentSentence('', null), []);
  // A token that overlaps the previous one or runs past the text is skipped, never rendered twice.
  const bad = segmentSentence('ab cd', [{ start: 0, end: 2, pos: 'noun', pronunciation: '' }, { start: 1, end: 3, pos: 'verb', pronunciation: '' }, { start: 3, end: 99, pos: 'verb', pronunciation: '' }]);
  assert.equal(bad.map((p) => p.text).join(''), 'ab cd');
  // Words the learner kept from this sentence are marked (case-insensitively).
  const marked = segmentSentence('The Fox ran.', null, { saved: new Set(['fox']) });
  assert.equal(marked.find((p) => p.text === 'Fox').saved, true);
  assert.equal(marked.find((p) => p.text === 'ran').saved, false);
  // pinyinStack: as many syllables as characters, else the whole reading over the first character.
  assert.deepEqual(pinyinStack('故乡', 'gù xiāng'), [{ h: '故', p: 'gù' }, { h: '乡', p: 'xiāng' }]);
  assert.deepEqual(pinyinStack('故乡', 'gùxiāng'), [{ h: '故', p: 'gùxiāng' }, { h: '乡', p: '' }]);
  assert.deepEqual(pinyinStack('hello', 'x'), []);
  assert.deepEqual(pinyinStack('故乡', ''), []);
}

// 8. End-of-content: a real quiz drives "Check understanding" (and "Mark as finished" as the
// secondary); a book has its chapter's own end note and a Next chapter only when one exists; a
// flat text with no quiz is the plain case.
assert.deepEqual(endOfContent({ isBook: false, hasQuiz: true, hasNextChapter: false, chapterNumber: 0 }), {
  primaryIsCheck: true,
  secondaryHas: true,
  hasNextChapter: false,
  endNoteKey: 'endNoteArticle',
  endNoteParams: {},
});
assert.deepEqual(endOfContent({ isBook: true, hasQuiz: false, hasNextChapter: true, chapterNumber: 2 }), {
  primaryIsCheck: false,
  secondaryHas: false,
  hasNextChapter: true,
  endNoteKey: 'endNoteChapter',
  endNoteParams: { n: 2 },
});
assert.equal(endOfContent({ isBook: true, hasQuiz: false, hasNextChapter: false, chapterNumber: 3 }).hasNextChapter, false);
assert.equal(endOfContent({ isBook: false, hasQuiz: false, hasNextChapter: false, chapterNumber: 0 }).endNoteKey, 'endNoteText');

// 9. Reading percent from scroll metrics, clamped, and its inverse; content shorter than its own
// viewport (nothing left to scroll) reads as fully read, not stuck at 0.
assert.equal(percentFromScroll(0, 1000, 500), 0);
assert.equal(percentFromScroll(250, 1000, 500), 50);
assert.equal(percentFromScroll(500, 1000, 500), 100);
assert.equal(percentFromScroll(0, 400, 500), 100);
assert.equal(scrollTopFor(50, 1000, 500), 250);
assert.equal(scrollTopFor(100, 1000, 500), 500);
assert.equal(scrollTopFor(50, 400, 500), 0);
assert.equal(furthest(60, 20), 60, 'reading back up never lowers the furthest point');
assert.equal(furthest(undefined, 15), 15);

// 10. place() for product/memory.js#enter: a book's real chapter position, a flat text's honest
// "1 of 1"; `within` only once there is a real percent (a place with none is "opened, not yet
// moved through" - memory.js's own distinction) - and memory.js's readPlace accepts what is built.
{
  assert.deepEqual(placeFor2('book', { chapterIndex: 2, chapterTotal: 6, percent: 40 }), { index: 3, total: 6, within: 40 });
  assert.deepEqual(placeFor2('flat', { percent: 12 }), { index: 1, total: 1, within: 12 });
  assert.deepEqual(placeFor2('flat', {}), { index: 1, total: 1 });
  assert.deepEqual(placeFor2('book', { chapterIndex: 0, chapterTotal: 12, percent: null }), { index: 1, total: 12 });
  const { learnerMemory } = await import('../static/orena/product/memory.js');
  const store = new Map();
  const storage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) };
  const memory = learnerMemory(storage, 'owner', 'en');
  memory.enter({ id: 'book:b:c', title: 'Chapter I', context: 'Alice', excerpt: 'x', place: placeFor2('book', { chapterIndex: 0, chapterTotal: 12, percent: 33 }) });
  assert.deepEqual(memory.value.continuation[0].place, { index: 1, total: 12, within: 33 });
  memory.enter({ id: 'article:a', title: 'A', place: placeFor2('flat', {}) });
  assert.deepEqual(memory.value.continuation[0].place, { index: 1, total: 1 }, 'opened, not yet moved through');
}

// 11. The toolbar's second line, as frame 14 builds it: source · kind · level · mode · page; a book
// names its chapter and position; missing parts are absent (D-129 R-07).
assert.equal(toolbarMeta({ isBook: false, author: 'The Slow Review', kindLabel: 'Article', level: 'B2', modeLabel: 'Active Reading', pageLabel: 'p. 1 of 3' }), 'The Slow Review · Article · B2 · Active Reading · p. 1 of 3');
assert.equal(toolbarMeta({ isBook: true, chapterTitle: 'CHAPTER I', chapterIndex: 0, chapterTotal: 12, kindLabel: 'Book', pageLabel: 'p. 2 of 4' }), 'CHAPTER I · Book · 1/12 · p. 2 of 4');
assert.equal(toolbarMeta({ isBook: false }), '');
assert.deepEqual(pageOf(15, 0), { n: 1, total: 3 });
assert.deepEqual(pageOf(15, 50), { n: 2, total: 3 });
assert.deepEqual(pageOf(15, 100), { n: 3, total: 3 });
assert.deepEqual(pageOf(0, 0), { n: 1, total: 1 });

// 12. excerptFrom: a real paragraph opener nearest the learner's position, trimmed, never invented.
assert.equal(excerptFrom(['First paragraph.', 'Second paragraph.', 'Third paragraph.'], 0), 'First paragraph.');
assert.equal(excerptFrom(['First paragraph.', 'Second paragraph.', 'Third paragraph.'], 99), 'Third paragraph.');
assert.equal(excerptFrom([], 50), '');
assert.equal(excerptFrom(['x'.repeat(300)], 0), `${'x'.repeat(160)}…`);

// 13. Re-exported contracts still resolve through this module (used by screen.js without a second
// import path).
assert.equal(typeof chapterNeighbours, 'function');
assert.equal(typeof selectionKind, 'function');
assert.equal(typeof sentenceAround, 'function');
assert.deepEqual(parseContentId('book:b1:c2'), { kind: 'book', id: 'b1', chapterId: 'c2' });
assert.equal(contentIdFor('article', 'x'), 'article:x');

// 14. Real captured sources: an article carries `body`/`title`/`language`/`level`/
// `attribution.author` (never `blocks`); a book chapter carries `blocks` and `paragraphs`,
// `book_title`, `title`, `language` and `author`. screens/reader/source.js reads exactly these.
{
  const article = fixture('reading_article_detail.json');
  for (const field of ['title', 'body', 'language', 'level']) assert.equal(typeof article[field], 'string', `article.${field}`);
  assert.equal(typeof article.attribution?.author, 'string');
  const blocks = blocksForSource('article', article);
  assert.ok(blocks.length > 0 && blocks.every((b) => b.type === 'paragraph'));
  const page = pageBlocks(blocks, article.title);
  assert.ok(paragraphsOf(page).length > 0);

  const zhArticle = fixture('reading_article_detail.zh.json');
  assert.equal(zhArticle.language, 'zh');
  assert.ok(sentencesOf(paragraphsFromText(zhArticle.body)[0]).length > 0);

  const chapter = fixture('reading_library_book_chapter.json');
  for (const field of ['title', 'book_title', 'author', 'language']) assert.equal(typeof chapter[field], 'string', `chapter.${field}`);
  assert.ok(Array.isArray(chapter.blocks) && chapter.blocks.length > 0);
  const chapterBlocks = pageBlocks(blocksForSource('book', chapter), chapter.title);
  assert.ok(chapter.blocks[0].type === 'heading' && !chapterBlocks.some((b) => b.type === 'heading'), "the chapter's own title heading is not printed twice");
  assert.deepEqual(paragraphsOf(chapterBlocks).map((b) => b.text), chapter.paragraphs, 'the real blocks and the real paragraphs array agree');
  assert.ok(sentencesOf(chapter.paragraphs[2]).length > 1, 'a real paragraph splits into more than one sentence span');

  const book = fixture('reading_library_book_detail.json');
  assert.ok(Array.isArray(book.chapters) && book.chapters.every((c) => 'id' in c && 'position' in c && 'title' in c));
  assert.equal(chapterNeighbours(book.chapters, book.chapters[0].id).index, 0);
}

// 15. Reader size: the Aa control's stored multiplier (product/reader-settings.js, shared with
// Settings' S/M/L) in the pixels the frame's own control shows - 18px default, 15..24, 1px a step -
// and every step survives the shared setting's own clamping and rounding.
{
  assert.equal(readerSizePx(1), 18);
  assert.equal(readerSizePx(0.85), 15);
  assert.equal(readerSizePx(READER_SIZE.max), 24, "a stored maximum shows as the control's own 24px");
  assert.equal(readerSizePx(undefined), 18, 'a non-finite size falls back to the default, never NaN-px');
  let size = 1;
  const seen = [readerSizePx(size)];
  for (let i = 0; i < 12; i += 1) {
    size = readerSettings({ size: steppedSize(size, 1) }).size;
    seen.push(readerSizePx(size));
  }
  assert.deepEqual(seen, [18, 19, 20, 21, 22, 23, 24, 24, 24, 24, 24, 24, 24], 'A+ climbs one pixel a step and stops at 24');
  size = 1;
  const down = [];
  for (let i = 0; i < 6; i += 1) {
    size = readerSettings({ size: steppedSize(size, -1) }).size;
    down.push(readerSizePx(size));
  }
  assert.deepEqual(down, [17, 16, 15, 15, 15, 15], 'A- falls one pixel a step and stops at 15');
}

// 16. Translation turns: the backend takes at most 48 segments of at most 6000 characters and its
// own comment says a chapter "is sent in turns". Twelve paragraphs a turn, none over the text
// limit, ids are the paragraph's own index; only a `ready` answer carries meanings (the captured
// unavailable answer carries none).
{
  const paragraphs = Array.from({ length: 30 }, (_, i) => `Paragraph ${i}.`);
  const turns = translationTurns(paragraphs);
  assert.deepEqual(turns.map((t) => t.length), [12, 12, 6]);
  assert.equal(turns[1][0].segment_id, 'p12');
  assert.ok(translationTurns(['x'.repeat(9000)])[0][0].text.length <= 5900, 'a paragraph over the limit is cut to it');
  const big = translationTurns(['a'.repeat(4000), 'b'.repeat(4000)]);
  assert.equal(big.length, 2, 'two paragraphs that together exceed the limit go in separate turns');
  assert.deepEqual(translationTurns(['']), [], 'an empty paragraph is not sent (the backend requires at least one character)');
  assert.deepEqual([...translationsFrom(fixture('reading_translate.json'))], []);
  const ready = translationsFrom({ status: 'ready', translations: [{ segment_id: 'p2', translated_meaning: ' Bản dịch ' }, { segment_id: 'bogus', translated_meaning: 'x' }, { segment_id: 'p3', translated_meaning: '' }] });
  assert.deepEqual([...ready], [[2, 'Bản dịch']]);
}

// 17. Words kept from THIS text: an item the Quick Sheet saved from a sentence of this text carries
// that sentence as `source_fragment` (screens/quick-sheet/model.js#wordSavePayload). The captured
// vocabulary list has the fields the join reads; an exact match on a sentence of the document
// counts, a word merely appearing in it does not.
{
  const page = fixture('library_vocabulary.json');
  assert.ok(page.items.every((item) => 'word' in item && 'source_fragment' in item && 'source_kind' in item));
  const sentence = 'She resorted to all her tricks to get at them.';
  const items = [
    { word: 'Resorted', source_fragment: `  ${sentence}  `, source_kind: 'reading' },
    { word: 'tricks', source_fragment: sentence, source_kind: 'reading' },
    { word: 'them', source_fragment: 'Another sentence altogether.', source_kind: 'reading' },
    { word: 'resorted', source_fragment: sentence, source_kind: 'reading' },
    { word: 'ignored', source_fragment: '', source_kind: 'dictionary' },
  ];
  const found = savedFromSentences(items, [sentence, 'Unrelated.']);
  assert.equal(found.count, 2, 'distinct words (resorted counted once)');
  assert.deepEqual([...found.bySentence.get(sentence)].sort(), ['resorted', 'tricks']);
  assert.equal(savedFromSentences(page.items, ['A famished fox saw some clusters.']).count, 0, 'real vocabulary with no matching provenance');
  assert.equal(savedFromSentences(null, []).count, 0);
  assert.equal(squash(' a \n b  c '), 'a b c');
}

// 18. Highlights (device memory): one list per text per learner, keyed by segment + the sentence's
// own text, toggled, bounded.
{
  const store = new Map();
  const storage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) };
  const sentence = 'She resorted to all her tricks.';
  assert.deepEqual(loadHighlights(storage, 'me', 'article:a'), []);
  const on = toggleHighlight(storage, 'me', 'article:a', { segment: 'p0s1', sentence });
  assert.equal(on.on, true);
  assert.equal(isHighlighted(on.list, 'p0s1', ` ${sentence} `), true);
  assert.equal(isHighlighted(on.list, 'p0s2', sentence), false, 'another sentence is not highlighted');
  assert.equal(isHighlighted(loadHighlights(storage, 'me', 'article:a'), 'p0s1', sentence), true, 'kept across a reload');
  assert.deepEqual(loadHighlights(storage, 'other', 'article:a'), [], 'per learner');
  assert.deepEqual(loadHighlights(storage, 'me', 'article:b'), [], 'per text');
  assert.equal(highlightKey('p0s1', 'A  b'), highlightKey('p0s1', 'a b'));
  const off = toggleHighlight(storage, 'me', 'article:a', { segment: 'p0s1', sentence });
  assert.equal(off.on, false);
  assert.deepEqual(loadHighlights(storage, 'me', 'article:a'), []);
  assert.equal(toggleHighlight(storage, 'me', 'article:a', { segment: 'p0s1', sentence: '  ' }).on, false, 'nothing to highlight');
  for (let i = 0; i < MAX_PER_TEXT + 20; i += 1) toggleHighlight(storage, 'me', 'article:big', { segment: `p${i}s0`, sentence: `Sentence ${i}.` });
  assert.equal(loadHighlights(storage, 'me', 'article:big').length, MAX_PER_TEXT, 'bounded per text');
  const broken = { getItem: () => '{not json', setItem: () => { throw new Error('quota'); } };
  assert.deepEqual(loadHighlights(broken, 'me', 'x'), [], 'unreadable storage is an empty list, not a crash');
  assert.equal(toggleHighlight(broken, 'me', 'x', { segment: 'p0s0', sentence: 'A.' }).on, true, 'a full device keeps it for this visit');
}

console.log('Orena Reader model: shaping, word roles and pieces (real tagger payloads), end-of-content, position, size, translation turns, words kept from here, highlights: PASS');
