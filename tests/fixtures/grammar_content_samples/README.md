# Grammar content samples (fixtures, NOT approved content)

**SAMPLE DATA for UI development. Not reviewed, not approved, not for learners.**

13 grammar points (10 English, 3 Chinese) in the shape of
`docs/project/GRAMMAR_CONTENT_CONTRACT.md` (schema v0.4 with the 2026-09-30 patch), written by the
Grammar Lab lane as AI drafts (`status: draft_ai`). They exist so the Grammar Library and Grammar
Concept screens can be built against real data before any point is approved.

- `points/<id>.json` - one point each, contract fields only (Grammar Lab's internal `provenance`,
  `review` and `flags` are left out).
- `functions.json` - the display label of every `function` in use; each `title` has `vi`, `en` and
  `zh-Hans` (Library group headers).
- `index.json` - the set: `sample: true`, `approved: false`, one row per point.

Things to know when reading them:

- Only `header.title`, `header.summary`, `header.sub`, `personal_production.prompt` and the
  function labels carry `en`; every other explanation is `vi` only. That is legal for a draft (`vi`
  always, `en` at `approved`), and it is also a real test of the fallback to `en`.
- The Chinese locale key is `zh-Hans` (not `zh`), as in Grammar Lab's schema.
- `sequence` orders points within a `function` + `level`; it is not yet a global order.
- The wording, examples and quick-practice options are drafts; the explanations may be replaced
  when the points are regenerated and reviewed. Do not copy them into product copy.
- Two points list a contrast without a `compare` block on the other side
  (`en.present_simple.third_person_s`, `en.past_simple`): `contrasts` is symmetric, `compare` is not
  required to be.

They validate clean under Grammar Lab's validator (`python -m grammar_lab.pipeline.cli validate`,
on branch `feature/grammar-lab-pipeline`). This directory is data only; there is no code here.
