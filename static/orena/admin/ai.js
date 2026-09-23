/* AI & Models: which provider and model answers each capability, whether it
   is healthy, and what learners actually use right now.

   Everything is read from the existing control plane - the capability
   registry and saved routes (/api/admin/ai/config), the provider catalog with
   live model lists (/api/admin/ai/catalog), recorded operation telemetry
   (/api/admin/ai/operations) - plus the console's runtime facts. The table has
   one row per registry entry, so a capability added to the registry appears
   here without a change to this file.

   Saving a route never changes what learners use: while the learner runtime
   is `legacy` every request goes to one saved model, and switching to per
   capability routing is a deployment decision. Health checks run only when
   someone presses Test. Keys are sent once, to the server, and never read
   back. */
import { adminApi, failureReason } from './api.js';
import { chip, esc, fill, info, kv, latency, mono, num, panel, table, notice } from './format.js';

const HEALTH_ERRORS = new Set([
  'capability_disabled', 'capability_not_configured', 'provider_not_configured', 'model_catalog_empty',
  'model_unavailable', 'provider_unavailable', 'provider_response_invalid', 'provider_error', 'capability_invalid',
]);

export function capabilityKind(capability) {
  if (!capability?.implemented) return 'reserved';
  if (!capability.provider_backed) return 'deterministic';
  return capability.configurable ? 'configurable' : 'reserved';
}

export function capabilityLabel(key, t) {
  return t[`cap_${key}`] || String(key || '').replaceAll('_', ' ');
}

export function credentialState(provider) {
  const configuration = provider?.configuration || {};
  if (configuration.credential_env === null || provider?.secret_mode === 'none') return 'not_required';
  if (configuration.credential_source === 'encrypted_server_store') return provider.configured ? 'encrypted_server_store' : 'unreadable';
  if (configuration.credential_source === 'server_environment') return 'server_environment';
  return 'not_configured';
}

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

function testLine(test, standby, t, ui) {
  if (!test) return '';
  const body = test.state === 'testing'
    ? esc(t.testing)
    : test.state === 'ok'
      ? chip('healthy', t, { label: fill(standby ? t.standbyOk : t.testOk, { latency: latency(test.latency, ui) }) })
      : chip('failed', t, { label: test.reason });
  return `<span class="ac-test" data-state="${esc(test.state)}">${body}</span>`;
}

/* Recorded health from telemetry first, then whatever was tested in this
   session: the two answer different questions and are never merged. */
function healthCell(row, test, standbyTest, t, ui) {
  const recorded = row
    ? `${chip(row.health_state || 'no_data', t)}<small>${esc(row.evidence_count
        ? fill(t.healthEvidence, { count: num(row.evidence_count, ui), failures: num(row.failure_rate_percent, ui), latency: latency(row.avg_latency_ms, ui) })
        : t.healthNoEvidence)}</small>`
    : `${chip('no_data', t)}<small>${esc(t.healthNoEvidence)}</small>`;
  return `<div class="ac-cell-stack">${recorded}${testLine(test, false, t, ui)}${testLine(standbyTest, true, t, ui)}</div>`;
}

function route(provider, model, providers, t) {
  if (!provider) return `<span class="ac-muted">${esc(t.none)}</span>`;
  const found = providers.find((item) => item.id === provider);
  const name = found?.name || provider;
  const warning = found && !found.configured ? chip('not_configured', t) : '';
  return `<div class="ac-cell-stack"><span>${esc(name)}</span>${model ? mono(model) : ''}${warning}</div>`;
}

function options(list, selected, placeholder) {
  return `${placeholder ? `<option value="">${esc(placeholder)}</option>` : ''}${list
    .map(([value, label]) => `<option value="${esc(value)}"${value === selected ? ' selected' : ''}>${esc(label)}</option>`)
    .join('')}`;
}

export function modelOptions(provider, selected, t, catalogState) {
  if (!provider) return { html: options([], '', t.chooseModel), disabled: true, note: '' };
  if (catalogState === 'loading') return { html: options([], '', t.modelsLoading), disabled: true, note: t.modelsLoading };
  const models = [...(provider.models || [])];
  if (selected && !models.includes(selected)) models.unshift(selected);
  if (!models.length) return { html: options([], '', t.noModels), disabled: true, note: t.noModels };
  return { html: options(models.map((model) => [model, model]), selected, t.chooseModel), disabled: false, note: '' };
}

