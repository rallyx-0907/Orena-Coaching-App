# Canonical grammar catalog v1 — imported research artifact

Imported from `research/canonical-grammar-catalog` at commit `6e20c751dbeeabc58b933b99eaa822544e6e2e12`.

These files are **catalog source-of-truth artifacts**, not yet Grammar Lab's runtime `inventory/en.yaml`, `inventory/zh.yaml` or `seeds_<lang>.yaml` schema.

Rules for the pipeline lane:

1. Do not research the syllabus again.
2. Do not add/remove/relevel/split/merge canonical points during content generation.
3. Convert the locked catalogs deterministically into Grammar Lab inventory/seed schema first.
4. Preserve source provenance and legacy R5 aliases.
5. EN catalog: 215 points, A1-C2.
6. ZH catalog: 380 points, HSK1-HSK9, with 572/572 GF0025 source coverage.
7. The HSK7/8/9 split is Orena internal sequencing inside the official HSK7-9 band.
8. Any syllabus change after import is a catalog-v2 change and requires explicit review.

Do not overwrite `inventory/en.yaml` or `inventory/zh.yaml` with these raw catalog files directly; their schemas differ.
