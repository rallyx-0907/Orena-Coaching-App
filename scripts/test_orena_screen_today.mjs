/* Gate for Today's pure data mapping (static/orena/screens/today/model.js): the recommendation
   pool (review/reading/listening/speaking), the continuation (device-memory) mapping, the "For
   you" rail, the rule-40 zero-fallback for the goal ring, streak and level/XP card (Design
   Contract rule 40 - no cross-activity backend; must never render an invented figure), and the
   header's real-data greeting/subtitle (human review item: never the frame's fixed "Good
   morning" / "Two things worth doing today..."). DOM-free: imports only the screen's own model.js
   and copy.js, no browser. */
import assert from 'node:assert/strict';

// copy/index.js resolves the interface language at import time from window.localStorage/navigator.
const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

const { t } = await import('../static/orena/screens/today/copy.js');
const {
  formatDuration,
  pickMeaning,
  buildRecommendationPool,
  mapContinuationEntry,
  buildForYou,
  usedRecommendationIds,
  buildGoalSummary,
  buildSkillRings,
  buildStreak,
  leadWithContinuation,
  buildLevel,
  todayDateLabel,
  greetingPeriod,
  buildGreeting,
  buildHeadSubtitle,
  RECOMMEND_LIMIT,
} = await import('../static/orena/screens/today/model.js');

// 1. formatDuration: the locale-invariant "M:SS" clock, empty for an unmeasured duration - never
// an invented figure (rule 40).
assert.equal(formatDuration(0), '', 'no duration renders nothing, not "0:00"');
assert.equal(formatDuration(null), '');
assert.equal(formatDuration(undefined), '');
assert.equal(formatDuration(46000), '0:46');
assert.equal(formatDuration(8547), '0:09', 'rounds to the nearest second, matching Discover\'s identical clipMs formatting');
assert.equal(formatDuration(125000), '2:05');

// 2. pickMeaning: the learner's support language, else English, else whatever is first - never a
// language the entry does not carry.
const meanings = [{ language: 'en', text: 'health' }, { language: 'vi', text: 'sức khỏe' }];
assert.equal(pickMeaning(meanings, 'vi'), 'sức khỏe', 'the support language wins when present');
assert.equal(pickMeaning(meanings, 'zh'), 'health', 'falls back to English when the support language is absent');
assert.equal(pickMeaning([{ language: 'fr', text: 'santé' }], 'zh'), 'santé', 'falls back to the first entry when neither the support language nor English is present');
assert.equal(pickMeaning([], 'en'), '', 'no meanings at all is empty, not invented');

