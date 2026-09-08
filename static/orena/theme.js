// Runs before styles paint. One preference, including a live system default.
// This small DOM adapter is intentionally independent of auth and routing.
//
// The registry below is the canonical list of Orena themes. A theme has an
// identity and, separately, an appearance: "deep-forest" is the identity,
// "dark" is only how bright it is. The product used to conflate the two - the
// preference was literally the string 'light' or 'dark' - which is why a third
// theme could not exist without rewriting the switch and the settings UI.
//
// Adding a theme is an entry here plus a [data-theme] block in theme.css.
// Nothing else. Learner-facing names live in ui/copy.js with every other
// string, so a new theme is translated the same way everything else is.
(() => {
  const key = 'orena.theme';
  const THEMES = [
    { id: 'paper', appearance: 'light', mood: 'reading-room' },
    { id: 'night-ink', appearance: 'dark', mood: 'evening-indoors' },
    { id: 'deep-forest', appearance: 'dark', mood: 'evening-field' },
    { id: 'sage-field', appearance: 'light', mood: 'morning' },
  ];
  // What "follow the system" resolves to. Appearance chooses; identity is the
  // product's decision, not the operating system's.
  const SYSTEM_DEFAULT = { light: 'paper', dark: 'night-ink' };

  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const known = (id) => THEMES.some((theme) => theme.id === id);
  /* A preference written by an older build said 'light' or 'dark'. Those are
     appearances, and each still names exactly one theme, so they are read as
     that theme rather than discarded - nobody loses their choice to an
     upgrade. Anything unrecognised falls back to following the system. */
  const valid = (value) => {
    if (known(value)) return value;
    if (value === 'light' || value === 'dark') return SYSTEM_DEFAULT[value];
    return 'system';
  };

  let preference = 'system';
  try {
    preference = valid(localStorage.getItem(key));
  } catch {}

  const resolve = () =>
    preference === 'system'
      ? SYSTEM_DEFAULT[media.matches ? 'dark' : 'light']
      : preference;

  /* The browser's own chrome should match the page it frames. This used to be
     a hardcoded pair of hex values, which drifted: it was still serving the
     pre-brand green while the page had been ivory for some time. Reading the
     resolved token means it cannot drift again, and it costs one lookup.

     The stylesheet is not parsed yet on the first call - this script runs
     ahead of it deliberately, so the theme is right before anything paints -
     so the read is retried once the document is ready. */
  function paintBrowserChrome() {
    const meta = document.querySelector('meta[name="theme-color"]');
    if (!meta) return;
    const ground = getComputedStyle(document.documentElement)
      .getPropertyValue('--paper')
      .trim();
    if (ground) meta.setAttribute('content', ground);
  }

  function apply() {
    const theme = resolve();
    const entry = THEMES.find((x) => x.id === theme);
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.appearance = entry.appearance;
    document.documentElement.dataset.themePreference = preference;
    paintBrowserChrome();
  }

  window.orenaTheme = {
    // The registry, so the settings UI is built from the themes that exist
    // rather than from a list written out a second time beside it.
    get themes() {
      return THEMES.map((theme) => ({ ...theme }));
    },
    get preference() {
      return preference;
    },
    get current() {
      return resolve();
    },
    set(value) {
      preference = valid(value);
      try {
        localStorage.setItem(key, preference);
      } catch {}
      apply();
    },
  };

  media.addEventListener('change', apply);
  window.addEventListener('storage', (event) => {
    if (event.key === key || event.key === null) {
      preference = valid(event.newValue);
      apply();
    }
  });
  apply();
  // Once the stylesheet exists, the chrome colour can actually be read.
  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', paintBrowserChrome, {
      once: true,
    });
  else paintBrowserChrome();
})();
