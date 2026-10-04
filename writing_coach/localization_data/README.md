# Support-language gloss data

Vietnamese short meanings for English headwords (and, through their CC-CEDICT English
sense, Chinese words), used as D-124 localization sources: open lexical data, no model.
Only the entries the starter collections and `needed_words.txt` need are kept (18.5 kB);
the full upstream extracts stay outside the repository.

| | |
| --- | --- |
| Upstream | open-dsl-dict [`en-vi-enwiktionary`](https://github.com/open-dsl-dict/wiktionary-dict) (English Wiktionary translation tables, 2015; CC BY-SA 3.0 / GFDL) and Vietnamese Wiktionary (vi.wiktionary.org) as extracted by Wiktextract and published by [kaikki.org](https://kaikki.org/dictionary/rawdata.html) |
| Release | kaikki.org extraction of 2026-09-28 (`vi-extract.jsonl.gz`); SHA-256 of the input recorded in `vi_glosses.json.gz` → `sources` |
| Licence | Creative Commons Attribution-ShareAlike 4.0 — [`CC-BY-SA-4.0.txt`](CC-BY-SA-4.0.txt). Wiktionary text is also available under the GFDL. |
| Attribution | Wiktionary contributors; extraction by Tatu Ylonen's Wiktextract (kaikki.org) |

## Modification notice

Changed on 2026-10-04 by the Orena project: from each English entry, the first
gloss of each sense is kept when it is short (at most two comma items of at
most six words; parenthesised text removed); longer glosses are definitions
and are dropped. From each Vietnamese entry, its English translations are
indexed back to the Vietnamese headword. Text is otherwise unchanged. This
derived data remains under CC BY-SA 4.0.

Rebuild (after adding words to `needed_words.txt`):
`python scripts/build_vietnamese_wiktionary_pack.py --vi-extract <vi-extract.jsonl.gz> --opendsl <en-vi-enwiktionary.dsl.dz>`;
verify: `--check`. Policy (human, 2026-10-04): open-dsl-dict first; Vietnamese Wiktionary only for
one unambiguous sense of the chosen part of speech, never a cross-reference or an empty gloss;
otherwise the card shows the English meaning, labelled.

Status: measured, not a default source until the human grades its sample
(`docs/reviews/evidence/d124-vi/`).
