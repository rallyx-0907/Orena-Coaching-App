/* Gate for the Word Quick Sheet / Sentence Quick Sheet overlay's pure data mapping
   (static/orena/screens/quick-sheet/model.js), D-066. Imports only the DOM-free module.

   Loads the real captured payloads (scripts/fixtures/api/word_detail_sheet(.zh).json,
   sentence_sheet(.zh).json - `POST .../word-detail` with `depth:'sheet'` and
   `POST .../sentence-sheet`, this sandbox's real `available:false` fallback, no AI provider key)
   so a screen model that reads a field these payloads do not carry fails this gate. The
   `available:true` shape (never captured here - no provider) is exercised with an object built
   field-for-field from `writing_coach/word_detail.py`'s own `project_word_detail()` /
   `project_sentence_sheet()` output keys, per the task brief - not shipped as data anywhere. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  contextFor,
  lookupContentId,
  wordDetailRequest,
  surfaceFor,
  posLabel,
  savedTone,
  masteryFilled,
  stageCopyKey,
  dueInfo,
  highlightExample,
  mapWordCard,
  wordSavePayload,
  resaveContextualMeaning,
  wordRestorePayload,
  mapSentenceSheet,
  vocabSavePayload,
  noteKeyFor,
  noteTypeColorKey,
  loadNotes,
  addNote,
  deleteNote,
} from '../static/orena/screens/quick-sheet/model.js';

function fixture(name) {
  return JSON.parse(readFileSync(new URL(`./fixtures/api/${name}`, import.meta.url)));
}

const T = (key, params) => {
  const table = { posNoun: 'noun', posAdjective: 'adjective', stageNew: 'New', stageReinforcing: 'Reinforcing' };
  return params ? `${table[key] || key}:${JSON.stringify(params)}` : table[key] || key;
};

/* --- contextFor: the server rejects a context that does not contain the selection --- */
assert.equal(contextFor('health', ''), 'health', 'no sentence: the selection is its own valid context');
assert.equal(contextFor('health', 'Regular exercise is good for your health.'), 'Regular exercise is good for your health.');
assert.equal(contextFor('health', 'This sentence has nothing to do with it.'), 'health', "a sentence that doesn't contain the selection is never sent as if it did");

/* --- surfaceFor: AGENT_CONTRACT §6.1 - the surface is where the learner is, not what they tapped --- */
assert.equal(surfaceFor({ kind: 'reading' }, 'fallback'), 'reading.workspace');
assert.equal(surfaceFor({ kind: 'listening' }, 'fallback'), 'listening.workspace');
assert.equal(surfaceFor({ kind: 'dictation' }, 'fallback'), 'listening.dictation');
assert.equal(surfaceFor(null, 'vocabulary.word'), 'vocabulary.word', 'no source: the caller-given fallback, never a guess');
assert.equal(surfaceFor({ kind: 'nonsense' }, 'vocabulary.word'), 'vocabulary.word', 'an unrecognised kind falls back too');

/* --- posLabel --- */
assert.deepEqual(posLabel('noun', T), { text: 'noun', known: true });
assert.deepEqual(posLabel('adjective', T), { text: 'adjective', known: true });
assert.deepEqual(posLabel('gizmo', T), { text: 'gizmo', known: false }, 'an out-of-set value is shown exactly as the backend gave it');
assert.deepEqual(posLabel('', T), { text: '', known: false });

/* --- savedTone: tokens only, never a literal --- */
assert.deepEqual(savedTone(true), { bg: 'var(--amber-soft)', color: 'var(--amber)' });
assert.deepEqual(savedTone(false), { bg: 'var(--surface2)', color: 'var(--muted)' });

