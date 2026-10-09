/* AI & Models, drawn as the pinned design draws it (Orena-Admin.dc.html A2 list, A3 configure key,
   A4 provider detail, A5 capability routing). Pure: each builder takes the controller's state
   (capabilities/admin-ai.js), the page's own view state and the copy function, and returns markup -
   so scripts/test_orena_screen_admin.mjs renders every page from a fixture without a browser.

   What the design draws that the control plane cannot answer is left out, not invented
   (UI_BACKEND_GAPS "Admin: AI & Models"): a key's last four characters and its age, a provider's
   test history, a header environment label. */
import { html } from '../../kit/html.js';
import {
  capabilityRows,
  compatibleProviders,
  credentialState,
  modelChoices,
  providerStatus,
  providerUsage,
  providerUsedBy,
  removalConsequences,
  routeChanged,
  routingIsLive,
  standbySameProvider,
} from '../../capabilities/admin-ai.js';
import { relative, latency, num, percent } from '../../capabilities/admin-format.js';
import { humanKey, matchesFilter, providerMono, providerPill, routePill, sourceLabel } from './model.js';
import { banner, bars, block, chipRow, formBlock, kv, metrics, pageHead, rowList, skeleton, stateBlock, tabs } from './blocks.js';

const capName = (t, key) => (t.has(`cap_${key}`) ? t(`cap_${key}`) : humanKey(key));
const capHint = (t, key) => (t.has(`capHint_${key}`) ? t(`capHint_${key}`) : '');

export function capabilityName(t, key) {
  return capName(t, key);
}

/* The reason a route or provider test failed, in words. */
export function failureText(t, test) {
  if (test?.code) return t(`healthError_${test.code}`);
  return test?.reason || t('healthError_unknown');
}

const pillOf = (t, { label, tone }) => ({ label: t(label), tone });

function providerActions(t, provider, test) {
  const credential = credentialState(provider);
  const testing = test?.state === 'testing';
  const id = provider.id;
  const testButton = { label: t('actTest'), a: 'test-provider', data: { id }, disabled: testing };
  const update = { label: t('actUpdateKey'), a: 'open-key', data: { id } };
  const remove = { label: t('actRemoveKey'), kind: 'danger', a: 'ask-remove', data: { id } };
  if (credential === 'encrypted_server_store') return [testButton, update, remove];
  if (credential === 'server_environment' || credential === 'configured') return [testButton, update];
  if (credential === 'not_required') return [testButton, { label: t('actConfigure'), a: 'open-key', data: { id } }];
  if (credential === 'unreadable') return [{ label: t('actConfigure'), kind: 'primary', a: 'open-key', data: { id } }, remove];
  return [{ label: t('actConfigure'), kind: 'primary', a: 'open-key', data: { id } }];
}

function failingBanner(t, state, href) {
  const failing = state.providers.find((provider) => state.providerTests.get(provider.id)?.state === 'failed');
  if (!failing) return [];
  return [{
    tone: 'err',
    title: t('failingTitle', { provider: failing.name || failing.id }),
    text: t('failingText'),
    actions: [{ label: t('openProvider'), size: 'sm', a: 'go', data: { to: href('adminProvider', { id: failing.id }) } }],
  }];
}

/* A compact operational status, not body copy (D-104): shown only while it is true. */
function legacyStatus(t, state) {
  return routingIsLive(state.config) ? '' : html`<div class="a-opstatus" role="status"><span class="a-opstatus__dot" aria-hidden="true"></span>${t('runtimeLegacyStatus')}</div>`;
}

/* What an empty list says: nothing matches the header filter, or there is nothing to list. */
function emptyList(t, query) {
  const q = String(query || '').trim();
  return { title: q ? t('noMatch', { q }) : t('emptyNothing'), text: '' };
}

function loadFailed(t) {
  return stateBlock({ span: true, kind: 'error', heading: t('loadFailedTitle'), text: t('loadFailedText'), actions: [{ label: t('retry'), kind: 'primary', size: 'sm', a: 'reload' }] });
}

export const TOKEN_PERIODS = [1, 7, 30];

