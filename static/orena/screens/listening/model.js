/* Listening Workspace (design route `listening`, frame 06, D-091): pure data mapping, DOM-free
   so scripts/test_orena_screen_listening.mjs can test it without a browser.

   Source of truth for the payload shape: `GET /api/listening/library/{lessonId}` as captured in
   scripts/fixtures/api/listening_library_lesson.{en,zh}.json (writing_coach/listening_api.py). A
   field this module reads that those captures do not carry fails the screen's node gate.

   The behaviour rules below (what a tap does in each mode, which line "previous" means, how the
   speed cycles, which word the estimate marks) are the design script's own handlers for this
   frame (`orena-script.js`: `segs`, `prevLine`, `cycleSpeed`, `modes`, `modeHint`), restated as
   pure functions over the real transcript - not its prototype timers or canned data. */
import { wordSpans, activeWordIndex } from '../../capabilities/word-timeline.js';

export function transcriptState(payload) {
  if (payload?.transcript?.segments?.length) return 'ready';
  return payload?.asset?.processing_state === 'processing' ? 'processing' : 'unavailable';
}

/* The design's own cycle: 1x -> 0.75x -> 0.5x -> 1.25x -> 1x. */
export const SPEEDS = Object.freeze([1, 0.75, 0.5, 1.25]);

export function nextSpeed(current) {
  const index = SPEEDS.indexOf(Number(current));
  return index < 0 ? SPEEDS[0] : SPEEDS[(index + 1) % SPEEDS.length];
}

export function speedLabel(rate) {
  const value = Number(rate) || 1;
  return `${value}×`;
}

/* The route id for this lesson's own content-id namespace (screens/content/model.js's own
   "<kind>:<id>" convention, shared verbatim: a Listening lesson is always "media:<id>"). */
export function contentIdFor(lessonId) {
  return `media:${lessonId}`;
}

/* A transcript timestamp, "0:44" - null when the value is not a real number (rule 40: no
   fabricated "0:00"), same rule screens/content/model.js already applies. */
