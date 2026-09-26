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
import { icon } from './phosphor.js';
import { refCopy } from './reference.js';
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
   what an explanation or a kept word is filed under; `origin` is where it was met (the
   provenance a kept word carries), which is not a link. The way back is the book's page
   for a chapter and the reading practice otherwise. */
export function mountReader(
  host,
  ctx,
  { item, blocks: sourceBlocks, book = null, progressive = false, title, origin, actions = [], onAction = null, onPlace = null },
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

  const where = place ? chapterLabel(c, place.index) : '';
  const barTitle = book ? book.title : item.title;
  const nextHref = place?.next ? chapterHref(book.id, place.next.id) : '';

  /* The phone's old chapter dock is deleted rather than restyled: neither
     frame draws one. The phone turns a chapter from the bar's primary tile,
     and reaches the whole list through the book the back arrow returns to. */

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
  /* The source draws no end-of-chapter sheet. The D-059 composition that
     covered half the screen the moment a chapter opened is deleted (rule 44),
     not restyled: what it reported - the words kept here, the way on - is
     already the side panel's and the foot row's work.  */

  /* The approved reader (D-059 Phase 5): a compact bar - the way back, where
     the learner is, the progress rail, the reading layers and the type size -
     over a split pane. The text takes the page; the side panel holds the word
     just looked up, notes and the contents. A phone drops the panel: the word
     arrives as the anchored sheet the design draws. */
  const r = refCopy(ctx);
  /* The source draws this as a pill with the translate glyph and a word, not a
     bare language code: "Song ngữ" - the bilingual layer over the same text. */
  const layerChip = (key, label, on, available, glyph = null) =>
    `<button type="button" class="reader-layer${glyph ? ' reader-layer--pill' : ''}" data-reader-layer="${key}" aria-pressed="${on}"${available ? '' : ` aria-disabled="true" title="${esc(r.readerLayerUnavailable)}"`}>${glyph ? icon(glyph, { size: 19, filled: on }) : ''}<span>${esc(label)}</span></button>`;
  const tabs = ['word', 'grammar', 'notes'];
  /* The reader of the updated design (D-065, device overview 03): the contents
     on the left at 300px, the text in the middle at its own measure, and the
     word panel on the right at 440px. The bar carries what this is and the
     three controls that change how it reads; how far through it the learner
     is sits under the text, with the way to the next chapter. A phone drops
     the two side columns: the contents live behind the title, and a word
     arrives as the anchored sheet. */
  const readerWords = blocks.reduce((total, block) => total + String(block.text || '').split(/\s+/).filter(Boolean).length, 0);
  /* The frame writes "chương 3 · còn 9 phút": where this sits, and how long is
     left of it. A chapter carries the duration the server derived; a text that
     carries none says how many words it is, which is what the app can measure
     for itself. */
  const readerSeconds = Number(item?.reading_time_seconds || 0);
  const howLong = readerSeconds
    ? String(r.readerMinutesLeft).replace('{n}', String(Math.max(1, Math.round(readerSeconds / 60))))
    : readerWords
      ? String(r.readerWords).replace('{n}', readerWords.toLocaleString())
      : '';
  /* The wide frame writes both ("chương 3 · còn 9 phút"); the phone frame,
     with a third of the room, writes only what is left. Same line, one part
     of it put away where it does not fit. */
  const metaLine = [where, howLong].filter(Boolean).join(' · ');
  const metaHtml = [
    where ? `<span class="reader-bar__where">${esc(where)}</span>` : '',
    where && howLong ? '<span class="reader-bar__dot" aria-hidden="true"> · </span>' : '',
    howLong ? `<span>${esc(howLong)}</span>` : '',
  ].join('');
  /* The frame's floating bar under the text: what the learner can do with this whole text, once, in
     one place. The reader owns the two it can answer itself - keeping the text and hearing it - and the
     room that mounted it supplies the rest, because only that room knows whether they exist here. */
  const barAction = ({ name, glyph, label, short = '', wide = false, primary = false, available = true, title = '', pressed = null }) =>
    `<button type="button" class="reader-action${primary ? ' reader-action--primary' : ''}${wide ? ' reader-action--wide' : ''}" data-reader-action="${esc(name)}"${pressed === null ? '' : ` aria-pressed="${pressed}"`}${available ? '' : ` aria-disabled="true"`}${title ? ` title="${esc(title)}"` : ''}>${icon(glyph, { size: 19, filled: primary })}<span class="reader-action__label">${esc(label)}</span>${short && short !== label ? `<span class="reader-action__short">${esc(short)}</span>` : ''}</button>`;
  /* The six the desktop source draws, in its order, with its icons (measured
     2026-09-22): Lưu bài · Nghe · Kiểm tra hiểu · Thảo luận · Viết phản hồi ·
     Đọc tiếp sau, the last one the primary. The caller says which of the
     middle ones this text can actually offer; nothing else joins the bar -
     prepared notes are the side panel's third tab, where the frame puts them.

     The phone frame draws five of the same tiles in a docked bar, with the
     shorter labels it writes (Lưu · Nghe · Hiểu bài · Viết) and the way on to
     the next chapter as its primary, because it draws no foot row to hold it.
     Same bar, same actions, the two the narrow frame leaves out marked. */
  const actionBar = () => {
    const supplied = new Map(actions.map((action) => [action.name, action]));
    const all = [
      { name: 'keep', glyph: 'bookmark-simple', label: r.readerSave, short: r.readerSaveShort, pressed: kept() },
      { name: 'listen', glyph: 'speaker-high', label: r.readerListen, available: false, title: r.bookSoon },
      supplied.get('check') && { short: r.readerCheckShort, ...supplied.get('check') },
      supplied.get('discuss') && { ...supplied.get('discuss'), wide: true },
      supplied.get('respond') && { short: r.readerRespondShort, ...supplied.get('respond') },
      { name: 'later', glyph: 'bookmark-simple', label: c.readerKeep, primary: true, wide: true },
    ].filter(Boolean);
    const onward = nextHref
      ? `<a class="reader-action reader-action--primary reader-action--phone" href="${esc(nextHref)}">${icon('arrow-right', { size: 19 })}<span class="reader-action__label">${esc(r.readerNextChapter)}</span></a>`
      : '';
    return `<div class="reader-actions" role="group" aria-label="${esc(r.readerActions)}">${all.map(barAction).join('')}${onward}</div>`;
  };
  const contentsColumn = place
    ? `<nav class="reader-contents-column" aria-label="${esc(r.readerContents)}"><span class="ds-label">${esc(r.readerContents)}</span>${tocHtml(c, { bookId: book.id, chapters: book.chapters, currentId: book.chapterId, provenance: book.provenance })}</nav>`
    : '';
  host.innerHTML = `<div class="reader" data-reader><span class="reader-rail" aria-hidden="true"><i data-reader-rail></i></span><header class="reader-bar"><a class="reader-bar__back" href="${esc(book?.id ? link('book', { id: book.id }) : link('practice', { intent: 'reading' }))}" aria-label="${esc(c.readerBackToReading)}">${icon('arrow-left', { size: 20 })}<span class="reader-bar__title"${book ? ` lang="${esc(language)}"` : ''}>${esc(barTitle)}</span></a>${metaLine ? `<span class="reader-bar__meta ds-data">${metaHtml}</span>` : ''}<div class="reader-bar__tools">${language === 'zh' ? layerChip('pinyin', r.readerPinyin, false, false) : ''}${translatable ? layerChip('support', r.readerBilingual, false, true, 'translate') : ''}<button type="button" class="reader-tool reader-tool--text" data-reader-settings-toggle aria-label="${esc(c.readerSettings)}" aria-expanded="false">Aa</button></div></header><div class="reader-settings-pop" data-reader-settings hidden></div><div class="reader-layout">${contentsColumn}<div class="reader-body" data-reader-body>${bodyHtml()}</div><aside class="reader-aside" aria-label="${esc(r.readerPanel)}"><div class="reader-aside__tabs" role="tablist">${tabs
    .map((tab) => `<button type="button" role="tab" class="reader-aside__tab" aria-selected="${tab === 'word'}" data-reader-tab="${tab}">${esc(r[`readerTab_${tab}`])}</button>`)
    .join('')}</div><div class="reader-aside__body" role="tabpanel" data-reader-panel></div></aside>${actionBar()}</div><footer class="reader-foot"><div class="reader-foot__row"><span class="reader-foot__place ds-data" data-reader-percent>${esc(progressLabel(c, 0))}</span>${nextHref ? `<a class="primary reader-foot__next" href="${esc(nextHref)}">${esc(r.readerNextChapter)}${icon('arrow-right', { size: 16 })}</a>` : ''}</div></footer></div>`;

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
    if (tab === 'grammar')
      return `<div class="state-panel state-panel--empty">${icon('info', { size: 20 })}<div><strong>${esc(r.readerGrammarUnavailable)}</strong></div></div>`;
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
  const rail = host.querySelector('[data-reader-rail]');
  const page = () => body.querySelector('[data-reader-page]');

  /* --- Settings --- */
  const applySettings = () => {
    const presentation = readerPresentation(settings);
    reader.setAttribute('style', presentation.style);
    reader.dataset.readerFont = presentation.font;
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
    for (const key of ['font', 'spacing', 'width']) {
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

  /* --- The bar under the text: keeping and hearing are the reader's own; the rest belong to the room
     that mounted it, which is told by name which one was pressed. --- */
  host.querySelectorAll('[data-reader-action]').forEach((button) => {
    button.onclick = (event) => {
      event.preventDefault();
      if (button.getAttribute('aria-disabled') === 'true') return;
      const name = button.dataset.readerAction;
      if (name === 'keep') {
        memory.keep(item.id);
        button.setAttribute('aria-pressed', String(kept()));
        return;
      }
      if (name === 'listen') return;
      /* "Đọc tiếp sau" is the frame's primary: keep the place - which the room
         already records - and leave the text, so the learner comes back to it
         from the library rather than staying on the page they stopped reading. */
      if (name === 'later') {
        if (!kept()) memory.keep(item.id);
        location.hash = book?.id ? link('book', { id: book.id }) : link('practice', { intent: 'reading' });
        return;
      }
      onAction?.(name, button);
    };
  });
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


  /* --- Progress through this text --- */
  let progressFrame = 0;
  function updateProgress() {
    progressFrame = 0;
    const article = page();
    if (!article || !alive()) return;
    const box = article.getBoundingClientRect();
    const read = box.height ? (window.innerHeight - box.top) / box.height : 1;
    const percent = Math.max(0, Math.min(100, Math.round(read * 100)));
    /* "34% · còn 9 phút": how far in, and what is left of it at the pace the
       server counted. A text with no count keeps the figure alone. */
    const leftLabel = readerSeconds
      ? String(r.readerMinutesLeft).replace('{n}', String(Math.max(1, Math.round((readerSeconds * (100 - percent)) / 6000))))
      : '';
    percentLabel.textContent = [progressLabel(c, percent), leftLabel].filter(Boolean).join(' · ');
    if (progressBar) progressBar.style.inlineSize = `${percent}%`;
    // The frame draws the figure twice, but only one of them is a bar: the
    // hairline across the top of the screen, and the same percentage as text at
    // the foot of the reading column. A second bar under the text is not drawn.
    // under the text. One measurement, both.
    if (rail) rail.style.inlineSize = `${percent}%`;
    /* And it is worth keeping: Book detail draws how far into the current
       chapter the learner is, which is this number. Only whole steps forward
       are reported - rereading a paragraph is not un-reading the chapter. */
    if (onPlace && percent > furthest) {
      furthest = percent;
      onPlace(percent);
    }
  }
  let furthest = 0;
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
