/* The learner language contract, enforced against the surfaces themselves.

   Orena has two learner language roles and only two. The support language owns
   every word Orena says - navigation, controls, headings, instructions, status,
   errors, feedback, explanations, tooltips. The learning language owns the
   material - the transcript, the book, the target sentence, the example.

   The gate this replaces was too shallow to catch the defect it was meant to
   catch: a partial Vietnamese pack merged over English still rendered, so
   every test passed while a learner with Vietnamese support read "Dictation",
   "Feedback target", "USED WELL" and "Review my words" in the middle of their
   own language. Counting keys in a pack cannot see that. This reads the
   surfaces, collects every interface string each one actually asks for, and
   requires the supported locales to own all of them.

   Platform Admin is not a learner surface and is deliberately not listed. */
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { copy, supportedLocales, untranslated } from '../static/orena/ui/copy.js';
import { referenceCopy } from '../static/orena/ui/reference.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

/* Every learner-facing module, found rather than listed, so a new room cannot
   join Orena without joining this gate. Admin is the one exclusion, and it is
   named here so the exclusion is a decision rather than an oversight. */
const NOT_A_LEARNER_SURFACE = new Set(['admin.js']);
/* Platform Admin is not a learner surface, and part of it is hosted inside a
   module that also serves learners: the media import form lives in
   `media-library.js`, and the Admin destination is named in the shell's
   navigation but is rendered only for `user.is_admin`. Its strings are marked
   by their key, so the boundary is the prefix rather than the file. */
const platformAdmin = (key) => /^admin/.test(key);
const learnerSurfaces = [
  'static/orena/app.js',
  ...readdirSync(new URL('../static/orena/ui', import.meta.url))
    .filter((name) => name.endsWith('.js') && !NOT_A_LEARNER_SURFACE.has(name))
    .map((name) => `static/orena/ui/${name}`),
];
assert.ok(learnerSurfaces.length > 20, 'the learner surfaces were actually found');

/* What a surface says is what it reads off the copy object it is handed -
   including the strings it composes a key for at the point of use. A topic, a
   theme, a part of speech, a rubric category and a growth domain are all named
   as `c['topic_' + topic]` or `` c[`pos_${tag}`] ``, and the first version of
   this gate could not see them: it read literal keys only, so six English
   topic labels sat in a Vietnamese room with every test passing. A family is
   answered whole or not at all - half a family shows one word in Vietnamese
   and the next in English, inside the same sentence. */
