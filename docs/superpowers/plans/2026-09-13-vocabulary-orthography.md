# Vocabulary Card and Orthography Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pure, language-neutral Vocabulary Card and orthography contract over Orena's existing saved-word and language owners, including truthful Chinese stroke data and polyphonic readings without persistence changes.

**Architecture:** Keep `vocabulary_card_from_saved_word` as the compatibility projection over the existing learner relationship and review state. Add a shared validator rooted at generic `OrthographicUnit` objects; Chinese adapts the current vendored stroke-order provider into that shape. Optional typed explanation artifacts and assertion-level provenance are validated in the same pure domain layer, with no generation or knowledge store.

**Tech Stack:** Python 3, standard-library mappings/dataclasses/type hints, existing pytest suite, existing vendored Make Me a Hanzi adapter.

**Spec:** `docs/superpowers/specs/2026-09-13-vocabulary-orthography-design.md`

## Global Constraints

- No persistence schema, migration, database, container, provider activation, I2/I3, learner route, UI/theme, or shared project-status changes.
- Existing saved-word identity and Active Recall state remain authoritative.
- `OrthographicUnit` is the shared root; do not make `grapheme` universal.
- Readings remain one-to-many and may bind to senses or exact contexts; never model a character as one pronunciation.
- Mental model, mnemonic, linguistic explanation, and verified etymology/history are distinct optional artifact kinds.
- Unknown orthographic or linguistic facts remain absent/unavailable rather than guessed.
- Verified etymology/history requires trusted source provenance.

### Task 1: Add the generic orthography contract

**Files:**
- Create: `writing_coach/orthography.py`
- Create: `tests/test_orthography_contract.py`

**Interfaces:**
- Produces `validate_orthography(orthography: Mapping[str, Any]) -> None`.
- Produces `OrthographyContractError(ValueError)`.
- Accepts a top-level `{script, units}` payload. Each unit has `surface`, `script`, `unit_kind`, zero or more `readings`, and optional `facts`.
- Each reading has `value`, `notation`, optional `bindings`, and optional provenance.
- Each factual assertion has `value` and `provenance`; provenance accepts source/reference, revision/version, evidence type, rights/license, trusted, and future extension keys.

- [ ] **Step 1: Write the failing tests**

```python
def test_accepts_non_chinese_units_and_multiple_context_bound_readings():
    validate_orthography({
        "script": "arabic",
        "units": [{
            "surface": "ع",
            "script": "arabic",
            "unit_kind": "letter-form",
            "readings": [
                {"value": "ʿ", "notation": "latin", "bindings": [{"kind": "context", "text": "عَلَم"}]},
                {"value": "a", "notation": "latin", "bindings": [{"kind": "context", "text": "عَلِمَ"}]},
            ],
        }],
    })


def test_accepts_assertion_level_provenance_and_extensible_metadata():
    validate_orthography({
        "script": "han",
        "units": [{
            "surface": "学",
            "script": "han",
            "unit_kind": "character",
            "facts": {
                "stroke_count": {"value": 8, "provenance": {"source": "vendor", "version": "1", "evidence_type": "dataset", "license": "MIT"}},
                "components": {"value": [{"surface": "子"}], "provenance": {"reference": "editorial-record", "revision": "r2"}},
            },
        }],
    })


def test_rejects_verified_etymology_without_trusted_provenance():
    with pytest.raises(OrthographyContractError, match="trusted provenance"):
        validate_orthography({
            "script": "han",
            "units": [{
                "surface": "学", "script": "han", "unit_kind": "character",
                "facts": {"etymology": {"value": "a story", "provenance": {"source": "none"}}},
            }],
        })


def test_rejects_missing_or_guessed_factual_provenance():
    with pytest.raises(OrthographyContractError, match="provenance"):
        validate_orthography({
            "script": "han",
            "units": [{
                "surface": "学", "script": "han", "unit_kind": "character",
                "facts": {"stroke_count": {"value": 8}},
            }],
        })
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `python -m pytest -q -p no:cacheprovider tests/test_orthography_contract.py`

Expected: collection fails because `writing_coach.orthography` and `validate_orthography` do not exist.

- [ ] **Step 3: Implement the minimal shared validator**

Implement mapping/list/text helpers, generic unit and reading validation, assertion validation, and the verified-etymology rule. Preserve unknown provenance keys for forward compatibility, but type-check known metadata when present. Do not add language-specific branches.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `python -m pytest -q -p no:cacheprovider tests/test_orthography_contract.py`

Expected: all Task 1 tests pass.

### Task 2: Adapt Chinese stroke data to the generic contract

**Files:**
- Create: `writing_coach/languages/chinese/orthography.py`
- Create: `tests/test_chinese_orthography.py`

**Interfaces:**
- Produces `build_chinese_orthography(word: str, *, readings: Mapping[str, Sequence[Mapping[str, Any]]] | None = None, facts: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]`.
- Reuses `writing_coach.languages.chinese.stroke_order.stroke_order_for` and never computes or guesses missing radical, component, reading, or etymology facts.
- Emits generic `script: "han"` and `units`; each verified stroke count and stroke-order representation carries Make Me a Hanzi source/version provenance.

- [ ] **Step 1: Write the failing tests**

```python
def test_builds_generic_chinese_units_from_verified_stroke_owner():
    result = build_chinese_orthography("学习")
    assert result["script"] == "han"
    assert [unit["surface"] for unit in result["units"]] == ["学", "习"]
    assert result["units"][0]["facts"]["stroke_count"]["value"] == 8
    assert result["units"][0]["facts"]["stroke_count"]["provenance"]["source"] == "make-me-a-hanzi"
    assert result["units"][0]["facts"]["stroke_order"]["value"]["representation"] == "svg-paths"


