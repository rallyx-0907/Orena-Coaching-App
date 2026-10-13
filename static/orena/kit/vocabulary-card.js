/* VocabularyCard (D-178, D-179): the one vocabulary card, drawn from the model
   `product/vocabulary-card.js#toVocabularyModel` makes.

   Provenance (UI provenance gate). LAYOUT and INFORMATION: the human's design reference for this
   component, the Claude Design canvas "Flashcard từ vựng Anh – Trung" (claude.ai/artifact/
   9wmYKVJVn8cBuX8ButSryF): artboard `Main.dc.html` (English, "resilient") and `Chinese.dc.html` (Chinese,
   "森林") - a two-face card, the front with the word and its facts, the back with the examples, turned by
   "See examples ->" / "<- Front". LOOK (D-180, human 2026-10-12): the same design, now pinned in
   docs/design/vocab-card/ - its own palette as card-scoped tokens (`--vcard-*`, kit/tokens.css; light "watercolor
   paper", dark "night violet", the Chinese seal), its shapes (the English line border and pill, the Chinese paper and
   gold ruled frame, the seal tag and radical box), its highlights and buttons, and its two line drawings as library
   art for the samples (kit/vocabulary-art.js); local fonts only, the kit's focus ring (AA). Adaptations, each recorded
   in D-179 / D-180 and UI_BACKEND_GAPS "Vocabulary card":
   the play and save discs sit in a quiet action row under the reading (the design draws neither; the top row stays
   level/source left, part of speech right, as drawn - D-180 point 8); collocations are chips; a section with no data
   is left out. Every tag, chip and accent of the CONTENT is `--vcard-*` (no kit `o-tag`); every BUTTON keeps the app's
   kit design and tokens - the turn actions are `o-btn`, the discs the app's icon-button colours (the human,
   2026-10-12: the flashcard skin is the content only).

   Faces, top to bottom as the reference draws them:
   - EN front: level tag + source; part of speech (its English name · the localized name); the headword;
     the UK and US IPA rows; "Meaning" (support-language meaning, the English definition); "Word family";
     "Synonyms / antonyms" (≈ / ≠); "See examples ->".
   - EN back: the headword and "Examples & usage"; numbered examples (label, sentence with its highlight,
     translation, explanation); "Structure"; "Common collocations"; "Memory tip"; "<- Front".
   - ZH front: HSK tag; part of speech (中文名 · localized); the Hanzi with each character's pinyin above
     it, Hán Việt beside; "Meaning"; "Radical" (the radical, its pinyin and name, then each character =
     its components · strokes); "Measure word"; "Related words"; "See examples ->".
   - ZH back: the Hanzi and pinyin and "Examples & usage"; numbered examples (label, sentence with the
     Hanzi span, pinyin with the matching span, translation, note); "Memory tip"; "<- Front".

   Modes: `detail` and `feed` draw the two faces, starting on the front, with Save. `review-front` is the
   recall face (D-179 point 2): the word or Hanzi, its reading, part of speech and level, play - nothing
   that answers. `review-back` is the two faces, with no bookmark: Save and
   remove belong to Word Detail and the Feed (D-179 point 4). The grades are the screen's, outside the card.

   Each face is a body that scrolls inside itself and a foot that holds the turn action, so the action
   stays in view when a long entry fills a phone (rule 49). Learner state (`learner`, from
   `learnerState`) only sets the save disc and the mastery footer; the content never depends on it. */
import { html, raw, cls } from './html.js';
import { icon } from './icons.js';
import { langAttr } from './lang.js';
import { masteryBars } from './components.js';
import { libraryArt } from './vocabulary-art.js';
import { registeredCopy } from '../copy/index.js';
import { t } from '../copy/vocabulary-card.js';

export const CARD_MODES = Object.freeze(['detail', 'feed', 'review-front', 'review-back']);

const POS_KEY = Object.freeze({
  noun: 'posNoun', verb: 'posVerb', adjective: 'posAdjective', adverb: 'posAdverb', pronoun: 'posPronoun',
  determiner: 'posDeterminer', preposition: 'posPreposition', conjunction: 'posConjunction',
  numeral: 'posNumeral', particle: 'posParticle', auxiliary: 'posAuxiliary', interjection: 'posInterjection',
  classifier: 'posClassifier', measure_word: 'posMeasureWord', phrase: 'posPhrase', idiom: 'posIdiom',
  proper_noun: 'posProperNoun', other: 'posOther',
});
const ZH_NUMERALS = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十'];

function posKeys(value) {
  const parts = String(value ?? '').trim().split(/\s*[/,;|]\s*/).filter(Boolean);
  const keys = parts.map((part) => POS_KEY[part.toLowerCase().replace(/\s+/g, '_')]);
  return parts.length && keys.every(Boolean) ? keys : null;
}

