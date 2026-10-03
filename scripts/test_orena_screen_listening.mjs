/* Gate for the Listening Workspace's pure data mapping (static/orena/screens/listening/model.js),
   frame 06, D-091. Imports only the DOM-free module.

   Loads the real captured payloads (scripts/fixtures/api/listening_library_lesson.{en,zh}.json -
   `GET /api/listening/library/{lessonId}`) so a screen model that reads a field these payloads do
   not carry fails this gate. The Save-phrase payload is checked against the real route's own
   schema (`LibraryVocabularyIn` in writing_coach/becoming_library.py), read from source. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  SPEEDS, nextSpeed, speedLabel, contentIdFor, mmss, minutesFrom, metaLine, mapLesson,
  wordTokens, hanTokens, lookupContext, estimatedTokenIndex, currentTokenIndex, rowTone, modeHintKey,
  selectionAfterModeChange, previousIndex, nextIndex, PHRASE_MAX, phraseSaveable, phraseSavePayload,
  phraseSaved, vocabularyForSegment, placeFor, dictationLinesCompleted,
  pickNextRecommendation, progressPercent, msAtSeekFraction, timeLabel, reachedEnd, listenedMinutesLabel,
} from '../static/orena/screens/listening/model.js';

function fixture(name) {
  return JSON.parse(readFileSync(new URL(`./fixtures/api/${name}`, import.meta.url)));
}

const en = fixture('listening_library_lesson.en.json');
const zh = fixture('listening_library_lesson.zh.json');

/* --- speed cycle: the design's own (1x -> 0.75x -> 0.5x -> 1.25x -> 1x) --- */
assert.deepEqual(SPEEDS, [1, 0.75, 0.5, 1.25]);
assert.equal(nextSpeed(1), 0.75);
assert.equal(nextSpeed(0.75), 0.5);
assert.equal(nextSpeed(0.5), 1.25);
assert.equal(nextSpeed(1.25), 1, 'cycles back to the start');
assert.equal(nextSpeed(0.9), 1, 'an unrecognised current rate does not throw - it restarts the cycle');
assert.equal(speedLabel(1), '1×');
assert.equal(speedLabel(1.25), '1.25×');
assert.equal(speedLabel(0.75), '0.75×');

/* --- content id / mmss / minutes --- */
assert.equal(contentIdFor('en-science-cosmic-calendar'), 'media:en-science-cosmic-calendar');
assert.equal(mmss(44000), '0:44');
assert.equal(mmss(125000), '2:05');
assert.equal(mmss(null), null, 'rule 40: an absent time is not a fabricated 0:00');
assert.equal(mmss(-1), null);
assert.equal(minutesFrom(0), 0, 'a real zero-length duration stays a real zero');
assert.equal(minutesFrom(90000), 2);
assert.equal(minutesFrom(null), null);
assert.equal(metaLine(['B2', '', '3 min']), 'B2 · 3 min', 'an empty part never leaves a stray separator');
assert.equal(metaLine([null, undefined]), '');

/* --- mapLesson: the real EN capture --- */
{
  const lesson = mapLesson(en);
  assert.equal(lesson.lessonId, 'en-science-cosmic-calendar');
  assert.equal(lesson.title, 'The cosmic calendar');
  assert.equal(lesson.language, 'en');
  assert.equal(lesson.topic, 'science');
  assert.equal(lesson.level, 'B2');
  assert.equal(lesson.durationMs, 46000);
  assert.equal(lesson.excerptStartMs, 1000);
  assert.equal(lesson.excerptEndMs, 47000);
  assert.deepEqual(lesson.vocabulary, ['galaxy', 'solar system', 'extinct']);
  assert.deepEqual(lesson.modes, { follow: true, active: true, shadowing: true, dictation: true });
  assert.equal(lesson.playbackKind, 'video');
}

/* --- mapLesson: the real ZH capture (different modes/vocabulary/language) --- */
{
  const lesson = mapLesson(zh);
  assert.equal(lesson.language, 'zh');
  assert.deepEqual(lesson.vocabulary, ['输入', '条目', '搜寻']);
  assert.ok(lesson.title.length > 0);
}

/* --- mapLesson: a stored/imported payload with no `catalog` never throws (rule 40 degrade) --- */
{
  const bare = { asset: { asset_id: 'x', title: 'Imported clip', source_language: 'en', duration_ms: 90000 }, playback: null };
  const lesson = mapLesson(bare);
  assert.equal(lesson.title, 'Imported clip');
  assert.equal(lesson.lessonId, '');
  assert.equal(lesson.durationMs, 90000, 'an upload has no catalogue: its own asset duration stands');
  assert.deepEqual(lesson.vocabulary, []);
  assert.deepEqual(lesson.modes, { follow: true, active: false, shadowing: false, dictation: false });
}

