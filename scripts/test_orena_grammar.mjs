// Grammar reaches the same explanation surface every other capability uses,
// and teaches each pattern against the thing it is not. Depth here is the
// shared system doing more work, not a longer catalog.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import { patternsFor } from '../static/orena/content/patterns.js';
import { JUDGEMENT_KEYS, judgementLabel } from '../static/orena/ui/understanding.js';

// Source is compared as text, so a checkout with CRLF endings (Git for
// Windows' default) reads the same as the LF tree CI checks out.
const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8').replace(/\r\n/g, '\n');
const LANGUAGES = ['en', 'zh'];

// Both languages carry the same authored depth. A pattern taught with a
// contrast in one language and without it in the other is not parity.
const counts = LANGUAGES.map((language) => patternsFor(language).length);
assert.ok(counts.every((n) => n > 0), 'every language has authored patterns');
assert.equal(counts[0], counts[1], 'EN and ZH carry the same number of patterns');

for (const language of LANGUAGES) {
  for (const pattern of patternsFor(language)) {
    const where = `${language}/${pattern.id}`;
    assert.ok(pattern.line, `${where}: no pattern line`);
    assert.ok(pattern.parts?.length, `${where}: no parts`);
    for (const ui of LANGUAGES)
      assert.ok(pattern.title?.[ui], `${where}: no ${ui} title`);

    const contrast = pattern.contrast;
    assert.ok(contrast, `${where}: no contrast - a pattern is learned against what it is not`);
    assert.ok(contrast.instead, `${where}: the contrast shows nothing`);
    assert.notEqual(
      contrast.instead,
      pattern.line,
      `${where}: the contrast must differ from the pattern`,
    );
    // The one vocabulary the product uses to say what kind of problem this is.
    // Grammar naming a problem its own way would mean "wrong" meant something
    // different here than in a writing review or a reading explanation.
    assert.ok(
      JUDGEMENT_KEYS.includes(contrast.judgement),
      `${where}: "${contrast.judgement}" is not a shared judgement`,
    );
    for (const support of ['en', 'zh', 'vi']) {
      const why = contrast.why?.[support];
      assert.ok(why, `${where}: no reason in ${support}`);
      assert.ok(why.length > 40, `${where}: the ${support} reason says too little`);
    }
    // The reason has to teach, not just restate the label.
    assert.notEqual(
      contrast.why.en.trim(),
      judgementLabel(copy.en, contrast.judgement),
      `${where}: the reason only repeats the judgement`,
    );
  }
}

// Every judgement a pattern can carry is readable in both interface languages.
for (const ui of LANGUAGES)
  for (const language of LANGUAGES)
    for (const pattern of patternsFor(language))
      assert.ok(
        judgementLabel(copy[ui], pattern.contrast.judgement),
        `${ui}: no label for "${pattern.contrast.judgement}"`,
      );

for (const ui of LANGUAGES)
  assert.ok(copy[ui].notThis, `${ui}: the contrast heading is missing`);

/* Grammar was the one capability that could not ask its own question. Every
   example now reaches the shared explanation carrying the pattern as context. */
const expression = read('static/orena/ui/expression.js');
assert.ok(
  expression.includes("root.querySelectorAll('[data-explain]')"),
  'grammar examples must be able to ask for an explanation',
);
assert.ok(
  expression.includes('openUnderstanding(ctx, {\n        selection: sentence,'),
  'an example asks about itself, through the shared surface',
);
assert.ok(
  expression.includes('[...new Set([note?.line, sentence]'),
  'the pattern travels as context, and is not repeated when it is the example',
);
assert.ok(
  expression.includes('judgementLabel(c, contrast.judgement)'),
  'the contrast is labelled from the shared vocabulary, not a local string',
);
// The authored contrast is editorial content and must be labelled as such
// wherever the authored note already is.
assert.ok(
  expression.includes('c.generatedNote'),
  'authored grammar presentation stays labelled as authored',
);

/* Vocabulary practice had the same gap Grammar did. A kept word already
   carries the sentence it came from, so the collection can ask about it in
   context rather than being a list to reread. */
assert.ok(
  expression.includes('[data-word-explain]'),
  'a kept word must be able to ask about itself',
);
assert.ok(
  expression.includes('context: entry.source_fragment.slice(0, 2400)'),
  'the sentence the word came from is the context it is explained in',
);
assert.ok(
  expression.includes("x.source_fragment ? `<button"),
  'a word with no recorded sentence offers no context-free lookup',
);

