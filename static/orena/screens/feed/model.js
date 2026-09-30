/* Vocabulary Daily Feed's pure data mapping (frame 36, D-091). `GET /api/vocabulary/feed`
   (day-seeded, excludes words the learner already saved - `writing_coach/vocabulary_feed.py`)
   answers Vocabulary Card entries, the same shape `GET /api/vocabulary/library/collections/{id}`
   already gives Collection Detail (`vocabulary_card_from_catalog_entry()`): `{identity:{language,
   normalized}, headword, meanings:[{language,text}], examples:[{language,text}], pronunciation?,
   part_of_speech?, level?}`. This screen reuses `screens/collection/model.js#supportMeaning` and
   `screens/word/model.js#highlightExample` rather than re-deriving them.

   Rule 40: a feed candidate was never saved, so it carries no schedule/mastery at all - the front
   and back faces draw no mastery meter, stage or due line (the same `hasSchedule`-gated omission
   `mapWordCard` already establishes for an unsaved word). The frame's front-card photo is a
   2-image stock fallback with no real per-word source (E4 §3 "Data the backend must provide");
   VocabularyCard carries no image field at all, so this screen draws no image region - recorded as
   a deviation in the surface report, not a silent invention. */
import { supportMeaning } from '../collection/model.js';
import { highlightExample } from '../word/model.js';

const HAN = /[㐀-鿿]/;

function text(value) {
  return String(value ?? '').trim();
}

export function cardScript(entry) {
  const headword = text(entry?.headword);
  return entry?.identity?.language === 'zh' || HAN.test(headword) ? 'hanzi' : 'latin';
}

/* The one authored example a catalogue entry carries for its own language (Collection Detail's
   word rows draw no example at all; the Daily Feed's flip-card back does, so this is new, not a
   duplicate of that screen's own mapping). */
export function primaryExample(examples) {
  const list = Array.isArray(examples) ? examples : [];
  return text(list[0]?.text);
}

export function mapFeedCard(entry, support = '') {
  const source = entry || {};
  const headword = text(source.headword);
  const script = cardScript(source);
  const meaning = supportMeaning(source, support);
  const example = primaryExample(source.examples);
  const level = text(source.level);
  return {
    word: headword,
    script,
    ipa: text(source.pronunciation),
    pos: text(source.part_of_speech),
    hasLevel: Boolean(level),
    level,
    meaning,
    hasMeaning: Boolean(meaning),
    hasExample: Boolean(example),
    exampleParts: highlightExample(example, headword),
  };
}

export function mapFeedCards(payload, support = '') {
  const items = Array.isArray(payload?.items) ? payload.items : [];
  return items.map((entry) => mapFeedCard(entry, support)).filter((card) => card.word);
}

/* "Keep" from the feed (`app.py`'s own comment: reuses POST /api/library/vocabulary with
   source_kind="feed" - no new save endpoint). */
export function savePayload(card) {
  return {
    word: text(card?.word),
    phonetic: text(card?.ipa),
    part_of_speech: text(card?.pos),
    definition: text(card?.meaning),
    source_kind: 'feed',
  };
}
