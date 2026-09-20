# Decision Log

This is an append-only log of accepted durable product and architecture
decisions. Do not silently rewrite past decisions. If a decision changes,
append a new entry and mark the earlier entry superseded.

## D-001 — PostgreSQL authority

**Status:** Accepted

**Decision:** PostgreSQL is authoritative after operational cutover. SQLite is
frozen rollback/archive only.

**Reason:** The reviewed cutover, PostgreSQL-backed staging verification, and
runtime smoke established PostgreSQL as the deployed system of record.

**Consequences:** Current operations and architecture must not describe SQLite
as authoritative. SQLite artifacts remain preserved for rollback/archive and
historical tooling.

**Supersedes / Superseded by:** Supersedes the pre-cutover SQLite-authoritative
state. Not superseded.

## D-002 — No hidden persistence synchronization

**Status:** Accepted

**Decision:** No dual-write, reverse sync, silent SQLite fallback, startup
auto-import, or startup auto-Alembic.

**Reason:** Hidden synchronization and mutation paths increase corruption,
rollback ambiguity, and production risk.

**Consequences:** Runtime fails closed, migrations are explicit, and rollback
boundaries remain operator-controlled.

**Supersedes / Superseded by:** None.

## D-003 — Shared features are multilingual

**Status:** Accepted

**Decision:** All shared learner features are multilingual by default; current
required languages are EN and ZH.

**Reason:** BECOMING is one product, not independent English and Chinese forks.

**Consequences:** Shared contracts are language-neutral. Adapters exist only
for real linguistic differences, and language-scoped data remains isolated.

**Supersedes / Superseded by:** None.

## D-004 — First public product composition

**Status:** Accepted

**Decision:** The first public learning product is Writing plus Speaking, both
complete for EN and ZH.

**Reason:** The release must deliver a coherent productive-language loop rather
than prematurely publishing a partial skill set.

**Consequences:** Writing COMPLETE, Speaking COMPLETE, EN PASS, and ZH PASS are
all mandatory before public promotion.

**Supersedes / Superseded by:** None.

## D-005 — Reading and Listening release separately

**Status:** Accepted

**Decision:** Reading releases separately after the first public product;
Listening releases later still.

**Reason:** Their completion and acceptance gates are distinct from the first
Writing + Speaking product.

**Consequences:** Existing internal Reading work does not imply a public claim.
Listening remains hidden future work.

**Supersedes / Superseded by:** None.

## D-006 — AI Control Plane scope

**Status:** Accepted

**Decision:** The AI Capability Control Plane manages AI workloads only.

**Reason:** Provider configuration, capability routing, and AI diagnostics form
a bounded infrastructure concern.

**Consequences:** It does not become a registry for identity, Social, or
deterministic product domains unrelated to AI infrastructure.

**Supersedes / Superseded by:** None.

## D-007 — Social is not an AI domain

**Status:** Accepted

**Decision:** Social is not an AI capability or AI-owned domain. Its future
concept includes Rooms, Friends, Messaging, Presence, Reactions, Blocking, and
Moderation.

**Reason:** Social interaction must remain available when AI is unavailable.
AI may assist Social but cannot own its continuity.

**Consequences:** Future Social contracts and storage stay outside the AI
Control Plane. Documentation does not imply Social is currently implemented.

**Supersedes / Superseded by:** None.

## D-008 — Modular monolith

**Status:** Accepted

**Decision:** The architecture remains a modular monolith for now, not
microservices.

**Reason:** Current scale and team coordination benefit from explicit module and
repository boundaries without distributed-system overhead.

**Consequences:** Domain boundaries are conceptual and enforce ownership inside
one deployable application.

**Supersedes / Superseded by:** None.

## D-009 — Initial realtime Social architecture

**Status:** Accepted

**Decision:** When Social is implemented, initial realtime architecture should
prefer FastAPI WebSocket plus PostgreSQL. Redis is deferred until scale requires
it.

**Reason:** This preserves operational simplicity while leaving a clear scaling
path.

**Consequences:** Do not introduce Redis preemptively or treat this decision as
authorization to implement Social now.

**Supersedes / Superseded by:** None.

## D-010 — No silent paid-provider failover

**Status:** Accepted

**Decision:** No provider-to-provider silent paid failover.

**Reason:** Cost, privacy, behavior, and operator intent must remain explicit.

**Consequences:** Provider failures are visible and typed; changing providers is
an explicit configuration or future reviewed policy decision.

**Supersedes / Superseded by:** None.

## D-011 — Static and live AI validation are separate

**Status:** Accepted

**Decision:** Static AI configuration validation is separate from live
provider/model validation.

**Reason:** Valid configuration must be persistable while a provider is offline,
while live tests need precise credentials, catalog, transport, and response
diagnostics.

**Consequences:** Configuration mutation performs no provider network call;
explicit live-test APIs own runtime validation.

**Supersedes / Superseded by:** None.

## D-012 — Atomic learner runtime activation

**Status:** Accepted

**Decision:** Learner capability routing activation must be atomic; mixed
partial activation is prohibited.

**Reason:** Partial workload migration would create inconsistent behavior and an
unclear rollback boundary.

**Consequences:** Until the reviewed activation gate passes,
`generate_structured()` remains wholly on legacy `active_selection()`.

**Supersedes / Superseded by:** None.

## D-013 — Human coordination and repository context

**Status:** Accepted

**Decision:** The human remains the coordinator between agents; verified Git
state and repository governance documents are persistent project context.

**Reason:** Chat histories are incomplete and transient across implementation,
review, and domain agents.

**Consequences:** Agents follow the canonical read order, update handoffs and
state responsibly, and stop on material contradictions or human gates.

**Supersedes / Superseded by:** None.

## D-014 — Shared Media Learning content

**Status:** Accepted

**Decision:** An imported media source is processed once into one reusable,
provider-neutral Media Learning Object. Its source-language transcript,
timestamped segments, and support-language translations are shared learning
content consumed by both Listening and Speaking Shadowing and reusable by
Vocabulary / Library and Grammar.

**Reason:** Independent media representations for Listening and Shadowing would
duplicate acquisition and processing, allow transcript identity to drift, and
disconnect vocabulary and grammar evidence from the source learners actually
used.

**Consequences:** Learner progress is not part of shared media content. Listening
progress, Shadowing attempts, saved vocabulary, learned segments, and exercise
outcomes remain scoped by user and learning language. M1 may deliver a
non-public Listening MVP before R11; R11 remains the Listening completion and
public-release-readiness gate. R9 remains advanced Shadowing completion rather
than the first authorization for media learning. This decision does not make
Listening or Speaking public and does not close R2.

**Supersedes / Superseded by:** None.

## D-015 — Closed-stage preservation and contract-first integration

**Status:** Accepted

**Decision:** A reviewed CLOSED stage becomes a protected product baseline.
Later stages consume its stable contracts, IDs, and data instead of
opportunistically rewriting the subsystem. Reopening requires a concrete
learner-facing regression, an explicitly approved extension, or a new accepted
architecture decision.

**Reason:** Rebuilding already-passing systems wastes implementation capacity,
creates regressions, and causes agents to lose the product-level roadmap while
chasing local improvements.

**Consequences:** R5 Grammar and M1 Media Learning are the first explicit
protected examples. Writing, Speaking, Reading, and Listening integrations must
reference their stable contracts instead of creating duplicate curricula,
renderers, transcript models, or migration paths. P2 polish remains deferable.

**Supersedes / Superseded by:** None.

## D-016 — Multilingual Writing quality is not a later retrofit

**Status:** Accepted

**Decision:** EN/ZH Writing evaluation quality is part of R3 Writing Evaluation
Completion itself. The former standalone roadmap stage “R4 — Multilingual
Writing Language Lens” is absorbed into R3. R4 is redefined as “Writing
Learning Loop + Grammar Transfer.”

**Reason:** D-003 already establishes multilingual shared behavior as a product
invariant. A later language-lens stage encourages an English-first flow and
creates avoidable divergence.

**Consequences:** R3 must pass representative EN and ZH evaluation and learner
feedback evidence. R4 focuses on turning those findings into targeted practice,
revision, progress, and stable R5 Grammar concept transfer rather than building
a second language-specific evaluator.

**Supersedes / Superseded by:** Supersedes the old R4 roadmap meaning only. It
does not supersede D-003.

## D-017 — Interactive transcript timing is additive to Media Learning

**Status:** Accepted

**Decision:** Real word timing for interactive transcript playback is an
additive interaction layer over the CLOSED M1 Media Learning contract. Native
provider captions remain canonical source text when available. The existing
Groq Whisper ASR boundary may resolve real segment/word timestamps from a
short-lived provider media-file URL and may supply a missing source transcript
when no canonical transcript exists. Supadata remains a transcript fallback;
it does not become a second Media Learning model.

**Reason:** Listening and Shadowing need truthful active-word synchronization,
while M1 intentionally owns stable reusable media assets and segment identity.
Fabricating equal-duration word timestamps or creating parallel Listening and
Speaking transcript pipelines would violate those contracts.

**Consequences:** Word timing is optional API interaction metadata and may
degrade to segment-only synchronization. Provider media is not persisted merely
to obtain timing. EN/ZH use the same flow. Existing source captions are not
overwritten by ASR text solely to gain timing. Provider failures remain typed
and must not cause a hidden cross-provider billing policy. Any future durable
processing-job persistence or schema change requires its normal human gate.

**Supersedes / Superseded by:** Extends D-014 and D-015; supersedes neither.

## D-018 — YouTube timing uses bounded ephemeral provider-native download

**Status:** Accepted

**Decision:** When Groq cannot retrieve a resolved YouTube media URL, Orena may
use yt-dlp itself to acquire the selected audio format into bounded ephemeral
temporary storage and upload those bytes through the existing Groq ASR boundary.
The temporary artifact is not product storage and is deleted automatically.

**Reason:** Live validation on 2026-08-19 showed Groq returning HTTP 400 because
its media fetcher received a 302 redirect. A generic `requests` fallback also
failed, while yt-dlp's own downloader successfully retrieved YouTube format 140.
The provider-native downloader is therefore the transport path actually verified.

**Consequences:** No durable media cache, database schema, or Alembic migration is
introduced. The Groq byte limit is enforced around acquisition, yt-dlp filesystem
cache is disabled for this operation, native captions remain canonical when
available, and no hidden cross-provider failover is added.

**Supersedes / Superseded by:** Extends D-017; supersedes neither D-014 nor D-017.

## D-019 — YouTube word timing degrades truthfully when audio transport is unavailable

**Status:** Accepted

**Decision:** The default YouTube Interactive Transcript path does not claim
word-level timing unless Orena has a verified raw-audio transport that can
deliver real media bytes to ASR. With canonical YouTube captions available,
the learner receives real segment-level synchronization. Without a canonical
transcript, the existing explicitly configured transcript fallback policy may
run. Orena does not fabricate equal-duration word timing.

**Reason:** Live validation on 2026-08-19 showed that Groq could not retrieve
the resolved media URL, generic direct download was not reliable, and a full
yt-dlp audio download returned HTTP 403 even with a supported JavaScript
runtime. A short `--test` download was therefore insufficient evidence for
full-media transport.

**Consequences:** The failed experimental direct-download transport is removed
from the default path. Native caption text and segment timing remain canonical.
Real word timing can return later only through a separately reviewed and
verified media transport capability. This does not authorize hidden provider
failover, account-cookie use, fabricated timing, or a schema change.

**Supersedes / Superseded by:** Supersedes D-018. Extends D-017 without
superseding D-014 or D-017.

## D-020 — Playback clock ownership and learner-facing transcript units

**Status:** Accepted

**Decision:** Media playback owns the provider clock. Interactive Transcript
consumes an internal media-time event and never instantiates or polls a provider
player itself. Canonical M1 transcript snippets remain unchanged; Listening may
derive deterministic learner-facing display units that map one or more
canonical segment IDs into one presentation row. Automatic linguistic AI
annotation is opt-in rather than viewport-triggered.