/* --- wordTokens: one token per space-delimited word, punctuation kept inside it, the looked-up
   word the token with that punctuation stripped (the frame's own `seg.words`) --- */
{
  const line = "With the big bang starting the year and as cheering new year's eve, one year later.";
  const tokens = wordTokens(line);
  assert.deepEqual(tokens.slice(0, 4).map((token) => token.text), ['With', 'the', 'big', 'bang']);
  const eve = tokens.find((token) => token.text === 'eve,');
  assert.equal(eve.core, 'eve', 'trailing punctuation stays in the token but not in the word looked up');
  assert.ok(tokens.some((token) => token.core === "year's"), 'an apostrophe inside a word stays part of the word');
  for (const token of tokens) assert.equal(line.slice(token.start, token.end), token.text, 'offsets index the real line (word timing is expressed in them)');
  assert.deepEqual(wordTokens('   '), []);
}

/* --- hanTokens against the REAL zh capture: the backend's reading lists the Han characters in order
   and nothing else, so a Latin run and punctuation in the line are still drawn --- */
{
  const seg = zh.transcript.segments[0];
  const aligned = zh.catalog.pinyin_chars_by_segment[seg.segment_id];
  assert.ok(aligned.length >= 1);
  assert.ok(aligned.length < [...seg.original_text].length, 'the alignment is Han-only (and this capture is trimmed): shorter than the whole line');
  const tokens = hanTokens(seg.original_text, aligned);
  const han = tokens.filter((token) => /\p{Script=Han}/u.test(token.core));
  assert.ok(han.length > aligned.length, 'the line has more Han characters than the trimmed reading names');
  assert.ok(aligned.every((entry, i) => han[i].text === entry.char && han[i].pinyin === entry.pinyin), 'every Han character the reading names carries it, in order');
  assert.ok(han.slice(aligned.length).every((token) => token.pinyin === ''), 'a character the reading does not name gets none, never a guess');
  assert.ok(tokens.some((token) => token.core === 'Vector' && token.pinyin === ''), 'a Latin run inside a Chinese line is one tappable word, with no invented reading');
  assert.ok(tokens.some((token) => token.text === '(' && token.core === ''), 'punctuation is drawn and inert');
  assert.equal(tokens.map((token) => token.text).join(''), seg.original_text.replace(/\s+/gu, ''), 'nothing is dropped or reordered');
  for (const token of tokens) assert.equal(seg.original_text.slice(token.start, token.end), token.text);
  const bare = hanTokens('你好', null);
  assert.deepEqual(bare.map((token) => [token.text, token.pinyin]), [['你', ''], ['好', '']], 'no alignment: a real character with no invented reading (rule 40)');
  const wrong = hanTokens('你好', [{ char: '们', pinyin: 'men' }]);
  assert.deepEqual(wrong.map((token) => token.pinyin), ['', ''], 'a reading that does not match its character is never applied');
}

/* --- the word marked while playing: the frame's estimate, and real timing when the asset has it --- */
{
  const tokens = wordTokens('aa bbbb cc');
  assert.equal(estimatedTokenIndex(tokens, 0), 0);
  assert.equal(estimatedTokenIndex(tokens, 0.2), 0, 'weights are length + 1: "aa" owns the first 3/12');
  assert.equal(estimatedTokenIndex(tokens, 0.3), 1);
  assert.equal(estimatedTokenIndex(tokens, 0.99), 2);
  assert.equal(estimatedTokenIndex(tokens, 5), 2, 'clamped');
  assert.equal(estimatedTokenIndex([], 0.5), -1);
  const seg = { start_ms: 1000, end_ms: 5000, original_text: 'aa bbbb cc' };
  assert.equal(currentTokenIndex(seg, tokens, 1000), -1, 'segment timing does not prove word timing');
  assert.equal(currentTokenIndex(seg, tokens, 3400), -1);
  assert.equal(currentTokenIndex(seg, tokens, 999), -1, 'outside the segment nothing is marked');
  assert.equal(currentTokenIndex(seg, tokens, 5000), -1);
  const timed = { ...seg, words: [
    { text: 'aa', start_ms: 1000, end_ms: 1500 }, { text: 'bbbb', start_ms: 1600, end_ms: 4000 }, { text: 'cc', start_ms: 4100, end_ms: 4900 },
  ] };
  assert.equal(currentTokenIndex(timed, tokens, 1200), 0, 'real timing wins over the estimate');
  assert.equal(currentTokenIndex(timed, tokens, 1550), -1, 'a real pause between words is not the previous word continuing');
  assert.equal(currentTokenIndex(timed, tokens, 4500), 2);
  const mismatched = { ...seg, words: [{ text: 'zz', start_ms: 1000, end_ms: 2000 }] };
  assert.equal(currentTokenIndex(mismatched, tokens, 1200), -1, 'mismatched timing must never invent a word position');
}

