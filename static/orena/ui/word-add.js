/* Adding a word, and the set it goes into.
 *
 * The canonical frames "Save to deck sheet mobile" (22), "Add word modal"
 * (23), "Add word mobile" (24) and "Create deck mobile" (25). One module,
 * because they are one errand: the learner has a word, or is about to have
 * one, and it has to land somewhere.
 *
 * The set is a **Deck**: a learning/review set that belongs to Vocabulary.
 * It is not a My Library Collection - the human settled on 2026-09-23 that
 * those are two different things, a Collection being what organises items
 * inside My Library. These screens therefore talk to `/api/vocabulary/decks`
 * and to nothing in the library's relationship layer.
 *
 * The desktop "Add word modal" and the phone "Add word mobile" are the same
 * fields in the same order; the stylesheet decides which shape they take, so
 * the two cannot drift.
 */
import { esc } from './html.js';
import { icon } from './phosphor.js';
import { contentCover } from './cover.js';

/* Whether the word the learner typed is one the catalogue knows. The frame
   draws this line in the affirmative only - "Có trong từ điển · đã điền sẵn" -
   so a word the catalogue does not have says nothing rather than accusing the
   learner of inventing it. */
function dictionaryLine(c, found) {
  if (!found) return '';
  return `<span class="word-add__found">${icon('check-circle', { size: 16, filled: true })}${esc(c.addWordInDictionary)}</span>`;
}

function field(label, body, { hint = '' } = {}) {
  return `<label class="word-add__field"><span class="word-add__label">${esc(label)}${
    hint ? `<span class="word-add__hint"> · ${esc(hint)}</span>` : ''
  }</span>${body}</label>`;
}

/* A deck's cover is the colour the learner chose, which the stylesheet turns
   into a gradient. A deck with no chosen cover falls back to the app's own
   drawn cover, so an older set is never blank. */
function deckArt(deck, extra = '') {
  return deck?.cover
    ? `<span class="deck-row__art ${extra}" data-cover="${esc(deck.cover)}"></span>`
    : `<span class="deck-row__art ${extra}">${contentCover({ id: String(deck?.id || deck?.title || ''), title: deck?.title || '', material: 'collection' })}</span>`;
}

function setRow(c, deck, { chosen = false, action = '' } = {}) {
  return `<button type="button" class="deck-row"${action ? ` ${action}` : ''} aria-pressed="${chosen}"${chosen ? ' data-chosen="true"' : ''}>${deckArt(deck)}<span class="deck-row__title">${esc(deck.title)}</span>${icon(chosen ? 'check-circle' : 'circle', { size: 21, filled: chosen })}</button>`;
}

/* Frame 22: which of the learner's sets this word goes into. */
export function saveToDeckSheet(c, { word, note = '', decks = [], chosen = '', unavailable = false }) {
  const rows = decks
    .map((deck) =>
      setRow(c, deck, {
        chosen: String(deck.id) === String(chosen),
        action: `data-deck-pick="${esc(deck.id)}"`,
      }),
    )
    .join('');
  const into = decks.find((deck) => String(deck.id) === String(chosen));
  return `<div class="deck-sheet" role="dialog" aria-modal="true" aria-label="${esc(c.saveToDeck)}"><button type="button" class="deck-sheet__scrim" data-deck-close aria-label="${esc(c.back)}"></button><section class="deck-sheet__sheet"><span class="deck-sheet__grab" aria-hidden="true"></span><div class="deck-sheet__head"><strong>${esc(
    String(c.saveWordTitle).replace('{w}', word),
  )}</strong>${note ? `<span>${esc(note)}</span>` : ''}</div><div class="deck-sheet__rows">${unavailable ? `<p class="word-add__note">${esc(c.decksUnavailable)}</p>` : rows}<button type="button" class="deck-row deck-row--new" data-deck-new><span class="deck-row__art deck-row__art--new">${icon('plus', { size: 17 })}</span><span class="deck-row__title">${esc(c.createDeck)}</span></button></div><button type="button" class="primary deck-sheet__save"${into ? '' : ' disabled'} data-deck-save>${esc(
    into ? String(c.saveIntoDeck).replace('{d}', into.title) : c.saveToDeck,
  )}</button></section></div>`;
}

