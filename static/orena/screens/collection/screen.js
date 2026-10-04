/* Collection Detail (frame 21, D2 §6): a curated vocabulary pack (concept A, C6 §2.1) - cover,
   progress, "Start review" scoped to it, and its word list. Explicit Add all
   reuses saved vocabulary; browsing never creates a learner relationship. Data:
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
import { langAttr, langSpan } from '../../kit/lang.js';
import { api } from '../../infrastructure/api.js';
import { languages } from '../../copy/index.js';
import { meaningLanguageLabel } from '../../product/vocabulary-meaning.js';
import { shellCopy } from '../../copy/shell.js';
import { t } from './copy.js';
import { collectionViewModel } from './model.js';
import { readCollection, keepCollectionWords } from './actions.js';

/* The row opens Word Detail (cw.wc.onOpen) and also carries a real, separately-activatable play
   control - two interactive targets on one row. HTML forbids nesting interactive content inside
   a <button> (a real <button> containing a role="button" span is the "nested button" anti-pattern:
   invalid content model, broken screen-reader/keyboard semantics, flagged by axe/Lighthouse), so
   the row itself is a non-interactive-tag container with role="button"/tabindex, matching the
   already-correct, already-shared pattern My Library's languageRow() uses for the same "row with a
   nested play button" shape (static/orena/screens/library/screen.js) - a non-button row plus a real
   <button> for play, never a role="button" span. */
/* The kit's small tag naming a meaning's language when it is not the support language (D-124). */
function meaningTag(language) {
  const label = meaningLanguageLabel(language, languages().support, languages().ui);
  return label ? html` <span class="o-tag">${label}</span>` : '';
}

function wordRowMarkup(word) {
  const badge = word.isNew
    ? html`<span class="s-collection-word__new">${t('collectionNewBadge')}</span>`
    : masteryBars({ filled: word.filled, total: word.total, color: 'var(--green)' });
  return html`<div class="s-collection-word" role="button" tabindex="0" data-word-open data-word="${word.id}">
    <span class="s-collection-word__body">
      <span class="s-collection-word__title" lang="${langAttr(word.lang)}">${word.word}</span>
      <span class="s-collection-word__meaning"><span lang="${langAttr(word.meaningLanguage || languages().support)}">${word.meaning}</span>${meaningTag(word.meaningLanguage)}</span>
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
    title: langSpan(model.title, model.language),
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
          <button type="button" class="s-collection-cta" data-review${model.savedCount ? '' : raw(' disabled')}>${t.plural('collectionStartReview', model.savedCount)}</button>
          <button type="button" class="s-collection-save" data-save${model.missingCount ? '' : raw(' disabled')}>${t(model.missingCount ? 'collectionSave' : 'collectionSaved')}</button>
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

  let data = await readCollection(collectionId, api.vocabularyLibraryCollection);
  if (!ctx.isCurrent()) return;
  const { support } = languages();
  let model = collectionViewModel(data, support);

  function paint() {
    model = collectionViewModel(data, support);
    mount(element, screenMarkup(model));
  }

  paint();
  let saving = false;
  const click = async (event) => {
    const target = event.target.closest('button, [data-word-open]');
    if (!target || !element.contains(target)) return;
    if (target.hasAttribute('data-back')) ctx.back();
    else if (target.hasAttribute('data-review') && model.savedCount && !saving) {
      ctx.go(ctx.href('review', {}, { collection: model.id }));
    } else if (target.hasAttribute('data-save') && !saving && model.missingCount) {
      saving = true;
      target.disabled = true;
      target.textContent = t('collectionSaving', { n: 0, total: model.missingCount });
      element.querySelector('[data-review]').disabled = true;
      try {
        const result = await keepCollectionWords(data, {
          language: ctx.context.language,
          save: api.saveLibraryVocabulary,
          isCurrent: ctx.isCurrent,
          onProgress: (n, total) => {
            if (ctx.isCurrent()) target.textContent = t('collectionSaving', { n, total });
          },
        });
        if (!ctx.isCurrent()) return;
        // Each successful word is already persisted. Retry reads that truth and
        // skips it, preserving its schedule and all previously held words.
        data.progress = { ...data.progress, learned_count: data.items.filter((card) => card.saved).length };
        toast(result.error ? t('collectionSaveFailed', { n: result.added, remaining: result.remaining })
          : t.plural('collectionAdded', result.added));
        paint();
      } catch {
        if (ctx.isCurrent()) { toast(t('collectionActionFailed')); paint(); }
      } finally { saving = false; }
    } else if (target.hasAttribute('data-word-play')) {
      event.stopPropagation();
      playWord(target, target.dataset.word);
    } else if (target.hasAttribute('data-word-open')) {
      ctx.go(ctx.href('word', { id: target.dataset.word }));
    }
  };
  element.addEventListener('click', click);
  const keydown = (event) => {
    if (!event.target.matches('[data-word-open]') || !['Enter', ' '].includes(event.key)) return;
    event.preventDefault();
    ctx.go(ctx.href('word', { id: event.target.dataset.word }));
  };
  element.addEventListener('keydown', keydown);
  return () => {
    element.removeEventListener('click', click);
    element.removeEventListener('keydown', keydown);
  };
}