/* A2 Token usage, from the AI cost ledger (GET /api/admin/ai/costs): tokens, requests and audio seconds by
   capability x provider x model. The ledger has no per-day token count, no budget and no per-character
   count, so the design's per-day chart, budget block and alert are not drawn (UI_BACKEND_GAPS, "Admin Token
   usage"). Nothing here is estimated. */
function tokenUsage({ state, usage, t, ui }) {
  const compact = (value) => new Intl.NumberFormat(ui, { notation: 'compact', maximumFractionDigits: 1 }).format(value || 0);
  const whole = (value) => num(Math.round(value || 0), ui);
  const money = (value) => new Intl.NumberFormat(ui, { style: 'currency', currency: 'USD', minimumFractionDigits: value < 1 ? 4 : 2, maximumFractionDigits: value < 1 ? 4 : 2 }).format(value || 0);
  const days = usage.days;
  const periodLabel = days === 1 ? t('tkToday') : t('costDays', { n: days });
  const period = chipRow({ label: t('costRange'), a: 'tk-period', options: TOKEN_PERIODS.map((n) => ({ id: String(n), label: n === 1 ? t('tkToday') : t('costDays', { n }), on: n === days })) });
  if (usage.failed) return html`${period}<div class="a-blocks">${block({ span: true, body: t('opUnavailable') })}</div>`;
  if (!usage.report) return html`${period}${skeleton(t('loading'))}`;
  const features = usage.report.by_feature || [];
  const providerName = (id) => state.providers.find((item) => item.id === id)?.name || id || '';
  const tokens = (row) => (row.prompt_tokens || 0) + (row.completion_tokens || 0);
  const llm = features.filter((row) => tokens(row) > 0);
  const tin = llm.reduce((sum, row) => sum + row.prompt_tokens, 0);
  const tout = llm.reduce((sum, row) => sum + row.completion_tokens, 0);
  const total = tin + tout;
  const cost = features.reduce((sum, row) => sum + (row.usd || 0), 0);
  const share = (value, of) => (of ? Math.round((value / of) * 100) : 0);
  const byProvider = new Map();
  for (const row of features) {
    if (!row.provider) continue;
    const item = byProvider.get(row.provider) || { id: row.provider, input: 0, output: 0, calls: 0, usd: 0, seconds: 0 };
    item.input += row.prompt_tokens || 0;
    item.output += row.completion_tokens || 0;
    item.calls += row.calls || 0;
    item.usd += row.usd || 0;
    item.seconds += row.audio_seconds || 0;
    byProvider.set(row.provider, item);
  }
  const providerRows = [...byProvider.values()].sort((a, b) => b.usd - a.usd).map((item) => {
    const name = providerName(item.id);
    const parts = [];
    if (item.input + item.output) parts.push(t('tkProviderMeta', { input: compact(item.input), output: compact(item.output), calls: whole(item.calls) }));
    if (item.seconds) parts.push(t('tkProviderAudio', { minutes: whole(item.seconds / 60) }));
    return { tile: providerMono(name), title: name, meta: parts.join(' · '), right: money(item.usd) };
  });
  const byCapability = new Map();
  for (const row of llm) byCapability.set(row.capability, (byCapability.get(row.capability) || 0) + tokens(row));
  const capabilityBars = [...byCapability.entries()].sort((a, b) => b[1] - a[1]).map(([key, value]) => ({ label: capName(t, key), pct: share(value, total), value: `${share(value, total)}%` }));
  const modelRows = [...features].sort((a, b) => b.usd - a.usd).map((row) => {
    const audio = !tokens(row) && row.audio_seconds > 0;
    const requests = Math.max(1, (row.calls || 0) - (row.failures || 0));
    return {
      tile: providerMono(providerName(row.provider)),
      title: row.model || capName(t, row.capability),
      meta: audio
        ? t('tkAudioMeta', { provider: providerName(row.provider), minutes: whole(row.audio_seconds / 60), calls: whole(row.calls) })
        : t('tkModelMeta', { provider: providerName(row.provider), input: compact(row.prompt_tokens), output: compact(row.completion_tokens), avg: compact(tokens(row) / requests) }),
      pills: [{ label: t(audio ? 'tkPillAudio' : 'tkPillTokens'), tone: audio ? 'mute' : 'info' }],
      right: money(row.usd),
    };
  });
  const empty = { title: t('opNone'), text: '' };
  return html`${period}<div class="a-blocks">
    ${block({ span: true, body: metrics([
      { label: t('tkTotal'), value: compact(total), note: t('tkPeriodNote', { period: periodLabel }) },
      { label: t('tkIn'), value: compact(tin), note: t('tkShare', { pct: share(tin, total) }) },
      { label: t('tkOut'), value: compact(tout), note: t('tkShare', { pct: share(tout, total) }) },
      { label: t('costTotal'), value: money(cost), note: t('tkCostNote') },
    ], { columns: 4 }) })}
    ${block({ title: t('tkByProvider'), sub: t('tkByProviderSub'), body: rowList(providerRows, empty) })}
    ${block({ title: t('tkByCap'), sub: t('tkByCapSub'), body: capabilityBars.length ? bars(capabilityBars) : rowList([], empty) })}
    ${block({ span: true, title: t('tkByModel'), body: rowList(modelRows, empty) })}
  </div>`;
}

