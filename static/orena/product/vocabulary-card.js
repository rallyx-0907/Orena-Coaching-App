/* The vocabulary card's content model (D-178, D-17W): one pure mapper from whatever a surface holds
   about a word to what the shared VocabularyCard (kit/vocabulary-card.js) draws.

   A "flashcard" is the existing vocabulary entry shown differently, so the inputs are the shapes the
   backend already answers - a saved-word item (`becoming_library.py#_row_to_item`, which reads the
   catalogue entry through), a catalogue card (`vocabulary_cards.py#vocabulary_card_from_catalog_entry`,
   Collection Detail and the Daily Feed), a raw catalogue entry, the word seed a list leaves behind,
   and the Word Detail lookup (`POST /api/dictionary/word-detail`). Whichever carries a field gives it.

   PURE CONTENT. No learner state is read or returned here - not saved, stage, due, mastery or the
   learner's own sentence. A screen that has a learner record applies `learnerState(item)` beside the
   model; the Admin preview renders the same model with none (D-178 point 5). No DOM, no fetch.

   Rule 40 throughout: a field nobody carries is absent (an empty list, null), never invented. The
   support-language layer (translations, labels, explanations, tips) shows only in the learner's
   support language; the meaning alone falls back to another language, tagged with it
   (product/vocabulary-meaning.js, D-124). */
import { localizedMeaning, vocabularyMeaning } from './vocabulary-meaning.js';
import { dueInfo } from './due-schedule.js';

const HAN = /[㐀-鿿]/;
const LETTER = /[\p{L}\p{N}_]/u;

function text(value) {
  return String(value ?? '').trim();
}

function list(value) {
  return Array.isArray(value) ? value : [];
}

function lower(value) {
  return text(value).toLowerCase();
}

/* A language-tagged support value (`{vi: '…'}`) in the support language only; a plain string is
   already the learner's (older shapes). */
function inSupport(value, supportLanguage) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const found = text(value[lower(supportLanguage)]);
    return found ? { text: found, language: lower(supportLanguage) } : null;
  }
  const plain = text(value);
  return plain ? { text: plain, language: '' } : null;
}

export function scriptOf(word, language = '') {
  return lower(language).startsWith('zh') || HAN.test(text(word)) ? 'hanzi' : 'latin';
}

/* ---- Highlight -------------------------------------------------------------------------------
   An example's highlight is a string to find (`highlight.match`, the `occurrence`-th time,
   default 1; docs/vocab README), never character offsets. Latin script is matched as a whole word
   (a match inside a longer word is no match: "cat" never lights "category"); Han has no word
   boundaries and is matched where it stands. With no authored highlight, the headword is looked for
   the same way, case-insensitively for Latin. Not found: one plain part - the sentence is shown
   unhighlighted rather than wrongly. */
function findSpan(sentence, needle, occurrence, { latin, caseless }) {
  if (!sentence || !needle) return -1;
  const haystack = caseless ? sentence.toLowerCase() : sentence;
  const target = caseless ? needle.toLowerCase() : needle;
  let seen = 0;
  let from = 0;
  while (from <= haystack.length) {
    const at = haystack.indexOf(target, from);
    if (at < 0) return -1;
    const before = at > 0 ? sentence[at - 1] : '';
    const after = sentence[at + needle.length] || '';
    const whole = !latin || (!LETTER.test(before) && !LETTER.test(after));
    if (whole) {
      seen += 1;
      if (seen === occurrence) return at;
    }
    from = at + 1;
  }
  return -1;
}

export function highlightParts(sentence, { match = '', occurrence = 1, latin = true, caseless = false } = {}) {
  const value = text(sentence);
  if (!value) return [];
  const needle = text(match);
  const at = findSpan(value, needle, Math.max(1, Number(occurrence) || 1), { latin, caseless });
  if (at < 0) return [{ value, hit: false }];
  const parts = [];
  if (at > 0) parts.push({ value: value.slice(0, at), hit: false });
  parts.push({ value: value.slice(at, at + needle.length), hit: true });
  if (at + needle.length < value.length) parts.push({ value: value.slice(at + needle.length), hit: false });
  return parts;
}

