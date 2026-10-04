/* Gate for Scripted Pronunciation's pure data mapping (static/orena/screens/speak/model.js), the
   shared source resolution all four Speaking screens use (static/orena/product/speaking-source.js),
   the take store's views (static/orena/product/take-store.js) and the recorder that turns a take
   into an attempt exactly once (static/orena/product/speaking-recorder.js). Imports only DOM-free
   modules.

   Real payloads: `scripts/fixtures/api/listening_library_lesson.en.json`/`.zh.json` (captured,
   `GET /api/listening/library/{lessonId}`) and `scripts/fixtures/api/speaking_item.json` (the
   Speaking catalogue ships empty in this sandbox - built from `speaking_library.py`'s own
   serializer, see the fixtures README's "Built from the serializer" section). The
   `score_kind:"measured"` pronunciation shape (no speech provider here) is built inline from
   `writing_coach/speech_api.py`'s own response dict, same reasoning. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  scoreBand, scoreInk, bandInk, ringBand, ringTone, verdictKey, tokenStrip, tipFor, detailFor, metricsFor, recorderState,
  recCaptionKey, micStateFor, attemptOrdinal, clockLabel, restingWave, liveWave, whenLabel, WAVE_BARS,
} from '../static/orena/screens/speak/model.js';
import { parseSpeakingId, segmentOf, sourceFromCatalogItem, sourceFromLesson, loadSpeakingSource } from '../static/orena/product/speaking-source.js';
import { pronunciationView } from '../static/orena/capabilities/pronunciation-result.js';
import { recordTake, richView, viewOfTake, noteAttemptId, attemptIdOf, lineKey, listTakes, setTakeStoreScope } from '../static/orena/product/take-store.js';
import { createSpeakingRecorder, TAKE } from '../static/orena/product/speaking-recorder.js';
import { readSpeakingSession, setSpeakingSessionScope } from '../static/orena/product/speaking-session.js';

function fixture(name) {
  return JSON.parse(readFileSync(new URL(`./fixtures/api/${name}`, import.meta.url)));
}

/* --- The three colour rules frame 15 draws, each with its own thresholds --- */
assert.equal(scoreBand(85), 'good');
assert.equal(scoreBand(84), 'ok');
assert.equal(scoreBand(65), 'ok');
assert.equal(scoreBand(64), 'weak');
assert.equal(scoreInk(90), 'var(--green)');
assert.equal(scoreInk(70), 'var(--amber)');
assert.equal(scoreInk(10), 'var(--red)');
assert.equal(bandInk('ok'), 'var(--amber)');
assert.equal(ringBand(85), 'good');
assert.equal(ringBand(70), 'ok');
assert.equal(ringBand(69), 'weak');
assert.deepEqual(ringTone(90), { bg: 'var(--green-soft)', ink: 'var(--green)' });
assert.deepEqual(ringTone(75), { bg: 'var(--accent-soft)', ink: 'var(--accent)' });
assert.deepEqual(ringTone(10), { bg: 'var(--amber-soft)', ink: 'var(--amber)' });
assert.equal(verdictKey(85), 'verdictClear');
assert.equal(verdictKey(70), 'verdictUnderstandable');
assert.equal(verdictKey(69), 'verdictNeedsWork');