/* A part of speech in the interface language when it is a known code; otherwise as the source wrote it,
   marked as English content metadata. */
export function posLabel(value) {
  const keys = posKeys(value);
  if (keys) return { text: keys.map((key) => t(key)).join(t('posJoin')), known: true };
  return { text: String(value ?? '').trim(), known: false };
}

/* The part of speech's name in the word's own language - "adjective", "名词" - the reference's first half
   of the part-of-speech line. Read from this table's own pack for that language, not the interface's. */
export function posNative(value, language) {
  const keys = posKeys(value);
  if (!keys) return '';
  const pack = registeredCopy().get('vocabularyCard')?.packs?.[language === 'zh' ? 'zh' : 'en'] || {};
  return keys.map((key) => pack[key] || '').filter(Boolean).join(pack.posJoin || ' / ').toLowerCase();
}

/* How long the headword's longest unbreakable run is, so its type can shrink to fit the width instead of
   breaking inside a word (CSS `--len`). Han has no spaces: the whole word is one run. */
export function headwordRun(word, script) {
  const value = String(word ?? '').trim();
  if (script === 'hanzi') return Math.max(1, [...value].length);
  return Math.max(1, ...value.split(/\s+/).map((part) => [...part].length));
}

function parts(list) {
  return list.map((part) => (part.hit ? html`<mark class="c-vcard__hit">${part.value}</mark>` : part.value));
}

function section(titleKey, body, extra = '') {
  if (!body || !String(body)) return '';
  return html`<section class="${cls('c-vcard__section', extra)}" data-section="${titleKey}"><h3 class="c-vcard__label">${t(titleKey)}</h3>${body}</section>`;
}

function playDisc(region = '') {
  return html`<button type="button" class="c-vcard__disc c-vcard__disc--play" data-play${region ? raw(` data-region="${region}"`) : ''} aria-label="${t('playWord')}">${raw(icon('volume-2', { size: 15 }))}</button>`;
}

function saveDisc(learner) {
  return html`<button type="button" class="${cls('c-vcard__disc', learner?.saved && 'is-saved')}" data-save aria-pressed="${learner?.saved ? 'true' : 'false'}" aria-label="${t(learner?.saved ? 'unsaveWord' : 'saveWord')}">${raw(icon('bookmark-check', { size: 15 }))}</button>`;
}

function headword(model, size = '') {
  const lang = langAttr(model.language);
  const run = headwordRun(model.word, model.script);
  if (model.script !== 'hanzi') return html`<h2 class="${cls('c-vcard__word', size)}" lang="${lang}" style="--len:${run}">${model.word}</h2>`;
  const units = model.units.length ? model.units : null;
  if (!units) {
    // No character units: the word's reading above it, whole.
    return html`<h2 class="${cls('c-vcard__word c-vcard__word--han', size)}" lang="${lang}" style="--len:${run}">${model.pronunciation.pinyin ? html`<ruby>${model.word}<rt>${model.pronunciation.pinyin}</rt></ruby>` : model.word}</h2>`;
  }
  return html`<h2 class="${cls('c-vcard__word c-vcard__word--han', size)}" lang="${lang}" style="--len:${run}">${units.map((unit) => html`<ruby>${unit.hanzi}${unit.pinyin ? html`<rt>${unit.pinyin}</rt>` : ''}</ruby>`)}</h2>`;
}

function posLine(model) {
  if (!model.pos) return '';
  const native = posNative(model.pos, model.language);
  const local = posLabel(model.pos);
  const localText = local.text.toLowerCase();
  return html`<div class="c-vcard__pos">${native && native !== localText ? html`<span lang="${langAttr(model.language)}">${native}</span> · ` : ''}<span${local.known ? '' : raw(` lang="${langAttr('en')}"`)}>${local.text}</span></div>`;
}

/* "HSK 4" for an HSK level stored as its number; a level that already names its scale stays as it is. */
export function levelLabel(model) {
  const level = String(model.level || '').trim();
  if (/^hsk/i.test(level) || !/^hsk/i.test(String(model.framework || ''))) return level;
  return `HSK ${level}`;
}

/* The top row (the human, 2026-10-13): the level tag, on the English card its source, and the part of speech beside
   them on the left; the word's actions - play, and Save on the cards a word is met on - alone on the right, smaller,
   so the illustration takes the room their own row had. */
function topRow(model, save) {
  const tags = [
    model.level ? html`<span class="c-vcard__level">${levelLabel(model)}</span>` : '',
    model.script !== 'hanzi' && model.levelSource ? html`<span class="c-vcard__source">${model.levelSource}</span>` : '',
    posLine(model),
  ];
  return html`<div class="c-vcard__top"><div class="c-vcard__tags">${tags}</div><div class="c-vcard__top-end"><div class="c-vcard__actions">${playDisc()}${save || ''}</div></div></div>`;
}

