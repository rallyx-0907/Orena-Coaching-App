# Account deletion tool (PR #380, PRE-502 R4): independent architecture review (2026-10-19)

- **Role:** Delegated Architecture Reviewer (AGENTS.md "Architecture review authority"): Claude (Opus 5.5), independent of the implementer, read-only.
- **Reviewed:** `54ad1051` against `b978bac2`, after a first round on `b978bac2` that returned CHANGES REQUIRED.
- **Outcome: APPROVE of the tool's code, leaving out D-054's gate.** This is not an approval to lift the gate, and not an authorisation to run the tool on any runtime. Running it on :8000 is a human gate.

## Round 1 (`b978bac2`): CHANGES REQUIRED

Fixed in `54ad1051`:
- An account with no incarnation got no barrier. It now gets a deleted epoch-1 row, and the incarnations are read under the lock.
- An email shared by more than one account could pick the wrong one. It is now refused, and the candidates are named.
- Sessions were not ended. They are now revoked in the same transaction (#377).
- Actor audit rows of an administrator's own account were deleted. Now only `learner.*` and `agent.*` rows go.
- `--commerce delete` could never run. `keep` is now the only choice, and the public page is flagged to the owner.

P2s fixed: uuid comparisons, identifier quoting, the role reset, and the runbook order and verify steps.

## Round 2 (`54ad1051`): APPROVE (code)

Remaining P2s were fixed after the round in a follow-up commit: stale runbook rows, a test assertion that could no longer fail, and a note on handling the tool's output.

**Verified in the review:**
- the schema scan is complete for learner data;
- child tables cascade;
- the editorial actor columns are not scanned;
- the barrier matches `mark_deleted` and `DeletionBarrier`;
- the dry run is READ ONLY;
- every refusal happens before any write.

## Open, not code (the owner decides)

1. **D-054's gate.** `tests/test_deletion_journal.py::test_no_runtime_code_deletes_or_re_registers_an_account_yet` stays red while the gate stands. The tool marks incarnations deleted. Lifting the gate needs its own reviewed change:
   - a continuous out-of-database journal append, in a defined order;
   - an owner-table replay after a restore;
   - a DECISION_LOG entry;
   - the test edited to allow exactly `persistence/account_deletion.py`.

   AGENTS.md section 7 reserves the account-deletion runtime for the human.
2. **The public deletion page and kept payment records.** Disclose that they are kept, or design a deletable path.
3. **Before the first use:** the review recorded here, backup rotation applied on the host, and the :8000 run itself (a human gate).
4. **Returning learners.** What a returning learner gets on the legacy owner routes is still a product question (D-055).