/* --- A real pronunciation result (built field-for-field from speech_api.py, no provider here) --- */
const RESULT = {
  score_kind: 'measured', mode: 'scripted', reference_text: 'Could I get a coffee, please?',
  recognized_text: 'Could I get a coffee please',
  pron_score: 82, accuracy_score: 80, fluency_score: 88, completeness_score: 95, prosody_score: 70,
  words: [
    { word: 'Could', accuracy_score: 92, error_type: 'None', offset_ms: 0, duration_ms: 300, phonemes: [], syllables: [] },
    { word: 'I', accuracy_score: 95, error_type: 'None', offset_ms: 320, duration_ms: 120, phonemes: [], syllables: [] },
    { word: 'get', accuracy_score: 90, error_type: 'None', offset_ms: 460, duration_ms: 200, phonemes: [], syllables: [] },
    { word: 'a', accuracy_score: 96, error_type: 'None', offset_ms: 680, duration_ms: 80, phonemes: [], syllables: [] },
    {
      word: 'coffee', accuracy_score: 52, error_type: 'Mispronunciation', offset_ms: 780, duration_ms: 420,
      phonemes: [{ phoneme: 'k', accuracy_score: 80 }, { phoneme: 'f', accuracy_score: 40 }], syllables: [],
    },
    { word: 'please', accuracy_score: 88, error_type: 'None', offset_ms: 1220, duration_ms: 300, phonemes: [], syllables: [] },
  ],
};
const view = pronunciationView(RESULT, { language: 'en', readings: [], modelSpanMs: 1600 });
assert.equal(view.measured, true);

/* --- tokenStrip: no result yet -> no band on any token --- */
{
  const tokens = tokenStrip('Could I get a coffee, please?', 'en', pronunciationView(null));
  assert.ok(tokens.every((unit) => unit.band == null && unit.wordIndex == null));
  assert.ok(tokens.some((unit) => unit.unit && unit.text === 'coffee'));
}
/* --- tokenStrip: a result places each word's band (green / amber / red, `scoreColor`) --- */
{
  const tokens = tokenStrip('Could I get a coffee, please?', 'en', view);
  const coffee = tokens.find((unit) => unit.text === 'coffee');
  assert.equal(coffee.band, 'weak', 'accuracy_score 52 < 65');
  assert.equal(coffee.flagged, true);
  assert.equal(bandInk(coffee.band), 'var(--red)');
  const please = tokens.find((unit) => unit.text === 'please');
  assert.equal(please.band, 'good', 'accuracy_score 88 >= 85');
  // A word between the two lines is amber.
  const mid = pronunciationView({ ...RESULT, words: [{ ...RESULT.words[0], accuracy_score: 70 }] }, { language: 'en' });
  assert.equal(tokenStrip('Could', 'en', mid).find((unit) => unit.unit).band, 'ok');
}

/* --- tipFor: the worst flagged word, with its weakest measured unit --- */
{
  assert.equal(tipFor(pronunciationView(null)), null, 'nothing attempted yet');
  const tip = tipFor(view);
  assert.equal(tip.word, 'coffee');
  assert.equal(tip.errorType, 'Mispronunciation');
  assert.deepEqual(tip.weakest, { label: 'f', score: 40 });
  const clean = pronunciationView({ ...RESULT, words: RESULT.words.slice(0, 2) }, { language: 'en' });
  assert.equal(tipFor(clean), null, 'nothing flagged: no coaching line is invented');
}

/* --- detailFor --- */
{
  assert.equal(detailFor(view, 99), null, 'no such word');
  const detail = detailFor(view, 4);
  assert.equal(detail.word, 'coffee');
  assert.equal(detail.score, 52);
  assert.equal(detail.ink, 'var(--red)');
}

/* --- metricsFor: Accuracy / Fluency / Completeness; unsupported fluency remains unavailable --- */
{
  assert.deepEqual(metricsFor(pronunciationView(null)), [], 'nothing measured: no cells');
  const measured = metricsFor(view);
  assert.deepEqual(measured.map((m) => m.key), ['accuracy', 'fluency', 'completeness']);
  assert.deepEqual(measured.map((m) => m.value), [80, 88, 95]);
  const noFluency = metricsFor(pronunciationView({ ...RESULT, fluency_score: null }, { language: 'en' }));
  assert.equal(noFluency.find((m) => m.key === 'fluency').value, null, 'an unsupported provider metric is unavailable, never a measured zero');
  assert.equal(noFluency.find((m) => m.key === 'fluency').ink, 'var(--muted)', 'unavailable metrics must not encode a poor score');
  assert.equal(metricsFor({ measured: true, reduced: true, overall: 70 }).length, 0, 'a reopened attempt knows only its overall score');
}

