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
playable EN *and* ZH evidence plus human playback acceptance, and that
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

## D-044 - L3 content ingestion is not blocked by an external provider quota

**Date:** 2026-09-03

**Status:** Accepted (human decision)

**Decision:** The remaining L2.5 evidence - one real cold Supadata acceptance on
fixture `iSTlFeW-Z9M` - is an EXTERNAL PROVIDER ACCEPTANCE GATE, not a
precondition for L3 content ingestion. L3 may execute while it is outstanding.
L2.5 is NOT marked complete: its acceptance stands as
`OVERALL_L2_5_ACCEPTANCE = PARTIAL / EXTERNAL_GATE_PENDING`, with
implementation, automated regression and real warm end-to-end all PASS and
`REAL_COLD_PROVIDER_ACCEPTANCE = PENDING_EXTERNAL_QUOTA`. That debt survives
L3 and must still be run when quota resets.

**Reason:** The earlier sequencing rule - L2.5 must fully pass before L3 - was
written when the missing evidence could plausibly have indicated a code defect.
It no longer can: the cold path was measured returning `provider_starting` with
a resume handle in 1.36s, the async orchestration and the atomic provider poll
are contract-tested, and warm generated-transcript end-to-end is proven on real
media. The only unproven step is the provider finishing a job, and the only
blocker is a purchased quota that has run out. Holding all content work behind
someone else's billing cycle would stall the product for a reason unrelated to
Orena's correctness.

**Consequences:** L3 runs with Supadata generation switched off across the pack.
A playable source without captions is classified `RECOVERY_REQUIRED` - valid
media awaiting transcript recovery - and never `unsupported` or
`MEDIA_UNAVAILABLE`. No paid transcript generation is spent on bulk import.
Project memory keeps `L2_5_REAL_COLD_ACCEPTANCE=PENDING_EXTERNAL_PROVIDER_QUOTA`
as an open item even if L3 completes and the next task advances to L4.

**Supersedes / Superseded by:** Supersedes the sequencing rule that L2.5 had to
pass completely before L3 began. Supersedes no product, rights or persistence
contract, and does not weaken any production guard.

## D-045 - Listening content is short-form dialogue, not long informational video

**Date:** 2026-09-03

**Status:** Accepted (human product decision)

**Decision:** The Listening library's primary material is short memorable
dialogue: movie and animation scene excerpts, quotes in real spoken context,
short stories and situational comedy, natural conversational speech. Most
lessons run 15-60 seconds, up to ~90 when a scene needs the context. Long
informational video is no longer primary material and is used only where it
contains clearly excerptable sections. The 100 EN / 100 ZH development pack is
retired as the primary source strategy; the first pilot families are Kung Fu
Panda scene clips from licensed distributors (EN) and the DaihuaXiyou 呆話西遊
channel (ZH).

**Reason:** The old pack was too long, too informational and too boring for the
product this is meant to be. The learner should think "I want to watch this",
not "I am opening a textbook video". Excerpt length should follow the natural
dialogue unit - setup, response, conclusion - rather than a fixed duration.

**Consequences:** Pilot source packs
`listening_sources_en_pilot_dialogue.csv` (11 rows) and
`listening_sources_zh_pilot_daihuaxiyou.csv` (6 rows) encode the new policy at
15-90 seconds and at most two excerpts per source. Every row's channel identity
was verified through provider oEmbed rather than assumed, and reupload channels
were excluded rather than used to pad the count. Rights truth is unchanged:
everything stays DEV_CANDIDATE / rights_review / proposed / reviewed_level null,
because availability on YouTube is not publication permission.

A structural consequence found while verifying: short-form animation channels
commonly disable captions entirely. All 7 DaihuaXiyou videos checked have
captions disabled, so this content direction depends on generated transcript
recovery - a paid provider - far more than the old informational pack did. That
is a cost and gating consideration for scaling, not a reason to reject the
direction.

**Supersedes / Superseded by:** Supersedes the source strategy behind the
100 EN / 100 ZH development pack as primary Listening material. Supersedes no
rights, persistence or excerpt-timing contract - excerpt boundaries still come
only from real transcript timing.

## D-046 - Curated transcripts are acquired at ingestion, never at learner runtime

**Date:** 2026-09-03

**Status:** Accepted (human product decision)

