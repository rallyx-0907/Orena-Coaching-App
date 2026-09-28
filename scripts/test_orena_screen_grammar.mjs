/* Gate for the Grammar surface's pure data mapping: screens/grammar/model.js (Grammar Library,
   frame 44) and screens/grammar-concept/model.js (Grammar Concept, frame 47). No DOM, no fetch:
   every function here takes already-fetched API data and returns the shape the screen paints.
   Design Contract rule 40 (never invent data) is what most of these assertions hold. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { buildLibraryGroups, droppedCount, levelName } from '../static/orena/screens/grammar/model.js';

/* A tiny stand-in for grammar/copy.js's translate function, exactly the shape levelName()/
   buildLibraryGroups() are documented to take (a plain function of one key). */
const LEVEL_LABELS = {
  levelFoundation: 'Foundation', levelCore: 'Core', levelBasic: 'Basic', levelIntermediate: 'Intermediate',
  levelLowerIntermediate: 'Lower-intermediate', levelUpperIntermediate: 'Upper-intermediate',
  levelAdvanced: 'Advanced', levelMastery: 'Mastery', levelAdvancedMastery: 'Advanced mastery',
};
const fakeLevelT = (key) => LEVEL_LABELS[key] ?? key;
import {
  pickLocale, roleBucket, primaryPattern, examplesOf, mistakeOf, quizQuestions, personalPractice, headerMeta, findBlock,
} from '../static/orena/screens/grammar-concept/model.js';

// --- Grammar Library: real fields group it, review-kind and preview-less lessons drop out ------
{
  const library = {
    levels: ['A1', 'A2'],
    level_names: { A1: 'Foundation', A2: 'Core' },
    lessons: [
      { id: 'a1-be', level: 'A1', kind: 'lesson', module: 'Sentence foundations', title: 'Be: am/is/are', preview: { text: 'I am ready.' }, completed: true },
      { id: 'a1-pronouns', level: 'A1', kind: 'lesson', module: 'Sentence foundations', title: 'Pronouns', preview: { text: 'She likes tea.' }, completed: false },
      { id: 'a1-review-1', level: 'A1', kind: 'review', module: 'Sentence foundations', title: 'Review 1', preview: { text: 'Review.' }, completed: false },
      { id: 'a2-plurals', level: 'A2', kind: 'lesson', module: 'Nouns', title: 'Plurals', preview: { text: 'Two cats.' }, completed: false },
      { id: 'a2-no-preview', level: 'A2', kind: 'lesson', module: 'Nouns', title: 'No example yet', preview: null, completed: false },
      { id: 'b1-orphan', level: 'B1', kind: 'lesson', module: 'Unlisted', title: 'Not in levels[]', preview: { text: 'x' }, completed: false },
    ],
  };
  const groups = buildLibraryGroups(library, 'en', fakeLevelT);
  assert.equal(groups.length, 2, 'one group per level that actually has items, in the levels[] order (B1 is not in levels[] and is left out)');
  assert.equal(groups[0].level, 'A1');
  // languages-4 (2) / finding B.2: the level code is mapped to real interface copy
  // (grammar/copy.js) - never the backend's own English `level_names[level]` text.
  assert.equal(groups[0].levelName, 'Foundation', 'a translated level-name label, keyed by the level code, not the raw code or the backend English text');
  assert.equal(groups[0].total, 2, 'the review-kind lesson is dropped by grammarShelf, so A1 has 2 concepts, not 3');
  assert.equal(groups[0].completed, 1);
  assert.deepEqual(groups[0].items.map((item) => item.id), ['a1-be', 'a1-pronouns']);
  assert.equal(groups[0].items[0].completed, true);
  assert.equal(groups[0].items[0].note, 'I am ready.', 'no editorial note exists, so the note falls back to the lesson\'s own preview line');
  // languages-4 (1) / finding A: the English track's own lesson titles are genuine English
  // (UI_BACKEND_GAPS.md N-33) - marked lang="en".
  assert.equal(groups[0].titleLang, 'en');

  assert.equal(groups[1].level, 'A2');
  assert.equal(groups[1].total, 1, 'the lesson with no preview at all has no line and grammarShelf drops it - never a fabricated one');

  assert.deepEqual(buildLibraryGroups({ levels: [], lessons: [] }, 'en', fakeLevelT), [], 'no levels is no groups, not a crash');
  assert.deepEqual(buildLibraryGroups({}, 'en', fakeLevelT), [], 'a missing shape is no groups, not a crash');

  assert.equal(droppedCount(library), 2, 'the review lesson and the preview-less lesson are the two the shelf does not surface');

  // languages-4 (2): every level code both providers actually return maps to a real label -
  // never a fallback to the raw code for a level this build knows about.
  for (const code of ['A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'HSK1', 'HSK2', 'HSK3', 'HSK4', 'HSK5', 'HSK6', 'HSK7-9']) {
    assert.notEqual(levelName(code, fakeLevelT), code, `${code} maps to a translated label, not its own raw code`);
  }
  assert.equal(levelName('X9', fakeLevelT), 'X9', 'an unrecognised level code (a future provider) falls back to the raw code rather than guessing a label');

  // languages-4 (1) / finding A: the Chinese/HSK track's own lesson titles are a Vietnamese-only
  // content gap (N-33), never genuinely Chinese - this build must not mark them lang="zh".
  const hskLibrary = {
    levels: ['HSK1'],
    lessons: [{ id: 'hsk1-svo', level: 'HSK1', kind: 'lesson', module: 'Sentence order', title: 'SVO cơ bản', preview: { text: 'x' }, completed: false }],
  };
  const hskGroups = buildLibraryGroups(hskLibrary, 'zh', fakeLevelT);
  assert.equal(hskGroups[0].titleLang, '', 'the HSK track\'s own titles are Vietnamese, not Chinese - left unmarked rather than mislabelled');
}

// --- Grammar Library copy: the not-yet-done tag is a STATUS in every language, never an action
//     verb in one and a status in the others (found live: en 'Open' reads as an instruction while
//     vi 'Chưa học' / zh '未学' both unambiguously mean "not learned yet", the same status the
//     paired 'done' key expresses consistently across all three) ------------------------------
{
  const store = new Map();
  globalThis.window = {
    localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) },
  };
  Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
  globalThis.document = { documentElement: { lang: 'en', dataset: {} } };
  await import('../static/orena/screens/grammar/copy.js');
  const copy = await import('../static/orena/copy/index.js');
  const table = copy.registeredCopy().get('grammar');
  assert.ok(table, 'the grammar namespace registered');
  assert.notEqual(
    table.packs.en.open.trim().toLowerCase(),
    'open',
    'the not-yet-done tag must read as a status (e.g. "Not done"), never a bare imperative ("Open") that only vi/zh disambiguate from the identical-looking action verb used elsewhere (screens/word/copy.js, ui/copy.js)',
  );
}