/* The meaning panel. Still being looked up: the kit's skeleton bones, never "no meaning". The word's
   own-language definition is the line under the meaning, or the only line, tagged with its language. */
function meaningSection(model, { meaningLabel, pending }) {
  // The card draws the language tag itself (card colours); the screen only names the language, in its own words.
  const tag = (language) => {
    const label = language && meaningLabel ? meaningLabel(language) : '';
    return label ? html` <span class="c-vcard__lang">${label}</span>` : '';
  };
  let body;
  if (!model.meaning && !model.definition && !model.english) {
    body = pending
      ? html`<div class="c-vcard__meaning" aria-busy="true" data-meaning-pending><div class="o-bone o-bone--strong" style="height:12px;width:55%"></div><div class="o-bone" style="height:10px;width:32%"></div></div>`
      : html`<div class="c-vcard__meaning"><p class="c-vcard__definition" data-no-meaning>${t('meaningUnavailable')}</p></div>`;
  } else {
    body = html`<div class="c-vcard__meaning">
      ${model.meaning ? html`<p class="c-vcard__meaning-text">${model.meaning.text}${tag(model.meaning.language)}</p>` : ''}
      ${model.support ? html`<p class="c-vcard__definition">${model.support}</p>` : ''}
      ${model.english ? html`<p class="c-vcard__definition" lang="en">${model.english}</p>` : ''}
      ${model.definition ? html`<p class="${model.meaning ? 'c-vcard__definition' : 'c-vcard__meaning-text'}"><span lang="${langAttr(model.definitionLanguage)}">${model.definition}</span>${tag(model.definitionLanguage)}</p>` : ''}
    </div>`;
  }
  return section('sectionMeaning', body);
}

/* The illustration frame, only when there is an image: an upload, or a library drawing the kit knows by its `ref`
   (kit/vocabulary-art.js). EN: the design's 180px rounded box on the alternate surface; ZH: the 150px band between two
   rules. Nothing at all otherwise. */
function illustration(model) {
  const art = model.illustration;
  if (!art) return '';
  const label = art.alt || model.word;
  if (art.kind === 'upload') return html`<figure class="c-vcard__art"><img src="${art.src}" alt="${label}" loading="lazy" /></figure>`;
  const drawing = libraryArt(art.ref);
  return drawing ? html`<figure class="c-vcard__art" role="img" aria-label="${label}" data-art="${art.ref}">${raw(drawing)}</figure>` : '';
}

/* ---- English front ---- */
function ipaRows(model) {
  const rows = model.pronunciation.ipa;
  if (!rows.length) return '';
  return html`<div class="c-vcard__ipa-rows">${rows.map((row) => html`<span class="c-vcard__ipa" data-region="${row.region}">${row.region === 'uk' || row.region === 'us' ? html`<b>${t(row.region === 'uk' ? 'regionUk' : 'regionUs')}</b>` : ''}<span>${row.text}</span></span>`)}</div>`;
}

function enFront(model, ctx) {
  const lang = langAttr(model.language);
  const hasIpaRows = model.pronunciation.ipa.length > 0;
  const family = model.wordFamily.length
    ? html`<div class="c-vcard__lines" lang="${lang}">${model.wordFamily.map((item) => html`<div>${item.word}${item.pos ? html` <span class="c-vcard__muted">${item.pos}</span>` : ''}</div>`)}</div>`
    : '';
  const synAnt = model.synonyms.length || model.antonyms.length
    ? html`<div class="c-vcard__lines" lang="${lang}">${model.synonyms.length ? html`<div>≈ ${model.synonyms.join(', ')}</div>` : ''}${model.antonyms.length ? html`<div>≠ ${model.antonyms.join(', ')}</div>` : ''}</div>`
    : '';
  const pair = [section('sectionWordFamily', family), section('sectionSynAnt', synAnt)].filter((cell) => String(cell));
  return html`
    <div class="c-vcard__ident">
      ${headword(model)}
      ${hasIpaRows ? ipaRows(model) : (model.pronunciation.text ? html`<div class="c-vcard__ipa"><span>${model.pronunciation.text}</span></div>` : '')}
    </div>
    ${illustration(model)}
    ${meaningSection(model, ctx)}
    ${pair.length ? html`<div class="c-vcard__pair">${pair}</div>` : ''}`;
}

