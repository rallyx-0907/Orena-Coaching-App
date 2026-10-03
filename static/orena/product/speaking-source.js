/* One line to say, and how to reach its real model audio - shared by every Speaking route this
   wave owns (`screens/speak`, `screens/compare`, `screens/attempts`, `screens/speak-summary`), so
   the same `id` resolves to the same line everywhere it is used.

   `id` is one of:
   - `speak:<item_id>`  - the authored Speaking catalogue (`GET /api/speaking/items/{id}`). It
     ships empty by default (UI_BACKEND_GAPS SP-1) and has no recorded model line at all - real,
     not a bug (`writing_coach/speaking_library.py#SpeakingLine` carries text/reading/translations,
     never audio).
   - `media:<lessonId>` - any usable transcript-backed Listening source
     (`GET /api/listening/library/{lessonId}`); its own clip is the model, cut and served
     same-origin (`/api/speaking/model-audio/{lessonId}/{segmentId}`) so the browser can measure
     its own waveform/pitch (`capabilities/audio-analysis.js`) rather than trust a synthesized one.
   - a bare id with neither prefix - Progress's own speaking-evidence rows link here with a bare
     Listening asset id (`screens/progress/screen.js#openRoute`, `ctx.href('speak', { id:
     item.assetId })`), not the `speak:`/`media:` convention every other entry point
     (`screens/today/model.js`, `screens/practice/model.js`) uses. That is a cross-screen
     inconsistency in that link, recorded in this wave's report; it is read here as "a lesson, or
     the media object one was recorded against" (`lessonFor` below) so the link still opens.

   Media Shadowing and Pronunciation share Compare, with an explicit segment picker and
   exact-line links back to Listening. An unnamed source starts at its first usable line. */
import { readingsFor } from '../capabilities/dictation-result.js';
import { openMedia } from './media-source.js';
import { wordSpans } from '../capabilities/word-timeline.js';
import { encounter } from './encounter.js';
import { primaryLanguage } from '../kit/lang.js';
import { playbackAvailable } from '../capabilities/media-player.js';

/* The segment a route names (`?segment=`), or none: the first line of the source. */
export function segmentOf(query) {
  return String(query?.get?.('segment') || query?.get?.('seg') || '');
}

export function parseSpeakingId(id) {
  const raw = String(id || '').trim();
  if (raw.startsWith('speak:')) return { kind: 'speak', rawId: raw.slice(6) };
  if (raw.startsWith('media:')) return { kind: 'media', rawId: raw.slice(6) };
  return { kind: 'media', rawId: raw, unprefixed: true };
}

/* The authored catalogue: no model clip, no per-word timing - `hasModelAudio: false` throughout. */
export function sourceFromCatalogItem(item, support) {
  const line = (item?.lines || [])[0];
  if (!item || !line) return null;
  return {
    sourceId: item.id,
    title: item.title || '',
    level: item.level || '',
    language: item.language || '',
    assetId: '',
    hasModelAudio: false,
    modelAudioUrl: null,
    line: {
      lineId: `${item.id}:${line.line_id}`,
      ordinal: 1,
      text: line.text || '',
      reading: line.reading || '',
      meaning: line.translations?.[support] || '',
      startMs: 0,
      endMs: 0,
    },
  };
}

/* The reading under the line, the same "what is actually said, not what is written" rule the old
   Speaking room used (speakers' names are not said): the reviewed whole-line reading only when it
   is the reading of exactly what is said; otherwise the aligned per-character reading of what is
   said; otherwise no reading, never somebody else's. */
function lineReading(segment, spokenText, catalog) {
  const whole = catalog.pinyin_by_segment?.[segment.segment_id] || '';
  if (whole && spokenText === segment.original_text) return whole;
  const chars = readingsFor(spokenText, segment.original_text, catalog.pinyin_chars_by_segment?.[segment.segment_id]);
  if (chars.length) return chars.map((item) => item?.pinyin || '').join(' ');
  return '';
}