**Decision:** For curated Listening media, transcript acquisition is an
INGESTION-time operation. The canonical transcript is persisted before a lesson
is READY, and a learner opening that lesson must never cause a call to the
YouTube transcript API, Supadata, or any other transcript provider. Provider
APIs belong to ingestion; the learner runtime reads a PERSISTED CANONICAL
TRANSCRIPT ARTIFACT.

Meaning is deliberately the opposite: transcript is eager and persisted, while
translation stays lazy and cached (editorial → persisted generated → live
service → truthful unavailable). Pinyin is derived deterministically from the
canonical Hanzi and never from an external AI.

**Reason:** A learner should never wait on somebody else's API to read a
sentence Orena already has, and Orena should never pay twice for the same
transcript. It is also a resilience property, proven the hard way this week: the
build host is IP-blocked by YouTube, yet every curated lesson still opens
instantly, because the transcript was acquired once and stored.

**Consequences:** The storage backend today is the existing generated catalog
artifact - the durable rule is "persisted canonical transcript artifact", NOT
"transcripts live in JSON forever". Migration to database or object storage is
expected when artifact size slows checkout/build/CI, when the corpus reaches
many thousands of lessons, or when editorial workflow needs independent
transcript revisions; it must happen behind this same contract.

Transcript provenance travels with the persisted text: origin
(provider_caption / generated_asr / unspecified), revision, language, quality
state (provider_caption / generated_unreviewed / reviewed) and provider/model.
Lessons predating this default to UNSPECIFIED rather than being promoted to
"official captions", and the loader refuses to let generated ASR be labelled as
provider captions.

`tests/test_curated_transcript_contract.py` makes this permanent: it patches
every transcript provider to raise on any call, then opens real EN and ZH
lessons. A refactor that moves acquisition back into the hot path fails there.

My Media is explicitly NOT covered. User imports keep native captions →
recovery → generated ASR, with the async provider_starting / queued /
processing lifecycle. The rule applies to CURATED READY content only, and the
pipeline is not duplicated.

**Supersedes / Superseded by:** Supersedes nothing; it makes explicit an
architecture the code already had but did not guarantee. Extends D-042's
disclosure rule to persisted curated transcripts.

## D-047 - A preview deployment tier, separate from APP_ENV

**Date:** 2026-09-03

**Status:** Accepted (human product decision)

**Decision:** Orena gains an explicit deployment tier, `ORENA_DEPLOYMENT_TIER`,
with values `production` and `preview`. It is distinct from `APP_ENV`:

    APP_ENV                runtime and security posture (HTTPS, Google auth,
                           secure cookies, fail-fast guards)
    ORENA_DEPLOYMENT_TIER  product publication tier: which catalog content this
                           deployment may expose at all

A preview deployment runs `APP_ENV=production` with
`PERSISTENCE_BACKEND=postgresql` on its own database, reached over real HTTPS
with real Google login. It is production-like runtime behaviour with restricted
unreviewed content. It is NOT production publication.

The tier defaults to `production` when unset, and an unrecognised value is
refused at startup rather than coerced.

**Reason:** The previous preview rule (D-043) put unreviewed content on a local
development runtime. That was right for a throwaway check and wrong for using
Orena as a learner: `APP_ENV=development` skips the auth, cookie and persistence
paths that production actually uses, and SQLite cannot exercise the Listening
progress/resume path at all. A preview that does not exercise production
behaviour cannot tell us whether production behaviour works.

**Consequences:** Production tier never loads the preview artifact, so preview
lessons are absent from the process rather than filtered from a response - the
failure mode is closed, not cosmetic. On preview tier, visibility is enforced
server-side in the catalog on both the listing and the single-lesson endpoint,
and requires the existing platform-admin role; authentication alone is not
enough, because preview content is unreviewed with unresolved rights.

Preview content keeps DEV_CANDIDATE / proposed / rights_review /
reviewed_level null, and uses the same lesson model, canonical segments,
Dictation, Shadowing, Meaning, Pinyin and progress model as everything else.
Only visibility differs.

`compose.preview.yaml` is a separate Compose project with its own volumes,
database, loopback port and tunnel token, so preview runs beside production
without stopping it and shares no production data. Deployment, DNS, Cloudflare
and Google OAuth changes remain human gates.