/* ---- Chinese front ---- */
function radicalSection(model) {
  const withRadical = model.units.filter((unit) => unit.radical);
  if (!withRadical.length) return '';
  const lang = langAttr(model.language);
  // One box per distinct radical; a word whose characters share it (森林 -> 木) shows it once (docs/vocab README).
  const groups = [];
  for (const unit of withRadical) {
    const group = groups.find((item) => item.radical.surface === unit.radical.surface);
    if (group) group.units.push(unit);
    else groups.push({ radical: unit.radical, units: [unit] });
  }
  return section('sectionRadical', html`${groups.map((group) => html`<div class="c-vcard__radical">
    <span class="c-vcard__radical-glyph" lang="${lang}">${group.radical.surface}</span>
    <div class="c-vcard__lines">
      <div>${group.radical.reading ? html`<b>${group.radical.reading}</b>` : ''}${group.radical.name ? html` · ${group.radical.name}` : ''}${group.radical.gloss ? html` (${group.radical.gloss})` : ''}</div>
      ${group.units.map((unit) => html`<div><span lang="${lang}">${unit.hanzi}${unit.components.length ? ` = ${unit.components.join(' + ')}` : ''}</span>${unit.strokes ? html` · ${t.plural('strokeCount', unit.strokes)}` : ''}</div>`)}
    </div>
  </div>`)}`);
}

/* Meaning and Radical side by side (the human, 2026-10-13), in the columns of the Measure word / Related words pair
   below, so Radical lines up with Related words and a long meaning wraps in its own column. */
function lead(...cells) {
  const present = cells.filter((cell) => String(cell));
  return present.length ? html`<div class="c-vcard__lead">${present}</div>` : '';
}

function zhFront(model, ctx) {
  const lang = langAttr(model.language);
  const measure = model.classifiers.length
    ? html`<div class="c-vcard__lines">${model.classifiers.map((item) => html`<div><span lang="${lang}">${item.phrase || item.mw}</span>${item.phraseReading || item.reading ? html`<br /><span class="c-vcard__muted">${item.phraseReading || item.reading}</span>` : ''}</div>`)}</div>`
    : '';
  const related = model.related.length
    ? html`<div class="c-vcard__lines">${model.related.map((item) => html`<div><span lang="${lang}">${item.word}</span>${item.reading ? html` <span class="c-vcard__muted">${item.reading}</span>` : ''}${item.gloss ? html` · ${item.gloss}` : ''}</div>`)}</div>`
    : '';
  const pair = [section('sectionMeasureWord', measure), section('sectionRelated', related)].filter((cell) => String(cell));
  return html`
    <div class="c-vcard__hanrow">
      ${headword(model)}
      ${model.hanViet ? html`<div class="c-vcard__hanviet"><span class="c-vcard__label">${t('hanVietLabel')}</span><span>${model.hanViet}</span></div>` : ''}
    </div>
    ${illustration(model)}
    ${lead(meaningSection(model, ctx), radicalSection(model))}
    ${pair.length ? html`<div class="c-vcard__pair">${pair}</div>` : ''}`;
}

/* ---- Backs ---- */
function exampleNumber(index, model) {
  return model.script === 'hanzi' ? ZH_NUMERALS[index] || String(index + 1) : String(index + 1).padStart(2, '0');
}

function examplePanel(example, index, model) {
  const lang = langAttr(model.language);
  return html`<li class="c-vcard__example">
    <div class="c-vcard__example-label">${exampleNumber(index, model)}${example.label ? ` · ${example.label}` : ''}</div>
    <p class="c-vcard__example-text" lang="${lang}">${parts(example.parts)}</p>
    ${example.reading ? html`<p class="c-vcard__example-reading" lang="zh-Latn">${parts(example.readingParts)}</p>` : ''}
    ${example.translation ? html`<p class="c-vcard__example-translation">${example.translation}</p>` : ''}
    ${example.explanation ? html`<p class="c-vcard__example-note">${example.explanation}</p>` : ''}
  </li>`;
}

