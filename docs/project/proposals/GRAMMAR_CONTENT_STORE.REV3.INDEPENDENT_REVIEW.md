# Independent architecture review: Grammar Content Store revision 3a

- **Reviewer:** ChatGPT (GPT-5.6 Sol), acting as **Delegated Architecture Reviewer** under `AGENTS.md` section "Architecture review authority".
- **Independence:** I did not author revision 3/3a, the proposed migration, the rehearsal, or the implementation commits. I previously reviewed the PR conversationally and identified issues, but made no implementation changes before this review.
- **Reviewed PR:** #100.
- **Reviewed commit:** `06130921efdde5e9b21f1a4a85f6026b8a1f43f5` (`codex/work`).
- **Base:** `main` `a2342e620b91307ed6ee5cb754a0edbaa286073d`.
- **Policy:** `AGENTS.md` architecture-review rules and `docs/project/REVIEW_POLICY.md`.
- **Files inspected for the Grammar gate:** `GRAMMAR_CONTENT_STORE.md` revision 3a; `GRAMMAR_CONTENT_STORE.REV3_REVIEW_REQUEST.md`; `GRAMMAR_CONTENT_STORE.REHEARSAL.md`; `migrations/proposed/20261008_0030_grammar_content_store.py`; `scripts/check_grammar_export_contract.py`; `scripts/rehearse_grammar_content_store.py`; `tests/test_grammar_content_store_migration.py`; prior `GRAMMAR_CONTENT_STORE.REVIEW.md`; `CURRENT_HANDOFF.md`; the PR diff and current CI state.
- **Execution:** I did **not** rerun the local PostgreSQL rehearsal or local test suite. I inspected their recorded evidence and code. I independently verified GitHub Actions CI run `37737089459` for the reviewed head completed with conclusion `success`. No local PASS is claimed by this review.

## Verdict: **REQUEST CHANGES**

The Grammar Store architecture itself is now in substantially good shape: the two Codex P1 findings from `3f971976` are resolved in revision 3a, the migration remains additive and separated from learner-owned data, the rollback model is coherent, and the evidence package is materially stronger. However, the **actual reviewed PR head no longer matches the approved task scope**. Under `REVIEW_POLICY.md`, that is a merge-blocking P1.

## P1 findings

### P1-1 — PR #100 is no longer an architecture/migration-gate-only change

The PR body explicitly says this PR covers the **architecture/migration gate only**, adds no Store/API code, and applies no migration. At reviewed head `06130921`, the diff from `main` contains 28 files, including runtime and deployment changes unrelated to the Grammar Store review:

- `app.py`
- `auth_support.py`
- `writing_coach/core/deployment.py`
- `writing_coach/agent/api.py`
- `static/orena/agent/presence.js`
- `writing_coach/listening_catalog.py`
- `.env.example`
- `scripts/reading_canonical_cutover.py`
- `scripts/reading_canonical_e2e.py`
- `scripts/validate_public_staging_readiness.py`
- `tests/test_staging_environment.py`
- deployment/public-runtime documentation and decision-log changes.

The delta from the previously reviewed Grammar head `fd0fd1e3` to `06130921` is two commits and includes material public-runtime behavior. For example, `writing_coach/core/deployment.py` adds a new `staging` environment and changes public-environment security behavior; `app.py` changes developer-doc exposure and agent enabling. These are not project-memory-only edits and are not part of issue #99's Grammar architecture/migration gate.

`REVIEW_POLICY.md` requires reviewing the actual diff, says scope creep is reviewable and may be P1 when it increases risk or bypasses an approved boundary, and requires unexpected cross-domain changes to have ownership and regression evidence. Merging #100 in its current form would couple a high-risk schema gate with unrelated deployment/auth/agent/runtime changes and would make the architecture approval ambiguous.

**Required change:** isolate the Grammar work again before requesting architecture approval. Either:

1. move the unrelated staging/deployment/runtime commits to their own PR and restore #100 to the Grammar-only delta, or
2. merge those unrelated commits to `main` through their own approved path first, then rebase/retarget #100 so its remaining diff is only the Grammar gate.

After isolation, request a fresh independent review on the new exact head SHA. Do not treat this review as approval of the contaminated head.

## P2 findings / conditions for the next review

### P2-1 — Evidence summary drift

`GRAMMAR_CONTENT_STORE.md` still contains a summary line saying the migration was rehearsed on PostgreSQL 16 with **59 PASS**, while the current rehearsal evidence is **66 PASS, 0 FAIL**. This does not invalidate the architecture, but the proposal and evidence should agree before the gate closes.

### P2-2 — Re-parenting requires fresh chain evidence

`0030` currently has `down_revision = 20261007_0029`. The proposal correctly notes that proposed `0026` is also parented on `0029` and whichever migration is promoted second must be re-parented. If `0030` is re-parented before promotion, the current PostgreSQL chain rehearsal is no longer evidence for the exact migration being promoted. Re-run the chain/downgrade rehearsal and review the changed migration after any re-parenting.

### P2-3 — Function-label boundary should be aligned upstream before first real import

Revision 3a intentionally makes the app importer stricter than the current exporter for function labels: importer requires `vi`, `en`, `zh`, while the exporter currently requires only `vi`, `en`. The present 43/43 labels satisfy all three, so this is not a current corpus blocker. Align the upstream exporter/contract before relying on this boundary for future packages.

## Architecture judgement on revision 3a

Subject to the P1 scope isolation above, I agree with the revision 3a answers:

- **R3-1 `source_dirty`:** reject dirty-tree packages.
- **R3-2 served body:** whitelist export-profile top-level keys minus `source_refs`.
- **R3-3 stronger DB rules:** keep the immutability/delete trigger, append-only events, publish gate, published projection, id/language agreement and one-resolution-per-R5-id constraints.
- **R3-4 function labels:** the stricter importer is safe for the current corpus; align exporter before future production use.
- **R3-5 promotion order:** either migration may go first, but a changed parent requires fresh rehearsal/review evidence.
- **R3-6 runtime:** remains a human decision.
- **R3-7 review verdict vs serving state:** approve the split: `review_status = imported|accepted|rejected`; `superseded_at` records serving supersession. This makes rollback coherent without erasing a prior acceptance decision.

The two earlier Codex P1s are resolved in the reviewed Grammar files:

1. Missing `jsonschema` or PyYAML now produces a FAIL/NOT RUN and non-zero checker exit rather than a false PASS.
2. A superseded version remains `accepted`, so rollback can republish it through the normal publish gate; `superseded_at` is distinct from review verdict.

The rehearsal also now validates every synthetic body against the pinned export profile before import and contains a negative control proving the removed `rehearsal_marker` would be rejected.

## Gate state

- Grammar architecture core: **no new P0/P1 found inside revision 3a itself**.
- PR #100 as currently composed: **P1 scope blocker remains**.
- Migration promotion: **not authorized**.
- Runtime apply/deploy: **not authorized**.
- Store/API implementation: remains behind the architecture gate and human authorization.

Once #100 is isolated back to the Grammar-only scope, re-review the exact new head. If no new P0/P1 appears, the architecture is positioned to receive `APPROVE` at that point.
