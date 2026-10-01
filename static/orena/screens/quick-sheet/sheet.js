/* The Word Quick Sheet (frame 53) and the Sentence Quick Sheet (frame 57) - D-066's one overlay
   for "what does this mean, right here": tap a word or select a sentence, anywhere in the app, and
   the same sheet opens over it. No route: `openWordSheet`/`openSentenceSheet` are called by a
   workspace (Reader, Listening's transcript, …) with the selection and where it came from.

   Both sheets share the shell kit/overlay.js already gives every sheet (`.o-sheet`, the design's
   own `--sheet-*` device variables: a 440px right panel on a desk, a bottom sheet on a phone) - only
   the body differs, so one module and one stylesheet serve both (E5 §3.4/§4.4: the two frames'
   header/action-button signatures are pixel-identical).

   Data: `POST /api/dictionary/word-detail` (`depth:'sheet'`) and `POST /api/dictionary/sentence-sheet`
   - this sandbox has no AI provider key, so both answer their documented `available:false` fallback
   (captured: scripts/fixtures/api/word_detail_sheet(.zh).json, sentence_sheet(.zh).json); the frame's
   own "not prepared" branches (qsNoWC / each tab's empty state) are exactly that fallback, not an
   error screen (rule 40). Saving a word reuses `POST /api/library/vocabulary` (D-091 precedent,
   `screens/word/model.js`); the Sentence Quick Sheet's own "Save highlight" has no backend
   equivalent at sentence grain (`/api/library/items`' `kind` is a content domain - word / grammar /
   reading / listening / writing / speaking - never a single sentence) and is not built here
   (recorded in this pass's report and `docs/project/UI_BACKEND_GAPS.md`); its Vocabulary tab's
   per-term saves are real (the same `/api/library/vocabulary`). Notes are device memory
   (`AGENTS.md` §7: learner-owned data with no server schema decision yet is device memory by
   design), like kept-language and drafts elsewhere in this build - not a fabricated server save. */
import { openSheet } from '../../kit/overlay.js';
import { html, mount, raw, cls } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { toast } from '../../kit/toast.js';
import { langAttr } from '../../kit/lang.js';
import { masteryBars } from '../../kit/components.js';
import { shellCopy as s } from '../../copy/shell.js';
import { href } from '../../shell/routes.js';
import { languages } from '../../copy/index.js';
import { api } from '../../infrastructure/api.js';
import { askOrena } from '../../shell/agent-bridge.js';
import { t } from './copy.js';
import {
  contextFor,
  surfaceFor,
  posLabel,
  mapWordCard,
  wordSavePayload,
  wordRestorePayload,
  mapSentenceSheet,
  vocabSavePayload,
  noteKeyFor,
  noteTypeColorKey,
  loadNotes,
  addNote,
  deleteNote,
} from './model.js';
import { pullIntoDevice, scheduleAnnotationPush, noteRemoved } from '../reader/annotations-sync.js';
import { keepProvenance } from '../../product/account-records.js';

let audio = null;
function playUrl(url) {
  try {
    audio?.pause();
    audio = new Audio(url);
    audio.play().catch(() => {});
  } catch {
    /* A device that cannot play audio just does not play it. */
  }
}

function askWordDeeper(word, lang, source) {
  askOrena({
    surface: surfaceFor(source, 'vocabulary.word'),
    content_id: source?.content_id || undefined,
    selected_item: { type: 'word', text: word, lang },
  });
}

function askSentenceDeeper(sentence, lang, source) {
  askOrena({
    surface: surfaceFor(source, 'vocabulary.my_language'),
    content_id: source?.content_id || undefined,
    selected_item: { type: 'sentence', text: sentence, lang },
  });
}

/* ---------------------------------------------------------------------- Word Quick Sheet -- */

async function fetchSavedItem(word) {
  try {
    const page = await api.libraryVocabulary({ query: word, limit: 5, order: 'word' });
    const norm = String(word).trim().toLowerCase();
    return (page?.items || []).find((row) => String(row.word || '').trim().toLowerCase() === norm) || null;
  } catch {
    return null;
  }
}

/* `source.title` is optional (measured live against the source: "Source sentence · {{title}}" is
   the article/lesson title the word was met in, not a timestamp as the frame's own template
   placeholder name suggested) - a caller that knows it passes it; one that does not just gets the
   bare "Source sentence" label, never a guessed one. */
