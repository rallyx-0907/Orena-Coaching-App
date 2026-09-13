# Orena backbone integration and implementation gates

Status: architectural handoff specification. Runtime integrations below are
not claimed implemented. Parent: ORENA_BACKBONE_EXECUTION.md.

## Contract inventory and safe implementation packages

| Package / Opus ownership | Specification | Existing anchors / first implementation seam | Dependency and exit gate |
| --- | --- | --- | --- |
| I1. Profile and account lifecycle adapters | ORENA_ACCOUNT_DATA_ARCHITECTURE §§1-3 | auth_support.py; User/UserLanguageProfile; account/profile read adapters | scoped read/patch and logout/incarnation scenarios; no theme WIP edits |
| I2. Transactional work/evidence persistence | account architecture §§3-7 | persistence repositories, existing essay/attempt/library IDs | I1; reviewed additive schema, receipts, cursor/snapshot and PostgreSQL concurrency proof |
| I3. Plans, subscription and quota | ORENA_COMMERCE_ARCHITECTURE | product/catalog.py, service.py, api.py; PostgreSQL product repository | I1-I2 transaction foundation; read UI first; enforcement/provider activation separately gated |
| I4. My Content/My Language retrieval | ORENA_COLLECTION_ARCHITECTURE | memory.js, collection-search.js, existing saved-word repository | I1-I2; private membership/provenance, query pagination; no implicit navigation promotion |
| I5. Provider/content job adapters | ORENA_CONTENT_EXECUTION_ARCHITECTURE | media_ingestion.py; media_providers/supadata.py; canonical media model | I2-I3; atomic admission, fenced workers, unknown-outcome reconciliation |
| I6. Profile/Growth/achievement views | ORENA_EVIDENCE_ARCHITECTURE | domain evidence read APIs; versioned projection/policy adapters | I2/I4; justified domain claims; commerce read decisions for any gated operation |
| I7. Cross-domain release integration | this document | existing CI plus new scenario gate; Opus functional/browser evidence | I1-I6 relevant gates; no product approval inferred |

Document names in the specification column live in `docs/product/`. Each package
is safe for implementation planning and ungated adapters under its contract.
Schema, destructive lifecycle, paid enforcement and live providers are not
authorized merely by inclusion. Codex reviews architecture deviations, not every
interaction detail. Opus owns implementation tests, UI and browser verification.

## Architectural executable contract

`writing_coach/reference_backbone.py` supplies pure decisions for scope,
mutation replay/conflict, quota admission, stale response, worker fencing,
evidence version selection, metric comparability and cursor binding.
`scripts/test_orena_backbone.py` runs its counterexamples with stdlib unittest.
These are reusable reference policies, not authenticated service endpoints,
transaction implementations, durable receipts or runtime security proof.
Adapters may reuse them directly where compatible or prove equivalent behavior
with the same scenarios. Existing envelopes remain adapted, not renamed.

The CI gate executes these alongside existing architecture/memory validators.
Existing A-D gates remain unchanged. No claim that pure tests verify PostgreSQL
locking, provider semantics, billing integration, or browser rendering.

## Mandatory cross-domain acceptance matrix

Run each applicable case with two accounts and EN/ZH before activating its package.
These are adapter-level requirements, pending until real implementations exist.

