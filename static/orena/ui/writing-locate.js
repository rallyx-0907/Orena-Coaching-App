/* "Where is that in what I wrote?"

   A review quotes the learner's own wording back at them. In a paragraph of
   two hundred words that quote is a needle, and asking somebody to find it by
   eye is asking them to do the boring half of revising. The browser already
   has a way to point at a run of text inside a box - its own selection - so
   this uses that rather than inventing a highlight layer over a textarea,
   which cannot hold markup anyway (DESIGN_CONTRACT: one semantic treatment,
   not five).

   Selecting is also the right thing to leave behind: the caret is in the
   phrase, so the learner types over it and the revision has begun. */
export function locateInText(box, quote) {
  const needle = String(quote || '');
  if (!box || !needle) return false;
  const at = box.value.indexOf(needle);
  if (at < 0) return false;
  box.focus({ preventScroll: true });
  box.setSelectionRange(at, at + needle.length);
  /* A textarea does not scroll a selection into view on its own. The line the
     match starts on is measured from the text before it, so the box is moved
     to put that line a little above the middle - close enough to read the
     sentence around it, which is what makes the quote make sense. */
  const before = box.value.slice(0, at);
  const lines = before.split('\n').length - 1;
  const lineHeight =
    parseFloat(getComputedStyle(box).lineHeight) ||
    parseFloat(getComputedStyle(box).fontSize) * 1.5 ||
    20;
  const target = lines * lineHeight - box.clientHeight / 3;
  box.scrollTop = Math.max(0, target);
  return true;
}