/* --- rule 40: no saved item means 0/empty/null, never a guess --- */
assert.equal(masteryFilled(null), 0);
assert.equal(masteryFilled({ review_stage: 2 }), 2);
assert.equal(masteryFilled({ review_stage: 9 }), 4, 'clamped to the 4-bar frame');
assert.equal(stageCopyKey(null), '');
assert.equal(stageCopyKey({ stage_label: 'Reinforcing' }), 'stageReinforcing');
assert.equal(dueInfo(null), null);
assert.equal(dueInfo({}), null, 'a saved item with no schedule field reports no due line, not "due today"');
assert.deepEqual(dueInfo({ next_review_at: new Date(Date.now() - 1000).toISOString(), due: true }), { key: 'dueToday' });
{
  const inDays = dueInfo({ next_review_at: new Date(Date.now() + 86400000 * 3).toISOString(), due: false });
  assert.equal(inDays.key, 'dueInDays');
  assert.ok(inDays.n >= 2 && inDays.n <= 3);
}

/* --- highlightExample --- */
assert.deepEqual(highlightExample('', 'settled'), []);
assert.deepEqual(highlightExample('No match here.', 'settled'), [{ value: 'No match here.', hit: false }], 'a word absent from its own example is never fabricated as a match');
{
  const parts = highlightExample('She finally feels settled today.', 'settled');
  assert.ok(parts.some((p) => p.hit && p.value === 'settled'));
}

/* --- mapWordCard against the real captured "no AI provider" fallback (EN) --- */
{
  const detail = fixture('word_detail_sheet.json');
  assert.equal(detail.available, false, 'fixture is the real, current sandbox answer');
  const card = mapWordCard('health', { detail, item: null });
  assert.equal(card.word, 'health');
  assert.equal(card.script, 'latin');
  assert.equal(card.hasContent, false, 'meaningSource is "none": the frame\'s fallback branch, not the content card');
  assert.equal(card.saved, true, 'the fixture\'s own saved flag is carried through even in the fallback branch');
  assert.equal(card.example, '', 'no deeper.examples in this answer: never fabricated');
  assert.equal(card.hasSchedule, false, 'no saved-item record was supplied here');
}

/* --- mapWordCard against the real captured Chinese fallback --- */
{
  const detail = fixture('word_detail_sheet.zh.json');
  const card = mapWordCard('电视', { detail, item: null });
  assert.equal(card.script, 'hanzi');
  assert.equal(card.reading, 'kàn diàn shì', 'a real pinyin the lookup returned is shown even while the fallback branch is active');
  assert.equal(card.saved, false);
}

/* --- the reading is the field of the word's own script: pinyin for hanzi, IPA for latin, never the other --- */
{
  const zh = mapWordCard('政府', { detail: { headword: '政府', script: 'hanzi', pinyin: 'zhèng fǔ', ipa: null, contextMeaning: 'chính phủ', meaningSource: 'word_translation' } });
  assert.equal(zh.reading, 'zhèng fǔ');
  const en = mapWordCard('aid', { detail: { headword: 'aid', script: 'latin', pinyin: null, ipa: '/eɪd/', contextMeaning: 'viện trợ', meaningSource: 'word_translation' } });
  assert.equal(en.reading, '/eɪd/');
}

/* --- mapWordCard, the "available" branch: built from word_detail.py#project_word_detail's own
   keys (never captured - this sandbox has no AI provider), never shipped as a fixture --- */
{
  const detail = {
    headword: 'settled', script: 'latin', pinyin: null, ipa: '/ˈsɛtəld/', partOfSpeech: 'adjective',
    contextMeaning: 'feeling comfortable and relaxed in a place or situation',
    contextSentence: 'She finally feels settled in her new routine.',
    audioUrl: 'https://cdn.example/settled.mp3', saved: false,
    deeper: {
      coreIdea: '', mentalModel: '', whyHere: 'it describes an emotional state, not a location',
      contrast: [], examples: ['She finally feels settled in her new routine.'],
      commonMistake: '', grammarNote: '', relatedExpressions: [], sources: [], learnerSentences: [],
    },
    usageVerdict: null, meaningSource: 'context', depth: 'sheet', answer: '', followUps: [],
    available: true, claim: 'word_detail',
  };
  const item = { review_stage: 2, stage_label: 'Reinforcing', next_review_at: new Date(Date.now() + 86400000 * 3).toISOString(), due: false, level: 'B1' };
  const card = mapWordCard('settled', { detail, item });
  assert.equal(card.hasContent, true);
  assert.equal(card.meaning, detail.contextMeaning);
  assert.equal(card.example, detail.deeper.examples[0]);
  assert.ok(card.exampleParts.some((p) => p.hit));
  assert.equal(card.whyHere, detail.deeper.whyHere);
  assert.equal(card.hasSchedule, true);
  assert.equal(card.filled, 2);
  assert.equal(card.stageKey, 'stageReinforcing');
  assert.deepEqual(card.due, { key: 'dueInDays', n: 3 });
  assert.equal(card.level, 'B1', 'the saved item\'s own CEFR level, shown as the level chip - real data source library_vocabulary.json already carries');
}
{
  // No saved item at all: no level chip, ever (rule 40 - never a guessed CEFR level).
  const card = mapWordCard('settled', { detail: null, item: null });
  assert.equal(card.level, '');
}