export function mmss(ms) {
  if (ms == null) return null;
  const value = Number(ms);
  if (!Number.isFinite(value) || value < 0) return null;
  const totalSeconds = Math.floor(value / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

export function minutesFrom(ms) {
  if (ms == null) return null;
  const value = Number(ms);
  if (!Number.isFinite(value) || value < 0) return null;
  if (value === 0) return 0;
  return Math.max(1, Math.round(value / 60000));
}

export function metaLine(parts, sep = ' · ') {
  return parts.filter((part) => part != null && part !== '').join(sep);
}

/* A provider's regional tag ("en-GB", "zh-CN") is provenance, not identity: the room compares the
   language against "zh", so only the primary subtag counts (an acquisition payload, unlike a stored
   catalog entry, carries the provider's tag). A provider that could not tell ("und") leaves the
   choice to the caller's fallback - the learner's own learning language - rather than a guess. */
export function primaryLanguage(tag, fallback = 'en') {
  const primary = String(tag || '').trim().toLowerCase().split(/[-_]/)[0];
  return !primary || primary === 'und' ? fallback : primary;
}

function finiteOrNull(value) {
  if (value == null || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function lastSegmentEnd(payload) {
  const segments = payload?.transcript?.segments;
  return finiteOrNull(Array.isArray(segments) && segments.length ? segments[segments.length - 1]?.end_ms : null);
}

/* Every element the workspace draws from the real payload, in one place, except the transcript
   segments themselves - `product/encounter.js#encounter()` already owns that shape (current/
   select/follow/meaning), reused as-is rather than a second parallel mapping. Nothing here invents
   a field: an absent value stays null/empty and the caller renders rule 40's zero/omitted shape. */
export function mapLesson(payload, { levelLabel = (lv) => lv, fallbackLanguage = 'en' } = {}) {
  const catalog = payload?.catalog || {};
  const asset = payload?.asset || {};
  const modes = Array.isArray(catalog.available_modes) ? catalog.available_modes : [];
  return {
    lessonId: catalog.lesson_id || '',
    mediaObjectId: catalog.media_object_id || asset.asset_id || '',
    title: catalog.title || asset.title || '',
    language: primaryLanguage(catalog.language || asset.source_language, fallbackLanguage),
    topic: catalog.topic || '',
    level: catalog.level || '',
    levelText: catalog.level ? levelLabel(catalog.level) : '',
    sourceLevel: catalog.source_declared_level || '',
    // Number(null) is 0: an unmeasured length (a provider that reports none) stays null, never "0 min".
    durationMs: finiteOrNull(catalog.duration_ms ?? asset.duration_ms),
    excerptStartMs: finiteOrNull(catalog.excerpt_start_ms) ?? 0,
    // An acquisition carries no excerpt: its clip ends where its last spoken line does.
    excerptEndMs: finiteOrNull(catalog.excerpt_end_ms) ?? lastSegmentEnd(payload),
    posterUrl: catalog.poster_url || asset.thumbnail_url || '',
    playback: payload?.playback || null,
    playbackKind: payload?.playback?.kind || '',
    vocabulary: Array.isArray(catalog.vocabulary) ? catalog.vocabulary : [],
    pinyinChars: catalog.pinyin_chars_by_segment || {},
    modes: {
      follow: true, // Follow always exists - it is the room's own default state, not a catalogue gate.
      active: modes.includes('active'),
      shadowing: modes.includes('shadowing'),
      dictation: modes.includes('dictation'),
    },
    rights: catalog.source || null,
    attributionUrl: catalog.source?.provenance_url || catalog.source?.source_url || '',
  };
}

/* ---- Transcript text ---------------------------------------------------------------------- */

/* One space-delimited token per tappable word, exactly as the frame's `seg.words` are (its text
   is split on spaces, so trailing punctuation stays inside the token and the word the learner
   looks up is the token with that punctuation stripped). `start`/`end` are string offsets into
   the line, which is what real word timing (capabilities/word-timeline.js) is expressed in. */
export function wordTokens(text) {
  const value = String(text ?? '');
  const tokens = [];
  const re = /\S+/gu;
  let match = re.exec(value);
  while (match) {
    const raw = match[0];
    const core = raw.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '');
    tokens.push({ text: raw, core, start: match.index, end: match.index + raw.length });
    match = re.exec(value);
  }
  return tokens;
}

/* Chinese tokens: one per Han character (with its reading), one per run of other letters or
   digits ("Vector" inside a Chinese line is one word, not six), and one per punctuation mark
   (inert: `core` is empty). The reading is the backend's own `pinyin_chars_by_segment` alignment,
   which lists the line's Han characters in order and nothing else (DC-3); a character it does not
   name in order gets no reading rather than a guessed one (rule 40: no pinyin is a true, drawable
   state, not an error). Whitespace is dropped, as the frame's per-character stacks draw none. */
export function hanTokens(text, pinyinChars) {
  const value = String(text ?? '');
  const readings = Array.isArray(pinyinChars) ? pinyinChars : [];
  const tokens = [];
  let next = 0;
  let offset = 0;
  const chars = [...value];
  for (let i = 0; i < chars.length; i += 1) {
    const ch = chars[i];
    const start = offset;
    if (/\s/u.test(ch)) {
      offset += ch.length;
    } else if (/\p{Script=Han}/u.test(ch)) {
      const entry = readings[next];
      const matched = entry && String(entry.char) === ch;
      if (matched) next += 1;
      offset += ch.length;
      tokens.push({ text: ch, pinyin: matched ? String(entry.pinyin || '') : '', core: ch, start, end: offset });
    } else if (/[\p{L}\p{N}]/u.test(ch)) {
      let run = ch;
      while (i + 1 < chars.length && /[\p{L}\p{N}]/u.test(chars[i + 1]) && !/\p{Script=Han}/u.test(chars[i + 1])) {
        i += 1;
        run += chars[i];
      }
      offset += run.length;
      tokens.push({ text: run, pinyin: '', core: run, start, end: offset });
    } else {
      offset += ch.length;
      tokens.push({ text: ch, pinyin: '', core: '', start, end: offset });
    }
  }
  return tokens;
}

/* The frame's estimate of "the likely current word inside a segment" (its own `starts` maths:
   each token weighs its length plus one, the token whose share of the segment has begun is the
   current one). */
export function estimatedTokenIndex(tokens, fraction) {
  if (!tokens.length) return -1;
  const weights = tokens.map((token) => token.text.length + 1);
  const total = weights.reduce((sum, weight) => sum + weight, 0);
  const at = Math.max(0, Math.min(1, Number(fraction) || 0));
  let acc = 0;
  let found = 0;
  for (let k = 0; k < tokens.length; k += 1) {
    if (at >= acc / total) found = k;
    acc += weights[k];
  }
  return found;
}

/* The token being spoken at `timeMs`. Real word timing wins when the asset ships some that
   reconciles with the line (capabilities/word-timeline.js: a wrong-word highlight is worse than
   none, so it returns null wholesale otherwise); the segment-timing estimate is the fallback the
   control's own "· est." label admits to. -1 outside the segment. */
export function currentTokenIndex(segment, tokens, timeMs) {
  const at = Number(timeMs);
  const start = Number(segment?.start_ms);
  const end = Number(segment?.end_ms);
  if (!tokens.length || !Number.isFinite(at) || !Number.isFinite(start) || !Number.isFinite(end) || end <= start) return -1;
  if (at < start || at >= end) return -1;
  const spans = wordSpans(segment);
  if (spans) {
    const word = activeWordIndex(spans, at);
    if (word < 0) return -1;
    const span = spans[word];
    return tokens.findIndex((token) => span.start < token.end && span.end > token.start);
  }
  return -1; // Segment timing cannot establish which word is being spoken.
}

export function currentTokenIndices(segment, tokens, timeMs) {
  const spans = wordSpans(segment);
  const index = activeWordIndex(spans, timeMs);
  if (index < 0 || timeMs < segment.start_ms || timeMs >= segment.end_ms) return [];
  const span = spans[index];
  return tokens.flatMap((token, at) => span.start < token.end && span.end > token.start ? [at] : []);
}

export function hasWordTiming(segment) { return Boolean(wordSpans(segment)); }

/* ---- Rows and modes ---------------------------------------------------------------------- */

/* The frame's row states (`segs` in its script: `bg: isSel ? accent-soft : isCur ? tint2`): the
   line the learner selected (Active mode) wins the ground - a tap selects the line and plays it,
   so it is normally both - then the line being played, then a line already heard (`sg.e <= t`,
   drawn quieter) or one still to come. Whether the line is being played is kept apart (its text is
   a weight heavier), so the caller asks `isCurrent` for that. */
export function rowTone({ isCurrent, isSelected, endMs, timeMs }) {
  if (isSelected) return 'selected';
  if (isCurrent) return 'current';
  return Number(endMs) <= Number(timeMs) ? 'past' : 'future';
}

/* What the mode says a tap on a line does (`modeHint` in the frame's script). */
export function modeHintKey(mode) {
  return mode === 'active' ? 'hintActive' : 'hintFollow';
}

/* The frame's own switching rule (`modes[].onClick`): Active selects the line being played,
   Follow clears the selection. Shadowing is not a mode of this room - it leaves it. */
export function selectionAfterModeChange(mode, currentId) {
  return mode === 'active' ? currentId || null : null;
}

/* `prevLine`: past the first second of a line, "previous" restarts it; within it, goes back one. */
export function previousIndex(segments, currentIndex, timeMs) {
  const list = Array.isArray(segments) ? segments : [];
  if (!list.length) return -1;
  const at = currentIndex < 0 ? 0 : currentIndex;
  const restart = Number(timeMs) - Number(list[at]?.start_ms) > 1000;
  return Math.max(0, restart ? at : at - 1);
}

export function nextIndex(segments, currentIndex) {
  const list = Array.isArray(segments) ? segments : [];
  if (!list.length) return -1;
  return Math.min(list.length - 1, (currentIndex < 0 ? 0 : currentIndex) + 1);
}

/* Whether this lesson's own real vocabulary term appears in a segment's real text - a light,
   real text match (case-insensitive; a trailing-letter stem for English plurals/inflections,
   e.g. "galaxy" still matches "galaxies") over the lesson's own catalogue words, never a guessed
   or generated phrase. Chinese needs no stemming: its characters already match as substrings. */
export function vocabularyForSegment(vocabulary, text) {
  const lower = String(text).toLowerCase();
  return vocabulary.filter((term) => {
    const word = String(term).toLowerCase();
    if (!word) return false;
    if (lower.includes(word)) return true;
    const stem = word.length > 4 ? word.slice(0, -1) : word;
    return lower.includes(stem);
  });
}

/* A valid `context` for `POST /api/dictionary/word-detail` must contain the looked-up text (the
   server answers 422 otherwise - the catalogue term "galaxy" is not inside a line that says
   "galaxies"). The line is the context when it really holds the term; otherwise the term is its own
   (still valid) context - never an invented sentence. */
export function lookupContext(term, line) {
  const word = String(term ?? '').trim();
  const sentence = String(line ?? '').trim();
  return sentence && word && sentence.toLowerCase().includes(word.toLowerCase()) ? sentence : word;
}

/* The learner's device-memory continuation entry for this content id (product/memory.js#enter),
   reduced to the one thing this room resumes: which segment they were on. */
export function placeFor(continuation, contentId) {
  const entry = Array.isArray(continuation) ? continuation.find((item) => item?.id === contentId) : null;
  return { segmentId: entry?.segment || '', started: Boolean(entry) };
}

/* ---- Save phrase --------------------------------------------------------------------------- */

/* The library keeps a saved phrase the way it keeps a saved word: one vocabulary entry named by
   its text (`POST /api/library/vocabulary`, `word` up to 180 characters). A line longer than that
   cannot be an entry, and is never truncated into a different phrase. `source_kind` is `manual`
   - the real API accepts only manual | dictionary | feedback | strength | reading | feed |
   collection, and `listening` is not one of them (422). */
export const PHRASE_MAX = 180;

export function phraseSaveable(text) {
  const value = String(text ?? '').trim();
  return value.length > 0 && value.length <= PHRASE_MAX;
}

export function phraseSavePayload(text, { meaning = '' } = {}) {
  const value = String(text ?? '').trim();
  return {
    word: value,
    definition: String(meaning || '').slice(0, 2400),
    source_fragment: value.slice(0, 1200),
    source_kind: 'listening',
  };
}

/* Whether a vocabulary listing (`GET /api/library/vocabulary?query=`) already holds this phrase. */
export function phraseSaved(items, text) {
  const value = String(text ?? '').trim().toLowerCase();
  if (!value) return false;
  return (Array.isArray(items) ? items : []).some((item) => String(item?.word ?? '').trim().toLowerCase() === value);
}

/* ---- End of media ----------------------------------------------------------------------- */

/* Real dictation evidence for this asset (`GET /api/listening/progress`), read-only: how many of
   this lesson's segments have been checked at least once. Listening does not own the Dictation
   room, but it may read this room's own real evidence to report a true end-of-media count rather
   than a 0 it could have answered honestly. */
export function dictationLinesCompleted(progressItems) {
  return (Array.isArray(progressItems) ? progressItems : []).filter((item) => item?.presentation && item.presentation !== 'prompt').length;
}

/* A genuine next recommendation: another catalogue lesson, never the current one - one sharing
   this lesson's own real topic when there is one (and then the eyebrow may say so), otherwise the
   next lesson of the library with no reason claimed. Null only when the library holds no other
   lesson at all (rule 40: nothing is invented to fill the row). */
export function pickNextRecommendation(items, currentLessonId, topic) {
  const others = (Array.isArray(items) ? items : []).filter((item) => item && item.lesson_id && item.lesson_id !== currentLessonId);
  const hit = (topic && others.find((item) => item.topic === topic)) || others[0];
  if (!hit) return null;
  return {
    lessonId: hit.lesson_id,
    title: hit.title || '',
    posterUrl: hit.poster_url || '',
    minutes: minutesFrom(hit.duration_ms),
    topic: topic && hit.topic === topic ? hit.topic : '',
  };
}

/* The seek bar's fill, 0-100, over the real excerpt span (not the raw media element's own full
   length, which may run longer than the licensed/curated excerpt). */
export function progressPercent(timeMs, startMs, endMs) {
  const start = Number(startMs) || 0;
  const end = Number(endMs);
  if (!Number.isFinite(end) || end <= start) return 0;
  const at = Number(timeMs);
  if (!Number.isFinite(at)) return 0;
  return Math.max(0, Math.min(100, ((at - start) / (end - start)) * 100));
}

/* A tapped position on the seek bar back into an absolute media time, honouring the excerpt's
   own start offset. */
export function msAtSeekFraction(fraction, startMs, endMs) {
  const start = Number(startMs) || 0;
  const end = Number(endMs);
  if (!Number.isFinite(end) || end <= start) return start;
  return start + Math.max(0, Math.min(1, fraction)) * (end - start);
}

export function timeLabel(timeMs, startMs, endMs) {
  const elapsed = mmss(Math.max(0, Number(timeMs) - (Number(startMs) || 0)));
  if (elapsed == null) return '';
  // A source whose length nobody measured (a provider that reports none, no transcript) has no
  // total to draw: the elapsed time stands alone rather than "/ 0:00" (rule 40).
  if (!Number.isFinite(Number(endMs)) || Number(endMs) <= (Number(startMs) || 0)) return elapsed;
  const total = mmss(Number(endMs) - (Number(startMs) || 0));
  return total == null ? elapsed : `${elapsed} / ${total}`;
}

/* Whether the clip has been heard out: within one clock tick (media-player.js polls at 125ms) of
   its real excerpt end. */
export function reachedEnd(timeMs, endMs) {
  const end = Number(endMs);
  const at = Number(timeMs);
  // An unknown end (0) is not an end: a source of unmeasured length is never "heard out" on open.
  return Number.isFinite(end) && end > 0 && Number.isFinite(at) && at >= end - 300;
}

/* real per-session listened time: the caller sums wall-clock deltas while `player_state===1`
   (media-player.js's own clock event) and hands the running total here only for display
   rounding - never a value this module invents on its own. */
export function listenedMinutesLabel(ms) {
  if (!Number.isFinite(ms) || ms < 0) return null;
  const totalSeconds = Math.round(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}
