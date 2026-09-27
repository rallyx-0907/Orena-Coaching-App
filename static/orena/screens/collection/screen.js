/* Collection Detail (frame 21, D2 §6): a curated vocabulary pack (concept A, C6 §2.1) - cover,
   progress, "Start review" scoped to it, and its word list. Data:
   GET /api/vocabulary/library/collections/{id} (app.py becoming_vocabulary_library_collection_
   detail); word meanings read the learner's support language from the card's own meanings[]
   (model.js#supportMeaning), never a hardcoded field. Saving one word is a different screen's
   job (Word Detail); this frame draws no per-word save control (D2 §6 word-row composition). */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { loadingMarkup, emptyMarkup } from '../../kit/states.js';
import { toast } from '../../kit/toast.js';
import { heroMedia, masteryBars } from '../../kit/components.js';
import { api } from '../../infrastructure/api.js';
import { languages } from '../../copy/index.js';
import { shellCopy } from '../../copy/shell.js';
import { t } from './copy.js';
import { collectionViewModel } from './model.js';

/* The row opens Word Detail (cw.wc.onOpen) and also carries a real, separately-activatable play
   control - two interactive targets on one row. HTML forbids nesting interactive content inside
   a <button> (a real <button> containing a role="button" span is the "nested button" anti-pattern:
   invalid content model, broken screen-reader/keyboard semantics, flagged by axe/Lighthouse), so
   the row itself is a non-interactive-tag container with role="button"/tabindex, matching the
   already-correct, already-shared pattern My Library's languageRow() uses for the same "row with a
   nested play button" shape (static/orena/screens/library/screen.js) - a non-button row plus a real
   <button> for play, never a role="button" span. */
function wordRowMarkup(word) {
  const badge = word.isNew
    ? html`<span class="s-collection-word__new">${t('collectionNewBadge')}</span>`
    : masteryBars({ filled: word.filled, total: word.total, color: 'var(--green)' });
  return html`<div class="s-collection-word" role="button" tabindex="0" data-word-open data-word="${word.id}">
    <span class="s-collection-word__body">
      <span class="s-collection-word__title">${word.word}</span>
      <span class="s-collection-word__meaning">${word.meaning}</span>
    </span>
    ${badge}
    <button type="button" class="s-collection-word__play" data-word-play data-word="${word.id}" aria-label="${t('collectionPlay')}">${raw(icon('volume-2', { size: 18 }))}</button>
  </div>`;
}

function screenMarkup(model) {
  const pill = model.level ? t('collectionPillLevel', { level: model.level }) : t('collectionPillPlain');
  const meta = `${t.plural('collectionWordCount', model.wordCount)} · ${t('collectionMetInSources', { n: model.metInSources })}`;
  const hero = heroMedia({
    image: '', // rule 40: VocabularyCollection carries no cover-image field (backend gap)
    height: 'auto',
    titleSize: 26,
    pill,
    title: model.title,
    meta,
    dataset: { hero: 'collection' },
  });
  return html`<div class="s-collection">
    <button type="button" class="o-iconbtn" data-back aria-label="${shellCopy('back')}">${raw(icon('arrow-left', { size: 19 }))}</button>
    <div class="s-collection-grid">
      <div class="s-collection-main">
        ${hero}
        <div class="s-collection-bar"><span style="width:${model.percent}%"></span></div>
        <div class="s-collection-actions">
          <button type="button" class="s-collection-cta" data-review>${t.plural('collectionStartReview', model.wordCount)}</button>
          <button type="button" class="s-collection-save" data-save>${t('collectionSave')}</button>
        </div>
        ${model.description ? html`<p class="s-collection-desc">${model.description}</p>` : ''}
      </div>
      <div class="s-collection-words">
        <div class="s-collection-words-heading">${t('collectionWordsHeading')}</div>
        ${model.words.length
          ? model.words.map(wordRowMarkup)
          : emptyMarkup({ text: t('collectionEmptyWords'), iconName: 'inbox' })}
      </div>
    </div>
  </div>`;
}

async function playWord(button, word) {
  if (button.getAttribute('aria-disabled') === 'true') return;
  button.setAttribute('aria-disabled', 'true');
  try {
    const found = await api.wordAudio(word);
    if (found?.available && found.url) {
      await new Audio(found.url).play();
    } else {
      toast(t('collectionAudioUnavailable'), { iconName: 'volume-2' });
    }
  } catch {
    toast(t('collectionAudioUnavailable'), { iconName: 'volume-2' });
  } finally {
    button.removeAttribute('aria-disabled');
  }
}

export default async function collectionScreen(element, ctx) {
  await useStyles('screens/collection/collection.css');
  const collectionId = ctx.params?.id || '';
  mount(element, html`<div class="s-collection">${loadingMarkup(t('collectionLoading'))}</div>`);

  const data = await api.vocabularyLibraryCollection(collectionId, { limit: 5000 });
  if (!ctx.isCurrent()) return;
  const { support } = languages();
  const model = collectionViewModel(data, support);

  mount(element, screenMarkup(model));
  element.querySelector('[data-back]').addEventListener('click', () => ctx.back());
  element.querySelector('[data-review]').addEventListener('click', () => {
    ctx.go(ctx.href('review', {}, { collection: model.id }));
  });
  element.querySelector('[data-save]').addEventListener('click', () => {
    // Backend gap: no endpoint or device-memory concept saves/bookmarks a whole curated
    // collection (concept A) - only an individual word (POST /api/library/vocabulary). See
    // the surface report ("colSave") for why this stays a toast rather than an invented
    // persistence mechanism.
    toast(t('collectionSaveUnavailable'));
  });
  // The row is a role="button" div (not a real <button> - see wordRowMarkup's comment), so its
  // open behaviour is wired by hand: click, and Enter/Space on keydown (the same activation a
  // native button gives for free). Both ignore an event whose target is the nested play button -
  // that control is a real <button> and handles its own activation (including its own native
  // Enter/Space), and its click handler already stops the event from bubbling here too.
  element.querySelectorAll('[data-word-open]').forEach((row) => {
    const open = () => ctx.go(ctx.href('word', { id: row.dataset.word }));
    row.addEventListener('click', (event) => {
      if (event.target.closest('[data-word-play]')) return;
      open();
    });
    row.addEventListener('keydown', (event) => {
      if (event.target.closest('[data-word-play]')) return;
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      open();
    });
  });
  element.querySelectorAll('[data-word-play]').forEach((play) => {
    play.addEventListener('click', (event) => {
      event.stopPropagation();
      playWord(play, play.dataset.word);
    });
  });
}
