# Voice chat for Plus and Pro (D-236, PR #317): independent architecture review (2026-10-19)

- **Reviewer:** Claude (Opus 5.5), independent and read-only.
- **Reviewed commit:** `a16a1d95`.
- **Outcome:** **APPROVE**, with no P0 or P1.

What the reviewer confirmed:
- **No learner-visible defect.** The Plan and Pricing screens only draw the keys they list, and the UI lane's D-235 adds the copy.
- **Catalogue round-trip.** A stored catalogue keeps the code defaults.
- **Not funded, enforced or metered.** The entitlement is outside billing and quota.
- **Order.** 404, then plan, then spend, then window.
- **Manual grants count** (D-154), and the check fails closed.
- **The `plan_for is None` bypass cannot happen in the real app,** because app.py always passes `plan_for`.

Rollout note for the owner: with billing off, every :8000 learner without a manual grant loses voice on deploy. That is intended (D-236 point 5).

| ID | Finding | Disposition |
| --- | --- | --- |
| P2-1 | The Admin plan editor shows a placeholder name and a meaningless limit field for an on/off entitlement. | **UI lane.** D-235 adds the copy. A toggle-only editor is recorded as a gap. |
| P2-2 | `entitled: false` on a 503 would show a paying learner the upgrade sheet during an outage. | **Fixed.** `entitled` is `null` when the plan cannot be read. |
| P2-3 | A Free learner gets 403 before the voice-off 404. | **Accepted.** It is minor: the voice list already answers 404 in that state. |
| P2-4 | Ordering tests for Free at the spend cap, and for an extend after a downgrade. | **Deferred.** |
| P2-5 | D-236 had no Status line. | **Fixed.** |
