/* VocabularyCard (D-178, D-17W): the one rich vocabulary card, drawn from the model
   `product/vocabulary-card.js#toVocabularyModel` makes, for Word Detail (`detail`), the Daily Feed
   (`feed`) and Review (`review-front`, then `review-back`). The Admin preview (PR 3) renders the
   same markup with no learner state.

   Provenance (UI provenance gate): Orena.dc.html -> Word Detail / Review Session -> the word card
   (`wdWC` / `rvWC`: header with word, reading, part-of-speech and level tags, the play and save
   discs, the tinted meaning panel, the example with its tinted highlight, the stroke-order block,
   the mastery footer) -> reused as this component. Adaptations: the meaning panel lists more than one
   example; the further entry facts (collocations, synonyms and opposites, word family, related
   words, measure words, the Chinese character units, the memory tip) are drawn as the card's own
   small-caps section label over plain text - the stroke-order block's label pattern - in a two-column
   grid that drops to one column on a phone; the layout and information follow the human's flashcard
   reference ("Flashcard từ vựng Anh – Trung", D-178), its colours, faces and paper look do not.
   Tokens only (kit/tokens.css); edges are `--edge-light` (D-147).

   Modes:
   - `review-front`: the word or Hanzi, its reading, part of speech and level, the play disc.
     Nothing that answers the card (no meaning, example, translation, relation or character facts).
   - `review-back`: the whole card; the screen draws the grades under it.
   - `detail`: the whole card with the save disc.
   - `feed`: the whole card with the save disc, the first example only.

   Learner state is a separate decorator (`learner`, from `learnerState`), drawn only as the
   footer and the save disc's state; the content never depends on it. No illustration means no frame. */
import { html, raw, cls } from './html.js';
import { icon } from './icons.js';
import { langAttr } from './lang.js';
import { masteryBars } from './components.js';
import { t } from '../copy/vocabulary-card.js';

export const CARD_MODES = Object.freeze(['detail', 'feed', 'review-front', 'review-back']);

const POS_KEY = Object.freeze({
  noun: 'posNoun', verb: 'posVerb', adjective: 'posAdjective', adverb: 'posAdverb', pronoun: 'posPronoun',
  determiner: 'posDeterminer', preposition: 'posPreposition', conjunction: 'posConjunction',
  numeral: 'posNumeral', particle: 'posParticle', auxiliary: 'posAuxiliary', interjection: 'posInterjection',
  classifier: 'posClassifier', measure_word: 'posMeasureWord', phrase: 'posPhrase', idiom: 'posIdiom',
  proper_noun: 'posProperNoun', other: 'posOther',
});

/* A part of speech in the interface language when it is one of the known codes; otherwise the
   value as the source wrote it, marked as English content metadata (the word/copy.js precedent). */
export function posLabel(value) {
  const raw0 = String(value ?? '').trim();
  const parts = raw0.split(/\s*[/,;|]\s*/).filter(Boolean);
  const keys = parts.map((part) => POS_KEY[part.toLowerCase().replace(/\s+/g, '_')]);
  if (parts.length && keys.every(Boolean)) return { text: keys.map((key) => t(key)).join(t('posJoin')), known: true };
  return { text: raw0, known: false };
}

function posTag(value) {
  if (!value) return '';
  const label = posLabel(value);
  return html`<span class="o-tag"${label.known ? '' : raw(` lang="${langAttr('en')}"`)}>${label.text}</span>`;
}

function parts(list, hitClass = 'c-vcard__hit') {
  return list.map((part) => (part.hit ? html`<mark class="${hitClass}">${part.value}</mark>` : part.value));
}

function section(titleKey, body, extra = '') {
  if (!body) return '';
  return html`<section class="${cls('c-vcard__section', extra)}"><h3 class="c-vcard__label">${t(titleKey)}</h3>${body}</section>`;
}

/* The heading: the word (a Chinese word as its character units with their pinyin above when the
   entry carries them), the reading(s), the tags, the play and save discs. */
/* How long the headword's longest unbreakable run is, so its type can shrink to fit the card's width
   instead of breaking inside a word (CSS `--len`, kit/vocabulary-card.css). Han has no spaces: the whole
   word is one run. A number, never a colour. */
export function headwordRun(word, script) {
  const value = String(word ?? '').trim();
  if (script === 'hanzi') return Math.max(1, [...value].length);
  return Math.max(1, ...value.split(/\s+/).map((part) => [...part].length));
}

