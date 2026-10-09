/* A room's answer to the server's plan-limit refusal (HTTP 429 `quota_exhausted`, D-161). The design draws
   no in-room exhausted state (docs/project/UI_BACKEND_GAPS.md, "Plan limits: the in-room exhausted
   message"); the room shows this sentence in the place it already shows a failed request, with the plan's
   "See all plans" link. Every figure is the server's own (`context.used`, `context.limit`), in the
   interface language; nothing is invented when the server sends none.

   A figure is shown in the unit a learner reads, exactly as Plan & usage shows it (`displayAmount`): the server
   stores pronunciation in seconds (`context.scale` 60) and the sentence says minutes, whole when whole and with
   one decimal otherwise ("1.1 of 5 pronunciation minutes"). */
import { languages } from '../../copy/index.js';
import { toast } from '../../kit/toast.js';
import { t } from './copy.js';
import { displayAmount, formatNumber } from './model.js';

export function isQuotaExhausted(error) {
  return Boolean(error) && error.status === 429 && error.category === 'quota_exhausted';
}

export function quotaMessage(error) {
  const context = error?.context || {};
  const key = `exhausted_${String(context.feature || '').replace(/\./g, '_')}`;
  const scale = Number(context.scale) > 0 ? Number(context.scale) : 1;
  if (t.has(key) && context.used != null && context.limit != null) {
    const figure = (value) => formatNumber(displayAmount(value, scale), languages().ui);
    return t(key, { used: figure(context.used), limit: figure(context.limit) });
  }
  return t('exhausted_generic');
}

export function seePlansLabel() {
  return t('seePlans');
}

/* The refusal as the learning rooms that have no failed-request place of their own show it: the sentence, with
   the way to the plans as the toast's action (the Respond room's pattern). */
export function showQuotaNotice(ctx, error) {
  toast(quotaMessage(error), { undo: () => ctx.go(ctx.href('pricing')), undoLabel: seePlansLabel() });
}