/* --- the frame's mode, row and line-step rules --- */
{
  // The frame's `bg: isSel ? accent-soft : isCur ? tint2`: the selected line wins the ground even
  // while it is the line being played (a tap in Active mode selects and plays it).
  assert.equal(rowTone({ isCurrent: true, isSelected: true, endMs: 1, timeMs: 5 }), 'selected');
  assert.equal(rowTone({ isCurrent: true, isSelected: false, endMs: 1, timeMs: 5 }), 'current');
  assert.equal(rowTone({ isCurrent: false, isSelected: true, endMs: 1, timeMs: 5 }), 'selected');
  assert.equal(rowTone({ isCurrent: false, isSelected: false, endMs: 4000, timeMs: 5000 }), 'past');
  assert.equal(rowTone({ isCurrent: false, isSelected: false, endMs: 9000, timeMs: 5000 }), 'future');
  assert.equal(modeHintKey('follow'), 'hintFollow');
  assert.equal(modeHintKey('active'), 'hintActive');
  assert.equal(selectionAfterModeChange('active', 'seg:2'), 'seg:2', 'Active selects the line being played');
  assert.equal(selectionAfterModeChange('active', null), null);
  assert.equal(selectionAfterModeChange('follow', 'seg:2'), null, 'Follow clears the selection');
  const segs = [{ start_ms: 0 }, { start_ms: 5000 }, { start_ms: 9000 }];
  assert.equal(previousIndex(segs, 1, 6500), 1, 'past the first second of a line, previous restarts it');
  assert.equal(previousIndex(segs, 1, 5800), 0, 'within the first second it goes back one');
  assert.equal(previousIndex(segs, 0, 300), 0, 'never before the first line');
  assert.equal(nextIndex(segs, 1), 2);
  assert.equal(nextIndex(segs, 2), 2, 'never past the last line');
  assert.equal(previousIndex([], 0, 0), -1);
  assert.equal(nextIndex([], 0), -1);
}

/* --- Save phrase: the library's own vocabulary entry, in the shape the REAL route accepts --- */
{
  const source = readFileSync(new URL('../writing_coach/becoming_library.py', import.meta.url), 'utf8');
  const model = source.slice(source.indexOf('class LibraryVocabularyIn'), source.indexOf('class VocabularyReviewIn'));
  const maxWord = Number(/word: str = Field\(min_length=1, max_length=(\d+)\)/.exec(model)?.[1]);
  assert.equal(PHRASE_MAX, maxWord, "the phrase ceiling is the route's own `word` ceiling");
  const pattern = new RegExp(/pattern=r"([^"]+)"/.exec(model)[1]);
  const payload = phraseSavePayload('  With the big bang starting the year  ', { meaning: 'Với vụ nổ lớn' });
  assert.equal(payload.word, 'With the big bang starting the year');
  assert.equal(payload.definition, 'Với vụ nổ lớn');
  assert.ok(pattern.test(payload.source_kind), `source_kind ${payload.source_kind} must be one the real route accepts (a "listening" value is a 422)`);
  assert.equal(pattern.test('listening'), true, 'a word kept from Listening is saved as one (D-107): the route accepts "listening"');
  assert.equal(pattern.test('nonsense'), false, 'and still only the kinds it names');
  for (const key of Object.keys(payload)) assert.ok(model.includes(`${key}:`), `${key} is a field of LibraryVocabularyIn`);
  assert.equal(phraseSaveable('x'.repeat(PHRASE_MAX)), true);
  assert.equal(phraseSaveable('x'.repeat(PHRASE_MAX + 1)), false, 'a line longer than an entry can be is never truncated into a different phrase');
  assert.equal(phraseSaveable('   '), false);
  assert.equal(phraseSaved([{ word: 'Galaxy' }, { word: 'other' }], ' galaxy '), true, 'matched by text, case-insensitively');
  assert.equal(phraseSaved([{ word: 'other' }], 'galaxy'), false);
  assert.equal(phraseSaved(null, 'galaxy'), false);
}