/* A2: the Providers, Capability routing and Token usage tabs. */
export function listPage({ state, view, t, ui, href, now }) {
  const tab = view.tab === 'route' ? 'route' : view.tab === 'tok' ? 'tok' : 'prov';
  const rows = capabilityRows(state.config, state.operations, state.providers);
  let body;
  if (tab === 'tok') {
    body = tokenUsage({ state, usage: view.usage || { days: 30, report: null, failed: false }, t, ui });
  } else if (tab === 'prov') {
    body = rowList(
      state.providers
        .filter((provider) => matchesFilter(view.query, provider.name, provider.id))
        .map((provider) => {
          const test = state.providerTests.get(provider.id);
          const credential = credentialState(provider);
          const used = providerUsedBy(state.config?.capabilities, provider.id).length;
          const parts = [t(sourceLabel(credential))];
          if (provider.catalogLoaded && provider.models.length) parts.push(t.plural('models', provider.models.length));
          parts.push(used ? t.plural('usedBy', used) : t('notUsed'));
          const pills = [pillOf(t, providerPill(providerStatus(provider, test)))];
          if ((test?.state === 'ok' || test?.state === 'failed') && test.at) pills.push({ label: t('lastTest', { when: relative(test.at, ui, now) }), tone: 'mute' });
          return {
            tile: providerMono(provider.name || provider.id),
            title: provider.name || provider.id,
            meta: parts.join(' · '),
            pills,
            actions: providerActions(t, provider, test),
            go: href('adminProvider', { id: provider.id }),
          };
        }),
      emptyList(t, view.query),
    );
  } else {
    body = rowList(
      rows
        .filter((row) => matchesFilter(view.query, capName(t, row.key), row.key))
        .map((row) => {
          const editable = row.kind === 'configurable';
          const side = (route) => (route ? `${route.name}${route.model ? ` · ${route.model}` : ''}` : '');
          return {
            title: capName(t, row.key),
            meta: row.saved ? t('routeMeta', { primary: side(row.primary) || t('routeNone'), standby: side(row.standby) || t('routeNone') }) : '',
            detail: capHint(t, row.key),
            pills: [pillOf(t, routePill(row.state))],
            actions: editable ? [{ label: t('actEditRoute'), a: 'go', data: { to: href('adminCapability', { id: row.key }) } }] : [],
            go: editable ? href('adminCapability', { id: row.key }) : '',
          };
        }),
      emptyList(t, view.query),
    );
  }
  const banners = tab === 'tok' ? [] : failingBanner(t, state, href);
  return {
    title: t('aiTitle'),
    markup: html`<section class="a-page" data-screen-label="A2 AI &amp; Models">
      ${pageHead({ title: t('aiTitle'), sub: t('aiSub'), actions: [{ label: t('costTitle'), size: 'sm', a: 'go', data: { to: href('adminAiCosts') } }] })}
      ${banners.map(banner)}
      ${tab === 'route' ? legacyStatus(t, state) : ''}
      ${tabs([
        { id: 'prov', label: t('tabProviders'), count: num(state.providers.length, ui), selected: tab === 'prov' },
        { id: 'route', label: t('tabRouting'), count: num(rows.length, ui), selected: tab === 'route' },
        { id: 'tok', label: t('tabTokens'), count: null, selected: tab === 'tok' },
      ])}
      ${tab === 'tok' ? body : html`<div class="a-blocks">${block({ span: true, flat: true, body })}</div>`}
    </section>`,
  };
}

