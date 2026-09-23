/* One word, opened all the way.
 *
 * The canonical frames "Vocabulary card deep", "Vocabulary card deep scrolled"
 * and "Vocabulary deep desktop". On a phone the word is two pages - the
 * dictionary's half, then the learner's half - with the foot carrying the way
 * between them; on a desktop both halves are on one screen, which is what the
 * desktop frame draws, so the "scroll on" button has nothing to do there and
 * is not drawn.
 *
 * Every section is drawn only when it has something in it. The read
 * (`/api/library/vocabulary/{word}/deep`) leaves a section out rather than
 * filling it, so a word the catalogue knows three senses of and no contrast
 * for shows three senses and no contrast heading - not a heading over nothing.
 */
import { esc } from './html.js';
import { icon } from './phosphor.js';

/* The two pages the phone frames draw, in the order the foot moves through. */
export const PAGES = ['meaning', 'yours'];

function label(text) {
  return `<span class="ds-label word-deep__label">${esc(text)}</span>`;
}

function section(name, body) {
  return body ? `<section class="word-deep__section">${label(name)}${body}</section>` : '';
}

/* The word inside one of the learner's own sentences, marked where it stands.
   Split rather than replaced, so nothing in the sentence can be read as
   markup. */
function marked(text, word) {
  const at = String(text).toLowerCase().indexOf(String(word).toLowerCase());
  if (at < 0 || !word) return esc(text);
  return `${esc(text.slice(0, at))}<mark>${esc(text.slice(at, at + word.length))}</mark>${esc(text.slice(at + word.length))}`;
}

function senses(c, list) {
  if (!list.length) return '';
  return `<div class="word-deep__rows">${list
    .map(
      (sense) =>
        `<div class="word-deep__sense"><span class="word-deep__pos ds-data">${esc(sense.pos)}</span><span class="word-deep__meaning">${esc(sense.meaning)}${sense.example ? ` — ${esc(sense.example)}` : ''}</span></div>`,
    )
    .join('')}</div>`;
}

function combinations(list) {
  if (!list.length) return '';
  return `<div class="word-deep__chips">${list
    .map((item) => `<span class="word-deep__chip"${item.reading ? ` title="${esc(item.reading)}"` : ''}>${esc(item.term)}</span>`)
    .join('')}</div>`;
}

function pairs(list, wide = false) {
  if (!list.length) return '';
  return `<div class="word-deep__rows">${list
    .map(
      (row) =>
        `<div class="word-deep__pair${wide ? ' word-deep__pair--wide' : ''}"><span class="word-deep__term">${esc(row.term)}</span><span class="word-deep__note">${esc(row.note)}</span></div>`,
    )
    .join('')}</div>`;
}

function prose(text) {
  return text ? `<p class="word-deep__text">${esc(text)}</p>` : '';
}

/* Which capability the learner met the word in decides the icon, because that
   is what the frame draws: headphones for something heard, an open book for
   something read, a pencil for something written. */
const SOURCE_ICON = {
  listening: 'headphones',
  media: 'headphones',
  shadowing: 'headphones',
  reading: 'book-open',
  story: 'book-open',
  writing: 'pencil-simple',
  essay: 'pencil-simple',
  speaking: 'microphone',
};

function sources(c, list) {
  if (!list.length) return '';
  return `<div class="word-deep__rows">${list
    .map(
      (row) =>
        `<div class="word-deep__source">${icon(SOURCE_ICON[row.kind] || 'bookmark-simple', { size: 17 })}<span class="word-deep__source-title">${esc(row.title)}${row.at ? ` · ${esc(row.at)}` : ''}</span></div>`,
    )
    .join('')}</div>`;
}

function learnerSentences(c, list, word) {
  if (!list.length) return '';
  return `<div class="word-deep__rows">${list
    .map(
      (row) =>
        `<div class="word-deep__mine"><span class="word-deep__mine-text">${marked(row.text, word)}</span><span class="word-deep__mine-note ds-data">${esc(row.writtenOn ? row.writtenOn.slice(0, 10) : '')}${row.checked ? ` · ${esc(c.wordDeepChecked)}` : ''}</span></div>`,
    )
    .join('')}</div>`;
}