/* --- vocabularyForSegment: real catalogue words matched into a real segment, plural-tolerant --- */
{
  const seg = en.transcript.segments.find((s) => s.original_text.includes('galax'));
  const hit = vocabularyForSegment(['galaxy', 'solar system', 'extinct'], seg.original_text);
  assert.deepEqual(hit, ['galaxy'], 'the plural "galaxies" still matches the catalogue\'s singular "galaxy"');
  assert.deepEqual(vocabularyForSegment(['extinct'], 'nothing relevant here'), []);
}

/* --- lookupContext: the line only when it really holds the term (the route answers 422 otherwise) --- */
{
  const line = 'The first stars formed and the first galaxies formed on the 9th';
  assert.equal(lookupContext('galaxies', line), line);
  assert.equal(lookupContext('Galaxies', line), line, 'case-insensitively');
  assert.equal(lookupContext('galaxy', line), 'galaxy', 'a catalogue term the line only inflects is its own valid context');
  assert.equal(lookupContext('', line), '');
}

/* --- placeFor: device-memory continuation, real content-id namespace --- */
{
  const continuation = [{ id: 'media:abc', segment: 'abc:002' }, { id: 'article:xyz', segment: 'p3' }];
  assert.deepEqual(placeFor(continuation, 'media:abc'), { segmentId: 'abc:002', started: true });
  assert.deepEqual(placeFor(continuation, 'media:none'), { segmentId: '', started: false });
  assert.deepEqual(placeFor(null, 'media:abc'), { segmentId: '', started: false }, 'no continuation array at all does not throw');
}

/* --- dictationLinesCompleted: only real checked/revealed evidence counts, never a "prompt" row --- */
{
  const items = [{ presentation: 'prompt' }, { presentation: 'checked' }, { presentation: 'revealed' }, {}];
  assert.equal(dictationLinesCompleted(items), 2);
  assert.equal(dictationLinesCompleted([]), 0);
  assert.equal(dictationLinesCompleted(null), 0);
}

/* --- pickNextRecommendation: a real other item, same real topic, never the current one --- */
{
  const items = [
    { lesson_id: 'en-science-cosmic-calendar', topic: 'science', title: 'This one' },
    { lesson_id: 'en-science-other', topic: 'science', title: 'Another science lesson', poster_url: '', duration_ms: 60000 },
    { lesson_id: 'en-travel-x', topic: 'travel', title: 'Unrelated' },
  ];
  const pick = pickNextRecommendation(items, 'en-science-cosmic-calendar', 'science');
  assert.equal(pick.lessonId, 'en-science-other');
  assert.equal(pick.minutes, 1);
  assert.equal(pick.topic, 'science', 'a same-topic pick may say why');
  const plain = pickNextRecommendation(items, 'en-travel-x', 'travel');
  assert.equal(plain.lessonId, 'en-science-cosmic-calendar', "no other lesson on the topic: the library's next lesson, still a real one");
  assert.equal(plain.topic, '', 'and it claims no reason it does not have');
  assert.equal(pickNextRecommendation(items, 'en-science-cosmic-calendar', '').topic, '', 'no real topic: no invented reason');
  assert.equal(pickNextRecommendation([{ lesson_id: 'only', topic: 'x' }], 'only', 'x'), null, 'the current lesson is never its own next');
  assert.equal(pickNextRecommendation([], 'en-science-cosmic-calendar', 'science'), null);
}

/* --- progress / seek / time-label / ended, over the real EN excerpt bounds --- */
{
  const start = 1000, end = 47000;
  assert.equal(progressPercent(1000, start, end), 0);
  assert.equal(progressPercent(47000, start, end), 100);
  assert.equal(Math.round(progressPercent(24000, start, end)), 50);
  assert.equal(progressPercent(NaN, start, end), 0);
  assert.equal(msAtSeekFraction(0.5, start, end), start + (end - start) * 0.5);
  assert.equal(msAtSeekFraction(-1, start, end), start, 'clamped, never before the excerpt start');
  assert.equal(msAtSeekFraction(2, start, end), end, 'clamped, never past the excerpt end');
  assert.equal(timeLabel(24000, start, end), '0:23 / 0:46');
  assert.equal(reachedEnd(46750, end), true, 'within one 125ms clock tick of the real end');
  assert.equal(reachedEnd(30000, end), false);
}

assert.equal(listenedMinutesLabel(75000), '1:15');
assert.equal(listenedMinutesLabel(0), '0:00', 'a real zero-length session is a real zero, not an omission');
assert.equal(listenedMinutesLabel(-1), null);
assert.equal(listenedMinutesLabel(NaN), null);