def test_preserves_polyphonic_readings_and_context_bindings_without_collapsing_them():
    result = build_chinese_orthography(
        "银行",
        readings={"行": [
            {"value": "xíng", "notation": "pinyin", "bindings": [{"kind": "sense", "id": "bank"}]},
            {"value": "háng", "notation": "pinyin", "bindings": [{"kind": "context", "text": "银行"}]},
        ]},
    )
    readings = result["units"][1]["readings"]
    assert [reading["value"] for reading in readings] == ["xíng", "háng"]
    assert readings[0]["bindings"] != readings[1]["bindings"]


def test_does_not_invent_radical_components_or_etymology():
    result = build_chinese_orthography("学")
    facts = result["units"][0]["facts"]
    assert "radical" not in facts
    assert "components" not in facts
    assert "etymology" not in facts
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `python -m pytest -q -p no:cacheprovider tests/test_chinese_orthography.py`

Expected: collection fails because the Chinese generic adapter does not exist.

- [ ] **Step 3: Implement the adapter**

Convert each provider character entry into one `OrthographicUnit`, map stroke paths/medians into a generic `stroke_order` representation, attach assertion provenance, copy only caller-supplied readings and trusted facts, and omit unavailable facts. Call `validate_orthography` before returning.

- [ ] **Step 4: Run focused and existing Chinese tests**

Run: `python -m pytest -q -p no:cacheprovider tests/test_chinese_orthography.py tests/test_chinese_stroke_order.py`

Expected: all new and existing Chinese stroke-order tests pass.

### Task 3: Enrich and validate Vocabulary Cards

**Files:**
- Modify: `writing_coach/vocabulary_cards.py`
- Modify: `tests/test_vocabulary_cards.py`

**Interfaces:**
- Produces `validate_vocabulary_card(card: Mapping[str, Any]) -> None`.
- Extends `vocabulary_card_from_saved_word` with optional `enrichments: Mapping[str, Any] | None = None` while preserving existing callers and saved-word memory fields.
- Optional `enrichments` keys are `meanings`, `examples`, `collocations`, `related`, `learner_traps`, `learner_examples`, `understanding_refs`, and `explanation_artifacts`; supplied values are preserved as one-to-many entries and validated.
- Explanation artifacts use one of `mental_model`, `mnemonic`, `linguistic_explanation`, `verified_etymology`; verified etymology requires trusted provenance, while all four remain optional.

- [ ] **Step 1: Write the failing tests**

