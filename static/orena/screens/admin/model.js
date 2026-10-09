/* Platform Admin's pure model (Orena-Admin.dc.html, D-101 E): who may open it, which areas its
   navigation draws, and how a control-plane fact becomes a pill. No DOM, no requests - the screen
   draws it and scripts/test_orena_screen_admin.mjs checks it.

   Access is decided here from what the shell already knows about the account (`/api/me`), before any
   admin request exists: an account that is not an admin gets the design's No access frame and the
   client never asks the server for admin data. The server refuses non-admins on its own
   (tests/test_admin_authorization_matrix.py); this is the client keeping its side of that. */

/* The six operator areas of the approved Admin product. The former staging-only
   subset is superseded by basic Product Completion; all use the existing backend.
   Reading remains inside Content. The Practice generator has no backend. */
export const AREAS = Object.freeze([
  { id: 'overview', route: 'adminOverview', label: 'navOverview' },
  { id: 'ai', route: 'adminAi', label: 'navAi' },
  { id: 'users', route: 'adminUsers', label: 'navUsers' },
  { id: 'content', route: 'adminContent', label: 'navContent' },
  { id: 'imports', route: 'adminImports', label: 'navImports' },
  { id: 'operations', route: 'adminOperations', label: 'navOperations' },
]);

/* Which area each admin route belongs to, and the module that draws it. */
const ROUTES_OF = {
  overview: ['adminOverview', 'adminTraffic'],
  users: ['adminUsers', 'adminUser', 'adminPlans', 'adminFeedback'],
  operations: ['adminOperations', 'adminWorkers', 'adminPolling', 'adminErrors'],
  ai: ['adminAi', 'adminProvider', 'adminProviderKey', 'adminCapability', 'adminAiCosts'],
  content: ['adminContent', 'adminBooks', 'adminBook', 'adminMedia', 'adminMediaItem', 'adminVocab', 'adminCollection',
    'adminGrammar', 'adminGrammarPoint',
    'adminReading', 'adminQueue', 'adminArticle', 'adminSet', 'adminAdd', 'adminSources', 'adminSource'],
  imports: ['adminImports', 'adminImportBooks', 'adminImportMedia', 'adminImportVocab', 'adminImportPack', 'adminImportGrammar', 'adminImportSource', 'adminJobs', 'adminJob', 'adminHistory'],
};

export function areaOf(routeId) {
  if (routeId === 'admin') return 'overview';
  return Object.keys(ROUTES_OF).find((area) => ROUTES_OF[area].includes(routeId)) || '';
}

/* Every route the Admin serves, for the gates. */
export const ADMIN_ROUTE_IDS = Object.freeze(['admin', ...Object.values(ROUTES_OF).flat()]);

/* May this account open Platform Admin? Only an account the server named an admin. `email` is what
   the No access frame quotes back; an account with none (local mode) is quoted by name, or not at all. */
export function adminAccess(context) {
  const user = context?.user || {};
  return {
    allowed: context?.isAdmin === true,
    email: String(user.email || '').trim(),
    name: String(context?.name || user.name || '').trim(),
  };
}

/* The design's pill tones (its `T` map): soft fill with a strong ink. `fut` is the dashed, unfilled
   "future" pill. */
export const TONES = Object.freeze(['ok', 'warn', 'err', 'info', 'mute', 'fut']);

const PROVIDER_STATUS = {
  not_configured: ['statusNotConfigured', 'mute'],
  unreadable: ['statusUnreadable', 'err'],
  testing: ['statusTesting', 'info'],
  healthy: ['statusHealthy', 'ok'],
  failed: ['statusFailed', 'err'],
  untested: ['statusUntested', 'warn'],
};

/* `providerStatus()` (capabilities/admin-ai.js) → the pill's copy key and tone. */
export function providerPill(status) {
  const [label, tone] = PROVIDER_STATUS[status] || PROVIDER_STATUS.not_configured;
  return { label, tone };
}

const ROUTE_STATE = {
  routed: ['routeStateRouted', 'ok'],
  disabled: ['routeStateDisabled', 'mute'],
  primary_unavailable: ['routeStatePrimaryUnavailable', 'err'],
  failing_standby: ['routeStateFailingStandby', 'warn'],
  failing_no_standby: ['routeStateFailingNoStandby', 'err'],
  not_configured: ['routeStateNotConfigured', 'mute'],
  local: ['routeStateLocal', 'mute'],
  reserved: ['routeStateReserved', 'fut'],
};

/* `capabilityRows()[i].state` → the pill's copy key and tone. */
export function routePill(state) {
  const [label, tone] = ROUTE_STATE[state] || ROUTE_STATE.not_configured;
  return { label, tone };
}

/* How a credential source reads (copy key), from `credentialState()`. */
export function sourceLabel(credential) {
  return {
    configured: 'sourceConfigured',
    encrypted_server_store: 'sourceStored',
    server_environment: 'sourceEnvironment',
    not_required: 'sourceNotRequired',
    unreadable: 'sourceUnreadable',
    not_configured: 'sourceNone',
  }[credential] || 'sourceNone';
}

/* The two letters on a provider's tile: the initials of a two-word name ("Google Gemini" -> GG), else
   the first two letters. A trailing "API" is part of the product name, not of the mark ("Groq API" -> GR). */
export function providerMono(name) {
  const words = String(name || '').trim().split(/\s+/).filter((word) => word && word.toLowerCase() !== 'api');
  if (words.length >= 2) return `${words[0][0]}${words[1][0]}`.toUpperCase();
  return String(name || '?').trim().slice(0, 2).toUpperCase();
}

/* The name a key is shown under when the copy does not know it yet (a capability added to the
   registry before its words are): the key, humanised. */
export function humanKey(key) {
  const text = String(key || '').replaceAll('_', ' ').trim();
  return text ? text[0].toUpperCase() + text.slice(1) : '';
}

/* Filter a list on the current page by what the header field holds (matching any of the words a
   row carries). An empty query keeps every row. */
export function matchesFilter(query, ...words) {
  const needle = String(query || '').trim().toLowerCase();
  if (!needle) return true;
  return words.some((word) => String(word || '').toLowerCase().includes(needle));
}

/* The key form's checks, before anything is sent. The design asks for a key every time ("the stored
   key can't be shown or reused") and refuses one that cannot be a key. */
export function validateKey(value, { required = true } = {}) {
  const key = String(value || '').trim();
  if (!required) return '';
  if (!key) return 'errKeyRequired';
  if (key.length < 12) return 'errKeyShort';
  return '';
}