**Supersedes / Superseded by:** EXTENDS **D-043**, which stays correct for local
development QA of generated content. D-043's rule that unreviewed content must
never reach the production deployment is unchanged and is now enforced by the
tier rather than only by APP_ENV. Supersedes no rights, persistence or
publication contract: preview visibility is a deployment concern, not a
publication decision.

## D-048 - One local Orena runtime; preview is per-user, not per-deployment

**Date:** 2026-09-03

**Status:** Accepted (human operational decision)

**Decision:** This machine runs ONE long-lived Orena runtime: the existing
Compose stack on `127.0.0.1:8000`, with one PostgreSQL and one Cloudflare
tunnel, reached over real HTTPS with real Google login. Preview content is an
authorization capability of that runtime, enabled with
`ORENA_DEPLOYMENT_TIER=preview` in the existing environment. There is no second
Orena container, PostgreSQL, image, port, tunnel or Compose project, and no
feature-specific database volumes.

The preview marker is scoped to the USER, not the deployment: it appears only
for a caller who may actually see preview content. Normal learners see the
ordinary product with no marker, on the same runtime, at the same time.

Daily development is `docker compose restart writing-coach` — source is
bind-mounted, so Python, JS, CSS and catalog changes need no rebuild. Rebuild
only when the image changes (Dockerfile, requirements, system packages). Docker
keeps one CURRENT image and one ROLLBACK image; QA, feature, milestone and test
images are not retained.

**Reason:** A second stack duplicated the parts that carry real risk -
persistence and identity - to gain nothing the tier did not already provide.
Preview visibility is a question about WHO is asking, and that is already
answered inside one process. Duplicating databases per feature is how learner
data gets stranded in a volume nobody remembers, and the previous plan would
also have taught a bad default: spin up infrastructure to look at content.

The deployment-wide badge was the same mistake in miniature. On a shared runtime
it would have told every ordinary learner they were using a preview, which is
false for them.

**Consequences:** `compose.preview.yaml` remains as an optional ISOLATED STAGING
pattern for something that genuinely must not share persistence, and its header
says it is not the normal workflow. Port 18080 and `orena-preview-*` volumes are
not part of ordinary development; none were ever created.

Port 8000 is the current developer/dogfood convention, NOT permanent product
architecture.

The tier contract, its server-side enforcement and its security tests from
**D-047** are unchanged and still required.

**Supersedes / Superseded by:** SUPERSEDES the deployment topology of **D-047**
(a separate preview stack with its own database and port). D-047's tier
contract, fail-closed production behaviour and admin-only visibility remain in
force. Extends **D-043**; no history rewritten.

## D-049 - Learner progress is lesson-scoped; Continue Learning is real progress

**Date:** 2026-09-03

**Status:** Accepted

**Decision:** Durable Listening/Dictation and Shadowing progress is identified by
`(user, language, lesson, segment)`. `asset_id` remains on the row as
provenance and keeps its index, but no longer defines progress identity.
Continue Learning is generated server-side from that persisted PostgreSQL
progress, not from catalog metadata, client storage or any recommendation
heuristic.

**Reason:** Shared media identity and learner progress identity are different
things. One source carries several curated excerpts, so keying progress by the
media asset meant finishing one excerpt made its siblings look started, and two
excerpts sharing a segment id shared a row. Continue Learning, meanwhile, was
declared in the discovery order and never populated: the first rail a returning
learner sees was always empty.

**Consequences:** Migration `20260903_0005` adds `lesson_id` and re-keys both
tables. Backfill associates a legacy row with a lesson ONLY where its asset maps
to exactly one lesson; assets with none or several stay `lesson_id = ""`,
legacy/unassigned. Picking the first or newest lesson would manufacture a
certainty the data does not contain and attach real work to the wrong excerpt,
so ambiguous history is preserved rather than resolved.

The server validates every progress write: the lesson must exist, belong to the
stated asset, match the learning language and contain the segment. A client
lesson_id is never trusted on its own. An omitted lesson_id is a legacy path
that resolves only when the asset is unambiguous; it can be removed once no
client omits it.

Continue Learning obeys the same visibility boundary as discovery, enforced
server-side, so preview content cannot reappear through a learner's own
progress. A segment that no longer exists resumes at the lesson start rather
than seeking to something gone.

Listening MODE is still not persisted; resuming restores the lesson and segment
only. That is recorded as a follow-up rather than claimed.

**Supersedes / Superseded by:** Supersedes the asset-scoped progress identity
introduced with durable Listening progress. Supersedes no persistence,
publication or visibility contract.

