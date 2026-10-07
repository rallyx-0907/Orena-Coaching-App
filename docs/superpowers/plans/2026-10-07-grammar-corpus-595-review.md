# Grammar Corpus 595 Review Implementation Plan

> **For agentic workers:** Review and correct the complete Grammar Lab corpus without paid regeneration.

**Goal:** Review all 595 canonical grammar points (EN 215, ZH 380) on an isolated branch and correct only learner-impacting errors.

**Architecture:** Work level-by-level. First run deterministic structural checks across the corpus, then review semantic hotspots (knowledge, scope, ambiguous quick-practice answers, invalid error examples, pattern/pinyin mismatches). Apply only bounded corrections; do not rewrite acceptable content for style.

**Tech Stack:** Grammar Lab JSON corpus, Python validators/tests, GitHub branch/CI.

## Global Constraints

- No paid LLM/provider calls.
- Preserve canonical membership and level assignment unless a verified catalogue error is found.
- Fix blocker/major learner-impacting issues; ignore cosmetic wording unless misleading.
- Every quick-practice item must have exactly one defensible answer.
- Chinese pinyin/spans must match the written sentence and context.
- Run Grammar Lab validation/tests before completion.

## Tasks

- [ ] Inventory all 595 points and establish current validation baseline.
- [ ] Review EN A1-C2 by level and apply bounded fixes.
- [ ] Review ZH HSK1-HSK9 by level and apply bounded fixes.
- [ ] Re-run full Grammar Lab tests, canonical import/check, metadata sync/check, seed audit, corpus plan, and validate.
- [ ] Produce review summary with counts by level and issue class.
