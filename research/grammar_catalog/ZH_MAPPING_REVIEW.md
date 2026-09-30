# Chinese GF0025 -> Orena mapping review checkpoint

This checkpoint does **not** declare the Chinese canonical catalog finished. It creates the auditable graph needed to finish it without spending provider quota on syllabus research.

## Inputs

- GF0025-2021 Appendix A reference inventory: 572 rows.
- Current R5 Chinese lessons: 197.
- Current R5 conversion plan: 171 base canonical candidates after merge/split/remove/add proposals.
- Existing reviewed HSK1-2 seeds are reused where they give a stable candidate id/title.

## Mapping result

| Confidence | Count | Meaning |
| --- | ---: | --- |
| High | 96 | exact/manual or strong title-pattern candidate |
| Medium | 61 | useful candidate, still reviewable |
| Low | 46 | weak candidate; do not ingest automatically |
| Unmapped | 369 | current R5-derived base has no safe match |

Per band:

| Band | High | Medium | Low | Unmapped |
| --- | ---: | ---: | ---: | ---: |
| HSK1 | 23 | 5 | 5 | 15 |
| HSK2 | 16 | 11 | 4 | 50 |
| HSK3 | 20 | 13 | 9 | 39 |
| HSK4 | 16 | 8 | 4 | 48 |
| HSK5 | 8 | 10 | 9 | 44 |
| HSK6 | 3 | 6 | 2 | 56 |
| HSK7-9 | 10 | 8 | 13 | 117 |

## Interpretation

The large unmapped set is expected and important. GF0025 is a reference inventory containing lexical-class grammar, phrase structure, sentence components, sentence types, discourse structures and advanced written grammar. R5 has only 197 lessons and intentionally omits or compresses many of these. Therefore unmapped rows must become inputs to a **new-point / clustering review**, not be silently discarded and not be converted 1:1 into lessons.

## Next catalog step

1. Accept/reject high + medium candidate edges.
2. Cluster the remaining GF0025 rows by official category path and pedagogical function.
3. Add new canonical Orena points only where existing 171 candidates cannot cover the source scope.
4. Verify every one of the 572 source rows has at least one final `maps_to` edge.
5. Human-lock the resulting canonical catalog; only then hand it to Grammar Lab generation.
