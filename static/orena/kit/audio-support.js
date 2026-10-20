/* Can this device play a word's recording? A Wikimedia Commons pronunciation is usually Ogg (Vorbis or Opus), which
   iOS Safari may not play: there the play button would do nothing. Each surface that plays a word asks here first and,
   when the recording cannot be played, uses the device's own voice (kit/device-voice.js, labelled as the device's),
   the same fallback it already takes when the server has no voice (#449).

   The media type is the payload's `mediaType` when there is one, else the URL's extension. A type the browser does
   not know is asked as-is; a URL with no recognisable type is assumed playable (the browser then decides). */

const BY_EXTENSION = {
  ogg: 'audio/ogg', oga: 'audio/ogg', opus: 'audio/ogg; codecs="opus"', mp3: 'audio/mpeg', m4a: 'audio/mp4',
  aac: 'audio/aac', wav: 'audio/wav', flac: 'audio/flac', webm: 'audio/webm',
};

export function mediaTypeOf(url = '', mediaType = '') {
  const given = String(mediaType || '').trim().toLowerCase();
  if (given) return given;
  const match = /\.([a-z0-9]{2,5})(?:[?#]|$)/i.exec(String(url || ''));
  return match ? BY_EXTENSION[match[1].toLowerCase()] || '' : '';
}

/* The canPlayType variants that answer for a type: Ogg is asked with its two codecs, since "audio/ogg" alone can say
   "maybe" on a browser with no Vorbis decoder. */
function variants(type) {
  if (type === 'audio/ogg' || type === 'application/ogg') return ['audio/ogg; codecs="vorbis"', 'audio/ogg; codecs="opus"'];
  return [type];
}

function defaultProbe() {
  try {
    return typeof Audio === 'function' ? new Audio() : null;
  } catch {
    return null;
  }
}

/* True when this device can play a recording of this type (or the type is unknown); false when it surely cannot. */
export function canPlayAudio(url = '', mediaType = '', probe = defaultProbe) {
  const type = mediaTypeOf(url, mediaType);
  if (!type) return true;
  const element = typeof probe === 'function' ? probe() : probe;
  if (!element || typeof element.canPlayType !== 'function') return true; // no way to ask: let the browser try
  return variants(type).some((variant) => {
    try {
      return element.canPlayType(variant) !== '';
    } catch {
      return false;
    }
  });
}
