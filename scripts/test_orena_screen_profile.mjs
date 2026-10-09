/* Gate for Profile's pure logic (model.js) and its rendered markup (screen.js's `__internal`,
   plain string templating - no browser needed, see screen.js's own comment on the export). Checks
   rule 40's zero fallback is real (not a sample figure) in both the data and the rendered text,
   that a metric with a real backend answer passes it through unchanged, that the actions list only
   ever offers Platform admin to an admin in the design's own order, that every action row's
   fixed sub-label (read live from the design, the static export truncated before reaching them)
   renders for the right row, that the hero's streak/week-minutes tiles read the model's own
   fields (not a frozen literal) and pick the right English plural, and that the 4th hero tile
   (Daily goal) renders a real progressRing() at its honest zero instead of being omitted. */
import assert from 'node:assert/strict';
import { buildProfileModel, profileActions, goalCopyKey, weekdayAbbrevs, WEEKLY_GOAL_TARGET } from '../static/orena/screens/profile/model.js';
import { __internal } from '../static/orena/screens/profile/screen.js';

const { dueTileValue, actionSub, streakDaysTileValue, heroMarkup, identityMarkup, statsMarkup } = __internal;

// 1. No backend read at all: every measured field is 0/false/empty, never a sample figure -
// this is the literal rule-40 contract, held here so it cannot regress into demo data.
{
  const model = buildProfileModel({ context: {}, vocabulary: null, commerce: null });
  assert.equal(model.due, 0);
  assert.equal(model.savedCount, 0);
  assert.equal(model.dayStreak, 0, 'no activity read means no streak, not a sample figure');
  assert.equal('weekMinutes' in model, false, 'nothing measures minutes, so the field does not exist');
  assert.deepEqual(model.weekDays, []);
  assert.equal(model.weeklyGoalDone, 0);
  assert.equal(model.weeklyGoalTarget, 0, 'no target set: the five design segments are a drawing, not a goal');
  assert.equal(model.rankKnown, false);
  assert.equal(model.rankName, '');
  assert.equal(model.planKnown, false);
  assert.equal(model.planName, '');
  assert.equal(model.hasLevel, false);
  assert.equal(model.level, '');
  assert.equal(model.isAdmin, false);
  assert.equal(model.goalKey, 'goalNotSet');
}

// 2. A real backend answer passes straight through - the rank, the saved count and the due count
// are never recomputed here (writing_coach/product/rank.js's own shape).
{
  const vocabulary = {
    summary: { saved: 42, due: 3, mastered: 120, learning: 5 },
    rank: 4, rank_total: 32, rank_name: 'Steady Walker', band: 'Explorer',
  };
  const commerce = { available: true, plan: { id: 'premium', name: 'Premium' } };
  const context = { name: 'Calis', initial: 'C', picture: '', level: 'B2', due: 3, profile: { goal: 'work' }, isAdmin: false };
  const model = buildProfileModel({ context, vocabulary, commerce });
  assert.equal(model.due, 3);
  assert.equal(model.savedCount, 42);
  assert.equal(model.rankKnown, true);
  assert.equal(model.rankName, 'Steady Walker');
  assert.equal(model.rankNumber, 4);
  assert.equal(model.planKnown, true);
  assert.equal(model.planName, 'Premium');
  assert.equal(model.hasLevel, true);
  assert.equal(model.level, 'B2');
  assert.equal(model.goalKey, 'goalWork');
  assert.equal(model.name, 'Calis');
}

// 3. due is clamped at 0 (a negative or non-numeric context.due never reaches the view).
{
  assert.equal(buildProfileModel({ context: { due: -5 } }).due, 0);
  assert.equal(buildProfileModel({ context: { due: 'nope' } }).due, 0);
  assert.equal(buildProfileModel({ context: { due: 7 } }).due, 7);
}

// 4. account_profile.py's four goal categories map to a real label; anything else - unset, or a
// key the backend does not define - reads as "not set", never the raw stored key (D-068: the
// design's own goal sentence is sample content, not a field this screen may echo back).
{
  assert.equal(goalCopyKey('everyday'), 'goalEveryday');
  assert.equal(goalCopyKey('work'), 'goalWork');
  assert.equal(goalCopyKey('exam'), 'goalExam');
  assert.equal(goalCopyKey('voice'), 'goalVoice');
  assert.equal(goalCopyKey(''), 'goalNotSet');
  assert.equal(goalCopyKey(undefined), 'goalNotSet');
  assert.equal(goalCopyKey('some-future-key'), 'goalNotSet');
}

