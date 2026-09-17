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
import { esc, dialog, focusRegion } from './html.js';
import { openUnderstanding } from './understanding.js';
import { progressReporter, savedLanguageLink } from './patterns.js';
import { symbol } from './symbols.js';
import { link } from '../product/intent.js';
import {
  EXPLAIN_LIMITS,
  LOOKUP_LIMITS,
  READER_SIZE,
  TRANSLATE_LIMITS,
  blocksFrom,
  chapterHref,
  chapterLabel,
  chapterNeighbours,
  explainBounds,
  keepPayload,
  lookupPanelHtml,
  progressLabel,
  readerArticleHtml,
  readerPresentation,
  readerSettings,
  selectionActions,
  selectionKind,
  selectionToolbarHtml,
  sentenceAround,
  settingsHtml,
  tocHtml,
} from './reading-room.js';

const SETTINGS_KEY = 'orena.reader';
// What the shared tagger accepts in one request (media_interaction.MediaAnnotateIn).
const ANNOTATE_LIMIT = 1200;
const narrow = () => window.matchMedia('(max-width: 700px)').matches;
const elementOf = (node) => (node?.nodeType === 1 ? node : node?.parentElement) || null;
const squash = (value) => String(value ?? '').replace(/\s+/g, ' ').trim();

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

  /* --- Selection --- */
  let active = null;
  let toolbar = null;
  let panel = null;
  let panelTarget = null;
  let selectionTimer = 0;
  const coarse = window.matchMedia?.('(pointer: coarse)')?.matches;

  const readSelection = () => {
    const selection = window.getSelection?.();
    const article = page();
    if (!article || !selection || selection.isCollapsed || !selection.rangeCount) return null;
    const range = selection.getRangeAt(0);
    if (!article.contains(range.commonAncestorContainer)) return null;
    const text = squash(selection.toString());
    const kind = selectionKind(text, language);
    if (!kind) return null;
    const startBlock = elementOf(range.startContainer)?.closest('[data-block]');
    const endBlock = elementOf(range.endContainer)?.closest('[data-block]');
    const index = startBlock && startBlock === endBlock ? Number(startBlock.dataset.block) : -1;
    const blockText = index >= 0 ? squash(blocks[index]?.text) : '';
    const at = blockText ? blockText.indexOf(text) : -1;
    const limit = kind === 'passage' ? EXPLAIN_LIMITS.context : LOOKUP_LIMITS.context;
    const context = at >= 0 ? sentenceAround(blockText, at, at + text.length, limit) : text;
    return { text, kind, context, rect: range.getBoundingClientRect() };
  };

  const hideToolbar = () => {
    toolbar?.remove();
    toolbar = null;
  };
  const closePanel = () => {
    panel?.remove();
    panel = null;
    panelTarget = null;
  };
  const anchorBelow = (element, rect) => {
    if (narrow()) return element.removeAttribute('style');
    const gap = 10;
    const width = element.offsetWidth;
    const height = element.offsetHeight;
    const room = document.documentElement.clientWidth;
    const above = rect.top - gap - height;
    const top = above > gap ? above : Math.min(window.innerHeight - height - gap, rect.bottom + gap);
    const left = Math.min(Math.max(gap, rect.left + rect.width / 2 - width / 2), room - width - gap);
    element.style.top = `${Math.round(top)}px`;
    element.style.left = `${Math.round(left)}px`;
  };

  const showToolbar = (target) => {
    const actions = selectionActions(target.kind, { canSpeak }).filter(
      (action) => translatable || action !== 'translate',
    );
    if (!actions.length) return hideToolbar();
    active = target;
    if (!toolbar) {
      toolbar = document.createElement('div');
      toolbar.className = 'reader-selection';
      reader.append(toolbar);
      // Pressing a tool must not take the selection away with the mouse press.
      toolbar.addEventListener('mousedown', (event) => event.preventDefault());
      toolbar.addEventListener('click', (event) => {
        const button = event.target.closest('[data-selection-action]');
        if (button) runAction(button.dataset.selectionAction);
      });
    }
    toolbar.innerHTML = selectionToolbarHtml(c, actions);
    anchorBelow(toolbar, target.rect);
  };

  const renderPanel = (target, state, result = {}) => {
    if (!panel) {
      panel = document.createElement('div');
      panel.className = 'reader-panel';
      panel.setAttribute('role', 'dialog');
      panel.setAttribute('aria-modal', 'false');
      panel.setAttribute('aria-label', target.text);
      panel.tabIndex = -1;
      reader.append(panel);
      panel.addEventListener('mousedown', (event) => {
        if (event.target.closest('button')) event.preventDefault();
      });
      panel.addEventListener('click', (event) => {
        if (event.target.closest('[data-panel-close]')) return closePanel();
        const button = event.target.closest('[data-panel-action]');
        if (button) runAction(button.dataset.panelAction);
      });
    }
    panelTarget = target;
    const closeLabel = document.documentElement.dataset.close || 'Close';
    panel.innerHTML = `<button type="button" class="reader-panel__close" data-panel-close aria-label="${esc(closeLabel)}">×</button>${lookupPanelHtml(c, { selection: target.text, language, support, kind: target.kind, state, result, canSpeak, kept: alreadyKept(target.text) })}`;
    if (!translatable) panel.querySelector('[data-panel-action="retry"]')?.remove();
    anchorBelow(panel, target.rect);
  };

  // A word is looked up; a phrase or passage is translated. Never AI.
  async function answer(target) {
    const key = `${target.kind}:${target.text}`;
    if (answers.has(key)) return answers.get(key);
    let found = { state: 'failed', result: {} };
    try {
      if (target.kind === 'word') {
        const value = await api.readingLookup({
          text: target.text,
          context: target.context,
          source_language: language,
          target_language: support,
        });
        found = { state: value?.available ? 'ready' : 'unavailable', result: value || {} };
      } else {
        const value = await api.readingTranslate({
          source_language: language,
          target_language: support,
          segments: [{ segment_id: 's0', text: target.text.slice(0, TRANSLATE_LIMITS.text) }],
        });
        const translation =
          value?.status === 'ready' ? value.translations?.[0]?.translated_meaning || '' : '';
        found = translation
          ? { state: 'ready', result: { translation } }
          : { state: 'unavailable', result: {} };
      }
      answers.set(key, found);
    } catch {
      found = { state: 'failed', result: {} };
    }
    return found;
  }

  async function showAnswer(target) {
    hideToolbar();
    renderPanel(target, 'loading');
    focusRegion(panel);
    const found = await answer(target);
    if (!alive() || panelTarget !== target) return found;
    renderPanel(target, found.state, found.result);
    return found;
  }

  async function keep(target) {
    const found = translatable ? await showAnswer(target) : { result: {} };
    if (!panel) renderPanel(target, 'ready', found.result);
    const button = panel.querySelector('[data-panel-action="save"]');
    const report = progressReporter(panel.querySelector('[data-panel-status]'), ctx, alive);
    if (button) button.disabled = true;
    report.saving();
    try {
      await ctx.mutate(() =>
        api.saveLibraryVocabulary(
          keepPayload({ selection: target.text, result: found.result, context: target.context, title }),
        ),
      );
      if (origin?.why)
        memory.rememberLanguage({
          term: target.text,
          origin: origin.id || '',
          where: origin.where || title,
          why: origin.why,
          context: target.context,
        });
      savedTerms.add(String(target.text).trim().toLocaleLowerCase());
      const control = panel?.querySelector('[data-panel-action="save"]');
      if (control && alive()) {
        const state = document.createElement('span');
        state.className = 'reader-panel__kept';
        state.dataset.panelKept = '';
        state.textContent = c.selectionSaved;
        control.replaceWith(state);
      }
      report.saved(savedLanguageLink(c));
    } catch {
      report.failed(c.failedSave, () => keep(target));
      if (button && alive()) button.disabled = false;
    }
  }

  function speak(text) {
    if (!canSpeak) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = language === 'zh' ? 'zh-CN' : 'en-US';
    window.speechSynthesis.speak(utterance);
  }

  function runAction(action) {
    const target = panelTarget || active;
    if (!target) return;
    switch (action) {
      case 'translate':
      case 'retry':
        answers.delete(`${target.kind}:${target.text}`);
        showAnswer(target);
        break;
      case 'explain':
      case 'pattern': {
        /* Both go to the one explanation surface. "How this works" is the same
           request carrying the pattern question, which is what the Understanding
           Engine already accepts - not a grammar module of its own, and not a
           second way to reach AI. */
        const whole = target.kind === 'passage' ? explainBounds(target.text) : null;
        hideToolbar();
        closePanel();
        openUnderstanding(ctx, {
          selection: whole ? whole.selection : target.text,
          context: target.context.includes(whole ? whole.selection : target.text) ? target.context : whole?.context || target.text,
          title,
          origin,
          question: action === 'pattern' ? c.askPattern || '' : '',
        });
        break;
      }
      case 'save':
        keep(target);
        break;
      case 'pronounce':
        speak(target.text);
        break;
      default:
        break;
    }
  }

  /* Tapping a word.

     Selecting by dragging is fine with a mouse and awkward with a thumb, and
     for Chinese it is worse than awkward: there are no spaces, so a drag or a
     double-click cuts wherever it likes and hands the lookup half a word. So a
     single tap asks the shared tagger where the words in this paragraph are -
     the same local, non-AI segmentation Listening already uses - and selects
     the one the learner touched.

     It runs on a tap and never before: nothing is tokenised while the learner
     reads, and a paragraph is asked about once. If the tagger is unavailable
     the tap still works, on a plainer rule, rather than doing nothing. */
  async function tokensFor(index, text) {
    if (tokenised.has(index)) return tokenised.get(index);
    let tokens = null;
    try {
      const value = await api.annotateMediaText({
        text: text.slice(0, ANNOTATE_LIMIT),
        source_language: language,
      });
      const source = Array.from(value?.text === text.slice(0, ANNOTATE_LIMIT) ? value.text : '');
      tokens = (value?.annotations || [])
        .filter(
          (token) =>
            Number.isInteger(token?.start) &&
            Number.isInteger(token?.end) &&
            token.end > token.start &&
            token.end <= source.length,
        )
        .map((token) => ({
          // Annotation offsets count code points; the DOM counts UTF-16 units.
          start: source.slice(0, token.start).join('').length,
          end: source.slice(0, token.end).join('').length,
          pos: token.pos || '',
        }))
        .filter((token) => /[\p{L}\p{N}]/u.test(text.slice(token.start, token.end)));
    } catch {
      tokens = null;
    }
    tokenised.set(index, tokens);
    return tokens;
  }

  /* The character the pointer landed on, counted through the paragraph as the
     text was written - line breaks included, since a paragraph renders them as
     elements rather than as characters. */
  function offsetAt(paragraph, x, y) {
    const caret = document.caretPositionFromPoint
      ? document.caretPositionFromPoint(x, y)
      : null;
    const range = caret
      ? { node: caret.offsetNode, offset: caret.offset }
      : document.caretRangeFromPoint
        ? (() => {
            const found = document.caretRangeFromPoint(x, y);
            return found ? { node: found.startContainer, offset: found.startOffset } : null;
          })()
        : null;
    if (!range?.node || !paragraph.contains(range.node)) return null;
    let total = 0;
    const walker = document.createTreeWalker(paragraph, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    let node = walker.nextNode();
    while (node) {
      if (node === range.node) return total + (node.nodeType === 3 ? range.offset : 0);
      if (node.nodeType === 3) total += node.data.length;
      else if (node.tagName === 'BR') total += 1;
      node = walker.nextNode();
    }
    return null;
  }

  /* Without the tagger: a run of letters for an alphabet, and one character for
     a script written without spaces. Deliberately the smallest honest unit -
     guessing a longer Chinese word here would hand the lookup something the
     learner did not point at. */
  function plainWordAt(text, offset) {
    const at = Math.min(Math.max(0, offset), Math.max(0, text.length - 1));
    if (!/[\p{L}\p{N}]/u.test(text[at] || '')) return null;
    if (/[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]/u.test(text[at]))
      return { start: at, end: at + 1 };
    let start = at;
    let end = at + 1;
    const wordish = /[\p{L}\p{M}\p{N}'’-]/u;
    while (start > 0 && wordish.test(text[start - 1])) start -= 1;
    while (end < text.length && wordish.test(text[end])) end += 1;
    return { start, end };
  }

  function selectRange(paragraph, start, end) {
    const walker = document.createTreeWalker(paragraph, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    let total = 0;
    let from = null;
    let to = null;
    let node = walker.nextNode();
    while (node && !to) {
      const length = node.nodeType === 3 ? node.data.length : node.tagName === 'BR' ? 1 : 0;
      if (node.nodeType === 3) {
        if (!from && start >= total && start <= total + length) from = { node, offset: start - total };
        if (from && end >= total && end <= total + length) to = { node, offset: end - total };
      }
      total += length;
      node = walker.nextNode();
    }
    if (!from || !to) return false;
    const range = document.createRange();
    range.setStart(from.node, from.offset);
    range.setEnd(to.node, to.offset);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    return true;
  }

  async function tapWord(event) {
    if (event.target.closest('button, a, [data-panel-close]')) return;
    const article = page();
    const paragraph = event.target.closest('[data-block]');
    if (!article || !paragraph || !article.contains(paragraph)) return;
    const selection = window.getSelection?.();
    // A learner who dragged a selection meant that selection, not this tap.
    if (selection && !selection.isCollapsed && squash(selection.toString())) return;
    const index = Number(paragraph.dataset.block);
    const text = blocks[index]?.text;
    if (!text) return;
    const offset = offsetAt(paragraph, event.clientX, event.clientY);
    if (offset == null) return;
    const tokens = await tokensFor(index, text);
    if (!alive()) return;
    const span =
      tokens?.find((token) => offset >= token.start && offset < token.end) ||
      plainWordAt(text, offset);
    if (!span || !selectRange(paragraph, span.start, span.end)) return;
    evaluateSelection();
  }

  const evaluateSelection = () => {
    if (!alive()) return;
    const target = readSelection();
    if (target) showToolbar(target);
    else if (!panel) hideToolbar();
  };
  const onSelectionChange = () => {
    clearTimeout(selectionTimer);
    const selection = window.getSelection?.();
    if (!selection || selection.isCollapsed) {
      if (!panel) hideToolbar();
      return;
    }
    // A mouse drag is finished on pointerup; touch and keyboard settle here.
    if (coarse || !pointerDown) selectionTimer = setTimeout(evaluateSelection, coarse ? 450 : 200);
  };
  let pointerDown = false;
  const onPointerDown = (event) => {
    if (toolbar?.contains(event.target) || panel?.contains(event.target)) return;
    pointerDown = true;
    closeSettingsIfOutside(event);
    if (panel) closePanel();
    hideToolbar();
  };
  const onPointerUp = () => {
    if (!pointerDown) return;
    pointerDown = false;
    setTimeout(evaluateSelection, 10);
  };
  const closeSettingsIfOutside = (event) => {
    if (!settingsPop.hidden && !settingsPop.contains(event.target) && !settingsToggle.contains(event.target))
      closeSettings();
  };
  const onKeyDown = (event) => {
    if (event.key !== 'Escape') return;
    if (panel) {
      closePanel();
      page()?.focus?.({ preventScroll: true });
    } else if (toolbar) hideToolbar();
    else closeSettings({ restore: true });
  };
  const onPageScroll = () => {
    if (toolbar && active) hideToolbar();
    if (panel && !narrow()) closePanel();
  };
  body.addEventListener('click', (event) => {
    if (event.target.closest('[data-next]')) return;
    tapWord(event);
  });
  document.addEventListener('selectionchange', onSelectionChange);
  document.addEventListener('pointerdown', onPointerDown, true);
  document.addEventListener('pointerup', onPointerUp, true);
  document.addEventListener('keydown', onKeyDown);
  window.addEventListener('scroll', onPageScroll, { passive: true });

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
      clearTimeout(selectionTimer);
      if (progressFrame) cancelAnimationFrame(progressFrame);
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      window.removeEventListener('scroll', onPageScroll);
      document.removeEventListener('selectionchange', onSelectionChange);
      document.removeEventListener('pointerdown', onPointerDown, true);
      document.removeEventListener('pointerup', onPointerUp, true);
      document.removeEventListener('keydown', onKeyDown);
      hideToolbar();
      closePanel();
    },
  };
}
