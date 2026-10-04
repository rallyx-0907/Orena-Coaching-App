# Vocabulary collection practice plan

Goal: complete the approved S3 learner journey: admitted collection -> explicitly
add missing words -> scoped review -> reopen with the existing saved state.
Grammar is deferred by explicit human instruction2026-10-04.
Architecture: existing catalog and saved-word/SRS owner only. Existing per-word
save endpoint, no new schema or provider. Collection detail can optionally return
its already-resolved saved rows so review is not limited to the first200 unrelated
saved words. Read all collection pages, not the learner's entire vocabulary.
Provenance: Orena.dc.html frame21 Collection Detail's two actions/word rows and
frame13 Review Session. Adapt the existing secondary Save to Add all to my words,
truthfully count saved review items; no new visual component or colour.

- [x] Regression tests for saving only missing words, partial failure/retry,
  preserved reading/provenance, unchanged existing schedule and scoped review
  beyond the first200 saved words; EN/ZH and locale packs.
- [x] Implement shared collection page reader and explicit per-word saves,
  action progress/error/retry on the existing control; no work on lesson open.
- [x] Expose requested saved rows on the existing detail read, use them for
  Review Session; browse remains read-only. No dictionary/translation generation.
- [x] Test, browser-verify real EN/ZH QA collections and phone workflow; independent
  review, memory/checkpoint. Do not claim AI enrichment/publication completion.