| Scenario | Required result | Implementation evidence owner |
| --- | --- | --- |
| Sign out/switch account during evaluation | old result cannot enter new UI/work/cache | I1/I2, Opus browser + service |
| Delete and re-register same external identity | new incarnation rejects old command/cursor/job/callback | I1-I3, identity integration |
| Two edits from same work version | one accepted, other explicit conflict; both texts retained | I2, PostgreSQL concurrent sessions |
| Lost acknowledgment after successful write | same operation replays same result; no second evidence/quota charge | I2/I3, transaction fault injection |
| Account stream transaction 10 stalls while 11 attempts commit | serialized stream prevents skipped late commit | I2, PostgreSQL concurrent sessions |
| Snapshot page and concurrent mutation/deletion | stable snapshot watermark + changes covers exactly once | I2/I4, snapshot expiry/restart test |
| Quota has one unit, EN and ZH submit concurrently | one reservation, one exhausted; same shared bucket | I3, PostgreSQL concurrent sessions |
| Duplicate/reversed provider subscription events | canonical current state, no duplicate grant or usage reset | I3, provider adapter fixtures |
| Period boundary while provider job runs | original reservation/window settled once | I3/I5, controlled clock |
| Downgrade while work exists | retained work/evidence; new admission uses effective policy | I2-I4, service and UI |
| Checkout/callback for deleted incarnation | no new-account grant; historical reconciliation isolated | I1/I3, fixture |
| Private source appears in shared dedup cache | another account gets no body/title/snippet/access grant | I4/I5, access tests |
| Remove content membership versus delete source | only intended relationship removed; other owners untouched | I4, repository/service |
| Search across work/source/phrase with colliding IDs | domain-qualified refs preserve all destinations | I4, query and route tests |
| Content owner temporarily unavailable | partial collection, not false empty; exact/unknown counts explicit | I4, outage fixture |
| Worker lease expires/cancel races completion | old lease cannot publish; unknown cost remains reconcilable | I3/I5, worker fault injection |
| Source revision/access changes mid-job | result cannot attach to current source or expose revoked excerpt | I2/I4/I5, integration fixture |
| Correct/delete evidence after achievement | projection reevaluated; unsupported claim withdrawn | I6, replay/rebuild tests |
| No approved achievement policy or comparable evidence | truthful empty/unknown, no invented award or growth | I6, policy fixtures |
| Restore after deletion/receipt compaction | deletion barrier and replay safety applied before serving | I1-I7, authorized restore rehearsal |

## Migration and activation order

1. Correct the known startup auto-Alembic path in a deliberate persistence slice,
   preserving operator bootstrap as an explicit command; validate empty/existing/
   mismatch/unavailable database behavior. This is a tracked P1, not a foundation
   re-audit and not something this architecture checkpoint silently fixes.
2. Establish account incarnation, transactional receipt and stream primitives in
   reviewed additive migrations. Validate old readers and constraints before writes.
3. Add work/membership/provenance adapters without moving existing evidence owners.
4. Introduce commerce event/entitlement/quota adapters with enforcement disabled
   until policy and provider gates. No account mutation grants paid access.
5. Introduce durable jobs after quota/admission and retention contracts exist.
6. Build projections from acknowledged domain records; read through authorized
   contracts. Do not backfill fictional evidence or historical achievements.
7. Exercise the matrix, load profile, migration and restore gates. Activate a
   coherent domain with all its direct/contextual paths, not a partial bypass.

**Hard gate - deletion and re-registration (D-054, D-055).** No runtime path
may call `mark_deleted` or `register_new` (enforced by
`tests/test_deletion_journal.py::test_no_runtime_code_deletes_or_re_registers_an_account_yet`)
until both exist and have passed independent review: (a) each deletion is
appended, as it happens, to a journal outside the database, so a restore after
losing the database still knows it; (b) the account-deletion workflow removes
the account's rows from owner tables keyed by account rather than incarnation,
and is replayed after a restore. Restore suppression (`runtime_backup.py
suppress`) covers incarnation barriers only. Lifting the gate is a reviewed
change to this paragraph and that test together.

Deployment gate inputs: approved schema, retention/deletion policy values,
commercial plan/price/grace/meter policies, any achievement/pedagogical policies,
provider credentials, measured workload/SLO and recovery objectives, backup/restore
evidence, and explicit activation authorization. Absent policies have defined
unknown/disabled behavior; ordinary UI can implement those states now.
No speculative legal retention duration or commercial price is chosen here.

## Whole-product acceptance remains separate

Golden Star ledger retains the closed Recall/Writing/context findings and pending
language-sweep investigation, live-provider/microphone and human visual gates.
Opus preserves rich compositions, approved theme/brand, eleven destinations,
EN/ZH, narrow/desktop/wide, accessibility and source return. Architecture tests
do not substitute for those journeys. This architecture cannot declare product
APPROVED, public release, or 100,000-user capacity.
