/* The reader in the page: reading first, learning tools on demand.

   The text is the page. A compact bar keeps the learner's place (chapter,
   progress) and holds the contents and the reader settings; chapters turn at
   the end of the text and, on a phone, from a dock at the bottom. Nothing is
   requested while the learner reads. Selecting text offers the tools that fit
   what was selected:

   - Translate: a word is looked up (dictionary and word lists, never AI); a
     phrase or passage is machine translated. Answers are kept for the visit.
   - Explain: the one explanation surface, and the only way this reader
     reaches AI - always an explicit request.
   - Save: into the learner's collection, with the sentence it came from.
   - Pronounce: the device's own speech, when it has any. */
import { esc, dialog } from './html.js';
import { mountLexicalLayer } from './lexical.js';
import { symbol } from './symbols.js';
import { icon } from './phosphor.js';
import { referenceCopy } from './reference.js';
import { contentCover } from './cover.js';
import { link } from '../product/intent.js';
import {
  EXPLAIN_LIMITS,
  READER_SIZE,
  blocksFrom,
  chapterHref,
  chapterLabel,
  chapterNeighbours,
  progressLabel,
  readerArticleHtml,
  readerPresentation,
  readerSettings,
  settingsHtml,
  tocHtml,
} from './reading-room.js';

const SETTINGS_KEY = 'orena.reader';

function loadSettings() {
  try {
    return readerSettings(JSON.parse(localStorage.getItem(SETTINGS_KEY) || 'null'));
  } catch {
    return readerSettings(null);
  }
}

function saveSettings(settings) {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    // A device that cannot keep the preference still reads with it this visit.
  }
}

/* `book` is set for a library chapter: { id, title, chapterId, chapters,
   provenance }. `progressive` reveals a dialogue a line at a time. `title` is
   what an explanation or a kept word is filed under; `origin` is the way back. */
