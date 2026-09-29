/* Tap a word, tap a sentence, select text: the Reader's own pointer layer (frame 14's `rw.onTap`,
   `sn.onTap` and `rdMouseUp`). It only reports what the learner pointed at; what each thing does
   - the word sheet, the word-role toast, the selection toolbar - is the screen's.

   static/orena/capabilities/lexical.js is the older, shared tap layer for Reading and Listening,
   but it builds the OLD Reader's own sheet (`ui/quick-sheet.js`) and reaches it only through
   `ui/html.js`/`ui/reading-room.js` - old presentation this screen may not import (brief section 0).
   It also acts on a tap before any choice is offered, which is the old interaction the design
   does not draw (rule 44): here a tap on a word opens that word, a tap on the sentence around it
   offers the sentence's actions, and selected text offers them too. Recorded as a kit request
   (rewire capabilities/lexical.js onto the new overlay) rather than edited here.

   Words are the `<span data-w>` elements the screen draws (reader/model.js#segmentSentence). A
   script written without spaces that the tagger has not segmented yet has none, so the character
   under the pointer stands in for the word - `plainWordAt` (product/word-span.js) is the one shared,
   DOM-free rule for that, imported here and by capabilities/lexical.js rather than kept as two
   copies of the same function. */
import { plainWordAt } from '../../product/word-span.js';

const squash = (value) => String(value ?? '').replace(/\s+/g, ' ').trim();

/* The character offset a pointer landed on, counted through the sentence's own text nodes. */
function offsetAt(unit, x, y) {
  let caret = null;
  if (document.caretPositionFromPoint) {
    const found = document.caretPositionFromPoint(x, y);
    if (found) caret = { node: found.offsetNode, offset: found.offset };
  } else if (document.caretRangeFromPoint) {
    const found = document.caretRangeFromPoint(x, y);
    if (found) caret = { node: found.startContainer, offset: found.startOffset };
  }
  if (!caret?.node || !unit.contains(caret.node)) return null;
  let total = 0;
  const walker = document.createTreeWalker(unit, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();
  while (node) {
    if (node === caret.node) return total + caret.offset;
    total += node.data.length;
    node = walker.nextNode();
  }
  return null;
}

/* `root` bounds the reading column. `unitOf(node)` finds the sentence element a node belongs to (or
   null). Callbacks: `onTapWord({ word, unit })`, `onTapSentence({ unit })`, `onSelect({ unit, text })`.
   Mounted once per Reader visit; returns a cleanup that drops every listener. */
export function mountReaderLexical({ root, unitOf, onTapWord, onTapSentence, onSelect }) {
  let alive = true;
  let selectionTimer = 0;

  const elementOf = (node) => (node?.nodeType === 1 ? node : node?.parentElement) || null;

  function selectedText() {
    const selection = window.getSelection?.();
    return selection && !selection.isCollapsed ? squash(selection.toString()) : '';
  }

  function onClick(event) {
    if (!alive) return;
    const target = elementOf(event.target);
    const unit = unitOf(target);
    if (!unit || !root.contains(unit)) return;
    // A learner who dragged a selection meant that selection (evaluateSelection below), not a tap
    // on whatever character the drag happened to end on.
    if (selectedText().length >= 2) return;
    const wordEl = target?.closest?.('[data-w]');
    if (wordEl && unit.contains(wordEl)) {
      onTapWord({ word: wordEl.dataset.w, unit });
      return;
    }
    const offset = offsetAt(unit, event.clientX, event.clientY);
    if (offset != null) {
      const text = unit.textContent || '';
      const span = plainWordAt(text, offset);
      if (span) {
        onTapWord({ word: text.slice(span.start, span.end), unit });
        return;
      }
    }
    onTapSentence({ unit });
  }

  function evaluateSelection() {
    if (!alive) return;
    const selection = window.getSelection?.();
    if (!selection || selection.isCollapsed || !selection.rangeCount) return;
    const range = selection.getRangeAt(0);
    if (!root.contains(range.commonAncestorContainer)) return;
    const text = squash(selection.toString());
    if (text.length < 2) return;
    // The sentence the selection starts in (frame 14's `rdMouseUp` reads the anchor node).
    const unit = unitOf(elementOf(selection.anchorNode)) || unitOf(elementOf(range.commonAncestorContainer));
    if (!unit) return;
    onSelect({ unit, text });
  }

  function onSelectionChange() {
    clearTimeout(selectionTimer);
    const selection = window.getSelection?.();
    if (!selection || selection.isCollapsed) return;
    selectionTimer = window.setTimeout(evaluateSelection, 250);
  }

  root.addEventListener('click', onClick);
  document.addEventListener('selectionchange', onSelectionChange);

  return function destroy() {
    alive = false;
    clearTimeout(selectionTimer);
    root.removeEventListener('click', onClick);
    document.removeEventListener('selectionchange', onSelectionChange);
  };
}
