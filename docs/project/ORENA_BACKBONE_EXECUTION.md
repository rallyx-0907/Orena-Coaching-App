# Orena architecture backbone execution

Status: REVIEWABLE; architecture backbone specified and independently reviewed.
Scope: principal architecture, under the human instruction
of 2026-09-08. Product Golden Star acceptance is a separate, still-open mission.

**Goal:** establish the remaining reference backbone so Opus can implement
features without inventing ownership, consistency or cross-domain contracts.
**Architecture:** retain the modular monolith, existing domain repositories and
eleven destinations. Specify additive seams; do not replace completed A-D.
**Tech stack:** existing Python/PostgreSQL services and browser ES modules.
**Spec:** `docs/product/ORENA_REFERENCE_ARCHITECTURE.md`, its linked backbone
contracts, Product Constitution and Content Architecture.

Use Superpowers execution and verification methodology within the existing lane.
This file is the execution ledger referenced by CURRENT_HANDOFF, not a second
project-memory system. No production, schema activation or human approval implied.

## Restore and coordination

Previous Codex checkpoint: `8535cf140139f910562d4370d0438606032a6418`.
Inspected HEAD: `fe963bfcd8c7ffecddf9737db5ac818cf81f842e` on `codex/work`.
Opus commits since that checkpoint: `542daae`, `220b148`, `cec1e20`, `8a56dbb`,
`47f783d`, `f68f31a`, `f7d3fd9`, `d872f09`, `fe963bf`.
A-D completion is recorded by Opus in GOLDEN_STAR_COMPLETION and corroborated
by the changed context/outcome/intent/memory implementations and gates. This
session does not repeat its browser acceptance or claim fresh UI evidence.
Theme implementation is committed; theme and all active brand asset WIP remain
reserved. Inspect HEAD/status before each cycle and before shared-doc edits.

## Ordered architecture milestones

| ID | Status | Deliverable | Dependency / exit evidence |
| --- | --- | --- | --- |
| B1 | DONE | Existing reference A-D reconciled | Git comparison; preserve Opus work |
| B2 | DONE | Domain and cross-domain contract map | Owners, identifiers, transitions, language, adapters |
| B3 | DONE | Account/work/persistence and learner profile | Account specification; reviewed incarnation/commit-order fixes |
| B4 | DONE | Commerce, subscription, entitlement and quota | Commerce specification; quota scenarios and independent review |
| B5 | DONE | Collection / My Content / My Language | Collection specification; scoped cursor/domain identity scenarios |
| B6 | DONE | Content and provider/job lifecycle | Execution specification; cancellation/lease scenarios |
| B7 | DONE | Profile/Growth/achievement projections | Evidence specification; version/invalidation/comparison scenarios |
| B8 | DONE | Cross-domain integration and migration gates | I1-I7 handoff, 18 pure tests, validators, independent review |

For each milestone: inspect live Git; implement in dedicated architecture files;
verify its contract against source anchors and counterexamples; record evidence;
continue. Final checkpoint stages only these files and current-state links.

## Completion definition

All eight milestones must have a reviewed deliverable and reproducible evidence.
Every major current domain must have an owner, contract, lifecycle, failure and
consistency rules, implementation destination and acceptance conditions.
Future Social/Notifications/native have explicit boundaries without invented
functionality. Ordinary feature work must not require a new identity, source,
evidence, work, synchronization or provider architecture.

Architecture completion does not claim runtime implementation, cross-device
sync, successful migration, load capacity, live-provider quality, or Golden
Star approval. Gated operational values and product policies remain explicit
deployment inputs; no destructive behavior may guess their values.

## Verification and findings

Local execution: 18 pure contract tests passed, 0 failed, 0 skipped. Initial red
execution failed because the reference module did not exist; green followed its
implementation. Reviewer independently executed the same 18 tests successfully.
Memory validator and architecture validator passed. Reference topology check
resolved six companion specifications and integration gates; Python AST parsed
both new code files. Diff whitespace check passed. Ruff initially found one
obsolete typing import; corrected to collections.abc and rechecked.
No new application behavior, full-suite, browser or CI PASS claimed.

