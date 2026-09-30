# External canonical grammar catalog handoff

This research branch separates syllabus/reference research from `feature/grammar-lab-pipeline`.
No Gemini, DeepSeek, evaluator or paid API call is required for the source-catalog work here.

## Chinese: reference inventory first, canonical points second

- `source_inventory_zh_gf0025.yaml` is the complete **572-row GF0025-2021 Appendix A reference inventory**.
- It is **not** a 572-lesson Orena curriculum.
- Count gate: HSK1 48 / HSK2 81 / HSK3 81 / HSK4 76 / HSK5 71 / HSK6 67 / HSK7-9 148.
- The transcription defect at item 四54 was corrected to `无论⋯⋯，都/也⋯⋯` after checking the official syllabus text.
- `canonical_grammar_zh.yaml` is intentionally not populated yet. The next research step is mapping/clustering the 572 reference rows plus R5 source material into pedagogical Orena grammar points.
- GF0025 publishes the advanced band as HSK7-9. A later split into HSK7/8/9 is Orena sequencing, not a source claim.

## English: canonical candidate cleaned

- `canonical_grammar_en.yaml` is the current **215-point** candidate obtained by executing the current conversion map over 228 R5 lessons.
- Executed counts are A1 30 / A2 38 / B1 55 / B2 44 / C1 30 / C2 18. The older count table in R5_CONVERSION_PLAN.md was stale and is corrected on this research branch.
- `r5_sources` means provenance/source material.
- `r5_aliases` means legacy redirect compatibility and is strictly one legacy id -> one canonical point.
- On a split, every child may cite the same `r5_sources`, but only the first designated child owns the legacy alias.
- No fuzzy Core Inventory matches are promoted to anchors. Manually reviewed anchors already present in `grammar_lab/inventory/seeds_en.yaml` remain the trusted anchors.
- All non-`keep` conversion decisions plus C2 still require one catalog review before EN can be human-locked.

## Grammar Lab boundary

Grammar Lab must not research or redefine the syllabus while generating content.

Before generation:
1. Human-lock the EN canonical catalog.
2. Build and human-lock the ZH canonical point mapping from the GF0025 reference inventory.
3. Convert the locked canonical catalogs into Grammar Lab inventory/seed schema.

Only then run:

`generate -> validate -> review-export -> apply-feedback -> engine-grade`.

Any later add/remove/relevel/split/merge is a catalog change and requires an explicit catalog review; it is not a generation-time decision.