function back(model, { learner, mode }) {
  const lang = langAttr(model.language);
  const examples = mode === 'feed' ? model.examples.slice(0, 2) : model.examples;
  const context = !examples.length && learner?.context
    ? html`<li class="c-vcard__example"><p class="c-vcard__example-text" lang="${lang}">${parts(learner.contextParts || [{ value: learner.context, hit: false }])}</p></li>`
    : '';
  const head = html`<div class="c-vcard__backhead c-vcard__head">
    ${model.script === 'hanzi'
      ? html`<span class="c-vcard__backword"><span lang="${lang}">${model.word}</span> <span class="c-vcard__muted">${model.pronunciation.pinyin}</span></span>`
      : html`<span class="c-vcard__backword" lang="${lang}">${model.word}</span>`}
    <span class="c-vcard__muted c-vcard__backtitle">${t('sectionExamplesUsage')}</span>
  </div>`;
  const list = examples.length || context
    ? html`<ol class="c-vcard__examples">${examples.map((example, index) => examplePanel(example, index, model))}${context}</ol>`
    : '';
  const notes = [
    model.script !== 'hanzi' ? section('sectionStructure', model.usage.length ? html`<div class="c-vcard__lines">${model.usage.map((note) => html`<div>${note}</div>`)}</div>` : '') : '',
    model.collocations.length ? section('sectionCollocations', html`<div class="c-vcard__chips" lang="${lang}">${model.collocations.map((item) => html`<span class="c-vcard__chip">${item}</span>`)}</div>`) : '',
    model.memoryTip ? section('sectionMemoryTip', html`<p class="c-vcard__note">${model.memoryTip.text}</p>`) : '',
    model.script === 'hanzi' && model.usage.length ? section('sectionStructure', html`<div class="c-vcard__lines">${model.usage.map((note) => html`<div>${note}</div>`)}</div>`) : '',
    model.commonMistakes.length ? section('sectionCommonMistake', html`<div class="c-vcard__lines">${model.commonMistakes.map((note) => html`<div>${note}</div>`)}</div>`) : '',
    model.etymology ? section('sectionEtymology', html`<p class="c-vcard__note">${model.etymology}</p>`) : '',
  ].filter((cell) => String(cell));
  return { head, body: html`${list}${notes.length ? html`<div class="c-vcard__pair c-vcard__pair--back">${notes}</div>` : ''}` };
}

function footer(learner, labels) {
  if (!learner?.hasSchedule) return '';
  return html`<div class="c-vcard__mastery"><span class="c-vcard__bars">${masteryBars({ filled: learner.filled, total: 4, color: 'var(--vcard-accent)', emptyColor: 'var(--vcard-line)' })}</span>${labels?.stage ? html`<span class="c-vcard__stage">${labels.stage}</span>` : ''}${labels?.due ? html`<span class="c-vcard__due">· ${labels.due}</span>` : ''}</div>`;
}

let cardSeq = 0;

/* `slots`: `strokes` (the Chinese stroke-order block, a screen's), `footer` ({ stage, due } in the
   screen's words), `meaningLabel(language)` (the name of a meaning's language when it is not the support language,
   or ''), `meaningPending` (the lookup is still out). */
export function vocabularyCard(model, { mode = 'detail', learner = null, slots = {} } = {}) {
  if (!CARD_MODES.includes(mode)) throw new Error(`VocabularyCard: unknown mode ${mode}`);
  const han = model.script === 'hanzi';
  if (mode === 'review-front') {
    const reading = han ? model.pronunciation.pinyin : model.pronunciation.text;
    return html`<article class="c-vcard c-vcard--review-front${cls(han && ' c-vcard--han')}" data-vcard-mode="review-front">
      <div class="c-vcard__recall">
        <h2 class="${cls('c-vcard__word', han && 'c-vcard__word--han')}" lang="${langAttr(model.language)}" style="--len:${headwordRun(model.word, model.script)}">${model.word}</h2>
        <div class="c-vcard__recall-meta">${posLine(model)}${reading ? html`<span class="c-vcard__ipa"><span>${reading}</span></span>` : ''}${model.level ? html`<span class="c-vcard__level">${levelLabel(model)}</span>` : ''}${playDisc()}</div>
      </div>
    </article>`;
  }
  cardSeq += 1;
  const id = `vcard-${cardSeq}`;
  // Save on the cards a word is met on; in Review, where every word is already saved, the bookmark is only a
  // remove toggle, drawn saved (D-179, the exception to "Save is not Review"; the pinned frame draws it).
  const save = mode === 'detail' || mode === 'feed' ? saveDisc(learner) : '';
  const ctx = { meaningLabel: slots.meaningLabel, pending: slots.meaningPending };
  const front = han ? zhFront(model, ctx) : enFront(model, ctx);
  // Each face: a head that stays (the design's top row / the back's title line), a body that alone scrolls when the
  // face holds more than fits, and a foot with the turn action (rule 49).
  const frontHead = topRow(model, save);
  const backFace = back(model, { learner, mode });
  return html`<article class="${cls('c-vcard', `c-vcard--${mode}`, han && 'c-vcard--han')}" data-vcard-mode="${mode}" data-face="front">
    <div class="c-vcard__face c-vcard__face--front" id="${id}-front">
      <div class="c-vcard__head">${frontHead}</div>
      <div class="c-vcard__body">${front}${slots.strokes || ''}</div>
      <div class="c-vcard__foot">
        ${footer(learner, slots.footer)}
        <button type="button" class="o-btn o-btn--primary c-vcard__turn" data-vcard-turn="back" aria-controls="${id}-back">${t('seeExamples')}</button>
      </div>
    </div>
    <div class="c-vcard__face c-vcard__face--back" id="${id}-back" hidden>
      ${backFace.head}
      <div class="c-vcard__body">${backFace.body}</div>
      <div class="c-vcard__foot c-vcard__foot--back">
        <button type="button" class="o-btn o-btn--secondary c-vcard__turn" data-vcard-turn="front" aria-controls="${id}-front">${t('backToFront')}</button>
      </div>
    </div>
  </article>`;
}

