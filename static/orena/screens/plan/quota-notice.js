/* A room's answer to the server's plan-limit refusal (HTTP 429 `quota_exhausted`, D-160). The design draws
   no in-room exhausted state (docs/project/UI_BACKEND_GAPS.md, "Plan limits: the in-room exhausted
   message"); the room shows this sentence in the place it already shows a failed request, with the plan's
   "See all plans" link. Every figure is the server's own (`context.used`, `context.limit`), in the
   interface language; nothing is invented when the server sends none. */
import { t } from './copy.js';

export function isQuotaExhausted(error) {
  return Boolean(error) && error.status === 429 && error.category === 'quota_exhausted';
}

export function quotaMessage(error) {
  const context = error?.context || {};
  const key = `exhausted_${String(context.feature || '').replace(/\./g, '_')}`;
  const scale = Number(context.scale) > 0 ? Number(context.scale) : 1;
  if (t.has(key) && context.used != null && context.limit != null) {
    return t(key, { used: String(Math.round(Number(context.used) / scale)), limit: String(Math.round(Number(context.limit) / scale)) });
  }
  return t('exhausted_generic');
}

export function seePlansLabel() {
  return t('seePlans');
}
