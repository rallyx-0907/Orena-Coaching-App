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
import { aiPauseOf, recentAiPause } from '../../infrastructure/ai-paused.js';
import { t } from './copy.js';
import { displayAmount, formatNumber } from './model.js';
import { holdLanguageRefusal, REASON_LANGUAGE } from './reason.js';

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

/* The line for the day's voice minutes running out inside a chunk (`day_limit_reached`, D-237): no 429 carries the figure, so
   `n` is the plan's own `orena.voice` limit and scale from the commerce read (GET /api/product/commerce). Without it the
   generic line is used, never a made-up number. */
export function voiceDayLimitMessage(commerce) {
  const item = commerce?.features?.['orena.voice'];
  const limit = item?.limit ?? item?.monthly_limit;
  if (limit == null) return quotaMessage(null);
  return quotaMessage({ context: { feature: 'orena.voice', used: limit, limit, scale: item.scale } });
}

/* At the daily voice-minute cap (429 `quota_exhausted`, feature `orena.voice`, D-237) a paying learner is told the line and
   nothing more: text chat is unchanged and an upsell would only stand in the way. The way to the plans is offered only when
   the server says a higher plan holds more (`context.options` lists `upgrade`). Every other meter keeps its link. */
export function quotaOffersPlans(error) {
  const context = error?.context || {};
  if (context.feature !== 'orena.voice') return true;
  return Array.isArray(context.options) && context.options.includes('upgrade');
}

/* HTTP 429 `daily_ai_limit` (contract v10, D-232): Orena's AI is paused for everyone until `resets_at`. Not the learner's
   plan: told once in one line, in the interface language, with `resets_at` in the learner's local time (the server's
   `message` is an English fallback and is never shown); never waited out or resent, no way to the plans. */
export function isDailyAiLimit(error) {
  return Boolean(error) && error.status === 429 && error.category === 'daily_ai_limit';
}

export function pausedMessage(resetsAt) {
  const at = new Date(resetsAt);
  if (!resetsAt || Number.isNaN(at.getTime())) return t('aiPausedNoTime'); // no time to promise
  return t('aiPaused', { time: new Intl.DateTimeFormat(languages().ui, { hour: 'numeric', minute: '2-digit' }).format(at) });
}

/* The same pause as any response carries it (header `X-Orena-AI-Paused`, contract v11, D-235): the surface that made the call
   shows this line in the place it already shows a failed request - no retry (it would be refused again), no way to the plans
   (it is not the learner's plan). `pausedLineOf(error)` reads a refused request; `pausedLineNow(route)` serves a call the server
   answered 200 with part of it unavailable (Listening's meaning), which has no error to read. '' when there is no pause,
   so a surface falls through to its own failed-request text. */
export function isAiPaused(error) {
  return Boolean(aiPauseOf(error));
}

export function pausedLineOf(error) {
  const pause = aiPauseOf(error);
  return pause ? pausedMessage(pause.resetsAt) : '';
}

export function pausedLineNow(routes) {
  const pause = recentAiPause(routes);
  return pause ? pausedMessage(pause.resetsAt) : '';
}

/* Voice chat is a Plus and Pro benefit (contract v11, D-235): `voice/session` and `voice/extend` answer a Free learner 403
   `feature_not_in_plan` with `context.feature` `orena.voice`. Told as the voice upsell sheet (plan/voice-upsell.js), never as a failure. */
export function isVoiceNotInPlan(error) {
  return Boolean(error) && error.status === 403 && error.category === 'feature_not_in_plan' && error.context?.feature === 'orena.voice';
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
   `language_limit_reached`, or `feature_not_in_plan` for `languages.target`, D-170). The server judges it; the client
   only says it. A toast was too small and gone too soon to explain it, so the refusal opens Plans at once
   (`?reason=language`, D-171) with the explanation on top: the plan's limit and the languages the learner holds, from the
   server's own `context`, the language they tried to add (`requested`) and the plan that allows it (plan/pricing.js).
   Nothing was changed on the server; Back returns to the language the learner is on, which stays switchable. */
export function isLanguageLimit(error) {
  if (!error || error.status !== 403) return false;
  if (error.category === 'language_limit_reached') return true;
  return error.category === 'feature_not_in_plan' && error.context?.feature === 'languages.target';
}

export function showLanguageLimitNotice(ctx, error, requested = '') {
  holdLanguageRefusal(error, requested);
  ctx.go(ctx.href('pricing', {}, { reason: REASON_LANGUAGE }));
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
