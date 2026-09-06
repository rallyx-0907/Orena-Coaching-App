// Runs before styles paint. One preference, including a live system default.
// This small DOM adapter is intentionally independent of auth and routing.
(() => {
  const key = 'orena.theme';
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const valid = (value) =>
    ['light', 'dark'].includes(value) ? value : 'system';
  let preference = 'system';
  try {
    preference = valid(localStorage.getItem(key));
  } catch {}
  function apply() {
    const theme =
      preference === 'system' ? (media.matches ? 'dark' : 'light') : preference;
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.themePreference = preference;
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute('content', theme === 'dark' ? '#142c27' : '#f6f1e7');
  }
  window.orenaTheme = {
    get preference() {
      return preference;
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
})();
