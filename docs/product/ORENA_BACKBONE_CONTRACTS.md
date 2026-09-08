# Orena backbone contracts

Status: architecture specification for implementation, not deployed API/schema.
Owner: Codex principal architect. Opus implements adapters and features beneath
these contracts. Subordinate to ORENA_REFERENCE_ARCHITECTURE and product/domain
authorities. Current execution evidence: `docs/project/ORENA_BACKBONE_EXECUTION.md`.

## 1. Domain ownership and dependency direction

| Owner | Canonical objects / decisions | Existing implementation anchor | Consumers |
| --- | --- | --- | --- |
| Identity | authenticated principal, session, account lifecycle | `auth_support.py`, `writing_coach/persistence/auth_repository.py`, `writing_coach/persistence/models.py:User` | all private commands/queries |
| Product access | entitlements and usage policy, independently of learning | `writing_coach/product/repository.py`, `writing_coach/persistence/product_repository.py` | admission before expensive execution |
| Content | source identity, original body, rights, revisions | `writing_coach/media_learning.py`, `writing_coach/media_ingestion.py`, `static/orena/content/reading.js` | encounters and capabilities |
| Learner work | draft, turn sequence, pending response, continuation reference | `static/orena/product/memory.js`, `static/orena/product/revision.js`, `static/orena/product/conversation.js` | Writing, Speaking, Continue |
| Capability domains | evaluation and valid evidence meaning | `writing_coach/becoming_reading.py`, `writing_coach/speaking_evaluator.py`, learning/specialized repositories | projections, feedback, recall |
| Language knowledge | linguistic behavior and canonical Concept IDs | `writing_coach/languages/`, static grammar KB | all language-aware capabilities |
| Learner projections | derived views with explicit supporting evidence | existing progress services and `static/orena/product/evidence.js` | Journey, suggestions, Recall, Discover |
| AI platform | provider configuration and execution adapters | existing AI control plane, `writing_coach/media_providers/` | capability services; never direct browser credentials |
| Infrastructure | transactions, job execution, cache, telemetry | `writing_coach/persistence/`, existing provider jobs | domains; never interpretation of learning |
| Experience orchestration | transient focus, source return, request lifecycle | `static/orena/product/intent.js`, `static/orena/ui/understanding.js`, `static/orena/capabilities/outcome.js` | distinct compositions |

Paths in the table are repository-relative.
No new service deployment, all-purpose event bus, router or global frontend
store is required. Services call owning repositories, never another domain's
tables. Cross-domain views use read contracts. Future Social owns membership,
moderation and messaging; Notifications owns delivery preferences; neither is
an AI workload or a new authorization bypass. Native remains frozen.

## 2. Identifier and request contracts

New cross-domain interfaces use these logical fields. Existing wire names are
adapted at boundaries, not globally renamed. Types here are contract notation.

`Principal = {accountId, incarnation, sessionEpoch}` comes only from verified server identity.
`Scope = {principal, learningLanguage}` is immutable for one operation.
`SourceRef = {kind, id, revision?}` reuses canonical domain IDs; kind disambiguates
namespaces. A route, title, URL or normalized phrase is never an account ID.
`WorkRef = {kind, id, version}` identifies work separately from its source.
`EvidenceRef = {domain, id, version}` references the domain-owned result.
Legacy numeric IDs remain valid only within their account/language/domain scope.
User.id and stable UUID mappings are retained; no email-based account merging.

Interface language affects presentation; support language affects explanation;
learning language scopes learner data. They are separate, not inferred from one
another. EN and ZH use the same envelope and lifecycle. Segmentation offsets
declare their indexing convention; convert Python codepoints at the browser
boundary rather than treating them as UTF-16 offsets. Pinyin is an aid, not text
identity or a replacement for Chinese.

`resolve(scope, sourceRef, workRef?, intention?, focus?)` returns a resolved
source/work, missing, forbidden, stale, or unsupported outcome. It checks access
before returning body/context. It never returns a different source as recovery.
Public responses may deliberately collapse forbidden/missing to prevent ID
enumeration. Internal reason codes remain distinct and redact private payloads.

Routes encode only supported intent and public/opaque references. Private text,
provider responses and credentials stay out of URL/history. Browser route state
is an entry request, not authorization or authoritative learner state. Existing
`intent.js` remains the resolver seam; work-type determines continuation target.

## 3. Transition and response lifecycle

1. Capture immutable scope, source, exact text/revision, work version and request
   generation before a call. Validate selection within its supplied passage.
2. Resolve source/access; check content suitability, runtime readiness and
   authorization separately. Preserve domain error envelopes through adapters.
3. Invoke the existing capability; keep pending learner work independently.
4. Accept a presentation result only while account/session epoch, language,
   focus/revision and request generation still match. A late response may belong
   to historical work but cannot mutate the newer visible work.
5. Persist only through the owning command; show saved only after acknowledgment.
6. Leaving destroys view listeners and aborts view requests where possible.
   Leaving a view does not prove cancellation of provider execution or a write.

Logout/account switch increments the view generation, clears private in-memory
objects and prevents outstanding callbacks from writing into the next account's
device namespace. Server work is reauthorized at write/commit, not protected by
a browser cancellation flag. No guest/legacy work is silently attached on login.

Existing four-state CapabilityOutcome remains a presentation adapter. New
services additionally preserve structured reason and retry policy: invalid,
unauthenticated, forbidden and conflict are not generic retryable outages.
Retryable timeouts cannot mean a mutating operation definitely failed. The
existing generic `attempt()` helper is not a server idempotency guarantee.

## 4. Contract compatibility and extension rule

Additive optional fields may preserve a contract version. Required semantics,
identity or evidence meaning changes require a versioned adapter and migration
plan. Unknown enum values fail truthfully; they cannot become success. Old
clients must not replace an object wholesale and erase fields they do not know.
Schema revision, work version, source revision and evaluator version are separate.

An Opus feature declares: owner; existing primitive consumed; input/output and
failure cases; work/evidence distinction; EN/ZH case; return path; acceptance
gate. A new composition needs no new domain. A genuinely new domain must name
its owner and contract before implementation, with Codex architectural review.
