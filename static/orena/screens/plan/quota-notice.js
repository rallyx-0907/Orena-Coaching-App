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

/* Taking a learning language the account does not hold yet, when the plan's count is reached (HTTP 403
   `language_limit_reached`, or `feature_not_in_plan` for `languages.target`, D-16R). The server judges it; the client
   only says it, in the interface language, from the server's own figures (`context.limit`, `context.owned`), with the
   way to the plans. Nothing was changed on the server, and a language the account already learns stays switchable. */
export function isLanguageLimit(error) {
  if (!error || error.status !== 403) return false;
  if (error.category === 'language_limit_reached') return true;
  return error.category === 'feature_not_in_plan' && error.context?.feature === 'languages.target';
}

export function languageLimitMessage(error) {
  const context = error?.context || {};
  const limit = Number(context.limit);
  const owned = Number(context.owned);
  if (error?.category === 'language_limit_reached' && Number.isFinite(limit) && Number.isFinite(owned)) {
    const ui = languages().ui;
    return t.plural('languageLimit', limit, { limit: formatNumber(limit, ui), owned: formatNumber(owned, ui) });
  }
  return t('languageNotInPlan');
}

export function showLanguageLimitNotice(ctx, error) {
  toast(languageLimitMessage(error), { undo: () => ctx.go(ctx.href('pricing')), undoLabel: seePlansLabel() });
}

/* A take the server already processed (its answer was lost on the way back): it cannot be assessed again under the
   same request, so the room says so and the learner records again. Said as a toast - the design draws no state for
   it (docs/project/UI_BACKEND_GAPS.md QTA-15). */
export function showRecordAgainNotice() {
  toast(t('recordAgain'));
}

/* What a Speaking room does with a take failure of the plan's making: `quota` (the allowance is used up) or
   `already_assessed` (record again). False for every other failure, which the room handles as before. */
export function showAssessmentRefusal(ctx, failure) {
  if (failure?.kind === 'quota') showQuotaNotice(ctx, failure.error);
  else if (failure?.kind === 'already_assessed') showRecordAgainNotice();
  else return false;
  return true;
}