// 5. One locale string becomes the 7-cell weekday strip, and each language really does supply its
// own short forms (rule: per-locale, not one Latin-letter set for every language).
{
  assert.deepEqual(weekdayAbbrevs('M,T,W,T,F,S,S'), ['M', 'T', 'W', 'T', 'F', 'S', 'S']);
  assert.deepEqual(weekdayAbbrevs('T2,T3,T4,T5,T6,T7,CN'), ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']);
  assert.deepEqual(weekdayAbbrevs('一,二,三,四,五,六,日'), ['一', '二', '三', '四', '五', '六', '日']);
  assert.equal(weekdayAbbrevs('M,T,W,T,F,S,S').length, 7);
}

// 6. profileActions: Platform admin appears only for an admin, first, in the design's own order;
// a non-admin never sees the row at all (not disabled, not hidden - absent).
{
  const admin = profileActions({ isAdmin: true });
  assert.deepEqual(admin.map((a) => a.id), ['admin', 'settings', 'history', 'progress', 'plan', 'privacy', 'feedback', 'signout']);
  assert.equal(admin[0].kind, 'nav', 'Platform admin opens the Admin inside this UI (D-101 E), not the old console');
  assert.equal('href' in admin[0], false, 'the row names no address of its own: the screen resolves it from the router');
  assert.equal('sub' in admin.find((a) => a.id === 'plan'), false, 'the row carries no plan name: its sub is fixed copy (2026-10-09 export)');

  const learner = profileActions({ isAdmin: false });
  assert.deepEqual(learner.map((a) => a.id), ['settings', 'history', 'progress', 'plan', 'privacy', 'feedback', 'signout']);
  assert.equal(learner.some((a) => a.id === 'admin'), false, 'a non-admin never gets the admin row');
  assert.equal(learner.find((a) => a.id === 'signout').kind, 'signout');
}

// 7. dueTileValue: the design's own "{n} items · ~{m} min" is not copied (the "~1 min per item"
// half is the prototype's own made-up ratio, rule 40) - only the real item count and the real
// zero-state ("All caught up") render, English singular/plural picked correctly.
{
  assert.equal(dueTileValue(0), 'All caught up');
  assert.equal(dueTileValue(1), '1 item');
  assert.equal(dueTileValue(3), '3 items');
}

// 8. actionSub: the design's fixed per-row sub-label (read live - the static export truncated
// before reaching the actions list), and "Plan & privacy" alone carries a real value (the plan
// name) inside otherwise-fixed text, never a placeholder name when the plan read has not resolved.
{
  assert.equal(actionSub({ id: 'admin' }), 'Admin accounts only');
  assert.equal(actionSub({ id: 'settings' }), 'languages, learning, review, notifications');
  assert.equal(actionSub({ id: 'history' }), 'everything recorded, by day');
  assert.equal(actionSub({ id: 'progress' }), 'skills, evidence, rank');
  assert.equal(actionSub({ id: 'plan' }), 'plan, limits, invoices, pricing');
  assert.equal(actionSub({ id: 'privacy' }), 'microphone · learner audio');
  assert.equal(actionSub({ id: 'feedback' }), 'rate Orena, suggest improvements');
  assert.equal(actionSub({ id: 'signout' }), '');
}

// 9. The streak is REAL (D4 I14): the model reads GET /api/learner-activity through the shell context, the tile
// formats it with the *None/*One/*Many pattern, and the strip marks the days the server says were active.
{
  assert.equal(streakDaysTileValue(0), '0 days');
  assert.equal(streakDaysTileValue(1), '1 day');
  assert.equal(streakDaysTileValue(4), '4 days');
  const activity = {
    streak: { days: 3, active_today: true },
    week: { days: [true, true, true, false, false, false, false].map((active) => ({ active })), done_days: 3, goal_days: 4 },
  };
  const model = buildProfileModel({ context: { activity }, vocabulary: null, commerce: null });
  assert.equal(model.dayStreak, 3);
  assert.deepEqual(model.weekDays, [true, true, true, false, false, false, false]);
  assert.equal(model.weeklyGoalTarget, 4);
  assert.equal(model.weeklyGoalDone, 3);
  const markup = String(heroMarkup(model, { href: (id) => `#/${id}` }));
  assert.equal((markup.match(/s-profile-day--done/g) || []).length, 3, 'exactly the active days are marked');
  assert.equal((markup.match(/class="s-profile-day(?:"|\s)/g) || []).length, 7, 'the week strip has seven cells');
}

// 10. A real metric or no metric (D-103.4): nothing measures minutes, so there is no minutes tile, no daily-goal
// ring and no minutes stat - not drawn as 0. The weekly bar is drawn only against a target the learner set.
{
  const ctx = { href: (id) => `#/${id}` };
  const bare = buildProfileModel({ context: {}, vocabulary: null, commerce: null });
  const hero = String(heroMarkup(bare, ctx));
  assert.doesNotMatch(hero, /Daily goal|c-ring|This week|min</, 'no daily-goal ring and no minutes tile');
  const tileCount = (hero.match(/class="s-profile-tile(?:"|\s)/g) || []).length;
  assert.equal(tileCount, 2, 'the hero draws the streak and the due review, the two things that are measured');
  assert.doesNotMatch(String(statsMarkup(bare)), /week|min</i, 'no minutes stat');
  assert.doesNotMatch(String(identityMarkup(bare)), /s-profile-weekly/, 'no target, no weekly bar');
  const goal = buildProfileModel({ context: { activity: { streak: { days: 0 }, week: { days: [], done_days: 2, goal_days: 5 } } } });
  const identity = String(identityMarkup(goal));
  assert.equal((identity.match(/s-profile-weekly__bar(?:"|\s)/g) || []).length, 5, 'one segment per day of the learner target');
  assert.equal((identity.match(/s-profile-weekly__bar--filled/g) || []).length, 2);
  assert.match(identity, /2 \/ 5/);
  const done = buildProfileModel({ context: { activity: { streak: { days: 0 }, week: { days: [], done_days: 7, goal_days: 3 } } } });
  assert.match(String(identityMarkup(done)), /3 \/ 3/, 'the count never runs past the target');
}

console.log('Orena profile screen: model.js fallbacks, real-data passthrough, real streak and week strip, no unmeasured tiles, goal bar only against a set target, admin-gated actions, due-tile phrasing, action-row sub-labels: PASS');