export function routeEditor(capability, draft, providers, t, catalogState) {
  const compatible = providers.filter((provider) => !Array.isArray(provider.supported_operations) || provider.supported_operations.includes(capability.operation));
  const primary = compatible.find((provider) => provider.id === draft.provider);
  const standby = compatible.find((provider) => provider.id === draft.backup_provider);
  const primaryModels = modelOptions(primary, draft.model, t, catalogState);
  const standbyModels = modelOptions(standby, draft.backup_model, t, catalogState);
  const providerList = compatible.map((provider) => [provider.id, provider.name || provider.id]);
  return `<form class="ac-editor" data-ac-route-form="${esc(capability.key)}"><div class="ac-editor__fields"><label class="ac-field"><span>${esc(t.providerField)}</span><select name="provider">${options(providerList, draft.provider, '')}</select></label><label class="ac-field"><span>${esc(t.modelField)}</span><select name="model"${primaryModels.disabled ? ' disabled' : ''}>${primaryModels.html}</select></label><label class="ac-field"><span>${esc(t.standbyProvider)}</span><select name="backup_provider">${options(providerList, draft.backup_provider || '', t.noStandby)}</select></label><label class="ac-field"><span>${esc(t.standbyModel)}</span><select name="backup_model"${standby && !standbyModels.disabled ? '' : ' disabled'}>${standby ? standbyModels.html : options([], '', t.noStandby)}</select></label><label class="ac-check"><input type="checkbox" name="enabled"${draft.enabled ? ' checked' : ''}><span>${esc(t.enabledField)}</span></label></div>${primaryModels.note ? `<p class="ac-note">${esc(primaryModels.note)}</p>` : ''}<div class="ac-editor__actions"><button type="submit" class="ac-button ac-button--primary" data-focus-key="save:${esc(capability.key)}"${primaryModels.disabled || !draft.model ? ' disabled' : ''}>${esc(t.saveRoute)}</button><button type="button" class="ac-button" data-ac-action="cancel-edit">${esc(t.cancel)}</button><span class="ac-editor__status" role="status">${esc(draft.message || '')}</span></div></form>`;
}

export function routingView(state, t, ui) {
  const providers = state.providers;
  const operations = new Map((state.operations?.by_capability || []).map((row) => [row.capability, row]));
  const rows = [];
  for (const capability of state.config?.capabilities || []) {
    const kind = capabilityKind(capability);
    const config = capability.config || {};
    const saved = capability.explicit_config_exists && capability.config;
    const enabled = kind === 'configurable'
      ? saved ? chip(config.enabled === false ? 'disabled' : 'enabled', t) : chip('not_configured', t)
      : chip(kind, t);
    const test = state.tests.get(capability.key);
    const standbyTest = state.tests.get(`${capability.key}:standby`);
    const actions = kind === 'configurable'
      ? `<div class="ac-actions"><button type="button" class="ac-button" data-ac-action="edit" data-key="${esc(capability.key)}" data-focus-key="edit:${esc(capability.key)}" aria-expanded="${state.editing === capability.key}">${esc(t.editRoute)}</button>${saved && config.enabled !== false ? `<button type="button" class="ac-button" data-ac-action="test" data-key="${esc(capability.key)}" data-focus-key="test:${esc(capability.key)}"${test?.state === 'testing' ? ' disabled' : ''}>${esc(t.test)}</button>` : ''}${saved && config.enabled !== false && config.backup_provider && config.backup_model ? `<button type="button" class="ac-button" data-ac-action="test-standby" data-key="${esc(capability.key)}" data-focus-key="standby:${esc(capability.key)}"${standbyTest?.state === 'testing' ? ' disabled' : ''}>${esc(t.testStandby)}</button>` : ''}</div>`
      : `<span class="ac-muted">${esc(kind === 'deterministic' ? t.notConfigurable_deterministic : t.notConfigurable_reserved)}</span>`;
    const label = capabilityLabel(capability.key, t);
    const hintText = t[`capHint_${capability.key}`];
    rows.push({
      attributes: ` data-capability="${esc(capability.key)}"${state.editing === capability.key ? ' data-editing' : ''}`,
      cells: [
        `<div class="ac-cell-stack"><strong>${esc(label)}${hintText ? info(hintText, label) : ''}</strong>${mono(capability.key)}<small>${esc(t[`operation_${capability.operation}`] || capability.operation)}</small></div>`,
        enabled,
        kind === 'configurable' ? route(saved ? config.provider : '', saved ? config.model : '', providers, t) : '<span class="ac-muted">—</span>',
        kind === 'configurable' ? route(saved ? config.backup_provider : '', saved ? config.backup_model : '', providers, t) : '<span class="ac-muted">—</span>',
        kind === 'configurable' ? healthCell(operations.get(capability.key), test, standbyTest, t, ui) : '<span class="ac-muted">—</span>',
        actions,
      ],
    });
    if (state.editing === capability.key) {
      rows.push({ attributes: ' class="ac-editor-row"', full: routeEditor(capability, state.draft, providers, t, state.catalogState) });
    }
  }
  const body = table({
    head: [t.colCapability, t.colEnabled, t.colPrimary, t.colStandby, t.colHealth, { label: t.colActions, hidden: true }],
    rows,
    empty: t.notAvailable,
    className: 'ac-table--routing',
  });
  return panel({ title: t.routingTitle, note: t.routesNote, body });
}

