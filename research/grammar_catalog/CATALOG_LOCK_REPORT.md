# Canonical Grammar Catalog Lock Report

## Result

Both production catalogs are now locked for Grammar Lab generation on this research branch.

### English

- Canonical points: **215**.
- Range: **A1-C2**.
- Status: `locked_for_generation`.
- This is an **Orena syllabus**, not a claim that CEFR itself provides an exhaustive grammar list.
- R5 conversion decisions (keep/merge/split/relevel/rescope/add/remove) are accepted for generation.
- Weak fuzzy Core Inventory matches are not used as authority; only reviewed seed anchors remain authoritative references.

### Chinese

- Official GF0025 source rows: **572**.
- Final canonical points: **416**.
- Coverage: **572/572 source rows**.
- Legacy alias collisions: **0**.
- Final point counts:
  - HSK1: 48
  - HSK2: 63
  - HSK3: 65
  - HSK4: 56
  - HSK5: 58
  - HSK6: 52
  - HSK7: 25
  - HSK8: 25
  - HSK9: 24
- GF0025 officially groups advanced grammar as HSK7-9. Orena distributes those final points into HSK7/8/9 only for internal sequencing; the split is not represented as an official GF0025 distinction.
- Existing R5 material is reused where safe. Missing R5 coverage creates source-derived canonical points instead of dropping the official source row.

## Generation gate

Grammar Lab may now ingest the locked catalogs. It must not research, add, remove, relevel, merge or split syllabus points during content generation. Any future catalog change requires a new catalog revision.

Generation order:

`locked catalog -> import/seed adapter -> generate -> validate -> review-export -> apply-feedback -> engine-grade`
