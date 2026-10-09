/* Gate for Practice Hub / Skill Hub's pure data mapping (screens/practice/model.js). No DOM, no
   fetch: every function here takes already-fetched API data / device memory and returns the shape
   the screen paints. Design Contract rule 40 (never invent data) is what most assertions exist to
   hold: a mode with no real, addressable route is left out rather than shown disabled; a metric
   the backend does not measure is an honest 0. */
import assert from 'node:assert/strict';
import {
  SKILL_ORDER, SKILL_ICONS, SKILL_TINT, SKILL_BUILDERS,
  speakModes, writeModes, listenModes, vocabularyModes, grammarModes, readingModes, buildSkillSections, weakestLines, vocabularyRecommendation,
  continuationTarget, continuationRows, writeRecommendation,
} from '../static/orena/screens/practice/model.js';

// --- Skill order / icon / tint tables agree with each other -----------------------------------
{
  assert.deepEqual(SKILL_ORDER, ['listen', 'speak', 'reading', 'write', 'vocabulary', 'grammar'], 'all six of the design\'s skills are known skills - which ones render a hub section is decided by buildSkillSections from real data, not by this list (rule 40, corrected per N-22)');
  for (const skill of SKILL_ORDER) {
    assert.ok(SKILL_ICONS[skill], `${skill} has an icon table`);
    assert.ok(SKILL_TINT[skill]?.startsWith('var(--skill-'), `${skill} tints its icon swatch with the design's own --skill-* hue (rule 32), never a flat accent`);
    assert.ok(SKILL_BUILDERS[skill], `${skill} has a builder`);
  }
  // The six hues are distinct - one per skill, not accidentally collapsed to the same token.
  const tints = new Set(Object.values(SKILL_TINT));
  assert.equal(tints.size, 6, 'each skill gets its own hue token');
}

// --- Speak: three bare modes always, two content-gated modes when the library has one ----------
// D-101 H9 (named contract change): Timed Reaction, Mock Interview, Sound/Tone and Retell are deferred
// with the Coming-soon screens, so no entry to them is offered.
{
  const bare = speakModes([]);
  assert.equal(bare.length, 5, 'Pronunciation has a real content/import chooser even without public catalogue items');
  assert.deepEqual(bare.map((m) => m.key), ['situation', 'conv', 'freetalk', 'speak', 'shadow'], 'D-139 HD-2: Shadowing is the one extra mode offered');
  for (const m of bare) assert.equal(m.params, undefined, 'a parameterless route carries no params object');

  const withItems = speakModes([
    { id: 11, practice_type: 'sentences', level: 'B1' },
    { id: 'media:77', practice_type: 'clip', level: 'B2' },
    { id: 22, practice_type: 'retell', level: 'A2' },
    { id: 33, practice_type: 'sentences', level: 'C1' }, // a later duplicate type must not replace the first
  ]);
  assert.equal(withItems.length, 5, 'Pronunciation and Shadowing are two entries (D-139 HD-2)');
  const speak = withItems.find((m) => m.key === 'speak');
  assert.equal(speak.routeId, 'discover', 'Pronunciation starts with content choice');
  assert.equal(speak.labelRouteId, 'speak');
  assert.deepEqual(speak.query, { tab: 'listen', practice: 'pronunciation' });
  assert.equal(speak.params, undefined, 'no arbitrary first lesson is selected');
  const shadow = withItems.find((m) => m.key === 'shadow');
  assert.equal(shadow.routeId, 'discover', 'Shadowing opens the shared room through the media chooser (its route needs a media id)');
  assert.deepEqual(shadow.query, { tab: 'listen', practice: 'shadowing' });
  assert.equal(shadow.params, undefined, 'no arbitrary first lesson is selected');
  assert.equal(withItems.find((m) => m.key === 'retell'), undefined, 'Retell is deferred (H9) even when the library has an item');

  const chooser = speakModes([]).find((m) => m.key === 'speak');
  assert.equal(chooser.routeId, 'discover', 'D-149 (superseding D-139 HD-3): Pronunciation always opens the source chooser first');
  assert.deepEqual(chooser.query, { tab: 'listen', practice: 'pronunciation' });
  assert.equal(chooser.params, undefined, 'never straight into an attempt on the last line');
  assert.deepEqual(speakModes(), speakModes([]), 'a missing list behaves like an empty one');
  assert.deepEqual(speakModes(null), speakModes([]), 'a non-array list behaves like an empty one, never a crash');
}

