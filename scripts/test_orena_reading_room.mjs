/* The reader: reading first, learning tools on demand.

   Pure rendering, settings and request-shaping contracts for
   static/orena/ui/reading-room.js, plus source-level guarantees about the DOM
   controller (static/orena/ui/reader.js) and the encounter that mounts it. The
   browser behaviour itself is checked in the browser; what can be checked
   without one is checked here - structure, escaping, what is (and is not)
   rendered by default, which learner action reaches which service, and EN/ZH. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import {
  EXPLAIN_LIMITS,
  LOOKUP_LIMITS,
  READER_DEFAULTS,
  blocksFrom,
  chapterLabel,
  chapterNeighbours,
  keepPayload,
  paragraphHtml,
  readerArticleHtml,
  readerSettings,
  readerPresentation,
  selectionKind,
  sentenceAround,
  settingsHtml,
  tocHtml,
} from '../static/orena/ui/reading-room.js';
import { quickSheetHtml, wordView } from '../static/orena/ui/quick-sheet.js';

const c = copy.en;

/* --- Content: typed blocks, never flattened strings --------------------- */
{
  // Structured chapters keep their blocks; unknown or empty blocks drop.
  const blocks = blocksFrom({
    blocks: [
      { type: 'break' },
      { type: 'heading', level: 2, text: 'CHAPTER I.\nDown the Rabbit-Hole' },
      { type: 'paragraph', text: '  Alice was beginning to get very tired.  ' },
      { type: 'paragraph', text: '   ' },
      { type: 'script', text: 'nope' },
      { type: 'break' },
      { type: 'break' },
      { type: 'heading', level: 9, text: 'Deep' },
      { type: 'break' },
    ],
  });
  assert.deepEqual(blocks, [
    { type: 'heading', level: 2, text: 'CHAPTER I.\nDown the Rabbit-Hole' },
    { type: 'paragraph', text: 'Alice was beginning to get very tired.' },
    { type: 'break' },
    { type: 'heading', level: 6, text: 'Deep' },
  ]);
  // A source with only paragraphs reads as paragraphs.
  assert.deepEqual(blocksFrom({ paragraphs: ['One.', ' ', 'Two.'] }), [
    { type: 'paragraph', text: 'One.' },
    { type: 'paragraph', text: 'Two.' },
  ]);
}

/* --- The page is continuous text: no per-line tools, no numbering -------- */
{
  const html = readerArticleHtml(c, {
    title: 'CHAPTER I. Down the Rabbit-Hole',
    language: 'en',
    blocks: [
      { type: 'heading', level: 2, text: 'CHAPTER I.\nDown the Rabbit-Hole' },
      { type: 'paragraph', text: 'Alice <b>was</b> tired.' },
      { type: 'break' },
      { type: 'paragraph', text: 'Line one\nLine two' },
    ],
  });
  assert.match(html, /^<article class="reader-page" lang="en" data-reader-page>/);
  // The chapter's own heading is the page title - not repeated above itself.
  assert.equal((html.match(/<h1/g) || []).length, 1);
  assert.match(html, /<h1 class="reader-title" data-block="0">CHAPTER I\.<br>Down the Rabbit-Hole<\/h1>/);
  assert.match(html, /<p data-block="1">Alice &lt;b&gt;was&lt;\/b&gt; tired\.<\/p>/);
  assert.match(html, /<hr class="reader-break">/);
  assert.match(html, /<p data-block="3">Line one<br>Line two<\/p>/);
  for (const forbidden of [/data-translate/, /data-explain/, /reading-block__number/, /Translate/, /Explain/])
    assert.doesNotMatch(html, forbidden, 'reading content carries no learning actions by default');

  // A heading that is not the title keeps its place in the outline.
  const titled = readerArticleHtml(c, {
    title: 'A table for two strangers',
    language: 'en',
    blocks: [
      { type: 'paragraph', text: 'The café was full.' },
      { type: 'heading', level: 1, text: 'Later' },
    ],
  });
  assert.match(titled, /<h1 class="reader-title">A table for two strangers<\/h1><p data-block="0">/);
  assert.match(titled, /<h2 class="reader-heading" data-block="1">Later<\/h2>/);

  // Evidence a question points at is marked in place.
  const marked = readerArticleHtml(c, {
    title: 'T',
    language: 'en',
    blocks: [{ type: 'paragraph', text: 'A b c' }],
    marks: new Map([[0, { start: 2, end: 3 }]]),
  });
  assert.match(marked, /<p data-block="0">A <mark>b<\/mark> c<\/p>/);
  assert.equal(paragraphHtml('x\ny', { start: 0, end: 1 }), '<mark>x</mark><br>y');
}