**Reason:** Browser acceptance showed split player ownership, overlapping
provider caption intervals, learner-visible over-segmentation, and unnecessary
automatic annotation calls. The upstream YouTube transcript contract describes
snippet duration as on-screen duration rather than speech duration and permits
overlaps, so raw snippet intervals are not a valid non-overlapping playback
timeline.

**Consequences:** Active caption lookup uses ordered caption starts with the
next start as the overlap boundary. Display grouping is deterministic and does
not rewrite stable canonical IDs. Dictionary/playback remain usable without AI.
POS/Pinyin annotation begins only after learner opt-in. Real word highlight is
shown only when true word timestamps exist.

**Supersedes / Superseded by:** Extends D-017 and D-019; supersedes neither.

## D-021 — Media Meaning uses isolated local machine translation

**Status:** Superseded by D-026

**Decision:** Normal Media Meaning translation uses a provider-neutral boundary
whose default provider is an isolated local Marian service. Canonical transcript
and playback readiness do not depend on translation readiness.

**Reason:** Per-request generic AI translation adds avoidable latency and cost,
and translation failure must not make otherwise usable media lessons unavailable.

**Consequences:** The application image contains no translation models. Models
are provisioned into a separate cache, loaded lazily by language pair, and used
in bounded batches. Completed translations are cached by engine version,
language pair, and canonical transcript hash. Generic AI remains available only
for explicit intelligence features, not normal Meaning generation.

**Supersedes / Superseded by:** Narrows D-014 for Media Meaning; extends D-020;
superseded by D-026 for the default provider selection.

## D-022 — Orena UI migration uses one bounded shared namespace

**Status:** Superseded by D-024

**Decision:** Frontend `2.17.4` uses `static/becoming/orena/**` as a bounded,
shared migration layer for the Orena shell and rebuilt Home, Writing, and Review
surfaces. The `--o-*` tokens and `.o-*` primitives are shared contracts loaded
after the legacy stylesheet stack. Screens not yet rebuilt are adopted through
the shared compatibility layer rather than receiving copied page-local design
systems.

**Reason:** The reference-led interface requires a coherent responsive shell,
depth, spacing, and interaction vocabulary while the protected Journey,
Library, Grammar, Media Learning, and other stable screens remain operational.
A namespaced migration boundary lets the product advance without a single
high-risk rewrite or uncontrolled cascade conflicts.

**Consequences:** New Orena work reuses the shared namespace, preserves EN/ZH,
light/dark, accessibility, and existing learner-flow contracts, and must not
duplicate tokens into screen-specific CSS. Legacy compatibility is transitional
and may be removed only through a separately reviewed migration. This decision
does not change backend, persistence, learner-skill release state, or production
deployment.

**Supersedes / Superseded by:** Extended the frontend invariant and OREN-16
shared-primitives checkpoint; superseded by D-024 for completed screen scope.

## D-023 — Hanzi stroke order is vendored data, never generated

**Status:** Accepted

**Decision:** Chinese stroke order is served from a glyph dataset vendored into
the repository (Make Me a Hanzi, redistributed as `hanzi-writer-data`, Arphic
Public License) through a deterministic Chinese language adapter,
`writing_coach/languages/chinese/stroke_order.py`, and the route
`GET /api/chinese/stroke-order`. No AI capability produces stroke data, and no
runtime CDN is consulted. A character the pack does not carry is reported as
unavailable; the learner then gets a shape-copying grid that makes no claim
about stroke order.

**Reason:** `UPGRADE_REGRESSION_RULES.md` §33 already forbade claiming verified
stroke order without verified stroke data, which left the Chinese dictionary
with a grid that could only show a finished character. Stroke order is exact,
per-character geometry: a language model cannot produce it truthfully, so the
only honest way to offer the feature is to ship real glyph data. Bundling it
rather than fetching per character from a CDN keeps the feature working offline
and in networks where public CDNs are unreachable — which includes the learner
population this feature is for.

**Consequences:** The repository carries ~14 MB of vendored stroke data
(9,565 characters) plus `ARPHICPL.TXT`, retained unaltered as the licence
requires, and a `README.md` carrying the §2a modification notice for the
container-format change. `scripts/build_hanzi_stroke_pack.py` rebuilds the pack
from the upstream package and `--check` verifies the committed one against its
recorded digest. The renderer, `hanzi-writer` (MIT), is vendored under
`static/becoming/vendor/` and imported lazily, so an English learner never
downloads it. The stroke-order route needs no AI capability and cannot degrade
with a provider. The numbered step diagram is built from the payload rather than
by the renderer, so it survives a failed vendor import.

**Supersedes / Superseded by:** Satisfies the condition `UPGRADE_REGRESSION_RULES.md`
§33 left open. Supersedes no earlier decision.

## D-024 — Orena completes the bounded learner-screen migration

**Status:** Accepted

**Decision:** Frontend `2.17.5` completes the bounded Orena presentation
migration across Home, Writing, Review, Reading, Listening, Speaking, Grammar,
Library, Journey, Profile, onboarding, and sign-in. Dedicated screen layers may
compose the shared `static/becoming/orena/**` tokens and primitives. They do not
own or replace domain models, stable identifiers, persistence boundaries,
learner evidence, release state, or shared EN/ZH behavior.

**Reason:** The explicitly requested resynchronization with `claude/work`
provided a coherent second migration slice for the remaining learner screens,
Grammar pedagogy presentation, Profile settings, and shared supporting
contracts. Keeping these screens indefinitely behind a compatibility-only
layer would leave two visual ownership models. Selective integration plus full
regression, release-gate, and responsive runtime verification establishes one
reviewable frontend boundary without reopening closed product systems.

**Consequences:** New visual work continues through shared Orena tokens and
primitives, with screen-local CSS limited to genuine screen composition.
Journey, Review, Library / Active Recall, Grammar, Media Learning, shared
layout, and overflow contracts remain protected and require focused validation
when touched. R5 Static Grammar KB, stable Grammar Concept IDs, schema-v2
models, completion semantics, PostgreSQL authority, application/frontend
versions, deployment, and learner-skill release state are unchanged.

**Supersedes / Superseded by:** Supersedes D-022 only for migration completion
and screen ownership. Retains D-022's bounded namespace and shared-contract
requirements.

## D-025 — Segmentation and part-of-speech tagging are deterministic

**Status:** Accepted

**Decision:** `writing_linguistic` is a deterministic capability, not a
provider-backed one. Word segmentation and part-of-speech tagging for EN and ZH
are performed locally by `writing_coach/linguistic_annotation.py` (NLTK for
English, jieba for Chinese, pypinyin for contextual readings), shared by the
Writing/Review parts-of-speech lens and the Listening interactive transcript.

**Reason:** The repository carried two implementations of one job. The
transcript already tagged locally and for free; `becoming_linguistics` asked a
model for the same result at 2 800 output tokens an essay. The local tagger's
label set is a superset of the eleven labels the prompt requested — it also
separates `proper_noun`, `classifier`, `auxiliary` and `interjection`, which the
prompt collapsed into `other`. Measured against the AI annotations cached in
eleven real learner essays: 92% of local annotations land on the identical span,
and 82% of those agree on the label; of the disagreements, 67 are the local
tagger being more specific. Neither tagger was ever validated against a gold
standard, so this is a change of engine, not a documented loss of accuracy — and
it makes Writing and Listening agree with each other, which they did not before.

**Consequences:** `writing_linguistic` leaves the configurable provider catalog,
so capability migration seeds seven explicit rows instead of eight and
activation readiness reports seven capabilities. No production rows exist to
orphan: the runtime carries no capability-config table and R2 activation remains
an unexecuted human gate. `configure_becoming_linguistics` no longer takes a
generator. The annotation cache, the literal-span validation, and the public
payload shape are unchanged, so no frontend contract moves.

**Supersedes / Superseded by:** Extends the deterministic-capability precedent
set by `reading_evaluator`. Supersedes no earlier decision.

## D-026 — Groq is the default translation provider; local Marian is the backup

**Status:** Accepted

**Decision:** Shared-media translation defaults to Groq through
`GroqTranslationProvider`, which implements the same `TranslationProvider`
boundary the local service does. Groq is also registered as a provider in the AI
capability catalog, so provider-backed capabilities can be routed to it. The
local Marian service is retained as the backup for a deployment with no external
dependency. The engine is chosen once at startup by
`MEDIA_TRANSLATION_PROVIDER`, defaulting to `groq` when `GROQ_API_KEY` is set
and `local` otherwise.

**Reason:** D-021 established a provider-neutral translation boundary whose
default was the local Marian service, and that service has never worked: it is
missing `protobuf`, and three of its four models were never provisioned.
Measured against this account's key, Groq translates a three-segment batch in
1.43 s with natural Vietnamese, where the local `qwen3:8b` needed 37 s for a
single dictionary entry. Production has no GPU, which rules out a local model as
the default.

**Consequences:** Translation becomes a third-party runtime dependency bounded
by a free-tier quota that is **per API key, so per product rather than per
learner** — the response headers report 1 000 requests and 8 000 tokens a
minute, and the provider records them in `last_quota` so an admin surface can
report the budget before it is exhausted. Surfacing that is not yet built.
Two behaviours were established by measurement and are encoded with their
reasons: `response_format: json_object` is required, because without it a
reasoning model spends its whole budget thinking and returns an empty string
rather than an error; and `reasoning_effort` is deliberately not sent, because
it is unnecessary in JSON mode and other Groq models reject it with HTTP 400.
A failure raises and stops — selecting the other provider is an operator action,
never an automatic switch, per the AI Platform invariant against
provider-to-provider fallback.

**Supersedes / Superseded by:** Extends D-021 by changing its default provider.
D-021's provider-neutral boundary and its rule that playback readiness does not
depend on translation readiness both stand.

## D-027 — Speaking attempts persist evaluator evidence without audio

**Status:** Accepted

**Decision:** Completed EN/ZH Speaking evaluations may be stored as bounded,
learner-scoped attempt records containing the transcript, source segment
reference, measured dimensions, provenance, evidence, and a server timestamp.
Raw audio and proficiency claims are excluded. PostgreSQL is the sole durable
runtime boundary; SQLite remains frozen rollback/archive and does not create or
write Speaking-attempt tables. An explicit migration is required before any
deployment cutover.

**Reason:** R7's learner-visible history/progress acceptance requires completed
take evidence to survive the transient recording screen while preserving the
privacy boundary established by R6. A dedicated repository/API/UI contract
keeps ownership and language scoping explicit without activating public
Speaking capabilities.

**Consequences:** The Speaking attempts API is authenticated and bounded,
updates a take by deterministic `take_id`, and returns unavailable dimensions
as `null`. The mounted EN/ZH screen can show history/progress from that
contract. Migration SQL is prepared but production execution, raw-audio
retention, provider activation, and public release remain human-gated.

**Supersedes / Superseded by:** Extends the R6 transient-audio boundary and
R7 per-take evaluator decision. Supersedes no earlier decision.

## D-028 — R8 release readiness is a deterministic pre-public matrix

**Status:** Accepted

**Decision:** R8 local acceptance is represented by one deterministic EN/ZH
matrix that exercises the existing Writing/Review and Speaking record,
evaluation, pronunciation, and history flows, then records deferred provider,
PostgreSQL migration, capability-activation, and public-promotion gates without
changing learner release state.

**Reason:** Writing (R3/R4) and Speaking (R6/R7) are locally closed, but their
public gate requires joined multilingual evidence and truthful separation of
offline verification from human-controlled operations. A successor matrix
validator keeps that evidence reproducible and prevents a local pass from being
reported as a public release.