// --- D-139 HD-1: Skill Hub Speak's Recommended card, from the learner's weakest real attempt ----
{
  const row = (assetId, segmentId, at, overall, words, verified = true) => ({ verified, overall, assetId, segmentId, at, evidence: words ? { words } : null });
  assert.deepEqual(weakestLines([]), [], 'no attempts, no candidate');
  assert.deepEqual(weakestLines([row('a', '1', 1, null, null, false)]), [], 'an unverified attempt has no score to be weak by');
  const found = weakestLines([
    row('a', '1', 1, 40, null), // improved since: its latest attempt (below) is what counts
    row('a', '1', 5, 90, null),
    row('b', '2', 2, 62, [{ text: 'tram', score: 31 }, { text: 'stop', score: 70 }, { text: 'x', score: null }]),
    row('c', '3', 3, 75, null),
  ]);
  assert.deepEqual(found.map((c) => c.assetId), ['b', 'c', 'a'], 'weakest line first, each by its latest attempt');
  assert.deepEqual(found[0].word, { text: 'tram', score: 31 }, 'the reason names the lowest-scoring word the account kept');
  assert.equal(found[1].word, null, 'no kept words, no word claimed');
}

// --- Write: the design's "Write freely" group, the built modes only (HW-1 B, D-101 H9) -----------
{
  assert.deepEqual(writeModes().map((m) => m.key), ['prompt', 'free', 'topic'], 'no waiting draft: no Continue draft');
  const modes = writeModes({ title: 'Weekend', n: 142 });
  assert.deepEqual(modes.map((m) => m.key), ['continue', 'prompt', 'free', 'topic']);
  assert.ok(modes.every((m) => m.group === 'free' && m.routeId === 'writing'), 'Respond, Context Rewrite and Timed Writing are not listed: not built / no content id');
  assert.deepEqual(modes.find((m) => m.key === 'prompt').query, { setup: 'prompt' }, 'Prompt opens Prompt Setup first (HW-2 B)');
  assert.deepEqual(modes.find((m) => m.key === 'topic').query, { setup: 'topic' });
  assert.deepEqual(modes.find((m) => m.key === 'free').query, { entry: 'free' });
  assert.equal(modes.find((m) => m.key === 'continue').query, undefined);
  assert.equal(writeModes({ title: 'x', n: 0 }).some((m) => m.key === 'continue'), false);
  for (const m of modes) assert.ok(SKILL_ICONS.write[m.key], `${m.key} has the design's icon`);
}

// --- Vocabulary: Due Review carries the real due count, clamped and coerced -------------------
{
  assert.equal(vocabularyModes(6).find((m) => m.key === 'review').due, 6);
  assert.equal(vocabularyModes(0).find((m) => m.key === 'review').due, 0, 'zero due is a real, honest answer - the mode still renders');
  assert.equal(vocabularyModes(-4).find((m) => m.key === 'review').due, 0, 'a negative count floors at 0 rather than showing nonsense');
  assert.equal(vocabularyModes(undefined).find((m) => m.key === 'review').due, 0, 'a missing count is the rule-40 zero, not an absent field');
  assert.equal(vocabularyModes('not-a-number').find((m) => m.key === 'review').due, 0);
  assert.deepEqual(vocabularyModes().map((m) => m.key), ['review', 'feed', 'collections', 'language'], 'the built modes only: Timed Recall and Context Transfer are deferred (H9); Collections and Saved language are the Library tabs (HV-1 B)');
  assert.deepEqual(vocabularyModes().map((m) => m.group), ['recall', 'browse', 'browse', 'browse'], 'the Recall and Browse groups of the design');
  assert.deepEqual(vocabularyModes().filter((m) => m.routeId === 'library').map((m) => m.query.tab), ['collections', 'language']);
  assert.deepEqual(vocabularyRecommendation(6), { n: 6 }, 'the Recommended card comes from the real due count');
  assert.equal(vocabularyRecommendation(0), null, 'nothing due, nothing recommended');
  assert.equal(vocabularyRecommendation(undefined), null);
}