export async function openWordSheet(ctx = {}, { word, lang, sentence = '', context = '', source = null, onOpen, onClose } = {}) {
  await useStyles('screens/quick-sheet/quick-sheet.css');
  const target = String(word || '').trim();
  if (!target) return null;
  const support = languages().support;
  let alive = true;
  let sheetEl = null;
  let detail = null;
  let item = null;
  let card = mapWordCard(target, {});
  let busy = false;

  function posMarkup() {
    const label = posLabel(card.pos, t);
    return html`<span class="s-qs__chip">${card.pos ? label.text : t('posUnknown')}</span>`;
  }

  function metaMarkup() {
    return html`<div class="s-qs__meta">
      ${card.reading ? html`<span class="s-qs__ipa">${card.reading}</span>` : ''}
      ${posMarkup()}
      ${card.level ? html`<span class="s-qs__chip s-qs__chip--level">${card.level}</span>` : ''}
    </div>`;
  }

  function strokeMarkup() {
    if (card.script !== 'hanzi') return '';
    return html`<div class="s-qs__stroke">
      <div class="s-qs__eyebrow">${t('strokeOrder')}</div>
      <button type="button" class="o-btn o-btn--secondary o-btn--sm" data-practise-strokes>${raw(icon('pencil', { size: 16 }))} ${t('practiseStrokes')}</button>
    </div>`;
  }

  function masteryMarkup() {
    if (!card.hasSchedule) return '';
    return html`<div class="s-qs__mastery">
      ${masteryBars({ filled: card.filled })}
      <span class="s-qs__stage">${card.stageKey ? t(card.stageKey) : ''}</span>
      ${card.due ? html`<span class="s-qs__due">${card.due.key === 'dueToday' ? t('dueToday') : t.plural('dueInDays', card.due.n)}</span>` : ''}
    </div>`;
  }

  function contentMarkup() {
    return html`
      <div class="s-qs__row">
        <div class="s-qs__wordblock">
          <div class="s-qs__word" lang="${langAttr(card.script === 'hanzi' ? 'zh' : 'en')}">${card.word}</div>
          ${metaMarkup()}
        </div>
        <div class="s-qs__icons">
          <button type="button" class="s-qs__iconbtn" data-play aria-label="${t('playWord')}">${raw(icon('volume-2', { size: 19 }))}</button>
          <button type="button" class="s-qs__iconbtn" data-save style="background:${card.savedBg};color:${card.savedColor}" aria-label="${t(card.saved ? 'unsaveWord' : 'saveWord')}">${raw(icon('bookmark-check', { size: 19 }))}</button>
        </div>
      </div>
      <div class="s-qs__card">
        <div class="s-qs__meaning">${card.meaning}</div>
      </div>
      ${card.example ? html`<div class="s-qs__example" lang="${langAttr(lang)}">${card.exampleParts.map((p) => (p.hit ? html`<mark>${p.value}</mark>` : p.value))}</div>` : ''}
      ${strokeMarkup()}
      ${masteryMarkup()}
    `;
  }

  function fallbackMarkup() {
    return html`
      <div class="s-qs__row">
        <div class="s-qs__wordblock">
          <div class="s-qs__word" lang="${langAttr(card.script === 'hanzi' ? 'zh' : 'en')}">${card.word}</div>
          <div class="s-qs__meta"><span class="s-qs__ipa">${card.reading || '—'}</span>${posMarkup()}</div>
        </div>
      </div>
      <div class="s-qs__card">
        <div class="s-qs__eyebrow">${t('meaningHere')}</div>
        <div class="s-qs__meaning">${t('meaningNotPrepared')}</div>
      </div>
      ${sentence ? html`<div class="s-qs__source"><div class="s-qs__eyebrow">${sourceLabel()}</div><div class="s-qs__source-text" lang="${langAttr(lang)}">${sentence}</div></div>` : ''}
      <div class="s-qs__notice">${t('noGlossNotice')}</div>
    `;
  }

  // "Source sentence" alone, or "Source sentence · {title}" once the caller has told us where the
  // word was met (`source.title`, optional - a caller with no title to give just gets the label).
  function sourceLabel() {
    const title = String(source?.title || '').trim();
    return title ? `${t('sourceSentence')} · ${title}` : t('sourceSentence');
  }

  function bodyMarkup() {
    return html`
      ${card.hasContent ? contentMarkup() : fallbackMarkup()}
      <div class="s-qs__actions">
        <button type="button" class="o-btn o-btn--primary s-qs__grow" data-save-cta>${t('saveWordCta')}</button>
        <button type="button" class="s-qs__ask s-qs__grow" data-ask>${raw(icon('audio-lines', { size: 20 }))} ${t('askDeeper')}</button>
      </div>
      <button type="button" class="s-qs__why" data-why>${t('whyHere')} — <span class="s-qs__why-text">${card.whyHere || t('whyHereFallback')}</span></button>
      ${card.saved ? html`<button type="button" class="s-qs__detail" data-detail>${t('fullWordDetail')} ${raw(icon('arrow-right', { size: 16 }))}</button>` : ''}
    `;
  }

  function headMarkup() {
    return html`<div class="s-qs__head"><div class="s-qs__label">${t('labelWord')}</div><button type="button" class="o-iconbtn o-iconbtn--close" data-sheet-close aria-label="${s('close')}">${raw(icon('x', { size: 17 }))}</button></div>`;
  }

  function paint() {
    if (!sheetEl || !alive) return;
    mount(sheetEl, html`${headMarkup()}<div class="s-qs__body" data-scroll-region>${bodyMarkup()}</div>`);
    // `mount()` replaces the sheet's children wholesale, destroying whatever was just focused
    // (e.g. the button that triggered this repaint) - without this, focus falls to <body> and
    // kit/overlay.js's Escape/Tab-trap keydown listener, bound to the sheet element, never fires
    // again for the rest of this sheet's open lifetime.
    if (!sheetEl.contains(document.activeElement)) sheetEl.focus({ preventScroll: true });
    bind();
  }

  function bind() {
    sheetEl.querySelector('[data-sheet-close]')?.addEventListener('click', () => handle.close());
    sheetEl.querySelector('[data-play]')?.addEventListener('click', () => {
      if (card.audioUrl) playUrl(card.audioUrl);
      else toast(t('noAudioSource'));
    });
    sheetEl.querySelector('[data-save]')?.addEventListener('click', toggleSave);
    sheetEl.querySelector('[data-save-cta]')?.addEventListener('click', toggleSave);
    sheetEl.querySelector('[data-ask]')?.addEventListener('click', () => askWordDeeper(card.word, lang, source));
    sheetEl.querySelector('[data-why]')?.addEventListener('click', () => askWordDeeper(card.word, lang, source));
    sheetEl.querySelector('[data-detail]')?.addEventListener('click', () => {
      if (typeof ctx.go === 'function') ctx.go(href('word', { id: card.word }));
    });
    sheetEl.querySelector('[data-practise-strokes]')?.addEventListener('click', openStroke);
  }

  async function toggleSave() {
    if (busy) return;
    busy = true;
    try {
      if (card.saved) {
        const payload = wordRestorePayload(item);
        await api.deleteLibraryVocabulary(card.word);
        item = null;
        detail = detail ? { ...detail, saved: false } : detail;
        card = mapWordCard(card.word, { detail, item });
        paint();
        toast(t('removedToast'), payload ? { undo: async () => {
          const restored = await api.restoreLibraryVocabulary(payload).catch(() => null);
          item = restored?.item || item;
          detail = detail ? { ...detail, saved: true } : detail;
          card = mapWordCard(card.word, { detail, item });
          paint();
        }, undoLabel: s('undo') } : {});
      } else {
        const saved = await api.saveLibraryVocabulary(wordSavePayload(card, sentence, source));
        // Where the word was met goes to the account beside the word itself (D4 I12d).
        void keepProvenance({ term: card.word, source, sentence });
        item = saved?.item || item;
        detail = detail ? { ...detail, saved: true } : detail;
        card = mapWordCard(card.word, { detail, item });
        paint();
        toast(t('savedToast'));
      }
    } catch {
      /* The sheet stays as it was; nothing was silently marked saved/unsaved. */
    } finally {
      busy = false;
    }
  }

  async function openStroke() {
    await useStyles('screens/word/word.css');
    const { mountStrokeSheet } = await import('../word/stroke-sheet.js');
    const titleWord = card.reading ? `${card.word} · ${card.reading}` : card.word;
    openSheet({
      label: t('strokePracticeTitle', { word: titleWord }),
      render: (strokeEl, strokeHandle) =>
        mountStrokeSheet(strokeEl, strokeHandle, {
          word: card.word,
          titleWord,
          chineseStrokeOrder: api.chineseStrokeOrder,
          t,
          closeLabel: s('close'),
        }),
    });
  }

  let handle = null;
  if (!ctx.isCurrent || ctx.isCurrent()) {
    handle = openSheet({
      label: t('labelWord'),
      className: 's-qs s-qs--word',
      render(element) {
        sheetEl = element;
        paint();
        onOpen?.();
        (async () => {
          const ctxText = contextFor(target, context || sentence);
          try {
            detail = await api.wordDetail({ depth: 'sheet', text: target, context: ctxText, source_language: lang, target_language: support });
          } catch {
            detail = null;
          }
          if (!alive) return;
          if (detail?.saved) item = await fetchSavedItem(target);
          if (!alive) return;
          card = mapWordCard(target, { detail, item });
          paint();
        })();
        return () => {
          alive = false;
        };
      },
      onClose: () => onClose?.(),
    });
  }
  return handle;
}

