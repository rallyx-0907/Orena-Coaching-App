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
  explainBounds,
  keepPayload,
  lookupPanelHtml,
  paragraphHtml,
  readerArticleHtml,
  readerSettings,
  readerPresentation,
  selectionActions,
  selectionKind,
  selectionToolbarHtml,
  sentenceAround,
  settingsHtml,
  tocHtml,
} from '../static/orena/ui/reading-room.js';

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
  assert.equal(chapterLabel(c, 1, 3), 'Chapter 2 of 3');
  assert.equal(chapterLabel(copy.zh, 1, 3), '第 2 章，共 3 章');

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

/* --- Reader settings: real, bounded, and theme-honest --------------------- */
{
  assert.deepEqual(readerSettings(null), READER_DEFAULTS);
  assert.deepEqual(
    readerSettings({ size: 99, font: 'comic', spacing: 'relaxed', width: 'wide', appearance: 'sepia' }),
    { ...READER_DEFAULTS, size: 1.4, spacing: 'relaxed', width: 'wide', appearance: 'sepia' },
  );
  assert.equal(readerSettings({ size: 0.1 }).size, 0.85);
  // Appearance maps onto the Orena themes, plus the reader-only sepia block
  // theme.css declares beside them, rather than inventing colours (D-059).
  assert.deepEqual(readerPresentation({ ...READER_DEFAULTS, appearance: 'light' }).theme, { theme: 'paper', appearance: 'light' });
  assert.deepEqual(readerPresentation({ ...READER_DEFAULTS, appearance: 'sepia' }).theme, { theme: 'sepia', appearance: 'light' });
  assert.deepEqual(readerPresentation({ ...READER_DEFAULTS, appearance: 'dark' }).theme, { theme: 'ink', appearance: 'dark' });
  for (const theme of ['paper', 'sepia', 'ink'])
    assert.ok(
      readFileSync('static/orena/theme.css', 'utf8').includes(`[data-theme='${theme}'] {`),
      `the reader's ${theme} appearance has a token block`,
    );
  assert.equal(readerPresentation(READER_DEFAULTS).theme, null, 'by default the reader follows the Orena theme');
  const style = readerPresentation({ ...READER_DEFAULTS, size: 1.2, spacing: 'compact', width: 'narrow', font: 'sans' });
  assert.match(style.style, /--reader-scale: 1\.2/);
  assert.match(style.style, /--reader-leading: 1\.55/);
  assert.match(style.style, /--reader-measure: 36rem/);
  assert.match(readerPresentation(READER_DEFAULTS).style, /--reader-measure: 44rem/, 'the default column is about 700px');
  assert.equal(style.font, 'sans');

  const panel = settingsHtml(c, { ...READER_DEFAULTS, appearance: 'dark' });
  for (const hook of ['data-reader-size="-1"', 'data-reader-size="1"', 'data-reader-font="serif"', 'data-reader-spacing="relaxed"', 'data-reader-width="wide"', 'data-reader-appearance="dark"'])
    assert.ok(panel.includes(hook), `settings control missing: ${hook}`);
  assert.match(panel, /data-reader-appearance="dark"[^>]*aria-pressed="true"/);
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

  /* A word is looked up, kept and spoken. A phrase or a sentence can also be
     asked how it works - the pattern question put to the one explanation
     surface, not a grammar module. A passage is too much to keep or speak. */
  assert.deepEqual(selectionActions('word', { canSpeak: true }), ['translate', 'explain', 'save', 'pronounce']);
  assert.deepEqual(selectionActions('phrase', { canSpeak: false }), ['translate', 'explain', 'pattern', 'save']);
  assert.deepEqual(selectionActions('passage', { canSpeak: true }), ['translate', 'explain', 'pattern']);
  assert.deepEqual(selectionActions(null, { canSpeak: true }), []);

  const bar = selectionToolbarHtml(c, ['translate', 'explain', 'save', 'pronounce']);
  assert.match(bar, /role="toolbar"/);
  for (const action of ['translate', 'explain', 'save', 'pronounce'])
    assert.ok(bar.includes(`data-selection-action="${action}"`));
  assert.match(bar, new RegExp(`>${c.selectionTranslate}<`));
}