## D-050 - Orena discovery is world-first; Web launches first with adaptive composition

**Date:** 2026-09-03

**Status:** Accepted (human product/design decision)

**Decision:** Orena's learner-facing discovery model is world-first:

```text
Language → World → Zone → Journey → Lesson → Activity
```

Listening, Speaking, Reading, Writing, Grammar, Vocabulary/Dictionary and Review
remain connected learning mechanisms, but Home/Explore do not have to present
them as a flat primary feature menu. Home owns motivation, discovery and real
continuation; detailed learning analytics live on a separate Progress surface.

Orena launches on responsive Web first. The Web product is the design and
product-meaning source of truth, but cross-platform parity follows **shared
meaning, adaptive composition** rather than pixel-identical layout. Desktop may
show more useful content simultaneously; tablet/mobile may progressively reveal
the same product meaning with different columns, rails, stacking, chrome and
gesture patterns.

The initial UI-system proof is the Golden Web slice Home → World → Listening
Journey. This establishes the Orena product UI kit and responsive grammar; it
does not by itself change existing public-release gates for skills.

**Reason:** Previous AI-generated UI repeatedly converged on sterile,
same-weight SaaS/dashboard patterns and made mobile a separate redesign effort.
The new system must create emotional pull before disciplined learning, while
remaining production-realistic and reusable across Web and later native
clients.

**Consequences:** `docs/ORENA_PRODUCT_DNA.md`,
`docs/ORENA_DESIGN_TOKENS.json`, `docs/ORENA_COMPONENT_CONTRACT.md`,
`docs/ORENA_RESPONSIVE_COMPOSITION.md`, and relevant Golden Specs govern
migrated learner UI. Agents compose approved product components/recipes instead
of redesigning from a blank canvas. Golden screens are reviewed at 1440, 1024
and 390 widths. Home analytics blocks are prohibited; journey-specific progress
cues remain allowed. Native preserves product semantics, feature access, state
and visual DNA but need not preserve desktop simultaneous visibility.

**Supersedes / Superseded by:** Clarifies and extends D-040 and the Design
Contract by replacing any pixel-identical/same-simultaneous-layout
interpretation with adaptive composition. It does not supersede D-004/D-005
public-release gates.

## D-051 - Home is built from Orena product components, and a World must have content

**Date:** 2026-09-03

**Status:** Accepted (implements D-050 and the H1 brief)

**Decision:** Migrated Orena learner screens are composed from a shared product
component layer rather than page-local markup. The first layer ships as
`static/becoming/orena/product-components.js` and its `.css`, opted into per
screen with `data-orena-ui="v2"` so a migrated screen cannot restyle a screen
that has not migrated yet. Home is the first migrated surface: its body is
JourneyHero → Continue → Explore Worlds → For You Today → Challenge → Continue
Exploring, and the Writing dashboard, latest-score panel, learning-memory cards,
streak block and recent-drafts list are no longer Home's.

Worlds become a versioned semantic source: `orena_worlds.v1.json` declares the
editorial world set per learning language, `world_catalog.py` computes each
world's availability, lesson count and lead lesson from the real curated
catalog, and `GET /api/worlds` returns that. A world with no real lesson is
defined but reports `available: false` and is not offered to a learner.
Membership is by canonical lesson topic, never by content tag.

Home shows no completion percentage. The D-049 resume contract carries a lesson
and a segment, not a ratio, so the continuation card states where the learner
was rather than how far along they are.

**Reason:** The previous Home was a Writing dashboard: same-weight analytics
panels organised around evidence rather than around wanting to start something.
Rebuilding it as page-local markup would have produced a second one-off visual
system, which the Component Contract exists to prevent. Worlds needed a source
of truth because the tempting failure is a discovery surface that looks full -
six confident cards per language claiming lessons that were never ingested.

**Consequences:** The catalog is small, so today EN exposes 3 of 6 defined
worlds and ZH 3 of 6; the rest appear when content does. Learning analytics
remain available and unchanged at their own surfaces - Journey still reads
`/api/dashboard` and `/api/learning-memory`, and no backend data or persistence
was removed. Stable Home handoffs are preserved inside the new components:
Library due review, personalized Writing practice, the Grammar handoff from the
latest outcome with its evidence and parent-essay lineage, the review cue, the
listening goal, and the cross-skill cue. Home tests that asserted the dashboard
were retired with their reason recorded rather than deleted silently. There is
no Explore route yet, so a World card opens its lead lesson through the existing
lesson autostart handoff; a real World route arrives with the shell migration.
Artwork containers, ratios and crop rules are real, but the artwork itself is a
textless development placeholder - H2 owns production artwork and visual Golden.

