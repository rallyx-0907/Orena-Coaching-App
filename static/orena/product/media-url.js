// A learner-pasted link is only ever handed to the media-acquisition pipeline
// when it is shaped like a real, public YouTube URL: https, no embedded
// credentials, no explicit port, and a plausible video id. This is a security
// boundary (what the client will even attempt to fetch through), not a
// presentation choice - moved out of the old UI's app.js unchanged rather
// than rewritten, so the allow-list stays exactly what was already reviewed.
export function isSupportedMediaUrl(value) {
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.username || url.password || url.port) return false;
    if (url.hostname === 'youtu.be') return /^\/[\w-]{11}$/.test(url.pathname);
    return (
      ['youtube.com', 'www.youtube.com', 'm.youtube.com'].includes(url.hostname) &&
      ((url.pathname === '/watch' && /^[\w-]{11}$/.test(url.searchParams.get('v') || '')) || /^\/(shorts|embed)\/[\w-]{11}$/.test(url.pathname))
    );
  } catch {
    return false;
  }
}