/* A Listening lesson (`GET /api/listening/library/{lessonId}`'s own payload shape - confirmed
   against `scripts/fixtures/api/listening_library_lesson.en.json`, not assumed): the spoken text
   of a segment is `catalog.spoken_text_by_segment[segment_id]`, never a `segment.spoken_text`
   field, which this payload does not carry. */
export function sourceFromLesson(lessonId, payload, segmentId = '', support = '') {
  const catalog = payload?.catalog || {};
  const asset = payload?.asset || {};
  const segments = payload?.transcript?.segments || [];
  const at = segmentId ? segments.findIndex((item) => item.segment_id === segmentId) : 0;
  const segment = segments[at];
  if (!segment) return null;
  const spokenText = catalog.spoken_text_by_segment?.[segment.segment_id] || segment.original_text || '';
  return {
    sourceId: `media:${lessonId}`,
    lessonId,
    title: asset.title || catalog.title || '',
    level: catalog.reviewed_level || catalog.level || '',
    language: primaryLanguage(asset.source_language, primaryLanguage(catalog.language, '')),
    assetId: asset.asset_id || '',
    lines: segments.map((item,index)=>({lineId:item.segment_id,ordinal:index+1,text:catalog.spoken_text_by_segment?.[item.segment_id] || item.original_text || ''})),
    hasModelAudio: playbackAvailable(payload?.playback),
    modelAudioUrl: (lineId) => `/api/speaking/model-audio/${encodeURIComponent(lessonId)}/${encodeURIComponent(lineId)}`,
    line: {
      lineId: segment.segment_id,
      ordinal: at + 1,
      text: spokenText,
      reading: lineReading(segment, spokenText, catalog),
      // Use Listening's support-language encounter translations; never guess a meaning.
      meaning: encounter(payload, support).meaning(segment.segment_id) || '',
      startMs: segment.start_ms,
      endMs: segment.end_ms,
      wordTimings: spokenText === segment.original_text ? (wordSpans(segment) || []).map(span=>({
        text:spokenText.slice(span.start,span.end),offsetKnown:true,
        offsetMs:span.start_ms-segment.start_ms,durationMs:span.end_ms-span.start_ms,
      })).filter(word=>word.offsetMs>=0) : [],
    },
  };
}

/* A bare id names the media object a spoken attempt was recorded against (Progress's evidence
   rows, `asset_id`) or, failing that, a lesson. The library says which lesson a media object
   belongs to (`media_object_id`), and that lesson is the source - so the attempt's own row opens
   the same room (and the same takes) as every other entry point. Looked up before asking for the
   id as a lesson, so a media object id never costs a failed request. */
async function lessonFor(rawId, { api, support, language, owner }) {
  const library = await api.listeningLibrary(language || '').catch(() => null);
  const match = (library?.items || []).find((item) => item.media_object_id === rawId);
  const lessonId = match?.lesson_id || rawId;
  return { lessonId, payload: await openMedia(lessonId, {api, support, language, owner}) };
}

/* Loads and resolves one `id` into a source, or throws (the router's own lesson-load error, Back
   / Retry, is what every one of these four screens wants for "this line is unavailable"). */
export async function loadSpeakingSource(id, { api, support, language, owner = 'local', segmentId = '' }) {
  const parsed = parseSpeakingId(id);
  if (parsed.kind === 'speak') {
    const item = await api.speakingItem(parsed.rawId);
    const source = sourceFromCatalogItem(item, support);
    if (!source || (language && item.language !== language)) throw new Error('speaking_item_unavailable');
    return source;
  }
  const { lessonId, payload } = parsed.unprefixed ? await lessonFor(parsed.rawId, { api, support, language, owner }) : { lessonId: parsed.rawId, payload: await openMedia(parsed.rawId, {api, support, language, owner}) };
  const source = sourceFromLesson(lessonId, payload, segmentId, support);
  if (!source || (language && source.language && source.language !== language)) throw new Error('speaking_lesson_unavailable');
  return source;
}
