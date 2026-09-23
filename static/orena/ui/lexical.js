/* One way to ask about language on screen, wherever it is on screen.

   Reading built this: tap a word or select a sentence and the Quick Sheet
   (ui/quick-sheet.js, D-066) opens on it. Listening needs exactly the same
   thing over a transcript line, and the one way to be
   sure a learner meets the same behaviour in both rooms - and that the two do
   not drift apart the first time either is touched - is for there to be one
   implementation. So the layer lives here and both rooms mount it.

   What the rooms differ in is only where the text is: Reading has paragraphs
   with `data-block`, Listening has transcript lines with `data-segment`. That
   difference is the `units` adapter, and it is the whole difference.

   Nothing here runs on its own. A lookup, a translation, a tokenisation and an
   explanation each happen because the learner asked for one. */
import { focusRegion } from './html.js';
import { createQuickSheet } from './quick-sheet.js';
import {
  EXPLAIN_LIMITS,
  LOOKUP_LIMITS,
  TRANSLATE_LIMITS,
  selectionKind,
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

/* `surface` hosts the sheet and must be positioned. `units`
   answers two questions about wherever the learner touched: which element is
   the smallest containing unit of text, and what that unit's text says. */
export function mountLexicalLayer({
  surface,
  ctx,
  units,
  title,
  origin = null,
  alive = () => true,
  /* Where the answer is shown. With a `dock` - the reader's side panel on a
     desk - the panel lives inside it, as the approved reader draws it; without
     one it anchors to the word, and on a phone CSS makes it the bottom sheet.
     `onPanel` lets the host restore its own placeholder when nothing is
     looked up. */
  dock = null,
  onPanel = () => {},
}) {
  const { api, c, language, memory } = ctx;
  const support = ctx.support;
  const translatable = Boolean(support) && support !== language;
  const canSpeak = typeof window !== 'undefined' && 'speechSynthesis' in window;
  const tokenised = new Map();
  const savedTerms = new Set(
    Object.keys(memory?.value?.keptLanguage || {}).map((term) => term.toLocaleLowerCase()),
  );
  const alreadyKept = (text) => savedTerms.has(String(text).trim().toLocaleLowerCase());

  let sheet = null;
  let panel = null;
  let scrim = null;
  let panelTarget = null;
  let selectionTimer = 0;
  let pointerDown = false;
  let lastThread = '';
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

  const dockNode = () => (typeof dock === 'function' ? dock() : dock) || null;
  // Replacing one sheet with the next is not closing: the host is told only when the layer ends.
  const closePanel = (notify = true) => {
    sheet?.cancel?.();
    panel?.remove();
    scrim?.remove();
    panel = null;
    scrim = null;
    panelTarget = null;
    sheet = null;
    lastThread = '';
    if (notify) onPanel(false);
  };
  /* A popover hangs off its word; on a phone CSS makes the same element the
     bottom sheet, so nothing is positioned there. */
  const anchorBelow = (element, rect) => {
    if (narrow()) return element.removeAttribute('style');
    const gap = 10;
    const width = element.offsetWidth;
    const height = element.offsetHeight;
    const room = document.documentElement.clientWidth;
    // Below the word, as the baseline draws it; above only when there is no room below.
    const below = rect.bottom + gap;
    const fits = below + height <= window.innerHeight - gap;
    const top = fits ? below : Math.max(gap, rect.top - gap - height);
    element.dataset.placement = fits ? 'below' : 'above';
    const left = Math.min(Math.max(gap, rect.left + rect.width / 2 - width / 2), room - width - gap);
    element.style.top = `${Math.round(top)}px`;
    element.style.left = `${Math.round(left)}px`;
  };

  const paintSheet = (html, state) => {
    const first = !panel?.isConnected;
    if (!panel) {
      panel = document.createElement('div');
      panel.setAttribute('role', 'dialog');
      panel.setAttribute('aria-modal', 'false');
      panel.setAttribute('aria-label', panelTarget.text);
      panel.tabIndex = -1;
      // Pressing a control must not take the selection away with the mouse press.
      panel.addEventListener('mousedown', (event) => {
        if (event.target.closest('button')) event.preventDefault();
      });
      panel.addEventListener('click', (event) => {
        const control = event.target.closest('[data-qs]');
        if (control && sheet) sheet.act(control.dataset.qs, control.dataset);
      });
      panel.addEventListener('submit', (event) => {
        const form = event.target.closest('[data-qs-form]');
        if (!form || !sheet) return;
        event.preventDefault();
        const question = form.elements.question?.value || '';
        form.reset();
        sheet.ask(question);
      });
    }
    const host = dockNode();
    const docked = Boolean(host);
    panel.className = `qs qs--${state.kind} qs--${state.view}${docked ? ' qs--docked' : ''}`;
    /* The sheet repaints whenever an answer arrives, which is seconds after the
       learner has started typing the next question. What they typed, and where
       the caret was, survive the repaint. */
    const typing = panel.querySelector('input[name="question"]');
    const draft = typing
      ? { value: typing.value, focused: document.activeElement === typing, at: typing.selectionStart }
      : null;
    panel.innerHTML = html;
    const typed = panel.querySelector('input[name="question"]');
    if (draft && typed) {
      typed.value = draft.value;
      if (draft.focused) {
        typed.focus({ preventScroll: true });
        try {
          typed.setSelectionRange(draft.at, draft.at);
        } catch {
          // A caret that cannot be restored is not worth failing the paint for.
        }
      }
    }
    /* A new answer arrives above the composer and may be below the fold in a
       tall panel; when the thread changed, bring the newest turn into view. */
    const threadKey = (state.thread || []).map((turn) => `${turn.id}:${turn.state}`).join(',');
    if (threadKey && threadKey !== lastThread) panel.querySelector('.qs-turn:last-child')?.scrollIntoView({ block: 'nearest' });
    lastThread = threadKey;
    if (docked) {
      panel.removeAttribute('style');
      if (panel.parentElement !== host) host.replaceChildren(panel);
    } else {
      if (narrow() && !scrim) {
        scrim = document.createElement('div');
        scrim.className = 'qs-scrim';
        scrim.addEventListener('click', closePanel);
        surface.append(scrim);
      }
      if (panel.parentElement !== surface) surface.append(panel);
      anchorBelow(panel, panelTarget.rect);
    }
    if (first) {
      focusRegion(panel);
      onPanel(true);
    }
  };

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

  /* One sheet per selection. A word opens the word sheet, and a phrase or a
     passage opens the sentence sheet: the same layer, never a second surface. */
  function openSheet(target) {
    // The same word in another sentence is another question: only the very same selection is left alone.
    if (panel && panelTarget && panelTarget.text === target.text && panelTarget.context === target.context) return;
    if (panel) closePanel(false);
    panelTarget = target;
    sheet = createQuickSheet({
      ctx,
      target,
      title,
      alive,
      paint: paintSheet,
      close: () => {
        closePanel();
        units.root()?.focus?.({ preventScroll: true });
      },
      speak,
      statusEl: () => panel?.querySelector('[data-panel-status]'),
      remember: (term, context) => {
        savedTerms.add(String(term).trim().toLocaleLowerCase());
        if (origin?.why)
          memory.rememberLanguage({
            term,
            origin: origin.id || '',
            where: origin.where || title,
            why: origin.why,
            context,
          });
      },
    });
    sheet.state.kept = alreadyKept(target.text);
    sheet.load();
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

  /* Only the latest tap is answered: the tagger may still be working on the word before it. */
  let tapSeq = 0;
  // What the last tap selected. Inside a control (a transcript row is a button) a later press does not
  // clear a selection, so a selection that is only our own last tap must not read as the learner's drag.
  let tapMade = '';
  async function tapWord(event) {
    const seq = ++tapSeq;
    const root = units.root();
    const unit = units.unitOf(event.target);
    /* A real control keeps its tap. A transcript row is one - a button that
       seeks - and the words inside it are what the learner meant, so a control
       that holds the unit does not count. */
    const control = event.target.closest('button, a, [data-qs]');
    if (control && !(unit && control.contains(unit))) return;
    if (!root || !unit || !root.contains(unit)) return;
    const selection = window.getSelection?.();
    // A learner who dragged a selection meant that selection, not this tap.
    if (selection && !selection.isCollapsed && squash(selection.toString()) && squash(selection.toString()) !== tapMade) return;
    const text = units.textOf(unit);
    if (!text) return;
    const offset = offsetAt(unit, event.clientX, event.clientY);
    if (offset == null) return;
    const tokens = await tokensFor(units.keyOf(unit), text);
    if (!alive() || seq !== tapSeq) return;
    const span =
      tokens?.find((token) => offset >= token.start && offset < token.end) ||
      plainWordAt(text, offset);
    if (!span || !selectRange(unit, span.start, span.end)) return;
    tapMade = squash(window.getSelection?.()?.toString() || '');
    evaluateSelection();
  }

  /* Touching a word, or selecting a phrase or a sentence, opens the sheet on it
     (D-066: one layer, in place, never a page change). Nothing is asked of a
     provider until the learner asks: the first answer is the dictionary's. */
  const evaluateSelection = () => {
    if (!alive()) return;
    const target = readSelection();
    if (!target) return;
    openSheet(target);
  };
  const onSelectionChange = () => {
    clearTimeout(selectionTimer);
    const selection = window.getSelection?.();
    if (!selection || selection.isCollapsed) return;
    // A mouse drag is finished on pointerup; touch and keyboard settle here.
    if (coarse || !pointerDown) selectionTimer = setTimeout(evaluateSelection, coarse ? 450 : 200);
  };
  const onPointerDown = (event) => {
    if (panel?.contains(event.target) || scrim?.contains(event.target)) return;
    pointerDown = true;
    if (panel) closePanel();
  };
  const onPointerUp = () => {
    if (!pointerDown) return;
    pointerDown = false;
    setTimeout(evaluateSelection, 10);
  };
  const onKeyDown = (event) => {
    if (event.key !== 'Escape' || !panel) return;
    closePanel();
    units.root()?.focus?.({ preventScroll: true });
  };
  const onPageScroll = () => {
    if (panel && !narrow() && !dockNode()) closePanel();
  };

  document.addEventListener('selectionchange', onSelectionChange);
  document.addEventListener('pointerdown', onPointerDown, true);
  document.addEventListener('pointerup', onPointerUp, true);
  document.addEventListener('keydown', onKeyDown);
  window.addEventListener('scroll', onPageScroll, { passive: true });
  // The sheet belongs to the screen it was opened on: going anywhere else closes it.
  const onRouteChange = () => closePanel();
  window.addEventListener('hashchange', onRouteChange);

  return {
    /* The support-language layer a room can turn on over its own text. It is
       here, with every other answer about text, so Reading and Listening
       cannot drift into two translators (one implementation, one contract).
       Returns a Map of segment index to translated line; a failure returns an
       empty map and the room simply shows no layer. */
    async translateBlocks(segments) {
      if (!translatable || !segments.length) return new Map();
      const out = new Map();
      try {
        const value = await api.readingTranslate({
          source_language: language,
          target_language: support,
          segments: segments.map(({ index, text }) => ({
            segment_id: `b${index}`,
            text: String(text).slice(0, TRANSLATE_LIMITS.text),
          })),
        });
        for (const translated of value?.translations || []) {
          const index = Number(String(translated.segment_id).slice(1));
          if (Number.isInteger(index) && translated.translated_meaning)
            out.set(index, translated.translated_meaning);
        }
      } catch {
        // No layer; the text is untouched.
      }
      return out;
    },
    tapWord,
    evaluateSelection,
    closePanel,
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
      window.removeEventListener('hashchange', onRouteChange);
      closePanel();
    },
  };
}
