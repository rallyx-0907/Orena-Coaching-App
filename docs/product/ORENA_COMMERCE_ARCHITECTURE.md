# Orena commerce, entitlement and quota architecture

Status: implementation specification, no billing activation. Commerce is a
separate product domain, not an incidental account field or learning capability.
Dependencies: ORENA_ACCOUNT_DATA_ARCHITECTURE and ORENA_BACKBONE_CONTRACTS.

## 1. Existing foundation and ownership

Reuse `writing_coach/product/catalog.py`, `service.py`, `repository.py`, `api.py`
and `writing_coach/persistence/product_repository.py`. `PlanRecord`,
`PlanEntitlement`, `Subscription`, `UsageEvent` already exist in persistence models.
Current `account_state()` reports Free/Premium facts with `billing_ready=False`;
the repository exposes subscription reads and monthly usage, not a complete
transactional billing/entitlement enforcement contract. Preserve these read APIs
through adapters. Existing catalog numbers are current configuration, not a new
pricing decision or proof they are suitable for activated commerce.

Commerce owns plan versions, price references, subscription lifecycle, resolved
entitlements, quota accounting and billing-event reconciliation. Identity owns
the principal; capability domains own which operation is performed; AI platform
owns provider cost telemetry; none may directly promote a subscription.
Commercial quota and provider token usage are separate ledgers with explicit unit
mapping. A provider call costs money but does not imply learner evidence.

## 2. Canonical logical records and read contract

- PlanVersion: stable plan ID, immutable policy version, effective interval,
  feature grants and metering policies. Feature keys remain shared across EN/ZH.
- PriceReference: plan version, external price ID, currency/interval and approved
  display metadata. No floating-point money or inferred price from a label.
- Subscription: account incarnation, provider/customer/subscription mapping,
  normalized state, observed provider revision, effective plan version,
  paid-through interval, scheduled change and reconciliation state.
- EntitlementDecision: feature, allowed/denied/unknown, reason, policy version,
  effective interval, quota unit/window and authoritative snapshot version.
- QuotaBucket: account incarnation + meter + window ID, limit policy version,
  consumed and reserved units. Language is diagnostic, not a second allowance.
- Reservation: operation ID, bucket, upper-bound units, state, admitted policy
  version and dispatch/result reference. Unique operation prevents double charge.
- BillingEventReceipt: verified provider event ID, external object reference,
  processing state, revision/digest and sanitized failure. Private raw payload
  retention is separately governed; never expose it in learner APIs.

`accountCommerce(scope)` returns known plan/subscription/entitlement/quota facts
and readiness flags; unknown data stays unknown. `resolveEntitlement(scope,
feature, at)` is the one server resolver used by all entry paths. Read-only UI
badges are not access enforcement. Feature code consumes the decision, never
checks `plan == premium`. Public UI gets no provider/customer identifiers.

## 3. Subscription lifecycle and provider reconciliation

Internal states: none, pending, trialing, active, past_due, paused, ended, unknown.
Provider adapters map explicitly and retain the original state internally.
Cancellation scheduled at period end is an effective-date intent on the current
subscription, not immediate loss of already-valid access. Activation/renewal needs
verified authoritative provider state; checkout return URLs cannot grant access.

Checkout initiation binds authenticated account incarnation, intended approved
price and one operation ID. Provider callbacks validate signature, replay rules
and account mapping server-side. Persist inbox receipt before acknowledging the
event; duplicate event IDs do not repeat grants. Events may arrive out of order:
use provider object version when authoritative, otherwise fetch current object
state and serialize reconciliation per subscription. Arrival timestamps alone
cannot decide which subscription state is newer. A pending/unverifiable fetch
leaves reconciliation unknown; do not promote access or erase known valid state.

Trial/past-due grace, proration, refunds, trials per account, upgrade timing and
downgrade timing are versioned commercial policy inputs requiring human decisions
before activation. The architecture has deterministic evaluation: verified facts
+ effective-date policy -> entitlement snapshot. Missing policy for a state
returns unknown and blocks new paid admissions for that state. A pinned verified
grant remains usable only until its explicit validity boundary; outages do not
extend it indefinitely. Free features follow their independently approved policy.

An upgrade cannot reset the existing usage window. A downgrade never deletes
learner work/evidence or silently charges for a new operation. Previously admitted
jobs retain their bounded reservation/policy until completion unless account/access
revocation requires cancellation. Refunds/chargebacks update commerce and audit;
they do not rewrite learning history. Account deletion stops new checkout/jobs
and enters a resumable billing-cancellation/reconciliation step; retained financial
records remain isolated under the approved retention policy, not active learner
accounts. Old callbacks cannot reactivate a deleted incarnation.

## 4. Atomic admission, settlement and time windows

`reserve(scope, feature, operationId, maxUnits, policyVersion)` reauthorizes and
locks the scoped bucket. In one transaction check duplicate operation, effective
entitlement and `consumed + reserved + requested <= limit`, then write reservation.
Return admitted reservation, quota_exhausted, denied, or unknown. Unlimited is
explicit and does not bypass provider capacity/safety limits. Unknown usage cannot
be interpreted as zero. Reject negative units, changed payload on duplicate ID,
and an expired/foreign window token. Server time determines windows.

Windows use immutable half-open UTC intervals `[start, end)` with a stable ID and
versioned policy (calendar month or verified billing period, never guessed).
Reserve and settle against the original window even if completion crosses its
end; a renewal creates a new bucket and does not move in-flight reservations.
Existing monthly_usage is a reporting read; it does not make parallel admission
atomic. Do not reset quota when UI/learning language changes.

`settle(operationId, actualUnits, outcomeRef)` is idempotent and atomically moves
reserved to consumed, releasing unused allowance. Actual units must not exceed
the admitted bound: request an atomic supplemental reservation before extending
work, or stop at the admitted boundary. Policy states which successful/failed
outcomes consume learner quota; actual provider spend is still tracked separately.
Cancellation before dispatch releases reservation. Dispatched/unknown-outcome work
retains its reservation until reconciliation; TTL alone cannot release allowance
while an expensive request may still finish. Lease expiry starts reconciliation.
Provider settlement late after learner cancellation cannot create a second charge.

Enforcement activates atomically across direct and contextual entry paths for one
feature; no paid operation bypass via a second route. Existing non-enforced behavior
remains until the explicit activation gate. Do not quietly enable billing during
account or UI implementation.

## 5. Implementation order and acceptance

First implement versioned read adapters preserving current truthful states. Then
prepare subscription inbox/reconciliation and quota transaction repositories;
then provider integration in isolated fixtures; then one capability admission
adapter covering all its entries. Prices, policy values, provider credentials,
schema, live billing tests and activation require their explicit gates.

Require duplicate/reversed events, checkout redirect forgery, deleted-account
callback, unknown provider state, renewal boundary, scheduled cancellation,
upgrade/downgrade without usage reset, two simultaneous final-unit reservations,
retry after settlement, crash between admission/dispatch, unknown outcome, and
EN/ZH sharing one account quota. Profile and plans UI consume the same read
contract; Growth/Collection never infer entitlement from displayed plan text.
