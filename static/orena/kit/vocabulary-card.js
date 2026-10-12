/* VocabularyCard (D-178, D-179): the one vocabulary card, drawn from the model
   `product/vocabulary-card.js#toVocabularyModel` makes.

   Provenance (UI provenance gate). LAYOUT and INFORMATION: the human's design reference for this
   component, the Claude Design canvas "Flashcard từ vựng Anh – Trung" (claude.ai/artifact/
   9wmYKVJVn8cBuX8ButSryF): artboard `Main.dc.html` (English, "resilient") and `Chinese.dc.html` (Chinese,
   "森林") - a two-face card, the front with the word and its facts, the back with the examples, turned by
   "See examples ->" / "<- Front". LOOK (D-17X, human 2026-10-12): the same design, now pinned in
   docs/design/vocab-card/ - its own palette as card-scoped tokens (`--vcard-*`, kit/tokens.css; light "watercolor
   paper", dark "night violet", the Chinese seal), its shapes (the English line border and pill, the Chinese paper and
   gold ruled frame, the seal tag and radical box), its highlights and buttons, and its two line drawings as library
   art for the samples (kit/vocabulary-art.js); local fonts only, the kit's focus ring (AA). Adaptations, each recorded
   in D-179 / D-17X and UI_BACKEND_GAPS "Vocabulary card":
   the play and save discs sit in a quiet action row under the reading (the design draws neither; the top row stays
   level/source left, part of speech right, as drawn - D-17X point 8); collocations are chips; a section with no data
   is left out. Every tag, chip and accent inside the card is `--vcard-*`: no global accent token, no kit `o-tag`.

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
  return html`<button type="button" class="c-vcard__disc c-vcard__disc--play" data-play${region ? raw(` data-region="${region}"`) : ''} aria-label="${t('playWord')}">${raw(icon('volume-2', { size: 17 }))}</button>`;
}

function saveDisc(learner) {
  return html`<button type="button" class="${cls('c-vcard__disc', learner?.saved && 'is-saved')}" data-save aria-pressed="${learner?.saved ? 'true' : 'false'}" aria-label="${t(learner?.saved ? 'unsaveWord' : 'saveWord')}">${raw(icon('bookmark-check', { size: 17 }))}</button>`;
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

/* The top row: the level tag (and, on the English card, its source), the discs on the right. */
/* The top row as the design draws it: the level tag (and, on the English card, its source) on the left, the part of
   speech on the right - one row; at a narrow width it may wrap, the part of speech staying the row's last item. */
function topRow(model) {
  const tags = [
    model.level ? html`<span class="c-vcard__level">${levelLabel(model)}</span>` : '',
    model.script !== 'hanzi' && model.levelSource ? html`<span class="c-vcard__source">${model.levelSource}</span>` : '',
  ];
  const pos = posLine(model);
  if (!String(tags.join('')) && !String(pos)) return '';
  return html`<div class="c-vcard__top"><div class="c-vcard__tags">${tags}</div>${pos}</div>`;
}

/* The word's actions - play, and Save on the cards a word is met on - in a quiet row under its reading, so the
   design's header stays as drawn (D-17X: derivation recorded in this file's header). */
function actionRow(save) {
  return html`<div class="c-vcard__actions">${playDisc()}${save || ''}</div>`;
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
      ${actionRow(ctx.save)}
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
    ${actionRow(ctx.save)}
    ${illustration(model)}
    ${meaningSection(model, ctx)}
    ${radicalSection(model)}
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
  const ctx = { save, meaningLabel: slots.meaningLabel, pending: slots.meaningPending };
  const front = han ? zhFront(model, ctx) : enFront(model, ctx);
  // Each face: a head that stays (the design's top row / the back's title line), a body that alone scrolls when the
  // face holds more than fits, and a foot with the turn action (rule 49).
  const frontHead = topRow(model);
  const backFace = back(model, { learner, mode });
  return html`<article class="${cls('c-vcard', `c-vcard--${mode}`, han && 'c-vcard--han')}" data-vcard-mode="${mode}" data-face="front">
    <div class="c-vcard__face c-vcard__face--front" id="${id}-front">
      ${frontHead ? html`<div class="c-vcard__head">${frontHead}</div>` : ''}
      <div class="c-vcard__body" data-scroll-region>${front}${slots.strokes || ''}</div>
      <div class="c-vcard__foot">
        ${footer(learner, slots.footer)}
        <button type="button" class="c-vcard__turn c-vcard__turn--primary" data-vcard-turn="back" aria-controls="${id}-back">${t('seeExamples')}</button>
      </div>
    </div>
    <div class="c-vcard__face c-vcard__face--back" id="${id}-back" hidden>
      ${backFace.head}
      <div class="c-vcard__body" data-scroll-region>${backFace.body}</div>
      <div class="c-vcard__foot c-vcard__foot--back">
        <button type="button" class="c-vcard__turn c-vcard__turn--secondary" data-vcard-turn="front" aria-controls="${id}-front">${t('backToFront')}</button>
      </div>
    </div>
  </article>`;
}

/* Fits each card to the height it has (rule 49, CLAUDE.md 6b). `viewport: true` (Word Detail, a browsing page): the
   card's max-height is the visible height of its scrolling column below the card's top, so on arrival the whole card -
   actions included - is in view. Otherwise the card already sits in a bounded slot (Review's face, the feed's card).
   Either way a card with little height drops its illustration first (`data-fit="short"`) before its body scrolls. */
export const SHORT_CARD_PX = 620;

export function fitVocabularyCards(root, { viewport = false, bottomGap = 16 } = {}) {
  root?.querySelectorAll?.('.c-vcard:not(.c-vcard--review-front)').forEach((card) => {
    if (viewport) {
      // Measured as if the column were at its top: arrival is what must fit.
      const column = card.closest('.o-main');
      const bottom = column ? column.getBoundingClientRect().bottom : window.innerHeight;
      const top = card.getBoundingClientRect().top + (column ? column.scrollTop : window.scrollY || 0);
      const available = Math.max(320, Math.floor(bottom - top - bottomGap));
      card.style.setProperty('--vcard-fit', `${available}px`);
      card.dataset.fit = available < SHORT_CARD_PX ? 'short' : 'full';
    } else {
      // The slot the card fills (Review's face, the feed's card), not the card's own content height.
      const slot = card.parentElement?.getBoundingClientRect().height || 0;
      card.dataset.fit = slot && slot < SHORT_CARD_PX ? 'short' : 'full';
    }
  });
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
      card.dataset.face = to;
      card.querySelector('.c-vcard__face--front').hidden = to !== 'front';
      card.querySelector('.c-vcard__face--back').hidden = to !== 'back';
      card.querySelector(`.c-vcard__face--${to} [data-vcard-turn]`)?.focus({ preventScroll: true });
    });
  });
}