export function runtimeView(runtime, t, names = {}) {
  const ai = runtime?.ai || {};
  const legacy = ai.legacy_selection || {};
  const mode = ai.learner_runtime_mode;
  const modeText = mode === 'legacy' ? t.runtimeLegacy : mode === 'capability' ? t.runtimeCapability : t.runtimeInvalid;
  const effective = legacy.effective || {};
  const named = (id) => names[id] || id || '';
  const rows = [[t.runtimeTitle, `${chip(mode === 'legacy' ? 'legacy' : mode === 'capability' ? 'capability' : 'invalid', t)} <span>${esc(modeText)}</span>`]];
  if (mode === 'legacy') {
    rows.push([t.legacyRoute, legacy.source === 'saved'
      ? `${esc(named(legacy.provider))} ${mono(legacy.model || '')}${legacy.provider_configured === false ? chip('not_configured', t) : ''}`
      : esc(t.legacyDefault)]);
    rows.push([t.legacyEffective, `${esc(named(effective.provider))} ${mono(effective.model || '')}${effective.fallback ? chip('fallback', t) : ''}`]);
  }
  rows.push([t.activation, chip('human_gated', t, { label: t.activationGated })]);
  const fallback = mode === 'legacy' && legacy.source === 'saved' && legacy.provider_configured === false
    ? notice(fill(t.legacyFallbackNote, { provider: named(legacy.provider) }), 'warn')
    : '';
  return panel({ title: t.runtimeTitle, className: 'ac-panel--runtime', body: `${kv(rows)}${fallback}` });
}

function providerForm(provider, state, t) {
  const configuration = provider.configuration || {};
  const test = state.providerTests.get(provider.id);
  const models = test?.models?.length ? test.models : provider.models || [];
  const store = state.runtime?.ai?.credential_store;
  const stored = configuration.credential_source === 'encrypted_server_store';
  const needsKey = credentialState(provider) !== 'not_required';
  const storeNote = store === 'not_configured' ? t.storeUnavailable : store === 'invalid' ? t.storeInvalid : '';
  const allowed = models.map((model) => `<label class="ac-check"><input type="checkbox" name="models" value="${esc(model)}" checked><span>${esc(model)}</span></label>`).join('');
  return `<form class="ac-editor" data-ac-provider-form="${esc(provider.id)}"><h3>${esc(fill(t.providerFormTitle, { provider: provider.name || provider.id }))}</h3><div class="ac-editor__fields"><label class="ac-field ac-field--wide"><span>${esc(t.endpoint)}</span><input type="url" name="base_url" value="${esc(configuration.endpoint_url || '')}" autocomplete="url"></label>${needsKey ? `<label class="ac-field ac-field--wide"><span>${esc(t.apiKey)}${info(t.apiKeyHint, t.apiKey)}</span><input type="password" name="api_key" autocomplete="new-password" placeholder="${esc(stored ? t.apiKeyKeep : '')}"></label>` : ''}<label class="ac-field"><span>${esc(t.defaultModel)}</span><select name="default_model"${models.length ? '' : ' disabled'}>${options(models.map((model) => [model, model]), provider.default_model || '', t.chooseModel)}</select></label></div><fieldset class="ac-models"><legend>${esc(t.allowedModels)}</legend>${allowed || `<p class="ac-note">${esc(t.allowedModelsHint)}</p>`}</fieldset>${storeNote ? notice(storeNote, 'warn') : ''}<div class="ac-editor__actions"><button type="button" class="ac-button" data-ac-action="form-test" data-provider="${esc(provider.id)}">${esc(t.testConnection)}</button><button type="submit" class="ac-button ac-button--primary"${storeNote || !models.length ? ' disabled' : ''}>${esc(t.saveSecurely)}</button>${stored ? (state.confirmRemove === provider.id
    ? `<span class="ac-confirm" role="group"><span>${esc(fill(t.removeConfirm, { provider: provider.name || provider.id }))}</span><button type="button" class="ac-button ac-button--danger" data-ac-action="remove-provider" data-provider="${esc(provider.id)}">${esc(t.removeKey)}</button><button type="button" class="ac-button" data-ac-action="cancel-remove">${esc(t.cancel)}</button></span>`
    : `<button type="button" class="ac-button ac-button--danger" data-ac-action="ask-remove" data-provider="${esc(provider.id)}">${esc(t.removeKey)}</button>`) : ''}<button type="button" class="ac-button" data-ac-action="close-provider">${esc(t.close)}</button><span class="ac-editor__status" role="status">${esc(state.providerMessage || '')}</span></div></form>`;
}

