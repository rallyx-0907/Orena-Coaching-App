import { html } from '../../kit/html.js';
import { planName } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { t } from './copy.js';
import { pageHead, block, metrics, rowList, kv, stateBlock, formBlock, banner } from './blocks.js';

const value = (x) => x === null || x === undefined || x === '' ? t('opUnavailable') : String(x);
const key = (x) => String(x || '').replaceAll('_', ' ');
const rows = (items) => rowList(items, { title: t('opNone'), text: '' });
const section = (title, body) => block({ title: t(title), body });
const capabilityHref = (id, href) => /^[a-z][a-z0-9_]*$/.test(String(id || ''))
  ? href('adminCapability', { id }) : href('adminAi');
const titleKey = {
  adminOverview: 'navOverview', adminUsers: 'navUsers', adminUser: 'opAccounts',
  adminOperations: 'navOperations', adminWorkers: 'opWorkers', adminPolling: 'opPolling', adminErrors: 'opErrors',
};

export function issueHref(item, href) {
  if (item.kind === 'transcript_missing') return href('adminMedia');
  if (item.kind === 'content_waiting') return href('adminVocab');
  if (item.kind === 'import_failed' || item.kind === 'reading_jobs_failed') return href('adminJobs', {}, { status: 'failed' });
  if (item.section === 'ai' && item.subject) return capabilityHref(item.subject, href);
  if (item.provider) return href('adminProvider', { id: item.provider });
  return href(({ ai: 'adminAi', content: 'adminContent', imports: 'adminImports' })[item.section] || 'adminOperations');
}

/* D-111 point 5: every kind of content in the five states; a kind whose owner cannot be read says so. */
function contentStates(states) {
  if (!states) return t('opUnavailable');
  const order = states.states || ['live', 'review', 'invalid', 'failed', 'processing'];
  const tone = { invalid: 'warn', failed: 'err' };
  return html`${metrics(order.map((state) => ({ label: t(`opSt_${state}`), value: value(states.totals?.[state]), tone: states.totals?.[state] ? tone[state] || '' : '' })), { columns: 5 })}${rows(Object.entries(states.kinds || {}).map(([kind, counts]) => ({
    title: t(`opKind_${kind}`),
    meta: counts ? order.map((state) => `${t(`opSt_${state}`)} ${value(counts[state])}`).join(' · ') : t('opUnavailable'),
  })))}`;
}

function attention(data, href) {
  const severity = { critical: 0, warning: 1, info: 2 };
  return rows([...(data || [])].sort((a, b) => (severity[a.severity] ?? 3) - (severity[b.severity] ?? 3)).map((item) => ({
    title: key(item.kind), meta: [item.subject, item.provider].filter(Boolean).join(' · '),
    right: item.count == null ? '' : value(item.count),
    pills: [{ label: key(item.severity), tone: item.severity === 'critical' ? 'err' : 'warn' }],
    go: issueHref(item, href),
  })));
}

/* D-154: an account's role and plan, set by hand. `membership` is { account, plans, draft, error, status, busy, self }
   from control.js; an unreadable membership read draws nothing rather than a dead form. */
export function membershipBlock(membership) {
  if (!membership || !membership.account) return '';
  const { account, plans = [], draft, error = '', status = '', busy = false, self = false } = membership;
  // What the server applies now: an ended manual plan reads as Free; a stored "premium" is Pro (D-153/D-154).
  const ended = account.provider === 'manual' && account.until && new Date(account.until) <= new Date();
  const planId = ended || !account.plan_id ? 'free' : (account.plan_id === 'premium' ? 'pro' : account.plan_id);
  const current = plans.find((plan) => plan.id === planId) || { id: planId, name: planId };
  const source = ended ? t('mbEnded') : account.provider === 'manual' ? t('mbManual') : account.provider ? t('mbBilling') : '';
  const until = account.until && !ended ? t('mbUntilAt', { date: new Intl.DateTimeFormat(languages().ui, { dateStyle: 'medium', timeZone: 'UTC' }).format(new Date(account.until)) }) : '';
  const fields = [
    { id: 'mbRole', kind: 'seg', label: t('mbRole'), options: ['user', 'admin'].map((role) => ({ id: role, label: t(role === 'admin' ? 'mbRoleAdmin' : 'mbRoleUser'), on: draft.role === role, disabled: self })) },
    { id: 'mbPlan', kind: 'seg', label: t('mbPlan'), options: plans.map((plan) => ({ id: plan.id, label: planName(plan), on: draft.plan_id === plan.id })) },
    ...(draft.plan_id === 'free' ? [] : [{ id: 'mbUntil', type: 'date', label: t('mbUntil'), value: draft.until || '', hint: t('mbUntilHint') }]),
  ];
  return formBlock({
    title: t('mbTitle'),
    sub: [t('mbSub'), t('mbCurrent', { plan: [current ? planName(current) : '', source, until].filter(Boolean).join(' · ') }), self ? t('mbSelf') : ''].filter(Boolean).join(' '),
    fields,
    error,
    status,
    actions: [{ label: busy ? t('mbSaving') : t('mbSave'), a: 'membership-save', kind: 'primary', disabled: busy }],
  });
}