/* ------------------------------------------------------------------- Sentence Quick Sheet -- */

export async function openSentenceSheet(ctx = {}, { sentence, lang, context = '', source = null, onOpen, onClose, onNote } = {}) {
  await useStyles('screens/quick-sheet/quick-sheet.css');
  const target = String(sentence || '').trim();
  if (!target) return null;
  const support = languages().support;
  const owner = ctx.context?.owner || 'local';
  const storage = (() => {
    try {
      return window.localStorage;
    } catch {
      return null;
    }
  })();
  const key = noteKeyFor(target, source);
  let alive = true;
  let sheetEl = null;
  let sheetData = { available: false, translation: '', structure: [], vocabulary: [] };
  let tab = 'Translation';
  let noteType = 'factual';
  let noteDraft = '';

  function tabsMarkup() {
    const tabs = [
      ['Translation', t('tabTranslation')],
      ['Structure', t('tabStructure')],
      ['Vocabulary', t('tabVocabulary')],
      ['Note', t('tabNote')],
    ];
    return html`<div class="s-qs__tabs">${tabs.map(([id, label]) => html`<button type="button" class="${cls('s-qs__tab', tab === id && 'is-active')}" data-tab="${id}" aria-selected="${tab === id}">${label}</button>`)}</div>`;
  }

  function translationMarkup() {
    return html`<div class="s-qs__panel">${sheetData.available && sheetData.translation ? sheetData.translation : t('translationNotPrepared')}</div>`;
  }

  function structureMarkup() {
    if (!sheetData.available || !sheetData.structure.length) return html`<div class="s-qs__panel">${t('structureNotPrepared')}</div>`;
    return html`<div class="s-qs__panel">${sheetData.structure.map((s2) => html`<div class="s-qs__structure-row"><b>${s2.chunk}</b>${s2.role ? html` — ${s2.role}` : ''}</div>`)}</div>`;
  }

  function vocabRow(item, index) {
    return html`<div class="s-qs__vocab">
      <div class="s-qs__vocab-body"><span class="s-qs__vocab-term">${item.term}</span><span class="s-qs__vocab-meaning">${item.meaning}</span></div>
      <button type="button" class="${cls('s-qs__vocab-save', item.saved && 'is-saved')}" data-vocab-save="${index}">${item.saved ? t('unsaveVocab') : t('saveVocab')}</button>
    </div>`;
  }

  function vocabularyMarkup() {
    if (!sheetData.available || !sheetData.vocabulary.length) return html`<div class="s-qs__empty">${t('vocabEmpty')}</div>`;
    return html`<div class="s-qs__vocab-list">${sheetData.vocabulary.map((v, i) => vocabRow(v, i))}</div>`;
  }

  function noteChip(id, label) {
    return html`<button type="button" class="${cls('s-qs__notechip', noteType === id && 'is-active')}" data-note-type="${id}">${label}</button>`;
  }

  function noteRow(note) {
    return html`<div class="s-qs__note">
      <div class="s-qs__note-head"><span class="s-qs__note-type" style="color:${noteTypeColorKey(note.type)}">${t(`note${note.type[0].toUpperCase()}${note.type.slice(1)}`)}</span><button type="button" class="s-qs__note-del" data-note-delete="${note.id}" aria-label="${t('deleteNote')}">${raw(icon('x', { size: 17 }))}</button></div>
      <div class="s-qs__note-text">${note.text}</div>
    </div>`;
  }

  function noteMarkup() {
    const notes = storage ? loadNotes(storage, owner, key) : [];
    return html`<div class="s-qs__panel s-qs__panel--note">
      <div class="s-qs__notechips">${noteChip('factual', t('noteFactual'))}${noteChip('reflection', t('noteReflection'))}${noteChip('question', t('noteQuestion'))}</div>
      <textarea class="s-qs__textarea" rows="3" placeholder="${t('notePlaceholder')}" data-note-draft>${noteDraft}</textarea>
      <button type="button" class="o-btn o-btn--primary" data-note-add>${t('addNote')}</button>
      ${notes.length ? html`<div class="s-qs__notes">${notes.map(noteRow)}</div>` : ''}
    </div>`;
  }

  function panelMarkup() {
    if (tab === 'Translation') return translationMarkup();
    if (tab === 'Structure') return structureMarkup();
    if (tab === 'Vocabulary') return vocabularyMarkup();
    return noteMarkup();
  }

  function bodyMarkup() {
    return html`
      <div class="s-qs__sentence" lang="${langAttr(lang)}">${target}</div>
      ${tabsMarkup()}
      ${panelMarkup()}
      <div class="s-qs__actions">
        <button type="button" class="s-qs__ask s-qs__grow" data-ask>${raw(icon('audio-lines', { size: 20 }))} ${t('askDeeper')}</button>
      </div>
    `;
  }

  function headMarkup() {
    return html`<div class="s-qs__head"><div class="s-qs__label">${t('labelSentence')}</div><button type="button" class="o-iconbtn o-iconbtn--close" data-sheet-close aria-label="${s('close')}">${raw(icon('x', { size: 17 }))}</button></div>`;
  }

  function paint() {
    if (!sheetEl || !alive) return;
    mount(sheetEl, html`${headMarkup()}<div class="s-qs__body" data-scroll-region>${bodyMarkup()}</div>`);
    // See openWordSheet's paint(): mount() destroys the focused element (a tab button, a
    // note-delete button, …) on every repaint - restore focus into the sheet so Escape and the
    // Tab focus-trap (kit/overlay.js, bound to the sheet element) keep working.
    if (!sheetEl.contains(document.activeElement)) sheetEl.focus({ preventScroll: true });
    bind();
  }

  function bind() {
    sheetEl.querySelector('[data-sheet-close]')?.addEventListener('click', () => handle.close());
    sheetEl.querySelector('[data-ask]')?.addEventListener('click', () => askSentenceDeeper(target, lang, source));
    sheetEl.querySelectorAll('[data-tab]').forEach((button) => button.addEventListener('click', () => { tab = button.dataset.tab; paint(); }));
    sheetEl.querySelectorAll('[data-vocab-save]').forEach((button) => button.addEventListener('click', () => toggleVocabSave(Number(button.dataset.vocabSave))));
    if (tab === 'Note') {
      const draft = sheetEl.querySelector('[data-note-draft]');
      draft?.addEventListener('input', () => { noteDraft = draft.value; });
      sheetEl.querySelectorAll('[data-note-type]').forEach((button) => button.addEventListener('click', () => { noteType = button.dataset.noteType; paint(); }));
      sheetEl.querySelector('[data-note-add]')?.addEventListener('click', submitNote);
      sheetEl.querySelectorAll('[data-note-delete]').forEach((button) => button.addEventListener('click', () => {
        if (!storage) return;
        deleteNote(storage, owner, key, button.dataset.noteDelete);
        if (source?.content_id) {
          noteRemoved(source.content_id, button.dataset.noteDelete);
          scheduleAnnotationPush(storage, owner, source.content_id);
        }
        paint();
        onNote?.();
      }));
    }
  }

  function submitNote() {
    if (!storage || !noteDraft.trim()) return;
    const note = addNote(storage, owner, key, { type: noteType, text: noteDraft, content: source?.content_id || '' });
    if (!note) return;
    if (source?.content_id) scheduleAnnotationPush(storage, owner, source.content_id);
    noteDraft = '';
    paint();
    toast(t('savedToast'));
    onNote?.(note);
  }

  async function toggleVocabSave(index) {
    const item = sheetData.vocabulary[index];
    if (!item) return;
    try {
      if (item.saved) {
        await api.deleteLibraryVocabulary(item.term);
      } else {
        await api.saveLibraryVocabulary(vocabSavePayload(item.term, item.meaning, target, source));
        void keepProvenance({ term: item.term, source, sentence: target });
      }
      item.saved = !item.saved;
      paint();
    } catch {
      /* Left as it was - no false confirmation. */
    }
  }

  let handle = null;
  if (!ctx.isCurrent || ctx.isCurrent()) {
    handle = openSheet({
      label: t('labelSentence'),
      className: 's-qs s-qs--sentence',
      render(element) {
        sheetEl = element;
        paint();
        onOpen?.();
        // Notes the account holds for this text arrive on this device too (D4 I10).
        if (source?.content_id) {
          pullIntoDevice(storage, owner, source.content_id)
            .then((changed) => { if (changed && alive) paint(); })
            .catch(() => {});
        }
        (async () => {
          const ctxText = context || target;
          let response = null;
          try {
            response = await api.sentenceSheet({ text: target, context: ctxText, source_language: lang, target_language: support });
          } catch {
            response = null;
          }
          if (!alive) return;
          sheetData = mapSentenceSheet(response || {});
          paint();
        })();
        return () => {
          alive = false;
        };
      },
      onClose: () => onClose?.(),
    });
  }
  return handle;
}
