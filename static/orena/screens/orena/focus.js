/* Orena's surfaces repaint their whole markup on every change of the conversation or the voice
   phase. A repaint must not take the keyboard away: the control that had focus (and the caret in
   the message box) is found again in the new markup. */
const FOCUS_ATTRS = [
  'data-input',
  'data-send',
  'data-to-voice',
  'data-voice-main',
  'data-voice-speak',
  'data-voice-close',
  'data-voice-full-main',
  'data-voice-full-speak',
  'data-voice-full-type',
  'data-voice-full-close',
  'data-starter',
  'data-retry',
];

function focusKey(element) {
  for (const attr of FOCUS_ATTRS) {
    if (element.hasAttribute(attr)) {
      const value = element.getAttribute(attr);
      return { selector: value ? `[${attr}="${CSS.escape(value)}"]` : `[${attr}]`, caret: element.selectionStart != null ? [element.selectionStart, element.selectionEnd] : null };
    }
  }
  return null;
}

/* Runs `render()` (which replaces `root`'s content) and puts focus back where it was inside `root`. */
export function keepFocus(root, render) {
  const active = document.activeElement;
  const key = active && root.contains(active) ? focusKey(active) : null;
  render();
  if (!key) return;
  const next = root.querySelector(key.selector);
  if (!next || next.disabled) return;
  next.focus({ preventScroll: true });
  if (key.caret && typeof next.setSelectionRange === 'function') {
    try {
      next.setSelectionRange(key.caret[0], key.caret[1]);
    } catch {
      /* not a text field */
    }
  }
}
