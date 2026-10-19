# Admin: delete one learner's Orena Memory on request (PR #344): independent review (2026-10-19)

- **Reviewer:** Claude (Opus 5.5), independent and read-only.
- **Rounds:** `cc61d49f` was **CHANGES REQUIRED** (one P1). `aa327ee0` (fix `4ad54c73`) was **APPROVE**.
- **Confirmed:** the guard is `require_admin`; the account id is the memory and incarnation key; the required pre-audit aborts on failure; the store's lock order is safe against a learner writing at the same moment; the matrix entry is correct.

| ID | Finding | Disposition |
| --- | --- | --- |
| P1-1 | A store failure read as "no memory here" (404), so an operator could say the notes were gone while they remained. | **Fixed.** It is a 503 `memory_unavailable`, with nothing erased. |
| P2-1 | The admin console's stricter same-origin check was not applied. | **Fixed.** |
| P2-2 | The audit had no outcome, and the id was stored exactly as typed. | **Fixed.** A UUID is required before any audit, and `admin.memory_erase_failed` carries a reason. After round 2, an unexpected store error is also a 503, with `store_error`. |
| P2-3/4 | Scope: the current incarnation only; suppression keys, the switch row and device notes remain. | **Documented.** It means "delete my notes", not account erasure (D-055). |
| P2-5 | Test gaps. | **Fixed.** |

**Merge:** held until Hermes confirms, because it is an admin route that deletes learner data (Hermes, 2026-10-19).