// 3. buildRecommendationPool: one candidate per real source, in order; a source with nothing
// available contributes nothing (never padded with an invented fourth kind); capped at
// RECOMMEND_LIMIT.
{
  const listening = [{ lesson_id: 'l1', title: 'Cosmic calendar', level: 'B2', duration_ms: 46000, thumbnail_url: 'https://x/img.jpg' }];
  const speaking = [{ id: 'media:pen', title: 'A pen in my bag', level: 'A1', duration_ms: 8547 }];
  const unavailable = buildRecommendationPool({ reading: { available: false, next: null }, listening, speaking }, t);
  assert.equal(unavailable.length, 2, 'no published article: the pool is listening + speaking, not padded');
  assert.equal(unavailable[0].routeId, 'listening');
  assert.equal(unavailable[0].id, 'l1');
  assert.equal(unavailable[0].durationLabel, '0:46');
  assert.equal(unavailable[1].routeId, 'speak');

  const article = { id: 'art-1', title: 'Why We Love Routines', level: 'B1' };
  const available = buildRecommendationPool({ reading: { available: true, next: { set: { article }, recommendation: 'sig-1' } }, listening, speaking }, t);
  assert.equal(available.length, 3, 'reading + listening + speaking = 3, matching RECOMMEND_LIMIT');
  assert.equal(available.length, RECOMMEND_LIMIT);
  assert.equal(available[0].routeId, 'reader');
  assert.deepEqual(available[0].routeParams, { id: 'art-1' });
  assert.deepEqual(available[0].routeQuery, { rec: 'sig-1' }, 'the signed recommendation travels with the reader link');
  assert.equal(available[0].durationLabel, '', 'the reading payload carries no duration - none is shown, not an invented one');

  assert.deepEqual(buildRecommendationPool({ reading: { available: false, next: null }, listening: [], speaking: [] }, t), [], 'every source empty is an empty pool, never invented cards');

  // A malformed item missing its id contributes nothing rather than a broken link.
  const noId = buildRecommendationPool({ reading: { available: false, next: null }, listening: [{ title: 'no id' }], speaking: [] }, t);
  assert.equal(noId.length, 0, 'a listening item with no lesson_id is skipped, not linked with an empty id');

  // 3b. The learner's real due-vocabulary-review queue (GET /api/library/review-queue, same
  // source My Library's Due-Review tab already reads) competes in the same pool, leading it
  // because a due SRS interval is time-sensitive (docs/project/UI_BACKEND_GAPS.md's review, P1).
  const withReview = buildRecommendationPool({ reading: { available: false, next: null }, listening, speaking, review: { due_count: 6, first_due_word: 'buffer' } }, t);
  assert.equal(withReview.length, 3, 'review + listening + speaking, never padded past the real sources');
  assert.equal(withReview[0].source, 'review', 'a due review queue leads the pool - time-sensitive, unlike a catalogue pick');
  assert.equal(withReview[0].routeId, 'review');
  assert.deepEqual(withReview[0].routeParams, {});
  assert.equal(withReview[0].kind, 'Review');
  assert.equal(withReview[0].title, 'buffer', 'the actual next-due word, not an invented headline');
  assert.equal(withReview[0].reason, '6 words due for review', 'a real, non-empty reason string - the due count itself');
  assert.equal(withReview[0].icon, 'whole-word');
  assert.equal(withReview[0].tint, 'var(--skill-vocab)');
  // languages-5 / finding A: a real vocabulary word carries the real active learning language
  // screen.js already read from ctx.context (never a script guess - kit/lang.js's own doc comment)
  // so screen.js can mark it with a real `lang` attribute via the shared helper.
  assert.equal(withReview[0].lang, '', 'no `language` argument (a rejected/unset context) carries an unknown lang - never an invented one');
  const withReviewEn = buildRecommendationPool({ reading: { available: false, next: null }, listening, speaking, review: { due_count: 6, first_due_word: 'buffer' }, language: 'en' }, t);
  assert.equal(withReviewEn[0].lang, 'en', 'an English-learning due word is marked lang="en", not left unmarked');
  const withHanziReview = buildRecommendationPool({ reading: { available: false, next: null }, listening: [], speaking: [], review: { due_count: 1, first_due_word: '生病' }, language: 'zh' }, t);
  assert.equal(withHanziReview[0].lang, 'zh', 'the active learning language is carried straight onto the review item, not re-derived from the word\'s script');

  // Singular English wording at exactly one due word.
  const singular = buildRecommendationPool({ reading: { available: false, next: null }, listening: [], speaking: [], review: { due_count: 1, first_due_word: 'habit' } }, t);
  assert.equal(singular[0].reason, '1 word due for review');

  // Competing for real: with all four sources available, review still takes a slot and the pool
  // stays capped at RECOMMEND_LIMIT (the least-priority source, speaking, is the one left out).
  const allFour = buildRecommendationPool({ reading: { available: true, next: { set: { article }, recommendation: 'sig-1' } }, listening, speaking, review: { due_count: 2, first_due_word: 'hectic' } }, t);
  assert.equal(allFour.length, RECOMMEND_LIMIT);
  assert.deepEqual(allFour.map((item) => item.source), ['review', 'reading', 'listening'], 'review competes for a real slot rather than only appearing when nothing else is available');

  // Rule 40: no real due-review evidence (queue empty, or a due_count with no resolvable word) is
  // an absent candidate, never an invented one.
  assert.equal(buildRecommendationPool({ reading: { available: false, next: null }, listening: [], speaking: [], review: { due_count: 0, first_due_word: '' } }, t).length, 0);
  assert.equal(buildRecommendationPool({ reading: { available: false, next: null }, listening: [], speaking: [], review: { due_count: 3, first_due_word: '' } }, t).length, 0, 'a count with no resolvable word is not shown either');
  assert.equal(buildRecommendationPool({ reading: { available: false, next: null }, listening: [], speaking: [] }, t).length, 0, 'no review argument at all (a rejected fetch) behaves exactly like an empty queue');
}

