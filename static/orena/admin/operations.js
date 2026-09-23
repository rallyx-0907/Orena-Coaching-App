/* Operations: the evidence behind the platform's state - readiness, recorded
   AI operations, learner runtime activation and the system itself.

   Readiness is the existing summary (/api/admin/readiness-summary) rendered
   as it is: its states and its approval are the server's, not this page's.
   Operation health is recorded telemetry; nothing here probes a provider. */
import { adminApi } from './api.js';
import { capabilityLabel } from './ai.js';
import { chip, dateTime, esc, fill, kv, latency, mono, notice, num, panel, percent, table } from './format.js';
import { futureBadge, gapNote, unavailableBlock } from './states.js';

export function readinessView(readiness, t) {
  if (!readiness || readiness.available === false) return panel({ title: t.readinessTitle, body: notice(t.notAvailable, 'neutral') });
  const rows = (readiness.indicators || []).map((indicator) => [
    esc(t[`indicator_${indicator.name}`] || indicator.name),
    chip(indicator.state, t),
    esc(indicator.source || '—'),
    esc(indicator.detail || ''),
  ]);
  return panel({
    title: t.readinessTitle,
    note: t.readinessNote,
    body: `${kv([
      [t.overall, chip(readiness.state, t)],
      [t.evidence, chip(readiness.evidence_state, t)],
      [t.approval, chip(readiness.approval_state || 'not_granted', t)],
    ])}${table({
      head: [t.colIndicator, t.colState, t.colSourceOps, t.colDetail],
      rows,
      empty: t.notAvailable,
    })}`,
  });
}

function tokens(row, ui) {
  const total = row.token_totals?.total_tokens;
  return total === null || total === undefined ? '—' : num(total, ui);
}

function cost(row, t) {
  const totals = row.cost_totals || [];
  if (!totals.length) return esc(t.costUnpriced);
  return esc(totals.map((item) => `${item.currency} ${Number(item.amount).toFixed(4)}`).join(', '));
}

export function operationsView(operations, t, ui, rules = null) {
  if (!operations || operations.available === false || !operations.has_data) {
    return panel({ title: t.operationsTitle, body: `<p class="ac-empty">${esc(t.opsEmpty)}</p>` });
  }
  const byCapability = table({
    head: [
      t.colCapability,
      t.colHealth,
      { label: t.colRequests, numeric: true },
      { label: t.colFailureRate, numeric: true },
      { label: t.colLatency, numeric: true },
      { label: t.colTokens, numeric: true },
      t.colCost,
      t.colQuota,
    ],
    rows: (operations.by_capability || []).map((row) => [
      `<div class="ac-cell-stack"><strong>${esc(capabilityLabel(row.capability, t))}</strong>${mono(row.capability)}</div>`,
      chip(row.health_state, t),
      esc(num(row.total, ui)),
      esc(row.failure_rate_percent === null || row.failure_rate_percent === undefined ? '—' : percent(row.failure_rate_percent, ui)),
      esc(latency(row.avg_latency_ms, ui)),
      esc(tokens(row, ui)),
      cost(row, t),
      esc(t[`quota_${row.quota_state}`] || row.quota_state || '—'),
    ]),
  });
  const recent = table({
    head: [t.colTime, t.colCapability, t.colOrigin, t.colOutcome, t.colProvider, { label: t.colLatency, numeric: true }, t.colErrorClass],
    rows: (operations.recent || []).slice(0, 15).map((event) => [
      esc(dateTime(event.created_at, ui)),
      esc(capabilityLabel(event.capability, t)),
      esc(t[`origin_${event.origin}`] || event.origin || '—'),
      chip(event.outcome === 'success' ? 'ok' : 'failed', t, { label: t[`outcome_${event.outcome}`] || event.outcome }),
      `<div class="ac-cell-stack"><span>${esc(event.provider || '—')}</span>${event.model ? mono(event.model) : ''}</div>`,
      esc(latency(event.latency_ms, ui)),
      event.error_class ? mono(event.error_class) : '',
    ]),
  });
  // The rule is the control plane's, sent by the server; without it nothing is claimed.
  const rule = rules && Number.isFinite(rules.degraded_latency_ms) && Number.isFinite(rules.degraded_failure_rate_percent)
    ? `<p class="ac-footnote">${esc(fill(t.opsHealthRule, { latency: latency(rules.degraded_latency_ms, ui), rate: percent(rules.degraded_failure_rate_percent, ui) }))}</p>`
    : '';
  return panel({
    title: t.operationsTitle,
    note: fill(t.opsSample, { count: num(operations.sample_limit || (operations.recent || []).length, ui) }),
    body: `${byCapability}${rule}<h3>${esc(t.recentEvents)}</h3>${recent}`,
  });
}