**Supersedes / Superseded by:** Implements D-050 for Home. Does not supersede
D-049; it consumes that contract. Does not change any public-release gate.

## D-052 - Orena product components carry no raw-markup escape hatch; the practice-outcome contract is backend-authoritative

**Date:** 2026-09-03

**Status:** Accepted (audit correction to D-051's H1 implementation)

**Decision:** Two standing rules for the Orena product component layer,
established while fixing the H1 audit findings.

First, a product component never accepts page-authored HTML. `bodyHtml` and
`secondaryActions` existed in the first H1 cut of
`static/becoming/orena/product-components.js` and are removed permanently.
Supporting text, a quoted sentence, or a secondary action is a semantic prop
(`quote`/`quoteLang`, `note`, `links`) that the component itself renders and
escapes. A caller that can inject markup will eventually inject page-specific
markup, at which point the "component" is a template and a native port has to
reimplement whatever the page happened to put in it.

Second, any UI surface that renders a backend-derived status enum must treat
that backend function as authoritative, not reinvent the enum from memory or
convenience. `derive_practice_outcome()` in `writing_coach/becoming_outcomes.py`
emits exactly seven statuses (`improved`, `transferred`, `held`,
`still_working`, `needs_attention`, `not_observed`, `needs_more_evidence`); a
frontend contract for that field must recognise exactly those seven, with
regression coverage per status.

**Reason:** The H1 implementation of Home invented four practice-outcome
statuses no backend has ever produced and silently excluded six of the seven
real ones, so a learner whose revision came back `still_working` or
`needs_attention` lost the Grammar practice handoff - the exact evidence,
grammar id and parent-essay lineage - without any visible error. Separately,
`bodyHtml`/`secondaryActions` had already let one screen's markup start
leaking into the "component" layer the Component Contract exists to keep
generic.

**Consequences:** `recommendationTile`, `challengeCard` and every other Orena
product component reject raw HTML through any prop name - the H1.1 regression
test in `test_orena_home_h1.mjs` checks this behaviourally, not by grepping for
one prop name. Any future screen that surfaces a backend enum states which
backend function is authoritative and lists every value that function can
return, the way this entry does for practice outcomes.

**Supersedes / Superseded by:** Corrects the H1 implementation of D-051; does
not change D-051's decision itself (Home's composition, the world-catalog
contract, or the removal of Home analytics).

## D-053 - Home obeys the screen-lifecycle contract, and a Listening continuation has exactly one source

**Date:** 2026-09-03

