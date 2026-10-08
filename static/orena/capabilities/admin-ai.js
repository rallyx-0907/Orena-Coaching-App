/* AI & Models: the Platform Admin's logic for the AI control plane, without any presentation.

   Shared by the old console (admin/ai.js imports the pure functions) and the new UI's Admin
   (screens/admin/ai/*), which draws the pinned `Orena Admin.dc.html` on top of it (D-101 E: one
   Admin backend, one implementation of its rules).

   Everything is read from the existing control plane - the capability registry and saved routes
   (GET /api/admin/ai/config), the provider catalog with live model lists (GET /api/admin/ai/catalog),
   recorded operation telemetry (GET /api/admin/ai/operations) - so a capability added to the
   registry appears without a change here. Saving a route never changes what learners use while the
   learner runtime is `legacy`. Health checks run only when someone presses Test. Keys are sent once,
   to the server, and never read back: nothing in this module holds a stored secret. */
import { adminApi, failureReason } from './admin-api.js';

export const HEALTH_ERRORS = new Set([
  'capability_disabled', 'capability_not_configured', 'provider_not_configured', 'model_catalog_empty',
  'model_unavailable', 'provider_unavailable', 'provider_response_invalid', 'provider_error', 'capability_invalid',
]);

/* configurable: a provider-backed capability an admin can route; deterministic: local processing,
   nothing to route; reserved: in the registry but not implemented or not routable yet. */
export function capabilityKind(capability) {
  if (!capability?.implemented) return 'reserved';
  if (!capability.provider_backed) return 'deterministic';
  return capability.configurable ? 'configurable' : 'reserved';
}

/* Where a provider's credential comes from, as the server reports it - never the credential. */
export function credentialState(provider) {
  const configuration = provider?.configuration || {};
  if (configuration.credential_env === null || provider?.secret_mode === 'none') return 'not_required';
  /* Before the live catalog has answered, only the registry's `configured` is known - not where the
     credential comes from. Say "configured" rather than a "not configured" nobody has checked. */
  if (!provider?.configuration && provider?.configured) return 'configured';
  if (configuration.credential_source === 'encrypted_server_store') return provider.configured ? 'encrypted_server_store' : 'unreadable';
  if (configuration.credential_source === 'server_environment') return 'server_environment';
  return 'not_configured';
}

/* The registry's providers joined with the live catalog. `catalogLoaded` says whether the model
   list is a live answer or simply not asked for yet. */
export function mergeProviders(config, catalog) {
  const live = new Map((catalog?.providers || []).map((provider) => [provider.id, provider]));
  return (config?.providers || []).map((provider) => {
    const found = live.get(provider.id) || {};
    return {
      ...provider,
      ...found,
      configured: found.configured ?? provider.server_configured ?? false,
      models: Array.isArray(found.models) ? found.models : [],
      catalogLoaded: live.has(provider.id),
    };
  });
}

/* Removing a credential: every enabled capability routed through the provider, and the named
   provider it would fall back to, or none. */
export function removalConsequences(providerId, capabilities, providers) {
  const name = (id) => providers.find((item) => item.id === id)?.name || id;
  const consequences = (capabilities || [])
    .filter((capability) => capability.config?.provider === providerId && capability.config?.enabled !== false)
    .map((capability) => ({
      key: capability.key,
      fallback: capability.config?.backup_provider && capability.config.backup_provider !== providerId
        ? name(capability.config.backup_provider)
        : '',
    }));
  if (providerId === 'azure-speech') consequences.push({ key: 'pronunciation_evaluator', fallback: '' });
  return consequences;
}

/* The route editor's starting values for a capability: what is saved, or the first configured
   provider when nothing is. A model the server redacted is never put back into a field. */
export function routeDraft(capability, providers) {
  const config = capability?.config || {};
  return {
    provider: config.provider || providers.find((provider) => provider.configured)?.id || providers[0]?.id || '',
    model: config.model_redacted ? '' : config.model || '',
    backup_provider: config.backup_provider || '',
    backup_model: config.backup_model_redacted ? '' : config.backup_model || '',
    enabled: config.enabled !== false,
  };
}

/* The PUT /api/admin/ai/config/{key} body. The tuning the console does not edit (timeout,
   temperature, fallback policy) is carried over from what is saved, so a route edit never resets it. */
