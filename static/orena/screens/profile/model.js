/* Profile (D-091, frames 24-25): pure data mapping, no DOM. Kept separate from screen.js so
   scripts/test_orena_screen_profile.mjs can hold this logic to rule 40 without a browser.

   What is real and what is not (D8/E1 inventory, confirmed against the running backend):
   - due, savedCount, rank/rankName/mastered come from GET /api/library/vocabulary/summary
     (writing_coach/becoming_library.py library_summary(): one aggregate query, the same answer
     Progress reads, via product/rank.js's rankSummary - never recomputed here).
   - plan name comes from GET /api/product/commerce (writing_coach/product/service.py
     account_state(): a real plan record, never a mock).
   - name/initial/picture/level/isAdmin/profile.goal come from the shell context (already read
     once at boot from /api/me and /api/learner-profile).
   - the streak and the week's active days are REAL (D4 I14, D-104 H-5): GET /api/learner-activity
     derives them from server records (essays, speaking attempts, Reading attempts), with no table.
     A page visit never counts.
   - "a real metric or no metric" (D-103.4): minutes studied and a daily-goal ring have no measure
     anywhere in this codebase (nothing records duration), so they are not drawn at all - not drawn
     as 0. The weekly-goal bar is drawn only against the target the learner has set
     (`users.weekly_goal_days`); with none set there is nothing to measure against. */
import { rankSummary } from '../../product/rank.js';

// The design's own segment count, kept for the record: the bar is drawn against the learner's target now.
export const WEEKLY_GOAL_TARGET = 5;

const GOAL_KEYS = Object.freeze({
  everyday: 'goalEveryday',
  work: 'goalWork',
  exam: 'goalExam',
  voice: 'goalVoice',
});

/* account_profile.py's four goal categories -> this screen's copy key. An unset or unknown value
   (never a stored free-text sentence - the design's "Speak comfortably..." line is sample content,
   D-068) reads as "not set" rather than as the raw stored key. */
export function goalCopyKey(goal) {
  return GOAL_KEYS[String(goal || '').trim()] || 'goalNotSet';
}

/* "M,T,W,T,F,S,S" -> ['M','T','W','T','F','S','S']: one locale string in copy.js becomes the
   7-cell strip, so each language supplies its own short weekday forms (rule: per-locale, not one
   Latin-letter set for every language). */
export function weekdayAbbrevs(source) {
  return String(source || '')
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
}

/* Everything the view needs, already resolved from the shell context and this screen's two extra
   reads. Every field a caller cannot honestly fill is 0, false or omitted - never guessed. */
export function buildProfileModel({ context, vocabulary, commerce } = {}) {
  const rank = rankSummary(vocabulary);
  const rankKnown = rank.known && rank.rank > 0;
  const planKnown = Boolean(commerce && commerce.available && commerce.plan);
  const plan = planKnown ? commerce.plan : null;
  const level = String(context?.level || '').trim();
  const due = Math.max(0, Number(context?.due) || 0);

  return {
    name: String(context?.name || ''),
    initial: String(context?.initial || ''),
    picture: String(context?.picture || ''),
    level,
    hasLevel: Boolean(level),
    rankKnown,
    rankName: rankKnown ? rank.rankName : '',
    rankNumber: rankKnown ? rank.rank : 0,
    planKnown,
    planName: planKnown ? String(plan.name || '') : '',
    planId: planKnown ? String(plan.id || '') : '',
    goalKey: goalCopyKey(context?.profile?.goal),
    due,
    savedCount: Math.max(0, Number(rank.saved) || 0),
    // Derived from server records (learner_activity.py); absent activity is 0 days, which is what it is.
    dayStreak: Math.max(0, Number(context?.activity?.streak?.days) || 0),
    weekDays: Array.isArray(context?.activity?.week?.days) ? context.activity.week.days.map((day) => Boolean(day?.active)) : [],
    // The learner's own target only; the design's five segments are a drawing, not a goal.
    weeklyGoalTarget: Math.max(0, Number(context?.activity?.week?.goal_days) || 0),
    weeklyGoalDone: Math.max(0, Number(context?.activity?.week?.done_days) || 0),
    isAdmin: Boolean(context?.isAdmin),
  };
}

/* The design's `profileActions` list (frame 25), in the source's own order: Platform admin only
   when the learner is one, then Settings / History / Progress / Plan & usage / Privacy / Feedback / Sign out (the 2026-10-09 export; Plan & usage and Feedback are their own routes). `kind`
   tells the view how to wire the row: 'nav' is an in-app route (rendered with data-go, which the
   shell router's own document-wide click listener already handles - no per-row listener needed;
   Platform admin is one, D-101 E: it opens the Admin inside this UI), 'signout' needs the screen's
   own handler. The row exists only for an admin - for anyone else it is absent, not disabled. */
export function profileActions({ isAdmin = false } = {}) {
  const actions = [];
  if (isAdmin) actions.push({ id: 'admin', kind: 'nav' });
  actions.push({ id: 'settings', kind: 'nav' });
  actions.push({ id: 'history', kind: 'nav' });
  actions.push({ id: 'progress', kind: 'nav' });
  actions.push({ id: 'plan', kind: 'nav' });
  actions.push({ id: 'privacy', kind: 'nav' });
  actions.push({ id: 'feedback', kind: 'nav' });
  actions.push({ id: 'signout', kind: 'signout' });
  return actions;
}
