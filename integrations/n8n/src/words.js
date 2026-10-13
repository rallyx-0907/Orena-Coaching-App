// Code node "Words" - one item per word, with the URLs of the two enrichment calls.
// Call 1: EN = Free Dictionary          | ZH = Tatoeba (sentences that have a Vietnamese translation)
// Call 2: EN = Tatoeba (with Vietnamese) | ZH = Tatoeba (any sentence, for more candidates)
const cfg = $('Config').first().json;
const S = cfg.sources;
const tq = (from, q, viOnly) => `${S.tatoebaSearch}?from=${from}&to=vie&orphans=no&unapproved=no&sort=relevance` +
  (viOnly ? '&trans_filter=limit&trans_to=vie' : '') + `&query=${encodeURIComponent(q)}`;
return $('Parse words').first().json.words.map(w => ({ json: {
  ...w,
  url1: w.lang === 'en' ? S.freeDictionary + encodeURIComponent(w.word) : tq('cmn', w.word, true),
  url2: w.lang === 'en' ? tq('eng', '=' + w.word, true) : tq('cmn', w.word, false),
} }));