// 4. mapContinuationEntry: only the id namespaces this shell can confidently route.
{
  const listen = mapContinuationEntry({ id: 'media:l1', title: 'Cosmic calendar', context: 'Science' }, t);
  assert.equal(listen.routeId, 'listening');
  assert.deepEqual(listen.routeParams, { id: 'l1' });
  assert.equal(listen.meta, 'Continue · Science', '"Continue" leads the meta line (design/UX review 2026-10-08)');
  assert.equal(listen.kind, 'Listen', 'the kind names the skill, not "Continue"');

  const dictation = mapContinuationEntry({ id: 'media:l1', title: 'x', intent: 'dictation' }, t);
  assert.equal(dictation.routeId, 'dictation', 'a dictation intent routes to Dictation, not plain Listening');

  const shadow = mapContinuationEntry({ id: 'media:l1', title: 'x', intent: 'shadowing' }, t);
  assert.equal(shadow.routeId, 'shadow');

  const grammar = mapContinuationEntry({ id: 'grammar:present-perfect', title: 'Present perfect' }, t);
  assert.equal(grammar.routeId, 'gconcept');
  assert.deepEqual(grammar.routeParams, { id: 'present-perfect' });

  // Named contract change (D4 I6): a conversation the learner left now opens in the Conversation room by id.
  const talk = mapContinuationEntry({ id: 'conversation:abc-1', title: 'Ordering coffee' }, t);
  assert.equal(talk.routeId, 'conv');
  assert.deepEqual(talk.routeQuery, { id: 'conversation:abc-1' });

  for (const id of ['voice:cafe', 'expression:1', 'essay:1', 'url:https://x', 'upload:1'])
    assert.equal(mapContinuationEntry({ id, title: 'x' }, t), null, `${id}: no confirmed new-shell route yet, left out rather than guessed`);
  assert.equal(mapContinuationEntry({ id: 'media:', title: 'x' }, t), null, 'an empty lesson id after the prefix is not a link either');
}

// 5. buildForYou: unfinished work first, then the catalogues, then the Daily Vocabulary Feed,
// deduplicated against whatever the recommendation pool already used, capped at the limit.
{
  const continuation = [{ id: 'media:l1', title: 'Continuing this' }, { id: 'conversation:x', title: 'dropped' }];
  const listening = [{ lesson_id: 'l1', title: 'used elsewhere' }, { lesson_id: 'l2', title: 'Free item', level: 'A2' }];
  const speaking = [{ id: 's1', title: 'Speak item', level: 'B1' }];
  const feed = [{ headword: 'habit', level: 'A2', meanings: [{ language: 'en', text: 'a settled tendency' }] }];
  const usedIds = new Set(['l1']);
  const items = buildForYou({ continuation, listening, speaking, feed, usedIds, supportLang: 'en', language: 'en' }, t);
  assert.equal(items[0].source, 'continue', 'unfinished work leads the rail');
  assert.ok(!items.some((item) => item.id === 'l1'), 'an item already used by the recommendation pool is not repeated');
  assert.ok(items.some((item) => item.id === 'l2'), 'the rest of the Listening catalogue fills in');
  assert.ok(items.some((item) => item.id === 's1'));
  const word = items.find((item) => item.source === 'word');
  assert.equal(word.title, 'habit');
  assert.equal(word.meta, 'a settled tendency');
  assert.equal(word.tag, 'A2');
  // languages-5 / finding A: the Daily Vocabulary Feed word carries the real active learning
  // language (already threaded through from the caller), never a script guess.
  assert.equal(word.lang, 'en');
  assert.ok(!('lang' in items.find((item) => item.source === 'listening')), 'a catalogue item is never given a `lang` - only a real vocabulary word is');

  const hanziFeed = [{ headword: '生病', level: 'A2', meanings: [{ language: 'en', text: 'to fall ill' }] }];
  const hanziItems = buildForYou({ feed: hanziFeed, supportLang: 'en', language: 'zh' }, t);
  assert.equal(hanziItems.find((item) => item.source === 'word').lang, 'zh', 'the active learning language is carried straight onto the feed item, not re-derived from the word\'s script');

  const many = Array.from({ length: 30 }, (_, i) => ({ lesson_id: `x${i}`, title: `x${i}` }));
  assert.ok(buildForYou({ listening: many }, t).length <= 12, 'the rail is capped, not unbounded');
}

