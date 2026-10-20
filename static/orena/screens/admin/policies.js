/* Admin > Operations > Policies & limits (D-172; the human's requirement 2026-10-11: "all tuning must be in Admin;
   changing something must never require touching code").

   The operational parameters the server used to carry as constants or environment variables - the Orena message
   limits, voice, speech and pronunciation, media import, feedback and retention, spend caps - as ONE page of kit blocks:
   a form block per group, each field a label, the value in force, where that value comes from (default, set in Admin,
   or locked by an environment variable the operator pinned), its unit and range, and one sentence saying what it does.
   Quota enforcement is the first block: it is its own document (`product.quota_enforcement`, D-161) and keeps its own
   Save; the rest is the `platform.policies` document and one Save at the foot and in the head.

   Save sends only what changed (`set` / `reset`) with the version the page loaded (`expected_updated_at`: a stale page
   is a 409 and nothing is overwritten). A change that deletes data (a retention switch or period) or raises a spend cap
   past its sane maximum is confirmed in a dialog first, and the server refuses it without that confirmation too.
   Built from existing kit blocks only; the page has no design frame of its own (scripts/test_orena_screen_admin.mjs
   KIT_PAGES). */
import { html, raw } from '../../kit/html.js';
import { languages } from '../../copy/index.js';
import { adminApi } from '../../capabilities/admin-api.js';
import { t } from './copy.js';
import { banner, block, formBlock, pageHead, skeleton } from './blocks.js';
import { createHost } from './host.js';
import { humanKey } from './model.js';
import { featureLabel } from './plans.js';

/* The order the groups are drawn in; "quota" first (the enforcement switch is above its settlement policy). */
export const GROUP_ORDER = Object.freeze(['quota', 'agent', 'voice', 'speech', 'media', 'vocabulary', 'rates', 'feedback', 'spend', 'billing', 'health', 'access']);

const copyKey = (prefix, key) => `${prefix}${String(key).replace(/[.]/g, '_')}`;
const text = (value) => (value == null ? '' : String(value));

/* ---- the pure model: drafts, the change a Save sends, and the confirmations it needs ------------------------ */

/* What a field's input holds before the operator touches it: the value in force, as typed. */
export function draftOf(policy) {
  if (policy.kind === 'bool') return policy.value === true;
  if (policy.kind === 'enum') return text(policy.value);
  return policy.value == null ? '' : text(policy.value);
}

export function draftsOf(doc) {
  return Object.fromEntries((doc?.policies || []).map((policy) => [policy.key, draftOf(policy)]));
}

/* The value an operator typed, as the server reads it. Text that is not a number is sent as typed, so the server's own
   message names it (nothing is corrected silently here); an empty box is "no cap" only where the policy allows one. */
export function parsedValue(policy, draft) {
  if (policy.kind === 'bool') return draft === true;
  if (policy.kind === 'enum') return text(draft);
  const typed = text(draft).trim();
  if (typed === '') return policy.nullable ? null : '';
  return Number.isFinite(Number(typed)) ? Number(typed) : typed;
}

const same = (a, b) => (a === b) || (typeof a === 'number' && typeof b === 'number' && Math.abs(a - b) < 1e-9);

/* {set, reset, changed}: the policies whose draft differs from the value in force. A policy an environment variable pins
   is never sent. Returning a stored value to its default is a reset, so the policy follows the default again. */
export function changeOf(doc, drafts) {
  const set = {};
  const reset = [];
  const changed = [];
  for (const policy of doc?.policies || []) {
    if (policy.locked || !(policy.key in drafts)) continue;
    const next = parsedValue(policy, drafts[policy.key]);
    if (same(next, policy.value)) continue;
    changed.push({ policy, from: policy.value, to: next });
    if (same(next, policy.default) && policy.has_admin) reset.push(policy.key);
    else set[policy.key] = next;
  }
  return { set, reset, changed };
}

/* Does this change need the operator's explicit yes? Mirrors the server's rule (writing_coach/policies.py), which
   enforces it: a policy that can delete data or changes what a learner is charged, or a value past the policy's sane
   maximum (or no cap at all). */
export function needsConfirmation(policy, from, to) {
  if (same(from, to)) return false;
  if (policy.danger) return true;
  return policy.confirm_above != null && (to === null || (typeof to === 'number' && to > policy.confirm_above));
}

export function confirmationsOf(change) {
  return change.changed.filter(({ policy, from, to }) => needsConfirmation(policy, from, to));
}

