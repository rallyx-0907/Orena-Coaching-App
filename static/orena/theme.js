// Runs before styles paint. One preference, including a live system default.
// This small DOM adapter is intentionally independent of auth and routing.
//
// The registry below is the canonical list of Orena themes. A theme has an
// identity and, separately, an appearance: "ink" is the identity, "dark" is
// only how bright it is. Keeping the two apart is what lets a theme be added,
// retired or renamed without rewriting the switch and the settings UI.
//
// Adding a theme is an entry here plus a [data-theme] block in theme.css.
// Nothing else. Learner-facing names live in ui/copy.js with every other
// string, so a new theme is translated the same way everything else is.
(() => {
  const key = 'orena.theme';
  // D-059: the Orena Design System is one identity in two appearances.
  const THEMES = [
    { id: 'ink', appearance: 'dark', mood: 'lamplight' },
    { id: 'paper', appearance: 'light', mood: 'daylight' },
  ];
  // What "follow the system" resolves to. Appearance chooses; identity is the
  // product's decision, not the operating system's.
  const SYSTEM_DEFAULT = { light: 'paper', dark: 'ink' };
  /* Themes an earlier build offered. Each is read as the theme that now
     carries its appearance, so nobody who chose one loses their choice to the
     D-059 upgrade - a dark choice stays dark and a light one stays light. The
     first two are what the preference stored before themes had names. */
  const RETIRED = {
    light: 'paper',
    dark: 'ink',
    'night-ink': 'ink',
    'deep-forest': 'ink',
    'sage-field': 'paper',
  };

  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const known = (id) => THEMES.some((theme) => theme.id === id);
  // Anything unrecognised falls back to following the system.
  const valid = (value) => {
    if (known(value)) return value;
    if (Object.hasOwn(RETIRED, value)) return RETIRED[value];
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
