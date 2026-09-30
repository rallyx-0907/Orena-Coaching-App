# Canonical grammar catalog v1 — completion audit

## Chinese

- GF0025 source inventory: **572** rows.
- Final canonical points: **380**.
- Source coverage: **572/572**.
- Missing source rows: **0**.
- Duplicate canonical ids: **0**.
- Duplicate legacy R5 aliases: **0**.
- Final Orena level counts: HSK1=43, HSK2=61, HSK3=55, HSK4=52, HSK5=51, HSK6=49, HSK7=23, HSK8=23, HSK9=23.
- Official source counts remain HSK1=48, HSK2=81, HSK3=81, HSK4=76, HSK5=71, HSK6=67, HSK7-9=148.
- HSK7/8/9 split is explicitly an Orena internal sequence inside the official HSK7-9 band.

Catalog-v1 acceptance rule used for this delegated completion pass:

1. high/medium source-to-R5 edges accepted;
2. low/unmapped rows preserved in official-taxonomy source clusters, max 4 rows per canonical point;
3. no source row discarded;
4. existing R5-only extensions retained as Orena extensions;
5. legacy alias uniqueness enforced.

## English

- Canonical points: **215**.
- Levels: A1=30, A2=38, B1=55, B2=44, C1=30, C2=18.
- Legacy alias uniqueness was already fixed in this branch.
- Fuzzy Core Inventory guesses are not source anchors; existing manually reviewed seed anchors remain authoritative.
- This delegated pass accepts the current R5 conversion map as English catalog v1, with C2 explicitly treated as an Orena extension rather than Core Inventory coverage.

## Generation boundary

The catalog research phase is complete enough for Grammar Lab generation. Grammar Lab must ingest these locked catalogs and must not add/remove/relevel grammar points during content generation.
