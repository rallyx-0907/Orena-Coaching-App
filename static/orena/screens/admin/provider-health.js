/* Provider health on the Admin pages (PR BZ), from GET /api/admin/ai/health. Pure: each builder takes the report,
   the copy function and how to name things, and returns plain data for the existing blocks - the design's banner
   (`BN`, the Overview's ovBanner and A2's failing-provider banner), its status pills and its row lists. The design draws
   no provider-health indicator of its own; this puts the data into those drawn elements (UI_BACKEND_GAPS.md,
   "Admin: provider health"). Nothing here is invented copy: every word is `ph*` in copy-health.js. */
import { num, relative } from '../../capabilities/admin-format.js';

const CLASSES = new Set(['spend_cap', 'rate_limit', 'auth', 'unconfigured', 'server', 'timeout', 'schema', 'other',
  'privacy', 'budget', 'unfunded']);

/* A failure class in plain words. */
export function reasonText(t, reason) {
  return t(`phReason_${CLASSES.has(reason) ? reason : 'other'}`);
}

export function downOf(health, providerId) {
  return (health?.down || []).find((row) => row.provider === providerId) || null;
}

export function providerHealthOf(health, providerId) {
  return (health?.providers || []).find((row) => row.provider === providerId) || null;
}

/* The capability's own entry under the provider that serves it (its primary), or null. */
export function capabilityHealthOf(health, providerId, key) {
  return providerHealthOf(health, providerId)?.capabilities?.find((row) => row.capability === key) || null;
}

/* The status pill of a provider that is down, in place of its configured/tested status; null when it is not down. */
export function downPill(t, health, providerId) {
  const down = downOf(health, providerId);
  if (!down) return null;
  return { label: t('phFailingPill', { reason: reasonText(t, down.reason) }), tone: down.severity === 'high' ? 'err' : 'warn' };
}

/* "Last error 4 min ago · 6 in 10 min", for an entry (provider or capability) that failed in the window. */
export function lastErrorPill(t, health, entry, { ui, now }) {
  if (!entry || !entry.failed || !entry.last_error_at) return null;
  return { label: t('phLastError', { when: relative(entry.last_error_at, ui, now), n: num(entry.failed, ui), minutes: num(health?.window_minutes || 10, ui) }), tone: 'mute' };
}

/* A provider's display name from the report itself (`provider_names`), else the page's own list, else its id. */
export function namedBy(health, providerName = null) {
  return (id) => {
    const named = providerName ? providerName(id) : '';
    if (named && named !== id) return named;
    const own = health?.provider_names?.[id];
    return typeof own === 'string' && own ? own : (named || id || '');
  };
}

/* One banner per provider that is down: who, why, since when, which capabilities run on a working backup (named),
   which got no answer, and which have no working route because their backup is down too. */
export function downBanners(t, health, { ui, now, href, providerName = null, capabilityName = (key) => key }) {
  const name = namedBy(health, providerName);
  return (health?.down || []).map((row) => {
    const parts = [];
    const withBackup = (key) => (row.backups?.[key] ? `${capabilityName(key)} (${name(row.backups[key])})` : capabilityName(key));
    if (row.since) parts.push(t('phDownSince', { when: relative(row.since, ui, now) }));
    if (row.on_backup?.length) parts.push(t('phOnBackup', { list: row.on_backup.map(withBackup).join(', ') }));
    if (row.backup_down?.length) parts.push(t('phNoRoute', { list: row.backup_down.map(withBackup).join(', ') }));
    if (row.without_backup?.length) parts.push(t('phNoBackup', { list: row.without_backup.map(capabilityName).join(', ') }));
    if (!row.on_backup?.length && !row.without_backup?.length && !row.backup_down?.length) parts.push(t('phNoCapability'));
    return {
      tone: row.severity === 'high' ? 'err' : 'warn',
      title: t('phDownTitle', { provider: name(row.provider), reason: reasonText(t, row.reason) }),
      text: parts.join(' '),
      actions: href ? [{ label: t('openProvider'), size: 'sm', a: 'go', data: { to: href('adminProvider', { id: row.provider }) } }] : [],
    };
  });
}

/* The switch history as rows: when, which capability, from -> to, why. */
export function switchRows(t, health, { ui, now, href, providerName: own = null, capabilityName = (key) => key }) {
  const providerName = namedBy(health, own);
  return (health?.switches || []).map((row) => ({
    title: capabilityName(row.capability),
    meta: [
      relative(row.at, ui, now),
      t('phSwitchMeta', { from: providerName(row.from), to: row.to ? providerName(row.to) : t('phSwitchNobody'), reason: reasonText(t, row.reason) }),
    ].join(' · '),
    pills: [{ label: t(`phTrigger_${['down', 'failed', 'refused'].includes(row.trigger) ? row.trigger : 'failed'}`), tone: row.answered ? 'warn' : 'err' }],
    go: href && row.from ? href('adminProvider', { id: row.from }) : '',
  }));
}