/* --- recorderState / caption / micStateFor --- */
assert.equal(recorderState('recording').key, 'recording');
assert.equal(recorderState('processing').key, 'scoring');
assert.equal(recorderState('result').key, 'ready', 'frame 15 has no separate "assessed" state');
assert.equal(recorderState('idle').key, 'ready');
assert.equal(recCaptionKey('idle', false), 'captionIdle');
assert.equal(recCaptionKey('result', true), 'captionAgain');
assert.equal(recCaptionKey('recording', false), 'captionRecording');
assert.equal(recCaptionKey('processing', false), '', 'the pill already says so');
assert.equal(micStateFor('no_speech'), 'notheard');
assert.equal(micStateFor('too_short'), 'notheard');
assert.equal(micStateFor('offline'), 'offline');
assert.equal(micStateFor('unavailable'), 'provider');
assert.equal(micStateFor('service'), 'provider');

/* --- attemptOrdinal: takes are newest-first, "Attempt N" counts from the oldest --- */
{
  const takes = [{ id: 'c' }, { id: 'b' }, { id: 'a' }];
  assert.equal(attemptOrdinal(takes, 'a'), 1, 'the oldest take is Attempt 1');
  assert.equal(attemptOrdinal(takes, 'c'), 3, 'the newest is Attempt 3');
  assert.equal(attemptOrdinal(takes, 'missing'), 3, 'not found: falls back to "just recorded" (the length)');
}

/* --- clock, wave, "Today 08:05" --- */
assert.equal(clockLabel(0), '00:00');
assert.equal(clockLabel(65_400), '01:05');
assert.equal(restingWave().length, WAVE_BARS);
assert.ok(restingWave().every((h) => h >= 25 && h <= 100));
assert.equal(liveWave([0, 0.5, 2, -1]).slice(0, 4).join(','), '6,50,100,6', 'a level is clamped to 0-1 and never a bar under 6%');
assert.equal(liveWave([]).length, WAVE_BARS);
{
  const noon = new Date(2026, 8, 28, 12, 0, 0).getTime();
  assert.match(whenLabel(noon, 'en', noon), /^Today /);
  assert.match(whenLabel(noon - 3 * 86_400_000, 'en', noon), /Sep/, 'an older day shows its date instead');
}

/* --- parseSpeakingId / segmentOf --- */
assert.deepEqual(parseSpeakingId('speak:demo-cafe-order'), { kind: 'speak', rawId: 'demo-cafe-order' });
assert.deepEqual(parseSpeakingId('media:en-daily-pen-in-my-bag'), { kind: 'media', rawId: 'en-daily-pen-in-my-bag' });
{
  const bare = parseSpeakingId('commons-royalsociety-cosmic-calendar');
  assert.equal(bare.kind, 'media');
  assert.equal(bare.unprefixed, true, 'a bare id (Progress\'s own assetId link) is tried as a lesson id, recorded as a cross-screen gap, not silently dropped');
}
assert.equal(segmentOf(new URLSearchParams('segment=abc:003')), 'abc:003');
assert.equal(segmentOf(new URLSearchParams('')), '');
assert.equal(segmentOf(null), '');

/* --- sourceFromCatalogItem against the real (serializer-built) catalogue item shape --- */
{
  const item = fixture('speaking_item.json');
  const source = sourceFromCatalogItem(item, 'vi');
  assert.equal(source.sourceId, 'speak:demo-cafe-order');
  assert.equal(source.hasModelAudio, false, 'the authored catalogue carries no recorded model line');
  assert.equal(source.modelAudioUrl, null);
  assert.equal(source.line.text, 'Could I get a coffee, please?');
  assert.equal(source.line.meaning, item.lines[0].translations.vi, 'the caller\'s own support language picks the translation');
  assert.equal(source.line.lineId, 'speak:demo-cafe-order:1');
  assert.equal(source.line.ordinal, 1);
}
{
  // A caller whose support language has no translation on this line gets no meaning, not English.
  const item = fixture('speaking_item.json');
  const source = sourceFromCatalogItem(item, 'ja');
  assert.equal(source.line.meaning, '');
}

