/* The source credit of a media item (D-239): the channel that published the video and the link to
   the original, taken from the provider metadata the payload already carries
   (`catalog.source.creator`, `provenance_url` / `source_url`, else `asset.source_url`). Only an
   http(s) address is a link; anything else (a local upload, a missing address) draws no credit.
   Pure and DOM-free so the Listening room and Content detail share one reading of it. */

function httpUrl(value) {
  const text = String(value || '').trim();
  try {
    const url = new URL(text);
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : '';
  } catch {
    return '';
  }
}

export function mediaCredit(payload) {
  const source = payload?.catalog?.source || {};
  const asset = payload?.asset || {};
  const url = httpUrl(source.provenance_url) || httpUrl(source.source_url) || httpUrl(asset.source_url);
  if (!url) return null;
  return { channel: String(source.creator || '').trim(), url };
}
