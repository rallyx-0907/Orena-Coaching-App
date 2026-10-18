# System-wide daily AI spend ceiling: independent review (2026-10-18, PR #298)

- **Reviewer:** Claude (Opus 5.5), independent and read-only. It did not write this code.
- **Reviewed commit:** `9fb93b84`.
- **Outcome:** **CHANGES REQUIRED** (one P1).

| ID | Finding | Disposition |
| --- | --- | --- |
| P1 | `.env.example` and the `paid_refused` docstring promised that every paid model entry is refused. In fact only Orena chat and voice and the paid standby/backup entries of capped capabilities pass the gate. | **Fixed.** Both now state exactly what stops and what does not: a routed paid primary, an uncapped paid entry, media/ASR and speech. The PR says the same, and the gap is in the owner's batch. |
| P2-1 | `LiveSpendGuard.status()` could show a stale cap after the cap was cleared, and "no cap" while turns were refused. | **Fixed.** The cap is read once, an unreadable cap or a missing ledger is shown as refused, and only the guard for the current cap is read. Test: `test_the_admin_status_never_shows_a_stale_or_missing_cap`. |
| P2-2 | With an unreadable ledger, the status showed the last spend that was read. | **Fixed.** `_last` is cleared and `readable: false` is reported. |
| P2-3 | The system's 80% warning could stay silent when traffic is mostly agent turns. | **Fixed.** The agent guard checks the system ceiling first (`ceiling=spend_gate.ceiling_wait`), so agent traffic also raises the system warning and stops at the ceiling whatever the agent cap. `effective_cap` is removed. Test: `test_the_agent_stops_at_the_system_ceiling_even_below_its_own_cap`. No Admin notice is drawn yet, as the env doc says. |
| P2-4 | `control_plane.py` still says the capability's cap is reached when the system ceiling is the cause, and telemetry records `budget` for both. | **Deferred.** `control_plane.py` and `platform.py` are outside the granted scope (spend_gate only). This goes to the owner's batch. |
| P2-5 | The ledger prices free-plan calls at their list price, so the ceiling measures value, not money billed. | **Owner question.** It is documented in spend_gate and `.env.example`. |
| P2-6 | "Cap reached" was logged at every 5-second refresh. | **Fixed.** It is logged once per UTC day. |
| P2-7 | Missing tests: the UTC rollover, the cached verdict, `LiveSpendGuard.status()`, and the agent capped by the ceiling. | **Fixed.** `test_the_lock_lifts_at_utc_midnight_and_the_warning_comes_again_the_next_day`, together with the tests above. |
| CI | `/api/admin/ai-spend` was not in the admin authorization matrix. | **Fixed.** It is now classified, the matrix checks that a learner is refused and an admin gets 200, and the route count is 113. |