/* --- sourceFromLesson against the real captured payload: `catalog.spoken_text_by_segment`,
   never a `segment.spoken_text` field this payload does not carry --- */
{
  const payload = fixture('listening_library_lesson.en.json');
  const segment = payload.transcript.segments[0];
  assert.ok(!('spoken_text' in segment), 'this payload\'s segment truly has no spoken_text field - the fixture, not a stale assumption');
  const source = sourceFromLesson('en-science-cosmic-calendar', payload);
  assert.equal(source.sourceId, 'media:en-science-cosmic-calendar');
  assert.equal(source.hasModelAudio, true, 'a video/audio playback lesson has a real model line');
  assert.equal(typeof source.modelAudioUrl, 'function');
  assert.equal(source.modelAudioUrl(source.line.lineId), `/api/speaking/model-audio/en-science-cosmic-calendar/${encodeURIComponent(source.line.lineId)}`);
  assert.equal(source.line.lineId, segment.segment_id);
  assert.equal(source.line.ordinal, 1);
  assert.equal(source.line.text, payload.catalog.spoken_text_by_segment[segment.segment_id] || segment.original_text);
  assert.equal(source.line.startMs, segment.start_ms);
  assert.equal(source.line.endMs, segment.end_ms);
  // A link that names a segment gets that line, with its own place in the transcript.
  const later = payload.transcript.segments[2];
  if (later) {
    const named = sourceFromLesson('en-science-cosmic-calendar', payload, later.segment_id);
    assert.equal(named.line.lineId, later.segment_id);
    assert.equal(named.line.ordinal, 3);
  }
  // A missing named segment must not silently open a different sentence.
  assert.equal(sourceFromLesson('en-science-cosmic-calendar', payload, 'no-such-segment'), null);
}

/* --- loadSpeakingSource: a fake api, both id shapes, and the language gate --- */
{
  const item = fixture('speaking_item.json');
  const fakeApi = { speakingItem: async () => item };
  const source = await loadSpeakingSource('speak:demo-cafe-order', { api: fakeApi, support: 'vi', language: 'en' });
  assert.equal(source.sourceId, 'speak:demo-cafe-order');
  await assert.rejects(() => loadSpeakingSource('speak:demo-cafe-order', { api: fakeApi, support: 'vi', language: 'zh' }), /unavailable/, 'the source is English; a Chinese-learning session cannot practise it');
}
{
  const payload = fixture('listening_library_lesson.zh.json');
  const fakeApi = { listeningLibraryLesson: async () => payload };
  const source = await loadSpeakingSource('media:whatever', { api: fakeApi, support: 'en', language: 'zh' });
  assert.equal(source.language, 'zh');
  await assert.rejects(() => loadSpeakingSource('media:whatever', { api: fakeApi, support: 'en', language: 'en' }), /unavailable/);
}