/* The dictionary's half of the word: what it means, what it combines into,
   what it is not, and where it goes wrong. */
export function meaningPage(c, data) {
  return [
    section(c.wordDeepSenses, senses(c, data.senses || [])),
    section(c.wordDeepCombinations, combinations(data.combinations || [])),
    section(c.wordDeepContrast, pairs(data.contrast || [])),
    section(c.wordDeepMistake, prose(data.commonMistake)),
    section(c.wordDeepMentalModel, prose(data.mentalModel)),
  ].join('');
}

/* The learner's half: the expressions around it, where they met it, and the
   sentences they have written with it. */
export function yoursPage(c, data) {
  return [
    section(c.wordDeepRelated, pairs(data.related || [], true)),
    section(c.wordDeepWhereFrom, sources(c, data.sources || [])),
    section(c.wordDeepYourSentences, learnerSentences(c, data.learnerSentences || [], data.headword)),
  ].join('');
}

function head(c, data) {
  return `<header class="word-deep__head"><button type="button" class="icon-button word-deep__back" data-word-deep-back aria-label="${esc(c.back)}">${icon('caret-right', { size: 22, className: 'is-flipped' })}</button><strong class="word-deep__word" lang="${esc(data.language || '')}">${esc(data.headword)}</strong>${data.reading ? `<span class="word-deep__reading ds-data">${esc(data.reading)}</span>` : ''}<button type="button" class="icon-button word-deep__speak" data-word-deep-speak aria-label="${esc(c.vocabularyListen || c.wordDeepListen)}">${icon('speaker-high', { size: 20, filled: true })}</button></header>`;
}

function foot(c, data, page) {
  const keep = `<button type="button" class="word-deep__action" data-word-deep-keep aria-pressed="${Boolean(data.saved)}">${icon('bookmark-simple', { size: 17, filled: Boolean(data.saved) })}<span>${esc(data.saved ? c.wordDeepUnkeep : c.wordDeepKeep)}</span></button>`;
  const ask = `<button type="button" class="word-deep__action" data-word-deep-ask>${icon('chat-teardrop-text', { size: 17 })}<span>${esc(c.wordDeepAsk)}</span></button>`;
  const on = `<button type="button" class="word-deep__action" data-word-deep-page="yours">${icon('caret-down', { size: 17 })}<span>${esc(c.wordDeepScrollOn)}</span></button>`;
  const back = `<button type="button" class="word-deep__action" data-word-deep-page="meaning">${icon('caret-up', { size: 17 })}<span>${esc(c.wordDeepScrollBack)}</span></button>`;
  return `<footer class="word-deep__foot">${page === 'yours' ? `${ask}${back}` : `${keep}${on}`}</footer>`;
}

/* Pure: the whole screen for a state. The desktop layout is the same sections
   in one column-pair, which the stylesheet does at width; the markup does not
   fork, so the two can never drift apart. */
export function wordDeepHtml(c, data, { page = 'meaning', state = 'ready' } = {}) {
  if (state === 'loading')
    return `<section class="word-deep is-loading" aria-busy="true"><p class="meta" role="status">${esc(c.loading || '')}</p></section>`;
  if (state === 'failed')
    return `<section class="word-deep"><p class="notice" role="alert">${esc(c.unavailable)} <button type="button" class="quiet" data-word-deep-retry>${esc(c.retry)}</button> <button type="button" class="quiet" data-word-deep-back>${esc(c.back)}</button></p></section>`;
  const meaning = meaningPage(c, data);
  const yours = yoursPage(c, data);
  return `<section class="word-deep" data-word-deep-page-now="${esc(page)}">${head(c, data)}<div class="word-deep__body">${data.gloss ? `<p class="word-deep__gloss">${esc(data.gloss)}</p>` : ''}<div class="word-deep__half word-deep__half--meaning"${page === 'meaning' ? '' : ' hidden'}>${meaning}</div><div class="word-deep__half word-deep__half--yours"${page === 'yours' ? '' : ' hidden'}>${yours}</div></div>${foot(c, data, page)}</section>`;
}