/* --- wordSavePayload / wordRestorePayload --- */
{
  const card = { word: 'settled', reading: '/ˈsɛtəld/', pos: 'adjective', meaning: 'feeling comfortable' };
  const payload = wordSavePayload(card, 'She feels settled.', { kind: 'reading' });
  assert.deepEqual(payload, {
    word: 'settled', phonetic: '/ˈsɛtəld/', part_of_speech: 'adjective', definition: 'feeling comfortable',
    source_fragment: 'She feels settled.', source_kind: 'reading',
  });
  assert.equal(wordSavePayload(card, '', { kind: 'nonsense' }).source_kind, 'dictionary', 'an unrecognised kind never invents a source');
  assert.equal(wordRestorePayload(null), null);
  const restored = wordRestorePayload({ word: 'settled', review_stage: 2, lapse_count: 1, next_review_at: '2026-10-01T00:00:00Z' });
  assert.equal(restored.word, 'settled');
  assert.equal(restored.review_stage, 2);
  assert.equal(restored.next_review_at, '2026-10-01T00:00:00Z');
  assert.ok(!('phonetic' in restored), 'a field the item never carried is left out, not sent as an empty string');
}

/* --- mapSentenceSheet against the real captured "no AI provider" fallback --- */
{
  const response = fixture('sentence_sheet.json');
  assert.equal(response.available, false);
  const mapped = mapSentenceSheet(response);
  assert.equal(mapped.available, false);
  assert.deepEqual(mapped.translation, '');
  assert.deepEqual(mapped.structure, []);
  assert.deepEqual(mapped.vocabulary, [], 'no vocabulary tab content invented when the explanation is unavailable');
}
{
  const response = fixture('sentence_sheet.zh.json');
  assert.equal(mapSentenceSheet(response).available, false);
}

/* --- mapSentenceSheet, the "available" branch: built from word_detail.py#project_sentence_sheet's
   own keys - never captured, never shipped as a fixture --- */
{
  const response = {
    available: true, claim: 'sentence_sheet', answer: '',
    sentence: 'Regular exercise is good for your health.',
    translation: 'Tập thể dục đều đặn tốt cho sức khỏe của bạn.',
    shortExplanation: 'A simple statement linking a habit to a benefit.',
    structure: [
      { chunk: 'Regular exercise', role: 'subject' },
      { chunk: 'is good for', role: 'verb phrase' },
      { chunk: 'your health', role: 'object' },
    ],
    vocabulary: [
      { term: 'regular', meaning: 'happening often, at the same time', saved: false },
      { term: 'exercise', meaning: 'physical activity to stay fit', saved: true },
    ],
  };
  const mapped = mapSentenceSheet(response);
  assert.equal(mapped.available, true);
  assert.equal(mapped.translation, response.translation);
  assert.equal(mapped.structure.length, 3);
  assert.equal(mapped.vocabulary.length, 2);
  assert.equal(mapped.vocabulary[0].saved, false);
  assert.equal(mapped.vocabulary[1].saved, true);
  // a fresher client-side saved-terms set (after the learner just saved one in this visit)
  // overrides the answer's own snapshot, never contradicts a more current save.
  const refreshed = mapSentenceSheet(response, new Set(['regular']));
  assert.equal(refreshed.vocabulary[0].saved, true);
}

/* --- vocabSavePayload --- */
{
  const payload = vocabSavePayload('exercise', 'physical activity', 'Regular exercise is good.', { kind: 'listening' });
  assert.deepEqual(payload, { word: 'exercise', definition: 'physical activity', source_fragment: 'Regular exercise is good.', source_kind: 'listening' });
}

