# HOW TO APPLY THIS GOVERNANCE UPDATE

This package is designed to merge into the existing Orena repository governance without destroying current rules.

## Do not overwrite existing governance files blindly

The patch files are additions/updates. An implementation agent should inspect current contents and merge semantically.

## Target mapping

- `PRODUCT_CONSTITUTION_PATCH_2026-09-17.md`
  → merge into `docs/project/PRODUCT_CONSTITUTION.md`

- `DESIGN_CONTRACT_PATCH_2026-09-17.md`
  → merge into `docs/project/DESIGN_CONTRACT.md`

- `ORENA_UI_AGENT_RULES.md`
  → use as/update the repo's short machine-oriented UI rules file. If the repo already has `docs/ORENA_UI_AGENT_RULES.md`, merge and remove contradictions instead of creating a duplicate.

- `AGENTS_ROUTER_PATCH_2026-09-17.md`
  → merge only the mandatory-read/router section into root `AGENTS.md`

- `DECISION_LOG_ENTRY_2026-09-17.md`
  → append as a durable decision to `docs/project/DECISION_LOG.md` using the repository's existing decision format/ID.

- `ORENA_DESIGN_AUDIT_RECOVERY_PLAN.md`
  → supporting audit/evidence; it is NOT higher authority than Product Constitution or Design Contract.

## Do NOT put these rules into

- `GOLDEN_STAR_COMPLETION.md` as design authority;
- current-state files as if they were permanent laws;
- implementation status/handoff as the only durable source.

## Required merge verification

After merge, ask the agent to report:

1. exact files changed;
2. exact sections added/updated;
3. any old rules that conflicted and how the conflict was resolved;
4. confirmation that AGENTS.md routes to the authoritative files;
5. confirmation that no duplicate/contradictory design constitutions remain;
6. `git diff --check`;
7. links/line references for the final authoritative clauses.

## Suggested instruction to the coding agent

"Merge the attached 2026-09-17 Orena governance patches into the repository's existing canonical governance architecture. Do not replace existing files wholesale. Preserve unrelated durable rules. Resolve contradictions in favor of the new dated direction only where the new patch explicitly supersedes old design/product direction. Keep AGENTS.md as a router, PRODUCT_CONSTITUTION as product authority, DESIGN_CONTRACT as durable UI/UX authority, and DECISION_LOG as the historical decision record. Then show me the exact diff and do not begin UI refactoring until I approve the governance diff."
