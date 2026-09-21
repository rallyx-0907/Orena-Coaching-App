// Runs before styles paint. Orena has one visual system, Dark Glass (D-066), so
// there is no preference to read and no theme to choose: this only marks the
// document and lets the browser's own chrome match the ground it frames.
//
// It replaces the D-059 registry of `ink` and `paper` themes. A stored
// 'orena.theme' choice from that build is simply ignored.
(() => {
  const root = document.documentElement;
  root.dataset.theme = 'glass';
  root.dataset.appearance = 'dark';

  /* The chrome colour is read from the resolved token rather than kept as a
     second copy of the palette. The stylesheet is not parsed on the first call -
     this script runs ahead of it deliberately, so the marks are right before
     anything paints - so the read is retried once the document is ready. */
  function paintBrowserChrome() {
    const meta = document.querySelector('meta[name="theme-color"]');
    if (!meta) return;
    const ground = getComputedStyle(root).getPropertyValue('--paper').trim();
    if (ground) meta.setAttribute('content', ground);
  }

  paintBrowserChrome();
  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', paintBrowserChrome, { once: true });
})();