/* The connection-test block of a provider (the design's four states). */
function testBlock(t, provider, test, ui, now) {
  const credential = credentialState(provider);
  const configured = credential !== 'not_configured' && credential !== 'unreadable';
  const title = t('testBlock');
  if (test?.state === 'testing') return stateBlock({ title, kind: 'empty', heading: t('testRunning'), text: t('testRunningText') });
  if (test?.state === 'ok') {
    const text = test.time == null ? t('testPassedNoTime', { when: relative(test.at, ui, now) }) : t('testPassedText', { ms: num(test.time, ui), when: relative(test.at, ui, now) });
    return stateBlock({ title, kind: 'ok', heading: t('testPassed'), text, actions: [{ label: t('actTestAgain'), size: 'sm', a: 'test-provider', data: { id: provider.id } }] });
  }
  if (test?.state === 'failed') {
    return stateBlock({
      title,
      kind: 'error',
      heading: t('testFailed'),
      text: t('testFailedText', { reason: failureText(t, test), when: relative(test.at, ui, now) }),
      actions: [
        { label: t('actUpdateKey'), kind: 'primary', size: 'sm', a: 'open-key', data: { id: provider.id } },
        { label: t('actTestAgain'), size: 'sm', a: 'test-provider', data: { id: provider.id } },
      ],
    });
  }
  return configured
    ? stateBlock({ title, kind: 'empty', heading: t('testNever'), text: t('testNeverText'), actions: [{ label: t('actRunTest'), kind: 'primary', size: 'sm', a: 'test-provider', data: { id: provider.id } }] })
    : stateBlock({ title, kind: 'unavail', heading: t('testNoKey'), text: t('testNoKeyText'), actions: [{ label: t('actConfigure'), kind: 'primary', size: 'sm', a: 'open-key', data: { id: provider.id } }] });
}

/* A4: one provider. */
export function providerPage({ state, view, t, ui, href, now }) {
  const provider = state.providers.find((item) => item.id === view.id);
  if (!provider) return { title: t('aiTitle'), markup: notFound(t, href) };
  const test = state.providerTests.get(provider.id);
  const credential = credentialState(provider);
  const status = providerPill(providerStatus(provider, test));
  const used = providerUsedBy(state.config?.capabilities, provider.id);
  const usage = providerUsage(state.operations, provider.id);
  const endpoint = provider.configuration?.endpoint_url || '';
  const head = providerActions(t, provider, test).filter((action) => action.a !== 'test-provider').map((action) => ({ ...action, size: 'md' }));

  let models;
  if (state.catalogState === 'loading' && !provider.catalogLoaded) models = stateBlock({ title: t('modelsBlock'), kind: 'empty', heading: t('modelsLoading') });
  else if (!provider.models.length) models = stateBlock({ title: t('modelsBlock'), kind: 'empty', heading: t('modelsEmptyTitle'), text: t('modelsEmptyText') });
  else models = block({ title: t('modelsBlock'), body: rowList(provider.models.map((model) => ({ title: model, pills: [{ label: t('modelAvailable'), tone: 'ok' }] }))) });

  const usedBy = block({
    title: t('usedByBlock'),
    sub: t('usedBySub'),
    body: rowList(
      used.map((item) => ({
        title: capName(t, item.key),
        meta: `${t(item.role === 'primary' ? 'rolePrimary' : 'roleStandby')}${item.model ? ` · ${item.model}` : ''}`,
        go: href('adminCapability', { id: item.key }),
      })),
      { title: t('usedByEmptyTitle'), text: t('usedByEmptyText') },
    ),
  });

  const usageBlock = usage
    ? block({
      title: t('usageBlock'),
      foot: t('usageFoot', { n: num(usage.sample, ui) }),
      body: metrics([
        { label: t('usageRequests'), value: num(usage.requests, ui) },
        { label: t('usageFailures'), value: percent(usage.failureRate, ui), tone: usage.failureRate > 5 ? 'err' : '' },
        { label: t('usageMean'), value: latency(usage.meanLatency, ui), note: t('usageMeanNote') },
        { label: t('usageP95'), value: t('usageP95Value'), note: t('usageP95Note'), tone: 'dim' },
      ]),
    })
    : stateBlock({ title: t('usageBlock'), kind: 'unavail', heading: t('usageNoneTitle'), text: t('usageNoneText') });

  return {
    title: `${t('aiTitle')} · ${provider.name || provider.id}`,
    crumb: provider.name || provider.id,
    markup: html`<section class="a-page" data-screen-label="A4 Provider detail">
      ${pageHead({ back: { href: href('adminAi'), label: t('aiTitle') }, pills: [pillOf(t, status)], title: provider.name || provider.id, sub: endpoint, actions: head })}
      <div class="a-blocks">
        ${block({ title: t('kvCredential'), body: kv([
          { key: t('kvStatus'), value: t(sourceLabel(credential)), tone: ['encrypted_server_store', 'server_environment', 'configured'].includes(credential) ? 'ok' : credential === 'unreadable' ? 'err' : '' },
          { key: t('kvEndpoint'), value: endpoint || '—', mono: true },
          { key: t('kvDefaultModel'), value: provider.default_model || '—', mono: true },
          ...(usage?.lastSuccessAt ? [{ key: t('kvLastSuccess'), value: relative(usage.lastSuccessAt, ui, now), tone: 'ok' }] : []),
          ...(usage?.lastFailureAt ? [{ key: t('kvLastFailure'), value: relative(usage.lastFailureAt, ui, now), tone: 'err' }, ...(usage.lastError ? [{ key: t('kvLastError'), value: usage.lastError, mono: true }] : [])] : []),
        ]) })}
        ${testBlock(t, provider, test, ui, now)}
        ${models}
        ${usedBy}
        ${usageBlock}
      </div>
    </section>`,
  };
}

