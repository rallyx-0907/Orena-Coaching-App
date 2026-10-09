import { html } from '../../kit/html.js';
import { loadingMarkup } from '../../kit/states.js';
import { adminApi } from '../../capabilities/admin-api.js';
import { createHost } from './host.js';
import { controlPage } from './control-pages.js';
import { pageHead, stateBlock } from './blocks.js';
import { t } from './copy.js';

/* The plan the server applies now: an ended manual plan is Free, a stored "premium" is Pro. */
function effectivePlan(account) {
  if (!account.plan_id) return 'free';
  if (account.provider === 'manual' && account.until && new Date(account.until) <= new Date()) return 'free';
  return account.plan_id === 'premium' ? 'pro' : account.plan_id;
}

/* The account's role and plan as a form draft (D-154). */
function membershipView(answer, context) {
  if (!answer || !answer.account) return null;
  const account = answer.account;
  return {
    account,
    plans: answer.plans || [],
    draft: { role: account.role, plan_id: effectivePlan(account), until: effectivePlan(account) !== 'free' && account.until ? String(account.until).slice(0, 10) : '' },
    error: '',
    status: '',
    busy: false,
    // Your own account: the server refuses a change to your own role; the form says so before you try.
    self: Boolean(account.email && context?.owner && String(context.owner).toLowerCase() === String(account.email).toLowerCase()),
  };
}

/* What Save sends: only what changed, and an end date only with a paid plan. */
export function membershipChange(view) {
  const change = {};
  if (view.draft.role !== view.account.role) change.role = view.draft.role;
  const plan = view.draft.plan_id;
  const until = plan === 'free' ? '' : view.draft.until;
  const stored = effectivePlan(view.account);
  if (plan !== stored || until !== (stored !== 'free' && view.account.until ? String(view.account.until).slice(0, 10) : '')) {
    change.plan_id = plan;
    if (until) change.until = `${until}T23:59:59Z`;
  }
  return change;
}

export async function mountControl(shell, ctx) {
  const host = createHost(shell, ctx);
  const route = ctx.route.id;
  const filters = { q: '', role: '', language: '', activity: '' };
  let offset = 0;
  let data = {};
  let loading = true;
  let failed = false;
  let generation = 0;
  let timer = 0;
  host.setBuilder(() => loading || failed ? {
    title: t(route === 'adminOverview' ? 'navOverview' : route.startsWith('adminUser') ? 'navUsers' : 'navOperations'),
    filterValue: filters.q,
    markup: html`<section class="a-page">${pageHead({ title: failed ? t('loadFailedTitle') : t('loading') })}${failed ? stateBlock({ kind: 'error', heading: t('loadFailedTitle'), text: t('loadFailedText'), actions: [{ label: t('retry'), a: 'reload' }] }) : loadingMarkup(t('loading'))}</section>`,
  } : controlPage(route, data, { href: ctx.href, filters, offset }), { filter: route === 'adminUsers' });

  async function load() {
    const request = ++generation;
    loading = true;
    failed = false;
    host.paint();
    try {
      if (route === 'adminOverview') data = { overview: await adminApi.overview() };
      else if (route === 'adminUser') {
        const [detail, membership] = await Promise.all([adminApi.user(ctx.params.id), adminApi.membership(ctx.params.id).catch(() => null)]);
        if (request !== generation) return;
        data = { detail, membership: membershipView(membership, ctx.context) };
      }
      else if (route === 'adminUsers') {
        const [summary, list] = await Promise.all([adminApi.usersSummary(), adminApi.users({ ...filters, offset, limit: 25 })]);
        if (request !== generation) return;
        data = { summary, list };
      } else if (route === 'adminPolling') data = { sources: await adminApi.readingSources() };
      else {
        const results = await Promise.allSettled([adminApi.runtime(), adminApi.aiOperations(), adminApi.overview(), adminApi.readingOperations()]);
        if (request !== generation) return;
        data = Object.fromEntries(['runtime', 'telemetry', 'overview', 'reading'].map((name, index) => [name, results[index].status === 'fulfilled' ? results[index].value : { available: false }]));
      }
    } catch {
      if (request !== generation) return;
      failed = true;
    }
    if (!host.alive() || request !== generation) return;
    loading = false;
    host.paint();
  }
  host.on('reload', load);
  host.on('pick', (_, dataset) => {
    const view = data.membership;
    if (!view || (dataset.field !== 'mbRole' && dataset.field !== 'mbPlan')) return;
    if (dataset.field === 'mbRole') view.draft.role = dataset.value;
    else view.draft.plan_id = dataset.value;
    view.status = '';
    view.error = '';
    host.paint();
  });
  host.on('membership-save', async () => {
    const view = data.membership;
    if (!view || view.busy) return;
    const change = membershipChange(view);
    if (!Object.keys(change).length) { view.status = t('mbSaved'); host.paint(); return; }
    view.busy = true;
    view.error = '';
    host.paint();
    try {
      const answer = await adminApi.saveMembership(ctx.params.id, change);
      if (!host.alive()) return;
      data.membership = { ...membershipView(answer, ctx.context), status: t('mbSaved') };
    } catch (failure) {
      view.busy = false;
      view.error = failure?.message || t('mbSaveFailed');
    }
    host.paint();
  });
  host.on('go', (_, dataset) => ctx.go(dataset.to));
  host.on('next', () => { offset += 25; load(); });
  host.on('previous', () => { offset = Math.max(0, offset - 25); load(); });
  host.onInput((field, next) => {
    if (field === 'mbUntil' && data.membership) { data.membership.draft.until = next; data.membership.status = ''; return; }
    if (!(field in filters)) return;
    filters[field] = next;
    offset = 0;
    load();
  });
  host.onFilter((next) => { filters.q = next; offset = 0; clearTimeout(timer); timer = setTimeout(load, 250); });
  await load();
  return () => { generation += 1; clearTimeout(timer); host.cleanup(); };
}