export function activationView(runtime, t) {
  const ai = runtime?.ai || {};
  const mode = ai.learner_runtime_mode;
  return panel({
    title: t.activationTitle,
    body: `${kv([
      [t.runtimeTitle, `${chip(mode === 'legacy' ? 'legacy' : mode === 'capability' ? 'capability' : 'invalid', t)} ${esc(mode === 'legacy' ? t.runtimeLegacy : mode === 'capability' ? t.runtimeCapability : t.runtimeInvalid)}`],
      [t.activation, chip('human_gated', t, { label: t.activationGated })],
    ])}<p class="ac-note">${esc(t.activationNote)}</p>`,
  });
}

export function systemView(runtime, t) {
  if (!runtime) return panel({ title: t.systemTitle, body: notice(t.notAvailable, 'neutral') });
  const schema = runtime.schema || {};
  const stores = runtime.stores || {};
  const backbone = runtime.account_backbone;
  const credentialStore = runtime.ai?.credential_store;
  return panel({
    title: t.systemTitle,
    body: kv([
      [t.sys_persistence, `${mono(runtime.persistence_backend || '—')}${runtime.persistence_backend === 'postgresql' ? chip('ok', t) : chip('invalid', t, { label: t.attention_persistence_not_authoritative })}`],
      [t.sys_schema, `${chip(schema.state, t)} ${schema.current ? esc(fill(t.schemaValue, { current: schema.current, expected: schema.expected || '—' })) : ''}`],
      [t.sys_backbone, chip(backbone === 'active' ? 'active' : backbone === 'disabled' ? 'off' : backbone || 'unknown', t)],
      [t.sys_media, chip(stores.media_index || 'unknown', t)],
      [t.sys_reading, chip(stores.reading_library || 'unknown', t)],
      [t.sys_vocabulary, chip(stores.vocabulary || 'unknown', t)],
      [t.sys_audit, chip(stores.audit_log || 'unknown', t)],
      [t.sys_credentials, chip(credentialStore === 'configured' ? 'configured' : credentialStore || 'unknown', t)],
      [t.sys_jobs, esc(t.jobsNone)],
      [t.sys_billing, `${chip('not_active', t)} ${esc(t.billingNotActive)}`],
      [t.sys_version, mono(runtime.app_version || '—')],
    ]),
  });
}

export function impactView(activity, t, ui) {
  const impact = activity?.learner_impact_failures;
  let body;
  if (!impact || impact.available === false) body = notice(t.impactUnavailable, 'neutral');
  else if (!(impact.by_capability || []).length) body = `<p class="ac-empty">${esc(t.impactNone)}</p>`;
  else {
    body = table({
      head: [t.colCapability, { label: t.colFailures, numeric: true }, { label: t.colDegraded, numeric: true }],
      rows: impact.by_capability.map((row) => [
        esc(capabilityLabel(row.capability, t)),
        esc(num(row.failure_count, ui)),
        esc(num(row.degraded_count, ui)),
      ]),
    });
  }
  return panel({ title: t.impactTitle, body });
}

/* The four areas the canonical design gives Operations: what the runtime is,
   what the worker is doing, what polling will do when it exists, and what an
   operator can act on right now. They are one section rather than four
   screens, because an operator reading one is usually about to read another. */
export function workerView(reading, t, ui) {
  if (!reading) return panel({ title: t.opsWorker, body: unavailableBlock(t, { title: t.opsWorker, note: t.readingOpsUnavailable }) });
  const queue = reading.queue || {};
  const running = Number(queue.running || 0);
  return panel({
    title: t.opsWorker,
    note: t.readingOpsWorkerNote,
    body: `${kv([
      [t.opsWorkerState, running ? chip('ok', t, { label: t.opsWorkerRunning }) : chip('info', t, { label: t.opsWorkerIdle })],
      [t.readingOpsQueued, esc(num(queue.queued || 0, ui))],
      [t.readingOpsRunning, esc(num(running, ui))],
      [t.readingOpsFailed, queue.failed ? chip('invalid', t, { label: num(queue.failed, ui) }) : esc(num(0, ui))],
    ])}${gapNote(t, t.opsWorkerHeartbeatGap)}`,
  });
}

