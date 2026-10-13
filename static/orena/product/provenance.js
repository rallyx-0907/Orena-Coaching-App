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