**Consequences:** `scripts/r8_release_matrix.mjs` runs the representative browser
contracts, records source-only boundary checks explicitly as static inspections,
and emits deterministic verified/inspected/deferred results. The canonical
report is byte-for-byte checked when the runner is invoked without `--output`.
Credentialed provider smoke, production migration, R2 activation, and promotion
remain explicit human actions.

**Supersedes / Superseded by:** Extends the R3/R4 and R6/R7 local acceptance
decisions. Supersedes no earlier decision.

## D-029 — R9 shared-media Shadowing returns through Speaking feedback

**Status:** Accepted

**Decision:** R9's first Shadowing Studio slice reuses the canonical M1 media
asset and segment session to open the existing Speaking recorder/evaluator, then
restores the same selected segment and Shadowing mode when the learner returns
to Listening.

**Reason:** The learner-visible advanced Shadowing loop must not duplicate media
ingestion or lose context at the Speaking boundary. Existing per-take feedback
already separates content match, pronunciation, fluency, unavailable
dimensions, and unassessed proficiency; this slice connects that loop without
adding raw-audio persistence or new providers.

**Consequences:** `setSharedMediaMode` records only the in-memory return mode,
the R9 mounted EN/ZH contract verifies asset/language/segment continuity and
dimension-specific evaluation, and provider scoring or public activation remain
human-gated.

**Supersedes / Superseded by:** Extends the M1.6 shared-media and R6/R7
Speaking decisions. Supersedes no earlier decision.

## D-030 — Reading internal comprehension loop

**Status:** Accepted

**Decision:** R10 Reading is locally complete for an internal EN/ZH loop from
session creation through passage-specific comprehension evidence, learner
history reopening, and saved-word handoff to Library. Reading results remain
transient comprehension checks and must not be presented as CEFR/HSK mastery.

**Reason:** The mounted contract exercises the existing authenticated Reading
session and answer boundaries in both required languages without promoting the
separate Reading release or introducing a schema/provider decision.

**Consequences:** Future Reading work consumes the existing session/API and
Vocabulary/Library contracts. Public Reading promotion remains a separate
human gate; no production activation or migration is implied.

**Supersedes / Superseded by:** Extends the R9 shared-media acceptance
decision. Supersedes no earlier decision.

## D-031 — Shadowing returns latest matching Speaking feedback

**Status:** Accepted

**Decision:** When Listening reopens an EN/ZH Shadowing segment, it may retrieve
the authenticated learner's latest Speaking evaluator outcome only when its
language, media asset, and canonical segment all match. The UI renders measured
dimensions separately and keeps empty/unavailable states explicit; proficiency
and raw audio are never surfaced.

**Reason:** The R9 handoff already preserves the canonical media identity, but
without this retrieval the learner returns to a score-free placeholder and
cannot connect a completed Speaking take to the segment they practised.

**Consequences:** Listening consumes the existing bounded Speaking attempts API
without new persistence or provider behavior. Public Shadowing/Speaking
promotion remains human-gated.

**Supersedes / Superseded by:** Extends D-029. Supersedes no earlier decision.

## D-032 — Durable Active Listening progress remains audio-free and scoped

**Status:** Accepted

**Decision:** R11 stores Active Listening reconstruction progress in a
PostgreSQL-only specialized record keyed by authenticated learner, learning
language, media asset, and canonical segment. The record contains only bounded
presentation/reveal state, text-match evidence, attempt count, and the latest
learner answer; raw audio, proficiency, and mastery claims are excluded.

**Reason:** Session-only reconstruction state disappeared when a learner
reopened a lesson, while the existing media object already provides stable
asset and segment identities. A scoped, audio-free record closes that learner
continuity gap without reopening M1 media ingestion or R9 Shadowing.

**Consequences:** Listening restores matching progress and renders localized
empty, unavailable, and persistence-failure states. The additive Alembic
artifact is prepared for the PostgreSQL authority, but production migration,
runtime cutover, and public Listening promotion remain human-gated.

**Supersedes / Superseded by:** Extends D-005 and D-029. Supersedes no earlier
decision.

## D-033 — Durable Shadowing rounds remain separate from Active Listening progress

**Status:** Accepted

**Decision:** R11 stores completed Shadowing rounds in a distinct PostgreSQL-only
specialized record keyed by authenticated learner, learning language, media
asset, and canonical segment. Shadowing records contain only a bounded round
count and timestamp; they never persist raw audio, transcript answers,
proficiency, or mastery claims. Active Listening reconstruction records remain a
separate table and state machine even when both practices use the same media
identity.

**Reason:** Shadowing and Active Listening have different learner evidence and
restore semantics. Reusing the reconstruction row would allow one practice to
overwrite or misrepresent the other when a learner revisits the same segment.

**Consequences:** Listening can restore both bounded practice states independently
with localized empty, unavailable, restored, and save-failure feedback. The
additive Alembic artifact is prepared for PostgreSQL authority, but production
migration, runtime cutover, and public Listening promotion remain human-gated.

**Supersedes / Superseded by:** Extends D-032. Supersedes no earlier decision.

## D-034 - Token cost is event-time, versioned operator evidence

**Status:** Accepted

**Decision:** R14 may estimate token cost only from an exact provider/model
entry in the code-owned versioned pricing catalog and complete provider-
reported prompt/completion dimensions. Each telemetry event snapshots the
catalog version and rates used. Unknown models, partial usage, and absent usage
remain distinct unpriced/partial/unknown states; cost is observation only and
never enforces billing, quota, or failover.

**Reason:** Recomputing historical cost from mutable current rates would make
Admin operations misleading. An explicit event-time provenance snapshot keeps
operator evidence auditable while avoiding unsupported price assumptions.

**Consequences:** Admin aggregates cost by currency and catalog version for
capability and bounded trend buckets. Pricing changes require a new catalog
version; no live price fetching or learner-facing behavior is introduced.

**Supersedes / Superseded by:** Supersedes no earlier decision.

## D-035 - Standby provider configuration is explicit and non-routing

**Status:** Accepted

**Decision:** R14 capability configuration may persist an optional, complete
standby provider/model pair after the same static operation validation as the
primary pair. Admin may run a click-only standby health check against that
saved pair. Learner runtime routing remains primary-only; no automatic retry,
cross-provider failover, or activation is implied.

**Reason:** Operators need readiness evidence without coupling preparation of a
backup to learner traffic or silently changing provider behavior.

**Consequences:** PostgreSQL platform settings and the Admin capability matrix
expose sanitized primary/standby configuration provenance. Standby checks are
explicit requests and remain subject to existing server-managed credentials and
human release gates.

**Supersedes / Superseded by:** Supersedes no earlier decision.

## D-036 - Native mobile client uses React Native + Expo + TypeScript

**Status:** Accepted

**Decision:** Orena's first real native mobile client is implemented in a
dedicated `mobile/` workspace using React Native + Expo + TypeScript. It
consumes the existing authenticated backend, R18 mobile/API contracts, shared
EN/ZH domain semantics, Media Learning identities, and PostgreSQL-backed server
authority. The app is not a WebView wrapper and must not copy web DOM/CSS or
fork learner scoring, Grammar, progress, or provider logic.

**Reason:** R18 intentionally completed only the server/API readiness layer.
There is no Android/iOS client workspace in the repository, so mobile remains a
real product gap. React Native + Expo provides one Android/iOS implementation
with strong TypeScript tooling and native access to microphone/audio, secure
storage, deep links, and app lifecycle behavior while preserving the existing
server architecture.

**Consequences:** R19 owns the mobile shell, typed API/session layer,
localization/theme/accessibility foundation, secure native session handling,
bounded caching, and native media permission boundaries. R20 owns learner-flow
parity. R21 owns release readiness and store-entitlement integration on top of
R15. Provider secrets remain server-side; production OAuth-console changes,
signing keys, store credentials, production activation, billing activation, and
public store submission remain explicit human gates.

**Supersedes / Superseded by:** Extends R18 mobile/API readiness and the shared
web/server product architecture. Supersedes no earlier decision.

## D-037 - Provider credentials are configured through an authenticated server UI

**Status:** Accepted

**Decision:** Admin may submit a provider credential through the same-origin
authenticated Admin application. The server validates the provider connection,
encrypts the credential before persisting it in the authoritative platform
settings store, and returns only masked status and model metadata. Credential
values are never returned to the browser, included in capability configuration,
telemetry, or operator-facing errors. A separate `AI_PROVIDER_SECRETS_KEY`
bootstrap secret must be supplied by the deployment secret store; the UI never
creates, displays, or replaces that encryption key.

**Reason:** Editing provider keys in source or `.env` files is operationally
unsafe and makes routine provider setup depend on filesystem access. The
server-managed flow follows the Dify-style boundary of encrypted-at-rest
credentials, explicit connection validation, and provider/model configuration
that is separate from secrets, while keeping this repository's no-production-
activation rule intact.

**Consequences:** The Admin UI can test, save, and remove cloud-provider
credentials without plaintext persistence. Production still requires TLS,
secure bootstrap-secret delivery, backup/restore handling for the encryption
key, audit/alert review, and explicit human approval before a credentialed
provider is activated for learner traffic. Loss or rotation of the bootstrap
key makes stored credentials unreadable until an approved key-recovery plan is
executed.

**Supersedes / Superseded by:** Supersedes no earlier decision.

## D-038 - Listening is content-first over one canonical Media Learning engine

**Status:** Accepted

**Decision:** The primary Listening entry is a curated, topic- and level-aware
content library. Learner-imported media remains available under My Media as a
secondary source. Curated excerpts and imported assets both resolve to the
existing canonical Media Learning Object, timestamped transcript segments, and
the same Listening workspace; Listen, Active Listening, Dictation, Shadowing,
progress, and Speaking handoff are modes over that shared identity rather than
separate players or transcript stores. A source may own multiple curated
excerpt identities, each with explicit start/end bounds and provenance, while
the canonical media object continues to own transcript content.

**Reason:** Requiring a learner to find and paste a URL before Listening has
value makes acquisition tooling the product. A curated library gives the
learner something useful immediately, while one shared engine prevents curated
and imported media from drifting into unequal learning experiences.

**Consequences:** Curated catalog listings stay metadata-light and load the
full media/transcript only when a lesson opens. Excerpt duration follows a
complete learning idea instead of a fixed timer. Built-in content requires
explicit rights/provenance metadata and verified timing; absent internal timing
must not be fabricated. EN and ZH, web and native, and resume/handoff contracts
must remain aligned. Catalog publication, broad content licensing approval,
and R11 public promotion remain human gates; this decision does not publish a
lesson or activate a provider.

**Supersedes / Superseded by:** Extends D-005, D-017, D-029, D-032, D-033,
and D-036. Supersedes the former Listening landing hierarchy in which media
URL import was the primary action, but does not supersede the canonical Media
Learning architecture.

## D-039 - Listening catalog publication is manifest-driven and rights-gated

**Status:** Accepted

**Decision:** Built-in Listening content is registered in a versioned catalog
manifest that keeps canonical source media and transcript segments separate
from curated excerpt lessons. A source may back multiple lesson identities;
lessons reference the source's canonical segments and add only excerpt,
discovery, level, lifecycle, and pedagogical metadata. Only `PUBLISHED` lessons
whose source rights have been explicitly reviewed may be returned to learners.
Both `estimated_level` and its evidence are retained, while an editorial
`reviewed_level`, when present, is the displayed canonical level.

**Reason:** Product content must be curatable without changing a React screen,
must preserve the one-source-to-many-excerpts model, and must not turn unsafe or
unreviewed external media into built-in catalog content. Separating source and
lesson records also prevents transcript duplication and keeps level decisions
explainable and overridable.

**Consequences:** Topic and tag taxonomies can expand through catalog data;
catalog listing remains metadata-light; full transcript/media payloads load
only when a lesson opens. Editors can move content through draft, processing,
review, ready, published, and archived states, but publication, licensing
approval, and public Listening promotion remain human gates. This decision does
not create a production CMS, publish third-party copyrighted content, or alter
learner-import policy.