**Status:** Accepted (audit correction to D-051/D-052's Home implementation)

**Decision:** Four standing rules, established while fixing the H1.2 audit
findings.

First, Home's progressive render obeys the same `root._cleanupScreen` contract
every other screen already uses (write.js, speaking.js, reading.js,
profile.js): `renderHome` registers a disposal flag as soon as it starts, and
every later repaint checks it before touching `root.innerHTML`. A
`settle()`-then-`paint()` that resolves after the learner has navigated away
is a no-op, not a rewrite of whatever screen is now on the page.

Second, `renderHome`'s returned promise is bounded. A request that never
settles at all - not merely a slow one - cannot hold the app-level render
lifecycle (`aria-busy`, the rail refresh, focus) open indefinitely. A
section-settle budget races the real requests; a request still outstanding
past the budget keeps running and still repaints if it answers, subject to the
disposal guard above, but the render lifecycle itself moves on.

Third, a Listening continuation has exactly one owner. D-049's server-side
Continue Learning already outranks a local per-device resume for the Hero
card; H1.2 closes the gap where Next Practice could independently reach for
the same, or a different, local resume and render a second, competing "resume
listening" affordance. Next Practice only considers a local resume when
nothing - server or local - has already claimed Listening as the
continuation.

Fourth, a section's "nothing to show" state distinguishes a genuine empty
answer from a real provider outage, and a composed label's UI-language and
content-language halves are tracked separately rather than forced into one
string. For You only claims "loading" while a provider that could still
supply content has not answered, only claims a genuine empty state once every
relevant provider has truthfully answered with nothing, and only claims
"unavailable" once at least one of them has failed outright. Personal's six
independent sub-requests keep their per-call resilience - one missing signal
must not cost the others - while a *total* failure across all six is now
distinguishable from a fresh learner's true absence of evidence. Separately, a
World's lead label ("Start with {title}") no longer forces its
interface-language prefix and its content-language lesson title into one
shared `lang`.

**Reason:** Home repaints itself progressively through independent,
asynchronously-settling request groups (D-052). Without a lifecycle guard, a
request that resolves after the learner has navigated to Write or Listen would
silently overwrite that screen with a stale Home render, and a request that
never resolves at all - `api.js` sets no client-side fetch timeout - would
leave `aria-busy="true"` on the page forever. Separately, the same per-device
local resume that legitimately becomes Home's own continuation card when no
server progress exists was also, independently, being offered a second time
through Next Practice: a real product bug where a learner could see two
different "resume listening" affordances for two different lessons at once.
And a personal-provider outage was rendering identically to a genuine
new-learner empty state, erasing exactly the signal an operator needs to tell
"nothing to see yet" from "something is broken".

**Consequences:** `static/becoming/screens/home.js` registers
`root._cleanupScreen` at the top of `renderHome` and guards `paint()` with it;
`renderHome` accepts an internal section-settle budget (default 6s) the render
lifecycle cannot exceed. `nextPracticePlan`'s local-resume branch is excluded
whenever the continuation already resolves to `listening` or
`listening-local`. The `personal` request group uses `Promise.allSettled` over
six independently-wrapped calls instead of per-call `optional()`, and rejects
only when every one of them failed. `worldCard` takes
`leadPrefix`/`leadTitle`/`leadSuffix`/`leadLang` instead of one pre-formatted
`leadLabel` string. Regression coverage lives in `test_orena_home_h1.mjs`
(blocks 15-19).

**Supersedes / Superseded by:** Corrects the H1/H1.1 implementation of
D-051/D-052; does not change either decision's own scope (Home's composition,
the product-component contract, or the practice-outcome status set).

## D-054 - Home's screen-lifecycle guard covers shared state, not only the DOM

**Date:** 2026-09-04

**Status:** Accepted (audit correction to D-053's Home lifecycle guard)

**Decision:** `root._cleanupScreen`'s disposal signal is authoritative for
every effect a progressive Home request can still have after it fires, not
only for `paint()`. A request that resolves after cleanup must not write into
`state.dashboard`, `state.memory`, `state.practiceRecommendation` or
`state.latestPracticeOutcome` - these are shared learner state, not local to
one render, and a late write reaches whatever screen or learning language is
current when the promise settles, not the one it was requested for. The check
runs at the moment of mutation, not at request time, and is joined by an
independent check on the learning language the render started with: a result
must not apply if that language is no longer current, even in a hypothetical
path that changes it without a full screen cleanup. Separately,
`root._cleanupScreen` now resolves a disposal promise that joins the same
`Promise.race` as the section-settle budget, so cleanup unblocks a render's
outstanding lifecycle immediately rather than leaving it to expire against
the budget after another screen has already started.

**Reason:** D-053 gave Home a screen-lifecycle guard, but only for the DOM:
`paint()` checked disposal, and nothing else did. A request already in flight
when the learner navigates away still resolves afterward, and its mutations
of shared state landed regardless - so a stale personal recommendation, a
stale learning-memory payload, or a stale dashboard snapshot could silently
overwrite what a *different* screen, or the learner's *new* learning
language, should have seen. Racing disposal into the section-budget wait
closes a smaller but related gap: without it, a render that has already been
cleaned up would still hold the app-level render lifecycle open for whatever
budget remained.

**Consequences:** `renderHome` snapshots `renderLanguage` and exposes a
`stale()` check; the `chrome` and `personal` request groups evaluate it
immediately before their respective `state.*` writes and skip the write when
stale. `root._cleanupScreen` resolves a `disposal` promise included in the
existing `Promise.race([settled, budget, disposal])`. Regression coverage
lives in `test_orena_home_h1.mjs` (blocks 20-22).

**Supersedes / Superseded by:** Corrects the H1.2 implementation of D-053;
does not change D-053's own scope (the disposal contract and bounded
provider budget both stand, just applied more completely).
