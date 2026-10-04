/* Gate for Word Detail's pure data mapping (static/orena/screens/word/model.js), D-091.
   Imports only the DOM-free module - no globals to stub, no fetch. Every assertion here ties back
   to a real backend contract (WordDetail.json, the saved-vocabulary item, the stroke-order
   payload) rather than the frame's own sample data, and checks rule 40 (never invent a metric,
   never fabricate a record) explicitly. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  contextFor,
  pronunciationOf,
  savedTone,
  masteryFilled,
  stageCopyKey,
  dueInfo,
  highlightExample,
  mapWordCard,
  mapDeepWord,
  mapClip,
  mapClips,
  mapMasteryEvidence,
  restorePayload,
  savePayload,
  hanziCharsOf,
  mapStrokeCharacters,
  cardLanguage,
  posLabel,
} from '../static/orena/screens/word/model.js';

/* --- contextFor: the server rejects a context that does not contain the word --- */
assert.equal(contextFor('buffer', null), 'buffer', 'no item: the word is its own valid context');
assert.equal(
  contextFor('buffer', { source_fragment: 'Keep a buffer before the deadline.' }),
  'Keep a buffer before the deadline.',
  'a real source sentence that actually contains the word is used',
);
assert.equal(
  contextFor('buffer', { source_fragment: 'This sentence has nothing to do with it.' }),
  'buffer',
  "a source fragment that doesn't contain the word is never sent as if it did",
);

/* --- pronunciationOf: one slot, language-dependent content, never invented --- */
assert.equal(pronunciationOf({ script: 'hanzi', pinyin: 'huǎn chōng' }, null), 'huǎn chōng');
assert.equal(pronunciationOf({ script: 'latin', ipa: '/ˈbʌfər/' }, null), '/ˈbʌfər/');
assert.equal(pronunciationOf(null, { phonetic: '/ˈbʌfər/' }), '/ˈbʌfər/', 'falls back to the saved item when the lookup is unavailable');
assert.equal(pronunciationOf(null, null), '', 'no data anywhere is an empty string, not a placeholder');

