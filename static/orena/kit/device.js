/* Theme and device for the new learner UI (D-089; Design Contract rules 30, 48).

   kit/boot.js sets the first paint; this module is what the app calls afterwards. The theme
   follows the operating system unless the learner used the Reader's light/dark button, which
   stores a device preference (never account data) - clearing it returns to the system. */

export const APPEARANCE_KEY = 'orena.appearance';
export const PHONE_QUERY = '(max-width: 899px)';

const root = document.documentElement;
const dark = window.matchMedia('(prefers-color-scheme: dark)');
const narrow = window.matchMedia(PHONE_QUERY);
const listeners = new Set();

function stored() {
  try {
    return window.localStorage.getItem(APPEARANCE_KEY) || '';
  } catch {
    return '';
  }
}

function apply() {
  const chosen = stored();
  const theme = chosen === 'light' || chosen === 'dark' ? chosen : dark.matches ? 'dark' : 'light';
  const device = narrow.matches ? 'mobile' : 'desktop';
  const changed = root.dataset.theme !== theme || root.dataset.device !== device;
  root.dataset.theme = theme;
  root.dataset.device = device;
  if (changed) for (const listener of listeners) listener({ theme, device });
}

dark.addEventListener('change', apply);
narrow.addEventListener('change', apply);

export function theme() {
  return root.dataset.theme === 'light' ? 'light' : 'dark';
}

export function device() {
  return root.dataset.device === 'mobile' ? 'mobile' : 'desktop';
}

/* 'light' | 'dark' stores the learner's choice on this device; null follows the system again. */
export function setAppearance(choice) {
  try {
    if (choice === 'light' || choice === 'dark') window.localStorage.setItem(APPEARANCE_KEY, choice);
    else window.localStorage.removeItem(APPEARANCE_KEY);
  } catch {
    /* A browser that refuses storage still switches for this visit. */
    root.dataset.theme = choice === 'light' || choice === 'dark' ? choice : root.dataset.theme;
  }
  apply();
}

export function toggleAppearance() {
  setAppearance(theme() === 'dark' ? 'light' : 'dark');
}

export function onDeviceChange(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

apply();
