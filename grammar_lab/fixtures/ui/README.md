# UI fixtures (schema v0.4)

Two complete grammar points for building the learner-UI renderer from
`schema/grammar_set.schema.json` + these files, without reading R5 or the canonical research.

| File | Point | Level | Shows |
| --- | --- | --- | --- |
| `en.present_continuous.now.json` | Present continuous (now) | A1 | formula with an optional slot, negative + question variants, `timeline` illustration, spans on every example form, compare, common mistakes, quick practice, personal production |
| `zh.le_completion.json` | Particle 了 (completion) | HSK1 | the same, plus per-character pinyin on formula, examples, compare, mistakes and quick-practice options, `native_title_pinyin` |
| `index.json` | | | the primitives each file carries, and what the pair does not cover |

What they are: the two points already on disk in `content/`, re-seeded through the runtime catalogue
(`import-canonical`) so level, function, aliases, source refs and anchors match it. Content and
provenance are unchanged; status is `draft_ai`. They are **reference fixtures, not provider output made
for this task** (`provider_calls_for_this_fixture: 0`) and not reviewed learner content.

Not covered, and not faked: `pattern.formula.options`, the `morphology` and `word_order` illustrations, and
the secondary `story` block (paused on v0.4). Read those from `GRAMMAR_CONTENT_CONTRACT.md` §2 and the
schema until a point that carries them is generated.

`prereqs`/`contrasts` may name catalogue points whose content is not written yet; the renderer must treat an
unresolved id as a plain label. Regenerate with `python -m grammar_lab.pipeline.cli ui-fixtures`.

## Codex handoff shape and the production rule

The files here are in the shape the Grammar Content Contract merged on `codex/work` reads, not Grammar
Lab's internal shape: `target_lang` is `zh` (not `zh-Hans`), locale-map keys are `vi`/`en`/`zh`, and every
locale map carries `vi` **and** `en`. `pipeline/ui_fixtures.py` does this explicitly and reversibly
(`to_codex_export` / `from_codex_export`); the lab form of each fixture is validated against the lab schema.

The source content has no `en` in most explanation fields and no translation was generated. Where `en` is
missing it is a **copy of `vi`**, declared per fixture in `index.json` -> `en_placeholder_paths`; such a
fixture has `production_ready: false` and must not be read as English copy.

Fixtures stay `draft_ai`. They are a dev/visual/reference harness input; the production rule is unchanged:
only `approved` points reach the learner UI.
