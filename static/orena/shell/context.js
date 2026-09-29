/* Who the learner is and what the shell shows about them, read once at boot from the existing
   services (D-091: the new UI reuses the backend as it is).

   - identity:  /api/me (name, picture, admin) - the owner of this device's learner memory;
   - languages: /api/session/bootstrap (the active learning language and the enabled ones) and
                /api/learner-profile (support language, declared level, pinyin preference);
   - counts:    /api/library/vocabulary/summary (words due - My Library's badge).

   Nothing here is invented: an unknown level shows no level, a count that cannot be read is 0
   and the badge is not drawn (Design Contract rule 40). */
import { request } from '../infrastructure/api.js';
import { learnerMemory } from '../product/memory.js';
import { learningLanguage } from '../product/languages.js';
import { setSupportFromProfile } from '../copy/index.js';

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

export async function loadContext(storage = window.localStorage) {
  const [user, bootstrap, profile, vocabulary] = await Promise.all([
    read('/api/me'),
    read('/api/session/bootstrap'),
    read('/api/learner-profile').catch(() => null),
    read('/api/library/vocabulary/summary').catch(() => null),
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
  state.level = String(profile?.declared_level || '').trim();
  state.pinyin = profile?.pinyin !== 'off';
  state.due = Number.isFinite(Number(vocabulary?.summary?.due)) ? Math.max(0, Number(vocabulary.summary.due)) : 0;
  state.memory = learnerMemory(storage, state.owner, state.language);
  if (profile) setSupportFromProfile(profile);
  applyLearningLanguage();
  state.ready = true;
  emit();
  return context();
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