/* --- Chapter identity and navigation ------------------------------------- */
{
  const chapters = [
    { id: 'a', title: 'CHAPTER I. Down the Rabbit-Hole', position: 0 },
    { id: 'b', title: 'CHAPTER II. The Pool of Tears', position: 1 },
    { id: 'c', title: 'CHAPTER III. A Caucus-Race', position: 2 },
  ];
  assert.deepEqual(chapterNeighbours(chapters, 'b'), {
    index: 1,
    total: 3,
    previous: chapters[0],
    next: chapters[2],
  });
  assert.equal(chapterNeighbours(chapters, 'a').previous, null);
  assert.equal(chapterNeighbours(chapters, 'c').next, null);
  assert.equal(chapterNeighbours(chapters, 'missing'), null);
  /* The frame writes the chapter alone beside the time left. */
  assert.equal(chapterLabel(c, 1), 'chapter 2');
  assert.equal(chapterLabel(copy.zh, 1), '第 2 章');

  const toc = tocHtml(c, { bookId: 'book-1', chapters, currentId: 'b' });
  assert.equal((toc.match(/<a /g) || []).length, 3);
  assert.match(toc, /aria-current="true"[^>]*>[\s\S]*CHAPTER II\. The Pool of Tears/);
  assert.match(toc, /href="#\/encounter\?id=book%3Abook-1%2Fc&amp;intent=reading"/);
  // Provenance lives beside the book, never in the text.
  const about = tocHtml(c, {
    bookId: 'book-1',
    chapters,
    currentId: 'a',
    provenance: { source_url: 'https://onemorelibrary.com', publisher: 'Macmillan <1865>' },
  });
  assert.match(about, /https:\/\/onemorelibrary\.com/);
  assert.match(about, /Macmillan &lt;1865&gt;/);
  assert.doesNotMatch(
    tocHtml(c, { bookId: 'b', chapters, currentId: 'a', provenance: { source_url: 'javascript:alert(1)' } }),
    /javascript:/,
  );
}

/* --- Reader settings: real and bounded ------------------------------------ */
{
  assert.deepEqual(readerSettings(null), READER_DEFAULTS);
  // D-066: appearance is not a reader setting. There is one Dark Glass system,
  // so a stored 'appearance' from an older build is simply dropped.
  assert.deepEqual(
    readerSettings({ size: 99, font: 'comic', spacing: 'relaxed', width: 'wide', appearance: 'sepia' }),
    { ...READER_DEFAULTS, size: 1.4, spacing: 'relaxed', width: 'wide' },
  );
  assert.ok(!('appearance' in READER_DEFAULTS), 'the reader has no appearance of its own');
  assert.equal(readerSettings({ size: 0.1 }).size, 0.85);
  assert.equal(readerPresentation(READER_DEFAULTS).theme, undefined, 'the reader wears no theme of its own');
  const style = readerPresentation({ ...READER_DEFAULTS, size: 1.2, spacing: 'compact', width: 'narrow', font: 'sans' });
  assert.match(style.style, /--reader-scale: 1\.2/);
  assert.match(style.style, /--reader-leading: 1\.55/);
  assert.match(style.style, /--reader-measure: 36rem/);
  assert.match(readerPresentation(READER_DEFAULTS).style, /--reader-measure: 44rem/, 'the default column is about 700px');
  assert.equal(style.font, 'sans');

  const panel = settingsHtml(c, { ...READER_DEFAULTS });
  for (const hook of ['data-reader-size="-1"', 'data-reader-size="1"', 'data-reader-font="serif"', 'data-reader-spacing="relaxed"', 'data-reader-width="wide"'])
    assert.ok(panel.includes(hook), `settings control missing: ${hook}`);
  assert.doesNotMatch(panel, /data-reader-appearance|reader-swatch/, 'no light, sepia or paper choice remains');
  assert.match(panel, new RegExp(c.readerTextSize));
}