/* A3: write a key (write-only) and set the endpoint. */
export function keyPage({ state, view, t, href }) {
  const provider = state.providers.find((item) => item.id === view.id);
  if (!provider) return { title: t('aiTitle'), markup: notFound(t, href) };
  const credential = credentialState(provider);
  const needsKey = credential !== 'not_required';
  const stored = ['encrypted_server_store', 'server_environment', 'configured'].includes(credential);
  const form = view.form || {};
  const name = provider.name || provider.id;
  const known = provider.models || [];
  const fields = [];
  if (needsKey) {
    fields.push({
      id: 'key', kind: 'text', type: 'password', label: t('fieldKey'), span: true, invalid: Boolean(form.error), value: form.key || '',
      placeholder: stored ? t('keyPlaceholderReplace') : t('keyPlaceholderNew'), tag: stored ? t(sourceLabel(credential)) : t('keyNone'),
      hint: stored ? t('keyHint') : '',
    });
  }
  fields.push({ id: 'endpoint', kind: 'text', label: t('fieldEndpoint'), value: form.endpoint ?? provider.configuration?.endpoint_url ?? '',
    hint: provider.id === 'azure-speech' ? t('azureSpeechHint') : '' });
  if (provider.id === 'azure-openai') {
    fields.push({ id: 'model', kind: 'text', label: t('fieldDefaultModel'), value: form.model || provider.default_model || '', hint: t('azureDeploymentHint') });
  } else if (provider.id !== 'azure-speech' && known.length) {
    const chosen = form.model || provider.default_model || known[0];
    fields.push({ id: 'model', kind: 'seg', label: t('fieldDefaultModel'), options: known.map((model) => ({ id: model, label: model, on: model === chosen })) });
  }
  const busy = Boolean(form.busy);
  return {
    title: `${t('aiTitle')} · ${stored ? t('formTitleUpdate', { provider: name }) : t('formTitleNew', { provider: name })}`,
    crumb: name,
    markup: html`<section class="a-page" data-screen-label="A3 Provider configure">
      ${pageHead({ back: { href: href('adminProvider', { id: provider.id }), label: name }, title: stored ? t('formTitleUpdate', { provider: name }) : t('formTitleNew', { provider: name }), sub: t('formSub') })}
      <div class="a-blocks">${formBlock({
        title: t('formCredential'),
        span: true,
        fields,
        error: form.error ? t(form.error, form.errorParams) : form.reason || '',
        status: busy ? t(form.busy) : '',
        actions: [
          { label: t('actCancel'), a: 'go', data: { to: href('adminProvider', { id: provider.id }) }, disabled: busy },
          { label: t('actSave'), a: 'save-key', data: { test: '0' }, disabled: busy },
          { label: t('actSaveTest'), kind: 'primary', a: 'save-key', data: { test: '1' }, disabled: busy },
        ],
      })}</div>
    </section>`,
  };
}