export function mountReader(
  host,
  ctx,
  { item, blocks: sourceBlocks, book = null, progressive = false, title, origin },
) {
  const { api, c, language, memory } = ctx;
  const alive = ctx.alive || (() => host.isConnected);
  const support = ctx.support;
  const translatable = Boolean(support) && support !== language;
  const canSpeak = typeof window !== 'undefined' && 'speechSynthesis' in window;
  const blocks = blocksFrom({ blocks: sourceBlocks, paragraphs: item.paragraphs || [item.text] });
  const place = book ? chapterNeighbours(book.chapters, book.chapterId) : null;
  const marks = new Map();
  const answers = new Map();
  // Which paragraph has been tokenised, and what the learner has already kept.
  const tokenised = new Map();
  const savedTerms = new Set(
    Object.keys(memory.value.keptLanguage || {}).map((term) => term.toLocaleLowerCase()),
  );
  const alreadyKept = (text) => savedTerms.has(String(text).trim().toLocaleLowerCase());
  let shown = progressive ? Math.min(1, blocks.length) : blocks.length;
  let settings = loadSettings();
  const kept = () => memory.value.kept.includes(item.id);

  const where = place ? chapterLabel(c, place.index, place.total) : '';
  const barTitle = book ? book.title : item.title;
  const prevHref = place?.previous ? chapterHref(book.id, place.previous.id) : '';
  const nextHref = place?.next ? chapterHref(book.id, place.next.id) : '';

  const stepLink = (href, label, direction) =>
    href
      ? `<a class="reader-step" href="${esc(href)}" rel="${direction === 'back' ? 'prev' : 'next'}" aria-label="${esc(label)}">${symbol(direction, 20)}</a>`
      : `<span class="reader-step" aria-hidden="true">${symbol(direction, 20)}</span>`;

  /* The support-language layer's state, declared with the other reading state
     because the first paint already asks whether it is on. */
  const translations = new Map();
  let showSupport = false;
  const supportLine = (index) => {
    const text = translations.get(index);
    return showSupport && text ? `<p class="reader-support" lang="${esc(support || '')}">${esc(text)}</p>` : '';
  };
  const bodyHtml = () => {
    const visible = blocks.slice(0, shown);
    const next =
      shown < blocks.length
        ? `<button type="button" class="outline reader-next-line" data-next>${esc(c.nextLine)} →</button>`
        : item.question
          ? `<p class="reader-question">${esc(item.question)}</p>`
          : '';
    const article = readerArticleHtml(c, { title: item.title, language, blocks: visible, marks });
    /* The support-language line sits under the paragraph it translates, as the
       design draws it - a layer over the same text, never a second column. */
    const withSupport = showSupport
      ? article.replace(/<\/p>/g, (match, offset, whole) => {
          const before = whole.slice(0, offset);
          const opened = [...before.matchAll(/data-block="(\d+)"/g)].pop();
          return `</p>${opened ? supportLine(Number(opened[1])) : ''}`;
        })
      : article;
    return `${withSupport}${next}`;
  };

  /* The end of a chapter, as the design draws it (Screens part 3): what was
     just finished, what it left behind, and the one way on. What nothing
     measures keeps its tile and says so - the quiz a library chapter does not
     carry (GAP-031) and the time nobody records (GAP-030). New words are the
     words kept since this chapter opened: a real count of real saves. */
  const chapterCompleteHtml = () => {
    if (!place) return '';
    const done = place.index + 1;
    const percent = place.total ? Math.max(1, Math.round((done / place.total) * 100)) : 0;
    const fresh = Object.entries(memory.value.keptLanguage || {}).filter(
      ([term, entry]) =>
        !savedTerms.has(String(term).trim().toLocaleLowerCase()) &&
        (!entry?.where || entry.where === item.title || entry.where === barTitle),
    );
    const tile = (label, value, note = '') =>
      `<div class="chapter-tile"><span class="ds-label">${esc(label)}</span><strong>${esc(value)}</strong>${note ? `<small>${esc(note)}</small>` : ''}</div>`;
    const next = place.next;
    const nextWords = Number(next?.word_count) > 0
      ? String(r.bookChapterWords || '{n}').replace('{n}', Number(next.word_count).toLocaleString())
      : '';
    return `<section class="chapter-complete" data-chapter-complete aria-label="${esc(r.chapterComplete)}"><span class="ds-label chapter-complete__label">${icon('check-circle', { size: 16, filled: true })}${esc(r.chapterComplete)}</span><h2 class="chapter-complete__line">${esc(
      String(r.chapterDoneLine).replace('{n}', String(done)).replace('{p}', String(percent)),
    )}</h2><div class="chapter-tiles">${tile(r.chapterQuiz, '—', r.bookNotMeasured)}${tile(
      r.chapterNewWords,
      String(fresh.length),
    )}${tile(r.chapterTime, '—', r.bookNotMeasured)}</div>${
      fresh.length
        ? `<div class="chapter-saved"><div class="chapter-saved__head"><span class="ds-label">${esc(r.chapterSavedHere)}</span><a class="chapter-saved__review" href="${esc(link('practice', { intent: 'recall' }))}">${esc(r.chapterReviewNow)}</a></div><div class="chapter-words">${fresh
            .slice(0, 6)
            .map(([term, entry]) => `<span class="chapter-word"><span lang="${esc(language)}">${esc(term)}</span>${entry?.reading || entry?.pronunciation ? `<small class="ds-data">${esc(entry.reading || entry.pronunciation)}</small>` : ''}</span>`)
            .join('')}${fresh.length > 6 ? `<span class="chapter-word chapter-word--more ds-data">+${fresh.length - 6}</span>` : ''}</div></div>`
        : ''
    }${
      next
        ? `<a class="chapter-next" href="${esc(nextHref)}"><span class="chapter-next__cover">${contentCover({ id: `${book.id}/${next.id}`, title: next.title, material: 'book' })}</span><span class="chapter-next__text"><span class="ds-label">${esc(r.chapterUpNext)}</span><strong lang="${esc(language)}">${esc(next.title)}</strong>${nextWords ? `<small class="ds-data">${esc(nextWords)}</small>` : ''}</span></a>`
        : `<p class="chapter-complete__last">${esc(r.chapterLast)}</p>`
    }<div class="chapter-actions">${
      nextHref
        ? `<a class="primary" href="${esc(nextHref)}">${icon('book-open', { size: 18, filled: true })}<span>${esc(r.chapterContinue)}</span></a>`
        : `<a class="primary" href="${esc(link('book', { id: book.id }))}">${icon('books', { size: 18 })}<span>${esc(c.libraryChapters)}</span></a>`
    }<button type="button" class="icon-button chapter-contents" data-reader-toc aria-label="${esc(c.readerContents)}">${icon('list', { size: 20 })}</button></div></section>`;
  };

  /* The approved reader (D-059 Phase 5): a compact bar - the way back, where
     the learner is, the progress rail, the reading layers and the type size -
     over a split pane. The text takes the page; the side panel holds the word
     just looked up, notes and the contents. A phone drops the panel: the word
     arrives as the anchored sheet the design draws. */
  const r = referenceCopy[ctx.ui] || referenceCopy.en;
  const layerChip = (key, label, on, available) =>
    `<button type="button" class="reader-layer" data-reader-layer="${key}" aria-pressed="${on}"${available ? '' : ` aria-disabled="true" title="${esc(r.readerLayerUnavailable)}"`}>${esc(label)}</button>`;
  const tabs = ['word', 'notes', 'chapters'].filter((tab) => tab !== 'chapters' || place);
  host.innerHTML = `<div class="reader" data-reader><header class="reader-bar"><a class="reader-bar__back" href="${esc(origin || link('practice', { intent: 'reading' }))}" aria-label="${esc(c.readerBackToReading)}">${icon('caret-right', { size: 20, className: 'is-flipped' })}</a><span class="reader-bar__title"${book ? ` lang="${esc(language)}"` : ''}>${esc(barTitle)}${where ? ` · ${esc(where)}` : ''}</span><div class="reader-progress" aria-hidden="true"><span data-reader-progress></span></div><span class="reader-bar__percent ds-data" data-reader-percent>${esc(progressLabel(c, 0))}</span><div class="reader-bar__tools">${language === 'zh' ? layerChip('pinyin', r.readerPinyin, false, false) : ''}${translatable ? layerChip('support', String(support || '').toUpperCase(), false, true) : ''}<button type="button" class="reader-tool reader-tool--text" data-reader-settings-toggle aria-label="${esc(c.readerSettings)}" aria-expanded="false">Aa</button>${book ? '' : `<button type="button" class="reader-tool" data-keep aria-pressed="${kept()}" aria-label="${esc(c.readerKeep)}">${symbol('bookmark', 20)}</button>`}</div></header><div class="reader-settings-pop" data-reader-settings hidden></div><div class="reader-layout"><div class="reader-body" data-reader-body>${bodyHtml()}</div><aside class="reader-aside" aria-label="${esc(r.readerPanel)}"><div class="reader-aside__tabs" role="tablist">${tabs
    .map((tab) => `<button type="button" role="tab" class="reader-aside__tab" aria-selected="${tab === 'word'}" data-reader-tab="${tab}">${esc(r[`readerTab_${tab}`])}</button>`)
    .join('')}</div><div class="reader-aside__body" role="tabpanel" data-reader-panel></div></aside></div>${chapterCompleteHtml()}${place ? `<nav class="reader-dock" aria-label="${esc(c.readerContents)}">${stepLink(prevHref, c.readerPrevious, 'back')}<button type="button" class="reader-dock__where" data-reader-toc>${esc(`${place.index + 1} / ${place.total}`)}<span class="sr-only"> ${esc(where)}</span></button>${stepLink(nextHref, c.readerNext, 'forward')}</nav>` : ''}</div>`;

  const reader = host.querySelector('[data-reader]');
  const body = host.querySelector('[data-reader-body]');
  const asidePanel = host.querySelector('[data-reader-panel]');
  let tab = 'word';
  const wide = () => window.matchMedia('(min-width: 901px)').matches;
  /* The words kept while reading this text, as the design's "saved in this
     chapter" list - read from device memory, never a second store. */
  const savedHere = () =>
    Object.entries(memory.value.keptLanguage || {})
      .filter(([, kept]) => !kept?.where || kept.where === barTitle || kept.where === item.title)
      .slice(0, 8);
  const panelPlaceholder = () => {
    if (tab === 'chapters' && place)
      return tocHtml(c, { bookId: book.id, chapters: book.chapters, currentId: book.chapterId, provenance: book.provenance });
    if (tab === 'notes')
      return `<div class="state-panel state-panel--empty">${icon('pencil-simple', { size: 20 })}<div><strong>${esc(r.savedNotesUnavailable)}</strong></div></div>`;
    const saved = savedHere();
    return `<p class="reader-aside__hint">${icon('hand-tap', { size: 16 })}<span>${esc(r.readerTapWord)}</span></p>${
      saved.length
        ? `<div class="reader-aside__saved"><span class="ds-label">${esc(r.readerSavedHere)}</span>${saved
            .map(([term, kept]) => `<span class="reader-saved-row"><span lang="${esc(language)}">${esc(term)}</span><small class="ds-data">${esc(kept?.reading || kept?.pronunciation || '')}</small></span>`)
            .join('')}</div>`
        : ''
    }`;
  };
  const paintPanel = () => {
    asidePanel.innerHTML = panelPlaceholder();
    asidePanel.querySelectorAll('.reader-toc a').forEach((a) => a.setAttribute('data-reader-chapter', ''));
  };
  host.querySelectorAll('[data-reader-tab]').forEach((button) => {
    button.onclick = () => {
      tab = button.dataset.readerTab;
      host.querySelectorAll('[data-reader-tab]').forEach((x) => x.setAttribute('aria-selected', String(x === button)));
      paintPanel();
    };
  });
  const settingsPop = host.querySelector('[data-reader-settings]');
  const settingsToggle = host.querySelector('[data-reader-settings-toggle]');
  const percentLabel = host.querySelector('[data-reader-percent]');
  const progressBar = host.querySelector('[data-reader-progress]');
  const page = () => body.querySelector('[data-reader-page]');

  /* --- Settings --- */
  const applySettings = () => {
    const presentation = readerPresentation(settings);
    reader.setAttribute('style', presentation.style);
    reader.dataset.readerFont = presentation.font;
    if (presentation.theme) {
      reader.dataset.theme = presentation.theme.theme;
      reader.dataset.appearance = presentation.theme.appearance;
    } else {
      delete reader.dataset.theme;
      delete reader.dataset.appearance;
    }
  };
  const paintSettings = (focusSelector) => {
    settingsPop.innerHTML = settingsHtml(c, settings);
    if (focusSelector) settingsPop.querySelector(focusSelector)?.focus({ preventScroll: true });
  };
  const closeSettings = ({ restore = false } = {}) => {
    if (settingsPop.hidden) return;
    settingsPop.hidden = true;
    settingsToggle.setAttribute('aria-expanded', 'false');
    if (restore) settingsToggle.focus({ preventScroll: true });
  };
  settingsToggle.onclick = () => {
    if (!settingsPop.hidden) return closeSettings();
    paintSettings();
    settingsPop.hidden = false;
    settingsToggle.setAttribute('aria-expanded', 'true');
    settingsPop.querySelector('button:not([disabled])')?.focus({ preventScroll: true });
  };
  settingsPop.addEventListener('click', (event) => {
    const button = event.target.closest('button');
    if (!button || button.disabled) return;
    let focus = null;
    if (button.dataset.readerSize) {
      const step = Number(button.dataset.readerSize) * READER_SIZE.step;
      settings = readerSettings({ ...settings, size: settings.size + step });
      focus = `[data-reader-size="${button.dataset.readerSize}"]`;
    }
    for (const key of ['font', 'spacing', 'width', 'appearance']) {
      const value = button.dataset[`reader${key[0].toUpperCase()}${key.slice(1)}`];
      if (value) {
        settings = readerSettings({ ...settings, [key]: value });
        focus = `[data-reader-${key}="${value}"]`;
      }
    }
    saveSettings(settings);
    applySettings();
    paintSettings(focus);
    updateProgress();
  });
  applySettings();

  /* --- Reading layers --- */
  async function toggleSupport(button) {
    showSupport = !showSupport;
    button.setAttribute('aria-pressed', String(showSupport));
    reader.dataset.readerSupport = showSupport ? 'on' : 'off';
    if (!showSupport) return repaintBody();
    const missing = blocks
      .map((block, index) => ({ block, index }))
      .filter(({ block, index }) => block.type === 'paragraph' && !translations.has(index))
      .slice(0, 12);
    if (missing.length) {
      button.disabled = true;
      const answered = await lexical.translateBlocks(
        missing.map(({ block, index }) => ({ index, text: block.text })),
      );
      for (const [index, line] of answered) translations.set(index, line);
      button.disabled = false;
    }
    repaintBody();
  }
  host.querySelectorAll('[data-reader-layer]').forEach((button) => {
    button.onclick = () => {
      if (button.getAttribute('aria-disabled') === 'true') return;
      if (button.dataset.readerLayer === 'support') toggleSupport(button);
    };
  });

  /* --- Keep, contents, dialogue --- */
  const keepButton = host.querySelector('[data-keep]');
  if (keepButton)
    keepButton.onclick = () => {
      memory.keep(item.id);
      keepButton.setAttribute('aria-pressed', String(kept()));
    };
  function bindContents() {
    host.querySelectorAll('[data-reader-toc]').forEach(
    (button) =>
      (button.onclick = () => {
        const sheet = dialog({
          title: c.readerContents,
          body: tocHtml(c, {
            bookId: book.id,
            chapters: book.chapters,
            currentId: book.chapterId,
            provenance: book.provenance,
          }),
        });
        sheet.classList.add('reader-toc-sheet');
        // Following a chapter link leaves the room; the sheet goes with it.
        sheet.querySelectorAll('.reader-toc a').forEach((a) => (a.onclick = () => sheet.close()));
        const current = sheet.querySelector('[aria-current="true"]');
        current?.scrollIntoView({ block: 'center' });
        current?.focus({ preventScroll: true });
      }),
    );
  }
  bindContents();
  body.addEventListener('click', (event) => {
    if (!event.target.closest('[data-next]')) return;
    shown = Math.min(blocks.length, shown + 1);
    repaintBody();
    (body.querySelector('[data-next]') || document.querySelector('#response'))?.focus({
      preventScroll: true,
    });
  });
  const repaintBody = () => {
    body.innerHTML = bodyHtml();
    lexical.forget();
  };
  /* The end-of-chapter panel counts what has been kept, so it is repainted
     whenever a word is saved - the same moment the side panel goes back to
     its own placeholder. */
  const repaintComplete = () => {
    const panel = host.querySelector('[data-chapter-complete]');
    if (!panel) return;
    panel.outerHTML = chapterCompleteHtml();
    bindContents();
  };

  /* --- Progress through this text --- */
  let progressFrame = 0;
  function updateProgress() {
    progressFrame = 0;
    const article = page();
    if (!article || !alive()) return;
    const box = article.getBoundingClientRect();
    const read = box.height ? (window.innerHeight - box.top) / box.height : 1;
    const percent = Math.max(0, Math.min(100, Math.round(read * 100)));
    percentLabel.textContent = progressLabel(c, percent);
    progressBar.style.inlineSize = `${percent}%`;
  }
  const onScroll = () => {
    if (!progressFrame) progressFrame = requestAnimationFrame(updateProgress);
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll, { passive: true });
  updateProgress();

  /* --- Selection, tap and the answer --- */

  /* One lexical layer, shared with Listening's transcript (`ui/lexical.js`).
     The reader only says where its text is: a paragraph or heading carrying
     `data-block`, and the block text it was rendered from. */
  const lexical = mountLexicalLayer({
    surface: reader,
    ctx,
    title,
    origin,
    alive,
    dock: () => (wide() ? (tab === 'word' ? asidePanel : null) : null),
    onPanel: (open) => {
      if (open) return;
      paintPanel();
      repaintComplete();
    },
    units: {
      root: () => page(),
      unitOf: (node) => node?.closest?.('[data-block]') || null,
      textOf: (unit) => blocks[Number(unit.dataset.block)]?.text || '',
      keyOf: (unit) => `block:${unit.dataset.block}`,
    },
  });

  body.addEventListener('click', (event) => {
    if (event.target.closest('[data-next]')) return;
    lexical.tapWord(event);
  });

  paintPanel();

  const closeSettingsIfOutside = (event) => {
    if (!settingsPop.hidden && !settingsPop.contains(event.target) && !settingsToggle.contains(event.target))
      closeSettings();
  };
  const onReaderPointerDown = (event) => closeSettingsIfOutside(event);
  const onReaderKeyDown = (event) => {
    if (event.key === 'Escape' && !settingsPop.hidden) closeSettings({ restore: true });
  };
  document.addEventListener('pointerdown', onReaderPointerDown, true);
  document.addEventListener('keydown', onReaderKeyDown);

  return {
    /* Where a comprehension answer lives, marked in the text and brought into
       view. Returns the paragraph, which is the context the check explains. */
    showEvidence(fragment) {
      const index = blocks.findIndex((block) => block.type === 'paragraph' && block.text.includes(fragment));
      if (index < 0) return '';
      marks.clear();
      const start = blocks[index].text.indexOf(fragment);
      marks.set(index, { start, end: start + fragment.length });
      if (index < shown) {
        repaintBody();
        body.querySelector(`[data-block="${index}"]`)?.scrollIntoView({ block: 'center' });
      }
      return blocks[index].text.slice(0, EXPLAIN_LIMITS.context);
    },
    destroy() {
      if (progressFrame) cancelAnimationFrame(progressFrame);
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      document.removeEventListener('pointerdown', onReaderPointerDown, true);
      document.removeEventListener('keydown', onReaderKeyDown);
      lexical.destroy();
    },
  };
}