function heading(model, { mode, learner }) {
  const lang = langAttr(model.language);
  const run = headwordRun(model.word, model.script);
  const units = model.script === 'hanzi' ? model.units : [];
  const word = units.length
    ? html`<span class="c-vcard__word c-vcard__word--han" lang="${lang}" style="--len:${run}">${units.map((unit) => html`<ruby>${unit.hanzi}${unit.pinyin ? html`<rt>${unit.pinyin}</rt>` : ''}</ruby>`)}</span>`
    : html`<span class="c-vcard__word${cls(model.script === 'hanzi' && ' c-vcard__word--han')}" lang="${lang}" style="--len:${run}">${model.word}</span>`;
  const ipa = model.pronunciation.ipa.length > 1
    ? model.pronunciation.ipa.map((item) => html`<span class="c-vcard__ipa">${item.region === 'uk' || item.region === 'us' ? html`<b>${t(item.region === 'uk' ? 'regionUk' : 'regionUs')}</b> ` : ''}${item.text}</span>`)
    : (model.pronunciation.text ? html`<span class="c-vcard__ipa">${model.pronunciation.text}</span>` : '');
  const save = mode === 'detail' || mode === 'feed' || (mode === 'review-back' && learner)
    ? html`<button type="button" class="${cls('c-vcard__disc', learner?.saved && 'is-saved')}" data-save aria-pressed="${learner?.saved ? 'true' : 'false'}" aria-label="${t(learner?.saved ? 'unsaveWord' : 'saveWord')}">${raw(icon('bookmark-check', { size: 19 }))}</button>`
    : '';
  return html`<header class="c-vcard__head">
    <div class="c-vcard__id">
      ${word}
      <div class="c-vcard__meta">${ipa}${posTag(model.pos)}${model.level ? html`<span class="o-tag">${model.level}</span>` : ''}${model.hanViet ? html`<span class="c-vcard__hanviet"><b>${t('hanVietLabel')}</b> ${model.hanViet}</span>` : ''}</div>
    </div>
    <div class="c-vcard__discs">
      <button type="button" class="c-vcard__disc c-vcard__disc--play" data-play aria-label="${t('playWord')}">${raw(icon('volume-2', { size: 19 }))}</button>
      ${save}
    </div>
  </header>`;
}

/* The meaning panel. A meaning still being looked up shows the kit's skeleton bones, never a claim
   that there is none; "no meaning" only when nothing at all exists (rule 40). The word's own-language
   definition is the line under the meaning, or the panel's only line, tagged with its language. */
function meaningBlock(model, { meaningTag, pending }) {
  const tag = (language) => (language && meaningTag ? meaningTag(language) : '');
  if (!model.meaning && !model.definition) {
    if (pending) {
      return html`<div class="c-vcard__meaning" aria-busy="true" data-meaning-pending><div class="o-bone o-bone--strong" style="height:12px;width:55%"></div><div class="o-bone" style="height:10px;width:32%"></div></div>`;
    }
    return html`<div class="c-vcard__meaning"><div class="c-vcard__support" data-no-meaning>${t('meaningUnavailable')}</div></div>`;
  }
  const definition = model.definition
    ? html`<div class="${model.meaning ? 'c-vcard__definition' : 'c-vcard__meaning-text'}"><span lang="${langAttr(model.definitionLanguage)}">${model.definition}</span>${tag(model.definitionLanguage)}</div>`
    : '';
  return html`<div class="c-vcard__meaning">
    ${model.meaning ? html`<div class="c-vcard__meaning-text">${model.meaning.text}${tag(model.meaning.language)}</div>` : ''}
    ${model.support ? html`<div class="c-vcard__support">${model.support}</div>` : ''}
    ${definition}
  </div>`;
}

function exampleItem(example, model) {
  const lang = langAttr(model.language);
  return html`<li class="c-vcard__example">
    ${example.label ? html`<div class="c-vcard__example-label">${example.label}</div>` : ''}
    <div class="c-vcard__example-text" lang="${lang}">${parts(example.parts)}</div>
    ${example.reading ? html`<div class="c-vcard__example-reading" lang="zh-Latn">${parts(example.readingParts)}</div>` : ''}
    ${example.translation ? html`<div class="c-vcard__example-translation">${example.translation}</div>` : ''}
    ${example.explanation ? html`<div class="c-vcard__example-note">${example.explanation}</div>` : ''}
  </li>`;
}

function examplesBlock(model, { mode, learner }) {
  const list = mode === 'feed' ? model.examples.slice(0, 1) : model.examples;
  if (list.length) return section('sectionExamples', html`<ul class="c-vcard__examples">${list.map((example) => exampleItem(example, model))}</ul>`, 'c-vcard__section--wide');
  // No authored example: the sentence the learner met the word in, when there is one (theirs, so a decorator).
  const context = learner?.context;
  if (!context) return '';
  return section('sectionMetIn', html`<div class="c-vcard__example-text" lang="${langAttr(model.language)}">${parts(learner.contextParts || [{ value: context, hit: false }])}</div>`, 'c-vcard__section--wide');
}

function wordList(words, lang) {
  return words.length ? html`<div class="c-vcard__words" lang="${langAttr(lang)}">${words.join(', ')}</div>` : '';
}

