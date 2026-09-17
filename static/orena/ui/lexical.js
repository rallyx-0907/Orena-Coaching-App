/* One way to ask about language on screen, wherever it is on screen.

   Reading built this: tap a word and it is looked up, select a phrase and it
   can be translated, explained, asked how it works, kept, or spoken. Listening
   needs exactly the same thing over a transcript line, and the one way to be
   sure a learner meets the same behaviour in both rooms - and that the two do
   not drift apart the first time either is touched - is for there to be one
   implementation. So the layer lives here and both rooms mount it.

   What the rooms differ in is only where the text is: Reading has paragraphs
   with `data-block`, Listening has transcript lines with `data-segment`. That
   difference is the `units` adapter, and it is the whole difference.

   Nothing here runs on its own. A lookup, a translation, a tokenisation and an
   explanation each happen because the learner asked for one. Explain is the
   only path to a provider, exactly as it was in the reader. */
import { esc, focusRegion } from './html.js';
import { openUnderstanding } from './understanding.js';
import { progressReporter, savedLanguageLink } from './patterns.js';
import {
  EXPLAIN_LIMITS,
  LOOKUP_LIMITS,
  TRANSLATE_LIMITS,
  explainBounds,
  keepPayload,
  lookupPanelHtml,
  selectionActions,
  selectionKind,
  selectionToolbarHtml,
  sentenceAround,
} from './reading-room.js';

// What the shared tagger accepts in one request (media_interaction.MediaAnnotateIn).
const ANNOTATE_LIMIT = 1200;
const narrow = () => window.matchMedia('(max-width: 700px)').matches;
const elementOf = (node) => (node?.nodeType === 1 ? node : node?.parentElement) || null;
const squash = (value) => String(value ?? '').replace(/\s+/g, ' ').trim();

/* The character the pointer landed on, counted through the unit as its text
   was written - line breaks included, since a paragraph renders them as
   elements rather than as characters. */