assert.deepEqual(usedRecommendationIds([{ id: 'a' }, { id: 'b' }, { id: null }]), new Set(['a', 'b']));

// 6. buildGoalSummary: real evidence when the window has any, the honest "not tracked yet" when it
// does not - the pct is always 0 (no daily-goal measure exists at all, rule 40).
{
  const empty = buildGoalSummary({ domains: {} }, t);
  assert.equal(empty.pct, 0);
  assert.equal(empty.sub, 'Not tracked yet');

  const withEvidence = buildGoalSummary({ domains: { speaking: { activity: { count: 3, undated: 0, label: 'takes' } }, writing: { activity: { count: 0, undated: 0, label: 'submitted_versions' } } } }, t);
  assert.equal(withEvidence.pct, 0, 'the ring itself never claims a real percent - there is no daily-goal measure to show one');
  assert.equal(withEvidence.sub, 'This week: 3 speaking takes', 'real evidence names its own window, never "today"');
}

// 7. buildSkillRings / buildStreak / buildLevel: the rule-40 zero shape, in the canonical component.
{
  const rings = buildSkillRings(t);
  assert.equal(rings.length, 3);
  for (const ring of rings) assert.equal(ring.percent, 0, `${ring.key}: no per-skill daily measure exists, so 0 - never an invented percent`);
  assert.deepEqual(rings.map((r) => r.color), ['var(--skill-read)', 'var(--skill-listen)', 'var(--skill-speak)']);
  assert.deepEqual(rings.map((r) => r.icon), ['book-open', 'headphones', 'mic']);
  // The frame fuses the caption with the ring's own percent ("Reading 0%"), not the bare name.
  assert.deepEqual(rings.map((r) => r.label), ['Reading 0%', 'Listening 0%', 'Speaking 0%']);
  assert.deepEqual(rings.map((r) => r.name), ['Reading', 'Listening', 'Speaking'], 'the bare name is kept too, for the ring\'s title tooltip');

  const streak = buildStreak(t);
  assert.equal(streak.known, false, 'no activity read: there is no streak to show, not 0 days');
  assert.equal(streak.n, 0, 'no cross-activity streak exists (only the Writing-only one on /api/dashboard, which this screen must not reuse)');
  assert.equal(streak.days.length, 7);
  assert.ok(streak.days.every((day) => day.done === false));
  // English puts the count first ("{n} day streak"), so `before` is empty and the count leads;
  // the frame bolds only the count, which is why the sentence is split around it rather than
  // rendered as one flat string.
  assert.equal(streak.before, '');
  assert.equal(streak.after, ' day streak');
  assert.equal(`${streak.before}${streak.n}${streak.after}`, '0 day streak', 'reassembled, it reads exactly like the un-split translation');

  // The streak is real (D4 I14): the days the server says were active, Monday first, and never a visit.
  const real = buildStreak(t, {
    streak: { days: 2, active_today: true },
    week: { days: [false, false, false, true, true, false, false].map((active) => ({ active })) },
  });
  assert.equal(real.known, true);
  assert.equal(real.n, 2);
  assert.deepEqual(real.days.map((day) => day.done), [false, false, false, true, true, false, false]);
  assert.equal(`${real.before}${real.n}${real.after}`, '2 day streak');

  const level = buildLevel(t);
  assert.equal(level.pct, 0);
  assert.equal(level.xp, '0 XP');
  assert.equal(level.next, 'Not tracked yet');
  assert.equal(level.badge, '–', 'a placeholder glyph, never an invented tier');
}

