# Orena content and execution architecture

Status: architecture specification, not deployed worker infrastructure.
Read with ORENA_BACKBONE_CONTRACTS and ORENA_ACCOUNT_DATA_ARCHITECTURE.

## 1. Content identity, access and admission

Retain `MediaLearningAsset`, `MediaTranscript`, `TranscriptSegment`,
`SegmentTranslation` and `MediaLearningObject` in `writing_coach/media_learning.py`.
All supported media imports end at that model through `media_ingestion.py`.
All text adapters end at `static/orena/content/reading.js:readable()`; library
admission stays in `reading-library.js`. Do not introduce another media catalog
for Speaking or an imported-only learning engine.

Separate three axes: origin (curated/generated/imported), access (shared/private),
and readiness (pending/usable/unavailable/failed). A save creates a relationship,
never changes origin, rights or visibility. Shared media stays learner-neutral;
an account content-access relationship carries private ownership and admission
outside that canonical payload. Deduplication of an asset never grants a second
account access to a private import or exposes the first account's metadata.

Admission checks source type, language support, truthful provenance and rights,
size/duration policy, safe acquisition and allowed storage before processing.
For URL adapters allow supported schemes/providers, reject credentials and local,
private, loopback/link-local destinations, and revalidate redirects/resolution at
the server fetch boundary. Private inputs do not become public cache entries.
These are implementation acceptance requirements, not claims that every adapter
already enforces them. Unsupported import is a truthful outcome, not generation
of a replacement pretending to be the requested source.

Generated content records generation provenance separately from external source
attribution. Authored grammar continues to reference stable canonical Concept IDs;
no generated syllabus or provider-routed deterministic grammar engine. Published
reading requires per-text rights approval; this architecture admits no new text.

## 2. Revision and dependency contract

The owning content adapter supplies a revision when supported; missing revision
means unknown, never a fabricated constant. Store exact snapshot/hash with work
when the domain needs reproducible evaluation. A local hash is a snapshot check,
not an assertion of publisher identity or permission to retain copyrighted body.
Source edit invalidates offsets and timing-dependent derived outputs. Translation
is keyed by source revision, segment and support language; changing interface
language alone does not retarget the original or invalidate a learner attempt.

Revocation/deletion immediately prevents new body reads and processing. Existing
private learner work remains governed by its own deletion policy; a source return
can be unavailable while the learner's own response remains accessible. Evidence
records its original source relationship without asserting current access.
If exact source cannot lawfully be retained, preserve allowed identifiers and
truthfully report that recomputation/return is unavailable.

Deleting one account's imported/saved relationship never deletes a shared canonical
asset. Canonical removal belongs to the content owner. Copied source excerpts in
work/evaluation snapshots retain their source access/retention classification;
they cannot bypass revocation by being read through the work API. Separate the
learner's own response from restricted source excerpts so access can be removed
without misattributing or unnecessarily erasing that response.

## 3. Expensive operation contract

The AI platform retains provider selection/configuration, domain services retain
input validation and output interpretation. Deterministic workloads stay local.
No silent paid fallback, provider substitution or runtime activation.

An execution request carries server scope, operation ID, capability/contract
version, source/work revision, validated input digest and explicit execution
policy reference. It returns ready result, rejected/unavailable reason, or an
opaque operation reference. Existing synchronous APIs remain valid; durable jobs
are added only for workloads whose latency/retry behavior needs them. Existing
Supadata job IDs are provider handles, not a cross-account application job API.

Logical job record: account/access scope, capability, operation ID, validated
input reference/digest, pinned provider/config version, state, attempt count,
lease generation/expiry, result reference, policy version, cancellation state,
sanitized failure code and timestamps. Secrets never enter the record. Durable
private input references obey the retention/access contract, not generic logs.

States and transitions:

| State | Allowed next | Required condition |
| --- | --- | --- |
| queued | running, cancelled, rejected | access/budget check before lease |
| running | succeeded, failed, waiting_retry, outcome_unknown, cancelled | current lease; recheck deletion/version before publish |
| waiting_retry | running, cancelled, rejected | explicit retryable error, budget and deadline remain |
| outcome_unknown | succeeded, failed, cancelled | reconcile provider handle/status; never blind resubmit |
| succeeded / failed / cancelled / rejected | none | terminal; a new learner action has a new operation ID |

A lease generation fences writes from an expired worker. Lease expiry permits
reconciliation; it does not prove the provider stopped or that resubmission is
safe. If provider acceptance may have happened without an acknowledgment, mark
outcome_unknown. Query the same provider handle/idempotency token when supported;
otherwise require explicit resolution, not automatic repeat billing. Do not
claim exactly-once external execution from an internal database transaction.

Before an external call commit the admitted job/usage reservation; workers claim
it atomically. Never hold a database transaction open for the provider latency.
Record result and its domain acknowledgment atomically where one database permits;
otherwise durable result reference plus idempotent domain ingestion ensures retry
does not create duplicate evidence. A job result is not automatically evidence.

Cancellation before dispatch prevents execution. During execution cancellation is
best-effort at the provider; mark the application job terminal and suppress result
publication with the lease/cancel fence. Late provider completion still settles
actual usage; never claim cancelled means unbilled. A disconnect only ends the
subscription/poll, not the job. Account deletion invalidates authorization even
if a worker still holds a lease. Polling rechecks scope and never reveals foreign
job existence or payload.

## 4. Resource and scale boundary

One PostgreSQL authority and modular application remain the starting topology.
Separate web request capacity from bounded workers only when job implementation
requires it. No speculative microservices, sharding, Redis or vector database.

Execution policy must explicitly configure maximum input size/duration, per-user
and global concurrency, queue capacity, provider deadline, maximum attempts,
retry backoff, retention class and usage reservation limits. Missing configuration
fails admission for a newly activated expensive path; feature code must not
invent billing limits. Reuse current entitlement/usage owners; admission checks
are atomic so parallel jobs cannot each spend the same remaining allowance.
Settle actual usage once by operation identity, releasing unused reservations.

100,000 registered users is a planning population, not measured capacity. Before
rollout measure active fraction, arrival rate by workload, p95/p99 provider latency,
payload distribution, queue wait, DB pool wait/lock contention and storage growth.
Use concurrency approximately equal to arrival rate times service time to build
load scenarios; do not hardcode worker counts from registered population.
Capacity gate requires a declared workload/SLO, bounded saturation behavior and
measured recovery after overload, including EN/ZH long text and audio sizes.

Cache public immutable reference data by revision and language. Private caches
include account/access epoch and obey revocation. Never cache an authorization
failure as global content absence. Cap cache size and expiration explicitly;
cache is discardable, not a second persistence authority.

Telemetry records correlation/operation ID, domain, language, state, duration,
sanitized error class, retry and usage counts. Do not log draft/transcript bodies,
tokens, credential URLs or raw provider payloads. Keep operational usage separate
from learner evidence; a paid call is not a learning achievement.

## 5. Acceptance and handoff

Opus implements admission adapters first, then an isolated durable-job repository
only after schema authorization, then one real expensive consumer. Demonstrate
private-source isolation, revoked source, revision changed during execution,
duplicate submit, worker crash after dispatch, expired lease completion, cancel
race, provider unknown outcome, saturated queue and account deletion. Repeat
language-neutral cases for EN/ZH. Keep current supported providers and existing
media recovery contracts; a runtime migration is not part of visual feature work.
