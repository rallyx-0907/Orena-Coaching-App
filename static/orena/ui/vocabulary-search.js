/* Searching the room: the learner's own words, and the catalogue's.
 *
 * The canonical frames "Vocabulary search" (20) and "Vocabulary search mobile"
 * (21). It is the room's own search, not the shared top bar's - the top bar
 * searches the whole app, and this searches words - so it lives here and
 * leaves that one alone.
 *
 * Two lists, each labelled: what the learner has kept, and what the catalogue
 * has. A kept word says where it lives and when it comes back; a catalogue
 * word offers the one thing worth offering, which is keeping it.
 */
import { esc } from './html.js';
import { icon } from './phosphor.js';

export const FILTERS = ['all', 'saved', 'dictionary'];

/* The part of the word the learner has typed, picked out where it stands.
   Split rather than replaced, so nothing in a word can be read as markup. */
function matched(word, query) {
  const at = String(word).toLowerCase().indexOf(String(query).toLowerCase());
  if (!query || at < 0) return esc(word);
  return `${esc(word.slice(0, at))}<b>${esc(word.slice(at, at + query.length))}</b>${esc(word.slice(at + query.length))}`;
}

function label(text) {
  return `<span class="ds-label vocab-search__label">${esc(text)}</span>`;
}

function savedRow(c, item, query) {
  const when = item.due ? c.vocabularyDueState : item.next_review_at ? String(item.next_review_at).slice(0, 10) : '';
  const where = [item.definition || item.translation_vi, item.focus_note].filter(Boolean).join(' · ');
  return `<button type="button" class="vocab-search__row" data-search-open="${esc(item.word)}"><span class="vocab-search__text"><span class="vocab-search__word">${matched(item.word, query)}</span>${
    where ? `<span class="vocab-search__note">${esc(where)}</span>` : ''
  }</span>${when ? `<span class="vocab-search__when ds-data"${item.due ? ' data-tone="due"' : ''}>${esc(when)}</span>` : ''}</button>`;
}

function catalogueRow(c, entry, query, kept) {
  const meaning = (entry.short_meanings || [])[0];
  const note = [typeof meaning === 'string' ? meaning : meaning?.text, entry.part_of_speech].filter(Boolean).join(' · ');
  return `<div class="vocab-search__row vocab-search__row--catalogue"><button type="button" class="vocab-search__text" data-search-open="${esc(entry.word)}"><span class="vocab-search__word">${matched(entry.word, query)}</span>${
    note ? `<span class="vocab-search__note">${esc(note)}</span>` : ''
  }</button>${
    kept
      ? `<span class="vocab-search__kept" aria-label="${esc(c.vocabularySaved)}">${icon('check', { size: 18 })}</span>`
      : `<button type="button" class="vocab-search__keep" data-search-keep="${esc(entry.word)}" aria-label="${esc(c.vocabularySave)}">${icon('plus', { size: 19 })}</button>`
  }</div>`;
}

export function vocabularySearchHtml(c, state) {
  const { query = '', filter = 'all', saved = [], catalogue = [], savedTotal = 0, language = '', busy = false } = state;
  const chips = FILTERS.map((name) => {
    const text =
      name === 'saved'
        ? `${c.vocabularySearchSaved}${savedTotal ? ` · ${savedTotal}` : ''}`
        : name === 'dictionary'
          ? c.vocabularySearchDictionary
          : c.vocabularyFilterAll;
    return `<button type="button" class="vocab-search__chip" data-search-filter="${name}" aria-pressed="${filter === name}">${esc(text)}</button>`;
  }).join('');
  const showSaved = filter !== 'dictionary' && saved.length;
  const showCatalogue = filter !== 'saved' && catalogue.length;
  const body = query
    ? `${showSaved ? `${label(c.vocabularySearchSaved)}${saved.map((item) => savedRow(c, item, query)).join('')}` : ''}${
        showCatalogue
          ? `${label(`${c.vocabularySearchDictionary} · ${String(language).toUpperCase()}`)}${catalogue
              .map((entry) => catalogueRow(c, entry, query, saved.some((item) => item.word === entry.word)))
              .join('')}`
          : ''
      }${!showSaved && !showCatalogue && !busy ? `<p class="vocab-search__none">${esc(c.vocabularyNoMatches)}</p>` : ''}`
    : '';
  return `<section class="vocab-search"><header class="vocab-search__head"><label class="vocab-search__field"><span class="sr-only">${esc(c.vocabularySearch)}</span>${icon('magnifying-glass', { size: 18 })}<input type="search" data-search-input value="${esc(query)}" placeholder="${esc(c.vocabularySearch)}" autocomplete="off">${
    query ? `<button type="button" class="vocab-search__clear" data-search-clear aria-label="${esc(c.vocabularySearchClear)}">${icon('x-circle', { size: 18, filled: true })}</button>` : ''
  }</label><button type="button" class="quiet vocab-search__cancel" data-search-cancel>${esc(c.cancel)}</button></header><div class="vocab-search__chips">${chips}</div><div class="vocab-search__results" role="status" aria-busy="${busy}">${body}</div></section>`;
}
