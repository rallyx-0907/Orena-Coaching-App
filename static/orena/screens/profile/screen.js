/* Profile (D-091, frames 24-25 "Profile" / "Profile · Today's progress"): the learner's own
   destination - today's compact progress, who they are, and the actions list (Settings, History,
   Progress, Plan & privacy, Platform admin when they are one, Sign out). Not a focus route: it
   scrolls like any other browsing place (routes.js `focus:false`).

   Real data only (rule 40): due, savedCount and the rank name/number come from
   /api/library/vocabulary/summary (the same read Progress and the rail already use); the plan
   name from /api/product/commerce; name/initial/picture/level/goal/isAdmin from the shell context
   already loaded at boot. Day streak, this-week minutes and the weekly-goal count have no backend
   measure anywhere in this codebase and render 0, never a sample figure (model.js explains why).
   The Achievements block the frame draws (four badges: "First article", "10 videos", "Speak 7
   days · 4/7", "C1 writer") is not built at all - none of it is real, and there is no achievement
   catalogue to read even a zero from (learner_summary.py's own achievements object is
   `{status:'unavailable', reason:'no_approved_policy'}`) - recorded as a backend gap, not
   invented (docs/project/UI_BACKEND_GAPS.md N-25).

   One frame element is dropped, confirmed against the live design's own script
   (orena-script.js `sessVals()`), not just the truncated static export: the hero's middle
   "Counted from this session · Ns" line (`pf.sessLabel`) is a live client-side stopwatch since the
   prototype loaded - exactly the "simulated/fake timer" category the brief says is not behaviour
   to copy, not a backend measure. The "This week" tile's own `weekDelta` ("+N min vs last week")
   is dropped for the identical reason - a comparison between two unmeasured numbers is not a real
   signal.

   The 4th hero tile, "Daily goal" (a 60x60 ring around a 46px disc + a label/value pair, E1 frame
   25 §2.1), IS built, at its honest rule-40 zero: `kit/components.js`'s `progressRing()` primitive
   names this exact tile in its own header comment, and the sibling Today screen hits the identical
   "no cross-activity daily-goal backend" gap (N-21) and still draws its ring permanently at 0%
   with an honest "not tracked yet" caption rather than omitting it - rule 40's own text is "renders
   0 in its canonical component", not "omit the component". Kept here the same way: the ring always
   reads 0% (no per-day study-time aggregate exists to fill it, and the design's own "15 minutes"
   goal is a constant living only inside the prototype's fake stopwatch function, with no standing
   as a real setting anywhere - unlike WEEKLY_GOAL_TARGET below, which is the segment *count* the
   weekly-goal bar always draws, not a claimed measurement), so the value line reads the same
   honest "not tracked yet" text Today already uses for its own goal ring, rather than fabricating
   a "0 / 15 min" figure against a target that does not really exist (N-25). */
import { html, mount, raw, cls } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { listRow } from '../../kit/components.js';
import { useStyles } from '../../kit/styles.js';
import { api } from '../../infrastructure/api.js';
import { shellCopy } from '../../copy/shell.js';
import { t } from './copy.js';
import { buildProfileModel, profileActions, weekdayAbbrevs, WEEKLY_GOAL_TARGET } from './model.js';

function avatarMarkup(model) {
  if (model.picture) return html`<span class="s-profile-avatar o-avatar"><img src="${model.picture}" alt=""></span>`;
  return html`<span class="s-profile-avatar o-avatar" aria-hidden="true">${model.initial}</span>`;
}

/* due === 0 has its own key with no placeholder (heroHeadlineNone); due >= 1 always fills a real,
   non-zero {n} - see copy.js's header for why that split matters (t()'s shared fill() drops a
   placeholder whose value is exactly 0, so this screen never asks it to fill one). */
function heroHeadline(due) {
  if (due === 0) return t('heroHeadlineNone');
  return t(due === 1 ? 'heroHeadlineDueOne' : 'heroHeadlineDueMany', { n: due });
}

/* The design's own due-tile value is "{n} items · ~{n/2} min" (or "All caught up" at 0) - the
   "~1 min per item" half is the prototype's own made-up ratio, not a real per-item duration
   anywhere in this codebase, so it is dropped (rule 40); the item count and the "All caught up"
   zero-state are real and kept. */
function dueTileValue(due) {
  if (due === 0) return t('dueValueNone');
  return t(due === 1 ? 'dueValueOne' : 'dueValueMany', { n: due });
}

