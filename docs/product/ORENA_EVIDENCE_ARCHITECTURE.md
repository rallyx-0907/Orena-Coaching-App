# Orena evidence and learner projection architecture

Status: implementation specification. No new mastery model or recommendation
engine is claimed. Read with ORENA_BACKBONE_CONTRACTS and account/data architecture.

## 1. Evidence owners and meaning

| Producer | Evidence that may be retained | Claims excluded |
| --- | --- | --- |
| Listening reconstruction | actual answer, reveal/hint state, domain comparison and source segment | hearing/opening proves comprehension; revealed answer proves unaided recall |
| Reading | submitted answers, question/source revision, evaluator result | reading time alone proves understanding; missing questions are invented |
| Writing | immutable submitted draft, task, evaluator version, grounded dimensions | model rewrite is learner work; difference from expected wording is automatically wrong |
| Speaking/shadowing | own take/transcript, reference when applicable, dimension measurement status | typed coaching measured pronunciation; free expression has alignment to absent reference |
| Grammar | canonical Concept ID, actual response and existing domain judgment | authored explanation or concept visit equals mastery |
| My Language | acknowledged saved relationship with provenance when known | keeping a word establishes successful use or recall |
| Recall | explicit attempt/reveal/self-assessment with existing review scheduling owner | reveal or card visit automatically advances schedule |
| Understanding | source-bound explanation and optional learner question | receiving AI text is evaluated learner performance |
| Continue | work/source reference and actual lifecycle | unfinished thread is a recommendation backed by mastery |

Existing domain records remain canonical. A shared EvidenceRef/index locates
them; it must not flatten every score into a universal accuracy number or replace
the evaluator payload. `static/orena/product/evidence.js` is a client adapter,
not an authoritative multi-user event store.

## 2. Evidence ingestion contract

Normalized metadata, when an adapter needs it: scoped EvidenceRef, producer
contract/evaluator version, source/work snapshot reference, learning language,
server acknowledgment/sequence, measurement kind, assisted/revealed status,
observed time and invalidation status. Preserve all domain fields, including
unknown, not-measured and not-applicable distinctions. Unknown is not zero.
Client time is contextual metadata; server sequence orders accepted changes.

Only an acknowledged domain write may enter an account projection. A pending
local comparison may be shown as local feedback, labeled accordingly. An event
notification carries references/version, not all private text. The projection
loads through domain read contracts with account/language scope. A failed
projection does not retry the learner's already-committed domain write.

New ingestion uses stable operation identity and transaction semantics from the
account contract. Existing aggregates may seed a labeled legacy aggregate
baseline with known provenance; do not synthesize constituent events or missing
historical timestamps/evaluator versions. Compatibility views can continue to
read old records until the migration is explicitly activated.

## 3. Projection lifecycle and consistency

Projection identity is account incarnation + learning language + projection-policy version.
Dependencies include source EvidenceRefs and domain versions, not only a last
modified timestamp. Start with direct bounded queries when sufficient. If a
materialized projection is needed, use a transactionally recorded change feed
and idempotent consumer; no speculative event infrastructure is required.

Apply an evidence version once; re-delivery is a no-op. Out-of-order older
versions cannot restore invalidated evidence. Domain correction records supersede
earlier interpretation without silently rewriting history. Deletion/revocation
invalidates dependent rows and private caches. Rebuild from authorized domain
records under a pinned policy version; do not replay usage telemetry as evidence.

Read outcomes: current with provenance, stale with known checkpoint, unavailable,
or empty with no evidence. A partial rebuild may not claim current completeness.
If a dependency is no longer authorized, omit private details and mark the view
unavailable/stale as appropriate; cache presence does not confer authorization.
Projection failure preserves source evidence and ordinary practice access.

## 4. Consumers without fabricated intelligence

Continue resolves actual work independently of recommendation. My Language reads
saved relationships plus available origin; missing origin never becomes a made-up
encounter. Recall preserves the existing scheduler and explicit self-assessment
contract. A future evidence-driven candidate selector may supply candidate refs
to that owner, but cannot independently advance due dates or grade an attempt.