/* --- imported media opens through the same room (product/media-source.js) --- */
{
  const { mediaRef, openMedia } = await import('../static/orena/product/media-source.js');
  const { primaryLanguage } = await import('../static/orena/screens/listening/model.js');
  assert.deepEqual(mediaRef('url:https://www.youtube.com/watch?v=abc'), { kind: 'url', value: 'https://www.youtube.com/watch?v=abc' });
  assert.deepEqual(mediaRef('upload:upload-1f'), { kind: 'upload', value: 'upload-1f' });
  assert.deepEqual(mediaRef('upload-1f'), { kind: 'lesson', value: 'upload-1f' }, 'a bare stored media id resolves through the library route');
  assert.deepEqual(mediaRef('en-science-cosmic-calendar'), { kind: 'lesson', value: 'en-science-cosmic-calendar' });

  const calls = [];
  const acquired = { asset: { asset_id: 'youtube:abc', title: 'Clip', source_language: 'en-GB', duration_ms: 61000, thumbnail_url: 'https://img/x.jpg' }, playback: { kind: 'youtube', url: 'https://www.youtube.com/embed/abc' }, transcript: { segments: [] }, translations: [] };
  const api = {
    importMedia: async (body) => { calls.push(['import', body.source_url, body.target_language]); return acquired; },
    mediaImportStatus: async () => { throw new Error('not resumable'); },
    mediaMy: async (id) => { calls.push(['my', id]); return { asset: { asset_id: id }, playback: { kind: 'audio' } }; },
    listeningLibraryLesson: async (id, support) => { calls.push(['lesson', id, support]); return { asset: { asset_id: id } }; },
  };
  const storage = { getItem: () => null, setItem() {}, removeItem() {} };
  globalThis.localStorage = storage;
  assert.equal(await openMedia('url:https://youtu.be/abc', { api, support: 'vi', language: 'en' }), acquired);
  await openMedia('upload:upload-1f', { api, support: 'vi', language: 'en' });
  await openMedia('upload-1f', { api, support: 'vi', language: 'en' });
  await openMedia('en-x', { api, support: 'vi', language: 'en' });
  assert.deepEqual(calls, [
    ['import', 'https://youtu.be/abc', 'vi'],
    ['my', 'upload-1f'],
    ['lesson', 'upload-1f', 'vi'],
    ['lesson', 'en-x', 'vi'],
  ]);
  await assert.rejects(() => openMedia('url:', { api }), /No media id/);

  /* A provider acquisition has no catalog: the room maps from the asset, the poster falls back to
     the asset's thumbnail, and the provider's regional tag does not decide the language. */
  const mapped = mapLesson(acquired);
  assert.equal(mapped.language, 'en');
  assert.equal(mapped.title, 'Clip');
  assert.equal(mapped.posterUrl, 'https://img/x.jpg');
  assert.equal(mapped.durationMs, 61000);
  const unmeasured = mapLesson({ ...acquired, asset: { ...acquired.asset, duration_ms: null }, transcript: { segments: [{ segment_id: 'a', start_ms: 1200, end_ms: 3360 }, { segment_id: 'b', start_ms: 16881, end_ms: 18881 }] } });
  assert.equal(unmeasured.durationMs, null, 'rule 40: a length the provider did not report is not "0 min"');
  assert.equal(minutesFrom(unmeasured.durationMs), null);
  assert.equal(unmeasured.excerptEndMs, 18881, 'the clip of a provider source ends where its last line does');
  assert.equal(mapLesson({ ...acquired, asset: { ...acquired.asset, duration_ms: null } }).excerptEndMs, null, 'no transcript, no length: no invented end');
  assert.equal(mapped.modes.follow, true);
  assert.equal(mapped.modes.dictation, false, 'no catalog modes: only Follow, nothing invented');
  assert.equal(timeLabel(3000, 0, 0), '0:03', 'no measured length: the elapsed time stands alone, never "/ 0:00"');
  assert.equal(timeLabel(3000, 0, null), '0:03');
  assert.equal(reachedEnd(0, 0), false, 'an unmeasured end is not an end: the end-of-media card must not open at once');
  assert.equal(reachedEnd(0, null), false);
  assert.equal(mapLesson({ asset: { source_language: 'und', title: 'x' } }, { fallbackLanguage: 'zh' }).language, 'zh', 'a provider that cannot tell the language leaves it to the learner own');
  assert.equal(primaryLanguage('zh-CN'), 'zh');
  assert.equal(primaryLanguage('zh'), 'zh');
  assert.equal(primaryLanguage(''), 'en');
}

console.log('test_orena_screen_listening.mjs: Listening Workspace data mapping - real GET /api/listening/library/{id} captures (en+zh), rule 40 throughout: PASS');
