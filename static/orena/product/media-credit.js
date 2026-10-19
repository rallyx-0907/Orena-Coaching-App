/* The source credit of a media item (D-239): the channel that published the video and the link to
   the original, taken from the provider metadata the payload already carries
   (`catalog.source.creator`, `provenance_url` / `source_url`, else `asset.source_url`). Only an
   https address on YouTube is a link; any other address draws no link (the channel text stays).
   Pure and DOM-free so the Listening room and Content detail share one reading of it. */

export const CREDIT_HOSTS = ['www.youtube.com', 'youtube.com', 'm.youtube.com', 'youtu.be'];

function youtubeUrl(value) {
  try {
    const url = new URL(String(value || '').trim());
    return url.protocol === 'https:' && CREDIT_HOSTS.includes(url.hostname) ? url.href : '';
  } catch {
    return '';
  }
}

export function mediaCredit(payload) {
  const source = payload?.catalog?.source || {};
  const asset = payload?.asset || {};
  const url = youtubeUrl(source.provenance_url) || youtubeUrl(source.source_url) || youtubeUrl(asset.source_url);
  const channel = String(source.creator || '').trim();
  if (!url && !channel) return null;
  return { channel, url };
}