**Supersedes / Superseded by:** Extends D-038 and the canonical Media Learning
decisions it references. Supersedes no earlier decision.

## D-040 - Orena direction is restored from repository-backed project memory

**Status:** Accepted

**Decision:** Orena is the canonical active product identity and `/` is its
canonical web route. `/becoming` is compatibility-only. Historical
BECOMING-named files, directories, symbols, database identifiers, and archived
evidence may remain where technically required but do not define current
product direction. The approved responsive Orena web product is the visual,
functional, and interaction source of truth; native mobile is a full native
port, not an independent redesign or simplified edition.

Current project direction and execution state are restored from the bounded
repository-backed memory rooted at `docs/project/PROJECT_MEMORY.md`. Agent chat
history is never authoritative project state. Durable product intent is
human-governed; machine-readable current truth is schema-validated; retired
directions are tombstoned; and every verified batch runs the project-memory
validator before commit.

**Reason:** Multi-agent sessions lose chat context and were repeatedly reviving
obsolete routes, names, design assumptions, and stale roadmap paths. A compact,
versioned, machine-enforced repository memory lets a zero-context session
recover the active product, current state, retired directions, human gates, and
exact next task without loading all historical documents.

**Consequences:** `PRODUCT_CONSTITUTION.md`, fundamental
`DESIGN_CONTRACT.md` principles, and `LEGACY_TOMBSTONES.md` are human-governed.
`CURRENT_PRODUCT_STATE.yaml` accepts only its validated schema. The compact
`CURRENT_HANDOFF.md` no longer carries historical closeouts. CI fails on active
navigation to `/becoming`, learner-facing BECOMING branding, route/state
contradictions, EN/ZH parity loss, independent-native-redesign state, or missing
memory contracts. Valid legacy technical namespaces and compatibility redirect
tests remain allowed.

**Supersedes / Superseded by:** Extends D-013 and supersedes any interpretation
that chat history, human recollection, legacy filenames, or the old route is the
primary source of current project direction. It does not supersede valid
historical implementation contracts recorded by D-014 through D-039.

## D-041 - Skill state is seven independent truths, and a Listening engine is not a Listening catalog

**Status:** Accepted

**Decision:** `CURRENT_PRODUCT_STATE.yaml` records each learner skill as seven
independent dimensions - implementation, local acceptance, pre-public matrix,
learner visibility, content readiness, human acceptance, and public release -
instead of one collapsed status enum. Listening additionally carries a
`real_media_catalog` block holding its own readiness, per-language real playable
evidence, human playback acceptance, and catalog publication state. Seed, mock,
or synthetic content is never real-content completion evidence.

**Reason:** The single per-skill enum (`development` /
`pre_public_matrix_complete` / `public`) collapsed distinct verified truths into
one misleading value, in both directions. Reading `development` for locally
completed Writing, Speaking, and Reading invited a fresh agent to rebuild work
that R3/R4, R6/R7/R9, and R10 had already closed with local acceptance passes.
Reading `pre_public_matrix_complete` for Listening implied a finished product,
when human QA confirmed the built-in lessons remain seed/synthetic, real source
video playback has not been accepted, and cards can present text with no
meaningful real video. Behavioural completeness and content completeness are
different facts and now have different fields.

**Consequences:** `release_state` keeps only genuinely global release facts;
per-skill status lives in `skills.state`. The validator enforces that public
visibility requires an approved public release, that release requires human
acceptance, that seed/mock content can never carry real playable evidence,
human acceptance, or publication, that a complete real catalog requires real
playable EN _and_ ZH evidence plus human playback acceptance, and that
`skills.state.listening.content_readiness` cannot drift from
`listening.real_media_catalog.status`. Completed local work paired with
`internal` visibility is an explicitly valid state and must not be read as
missing. The memory schema version moves to 1.1.

**Supersedes / Superseded by:** Supersedes the collapsed per-skill
`release_state` enum introduced with D-040. It does not modify D-040's memory
topology, precedence model, or governance ownership, and supersedes no
implementation contract.

## D-042 - Support language is a learner choice, and missing captions are not rejection

**Status:** Accepted

**Decision:** LEARNING_LANGUAGE, SUPPORT_LANGUAGE and UI_LOCALE are three
distinct concepts. Meaning, explanations, grammar notes and dictionary support
are delivered in the learner's support language, resolved as stored profile
preference → explicit valid selection → configured neutral default, and stored
BCP-47-shaped in the learner profile. Separately, a playable supported video
without captions is a valid media source: playback state and transcript state
are independent, missing captions start recovery through the existing provider →
ASR → Supadata chain, and a generated transcript discloses its provenance.

**Reason:** Both rules were lost repeatedly. Vietnamese had become the de facto
canonical translation target in four places - `validSupportLanguage` accepting
only vi/en/zh, `supportLanguage()` falling back to vi, `target_language` defaulting
to vi, and `targetLanguage || 'vi'` in the client - which encoded Orena as a
Vietnamese-only product in the data model rather than in configuration. In
parallel, a caption-less video was being treated as unsupported, which threw away
media the product can genuinely teach from, and My Media and the bulk importer
had drifted into two different definitions of "no captions" because they built
the provider adapter with opposite recovery flags.

**Consequences:** `writing_coach/core/support_languages.py` holds the one resolution
rule; the profile exposes a resolved `support_language`; the client keeps no
language default of its own. `writing_coach/media_recovery_policy.py` holds the
one recovery policy, and both the runtime and the importer build their adapter
through it, so neither can drift again. `transcript_origin` travels with every
media response and joined the shared workspace contract. Vietnamese remains a
fully supported support language - it is simply no longer the built-in answer.

**Supersedes / Superseded by:** Supersedes any earlier reading in which
Vietnamese was the canonical translation target or in which absent captions made
a source unsupported. Supersedes no implementation contract.

## D-043 - Unreviewed development catalog content is QA'd off production

**Date:** 2026-09-02

**Status:** Accepted

**Decision:** Generated development catalog content (`DEV_CANDIDATE` /
`rights_review` / `proposed`) is reviewed on a separate local development
runtime, never on the production domain. The runtime is the same app image run
from the worktree with `APP_ENV=development`, `ENABLE_DEV_LISTENING_CATALOG=1`,
SQLite, writable paths under `/tmp`, published on `127.0.0.1` only and kept off
the tunnel. Promotion into the production catalog remains a human gate.

**Reason:** L3 produces content at scale whose rights and pedagogy are not yet
reviewed. An admin-gated preview inside production was considered and rejected:
it would mean the production runtime serving unreviewed content, and it would
put the dev overlay one authorisation bug away from public learners.
`orena.chillpickle.org` runs `APP_ENV=production`, where the overlay is refused
by design, and that guard must not be weakened to enable QA.

**Consequences:** L3 can proceed without touching production or the deployment
gate. The production guard in `listening_catalog.dev_catalog_enabled()` stays a
hard refusal rather than a configurable one. QA evidence for generated content
comes from the development runtime and is labelled as such.

**Supersedes / Superseded by:** Supersedes the earlier open question of how L3
content would be visually QA'd. Supersedes no implementation contract.

## D-044 — Orena experience-first product model

**Status:** Accepted

**Decision:** Orena's durable product North Star is now defined by
`docs/product/ORENA_PRODUCT_CONSTITUTION.md`.

Learner-facing Orena is organized conceptually around meaningful language
experiences, contexts, discovery, understanding, expression, and continuation.

Reading, Writing, Listening, Speaking, Grammar, Vocabulary, Pronunciation,
Dictation, Shadowing, and Active Recall remain underlying learning capabilities
and technical domains, but do not automatically define the learner-facing
information architecture.

AI remains an enabling layer rather than the conceptual identity of the
learner-facing product.

Meaningful learner-facing development must use browser-reviewable vertical
slices and human product checkpoints.

**Reason:** Orena is evolving from a skill/module-centered learning application
into a coherent language-learning world where multiple capabilities participate
naturally in connected experiences. Durable repository guidance is required so
new agents do not reconstruct product direction from historical implementation
alone.

**Consequences:** Product intent authority moves to
`docs/product/ORENA_PRODUCT_CONSTITUTION.md`. Existing implementation, release
states, historical decisions, and technical contracts remain valid evidence of
current system state where factual, but no longer define Orena's product North
Star.

**Supersedes / Superseded by:** Supersedes earlier global product assumptions
that treat Writing-first sequencing, individual skill modules, or a historical
presentation system as Orena's permanent conceptual hierarchy. It does not
invalidate technical domain contracts or verified historical implementation
facts.

## D-045 — Orena content world combines discovery with learner-owned content

**Status:** Accepted

**Decision:** Orena's learner-facing content model must support both a rich
discoverable Orena-provided content world and learner-owned content brought into
the product.

The durable content contract is defined by:

`docs/product/ORENA_CONTENT_ARCHITECTURE.md`

Orena should provide meaningful texts, media, situations, prompts,
conversations, stories, ideas, and other language experiences worth
discovering.

Learners should also be able to bring supported content they genuinely care
about into Orena.

Where technically and pedagogically appropriate, Orena-provided and
learner-imported content should enter the same learning architecture rather than
forming disconnected products.

Reading, Listening, Writing, Speaking, Grammar, Vocabulary, Shadowing,
Dictation, and Recall remain learning capabilities that may participate in
those experiences.

**Reason:** The experience-first Product Constitution establishes discovery,
meaningful content, continuity, and learner agency, but the existing
implementation can still be interpreted as separate learning tools: generated
Reading passages, a media-import-oriented Listening surface, Writing task
selectors, Speaking recorders, and an Active Recall Library.

Without a durable content contract, future agents may preserve or redesign
those implementations as isolated feature modules rather than building the
content-rich world required by the current Orena direction.

The product must be useful and interesting before a learner imports anything,
while still allowing learners to connect their own interests and materials to
the same learning system.

**Consequences:** Content origin must remain truthful. Curated/provided,
generated, imported, and saved content must not be falsely represented as one
another.

Reading must not treat generated Article / Book / News / Quote simulations as
the complete Reading end-state.

Listening media import remains a valid and important input path, but it is not
the definition of the Listening product.

Speaking should continue to reuse shared media identities where appropriate
rather than creating an unnecessary parallel media pipeline.

Writing should evolve beyond exercise-type selection into meaningful reasons
and situations for expression while preserving free/custom learner starting
points.

Explore, learner-owned content, learner-collected language, and Active Recall
are distinct product concepts even if future UI terminology changes.

Existing stable learning, evaluation, Media Learning, Grammar, persistence, and
learner-evidence contracts should be reused rather than rebuilt merely to
implement this content model.

English and Chinese remain first-class across both Orena-provided and
learner-owned content experiences.

External content must preserve truthful provenance and follow applicable rights
and provider constraints.

**Supersedes / Superseded by:** Extends D-044 and D-014. It does not supersede
the stable Shared Media Learning contract or existing verified learning-domain
implementation.

## D-046 — Experience-centered entry, synchronized Follow, and product-layer reset

**Status:** Accepted by explicit human instruction, 2026-09-06.

**Decision:** Orena is experience-centered, not discovery-only. Discovery,
direct intentional practice, continuation, learner-owned content, and revisiting
language are first-class entry intentions. Direct Dictation, Shadowing,
Speaking, Writing, Grammar, and Recall access is valid. Every entry converges
on shared capability primitives, content identities, and learner evidence.

Listening must provide synchronized Follow: media playback, active original
segment, and that segment's support-language meaning together. Seeking,
transcript selection, replay, and speed changes preserve synchronization.
Chinese is primary with optional contextual Pinyin. Follow never requires
Dictation or Shadowing; deeper practice can use the current segment.