/* ---- words for one policy ------------------------------------------------------------------------------------ */

export function policyLabel(policy) {
  const key = copyKey('pol_', policy.key);
  return t.has(key) ? t(key) : humanKey(String(policy.key).replace(/[._]/g, ' '));
}

function policyHelp(policy) {
  const key = copyKey('polHelp_', policy.key);
  return t.has(key) ? t(key) : '';
}

/* A value as the operator reads it: with its unit, "off" / "on" for a switch, "no cap" for a cap that is not set. */
export function valueLabel(policy, value, ui = 'en') {
  if (policy.kind === 'bool') return value ? t('polOn') : t('polOff');
  if (value === null || value === undefined) return policy.nullable ? t('polNoCap') : '';
  if (policy.kind === 'enum') {
    const key = copyKey('polChoice_', `${policy.key}_${value}`);
    return t.has(key) ? t(key) : text(value);
  }
  const number = new Intl.NumberFormat(ui, { maximumFractionDigits: 4 }).format(Number(value));
  const unit = policy.unit && t.has(`polUnit_${policy.unit}`) ? t(`polUnit_${policy.unit}`) : '';
  return unit ? `${number} ${unit}` : number;
}

function sourceTag(policy) {
  if (policy.locked) return t('polLocked');
  return policy.source === 'admin' ? t('polSourceAdmin') : t('polSourceDefault');
}

function hintOf(policy, ui) {
  const parts = [policyHelp(policy)];
  if (policy.locked) parts.push(t('polLockedHint', { env: policy.env }));
  else if (policy.kind === 'int' || policy.kind === 'float') {
    const unit = policy.unit && t.has(`polUnit_${policy.unit}`) ? ` ${t(`polUnit_${policy.unit}`)}` : '';
    parts.push(t('polRange', { low: new Intl.NumberFormat(ui).format(policy.low), high: new Intl.NumberFormat(ui).format(policy.high), unit }));
  }
  if (!policy.locked || policy.default !== policy.value) parts.push(t('polDefaultIs', { value: valueLabel(policy, policy.default, ui) }));
  if (policy.danger && !policy.locked) parts.push(t('polDangerHint'));
  return parts.filter(Boolean).join(' · ');
}

/* The kit form field for one policy (blocks.js `field`): a switch, a choice or a number box. A locked policy is
   shown with its value and cannot be edited. */
export function fieldOf(policy, draft, ui = 'en') {
  const base = { id: `pol|${policy.key}`, label: policyLabel(policy), tag: sourceTag(policy), hint: hintOf(policy, ui), hintTone: policy.locked ? 'warn' : '' };
  if (policy.kind === 'bool') {
    return { ...base, kind: 'toggle', on: draft === true, toggleLabel: draft === true ? t('polOn') : t('polOff'), disabledToggle: policy.locked };
  }
  if (policy.kind === 'enum') {
    return { ...base, kind: 'select', disabled: policy.locked, options: policy.choices.map((choice) => ({ id: choice, label: valueLabel(policy, choice, ui), on: draft === choice })) };
  }
  return { ...base, kind: 'text', value: text(draft), readOnly: policy.locked, placeholder: policy.nullable ? t('polNoCap') : '' };
}

/* ---- the quota switch (its own endpoint and document, D-161) ------------------------------------------------- */

export function quotaDraftOf(quota) {
  const enforced = new Set(quota?.meters || []);
  return { enabled: quota?.enabled === true, meters: Object.fromEntries([...(quota?.wired_meters || []), ...(quota?.wired_entitlements || [])].map((key) => [key, enforced.has(key)])) };
}

/* What the quota Save sends: the whole switch (it is a small document), with the version it was loaded at. */
export function quotaPayload(quota, draft) {
  return {
    enabled: draft.enabled === true,
    meters: Object.entries(draft.meters).filter(([, on]) => on).map(([key]) => key),
    expected_updated_at: quota?.updated_at || null,
  };
}

function quotaStateLine(quota) {
  if (quota.state === 'unavailable') return t('polQuotaState_unavailable', { reason: quota.reason || '' });
  return t(quota.state === 'enforced' ? 'polQuotaState_enforced' : 'polQuotaState_off');
}

function changedLine(meta, ui) {
  if (!meta?.updated_at) return '';
  const date = new Date(meta.updated_at);
  const when = Number.isNaN(date.getTime()) ? String(meta.updated_at) : new Intl.DateTimeFormat(ui, { dateStyle: 'medium', timeStyle: 'short' }).format(date);
  return [t('polChangedAt', { when }), meta.updated_by ? t('polChangedBy', { name: meta.updated_by }) : ''].filter(Boolean).join(' · ');
}