function routeTestLine(t, test, ui, needsSave) {
  if (needsSave) return { text: t('testNeedsSave'), tone: '' };
  if (!test) return { text: t('testNotYet'), tone: '' };
  if (test.state === 'testing') return { text: t('statusTesting'), tone: 'info' };
  if (test.state === 'ok') return { text: t('testResultOk', { ms: latency(test.latency, ui) }), tone: 'ok' };
  return { text: failureText(t, test), tone: 'err' };
}

/* The saved side of the draft: a route test runs against what the server has saved, so it is only
   offered while the draft matches it. */
function sideSaved(saved, draft, side) {
  if (!saved || saved.enabled === false) return false;
  return side === 'p'
    ? saved.provider === draft.provider && saved.model === draft.model && Boolean(draft.model)
    : Boolean(saved.backup_provider) && saved.backup_provider === draft.backup_provider && saved.backup_model === draft.backup_model;
}

/* A5: one capability's route - primary, standby, availability. */
export function capabilityPage({ state, view, t, ui, href }) {
  const capability = (state.config?.capabilities || []).find((item) => item.key === view.id);
  if (!capability) return { title: t('aiTitle'), markup: notFound(t, href) };
  const saved = capability.explicit_config_exists ? capability.config : null;
  const draft = view.draft;
  const compatible = compatibleProviders(capability, state.providers);
  const name = capName(t, capability.key);
  const dirty = routeChanged(saved || {}, draft) || !saved;
  const needs = (side) => !sideSaved(saved, draft, side);

  const providerOptions = (which) => [
    ...(which === 's' ? [{ id: '', label: t('none'), on: !draft.backup_provider }] : []),
    ...compatible.map((provider) => {
      const configured = Boolean(provider.configured);
      const status = providerPill(providerStatus(provider, state.providerTests.get(provider.id)));
      return {
        id: provider.id,
        label: provider.name || provider.id,
        sub: configured ? t(status.label) : t('statusNotConfigured'),
        on: (which === 'p' ? draft.provider : draft.backup_provider) === provider.id,
        disabled: !configured && (which === 'p' ? draft.provider : draft.backup_provider) !== provider.id,
        tip: configured ? '' : t('needsKey'),
      };
    }),
  ];
  const modelOptions = (which) => {
    const providerId = which === 'p' ? draft.provider : draft.backup_provider;
    const chosen = which === 'p' ? draft.model : draft.backup_model;
    const provider = compatible.find((item) => item.id === providerId);
    const { models, loading } = modelChoices(provider, chosen, state.catalogState);
    return {
      loading,
      options: models.map((model) => ({
        id: model.id, label: model.id, on: model.id === chosen, sub: model.unavailable ? t('unavailableModel') : '',
        disabled: model.unavailable && model.id !== chosen, tip: model.unavailable ? t('unavailableModelTip') : '',
      })),
    };
  };
  const primaryLine = routeTestLine(t, state.routeTests.get(capability.key), ui, needs('p'));
  const standbyLine = routeTestLine(t, state.routeTests.get(`${capability.key}:standby`), ui, needs('s'));
  const primaryModels = modelOptions('p');
  const standbyModels = modelOptions('s');
  const banners = [...(standbySameProvider(draft) ? [{ tone: 'warn', title: t('sameProviderTitle'), text: t('sameProviderText') }] : [])];

  const enabledPill = draft.enabled ? { label: t('routeEnabled'), tone: 'ok' } : { label: t('routeDisabledPill'), tone: 'mute' };
  return {
    title: `${t('aiTitle')} · ${name}`,
    crumb: name,
    markup: html`<section class="a-page" data-screen-label="A5 Capability routing">
      ${pageHead({ back: { href: href('adminAi', {}, { tab: 'route' }), label: t('tabRouting') }, pills: [enabledPill], title: name, sub: capHint(t, capability.key) })}
      ${banners.map(banner)}
      ${legacyStatus(t, state)}
      <div class="a-blocks">
        ${formBlock({
          title: t('blockPrimary'),
          fields: [
            { id: 'provider', kind: 'seg', label: t('fieldProvider'), span: true, options: providerOptions('p') },
            { id: 'model', kind: 'seg', label: t('fieldModel'), span: true, options: primaryModels.options, hint: primaryModels.loading ? t('modelsLoading') : primaryModels.options.length ? primaryLine.text : t('noModelsYet'), hintTone: primaryLine.tone },
          ],
          actions: [{ label: t('actTestPrimary'), a: 'test-route', data: { side: 'p' }, disabled: needs('p') || state.routeTests.get(capability.key)?.state === 'testing', tip: needs('p') ? t('testNeedsSave') : '' }],
        })}
        ${formBlock({
          title: t('blockStandby'),
          sub: t('blockStandbySub'),
          fields: [
            { id: 'backup_provider', kind: 'seg', label: t('fieldProvider'), span: true, options: providerOptions('s') },
            ...(draft.backup_provider ? [{ id: 'backup_model', kind: 'seg', label: t('fieldModel'), span: true, options: standbyModels.options, hint: standbyModels.loading ? t('modelsLoading') : standbyLine.text, hintTone: standbyLine.tone }] : []),
          ],
          actions: [{ label: t('actTestStandby'), a: 'test-route', data: { side: 's' }, disabled: !draft.backup_provider || needs('s') || state.routeTests.get(`${capability.key}:standby`)?.state === 'testing', tip: draft.backup_provider && needs('s') ? t('testNeedsSave') : '' }],
        })}
        ${formBlock({
          title: t('blockAvailability'),
          span: true,
          fields: [{ id: 'enabled', kind: 'toggle', label: t('fieldCapability'), span: true, on: draft.enabled, toggleLabel: draft.enabled ? t('toggleOn') : t('toggleOff') }],
          error: view.error || '',
          status: view.busy ? t('saving') : '',
          actions: [
            { label: t('actDiscard'), a: 'discard-route', disabled: !dirty || view.busy },
            { label: dirty ? t('actSaveRoute') : t('actSaved'), kind: 'primary', a: 'save-route', disabled: !dirty || !draft.model || view.busy },
          ],
        })}
      </div>
    </section>`,
  };
}