/* Frames 23 and 24: the word, what it means, a sentence if there is one, and
   which set it joins. */
export function addWordScreen(c, state) {
  const { word = '', meaning = '', example = '', decks = [], chosen = '', found = false, again = true, busy = false, unavailable = false } = state;
  const into = decks.find((deck) => String(deck.id) === String(chosen));
  return `<section class="word-add"><header class="word-add__head"><button type="button" class="quiet" data-add-cancel>${esc(c.cancel)}</button><strong>${esc(c.addWord)}</strong><button type="button" class="quiet word-add__go" data-add-save${word.trim() && meaning.trim() && !busy ? '' : ' disabled'}>${esc(c.add)}</button></header><div class="word-add__body">${field(
    c.addWordWord,
    `<input type="text" class="word-add__input word-add__input--word" data-add-word value="${esc(word)}" autocomplete="off" spellcheck="false">${dictionaryLine(c, found)}`,
  )}${field(c.addWordMeaning, `<input type="text" class="word-add__input" data-add-meaning value="${esc(meaning)}" autocomplete="off">`)}${field(
    c.addWordExample,
    `<input type="text" class="word-add__input word-add__input--serif" data-add-example value="${esc(example)}" autocomplete="off">`,
    { hint: c.optional },
  )}${field(
    c.deck,
    `<button type="button" class="word-add__deck" data-add-pick-deck${unavailable ? ' disabled' : ''}>${
      into ? deckArt(into) : '<span class="deck-row__art"></span>'
    }<span>${esc(unavailable ? c.decksUnavailable : into ? into.title : c.chooseDeck)}</span>${icon('caret-up-down', { size: 17 })}</button>`,
  )}<label class="word-add__again"><input type="checkbox" data-add-again${again ? ' checked' : ''}><span>${esc(c.addAnother)}</span></label></div></section>`;
}

/* Frame 25: a new set. Its cover is the app's own - drawn from the set's
   identity, the way every other cover in the room is drawn - because a chosen
   colour is a stored thing and nothing stores it yet (UI_BACKEND_GAPS.md). */
export function createDeckScreen(c, state) {
  const { title = '', languages = [], language = '', locked = false, busy = false, covers = [], cover = '', unavailable = false } = state;
  const swatches = covers.length
    ? `<div class="deck-new__covers" role="group" aria-label="${esc(c.deckCover)}">${covers
        .map(
          (name) =>
            `<button type="button" class="deck-new__cover-pick" data-cover="${esc(name)}" data-deck-cover="${esc(name)}" aria-pressed="${name === cover}" aria-label="${esc(name)}"></button>`,
        )
        .join('')}</div>`
    : '';
  const options = languages
    .map(
      (option) =>
        `<button type="button" class="deck-new__lang" data-deck-language="${esc(option.code)}" aria-pressed="${option.code === language}"${locked ? ' disabled' : ''}>${esc(option.label)}</button>`,
    )
    .join('');
  return `<section class="deck-new"><header class="word-add__head"><button type="button" class="quiet" data-deck-cancel>${esc(c.cancel)}</button><strong>${esc(c.newDeck)}</strong><button type="button" class="quiet word-add__go" data-deck-create${title.trim() && language && !busy && !unavailable ? '' : ' disabled'}>${esc(c.create)}</button></header><div class="word-add__body">${
    unavailable ? `<p class="word-add__note">${esc(c.decksUnavailable)}</p>` : ''
  }<div class="deck-new__cover"${cover ? ` data-cover="${esc(cover)}"` : ''}>${
    cover ? '' : contentCover({ id: String(title || 'new'), title: title || '', material: 'collection' })
  }<span class="deck-new__cover-title">${esc(title)}</span></div>${field(
    c.deckName,
    `<input type="text" class="word-add__input" data-deck-title value="${esc(title)}" autocomplete="off">`,
  )}${field(c.deckLanguage, `<div class="deck-new__langs">${options}</div>${locked ? `<span class="word-add__note">${esc(c.deckLanguageLocked)}</span>` : ''}`)}${swatches ? field(c.deckCover, swatches) : ''}</div></section>`;
}