export function routeBody(capability, draft) {
  const saved = capability?.config || {};
  return {
    enabled: Boolean(draft.enabled),
    provider: draft.provider,
    model: draft.model,
    backup_provider: draft.backup_provider || null,
    backup_model: draft.backup_model || null,
    timeout_seconds: saved.timeout_seconds ?? null,
    temperature: saved.temperature ?? null,
    fallback_policy: saved.fallback_policy || (capability?.allowed_fallback_policies || ['none'])[0],
  };
}

/* The PUT /api/admin/ai/credentials/{id} body. An empty key is left out so the server keeps the one
   it has; the key is never trimmed into anything else. */
export function providerBody({ baseUrl = '', apiKey = '', defaultModel = '', models = [] } = {}) {
  const body = { base_url: String(baseUrl).trim() || undefined, default_model: defaultModel || '', models };
  const key = String(apiKey).trim();
  if (key) body.api_key = key;
  return body;
}

/* The error class the server named for a failed capability test, if it is one the console knows. */
export function healthErrorClass(result) {
  const detail = result?.body?.detail;
  const code = detail && typeof detail === 'object' ? detail.error_class : '';
  return HEALTH_ERRORS.has(code) ? code : '';
}

/* Do saved routes reach learners? Only when the learner runtime routes per capability. While it is
   `legacy` (one saved model for every request) a Save records the route and changes nothing a learner
   meets - the console must not imply otherwise. Read from the control plane's own fields. */
export function routingIsLive(config) {
  const mode = config?.learner_runtime?.mode;
  const uses = config?.policy?.learner_runtime_uses_capability_config;
  return mode === 'capability' && uses !== false;
}

/* Does the draft differ from what is saved? */
export function routeChanged(saved, draft) {
  const base = routeDraft({ config: saved }, []);
  return ['provider', 'model', 'backup_provider', 'backup_model', 'enabled'].some((field) => base[field] !== draft[field]);
}

/* The providers a capability can be routed to: the ones whose supported operations include it. */
export function compatibleProviders(capability, providers) {
  return providers.filter((provider) => !Array.isArray(provider.supported_operations) || provider.supported_operations.includes(capability.operation));
}

/* The models offered for a provider in a route. A saved model the live catalog no longer lists is
   kept and flagged `unavailable`, so the operator sees what the route says rather than a silent
   swap. catalogState 'loading' has nothing to offer yet. */
export function modelChoices(provider, selected, catalogState) {
  if (!provider) return { models: [], loading: false };
  if (catalogState === 'loading') return { models: [], loading: true };
  const models = (provider.models || []).map((id) => ({ id, unavailable: false }));
  if (selected && !models.some((model) => model.id === selected)) models.unshift({ id: selected, unavailable: true });
  return { models, loading: false };
}

/* A standby on the primary's own provider is not a fallback. */
export function standbySameProvider(draft) {
  return Boolean(draft.provider && draft.backup_provider && draft.provider === draft.backup_provider);
}

/* The state of a provider as the list and the detail say it (the design's `pst`): configured is
   not healthy, so a provider is `healthy` only when a test in this session passed and `failed`
   only when one failed. */
export function providerStatus(provider, test) {
  const credential = credentialState(provider);
  if (credential === 'unreadable') return 'unreadable';
  if (credential === 'not_configured') return 'not_configured';
  if (test?.state === 'testing') return 'testing';
  if (test?.state === 'ok') return 'healthy';
  if (test?.state === 'failed') return 'failed';
  return 'untested';
}

/* Which capabilities a provider serves, and in which role. */
export function providerUsedBy(capabilities, providerId) {
  const used = [];
  if (providerId === 'azure-speech') used.push({ key: 'pronunciation_evaluator', role: 'primary', model: 'pronunciation-assessment' });
  for (const capability of capabilities || []) {
    const config = capability.config;
    if (!config) continue;
    if (config.provider === providerId) used.push({ key: capability.key, role: 'primary', model: config.model || '', enabled: config.enabled !== false });
    else if (config.backup_provider === providerId) used.push({ key: capability.key, role: 'standby', model: config.backup_model || '', enabled: config.enabled !== false });
  }
  return used;
}