function notFound(t, href) {
  return html`<section class="a-page">${pageHead({ back: { href: href('adminAi'), label: t('aiTitle') }, title: t('aiTitle') })}<div class="a-blocks">${stateBlock({ span: true, kind: 'unavail', heading: t('usedByEmptyTitle'), text: '' })}</div></section>`;
}

/* The remove-credential dialog's content (title, sentence, consequences, the word to type). */
export function removeDialog({ state, providerId, typed, t }) {
  const provider = state.providers.find((item) => item.id === providerId);
  if (!provider) return null;
  const name = provider.name || provider.id;
  const primary = removalConsequences(providerId, state.config?.capabilities, state.providers);
  const standby = (state.config?.capabilities || []).filter((capability) => capability.config?.backup_provider === providerId && capability.config?.enabled !== false);
  const list = [
    ...primary.map((row) => t(row.fallback ? 'removeLosesPrimaryFallback' : 'removeLosesPrimaryNone', { capability: capName(t, row.key), provider: row.fallback })),
    ...standby.map((capability) => t('removeLosesStandby', { capability: capName(t, capability.key) })),
  ];
  return {
    title: t('removeTitle', { provider: name }),
    body: t('removeBody'),
    list: list.length ? list : [t('removeNoneUse')],
    typeWord: name,
    typeLabel: t('removeType', { word: name }),
    typed,
    cancel: t('actCancel'),
    confirm: t('removeConfirm'),
    danger: true,
    ready: typed.trim() === name,
  };
}

export { loadFailed };
