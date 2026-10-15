# PR-MON-7B1: semantic AI meters in the plan catalogue (review request)

**Status: IMPLEMENTING, draft PR for CI and independent review.** Branched from `main` `4327250d`. The owner decision
is H7-3 (D-MON-025, recorded in the Billing decision log on PR #231/#233).

## What it adds

`word.assist`, `reading.assist` and `writing.task` are added to `writing_coach/product/catalog.py` `METERS`. Each is a
**day** window and a **request** unit, the unit frozen by D-MON-023 H-2 (`funding.NEW_METER_UNITS`). They carry these
bootstrap entitlements:

| Meter | Free | Plus | Pro |
| --- | ---: | ---: | ---: |
| `word.assist` | 30/day | 300/day | 1500/day |
| `reading.assist` | 10/day | 100/day | 500/day |
| `writing.task` | 5/day | 30/day | 100/day |

- **Admin-editable** through the existing catalogue (`PUT /api/product/admin/plans`, Plans & pricing). The editor
  already lists every catalogue meter. This PR adds names and the `request` unit in EN/VI/ZH.
- **No version bump, no migration.** Catalogue v2 accepts partial entitlements: a catalogue stored before this PR
  reads the new meters at their code defaults and keeps every stored limit. Quota buckets store the meter as a
  free-form string.
- **Nothing activated:**
  - none of the three is in `quota.WIRED_METERS`, so none is enforceable and nothing admits them;
  - they are not credit-eligible;
  - no route, router or learner capability changes;
  - quota and funding enforcement stay off.

## Learner Plan & usage

The pinned design's Pricing (`BILL_PLANS.lim`) and Plan & usage frames do not draw these meters. The learner screens
are unchanged: `FEATURE_ORDER` / `USAGE_ORDER` keep the design's five and four. The gap is recorded in
`docs/project/UI_BACKEND_GAPS.md` ("Plan & usage has no rows for the semantic AI meters") for a separate fast UI slice
before any of them is enforced. The names added to `screens/plan/copy.js` are read by Admin only.

## Tests

`tests/test_product_foundation.py`:
- the meter list now includes the three;
- their limits, window and unit match the frozen H-2 unit;
- they activate nothing (not wired, not enforceable, not credit-eligible);
- a pre-7B1 stored catalogue reads their defaults and keeps its own limits;
- an admin edits one like any other limit.
