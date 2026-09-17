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

  const bodyHtml = () => {
    const visible = blocks.slice(0, shown);
    const next =
      shown < blocks.length
        ? `<button type="button" class="outline reader-next-line" data-next>${esc(c.nextLine)} →</button>`
        : item.question
          ? `<p class="reader-question">${esc(item.question)}</p>`
          : '';
    return `${readerArticleHtml(c, { title: item.title, language, blocks: visible, marks })}${next}`;
  };

  const chapterNav = place
    ? `<nav class="reader-chapter-nav" aria-label="${esc(c.readerContents)}">${prevHref ? `<a href="${esc(prevHref)}" rel="prev">${symbol('back', 18)}<span>${esc(c.readerPrevious)}</span></a>` : '<span></span>'}<span class="reader-chapter-nav__where">${esc(where)}</span>${nextHref ? `<a href="${esc(nextHref)}" rel="next"><span>${esc(c.readerNext)}</span>${symbol('forward', 18)}</a>` : `<span class="reader-chapter-nav__end">${esc(c.readerEnd)}</span>`}</nav>`
    : '';

  host.innerHTML = `<div class="reader" data-reader><header class="reader-bar"><a class="reader-bar__back" href="${esc(link('practice', { intent: 'reading' }))}">${symbol('back', 18)}<span>${esc(c.readerBackToReading)}</span></a><div class="reader-bar__where"><span class="reader-bar__title"${book ? ` lang="${esc(language)}"` : ''}>${esc(barTitle)}</span><span class="reader-bar__place">${where ? `<span>${esc(where)}</span><span aria-hidden="true"> · </span>` : ''}<span data-reader-percent>${esc(progressLabel(c, 0))}</span></span></div><div class="reader-bar__tools">${place ? `<span class="reader-bar__steps">${stepLink(prevHref, c.readerPrevious, 'back')}${stepLink(nextHref, c.readerNext, 'forward')}</span><button type="button" class="reader-tool" data-reader-toc aria-label="${esc(c.readerContents)}" aria-haspopup="dialog">${symbol('contents', 20)}</button>` : ''}<button type="button" class="reader-tool reader-tool--text" data-reader-settings-toggle aria-label="${esc(c.readerSettings)}" aria-expanded="false">Aa</button><button type="button" class="reader-tool" data-keep aria-pressed="${kept()}" aria-label="${esc(c.readerKeep)}">${symbol('bookmark', 20)}</button></div><div class="reader-progress" aria-hidden="true"><span data-reader-progress></span></div></header><div class="reader-settings-pop" data-reader-settings hidden></div><div class="reader-body" data-reader-body>${bodyHtml()}${chapterNav}</div>${place ? `<nav class="reader-dock" aria-label="${esc(c.readerContents)}">${stepLink(prevHref, c.readerPrevious, 'back')}<button type="button" class="reader-dock__where" data-reader-toc>${esc(`${place.index + 1} / ${place.total}`)}<span class="sr-only"> ${esc(where)}</span></button>${stepLink(nextHref, c.readerNext, 'forward')}</nav>` : ''}</div>`;

  const reader = host.querySelector('[data-reader]');
  const body = host.querySelector('[data-reader-body]');
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

  /* --- Keep, contents, dialogue --- */
  const keepButton = host.querySelector('[data-keep]');
  keepButton.onclick = () => {
    memory.keep(item.id);
    keepButton.setAttribute('aria-pressed', String(kept()));
  };
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
  body.addEventListener('click', (event) => {
    if (!event.target.closest('[data-next]')) return;
    shown = Math.min(blocks.length, shown + 1);
    repaintBody();
    (body.querySelector('[data-next]') || document.querySelector('#response'))?.focus({
      preventScroll: true,
    });
  });
  const repaintBody = () => {
    const nav = body.querySelector('.reader-chapter-nav');
    body.innerHTML = bodyHtml();
    if (nav) body.append(nav);
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
