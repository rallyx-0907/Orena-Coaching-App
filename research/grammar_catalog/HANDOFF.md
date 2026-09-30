# External canonical grammar catalog handoff

This research branch exists so Grammar Lab does not spend provider time researching the syllabus.
No Gemini, DeepSeek, evaluator or paid API call was used to create these catalogs.

## Chinese source catalog

- File: `canonical_grammar_zh.yaml`
- Complete GF0025-2021 Appendix A inventory: **572 points**.
- Count gate: HSK1 48 / HSK2 81 / HSK3 81 / HSK4 76 / HSK5 71 / HSK6 67 / HSK7-9 148.
- The official standard groups advanced grammar as **7-9 together**. Any later split into 7 vs 8 vs 9 is an Orena sequencing decision, not a source claim.
- R5 aliases are left blank rather than guessed.

## English candidate catalog

- File: `canonical_grammar_en.yaml`
- Starts from 228 R5 lessons and applies the current `r5_conversion_map.tsv`.
- Result: **215 points**: A1 30 / A2 38 / B1 55 / B2 44 / C1 30 / C2 18.
- Core Inventory candidates are advisory only. The Core Inventory itself describes a minimum core and covers A1-C1, not an exhaustive A1-C2 grammar syllabus.
- Human review is still required for add/relevel/split/rescope items and for C2 source authority before EN is declared locked.

## What Grammar Lab should do with this

After human catalog lock:

1. Convert these files into Grammar Lab's inventory/seed schema.
2. Do **not** research the syllabus again during generation.
3. Do **not** add/remove/relevel points without a catalog decision.
4. Reuse R5 content where an alias/mapping exists; absence of R5 content never removes a canonical source point.
5. Then run the content factory: generate -> validate -> review-export -> apply-feedback -> engine-grade.