export function providersView(state, t, ui) {
  const rows = [];
  for (const provider of state.providers) {
    const test = state.providerTests.get(provider.id);
    const connection = test
      ? test.state === 'testing'
        ? esc(t.testing)
        : test.state === 'ok'
          ? chip('ok', t, { label: fill(t.connectionOk, { count: num(test.count, ui), time: latency(test.time, ui) }) })
          : chip('failed', t, { label: test.reason })
      : `<span class="ac-muted">${esc(t.connectionNotTested)}</span>`;
    const models = provider.catalogLoaded
      ? provider.models.length
        ? `<button type="button" class="ac-button ac-button--quiet" data-ac-action="toggle-models" data-provider="${esc(provider.id)}" aria-expanded="${state.expanded === provider.id}">${esc(fill(t.showModels, { count: num(provider.models.length, ui) }))}</button>`
        : `<span class="ac-muted">0</span>`
      : `<span class="ac-muted">${esc(state.catalogState === 'loading' ? t.modelsLoading : t.modelsUnavailable)}</span>`;
    rows.push({
      attributes: ` data-provider="${esc(provider.id)}"`,
      cells: [
        `<div class="ac-cell-stack"><strong>${esc(provider.name || provider.id)}</strong>${mono(provider.id)}</div>`,
        esc(t[`kind_${provider.kind}`] || provider.kind || ''),
        chip(credentialState(provider) === 'unreadable' ? 'unreadable' : credentialState(provider) === 'not_configured' ? 'not_configured' : 'configured', t, { label: t[`credential_${credentialState(provider)}`] }),
        models,
        connection,
        `<div class="ac-actions"><button type="button" class="ac-button" data-ac-action="test-provider" data-provider="${esc(provider.id)}" data-focus-key="ptest:${esc(provider.id)}"${test?.state === 'testing' ? ' disabled' : ''}>${esc(t.testConnection)}</button><button type="button" class="ac-button" data-ac-action="configure" data-provider="${esc(provider.id)}" aria-expanded="${state.providerForm === provider.id}">${esc(t.configure)}</button></div>`,
      ],
    });
    if (state.expanded === provider.id && provider.models.length) {
      rows.push({ attributes: ' class="ac-editor-row"', full: `<ul class="ac-model-list">${provider.models.map((model) => `<li>${mono(model)}</li>`).join('')}</ul>` });
    }
    if (state.providerForm === provider.id) {
      rows.push({ attributes: ' class="ac-editor-row"', full: providerForm(provider, state, t) });
    }
  }
  return panel({
    title: t.providersTitle,
    body: table({
      head: [t.colProvider, t.colType, t.colCredential, t.colModels, t.colConnection, { label: t.colActions, hidden: true }],
      rows,
      empty: t.notAvailable,
      className: 'ac-table--providers',
    }),
  });
}

export function servicesView(runtime, t) {
  const services = runtime?.services || [];
  return panel({
    title: t.servicesTitle,
    note: t.servicesNote,
    body: table({
      head: [t.colService, t.colEngine, t.colModel, t.colState],
      rows: services.map((service) => [
        esc(t[`service_${service.id}`] || service.id),
        service.engine ? mono(service.engine) : '<span class="ac-muted">—</span>',
        service.model ? mono(service.model) : '<span class="ac-muted">—</span>',
        chip(service.state, t),
      ]),
      empty: t.notAvailable,
    }),
  });
}