/* --- savedTone: tokens only, never the frame's literal hex --- */
assert.deepEqual(savedTone(true), { bg: 'var(--amber-soft)', color: 'var(--amber)' });
assert.deepEqual(savedTone(false), { bg: 'var(--surface2)', color: 'var(--muted)' });
for (const tone of [savedTone(true), savedTone(false)]) {
  assert.doesNotMatch(tone.bg, /#|rgb/, 'no colour literal');
  assert.doesNotMatch(tone.color, /#|rgb/, 'no colour literal');
}

/* --- masteryFilled / stageCopyKey: real schedule data, clamped, rule 40 default is 0 --- */
assert.equal(masteryFilled(null), 0, 'an unsaved word has zero mastery bars, not a guess');
assert.equal(masteryFilled({ review_stage: 2 }), 2);
assert.equal(masteryFilled({ review_stage: 9 }), 4, 'clamped to the 4 bars the frame draws');
assert.equal(masteryFilled({ review_stage: -3 }), 0, 'clamped at zero, never negative');
assert.equal(stageCopyKey(null), '', 'no item, no stage to report');
assert.equal(stageCopyKey({ stage_label: 'Reinforcing' }), 'stageReinforcing');
assert.equal(stageCopyKey({ stage_label: 'Available' }), 'stageAvailable');
assert.equal(stageCopyKey({ stage_label: 'made-up' }), '', 'an unrecognised label is not guessed into one of the four');

/* --- dueInfo: real dates, or nothing to report --- */
assert.equal(dueInfo(null), null, 'no item, no due line');
assert.equal(dueInfo({ next_review_at: '' }), null, 'no schedule, no due line (not "due today" by default)');
const now = Date.parse('2026-09-27T09:00:00');
assert.deepEqual(dueInfo({ due: true, next_review_at: '2026-09-27T08:00:00' }, now), { key: 'dueToday' });
assert.deepEqual(
  dueInfo({ due: false, next_review_at: '2026-09-30T09:00:00' }, now),
  { key: 'dueInDays', n: 3 },
  'a real day count from the real schedule, not the frame\'s canned "review in N days" formula',
);
assert.deepEqual(dueInfo({ due: false, next_review_at: '2099-01-01T00:00:00' }, now).key, 'dueInDays');
// Past and today, with `due` not set, are due today - against the same fixed clock.
assert.deepEqual(dueInfo({ due: false, next_review_at: '2026-09-20T09:00:00' }, now), { key: 'dueToday' }, 'a past date is due today');
assert.deepEqual(dueInfo({ due: false, next_review_at: '2026-09-27T09:00:00' }, now), { key: 'dueToday' }, 'exactly now is due today');
// A date that cannot be read is no due line at all, never a guess.
assert.equal(dueInfo({ due: false, next_review_at: 'not-a-date' }, now), null, 'an unreadable date reports nothing');
assert.equal(dueInfo({ due: true }, now), null, 'no date, no due line, even when flagged due');

/* --- highlightExample: only a real occurrence is highlighted --- */
assert.deepEqual(highlightExample('', 'buffer'), [], 'no example, no parts');
assert.deepEqual(highlightExample('Keep a buffer.', ''), [{ value: 'Keep a buffer.', hit: false }]);
assert.deepEqual(highlightExample('Nothing matches here.', 'buffer'), [{ value: 'Nothing matches here.', hit: false }], 'a word absent from the sentence is never marked as found');
assert.deepEqual(highlightExample('Keep a buffer before it breaks.', 'buffer'), [
  { value: 'Keep a ', hit: false },
  { value: 'buffer', hit: true },
  { value: ' before it breaks.', hit: false },
]);

/* --- mapWordCard: the header/meaning/footer shape, from whichever answer carries each field --- */
const zhCard = mapWordCard('缓冲', {
  detail: { headword: '缓冲', script: 'hanzi', pinyin: 'huǎn chōng', partOfSpeech: '', contextMeaning: 'to cushion; a buffer', saved: false, audioUrl: '' },
  item: null,
});
assert.equal(zhCard.script, 'hanzi');
assert.equal(zhCard.saved, false);
assert.equal(zhCard.hasLevel, false, 'no level in either answer: the chip is left out, not shown empty');
assert.equal(zhCard.hasSchedule, false, 'an unsaved word has no mastery footer to draw at all');

/* mapWordCard reads the real clock (it takes no `now`), so its saved item is scheduled relative
   to it, far enough ahead that the day count cannot cross a boundary while the test runs. */
const inFiveDays = new Date(Date.now() + 5 * 86400000).toISOString();
const savedCard = mapWordCard('buffer', {
  detail: { headword: 'buffer', script: 'latin', ipa: '/ˈbʌfər/', partOfSpeech: 'noun', contextMeaning: 'extra time or space kept in reserve', saved: true, audioUrl: '/a.mp3' },
  item: { word: 'buffer', level: 'B1', review_stage: 2, stage_label: 'Reinforcing', due: false, next_review_at: inFiveDays, translation_vi: 'khoảng đệm', source_fragment: 'Keep a buffer before the deadline.' },
  supportLanguage: 'vi',
});
/* D-124: the support line is the sense's localization for the learner's support language. A
   learner record's older `translation_vi` is only the Vietnamese localization, never shown to
   another support language, and the sense's own localization wins over it. */
const bufferItem = { word: 'buffer', translation_vi: 'khoảng đệm' };
assert.equal(mapWordCard('buffer', { item: bufferItem, supportLanguage: 'en' }).hasSupport, false);
assert.equal(mapWordCard('buffer', { item: bufferItem, supportLanguage: 'zh' }).hasSupport, false);
const localized = { ...bufferItem, short_meanings: [{ language: 'vi', text: 'vùng đệm' }, { language: 'fr', text: 'tampon' }] };
assert.equal(mapWordCard('buffer', { item: localized, supportLanguage: 'vi' }).support, 'vùng đệm');
assert.equal(mapWordCard('buffer', { item: localized, supportLanguage: 'fr' }).support, 'tampon');
assert.equal(savedCard.saved, true);
assert.equal(savedCard.savedBg, 'var(--amber-soft)');
assert.equal(savedCard.hasLevel, true);
assert.equal(savedCard.level, 'B1');
assert.equal(savedCard.stageKey, 'stageReinforcing');
assert.equal(savedCard.filled, 2);
assert.equal(savedCard.hasSupport, true);
assert.equal(savedCard.support, 'khoảng đệm');
assert.deepEqual(savedCard.due, { key: 'dueInDays', n: 5 });
assert.ok(savedCard.exampleParts.some((part) => part.hit), 'the saved source sentence highlights the real headword');

const unknownCard = mapWordCard('zzznope', { detail: null, item: null });
assert.equal(unknownCard.saved, false);
assert.equal(unknownCard.hasMeaning, false, 'nothing knows this word: no invented meaning');
assert.equal(unknownCard.filled, 0);

/* `available: false` (`claim: "word_detail_unavailable"`) means the whole lookup is unresolved,
   even when an individual field like `partOfSpeech` still comes back non-empty (a real backend
   response shape: POST /api/dictionary/word-detail on an unresolvable word) - that field must not
   render as though it were a real fact about the word (rule 40). */
const unresolvedCard = mapWordCard('thiswordreallydoesnotexistxyz123', {
  detail: { available: false, claim: 'word_detail_unavailable', partOfSpeech: 'noun', contextMeaning: '', headword: 'thiswordreallydoesnotexistxyz123' },
  item: null,
});
assert.equal(unresolvedCard.pos, '', 'an unresolved lookup does not get to render a part-of-speech chip');
assert.equal(unresolvedCard.hasMeaning, false);
// A saved item's own real part_of_speech still renders even when the fresh lookup is unresolved.
const unresolvedButSavedCard = mapWordCard('buffer', {
  detail: { available: false, claim: 'word_detail_unavailable', partOfSpeech: 'noun', contextMeaning: '' },
  item: { word: 'buffer', part_of_speech: 'noun (verb)', review_stage: 1 },
});
assert.equal(unresolvedButSavedCard.pos, 'noun (verb)', "the saved item's own real field still wins over discarding an unresolved detail");

/* `saved` with no item present is read straight off `detail.saved` - a mount-time snapshot that
   never refetches itself. screen.js's unsave handler (not this pure function - see its own
   comment) is responsible for passing a corrected `saved: false` once a real delete has just
   happened, since a stale `true` here would otherwise outrank it; this only documents the plain,
   non-stale case the function itself controls. */
const staleDetailCard = mapWordCard('buffer', {
  detail: { headword: 'buffer', script: 'latin', ipa: '/ˈbʌfər/', partOfSpeech: 'noun', contextMeaning: 'extra time or space kept in reserve', saved: false, audioUrl: '/a.mp3' },
  item: null,
});
assert.equal(staleDetailCard.saved, false, 'saved:false plus no item is not saved, not a guess from an older answer');
assert.equal(staleDetailCard.hasSchedule, false, 'no item: no mastery footer to draw');

/* --- mapDeepWord: only rows with real content; "Natural patterns" from real example sentences --- */
assert.deepEqual(mapDeepWord(null), [], 'no explanation, no Deep Word card at all');
assert.deepEqual(mapDeepWord({ deeper: {} }), [], 'an explanation with nothing in it is still no card');
const deep = mapDeepWord({
  deeper: { coreIdea: 'Extra room kept in reserve.', whyHere: '', commonMistake: 'Not "a buffer of time" as a countable thing in every register.', examples: ['We built in a buffer.', '', 'Add a buffer for delays.'] },
});
assert.deepEqual(deep.map((row) => row.key), ['deepCoreIdea', 'deepWatchOut', 'deepPatterns'], 'whyHere absent -> its row is left out, not shown empty');
assert.equal(deep.find((row) => row.key === 'deepPatterns').value, 'We built in a buffer. · Add a buffer for delays.');

/* --- clips: real catalogue moments, never a placeholder for a word never said --- */
assert.deepEqual(mapClips(null), []);
assert.deepEqual(mapClips({ clips: [] }), []);
const clip = mapClip({ text: 'We need a buffer.', title: 'Office Talk', at: '01:12', seconds: 4, lessonId: 'l1', startMs: 72000, endMs: 76000, url: '/c.mp3' });
assert.equal(clip.text, 'We need a buffer.');
assert.equal(clip.source, 'Office Talk · 01:12');
assert.equal(mapClips({ clips: [{ text: '' }, { text: 'ok', title: 't', at: '0:00' }] }).length, 1, 'a clip with no real line is dropped, not shown blank');

/* --- mastery evidence: real, dated facts only - never a zero-count row --- */
assert.deepEqual(mapMasteryEvidence(null), [], 'no item, no evidence card content');
assert.deepEqual(mapMasteryEvidence({ added_at: '', successful_recalls: 0, lapse_count: 0, last_reviewed_at: '' }), [], 'nothing has actually happened yet: the empty state, not five placeholders');
const evidence = mapMasteryEvidence({ added_at: '2026-08-01T00:00:00', source_kind: 'reading', successful_recalls: 3, lapse_count: 0, last_reviewed_at: '2026-09-20T00:00:00' });
assert.deepEqual(evidence.map((row) => row.key), ['evidenceReviewed', 'evidenceRecalled', 'evidenceSaved'], 'lapse_count is 0: that row is left out entirely, not "missed 0 times"');
assert.equal(evidence.find((row) => row.key === 'evidenceRecalled').n, 3);

/* --- restore/save payloads: exactly what the server needs, nothing reconstructed --- */
assert.equal(restorePayload(null), null);
const restore = restorePayload({ word: 'buffer', phonetic: '/ˈbʌfər/', part_of_speech: 'noun', definition: 'x', translation_vi: 'y', added_at: '2026-08-01T00:00:00', source_fragment: '', source_kind: 'manual', focus_note: '', review_stage: 2, successful_recalls: 3, lapse_count: 0, last_reviewed_at: '2026-09-20T00:00:00', source_essay_id: null });
assert.equal(restore.word, 'buffer');
assert.equal(restore.review_stage, 2);
assert.ok(!('source_essay_id' in restore), 'a null field is left out, not sent as null');
// Undo keeps the schedule and the catalogue identity (mirrors quick-sheet's wordRestorePayload).
const scheduled = restorePayload({ word: 'buffer', review_stage: 2, next_review_at: '2026-10-01T00:00:00Z', entry_identity_key: 'en:buffer:noun', entry_id: 'e-1', reading_key: 'buffer' });
assert.equal(scheduled.next_review_at, '2026-10-01T00:00:00Z', 'the due date survives an undo');
assert.equal(scheduled.entry_identity_key, 'en:buffer:noun');
assert.equal(scheduled.entry_id, 'e-1');
assert.equal(scheduled.reading_key, 'buffer');
assert.ok(!('phonetic' in scheduled), 'a field the item never carried is left out, not sent as an empty string');
// Every field POST /api/library/vocabulary/restore accepts is carried when the item has it.
{
  const { readFileSync: readSource } = await import('node:fs');
  const python = readSource(new URL('../writing_coach/becoming_library.py', import.meta.url), 'utf8');
  const block = python.slice(python.indexOf('class RestoreVocabularyIn'), python.indexOf('\ndef ', python.indexOf('class RestoreVocabularyIn')));
  const fields = [...block.matchAll(/^ {4}(\w+): (?:str|int)/gm)].map((m) => m[1]);
  assert.ok(fields.length >= 18, `RestoreVocabularyIn's fields are read (${fields.length})`);
  const full = restorePayload(Object.fromEntries(fields.map((f) => [f, f === 'word' ? 'buffer' : /stage|recalls|count|essay_id/.test(f) ? 1 : 'x'])));
  assert.deepEqual(Object.keys(full).sort(), [...fields].sort(), 'restorePayload carries every field RestoreVocabularyIn accepts');
}
const save = savePayload({ word: 'buffer', ipa: '/ˈbʌfər/', pos: 'noun', meaning: 'extra room kept in reserve', support: 'khoảng đệm' });
assert.equal(save.source_kind, 'dictionary');
assert.equal(save.definition, 'extra room kept in reserve');

/* --- Stroke Practice: Chinese-only, real per-character stroke data --- */
assert.deepEqual(hanziCharsOf('buffer'), [], 'an English word has no Han characters to practise strokes for');
assert.deepEqual(hanziCharsOf('缓冲'), ['缓', '冲']);
const strokes = mapStrokeCharacters('缓冲冲', {
  characters: [
    { character: '缓', stroke_count: 12, stroke_paths: ['M0 0'], medians: [[[0, 0], [1, 1]]] },
    { character: '冲', stroke_count: 6, stroke_paths: ['M1 1'], medians: [[[1, 1], [2, 2]]] },
  ],
  unavailable: [],
});
assert.equal(strokes.length, 3, 'the repeated character keeps its place in the word, duplicates included');
assert.equal(strokes[0].ch, '缓');
assert.equal(strokes[1].ch, '冲');
assert.equal(strokes[2].ch, '冲');
assert.equal(strokes[2].available, true, 'the second occurrence of a character already seen is still resolved');
assert.deepEqual(strokes[2].data, strokes[1].data);
const missing = mapStrokeCharacters('缓氿', { characters: [{ character: '缓', stroke_count: 12, stroke_paths: [], medians: [] }], unavailable: ['氿'] });
assert.equal(missing[1].available, false, "a character the pack doesn't have is unavailable, not zero strokes");

/* --- languages-5 / finding A: cardLanguage - the one script-check fallback in this build, turned
   into a real `lang` code (kit/lang.js's `langAttr`/`langSpan` take 'en'/'zh', never 'hanzi'/
   'latin'). Fixes the bug this pass found: a Latin headword used to get lang="" (no attribute
   effect at all), not lang="en" - English text under a vi/zh interface went unmarked. --- */
assert.equal(cardLanguage('hanzi'), 'zh');
assert.equal(cardLanguage('latin'), 'en', 'a Latin-script card is real English, not an unmarked language');

/* --- languages-4 (2) / finding B.1: posLabel - the closed ALLOWED_POS space translates; anything
   else (an external dictionary's own wording, a content-authored free-text field) is returned
   verbatim with known:false, for the caller to mark lang="en" rather than translate it. --- */
const fakeT = (key) => `[${key}]`;
assert.deepEqual(posLabel('pronoun', fakeT), { text: '[posPronoun]', known: true });
assert.deepEqual(posLabel('PROPER_NOUN', fakeT), { text: '[posProperNoun]', known: true }, 'case-insensitive against the backend value');
assert.deepEqual(posLabel('transitive verb phrase', fakeT), { text: 'transitive verb phrase', known: false }, 'an unrecognised value is shown as-is, never guessed into one of the fifteen');
assert.deepEqual(posLabel('', fakeT), { text: '', known: false }, 'no part of speech at all is not a translated label either');

/* --- journeys-1 (P1): the main column must never sit blank behind only the back button while
   api.wordDetail() (AI-backed, 11-15s+ uncached in the sandbox) and api.wordClips() are pending.
   screen.js has no DOM to mount in this gate (no `document`), so this checks the source directly:
   the shared loading skeleton (kit/states.js - the same primitive the router's own lesson skeleton
   and Collection Detail already use, rule 40's "reuse before inventing") is painted before either
   async lookup starts, not only after both resolve. --- */
const screenSrc = readFileSync(new URL('../static/orena/screens/word/screen.js', import.meta.url), 'utf8');
// languages-5 / finding A: wires the shared kit/lang.js helper (never the old ad-hoc
// `? 'zh' : ''` ternary, which left a Latin card with no lang attribute at all).
assert.match(screenSrc, /import\s*\{\s*langAttr\s*\}\s*from\s*'\.\.\/\.\.\/kit\/lang\.js'/, 'imports the shared lang helper from kit/lang.js');
assert.doesNotMatch(screenSrc, /'hanzi'\s*\?\s*'zh'\s*:\s*''/, 'no ad-hoc script-to-lang ternary left inline (kit/lang.js + model.js#cardLanguage own this now)');
assert.match(screenSrc, /lang="\$\{langAttr\(cardLang\)\}"/, 'both the headword and the example carry a real lang attribute via the shared helper');
assert.match(screenSrc, /import\s*\{\s*loadingMarkup\s*\}\s*from\s*'\.\.\/\.\.\/kit\/states\.js'/, 'imports the shared loading skeleton primitive, not a bespoke one');
assert.match(screenSrc, /loadingMarkup\(t\('wordLoading'\)\)/, 'paints the loading skeleton with a real, translated status label');
const loadingCallIndex = screenSrc.indexOf("loadingMarkup(t('wordLoading'))");
const fetchItemCallIndex = screenSrc.indexOf('await fetchItem(word)');
const promiseAllIndex = screenSrc.indexOf('Promise.all([');
assert.ok(loadingCallIndex > -1 && fetchItemCallIndex > -1 && promiseAllIndex > -1, 'all three anchors are present in the mount function');
assert.ok(
  loadingCallIndex < fetchItemCallIndex && fetchItemCallIndex < promiseAllIndex,
  'the loading skeleton is mounted before the item lookup and before the AI-backed wordDetail/wordClips fetch, so the main column is never blank while either is pending',
);

console.log('test_orena_screen_word.mjs: Word Detail data mapping - real backend contracts, rule 40 throughout: PASS');