export function controlPage(route, data, { href, filters = {}, offset = 0 } = {}) {
  const title = t(titleKey[route]);
  let body = '';
  let sub = '';
  let back = null;
  if (route === 'adminOverview') {
    sub = t('opOverviewSub');
    const d = data.overview || {};
    body = html`<div class="a-overview-metrics">${metrics([
      { label: t('opActive'), value: d.activity?.available ? value(d.activity.active_7d) : t('opUnavailable') },
      { label: t('opNew'), value: d.accounts?.available ? value(d.accounts.new_7d) : t('opUnavailable') },
      // Every kind, Reading included (content.states); the older count left Reading out.
      { label: t('opPublished'), value: value(d.content?.states?.totals?.live ?? d.content?.published) },
      { label: t('opTotal'), value: d.accounts?.available ? value(d.accounts.total) : t('opUnavailable') },
    ], { columns: 4 })}</div>${section('opContentStates', contentStates(d.content?.states))}${section('opAttention', attention(d.attention, href))}${section('opRuntime', kv([
      { key: t('opMode'), value: value(d.ai?.runtime_mode) },
    ]))}${section('opDomains', d.activity?.available ? rows((d.activity.domains || []).map((domain) => ({ title: key(domain.domain), right: value(domain.events), meta: t('opCount') }))) : t('opUnavailable'))}
    ${section('opDaily', d.activity?.available ? rows((d.activity.daily || []).slice(-7).map((day) => ({ title: day.date, right: value(day.learners), meta: t('opActiveFilter') }))) : t('opUnavailable'))}`;
  } else if (route === 'adminUsers') {
    sub = t('opUsersSub');
    const summary = data.summary || {};
    const list = data.list || {};
    const field = (id, label, options) => ({ id, label: t(label), kind: 'select', options: options.map(([idValue, labelKey]) => ({ id: idValue, label: t(labelKey), on: (filters[id] || '') === idValue })) });
    body = html`${metrics([
      { label: t('opTotal'), value: summary.accounts?.available ? value(summary.accounts.total) : t('opUnavailable') },
      { label: t('opActive'), value: summary.activity?.available ? value(summary.activity.active_7d) : t('opUnavailable') },
    ])}${formBlock({ title: t('opAccounts'), fields: [
      field('role', 'opRole', [['', 'opAll'], ['user', 'opLearner'], ['admin', 'opAdmin']]),
      field('language', 'opLanguage', [['', 'opAll'], ['en', 'opEnglish'], ['zh', 'opChinese']]),
      field('activity', 'opStatus', [['', 'opAll'], ['active', 'opActiveFilter'], ['idle', 'opIdle'], ['never', 'opNever']]),
    ] })}${list.available === false ? stateBlock({ kind: 'unavail', heading: t('opUnavailable') }) : section('opAccounts', rows((list.items || []).map((item) => ({
      title: item.display_name || item.id, meta: [item.email_masked, ...(item.languages || [])].filter(Boolean).join(' · '),
      detail: `${t('opJoined')}: ${value(item.joined_at)} · ${t('opLastActive')}: ${value(item.last_active_at)}`,
      pills: [{ label: key(item.role) }, { label: key(item.status) }], go: href('adminUser', { id: item.id }),
    }))))}${block({ title: t('opCount'), body: kv([{ key: t('opCount'), value: value(list.total) }]), actions: [
      { label: t('opPrevious'), a: 'previous', disabled: offset === 0 },
      { label: t('opNext'), a: 'next', disabled: offset + (list.items?.length || 0) >= (list.total || 0) },
    ] })}`;
  } else if (route === 'adminUser') {
    const d = data.detail || {};
    back = { href: href('adminUsers'), label: t('navUsers') };
    body = html`${section('opAccounts', kv([
      { key: t('opAccounts'), value: value(d.display_name) }, { key: 'ID', value: value(d.id), mono: true },
      { key: t('opRole'), value: value(d.role) }, { key: t('opJoined'), value: value(d.joined_at) },
      { key: t('opLastActive'), value: value(d.last_active_at) },
    ]))}${section('opProfile', rows((d.profiles || []).map((p) => ({ title: value(p.language), meta: `${t('opSupport')}: ${value(p.support_language)}` }))))}
    ${section('opActivity', rows((d.activity || []).map((a) => ({ title: key(a.measure), meta: [a.language, a.last_at].filter(Boolean).join(' · '), right: value(a.count) }))))}
    ${membershipBlock(data.membership)}${block({ body: t('opPrivacy') })}`;
  } else {
    sub = t('opOperationsSub');
    const runtime = data.runtime || {};
    const telemetry = data.telemetry || {};
    if (route !== 'adminOperations') back = { href: href('adminOperations'), label: t('navOperations') };
    if (route === 'adminWorkers') {
      body = data.reading?.available === false ? stateBlock({ kind: 'unavail', heading: t('opWorkers'), text: t('opWorkerUnavailable'), actions: [{ label: t('opReading'), a: 'go', data: { to: href('adminJobs') } }] }) : block({ title: t('opWorkers'), sub: t('opWorkerClaims'), body: rows((data.reading?.workers?.items || []).map((worker) => ({ title: worker.worker_id, meta: `${t('opHeartbeat')}: ${value(worker.last_seen_at)} · ${t('opRunning')}: ${value(worker.running)}`, pills: [{ label: value(worker.state), tone: worker.state === 'stale' ? 'err' : 'mute' }] }))) });
    } else if (route === 'adminPolling') {
      body = section('opPolling', rows((data.sources?.items || data.sources?.sources || []).map((s) => ({ title: s.name || s.id, meta: `${key(s.state)} · ${key(s.rights_status)}`, go: href('adminSource', { id: s.id }) }))));
      body = html`${body}${block({ title: t('opPollingAction'), body: '', actions: [{ label: t('opPollingAction'), a: 'go', data: { to: href('adminSources') } }] })}`;
    } else {
      body = route === 'adminErrors' ? section('opAttention', data.overview?.available === false ? t('opUnavailable') : attention(data.overview?.attention, href)) : html`
        ${runtime.ai?.learner_runtime_mode === 'legacy' ? banner({ tone: 'warn', title: t('opMode'), text: t('opLegacy'), actions: [{ label: t('navAi'), a: 'go', data: { to: href('adminAi') } }] }) : ''}
        ${section('opRuntime', kv([
          { key: t('opBackend'), value: value(runtime.persistence_backend) },
          { key: t('opMode'), value: value(runtime.ai?.learner_runtime_mode) },
          { key: t('opCredential'), value: value(runtime.ai?.credential_store) },
        ]))}${section('opStores', kv(Object.entries(runtime.stores || {}).map(([name, state]) => ({ key: key(name), value: value(state) }))))}
        ${section('opServices', rows((runtime.services || []).map((s) => ({ title: key(s.id), meta: [s.engine, s.model].filter(Boolean).join(' · '), pills: [{ label: s.state === 'configured' ? t('opConfigured') : s.state === 'not_configured' ? t('opNotConfigured') : value(s.state) }] }))))}
        ${block({ title: t('opReading'), body: data.reading?.available === false ? t('opUnavailable') : metrics(['queued', 'running', 'failed', 'completed'].map((state) => ({ label: t(({ queued: 'opQueued', running: 'opRunning', failed: 'opFailed', completed: 'opCompleted' })[state]), value: data.reading?.queue ? value(data.reading.queue[state] ?? 0) : t('opUnavailable') }))), actions: [{ label: t('opReading'), a: 'go', data: { to: href('adminJobs') } }] })}`;
      body = html`${body}${block({ title: t('opTelemetry'), sub: t('opSample'), body: telemetry.available === false ? stateBlock({ kind: 'unavail', heading: t('opUnavailable') }) : rows((telemetry.by_capability || []).map((c) => ({
        title: key(c.capability), meta: `${t('opRequests')}: ${value(c.total)} · ${t('opFailures')}: ${value(c.failure_rate_percent)}% · ${t('opLatency')}: ${value(c.avg_latency_ms)} ms`,
        pills: [{ label: key(c.health_state), tone: c.health_state === 'healthy' ? 'ok' : 'warn' }], go: capabilityHref(c.capability, href),
      }))) })}${section('opEvents', rows((telemetry.recent || []).slice(0, 15).map((e) => ({
        title: key(e.capability), meta: [e.created_at, e.provider, e.error_class].filter(Boolean).join(' · '),
        pills: [{ label: key(e.outcome), tone: e.outcome === 'success' ? 'ok' : 'err' }],
        go: e.provider ? href('adminProvider', { id: e.provider }) : href('adminAi'),
      }))))}`;
      if (route === 'adminOperations') body = html`${body}${section('navOperations', rows([
        ['opReading', 'adminJobs'], ['opWorkers', 'adminWorkers'], ['opPolling', 'adminPolling'], ['opErrors', 'adminErrors'],
      ].map(([label, routeId]) => ({ title: t(label), go: href(routeId) }))))}`;
    }
  }
  return { title, filterValue: filters.q || '', markup: html`<section class="a-page">${pageHead({ title, sub, back, actions: [...(route === 'adminOverview' ? [{ label: t('trafTitle'), size: 'sm', a: 'go', data: { to: href('adminTraffic') } }] : []), ...(route === 'adminUsers' ? [{ label: t('plansTitle'), size: 'sm', a: 'go', data: { to: href('adminPlans') } }, { label: t('fbTitle'), size: 'sm', a: 'go', data: { to: href('adminFeedback') } }] : []), { label: t('retry'), a: 'reload' }] })}<div class="a-blocks">${body}</div></section>` };
}
