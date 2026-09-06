// The real-media Listening slice: a curated video lesson has to reach the
// learner through the SAME canonical player and media object the audio and
// YouTube lessons use. These assertions exist so a future change cannot quietly
// grow a second curated-media implementation, and cannot let a poster or a
// playback URL point somewhere the rights review never covered.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {mediaPlayer, playbackAvailable} from '../static/orena/capabilities/media-player.js';

const manifest = JSON.parse(readFileSync(new URL('../writing_coach/content/listening_catalog.v1.json', import.meta.url), 'utf8'));
const sources = new Map(manifest.sources.map(source => [source.source_media_id, source]));

const REAL_VIDEO_LESSONS = ['en-science-cosmic-calendar', 'zh-technology-search-wikipedia'];

// --- The catalog carries real, rights-reviewed video, not a text placeholder ---
for (const lessonId of REAL_VIDEO_LESSONS) {
  const lesson = manifest.lessons.find(item => item.lesson_id === lessonId);
  assert.ok(lesson, `${lessonId} is missing from the catalog`);
  const source = sources.get(lesson.source_media_id);
  assert.ok(source, `${lessonId} has no source media`);

  assert.equal(source.playback.kind, 'video', `${lessonId} must be real video`);
  assert.equal(source.playback.provider, 'wikimedia-commons');
  assert.match(source.playback.url, /^https:\/\/upload\.wikimedia\.org\/.+\.webm$/);
  assert.match(source.poster_url, /^https:\/\/thumb\.wikimedia\.org\/.+\.jpg$/);

  // Rights and provenance stay attached to the canonical media object.
  assert.equal(source.rights.review_status, 'verified');
  assert.ok(source.rights.license_name && source.rights.license_url);
  assert.match(source.rights.provenance_url, /^https:\/\/commons\.wikimedia\.org\/wiki\/File:/);

  // Truthful timings: every segment sits inside the real source duration, in
  // order, and the excerpt is a real range rather than the whole file by default.
  assert.ok(source.duration_ms > 0);
  let previousEnd = -1;
  for (const segment of source.segments) {
    assert.ok(segment.start_ms >= previousEnd, `${lessonId} segments overlap`);
    assert.ok(segment.end_ms > segment.start_ms);
    assert.ok(segment.end_ms <= source.duration_ms, `${lessonId} segment runs past the source`);
    assert.ok(segment.original_text.trim().length > 0);
    previousEnd = segment.end_ms;
  }
  assert.ok(lesson.excerpt_end_ms > lesson.excerpt_start_ms);
  assert.ok(lesson.excerpt_end_ms <= source.duration_ms);


}

// --- English and Chinese are both represented by real video ---
const languages = REAL_VIDEO_LESSONS.map(id => {
  const lesson = manifest.lessons.find(item => item.lesson_id === id);
  return sources.get(lesson.source_media_id).language;
});
assert.deepEqual([...languages].sort(), ['en', 'zh'], 'the real slice must cover EN and ZH');

// --- One player renders it, and it renders a real <video> with a poster ---
const en = sources.get('commons-royalsociety-cosmic-calendar');
assert.equal(playbackAvailable(en.playback), true);
const html = mediaPlayer(en.playback, 'The cosmic calendar', {startMs: 1000, endMs: 47000, poster: en.poster_url});
assert.match(html, /^<video id="orenaMedia"/);
assert.match(html, /poster="https:\/\/thumb\.wikimedia\.org\//);
assert.match(html, /data-excerpt-start-ms="1000" data-excerpt-end-ms="47000"/);
assert.match(html, /playsinline/);
assert.doesNotMatch(html, /<iframe/);

// --- A poster may never escape the reviewed origins ---
// Credentials, a port and a lookalike suffix all survive a naive host check,
// so each is named. The server and the native adapter apply the same list.
for (const hostile of [
  'https://evil.example/poster.jpg',
  'http://upload.wikimedia.org/poster.jpg',
  'javascript:alert(1)',
  'https://user:password@upload.wikimedia.org/poster.jpg',
  'https://upload.wikimedia.org:8443/poster.jpg',
  'https://upload.wikimedia.org.evil.example/poster.jpg',
]) {
  assert.doesNotMatch(
    mediaPlayer(en.playback, 'T', {poster: hostile}),
    /poster=/,
    `poster from ${hostile} must be dropped`,
  );
}

// --- A video playback URL off the reviewed hosts is not playable at all ---
for (const hostile of [
  {provider: 'wikimedia-commons', kind: 'video', url: 'https://evil.example/x.webm'},
  {provider: 'evil', kind: 'video', url: 'https://upload.wikimedia.org/x.webm'},
  {provider: 'wikimedia-commons', kind: 'video', url: 'http://upload.wikimedia.org/x.webm'},
  {provider: 'wikimedia-commons', kind: 'video', url: 'https://user:password@upload.wikimedia.org/x.webm'},
  {provider: 'wikimedia-commons', kind: 'video', url: 'https://upload.wikimedia.org:8443/x.webm'},
  {provider: 'wikimedia-commons', kind: 'video', url: 'https://upload.wikimedia.org.evil.example/x.webm'},
]) {
  assert.equal(playbackAvailable(hostile), false, `${hostile.url} must not be playable`);
  assert.match(mediaPlayer(hostile, 'T', {}), /listening-player-unavailable/);
}

// --- Existing audio and YouTube lessons keep working: no second player ---
const audio = manifest.sources.find(source => source.playback.kind === 'audio');
assert.match(mediaPlayer(audio.playback, 'Audio lesson', {}), /^<audio id="orenaMedia"/);
assert.match(
  mediaPlayer({provider: 'youtube', kind: 'embed', url: 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ'}, 'V', {}),
  /^<iframe id="orenaMedia"/,
);

console.log('REAL_MEDIA_CATALOG_CONTRACT=PASS');