// 8. todayDateLabel: the real date, never the frame's hardcoded "Fri, Sep 25". A date picked
// clear of that sample (Dec 3, 2026 is a Thursday) so the "not the sample" check cannot
// coincidentally pass just because the real calendar and the frame's sample date agree.
{
  const date = new Date(Date.UTC(2026, 11, 3));
  const en = todayDateLabel(date, 'en');
  assert.match(en, /\b3\b/, 'the real day of month appears');
  assert.notEqual(en, 'Fri, Sep 25', 'not the frame\'s literal sample text');
  const vi = todayDateLabel(date, 'vi');
  const zh = todayDateLabel(date, 'zh');
  assert.ok(vi.length > 0 && zh.length > 0);
  assert.equal(todayDateLabel(date, '!!!'), todayDateLabel(date, 'en'), 'a locale Intl rejects falls back to English rather than throwing');
}

// 9. languages-5 / finding A: screen.js wires the shared kit/lang.js helper for a vocabulary
// word's title - never a per-screen Han-range copy (the defect this pass fixed for real).
{
  const { readFileSync } = await import('node:fs');
  const screenSrc = readFileSync(new URL('../static/orena/screens/today/screen.js', import.meta.url), 'utf8');
  assert.match(screenSrc, /import\s*\{\s*langSpan\s*\}\s*from\s*'\.\.\/\.\.\/kit\/lang\.js'/, 'imports the shared lang helper from kit/lang.js');
  assert.doesNotMatch(screenSrc, /㐀-鿿/, 'no local Han-range regex left in screen.js');
  const modelSrc = readFileSync(new URL('../static/orena/screens/today/model.js', import.meta.url), 'utf8');
  assert.doesNotMatch(modelSrc, /㐀-鿿/, 'no local Han-range regex left in model.js either - the active learning language is real data, not a script guess');
}

// 10. greetingPeriod / buildGreeting: the header's real-clock greeting (human review item).
// Boundaries as documented in model.js - 05:00 starts morning, 12:00 starts afternoon, 18:00
// starts evening, and the remaining night hours fall back to evening (the frame draws only
// three greeting states, never a fourth "good night" one).
{
  assert.equal(greetingPeriod(0), 'evening', 'midnight is still evening - no fourth state exists');
  assert.equal(greetingPeriod(4), 'evening', 'one minute-hour before the morning boundary');
  assert.equal(greetingPeriod(5), 'morning', 'the morning boundary itself, inclusive');
  assert.equal(greetingPeriod(11), 'morning', 'the last hour still counted as morning');
  assert.equal(greetingPeriod(12), 'afternoon', 'the afternoon boundary itself, inclusive');
  assert.equal(greetingPeriod(17), 'afternoon', 'the last hour still counted as afternoon');
  assert.equal(greetingPeriod(18), 'evening', 'the evening boundary itself, inclusive');
  assert.equal(greetingPeriod(23), 'evening');

  // Local-time Date constructor (never Date.UTC) so the asserted hour is exactly what
  // Date#getHours() (the device's own local clock) returns, whatever timezone this gate runs in.
  assert.equal(buildGreeting(new Date(2026, 0, 1, 7), t), 'Good morning');
  assert.equal(buildGreeting(new Date(2026, 0, 1, 15), t), 'Good afternoon');
  assert.equal(buildGreeting(new Date(2026, 0, 1, 21), t), 'Good evening');
  assert.equal(buildGreeting(new Date(2026, 0, 1, 2), t), 'Good evening', 'the pre-dawn hours read as evening too');
  assert.equal(buildGreeting(new Date(2026, 0, 1, 5), t), 'Good morning', 'the lower boundary carried through end to end');
  assert.equal(buildGreeting(new Date(2026, 0, 1, 17), t), 'Good afternoon');
  assert.equal(buildGreeting(new Date(2026, 0, 1, 18), t), 'Good evening');
}

