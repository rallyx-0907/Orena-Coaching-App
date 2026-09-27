/* First-paint attributes for the new learner UI, run as a classic script before any stylesheet
   applies (D-089, Design Contract rules 30 and 48).

   - data-theme: the learner's own choice from the Reader's light/dark button, kept on this device
     under APPEARANCE_KEY, else the operating system's prefers-color-scheme. Follows the system
     live while no choice is stored.
   - data-device: "mobile" below 900px, else "desktop" - the design's two frames and nothing between.
   - lang: the interface language (the device's choice, else the browser's when Orena speaks it,
     else English), so :lang(vi) can pick a face with Vietnamese glyphs from the first paint.

   kit/device.js owns the same keys for the modules; this file only makes the first paint right. */
(function () {
  var root = document.documentElement;
  var APPEARANCE_KEY = 'orena.appearance';
  var INTERFACE_KEY = 'orena.interface';
  var SUPPORTED = ['en', 'vi', 'zh'];
  function stored(key) {
    try {
      return window.localStorage.getItem(key) || '';
    } catch (error) {
      return '';
    }
  }
  var dark = window.matchMedia('(prefers-color-scheme: dark)');
  var narrow = window.matchMedia('(max-width: 899px)');
  function theme() {
    var chosen = stored(APPEARANCE_KEY);
    root.dataset.theme = chosen === 'light' || chosen === 'dark' ? chosen : dark.matches ? 'dark' : 'light';
  }
  function device() {
    root.dataset.device = narrow.matches ? 'mobile' : 'desktop';
  }
  function match(value) {
    var code = String(value || '').trim().toLowerCase();
    if (SUPPORTED.indexOf(code) >= 0) return code;
    var base = code.split(/[-_]/)[0];
    return SUPPORTED.indexOf(base) >= 0 ? base : '';
  }
  var ui = match(stored(INTERFACE_KEY));
  if (!ui) {
    var langs = navigator.languages || [navigator.language];
    for (var i = 0; i < langs.length && !ui; i += 1) ui = match(langs[i]);
  }
  root.lang = ui || 'en';
  theme();
  device();
  if (dark.addEventListener) {
    dark.addEventListener('change', theme);
    narrow.addEventListener('change', device);
  }
})();
