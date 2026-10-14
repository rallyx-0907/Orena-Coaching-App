/* The credit of a published Reading article (D-189): where it came from, read from the `provenance`
   object the learner list and detail payloads carry (writing_coach/reading_provenance.py).

   The design draws one source line per card (`c.source`), on the Content Detail hero and on the Reader
   toolbar's meta line, so these return the publisher for those. The design draws no licence or
   original-link line on those frames; they reach the learner in Settings > Licences and data sources
   (`GET /api/licences`), which the same backend credit feeds. */
export function publisherOf(article) {
  return String(article?.provenance?.publisher || '').trim();
}

/* A text's source line: its publisher, else the author the extractor found (an older payload). */
export function sourceLine(article) {
  return publisherOf(article) || String(article?.attribution?.author || '').trim();
}

/* The card/hero picture of a published article (D-192): `{ url, cssUrl, credit, alt }`, or null for the generated
   tile. The backend sends `image` only when the source allows pictures, an administrator approved one and a
   credit exists; the address is always our own same-origin copy. Anything else - another origin, no credit - is
   treated as no picture, so a payload can never make the page load a third party's file. */
const OWN_IMAGE = /^\/api\/reading\/articles\/[0-9a-f-]{8,40}\/image(\?v=\d{1,12})?$/i;
export function imageOf(article) {
  const image = article?.image;
  const url = typeof image?.url === 'string' ? image.url : '';
  const credit = String(image?.credit || '').trim();
  if (!OWN_IMAGE.test(url) || !credit) return null;
  return { url, cssUrl: `url("${url}")`, credit, alt: String(image?.alt || '').trim() };
}

/* Only a web address a browser may open as a link: http or https. Anything else (javascript:, data:, a bare
   string) is dropped, so a provenance field can never become a script href. */
export function safeHttpUrl(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  try {
    const url = new URL(raw);
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : '';
  } catch {
    return '';
  }
}

/* A value that says nothing ("unknown", "n/a", empty) is not a credit: the learner never reads the word. */
const empty = (value) => {
  const text = String(value || '').trim();
  return !text || /^(unknown|unknow|n\/a|none|null|undefined|-+|không rõ|không xác định|未知)$/i.test(text) ? '' : text;
};

/* The Reader's source footnote (docs/design/canonical-ui/brief/READER_SOURCE_LINE_2026-10-14.md), or null when
   the payload carries nothing to credit: { publisher, author, url, license: { name, url } }.
   The author appears only when it differs from the publisher; the licence only when the backend determined it
   (a name, linked when it also has a safe address). */
export function creditOf(article) {
  const p = article?.provenance;
  if (!p || typeof p !== 'object') return null;
  const publisher = empty(p.publisher);
  const author = empty(p.author);
  const url = safeHttpUrl(p.url);
  const licenseName = empty(p.license?.name);
  const credit = {
    publisher,
    author: author && author.toLowerCase() !== publisher.toLowerCase() ? author : '',
    url,
    license: licenseName ? { name: licenseName, url: safeHttpUrl(p.license?.url) } : null,
    // D-192: the picture's credit joins this footnote, only when a picture is shown.
    image: imageOf(article)?.credit || '',
  };
  return credit.publisher || credit.url || credit.image ? credit : null;
}
