# Grammar Corpus Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-point rescue loops with one corpus-wide stabilization workflow that salvages cache once, inventories every remaining failure by class, applies deterministic quality gates, and exposes one final acceptance gate for EN 215/215 and ZH 380/380.

**Architecture:** Reuse the existing deterministic validator as the structural authority. Add a stabilization layer that parses cache-only generation outcomes, groups failures by stable categories, audits objective learner-content quality, reads deferred state, and emits one machine-readable report. A CLI command runs a single cache-only corpus sweep (never provider-backed), then produces the report; later repairs/regeneration consume the report by category rather than stopping on the first point.

**Tech Stack:** Python 3.12, Typer, existing Grammar Lab validator/corpus planner/generator, pytest.

**Spec:** `docs/grammar_lab/GRAMMAR_CONTENT_CONTRACT.md` plus the canonical catalog and current v0.4 schema.

## Global Constraints

- No provider call in stabilization audit mode.
- Do not weaken existing validators or mark content approved automatically.
- Valid cached candidates may be materialized; invalid candidates are reported, never guessed into validity.
- Content quality gates are objective and deterministic; semantic ambiguity remains a regeneration/review item.
- Final acceptance requires canonical completeness, zero ready/blocked/deferred points, zero validator issues, and zero deterministic quality blockers.

## Review Focus

- Cache miss must be distinct from invalid cached content.
- One malformed candidate must not stop the corpus-wide audit.
- Duplicate examples/practice must be reported as quality blockers even if schema-valid.
- Deferred points must remain visible in the final acceptance report.
- A partial corpus must never report `accepted=true`.

---

### Task 1: Stabilization report core

**Files:**
- Create: `grammar_lab/pipeline/stabilize.py`
- Create: `grammar_lab/tests/test_stabilize.py`

**Interfaces:**
- Produces `classify_generation_reason(reason)`, `parse_generation_log(text)`, `quality_issues(point)`, and `build_stabilization_report(lang, root, probe_outcomes=None)`.

- [ ] Write RED tests for cache-miss vs formula/binding/practice categories and objective quality blockers.
- [ ] Implement the minimal pure functions.
- [ ] Verify focused tests GREEN.

### Task 2: Corpus-wide audit and one-process cache salvage

**Files:**
- Modify: `grammar_lab/pipeline/stabilize.py`
- Modify: `grammar_lab/pipeline/cli.py`
- Test: `grammar_lab/tests/test_stabilize.py`

**Interfaces:**
- Produces CLI `stabilize-corpus --lang en|zh [--skip-cache-sweep] [--json] [--out PATH]`.

- [ ] RED-test command contract and acceptance behavior.
- [ ] Run exactly one child `generate-corpus --cache-only --one-shot --no-paid-repairs` invocation for the selected language; capture all outcomes without provider access.
- [ ] Build/report the post-salvage corpus state.
- [ ] Verify focused tests GREEN.

### Task 3: Deterministic learner-quality gate

**Files:**
- Modify: `grammar_lab/pipeline/stabilize.py`
- Test: `grammar_lab/tests/test_stabilize.py`

**Interfaces:**
- Quality blockers cover duplicate examples, duplicate quick-practice prompts, wrong fixed v0.4 cardinalities, duplicated mistake pairs, and missing personal-production content on generated v0.4 points.

- [ ] RED-test each objective blocker.
- [ ] Implement blockers without subjective language scoring.
- [ ] Verify focused tests GREEN.

### Task 4: Final acceptance and documentation

**Files:**
- Modify: `grammar_lab/README.md`
- Modify: `grammar_lab/pipeline/cli.py`
- Test: `grammar_lab/tests/test_stabilize.py`

**Interfaces:**
- Report contains `accepted`, `acceptance_blockers`, grouped failure counts, per-point findings, and deferred IDs.

- [ ] RED-test that incomplete/dirty corpus cannot be accepted.
- [ ] Document stabilization as the required path before any further paid generation.
- [ ] Run full `python -m pytest grammar_lab/tests` and existing deterministic gates.
