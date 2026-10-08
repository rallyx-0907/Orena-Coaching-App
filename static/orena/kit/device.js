/* Theme and device for the new learner UI (D-089; Design Contract rules 30, 48).

   kit/boot.js sets the first paint from the same key, before any stylesheet applies; this module
   is what the app calls afterwards. Settings' Appearance row (screens/settings, D-067 review item)
   is the one in-product control: Light, Dark or System, kept as a device preference only (never
   account data, never sent to the server) under APPEARANCE_KEY - the same one-key pattern
   copy/index.js's INTERFACE_KEY already uses for the interface language. System is the default and
   stays live: an unset key, or any value that is not exactly 'light' or 'dark', resolves to System
   and keeps following the operating system's own prefers-color-scheme for as long as System is
   chosen - including a corrupted/unrecognised stored value, which is treated the same as unset
   rather than thrown on. */

export const APPEARANCE_KEY = 'orena.appearance';
export const PALETTE_KEY = 'orena.palette';
export const PALETTES = Object.freeze(['indigo', 'orchid', 'blue', 'rose']);
export function palette() {
  try { const value = window.localStorage.getItem(PALETTE_KEY); return PALETTES.includes(value) ? value : 'indigo'; }
  catch { return 'indigo'; }
}
export function setPalette(value) {
  const next = PALETTES.includes(value) ? value : 'indigo';
  try { window.localStorage.setItem(PALETTE_KEY, next); } catch {}
  root.dataset.palette = next;
}
export const PHONE_QUERY = '(max-width: 899px)';
export const APPEARANCES = Object.freeze(['light', 'dark', 'system']);

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

/* Anything but the two explicit values is System - absent, the literal 'system', or corrupted/
   unknown text alike (rule 40's zero-fallback shape: never guess, never throw). */
function normalize(value) {
  return value === 'light' || value === 'dark' ? value : 'system';
}

function paint(chosen) {
  const theme = chosen === 'system' ? (dark.matches ? 'dark' : 'light') : chosen;
  const device = narrow.matches ? 'mobile' : 'desktop';
  const changed = root.dataset.theme !== theme || root.dataset.device !== device;
  root.dataset.theme = theme;
  root.dataset.device = device;
  if (changed) for (const listener of listeners) listener({ theme, device });
}

function apply() {
  root.dataset.palette = palette();
  paint(normalize(stored()));
}

dark.addEventListener('change', apply);
narrow.addEventListener('change', apply);

export function theme() {
  return root.dataset.theme === 'light' ? 'light' : 'dark';
}

export function device() {
  return root.dataset.device === 'mobile' ? 'mobile' : 'desktop';
}

/* The learner's stored choice, normalized to exactly 'light' | 'dark' | 'system' - what Settings'
   Appearance row highlights. Nothing else needs the raw storage value. */
export function appearance() {
  return normalize(stored());
}

/* 'light' | 'dark' | 'system' (anything else normalizes to 'system') - stores the learner's choice
   on this device under the one key and applies it immediately. Always writes the normalized value
   explicitly, so a later read here or in boot.js never has to guess what an absent key meant. */
export function setAppearance(choice) {
  const next = normalize(choice);
  try {
    window.localStorage.setItem(APPEARANCE_KEY, next);
  } catch {
    /* A browser that refuses storage (e.g. a strict private window) still switches for this visit
       via the paint(next) below - it just will not survive a reload. */
  }
  paint(next);
}

export function toggleAppearance() {
  setAppearance(theme() === 'dark' ? 'light' : 'dark');
}

export function onDeviceChange(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

apply();