/* Fits each card to the height it has (rule 49, CLAUDE.md 6b), and its face to the card: a face NEVER scrolls inside
   (the human, 2026-10-12, D-180). Two steps.
   1. The box. `viewport: true` (Word Detail, a browsing page): the card's max-height is the visible height of its
      scrolling column below the card's top, above the phone bar and its orb, so on arrival the whole card - actions
      included - is in view. Otherwise the card already sits in a bounded slot (Review's face, the feed's card).
      `data-fit` records whether the card had less than SHORT_CARD_PX (information only).
   2. Contain. The composition is already scaled to the card's WIDTH by the CSS (cqi, from the 520px artboard). When
      the face's natural height at that scale is taller than the box, the card scales it to the box's HEIGHT too:
      s = min(widthScale, heightScale). Spacing and the illustration shrink first (--vc-ks), the type last (--vc-kt),
      down to the hard floors kit/vocabulary-card.css sets (body / meaning / example 11px, labels and tags 9.5px,
      pinyin and IPA 10px). Every element stays - the illustration included; the buttons keep 44px+. The achieved
      height scale is recorded as --vcard-s and data-vcard-s. */
export const SHORT_CARD_PX = 620;
/* How far each knob may go, in the order they move (the human, 2026-10-12):
   1. spacing (--vc-ks) to CONTAIN_SPACE_MIN, the illustration (--vc-ka) following it but held at CONTAIN_ART_MIN of
      its width-scaled height;
   2. then the type (--vc-kt) to CONTAIN_TYPE_MIN, the illustration shrinking with it in proportion (ka = ART_MIN x kt);
   3. last, spacing alone again, to CONTAIN_SPACE_FLOOR.
   The type's own floors (kit/vocabulary-card.css) bind before CONTAIN_TYPE_MIN on every line of reading text. */
export const CONTAIN_SPACE_MIN = 0.5;
export const CONTAIN_ART_MIN = 0.6;
export const CONTAIN_TYPE_MIN = 0.55;
export const CONTAIN_SPACE_FLOOR = 0.3;
/* The face is fitted to the box less this, so a sub-pixel or a font's rounding never leaves it a hair over. */
const CONTAIN_MARGIN = 1;
const CONTAIN_STEPS = 16;

function phaseOf({ ks, kt }) {
  if (ks > CONTAIN_SPACE_MIN + 1e-3 && kt >= 1 - 1e-6) return 1;
  if (kt > CONTAIN_TYPE_MIN + 1e-3) return 2;
  if (ks > CONTAIN_SPACE_FLOOR + 1e-3) return 3;
  return 0;
}

function knobsFor(phase, value, { ks, kt }) {
  if (phase === 1) return { ks: value, kt, ka: Math.max(CONTAIN_ART_MIN, value) };
  if (phase === 2) return { ks: Math.min(ks, CONTAIN_SPACE_MIN), kt: value, ka: CONTAIN_ART_MIN * value };
  return { ks: value, kt, ka: CONTAIN_ART_MIN * kt };
}

/* One contain step (pure, so the gate can drive it): given the space the face has, the height its content needs at the
   current knobs and, when there is one, the step before (its knobs and need), the next knobs. The first move in a
   phase is by the ratio; after that the need is taken as linear in the knob (secant), falling back to the ratio when
   a reflow makes the secant useless. */
export function containStep(available, need, { ks = 1, kt = 1, ka = 1 } = {}, previous = null) {
  const target = available - CONTAIN_MARGIN;
  if (!(need > 0) || need <= target) return { ks, kt, ka, done: true };
  const phase = phaseOf({ ks, kt });
  if (!phase) return { ks, kt, ka, done: true };
  const knob = phase === 2 ? 'kt' : 'ks';
  const min = phase === 1 ? CONTAIN_SPACE_MIN : phase === 2 ? CONTAIN_TYPE_MIN : CONTAIN_SPACE_FLOOR;
  const now = knob === 'ks' ? ks : kt;
  const byRatio = now * Math.max(0.2, target / need);
  let next = byRatio;
  const before = previous?.[knob];
  if (Number.isFinite(before) && before - now > 1e-4 && previous.need > need) {
    const secant = now - (need - target) / ((previous.need - need) / (before - now));
    if (Number.isFinite(secant) && secant < now) next = Math.min(secant, now - 0.01);
  }
  next = Math.max(min, Math.min(now - 0.005, next));
  return { ...knobsFor(phase, next, { ks, kt }), done: false };
}

