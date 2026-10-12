/* The phone shell hides on scroll (the human, 2026-10-12, D-17Y). On a phone, in the browsing places that have the
   phone header and the phone bar (rule 47: never on a learning workspace, never on the desktop), the header and the
   bar - with the Orena orb - slide away while the page scrolls down and come back when it scrolls up, and always at
   the top. The state is one attribute on the shell root, :root[data-chrome]:
     absent    the top of the page, a desktop, a learning workspace: the chrome as the design draws it;
     'hidden'  scrolled down: the header and the bar are moved out of view by a transform (no layout change);
     'shown'   scrolled up, away from the top: both are back, over the page.
   A control in the chrome that has the focus is never hidden: focusing one shows the chrome. shell/shell.css draws the
   states (and drops the motion under prefers-reduced-motion); this module only decides them. */

/* Movement smaller than this (a finger's jitter, a momentum tail) changes nothing. */
export const CHROME_SLACK_PX = 6;
/* Within this of the top the chrome is always shown, as at rest. */
export const CHROME_TOP_PX = 4;

/* The next state (pure): the attribute value, '' for absent, or null for "leave it as it is". */
export function nextChrome({ phone, browsing, top, delta, focused = false }) {
  if (!phone || !browsing || top <= CHROME_TOP_PX) return '';
  if (focused) return 'shown';
  if (delta > CHROME_SLACK_PX) return 'hidden';
  if (delta < -CHROME_SLACK_PX) return 'shown';
  return null;
}

function apply(root, value) {
  if (value === null || (root.dataset.chrome || '') === value) return;
  if (value) root.dataset.chrome = value;
  else delete root.dataset.chrome;
}

/* Binds the one scroll listener, on the main column. `root` is the shell root (<html>), which carries the device,
   focus and bare attributes the decision reads. Returns the reset, which the router calls on every route change so a
   page always arrives with its chrome in place. */
export function bindChromeScroll(main, root = document.documentElement) {
  const phone = () => root.dataset.device === 'mobile';
  const browsing = () => root.dataset.focus !== '1' && root.dataset.bare !== '1';
  const inChrome = (node) => Boolean(node?.closest?.('[data-part="mhead"], [data-part="bnav"]'));
  let last = main.scrollTop;
  let frame = 0;
  const update = () => {
    frame = 0;
    const top = main.scrollTop;
    const delta = top - last;
    last = top;
    apply(root, nextChrome({ phone: phone(), browsing: browsing(), top, delta, focused: inChrome(document.activeElement) }));
  };
  main.addEventListener('scroll', () => {
    if (!frame) frame = requestAnimationFrame(update);
  }, { passive: true });
  root.addEventListener('focusin', (event) => {
    if (inChrome(event.target) && root.dataset.chrome === 'hidden') root.dataset.chrome = 'shown';
  });
  return function resetChrome() {
    last = main.scrollTop;
    apply(root, '');
  };
}