/* --- A syllabus to walk into, and a catalogue to search ---

   Two hundred and thirty-four patterns in one flat list answers only "where is
   the pattern whose name I already know". The levels and families the syllabus
   already declares give the learner who does not know that a way in. The
   grouping is read from the data - nothing is ordered by difficulty,
   recommended, or marked as learned, because no such evidence exists. */
const { grammarFamilies, filterGrammar, grammarShelf } = await import(
  '../static/orena/product/grammar-shelf.js'
);

const catalogue = {
  lessons: [
    { id: 'a1-a', level: 'A1', module: 'Sentence foundations', kind: 'lesson', preview: { text: 'I study English every day.' } },
    { id: 'a1-b', level: 'A1', module: 'Sentence foundations', kind: 'lesson', preview: { text: 'She calls me after school.' } },
    { id: 'a1-c', level: 'A1', module: 'Present time', kind: 'lesson', preview: { text: 'I walk to school every day.' } },
    { id: 'b2-a', level: 'B2', module: 'Conditionals and modality', kind: 'lesson', preview: { text: 'If we leave now, we may arrive.' } },
    // A review never reaches the shelf, so it must not reach the syllabus.
    { id: 'b2-r', level: 'B2', module: 'Conditionals and modality', kind: 'review', preview: { text: 'Review.' } },
  ],
};
const shelf = grammarShelf(catalogue, [], 'en');
const syllabus = grammarFamilies(shelf);

assert.deepEqual(syllabus.map((x) => x.level), ['A1', 'B2'], 'levels come out ordered');
assert.equal(syllabus[0].total, 3);
assert.deepEqual(
  syllabus[0].families.map((f) => [f.name, f.count]),
  [['Sentence foundations', 2], ['Present time', 1]],
  'a level is grouped into the families its own data declares',
);
assert.equal(
  syllabus[0].families[0].line,
  'I study English every day.',
  'a family shows one real line from itself, never an invented sample',
);
assert.equal(syllabus[1].total, 1, 'a review is not a pattern to walk into');

// Every catalogued pattern is reachable through exactly one family, so the
// syllabus is a complete way in rather than a curated subset.
const grouped = syllabus.flatMap((l) => l.families).reduce((n, f) => n + f.count, 0);
assert.equal(grouped, shelf.length, 'the syllabus reaches every catalogued pattern');

// Entering a family narrows the catalogue to it.
assert.equal(filterGrammar(shelf, { family: 'Present time' }).length, 1);
assert.equal(filterGrammar(shelf, { family: 'Sentence foundations' }).length, 2);
assert.equal(filterGrammar(shelf, {}).length, shelf.length, 'no family means the whole catalogue');
// A family and a level filter compose rather than fighting.
assert.equal(filterGrammar(shelf, { family: 'Present time', level: 'B2' }).length, 0);

/* Both layers are present in the room, and the catalogue stays closed until
   asked for - it is the second question, not the first. */
const room = read('static/orena/ui/expression.js');
assert.ok(room.includes('class="grammar-syllabus"'), 'the syllabus layer is rendered');
assert.ok(
  /<details class="grammar-browse" data-browse>/.test(room),
  'the catalogue is a drawer, closed until the learner opens it',
);
assert.ok(
  room.includes('rerunSearch()'),
  'entering a family reports its count through the search binding, so the stated number matches the rows',
);
/* Searching stays inside the family the learner entered. Widening on the first
   keystroke meant a search could answer with patterns from a level they had not
   asked about, and clearing the box dropped them into the whole catalogue with
   no way back to where they were. */
assert.ok(
  !/if \(next\.query\.trim\(\)\) family = '';/.test(room),
  'a query must not silently clear the family scope',
);
assert.ok(
  room.includes('data-leave-family'),
  'leaving a family is an explicit action the learner can see and take',
);
for (const ui of LANGUAGES)
  assert.ok(copy[ui].grammarSearchAll, `${ui}: no way to say "search all patterns"`);
// Scope composes: a family and a query intersect rather than replacing.
assert.equal(
  filterGrammar(shelf, { family: 'Sentence foundations', query: 'study' }).length,
  1,
  'a query inside a family searches that family',
);
assert.equal(
  filterGrammar(shelf, { family: 'Sentence foundations', query: 'walk' }).length,
  0,
  'a match outside the family is not returned while the family is selected',
);
for (const ui of LANGUAGES)
  for (const key of ['grammarSyllabus', 'grammarBrowse', 'grammarPatterns', 'grammarPatternOne', 'grammarInFamily'])
    assert.ok(copy[ui][key], `${ui}: missing ${key}`);

console.log(
  'Grammar and vocabulary: shared judgements, EN/ZH contrast pedagogy, one explanation surface, and a syllabus beside the catalogue: PASS',
);
