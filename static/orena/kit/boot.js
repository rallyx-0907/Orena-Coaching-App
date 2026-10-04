/* First-paint attributes for the new learner UI, run as a classic script before any stylesheet
   applies (D-089, Design Contract rules 30 and 48).

   - data-theme: the learner's own choice from Settings' Appearance row (D-067 review item: Light /
     Dark / System, screens/settings), kept on this device under APPEARANCE_KEY, else the operating
     system's prefers-color-scheme. The stored value is 'light', 'dark' or 'system'; anything else
     - unset, 'system' itself, or a corrupted/unrecognised value - reads the same as System and
     follows the OS live while it stays chosen, so there is never a flash from a guess this file and
     kit/device.js resolve differently.
   - data-device: "mobile" below 900px, else "desktop" - the design's two frames and nothing between.
   - lang: the interface language (the device's choice, else the browser's when Orena speaks it,
     else English), so :lang(vi) can pick a face with Vietnamese glyphs from the first paint.

   kit/device.js owns the same key and the same fallback for the modules (its own `appearance()`/
   `setAppearance()`); this file only makes the first paint right, before that module has loaded. */
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
  var palette = stored('orena.palette');
  root.dataset.palette = ['indigo', 'orchid', 'blue', 'rose'].indexOf(palette) >= 0 ? palette : 'indigo';
  theme();
  device();
  if (dark.addEventListener) {
    dark.addEventListener('change', theme);
    narrow.addEventListener('change', device);
  }
})();