Discover can show editorial choices without claiming personalization. A future
personalized suggestion includes reason kind, supporting EvidenceRefs, policy
version and eligibility constraints. Filter account access, language, rights,
content readiness and suitable actions before ranking. If evidence is insufficient,
return an editorial/general choice with truthful labeling or no suggestion.
Generated explanations of a recommendation cannot invent the supporting facts.

Journey may show bounded statements such as an actual successful retrieval in a
specific context. Mastery thresholds, adaptive policy and claims of transferable
ability need a separately evaluated pedagogical policy; infrastructure does not
invent them. Existing closed Grammar curriculum/Concept IDs and progress owners
remain authoritative. Extension plug-in point is a versioned policy consuming
authorized domain evidence and returning justified candidates, not a new global
learner score. This establishes the seam while leaving product/pedagogical
choices explicit, rather than blocking ordinary feature implementation.

## 5. Architecture-level acceptance

### Profile, Growth and achievement read models

`LearnerSummary(scope, window, policyVersion)` returns domain-separated measures,
supporting EvidenceRefs, coverage, freshness and explicit unknowns. Profile
composes it with declared goals/preferences and commerce facts through read APIs;
none of those panels writes another domain's state. Growth compares compatible
measurements over explicit periods: evaluator/metric version, assistance mode,
language and task comparability must match, or report comparison unavailable.
An activity count is allowed as labeled activity, never renamed proficiency.
Do not average CEFR, Chinese levels, dictation accuracy and pronunciation into
one invented score. Cross-language views preserve separate measures and coverage.

`AchievementPolicy = {id, version, eligibilityPredicate, requiredEvidenceKinds,
assistanceRules, evaluationWindow, displayClaim, correctionRule}` is versioned
and product-approved before it issues a real achievement. No approved policy
means an empty/unavailable achievement catalog, not seeded awards. Policies use
deterministic domain evidence predicates; a provider cannot award arbitrary badges.
The policy structure is architecture; thresholds and motivational claims are
product/pedagogical inputs, not a frontend author's choice.

`AchievementRecord = {accountIncarnation, learningLanguage, policyId, policyVersion,
eligibilityKey, evidenceRefs, earnedAt, status, evaluatedCheckpoint}` is a derived
record. Unique eligibilityKey prevents duplicate awards during replay; key is
account incarnation + language + policy + occurrence/window (single lifetime policies have
one occurrence). Evaluation time and evidence time remain distinct. States are
eligible, earned, invalidated, unavailable; presentation cannot promote eligible
to earned without acknowledged evaluation. No separate points balance is implied.

Evidence correction/deletion triggers reevaluation. Invalidated records cannot
continue making an unsupported claim; retain only allowed minimal audit metadata
under retention policy. A policy revision does not silently change earlier awards:
new policy specifies retain-if-still-supported, reevaluate, or retire display.
Rebuild uses the recorded policy version and unique eligibility key. Replayed
awards must not repeat celebration/notification side effects; a future delivery
owner consumes acknowledged state changes with its own idempotency receipt.

Growth query returns current/stale/partial/unavailable and a stable checkpoint.
If insufficient comparable evidence exists, show real observations and no trend.
Achievements do not unlock paid entitlements; subscription events do not award
learning achievements. Advanced-view entitlement denial may restrict an operation
under approved commerce policy, but cannot erase underlying learner evidence.

### Gates

Test pending versus acknowledged results; assisted versus unaided claims;
duplicate/out-of-order events; revised evaluator result; deleted evidence;
revoked private source; cross-account and cross-language reads; projection
rebuild interruption; insufficient evidence; recommendation using an unavailable
source; Recall reveal without review write; provider coaching without measured
audio. Domain-specific feature and browser tests remain Opus's responsibility.

No change to the approved rich visual compositions follows from these contracts.
The same evidence can support different meaningful experiences without imposing
one global dashboard, navigation map or repeated card layout.
