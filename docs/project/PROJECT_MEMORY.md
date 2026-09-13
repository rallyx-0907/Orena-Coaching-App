# Orena Project Memory

## Purpose and authority

This is the canonical entrypoint for restoring Orena project context without
chat history. Repository memory is authoritative and persistent; an agent's
conversation memory is temporary and must never be treated as project state.

This file defines how memory is loaded and maintained. Agents may update its
operating procedure when an explicitly approved governance change requires it.
It must change when the memory topology or precedence model changes. It must not
contain feature history, implementation inventories, or transient task notes.
Do not store secrets, historical closeouts, or unverified success here.

## Session startup

Every implementation or review session starts by checking:

```text
git branch --show-current
git rev-parse HEAD
git status --short
git log -5 --oneline
```

Then read only this canonical sequence:

Then read this canonical sequence:

1. `docs/project/PROJECT_MEMORY.md`
2. `docs/product/ORENA_PRODUCT_CONSTITUTION.md`
3. `docs/product/ORENA_CONTENT_ARCHITECTURE.md`
4. `assets/brand/orena/README.md` for learner-facing visual/brand work
5. `docs/project/PRODUCT_CONSTITUTION.md`
6. `docs/project/CURRENT_PRODUCT_STATE.yaml`
7. `docs/project/LEGACY_TOMBSTONES.md`
8. `docs/product/ORENA_STATUS.md`
9. `docs/project/CURRENT_HANDOFF.md`
10. only the relevant section of `docs/project/PRODUCT_MAP.md`
11. only the relevant section of `docs/project/ROADMAP.md`
12. relevant code and tests for the current task

Consult `docs/project/DECISION_LOG.md` only when a durable product or
architecture decision is relevant. Read `docs/project/DESIGN_CONTRACT.md` for
UI/native work and `docs/project/REVIEW_POLICY.md` for review or checkpoint
acceptance. Do not load archived handoffs or all historical documents by
default.

The `/resume-orena` workflow performs this bounded restore. It does not replace
the live Git checks above.

## Memory topology

| File                         | Purpose                                 | Authority / editor                                                               | Change trigger                                     | Never store                                    |
| ---------------------------- | --------------------------------------- | -------------------------------------------------------------------------------- | -------------------------------------------------- | ---------------------------------------------- |
| `PRODUCT_CONSTITUTION.md`    | Durable Orena product intent            | Human-governed; agents only with explicit human instruction                      | Accepted durable principle change                  | Current task status or implementation excuses  |
| `CURRENT_PRODUCT_STATE.yaml` | Compact machine-readable verified truth | Agents after verification; schema-enforced                                       | Verified current truth changes                     | Narrative history, secrets, unverified success |
| `LEGACY_TOMBSTONES.md`       | Retired or forbidden directions         | Human-governed                                                                   | Explicit accepted retirement/supersession          | Ordinary backlog or temporary bugs             |
| `CURRENT_HANDOFF.md`         | Current execution state only            | Active agent after verification                                                  | Lane, status, gates, blocker, or next task changes | Product philosophy or historical closeouts     |
| `PRODUCT_MAP.md`             | Current learner/product architecture    | Human-governed for product direction; agents for accepted contract clarification | Accepted architecture relationship changes         | Source inventory or implementation history     |
| `DESIGN_CONTRACT.md`         | Durable web/native experience rules     | Human-governed                                                                   | Explicit accepted design-direction change          | Page-specific polish notes                     |
| `DECISION_LOG.md`            | Append-only durable decisions           | Agent may append only after explicit human direction/accepted decision           | Durable decision changes                           | Rewritten history                              |
| `ROADMAP.md`                 | Approved staged program                 | Human-approved status transitions                                                | Roadmap or stage transition                        | Session notes                                  |

`PROJECT_STATE.md`, `ARCHITECTURE_INVARIANTS.md`, `DOMAIN_BOUNDARIES.md`, release
matrices, and archived handoffs remain supporting evidence. They are not part
of every startup context.

## Precedence: intent versus fact

Product intent precedence:

```text
explicit current human instruction
→ docs/product/ORENA_PRODUCT_CONSTITUTION.md
→ docs/product/ORENA_CONTENT_ARCHITECTURE.md
→ assets/brand/orena/ for brand / mascot / visual identity work
→ accepted DECISION_LOG entries
→ docs/project/PRODUCT_CONSTITUTION.md for non-superseded compatibility invariants
→ DESIGN_CONTRACT and LEGACY_TOMBSTONES
→ CURRENT_PRODUCT_STATE
→ CURRENT_HANDOFF
→ implementation
```

Implementation fact precedence:

```text
actual code, tests, runtime evidence, and verified Git state
→ CURRENT_PRODUCT_STATE
→ CURRENT_HANDOFF
→ ROADMAP and supporting docs
```

Directory names, old filenames, historical symbols, archived scripts, stale
screenshots, deprecated routes, branch names, comments, and legacy
documentation never establish current product direction.

## Contradictions

When implementation contradicts durable product intent, implementation is the
suspect. Do not rewrite governance to make stale code appear correct. Report:

```text
MEMORY CONTRADICTION
Conflicting implementation:
Governing product rule:
Likely stale side:
Human decision required (only if genuinely ambiguous):
```

If implementation facts disagree with machine state or handoff, verify the
implementation/runtime and update current memory only after evidence exists.
Do not claim CI PASS from a local run, production readiness from tests, visual
parity from a component's existence, or real content completeness from mocks.

## Memory transaction

Every coherent batch follows:

```text
IMPLEMENT
→ TEST
→ VERIFY
→ UPDATE CURRENT MEMORY IF VERIFIED TRUTH CHANGED
→ python scripts/validate_project_memory.py
→ COMMIT
```

- Update `CURRENT_PRODUCT_STATE.yaml` only when verified current truth changes.
- Update `CURRENT_HANDOFF.md` when lane, progress, blockers, gates, or exact next
  task changes.
- Append `DECISION_LOG.md` only for a durable decision.
- Do not change `PRODUCT_CONSTITUTION.md`, fundamental `DESIGN_CONTRACT.md`
  principles, or `LEGACY_TOMBSTONES.md` without explicit human authorization.
- A durable principle change requires explicit human instruction, a new
  Decision Log entry, explicit supersession where applicable, and matching
  state/validator updates.
- Never store secrets or credential values in project memory.

If verified implementation truth changed but current memory did not, the batch
is incomplete.