/* The height a face body's CONTENT takes: from the body's top to its lowest child's bottom, plus its bottom padding.
   Not scrollHeight: a body that fills a slot taller than its content (Review's revealed face, the feed) is stretched,
   and its scrollHeight is then the slot - the face would always read as exactly full, and the loop would shrink a card
   that already fits (lead's check of e9e5f3d1: Review's card at s 0.933 with `fits` no, though wholly visible). */
function bodyContentHeight(body) {
  const children = body?.children;
  if (!children || typeof body.getBoundingClientRect !== 'function') return body ? body.scrollHeight || 0 : 0;
  const view = body.ownerDocument?.defaultView;
  const style = view?.getComputedStyle ? view.getComputedStyle(body) : null;
  const top = body.getBoundingClientRect().top;
  const paddingTop = style ? parseFloat(style.paddingTop) || 0 : 0;
  const paddingBottom = style ? parseFloat(style.paddingBottom) || 0 : 0;
  let bottom = top + paddingTop;
  for (const child of children) {
    const rect = child.getBoundingClientRect();
    if (rect.height <= 0 && rect.width <= 0) continue;
    const margin = view?.getComputedStyle ? parseFloat(view.getComputedStyle(child).marginBottom) || 0 : 0;
    bottom = Math.max(bottom, rect.bottom + margin);
  }
  return bottom - top + paddingBottom;
}

/* The face showing: the height its content needs (head + the body's content + foot) and the height it has. */
function faceHeights(card) {
  const face = [...card.querySelectorAll('.c-vcard__face')].find((node) => !node.hidden);
  if (!face) return null;
  const part = (name) => face.querySelector(`:scope > .c-vcard__${name}`);
  const head = part('head')?.getBoundingClientRect().height || 0;
  const foot = part('foot')?.getBoundingClientRect().height || 0;
  const need = head + bodyContentHeight(part('body')) + foot;
  return { available: face.clientHeight, need };
}

function setScales(card, { ks, kt, ka }) {
  card.style.setProperty('--vc-ks', ks.toFixed(4));
  card.style.setProperty('--vc-kt', kt.toFixed(4));
  card.style.setProperty('--vc-ka', ka.toFixed(4));
}

/* Step 2 for one card: from the width scale (knobs at 1), measure, step, repeat until the face fits. */
export function containCard(card) {
  if (typeof card?.querySelectorAll !== 'function') return null;
  let scales = { ks: 1, kt: 1, ka: 1 };
  setScales(card, scales);
  const natural = faceHeights(card);
  if (!natural) return null;
  let heights = natural;
  let prior = null;
  for (let step = 0; step < CONTAIN_STEPS; step += 1) {
    // The secant only within one phase: a new phase starts by the ratio.
    const previous = prior && phaseOf(prior) === phaseOf(scales) ? prior : null;
    const next = containStep(heights.available, heights.need, scales, previous);
    if (next.done) break;
    prior = { ...scales, need: heights.need };
    scales = { ks: next.ks, kt: next.kt, ka: next.ka };
    setScales(card, scales);
    heights = faceHeights(card);
  }
  const s = natural.need > 0 ? Math.min(1, heights.need / natural.need) : 1;
  card.style.setProperty('--vcard-s', s.toFixed(4));
  card.dataset.vcardS = s.toFixed(3);
  // clientHeight is whole pixels, the rects are not: within a pixel is inside.
  card.dataset.vcardFits = heights.need <= heights.available + 1 ? 'yes' : 'no';
  return { s, ...scales, need: heights.need, available: heights.available, natural: natural.need };
}

/* The top of the bottom chrome drawn over the page (the phone bar and its orb), or Infinity when there is none. While
   the shell holds its chrome hidden (D-181: :root[data-chrome='hidden'], how Word Detail arrives on a phone) there is
   none; otherwise it is measured where the bar rests, not where a running slide has moved it. */
export function bottomChromeTop(root) {
  const doc = root?.ownerDocument || (typeof document !== 'undefined' ? document : null);
  if (doc?.documentElement?.dataset?.chrome === 'hidden') return Infinity;
  const parts = doc?.querySelectorAll?.('[data-part="bnav"], [data-part="bnav"] .o-bnav__disc') || [];
  const view = doc?.defaultView;
  let top = Infinity;
  for (const part of parts) {
    const rect = part.getBoundingClientRect();
    if (!(rect.height > 0 && rect.width > 0)) continue;
    let shift = 0;
    const bar = part.closest?.('[data-part="bnav"]');
    const transform = bar && view?.getComputedStyle ? view.getComputedStyle(bar).transform : 'none';
    if (transform && transform !== 'none' && typeof view.DOMMatrixReadOnly === 'function') shift = new view.DOMMatrixReadOnly(transform).m42;
    top = Math.min(top, rect.top - shift);
  }
  return top;
}