function charactersBlock(model) {
  if (!model.units.length) return '';
  const lang = langAttr(model.language);
  return section('sectionCharacters', html`<ul class="c-vcard__units">${model.units.map((unit) => html`<li class="c-vcard__unit">
    <span class="c-vcard__unit-glyph" lang="${lang}">${unit.hanzi}</span>
    <span class="c-vcard__unit-body">
      <span>${unit.pinyin}${unit.hanViet ? html` · ${unit.hanViet}` : ''}${unit.strokes ? html` · ${t.plural('strokeCount', unit.strokes)}` : ''}</span>
      ${unit.radical ? html`<span><b>${t('radicalLabel')}</b> <span lang="${lang}">${unit.radical.surface}</span>${unit.radical.reading ? ` ${unit.radical.reading}` : ''}${unit.radical.name ? ` · ${unit.radical.name}` : ''}${unit.radical.gloss ? ` (${unit.radical.gloss})` : ''}</span>` : ''}
      ${unit.components.length ? html`<span lang="${lang}">${unit.hanzi} = ${unit.components.join(' + ')}</span>` : ''}
    </span>
  </li>`)}</ul>`, 'c-vcard__section--wide');
}

function relationsGrid(model) {
  const lang = model.language;
  const cells = [
    section('sectionCollocations', wordList(model.collocations, lang)),
    section('sectionClassifiers', model.classifiers.length ? html`<div class="c-vcard__words">${model.classifiers.map((item) => html`<div><span lang="${langAttr(lang)}">${item.phrase || item.mw}</span>${item.phraseReading || item.reading ? html` <span class="c-vcard__muted">${item.phraseReading || item.reading}</span>` : ''}</div>`)}</div>` : ''),
    section('sectionWordFamily', model.wordFamily.length ? html`<div class="c-vcard__words" lang="${langAttr(lang)}">${model.wordFamily.map((item, index) => html`${index ? ', ' : ''}${item.word}${item.pos ? html` <span class="c-vcard__muted">${item.pos}</span>` : ''}`)}</div>` : ''),
    section('sectionSynonyms', wordList(model.synonyms, lang)),
    section('sectionAntonyms', wordList(model.antonyms, lang)),
    section('sectionRelated', model.related.length ? html`<div class="c-vcard__words">${model.related.map((item) => html`<div><span lang="${langAttr(lang)}">${item.word}</span>${item.reading ? html` <span class="c-vcard__muted">${item.reading}</span>` : ''}${item.gloss ? html` · ${item.gloss}` : ''}</div>`)}</div>` : ''),
  ].filter((cell) => String(cell));
  return cells.length ? html`<div class="c-vcard__grid">${cells}</div>` : '';
}

function notesBlock(model) {
  return [
    model.memoryTip ? section('sectionMemoryTip', html`<p class="c-vcard__note">${model.memoryTip.text}</p>`, 'c-vcard__section--wide') : '',
    model.usage.length ? section('sectionUsage', html`${model.usage.map((note) => html`<p class="c-vcard__note">${note}</p>`)}`, 'c-vcard__section--wide') : '',
    model.commonMistakes.length ? section('sectionCommonMistake', html`${model.commonMistakes.map((note) => html`<p class="c-vcard__note">${note}</p>`)}`, 'c-vcard__section--wide') : '',
    model.etymology ? section('sectionEtymology', html`<p class="c-vcard__note">${model.etymology}</p>`, 'c-vcard__section--wide') : '',
  ];
}

function footerBlock(learner, labels) {
  if (!learner?.hasSchedule) return '';
  const items = [html`<span class="c-vcard__bars">${masteryBars({ filled: learner.filled, total: 4 })}</span>`];
  if (labels?.stage) items.push(html`<span class="c-vcard__stage">${labels.stage}</span>`);
  if (labels?.due) items.push(html`<span class="c-vcard__due">· ${labels.due}</span>`);
  return html`<footer class="c-vcard__footer">${items}</footer>`;
}

/* `slots`: markup a screen owns and places inside the card - `strokes` (the stroke-order block,
   Chinese), `footer` labels for the learner footer ({ stage, due } already in the screen's words),
   and `meaningTag(language)` to name a meaning's language when it is not the support language. */
export function vocabularyCard(model, { mode = 'detail', learner = null, slots = {} } = {}) {
  if (!CARD_MODES.includes(mode)) throw new Error(`VocabularyCard: unknown mode ${mode}`);
  const front = mode === 'review-front';
  const illustration = !front && model.illustration
    ? html`<figure class="c-vcard__art"><img src="${model.illustration.src}" alt="${model.illustration.alt}" loading="lazy" /></figure>`
    : '';
  const body = front
    ? ''
    : html`${illustration}
      ${meaningBlock(model, { meaningTag: slots.meaningTag, pending: slots.meaningPending })}
      ${examplesBlock(model, { mode, learner })}
      ${charactersBlock(model)}
      ${relationsGrid(model)}
      ${notesBlock(model)}
      ${slots.strokes || ''}`;
  return html`<article class="${cls('c-vcard', `c-vcard--${mode}`, model.script === 'hanzi' && 'c-vcard--han')}" data-vcard-mode="${mode}">
    ${heading(model, { mode, learner })}
    ${body}
    ${front ? '' : footerBlock(learner, slots.footer)}
  </article>`;
}
