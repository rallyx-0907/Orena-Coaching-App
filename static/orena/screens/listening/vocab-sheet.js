/* Vocabulary Focus (frame 54, D-091): the contextual terms for one Listening segment - this
   lesson's own real catalogue vocabulary (`catalog.vocabulary`, matched into the segment's real
   text by model.js#vocabularyForSegment), each resolved through the same Quick Sheet contract
   (`POST /api/dictionary/word-detail`) the shared word sheet uses, so "no AI provider" answers the
   same honest `available:false` fallback here as everywhere else (rule 40) - never a second,
   invented meaning source. Not one of the three shared overlays (quick-sheet/mic/lesson-complete);
   this panel is Listening's own, since no other surface in this wave draws it.

   Saving is the library's own vocabulary route; its `source_kind` is `manual` because the real API
   accepts only manual | dictionary | feedback | strength | reading | feed | collection (a
   `listening` value is a 422). */
import { openSheet } from '../../kit/overlay.js';
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { langAttr } from '../../kit/lang.js';
import { toast } from '../../kit/toast.js';
import { api } from '../../infrastructure/api.js';
import { shellCopy as s } from '../../copy/shell.js';
import { t } from './copy.js';
import { lookupContext } from './model.js';

async function resolveTerm(term, { lang, support, context }) {
  let detail = null;
  try {
    detail = await api.wordDetail({ depth: 'sheet', text: term, context: lookupContext(term, context), source_language: lang, target_language: support });
  } catch {
    detail = null;
  }
  return {
    word: term,
    reading: detail?.pinyin || detail?.ipa || '',
    meaning: detail?.available ? (detail.contextMeaning || '') : '',
    saved: Boolean(detail?.saved),
  };
}

export async function openVocabFocus(ctx, { label, terms, lang, support, context, onPlay }) {
  const words = [...new Set((terms || []).filter(Boolean))];
  let rows = words.map((word) => ({ word, reading: '', meaning: '', saved: false }));
  let alive = true;
  let sheetEl = null;

  function rowMarkup(row, index) {
    return html`<div class="s-vocab__row">
      <button type="button" class="s-vocab__play" data-play="${index}" aria-label="${t('hearInContext')}" title="${t('hearInContext')}">${raw(icon('play', { size: 14 }))}</button>
      <div class="s-vocab__main">
        <div class="s-vocab__word"><span lang="${langAttr(lang)}">${row.word}</span>${row.reading ? html` <span class="s-vocab__reading">${row.reading}</span>` : ''}</div>
        ${row.meaning ? html`<div class="s-vocab__meaning">${row.meaning}</div>` : ''}
      </div>
      <button type="button" class="s-vocab__save" data-save="${index}" aria-pressed="${String(row.saved)}">${row.saved ? t('saved') : t('save')}</button>
    </div>`;
  }

  function paint() {
    if (!sheetEl || !alive) return;
    mount(
      sheetEl,
      html`<div class="s-vocab__head">
        <div><div class="s-vocab__title">${t('vocabularyFocus')}</div><div class="s-vocab__label">${label}</div></div>
        <button type="button" class="o-iconbtn o-iconbtn--close" data-sheet-close aria-label="${s('close')}">${raw(icon('x', { size: 17 }))}</button>
      </div>
      <div class="s-vocab__body" data-scroll-region>
        ${rows.length ? rows.map(rowMarkup) : html`<div class="s-vocab__empty">${t('noFocusTerms')}</div>`}
      </div>`,
    );
    bind();
  }

  function bind() {
    sheetEl.querySelector('[data-sheet-close]')?.addEventListener('click', () => handle.close());
    sheetEl.querySelectorAll('[data-play]').forEach((button) => {
      button.addEventListener('click', () => onPlay?.());
    });
    sheetEl.querySelectorAll('[data-save]').forEach((button) => {
      button.addEventListener('click', () => toggleSave(Number(button.dataset.save)));
    });
  }

  async function toggleSave(index) {
    const row = rows[index];
    if (!row) return;
    try {
      if (row.saved) {
        await api.deleteLibraryVocabulary(row.word);
        row.saved = false;
        toast(t('removedToast'));
      } else {
        await api.saveLibraryVocabulary({
          word: row.word,
          phonetic: row.reading,
          definition: row.meaning,
          source_kind: 'manual',
          source_fragment: (context || '').slice(0, 1200),
        });
        row.saved = true;
        toast(t('saved'));
      }
      paint();
    } catch {
      if (alive) toast(t('saveFailed'));
    }
  }

  const handle = openSheet({
    label: t('vocabularyFocus'),
    className: 's-vocab',
    render(element) {
      sheetEl = element;
      paint();
      (async () => {
        const resolved = await Promise.all(rows.map((row) => resolveTerm(row.word, { lang, support, context })));
        if (!alive) return;
        rows = resolved;
        paint();
      })();
      return () => {
        alive = false;
      };
    },
  });
  return handle;
}