**Consequences:** Physically remove historical learner-facing skill dashboards,
module shells, Listening mode destinations, Shadowing Studio, screen-specific
handoffs/session orchestration, and tests/specifications whose sole purpose is
to preserve that product model. Extract and independently test useful primitives
from mixed modules before deletion. Git history is the archive; no legacy copy.
Build the new product layer around content, encounters, practice intentions,
continuation, learner memory, and expression. Preserve auth, ownership,
PostgreSQL, APIs, providers, media retrieval, evaluation, and evidence contracts
where valid. Deleting obsolete working-tree files is explicitly authorized;
production operations and destructive history rewriting remain unauthorized.

**Supersedes:** Narrows D-044/D-045 interpretations that could force discovery
before practice. Supersedes historical product shell, screen hierarchy,
Listening-mode and Studio composition decisions, and native instructions to
reproduce those obsolete products. Historical verified technical facts remain
historical facts. The preceding uncommitted experience mission is discarded as
a product direction; only independently useful primitives or approved assets
may survive. Product approval of the new implementation remains a final human
browser-review gate.

## D-047 — Bounded conversation evidence over shared web capabilities

2026-09-07. Human-authorized continuation of the Golden Star WEB mission.
Conversations use an ordered, immutable exchange of learner and generated partner
turns. A pending learner turn is retained before requesting a partner response;
retries reuse that exchange and responses identify the turn they answer. Closing
an exchange rejects late responses. Typed replies are not speech measurements.
Voice transcripts enter the composer by explicit learner action, using the same
recorder/evaluation/coaching primitives as independent Speaking.

The first implementation stores up to twelve bounded exchanges in existing
owner/language-scoped device memory. Per-take measured evidence stays in the
existing PostgreSQL API; conversational text does not create mastery claims.
The provider adapter is stateless and receives bounded turns as untrusted data.
No new schema, credential activation, real-person impersonation, or server-side
conversation durability is implied. Cross-device history can later replace the
storage adapter without replacing the exchange model.

## D-048 — Principal backbone ownership and implementation separation

2026-09-08. Explicit human direction: Codex/GPT-6 owns the complete Orena
reference architecture and technical backbone, beyond a single package. Opus
owns feature implementation, interactions, UI execution and verification under
those contracts. Existing A-D implementation is preserved; active Opus WIP is
reserved and each architecture cycle restores live Git before changes.

The required backbone explicitly includes account lifecycle and learner profile,
commerce/plans/subscription/entitlement/quota, Collection/My Content/My Language,
content/provider execution, evidence-backed Profile/Growth/achievement contracts,
and final integration/migration gates. Dedicated specifications are linked from
ORENA_REFERENCE_ARCHITECTURE.md; execution and evidence remain in project memory.

Ordinary architecture milestones may proceed continuously. This does not grant
destructive migration, schema/runtime activation, credentials, billing policy,
production operations or human Golden Star approval. No approved learner-facing
direction, theme/brand implementation or completed Opus feature is superseded.

## D-049 — Content domains, Understanding Engine, and Vocabulary Cards

**Status:** Accepted by explicit human instruction, 2026-09-12.

**Decision:** Orena's content architecture is amended per
`docs/product/ORENA_PHILOSOPHY_AMENDMENT_CONTENT_UNDERSTANDING.md`. Reading,
Writing, Listening, Speaking, Vocabulary, and Language Knowledge are separate
canonical learning domains, each with its own content model, sharing common
infrastructure for ingestion, provenance, publishing, indexing, recommendation,
moderation, and search. Do not force them into one universal content schema.

Orena adds a shared **Understanding Engine**: a cross-domain capability that
explains language through mental models, intuition, contrasts, and verified
knowledge rather than defaulting to translation-only or rule-memorization
answers, reusable from Reading, Listening, Speaking, Writing, and Vocabulary
alike. It must clearly distinguish a useful mental model or mnemonic from
verified linguistic fact.

Orena adds a reusable **Language Knowledge Graph** supporting that engine, and
a richer **Orena Vocabulary Card** specification — beyond `word ->
translation` — including pronunciation, meaning, usage, examples, semantic
connections, and, for Chinese and future scripts, a first-class
**orthography** capability (radicals, components, stroke order, tracing),
built as a general capability rather than hard-coded per script.

Discover/Home must distribute content from the domain libraries; they must
not own hard-coded canonical content. The target is substantial curated
default libraries over time, not one or two sample items kept small
indefinitely.

The durable contracts are:

`docs/product/ORENA_CONTENT_ARCHITECTURE.md` (amended)
`docs/product/ORENA_UNDERSTANDING_ENGINE.md` (new)
`docs/product/ORENA_VOCABULARY_ARCHITECTURE.md` (new)
`docs/product/ORENA_PRODUCT_CONSTITUTION.md` §31 (new)

**Reason:** Without this amendment, future agents could keep reducing content
work to "add a sample item to Discover's array" and vocabulary work to "a
flat saved-word list," as the existing implementation and even a same-session
task had just done. The Constitution and Content Architecture already implied
a content-rich world (D-045) and already named `Understanding` as an evidence-
owning capability (`ORENA_EVIDENCE_ARCHITECTURE.md` §1) and a canonical
Experience Composition (`ORENA_REFERENCE_ARCHITECTURE.md` §6, `ui/
understanding.js`), but neither the explanation philosophy, the Language
Knowledge Graph, nor a real Vocabulary Card model existed as a durable
contract. This decision names them explicitly so the gap cannot be mistaken
for "not yet gotten to" versus "not yet specified."

**Consequences:** `ORENA_CONTENT_ARCHITECTURE.md` is restructured: Vocabulary
and Language Knowledge become their own sections instead of a brief joint
mention with Grammar; Discover's distribution-not-storage role and a content
scale philosophy (batch/incremental growth, not hand-edited arrays) are made
explicit; the shared-infrastructure section is reworded to foreclose reading
it as one universal schema.

This does not reopen or re-litigate any CLOSED subsystem (R5 Grammar, M1
Media Learning) or any already-accepted backbone contract
(`ORENA_BACKBONE_CONTRACTS.md`, `ORENA_EVIDENCE_ARCHITECTURE.md`,
`ORENA_COLLECTION_ARCHITECTURE.md`, `ORENA_CONTENT_EXECUTION_ARCHITECTURE.md`).
The Understanding Engine deepens the existing `Understanding` capability and
the Language Knowledge Graph extends the existing Language Knowledge domain
ownership (`ORENA_BACKBONE_CONTRACTS.md` §1); neither replaces stable Grammar
Concept IDs. The Vocabulary Card model sits on top of the existing saved-word/
`LanguageItemRef` identity (`ORENA_COLLECTION_ARCHITECTURE.md`) without
changing how saving, occurrence identity, or review scheduling work.

No new persistence, schema, provider activation, or production change is
authorized by this decision. Any schema the eventual implementation needs
follows the existing architecture-review gate (`AGENTS.md` §1) — an
implementer does not self-approve it, matching the standard already applied
to the I2/I3 backbone schema proposals.

The already-committed small growth of the Discover generated-fiction array
(`da0e0b2`) is not reverted: the content itself remains valid under §2's
`origin: generated`, and existing hand-authored arrays are an acceptable
starting seam per §18. What changes going forward is the strategy — hand-
editing that array is not the target end-state, and Discover ceasing to own
it directly is (§3, and the tombstone recorded in `LEGACY_TOMBSTONES.md`).

**Supersedes / Superseded by:** Extends D-045 and D-044. Retires the implicit
interpretation that a small hard-coded Discover array or a flat saved-word
list is the completed Vocabulary/Discover product, recorded as a tombstone in
`docs/project/LEGACY_TOMBSTONES.md`. Does not supersede R5 Grammar, M1 Media
Learning, or any accepted backbone architecture contract.

## D-050 — Correcting D-049: Understanding is horizontal, not a sixth domain

**Status:** Accepted by explicit human instruction, 2026-09-12.

**Decision:** D-049's first integration over-modeled two things that were not
the intended product model, and this decision corrects them without reopening
the rest of D-049:

1. D-049 stated "Reading, Writing, Listening, Speaking, Vocabulary, and
   Language Knowledge are separate canonical learning domains." This is
   wrong. Orena has **five** canonical content domains — Reading, Writing,
   Listening, Speaking, Vocabulary. The Understanding Engine is a **horizontal
   capability** shared across all five, not a sixth learner-facing content
   domain or library a learner browses directly.
2. D-049 stated "Orena adds a reusable Language Knowledge Graph supporting
   that engine." This is wrong as a requirement. The Understanding Engine is
   **AI-first and context-grounded**: it receives the learner's exact context
   (the source sentence, media segment, or writing/speaking sample) and
   generates an explanation through the **Orena Explanation Contract**, not by
   looking an answer up in a precomputed store. An **explanation support
   layer** — trusted linguistic references, dictionary/corpus/etymology
   sources where needed, reusable explanation patterns, caching, retrieval,
   and quality/grounding validation — may be added later, but only as an
   **optional optimization once real repeated-question evidence justifies
   it**, never as a prerequisite or a canonical product domain. A structured
   knowledge graph, if ever built, is one possible shape that layer's
   caching/reference storage could take — it is not a required component.

The corrected explanation-generation model is:

```text
context -> cache/retrieval check -> AI explanation -> validation -> response
-> reusable cache where appropriate
```

Exact-context questions must still be generated from the learner's real
sentence/media/writing/speaking context; the flow above never substitutes a
pre-stored generic answer for that.

The Orena Explanation Contract's expected fields are: core idea; mental model
/ intuitive image; why the form works in the current context; related usages
where useful; contrasts; common learner misunderstanding; natural examples;
an optional quick check.

The accuracy rule is sharpened from a two-way distinction to a four-way one:
a mental model, a mnemonic, a linguistic explanation, and verified
etymology/history are four different things. An invented mnemonic or
explanatory story must never be presented as historical linguistic fact.

**Reason:** The human reviewing the D-049 integration identified that treating
Language Knowledge as a sixth content domain, and requiring a precomputed
Language Knowledge Graph as a prerequisite for the Understanding Engine, does
not match Orena's intended product model. The Understanding Engine is meant to
be reachable from within Reading, Writing, Listening, Speaking, and
Vocabulary — never a destination of its own — and meant to scale by generating
explanations live from context, not by pre-storing answers for every possible
question in a growing knowledge base ahead of actual need.

