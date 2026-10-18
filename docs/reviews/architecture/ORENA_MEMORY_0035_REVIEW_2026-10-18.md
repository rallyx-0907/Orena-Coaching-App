# Orena Memory M2.1: migration 0035 promotion and PostgreSQL repository, independent architecture review (2026-10-18)

- **Reviewer:** Claude (Opus 5.5), acting as Delegated Architecture Reviewer (AGENTS.md "Architecture review authority"). The review was read-only and independent of the implementer's session context.
- **Reviewed commit:** `d985e9b6` on `claude/intelligence-m2-store` (range `origin/main...d985e9b6`, 3 commits).
- **Scope:**
  - promotion of `20261018_0035_orena_memory.py`;
  - `writing_coach/persistence/memory_repository.py`;
  - the port changes in `writing_coach/agent/memory_store.py`;
  - the deletion enumeration;
  - `tests/test_agent_memory_contract.py`.
- **Outcome:** **APPROVE WITH CONDITIONS**. No P0. One P1 (governance). The schema, the locking and the scoping were found sound.

## Findings and their disposition

| ID | Finding | Disposition |
| --- | --- | --- |
| P1-1 | The no-ORM departure from rev 4.1 §9 and the handoff was not recorded, and the migration docstring was stale. | **Condition, done.** Recorded in `ORENA_MEMORY.md` §9 ("As built at M2 promotion"), in handoff §5 Step 1, and in the migration docstring. |
| P2-1 | `tests/test_credit_topup_migration_postgres.py` pinned the head to 0033. | **Condition, done.** The Billing proof now upgrades to `20261015_0033` by name and asserts it is on the single-head chain. The assertion is not weakened. |
| P2-2 | Reads did not fail closed after an incarnation was deleted. | **Fixed.** Every read requires an active incarnation, and an inactive one reads OFF. Test: `test_reads_fail_closed_once_the_incarnation_is_deleted` (red, then green). |
| P2-3 | The sweep could deadlock with a learner's bulk delete. | **Fixed.** The sweep subqueries use `FOR UPDATE SKIP LOCKED`. |
| P2-4 | First-write serialisation relied on the engine's default isolation. | **Fixed.** Writes pin `READ COMMITTED`. The lock order (incarnation, then state, then items) is in the module docstring, including the rule for the future D-055 runtime. |
| P2-5 | `versions_in_use` scans both tables in full. | **Deferred to M2.2.** It is not called on any live path. When wired, it runs as an operator step before a rotation, never as unbounded startup work. |
| P2-6 | The unique indexes ignore expiry (an M3 risk). | **Deferred to M3.** M3's materialisation deletes expired holders in the transaction or upserts. It cannot occur in M2, where only explicit rows are written. |
| P2-7 | Operational order for applying 0035 | **Condition, met elsewhere**: `CURRENT_HANDOFF.md` is at its 8,000-byte validator cap (12 bytes free), so the operator step - :8021 first (UI lane, `bootstrap_runtime_schema.py --upgrade`), every other runtime after a backup and the owner's go, before its next start - is in `migrations/proposed/README.md`, the migration docstring and the PR; the owner is told directly |
| P2-8 | Small divergences between the fake and PostgreSQL. | **Documented** in the port docstring. Callers validate before writing. |

## Checked and found correct (summary)

- **Scope.** Every statement filters by both `incarnation_id` and `user_id`, and the composite owner FKs are correct.
- **Snapshot.** `REPEATABLE READ` is used correctly.
- **Key rotation.** Dedupe and suppression match each row under its own stored version.
- **Unique indexes.** No reachable unique violation from `add_explicit`.
- **Deletion enumeration.** Complete.
- **D2.** Summaries deferred to M3, loudly.
- **Product invariants.** No breach: PostgreSQL only, no startup work, no dual-write.

**Merge condition carried forward:** the pack is not wired to `PostgresMemoryRepository` for continuity or summaries before M3.
