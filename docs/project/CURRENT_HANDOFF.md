# Current Handoff

## Governance

Purpose: current execution state only. Authority for durable product intent and technical rules is `PROJECT_MEMORY.md` and the canonical project-memory set. Change when the active lane, verified batch, gates, or next task changes. Do not store secrets, product philosophy, long history, or unverified claims here.

## Current branch / lane

`codex/work` is the product/UI baseline. `feature/orena-intelligence` builds Agent Intelligence against `AGENT_CONTRACT.md`; `feature/grammar-lab-pipeline` owns the isolated Grammar Lab. New learner UI is built under `/next` before cutover; `/` remains the legacy learner UI until the approved cutover. Grammar Lab is the future grammar source; R5 retirement/integration stays behind the documented architecture/human gates.

This handoff is being compacted from the Grammar Lab approval lane. PR #86 (`codex/grammar-approve-command` -> `feature/grammar-lab-pipeline`) adds the explicit human `approve` gate between review/apply-feedback and `export-package`.

## Last verified batch

Grammar Lab CI for PR #86 head `23b124a` passed on 2026-10-07: 697 collected, 695 passed, 2 skipped; `test_approve.py` 6/6; `import-canonical --check` current for EN 215 / ZH 380; `sync-metadata --check` current; `seed-audit --lang all` 0 findings; `corpus-plan --lang all` completed. Corpus plan: 595 canonical; EN 215 generated; ZH 157 generated and 223 ready.

Product/UI historical verification remains in `PROJECT_STATE.md` and related status docs; do not duplicate it here.

## DONE

- Canonical project-memory/governance set exists and is validated by `scripts/validate_project_memory.py`.
- `/next` learner UI foundation plus Wave A/Wave B surfaces are built/reviewable on the product lane; detailed history is in `PROJECT_STATE.md`.
- Agent contract work is isolated on `feature/orena-intelligence`.
- Grammar Lab has canonical catalogs, generation/validation/review/export pipeline, and dedicated CI.
- PR #86 adds human approval with reviewer metadata, fail-closed validation, batch preflight, idempotent already-approved handling, CLI coverage, and README workflow documentation.

## IN PROGRESS

- Human/product review of learner UI and completion roadmap.
- Agent Intelligence lane completion and live product verification.
- Grammar Lab: review generated content by level, apply external feedback, human-approve validated points, then export approved packages.
- Chinese writing evaluator recall remains a separate product-lane issue.

## PENDING

- Human decisions/gates recorded in the product roadmap and decision log.
- Grammar Lab content review/approval, starting with generated HSK levels as chosen by the human.
- R5 -> Grammar Lab integration only after the required architecture review and explicit human approval.
- Public learner-content publication remains gated.

## BLOCKED

- Do not modify production/shared databases, migrations, persistent volumes, provider credentials, deployment, DNS/Cloudflare, billing, or learner-owned persistence without the relevant human gate.
- Any stale sandbox/runtime migration state must be handled through its documented lane/runbook rather than from Grammar Lab work.
- No Grammar Lab content may bypass review by changing `draft_ai` directly to satisfy export.

## OPEN P0

None recorded here. See canonical status/issue documents for newly opened P0 items.

## OPEN P1

See `ORENA_STATUS.md`, `UI_BACKEND_GAPS.md`, and current lane issue/review logs. This file intentionally does not duplicate long issue lists.

## HUMAN GATES

PostgreSQL is authoritative for real product runtime; SQLite is for isolated tests or rollback/archive use. Production/preview mutation, provider credentials, OAuth/DNS/Cloudflare, billing, deployment, destructive lifecycle work, shared-runtime migrations, public learner-content publication, and new learner-owned persistence require explicit human authorization. Never touch persistent volumes as cleanup.

Grammar replacement/integration is protected: Grammar Lab may prepare/validate/export content independently, but replacing live R5-backed product paths is a separate architecture-reviewed phase.

## NEXT EXACT TASK

Grammar Lab:
1. Merge/review PR #86 when its checks are clean.
2. For a reviewed level, run external review -> `apply-feedback` -> validate -> `approve --lang <lang> --level <level> --reviewer <name>`.
3. Run `export-package`; only approved points may export.
4. Do not regenerate content merely to clear `draft_ai`.

Product/UI and Intelligence lanes continue from their own canonical roadmap/contract/status files; do not infer product readiness from Grammar Lab CI.