// --- Listen: two content-gated modes, one per available_modes value ----------------------------
{
  assert.deepEqual(listenModes([]).map(m=>m.key), ['dictation'], 'Dictation can choose personal prepared imports even with an empty public catalogue');
  assert.deepEqual(listenModes(), listenModes([]));
  assert.deepEqual(listenModes(null), listenModes([]), 'a non-array list behaves like an empty one, never a crash');

  const items = [
    { lesson_id: 'en-daily-pen-in-my-bag', level: 'A1', available_modes: ['listen', 'active', 'dictation', 'shadowing'], comprehension_count: 2 },
    { lesson_id: 'en-science-cosmic-calendar', level: 'B2', available_modes: ['listen', 'active', 'dictation', 'shadowing'] },
  ];
  const modes = listenModes(items);
  assert.deepEqual(modes.map((m) => m.key), ['listening', 'dictation'], 'comprehension and dictation have distinct choices; Shadowing belongs to Speaking');
  const dictation = modes.find((m) => m.key === 'dictation');
  assert.equal(dictation.params, undefined, 'no fixed lesson assignment');
  assert.deepEqual(dictation.query, {tab:'listen',practice:'dictation'});
  const shadow = modes.find((m) => m.key === 'shadow');
  assert.equal(shadow, undefined);

  const dictationOnly = listenModes([{ lesson_id: 'x', level: 'B1', available_modes: ['listen', 'dictation'] }]);
  assert.deepEqual(dictationOnly.map((m) => m.key), ['dictation'], 'shadowing stays out when no item supports it - never a fabricated tile');
}

// --- Reading: one content-gated mode, from the real next-article queue -------------------------
{
  assert.deepEqual(readingModes({ available: false, next: null }), [], 'no article published -> no mode, a real honest empty, not a missing endpoint');
  assert.deepEqual(readingModes(null), [], 'a malformed/missing payload does not crash');
  assert.deepEqual(readingModes({ available: true, next: null }), [], 'available with no next payload is still nothing to open');

  const modes = readingModes({
    available: true,
    next: { set: { article: { id: 'art-1', level: 'B2' } }, recommendation: 'sig-abc' },
  });
  assert.deepEqual(modes, [{ key: 'reader', routeId: 'reader', params: { id: 'art-1' }, level: 'B2', query: { rec: 'sig-abc' } }]);

  const noRec = readingModes({ available: true, next: { set: { article: { id: 'art-2', level: '' } } } });
  assert.deepEqual(noRec, [{ key: 'reader', routeId: 'reader', params: { id: 'art-2' }, level: '' }], 'no recommendation signature -> no query, never an invented one');
}

// --- Grammar: only the one real entry point -----------------------------------------------------
{
  assert.deepEqual(grammarModes(), [{ key: 'grammarlib', routeId: 'grammarlib' }]);
}

// --- buildSkillSections is data-driven: a skill's section appears only when it has real modes --
{
  const noListenOrReading = buildSkillSections({ speakingItems: [], due: 3, listeningItems: [], reading: { available: false, next: null } });
  assert.deepEqual(noListenOrReading.map((s) => s.skill), ['listen', 'speak', 'write', 'vocabulary', 'grammar'], 'Listen retains its personal-import Dictation chooser; comprehension requires a materialized set');
  assert.equal(noListenOrReading.find((s) => s.skill === 'vocabulary').modes.find((m) => m.key === 'review').due, 3);

  const withAll = buildSkillSections({
    speakingItems: [],
    due: 0,
    listeningItems: [{ lesson_id: 'l1', level: 'A2', available_modes: ['listen', 'dictation'] }],
    reading: { available: true, next: { set: { article: { id: 'art-1', level: 'B1' } } } },
  });
  assert.deepEqual(withAll.map((s) => s.skill), SKILL_ORDER, 'with real data for every skill, all six sections render, in the human\'s order (D-152)');

  assert.deepEqual(buildSkillSections(), buildSkillSections({}), 'no data bag at all does not crash - every builder has a safe default');
  assert.deepEqual(buildSkillSections(), buildSkillSections().filter((s) => s.modes.length > 0), 'no data bag never produces an empty-but-rendered section');
}