/* Where each card sits on the desktop two-column page (phones keep the authored order, one column). */
export const GROUP_COLUMN = Object.freeze({ quota: 'left', agent: 'left', voice: 'left', speech: 'left', media: 'left', rates: 'right', billing: 'right', vocabulary: 'right', spend: 'right', feedback: 'right', health: 'right', access: 'left' });

function quotaBlock(view, ui) {
  const { quota, quotaDraft: draft } = view;
  if (!quota) return block({ col: 'left', title: t('polQuotaTitle'), body: html`<p class="a-sub">${t('polQuotaUnavailable')}</p>` });
  const locked = quota.source === 'environment';
  const fields = [
    { id: 'quota|enabled', kind: 'toggle', label: t('polQuotaSwitch'), tag: locked ? t('polLocked') : (quota.source === 'setting' ? t('polSourceAdmin') : t('polSourceDefault')), span: true, on: draft.enabled, toggleLabel: draft.enabled ? t('polOn') : t('polOff'), disabledToggle: locked, hint: [t('polQuotaHelp'), locked ? t('polQuotaLockedHint') : ''].filter(Boolean).join(' · '), hintTone: locked ? 'warn' : '' },
    ...Object.keys(draft.meters).map((key) => ({ id: `quota|meter|${key}`, kind: 'toggle', label: featureLabel(key), span: true, on: draft.meters[key], toggleLabel: draft.meters[key] ? t('polQuotaEnforced') : t('polQuotaNotEnforced'), disabledToggle: locked })),
  ];
  return formBlock({
    col: 'left',
    title: t('polQuotaTitle'),
    sub: [quotaStateLine(quota), changedLine(quota, ui)].filter(Boolean).join(' · '),
    fields,
    error: view.quotaError || '',
    status: view.quotaStatus || '',
    actions: [{ label: view.quotaBusy ? t('polSaving') : t('polQuotaSave'), a: 'quota-save', kind: 'primary', disabled: view.quotaBusy || locked }],
  });
}

/* ---- the page ------------------------------------------------------------------------------------------------ */

function groupBlock(group, doc, drafts, ui) {
  const rows = doc.policies.filter((policy) => policy.group === group);
  if (!rows.length) return '';
  return formBlock({
    col: GROUP_COLUMN[group] || '',
    title: t(`polGroup_${group}`),
    sub: t(`polGroupSub_${group}`),
    fields: rows.map((policy) => fieldOf(policy, drafts[policy.key], ui)),
  });
}

export function policiesPage({ doc, quota, quotaDraft, drafts, view = {}, ui = 'en', href, failed = false }) {
  const back = { href: href('adminOperations'), label: t('navOperations') };
  const label = 'data-screen-label="Policies & limits"';
  if (failed) return html`<section class="a-page" ${raw(label)}>${pageHead({ back, title: t('polTitle') })}${block({ body: t('opUnavailable') })}</section>`;
  if (!doc) return html`<section class="a-page" ${raw(label)}>${pageHead({ back, title: t('polTitle'), sub: t('polSub') })}${skeleton(t('loading'))}</section>`;
  const sub = doc.source === 'stored' && doc.updated_at ? changedLine(doc, ui) : t('polDefaultDoc');
  const stateBanner = doc.state === 'stale' || doc.state === 'unreadable'
    ? banner({ tone: 'warn', title: t('polStateTitle'), text: t(doc.state === 'stale' ? 'polStateStale' : 'polStateUnreadable') }) : '';
  return html`<section class="a-page" ${raw(label)}>
    ${pageHead({ back, title: t('polTitle'), sub: [t('polSub'), sub].join(' ') , actions: [{ label: view.busy ? t('polSaving') : t('polSave'), a: 'policies-save', kind: 'primary', disabled: Boolean(view.busy) }, { label: t('polReload'), a: 'reload' }] })}
    ${stateBanner}
    <div class="a-blocks">
      ${quotaBlock({ quota, quotaDraft, ...view }, ui)}
      ${GROUP_ORDER.map((group) => groupBlock(group, doc, drafts, ui))}
      ${formBlock({ span: true, fields: [], error: view.error || '', status: view.status || '', actions: [{ label: view.busy ? t('polSaving') : t('polSave'), a: 'policies-save', kind: 'primary', disabled: Boolean(view.busy) }] })}
    </div>
  </section>`;
}