/* model.dayStreak/model.weekMinutes are always 0 today (rule 40 - no backend measure), but this
   reads the model field rather than a frozen "0 days"/"0 min" literal, the same *None/*One/*Many
   pattern dueTileValue() already uses - so the day either measure gains a real backend source, the
   hero tile updates itself instead of silently keeping stale zero text (the gap the review found:
   the stats card two rows down already reads model.dayStreak directly). */
function streakDaysTileValue(dayStreak) {
  if (dayStreak === 0) return t('streakDaysValueNone');
  return t(dayStreak === 1 ? 'streakDaysValueOne' : 'streakDaysValueMany', { n: dayStreak });
}
function heroMarkup(model, ctx) {
  return html`<div class="s-profile-hero">
    <div class="s-profile-hero__top">
      <div>
        <div class="s-profile-hero__eyebrow">${t('heroEyebrow')}</div>
        <div class="s-profile-hero__headline">${heroHeadline(model.due)}</div>
      </div>
      <button type="button" class="o-btn o-btn--primary s-profile-hero__cta" data-go="${ctx.href('progress')}">
        ${t('ctaOpenProgress')}${raw(icon('arrow-right', { size: 16 }))}
      </button>
    </div>
    <div class="s-profile-hero__grid">
      <div class="s-profile-tile s-profile-streak">
        <div class="s-profile-tile__head">
          <span class="s-profile-tile__label">${t('streakLabel')}</span>
          <span class="s-profile-tile__value">${streakDaysTileValue(model.dayStreak)}</span>
        </div>
        <div class="s-profile-streak__days">${weekdayAbbrevs(t('weekdays')).map((day, index) => html`<span class="${cls('s-profile-day', model.weekDays[index] && 's-profile-day--done')}">${day}</span>`)}</div>
      </div>
      <button type="button" class="s-profile-tile" data-go="${ctx.href('review')}">
        <span class="s-profile-tile__label">${t('dueLabel')}</span>
        <span class="s-profile-tile__value">${dueTileValue(model.due)}</span>
        <span class="s-profile-tile__cta">${t('startReview')}${raw(icon('arrow-right', { size: 14 }))}</span>
      </button>
    </div>
  </div>`;
}

function identityMarkup(model) {
  const metaParts = [];
  if (model.rankKnown) metaParts.push(`${model.rankName} · ${t('rankLevelLabel', { n: model.rankNumber })}`);
  if (model.planKnown) metaParts.push(model.planName);
  const meta = metaParts.join(' · ');
  const bars = Array.from({ length: model.weeklyGoalTarget }, (_, index) => html`<span class="${cls('s-profile-weekly__bar', index < model.weeklyGoalDone && 's-profile-weekly__bar--filled')}"></span>`);
  return html`<div class="s-profile-identity">
    <div class="s-profile-identity__top">
      <span class="s-profile-avatar-ring">
        ${avatarMarkup(model)}
        ${model.hasLevel ? html`<span class="s-profile-badge">${model.level}</span>` : ''}
      </span>
      <div>
        <h1 class="s-profile-name">${model.name}</h1>
        ${meta ? html`<div class="s-profile-meta">${meta}</div>` : ''}
        <div class="s-profile-goal">${t('goalPrefix')} · <b>${t(model.goalKey)}</b></div>
      </div>
    </div>
    ${model.weeklyGoalTarget > 0 ? html`<div class="s-profile-weekly">
      <div class="s-profile-weekly__head">
        <strong>${t('weeklyGoalTitle', { n: model.weeklyGoalTarget })}</strong>
        <span>${Math.min(model.weeklyGoalDone, model.weeklyGoalTarget)} / ${model.weeklyGoalTarget}</span>
      </div>
      <div class="s-profile-weekly__bars">${bars}</div>
    </div>` : ''}
  </div>`;
}

function statsMarkup(model) {
  return html`<div class="s-profile-stats">
    <div class="s-profile-stats__grid">
      <div class="s-profile-stat">
        <span class="s-profile-stat__icon" style="color:var(--skill-read)">${raw(icon('flame', { size: 20 }))}</span>
        <span class="s-profile-stat__value">${model.dayStreak}</span>
        <span class="s-profile-stat__label">${t('dayStreakStatLabel')}</span>
      </div>
      <div class="s-profile-stat">
        <span class="s-profile-stat__icon" style="color:var(--skill-vocab)">${raw(icon('case-lower', { size: 20 }))}</span>
        <span class="s-profile-stat__value">${model.savedCount}</span>
        <span class="s-profile-stat__label">${t('savedItemsStatLabel')}</span>
      </div>
    </div>
  </div>`;
}

