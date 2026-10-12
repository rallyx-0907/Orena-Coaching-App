/* The phone shell hides on scroll (the human, 2026-10-12, D-181). On a phone, in the browsing places that have the
   phone header and the phone bar (rule 47: never on a learning workspace, never on the desktop), the header and the
   bar - with the Orena orb - slide away while the page scrolls down and come back when it scrolls up, and always at
   the top. The state is one attribute on the shell root, :root[data-chrome]:
     absent    the top of the page, a desktop, a learning workspace: the chrome as the design draws it;
     'hidden'  scrolled down: the header and the bar are moved out of view by a transform (no layout change);
     'shown'   scrolled up, away from the top: both are back, over the page.
   A route may START collapsed (route.chrome = 'collapsed', :root[data-chrome-start='collapsed']; D-181 option 1, the
   human, 2026-10-12: Word Detail): on a phone it arrives 'hidden', so its card has the whole height; the chrome comes
   back when the page scrolls up, and at the top when the learner pulls down (wheel / touch) or taps the page outside
   a control. A control in the chrome that has the focus is never hidden: focusing one shows the chrome. Every change
   is announced as an `orena:chrome` event on the root, so a screen that fits to the height can fit again.
   shell/shell.css draws the states (and drops the motion under prefers-reduced-motion); this module only decides. */

/* Movement smaller than this (a finger's jitter, a momentum tail) changes nothing. */
export const CHROME_SLACK_PX = 6;
/* Within this of the top the chrome is always shown, as at rest - unless the route starts collapsed. */
export const CHROME_TOP_PX = 4;
/* A pull at the top of a collapsed route longer than this brings the chrome back. */
export const CHROME_PULL_PX = 12;

/* The next state (pure): the attribute value, '' for absent, or null for "leave it as it is". */
export function nextChrome({ phone, browsing, top, delta, focused = false, collapsed = false }) {
  if (!phone || !browsing) return '';
  if (top <= CHROME_TOP_PX) {
    // A collapsed route stays collapsed at the top until the learner scrolls (or pulls) up, or focuses the chrome.
    if (collapsed) return focused || delta < -CHROME_SLACK_PX ? 'shown' : null;
    return '';
  }
  if (focused) return 'shown';
  if (delta > CHROME_SLACK_PX) return 'hidden';
  if (delta < -CHROME_SLACK_PX) return 'shown';
  return null;
}

/* The state a route arrives with (pure). */
export function arrivalChrome({ phone, browsing, collapsed }) {
  return phone && browsing && collapsed ? 'hidden' : '';
}

/* Where a tap at the top of a collapsed route does NOT bring the chrome back: on a control or on the card. */
const OWN_TARGET = 'button, a, input, textarea, select, label, [role="button"], [contenteditable], .c-vcard';

function apply(root, value) {
  if (value === null || (root.dataset.chrome || '') === value) return;
  if (value) root.dataset.chrome = value;
  else delete root.dataset.chrome;
  root.dispatchEvent(new CustomEvent('orena:chrome', { detail: { chrome: value } }));
}

/* Binds the one scroll listener, on the main column. `root` is the shell root (<html>), which carries the device,
   focus, bare and chrome-start attributes the decision reads. Returns the reset, which the router calls on every route
   change so a page always arrives with its chrome as its route wants it. */
export function bindChromeScroll(main, root = document.documentElement) {
  const phone = () => root.dataset.device === 'mobile';
  const browsing = () => root.dataset.focus !== '1' && root.dataset.bare !== '1';
  const collapsed = () => root.dataset.chromeStart === 'collapsed';
  const inChrome = (node) => Boolean(node?.closest?.('[data-part="mhead"], [data-part="bnav"]'));
  const state = () => ({ phone: phone(), browsing: browsing(), collapsed: collapsed() });
  let last = main.scrollTop;
  let frame = 0;
  const update = () => {
    frame = 0;
    const top = main.scrollTop;
    const delta = top - last;
    last = top;
    apply(root, nextChrome({ ...state(), top, delta, focused: inChrome(document.activeElement) }));
  };
  main.addEventListener('scroll', () => {
    if (!frame) frame = requestAnimationFrame(update);
  }, { passive: true });
  root.addEventListener('focusin', (event) => {
    if (inChrome(event.target) && root.dataset.chrome === 'hidden') apply(root, 'shown');
  });
  // At the top of a collapsed route there is no scroll to read: a pull down or a tap on the page reveals the chrome.
  const revealAtTop = () => {
    if (root.dataset.chrome === 'hidden' && collapsed() && main.scrollTop <= CHROME_TOP_PX) apply(root, 'shown');
  };
  main.addEventListener('wheel', (event) => {
    if (event.deltaY < 0) revealAtTop();
  }, { passive: true });
  let touchY = null;
  main.addEventListener('touchstart', (event) => { touchY = event.touches[0]?.clientY ?? null; }, { passive: true });
  main.addEventListener('touchmove', (event) => {
    const y = event.touches[0]?.clientY;
    if (touchY !== null && y - touchY > CHROME_PULL_PX) revealAtTop();
  }, { passive: true });
  main.addEventListener('click', (event) => {
    if (!event.target?.closest?.(OWN_TARGET)) revealAtTop();
  });
  return function resetChrome() {
    last = main.scrollTop;
    apply(root, arrivalChrome(state()));
  };
}
