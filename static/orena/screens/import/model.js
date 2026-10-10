/* DOM-free logic for the Import sheet (Design Contract rule 40: nothing here invents a number or
   a stage the backend did not report). Kept apart from sheet.js so scripts/test_orena_screen_sheets.mjs
   can exercise it without a browser. */

/* A rough script check, just enough to choose "characters" over "words" for a text stat (Chinese
   text has no spaces to split on; counting words there would undercount by whole sentences). Not a
   language detector - the learner's pasted text is in their current learning language
   (`ctx.context.language`), the real source sheet.js's own `<textarea lang="…">` now reads
   (languages-5 / finding A), the same way the old text-import dialog set that attribute. */
const HAN_RANGE = /[㐀-鿿豈-﫿]/;

function isMostlyHan(text) {
  const letters = text.replace(/\s+/g, '');
  if (!letters) return false;
  const han = letters.match(new RegExp(HAN_RANGE, 'g')) || [];
  return han.length / letters.length > 0.4;
}

/* Sentence count for the "paste at least two sentences" gate - Latin and CJK sentence-final
   punctuation, run-together punctuation counted once. */
export function countSentences(text) {
  const trimmed = String(text || '').trim();
  if (!trimmed) return 0;
  const matches = trimmed.match(/[.!?…。！？]+/g);
  if (matches) return matches.length;
  return 1; // has content, no terminal punctuation: still one (unfinished) sentence.
}

/* { unit: 'words'|'characters', count, sentences, tooShort } - `tooShort` mirrors the design's own
   "paste at least two sentences" gate exactly (rule: fewer than two sentences). */
export function textStats(text) {
  const trimmed = String(text || '').trim();
  const sentences = countSentences(trimmed);
  if (!trimmed) return { unit: 'words', count: 0, sentences: 0, tooShort: true };
  if (isMostlyHan(trimmed)) {
    const count = trimmed.replace(/\s+/g, '').length;
    return { unit: 'characters', count, sentences, tooShort: sentences < 2 };
  }
  const count = trimmed.split(/\s+/).filter(Boolean).length;
  return { unit: 'words', count, sentences, tooShort: sentences < 2 };
}

/* The backend's own learner-safe failure categories (writing_coach/media_ingestion.py
   MediaImportCategory, plus the import/status route's own categories) mapped to a copy key -
   never the raw category string, and never a message this UI made up for a category the backend
   did not send. An unrecognised or missing category (a network failure, an aborted request) falls
   back to one generic key rather than a per-error guess. The upload route's own two categories
   (writing_coach/media_library_api.py `learner_upload`) are listed too: File posts there (D-098). */
const ERROR_KEYS = new Set([
  'malformed_url',
  'unsupported_provider',
  'media_unavailable',
  'provider_timeout',
  'provider_failure',
  'malformed_transcript',
  'unsupported_source_language',
  'invalid_target_language',
  'media_job_unavailable',
  'media_upload_invalid',
  'media_upload_unavailable',
  // The plan's own refusals other than the limit (D-168): the limit is a toast, these are said in the sheet.
  'quota_unavailable',
  'media_duration_unavailable',
  'feature_not_in_plan',
]);

export function importErrorKey(category) {
  return ERROR_KEYS.has(category) ? `error_${category}` : 'error_generic';
}

/* A `url:` membership record for product/memory.js#addMedia, built only from fields the import
   response actually returned - a field the response left empty is left out rather than filled with
   a placeholder (memory.addMedia already tolerates that: thumbnail/provider are additive). */
export function urlMediaEntry(url, result) {
  const asset = result?.asset || {};
  return {
    id: `url:${url}`,
    title: String(asset.title || url).slice(0, 500),
    kind: result?.playback?.kind || asset.source_type || '',
    duration_ms: Number.isFinite(asset.duration_ms) ? asset.duration_ms : undefined,
    thumbnail_url: asset.thumbnail_url || '',
    provider: asset.source_provider || '',
  };
}

/* An `upload:` membership record (product/memory.js#addMedia's own scheme: "upload:" + the stored
   media id) from what POST /api/media-learning/upload answered - the stored title, or the file's
   own name without its extension when the answer carries none. */
export function uploadMediaEntry(result, filename = '') {
  const asset = result?.asset || {};
  const mediaId = String(result?.media_id || '').trim();
  if (!mediaId) return null;
  const stem = String(filename).replace(/\.[^.]*$/, '').trim();
  return {
    id: `upload:${mediaId}`,
    title: String(asset.title || stem || mediaId).slice(0, 500),
    kind: result?.playback?.kind || asset.source_type || '',
    duration_ms: Number.isFinite(asset.duration_ms) ? asset.duration_ms : undefined,
    thumbnail_url: asset.thumbnail_url || '',
    provider: '',
  };
}