/* --- A bare id from Progress's evidence rows is a media object id, found in the library --- */
{
  const payload = fixture('listening_library_lesson.en.json');
  const asked = [];
  const fakeApi = {
    listeningLibraryLesson: async (id) => {
      asked.push(id);
      if (id !== 'en-science-cosmic-calendar') throw Object.assign(new Error('missing'), { status: 404 });
      return payload;
    },
    listeningLibrary: async () => ({ items: [{ lesson_id: 'en-science-cosmic-calendar', media_object_id: 'commons-royalsociety-cosmic-calendar' }] }),
  };
  const source = await loadSpeakingSource('commons-royalsociety-cosmic-calendar', { api: fakeApi, support: 'vi', language: 'en' });
  assert.equal(source.sourceId, 'media:en-science-cosmic-calendar', 'the same key every other entry point uses, so the takes are shared');
  assert.deepEqual(asked, ['en-science-cosmic-calendar'], 'the media object id never costs a failed request');
  const direct = await loadSpeakingSource('en-science-cosmic-calendar', { api: fakeApi, support: 'vi', language: 'en' });
  assert.equal(direct.sourceId, 'media:en-science-cosmic-calendar', 'a bare lesson id answers directly');
  await assert.rejects(() => loadSpeakingSource('no-such-media', { api: fakeApi, support: 'vi', language: 'en' }), /missing/, 'an id that is neither is the lesson-load error, not a guess');
  // A prefixed id never goes looking in the library.
  await assert.rejects(() => loadSpeakingSource('media:commons-royalsociety-cosmic-calendar', { api: fakeApi, support: 'vi', language: 'en' }), /missing/);
}

/* --- The take store: a reopened attempt is shown as the smaller thing it is --- */
{
  const key = lineKey('media:test-lesson', 'seg-1');
  const saved = await recordTake(key, { blob: null, ms: 1500, view });
  assert.ok(saved.take_ref.startsWith(`${key}::`));
  assert.equal(saved.list.length, 1);
  assert.equal(richView(saved.take_ref), view);
  const listed = await listTakes(key);
  const full = viewOfTake(listed[0]);
  assert.equal(full.reduced, false, 'this tab still holds the full assessment');
  assert.equal(full.words[4].scoreKnown, true);
  assert.equal(full.completeness, 95);
  // The same attempt without the in-memory assessment (a visit later, from IndexedDB retention).
  const reopened = viewOfTake({ id: 'gone', overall: 82, flagged: 1, words: [{ text: 'coffee', flagged: true, offsetMs: 780, durationMs: 420 }, { text: 'please', flagged: false }] });
  assert.equal(reopened.reduced, true);
  assert.equal(reopened.overall, 82);
  assert.equal(reopened.accuracy, null, 'not kept, so not shown as a number');
  assert.equal(reopened.words[0].scoreKnown, false);
  assert.equal(reopened.words[0].offsetKnown, true);
  assert.equal(reopened.passedCount, 1);
  assert.equal(viewOfTake(null), null);
  // Reopened words are marked by the flag alone, never by a score they do not have.
  const tokens = tokenStrip('coffee please', 'en', reopened);
  assert.equal(tokens.find((u) => u.text === 'coffee').band, 'ok', 'flagged, no score: amber');
  assert.equal(tokens.find((u) => u.text === 'please').band, 'good');
  // The server's record id lands after the result does.
  assert.equal(attemptIdOf(saved.take_ref), '');
  noteAttemptId(saved.take_ref, 'attempt-77');
  assert.equal(attemptIdOf(saved.take_ref), 'attempt-77');
  noteAttemptId(saved.take_ref, '');
  assert.equal(attemptIdOf(saved.take_ref), 'attempt-77', 'an empty id never erases a real one');
}