// --- Continuation: device-memory entries mapped to a real, resumable route --------------------
{
  assert.deepEqual(continuationTarget({ id: 'expression:9' }), { kind: 'write', routeId: 'writing' });
  assert.deepEqual(continuationTarget({ id: 'essay:9' }), { kind: 'write', routeId: 'writingDraft', params: { id: 'essay:9' } });
  assert.deepEqual(continuationTarget({ id: 'anything', intent: 'writing' }), { kind: 'write', routeId: 'writing' });

  assert.deepEqual(continuationTarget({ id: 'grammar:present-perfect' }), { kind: 'grammar', routeId: 'gconcept', params: { id: 'present-perfect' } });
  assert.equal(continuationTarget({ id: 'grammar:' }), null, 'an empty grammar id has nowhere real to open, so it is dropped, not linked to a broken route');

  assert.deepEqual(
    continuationTarget({ id: 'media:77', intent: 'dictation' }),
    { kind: 'listen', routeId: 'dictation', params: { id: '77' } },
  );
  assert.deepEqual(
    continuationTarget({ id: 'media:77', intent: 'shadowing' }),
    { kind: 'listen', routeId: 'shadow', params: { id: '77' } },
  );
  assert.deepEqual(
    continuationTarget({ id: 'media:77' }),
    { kind: 'listen', routeId: 'listening', params: { id: '77' } },
    'a media item with no recognised sub-intent falls back to the listening workspace itself',
  );
  assert.equal(continuationTarget({ id: 'media:' }), null);

  // Named contract change (D4 I6): a conversation the learner left opens in the Conversation room by id.
  assert.deepEqual(continuationTarget({ id: 'conversation:abc-1', intent: 'speaking' }), { kind: 'speak', routeId: 'conv', query: { id: 'conversation:abc-1' } });

  // Kinds this hub genuinely cannot resume yet - left out, not guessed at (rule 40).
  assert.equal(continuationTarget({ id: 'url:abc', intent: 'speaking' }), null, 'a spoken conversation has no confirmed id-contract with an unbuilt new-UI screen');
  assert.equal(continuationTarget({ id: 'some-reading-id' }), null, 'a bare reading id is not resolvable to a real reader route from this data alone');
  assert.equal(continuationTarget({}), null);
  assert.equal(continuationTarget(null), null, 'a malformed entry does not crash');

  const rows = continuationRows([
    { id: 'media:1', intent: 'dictation', title: 'A Morning in the City', place: { index: 2, total: 3 } },
    { id: 'grammar:present-perfect', title: 'Present perfect', context: 'from your errors' },
    { id: 'url:x', intent: 'speaking', title: 'unreachable, dropped' },
    { id: 'expression:2', title: 'Draft' },
  ]);
  assert.equal(rows.length, 3, 'the one unreachable entry is dropped, not padded with a broken link');
  assert.deepEqual(rows.map((r) => r.kind), ['listen', 'grammar', 'write']);
  assert.equal(rows[0].tint, 'var(--skill-listen)');
  assert.equal(rows[1].tint, SKILL_TINT.grammar);
  assert.equal(rows[2].tint, SKILL_TINT.write);
  assert.deepEqual(rows[0].place, { index: 2, total: 3 });
  assert.equal(rows[1].context, 'from your errors');
  assert.equal(rows[2].place, null, 'no place data is null, not an invented default');

  const many = Array.from({ length: 8 }, (_, i) => ({ id: `grammar:g${i}`, title: `G${i}` }));
  assert.equal(continuationRows(many).length, 5, 'default limit is 5');
  assert.equal(continuationRows(many, { limit: 2 }).length, 2);
  assert.deepEqual(continuationRows([]), []);
  assert.deepEqual(continuationRows(undefined), []);
}

// --- Write recommendation: the one real per-skill recommender, no fabricated duration ---------
{
  assert.equal(writeRecommendation(null), null);
  assert.equal(writeRecommendation({}), null, 'no focus_label at all means nothing to recommend, not an empty-titled card');
  assert.equal(writeRecommendation({ focus_label: '  ' }), null, 'whitespace-only is still nothing');
  const rec = writeRecommendation({ focus_label: 'Present perfect after "since"', reason: 'Seen in your draft', action_label: 'Fix it' });
  assert.deepEqual(rec, { title: 'Present perfect after "since"', reason: 'Seen in your draft', actionLabel: 'Fix it' });
  assert.ok(!('dur' in rec) && !('duration' in rec), 'no duration field ever appears - the backend never measures one, so the eyebrow never fabricates a "~N min"');
  const noReason = writeRecommendation({ focus_label: 'X' });
  assert.equal(noReason.reason, '', 'a missing reason is an honest empty string, not omitted or invented');
}

/* X-01 / HX-1 A: React / Reuse only with a real last listened line */
{
  assert.ok(!listenModes([]).some((m) => m.key === 'react'));
  const last = { params: { id: 'lesson-en' }, query: { seg: 'lesson-en:003' } };
  const react = listenModes([], last).find((m) => m.key === 'react');
  assert.deepEqual([react.routeId, react.params, react.query], ['react', last.params, last.query]);
}

console.log('Orena Practice Hub / Skill Hub screen: skill/mode mapping, continuation resolution, rule-40 zeros and drops, no invented data: PASS');
