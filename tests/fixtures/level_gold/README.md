# Level gold set (Reading level calibration)

The labelled texts the automatic level estimate (`writing_coach/reading_level.py`, D-199) is fitted and checked on:
`python scripts/eval_reading_level.py` (agreement) and `--fit` (grid search; prints, writes nothing).

**Every label here is PROVISIONAL. None is owner-approved.** Until the owner approves a label, accuracy against this
set is accuracy against a judgement, not against truth. The owner's job is to correct and approve; the estimator is
refitted from the approved set, never from the provisional one alone. Reviewer corrections (`reviewed_level` against
`estimated_level`, read-only from the database) are further calibration evidence, not the sole truth.

## Files

| File | What |
| --- | --- |
| `voa_en.json` + `en/*.txt` | 36 VOA Learning English pages (US-government work, public domain). Ten pages that credit an agency ("reported this story for the Associated Press / AFP", adapted for VOA) were dropped from the first 46: no agency-credited text is committed here. The label is the level VOA states for the programme (Beginning: Let's Learn English Level 1 = A1, Level 2 = A2; Intermediate = B1). VOA's Advanced tier has no label (`null`, status `UNLABELLED`): the tier describes the learner, not the vocabulary. Texts are cut at 700 words. |
| `samples_en.json`, `samples_zh.json` | Orena-written samples per band (A1-C2, HSK1-HSK6), owned by Orena. |
| `zh_real.json` + `zh/*.txt` | 13 real easy Chinese texts with clear reuse rights, fetched 2026-10-14: eight Tatoeba sentence sets (CC BY 2.0 FR; sentence ids in `source`; attribution Tatoeba contributors) and five Chinese Wikipedia leads (CC BY-SA 4.0, revision in `source`). Labels were written by the author before the estimator ran. |
| `real_articles.json` | Real pages already in `tests/fixtures` (NASA, Global Voices, VOA 中文), read through the page extractor. |

## Format

A JSON array. Each entry:

| Field | Meaning |
| --- | --- |
| `id` | unique, stable |
| `language` | `en` or `zh` |
| `label` | `A1`-`C2` or `HSK1`-`HSK6`; `null` when no band is claimed |
| `status` | `PROVISIONAL`, `UNLABELLED`, or **`APPROVED`** (owner only) |
| `label_basis` | where the label comes from |
| one of `text`, `path` (relative to this folder), `fixture` (relative to `tests/fixtures`) | the text |
| `source`, `program`, `truncated` | provenance of a fetched page (optional) |

## For the owner to fill

Add entries (or flip `status` to `APPROVED` with your label) in a new file `owner_approved.json` in this format and add
its name to `load_gold()` in `scripts/eval_reading_level.py`. A useful minimum is ten texts per band you care about, taken
from real articles Orena would publish, including some C2 and HSK6 text, which this set has few of outside the author's own
samples. Do not paste copyrighted text you may not store.