const ACTION_LABEL = (id) => ({
  admin: t('actionAdmin'),
  settings: shellCopy('settings'),
  history: t('actionHistory'),
  progress: shellCopy('progress'),
  plan: t('actionPlanPrivacy'),
  signout: t('actionSignOut'),
}[id]);

/* The design's own fixed sub-label per row (orena-script.js `profileActions`, read live - the
   static export truncated before reaching this list). Four are plain fixed copy describing what
   the destination holds, not learner data. "Plan & privacy" is the one row whose sub is part real
   (the plan name, already resolved in model.js) and part the same fixed description - shown
   without the plan segment when the plan read has not resolved, never a placeholder plan name. */
function actionSub(action) {
  if (action.id === 'plan') {
    return action.sub ? t('actionPlanSubKnown', { plan: action.sub }) : t('actionPlanSubUnknown');
  }
  return {
    admin: t('actionAdminSub'),
    settings: t('actionSettingsSub'),
    history: t('actionHistorySub'),
    progress: t('actionProgressSub'),
  }[action.id] || '';
}

function actionHref(id, ctx) {
  return {
    admin: ctx.href('adminAi'),
    settings: ctx.href('settings'),
    history: ctx.href('progress', {}, { tab: 'history' }),
    progress: ctx.href('progress'),
    plan: ctx.href('settings', {}, { tab: 'plan' }),
  }[id];
}

/* The frame's own action row (25-Profile-Today-s-progress.html): the sub sits inline after the
   label at a 16px title, not stacked underneath at listRow's own 15px default - kit/
   components.js#listRow's `inlineSub`/`titleSize` options exist for exactly this shape (D-091 kit
   fidelity pass). Confirmed live: no hover background change is drawn for this row either (only
   the "Due review" hero tile has its own `style-hover`), so this now correctly falls through to
   `.c-row--outline`'s own hover, not an invented `--surface2` swap. */
function actionRow(action, ctx) {
  const label = ACTION_LABEL(action.id);
  const sub = actionSub(action);
  const common = { variant: 'outline', radius: 16, pad: '18px 20px', titleSize: 16, inlineSub: true, title: label, sub, chevron: true };
  if (action.kind === 'signout') return listRow({ ...common, dataset: { action: 'signout' } });
  return listRow({ ...common, dataset: { go: actionHref(action.id, ctx) } });
}

async function signOut() {
  try {
    await api.logout();
  } catch (error) {
    console.error('[Orena] sign out failed', error);
  } finally {
    location.href = '/login';
  }
}

export default async function profile(element, ctx) {
  await useStyles('screens/profile/profile.css');
  const context = ctx.context;
  const [vocabulary, commerce] = await Promise.all([
    api.libraryVocabularySummary().catch(() => null),
    api.productCommerce().catch(() => null),
  ]);
  if (!ctx.isCurrent()) return undefined;

  const model = buildProfileModel({ context, vocabulary, commerce });
  const actions = profileActions({ isAdmin: model.isAdmin, planName: model.planName });

  mount(
    element,
    html`<div class="s-profile">
      ${heroMarkup(model, ctx)}
      <div class="s-profile-columns">
        ${identityMarkup(model)}
        ${statsMarkup(model)}
      </div>
      <div class="s-profile-actions">${actions.map((action) => actionRow(action, ctx))}</div>
    </div>`,
  );

  element.querySelector('[data-action="signout"]')?.addEventListener('click', signOut);
  return undefined;
}

// Exported for the node gate (scripts/test_orena_screen_profile.mjs). kit/html.js's `html`/`icon`
// are plain string templating with no DOM dependency, so these render to real markup in Node -
// the gate checks the rendered text/HTML directly, not a stubbed DOM, for what model.js's own
// pure-logic coverage cannot reach: the due-tile phrase, the action rows' fixed sub-labels, the
// rule-40 zero fallback in the rendered text, the weekly-goal bar count, the weekday strip length.
export const __internal = {
  avatarMarkup, heroMarkup, identityMarkup, statsMarkup, actionRow, dueTileValue, actionSub, WEEKLY_GOAL_TARGET,
  streakDaysTileValue, actionHref,
};