// 11. buildHeadSubtitle: the header's real-state subtitle (human review item) - built from the
// real size of the "Recommended for today" pool and whether the "For you" rail holds anything;
// never the frame's fixed "Two things worth doing today, then something to enjoy." (rule 40).
{
  assert.equal(buildHeadSubtitle({ recommendedCount: 0, forYouCount: 0 }, t), '', 'nothing recommended and nothing for-you: an honest silence, not an invented line');
  assert.equal(buildHeadSubtitle({ recommendedCount: 0, forYouCount: 6 }, t), '', 'a for-you rail alone (no recommendations) still gives no line - the sentence never leads with "then"');
  assert.equal(buildHeadSubtitle(undefined, t), '', 'no argument at all behaves exactly like all-zero counts');
  assert.equal(buildHeadSubtitle({ recommendedCount: 1, forYouCount: 0 }, t), '1 thing worth doing today.', 'singular English wording at exactly one');
  assert.equal(buildHeadSubtitle({ recommendedCount: 1, forYouCount: 4 }, t), '1 thing worth doing today, then something to enjoy.', 'the enjoy clause only when the for-you rail is real');
  assert.equal(buildHeadSubtitle({ recommendedCount: 2, forYouCount: 0 }, t), '2 things worth doing today.', 'plural wording, no enjoy clause - the for-you rail is genuinely empty');
  assert.equal(buildHeadSubtitle({ recommendedCount: 3, forYouCount: 12 }, t), '3 things worth doing today, then something to enjoy.');

  // Not a hardcoded copy of the frame's sample sentence: a different real count produces
  // different real text (a literal "Two things worth doing today..." return could never do this).
  assert.notEqual(
    buildHeadSubtitle({ recommendedCount: 3, forYouCount: 12 }, t),
    buildHeadSubtitle({ recommendedCount: 1, forYouCount: 12 }, t),
    'the count actually drives the sentence, so two different real pools read differently',
  );
}