/* --- Lookup/translation panel: says what it knows, and where it came from -- */
{
  const loading = lookupPanelHtml(c, { selection: 'cloak', language: 'en', support: 'vi', kind: 'word', state: 'loading' });
  assert.match(loading, /lang="en">cloak</);
  assert.match(loading, new RegExp(c.lookupLoading));

  const word = lookupPanelHtml(c, {
    selection: 'cloaks',
    language: 'en',
    support: 'vi',
    kind: 'word',
    state: 'ready',
    result: {
      base_form: 'cloak',
      part_of_speech: 'noun',
      pronunciation: '/kləʊk/',
      meanings: [
        { text: 'áo <choàng>', source: 'collection' },
        { text: 'áo khoác', source: 'machine_translation' },
      ],
      definitions: [{ part_of_speech: 'noun', definition: 'A sleeveless outer garment.' }],
    },
  });
  assert.match(word, /lang="vi">áo &lt;choàng&gt;</);
  assert.match(word, new RegExp(c.lookupSourceCollection));
  assert.match(word, new RegExp(c.lookupSourceMachine));
  assert.match(word, /\/kləʊk\//);
  assert.match(word, new RegExp(c.pos_noun));
  assert.match(word, /lang="en">A sleeveless outer garment\.</);
  assert.match(word, /data-panel-action="explain"/);
  assert.match(word, /data-panel-action="save"/);

  const phrase = lookupPanelHtml(c, {
    selection: 'She took off one garment after another.',
    language: 'en',
    support: 'vi',
    kind: 'passage',
    state: 'ready',
    result: { translation: 'Cô cởi bỏ từng món đồ.' },
  });
  assert.match(phrase, /lang="vi">Cô cởi bỏ từng món đồ\.</);
  assert.match(phrase, new RegExp(c.lookupSourceMachine));
  assert.doesNotMatch(phrase, /data-panel-action="save"/, 'a passage is not a word to keep');

  const nothing = lookupPanelHtml(c, { selection: 'zzz', language: 'en', support: 'vi', kind: 'word', state: 'unavailable', result: { meanings: [], definitions: [] } });
  assert.match(nothing, new RegExp(c.lookupUnavailable));
  assert.doesNotMatch(nothing, /lang="vi">zzz/, 'the original is never shown as its own meaning');

  const failed = lookupPanelHtml(c, { selection: 'cloak', language: 'en', support: 'vi', kind: 'word', state: 'failed' });
  assert.match(failed, /data-panel-action="retry"/);
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
  const long = 'A sentence that goes on for a while. '.repeat(120);
  const bounds = explainBounds(long);
  assert.ok(bounds.selection.length <= EXPLAIN_LIMITS.selection);
  assert.ok(bounds.context.length <= EXPLAIN_LIMITS.context && bounds.context.includes(bounds.selection));
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
  'readerBackToReading', 'readerContents', 'readerSettings', 'readerChapterOf', 'readerProgress',
  'readerPrevious', 'readerNext', 'readerEnd', 'readerAbout', 'readerSource', 'readerPublisher',
  'readerTextSize', 'readerSmaller', 'readerLarger', 'readerTypeface', 'readerSerif', 'readerSans',
  'readerSpacing', 'readerSpacingCompact', 'readerSpacingNormal', 'readerSpacingRelaxed',
  'readerWidth', 'readerWidthNarrow', 'readerWidthMedium', 'readerWidthWide',
  'readerAppearance', 'readerAppearanceAuto', 'readerAppearanceLight', 'readerAppearanceSepia', 'readerAppearanceDark',
  'selectionActions', 'selectionTranslate', 'selectionExplain', 'selectionSave', 'selectionPronounce',
  'selectionPattern', 'selectionSaved', 'askPattern',
  'lookupLoading', 'translationLoading', 'lookupUnavailable', 'lookupFailed', 'lookupSourceCollection',
  'lookupSourceDictionary', 'lookupSourceMachine', 'lookupDefinitions', 'lookupBaseForm',
];
const partsOfSpeech = ['noun', 'verb', 'adjective', 'adverb', 'pronoun', 'determiner', 'preposition', 'conjunction', 'numeral', 'particle', 'auxiliary', 'interjection', 'classifier', 'proper_noun'];
for (const ui of ['en', 'zh']) {
  for (const key of [...keys, ...partsOfSpeech.map((pos) => `pos_${pos}`)])
    assert.ok(copy[ui][key], `${ui}: missing ${key}`);
}
assert.notEqual(copy.en.selectionTranslate, copy.zh.selectionTranslate);

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
assert.match(lexical, /api\.readingLookup\(/);
assert.match(lexical, /api\.readingTranslate\(/);
assert.match(reader, /mountLexicalLayer\(\{/, 'Reading mounts the shared layer');
assert.match(encounterFile, /mountLexicalLayer\(\{/, 'Listening mounts the same layer');
for (const source of [reader, encounterFile]) {
  assert.doesNotMatch(source, /api\.readingLookup\(/, 'no room runs its own lookup');
  assert.doesNotMatch(source, /api\.readingTranslate\(/, 'no room runs its own translation');
  assert.doesNotMatch(source, /lookupPanelHtml\(/, 'no room renders its own answer panel');
  assert.doesNotMatch(source, /selectionToolbarHtml\(/, 'no room draws its own selection tools');
}
// AI is reached only through the one explanation surface, from an explicit Explain.
assert.match(lexical, /case 'explain':\s+case 'pattern': \{[\s\S]{0,700}openUnderstanding\(ctx, \{/);
assert.equal((lexical.match(/openUnderstanding\(/g) || []).length, 1, 'explain is the only way to AI');
/* "How this works" is the same explanation request carrying the pattern
   question, not a second surface and not a second route to a provider. */
assert.match(lexical, /question: action === 'pattern' \? c\.askPattern/);
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
assert.match(reader, /data-reader-paper/, 'the reading appearance has the one-tap control the design draws');
assert.match(reader, /data-reader-listen/, 'and the listen control keeps its place');
assert.match(reader, /const tabs = \['word', 'grammar', 'notes'\]/, 'the panel carries the three tabs the design draws');
assert.match(reader, /class="reader-foot"/, 'how far through it sits under the text');
const readerCss = readFileSync('static/orena/reader.css', 'utf8');
assert.match(readerCss, /\.reader-layout \{[\s\S]*grid-template-columns: 300px minmax\(0, 1fr\) 440px/,
  'the contents are 300px and the word panel 440px');
assert.match(readerCss, /--reader-measure: 780px/, 'the text keeps the measure the design protects');
assert.match(readerCss, /--reader-measure: 350px/, 'and its phone measure');

console.log('Reader: continuous text, selection-only tools, non-AI lookup, settings, chapters, three columns, EN/ZH PASS');