/* Recorded usage of one provider, from the operation events the control plane returns (a bounded,
   most-recent sample). Requests and failures are counted, latency is the mean of the events that
   recorded one; nothing the events do not carry is derived. null when the provider has none. */
export function providerUsage(operations, providerId) {
  const events = (operations?.recent || []).filter((event) => event.provider === providerId);
  if (!events.length) return null;
  const failures = events.filter((event) => event.outcome !== 'success').length;
  const latencies = events.map((event) => event.latency_ms).filter((value) => Number.isFinite(value));
  const stamp = (event) => (event?.created_at ? Date.parse(event.created_at) : NaN);
  const newest = (list) => list.filter((event) => Number.isFinite(stamp(event))).sort((a, b) => stamp(b) - stamp(a))[0] || null;
  const lastSuccess = newest(events.filter((event) => event.outcome === 'success'));
  const lastFailure = newest(events.filter((event) => event.outcome !== 'success'));
  return {
    lastSuccessAt: lastSuccess ? lastSuccess.created_at : '',
    lastFailureAt: lastFailure ? lastFailure.created_at : '',
    lastError: lastFailure?.error_class || '',
    requests: events.length,
    failures,
    failureRate: (failures / events.length) * 100,
    meanLatency: latencies.length ? Math.round(latencies.reduce((sum, value) => sum + value, 0) / latencies.length) : null,
    sample: Array.isArray(operations?.recent) ? operations.recent.length : 0,
    truncated: Boolean(operations?.sample_truncated),
  };
}

/* One row of the routing list: the capability, whether it can be routed, what it is routed to and
   how that route stands. `state` is one of:
     reserved | local            not a provider route (nothing to edit)
     not_configured              routable, no saved route
     disabled                    saved, switched off
     primary_unavailable         the primary provider has no working credential
     failing_standby             recent evidence says the primary fails, a standby exists
     failing_no_standby          ... and there is none
     routed                      saved, enabled, no evidence against it
   "Routed" is not "healthy": `health` carries the recorded telemetry state separately (rule: never
   imply configured = healthy). */
export function capabilityRows(config, operations, providers) {
  const byCapability = new Map((operations?.by_capability || []).map((row) => [row.capability, row]));
  const byProvider = new Map((providers || []).map((provider) => [provider.id, provider]));
  return (config?.capabilities || []).map((capability) => {
    const kind = capabilityKind(capability);
    const saved = capability.explicit_config_exists && capability.config ? capability.config : null;
    const evidence = byCapability.get(capability.key) || null;
    const primary = saved ? byProvider.get(saved.provider) || null : null;
    const standby = saved?.backup_provider ? byProvider.get(saved.backup_provider) || null : null;
    const failing = evidence && ['provider_failure', 'failed', 'degraded'].includes(evidence.health_state);
    let state;
    if (kind === 'reserved') state = 'reserved';
    else if (kind === 'deterministic') state = 'local';
    else if (!saved) state = 'not_configured';
    else if (saved.enabled === false) state = 'disabled';
    else if (!primary || !primary.configured) state = 'primary_unavailable';
    else if (failing) state = saved.backup_provider ? 'failing_standby' : 'failing_no_standby';
    else state = 'routed';
    return {
      key: capability.key,
      capability,
      kind,
      saved,
      state,
      primary: saved ? { provider: saved.provider, name: primary?.name || saved.provider, model: saved.model_redacted ? '' : saved.model || '', configured: Boolean(primary?.configured) } : null,
      standby: saved?.backup_provider ? { provider: saved.backup_provider, name: standby?.name || saved.backup_provider, model: saved.backup_model_redacted ? '' : saved.backup_model || '', configured: Boolean(standby?.configured) } : null,
      health: evidence?.health_state || 'no_data',
      evidence,
    };
  });
}

/* The controller behind the screens: the state one AI & Models session holds and the requests that
   change it. It never draws; `onChange` says something moved. Every request goes through `api`
   (the shared client), so a screen has no fetch of its own. */