**Consequences:** `docs/product/ORENA_UNDERSTANDING_ENGINE.md` is rewritten:
its diagram shows the five domains pointing into one horizontal engine; its
principle section states AI-first/context-grounded/format-constrained/
cache-retrieval-assisted explicitly; the Orena Explanation Contract and the
four-way accuracy rule are defined as their own sections; the former
"Language Knowledge Graph" section is replaced by an "explanation support
layer" section that is explicitly optional. `docs/product/
ORENA_CONTENT_ARCHITECTURE.md` drops its "Language Knowledge" section
entirely (renumbering every following section down by one) and restates the
domain count as five with the Understanding Engine shown as horizontal.
`docs/product/ORENA_VOCABULARY_ARCHITECTURE.md`,
`docs/product/ORENA_PRODUCT_CONSTITUTION.md` §31,
`docs/project/ROADMAP.md`'s Golden Star / Content Domain sequence,
`docs/project/ARCHITECTURE_INVARIANTS.md`, `docs/project/PRODUCT_MAP.md`,
`docs/project/DOMAIN_BOUNDARIES.md`, `docs/product/ORENA_BACKBONE_CONTRACTS.md`,
and `docs/product/ORENA_REFERENCE_ARCHITECTURE.md` are corrected to match. The
roadmap's sequence items 1-2 become "Understanding Engine + Orena Explanation
Contract" and "Explanation support layer" (trusted linguistic references;
dictionary/corpus/etymology sources where needed; reusable explanation
patterns; caching; retrieval; quality/grounding validation) — a knowledge
graph is no longer named as its own roadmap phase, only as a possible later
optimization inside the support layer. A new tombstone,
"Language Knowledge modeled as a sixth content domain / mandatory precomputed
graph," is recorded in `docs/project/LEGACY_TOMBSTONES.md` so an agent reading
the original amendment document directly does not reintroduce this framing.

This does not reopen or weaken the parts of D-049 that remain correct: five
domains existing as real canonical domains, the Orena Vocabulary Card
specification and its orthography capability, the Discover/Home
distribution-not-storage correction, the content-scale philosophy (batch/
incremental growth over hand-edited arrays), or the two tombstones D-049
already recorded. No new persistence, schema, provider activation, or
production change is authorized by this decision; any schema a later
implementation needs — including any future explanation support layer
storage — still follows the existing architecture-review gate (`AGENTS.md`
§1).

**Supersedes / Superseded by:** Corrects D-049's domain-count and
Language-Knowledge-Graph-as-prerequisite claims only. Does not supersede
D-049's other decisions, D-045, D-044, R5 Grammar, M1 Media Learning, or any
accepted backbone architecture contract.

## D-051 — One-frame learning loop, symbol-first optional guidance, coherent interface language

**Status:** Accepted by explicit human instruction, 2026-09-12.

**Decision:** Orena's learner-facing web experience follows a durable set of
design rules, recorded in `docs/project/DESIGN_CONTRACT.md` ("Learner-facing
experience rules"):

- every visible element must help the learner understand, act, understand the
  result, improve or continue, or it is removed, compressed, symbolised,
  demoted or moved after the learning loop;
- on desktop the core learning loop - source needed now, activity, learner
  work, essential controls, submit, immediate result and primary feedback -
  shares one viewport-sized frame wherever the experience can support it, with
  long content scrolling inside its own region;
- on narrow screens the same loop becomes sequential frames: the activity, then
  the result the learner is placed at the start of, with a natural way back;
- secondary material (history, earlier attempts, deeper theory, alternative
  starting points, continuation) comes after the loop;
- rooms where the learner works open compactly; atmosphere and artwork belong
  to entry, discovery, completion and empty states;
- supplementary guidance and minor status use a semantic symbol whose words
  appear on hover, focus or tap, while essential instructions and consent or
  privacy statements stay visible;
- information roles (material, instruction, input, error, correction,
  explanation, rule, result, next action, help, metadata) are visually
  distinguishable;
- learner-facing scaffolding follows the interface language through the shared
  localisation architecture, with no single-language special case;
- one design language with distinct experience compositions, solved in shared
  primitives rather than copied markup.

**Reason:** Surfaces kept revisiting the same basic problems - activity rooms
opening like entry pages, immediate results landing below the fold, optional
explanations and device metadata occupying layout as prose, and a result
column holding alternative starting points instead of the answer. Fixing them
page by page would keep reopening layout, hierarchy, helper text and feedback
placement instead of letting later work concentrate on content, pedagogy,
Understanding, Vocabulary and learning capabilities. A durable contract makes
the rule the default for every new surface.

**Consequences:** The web foundation gains shared primitives used by the rooms
that now follow the rule (`ui/patterns.js`: `hint`, `installHints`,
`workspaceFrames`, a symbol-form `draftStatus`, a compact `pageIntro`; a
back-row `practiceReturn`; `ui/symbols.js`), described in
`docs/product/ORENA_WEB_EXTENSION_GUIDE.md`. Writing, Speaking, Dictation,
Grammar lessons and Recall are brought under the rule in the same batch;
remaining surfaces are named as follow-up in `docs/project/CURRENT_HANDOFF.md`.
Native, when it thaws, ports these rules with the rest of the approved web.

This preserves the Product Constitution, Content Architecture, D-046's
experience-centred reset, the five content domains and horizontal
Understanding Engine (D-049/D-050), evidence ownership, the Speaking
distinction between measured evidence and coaching, Listening's synchronized
Follow composition, the canonical multi-theme system and the approved brand.
It changes no persistence, account, commerce, provider or capability semantics.

**Supersedes / Superseded by:** Adds to `DESIGN_CONTRACT.md`; supersedes no
earlier durable decision. It replaces the practice-room convention of naming
the current room in a divider row below the heading (an implementation
convention, not a recorded decision).

## D-052 — On a phone the screen belongs to the learning

**Status:** Accepted by explicit human instruction, 2026-09-12.

**Decision:** Narrow and mobile web adapt navigation, controls and the
learning content itself so the learner sees and works with substantially more
useful information per frame, in the priority learning content and learner work,
then controls, then navigation and secondary chrome. Recorded as rule 12 of the
Design Contract's learner-facing experience rules: an adaptive header that
compacts while the learner scrolls into a room and releases real height;
compact controls that keep full touch targets; denser but readable learning
typography and spacing; destinations that clear the header at its current
height; experience-specific priorities for Listening, Writing, Reading and the
action rooms.

**Reason:** At 390px the full header held 131px of an 844px screen at all
times, the Writing editor was 112px tall, a Listening voice card and its
controls filled the first screen before the spoken line and none of the
transcript was visible, and a source strip that stuck to the top of the page
slid underneath the header. D-051 fixed where results land; this fixes how much
of the phone the learning actually gets.

**Consequences:** The narrow shell gains a compact state (`#shell[data-compact]`)
driven by scroll intent in `app.js`, with its live height published as
`--shell-offset` and requested before any programmatic move to the learner's
work (`focusWork()` in `ui/html.js`). A phone density block in `rooms.css`
settles controls, encounter media, transcript, reading, grammar, speaking,
recall and feedback spacing, and while following a voice the transcript moves
directly under the spoken line. Implementation guidance is in
`docs/product/ORENA_WEB_EXTENSION_GUIDE.md`.

This preserves every D-051 rule, all destinations and the navigation sheet,
44px touch targets, theme and language behaviour, and every experience's
content; no learning information is removed to gain space. It changes no
product domain, capability or persistence.

**Supersedes / Superseded by:** Extends D-051. Replaces the narrow header's
fixed two-row height as the only narrow state (an implementation, not a
recorded decision).

## D-053 — A phone scale: type a step smaller, targets sized to the phone

**Status:** Accepted by explicit human instruction, 2026-09-13.

**Decision:** On a phone (up to 600px) Orena uses its own scale rather than
the desktop's carried over. Type steps down one size and stays readable - body
15px, nothing the learner reads below 12px, the line being learned the largest
text in its frame. The larger spaces tighten. Controls stay tappable at 36px
(`--tap`), quiet inline controls at 32px (`--tap-quiet`), and an inline target
such as a word in a spoken line is at least 24px (WCAG 2.5.8) by its height and
the space around it, never widened to a thumb. A checkbox or radio is sized to
the text beside it and its label is the target. Recorded in rule 12 of the
Design Contract.

**Reason:** The human reported that Listening and Dictation on a phone kept the
desktop's checkbox, element and font sizes, so content did not fit and a spoken
line wrapped into four to six lines that were hard to follow, and asked for
roughly half the size while staying readable and interactive, across every
phone screen. Measured at 390px: each word of "look at the words" was a 44px
target, so the longest line of a lesson took 308px in eleven rows; checkboxes
were 44px tall; the body was 16px with 1.7 line height.

**Consequences:** The phone tokens (`--text-*`, larger `--space-*`, `--tap`,
`--tap-quiet`) are set once in `foundation.css`; the global control height reads
`--tap`, which stays 44px above 600px. The phone block at the end of `rooms.css`
sets each room to the scale, and the narrow header's brand row follows it. The
destination control keeps its 46px target. Desktop and tablet are unchanged.

This supersedes the "full touch target (44px)" clause of D-052 on phones only;
every other D-052 and D-051 rule stands, and no learning information is removed.
It changes no product domain, capability or persistence.

**Supersedes / Superseded by:** Amends D-052 (phone touch-target size).

## D-054 — Permanent account deletion, and a delegated technical workflow

**Status:** Accepted by explicit human instruction, 2026-09-13.

**Decision (product policy):** Deleting an account is permanent. A deleted
account and its data are never restored to the learner - not through support,
not through a database restore, not through signing in again with the same
external identity. Registering again creates a completely new account
incarnation that inherits nothing from the deleted one. How long backups and
logs physically persist is a separate operational/legal retention policy; it
does not change what a learner can recover (nothing) and does not block I2.

**Decision (workflow):** Technical review is not a human question. Schema and
migration proposals (starting with I3's `20260911_0006` and `20260912_0007`)
go to an independent technical reviewer under `AGENTS.md` "Architecture review
authority"; the implementing agent resolves the findings itself and reports
the outcome (APPROVED / CHANGES REQUESTED) to the human. Once this deletion
policy is in the contracts and the technical review is clean, the agent may
apply independently approved additive migrations to the **sandbox** and set
`ORENA_ACCOUNT_BACKBONE=on` there to test integration, following the existing
runbook safety gates, without asking again. I4/I5/I6 continue in dependency
order without asking about implementation details.

**Still the human's:** a genuinely new product policy (plans, prices, quota or
entitlement values, retention durations, achievement or pedagogical policy);
an irreversible architecture decision; anything touching production (8000) or
preview (8010), credentials, providers or billing.

**Consequences:** `ORENA_ACCOUNT_DATA_ARCHITECTURE.md` §§1, 5 state the
policy: the deletion barrier is permanent for that incarnation, restore must
reapply every deletion recorded after the backup before serving, and
re-registration is a new incarnation. `I2_ACTIVATION_RUNBOOK.md` §1 records the
restore-suppression and barrier inputs as answered and the retention inputs as
decoupled (purge stays disabled until they exist; nothing deleted is ever
served). `ARCHITECTURE_INVARIANTS.md` human gates name the sandbox delegation.
Production gates are unchanged.

**Supersedes / Superseded by:** Answers the I2 activation policy inputs
"restore suppression" and "deletion barrier retention"; narrows the runtime
activation and schema gates to production/preview for work inside this lane.

## D-055 — D-054's re-registration holds only behind two preconditions

**Status:** Accepted as the technical resolution of the independent review of
D-054 (round 1, CHANGES REQUESTED), 2026-09-13. No product policy changes.

**Decision:** D-054 says re-registration is a new incarnation that inherits
nothing. The review found that owner tables (essays, saved words, ...) are keyed
by account, not incarnation, so a new incarnation would read the deleted one's
rows until the account-deletion workflow removes them, and that a point-in-time
deletion journal can miss deletions made after its last copy. Therefore no
runtime path may delete or re-register an account until (a) each deletion is
appended to an out-of-database journal as it happens and (b) the owner-table
deletion workflow exists and is replayed after a restore - both independently
reviewed. A test enforces the gate. Restore suppression now also puts back the
barrier row of an account restored without its incarnation, and
`runtime_backup.py suppress --check` is the verify step before serving.

**Consequences:** `ORENA_ACCOUNT_DATA_ARCHITECTURE.md` §§1, 5,
`ORENA_BACKBONE_INTEGRATION_GATES.md` (hard gate), `I2_ACTIVATION_RUNBOOK.md`
§2. I2 sandbox activation is unaffected: turning the flag on neither deletes
nor re-registers.

**Supersedes / Superseded by:** Qualifies D-054's "inherits nothing" wording;
the product policy (deletion is permanent, nothing is restored) is unchanged.

## D-056 — Shared Reading Library initial rollout ships without a per-text rights gate

**Status:** Accepted, explicit current human instruction (2026-09-16), scoped
and time-bounded as described below - not a repeal of the general principle.

**Decision:** The admin-facing EPUB import pipeline and its shared catalog
(`reading_books`/`reading_book_chapters`, `writing_coach/reading_library_api.py`,
`static/orena/ui/library.js`) ship for their initial rollout with no rights
investigation, no rights-approval workflow, no publishing-permission queue and
no legal-verification subsystem: a book becomes visible to every learner the
moment its import succeeds. The human explicitly instructed this scope
reduction in-session, after being told it contradicts the written architecture
hold, and accepted the consequence that content imported through this path
carries no recorded rights basis.