/* --- Selection decides what is offered ------------------------------------ */
{
  assert.equal(selectionKind('', 'en'), null);
  assert.equal(selectionKind('cloak', 'en'), 'word');
  assert.equal(selectionKind('rabbit-hole', 'en'), 'word');
  assert.equal(selectionKind('genial rays', 'en'), 'phrase');
  assert.equal(selectionKind('She took off one garment after another, and at last undressed.', 'en'), 'passage');
  assert.equal(selectionKind('学校', 'zh'), 'word');
  assert.equal(selectionKind('最后一班回家的车', 'zh'), 'phrase');
  assert.equal(selectionKind('林安赶到站台时，车站里的咖啡店已经关门了。', 'zh'), 'passage');
  assert.equal(selectionKind('x'.repeat(EXPLAIN_LIMITS.selection + 1), 'en'), null, 'too much to act on');
}

/* --- The Quick Sheet: layer one, ask more, deeper, and the sentence (D-066) - */
{
  const base = { kind: 'word', view: 'sheet', language: 'en', support: 'vi', selection: 'slukket',
    context: 'Ett etter ett forsvant vinduene, slukket som om noen hadde gjort det.', lookup: null, detail: null,
    detailState: 'loading', sentence: null, sentenceState: 'loading', thread: [], kept: false };
  const detail = {
    headword: 'slukket', script: 'latin', pinyin: null, ipa: '/ˈslʊkət/', partOfSpeech: 'verb',
    contextMeaning: 'tắt đi <như thể có người dập>', contextSentence: base.context, audioUrl: '', saved: false,
    usageVerdict: 'register-mismatch', meaningSource: 'context', followUps: ['Vì sao không dùng «slokket»?'],
    deeper: {
      coreIdea: 'Làm cho lửa ngừng cháy.', mentalModel: 'Bàn tay úp lên ngọn nến.', whyHere: 'Phân từ đứng như trạng ngữ.',
      contrast: [{ term: 'skru av', note: 'tắt thiết bị' }], examples: ['Hun slukket lyset.'], commonMistake: 'Đọc thành động từ chính.',
      grammarNote: 'Động từ yếu nhóm 1.\nPhân từ dùng như tính từ.', relatedExpressions: [{ term: 'tenne', note: 'bật' }],
      sources: [], learnerSentences: [],
    },
  };

  // Layer one answers before the explanation does: the dictionary's facts, a skeleton where the meaning will be.
  const loading = quickSheetHtml(c, { ...base, lookup: { pronunciation: '/ˈslʊkət/', part_of_speech: 'verb' } });
  assert.match(loading, /qs-skeleton/);
  assert.match(loading, /lang="en">slukket</);
  assert.match(loading, /\/ˈslʊkət\//);
  assert.match(loading, new RegExp(c.pos_verb));
  assert.match(loading, /data-qs="why"/);

  const ready = quickSheetHtml(c, { ...base, detail, detailState: 'ready' });
  assert.match(ready, new RegExp(c.quickMeaningLabel));
  assert.match(ready, /tắt đi &lt;như thể có người dập&gt;/, 'the meaning is escaped');
  assert.match(ready, /<mark class="qs-mark">slukket<\/mark>/, 'the word is marked in its sentence');
  assert.doesNotMatch(ready, /qs-source/, 'a contextual meaning is not labelled as the dictionary');

  const dictionary = quickSheetHtml(c, { ...base, detail: { ...detail, meaningSource: 'dictionary', usageVerdict: null }, detailState: 'ready' });
  assert.match(dictionary, new RegExp(c.quickFromDictionary), 'a dictionary sense says it is one');

  const none = quickSheetHtml(c, { ...base, detail: { ...detail, contextMeaning: '', meaningSource: 'none' }, detailState: 'unavailable' });
  assert.match(none, new RegExp(c.quickNothing));

  const zh = quickSheetHtml(c, { ...base, language: 'zh', selection: '把', context: '她走过去，把窗户打开了。',
    detail: { ...detail, headword: '把', script: 'hanzi', pinyin: 'bǎ', ipa: null, partOfSpeech: 'adposition' }, detailState: 'ready' });
  assert.match(zh, /qs-word--hanzi/);
  assert.match(zh, /data-reading="pinyin"[^>]*>bǎ</);
  assert.ok(zh.includes(`${c.quickGrammarOf} 把`), 'a grammar word names its grammar point');

  const ask = quickSheetHtml(c, { ...base, view: 'ask', detail, detailState: 'ready', thread: [{ id: 1, question: 'Why?', state: 'ready', answer: 'Because.' }] });
  assert.match(ask, new RegExp(c.quickVerdict_registerMismatch), 'the usage verdict is drawn');
  assert.match(ask, /Vì sao không dùng «slokket»\?/, 'the question written for this word comes first');
  assert.equal((ask.match(/qs-chip--ask/g) || []).length, 8, 'one written for the word and the seven the baseline offers');
  assert.match(ask, /data-qs-form/);
  assert.match(ask, /Because\./);

  const deeper = quickSheetHtml(c, { ...base, view: 'deeper', detail, detailState: 'ready' });
  for (const key of ['quickCore', 'quickMental', 'quickContrast', 'quickExamples', 'quickWhyHere', 'quickMistake', 'quickGrammarNote', 'quickRelated'])
    assert.ok(deeper.includes(c[key]), `deeper draws ${key}`);
  assert.match(deeper, /qs-note__head[^>]*>Động từ yếu nhóm 1\.<\/span><span class="qs-note__body">Phân từ/, 'the note is a headline and what follows it, as the frame draws it');
  assert.match(deeper, /aria-disabled="true"/, 'saving an explanation keeps its place and says it is not available yet');

  // Nothing the backend did not send is invented.
  const bare = quickSheetHtml(c, { ...base, view: 'deeper', detail: { ...detail, deeper: { coreIdea: 'Only this.' } }, detailState: 'ready' });
  assert.match(bare, /Only this\./);
  assert.doesNotMatch(bare, new RegExp(c.quickMental), 'an empty section is not drawn');
  assert.equal(wordView(c, { ...base, kept: true }).saved, true, 'a word kept on this device reads as kept');

  const sentence = {
    sentence: 'Ett etter ett forsvant vinduene i blokka overfor.', translation: 'Từng ô cửa sổ tối dần.', shortExplanation: 'Trạng ngữ đứng đầu.',
    structure: [{ chunk: 'Ett etter ett', role: 'adverbial' }, { chunk: 'forsvant', role: 'verb' }, { chunk: 'vinduene', role: 'subject' }],
    vocabulary: [{ term: 'forsvinne', meaning: 'biến mất', saved: false }, { term: 'blokk', meaning: 'khu chung cư', saved: true }],
  };
  const whole = quickSheetHtml(c, { ...base, kind: 'sentence', selection: sentence.sentence, sentence, sentenceState: 'ready' });
  assert.match(whole, new RegExp(c.quickWholeSentence));
  assert.match(whole, /Từng ô cửa sổ tối dần\./);
  assert.equal((whole.match(/data-qs="parts"/g) || []).length, 4, 'three chips and the primary action open the parts');
  const parts = quickSheetHtml(c, { ...base, kind: 'sentence', view: 'parts', selection: sentence.sentence, sentence, sentenceState: 'ready' });
  assert.match(parts, /qs-part--adverbial/);
  assert.match(parts, /qs-part--verb/);
  assert.match(parts, /qs-part--subject/);
  assert.match(parts, /<span class="qs-gap">i blokka overfor\.<\/span>/, 'words between the parts stay as plain text');
  assert.ok(parts.includes(c.quickSaveAll.replace('{n}', '1')), 'only the words not yet kept are counted');
  assert.match(parts, /data-qs="save-term"[^>]*data-term="forsvinne"/);
  const pending = quickSheetHtml(c, { ...base, kind: 'sentence', selection: sentence.sentence });
  assert.match(pending, /qs-skeleton/);
}

/* --- Context sent with a selection stays inside what each endpoint accepts - */
{
  const text = 'The wind blew. The traveler held his cloak tighter! Then the sun shone.';
  const start = text.indexOf('cloak');
  assert.equal(sentenceAround(text, start, start + 5), 'The traveler held his cloak tighter!');
  const zh = '北风吹得很猛。旅人把斗篷裹得更紧了！后来太阳出来了。';
  assert.equal(sentenceAround(zh, zh.indexOf('斗篷'), zh.indexOf('斗篷') + 2), '旅人把斗篷裹得更紧了！');
  const huge = `${'word '.repeat(400)}target ${'word '.repeat(400)}`;
  const at = huge.indexOf('target');
  const bounded = sentenceAround(huge, at, at + 6, LOOKUP_LIMITS.context);
  assert.ok(bounded.length <= LOOKUP_LIMITS.context && bounded.includes('target'));
}

/* --- Keeping a word keeps its meaning and where it was met ---------------- */
assert.deepEqual(
  keepPayload({
    selection: 'cloaks',
    result: { pronunciation: '/kləʊk/', part_of_speech: 'noun', meanings: [{ text: 'áo choàng', source: 'collection' }] },
    context: 'He held his cloaks.',
    title: 'CHAPTER I',
  }),
  {
    word: 'cloaks',
    phonetic: '/kləʊk/',
    part_of_speech: 'noun',
    definition: 'áo choàng',
    source_kind: 'reading',
    source_fragment: 'He held his cloaks.',
    focus_note: 'CHAPTER I',
  },
);

/* --- EN and ZH carry every word the reader says --------------------------- */
const keys = [
  'readerBackToReading', 'readerContents', 'readerSettings', 'readerChapter', 'readerProgress',
  'readerPrevious', 'readerNext', 'readerEnd', 'readerAbout', 'readerSource', 'readerPublisher',
  'readerTextSize', 'readerSmaller', 'readerLarger', 'readerTypeface', 'readerSerif', 'readerSans',
  'readerSpacing', 'readerSpacingCompact', 'readerSpacingNormal', 'readerSpacingRelaxed',
  'readerWidth', 'readerWidthNarrow', 'readerWidthMedium', 'readerWidthWide',
  'selectionPronounce', 'selectionSaved', 'lookupFailed',
];
const partsOfSpeech = ['noun', 'verb', 'adjective', 'adverb', 'pronoun', 'determiner', 'preposition', 'conjunction', 'numeral', 'particle', 'auxiliary', 'interjection', 'classifier', 'proper_noun'];
for (const ui of ['en', 'zh']) {
  for (const key of [...keys, ...partsOfSpeech.map((pos) => `pos_${pos}`)])
    assert.ok(copy[ui][key], `${ui}: missing ${key}`);
}
assert.notEqual(copy.en.quickWhy, copy.zh.quickWhy);

/* --- Which learner action reaches which service ---------------------------- */
const reader = readFileSync('static/orena/ui/reader.js', 'utf8');
const encounterFile = readFileSync('static/orena/ui/encounter.js', 'utf8');
// Listening shares encounter.js and legitimately tags words; only the text
// encounter is the reader's business here.
const encounter = encounterFile.slice(
  encounterFile.indexOf('function textEncounter('),
  encounterFile.indexOf('function waitingMedia('),
);
assert.ok(encounter.length > 0, 'the text encounter exists');
/* One lexical layer for the whole product.

   Reading and Listening must answer a tapped word the same way, and the only
   way to be sure they keep doing so is for there to be one implementation.
   `ui/lexical.js` is it; the rooms supply nothing but where their text is. */
const lexical = readFileSync('static/orena/ui/lexical.js', 'utf8');
const quickSheetSource = readFileSync('static/orena/ui/quick-sheet.js', 'utf8');
assert.match(quickSheetSource, /api\s*\.readingLookup\(/, 'the first answer is the deterministic lookup');
assert.match(quickSheetSource, /api\.wordDetail\(/);
assert.match(quickSheetSource, /api\.sentenceSheet\(/);
assert.match(lexical, /api\.readingTranslate\(/);
assert.match(lexical, /createQuickSheet\(\{/, 'a selection opens the Quick Sheet');
assert.doesNotMatch(lexical, /openUnderstanding|selectionToolbar|lookupPanelHtml/, 'no second surface answers a selection');
assert.match(reader, /mountLexicalLayer\(\{/, 'Reading mounts the shared layer');
assert.match(encounterFile, /mountLexicalLayer\(\{/, 'Listening mounts the same layer');
for (const source of [reader, encounterFile]) {
  assert.doesNotMatch(source, /api\.readingLookup\(/, 'no room runs its own lookup');
  assert.doesNotMatch(source, /api\.readingTranslate\(/, 'no room runs its own translation');
  assert.doesNotMatch(source, /lookupPanelHtml\(/, 'no room renders its own answer panel');
  assert.doesNotMatch(source, /selectionToolbarHtml\(/, 'no room draws its own selection tools');
}
// The contextual explanation is reached from one place, the Quick Sheet, and
// only for a selection the learner made. The rooms and the layer never call it.
for (const source of [reader, lexical, encounter])
  assert.doesNotMatch(source, /api\.(wordDetail|sentenceSheet)\(/, 'a room does not ask for an explanation itself');
for (const source of [reader, lexical, encounter]) {
  assert.doesNotMatch(source, /contextualGloss|contextualDictionary/, 'no AI runs while reading');
}
/* Tapping a word asks the shared local tagger where this unit's words are. It
   is not AI and it is not background work: one call, in the tap-time
   tokeniser, and a unit is asked about once. */
assert.equal((lexical.match(/api\.annotateMediaText\(/g) || []).length, 1,
  'segmentation is requested in exactly one place');
const tokensFor = lexical.slice(lexical.indexOf('async function tokensFor('), lexical.indexOf('async function tapWord('));
assert.match(tokensFor, /api\.annotateMediaText\(/, 'and that place is the tap-time tokeniser');
assert.match(tokensFor, /if \(tokenised\.has\(key\)\) return tokenised\.get\(key\)/,
  'a unit is tokenised once, not on every tap');
assert.doesNotMatch(reader, /annotateMediaText/, 'the reader does not tokenise anything itself');
// Nothing is requested until the learner selects or taps something.
assert.match(lexical, /selectionchange/);
assert.match(lexical, /async function tapWord\(event\)/, 'a tap is a first-class way in');
assert.doesNotMatch(reader, /IntersectionObserver/, 'no background work as paragraphs scroll by');
// The encounter mounts the reader instead of rendering its own passage.
assert.match(encounterFile, /from '\.\/reader\.js'/);
assert.match(encounter, /mountReader\(/);
assert.doesNotMatch(encounter, /language-margin|data-inspect|readingBlock|readingFrame|openWordCard/);
const api = readFileSync('static/orena/infrastructure/api.js', 'utf8');
assert.match(api, /readingLookup:\(payload\)=>request\('\/api\/reading\/lookup'/);
assert.doesNotMatch(api, /contextualGloss/);

/* --- The three columns of the updated design (D-065) -------------------- */
assert.match(reader, /class="reader-contents-column"/, 'a book keeps its contents beside the text');
assert.doesNotMatch(reader, /data-reader-paper/, 'Paper is retired with the light theme (D-066)');
assert.match(reader, /name: 'listen'/, 'and the listen control keeps its place, in the bar the frame draws under the text');
assert.match(reader, /class="reader-actions"/, 'which is one bar of what can be done with this whole text');
assert.match(reader, /class="reader-rail"/, 'where the learner is, as a hairline across the top, as the frame draws it');
assert.match(reader, /const tabs = \['word', 'grammar', 'notes'\]/, 'the panel carries the three tabs the design draws');
assert.match(reader, /class="reader-foot"/, 'how far through it sits under the text');
const readerCss = readFileSync('static/orena/reader.css', 'utf8');
assert.match(readerCss, /\.reader-layout \{[\s\S]*grid-template-columns: 300px minmax\(0, 1fr\) 440px/,
  'the contents are 300px and the word panel 440px');
assert.match(readerCss, /--reader-measure: 780px/, 'the text keeps the measure the design protects');
assert.match(readerCss, /--reader-measure: 350px/, 'and its phone measure');

console.log('Reader: continuous text, selection-only tools, non-AI lookup, settings, chapters, three columns, EN/ZH PASS');