function offsetAt(unit, x, y) {
  const caret = document.caretPositionFromPoint ? document.caretPositionFromPoint(x, y) : null;
  const point = caret
    ? { node: caret.offsetNode, offset: caret.offset }
    : document.caretRangeFromPoint
      ? (() => {
          const found = document.caretRangeFromPoint(x, y);
          return found ? { node: found.startContainer, offset: found.startOffset } : null;
        })()
      : null;
  if (!point?.node || !unit.contains(point.node)) return null;
  let total = 0;
  const walker = document.createTreeWalker(unit, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  let node = walker.nextNode();
  while (node) {
    if (node === point.node) return total + (node.nodeType === 3 ? point.offset : 0);
    if (node.nodeType === 3) total += node.data.length;
    else if (node.tagName === 'BR') total += 1;
    node = walker.nextNode();
  }
  return null;
}

/* Without the tagger: a run of letters for an alphabet, and one character for a
   script written without spaces. Deliberately the smallest honest unit -
   guessing a longer Chinese word here would hand the lookup something the
   learner did not point at. */
export function plainWordAt(text, offset) {
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

function selectRange(unit, start, end) {
  const walker = document.createTreeWalker(unit, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
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

/* `surface` hosts the toolbar and the panel and must be positioned. `units`
   answers two questions about wherever the learner touched: which element is
   the smallest containing unit of text, and what that unit's text says. */
export function mountLexicalLayer({
  surface,
  ctx,
  units,
  title,
  origin = null,
  alive = () => true,
}) {
  const { api, c, language, memory } = ctx;
  const support = ctx.support;
  const translatable = Boolean(support) && support !== language;
  const canSpeak = typeof window !== 'undefined' && 'speechSynthesis' in window;
  const answers = new Map();
  const tokenised = new Map();
  const savedTerms = new Set(
    Object.keys(memory?.value?.keptLanguage || {}).map((term) => term.toLocaleLowerCase()),
  );
  const alreadyKept = (text) => savedTerms.has(String(text).trim().toLocaleLowerCase());

  let active = null;
  let toolbar = null;
  let panel = null;
  let panelTarget = null;
  let selectionTimer = 0;
  let pointerDown = false;
  const coarse = window.matchMedia?.('(pointer: coarse)')?.matches;

  const readSelection = () => {
    const selection = window.getSelection?.();
    const root = units.root();
    if (!root || !selection || selection.isCollapsed || !selection.rangeCount) return null;
    const range = selection.getRangeAt(0);
    if (!root.contains(range.commonAncestorContainer)) return null;
    const text = squash(selection.toString());
    const kind = selectionKind(text, language);
    if (!kind) return null;
    const startUnit = units.unitOf(elementOf(range.startContainer));
    const endUnit = units.unitOf(elementOf(range.endContainer));
    const unitText =
      startUnit && startUnit === endUnit ? squash(units.textOf(startUnit)) : '';
    const at = unitText ? unitText.indexOf(text) : -1;
    const limit = kind === 'passage' ? EXPLAIN_LIMITS.context : LOOKUP_LIMITS.context;
    const context = at >= 0 ? sentenceAround(unitText, at, at + text.length, limit) : text;
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
      surface.append(toolbar);
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
      surface.append(panel);
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

  /* The device's own speech, for the selected language rather than for the
     interface. This is lexical pronunciation: hearing this word said, which is
     a different act from replaying the line it sits in. */
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
          context: target.context.includes(whole ? whole.selection : target.text)
            ? target.context
            : whole?.context || target.text,
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
     single tap asks the shared tagger where the words in this unit are - the
     same local, non-AI segmentation the transcript's close look already uses -
     and selects the one the learner touched.

     It runs on a tap and never before, and a unit is asked about once. */
  async function tokensFor(key, text) {
    if (tokenised.has(key)) return tokenised.get(key);
    let tokens = null;
    try {
      const asked = text.slice(0, ANNOTATE_LIMIT);
      const value = await api.annotateMediaText({ text: asked, source_language: language });
      const source = Array.from(value?.text === asked ? value.text : '');
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
    tokenised.set(key, tokens);
    return tokens;
  }

  async function tapWord(event) {
    if (event.target.closest('button, a, [data-panel-close]')) return;
    const root = units.root();
    const unit = units.unitOf(event.target);
    if (!root || !unit || !root.contains(unit)) return;
    const selection = window.getSelection?.();
    // A learner who dragged a selection meant that selection, not this tap.
    if (selection && !selection.isCollapsed && squash(selection.toString())) return;
    const text = units.textOf(unit);
    if (!text) return;
    const offset = offsetAt(unit, event.clientX, event.clientY);
    if (offset == null) return;
    const tokens = await tokensFor(units.keyOf(unit), text);
    if (!alive()) return;
    const span =
      tokens?.find((token) => offset >= token.start && offset < token.end) ||
      plainWordAt(text, offset);
    if (!span || !selectRange(unit, span.start, span.end)) return;
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
  const onPointerDown = (event) => {
    if (toolbar?.contains(event.target) || panel?.contains(event.target)) return;
    pointerDown = true;
    if (panel) closePanel();
    hideToolbar();
  };
  const onPointerUp = () => {
    if (!pointerDown) return;
    pointerDown = false;
    setTimeout(evaluateSelection, 10);
  };
  const onKeyDown = (event) => {
    if (event.key !== 'Escape') return;
    if (panel) {
      closePanel();
      units.root()?.focus?.({ preventScroll: true });
    } else if (toolbar) hideToolbar();
  };
  const onPageScroll = () => {
    if (toolbar && active) hideToolbar();
    if (panel && !narrow()) closePanel();
  };

  document.addEventListener('selectionchange', onSelectionChange);
  document.addEventListener('pointerdown', onPointerDown, true);
  document.addEventListener('pointerup', onPointerUp, true);
  document.addEventListener('keydown', onKeyDown);
  window.addEventListener('scroll', onPageScroll, { passive: true });

  return {
    tapWord,
    evaluateSelection,
    closePanel,
    hideToolbar,
    /* A room that repaints its own text drops whatever it had tokenised for
       the units it just replaced, rather than answering a tap from a cache
       about text that is no longer there. */
    forget(key) {
      if (key === undefined) tokenised.clear();
      else tokenised.delete(key);
    },
    destroy() {
      clearTimeout(selectionTimer);
      document.removeEventListener('selectionchange', onSelectionChange);
      document.removeEventListener('pointerdown', onPointerDown, true);
      document.removeEventListener('pointerup', onPointerUp, true);
      document.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('scroll', onPageScroll);
      hideToolbar();
      closePanel();
    },
  };
}