Independent review initially requested changes for commit-order/snapshot safety
and deleted-account reincarnation; both contracts were corrected. Source excerpt
revocation, anchor paths, projection incarnation and complete focus identity were
also clarified. Final verdict: APPROVE bounded architecture handoff, no new
architecture P0/P1. This is technical review, not human product approval.

Known implementation gap: `writing_coach/persistence/runtime.py` calls
`_bootstrap_empty_runtime()` from `_verify_runtime_readiness()`, which executes
Alembic upgrade. D-002 and ARCHITECTURE_INVARIANTS prohibit startup auto-Alembic.
Target is explicit operator migration and read-only startup verification.
Track as P1 before persistence activation/merge; do not normalize the discrepancy
by editing the invariant. No runtime or migration is executed here.

## Checkpoint evidence and implementation boundary

Architecture milestones: 8/8. Contract implementation is limited to pure decisions
in `writing_coach/reference_backbone.py`; no production caller was wired to them.
The transaction/identity/admission guarantees require I1-I7 adapters and the
real integration matrix. The matrix explicitly records pending PostgreSQL,
provider, billing, browser, migration and restore evidence. Do not conflate
architecture completeness with implementation completeness.

Exact task files:

- `.github/workflows/ci.yml`
- `docs/product/ORENA_REFERENCE_ARCHITECTURE.md`
- `docs/product/ORENA_BACKBONE_CONTRACTS.md`
- `docs/product/ORENA_ACCOUNT_DATA_ARCHITECTURE.md`
- `docs/product/ORENA_COMMERCE_ARCHITECTURE.md`
- `docs/product/ORENA_COLLECTION_ARCHITECTURE.md`
- `docs/product/ORENA_CONTENT_EXECUTION_ARCHITECTURE.md`
- `docs/product/ORENA_EVIDENCE_ARCHITECTURE.md`
- `docs/product/ORENA_STATUS.md`
- `docs/project/ORENA_BACKBONE_EXECUTION.md`
- `docs/project/ORENA_BACKBONE_INTEGRATION_GATES.md`
- `docs/project/CURRENT_HANDOFF.md`
- `docs/project/CURRENT_PRODUCT_STATE.yaml`
- `docs/project/DECISION_LOG.md`
- `scripts/test_orena_backbone.py`
- `writing_coach/reference_backbone.py`

Full base SHA is recorded above. Resolve this checkpoint's full SHA with
`git log -1 --format=%H -- docs/project/ORENA_BACKBONE_EXECUTION.md` after commit.
The user-facing final also names the resulting commit. Stage only the 16 files
above; preserve and leave unstaged all pre-existing brand asset changes.
Pre-stage reserved Git status: 25 modified brand files, 24 deleted brand files,
8 untracked brand paths (including directories). No theme/brand path is in this
checkpoint's index. HEAD remained fe963bf throughout the architecture cycles.

Protected UI/brand/theme/native/visual-reference changes: none by Codex.
Persistence/schema/runtime/provider/deployment/production changes: none.
Application version remains 1.4.0; frontend remains 2.17.5. PROJECT_STATE unchanged;
CURRENT_HANDOFF changed. D-048 records the explicit human role/scope direction,
not invented product policy. Historical verified application commit/time in
CURRENT_PRODUCT_STATE remain historical, rather than being relabeled by this run.

Remaining product/runtime findings stay in CURRENT_HANDOFF and the Golden Star
ledger. Recall/Writing/context findings remain tracked there as closed. Collection
navigation promotion, prices/grace/retention/achievement policies, live providers,
microphone, production and final human visual acceptance remain their named gates.
Ordinary Opus adapter/feature work proceeds in I1-I7 order; Codex owns any contract
deviation or new foundational question. Never restart completed A-D.