/* --- D18: the learner-language meaning is saved as such; an English fallback never lands in translation_vi --- */
{
  const vi = mapWordCard('松树', { detail: { headword: '松树', meaningSource: 'dictionary', meaningLanguage: 'vi', contextMeaning: 'cây thông' }, support: 'vi' });
  assert.equal(vi.meaningLanguage, '');
  assert.equal(wordSavePayload(vi, '', {}).translation_vi, 'cây thông');
  const en = mapWordCard('松树', { detail: { headword: '松树', meaningSource: 'dictionary', meaningLanguage: 'en', contextMeaning: 'pine tree' }, support: 'vi' });
  assert.equal(en.meaningLanguage, 'en', 'the fallback is labelled with its language');
  const saved = wordSavePayload(en, '', {});
  assert.equal(saved.definition, 'pine tree');
  assert.equal('translation_vi' in saved, false);
  const context = mapWordCard('x', { detail: { headword: 'x', meaningSource: 'context', meaningLanguage: '', contextMeaning: 'nghĩa' }, support: 'vi' });
  assert.equal(wordSavePayload(context, '', {}).translation_vi, 'nghĩa');
  const zhSupport = mapWordCard('x', { detail: { headword: 'x', meaningSource: 'context', contextMeaning: '意思' }, support: 'zh' });
  assert.equal('translation_vi' in wordSavePayload(zhSupport, '', {}), false);
  assert.equal(vocabSavePayload('a', 'nghĩa', 's', {}, 'vi').translation_vi, 'nghĩa');
  assert.equal('translation_vi' in vocabSavePayload('a', 'meaning', 's', {}, 'en'), false);
}