function interfaceStringsIn(source) {
  const keys = new Set();
  for (const match of source.matchAll(/\bc\.([A-Za-z_][A-Za-z0-9_]*)/g)) keys.add(match[1]);
  for (const match of source.matchAll(/\bc\[\s*'([^']+)'\s*\]/g)) keys.add(match[1]);
  for (const match of source.matchAll(/\bc\[\s*[`']([A-Za-z_][A-Za-z0-9_]*_)(?:'\s*\+|\$\{)/g))
    for (const key of Object.keys(copy.en)) if (key.startsWith(match[1])) keys.add(key);
  return [...keys].filter((key) => copy.en[key] !== undefined);
}

const asked = new Map();
for (const path of learnerSurfaces)
  for (const key of interfaceStringsIn(read(path))) {
    if (platformAdmin(key)) continue;
    (asked.get(key) || asked.set(key, []).get(key)).push(path);
  }
assert.ok(asked.size > 300, `the learner surfaces ask for real copy (${asked.size})`);

/* --- No silent fallback on a supported learner surface ------------------ */
for (const locale of supportedLocales) {
  if (locale === 'en') continue;
  const missing = untranslated(locale, [...asked.keys()]).sort();
  assert.deepEqual(
    missing,
    [],
    `${locale} silently shows English on learner surfaces for: ${missing
      .slice(0, 20)
      .map((key) => `${key} (${asked.get(key)[0]})`)
      .join(', ')}${missing.length > 20 ? ` and ${missing.length - 20} more` : ''}`,
  );
}

/* Owning a key is not the same as having translated it, so the words are
   checked too: a locale that answered with the English sentence has not
   answered. Short labels that are genuinely the same in both - a framework's
   name, a percentage, a letter range - are the exception and are named. */
const SAME_IN_EVERY_LANGUAGE = new Set([
  'vocabularyFramework_toeic',
  'vocabularyFramework_hsk',
  'vocabularySortAlpha',
  'readerProgress',
  // Vietnamese borrows this one whole; translating it would be inventing a word.
  'mediaVideo',
  'adminVocabularyCollectionTitlePlaceholder',
  'adminVocabularyCollectionIdPlaceholder',
]);
for (const locale of supportedLocales) {
  if (locale === 'en') continue;
  const echoed = [...asked.keys()].filter(
    (key) => !SAME_IN_EVERY_LANGUAGE.has(key) && copy[locale][key] === copy.en[key],
  );
  assert.deepEqual(echoed, [], `${locale} repeats the English words for: ${echoed.join(', ')}`);
}

/* --- The shell's own pack is held to the same contract ------------------ */
/* The rail, the room headings and the collection lenses read from a second
   pack (`ui/reference.js`), because those strings belong to the reference
   layer rather than to any room. It is a second pack, not a second system:
   same two language roles, same rule, so it is checked here rather than given
   a gate of its own - and it was exactly where the leak was widest, with
   forty-five English headings sitting over Vietnamese. */
const referenceSource = read('static/orena/ui/reference.js');
assert.match(referenceSource, /referenceCopy\.vi = \{/, 'the shell pack has a Vietnamese pack');
/* Vietnamese borrows these two whole, as the Canonical UI Baseline's own Vietnamese does
   ("VIDEO", "Nhập audio"); translating them would be inventing a word. */
const BORROWED_BY_VIETNAMESE = new Set(['dictVideo', 'dictAudio']);
/* The design's own product vocabulary (Design Contract, rule 45): the baseline names its destinations and
   skills in English in its Vietnamese interface, and the design's rule is to keep the names already used. */
const DESIGN_PRODUCT_NAMES = new Set(['home', 'library', 'vocabulary', 'progress', 'profile', 'reading', 'listening', 'speaking', 'writing', 'dictation', 'tabVocabulary']);
for (const locale of ['zh', 'vi']) {
  const echoed = Object.keys(referenceCopy.en).filter(
    (key) =>
      !platformAdmin(key) &&
      !(locale === 'vi' && (BORROWED_BY_VIETNAMESE.has(key) || DESIGN_PRODUCT_NAMES.has(key))) &&
      referenceCopy[locale][key] === referenceCopy.en[key],
  );
  assert.deepEqual(
    echoed,
    [],
    `the shell still speaks English to a ${locale} learner in: ${echoed.join(', ')}`,
  );
}

/* --- The fallback is recorded, not hidden ------------------------------- */
const copySource = read('static/orena/ui/copy.js');
assert.match(copySource, /export const supportedLocales/, 'which locales are supported is stated');
assert.match(copySource, /export function untranslated/, 'and what each one is missing is readable');
const shell = read('static/orena/app.js');
assert.match(shell, /untranslated\(ui\)/, 'the shell asks what the chosen locale is missing');
assert.match(shell, /console\.warn\(/, 'and says so where a developer will see it');
assert.doesNotMatch(shell, /throw .*untranslated|throw .*copy/, 'without breaking the page for a learner');

/* --- Support language and learning language are different things -------- */
/* A surface that prints learner material marks it with the learning language,
   and a surface that prints Orena's own words marks it with the support
   language. The transcript is the case that has to be right: the line is the
   material, its meaning is Orena speaking. */
const encounter = read('static/orena/ui/encounter.js');
assert.match(
  encounter,
  /<span class="line-original" lang="\$\{language\}"/,
  'the spoken line is the learning language',
);
assert.match(
  encounter,
  /<span class="line-meaning" lang="\$\{esc\(ctx\.support\)\}"/,
  'and what it means is the support language',
);
assert.match(
  encounter,
  /<span class="line-pinyin" data-line-pinyin lang="\$\{language\}"/,
  'a reading belongs to the language it reads',
);
/* Nothing in this gate may push a translator towards translating content: the
   keys checked above are interface strings, and a title or a passage never
   becomes one. */
for (const key of [...asked.keys()])
  assert.ok(
    copy.en[key] !== undefined,
    `${key} is an interface string with an English original, not content`,
  );

/* --- Vietnamese and Chinese are the same kind of citizen ---------------- */
for (const locale of ['zh', 'vi']) {
  assert.ok(copy[locale], `${locale} has a copy pack`);
  assert.equal(
    Object.keys(copy[locale]).length >= Object.keys(copy.en).length,
    true,
    `${locale} answers for every English key`,
  );
}
/* The three locales are genuinely three, not one wearing two names. */
for (const key of ['exitPractice', 'previousLine', 'lineNow', 'lookCloser', 'review'])
  assert.equal(
    new Set([copy.en[key], copy.zh[key], copy.vi[key]]).size,
    3,
    `${key} reads differently in each supported language`,
  );

console.log(
  `Learner language: ${asked.size} interface strings, no silent English on any learner surface, EN/ZH/VI: PASS`,
);
