# Billing / Monetization lane — risk register

This register lists meaningful residual risks only. The leader owns it, and changes it only when a risk opens,
changes or closes.

| ID | Severity | Risk | Owner | Status | Mitigation |
| --- | --- | --- | --- | --- | --- |
| R-MON-001 | P0 | A verified payment changes no plan. Billing writes `commerce_subscriptions`, but the plan and quota read the legacy `subscriptions` table. | lane | unresolved, PR-MON-1 active | One effective-entitlement resolver (D-MON-006), with precedence tests and a PostgreSQL proof. Billing stays off until it is reviewed. |
| R-MON-002 | P1 | Money is taken and nothing is granted, with no durable trace. A verified payOS mismatch, unknown order or deleted account answers 200 and leaves only a log line. | lane | unresolved, PR-MON-3 | D-MON-004: durable anomaly/reconciliation state and operator visibility. Billing stays off until then. |
| R-MON-003 | P1 | A trial or Free allowance is reset by deleting and re-registering. A new account incarnation would start with empty buckets. | lane | unresolved, PR-MON-6 | Bind promotional allowances to an identity that survives re-registration (the `users` row / sign-in subject). The design is reviewed with PR-MON-6. |
| R-MON-004 | P1 | The price shown and the price charged drift. The catalogue and `BILLING_PRICES_FILE` are independent. | lane | unresolved, PR-MON-2 | D-MON-005 consistency gate: checkout is blocked on a mismatch. |
| R-MON-005 | P2 | An expensive AI path bypasses admission. Only the four bucket meters are wired; other AI paths are bound by spend caps, not plan quota. | lane | unresolved, PR-MON-6/7 | Inventory every provider call site. Prove that no paid dispatch can happen without admission (brief §19, cost protection). |
| R-MON-006 | P2 | A Polar renewal webhook arrives late and access lapses at `paid_through` before the renewal event lands. | human (grace policy) | accepted until a grace policy exists | Commerce architecture §3: outages do not extend a grant. The grace window is a human policy input. |
| R-MON-007 | P2 | Cross-lane merge conflicts in `product/service.py`, `membership.py` and `app.py`, which the UI and other lanes also touch. | lane | unresolved | Keep changes minimal and response shapes unchanged. Rebase on `main` before review and note overlaps in `BILLING_STATUS.md`. |