export function pollingView(t) {
  /* Shown and disabled: recurring sources are designed, the registry and the
     rights gate exist, and nothing polls yet. The design keeps the control in
     the frame so the shape of the product is visible before it works. */
  // The badge rides in `actions`, which is raw markup; a panel escapes its
  // title, as it should.
  return panel({
    title: t.opsPolling,
    actions: futureBadge(t),
    body: `<p class="ac-note">${esc(t.opsPollingNote)}</p><div class="ac-actions"><button type="button" class="ac-button" disabled>${esc(t.opsPollingRun)}</button></div>`,
  });
}

export function actionableErrorsView(reading, activity, t, ui) {
  const failed = Number(reading?.queue?.failed || 0);
  const impact = activity?.learner_impact_failures;
  const rows = [];
  if (failed) {
    rows.push([
      esc(t.opsErrorReadingJobs),
      esc(num(failed, ui)),
      `<a class="ac-link" href="#/admin?id=imports&status=failed">${esc(t.opsErrorOpenImports)}</a>`,
    ]);
  }
  for (const row of impact?.by_capability || []) {
    rows.push([
      esc(t[`cap_${row.capability}`] || row.capability),
      esc(num(row.failure_count, ui)),
      `<a class="ac-link" href="#/admin?id=ai">${esc(t.opsErrorOpenAi)}</a>`,
    ]);
  }
  return panel({
    title: t.opsErrors,
    body: rows.length
      ? table({ head: [t.colWhat, { label: t.colCount, numeric: true }, { label: t.colActions, hidden: true }], rows })
      : `<p class="ac-empty">${esc(t.opsErrorsNone)}</p>`,
  });
}

export function readingEngineView(reading, t, ui) {
  /* The engine's own state, from its own endpoint: queue depth by state and
     how much is published. A runtime where the reviewed schema is not applied
     says so plainly rather than showing zeros that look like calm. */
  if (!reading) return panel({ title: t.readingOpsTitle, body: notice(t.readingOpsUnavailable, 'neutral') });
  const queue = reading.queue || {};
  return panel({
    title: t.readingOpsTitle,
    note: t.readingOpsWorkerNote,
    body: kv([
      [t.readingOpsQueued, esc(num(queue.queued || 0, ui))],
      [t.readingOpsRunning, esc(num(queue.running || 0, ui))],
      [t.readingOpsFailed, queue.failed ? chip('invalid', t, { label: num(queue.failed, ui) }) : esc(num(0, ui))],
      [t.readingOpsPublished, esc(num(reading.published || 0, ui))],
    ]),
  });
}

export function operationsSectionView({ readiness, runtime, operations, activity, reading = null }, t, ui) {
  return `<div class="ac-stack">${actionableErrorsView(reading, activity, t, ui)}${readinessView(readiness, t)}<div class="ac-grid ac-grid--2">${activationView(runtime, t)}${systemView(runtime, t)}</div><div class="ac-grid ac-grid--2">${workerView(reading, t, ui)}${pollingView(t)}</div>${operationsView(operations, t, ui, runtime?.ai?.health_rules)}${impactView(activity, t, ui)}</div>`;
}

export async function renderOperations(container, env) {
  const { t, ui, alive } = env;
  const api = env.api || adminApi;
  const [readiness, runtime, operations, activity, reading] = await Promise.all([
    api.readiness().catch(() => ({ available: false })),
    api.runtime().catch(() => null),
    api.aiOperations(200).catch(() => ({ available: false })),
    api.productActivity(7).catch(() => ({ available: false })),
    // A runtime without the reviewed Reading schema answers 503 here; that is
    // a state to report, not an error to fail the section on.
    api.readingOperations?.().catch(() => null) ?? null,
  ]);
  if (!alive()) return;
  container.innerHTML = operationsSectionView({ readiness, runtime, operations, activity, reading }, t, ui);
}