export async function mountPolicies(shell, ctx) {
  const host = createHost(shell, ctx);
  const view = { doc: null, quota: null, quotaDraft: null, drafts: {}, busy: false, error: '', status: '', quotaBusy: false, quotaError: '', quotaStatus: '', failed: false };
  const ui = () => languages().ui;
  host.setBuilder(() => ({
    title: t('polTitle'),
    markup: policiesPage({ doc: view.doc, quota: view.quota, quotaDraft: view.quotaDraft, drafts: view.drafts, view, ui: ui(), href: ctx.href, failed: view.failed }),
  }));

  async function load() {
    view.failed = false;
    try {
      const [doc, quota] = await Promise.all([adminApi.policies(), adminApi.quota().catch(() => null)]);
      if (!host.alive()) return;
      view.doc = doc;
      view.drafts = draftsOf(doc);
      view.quota = quota;
      view.quotaDraft = quota ? quotaDraftOf(quota) : null;
      view.error = '';
      view.status = '';
    } catch {
      view.failed = true;
    }
    host.paint();
  }

  host.on('go', (control, dataset) => { if (dataset.to) ctx.go(dataset.to); });
  host.on('reload', async () => { view.doc = null; view.status = ''; view.error = ''; host.paint(); await load(); });

  host.on('toggle', (control, dataset) => {
    const [kind, key, meter] = String(dataset.field || '').split('|');
    if (kind === 'quota' && view.quotaDraft) {
      if (key === 'enabled') view.quotaDraft.enabled = !view.quotaDraft.enabled;
      else if (key === 'meter' && meter in view.quotaDraft.meters) view.quotaDraft.meters[meter] = !view.quotaDraft.meters[meter];
      view.quotaStatus = '';
      view.quotaError = '';
    } else if (kind === 'pol' && key in view.drafts) {
      view.drafts[key] = !view.drafts[key];
      view.status = '';
      view.error = '';
    }
    host.paint();
  });
  host.onInput((name, value) => {
    const [kind, key] = String(name).split('|');
    if (kind !== 'pol' || !(key in view.drafts)) return;
    view.drafts[key] = value; // the box keeps its own text; nothing repaints under the operator's cursor
    view.status = '';
  });

  host.on('quota-save', async () => {
    if (view.quotaBusy || !view.quota) return;
    view.quotaBusy = true;
    view.quotaError = '';
    view.quotaStatus = '';
    host.paint();
    try {
      view.quota = await adminApi.saveQuota(quotaPayload(view.quota, view.quotaDraft));
      view.quotaDraft = quotaDraftOf(view.quota);
      view.quotaStatus = t('polSaved');
    } catch (failure) {
      view.quotaError = failure?.message || t('polSaveFailed');
    }
    view.quotaBusy = false;
    host.paint();
  });

  host.on('policies-save', async () => {
    if (view.busy || !view.doc) return;
    const change = changeOf(view.doc, view.drafts);
    if (!change.changed.length) { view.status = t('polNothing'); view.error = ''; host.paint(); return; }
    const confirmations = confirmationsOf(change);
    const confirm = {};
    if (confirmations.length) {
      const deletes = confirmations.some(({ policy }) => policy.danger === 'delete');
      const charging = confirmations.some(({ policy }) => policy.danger === 'charging');
      const answer = await host.confirm({
        title: t('polConfirmTitle'),
        body: t(deletes ? 'polConfirmBodyDelete' : charging ? 'polConfirmBodyCharging' : 'polConfirmBodySpend'),
        list: confirmations.map(({ policy, from, to }) => t('polConfirmLine', { name: policyLabel(policy), from: valueLabel(policy, from, ui()), to: valueLabel(policy, to, ui()) })),
        cancel: t('actCancel'),
        confirm: t('polConfirmYes'),
        danger: deletes,
      });
      if (!answer.confirmed) return;
      for (const { policy } of confirmations) confirm[policy.key] = true;
    }
    view.busy = true;
    view.error = '';
    view.status = '';
    host.paint();
    try {
      const body = { set: change.set, reset: change.reset, expected_updated_at: view.doc.updated_at || null };
      if (confirmations.length) body.confirm = confirm;
      view.doc = await adminApi.savePolicies(body);
      view.drafts = draftsOf(view.doc);
      view.status = t('polSaved');
    } catch (failure) {
      view.error = failure?.message || t('polSaveFailed');
    }
    view.busy = false;
    host.paint();
  });

  host.paint();
  await load();
  return () => host.cleanup();
}