This is a narrow, named carve-out for this one pipeline, not a change to the
general rule. It does **not** touch, weaken or supersede:

- `admittedReading()` in `static/orena/content/reading-library.js`, the
  existing hand-curated catalog's own rights gate (creator/license/
  evidence_url/verified_on/edition/changes) - unchanged, a fully separate code
  path that never calls or is called by the new pipeline;
- D-039's rights-gated publication model for the Listening domain;
- the general principle in `AGENTS.md` §"Architecture holds" ("Reading
  library breadth ... is a rights decision per text, not an implementation
  task") for any *other* Reading content path.

**Reason:** The human's own stated goal for this round was to prove a working
admin-import → shared-library → learner-read vertical slice end to end;
building a rights-review/approval subsystem first was explicitly out of scope
for that goal. The tradeoff (no recorded rights basis for imported EPUBs) was
named to the human before this decision, not discovered afterward.

**Consequences:** `docs/project/CURRENT_PRODUCT_STATE.yaml`'s `current_p1`
records this carve-out alongside the pre-existing, unchanged
`reading_library_breadth_requires_rights_decisions_per_text` entry.
`CURRENT_HANDOFF.md`'s own "Reading breadth: rights gate" bullet is
deliberately left unchanged: the file sits at `scripts/validate_project_
memory.py`'s hard 8000-byte cap with no room for a net addition, and this
entry plus the product-state array are the authoritative record instead -
`PROJECT_MEMORY.md`'s own precedence chain reads `CURRENT_PRODUCT_STATE`
before `CURRENT_HANDOFF`, so a bounded restore sees the accurate entry first.
The old hand-curated catalog's own rights gate is untouched and the general
hold remains live for any future Reading content path this decision does not
name. Any later decision to add rights review to this specific pipeline, or
to publish its content more broadly (e.g. outside this sandbox), is a new,
separate decision - this entry authorizes the initial rollout only, not a
permanent policy that imported books never need rights review.

**Supersedes / Superseded by:** None. A narrow, named exception alongside the
general principle, not a change to it.

## D-057 — Clarity first, a simple front door, and artwork as a system

**Status:** Accepted, explicit current human instruction (2026-09-17), after a
screen-by-screen design audit of the current web build.

**Decision:** Orena is reaffirmed as a content-rich language-learning product
with a beginner-safe front door and depth that reveals itself over time. Four
sentences govern the direction:

> **Clarity first. Curiosity next. Depth over time.**
> **Simple front door. Deep world behind it.**
> **Less words, more life.**
> **Artwork is a system, not decoration.**

The durable principles this decision accepts:

- "World" is an internal product and design principle. It is never
  learner-facing lore, fantasy, a traveller metaphor, or a concept a learner
  must understand before learning a language.
- A learner who has never used a language-learning app must always have one
  obvious next action; a returning learner an obvious way to continue.
- Guided path and Explore both exist, as two entry modes into the same content
  and learning system, and neither obscures the other.
- Skill labels are valid navigation vocabulary. A skill-module dashboard is not
  the primary product architecture. Clear labels are never traded for poetic
  wording that reduces comprehension.
- Library stores the world; Discover reveals it; the learning tools help the
  learner interact with it. One content object supports several learning
  actions rather than being duplicated per skill.
- Show first, say only what is needed. A full opening is permitted but is not a
  default page template, and the sequence eyebrow + giant headline + slogan +
  paragraph + mascot is not repeated across surfaces.
- All production artwork belongs to one Art Bible, owned by
  `assets/brand/orena/`. Content imagery, covers, thumbnails, icons, colour and
  motion carry more of the product's life than slogans do.
- Content artwork may be vivid; interface colour keeps its single owner in
  `static/orena/theme.css` and its accessibility obligations.
- Focused learning modes reduce shell noise and keep the learning tools within
  reach.
- English and Chinese remain first-class, unchanged.

Explicit non-goals: no fantasy or lore redesign; no removal of Reading,
Listening, Speaking, Writing, Vocabulary or Library as labels; no
redesign-by-decoration; no arbitrary palette; no generic SaaS dashboard; no
product philosophy explained to the learner; no placeholder artwork in a
reviewed build.

**Reason:** The audit found many individually good pieces — branding, palette,
typography, rails, an intention-centred Practice, the Daily Feed — assembled on
a conventional module architecture, with poetic copy carrying weight that
composition and artwork should carry, an inconsistent visual system, and a
repeated hero template. Separately, the "world" framing risked producing a
product a beginner has to decode. This decision restores the intended direction
while making beginner clarity the first constraint on it.

**Consequences:** Recorded in
`docs/product/ORENA_PRODUCT_CONSTITUTION.md` (§2 ranking, §5 skill labels and
interface language, §10 beginner-safe front door and guided path plus Explore,
§11 what "world" is not),
`docs/product/ORENA_CONTENT_ARCHITECTURE.md` (§1 Library/Discover/tools, §13 one
content object and several learning actions),
`docs/project/DESIGN_CONTRACT.md` (rules 13-18, the art-direction owner, the
beginner clarity and art acceptance gates, and a derived agent checklist),
`assets/brand/orena/README.md` (Art Bible authority, governed scope, recorded
gaps),
`AGENTS.md` (the mandatory-read routing for learner-facing work) and
`docs/project/REVIEW_POLICY.md` (both gates as completion evidence).
`docs/project/CURRENT_PRODUCT_STATE.yaml` records that the shipped UI does not
yet conform. No UI, code, palette or backend contract changed with this entry;
conforming the product is subsequent, separately scoped work.

**Supersedes / Superseded by:** Amends D-051 rule 5 in
`docs/project/DESIGN_CONTRACT.md`: a full opening with approved artwork remains
permitted on entry, discovery and empty states, but is no longer a default page
template. Supersedes nothing else. It does not change D-046 or its tombstones,
D-049/D-050's five domains and horizontal Understanding Engine, D-051's
remaining rules, D-052/D-053's phone rules, or any multilingual invariant.

## D-059 — The Orena Design System becomes the interface's visual source of truth

**Status:** Accepted, explicit current human instruction (2026-09-19). The
human approved the Orena Design System prototype (claude.ai design project
`7a5604ca-1e11-4d8e-8305-7d0cb32d552d`: Design Overview, Screens parts 1-6,
Visual Grammar, Checklist Status) and chose, when asked, each of the four
points below. Numbered D-059 because D-058 is held by the Admin lane's
unmerged control-centre decision.

**Decision:** The existing Orena frontend migrates onto the approved design
system. It is a UI migration over the existing backend, API, authentication,
routes, data model and learner state - not a rewrite, and not a second app.

1. **Interface palette.** Violet is the interface's action colour - action,
   navigation, selection - and lamp amber is its progress colour - progress,
   completion, anything earned. Grounds are cool ink greys on hue 300. Six
   domain hues (Reading 295, Listening 235, Speaking 170, Dictation 110,
   Writing 55, Vocabulary 350) sit at equal weight and appear in small doses
   only. Orena Orange `#FF7A3D` remains the mascot's and the artwork's colour
   and no longer carries an interface role.
2. **Themes.** One identity in two appearances: **Ink** (dark, default
   identity) and **Paper** (light), built from one mapping rather than two
   designs. The registry mechanism - identity separate from appearance, one
   block in `theme.css`, one entry in `theme.js` - is unchanged. Night Ink,
   Deep Forest and Sage Field are retired; a stored choice of any of them is
   read as the theme with the same appearance, so no learner wakes up to a
   different brightness. The reader keeps its sepia option as a reader-only
   block beside the two themes.
3. **Navigation.** Five destinations - Home, Library, Vocabulary, Progress,
   Profile - plus a Practice group. Nothing that exists is removed to fit the
   mockup: Continue lives on Home, Recall and collections in Vocabulary,
   bringing your own content in Library, Grammar/Understanding as a Practice
   entry (it stays horizontal, D-050), Shadowing and Conversation inside
   Listening and Speaking, Admin for admins only. Hash routes keep their
   meaning. The design's later additions (search, saved content, history,
   quizzes, details, practice indexes) join the migration backlog.
4. **Mark and mascot.** The approved mark and mascot in `assets/brand/orena/`
   stay. The design's violet square and the owl logo exploration are not
   adopted; a new logo would be its own decision.

Typography follows the human's instruction over the prototype's: Manrope for
the interface (700 headings, 600 labels, 400-500 body; no capitals or wide
tracking in learner UI, no monospace), Noto Sans SC for Han characters, the
serif for stories (Design Contract rule 18).

**Reason:** The approved system gives Orena one coherent visual language -
content-first, artwork as the brightest object, hierarchy readable at a glance -
where the shipped UI had accumulated four themes, a hero template and uneven
components. The token layer already routes almost every colour through
`theme.css`, so the change can land in the foundation first and reach every
room without per-page CSS.

**Consequences:** `static/orena/theme.css` holds the new foundation and a
semantic layer (surface, text, border, action, progress, status, domain,
elevation) with the earlier names kept as aliases; `static/orena/theme.js`
registers Ink and Paper and maps retired ids; `foundation.css` holds the
non-colour tokens (type, radius, motion, layers) and the restyled primitives.
`scripts/test_orena_foundation.mjs` now asserts violet and amber as canonical,
Orena Orange as the artwork colour, violet-never-progress, and AA for the new
semantic pairs in every theme block. `AGENTS.md` (Theme) and
`docs/project/DESIGN_CONTRACT.md` (Orena Design System section) carry the
rules. No backend, API, schema, route or learner-state contract changes.

**Supersedes / Superseded by:** Supersedes the interface-palette clauses of the
Theme invariant in `AGENTS.md` (Orena Orange as canonical interface brand
colour, themes derived only from `assets/brand/` palettes, the four named
themes) and the registry that implemented them. Does not supersede D-057: its
Art Bible authority, artwork licence, one colour owner, acceptance gates and
"no placeholder artwork in a reviewed build" all stand - the prototype's
dot-field placeholders are not adopted; covers use the Art Bible's designed
cover system until real artwork exists.

## D-060 — The approved mockup is the visual source of truth; backend gaps are tracked, not hidden

**Status:** Accepted, explicit current human instruction (2026-09-19), given
after the Phase 1-3 checkpoint of D-059.

**Decision:** The production frontend reproduces the approved Orena Design
System mockup as exactly as it can - layout, dimensions, spacing, alignment,
typography, proportions, radius, borders, shadow and glow, colour, hierarchy,
navigation, icons and responsive behaviour. Integration does not redesign or
"improve" the mockup; where the implementation differs, the implementation
changes.

1. **Backend gaps do not become UI gaps.** When the mockup draws a component
   whose data or behaviour the backend does not provide, the component keeps
   its approved place and shape and shows the design system's honest
   unavailable state. It is never removed, hidden or replaced, and it never
   shows invented data. Each such gap is recorded in
   `docs/project/UI_BACKEND_GAPS.md` (status `NOT_STARTED` until work starts).
2. **Artwork.** Where no real image exists, content uses the design system's
   artwork slot - dark ground, domain-hued bloom, dot field, at the card's own
   ratio - and real artwork replaces it with no layout change. The earlier Art
   Bible motif covers are retired as a fallback; missing artwork is a tracked
   gap (GAP-012), not a reason to return to the old style.
