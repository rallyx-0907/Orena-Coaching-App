# D-124 Vietnamese gloss coverage and grading samples (2026-10-04)

No model or paid provider was used. Sources:

- `viwikt` — Vietnamese Wiktionary via kaikki.org (CC BY-SA 4.0): English entries with
  Vietnamese glosses, plus Vietnamese entries' English translations indexed back.
- `enwikt-vi` — English Wiktionary's Vietnamese-language entries via kaikki.org (CC BY-SA 4.0):
  a Vietnamese headword whose English gloss is the word.
- `opendsl` — open-dsl-dict `en-vi-enwiktionary` (English Wiktionary translation tables;
  CC BY-SA 3.0 / GFDL; last updated 2015).

Chinese words reach these English-keyed sources through their CC-CEDICT English sense
(a dictionary pivot, no translation engine).

- `vi_coverage_report.csv` — per starter collection: share of words each source answers, and
  agreement (word overlap) with the curated Vietnamese where both exist.
- `vi_sample_<source>.csv` — 100 random answers per source (starter words plus random
  dictionary words), with an empty `grade` column for the human.
- `hanviet_sample.csv` — Hán-Việt readings from English Wiktionary's `han-viet-reading` tags
  (separate from `nom-reading`), per character or a cross-checked word form; `ambiguous`
  marks a character with several Hán-Việt readings (the first is shown, which is not
  frequency-ordered).

The data shown here is Wiktionary-derived text under CC BY-SA; it is quoted for review.