export function aiView(state, t, ui) {
  const names = Object.fromEntries((state.providers || []).map((provider) => [provider.id, provider.name || provider.id]));
  return `<div class="ac-stack">${runtimeView(state.runtime, t, names)}${routingView(state, t, ui)}${providersView(state, t, ui)}${servicesView(state.runtime, t)}</div>`;
}

function healthReason(result, t) {
  const detail = result?.body?.detail;
  const code = detail && typeof detail === 'object' ? detail.error_class : '';
  return HEALTH_ERRORS.has(code) ? t[`healthError_${code}`] : failureReason(result) || t.healthError_unknown;
}

export async function renderAi(container, env) {
  const { t, ui, alive } = env;
  const api = env.api || adminApi;
  const state = {
    config: null,
    catalog: null,
    catalogState: 'loading',
    operations: null,
    runtime: null,
    providers: [],
    tests: new Map(),
    providerTests: new Map(),
    editing: null,
    draft: {},
    providerForm: null,
    providerMessage: '',
    confirmRemove: null,
    expanded: null,
  };

  const paint = () => {
    if (!alive()) return;
    const focusKey = document.activeElement?.dataset?.focusKey;
    state.providers = mergeProviders(state.config, state.catalog);
    container.innerHTML = aiView(state, t, ui);
    if (focusKey) container.querySelector(`[data-focus-key="${CSS.escape(focusKey)}"]`)?.focus();
  };

  const loadCore = async () => {
    const [config, operations, runtime] = await Promise.all([
      api.aiConfig(),
      api.aiOperations(200).catch(() => ({ available: false, by_capability: [] })),
      api.runtime(),
    ]);
    state.config = config;
    state.operations = operations;
    state.runtime = runtime;
  };
  const loadCatalog = async () => {
    state.catalogState = 'loading';
    try {
      state.catalog = await api.aiCatalog();
      state.catalogState = 'ready';
    } catch {
      state.catalogState = 'failed';
    }
    paint();
  };

  await loadCore();
  if (!alive()) return;
  paint();
  loadCatalog();

  const draftFrom = (key) => {
    const capability = (state.config?.capabilities || []).find((item) => item.key === key) || {};
    const config = capability.config || {};
    return {
      provider: config.provider || state.providers.find((provider) => provider.configured)?.id || state.providers[0]?.id || '',
      model: config.model_redacted ? '' : config.model || '',
      backup_provider: config.backup_provider || '',
      backup_model: config.backup_model_redacted ? '' : config.backup_model || '',
      enabled: config.enabled !== false,
      message: '',
    };
  };

  const test = async (key, standby) => {
    const slot = standby ? `${key}:standby` : key;
    state.tests.set(slot, { state: 'testing' });
    paint();
    const result = await api.testCapability(key, standby);
    if (!alive()) return;
    state.tests.set(slot, result.ok
      ? { state: 'ok', latency: result.body?.latency_ms }
      : { state: 'failed', reason: healthReason(result, t) });
    try {
      state.operations = await api.aiOperations(200);
    } catch {
      // The recorded view stays as it was; the test result above still stands.
    }
    paint();
  };

  const testProvider = async (id, body = {}) => {
    state.providerTests.set(id, { state: 'testing' });
    paint();
    const started = performance.now();
    const result = await api.testProvider(id, body);
    if (!alive()) return;
    const time = Math.round(performance.now() - started);
    const models = Array.isArray(result.body?.models) ? result.body.models : [];
    state.providerTests.set(id, result.ok
      ? { state: 'ok', count: models.length, time, models }
      : { state: 'failed', reason: failureReason(result) || t.healthError_unknown });
    paint();
  };

  const onClick = async (event) => {
    const button = event.target.closest('[data-ac-action]');
    if (!button || !container.contains(button)) return;
    const { acAction: action, key, provider } = button.dataset;
    if (action === 'edit') {
      state.editing = state.editing === key ? null : key;
      state.draft = draftFrom(key);
      paint();
    } else if (action === 'cancel-edit') {
      state.editing = null;
      paint();
    } else if (action === 'test') {
      await test(key, false);
    } else if (action === 'test-standby') {
      await test(key, true);
    } else if (action === 'test-provider') {
      await testProvider(provider);
    } else if (action === 'toggle-models') {
      state.expanded = state.expanded === provider ? null : provider;
      paint();
    } else if (action === 'configure') {
      state.providerForm = state.providerForm === provider ? null : provider;
      state.providerMessage = '';
      state.confirmRemove = null;
      paint();
    } else if (action === 'close-provider') {
      state.providerForm = null;
      paint();
    } else if (action === 'form-test') {
      const form = button.closest('form');
      const body = { base_url: form.elements.base_url?.value?.trim() || undefined };
      const key = form.elements.api_key?.value?.trim();
      if (key) body.api_key = key;
      if (form.elements.api_key) form.elements.api_key.value = '';
      await testProvider(provider, body);
    } else if (action === 'ask-remove') {
      state.confirmRemove = provider;
      paint();
    } else if (action === 'cancel-remove') {
      state.confirmRemove = null;
      paint();
    } else if (action === 'remove-provider') {
      const result = await api.removeProvider(provider);
      if (!alive()) return;
      state.confirmRemove = null;
      state.providerMessage = result.ok ? t.keyRemoved : failureReason(result) || t.healthError_unknown;
      await loadCore();
      await loadCatalog();
    }
  };

  const onChange = (event) => {
    const form = event.target.closest('[data-ac-route-form]');
    if (!form) return;
    state.draft = {
      ...state.draft,
      provider: form.elements.provider.value,
      model: event.target.name === 'provider' ? '' : form.elements.model.value,
      backup_provider: form.elements.backup_provider.value,
      backup_model: event.target.name === 'backup_provider' ? '' : form.elements.backup_model.value,
      enabled: form.elements.enabled.checked,
      message: '',
    };
    if (event.target.tagName === 'SELECT' && ['provider', 'backup_provider'].includes(event.target.name)) {
      paint();
      return;
    }
    // Choosing a model is what makes a route savable; say so without a repaint
    // that would take the operator's focus away from the field.
    const save = form.querySelector('button[type="submit"]');
    if (save) save.disabled = form.elements.model.disabled || !state.draft.model;
  };

  const onSubmit = async (event) => {
    const routeForm = event.target.closest('[data-ac-route-form]');
    const providerFormNode = event.target.closest('[data-ac-provider-form]');
    if (!routeForm && !providerFormNode) return;
    event.preventDefault();
    if (routeForm) {
      const key = routeForm.dataset.acRouteForm;
      const capability = (state.config?.capabilities || []).find((item) => item.key === key) || {};
      const saved = capability.config || {};
      const body = {
        enabled: routeForm.elements.enabled.checked,
        provider: routeForm.elements.provider.value,
        model: routeForm.elements.model.value,
        backup_provider: routeForm.elements.backup_provider.value || null,
        backup_model: routeForm.elements.backup_model.value || null,
        timeout_seconds: saved.timeout_seconds ?? null,
        temperature: saved.temperature ?? null,
        fallback_policy: saved.fallback_policy || (capability.allowed_fallback_policies || ['none'])[0],
      };
      state.draft = { ...state.draft, message: t.saving };
      paint();
      const result = await api.saveCapability(key, body);
      if (!alive()) return;
      if (result.ok) {
        await loadCore();
        state.editing = null;
        env.notify?.(t.routeSaved);
      } else {
        state.draft = { ...state.draft, message: fill(t.routeRejected, { reason: failureReason(result) || t.healthError_unknown }) };
      }
      paint();
      return;
    }
    const id = providerFormNode.dataset.acProviderForm;
    const elements = providerFormNode.elements;
    const models = [...providerFormNode.querySelectorAll('input[name="models"]:checked')].map((input) => input.value);
    const body = { base_url: elements.base_url?.value?.trim() || undefined, default_model: elements.default_model?.value || '', models };
    const key = elements.api_key?.value?.trim();
    if (key) body.api_key = key;
    if (elements.api_key) elements.api_key.value = '';
    state.providerMessage = t.saving;
    paint();
    const result = await api.saveProvider(id, body);
    if (!alive()) return;
    const name = state.providers.find((item) => item.id === id)?.name || id;
    state.providerMessage = result.ok ? fill(t.providerSaved, { provider: name }) : failureReason(result) || t.healthError_unknown;
    if (result.ok) {
      await loadCore();
      await loadCatalog();
    } else {
      paint();
    }
  };

  container.addEventListener('click', onClick);
  container.addEventListener('change', onChange);
  container.addEventListener('submit', onSubmit);
  return () => {
    container.removeEventListener('click', onClick);
    container.removeEventListener('change', onChange);
    container.removeEventListener('submit', onSubmit);
  };
}