export function createAiAdmin({ api = adminApi, onChange = () => {} } = {}) {
  const state = {
    config: null,
    catalog: null,
    catalogState: 'loading',
    operations: null,
    providers: [],
    routeTests: new Map(),
    providerTests: new Map(),
  };
  const emit = () => {
    state.providers = mergeProviders(state.config, state.catalog);
    onChange(state);
  };

  async function loadCore() {
    const [config, operations] = await Promise.all([
      api.aiConfig(),
      api.aiOperations(200).catch(() => ({ available: false, by_capability: [], recent: [] })),
    ]);
    state.config = config;
    state.operations = operations;
    emit();
  }

  async function loadCatalog() {
    state.catalogState = 'loading';
    emit();
    try {
      state.catalog = await api.aiCatalog();
      state.catalogState = 'ready';
    } catch {
      state.catalogState = 'failed';
    }
    emit();
  }

  async function refreshOperations() {
    try {
      state.operations = await api.aiOperations(200);
    } catch {
      // The recorded view stays as it was; a test result already shown still stands.
    }
    emit();
  }

  const slot = (key, standby) => (standby ? `${key}:standby` : key);

  /* POST /api/admin/ai/test/{key}: tests the SAVED route (the server has no draft test). */
  async function testRoute(key, standby = false) {
    state.routeTests.set(slot(key, standby), { state: 'testing' });
    emit();
    const result = await api.testCapability(key, standby);
    state.routeTests.set(
      slot(key, standby),
      result.ok
        ? { state: 'ok', latency: result.body?.latency_ms }
        : { state: 'failed', code: healthErrorClass(result), reason: failureReason(result) },
    );
    emit();
    await refreshOperations();
    return result;
  }

  async function saveRoute(key, draft) {
    const capability = (state.config?.capabilities || []).find((item) => item.key === key) || {};
    const result = await api.saveCapability(key, routeBody(capability, draft));
    if (result.ok) {
      state.routeTests.delete(slot(key, false));
      state.routeTests.delete(slot(key, true));
      await loadCore();
    }
    return { ok: result.ok, reason: result.ok ? '' : failureReason(result) };
  }

  /* POST /api/admin/ai/credentials/{id}/test: with a body it tries the draft key/endpoint without
     storing anything; without one it tries what is stored. */
  async function testProvider(id, body = {}) {
    state.providerTests.set(id, { state: 'testing' });
    emit();
    const started = performance.now();
    const result = await api.testProvider(id, body);
    const time = Math.round(performance.now() - started);
    const models = Array.isArray(result.body?.models) ? result.body.models : [];
    state.providerTests.set(
      id,
      result.ok ? { state: 'ok', count: models.length, time, models, at: Date.now() } : { state: 'failed', reason: failureReason(result), at: Date.now() },
    );
    emit();
    return { ok: result.ok, models, reason: result.ok ? '' : failureReason(result) };
  }

  /* Save a credential and its endpoint. The server verifies against the live catalog itself and
     wants the default and allowed models from it, so the draft is tried first to learn them: a key
     that cannot connect is never stored. `remember` keeps the passing test as the provider's
     result (Save & test); a plain save leaves the provider untested. */
  async function saveProvider(id, { baseUrl = '', apiKey = '', defaultModel = '', remember = false } = {}) {
    const started = performance.now();
    const check = await api.testProvider(id, providerBody({ baseUrl, apiKey, defaultModel }));
    const time = Math.round(performance.now() - started);
    if (!check.ok) {
      state.providerTests.set(id, { state: 'failed', reason: failureReason(check), at: Date.now() });
      emit();
      return { ok: false, stage: 'verify', reason: failureReason(check) };
    }
    const live = Array.isArray(check.body?.models) ? check.body.models : [];
    const chosen = live.includes(defaultModel) ? defaultModel : live[0] || '';
    const result = await api.saveProvider(id, providerBody({ baseUrl, apiKey, defaultModel: chosen, models: live }));
    if (!result.ok) return { ok: false, stage: 'save', reason: failureReason(result) };
    state.providerTests.delete(id);
    if (remember) state.providerTests.set(id, { state: 'ok', count: live.length, time, models: live, at: Date.now() });
    await loadCore();
    await loadCatalog();
    return { ok: true, models: live };
  }

  async function removeProvider(id) {
    const result = await api.removeProvider(id);
    if (result.ok) {
      state.providerTests.delete(id);
      await loadCore();
      await loadCatalog();
    }
    return { ok: result.ok, reason: result.ok ? '' : failureReason(result) };
  }

  return { state, loadCore, loadCatalog, testRoute, saveRoute, testProvider, saveProvider, removeProvider };
}
