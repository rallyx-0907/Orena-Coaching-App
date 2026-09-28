/* Gate for Today's pure data mapping (static/orena/screens/today/model.js): the recommendation
   pool (review/reading/listening/speaking), the continuation (device-memory) mapping, the "For
   you" rail, and the rule-40 zero-fallback for the goal ring, streak and level/XP card (Design
   Contract rule 40 - no cross-activity backend; must never render an invented figure). DOM-free:
   imports only the screen's own model.js and copy.js, no browser. */
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
  buildLevel,
  todayDateLabel,
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
  assert.equal(listen.meta, 'Science');

  const dictation = mapContinuationEntry({ id: 'media:l1', title: 'x', intent: 'dictation' }, t);
  assert.equal(dictation.routeId, 'dictation', 'a dictation intent routes to Dictation, not plain Listening');

  const shadow = mapContinuationEntry({ id: 'media:l1', title: 'x', intent: 'shadowing' }, t);
  assert.equal(shadow.routeId, 'shadow');

  const grammar = mapContinuationEntry({ id: 'grammar:present-perfect', title: 'Present perfect' }, t);
  assert.equal(grammar.routeId, 'gconcept');
  assert.deepEqual(grammar.routeParams, { id: 'present-perfect' });

  for (const id of ['conversation:abc', 'voice:cafe', 'expression:1', 'essay:1', 'url:https://x', 'upload:1'])
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
  assert.equal(streak.n, 0, 'no cross-activity streak exists (only the Writing-only one on /api/dashboard, which this screen must not reuse)');
  assert.equal(streak.days.length, 7);
  assert.ok(streak.days.every((day) => day.done === false));
  // English puts the count first ("{n} day streak"), so `before` is empty and the count leads;
  // the frame bolds only the count, which is why the sentence is split around it rather than
  // rendered as one flat string.
  assert.equal(streak.before, '');
  assert.equal(streak.after, ' day streak');
  assert.equal(`${streak.before}${streak.n}${streak.after}`, '0 day streak', 'reassembled, it reads exactly like the un-split translation');

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

console.log('Orena Today: recommendation pool, continuation mapping, For-you rail and the rule-40 zero-fallback (goal ring, streak, level) all hold: PASS');