// 12. The header is wired from real data end to end, and the eyebrow's own name-fallback stays
// the source of "the greeting without one [a name]": screen.js never folds the learner's name
// into the greeting string itself (that would break the no-name case), and no longer shows the
// static shell page title in the H1 the frame draws as the greeting.
{
  const { readFileSync } = await import('node:fs');
  const screenSrc = readFileSync(new URL('../static/orena/screens/today/screen.js', import.meta.url), 'utf8');
  assert.match(screenSrc, /buildGreeting\(/, 'the H1 is built from the real-clock greeting');
  assert.match(screenSrc, /buildHeadSubtitle\(/, 'the subtitle is built from the real recommendation/for-you counts');
  assert.doesNotMatch(screenSrc, /shellCopy\('today'\)/, 'the H1 no longer shows the static shell page title in place of the real greeting');
  assert.match(screenSrc, /name \? html`<div class="s-today-eyebrow">/, 'the eyebrow (name) still renders only when a real name exists');
  // buildGreeting takes no name argument at all - structurally guaranteeing the greeting text
  // itself never depends on whether a name exists, which is what makes "no name -> the greeting
  // without one" true by construction rather than by a second branch to keep in sync.
  assert.equal(buildGreeting.length, 2, 'buildGreeting(date, t) takes no name parameter');
}

/* The skippable level prompt (D-105 H-19): only a profile that exists and declares no level. */
{
  const { needsLevelPrompt } = await import('../static/orena/screens/today/model.js');
  assert.equal(needsLevelPrompt({ exists: true, declared_level: '' }), true);
  assert.equal(needsLevelPrompt({ exists: true, declared_level: 'HSK4' }), false);
  assert.equal(needsLevelPrompt({ exists: false, declared_level: '' }), false, 'a missing profile is Welcome, not a prompt');
  assert.equal(needsLevelPrompt(null), false, 'an unreadable profile is not a missing level');
}

// LEX-073: the learner's unfinished work leads Recommended, is taken out of For you, and the week strip marks today.
{
  const pool = [{ source: 'listening', id: 'les1', routeParams: { id: 'les1' }, kind: 'Listen' }, { source: 'reading', id: 'art1', routeParams: { id: 'art1' }, kind: 'Read' }];
  const continuation = [{ id: 'media:les1', title: 'Cosmic', context: 'Continue listening', intent: 'listening' }];
  const led = leadWithContinuation(pool, continuation, t, () => ({ icon: 'headphones', tint: 'var(--skill-listen)' }));
  assert.equal(led[0].source, 'continue');
  assert.equal(led[0].reason, 'Continue listening');
  assert.deepEqual(led.map((item) => item.id), ['media:les1', 'art1'], 'the same lesson from the catalogue is not offered twice');
  assert.ok(usedRecommendationIds(led).has('les1'), 'the lesson id is used, so For you drops it too');
  assert.deepEqual(leadWithContinuation(pool, [], t, () => null), pool, 'nothing unfinished: the pool is unchanged');
  const strip = buildStreak(t, { streak: { days: 0 }, today: '2026-10-07', week: { days: ['2026-10-05', '2026-10-06', '2026-10-07', '2026-10-08', '2026-10-09', '2026-10-10', '2026-10-11'].map((date, i) => ({ date, active: i === 0, future: i > 2 })) } });
  assert.deepEqual(strip.days.map((day) => day.today), [false, false, true, false, false, false, false], 'today is marked');
  assert.deepEqual(strip.days.map((day) => day.done), [true, false, false, false, false, false, false], 'only a really active day is ticked');
  assert.deepEqual(strip.days.map((day) => day.future), [false, false, false, true, true, true, true]);
}

console.log('Orena Today: recommendation pool, continuation mapping, For-you rail, the rule-40 zero-fallback (goal ring, streak, level) and the real-data header greeting/subtitle all hold: PASS');

// LEX-073 / LEX-090: one card per title, the place when it is measured, a half-read text can be continued.
{
  const { buildForYou, usedRecommendationIds } = await import('../static/orena/screens/today/model.js');
  const placed = mapContinuationEntry({ id: 'media:l1', title: 'Cosmic calendar', context: 'Science', place: { index: 1, total: 1, within: 40 } }, t);
  assert.equal(placed.meta, 'Continue · Science · 40% done', 'the measured place follows the context');
  assert.equal(mapContinuationEntry({ id: 'media:l1', title: 'x', place: { index: 1, total: 1 } }, t).meta, 'Continue', 'a 1 of 1 place with nothing measured says only that it continues');
  const reading = mapContinuationEntry({ id: 'book:b1:c3', title: 'THE CRY IN THE CORRIDOR', context: 'The Secret Garden', place: { index: 3, total: 9 } }, t);
  assert.equal(reading.routeId, 'reader');
  assert.deepEqual(reading.routeParams, { id: 'book:b1:c3' });
  assert.equal(reading.title, 'The Cry in the Corridor', 'a title stored in capitals is not shouted');
  assert.equal(mapContinuationEntry({ id: 'article:a1', title: 'x', place: { index: 1, total: 1, within: 100 } }, t), null, 'a finished text is not continued');
  const speakingItems = [{ id: 's1', title: 'Make room for someone' }, { id: 's2', title: 'Make room for someone' }, { id: 's3', title: 'Order coffee' }];
  const rail = buildForYou({ continuation: [], listening: [], speaking: speakingItems, feed: [], usedIds: new Set() }, t);
  assert.deepEqual(rail.map((item) => item.title), ['Make room for someone', 'Order coffee'], 'the same title is one card');
  const used = usedRecommendationIds([{ id: 'x', title: 'Order coffee', routeParams: { id: 's3' } }]);
  assert.deepEqual(buildForYou({ continuation: [], listening: [], speaking: speakingItems, feed: [], usedIds: used }, t).map((item) => item.title), ['Make room for someone'], 'a title the hero already shows is not repeated below');
}