/* --- The recorder: a finished take becomes ONE attempt (the take emits its result twice) --- */
{
  setTakeStoreScope('account-a:en');
  const key = lineKey('media:shared', 'line');
  await recordTake(key, { blob: null, ms: 1500, view });
  setTakeStoreScope('account-b:en');
  assert.deepEqual(await listTakes(lineKey('media:shared', 'line')), [], 'another account cannot read retained takes');
  setTakeStoreScope('account-a:zh');
  assert.deepEqual(await listTakes(lineKey('media:shared', 'line')), [], 'another learning language has its own takes');
  setTakeStoreScope('account-a:en');
  assert.equal((await listTakes(lineKey('media:shared', 'line'))).length, 1);
  setTakeStoreScope('');
}
{
  const store = new Map();
  globalThis.window = { sessionStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) } };
  let clock = 0;
  const kept = [];
  const api = {
    assessPronunciation: async (blob, language, line) => ({ ...RESULT, reference_text: line }),
    evaluateSpeaking: async () => ({}),
    saveSpeakingAttempt: async (payload) => (kept.push(payload), { item: { id: 'server-attempt-1' } }),
  };
  const fakeRecorder = { start: async () => true, stop: async () => ({ blob: new Blob(['x'.repeat(4000)]), url: 'blob:r' }), cleanup() {}, discard() {}, snapshot: () => ({}) };
  const source = sourceFromLesson('rec-lesson', fixture('listening_library_lesson.en.json'));
  setSpeakingSessionScope('test-account:en');
  const key = lineKey(source.sourceId, source.line.lineId);
  const seen = [];
  const failures = [];
  const recorder = createSpeakingRecorder({
    api, source, key, language: 'en',
    facts: (finished) => [{ label: 'Accuracy', value: finished.accuracy }],
    on: { change: (snap) => seen.push(snap), failure: (error) => failures.push(error) },
    deps: { createRecorder: () => fakeRecorder, watchMic: () => ({ stop() {} }), now: () => clock, urls: { createObjectURL: () => 'blob:take', revokeObjectURL() {} } },
  });
  await recorder.start();
  assert.equal(recorder.phase, TAKE.RECORDING);
  assert.equal(recorder.busy, true);
  clock = 1500;
  await recorder.stop();
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.ok(seen.filter((snap) => snap.phase === TAKE.RESULT).length >= 2, 'the take really does report its result twice (the save of its record is the second)');
  const takes = await listTakes(key);
  assert.equal(takes.length, 1, 'one recording, one attempt - not two');
  assert.equal(readSpeakingSession().filter((entry) => entry.contentId === source.sourceId).length, 1, 'and one task in the session ledger');
  assert.equal(readSpeakingSession().find((entry) => entry.contentId === source.sourceId).attemptId, 'server-attempt-1', 'the ledger joins the server by identity');
  const finished = seen.at(-1).latest;
  assert.equal(finished.list.length, 1);
  assert.equal(finished.view.overall, 82);
  assert.equal(finished.view.heard, 'Could I get a coffee please');
  assert.equal(attemptIdOf(finished.take_ref), 'server-attempt-1', 'the server record\'s id is kept for Ask Orena\'s attempt_id');
  assert.equal(kept.length, 1);
  assert.deepEqual(failures, []);
  assert.equal(recorder.phase, TAKE.RESULT);
  recorder.dispose();
  delete globalThis.window;
}
{
  // A failure is reported once, and says whose it is.
  let clock = 0;
  const api = { assessPronunciation: async () => { throw Object.assign(new Error('x'), { category: 'pronunciation_no_speech' }); } };
  const fakeRecorder = { start: async () => true, stop: async () => ({ blob: new Blob(['x'.repeat(4000)]), url: 'blob:r' }), cleanup() {}, discard() {}, snapshot: () => ({}) };
  const source = sourceFromLesson('rec-lesson-2', fixture('listening_library_lesson.en.json'));
  const failures = [];
  const recorder = createSpeakingRecorder({
    api, source, key: lineKey(source.sourceId, source.line.lineId), language: 'en',
    on: { failure: (error) => failures.push(error) },
    deps: { createRecorder: () => fakeRecorder, watchMic: () => ({ stop() {} }), now: () => clock, urls: { createObjectURL: () => 'blob:take', revokeObjectURL() {} } },
  });
  await recorder.start();
  clock = 1500;
  await recorder.stop();
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.deepEqual(failures, [{ kind: 'no_speech', retry: false }]);
  recorder.dispose();
}

console.log('test_orena_screen_speak.mjs: Scripted Pronunciation data mapping, shared speaking-source resolution, take-store views and the one-attempt-per-take recorder - real backend contracts, rule 40 throughout: PASS');