/* --- Owner decision 2026-10-18: the base meaning is always on the sheet; a contextual meaning never hides it,
   and an English definition shown to a Vietnamese/Chinese learner is always labelled with its language --- */
{
  // The base meaning alone (no contextual meaning): a VI learner never sees an unlabelled English definition.
  const english = mapWordCard('shields', { detail: { headword: 'shields', meaningSource: 'dictionary', meaningLanguage: 'en', contextMeaning: 'Anything that protects or defends' }, support: 'vi' });
  assert.equal(english.hasContent, true, 'a base meaning draws the word card, never the "not prepared" branch');
  assert.equal(english.meaningLanguage, 'en', 'the English fallback is labelled');
  const translated = mapWordCard('shields', { detail: { headword: 'shields', meaningSource: 'word_translation', meaningLanguage: 'vi', contextMeaning: 'tấm chắn' }, support: 'vi' });
  assert.equal(translated.hasContent, true);
  assert.equal(translated.meaningLanguage, '', 'a meaning in the support language carries no label');
  const enLearner = mapWordCard('shields', { detail: { headword: 'shields', meaningSource: 'dictionary', meaningLanguage: 'en', contextMeaning: 'Anything that protects' }, support: 'en' });
  assert.equal(enLearner.meaningLanguage, '', 'an English learner reads the English definition unlabelled');
  // A contextual meaning keeps the base meaning beside it, labelled when it is English.
  const contextual = mapWordCard('shields', { detail: { headword: 'shields', meaningSource: 'context', contextMeaning: 'tấm chắn nhiệt', generalMeaning: 'Anything that protects', generalMeaningLanguage: 'en' }, support: 'vi' });
  assert.equal(contextual.generalMeaning, 'Anything that protects', 'the base meaning stays under the contextual one');
  assert.equal(contextual.generalMeaningLanguage, 'en');
  const sameLanguage = mapWordCard('shields', { detail: { headword: 'shields', meaningSource: 'context', contextMeaning: 'x', generalMeaning: 'y', generalMeaningLanguage: 'vi' }, support: 'vi' });
  assert.equal(sameLanguage.generalMeaningLanguage, '');
  const sheetSrc = readFileSync(new URL('../static/orena/screens/quick-sheet/sheet.js', import.meta.url), 'utf8');
  assert.match(sheetSrc, /card\.generalMeaningLanguage \? ` · \$\{meaningLanguageLabel\(card\.generalMeaningLanguage/, 'the common meaning names its language when it is not the support language');
}

/* --- Notes: device memory (AGENTS.md §7), a fake Web Storage --- */
class FakeStorage {
  constructor() {
    this.data = new Map();
  }
  getItem(key) {
    return this.data.has(key) ? this.data.get(key) : null;
  }
  setItem(key, value) {
    this.data.set(key, String(value));
  }
}
{
  const storage = new FakeStorage();
  const key = noteKeyFor('Regular exercise is good for your health.', { kind: 'reading', content_id: 'a1', segment: null });
  assert.deepEqual(loadNotes(storage, 'me', key), []);
  const note = addNote(storage, 'me', key, { type: 'question', text: 'Why present simple here?' });
  assert.equal(note.type, 'question');
  assert.equal(loadNotes(storage, 'me', key).length, 1);
  assert.equal(loadNotes(storage, 'other-owner', key).length, 0, 'notes are scoped per learner, never shared across owners');
  addNote(storage, 'me', key, { type: 'not-a-real-type', text: 'x' });
  assert.equal(loadNotes(storage, 'me', key)[1].type, 'factual', 'an unrecognised type never invents a category - falls back to the safest one');
  const before = loadNotes(storage, 'me', key).length;
  const rejected = addNote(storage, 'me', key, { type: 'factual', text: '   ' });
  assert.equal(rejected, null, 'an empty note is never saved');
  assert.equal(loadNotes(storage, 'me', key).length, before);
  deleteNote(storage, 'me', key, note.id);
  assert.equal(loadNotes(storage, 'me', key).length, before - 1);
}
{
  const a = noteKeyFor('Hello world.', { kind: 'reading', content_id: 'a1', segment: null });
  const b = noteKeyFor('Hello world.', { kind: 'reading', content_id: 'a1', segment: null });
  const c = noteKeyFor('Hello world.', { kind: 'listening', content_id: 'a1', segment: null });
  assert.equal(a, b, 'the same sentence in the same place finds the same notes later');
  assert.notEqual(a, c, 'the same sentence text in a different place is a different note thread');
}
assert.equal(noteTypeColorKey('question'), 'var(--amber)');
assert.equal(noteTypeColorKey('reflection'), 'var(--accent-text)');
assert.equal(noteTypeColorKey('factual'), 'var(--muted)');
assert.equal(noteTypeColorKey('anything-else'), 'var(--muted)');

/* The latest lookup wins (successor of the retired test_orena_lookup_race, D-143): a sheet that has been
   replaced or closed ignores the answers its requests bring back later. Each sheet paints only while it is
   alive, and its cleanup ends that. */
{
  const source = readFileSync(new URL('../static/orena/screens/quick-sheet/sheet.js', import.meta.url), 'utf8');
  for (const name of ['openWordSheet', 'openSentenceSheet']) {
    const start = source.indexOf(`export async function ${name}`);
    assert.ok(start >= 0, `${name} exists`);
    const next = source.indexOf('export ', start + 10);
    const body = source.slice(start, next === -1 ? undefined : next);
    assert.match(body, /let alive = true;/, `${name}: a sheet starts alive`);
    assert.match(body, /if \(!sheetEl \|\| !alive\) return;/, `${name}: a replaced or closed sheet never paints`);
    assert.match(body, /return \(\) => \{\s*alive = false;/, `${name}: closing or replacing the sheet ends it`);
  }
}

/* --- Support-language meaning: main line = the localized meaning, secondary = the dictionary's original --- */
{
  const detail = {
    headword: 'resilient', script: 'latin', pinyin: null, ipa: null, partOfSpeech: 'adjective',
    contextMeaning: 'kiên cường; có khả năng phục hồi nhanh', meaningLanguage: 'vi', generalMeaning: '',
    originalDefinition: { text: 'able to recover quickly from difficult conditions', language: 'en', source: 'dictionary' },
    contextSentence: 'She is resilient.', audioUrl: '', saved: false,
    deeper: { whyHere: '', examples: [] }, meaningSource: 'dictionary', contextStatus: 'skipped', available: true,
  };
  const card = mapWordCard('resilient', { detail, item: null });
  assert.equal(card.meaning, 'kiên cường; có khả năng phục hồi nhanh');
  assert.equal(card.meaningIsContextual, false, 'a dictionary meaning is never labelled as this sentence\'s');
  assert.deepEqual(card.originalDefinition, { text: 'able to recover quickly from difficult conditions', language: 'en' });
  assert.equal(mapWordCard('resilient', { detail: { ...detail, originalDefinition: null } }).originalDefinition, null);
  const sheetSrc = readFileSync(new URL('../static/orena/screens/quick-sheet/sheet.js', import.meta.url), 'utf8');
  assert.match(sheetSrc, /card\.originalDefinition\s*\?\s*html`<div class="s-qs__general" lang=/, 'the original is the quieter second line, tagged with its own language');
}