// --- Grammar Library row title line-height: the pinned design's 44-Grammar-Library.html frame
//     draws this row's 15px title at an explicit line-height:20px, the one exception among every
//     other 15px-title listRow consumer (which all leave line-height unset, ~19px "normal").
//     kit/components.js's listRow() carries a titleLineHeight param for exactly this case; the
//     screen must actually pass it (fidelity-001) --------------------------------------------
{
  const screenSrc = fs.readFileSync('static/orena/screens/grammar/screen.js', 'utf8');
  assert.match(
    screenSrc,
    /listRow\(\{[^}]*titleLineHeight:\s*20\b/,
    'the Grammar Library concept row must pass titleLineHeight: 20 to listRow(), matching the pinned design\'s explicit 20px line-height for this row',
  );
}

// --- Grammar Concept: locale picking (support language, English the documented fallback) ------
{
  assert.equal(pickLocale('plain target-language text', 'vi'), 'plain target-language text', 'a plain string is target-language content, never locale-picked');
  assert.equal(pickLocale({ en: 'Subject', vi: 'Chủ ngữ' }, 'vi'), 'Chủ ngữ');
  assert.equal(pickLocale({ en: 'Subject', vi: 'Chủ ngữ' }, 'zh'), 'Subject', 'zh has no pack for this field, so English, never the vi text and never the interface language');
  assert.equal(pickLocale({ vi: 'chỉ có vi' }, 'zh'), 'chỉ có vi', 'with no en pack either, whatever the field does have, not an empty string');
  assert.equal(pickLocale({ vi: 'chỉ có vi', default: 'câu mặc định' }, 'en'), 'câu mặc định', 'the schema\'s own "default" locale key (grammar_learning_model.py _locale_key) is checked before falling through to "whichever key happens to be first" - the real catalogue carries exactly this shape');
  assert.equal(pickLocale({ default: 'câu mặc định', vi: 'chỉ có vi' }, 'zh'), 'câu mặc định', 'default wins over key order regardless of which key the object lists first');
  assert.equal(pickLocale(null, 'en'), '');
  assert.equal(pickLocale(undefined, 'en'), '');
  assert.equal(pickLocale(42, 'en'), '42', 'a non-string, non-map value is stringified rather than dropped');
}

// --- roleBucket: the four chip colours, one deterministic default for the other 25+ roles ------
{
  assert.equal(roleBucket('verb'), 'a');
  assert.equal(roleBucket('AUXILIARY'), 'a', 'case-insensitive');
  assert.equal(roleBucket('complement'), 'b');
  assert.equal(roleBucket('subject'), 'k');
  assert.equal(roleBucket('time'), 'm', 'a role with no dedicated bucket is the marked/amber default');
  assert.equal(roleBucket(''), 'm');
  assert.equal(roleBucket(undefined), 'm');
}

// --- primaryPattern: chips (formula), transform, and the generic-row fallback ------------------
{
  const formulaConcept = {
    id: 'a1-be-am-is-are', title: 'Be: am/is/are', kind: 'lesson',
    learning_model: { blocks: [
      { id: 'f1', type: 'formula', stage: 'pattern', title: { en: 'The basic link' }, payload: { parts: [
        { text: 'I / you / he', role: 'subject', label: { en: 'Subject' } },
        { text: 'am / is / are', role: 'verb', label: { en: 'Matching form of be' } },
      ] } },
    ] },
  };
  const pattern = primaryPattern(formulaConcept, 'en');
  assert.equal(pattern.kind, 'chips');
  assert.equal(pattern.title, 'The basic link');
  assert.equal(pattern.parts.length, 2);
  assert.equal(pattern.parts[0].role, 'k', 'subject buckets to the neutral/participant colour');
  assert.equal(pattern.parts[1].role, 'a', 'verb buckets to the functional/accent colour');
  assert.equal(pattern.parts[0].text, 'I / you / he', 'target-language pattern text is carried through unchanged');

  const transformConcept = {
    id: 'reported-speech-basics', title: 'Reported speech', kind: 'lesson',
    learning_model: { blocks: [
      { id: 't1', type: 'transformation', stage: 'pattern', title: { en: 'Direct to reported' }, payload: { from: 'She said, "I am tired."', to: 'She said she was tired.' } },
    ] },
  };
  const transform = primaryPattern(transformConcept, 'en');
  assert.equal(transform.kind, 'transform');
  assert.equal(transform.from, 'She said, "I am tired."');
  assert.equal(transform.to, 'She said she was tired.');

  const contrastConcept = {
    id: 'x-vs-y', title: 'X vs Y', kind: 'lesson',
    learning_model: { blocks: [
      { id: 'c1', type: 'contrast', stage: 'pattern', title: { en: 'Compare' }, payload: { items: [
        { label: { en: 'A' }, text: 'Foo', note: { en: 'note foo' } },
        { label: { en: 'B' }, text: 'Bar', note: { en: 'note bar' } },
      ] } },
    ] },
  };
  const rows = primaryPattern(contrastConcept, 'en');
  assert.equal(rows.kind, 'rows', 'a block type frame 47 draws no chip shape for degrades to labelled rows, not an invented widget');
  assert.equal(rows.rows.length, 2);
  assert.equal(rows.rows[0].label, 'A');
  assert.equal(rows.rows[0].text, 'Foo');
  assert.equal(rows.rows[0].note, 'note foo');

  assert.equal(primaryPattern({ id: 'x', title: 'x', learning_model: { blocks: [] } }), null, 'no pattern block at all is null, not a fabricated one');
  assert.equal(findBlock({ learning_model: { blocks: [{ id: 'a', type: 'common_mistake' }] } }, 'common_mistake').id, 'a');
  assert.equal(findBlock({}, 'common_mistake'), null, 'a missing learning_model is a miss, not a crash');
}

// --- examplesOf: the lesson's own examples[]; its lone translation field is Vietnamese-only in
//     the real catalogue (confirmed against the live API, both target languages), so it is shown
//     only to a vi-support learner and left off for every other support language (D-079, no
//     hardcoding a language onto a learner who never chose it) ------------------------------
{
  const lesson = { examples: [
    { target: 'I am ready.', meaning_vi: 'Tôi đã sẵn sàng.' },
    { target: 'She is at school.', vi: 'Cô ấy ở trường.' },
    { target: 'No translation at all.' },
    { target: '' },
  ] };
  const examplesVi = examplesOf(lesson, 'vi');
  assert.equal(examplesVi.length, 3, 'the blank-target example is dropped');
  assert.equal(examplesVi[0].translation, 'Tôi đã sẵn sàng.', 'meaning_vi wins when present, for a vi-support learner');
  assert.equal(examplesVi[1].translation, 'Cô ấy ở trường.', 'vi is the fallback field');
  assert.equal(examplesVi[2].translation, '', 'neither field exists: an honest empty line, not a fabricated one');

  const examplesEn = examplesOf(lesson, 'en');
  assert.equal(examplesEn[0].translation, '', 'an en-support learner never sees the vi-only gloss (the bug this fixes: it used to show unconditionally)');
  const examplesZh = examplesOf(lesson, 'zh');
  assert.equal(examplesZh[0].translation, '', 'a zh-support learner never sees the vi-only gloss either');
  assert.equal(examplesOf(lesson).length, 3, 'support defaults to en (the documented fallback) - still no vi text leaks in');
  assert.equal(examplesOf(lesson)[0].translation, '');

  assert.deepEqual(examplesOf({}, 'vi'), []);
}

// --- mistakeOf / quizQuestions / personalPractice: only what the lesson actually carries -------
{
  assert.equal(mistakeOf({ learning_model: { blocks: [] } }), null, 'no common_mistake block is no mistake card, not an empty one');
  const mistake = mistakeOf({ learning_model: { blocks: [
    { id: 'm', type: 'common_mistake', payload: { incorrect: 'I is tired.', correct: 'I am tired.', why: { en: 'I always takes am.' } } },
  ] } }, 'en');
  assert.deepEqual(mistake, { incorrect: 'I is tired.', correct: 'I am tired.', why: 'I always takes am.' });

  const lesson = { learning_model: { blocks: [
    { id: 'q1', type: 'micro_practice', payload: { interaction: 'choose', prompt: { en: 'Pick one' }, options: ['am', 'is', 'are'], answer: 'are', explanation: { en: 'plural subject' } } },
    { id: 'q2', type: 'micro_practice', payload: { interaction: 'reorder', prompt: { en: 'Reorder' }, tokens: ['a', 'b'], answer: 'a b' } },
    { id: 'q3', type: 'micro_practice', payload: { interaction: 'choose', prompt: '', options: [] } },
  ] } };
  const quiz = quizQuestions(lesson, 'en');
  assert.equal(quiz.length, 1, 'a reorder interaction has no drawn quiz visual and is left out; a choose block with no real prompt/options is left out too');
  assert.equal(quiz[0].answer, 'are');
  assert.equal(quiz[0].options.length, 3);

  assert.equal(personalPractice({ learning_model: { blocks: [] } }), null);
  const practice = personalPractice({ learning_model: { blocks: [
    { id: 'p', type: 'personal_practice', payload: { prompt: { en: 'Write about yourself.' }, placeholder: { en: 'I am ...' } } },
  ] } }, 'en');
  assert.deepEqual(practice, { prompt: 'Write about yourself.', placeholder: 'I am ...' });
}

// --- headerMeta: level + whichever of module/category the lesson carries -----------------------
{
  assert.deepEqual(headerMeta({ level: 'B2', module: 'Conditionals' }), { level: 'B2', family: 'Conditionals' });
  assert.deepEqual(headerMeta({ level: 'B2', category: 'Conditionals' }), { level: 'B2', family: 'Conditionals' }, 'category is the fallback when module is absent');
  assert.deepEqual(headerMeta({}), { level: '', family: '' }, 'nothing measured is honest empty text, not invented');
}

console.log('Orena Grammar surface (Library + Concept) screen mapping, rule-40 zeros, no invented data: PASS');