/* The legacy two-argument form the older screens call: the headword in the sentence, whole-word for
   Latin, case-insensitive. */
export function highlightExample(example, word) {
  const latin = !HAN.test(text(word));
  return highlightParts(example, { match: word, latin, caseless: latin });
}

/* ---- Pronunciation ---------------------------------------------------------------------------- */
/* Readings are only ever the word's own kind (D-17W, :8021 check): a Chinese word's reading is pinyin -
   Latin letters with tone marks or tone digits, spaces, apostrophes, middle dots, hyphens - never an IPA
   string (slashes, ɪ ː ə ˈ …), which a lookup run in another language can hand back ("/paɪn triː/" for
   松树); a Latin word's reading is never pinyin or Hanzi. A value of the wrong kind is dropped, and a
   Chinese word with no pinyin is drawn without a reading rather than with the wrong one. */
const PINYIN = /^[a-zA-ZüÜāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜĀÁǍÀĒÉĚÈĪÍǏÌŌÓǑÒŪÚǓÙńňǹḿ1-5\s'’·-]+$/;
const TONE_MARK = /[āáǎàēěèīíǐìōóǒòūúǔùǖǘǚǜ]/;

export function isPinyin(value) {
  const candidate = text(value);
  return Boolean(candidate) && PINYIN.test(candidate) && /[a-zA-Zü]/.test(candidate);
}

/* A Latin word's reading: not Hanzi, and not toned pinyin. */
export function isLatinReading(value) {
  const candidate = text(value);
  return Boolean(candidate) && !HAN.test(candidate) && !(TONE_MARK.test(candidate) && isPinyin(candidate));
}

function pronunciationOf(source, { lookup, seed, script }) {
  const pick = (values, accept) => values.map(text).find((value) => value && accept(value)) || '';
  const readings = list(source?.readings).map((item) => text(typeof item === 'object' ? item?.text : item)).filter(Boolean);
  const fallbacks = [text(source?.phonetic), text(source?.pronunciation), text(seed?.pronunciation)];
  if (script === 'hanzi') {
    const units = list(source?.orthography?.units);
    const fromUnits = units.length && units.every((unit) => isPinyin(unitReading(unit, 'pinyin')))
      ? units.map((unit) => unitReading(unit, 'pinyin')).join(' ')
      : '';
    const pinyin = pick([...readings, fromUnits, text(lookup?.pinyin), ...fallbacks], isPinyin);
    return { text: pinyin, ipa: [], pinyin };
  }
  const ipa = [];
  for (const item of list(source?.pronunciations)) {
    const value = text(typeof item === 'object' ? item?.text : item);
    if (value && isLatinReading(value) && !ipa.some((entry) => entry.text === value)) ipa.push({ region: lower(item?.region), text: value });
  }
  const first = ipa[0]?.text || pick([text(lookup?.ipa), ...readings, ...fallbacks], isLatinReading);
  return { text: first, ipa, pinyin: '' };
}

/* ---- Meaning ----------------------------------------------------------------------------------
   The sense's meaning in the support language leads (D-124); the learner's own note and another
   language's localization come next (vocabularyMeaning), then the lookup's meaning, then the seed's,
   then a definition. `definition` is the English definition line of an English word (the authored
   format's `meanings[].en` for EN), shown under the meaning when it says something else. */
/* Precedence (D-124 kept: a support-language localization always leads): 1 the entry's sense in the support
   language, 2 the learner's own note, 3 the lookup's meaning (asked for in the support language), 4 the seed's sense
   in the support language, 5 only then a meaning in another language, tagged with it, 6 a definition written in a
   language other than the word's own. */
function meaningOf(source, { supportLanguage, lookup, seed, language }) {
  const sense = vocabularyMeaning(source, supportLanguage);
  const inSupportLanguage = (found) => found?.text && (found.source === 'localization' || found.source === 'saved');
  if (inSupportLanguage(sense)) return sense;
  if (sense?.text && sense.source === 'note') return sense;
  const looked = text(lookup?.contextMeaning);
  if (looked) return { text: looked, language: '' };
  const seeded = vocabularyMeaning(seed, supportLanguage);
  if (inSupportLanguage(seeded)) return seeded;
  if (sense?.text) return sense;
  if (seeded?.text) return seeded;
  for (const entry of list(source?.detailed_definitions)) {
    const tagged = lower(entry?.language);
    if (text(entry?.text) && tagged && tagged !== language) return { text: text(entry.text), language: tagged };
  }
  return null;
}

/* The word's own-language definition ("A reddish metal." for copper, 一种常绿的树。 for 松树): the line
   under the meaning, tagged with its language when that is not the support language. When it is the
   only meaning an entry has, it is what the card shows - never "no meaning" (rule 40). */
function definitionOf(source, seed, language, meaningText) {
  const candidates = [
    ...list(source?.detailed_definitions),
    ...list(source?.short_meanings),
    ...list(source?.meanings),
    ...list(seed?.short_meanings),
  ];
  for (const entry of candidates) {
    const value = text(typeof entry === 'object' ? entry?.text : entry);
    const tagged = lower(entry?.language);
    if (value && (tagged === language || (!tagged && entry === source?.detailed_definitions?.[0])) && value !== meaningText) return { text: value, language };
  }
  const note = text(source?.definition);
  if (note && note !== meaningText) return { text: note, language: HAN.test(note) ? 'zh' : language };
  return null;
}

function englishOf(source, meaningText) {
  for (const entry of [...list(source?.short_meanings), ...list(source?.meanings)]) {
    const value = text(entry?.text);
    if (value && lower(entry?.language) === 'en' && value !== meaningText) return value;
  }
  return text(source?.support_translations?.en) !== meaningText ? text(source?.support_translations?.en) : '';
}

/* ---- Typed usage notes (D-178) ----------------------------------------------------------------
   A raw entry carries `usage_notes` as typed items; a catalogue card has already grouped them
   (`collocations`, `related`, `classifiers`, `explanation_artifacts`, `common_mistakes`, and
   `usage_notes` as plain strings). Both read the same here. An untyped item is `usage`. */
function notesOf(source) {
  const typed = [];
  for (const item of list(source?.usage_notes)) {
    if (typeof item === 'string') typed.push({ type: 'usage', text: item });
    else if (item && text(item.text)) typed.push({ ...item, type: text(item.type) || 'usage' });
  }
  for (const item of list(source?.collocations)) {
    const value = typeof item === 'string' ? item : item?.text;
    if (text(value)) typed.push({ ...(typeof item === 'object' ? item : {}), type: 'collocation', text: text(value) });
  }
  for (const item of list(source?.related)) if (item && text(item.text)) typed.push({ ...item, type: text(item.type) || 'related' });
  for (const item of list(source?.classifiers)) if (item && text(item.text)) typed.push({ ...item, type: 'classifier' });
  for (const item of list(source?.common_mistakes)) if (item && text(item.text)) typed.push({ ...item, type: 'common_mistake' });
  for (const item of list(source?.explanation_artifacts)) {
    if (item?.kind === 'mnemonic' && text(item.text)) typed.push({ type: 'memory_tip', text: text(item.text), language: item.language });
  }
  const seen = new Set();
  return typed.filter((item) => {
    const key = `${item.type}|${text(item.text)}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function ofType(notes, type) {
  return notes.filter((note) => note.type === type);
}

/* A note written for learners of one support language (a memory tip, a usage note) shows only to
   them; an untagged note is shown as written. */
function supportNotes(notes, type, supportLanguage) {
  return ofType(notes, type)
    .filter((note) => !text(note.language) || lower(note.language) === lower(supportLanguage) || type === 'usage' || type === 'common_mistake')
    .map((note) => ({ text: text(note.text), language: lower(note.language) }));
}

/* ---- Chinese character units ------------------------------------------------------------------ */
function unitReading(unit, notation) {
  const found = list(unit?.readings).find((reading) => lower(reading?.notation) === notation);
  return text(found?.value);
}

function unitsOf(source, supportLanguage) {
  const units = list(source?.orthography?.units);
  return units
    .filter((unit) => text(unit?.surface))
    .map((unit) => {
      const facts = unit.facts || {};
      const radical = facts.radical?.value;
      const radicalModel = radical && text(radical.surface)
        ? {
            surface: text(radical.surface),
            reading: text(radical.reading),
            name: inSupport(radical.name, supportLanguage)?.text || '',
            gloss: inSupport(radical.gloss, supportLanguage)?.text || '',
          }
        : null;
      return {
        hanzi: text(unit.surface),
        pinyin: unitReading(unit, 'pinyin'),
        hanViet: unitReading(unit, 'han_viet'),
        strokes: Number(facts.stroke_count?.value) || 0,
        radical: radicalModel,
        components: list(facts.components?.value).map((part) => text(part?.surface)).filter(Boolean),
      };
    });
}

/* ---- Examples --------------------------------------------------------------------------------- */
function examplesOf(source, { language, script, word, supportLanguage }) {
  const latin = script !== 'hanzi';
  const out = [];
  for (const raw of list(source?.examples)) {
    const sentence = text(typeof raw === 'object' ? raw?.text : raw);
    if (!sentence) continue;
    const exampleLanguage = lower(raw?.language);
    if (exampleLanguage && language && exampleLanguage !== language) continue;
    const highlight = raw?.highlight && text(raw.highlight.match) ? raw.highlight : null;
    const parts = highlight
      ? highlightParts(sentence, { match: highlight.match, occurrence: highlight.occurrence, latin })
      : highlightParts(sentence, { match: word, latin, caseless: latin });
    const reading = text(raw?.reading);
    const readingHighlight = raw?.reading_highlight && text(raw.reading_highlight.match) ? raw.reading_highlight : null;
    // The pinyin span is lit only when it can be found; never the whole line, never guessed from the Hanzi.
    const readingParts = reading
      ? (readingHighlight ? highlightParts(reading, { match: readingHighlight.match, occurrence: readingHighlight.occurrence, latin: true }) : [{ value: reading, hit: false }])
      : [];
    out.push({
      text: sentence,
      parts,
      reading,
      readingParts,
      label: inSupport(raw?.label, supportLanguage)?.text || '',
      translation: inSupport(raw?.translation, supportLanguage)?.text || '',
      explanation: inSupport(raw?.explanation, supportLanguage)?.text || '',
    });
  }
  return out;
}

function illustrationOf(source) {
  const art = source?.illustration || source?.provenance?.illustration;
  // Only an uploaded image with a real address is drawn; a library reference with no asset behind it,
  // `kind: none`, or nothing at all draws no frame (D-178 point 9).
  if (!art || art.kind !== 'upload' || !/^(https?:\/\/|\/)/.test(text(art.ref))) return null;
  return { src: text(art.ref), alt: text(art.alt_vi) };
}

/* ---- The model -------------------------------------------------------------------------------- */
export function toVocabularyModel(source, { word = '', supportLanguage = '', lookup = null, seed = null } = {}) {
  const entry = source || {};
  const resolvedLookup = lookup?.available === false ? null : lookup;
  const headword = text(resolvedLookup?.headword) || text(word) || text(entry.word) || text(entry.term) || text(entry.headword);
  const declared = lower(entry.language_code || entry.identity?.language || seed?.identity?.language);
  const script = resolvedLookup?.script === 'hanzi' ? 'hanzi' : scriptOf(headword, declared);
  const language = script === 'hanzi' ? 'zh' : (declared && !declared.startsWith('zh') ? declared : 'en');
  const pronunciation = pronunciationOf(entry, { lookup: resolvedLookup, seed, script });
  const meaning = meaningOf(entry, { supportLanguage, lookup: resolvedLookup, seed, language });
  const meaningText = text(meaning?.text);
  const localized = text(localizedMeaning(entry, supportLanguage)?.text);
  const definition = definitionOf(entry, seed, language, meaningText);
  const notes = notesOf(entry);
  const units = script === 'hanzi' ? unitsOf(entry, supportLanguage) : [];
  const etymology = inSupport(entry.provenance?.etymology, supportLanguage);
  return {
    word: headword,
    script,
    language,
    pos: text(resolvedLookup?.partOfSpeech) || text(entry.part_of_speech),
    level: text(entry.level),
    framework: text(entry.framework),
    // Where the level comes from ("Oxford 5000"), as the entry records it.
    levelSource: text(entry.provenance?.level_source),
    pronunciation,
    meaning: meaningText ? { text: meaningText, language: lower(meaning.language) === lower(supportLanguage) ? '' : lower(meaning.language) } : null,
    support: localized && localized !== meaningText ? localized : '',
    definition: definition?.text || '',
    // The reference's Chinese card gives the meaning in English under the support-language one ("forest"):
    // the entry's English localization, for a word that is not English and a learner whose support is not.
    english: language !== 'en' && lower(supportLanguage) !== 'en' ? englishOf(entry, meaningText) : '',
    definitionLanguage: definition?.text ? definition.language : '',
    examples: examplesOf(entry, { language, script, word: headword, supportLanguage }),
    collocations: ofType(notes, 'collocation').map((note) => text(note.text)),
    synonyms: ofType(notes, 'synonym').map((note) => text(note.text)),
    antonyms: ofType(notes, 'antonym').map((note) => text(note.text)),
    wordFamily: ofType(notes, 'word_family').map((note) => ({ word: text(note.text), pos: text(note.pos) })),
    related: ofType(notes, 'related').map((note) => ({ word: text(note.text), reading: text(note.reading), gloss: inSupport(note.gloss, supportLanguage)?.text || '' })),
    classifiers: ofType(notes, 'classifier').map((note) => ({ mw: text(note.text), reading: text(note.reading), phrase: text(note.phrase), phraseReading: text(note.phrase_reading) })),
    memoryTip: supportNotes(notes, 'memory_tip', supportLanguage)[0] || null,
    usage: supportNotes(notes, 'usage', supportLanguage).map((note) => note.text),
    commonMistakes: supportNotes(notes, 'common_mistake', supportLanguage).map((note) => note.text),
    etymology: etymology?.text ? etymology.text : '',
    units,
    hanViet: units.every((unit) => unit.hanViet) && units.length ? units.map((unit) => unit.hanViet).join(' ') : '',
    illustration: illustrationOf(entry),
    audioUrl: text(resolvedLookup?.audioUrl),
  };
}

/* The learner decorator: what a saved record adds beside the content, for a screen that has one.
   `null` item means "not saved" - never a guessed schedule. */
export function learnerState(item, { saved = undefined } = {}) {
  if (!item) return { saved: Boolean(saved), hasSchedule: false, filled: 0, stageLabel: '', due: null, context: '' };
  return {
    saved: saved === undefined ? true : Boolean(saved),
    hasSchedule: true,
    filled: Math.max(0, Math.min(4, Number(item.review_stage) || 0)),
    stageLabel: text(item.stage_label),
    due: dueInfo(item),
    // The sentence the learner met the word in: theirs, not the entry's.
    context: text(item.source_fragment),
  };
}

/* What review-front may show: nothing that answers the card (D-17W). */
export function frontFields(model) {
  return {
    word: model.word,
    script: model.script,
    language: model.language,
    pronunciation: model.pronunciation,
    pos: model.pos,
    level: model.level,
  };
}

/* The save payload (`POST /api/library/vocabulary`) from what the card shows. */
export function savePayloadOf(model, sourceKind = 'dictionary') {
  return {
    word: text(model?.word),
    phonetic: text(model?.pronunciation?.text),
    part_of_speech: text(model?.pos),
    definition: text(model?.meaning?.text),
    source_kind: sourceKind,
  };
}