/* The bottom a card may reach in its column: the column's bottom less its own bottom padding (the home indicator's
   inset when the chrome is collapsed), or the window's. */
function columnBottom(column) {
  if (!column) return window.innerHeight;
  const rect = column.getBoundingClientRect();
  const view = column.ownerDocument?.defaultView;
  const padding = view?.getComputedStyle ? parseFloat(view.getComputedStyle(column).paddingBottom) || 0 : 0;
  const hidden = column.ownerDocument?.documentElement?.dataset?.chrome === 'hidden';
  return rect.bottom - (hidden ? padding : 0);
}

/* One card, one size from the first paint (the human, 2026-10-13): the hidden face is shown for one synchronous
   measure, contained the same way, and the card keeps the taller height (min-height, never past its box); then the face
   it was on is shown again. Turning keeps that height (bindVocabularyCards). */
function equalFaces(card) {
  const faces = typeof card?.querySelectorAll === 'function' ? [...card.querySelectorAll('.c-vcard__face')] : [];
  if (faces.length !== 2) return;
  const shown = faces.find((face) => !face.hidden) || faces[0];
  const other = faces.find((face) => face !== shown);
  let tallest = parseFloat(card.style.minHeight) || 0;
  for (const face of [other, shown]) {
    for (const each of faces) each.hidden = each !== face;
    containCard(card);
    tallest = Math.max(tallest, card.getBoundingClientRect().height);
  }
  card.style.minHeight = `${Math.round(tallest)}px`;
}

export function fitVocabularyCards(root, { viewport = false, bottomGap = 16 } = {}) {
  root?.querySelectorAll?.('.c-vcard').forEach((card) => {
    if (viewport) {
      // Measured as if the column were at its top: arrival is what must fit. The limit is the column's bottom or,
      // higher, the top of any bottom chrome over it - the phone bar and the Orena orb that rises above it (rule 47:
      // the browsing places have one) - so the card and its turn action never sit under it.
      const column = card.closest('.o-main');
      const bottom = Math.min(columnBottom(column), bottomChromeTop(root));
      const top = card.getBoundingClientRect().top + (column ? column.scrollTop : window.scrollY || 0);
      const available = Math.max(320, Math.floor(bottom - top - bottomGap));
      card.style.setProperty('--vcard-fit', `${available}px`);
      // The height kept across turns never outgrows the box (min-height would win over max-height).
      if (parseFloat(card.style.minHeight) > available) card.style.minHeight = `${available}px`;
      card.dataset.fit = available < SHORT_CARD_PX ? 'short' : 'full';
    } else {
      // The slot the card fills (Review's face, the feed's card), not the card's own content height.
      const slot = card.parentElement?.getBoundingClientRect().height || 0;
      card.dataset.fit = slot && slot < SHORT_CARD_PX ? 'short' : 'full';
    }
    equalFaces(card);
    containCard(card);
  });
  // Web fonts change the measure once they arrive: fit again then, once per document.
  const fonts = root?.ownerDocument?.fonts;
  if (fonts?.ready && !root.dataset?.vcardFontsFit) {
    root.dataset.vcardFontsFit = '1';
    fonts.ready.then(() => root.isConnected && fitVocabularyCards(root, { viewport, bottomGap })).catch(() => {});
  }
}

/* Turns a card between its faces (a real button each way, so the keyboard does it too), and gives the
   focus to the other face's turn action. A screen calls it once after mounting its cards. */
export function bindVocabularyCards(root) {
  root?.querySelectorAll?.('[data-vcard-turn]').forEach((button) => {
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      const card = button.closest('.c-vcard');
      if (!card) return;
      const to = button.dataset.vcardTurn;
      // One card, one size (the human, 2026-10-13): the card keeps the tallest height it has had, so neither face is
      // drawn smaller than the other. fitVocabularyCards caps it at the box.
      const kept = parseFloat(card.style.minHeight) || 0;
      card.style.minHeight = `${Math.round(Math.max(kept, card.getBoundingClientRect().height))}px`;
      card.dataset.face = to;
      card.querySelector('.c-vcard__face--front').hidden = to !== 'front';
      card.querySelector('.c-vcard__face--back').hidden = to !== 'back';
      containCard(card); // the other face fits on its own (a face never scrolls)
      card.querySelector(`.c-vcard__face--${to} [data-vcard-turn]`)?.focus({ preventScroll: true });
    });
  });
}