/* --- A word saved before "Why here?" answers takes the contextual meaning onto its saved card --- */
{
  const sheetSrc = readFileSync(new URL('../static/orena/screens/quick-sheet/sheet.js', import.meta.url), 'utf8');
  const wordSheet = sheetSrc.slice(sheetSrc.indexOf('export async function openWordSheet'), sheetSrc.indexOf('Sentence Quick Sheet --'));
  assert.match(wordSheet, /if \(next\.hasContent\) \{ detail = answer; card = next; void keepContextualMeaning\(\); \}/, 'an arrived contextual meaning is kept on the saved card');
  // Unsave while "Why here?" is pending: the arriving answer says saved, but the learner's unsave wins, so no POST.
  const toggler = wordSheet.slice(wordSheet.indexOf('async function toggleSave'), wordSheet.indexOf('async function openStroke'));
  assert.match(toggler, /deleteLibraryVocabulary\(card\.word\);\s*keptNow = false;/, 'an unsave clears the learner flag');
  assert.match(wordSheet, /\{ \.\.\.enriched, saved: keptNow \}/, 'an answer never overrides the learner flag with its own saved:true');
  assert.match(wordSheet, /resaveContextualMeaning\(\{/, 'the sheet re-saves through the guarded model function');
  const calls = [];
  const api = { saveLibraryVocabulary: async (body) => { calls.push(body); return { item: { word: body.word, definition: body.definition } }; } };
  const card = { word: 'bubble', meaning: 'bong bóng', meaningIsContextual: true };
  const row = { word: 'bubble', source_kind: 'reading', source_fragment: 'A bubble rose.' };
  const make = (over = {}) => {
    const state = { kept: true, busy: false };
    return { state, args: { api, card, stored: async () => row, guard: { readOnly: false, kept: () => state.kept, busy: () => state.busy, setBusy: (v) => { state.busy = v; }, ...over } } };
  };
  // The learner unsaves before the enrichment resolves: no POST.
  { const { state, args } = make(); state.kept = false; assert.equal(await resaveContextualMeaning(args), null); assert.equal(calls.length, 0, 'an unsaved word is never re-saved'); }
  // Unsaved while the stored row is being read: still no POST.
  { const { state, args } = make(); args.stored = async () => { state.kept = false; return row; }; assert.equal(await resaveContextualMeaning(args), null); assert.equal(calls.length, 0); }
  // A save or unsave in flight, or a read-only sheet: no POST.
  { const { state, args } = make(); state.busy = true; await resaveContextualMeaning(args); assert.equal(calls.length, 0); }
  { const { args } = make({ readOnly: true }); await resaveContextualMeaning(args); assert.equal(calls.length, 0); }
  // An empty stored kind cannot be sent back (the API would default it to "manual"): not re-saved.
  { const { args } = make(); args.stored = async () => ({ ...row, source_kind: '' }); await resaveContextualMeaning(args); assert.equal(calls.length, 0); }
  // Still kept: only the definition changes, the stored source goes back as it was, and busy is held during the write.
  { const { state, args } = make(); let heldDuring = false;
    const original = api.saveLibraryVocabulary; api.saveLibraryVocabulary = async (body) => { heldDuring = state.busy; return original(body); };
    const saved = await resaveContextualMeaning(args); api.saveLibraryVocabulary = original;
    assert.deepEqual(calls, [{ word: 'bubble', definition: 'bong bóng', source_kind: 'reading', source_fragment: 'A bubble rose.' }]);
    assert.equal(saved.definition, 'bong bóng'); assert.equal(heldDuring, true, 'busy is held while the write is in flight'); assert.equal(state.busy, false, 'and released after'); }
}

/* --- A tap is deterministic: the contextual (AI-backed) meaning is the learner's own "Why here?" ask only --- */
{
  const sheetSrc = readFileSync(new URL('../static/orena/screens/quick-sheet/sheet.js', import.meta.url), 'utf8');
  const wordSheet = sheetSrc.slice(sheetSrc.indexOf('export async function openWordSheet'), sheetSrc.indexOf('Sentence Quick Sheet --'));
  assert.ok(wordSheet.length > 1000, 'the word sheet source was located');
  assert.match(wordSheet, /let contextualPending = false;/, 'nothing is pending when the sheet opens');
  assert.match(wordSheet, /wordDetailRequest\(\{ contextual: false, target/,'the opening lookup is the deterministic one');
  const asks = [...wordSheet.matchAll(/askContextual\(\)/g)].map((m) => wordSheet.slice(Math.max(0, m.index - 40), m.index));
  assert.ok(asks.length >= 2, 'the explicit asks exist');
  for (const before of asks) assert.match(before, /addEventListener\('click', \(\) => $/, 'askContextual() runs only from a click handler, never on its own');
  assert.doesNotMatch(wordSheet, /meaningPending/, 'no spinner replaces an available dictionary meaning');
  assert.match(wordSheet, /wordDetailRequest\(\{ contextual: true, target/,'the explicit Why here? ask says so: the server treats a sheet without the flag as deterministic');
  const wordScreen = readFileSync(new URL('../static/orena/screens/word/screen.js', import.meta.url), 'utf8');
  assert.match(wordScreen, /depth: 'full', contextual: true/, 'Deep Word asks for its explanation explicitly');
  assert.match(wordSheet, /data-why-ask/, "frame 53's always-drawn Why here? row is the trigger");
  const listening = readFileSync(new URL('../static/orena/screens/listening/vocab-sheet.js', import.meta.url), 'utf8');
  assert.match(listening, /wordDetailRequest\(\{ contextual: false/, 'the Listening vocabulary taps are deterministic too');
  assert.match(listening, /resolveTerm\(row\.word, \{ lang, support, context, source \}\)/, 'and they carry the lesson as their source');
}

/* --- The lookup names the published content it is from (D-228); a personal import names none --- */
{
  const base = { contextual: false, target: 'bank', context: 'The bank was closed.', lang: 'en', support: 'vi' };
  const shared = wordDetailRequest({ ...base, source: { kind: 'reading', content_id: 'article:abc-123' } });
  assert.equal(shared.content_id, 'article:abc-123', 'a shared article reading carries its content id');
  assert.deepEqual(
    { depth: shared.depth, contextual: shared.contextual, text: shared.text, context: shared.context },
    { depth: 'sheet', contextual: false, text: 'bank', context: 'The bank was closed.' },
  );
  assert.equal(wordDetailRequest({ ...base, contextual: true, source: { kind: 'reading', content_id: 'article:abc-123' } }).contextual, true);
  assert.equal(wordDetailRequest({ ...base, source: { kind: 'listening', content_id: 'media:m-9', segment: 's1' } }).content_id, 'media:m-9', 'a listening item carries its content id');
  assert.equal('content_id' in wordDetailRequest({ ...base, source: { kind: 'reading', content_id: 'text:imp-1' } }), false, 'a personal import carries none');
  assert.equal('content_id' in wordDetailRequest({ ...base, source: null }), false, 'no source, no content id');
  assert.equal('content_id' in wordDetailRequest({ ...base, source: { kind: 'reading', content_id: '' } }), false);
  assert.equal(lookupContentId({ content_id: 'book:b:c1' }), 'book:b:c1');
}

console.log('test_orena_screen_quick-sheet.mjs: Word/Sentence Quick Sheet data mapping - real backend contracts (captured + serializer-built), rule 40 throughout: PASS');
