/* Interface and support strings of the new learner UI (D-079 language layers, Design Contract
   rules 9, 26 and 50).

   Each surface registers its own table with defineCopy(namespace, { layers, en, vi, zh }):
   `layers[key]` says whether the key is chrome ('interface': navigation, buttons, labels, states)
   or explanation ('support': hints, feedback, guidance). A key reads from the pack of its layer's
   language through product/layered-copy.js - the same algorithm the old UI uses - so a supported
   locale never silently shows English (rule 26), and support text never follows the interface
   language. scripts/test_orena_copy.mjs checks every table: all three packs carry every key, and
   every key has a layer.

   Strings are few and short by rule 50; the design's sample words are not copied as data. */
import { layeredCopy } from '../product/layered-copy.js';
import { INTERFACE_KEY, interfaceLanguage, supportLanguage } from '../product/languages.js';

export const LOCALES = Object.freeze(['en', 'vi', 'zh']);

const tables = new Map();
const listeners = new Set();
let current = { ui: 'en', support: 'en' };

export function defineCopy(namespace, { layers, en, vi, zh }) {
  if (tables.has(namespace)) throw new Error(`Copy namespace defined twice: ${namespace}`);
  tables.set(namespace, { layers, packs: { en, vi, zh } });
  const translate = (key, params) => t(namespace, key, params);
  translate.lang = (key) => langOf(namespace, key);
  translate.plural = (key, n, params = {}) => plural(namespace, key, n, params);
  translate.has = (key) => Object.prototype.hasOwnProperty.call(layers, key);
  return translate;
}

export function registeredCopy() {
  return new Map(tables);
}

function resolved(namespace) {
  const table = tables.get(namespace);
  if (!table) throw new Error(`Unknown copy namespace: ${namespace}`);
  return layeredCopy(table.packs, table.layers, current.ui, current.support);
}

/* A placeholder takes any given value, 0 included; one without a value stays visible. */
function fill(text, params) {
  if (!params) return text;
  return String(text).replace(/\{(\w+)\}/g, (match, name) => (params[name] != null ? String(params[name]) : match));
}

export function t(namespace, key, params) {
  const out = resolved(namespace)[key];
  if (out == null) {
    console.error(`[Orena copy] missing key ${namespace}.${key}`);
    return key;
  }
  return fill(out, params);
}

/* English is the only pack with a singular form; keys `x_one` / `x_other`, vi and zh use `x_other`. */
export function plural(namespace, key, n, params = {}) {
  const copy = resolved(namespace);
  const one = n === 1 && copy[`${key}_one`] != null;
  return fill(copy[one ? `${key}_one` : `${key}_other`] ?? copy[key] ?? key, { n, ...params });
}

/* The language a key renders in, for its element's `lang` attribute. */
export function langOf(namespace, key) {
  return resolved(namespace).langOf(key);
}

export function languages() {
  return { ...current };
}

/* Interface language: the device's choice, else the browser's when Orena speaks it, else English.
   Support language: the account's. Never inferred from each other (D-079). */
export function resolveInterface() {
  let stored = '';
  try {
    stored = window.localStorage.getItem(INTERFACE_KEY) || '';
  } catch {
    stored = '';
  }
  return interfaceLanguage({ stored, browser: navigator.languages || [navigator.language], supported: [...LOCALES] });
}

export function setLanguages({ ui = current.ui, support = current.support } = {}) {
  const next = { ui: LOCALES.includes(ui) ? ui : 'en', support: String(support || 'en').toLowerCase() };
  if (next.ui === current.ui && next.support === current.support) return;
  current = next;
  document.documentElement.lang = current.ui;
  for (const listener of listeners) listener(languages());
}

export function setSupportFromProfile(profile) {
  setLanguages({ support: supportLanguage(profile) });
}

export function chooseInterface(code) {
  try {
    window.localStorage.setItem(INTERFACE_KEY, code);
  } catch {
    /* kept for this visit only */
  }
  setLanguages({ ui: code });
}

export function onLanguageChange(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

setLanguages({ ui: resolveInterface() });
