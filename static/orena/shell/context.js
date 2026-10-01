/* Who the learner is and what the shell shows about them, read once at boot from the existing
   services (D-091: the new UI reuses the backend as it is).

   - identity:  /api/me (name, picture, admin) - the owner of this device's learner memory;
   - languages: /api/session/bootstrap (the active learning language and the enabled ones) and
                /api/learner-profile (support language, declared level, pinyin preference);
   - counts:    /api/library/vocabulary/summary (words due - My Library's badge).

   Nothing here is invented: an unknown level shows no level, a count that cannot be read is 0
   and the badge is not drawn (Design Contract rule 40). */
import { request } from '../infrastructure/api.js';
import { learnerMemory, setPlaceSink } from '../product/memory.js';
import { learningLanguage } from '../product/languages.js';
import { chooseInterface, setSupportFromProfile } from '../copy/index.js';
import { INTERFACE_KEY } from '../product/languages.js';
import { reconcileInterface, reviewFromProfile } from '../product/account-settings.js';
import { clearPlace, sendPlace, syncContinuation } from '../product/continue-sync.js';
import { attachProvenance, pullImports, pushImport, removeImport } from '../product/account-records.js';

const listeners = new Set();
const control = new AbortController();

const state = {
  ready: false,
  user: null,
  isAdmin: false,
  name: '',
  initial: '',
  picture: '',
  owner: 'local',
  language: 'en',
  activeLanguage: '',
  languageOptions: [],
  profile: null,
  account: null,
  activity: null,
  level: '',
  pinyin: true,
  due: 0,
  memory: null,
};

/* Context reads are the shell's, not a room's: they carry their own signal so a navigation (which
   aborts the room's requests, infrastructure/navigation.js) never cancels them. */
function read(url) {
  return request(url, { signal: control.signal });
}

function initialOf(name) {
  const letter = String(name || '').trim().charAt(0);
  return letter ? letter.toLocaleUpperCase() : '';
}

/* The learner's own timezone: the day boundary of their streak is a calendar day in it (D4 I14). */
function deviceTimezone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

export async function loadContext(storage = window.localStorage) {
  const [user, bootstrap, profile, vocabulary, account, activity] = await Promise.all([
    read('/api/me'),
    read('/api/session/bootstrap'),
    read('/api/learner-profile').catch(() => null),
    read('/api/library/vocabulary/summary').catch(() => null),
    read('/api/account-settings').catch(() => null),
    read(`/api/learner-activity?tz=${encodeURIComponent(deviceTimezone())}`).catch(() => null),
  ]);
  state.user = user;
  state.isAdmin = Boolean(user?.is_admin);
  state.name = String(user?.name || '').trim();
  state.initial = initialOf(state.name);
  state.picture = typeof user?.picture === 'string' && /^https:\/\//.test(user.picture) ? user.picture : '';
  state.owner = user?.email || user?.mode || 'local';
  state.language = learningLanguage(bootstrap?.language?.active);
  state.activeLanguage = String(bootstrap?.language?.active || '').trim();
  state.languageOptions = Array.isArray(bootstrap?.language?.options) ? bootstrap.language.options : [];
  state.profile = profile;
  state.account = account;
  state.activity = activity;
  state.level = String(profile?.declared_level || '').trim();
  state.pinyin = profile?.pinyin !== 'off';
  state.due = Number.isFinite(Number(vocabulary?.summary?.due)) ? Math.max(0, Number(vocabulary.summary.due)) : 0;
  setPlaceSink({ enter: sendPlace, clear: clearPlace, addImport: pushImport, removeImport, keepLanguage: attachProvenance });
  state.memory = learnerMemory(storage, state.owner, state.language);
  // The server's places, when it holds any; a failed read leaves the device list as it is.
  await syncContinuation(state.memory).catch(() => false);
  // Imports the account holds appear on this device too (a device value the server lacks stays, H-6).
  state.memory.mergeImports(await pullImports(state.language).catch(() => []));
  applyServerReview(state.memory, profile);
  // The interface language is the account's, with the device as the first-paint cache.
  let deviceInterface = '';
  try {
    deviceInterface = storage.getItem(INTERFACE_KEY) || '';
  } catch {
    /* no device store */
  }
  const accountInterface = await reconcileInterface(account, deviceInterface);
  if (accountInterface) chooseInterface(accountInterface);
  if (profile) setSupportFromProfile(profile);
  applyLearningLanguage();
  state.ready = true;
  emit();
  return context();
}

/* The server's review settings are the truth when it holds any; the device copy is only the cache. A value the
   server does not hold yet stays as the device has it, and nothing here writes to the server. */
function applyServerReview(memory, profile) {
  const review = reviewFromProfile(profile);
  if (!review || !memory) return;
  const held = memory.value?.reviewSettings || {};
  memory.setReview({ ...held, ...review, modes: { ...held.modes, ...review.modes } });
}

/* The learner's learning language just changed (the server has already switched the session). Everything that is
   scoped to a language is brought over BEFORE the shell repaints: the profile - so its version, its declared
   level, its support language and its stored review settings are the new language's, not the old one's - the
   continuation places, the imports, and the device copy of the review settings, overlaid with the server's. A
   control that is painted afterwards reads the new language's values, and its first write is made against the
   new language's profile version. */
export async function adoptLearningLanguage(code, storage = window.localStorage) {
  const next = learningLanguage(code);
  const memory = learnerMemory(storage, state.owner, next);
  const [profile] = await Promise.all([
    read('/api/learner-profile').catch(() => null),
    syncContinuation(memory).catch(() => false),
    pullImports(next).then((items) => memory.mergeImports(items)).catch(() => false),
  ]);
  applyServerReview(memory, profile);
  updateContext({
    language: next,
    memory,
    ...(profile ? { profile, level: String(profile.declared_level || '').trim(), pinyin: profile.pinyin !== 'off' } : {}),
  });
  if (profile) setSupportFromProfile(profile);
  refreshCounts().catch(() => {});
}

function applyLearningLanguage() {
  const root = document.documentElement;
  root.dataset.tl = state.language === 'zh' ? 'zh' : 'en';
  root.dataset.pyon = state.pinyin ? '1' : '0';
}

export function context() {
  return state;
}

export function updateContext(patch) {
  Object.assign(state, patch);
  if ('pinyin' in patch || 'language' in patch) applyLearningLanguage();
  emit();
}

export async function refreshCounts() {
  const vocabulary = await read('/api/library/vocabulary/summary').catch(() => null);
  if (vocabulary?.summary) updateContext({ due: Math.max(0, Number(vocabulary.summary.due) || 0) });
}

export function onContext(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function emit() {
  for (const listener of listeners) listener(state);
}
