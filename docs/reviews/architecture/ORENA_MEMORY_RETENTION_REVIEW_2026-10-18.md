# Orena Memory: explicit-note retention, independent review (2026-10-18, PR #292)

- **Reviewer:** Claude (Opus 5.5), an independent and read-only subagent. It did not write this code.
- **Scope:** a learner-data lifecycle change. A kept note now expires 180 days after it was last asked for (owner, PRE-005: pilot data is kept up to 6 months). A daily sweep deletes expired rows.

## Round 1: reviewed commit `b23128ff`, outcome **CHANGES REQUIRED**

| ID | Finding | Disposition |
| --- | --- | --- |
| P1-1 | An expired row still held the unique indexes, so keeping the same words again, or a new value in a single-valued slot, failed on PostgreSQL. | **Fixed** in `de5797f0`. `add_explicit` first deletes the learner's own expired explicit notes in that language, in both stores. Tests: `test_after_expiry_the_same_words_and_a_new_slot_value_can_be_kept` and `test_expired_notes_do_not_count_against_the_limit`. Each failed first on PostgreSQL with `UniqueViolation`, then passed. Local PostgreSQL contract: 42 passed. |
| P1-2 | Nothing called `sweep_expired`, yet the doc said expired notes are deleted. | **Fixed** in `de5797f0`. `ExpiredMemorySweep` runs once a day per process, off the request thread, in bounded batches. It is off unless `AGENT_MEMORY_RETENTION_SWEEP` is on, because automatic deletion is the owner's switch. An unclear value, or the switch on with a store that cannot sweep, refuses to start. The doc and `.env.example` say what happens while the switch is off. |
| P2-1 | No backfill for rows written before the change. | **Accepted as is.** The :8021 listing is empty and :8000 has no memory. |
| P2-2 | The server upsert event said `expires_at: null`. | **Fixed.** It now carries the item's expiry. The `AGENT_CONTRACT.md` example belongs to the contract owner (D-086). |
| P2-3 | The renewal UPDATE could find its row swept in between. | **Fixed.** That case falls through to an insert. |
| P2-4 | A renewed note keeps `created_at`, so it can be the first one cut past 20 notes. | **Product question**, left as is. |

## Round 2: reviewed commit `de5797f0` (head `b05d784d`), outcome **APPROVE**

There is no P0 or P1. The two new P2s are fixed in the commit that adds this record:

- **P2-A:** after the fall-through, the swept row still counted against the limit. It is now dropped from the count.
- **P2-B:** the sweep reuses `agent/retention.py`'s `_in_background`, and the test-only `_removed` is now documented as such.

**Open for the owner:** switching on `AGENT_MEMORY_RETENTION_SWEEP` on :8000. The 6-month deletion holds in full only once that switch is on. Until then, expired notes are invisible at once and deleted the next time the learner keeps a note in that language.