3. **Navigation.** The rail is exactly the approved one (four destinations,
   Practice, five rooms, the learner's card) and each destination carries the
   approved top bar. Capabilities the mockup does not draw keep a named home
   one step away rather than a place in the rail: Continue on Home, Recall
   behind the due chip and in Vocabulary, Grammar in the Practice map,
   bringing content in Library, Admin for admins only.
4. **Legacy.** Compatibility aliases in `theme.css` exist only so rooms not yet
   migrated keep rendering; a migrated surface reads only the semantic tokens,
   and no legacy composition survives under new colours on a migrated screen.

Two earlier explicit choices stand and are recorded as deliberate differences
from the mockup, not drift: the interface typeface is Manrope, with no
monospace, capitals or wide tracking in learner UI (the human's D-059 brief),
and the mark is the approved Orena mark, not the mockup's violet square (the
human's D-059 answer). Either can be reopened by the human.

**Reason:** A migration that trims the approved design to what today's
backend happens to supply drifts the product toward the backend's shape, and
the approved design stops being the thing that is built. Tracking the gaps
keeps both honest: the interface stays the approved one and the missing data
stays visible as work.

**Consequences:** `docs/project/UI_BACKEND_GAPS.md` is created as the backlog.
`docs/project/DESIGN_CONTRACT.md` rules 37 and 38 are amended and rule 40 is
added. `ui/cover.js` draws the artwork slot. The Phase 1-3 surfaces were
re-audited against the mockup; the parity result is recorded in
`docs/project/DESIGN_SYSTEM_MIGRATION.md`.

**Supersedes / Superseded by:** Amends D-059 §3 (the rail no longer carries
Continue, Recall or Grammar) and D-057's placeholder clause for covers in
favour of the design system's defined artwork slot. D-057's Art Bible
authority for mascot, scenes and real artwork is unchanged.

## D-061 — The mockup's typography replaces Manrope

**Status:** Accepted, explicit current human instruction (2026-09-19), answering
the question D-060 left open.

**Decision:** The interface takes the approved mockup's three faces: Nunito 800
for display and headline figures, Nunito Sans for interface and reading copy,
DM Mono for data (level, timing, score, state) and for the small uppercase
labels the mockup draws (section labels, domain labels, stat names), at the
mockup's sizes and tracking. The D-059 brief's "Manrope, no monospace, no
capitals" is superseded. DM Mono has no Vietnamese glyphs, so a Vietnamese
interface sets the same mono role in Roboto Mono; Han characters keep Noto Sans
SC. The mark stays the approved Orena mark for now - the human will revisit
the logo separately.

**Reason:** D-060 makes the mockup the visual source of truth; typography was
the last recorded difference the human had authorised, and the human chose
the mockup.

**Consequences:** `foundation.css` type tokens (`--display-font`, `--font`,
`--mono-font`, `--weight-heavy`, `.ds-label`, `.ds-data`); the migrated shell,
Home and Progress components; Design Contract rule 34. The mockup's 9.5-10.5px
labels sit below D-053's 12px phone floor; D-060 makes the mockup decide, so
the labels follow it, and D-053's floor still governs reading content.

**Supersedes / Superseded by:** Supersedes the typography clause of D-059 and
the typography difference recorded in D-060.

## D-062 — One library, one book page, and a reader whose word panel is the dictionary

**Status:** Accepted, under D-059 Phase 5 and D-060 (2026-09-20).

**Decision:** Reading is the approved library scoped to what can be read. The
Reading room renders `ui/library-browse.js` with `only: ['books']` - the same
search, facets, sections and cards as `#/content` - so there is one library
implementation, not two. The retired cover grid, its shelves and its inline
book-detail state are removed with the surface they served. A book card leads
to `#/book`, rebuilt to Screens part 4 section 16: cover, chips, progress and
one action above the fold; chapters below with a single highlighted next row,
an unread-only filter and show-all; description, the words this book taught and
recommendations in the side column. The reader follows part 1 section 04: a
compact bar (back, place, progress rail, reading layers, type size) over a
split pane, with the word panel docked beside the text on a desk and anchored
as a sheet on a phone. A tapped word answers itself - reading, meaning, save -
because that is the dictionary; the selection toolbar remains for a dragged
phrase, where the learner may have meant any of its tools.

**Reason:** D-060 makes the mockup decide, and the mockup draws one library and
one book page. Keeping the legacy grid beside the approved one would have left
two libraries with different cards, and a second book detail to maintain.

**Consequences:** `ui/library.js` is the book page only (`librarySection`,
`paintBookPage`, `wordsFromBook`); `ui/world.js` no longer paints a reading
grid; `ui/library-browse.js` takes `only`; `ui/reader.js` and `ui/lexical.js`
carry the split pane, the docked panel and tap-to-answer;
`scripts/test_orena_shared_reading_library.mjs` follows. Two deviations are
recorded in `DESIGN_SYSTEM_MIGRATION.md`: a chapter row shows its real word
count where the mockup draws minutes (GAP-029), and the phone keeps the book's
primary action inline because Orena's phone shell owns the bottom bar. Missing
backend capability is GAP-028 to GAP-036, all `NOT_STARTED`.

The check and the end of a chapter (Screens part 3 section 13) land in the same
phase. The check is one question at a time and stays optional - it opens from an
invitation after the text, never before it. Because the API scores a whole set,
the answers are collected first and the same rail then walks back through them
with the real results: no per-question verdict is invented on the client. The
answer panel names the paragraph its evidence came from when the text contains
it, and says "from the text" when it does not. The end of a chapter reports what
was finished, the words kept since it opened, and the one way on; the quiz and
time figures keep their tiles with a dash (GAP-031, GAP-030).

**Supersedes / Superseded by:** Extends D-059 and D-060 into Phase 5; retires
the D-057 reading-room cover grid and its shelves, and the `<details>` form the
comprehension check used to be.

## D-063 — Reading's approved scope is wider than the Phase 5 migration, and is not books-only

**Status:** Accepted, explicit current human instruction (2026-09-20), given at
the Phase 5 checkpoint of D-059.

**Decision:** Phase 5 is the **Reading UI and reader migration**, complete with
its functional backend gaps tracked. It does not make Reading feature complete,
and no document may say it does. The approved Reading capability remains wider
than Book -> Reader -> dictionary -> multiple-choice check, and every capability
in it stays recorded with an honest state: translation and contextual
explanation, pronunciation and audio, Chinese Pinyin, durable highlight of a
word, sentence or paragraph, saving vocabulary from the reader, grammar notes
and pattern explanation, contextual learner notes, bookmarks, the exact resume
position inside a chapter, open-answer comprehension, review of saved
highlights and notes, and review/SRS linkage. What is unsupported is
`NOT_STARTED` in `UI_BACKEND_GAPS.md` (GAP-028 to GAP-045), never absent.

**Reading content is not books-only.** Reading covers books, articles, stories,
news, essays, dialogues and the learner's own imported reading. The Reading
room being the approved library scoped to what can be read (D-062) is an
implementation of that scope, not a narrowing of it: every readable thing is
already in it and reachable. What is missing is a content kind and metadata per
type, so each can be named, filtered and counted as what it is (GAP-044).

**Reason:** the migrated screens are the visible part of Reading, and an
approved capability that no current screen happens to draw must not quietly
leave the product definition. A tracker that reads "Reading: Integrated" would
have done exactly that.

**Consequences:** `DESIGN_SYSTEM_MIGRATION.md` carries the Reading scope table
and its matrix row reads "UI migrated; Reading not feature complete";
`UI_BACKEND_GAPS.md` gains GAP-037 to GAP-045; `CURRENT_HANDOFF.md` says the
same in one line. The Phase 5 implementation itself is kept as it is.

**Supersedes / Superseded by:** Qualifies D-062 and the Phase 5 entry of D-059;
supersedes nothing.

## D-064 — Vocabulary takes the approved home, collection, card and review session

**Status:** Accepted, under D-059 Phase 6 and D-060 (2026-09-20).

**Decision:** The Vocabulary surfaces follow the approved design. The room opens
on the home panel of Screens part 4 section 18 - domain tile, what was kept and
mastered, what is due, the learner's collections, and the way to everything
saved - rather than the retired dashboard of metric tiles, recent rows, library
and feed columns. A collection follows part 1 section 05: its artwork, chips,
progress and one way in, then a compact two-column overview of its words with
the design's single "not mastered" filter; the dense list with search, level,
status and sort remains, one tap behind "show all". The flashcard is a card -
260x340, the amber rim of an earned mark, the word and its reading, then the
meaning, the sentence it came from and the two answers the scheduler accepts.
The review session shows what is due, how far through it the learner is, the
word, and the approved four-grade panel.

**Reason:** D-060 makes the mockup decide. The previous Vocabulary room was a
dashboard about the collection; the approved home is a place to decide from.

**Consequences:** `ui/expression.js` (home, collection detail, review session),
`ui/vocabulary-experience.js` (the card and `masteryStarRow`), `world.css`,
`rooms.css`, `reference.js` copy, and the gates
`test_orena_vocabulary_experience.mjs`, `test_orena_vocabulary_theme_tokens.mjs`,
`test_orena_language_and_recall.mjs` and `test_orena_reference.mjs`, which
pinned the retired composition. The legacy `.recall-moment` skin is removed.
Honest states, all tracked: a tier reads as a dash (GAP-020); Hard and Easy keep
their place and say they are not available yet (GAP-019); no interval is printed
beside a grade; the review-time estimate is GAP-046 and a card's position in its
collection GAP-047. The card is 260x340 rather than 232x306, at the same
proportions, because the mockup's width is sized for two Han characters.

**Supersedes / Superseded by:** Extends D-059 and D-060 into Phase 6; retires
the Vocabulary dashboard composition and the recall card skin that preceded it.

## D-065 — The 2026-09-20 design update: cards without borders, and learning surfaces recalibrated

**Status:** Accepted, explicit current human instruction (2026-09-20), pointing
at three updated documents in the approved design project: "Orena Card
Component", "Orena Recalibration" and "Orena Device Overview" (with "Orena
Design Overview" unchanged in its foundations).

**Decision:** Three changes are adopted, and they supersede the earlier Screens
parts wherever they disagree.

1. **A card has no border.** It is four layers: a translucent ground, an inner
   highlight that reads as a lit edge, a wide soft shadow, and - on ink - an
   optional violet bloom. Contrast comes from ground and shadow, never from a
   line. Hover lifts; selection is a ring of light. `theme.css` owns the
   tokens (`--card-surface`, `--card-edge`, `--card-shadow`, `--card-glow`,
   `--card-ring`), and one block in `rooms.css` names the surfaces that take
   them.
2. **A learning surface opens with a sentence, not a label**, at 29px over two
   lines, and carries one colour rising from the floor of the screen. Skill
   hues leave the learning surfaces entirely - they stay in the library and in
   navigation, which is where a learner is choosing rather than working.
3. **A score becomes a sentence.** Speaking drops the number, the four
   dimension bars and the per-word score chips; what comes back names the words
   that still wobble, from the assessment's own data, and says nothing when
   there is no assessment (GAP-021). This is also what Orena's evidence rules
   already required.

**Reason:** the human updated the approved design and instructed that the
update be applied to what is built and to Phase 8. D-060 makes the approved
mockup the visual source of truth; a newer approved document outranks an older
one.

**Consequences:** `theme.css`, `rooms.css` (the card block, Speaking, the
dictation field), `ui/voice-response.js`, `ui/speaking.js`,
`ui/pronunciation-report.js`, `ui/encounter.js`, copy packs, and
`test_orena_voice_interaction.mjs`. New gaps from the updated documents:
GAP-048 (rank and XP), GAP-049 (activity heatmap), GAP-050 (plans and
payment), GAP-051 (the per-character reading row in Dictation).

**Not yet applied, and recorded so it is not lost:** the 280px rail with the
five destinations plus Profile and per-domain level chips, Home's recalibrated
hero and rails, the reader's 440px word panel and 300px chapter list, the
listening transcript at 620px, Dictation's single play control and
per-character reveal, and the Progress rank panel. These are the next phases,
in the order `DESIGN_SYSTEM_MIGRATION.md` records.

**Supersedes / Superseded by:** Supersedes the bordered-card treatment of
D-059/D-060 across every surface, and the scorecard form of the speaking
report. Extends D-060's authority to the updated documents.