```python
def test_card_preserves_rich_one_to_many_content_and_horizontal_understanding_refs():
    card = vocabulary_card_from_saved_word(
        {"word": "学习", "normalized_word": "学习", "language_code": "zh"},
        enrichments={
            "meanings": [
                {"sense_id": "study", "language": "en", "text": "to study", "contexts": ["我学习中文。"]},
                {"sense_id": "learn", "language": "en", "text": "to learn", "contexts": ["学习经验"]},
            ],
            "examples": [{"text": "我学习中文。", "source": {"kind": "reading", "id": "r1"}}],
            "understanding_refs": [{"id": "u1", "kind": "linguistic_explanation", "context": "我学习中文。"}],
            "explanation_artifacts": [{"kind": "mental_model", "text": "A deliberate learning image."}],
        },
    )
    validate_vocabulary_card(card)
    assert len(card["meanings"]) == 2
    assert card["meanings"][0]["contexts"] == ["我学习中文。"]
    assert card["understanding_refs"][0]["kind"] == "linguistic_explanation"
    assert card["explanation_artifacts"][0]["kind"] == "mental_model"


def test_card_rejects_unprovenanced_verified_etymology_but_allows_other_optional_artifacts():
    card = vocabulary_card_from_saved_word(
        {"word": "学", "language_code": "zh"},
        enrichments={"explanation_artifacts": [
            {"kind": "mnemonic", "text": "A memory aid."},
            {"kind": "verified_etymology", "text": "A historical claim."},
        ]},
    )
    with pytest.raises(VocabularyCardError, match="trusted provenance"):
        validate_vocabulary_card(card)
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `python -m pytest -q -p no:cacheprovider tests/test_vocabulary_cards.py`

Expected: the new tests fail because `enrichments`, `validate_vocabulary_card`, and `VocabularyCardError` are not implemented.

- [ ] **Step 3: Implement card enrichment and validation**

Preserve legacy row projection behavior, copy non-empty optional enrichment collections without inventing entries, validate the shared orthography contract when present, validate rich card collections and explanation kinds, and keep review state sourced only from the row.

- [ ] **Step 4: Run the focused vocabulary and JavaScript contract tests**

Run: `python -m pytest -q -p no:cacheprovider tests/test_vocabulary_cards.py`; `node scripts/test_orena_vocabulary_card.mjs`

Expected: all existing and new Vocabulary Card tests pass, and the existing renderer contract remains green.

### Task 4: Full verification and checkpoint

**Files:**
- No additional production files.

- [ ] **Step 1: Run touched-file lint/compile checks**

Run: `ruff check writing_coach/orthography.py writing_coach/vocabulary_cards.py writing_coach/languages/chinese/orthography.py tests/test_orthography_contract.py tests/test_chinese_orthography.py tests/test_vocabulary_cards.py` and `python -m compileall -q writing_coach/orthography.py writing_coach/vocabulary_cards.py writing_coach/languages/chinese/orthography.py`.

Expected: exit code 0 for each command where the tool is installed; if a host tool is unavailable, record the environment limitation rather than changing application code.

- [ ] **Step 2: Run the complete relevant Python test set**

Run: `python -m pytest -q -p no:cacheprovider tests/test_vocabulary_cards.py tests/test_orthography_contract.py tests/test_chinese_orthography.py tests/test_chinese_stroke_order.py tests/test_grammar_universal_architecture.py tests/test_grammar_learning_model.py`

Expected: 0 failures.

- [ ] **Step 3: Inspect scope and Git state**

Run: `git diff --check`; `git status --short`; `git diff --stat codex/work...HEAD`.

Expected: only the approved spec, plan, contract, adapter, and tests are changed; no persistence, UI/theme, I2/I3, status-document, DB, or container artifacts appear.

- [ ] **Step 4: Commit the implementation**

```bash
git add docs/superpowers/plans/2026-09-13-vocabulary-orthography.md writing_coach/orthography.py writing_coach/vocabulary_cards.py writing_coach/languages/chinese/orthography.py tests/test_orthography_contract.py tests/test_chinese_orthography.py tests/test_vocabulary_cards.py
git commit -m "feat: add vocabulary orthography contracts"
```

- [ ] **Step 5: Verify clean branch and report**

Run: `git status --short`; `git branch --show-current`; `git rev-parse HEAD`.

Expected: empty status, branch `agent/vocab-orthography`, and a recorded commit SHA ready for handoff without merging into `codex/work`.
