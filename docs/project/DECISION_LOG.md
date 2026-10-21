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
  task") for any _other_ Reading content path.

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

## D-058 — Platform Admin becomes an operator control center

**Status:** Accepted, explicit current human instruction (2026-09-18). Built in
the parallel lane `admin/control-center`; REVIEWABLE, not merged, awaiting
human review.

**Decision:** `#/admin` is the Platform Admin control center: six sections -
Overview, AI & Models, Users, Content, Imports, Operations - built as
admin-only modules under `static/orena/admin/` behind the existing admin guard,
with one read-mostly router, `/api/admin/console`
(`writing_coach/admin_console_api.py`). It composes contracts that already
exist rather than adding new ones: the capability registry and AI control plane
(routes, provider credentials through the existing encrypted store, provider
and route tests), the readiness summary, product activity, the reading-library
importer and archive, the media source importer, and the vocabulary importer
with its admission-checked publication. The old `static/admin.js` shell is not
restored.

The human named the authorized admin use cases for account data
(`ORENA_ACCOUNT_DATA_ARCHITECTURE.md` §1): an account list whose identity is
masked, and an account detail limited to operational metadata (joined, last
sign-in, languages, activity counts by domain). Both reads write an audit
record and refuse to answer when it cannot be written. Learner writing,
private text, conversations and saved content are never read for the console.

Bounds set by the same instruction:

- no billing, revenue or subscription figures - no billing contract exists,
  and a registration is not a subscription;
- a retention rate only above a minimum cohort, otherwise "insufficient data";
- no account actions and no content delete, unpublish or metadata edit, since
  no contract implements them; the only actions are the existing ones - archive
  a book, publish a vocabulary collection after an attested admission, read a
  URL media source again;
- learner AI runtime activation (`AI_RUNTIME_MODE`) stays a human-gated
  deployment change: the console reports it and never switches it;
- secrets are write-only through the existing encrypted store; without its key
  the console says so and stores nothing;
- every book and media import attempt, failures included and with the stage
  that failed, is recorded as an `admin.import` row in the existing
  `audit_logs` table - no new table, no migration.

**Reason:** The page was readiness evidence above stacked importers. Operators
needed one place to see platform state and act on it, without new persistence
and without a second provider architecture.

**Consequences:** `docs/product/ORENA_STATUS.md`'s operator note describes the
console. `CURRENT_PRODUCT_STATE.yaml`'s `platform_admin_host_remains_a_human_hold`
and the Platform Admin line in `AGENTS.md` "Architecture holds" predate both
`04a56c4` and this entry; a parallel lane does not rewrite shared memory, so
closing them is left to the human review of this lane.

**Supersedes / Superseded by:** None.

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

## D-066 — The Canonical UI Baseline (Dark Glass) is the learner-facing visual source of truth, and the backend adapts to it

**Status:** Accepted, explicit current human instruction (2026-09-21), answering
the question the Phase 1-3 audit left open (does the frozen baseline replace
D-059/D-065?). The human's answer is yes.

**Decision:** The Canonical UI Baseline in the approved design project
`7a5604ca-1e11-4d8e-8305-7d0cb32d552d` - `Orena UI Baseline.dc.html`, the eight
canonical screen files (Home Discover, Reading, Quick Sheet, Listening,
Speaking, Writing, Vocabulary, Progress) and the `ui-baseline/` foundations,
templates, components, states, responsive rules and 17 data contracts - is the
highest source of truth for every learner-facing surface. A pinned copy lives
in `docs/design/canonical-ui/` so the authority is in the repository and not
in a design tool.

1. **One visual system: Dark Glass.** Ground `#050310` with the cosmic field,
   flat glass with a single ring, the violet accent gradient, semantic ink for
   text and icons only, Nunito / Nunito Sans / DM Mono / Noto Serif, Phosphor
   icons. There is no second approved colour or type system. D-059 and D-065 are
   no longer the visual authority. Patterns the baseline lists as LEGACY (the
   Device Overview, Design Overview, Screens parts 2-9, Card Component,
   Recalibration, Visual Direction and Visual Grammar documents) are superseded.
   There is no hybrid: a surface is either the baseline or awaiting migration,
   and nothing new is built on the old look.
2. **Paper is retired** from the active learner interface, and is not developed
   in parallel. So is the reader's sepia block, because the baseline draws no
   light reading surface. When migration finishes and nothing depends on them,
   the obsolete theme registry entries, tokens, CSS and components are deleted;
   Git keeps the history.
3. **The canonical UI decides, the backend adapts.** Screen structure, layout,
   hierarchy, interaction, states, responsive behaviour, the data a screen shows
   and the user flow come from the baseline. Missing data is added to the
   backend; a wrong shape is fixed in the API, serializer, service or contract;
   an insufficient schema is extended under control; a legacy implementation
   that no longer fits is migrated and then retired. No element is removed,
   moved or replaced because the backend cannot supply it.
4. **Metric rule.** A metric the baseline draws that has no measured value
   renders **0** in its canonical place, in the canonical component, so the
   layout is always complete: study time `0 h`, streak `0`, rank `0`, completed
   `0`, attempts `0`, due `0`; charts and heatmaps keep their component in its
   zero state and never generate activity. The 0 is a **presentation fallback,
   not a measurement.** The data layer keeps the truth: a read model says
   whether a metric is measured, `learner-summary/1`'s "unknown is not zero"
   still governs what is stored, computed and sent as evidence, and nothing
   writes a fallback 0 as data. When a metric is measured the real value
   replaces the fallback with no UI change. Demo figures from the design (61 h,
   128 days, rank 4, score 89) never appear in a production build.
5. **Progress** keeps the canonical UI. Study time, streak, completion,
   mastery, review due, the activity heatmap, per-domain progress and rank get
   an official definition and a real measurement before they show a value; time
   is never inferred from how long the app was open.
6. **Pronunciation is real or absent.** The interface reads a normalized
   pronunciation contract (overall, accuracy, fluency, completeness, words,
   phonemes and, where the provider supports them, Chinese tones) behind a
   provider abstraction; Azure Pronunciation Assessment and SpeechSuper are the
   target providers, and the UI never depends on a raw provider response. With
   no attempt the metrics read 0; with no configured provider the screen uses
   the canonical unavailable / error / retry state and never a synthetic
   assessment. This supersedes D-065's removal of the score, which was a
   consequence of there being no real assessment.
7. **Learner audio.** `speaking_attempts` keeps its policy of no durable raw
   audio: record to a temporary buffer, assess, persist the normalized result
   the product needs, discard the audio. Keeping recordings would need its own
   privacy and storage review; pronunciation work does not wait for it.
8. **Two different questions.** A basic lookup (headword, reading, part of
   speech, dictionary meaning) stays deterministic. "Nghĩa ở câu này" is a
   contextual semantic meaning and may use the AI/language capability through
   the provider abstraction, as an explicit contextual request, with no model
   named in the interface.
9. **Vocabulary review has three grades** - Quên, Chưa chắc, Nhớ rồi. Before
   the scheduler changes: map the two-grade state, update the SRS rule, add
   tests, document the behaviour change, and preserve every learner's history;
   nothing stored is silently reinterpreted.
10. **Loading, empty and error** use the baseline's state where it draws one
    and the existing pattern where it does not (the baseline marks them
    incomplete); no new visual is invented in a backend-integration task.
11. **Search** exists wherever the baseline draws it, over the content the
    canonical screens use (books and readable content, listening, vocabulary,
    collections) and nothing else.
12. **Contracts come from the UI.** Each canonical screen's required and
    optional fields, actions, persistence, states, permissions, filters,
    pagination, search and processing state define the API contract. A schema
    field must trace to a canonical requirement or a real business need.
13. **Readiness.** A slice is READY only when it matches the baseline on desktop
    and mobile, runs on real backend data with no production mock, keeps its
    state across a reload, honours auth, has working loading / empty / error /
    retry, returns the metric fallback correctly, passes existing and
    integration tests, and leaves no duplicate active implementation. Rendering
    is not READY.
14. **Accessibility never redesigns the baseline.** A token that fails AA is
    replaced by the smallest technical change that keeps the visual intent, and
    the deviation is documented.
15. **Migration ends in deletion.** After a canonical flow replaces an old one
    and verification passes, the old component, duplicate, dead CSS, obsolete
    token, obsolete service and unused API are removed. Old / New / V2 / Legacy
    never coexist as active implementation.
16. **Process.** This work proceeds directly on `codex/work` in the current
    worktree, with no new branch or worktree, in logical commits, staging only
    the files of each step. The lane rule in `AGENTS.md` section 3 is set aside
    for this task by explicit instruction.

**Not changed:** the Art Bible's authority for the mascot, scenes and real
artwork (D-057); the artwork slot stands until real art exists. The multilingual
invariants; PostgreSQL authority and the persistence rules; the native freeze;
every human gate. Two are restated because the work now reaches them:
a schema or migration for learner-owned data is authored against
`ORENA_ACCOUNT_DATA_ARCHITECTURE.md` and the backbone contracts and needs a
recorded independent architecture review before it is applied to any shared or
sandbox runtime, and production, provider credentials and billing remain human
gates. An implementer does not approve its own high-risk schema change.

**Reason:** D-060 already made the approved mockup the visual authority; the
mockup changed. A frozen baseline that the design project itself marks as the
official source, with data contracts, is a better basis for backend integration
than the earlier prototype set, and keeping two visual systems would leave
every surface half-migrated.

**Consequences:** `docs/design/canonical-ui/` pins the baseline.
`UI_BACKEND_GAPS.md` becomes the single tracker in the form canonical UI -
contract - backend - data source - tests - status, and absorbs the Phase 1-3
audit. `DESIGN_CONTRACT.md` replaces its D-059 section with the baseline;
`AGENTS.md` (Theme) points at it; `LEGACY_TOMBSTONES.md` retires the Ink/Paper
system; `DESIGN_SYSTEM_MIGRATION.md`, the tracker of the retired program, is
removed. `CURRENT_HANDOFF.md` and `CURRENT_PRODUCT_STATE.yaml` record the new
authority. The code still shows Ink and Paper until each surface migrates; that
is the work, not a competing authority.

**Supersedes / Superseded by:** Supersedes D-059 (palette, themes, navigation
composition), D-060's unavailable-state clause for metrics (the metric rule
above governs), D-062, D-063 and D-064 wherever their compositions disagree
with the baseline (D-063's Reading capability scope stands), and D-065 in full.
D-061's typefaces stand: the baseline uses the same set. D-057's artwork
authority stands.

## D-067 — The design is read at its source, the UI rules that pre-date the baseline are void, and "the same" is measured

**Status:** Accepted, explicit current human instruction (2026-09-21), after the
human reviewed the built screens and found that they were not identical to the
design, that old UI and old interactions remained, and that things the design
does not draw had been added.

**Decision:**

1. **The source is the Claude Design project itself.** The design project
   `7a5604ca-1e11-4d8e-8305-7d0cb32d552d` is read live (with `DesignSync`,
   reads only). The pinned copy in `docs/design/canonical-ui/` is a cache, and an
   incomplete one (no `Orena Quick Sheet.dc.html`, no design `CLAUDE.md`, no
   `UI_BASELINE.md`, no `ui-baseline/*.md` rules, no `ui-implementation/`).
   Where the cache and the source differ, the source wins. Before a
   learner-facing task the design project's own rules documents are read, not
   only the screens.
2. **UI rules older than D-066 that conflict with the design are void.** The
   layout, composition and interaction rules of D-046, D-051 and D-057 (rules
   1-8, 10-13, 15, 17-25 of the old Design Contract), the D-057 beginner and art
   gates, D-060's approved-mockup measurements and D-065's compositions no
   longer bind any surface. `DESIGN_CONTRACT.md` is rewritten to keep only what
   is still true; numbers that survive keep their number.
3. **"The same as the design" is measured** (rule 42): computed style against
   the source frame at true scale, deviation by deviation, on desktop and on a
   phone with real touch, and a surface is not `REVIEWABLE` with an unlisted
   deviation.
4. **Nothing is invented** (rule 43) and **old interaction is deleted, not
   restyled** (rule 44). Loading, empty and error are not drawn in the design,
   so no visual or copy is invented for them.
5. **The design's product vocabulary is kept** (rule 45), in the Vietnamese
   interface as the design has it (Home, Library, Vocabulary, Progress,
   Profile, Reading, Listening, Speaking, Writing, Dictation); icons are
   Phosphor 2.1.1 official paths only (rule 46); the rail and tab bar exist
   only on Home, Library, Vocabulary and Progress (rule 47); two frames, no
   invented breakpoint (rule 48).

**Reason:** the earlier rule that "rules 1-29 stand where they do not name a
colour, a theme or a component the baseline replaces" let the old layout rules
outrank the design, and reading the design from a partial local copy hid the
design's own rules. The human's instruction is that the design is the authority
and old UI rules must not obstruct it.

**Consequences:** `DESIGN_CONTRACT.md`, `AGENTS.md` and `CLAUDE.md` are
rewritten accordingly; `LEGACY_TOMBSTONES.md` records the retired rules;
`UI_BACKEND_GAPS.md` lists the measured deviations of every surface built so
far. Code comments that cite retired rules are stale and are removed as the
surface they sit in is migrated.

**Supersedes / Superseded by:** Supersedes the visual and interaction rules of
D-046 (Design Contract part), D-051, D-057 (gates), D-060 and D-065 wherever they
disagree with the design, and the sentence of D-066's Design Contract section
that kept old rules standing. D-066's authority, metric rule, backend-adapts
rule and pronunciation rule stand. D-057's Art Bible authority and D-061's
faces stand.

## D-068 — The design is the standard for how things look, not the content to copy; the open points of the fidelity pass are closed

**Status:** Accepted, explicit current human instruction (2026-09-21), closing
the decisions the Listening fidelity pass left open.

**Decision:**

1. **The design's words and data are sample content.** The canonical design is
   the standard for colour, layout, typography, component style and visual
   pattern. Its literal copy, lessons, numbers and states in the mockups are not
   copied. The interface speaks the learner's language setting (the support
   language): destination, skill and label names are translated, and rule 45 of
   the Design Contract no longer keeps English names in the Vietnamese
   interface. This amends D-067 point 5.
2. **The logo stays as it is** (the Orena tail mark and its wordmark) until the
   human decides otherwise; the frames' violet square is not adopted.
3. **DC-5:** a dictation attempt records `used_hint` (and the hint level reached)
   with the attempt. No effect on the score is inferred until a scoring rule
   exists. It is stored inside the existing evidence record and needs no new
   learner-data schema.
4. **The taxi lesson is removed** from the listening catalogue.
5. **Phone search and library paging** may be implemented as function needs, as
   long as they keep the visual system.
6. **Vietnamese keeps Roboto Mono** (D-061) until a new typography decision.
7. **"Kiểm tra hiểu" reflects real data:** with no questions it is disabled.
8. **The rights block stays under the workspace**, styled with the current
   design system.

**Reason:** the human reviewed the Listening work: the design fixes how the
product looks and behaves, not what its sample text says, and the product
language must follow the learner.

**Consequences:** `DESIGN_CONTRACT.md` rules 26 and 45 and the language section
are rewritten; the learner-language gate no longer exempts any product name;
the Vietnamese pack has Vietnamese names again.

**Supersedes / Superseded by:** Amends D-067 point 5. D-067 otherwise stands.

## D-069 — DC-5 is two additive columns on `listening_progress`; the human authorised the schema change and an independent review approved it

**Status:** Accepted. Amends D-068 point 3.

**Correction:** D-068 point 3 said the used-hint state "needs no new learner-data schema". That was wrong:
storing it is a schema change to learner-owned data (two columns on `listening_progress`). The human's
instruction of 2026-09-21 - "đồng ý lưu trạng thái đã dùng hint; thực hiện architect review và migration cần
thiết cho learner data" - authorises the change with its review and migration.

**Decision:** `last_used_hint` (boolean) and `last_hint_level` (0-3) are stored with the segment's progress row,
describing the last checked attempt like `last_answer`. The flag is exactly "level above zero" (CHECK
constraints, the API and the repository agree). It is a fact about the attempt; no scoring rule is inferred.
Migration `20260921_0010` sits on `20260916_0009` (the sandbox database is at `20260916_0009`), needs no
backfill, and is a metadata change on PostgreSQL 11+. An older client that omits the fields writes "no hint";
that is the same replace-the-aggregate behaviour `last_answer` has. The downgrade drops the facts and is for a
rehearsal, not a live account.

**Review record (AGENTS.md, Architecture review authority):**

- Reviewer role: Delegated Architecture Reviewer
- Reviewer identity: an independent Claude subagent (general-purpose), not the implementer's context
- Reviewed commit: `b881742699c427b8d9ed687fd89f29e406683441`
- Date: 2026-09-21
- First outcome: `CHANGES REQUIRED` - one P1 (the wrong D-068 premise, corrected here) and P2 findings
  (the flag derived from the level, a CHECK on the bound, non-integer input answering 500, the merge
  path overwriting a stored hint after a reveal-only session, a stale comment, the migration's notes).
- Fixes: made in the commit that follows this entry; the reviewer is asked to re-check that commit, and its
  outcome is recorded below before the migration is applied to the sandbox.

**Supersedes / Superseded by:** Amends D-068 point 3.

**Re-review outcome (2026-09-21):** `APPROVED` by the same independent reviewer for commit
`670ec798d156fddf3d1e17a6d3f2084af0a08e62` - no P0 or P1; remaining P2 items were a sturdier test for "this
session checked an attempt" (taken: the merge now keys on the checked-attempt count), a note that the CHECK
constraints validate existing rows under a brief lock (acceptable: the table is small and every row holds the
defaults), and commit scope (that commit also carried the Chinese Quick Sheet sizing). The migration is applied
to the sandbox database only, after this record.

## D-070 — A screen's ground is #060509 with the room's glows, not the cosmic field

**Status:** Accepted, explicit current human instruction (2026-09-22: the background still did not follow the new design).

**Decision:** Every frame of the design draws `#060509` with one violet glow at the top left and one glow per room
at the bottom right (reading violet, listening blue, speaking teal, writing amber, vocabulary pink, progress and
home blue). The twelve-layer cosmic field in `tokens.json` is the design's canvas around its frames, not a
screen's ground. The app paints the screen's ground: `theme.css` (`--screen-canvas`, `--screen-glow`,
`--room-glow-*`), `foundation.css` (body, `html[data-room]`), `app.js` (sets `data-room`). The cosmic field
stays declared because the foundation gate pins `tokens.json`, and paints nothing.

**Supersedes / Superseded by:** Corrects the reading of "one Dark Glass field under every screen" in D-066.

## D-071 — A screen's ground is the UI Baseline's, a lit indigo, not #060509

**Status:** Accepted, explicit current human instruction (2026-09-22: "the background is not the same because it
is too dark; the one in the UI Baseline is much brighter").

**Decision:** The app's ground is the body of `Orena UI Baseline.dc.html` at its source: `#0A0722` under seventeen
layers - violet and blue nebulae, four fields of stars, and a 170-degree wash from `#120C33` to `#0A0722` - fixed to
the viewport. It is one ground for every room; there are no per-room glows. `theme.css` owns it
(`--ground-color`, `--ground`, `--ground-size`), `foundation.css` paints it on `body`, `theme-color` is `#0A0722`.
The individual screen frames still draw `#060509` with a room glow: that is a conflict inside the design, and the
human has chosen the baseline. `tokens.json` keeps its older cosmic field declared (the foundation gate pins it);
it paints nothing.

**Supersedes / Superseded by:** Supersedes D-070 (its `--screen-*` and `--room-glow-*` tokens and `data-room` are
removed).

## D-072 — Three answers from the human: saved reviews, discussion over a text, the rail's learner card

**Status:** Accepted, explicit current human instruction (2026-09-22), answering the five points reported
after the Writing, Home and Reading slices.

**Decision:**

1. **"Lưu nhận xét" means keeping the review with the learner's graded work.** A review saved in the Writing
   room belongs to the skill-assessment record of that piece - the evaluation the server already stores -
   so the learner can read it again where their graded work lives, not as a second copy somewhere else.
   Building it must not make a new persistence decision for learner data (AGENTS.md, architecture holds):
   if it needs schema, it needs independent architecture review first, as DC-5 did (D-069).
2. **A discussion over a whole text is wanted** ("Thảo luận" in the Reading frame's bar). Today only the
   per-selection understanding surface exists. The thread is learner-owned data, so the same hold applies.
3. **The rail carries the learner's card and per-skill levels**, as the AppShell frames draw. The card is
   built (2026-09-22); the level beside each skill renders only from a profile field nothing serves yet, and
   is never the one declared level repeated four times.

**Supersedes / Superseded by:** Answers the open points left by D-067's fidelity work; does not change D-068.

---

## D-073 — The ground is the master preview's, and the cache had gone stale

**Date:** 2026-09-22
**Status:** Accepted

**Context.** The human reported that the interface was being built against an
out-of-date design, and they were right. `docs/design/canonical-ui/` was pinned
on 2026-09-21; since then three files had moved at the source. Two of them are
the ones this lane had been reading all day:

| File                        | Pinned |                       Source |
| --------------------------- | -----: | ---------------------------: |
| `Orena-Progress.dc.html`    | 78 947 | 101 462 (+22 515 - reworked) |
| `Orena-UI-Baseline.dc.html` | 91 651 |          90 759 (the ground) |
| `Orena-Listening.dc.html`   | 95 578 |                       95 302 |

Measuring Progress against the pinned copy is why its composition kept coming
out wrong, and reading the ground from the pinned master preview is why the
interface lost the light the human kept asking for.

**Decision.** The app's ground is the body of `Orena UI Baseline.dc.html` at its
source, which is now `#0B0A0F` under two magenta radials - `rgba(168,84,190,0.32)`
at 62% -6% and `rgba(196,104,196,0.20)` at 92% 2% - over
`linear-gradient(180deg, #17101F 0%, #0D0A12 44%, #0A090D 100%)`, fixed.
`theme.css` owns it as `--ground-color`, `--ground` and `--ground-size`;
`foundation.css` paints it on `html` so the canvas carries it across the whole
viewport rather than the body's clipped box. There is no separate page halo:
this ground carries its own light from the top.

Star dust is left out at the human's instruction - the dots read as crude. That
is their call, recorded here, not a reading of the design.

**Three sources in the design disagree about the ground, and only one is
current.** The eight screen files' own `body` is the design document's page, the
canvas their frames sit on, and was never the app's ground. `Orena Glass
System.dc.html` §02 states the earlier system (`#050408`, a three-direction
field, a 280-420px halo). The master preview is the product. Read the master
preview and nothing else for this one value.

**Consequence.** `PINS.tsv` is recomputed from disk on every re-pin so the record
cannot drift from the files beside it, and `SYNC_2026-09-22b.md` holds the
detail. A pinned cache is evidence of a moment, not of the present: before
measuring a surface, check the pin against the source.

**Supersedes / Superseded by:** Supersedes D-071's ground (`#0A0722` under
seventeen layers), which was true of the master preview on 2026-09-21. D-070 was
already superseded by D-071 and stays so.

## D-074 — Two libraries, one kept-item relation, and how a saved word knows which entry it is

**Date:** 2026-09-23. **Decided by:** the human, on three separate answers
(2026-09-23), with the schema shaped by this lane and approved by independent
architecture review round 1 before any of it was applied.

**1. What the two libraries are.** **Vocabulary is the shared content library** —
the catalogue a learner takes words from. **Thư viện của tôi is the learner's
personal library** — what they kept and what their learning produced. The data
contract prefers a reference to the source content plus the learner's own state
and metadata over copying content. This settles the question
`UI_BACKEND_GAPS.md` had been holding open about where a learner's own words
live: in My Library, not in the Vocabulary room, and the Vocabulary frames no
longer draw them.

**2. The kept-item relation.** `library_items` is the Collection Architecture's
`ContentMembership`: a relationship, never a copy — no body, no title, no
snippet. It holds no review schedule; words stay scheduled in `saved_words`,
and `pinned_at` is what the merged queue orders by. Collections are per kind,
enforced by composite `(id, kind)` references rather than by application
discipline. Schema `20260923_0013`, applied to **dev and sandbox only** on the
human's authorization of 2026-09-23; production is not authorized.

**3. A saved word records which entry, and which reading.** `saved_words` gains
`entry_id`, `entry_identity_key` and `reading_key`, because a join on
normalised text cannot say whether a saved 行 is xíng or háng, and per-word
pronunciation audio has to be keyed to a reading. Where the entry is ambiguous
and the caller does not know the reading, **nothing is linked** — an unlinked
word is as useful as it was before, a wrongly linked one would key the wrong
audio to it for as long as the row exists. No portable constraint can read a
JSON list of readings, so that half is held by
`becoming_library.save_library_vocabulary` with `tests/test_entry_identity.py`
behind it.

**4. Catalogue import merges; it does not replace.** Looking an entry up by
`identity_key` and merging in place is the import contract. A replacing import,
if it is ever wanted, is a separate declared import mode and its own decision —
never a silent change to this one. This answers the question architecture
review round 1 raised and could not resolve, and it is why
`entry_identity_key` is kept for the reason that holds (it is the identity
audio will be keyed by) rather than as protection against UUID churn that does
not happen.

**Out of this lane:** Admin Control Center and Speaking, both assigned
elsewhere by the human on 2026-09-23.

**Supersedes / Superseded by:** nothing. Extends D-066/D-067's design authority
into the data contract behind it.

## D-081 — codex/work was merged into admin/control-center as a one-way synchronization

**Date:** 2026-09-23
**Status:** Accepted

**Context.** `AGENTS.md` §3 keeps the two lanes intentionally independent and
forbids taking learner-facing implementation from the other lane "unless the
human explicitly instructs it". On 2026-09-23 the human merged `codex/work`
into `admin/control-center` themselves (merge commit `61e9668`, preceded by
their own `52c7246` "checkpoint learner UI before admin integration"), and the
Reading Content Engine work continued on top of it. The delta reviewer raised
that the instruction behind the merge was not recorded anywhere, and that the
rebase of the engine's migration onto the merged chain is downstream of it.

**Decision.** The merge is recorded here as a deliberate, human-performed
**synchronization in one direction only**: the admin lane takes the learner
lane's current state so that admin work is built against what learners
actually have. The lane's migration chain was rebased onto the merged head
(`20260922_0012`) rather than joined with an Alembic merge revision, so
`migrations/versions/` keeps one linear chain.

**What this decision does not authorize.** It is not authorization for the
reverse merge. `admin/control-center` is still not merged into `codex/work` or
`main` *(as of 2026-09-27; overtaken by PR #63, which merged it into
`codex/work` at `9c0fe31` - see D-085 and D-099)*, and nothing here changes `AGENTS.md` §3's rule that the two
implementations stay independent: a future sync in either direction is its own
human instruction, recorded on its own.

**Consequence.** Work in this lane may now assume the learner UI that arrived
with the merge. Two node gates that came with it — `test_orena_vocabulary_theme_tokens`
and `test_orena_writing_workspace` — fail identically at the merge commit and
were not introduced by admin work; they belong to whoever owns that UI.

**Supersedes / Superseded by:** None.

## D-082 — Reading has one canonical flow and one canonical evidence model

**Date:** 2026-09-24
**Status:** Accepted (explicit human direction, 2026-09-24)

**Context.** The Adaptive Reading schema proposal, approved by independent
review at `0d6efda`, extended `reading_attempts` with a `generated_session`
subject so that the AI-generated passage flow and the corpus flow would share
one attempts table. That kept the legacy shape as a formal, long-lived contract.

**Decision.** Reading has one flow: Admin imports content -> reviews it ->
publishes it to the Reading Corpus -> a comprehension set is generated and an
Admin reviews it -> the learner attempts it -> the attempt is persisted ->
ability/progression is updated -> the next passage is chosen. Specifically:

- No internal AI writes a source passage. AI only processes existing content:
  level, vocabulary, grammar, questions, explanations, evidence.
- Imports keeps five groups: Reading, Books, Media, Vocabulary, Sources. An
  Admin may register an internet source; automatic fetching from an approved
  source creates candidates only and never publishes.
- Ingestion method, source kind and content kind stay separate concepts;
  source category is deferred while it is not needed.
- Lifecycles are reversible and normal flow never hard-deletes. Books restore.
  Vocabulary is `pending_review -> published <-> unpublished -> archived ->
restore to unpublished`. Rights and completeness are warnings; an Admin may
  override, and the override is audited.
- Adaptive Reading uses only the published Reading Corpus. A comprehension set
  carries question type, answer, explanation and evidence grounded in the exact
  version of the passage, and passes Admin review before a learner meets it.
- A Reading attempt is one canonical evidence model; no parallel evidence
  store. Submit is idempotent: a retry creates no second attempt and moves
  ability once. Learner evidence never cascades away when content is edited,
  archived or deleted.
- Reading ability is a projection rebuildable from attempts, with a policy
  version and checkpoint, deterministic and testable. The next article is
  chosen by ability, recent performance and skill weakness - not purely at
  random.
- Cross-skill cue, Collection, Learner Summary, Admin Activity and Analytics
  move to the canonical Reading evidence before new learner submits are enabled.
- The AI-generated passage flow retires and is removed once the migration path
  is done. Legacy data that is only sandbox/test is reset or reseeded; real
  learner history is migrated or archived read-only. The legacy shape decides
  nothing in the new architecture.
- Text Discussion on a corpus article stays deferred, to its own proposal.

**Process.** The schema proposal is rewritten for this model, written as real
proposed DDL, independently reviewed, and taken to the human gate before any
sandbox apply. **The approval of the earlier schema (`0d6efda`) does not carry
to the new one.** The milestone is READY only after a live end-to-end run:
import -> review -> publish -> learner attempt -> attempt persisted -> ability
updated -> next passage chosen adaptively -> data still there after reload;
a retry does not duplicate; editing an article does not silently falsify old
evidence; the runtime works after being recreated.

**Supersedes / Superseded by:** Supersedes the `generated_session` design of
`ADAPTIVE_READING_SCHEMA_PROPOSAL.md` at `0d6efda` and its review approval.

## D-083 — Canonical Reading cutover authorized for the admin sandbox only

**Date:** 2026-09-24
**Status:** Accepted (explicit human authorization, 2026-09-24)

**Context.** The Admin-lane canonical Reading schema (`20260924_0014`, now
`20260924_0016` in this integration, D-082) passed
independent architecture review at `fdf198f` (round C1, confirmed). Its §11
recorded a deliberate departure from `ORENA_ACCOUNT_DATA_ARCHITECTURE.md` §6
steps 2 and 5 and the I2 additive-schema gate, for the human to confirm.

**Decision.**

- Apply the Admin-lane `20260924_0014` to the **admin sandbox only**, including the
  deliberate **non-additive cutover** from the legacy Reading tables to the
  canonical model. The exception is intentional: the generated-reading
  architecture is being retired, not preserved as a permanent compatibility
  model. Production (8000) and preview (8010) keep every gate they had.
- Apply after a backup, deploy the matching code in the same cutover, and run
  the PostgreSQL upgrade/downgrade rehearsal and the lock-order proof.
- The three concepts are: `job_type` = ingestion action; `source_type` =
  source acquisition / feed mechanism; `content_kind` = learner-facing content
  type. Editorial source category stays deferred. `source_type` is never
  described as a publisher/news/blog category.
- **Legacy Reading data is not deleted yet.** The archive inventory query runs
  first and its result is reported. Test/dev-only data may then be reset;
  meaningful learner history stays read-only.
- **No legacy "earlier practice" in Learner Summary** for now. Legacy history
  does not affect the canonical ability/progression model.
- Proceed with removing the AI passage generator, moving every Reading consumer
  to canonical evidence, adding the Reading rights-warning audit, and the live
  end-to-end run. **Learner submit stays disabled until the complete E2E passes.**

**Supersedes / Superseded by:** Confirms the deviation recorded in the
proposal's §11 for the admin sandbox only; it authorizes nothing beyond it.

The integration revision `20260924_0016` has a different parent and needs
independent architecture review before any shared-runtime application.

## D-084 — Speaking: "passed" is the provider's own flag; a Speaking library of its own plus a flow from Listening

**Date:** 2026-09-23. **Source:** the human, answering four questions in the
`feature/speaking` session before any code was written.

**Context.** The Speaking workspace frame draws "5 / 7 ĐẠT", a "Đạt" under
each word and an amber bar for a weak one, and no threshold for any of them
had been approved. The Speaking library was blocked on content (SP-1), and the
free-response room was a D-065 composition.

**Decision.**

1. A reference word is **not passed** when the pronunciation provider flags it
   with its own miscue verdict (Azure `ErrorType` other than `None`:
   Mispronunciation, Omission, ...). `passedCount` counts the reference words
   it did not flag. Orena sets no numeric threshold; the provider's scores are
   shown as numbers. The amber bar, the headline and the marks in the line
   follow the same flag and nothing else.
2. Speaking has **a library of its own** (an authored Speaking catalogue) **and
   a flow from Listening** (published lessons offering the shadowing mode, the
   clip as the model). Only real items are listed.
3. The review sandbox for this lane is a separate container on **8013** with
   its own throwaway database; 8000, 8010, 8011 and 8012 are other lanes'.
4. Free talk is **rebuilt on its frame after** the pronunciation flow, keeping
   the existing recognition and coaching.

**Not decided here** (recorded as S1-S13 in `UI_BACKEND_GAPS.md`): a fluency
threshold, tone assessment and its provider, durable recordings, the way back
from practising one word, a "previous line" control, phrases for free talk.

**Consequences.** `capabilities/pronunciation-result.js` is the only reader of
the assessment; `toneActual` stays empty until a provider measures pitch; an
unset `PRONUNCIATION_PROVIDER` no longer serves synthetic scores.

## D-075 — Speaking: the new Claude Design Speaking UI is the learner flow; Azure proven before review

**Date:** 2026-09-23. **Source:** the human, updating the Speaking decision now numbered D-084 in the `feature/speaking` session.

**Decision.**

1. The Speaking design in the Claude Design project, read at its source (DesignSync), is the
   Speaking learner flow and replaces the current one. The backend and provider already built are
   wired into it; no second Speaking flow runs beside it.
2. Azure Pronunciation Assessment is run end to end for real before review, using the repository's
   existing credential convention (not a `.env` assumed inside a worktree).
3. No SpeechSuper yet: Azure's real Mandarin gap is measured first
   (`docs/operations/SPEAKING_AZURE_E2E_2026-09-23.md`), then decided.
4. No fluency threshold.
5. The word verdict is the provider's; a weak phoneme is shown in the word's detail and never
   overrides the word's verdict.
6. Practising one word alone has a way back to the current line.
7. No "previous line" unless the design or product asks for it.
8. The Speaking catalogue is not seeded with invented content.
9. Free talk keeps its capability; its presentation follows the new Speaking UI.
10. Speaking is reported READY FOR HUMAN REVIEW only when the source was read, the main UI updated,
    Azure run end to end, and desktop and phone checked in EN, VI and ZH. No merge, no push.

**Supersedes:** the open questions S5 (fluency threshold: none), S6 (weak phoneme: detail only), S8
(previous line: not added) and the "no Azure yet" state of D-084.

## D-076 — The new Speaking frames: what their notes decide and what they do not

**Date:** 2026-09-23. **Source:** the human, answering four questions after the Speaking design was
read at its source (`docs/design/canonical-ui/SYNC_2026-09-23.md`).

**Decision.**

1. **A line to practise again** is a line with at least one word the provider flagged. The frames'
   "under 80" (lesson summary, attempts) is not adopted; "practise again" lists lines with flags.
2. **Audio.** By default a recording lives only for the session and is gone after it. An optional
   local retention, "Keep recent recordings", keeps at most five recordings per line on the learner's
   device. Nothing is saved to the server or the library in this phase; a server library comes only
   after a schema and a privacy/retention review, and is opt-in, never on by default.
3. **Free talk is scored only on real measurements.** Pronunciation and fluency come from the
   provider if its free-talk mode supports them. Grammar and vocabulary get no new AI scoring now;
   they follow the metric rule until an evaluator is approved. No overall score (the frames' 30/70)
   while a component it needs is missing. "Last time" is shown only against an earlier attempt
   scored under the same contract. The correction cards and the line to say again may come from the
   existing coaching: that is feedback, not a score.
4. **In this slice:** the measured tone contour (pitch from the audio itself, drawn, with no written
   verdict) and the shadowing mode. **Deferred:** Speaking settings (some options have no real
   capability yet) and sending often-missed characters to the SRS queue (a persistence and
   Vocabulary change for its own slice).

## D-077 — Speaking review answers: free talk's older ways kept one step in; `say_again` approved

**Date:** 2026-09-23. **Source:** the human, answering the first Speaking review report
(`feature/speaking`).

**Decision.**

1. **S14.** Free talk keeps its older capabilities (look closer, develop into writing, start a
   conversation). They need not sit on the result screen; they follow progressive disclosure in the
   new UI. Built: a "⋯" button in the result's top bar opens the deep-ways sheet Listening already
   uses, holding the three.
2. **S15.** The `say_again` field of the `spoken-response` contract is approved, because it serves
   the current Speaking flow (the result's "say this again" line and "say the corrected line"). It is
   required in the provider schema and returned only as a line in the learning language's script,
   else empty (`writing_coach/media_interaction.py`, `tests/test_learning_paths_with_provider.py`).
3. **S3 stays a known gap.** Azure is not reliable enough to judge Mandarin tones; no SpeechSuper.
4. **Not in this slice:** a paid tone provider, loudspeaker detection, a "previous line" control, new
   SRS persistence, invented content for the Speaking catalogue or phrase suggestions.
5. **S9, S10, S11, S16, S17, S23** stay documented gaps; scope is not widened for them unless a
   direct bug of the current flow needs it.
6. **Credentials.** The Azure key was rotated. No credential value is ever printed in a report, log
   or error; the cause of the one print (a transport error quoting a header) is fixed in the speech
   adapters.
7. A full end-to-end run on the current HEAD precedes the next review report; results from older
   commits do not stand in for it. No merge, no push.

**Supersedes:** the open questions S14 and S15 in `docs/project/UI_BACKEND_GAPS.md`.

## D-078 — App-wide: a learning workspace is the viewport, never a long page; one flow per capability

**Date:** 2026-09-23. **Source:** the human, "APP-WIDE LEARNING WORKSPACE RULES — NON-NEGOTIABLE",
given in the `feature/speaking` session. It overrides the design where they differ (explicit current
human instruction ranks first).

**Decision.**

1. **The rule** (verbatim): "Learning workspace không được trở thành một page dài. Workspace shell
   phải nằm trong viewport. Chỉ những vùng nội dung có bản chất dài mới được scroll nội bộ bên trong
   workspace. Primary learning controls và primary actions phải luôn nằm trong vùng thao tác của
   viewport." It binds every learning workspace (Reading, Listening, Speaking, Dictation, Writing,
   Vocabulary, Grammar and later ones), desk and phone. Browsing pages (Home, Library, catalogues,
   discovery, history) are exempt. No agent may loosen it for an implementation reason. Written as
   Design Contract rule 49 with its acceptance items in the fidelity gate; `AGENTS.md` and
   `CLAUDE.md` point to it.
2. **Internal scroll only for content long by nature**, in one bounded region per need; finite
   components are laid out directly and scroll regions are not nested.
3. **When it does not fit, recompose** by the stated priority (content being learned, primary
   interaction, task state, main feedback, submit/retry/next, support, detail); blind scaling is not
   a fix.
4. **One learner flow per capability.** Every way in reaches the current flow; old addresses
   redirect and old learner screens are never rendered.
5. **Speaking is to be cleaned up now** under this rule.

**Applied in this slice (`feature/speaking`).**

- Speaking: the room is bounded to the viewport. On a desk the task is fixed bands (steps, mode,
  line, controls) around a stage where the model clip takes the free height at 16:9 and yields first;
  the result is a fixed head, the word list (the one scroll region) and the actions in a foot band the
  same height as the controls, so the two panels close on one line. The result's actions are one row:
  "hear yours" and "compare" (icon-only on a narrow panel, still named), "next" as the primary; the
  second "record again" left the panel, recording again is the microphone and the retry beside it. On
  a phone the clip yields before the result card, whose flagged words scroll inside it. Compare
  (attempts), the summary (the lesson's lines) and free talk (the transcript) each have one scroll
  region. Measured at 1920x1080, 1440x900, 1366x768, 390x844 and 360x740, with a 32-character line,
  a 7-line lesson, five real takes and DOM-filled stress content (28 lines, 15 attempts, a long
  transcript).
- Routing: `static/orena/product/legacy-routes.js`, applied by the router before any render:
  `#/practice` (the Practice hub) goes Home; `#/practice?intent=shadowing` without a lesson goes to
  the Speaking library; `?intent=dictation` to the Listening library (or the lesson's dictation with
  an id); `?intent=writing` to `#/writing`. The hub (`practiceOverview`) and the list of moments are
  deleted; the back links that led to the hub now name their owner (Vocabulary for the review, Home
  for grammar); Progress's Dictation card and History's fallback point at the current places. Gate:
  `scripts/test_orena_legacy_routes.mjs`.

**Open for the human.** Grammar's own page had no way in but the retired hub, and the design draws
none (UI_BACKEND_GAPS, S24). The other workspaces (Reading, Listening, Dictation, Writing,
Vocabulary) are not re-measured in this Speaking slice; each owner applies rule 49 and its gate.

## D-079 — Three independent language layers: interface, support, target

**Date:** 2026-09-24. **Source:** the human, closing Speaking's merge blockers ("FIX GỐC LỖI NGÔN NGỮ —
APP-WIDE"), after a word sheet showed English, Vietnamese and Chinese at once.

**Decision.** Orena has three language layers and none is inferred from another:

- **interface** - navigation, buttons, menus, system chrome, Settings, system labels and actions;
- **support/native** - explanation, translation, hint, instruction, guidance, grammar and vocabulary
  explanation;
- **target learning** - the material: sentence, word, transcript, exercise.

`ctx.ui` is the interface language, `ctx.support` the support language, `ctx.language` the target
language. The support language never decides the interface language. Acceptance cases: A (interface
English, support Vietnamese, target Chinese), B (Vietnamese, Vietnamese, English), C (Chinese,
English, Chinese), each holding across boot, reload, cache, profile load, preference change,
navigation, the Speaking workspace and the word sheet.

**Supersedes.** D-051's "learner-facing scaffolding follows the interface language" (scaffolding
follows the support language), the Design Contract's former "two learner language roles, and only
two" (rewritten), and commit `474ab59` ("the support language owns the UI"). It restores the
three-layer rule `docs/product/ORENA_LANGUAGE_COHERENCE.md` already stated.

**Applied (`feature/speaking`).**

- Source of truth: `static/orena/product/languages.js`. Interface: the learner's choice on the device
  (`orena.interface`) - the account's `interface_language` stays unstored, its column being a gated
  migration - else the browser's language when Orena is written in it, else English. Support: the
  account's `support_language` (else `native_language`). Target: the server's active language.
- `app.js` assigns each layer only through its resolver; the old support cache (`orena.support`) is
  neither read nor written; the preferences sheet offers the interface language as its own choice;
  `account_profile.py` allows `vi` as an interface language (still not stored).
- Speaking picks each string by its layer (`ui/speaking-copy.js`, `GUIDANCE_KEYS`), with `lang` on the
  guidance it renders.
- Gate: `scripts/test_orena_language_layers.mjs` (in CI).

**Open.** Static guidance on the other surfaces still reads the interface pack (coherence audit
AUDIT-1b); each owner splits its keys. Storing the interface language on the account is a gated
migration for the human.

## D-080 — Every learner copy string declares its language layer (D-079 made app-wide)

**Date:** 2026-09-24. **Source:** the human: D-079 was not complete while static guidance outside
Speaking still read the interface pack (AUDIT-1b), and the Speaking copy relied on an allowlist of
guidance keys ("not in the list = interface").

**Decision.** Every key of every learner copy table declares its semantic layer - `interface`
(button, menu, navigation, title, region heading, label, metadata, counter, placeholder, short system
status), `support` (explanation, instruction, hint, coaching, verdict, feedback, the explanation of a
result, a state or an error) or `target` (material; none lives in copy). There is no default layer.
Each screen reads each string from the pack of its layer; a support language Orena has no pack for
reads guidance in English, never in the interface language. Content explanations follow the same
rule.

**Applied.** `static/orena/ui/copy-layers.js` (every key, with the reason for each decision that
differs from the plain rule), `static/orena/ui/layered-copy.js` (the one accessor), `ctx.c`,
`refCopy(ctx)` and `speakCopy(ui, support)` built by it, Grammar's pattern names and notes on the
support language. Gate: `scripts/test_orena_copy_layers.mjs` (in CI). Browser: cases A, B, C on
desktop and phone across Home, Library, Progress, Profile, Reading, Listening, Dictation, Writing,
Vocabulary, Grammar and Speaking - every visible copy string in its layer's language.

**Replaces** the Speaking `GUIDANCE_KEYS` allowlist. Closes coherence audit AUDIT-1b.

## D-085 — Orena Intelligence is a separate lane over the unified Codex baseline

**Date:** 2026-09-27
**Status:** Accepted (explicit human direction)

**Context.** The Admin + Speaking integration was externally reviewed and merged
into `codex/work` by PR #63 at
`9c0fe315601877b43ac23aaffec915628635f9ae`. Orena's own Agent Intelligence now
needs an isolated lane so it can evolve in parallel without reopening the
completed domain integration or coupling the product to one model provider.

**Decision.**

1. `codex/work` is the unified baseline. Orena Intelligence develops in a
   separate branch/worktree, `feature/orena-intelligence`, created from the
   latest unified baseline.
2. The Intelligence lane owns orchestration above the product: learner context,
   evidence/memory assembly, capability discovery and routing, contextual
   handoff, agent actions, conversation coordination, and model/provider
   abstraction.
3. It reuses the existing Reading, Listening, Speaking, Writing, Vocabulary,
   Grammar, Progress and other domain services. It does not create duplicate
   domain engines merely to make the agent easier to implement.
4. Agent actions are explicit, schema-bound, allowlisted capabilities. The agent
   does not receive unrestricted internal API access and must not invent actions
   the application cannot execute.
5. Model and provider names are infrastructure details. Learner-facing identity
   remains Orena; switching or falling back between providers must not change
   that product identity.
6. This decision does not authorize learner-UI redesign, production provider
   activation, shared-runtime migration, deployment, or destructive persistence
   change. Existing human gates remain in force.
7. The Intelligence lane may run in parallel with future UI work, but domain
   contracts remain authoritative and any later integration back into
   `codex/work` requires its own review and verification.

## D-086 — The new learner UI replaces the old one on codex/work; only it carries Orena Intelligence, through one shared contract

Date: 2026-09-27 Status: Accepted (explicit human direction)

Context. D-085 opened feature/orena-intelligence for the agent backend and gave it no learner-UI authority. The human is applying a new learner UI on codex/work that replaces the old UI entirely — its behavior included — and may add flows and retire old ones. The agent must appear only in that new UI. The two lanes do not read each other's implementation (AGENTS.md §3), so they need one interface both can build against.

Decision.

The new learner UI is built on codex/work and replaces the old learner UI, including behavior; flows it does not carry are retired with it. The old UI receives no agent integration.
docs/project/AGENT_CONTRACT.md (contract_version 1) is the only interface between the new UI and the intelligence lane: request, SSE events, segments, evidence, the action allowlist, surface/navigation intents, capabilities and the provisional voice session.
The contract is edited only on codex/work, by a reviewed commit that bumps contract_version and is recorded here. feature/orena-intelligence receives it by merging codex/work forward and never edits it.
The agent names intents and actions, never routes or screens, and emits only what the client declares in client.supported_actions / supported_intents. A flow the new UI drops therefore disappears from the agent without a backend change.
The UI lane owns the agent panel, the action dispatcher, intent-to-screen mapping, device memory for conversation and coach notes, mic/voice state, and a frontend mock that replays the contract's canonical streams. The intelligence lane owns /api/agent/\* and must reproduce the same streams in its contract tests.
Mutating actions are executed by the client through existing APIs with the learner's session; the agent backend stays read-only in v1.

This decision does not authorize production provider activation, shared-runtime migration, deployment or destructive persistence change, and does not settle visual fidelity: the Claude Design source remains unavailable and the visual-source gate UNVERIFIED as recorded in CURRENT_HANDOFF.md. Integration of the intelligence lane into codex/work requires its own review and verification.

Supersedes / Superseded by: nothing. Extends D-085.

## D-087 — Learner UI copy is learning-first, sparse and non-promotional

**Date:** 2026-09-27. **Status:** Accepted (explicit human direction).

**Context.** Learner surfaces had accumulated AI-style slogans, motivational
subheads, repeated explanations and decorative helper text. Even when each line
was harmless in isolation, the total copy density competed with the material
being learned and diluted attention.

**Decision.**

1. Persistent learner UI follows Design Contract rule 50: every visible
   sentence must justify itself through comprehension, safety, task completion
   or learning feedback; otherwise it is removed.
2. Slogans, inspirational/marketing copy, generic encouragement, redundant
   subtitles, obvious-control explanations and routine celebration are not
   generated by default.
3. Page subtitles and card descriptions default to absent. Controls and status
   text use the shortest unambiguous wording; empty states are at most one short
   sentence plus one action unless safety or task correctness requires more.
4. Measured state and concrete next actions are preferred over prose: e.g.
   "12 due today" is more useful than generic progress encouragement.
5. Learning material, the primary interaction and actionable feedback outrank
   product copy in both layout and attention. When space is constrained,
   decorative/support copy yields first.
6. Every learner-facing UI change performs a copy audit before review:
   decorative copy = 0, redundant subtitles = 0, duplicated meaning = 0, and
   every intentionally retained sentence has a clear functional reason.
7. This does not suppress lesson content, user-requested explanations,
   substantive pedagogical feedback, required error/safety text, or an Orena
   Intelligence conversation the learner intentionally opens. It governs
   persistent/unsolicited product copy and keeps those other surfaces concise.
8. External UX-writing repositories or skills may be used as references, but
   they do not become a second authority. This repository's Design Contract is
   the source of truth for Orena.

**Applied to:** both `codex/work` and `feature/orena-intelligence` so the
learner UI and Intelligence lane share the same copy-density constraint.

## D-088 — The learner design moves to Claude Design project e6dc1cb2; it replaces the Dark Glass baseline on every learner surface

**Date:** 2026-09-27. **Status:** Accepted (explicit human direction).

**Context.** The human approved a new learner design, in a different Claude
Design project from the one D-066/D-067 named, and made it "the visual and
interaction root of Orena", to be implemented app-wide as the canonical learner
UI that D-086 says replaces the old one. It changes the navigation (six places
instead of four), the type, the icon family, the colour system (two themes) and
nearly every component, so the old visual rules cannot be balanced against it.

**Decision.**

1. The authority for how every learner surface looks, behaves and what it shows
   is Claude Design project `e6dc1cb2-72d0-40b4-a916-5dcd47e17cc0`, read at its
   source and pinned byte for byte at revision `1790473816124946` in
   `docs/design/canonical-ui/screens/` (`Orena.dc.html`, `Onboarding.dc.html`,
   `Compare-With-Model.dc.html`; `SYNC_2026-09-27.md`, `PINS.tsv`). Within it:
   the frames, then the state script at the end of `Orena.dc.html` (behaviour),
   then the brief in `docs/design/canonical-ui/brief/` (intent). A screen the
   brief names and no frame draws is not designed. The script's prototype
   internals - simulated audio, canned scores, a browser pitch tracker, demo
   attempts, hard-coded positions - are not product behaviour: the product keeps
   its real services (Azure pronunciation, the YIN tracker, real media and
   positions) and shows their results in the design's components.
2. It supersedes project `7a5604ca-1e11-4d8e-8305-7d0cb32d552d` for learner
   surfaces, and with it the Dark Glass system of D-066 and Design Contract
   rules 30, 31, 34, 35, 36, 37, 38, 46, 47 and 48 as written: ground and glass,
   Nunito / Nunito Sans / DM Mono / Noto Serif, Phosphor, the five-item
   navigation, the 280px rail, the card and artwork-slot rules, the old shell
   and frame rules. The new system is the design's own: Outfit for the
   interface, Fredoka for the wordmark, Literata for reading text, JetBrains
   Mono for figures and labels, Noto Sans SC / Noto Serif SC for Chinese; the
   Lucide icon family at one pinned official release, every path taken from the
   package (the design's hand-typed variants of the same icons are replaced by
   the package's); Today, Discover, Practice Hub and My Library in the desktop
   rail with the "Ask Orena" card and the account row, and Today, Discover,
   Orena (the raised centre action), Practice and Library in the phone bar;
   Progress and Settings reached from Profile; a learning workspace (the
   design's focus list) has no top bar and no tab bar.
3. The design draws states: Banner, Loading, Load error, Coming soon, its empty
   states and the microphone states. Rule 39 no longer forbids what it draws;
   what it still does not draw follows rule 39.
4. Unchanged and binding on the new UI: rules 9, 14, 16, 26-29, 32, 33, 40-45,
   49 and 50, the learner language contract (D-079), D-068 point 1 (the
   design's words and data are sample content). Where the design and a rule
   disagree - a phone learning workspace drawn as a scrolling page against rule
   49, a decorative subtitle against rule 50 - the rule wins, the surface is
   recomposed or trimmed, and the deviation is recorded in
   `docs/project/UI_BACKEND_GAPS.md`.
5. A face without the glyphs a locale needs falls back technically, never by
   redesign (as D-061 did for DM Mono): Outfit has no Vietnamese subset, so
   Vietnamese interface text is set in a Vietnamese-complete face of the same
   geometric family, recorded as a deviation.
6. Platform Admin is not part of this change. `screens/Orena-Admin-Control-Center.dc.html`
   stays its authority until the human opens Admin; the new project's
   `Orena Admin.dc.html` is read only for shared primitives.
7. A design file over 256 KiB cannot be read whole through DesignSync; it is
   read from a human export and pinned byte for byte, and a later revision is
   diffed against `PINS.tsv`.

**Consequences.** `DESIGN_CONTRACT.md` (the authority and the visual rules),
the design pointers in `AGENTS.md` and `CLAUDE.md`, and the cache README are
rewritten; the learner pins of 7a5604ca move to
`docs/design/canonical-ui/superseded/7a5604ca/`; the visual-source gate in
`CURRENT_HANDOFF.md` is no longer UNVERIFIED.

**Supersedes / Superseded by:** Supersedes D-066 (its visual system and its
authority for learner surfaces) and the authority pointer of D-067; D-067's
method - read at the source, measure, invent nothing, delete the old
interaction - stands. Supersedes the Dark Glass ground decisions D-070, D-071
and D-073, and makes D-061 moot. D-068 point 2 is superseded by D-090.

## D-089 — The learner UI ships the design's light and dark themes, following the operating system

**Date:** 2026-09-27. **Status:** Accepted (explicit human direction).

**Context.** The new design (D-088) defines complete light and dark token sets.
The product has had one dark theme since D-066, and `LEGACY_TOMBSTONES.md`
forbade "a Paper or light theme returning as a setting".

**Decision.**

1. Both of the design's themes ship. The theme follows the operating system
   (`prefers-color-scheme`) and changes with it live.
2. The one in-product control the design draws - the light/dark button in the
   Reader's toolbar - switches the whole app, as the design's script does. The
   choice is a device preference kept in the browser (like the interface
   language before its column exists), never account data; it can be cleared
   to follow the system again. No Settings row is added: the design draws none.
3. Colour keeps one owner, the new UI's token file, holding both themes'
   values exactly as the design gives them; no component invents a colour, and
   AA contrast is checked for both themes.
4. This light theme is the new design's own. D-059's Ink and Paper themes, the
   sepia reader block and every hybrid remain retired.

**Supersedes / Superseded by:** Supersedes the tombstone clause "a Paper or
light theme returning as a setting" (the Ink / Paper tombstone is updated to
say so) and D-066's single-theme rule.

## D-090 — The design's logo and Orena Intelligence mark replace the curled-tail mark in the learner app

**Date:** 2026-09-27. **Status:** Accepted (explicit human direction).

**Decision.**

1. The learner app's brand mark is the design's: the gradient swirl (`ol-mark`)
   in its dark disc, with the Fredoka wordmark "Orena", in the rail, the phone
   header, onboarding and the favicon. It replaces the orange curled-tail mark
   (`static/orena/assets/mark.svg`) there.
2. The design's Orena Intelligence mark (`ol-intel` and its thinking, listening
   and speaking states) is the agent's identity wherever the design draws the
   agent: the Ask Orena card, the phone bar's centre action, Orena Home, the
   contextual panel and voice mode.
3. The marks are brand assets: their source copy lives in the Art Bible
   package (`assets/brand/orena/`), taken from the pinned design without
   redrawing, and the app renders that copy.
4. The red-panda mascot, its artwork and the Art Bible's rules are unchanged;
   Orena Orange stays the mascot's colour.

**Supersedes / Superseded by:** Supersedes D-068 point 2 ("the logo stays as it
is").

## D-091 — The new learner UI is built beside the old one and replaces it in one cutover

**Date:** 2026-09-27. **Status:** Accepted (migration strategy chosen by the
implementing lane under the human's migration brief; recorded for every lane).

**Context.** D-086 and D-088 replace the whole learner UI. Two ways were open:
migrate the old UI in place, surface by surface, or build the new UI beside it
and switch over once. The new design changes the navigation, the shell, the
type, the icons, the colour system and nearly every component at once, so
there is no surface where the two systems can sit on one screen without the
hybrid the contract forbids; an in-place migration would leave `/` a mixed app
for the whole migration, and the intelligence lane, which merges `codex/work`
forward, would be integrating its agent into a moving hybrid.

**Decision.**

1. The new UI is a separate entry: `templates/orena/next.html`, served at
   `/next`. `/` keeps serving the old UI, unchanged and fully gated, until the
   cutover.
2. Its code lives under final names from the start - `static/orena/main.js`
   (entry), `shell/` (frame, router, focus mode, overlays), `kit/` (tokens,
   icons, brand, primitives), `screens/` (one folder per canonical surface),
   `copy/` (interface strings, en / vi / zh, with their language layer),
   `agent/` (panel, dispatcher, device memory, contract mock) - so the cutover
   renames nothing.
3. It reuses the domain layer (`product/`, `capabilities/`, `content/`,
   `infrastructure/`) and the backend as they are. It never imports the old
   `ui/*.js` presentation or the old stylesheets. Logic worth keeping that sits
   in an old `ui/` module is moved (not copied) into the domain layer, and both
   UIs import it until the cutover.
4. Each slice builds a coherent set of surfaces with real data and real
   journeys, adds gates for them, is verified in a browser (desktop and phone,
   en / vi / zh, both themes), and is committed and pushed. A surface the
   backend cannot serve yet uses the design's own Coming soon screen, never
   invented data.
5. The cutover slice makes `/` serve the new UI, sends every old address into
   the new flow (`product/legacy-routes.js`), deletes the old template,
   `ui/*.js` presentation, the old stylesheets and `theme.js`, writes a
   `LEGACY_TOMBSTONES.md` entry per retired surface, and replaces each retired
   surface's gate with a gate on its successor. No gate is deleted to make CI
   pass.
6. Between slices `codex/work` is always in this state: `/` is the old UI,
   verified; `/next` is the new UI, with the surfaces listed under "New UI
   coverage" in `CURRENT_HANDOFF.md`; both share one domain layer; no
   learner-data schema has changed; the agent panel exists only in the new UI,
   on the contract mock (D-086), and calls no `/api/agent/*` until the human
   says the intelligence lane is integrated.

**Supersedes / Superseded by:** Nothing. Extends D-086.

## D-092 — Agent contract v2: the Orena destination, the opening turn, and payloads the product can execute

**Date:** 2026-09-27. **Status:** Accepted (explicit human approval of `docs/project/AGENT_CONTRACT_V2_PROPOSAL.md`, unchanged).

**Context.** The new learner design (D-088) makes Orena a destination and opens a thread with Orena speaking first; contract v1 could address neither. The intelligence lane's pre-flight, checked against the real APIs, found that five v1 actions and three surface ids named identifiers the product does not have: words have no id (the library keys a word on its text and the session's learning language), take audio is never stored (D-076), a speaking attempt record cannot be read by id, a review has no single call, and two collection systems exist. Neither lane had implemented v1's actions.

**Decision.** `AGENT_CONTRACT.md` becomes `contract_version: 2`:

1. `orena.home` is a surface id and a navigation intent.
2. `trigger: "open"` is an opening turn without a learner message: one short greeting, suggestions, at most two LOW actions, read-only, not a learner turn (new stream S13).
3. `action` and `evidence` may carry `display` (title, kind, duration from domain records; a checkable `reason` of at most 90 characters).
4. Words are `{ text, lang }`; `play_user` and `compare_with_model` act on a client-minted `take_ref`; `say_again` names the line; `start_review` is client-composed (`due` or one word); `add_word_to_collection` names `deck` or `library`; `attempt_id` is the stored audio-free record's id; `vocabulary.word`, `speaking.word_detail` and `speaking.compare` take those identifiers.
5. The contract keeps `zh-CN`; the product's internal code is `zh`; each side maps at its own boundary.
6. A server sends no v2-only field, id or changed action to a client that declared version 1.

**Consequences.** The new UI declares v2 intents and actions, sends `trigger: open`, mints `take_ref`, executes the payloads through the listed APIs, and its mock replays S13 and the revised S5. The intelligence lane merges `codex/work` forward and implements the same in its contract tests. Backend gap N-9 (owner-scoped read of a speaking attempt record by id, no schema change) is recorded in `UI_BACKEND_GAPS.md`.

**Supersedes / Superseded by:** Supersedes contract_version 1 (D-086 stands).

## D-093 — The new design's colours are adjusted minimally for AA contrast

**Date:** 2026-09-27. **Status:** Accepted (explicit human choice among the options recorded in `UI_BACKEND_GAPS.md` N-8).

**Context.** Measured against the pinned design's own tokens, 13 text-on-ground pairs failed AA 4.5:1 for the small interface text they carry: in the dark theme `--text3` (placeholders, meta, inactive phone tabs), `--accent` on `--accent-soft` (the active rail item, the language pill), white on `--accent` (primary buttons) and white on `--red` (count badges); in the light theme `--text3` and the green, red and amber result inks on their soft fills. Design Contract rule 41: accessibility never redesigns; a failing token gets the smallest technical change that keeps the visual intent.

**Decision.** Lightness only, hue and saturation kept:

1. Dark: `--text3` #77778E → #858599; `--accent` #7D78F5 → #847FF6; filled controls under white text use a new `--accent-fill` #6862F3 (hover #5E58EA, pressed #544EDC) instead of `--accent`; the numbers on the red count badge use a new `--badge-ink` #0E0E16.
2. Light: `--text3` #8E8EA2 → #6E6E86; `--green` #138A5A → #117E52; `--red` #D93D42 → #D0292E; `--amber` #B86E00 → #A16000; `--accent-fill` is the design's own accent (#5A55E3, hover #4C47D2, pressed #403BBE); `--badge-ink` stays white.
3. Every other token is the design's value. `scripts/test_orena_kit.mjs` pins these exact values, checks every drawn pair at 4.5:1 in both themes, and refuses white ink on `--accent`.

**Consequences.** A later design revision that fixes its own contrast replaces these values from its pin; one that does not is measured again under rule 41.

**Supersedes / Superseded by:** Nothing. Applies rule 41 to D-088's tokens.

## D-094 — Agent contract v3: an action's label is interface layer (amends D-092)

**Date:** 2026-09-27. **Status:** Accepted (explicit human direction).

**Context.** Contract v2 (D-092) said an action's `label` is in the support language. D-080 made every learner copy string declare its layer, and a button is interface layer. The agent's actions are drawn as buttons, so v2 contradicted D-080.

**Decision.** `AGENT_CONTRACT.md` becomes `contract_version: 3`. An action's `label` is in the interface language (`context.locale.interface`), at most 24 characters. The explanation an action's card carries (`display.reason`) stays in the support language, and so does every segment. A server may still send support-language labels to a client that declared version 2. The UI's request declares version 3; its mock labels buttons in the interface language; `scripts/test_orena_agent.mjs` checks both.

**Amends:** D-092 point 3/§7 rule on `label`. D-092 otherwise stands.

**Addendum (2026-09-27, the same amendment, explicit human direction).** Contract v3 also fixes the canonical streams S1 and S13, which put a §6.1 navigation id (`review_due`, `vocabulary.review_due`) in `suggestion.intent` although §4 requires a prompt intent. §4 now defines a prompt intent (the `prompt.` namespace, never a §6.1 id; tapping a suggestion sends its label as the learner's message), S1 and S13 use `prompt.review_due`, the mock follows, and `scripts/test_orena_agent.mjs` checks both the fixtures and the mock. `contract_version` stays 3.

## D-095 — Agent contract v4: HTTP statuses and error classes the UI must handle (amends D-092)

**Date:** 2026-09-27. **Status:** Accepted (explicit human direction).

**Context.** Contracts v2 and v3 described the turn stream and its `error` event but not the HTTP statuses of `/api/agent/*` or the error classes. The intelligence lane's server (`writing_coach/agent/api.py`, `errors.py`, `ratelimit.py`, read on `feature/orena-intelligence` at `f36f465`) answers 404 while `AGENT_ENABLED` is off (always in production), 429 `rate_limited` with `Retry-After` from a per-learner sliding window, 409 `target_language_mismatch` when the request's target language is not the learner's learning language, and 422 for a malformed request; its stream errors are `provider_unavailable` and `internal_error` (`retry`) and `voice_unavailable` (`text_only`). A UI that reads a 404 as an error, or treats a rate limit as a failure, would show the learner something false.

**Decision.** `AGENT_CONTRACT.md` becomes `contract_version: 4`.

1. §2.1 is the status table. 404: Orena is absent for the visit - every entry point hidden, no error, no retry; learned from `GET /api/agent/capabilities` at start or any 404. 429: a brief wait state (Orena stays thinking), then the same request again after `Retry-After`, waiting again if refused, cancellable. 409 `target_language_mismatch`: the UI re-reads the learning language, applies it as any language change and keeps the message unsent; no automatic resend. 401 is the app's sign-in handling; 422 is a client defect ending the turn with `fallback: none`.
2. §4.1 lists the classes and fallbacks. The UI acts on `fallback` (`retry`: a learner's retry control, never automatic; `text_only`: voice closes, text continues; `none`: message only), an unknown class by its fallback, an unknown fallback as `none`. The client's own `transport` class covers a network failure, an unlisted status and a stream without `done`/`error`.
3. The mock plays H404, H409 and H429 for review.

The UI's side ships with it: `static/orena/agent/contract.js` (version 4, the tables as data), `transport.js` (the live path answers every status; still off), `presence.js` (Orena absent for the visit), `session.js` (wait, unsent and absent states), `mock.js`; `scripts/test_orena_agent.mjs` reads both tables from the contract text and drives the live transport with a fake fetch. Hiding the shell's entry points on `absent` is wired with the Wave A shell integration.

**Amends:** D-092 (§2 and §4 grow a table each; nothing else changes). A server answers a v3 client as before.

## D-096 — Agent contract v5: the learner's address, offers not claims, surface names and purposes

**Date:** 2026-09-28. **Status:** Accepted (explicit human direction, on `docs/project/AGENT_CONTRACT_V5_PROPOSAL.md`, with seven reconciliation points and two clarifications).

**Context.** Vietnamese (and, less often, Chinese) has no neutral "I" and "you"; the server's fixed copy and the model used `mình` / `bạn` for everyone, and a learner's own choice could not stick. The intelligence lane had applied the choice in model replies under the human's rulings R19, R21 and R22 with v4's shapes, but its fixed copy could not follow a preference the contract did not carry. Separately, fixture S5 ("Mình lưu 我 cho bạn nhé.") read as if Orena had saved a word the learner had not tapped, S2 and the §5.1 example named the pronunciation provider, and the intelligence lane kept its own copies of the UI's screen names.

**Decision.** `AGENT_CONTRACT.md` becomes `contract_version: 5`.

1. **Address (§5.6).** `context.address { self?, user?, register?, lang }` carries the learner's choice for their support language; omitted is the default (vi `mình`/`bạn`, zh-CN `我`/`你` and `plain`, en `I`/`you`). `user` may be a name or a form of address with a name ("Minh", "anh Minh"). English takes only `user`, ignores `self` and never replaces "I"/"you". Chinese also takes `register`: `plain` (你) by default, `polite` (您) only when the learner asks. Terms are 1-24 characters, at most 3 words, Unicode letters (any script with its marks: Vietnamese with diacritics, Han characters) and single spaces; validated on both sides, invalid means default. The server always escapes the terms before the model and never inserts them raw, uses them for the turn only, and never writes them to logs, telemetry, traces or any store. It applies them to support-layer text and to its fixed copy through `{self}` / `{user}` slots; never to interface labels or target-language material.
2. **How it changes.** Orena never asks on its own when the learner has given no sign. A learner's request applies at once. Vietnamese kinship terms the learner uses of themselves or of Orena are answered in kind at once and saved (R22). A pair the learner keeps using that the server does not map by itself (e.g. `tớ` - `cậu`) is confirmed once; a no is saved. Signs of a minor keep the default. Nothing is inferred from gender, age, personality, a name or the learner's writing.
3. **The note.** Kind `address`, id `address-<lang>`, one per support language, no decay or expiry, set by `memory_update` upsert; a change, including back to the default, is an upsert that replaces it (R21). Sent as `context.address`, never in `coach_notes`; listed and deletable in `preferences.agent_memory`.
4. **Offers, not claims (§7, §10).** A segment that comes with an action offers it and never reports it done; a reply that names the button uses its interface-language label and does not describe the interface ("Bấm Lưu từ để thêm 我 vào từ vựng của bạn."). No reply, error message or fixed copy names a provider or model. S5, S2 and the §5.1 example are reworded.
5. **Surface names and purposes (§6.2).** The UI publishes, per §6.1 id, the place's name (from the shell's route titles) and a one-line purpose (interface layer, en/vi/zh-CN, ≤ 90 characters) as `static/orena/copy/surfaces.json`, generated from `static/orena/copy/surfaces.js` and gated; the server reads it and keeps no copies. "NEW_UI_MAP" is `docs/design/canonical-ui/IMPLEMENTATION_MAP.md`: purposes are written once it is stable.
6. New canonical streams S14 (setting an address) and S15 (identity answered by rule with an address).

The UI's side ships with the version: the address validation, note and request field, the mock's S14/S15 and reworded S2/S5 in vi/en/zh, the surfaces copy and its generated file, and their gates.

**Amends:** D-092 (§3, §5.4, §7, §10, §12). D-092, D-094 and D-095 otherwise stand. A client that declares `contract_version` ≤ 4 gets the defaults.

## D-097 — The learner can choose the theme in Settings (amends D-089)

**Date:** 2026-09-28. **Status:** Accepted (explicit human direction, a Wave A review item).

**Context.** D-089 ships the design's light and dark themes following the operating system, with the Reader's light/dark button as the only in-product switch, and added no Settings row because the design draws none. Reviewing Wave A, the human asked for the choice Light / Dark / System in Settings.

**Decision.** Settings offers Light, Dark and System (the Learning tab, drawn with the design's own choice-row control). System is the default and follows the operating system live, as D-089 says. The choice is a device preference in the browser, like the interface language, never account data; it is applied before first paint, at once when changed, and an unknown stored value reads as System. The Reader's light/dark button, when built, sets the same preference. Colour keeps its one owner and AA holds in both themes.

**Amends:** D-089 point 2 ("No Settings row is added"). D-089 otherwise stands; DESIGN_CONTRACT rule 30 says the same.

## D-098 — Answers to the new UI's open design questions and the Wave B review decisions

**Date:** 2026-09-29. **Status:** Accepted (explicit human direction).

**Context.** `UI_BACKEND_GAPS.md` section N, "Open design questions", and the Wave B hand-off left choices only the human could make. The human answered them in one message.

**Decision.**

1. **Today** keeps what the pinned frame draws: no review-reminder pill (brief part D) and no practice shortcuts (part G).
2. **Import, File** is wired to `POST /api/media-learning/upload` with the file types and size limit that endpoint already enforces; the UI states no limit of its own.
3. **Settings, support language** stays the frame's segmented control while the list has at most 4 languages, and becomes a picker, built from the kit's existing sheet and row components, when it has more.
4. **Grammar on Grammar Lab content** (question 6): the UI lane may build the word_order and morphology illustrations, a Chinese Grammar Library, Chinese-specific structures, and role colours linking a formula to its examples, using only the kit's existing tokens and components and modelled on the timeline component. No new visual language. The human reviews these by eye. Frame 23 or 47 (question 4) is answered separately.
5. **Japanese** gets a Writing-minimum row, counted in characters as for Chinese.
6. **Writing, Get feedback disabled:** one line says why, with a countdown of the words or characters still missing (interface layer, vi/en/zh).
7. **Lesson complete** shows only numbers the backend actually measured (for example correct / total); a tile with no measured number is hidden. No invented numbers.
8. **Onboarding** keeps the learner's self-chosen level; a placement check is deferred.
9. **Entry routing:** `/next` opens `#/welcome` when the profile has no learning language or no level, and Today otherwise. No new stored field.
10. **Compare Versions** follows the frame exactly.
11. **Lane:** `codex/work` is the UI lane (D-066) whichever agent works it, Claude included.

**Consequences.** Each Wave B item is its own commit. The Grammar authorisation takes effect when the Grammar screens are rebuilt on the grammar content contract.

## D-099 — Admin keeps its own address through the cutover; Grammar Concept is frame 47; the declared level goes to review

**Date:** 2026-09-29. **Status:** Accepted (explicit human direction).

**Context.** Planning the cutover (`UI_COMPLETION_ROADMAP.md`) found that the admin console,
merged into `codex/work` by PR #63 (D-085), would lose its host when `/` becomes the new UI, while
AGENTS section 7 and D-081 still described Admin as inert and unmerged. D-098 left the declared
level out of the entry rule because the backend does not store it.

**Decision.**

1. **Admin through the cutover.** The old admin console keeps running at an address of its own
   until the Admin wave, built on the pinned `Orena Admin.dc.html`, replaces it. The cutover does
   not wait for the Admin wave. `Orena Admin.dc.html` is pinned from the Claude Design project like
   the other design files. AGENTS section 7 says this; D-081's "not merged" is marked as overtaken.
2. **Before the cutover** the shared code the new UI still reaches in old `ui/` moves into
   `capabilities/` (roadmap step 3).
3. **H1:** frame 47 is the canonical Grammar Concept frame; frame 23 is not built. The timeline,
   word_order and morphology illustrations are built from the kit, as D-098 point 4 authorised.
4. **H2, the declared level.** The entry rule keeps its learning-language half now. Storing the
   declared level per learning language (CEFR for en, HSK 1-9 for zh, room for ja) follows the
   AGENTS section 7 process: a proposal after `ORENA_ACCOUNT_DATA_ARCHITECTURE.md`, an independent
   architecture review, human approval, then code, migration and tests. The human runs the
   migration on the sandbox; production is not touched. When it lands, `#/welcome` opens when there
   is no learning language or no level for it.
5. **Chinese Writing evaluator** (`ZH_WRITING_EVALUATOR_RECALL.md`): fix (1) with a zh+vi test now,
   benchmark (5) in parallel, prompt (4) only after (5) has measured, no deterministic detector
   (6), the token budget (7) only if truncation is measured.

**Amends:** D-081 (its "not merged" statement, as a matter of fact), AGENTS section 7's Platform
Admin hold. *Point 1 (an address of its own) is replaced by D-101 H8.* D-098 point 9 stands; its level half waits for point 4 here.

## D-100 — Grammar Lab replaces R5 as Orena's grammar source

**Date:** 2026-09-29. **Status:** Accepted (explicit human direction; PR #66 merged at `f86a2bf`).

**Context.** On 2026-09-28 the human began retiring R5 Grammar: Grammar Lab becomes the only
grammar source. The Grammar Lab lane drafted `docs/project/GRAMMAR_CONTENT_CONTRACT.md` (schema
v0.4). The UI lane reviewed it against the two Grammar screens, and the lane revised it
(`e293feb`, `4992cec`). The human merged it by PR #66.

**Decision.**

1. **Source.** Grammar content comes from Grammar Lab, in the shape of
   `GRAMMAR_CONTENT_CONTRACT.md`. R5 is no longer a grammar source: no new R5-specific rendering,
   content or contract work. The two Grammar screens are rebuilt on the contract: Grammar Library
   (frame 44) and Grammar Concept (frame 47, canonical per D-099).
2. **Order.** The UI lane builds the two screens' frame on the merged contract now and connects
   them to real data when the lane's fixture of 13 sample points arrives (Grammar Lab PR B). The
   lane's contract patch (PR A) fixes the five inconsistencies the UI lane listed and adds the
   "Try it yourself" recognition rule.
3. **Try it yourself** is drawn as frame 47 draws it. Until the contract carries a rule for
   recognising the target pattern, the screen never concludes "you used the pattern": a clean
   sentence is not evidence of use.
4. **API.** `/api/grammar/v1/*` is not built as part of this decision. It goes through its own
   architecture review. Until then the screens read fixtures, not a new route.
5. **What stays.** R5 code, Concept IDs and their gates remain until the rebuilt screens replace
   what reads them. Removing them is its own step, with a `LEGACY_TOMBSTONES.md` entry written on
   the human's instruction. AGENTS section 6 still lists "R5 Grammar contracts and Concept IDs" as
   protected until then. AGENT_CONTRACT section 6.1's `grammar.point{grammar_id}` moves to Grammar
   Lab ids in a contract bump.

**Supersedes:** R5 Grammar as the grammar authority (the R5 entries this log accepted stand as
history). Amends nothing else.

## D-101 — One complete staging on :8011 before the cutover; H1-H10 decided

**Date:** 2026-09-29. **Status:** Accepted (explicit human direction). **Replaces** the order,
the H1-H10 answers and the completion/cutover plans in the first version of
`UI_COMPLETION_ROADMAP.md`, and D-099 point 1 (Admin at an address of its own). It does not
override the Product Constitution, the Account Data Architecture, the Content Architecture, the
Agent Contract, auth and security rules or the architecture invariants, except where this entry
says so. Older documents that contradict it are updated to match.

**Goal.** One complete staging on :8011 running the latest `codex/work`: the old UI at `/` and
the new UI at `/next` until the human says "cutover". It holds the full learner UI for every
existing skill, the Admin needed to load real content, and Orena text chat with the intelligence
lane integrated. Complete means, for every existing skill (Reading, Listening, Dictation,
Shadowing, Speaking, Pronunciation, Writing, Vocabulary/Review, Grammar, Onboarding/Profile,
Orena): real content, the learner does the work, it is assessed where the domain contract defines
assessment, the result is stored on the server, and progress and history are still there after a
reload or a new login. No mock data on the :8011 critical path; learner progress is not
device-only.

**Principle.** Change what exists; do not build a parallel one. Before a screen, flow or
function, find its old-UI and current-Admin implementation, move logic, API calls and state
handling into shared modules and reuse them; rebuild only the presentation to the new design.
New code only where nothing can be reused, with the reason in the commit. Backend: reuse
services; add only what does not exist. The cutover deletes only old shells that have a
replacement.

**A. Staging.**
- :8011 always runs the latest `codex/work`.
- Its database sits on a durable volume of its own, apart from production and preview. Never
  `down -v`.
- `scripts/staging_backup.ps1` takes a `pg_dump` in one command.
- `scripts/staging_update.ps1` is run by the human, because migrations are the human's gate.
  - It fails closed on: a dirty tree, a branch other than `codex/work`, a pull that is not a
    fast-forward, a failed build, or a migration state it cannot read.
  - It prints the current revision and the pending list, and asks to confirm.
  - It backs up before migrating; a failed backup stops it.
  - It migrates, restarts, checks health, and prints the running SHA, the DB head and
    `:8011/next`.
  - Its first run takes :8011 from `20260923_0014` to the latest head.
- :8021 is the lane's own bench. Every try-it instruction to the human points at `:8011/next`.

**H1-H10.**
- H1: frame 47 is Grammar Concept.
- H2: `declared_level` is stored on the server. Architecture approved, with these conditions:
  - Meaning: the learner's self-declared current level, never measured or inferred;
    `account_profile.py` and the account data architecture are corrected to say so.
  - Existing accounts: option A. A learner who already has a learning language sees only
    Welcome's level step, not the whole onboarding.
  - Never inferred from old writing, history, evaluator output or evidence.
  - HSK 7-9 is one learner-facing band: no HSK7/HSK8/HSK9 choices. Finer curriculum metadata
    stays in the content domain and is never used to infer `declared_level`.
  - A throwaway-PostgreSQL up/down/up rehearsal, run when no lane is doing heavy Docker work.
  - The migration moves to `versions/` only with the human's permission.
  - `#/welcome` opens when there is no learning language, or no level for it.
- H3-H7: deferred, together with the eight Coming-soon screens and E1, until after staging.
- H8: the old console does not move to an address of its own. The existing Admin moves into the
  new UI (E). Until the cutover, the old UI's `/` and `/#/admin` stay untouched.
- H9: the eight Coming-soon screens are not in staging, and every entry to them in `/next` is
  hidden.
- H10: Admin on the pinned `Orena Admin.dc.html` starts now (E), not after the cutover.

**C. Chinese evaluator.**
- `EVALUATOR_CONTRACT_VERSION` v2.7 must not re-grade every stored review of every language.
  Only reviews that may be affected (Chinese writing with a non-Chinese explanation language) are
  re-graded, and only when the learner opens one. The approach is reported before the change.
- Benchmark v2 may run live with Gemini on the isolated stack, capped at USD 0.50 in total. Recall
  is reported for en and zh, and option (4) is decided on those numbers.
- C does not interrupt A -> D2 -> D3, and runs when Docker is free.

**D. Order.**
1. The staging scripts.
2. P1: every module `/next` loads from `ui/` moves to `capabilities/` or `kit/`, both UIs point
   at the one module, and a gate forbids `/next` from importing `ui/`. No behaviour change.
3. The D3 matrix, sent to the human once:
   - A summary row per skill, and a sub-row per flow present in staging.
   - Five steps per row: content / do / assess / store / come back.
   - Each cell is one of `RUNS_REAL`, `MISSING`, `N/A_BY_CONTRACT` (with evidence) or
     `PROPOSE_RETIRE` (needs approval).
   - A "reusable from the old UI / Admin" column.
   - `FUNCTIONAL_E2E_READY` and `CONTENT_SCALE_READY` recorded separately.
   - The open old flows: `url:` content, `#/language`/recall, `#/continue`, per-skill
     libraries, Growth summary, R5 ids.
4. One persistence proposal covering every storage gap, grammar progress included, merged with H2
   where sensible. One independent review, then human approval; migrations go through the
   rehearsal.
5. Admin.
6. Grammar.
7. Every `MISSING` cell, by reuse.
8. Orena.
9. The cutover, on the human's word.

A skill is complete only when every one of its non-deferred rows is.

**Persistence.** Server storage is required for learner-owned state that has learning meaning or
must survive across devices or sessions: progress, attempt/result, score/evidence, review
schedule, completion/history, declared level, and whatever D3 confirms as a learner record. Pure
presentation state (theme, text size, an open sheet, hover, a transient interaction) need not be
stored on the server. State that matters but is device-only is `MISSING` in D3 and goes into the
D4 proposal; no ad-hoc tables.

**E. Admin.**
- The existing Admin (`static/orena/admin/*`, PR #63) moves into the new UI on the kit, adjusted
  to the pinned `Orena Admin.dc.html`. Logic, APIs and `require_admin` stay unchanged; only the
  presentation and the old CSS variables are replaced. There is no second admin backend.
- Staging scope: shell, auth and No access, AI & Models, Reading pipeline, Imports, and Content
  (review and publish, including the Grammar Lab package import per `INTEGRATION_DESIGN.md`).
  Overview, Operations, Users and the Practice generator come later.
- Access is tested three ways:
  - the Profile entry shows only for an admin;
  - a normal account opening the address directly sees No access and loads no data;
  - admin APIs refuse at the server.
- Acceptance is one real loop: import real content, review it, publish it, and a learner opens it
  on `/next` and learns with it. The grammar package goes through the same loop.

**F. Grammar.**
- Frames 44 and 47 are built on the merged contract: the frame now, real data when Grammar Lab
  exports the core pack.
- Only approved content is shown, arriving by Grammar Lab validate/verify/review -> approved
  export -> Admin import/review/publish -> learner grammar source.
  - Never read drafts from `grammar_lab/content/`.
  - Never publish `draft_ai` fixtures; PR #68 is not production content.
- A level with no content shows "being completed". No R5.
- An old R5 id redirects through the R5 id that Grammar Lab records in each point's provenance.
- Try it yourself uses the contract's `pattern_rule` once PR #67 is merged. Before that it never
  concludes the pattern was used.

**G. Orena.**
- The panel stays on the mock until the intelligence lane's PR is merged.
- Then `AGENT_LIVE` is switched on, on :8011 only, and checked in full against contract v5:
  - a capabilities 404 hides Orena;
  - SSE turns;
  - 409 `target_language_mismatch`;
  - 429 with `Retry-After`;
  - `context.address`;
  - actions are only offered;
  - the opening turn comes from real data.
- Each surface in staging gets a one-line purpose in en/vi/zh.
- Staging is complete only once `AGENT_LIVE` runs on :8011.

**H. Cutover, only on the human's word.**
- Entry: the human approves staging, D3 has no `MISSING`, AA holds in both themes, rule 49 holds
  at four sizes, the full gate is green, and CI has run on the PR.
- One PR with three commits: move the code; put the new UI at `/` with redirects and new gates;
  remove the old shells with tombstones.
- Tagged so one revert undoes it. No schema change in it, no force-push. `main` is the human's.

**Staging complete is not public release.** EN and ZH need enough real content for the required
E2E runs; content breadth for a beta is a separate gate. "Product content complete" is never
claimed because one item per skill runs.

**Working rules.**
- Each milestone ends with one line: "run staging_update, open :8011/next, press X". One batch of
  questions per milestone; stop only when truly blocked.
- One independent reviewer per milestone, more only where learner data or security is touched.
- At most three parallel agents. Commit and push per item. Long command output goes to files;
  report summaries only.
- Heavy Docker work (full suite, builds, migration rehearsal) never overlaps another lane's heavy
  Docker work.
- From A to G, no standalone polish task. The exceptions are a problem that blocks a D3 E2E, gives
  a learner wrong data or grading, loses persistence or history, breaks auth/security, an agreed
  accessibility gate or rule 49, or has to be fixed to move old logic into a shared module. Other
  polish goes to a backlog.

## D-102 — The product is finished on codex/work and reaches :8000 through main; :8011 deployment deferred

**Date:** 2026-09-29. **Status:** Accepted (explicit human direction). **Amends** D-101's staging
and deployment parts (A, and the "staging on :8011" framing). H1-H10, D2-D7, Admin, Grammar,
Orena and the cutover stand as D-101 says, except where this entry changes them.

**Decision.**

1. **Goal.** The goal is not a separate staging runtime on :8011 kept up through development. The
   goal is to finish the whole product on `codex/work`, test it fully on a local/lane runtime, and
   open a PR from `codex/work` into `main`. After the human merges it, the main runtime is :8000,
   with its existing auth/login and environment configuration. No parallel deployment system is
   built for the new UI.
2. **Before the merge.** `/` and the main runtime are not changed by new-UI work. Development and
   QA of `codex/work` run on the lane's runtime (:8021 or another local port). :8011 is not
   rebuilt or redeployed after each milestone.
3. **Milestone A** is `TOOLING_READY / DEPLOYMENT_DEFERRED`. `scripts/staging_update.ps1` and
   `scripts/staging_backup.ps1` are kept, not deleted. :8011 is not run or migrated unless the
   human asks separately; D2 does not wait for it.
4. **Critical path.**
   1. D2, the shared modules.
   2. D3, the matrix.
   3. D4, one persistence proposal including H2.
   4. E, Admin with real content ingest and publish.
   5. F, real Grammar.
   6. D7, every `MISSING` cell.
   7. G, Orena Intelligence.
   8. Integration QA on `codex/work`.
   9. The PR `codex/work` -> `main`.
   10. After the human merges it, :8000 is updated with migrations under the human's gate.
   11. The old-UI cutover, only when the human says so.

   C runs after D3, when Docker is free.
5. **Testing per milestone.**
   - The relevant automated gates.
   - A browser test on the lane runtime, against the real backend (no fake data on a critical
     E2E), with PostgreSQL wherever persistence is part of the acceptance.
   - The endpoint, storage and reload evidence recorded in D3.
   - The full Docker suite only at checkpoints that are worth it.
6. **Integration QA before the PR.** One pass on the HEAD of `codex/work` proves, in EN and ZH, for
   every non-deferred flow: real content -> learner interaction -> assessment where the domain has
   it -> server persistence -> reload or a new session -> history and progress still there.
   - Flows covered: Onboarding/Profile, Reading, Listening, Dictation, Shadowing,
     Speaking/Pronunciation, Writing, Vocabulary/Review, Grammar, Admin import/review/publish,
     and Orena contextual text chat.
   - D3 has no `MISSING`.
   - Fixture or test data never supports a claim that product E2E is complete.
7. **Runtime :8000 after the merge.**
   - Updated from `main` with its existing auth, login and environment configuration, and no
     parallel secrets.
   - Migrations stay the human's gate, with a backup first, then a smoke test of login and the
     key learner E2E.
   - A migration developed in D4 is rehearsed up/down/up on a throwaway PostgreSQL before the PR,
     not applied to the main runtime during development.
8. **Priority.** No deployment infrastructure, UI polish or small fix unless it blocks a D3 E2E,
   learner correctness, server persistence, the Admin content loop, Grammar production, the
   Orena integration, auth/security or merge readiness.
9. **Progress.** Progress is counted in finished product flows, not in staging deploys or screens
   rendered.

## D-103 — Answers to the D3 decisions: retirements, Dictation, metrics, speech providers, prompts, the Chinese evaluator

**Date:** 2026-09-29. **Status:** Accepted (explicit human direction, on `D3_PRODUCT_MATRIX.md`).

1. **Retirements approved.** The following retire:
   - the old `#/continue`;
   - the old per-skill library rooms;
   - learner-facing R5 grammar routes and the presentation of R5 `grammar_links`;
   - the old Growth Summary;
   - recall modes that have no staging frame.

   Retirement covers obsolete UI and routes only. Reusable domain logic and historical learner
   data are not deleted. Historical R5 ids stay readable for legacy resolution and redirect through
   Grammar Lab provenance and aliases once that mapping exists.
2. **Dictation.** Client-side grading is not `N/A_BY_CONTRACT`. The server is authoritative for
   persisted Dictation evidence:
   - The browser may compute the deterministic score at once, for the learner's experience.
   - Before storing, the server recomputes the score from the learner's answer and the canonical
     target/line identity, reusing the existing deterministic comparison. No AI is involved.
   - Until this exists, Dictation's assess and store cells stay `MISSING`.
3. **Books and pasted texts** are `N/A_BY_CONTRACT` for comprehension assessment in this scope.
   Approved question sets remain the article assessment contract. A source type with no
   comprehension contract shows no Check Understanding entry that only reaches an unavailable state.
4. **Profile and Progress metrics: a real metric or no metric.** An unmeasured value is never shown
   as 0.
   - D4 defines and builds only metrics with defensible semantics and real server evidence,
     deriving from existing records before adding persistence: a real streak, persisted learner
     goals where they apply, and real activity and progress counts.
   - Weekly minutes appear only if duration is genuinely measured; otherwise they are hidden.
   - Achievements, trends and skill percentages have no evidence definition yet, so they are
     hidden until their contract exists.
5. **Speech providers approved for lane E2E testing.** This reuses the existing integrations and
   runtime credentials: Azure Speech Pronunciation Assessment, and the existing ASR provider (Groq
   where the flow needs it). Only the required speech variables are passed to the lane runtime.
   The whole `.env` is never copied, printed or committed. The purpose is to prove Shadowing,
   Pronunciation and Compare end to end.
6. **Writing prompts.** The curated-prompt capability stays. The old prompt choice moves into the
   new Writing Setup, and free or custom writing is kept. The existing material is the migration
   seed, but `content/texts.js` is not the long-term authority: the destination is the Writing
   Prompt Bank under the content architecture.
7. **Chinese evaluator.**
   - The affected review identity is `target_language == zh` and support/explanation language
     `!= zh`. It is not defined as "non-CJK".
   - Unrelated pairs stay on the previous effective evaluator identity, so they are not re-graded.
   - Opening an affected old essay works like this:
     1. Show the stored review.
     2. Call an idempotent POST refresh-if-stale.
     3. The server verifies the pair, the submission identity and the evaluator version.
     4. If current, it returns the stored review with no provider work.
     5. If stale, it re-grades exactly that submission once and stores the result against the
        same learner submission.
     6. The previous review is kept as immutable history and audit evidence.
   - No learner revision is created, and nothing claims the learner rewrote the essay. There is no
     batch re-grade of history.
   - The live Gemini benchmark v2 is approved with a total ceiling of USD 0.50, and EN and ZH
     recall are reported separately. Option (4) waits until those numbers are reviewed.

D4 stays one persistence proposal and one independent review before any learner-data migration is
promoted.

## D-104 — The D4 decisions, the Admin answers and the evaluator option (4)

**Date:** 2026-09-30. **Status:** Accepted (explicit human direction, on
`proposals/LEARNER_RECORDS_D4.md` rev 2 and the Admin slice 1 report).

**D4 (learner records).**
- **H-18, approved.** AGENTS section 7 is amended: these learner-owned records live on the server:
  - drafts;
  - conversations;
  - continuation/place;
  - notes, highlights and annotations;
  - learner-imported private content;
  - the provenance needed to keep where learner content and actions came from.

  Still deferred: the general multi-device sync protocol, receipt compaction, the account-deletion
  runtime, the export format, and Orena conversation/history persistence (unless the Agent
  Contract changes it).

  Storage ownership:
  - `users`: `learning_language`, `interface_language`, `weekly_goal_days`,
    `settings_updated_at`.
  - `user_language_profiles`: `declared_level`, review settings, and settings that belong to one
    learning language.

  There is no generic account-settings table.
- **H-12: Design B.** Continuation/place lives on `library_items`. It is navigation and progress
  state, not learning evidence. `works` continuation with high-volume receipts is not used.
  Migration 0022 is part of D4.
- **H-17: versioned account settings.**
  - `users.settings_updated_at` carries a server-owned conditional (expected-version) update for
    account scalar settings.
  - There is no blind arrival-order last-write-wins, and a client timestamp never resolves a
    conflict.
  - Migration 0018 includes the column.
- **H-11: backbone approved.**
  - `ORENA_ACCOUNT_BACKBONE` is enabled on the lane runtime once the D4 migrations have passed a
    PostgreSQL up/down/up rehearsal and have been applied to that lane.
  - Its default stays off. :8000 is enabled only after the merge, a backup, the migration human
    gate and smoke verification.
- **H-6: no bulk device migration.**
  - There is no "bring this device's work into your account" flow and no silent bulk upload.
  - Legacy device values stay readable where a compatibility path already reads them.
  - New learner state from the finished `/next` flows uses the server. Existing draft sync may
    remain.
- **H-1, approved.** Welcome/setup is required once per learning language whose learner-language
  profile does not exist yet, without replaying the whole onboarding.
- **H-5: a real streak.**
  - No new streak table; it is derived from meaningful, timestamped server-side learning activity.
    Page visits do not count.
  - It is not permanently limited to Reading/Writing/Speaking: every staging skill with equally
    valid server-side completed activity counts, using the domain records available after D4/D7.
- **H-4: quiz result stored.** Grammar progress keeps `last_quiz_correct`, `last_quiz_total` and
  `last_quiz_at` beside the existing completion state.
  - Try-it-yourself results belong to the Writing/evaluator record and are not duplicated.
  - Migration 0023 is part of D4.
  - A future Grammar API validates the published point before accepting progress; R5 is not
    revived as learner authority.
- **H-14, approved.** Legacy Dictation numbers that were not server-verified are superseded by the
  learner's next server-verified result, never rewritten as if verified.
- **H-15, approved.** An old Chinese essay is not refreshed when its stored review identity does
  not prove the original language pair; that identity is never inferred from the current
  profile.
- **H-3, approved.** Reading Transfer is stored as learner work/response, not mastery evidence.

**Admin.**
- **AD-6.** The warning is compact operational status, shown only while it is true: "Saved ·
  learner evaluator still uses legacy routing." It is removed when learner evaluation consumes
  the configured route. Save never pretends to change runtime behaviour.
- **AD-7, approved.** Provider tiles use the shared accent/status tokens; no provider-brand colours.
- **AD-8.** Back to Orena is added: the Admin utility action on desktop, and a compact back action
  in the Admin header on phone.
- **AD-1/AD-2.**
  - Credentials stay write-only, and no last-four characters are stored or shown.
  - Allowed provider metadata: configured / not configured, credential updated timestamp, last
    provider test, latency, last success/failure, and last error where available.
  - Existing audit/test records are reused. No new provider-test-history store is built for the
    UI.

**Chinese evaluator option (4).** Not activated. Measured recall is EN 0.60 and ZH 0.60, which
shows no Chinese-specific deficit and does not show that broadening the prompt helps without
more false positives. The v2.7 fixes stay. Option (4) needs comparative benchmark evidence of a
meaningful recall gain without a material clean-case/precision regression.

**Next.**
1. The D4 proposal and the proposed migrations follow these choices: 0018 carries
   `settings_updated_at`, and 0022 and 0023 are required.
2. The PostgreSQL throwaway up/down/up rehearsal runs.
3. The migrations are not moved to `versions/` or applied to :8000 without the existing human
   gate.

E continues in parallel where it does not depend on D4 schema.

## D-105 — D4 approved for the lane runtime; H-19, H-20; the grammar content path; three Admin answers

**Date:** 2026-09-30. **Status:** Accepted (explicit human direction).

1. **D4 approved on :8021, not :8000.** Migrations 0017-0023 (`migrations/proposed/`,
   independently reviewed and rehearsed, `9ca6c3f`) may move to `versions/` and be applied to the
   lane runtime, one revision per invocation after a backup. The implementation follows proposal
   section 15, and `ORENA_ACCOUNT_BACKBONE` goes on for the lane per D-104 H-11. :8000 is not
   touched until the merge and its own gates.
2. **H-19.** An existing learner-language profile with no declared level gets a level prompt the
   learner can skip. The entry rule stays as D-104 H-1 states it.
3. **H-20.** Grammar completion and the quiz result are written atomically, in one operation.
4. **Grammar content path.** Grammar Lab is upstream: an approved export is imported into the
   database through Admin, reviewed and published there, and learners read it from a published
   grammar API. Content does not ship as JSON with the source code. The grammar content store and
   `/api/grammar/v1/*` go through their own proposal and independent architecture review before
   code.
5. **Admin.**
   - (a) Copyright is a hard gate at Publish: an article whose rights do not allow publication
     cannot be published. This amends the earlier "rights are decision support, never a hard block"
     wording for Reading.
   - (b) For vocabulary publication the server is the authority; the UI states the server's rule.
   - (c) The review queue shows Source, Rights and Target count.

## D-106 — Reading rights in the overview, article-level automation override, the grammar store decisions

**Date:** 2026-09-30. **Status:** Accepted (explicit human direction).

**Reading.**
1. **READING-1.** "Next in review" shows a compact effective Rights status that agrees with the
   Review queue. The full rights form is not duplicated there.
2. **READING-2.** A source's `automation_allowed` is a default, not the only authority. An article
   may carry a reviewed override. The effective value is the article override when present,
   otherwise the source default. Publish uses the article's effective value, and overrides are
   audited.

**Grammar content store** (`proposals/GRAMMAR_CONTENT_STORE.md` rev 2, section 17):
1. The model is approved: content in the DB, immutable versions, authored only upstream, publish
   an explicit act.
2. Approved: an explicit `r5_map`; the canonical JSON/hash rule; an R5 alias sits on the primary
   point only, and split secondaries use `source_refs`.
3. Batch atomicity is approved as proposed.
4. A merged R5 point is complete only when **all** aliased R5 lessons are complete.
5. No reviewer separation for now. Import, accept, rights and publish stay four separately
   audited acts.
6. The hard rights gate is approved.
7. Publish is refused while a published reference would dangle.
8. `jsonschema` is used, with a derived single-version export-profile schema from the merged
   Grammar contract. The current multi-version upstream schema is not vendored verbatim.
   Upstream-drift and golden-vector tests are added.
9. The progress endpoint `PUT /api/grammar/v1/progress/{id}` and manifest-only retention are
   approved.
10. Re-importing an already rejected content hash is refused; upstream must change the content.
    Grammar-store implementation waits for the required merged contract (PR #67).

The reviewer's N-1..N-6 are carried into implementation without reopening these decisions. For
unavailable or dropped Grammar responses the learner UI uses the existing not-found shape; no new
learner landing is invented.

## D-107 — D4 accepted on the lane runtime; delete-import UX; separate media-import limits; merge forward to Intelligence

**Date:** 2026-10-01. **Status:** Accepted (explicit human direction).

1. **D4 lane acceptance is PASS** on :8021 (flag-on browser QA round 2 at `9a7b190`, all six flows). The
   D4 account backbone is the accepted development baseline. `ORENA_ACCOUNT_BACKBONE` is not enabled
   beyond :8021.
2. **Deleting an import.** Canonical place: My Library -> imported item -> overflow menu ->
   "Delete from Orena"; the same action in the imported item's Content Detail overflow menu. No
   destructive delete directly on Discover. Deletion removes the import from the learner's library,
   propagates a tombstone across devices, prevents a stale device from resurrecting it, deletes owned
   uploaded media files, keeps only integrity/audit metadata, and never touches the learner's
   original external source. A device that has learned of the deletion stops opening a stale cached
   copy (promoted from P3 to production P2).
3. **Media-import limits.** Media imports use a pool separate from text imports; text, URL and upload
   imports do not all consume the `20 live / 360 total` text-import limits. Three rails: text-import
   limits, a media-import item count (URL/YouTube and uploads share it), and an uploaded-media
   storage-byte limit. Defaults are proposed from the limits proposal's measurements and storage
   estimates, not chosen arbitrarily. An import that cannot sync because of a quota is never shown as
   saved to the account; if local-only fallback remains, that state is shown to the learner explicitly.
4. **Follow-up priorities.** Production P2: a cached deleted import usable after the deletion has
   synchronized; Listening saved-word provenance missing (must converge with Reading provenance).
   P3 stays: Conversation End state, draft conflict chooser, mic-blocked Free Talk copy, an open page
   showing a removed highlight until reload, the hard-coded media thumbnail temp path.
5. **Rollout gate beyond :8021.** The limits implementation completed and approved after measuring
   draft autosave behaviour; delete-import UI and lifecycle implemented; uploaded-import deletion
   removes owned media files; code and migrations 0017-0023 deployed together after a backup; the
   relevant acceptance checks rerun.
6. **Merge.** `codex/work` may be merged forward into `feature/orena-intelligence` and reconciled and
   tested there. Intelligence is not merged back into `codex/work`, and `codex/work` is not merged into
   `main`, until Intelligence tests/E2E and an independent review pass on this D4 baseline.

## D-108 — Delete import with Undo; what a deletion keeps; verified scores only; no local-only import under sync; media metadata in PostgreSQL

**Date:** 2026-10-01. **Status:** Accepted (explicit human direction).

1. **Undo, not a confirmation.** "Delete from Orena" takes effect with an Undo, never a confirmation modal.
2. **After an import is deleted:**
   - the source content is gone;
   - notes and highlights attached directly to that source are no longer served;
   - learner history (Dictation, Shadowing, progress) is kept;
   - saved words are kept, with their source marked deleted/unavailable;
   - a stored excerpt is never used to reconstruct the deleted content.
3. **Unverified dictation scores are hidden entirely.** Only a server-verified score may be used or repeated
   by the Agent.
4. **No local-only import while account sync is on.** An import the account does not accept is not kept on
   the device as a substitute.
5. **Media metadata authority.** Long term, media metadata uses PostgreSQL as its authority; the shared
   media file (`index.json`) is not a writable source of truth.
6. **Import listing paginates.** It is never silently limited to 50.
7. **Separate quotas** for text imports, media item count and uploaded-media bytes (confirms D-107.3).
8. **Merges.** Intelligence is not merged into `codex/work`, and `codex/work` is not merged into `main`, yet.

## D-109 — The completion target is a complete, usable product, not deeper infrastructure hardening

**Date:** 2026-10-01. **Status:** Accepted (explicit human direction).

Orena is product-complete only when the content/admin side and the learner side exist as one connected
system, in English and Chinese as equivalent products.

1. **Content / Admin.** Books and reading content, listening media (audio, video, YouTube), vocabulary
   collections, Grammar (canonical catalog -> generation -> validation -> review -> publish -> learner runtime)
   and practice material generated from published content all enter, are processed, reviewed when needed,
   published and reach learners without code changes. AI-generated content flows automatically where
   confidence is sufficient; human review only where needed. Failed jobs are visible and recoverable. Admin can
   see what is unpublished, invalid, waiting for review, failed or live. The learner library feels populated,
   not like demo cards.
2. **Learner.** Complete loops for Listening, Speaking, Reading, Writing, Vocabulary/Recall and Grammar, and one
   Progress/Continue state across skills, with no unfinished system boundaries in a normal session.
3. **Connected system.** Words met in Reading/Listening feed Vocabulary and review; grammar weaknesses seen in
   Writing/Speaking connect to Grammar; imported content serves several activities; progress and attempts
   persist across sessions; Orena Agent understands current content, language and meaningful history.
4. **Orena Agent** is complete when it enhances the finished learning system inside each skill without a
   competing source of truth.
5. **English / Chinese** stay equivalent: same layouts and journeys, with Chinese-specific mechanics (characters,
   pinyin, classifiers, particles) where needed.
6. **Definition of done.** Learner: discover content, learn, practise, get useful feedback, save state, return,
   continue, see progress. Admin: introduce or generate content, validate/review where needed, publish, and see
   it usable by learners without editing code. Passing tests alone is not completion.
7. **Priority.** Infrastructure hardening, rare races, migration polish and unusual multi-device edge cases are
   secondary unless they cause data loss, a security/ownership problem, failure of a normal learning journey or
   failure of the content publishing journey.

## D-110 — The final target of Orena (source of truth for current and future planning)

**Date:** 2026-10-02. **Status:** Accepted (explicit human direction). Extends D-109.

Orena reaches a complete language-learning product with real content, usable immediately, before it goes public.

1. **Learner product.** Today / Discover / My Library are the main entrances. Content is the centre; Reading,
   Listening, Speaking, Writing, Vocabulary and Grammar are capabilities around content, not separate modules.
   A learner can discover content -> learn -> practise -> get feedback -> save progress -> return and continue ->
   see progress. Reading, Listening, Speaking, Writing, Vocabulary/Recall, Grammar, Continue and Progress each
   have a working E2E journey. History, Speaking Summary, Overview, Rank, From Your Errors and every progress
   surface reflect server data and are never empty when data exists. Books, articles, media and imported
   content open and can be studied normally. Media used as a lesson has a usable transcript. Grammar has a real
   store, API and content for EN and ZH. Orena Agent understands the current learning context and supports the
   finished learning system.
2. **Library before public.** Orena does not go public with a demo or thin library. EN and ZH each have reading
   content, listening/media, books/long-form, vocabulary collections, a grammar curriculum and practice
   material, across several levels, topics and content types. Discover and Library feel like a real world of
   content.
3. **Admin is Orena's control center.** It shows usage, engagement, learner activity, progress, content usage
   and operational health; what is live, in review, invalid, processing or failed; manages Books, Reading,
   Media, Vocabulary, Grammar and Practice; supports the content lifecycle from source/import/generation to
   publish/archive; supports growing the library after public; adding and managing content needs no code change.
4. **Content supply.** source/import/generation -> processing/enrichment -> validation -> review when needed ->
   publish -> learner use. Content that meets the quality and rights gates may flow through automatically;
   content that fails a quality or rights gate goes to review.
5. **Product-complete means:** real content to learn at once; no main journey ends on an empty screen or an
   unconnected capability; EN and ZH are both real products; Admin can operate and grow content; the library is
   thick before public; normal-journey defects such as Books 503, media without a transcript, progress empty
   despite server data, and Grammar without a runtime no longer exist.
6. **Priority.** Rare edge cases, migration polish and infrastructure hardening do not decide completion unless
   they cause data loss, a security/ownership issue, or break a normal learner or Admin journey.

## D-111 — Auto-publish rule, library sources, media transcripts, Grammar build, Admin Overview, lane budget, durable lane store, leftovers, Agent gate

**Date:** 2026-10-02. **Status:** Accepted (explicit human direction). Answers the D-109 audit questions.

1. **Auto-publish.** Yes, without self-declared AI confidence. Content auto-publishes when its rights are cleared
   and the deterministic schema, semantic and content validators all pass. Question sets auto-approve when the
   grounding, answer and duplicate validators pass. Any failure, or unknown rights -> review queue.
2. **Library sources.** Public domain, owned, licensed, explicit permission, and sources/APIs with clear usage
   rights. Learner-imported private content never becomes public catalog. Bootstrap target per language:
   30 Reading + 20 Listening + 10 Vocabulary collections, with a sensible level/topic spread. Rights are decided
   at source policy where possible; texts from an already-cleared source are not re-approved one by one.
   Unknown rights -> not published.
3. **YouTube / media.** Public captions first; when missing or not good enough, speech recognition on the audio.
   Paid fallback allowed within the spending cap. Media is not published as learning content without a usable
   transcript; it stays draft/processing until it has one.
4. **Grammar.** The Grammar Store/API architecture is approved to build. PR #67/#68 may merge when their current
   reviews/gates pass; no parallel Grammar system. Chinese comes from the canonical HSK/GF catalog through the
   generation/validation pipeline, not hand-written point by point. The old 269 EN / 239 ZH lessons stay retired
   from the learner UI, usable only as reference/migration source.
5. **Admin Overview: build now.** The Admin Content Engine is core product and must show live / review / invalid /
   failed / processing.
6. **Lane spending cap (:8021).** AI enrichment at most $10 per batch, speech recognition at most $5 per batch,
   all automatic processing at most $25 per day. No unlimited background spend. Production budget is set after
   real usage.
7. **:8021 file store** is durable development/QA storage and must survive normal restart/recreate; it is not the
   long-term production authority. The Books chapter 503 is a normal product bug to fix.
8. **Test leftovers.** Archive the 18 Bridge articles, the 14 review test items, the tone/clip imports and other
   test content from the learner-facing library. Keep evidence in QA reports; one failed-job example may stay in
   Admin for Operations testing.
9. **Agent.** Grammar does not block the whole Agent. The provider gate can open once the core content journeys
   and Progress/return state work correctly. Grammar-specific Agent capability turns on after the Grammar
   API/content is ready.
## D-112 — Product completion requires the full UI/flow inventory and integrated Intelligence

2026-10-02, explicit human instruction. The accepted handoff is preparation, not delivery.
Every important element/action/state/transition in the current new Orena learner and Admin spec
must work in the browser or show an explicitly truthful unavailable state. Completion includes
Orena Intelligence, its existing reconciliation work, and Orena Agent together: real learner
context/evidence, recommendations, Today/Practice routing, From Your Errors, targeted practice,
WHY/HOW and Progress/contextual explanations. They reuse existing learner-data authority;
account/language scope and deleted-source boundaries hold. No invented learner history, scores,
weaknesses or fake personalization. General/unavailable states are honest fallbacks, not evidence
of completed personalization. Desktop/mobile and EN/ZH browser journeys are required after each
slice. A substantial real validated EN/ZH content library is required before public release.
Truthful Progress → Books learner verification → transcript-backed Media remain the next slices,
not the complete program. Paid-provider/public-deployment gates are unchanged.

## D-113 — Reconcile current execution authority with Product Completion

2026-10-02, explicit human instruction. ROADMAP owns the current coherent content-first
Product Completion program; R21/mobile-first execution and separate Writing → Speaking →
Reading → Listening public-release sequencing are historical, explicitly superseded as current
instructions. Native remains frozen. Preserve historical decisions and evidence unchanged.
The Product North Star, content model and pinned UI/Design Contract keep their existing domains;
PROJECT_MEMORY routes precedence, machine state records verified truth, handoff active position,
and ORENA_STATUS capability state. No additional product-authority document is created.
Public readiness requires the new UI as the actual product, full connected learner/Admin journeys,
integrated Intelligence + Agent, truthful evidence and substantial real EN/ZH content. Individual
skill/backend/test completion is insufficient. D-110–D-112 decisions remain settled. Continue
valid unfinished implementation immediately after reconciliation, using actual browser evidence.


## D-114 - Basic whole-product coverage before deep refinement

2026-10-02, explicit human instruction. Continue preserved Listening/Media on codex/work;
do not reopen accepted Books/Progress or restart a full-app audit. Complete normal
browser-usable EN/ZH Listening with real imports/transcripts and its existing connected
practice/context paths, truthful unavailable states, then move to the next major basic gap.
Complete basic functional coverage of the full approved learner/Admin UI before deep
fidelity, cross-device completeness, edge cases, performance or infrastructure refinement.
Data safety, ownership/security and normal journey blockers still take priority. This
supersedes stale NEXT instructions to deepen Books/Progress, without rewriting their evidence.

## D-115 - Listening support meaning and visible AI processing

2026-10-02, explicit human instruction following the B0p5SdkBydU import report.
Support-language translation is a core Listening journey, not optional enrichment
that can be declared complete while missing. A wait exceeding 2-3 seconds needs
a visible processing state. When source transcript/translation is absent and a
paid service is required, disclose Orena's AI processing and resource use.
Disclosures must reflect real processing stages/provenance; cached/editorial,
same-language and local-provider paths must not falsely claim a paid API action.
Orena Agent/Intelligence activation and existing provider/budget gates remain unchanged.

## D-116 - Listening correction and application-wide truthful loading

2026-10-02, explicit human correction. Supersedes D-115's user-visible paid-service
disclosure wording only: say Orena AI is processing; never mention paid APIs in
the learner wait screen. Provider/budget gates remain in force. Apply visible
loading and a progress bar across the app for waits beyond 2-3 seconds; known
stages show actual step progress, unknown duration stays indeterminate, never
invented percent/time. Dictionary meaning, pronunciation and Chinese stroke
support belong to lookup. Word highlighting requires genuine word timestamps;
segment timing is not word evidence. Practice handoffs reuse scoped media and
support meaning, and long learning text must fit/wrap within its workspace.

## D-117 - Admin reconciliation under nonpublic Product Completion

2026-10-03, explicit human instruction. Preserve completed admin/control-center
credential security and capability configuration. Missing sandbox encryption key
is provisioning; LEGACY is deferred activation, not missing UI implementation.
Reevaluate historical activation holds against operating the current nonpublic
Product Completion runtime; they must not automatically obstruct supported Admin
journeys. This does not authorize production/public routing or credential exposure.
Admin completion requires actual operator journeys in all six approved areas;
unsupported controls must be unavailable. Stop deepening basic-complete areas
and return to the remaining basic app gaps; hardening follows broad coverage.

## D-118 - Azure Admin scope and approved Visual Skin supplements

2026-10-03, explicit human direction: complete both Azure Speech and Azure
OpenAI configuration/runtime using existing Admin security and supported domain
adapters. This does not activate production/public routing or reserved speech
capability pickers.

The supplied Visual Skin EN (requested as “Orena Visual Skin (2).html”) and ZH
exports own visual language, palette/accent and light/dark treatment. Existing
screen-specific canonical prototypes retain composition/layout/interaction.
ZH keeps product parity with its typography/content treatment. Outdated skin
logos, marks, icons and artwork are excluded; approved brand assets always win.
Update the existing Design Contract, never a competing authority document.

## D-119 - One media Shadowing / Pronunciation learning flow

2026-10-03, explicit human instruction supersedes the separate simultaneous
Shadowing interaction: usable transcript-backed video/media offers Listen and
Shadowing / Pronunciation. Practice selects a real segment, hears its source
model, records, receives assessment, compares and retries in one shared runtime.
It is not restricted to a seeded sentence or separate Speaking catalogue.
Old Shadowing/Pronunciation links preserve the chosen segment and use this runtime;
Listening return preserves that segment. Unsupported transcript, timing or pitch
remains truthful. Composition reuses canonical Pronunciation/Compare components;
Visual Skin EN/ZH owns treatment, approved brand remains unchanged.

## D-120 - Original media voice remains the pronunciation model

2026-10-03, explicit human decision: media Shadowing / Pronunciation uses only
the original video voice. Do not replace an unusable source excerpt with generated
speech or present synthetic timing/pitch as original evidence. A line that cannot
be prepared has a truthful learner-facing state and another-line/retry action.

## D-121 - Content readiness precedes learning; reusable source work is materialized once

2026-10-03, explicit human instruction repairing the imported-media Shadowing
regression. Import/preparation happens at the content boundary; learning happens
after readiness. Required source artifacts use stable content/revision/kind/
language/config identity and existing storage/execution owners, are materialized
once and reused across capabilities and returns. Navigation cannot acquire,
transcribe, translate, synthesize or assess the source again. No blanket provider
fan-out during import. Canonical original segment playback is Shadowing's model;
separate segment audio is prepared only when genuinely required, before admission.
New learner recordings/responses/questions remain legitimate new compute.

Content Architecture §7.1 and Content Execution Architecture §3 own the contract;
Design Contract carries only the workspace consequence. Shared Media Learning
remains the media owner. This supersedes D-120's source-preparation retry inside
learning, while preserving its original-voice rule, rights/access gates and truthful
unavailable optional measurements. It authorizes no new schema or retention policy.


## D-122 - Pronunciation chooses content; phone web defines the future native reference

2026-10-04, explicit human correction: generic Pronunciation entry offers content
choice rather than silently assigning the first catalogue item. Reuse Discover's
approved cards/search/filter/import patterns with practice intent; selecting or
changing media returns directly to shared Shadowing / Pronunciation, preserving
the segment when the same source is chosen. Authored sentence lessons remain
addressable; contextual recommendations and resume links keep their named source.

Phone web is the review reference for future native layout and learning flow.
The selected media and line are clear; the sentence/readings/meaning own the main
space, with balanced controls and Hear/Record in view. The original embedded
video is revealed while playing on phones, without replacing or preparing it.
Initial positioning never autoplays. Existing canonical components and semantic
tokens remain the design vocabulary. Native remains frozen; this changes neither
Shared Media Learning nor D-121's preparation/readiness boundary. Human product
approval still follows browser review.

## D-123 - Listening practice separates comprehension and Dictation

2026-10-04, explicit human correction and confirmed grouping: the Listen group
offers Listening comprehension (Nghe hiểu) and Dictation (Chép chính tả), each
with content choice. Speaking has one Pronunciation entry, whose media practice
is shared Shadowing; remove duplicate cards. Canonical Follow remains the media
exploration workspace, not a second pronunciation entry.

Comprehension listens to original media, answers admitted source-bound questions,
then shows checked answers and evidence. Persist reusable question derivatives
through the existing catalog/shared-content owner before offering this mode;
never generate them on entry. Questionless imports retain other ready modes.
This is not a claim of licensed TOEIC exam content. D-121 readiness and shared
media identity remain binding. Session results add no learner persistence or
mastery model. Native remains frozen; product approval requires human review.

## D-124 - Vocabulary is localization of one sense, not AI enrichment

2026-10-04, explicit human instruction (two messages, replacing a rejected proposal to batch
`learner_dictionary` over every vocabulary import). Vocabulary is canonical sense → meaning in
the learner's support language → card/SRS. A sense exists once; localized meanings are
separate reusable records keyed by (sense, support language); `meaning_vi` / `translation_vi`
is one localization, never the meaning model. Adding a support language is "add a
localization source, materialize glosses", not a product-code change, and duplicates no corpus.
Lifecycle: import → normalize/sense identity → localize → validate → persist → publish →
render; learner use after publication is read-only and costs zero provider tokens. Sources are
deterministic/open lexical data first, then free/offline translation infrastructure where
direct bilingual data is missing; no paid model in ingestion, localization, publishing,
opening, review or SRS. No decorative generated card content. Contextual AI explanation stays a
separate learner-requested capability. This applies the cost plan's rule 1 and implements its P1
(CC-CEDICT + Unihan vendored, CC BY-SA 4.0 / Unicode licence, named in data provenance;
visible learner attribution is an open pre-release gate). Schema:
`proposals/VOCABULARY_LOCALIZATION.md`; its table needs independent review and authorization
before promotion. Native frozen; product approval still follows browser review.

## D-125 - Orena agent live on the lane runtime :8021

2026-10-04, explicit human instruction after PR #69 (Orena Intelligence, dark merge): the agent is
switched on at the lane runtime :8021, not :8011 (deferred by D-102), superseding D-101 G's choice
of runtime only. `AGENT_ENABLED` on the server is the per-environment switch; the client follows
`GET /api/agent/capabilities` (404 hides Orena) and keeps the contract mock for forced review only.
Checked in full against contract v5 (capabilities, SSE turn, 409, 429 with Retry-After,
`context.address`, actions as invitations, opening turn from real data, `tool_call` labels).
Production and public activation remain human gates.

## D-126 - Agent contract id conventions: Grammar Lab ids and one content-id namespace

2026-10-04, explicit human instruction closing INTELLIGENCE_RECONCILIATION_D4 F-3 and F-9 on the
UI lane. F-3: `grammar_id` in the agent contract is a Grammar Lab point id (D-100); an R5 Concept
ID is never sent or emitted, and until the canonical Grammar Store/API serves points the UI leaves
`grammar.point` out of `supported_intents`. F-9: `content_id` is `<kind>:<id>` (`article:`,
`book:<id>:<chapter>`, `media:`), one namespace for UI context and agent payloads, owned by
contract §6.1; tools may accept a bare id from an older client, never emit one. Contract v5 text
clarified, no version bump (no id added or renamed).

## D-127 - Runtime roles: :8000 is the local product, :8021 the lane's dev runtime (supplements D-102)

2026-10-04, explicit human instruction. Supplements D-102; its merge path stands.

1. **:8000 is the product, run locally.** It behaves exactly as the product will: real Google sign-up
   and sign-in, real content added through Admin, payments in test mode, learning as a real user.
   When everything passes on :8000, the whole system moves to a VPS.
2. **:8021 stays the lane's development runtime.** It holds only the test-sample set used to check
   functions (labelled sample sources, D-111 flows). Real content is loaded on :8000 only.
3. **No lane touches :8000.** Only the human updates it, through a PR `codex/work` -> `main`. No lane
   restarts Docker either: :8000 runs on the same engine.
4. **Completion plan additions.**
   - A safe :8000 update: backup and restore scripts for the database and the file directories, a
     migration rehearsal on a copy of :8000's data before the real run, and a check that both the
     database and the files sit on persistent volumes.
   - Billing, only after the technical and security review: a payment gateway suited to a Vietnamese
     merchant, in test mode on :8000 through the existing domain. It covers plans, entitlements per
     account (quota), renewal, cancellation, refunds and signature-checked webhooks, with the
     per-feature cost report for pricing.
   - Terms of use, privacy policy and refund policy pages, with content approved by the human.
   - A VPS runbook: production environment variables and secrets, Google OAuth and webhook return
     addresses on the new domain, DNS/Cloudflare, HTTPS, backup and restore, monitoring. It is
     rehearsed by restoring a :8000 backup into a fresh environment.
   - Content pack export/import in Admin, to move content between environments.

## D-128 - Admin pages the design does not draw are built from existing kit blocks

2026-10-04, explicit human instruction (completion plan, decision 2): the Admin AI-cost page and the legal
pages (terms, privacy, refund) are built from the existing kit components, with no design frame. The UI lane
applies the same rule to the Admin content-pack page (export/import, item 2 of the plan) and lists it here for
the human to confirm. Such a page uses only existing kit blocks and copy in en/vi/zh, invents no component,
and is named in `scripts/test_orena_screen_admin.mjs` KIT_PAGES with its reason. Every other Admin page stays
on the pinned design (D-067).

## D-129 - "Done" for a learning skill includes matching the design step by step; the human approves

2026-10-05, explicit human instruction. The human tested the learning skills against the pinned prototype and
found them unlike the design: different steps, and components the agents added that the prototype does not
draw and that do not follow the Visual skin. D-109's audit scored "works" by function, not by design.

1. **Done means both.** A learning skill is done only when it works *and* matches the pinned design step by
   step:
   - the same screens, in the same order;
   - the same states (empty, in progress, result, error);
   - the same actions and the same transitions;
   - only components the prototype draws, in the Visual skin.
   Function alone is not done; D-109's "works" verdicts are not design verdicts.
2. **Priority, in this order.** First the learning skills, one at a time: Reading → Listening (with Dictation
   and Shadowing) → Speaking/Pronunciation (with Free talk) → Writing → Vocabulary/Review → Grammar. Then the
   cross-skill flows the design draws, including Orena's contextual entry points. Onboarding waits. Billing,
   legal pages, VPS, the :8000 update and the operator content guide stop at their current gates.
3. **Method, per skill.**
   - Walk the prototype as a learner and write a scenario: the screen, state, action and transition of each
     step, with a screenshot of each step.
   - Walk the same scenario on :8021/next with sample content, with screenshots.
   - Tabulate every deviation, classified as: missing step, wrong order, component not in the design, wrong
     Visual skin, missing state, or different behaviour.
   - Send the table, then fix. A component the prototype does not draw is removed; where the design does not
     draw something, ask the human, never invent.
4. **The human approves.** Each skill ends with its scenario sent to the human, who walks the prototype and
   the app side by side. The next skill starts only after the human's approval. The human is the final
   approver of "done" for every skill.

## D-130 - Reading: translation, summary and contextual meaning are generated on request and cached; no fake XP; description is its own metadata

2026-10-05, explicit human decisions on the Reading deviation table (D-129 batch):

1. **Translation**, in the Reader aid and the Sentence Quick Sheet, is kept. It is generated by AI on the
   learner's first request and cached and persisted, so a text is never translated twice. The two places
   share one source and one cache. A provider error shows a short retry state; it never says the feature
   does not exist.
2. **Summary** is generated only when the learner opens it ("Generated on request"), once, and is then
   cached and persisted with a loading state. It is never generated just because an article was opened.
3. **Word Quick Sheet**: the meaning of the word in this sentence is the primary information, with the
   general dictionary meaning secondary. "Why here?" explains briefly why the word has that meaning in this
   sentence, and is generated on request and cached. No "ask Orena" deferral for something the sheet itself
   offers.
4. **No XP system** is built to match the mockup. The completion overlay keeps the design's layout with real
   learning figures (for example "2/5 correct · 0 new words · 1 min"). A point system is connected later, if
   one is ever made official.
5. **Description** is separate content metadata, provided by an administrator. The block is hidden when
   there is none; the first lines of the text are never presented as a description.
6. After the current Reading batch, issues come from the independent Learning Experience Reviewer
   (`docs/UX_REVIEW_LOG.md`). The UI lane takes only `READY_FOR_FIX` and `REOPENED` issues, moves them to
   `READY_FOR_VERIFY`, and never marks them `VERIFIED`.
7. **Live AI**: no live provider call without the provider lock. Data or cache is used for QA where
   possible, and every on-demand feature caches its result.

## D-131 - Reading Aids are icon-first toggles (design adaptation, LEX-009)

2026-10-05, explicit human decision on UX review LEX-009. Frame 14 draws the Reading Aids (support-language
meaning, vocabulary lens, word roles, pinyin) as four equal-weight text pills. The independent Learning
Experience Reviewer found them word-heavy and tall: they wrap to two rows on a phone. The human chose the
Reviewer's direction over the frame. This is a recorded design adaptation, not a precedent for other pills:
- each aid is an icon toggle with a clear filled active state and `aria-pressed`;
- Lucide icons come from the pinned package: `languages`, `scan-text`, `tags`, `case-lower`;
- a short caption sits under each icon on every breakpoint (the Reviewer's follow-up: one strategy, not
  hover-only on a desk), and the full name is the tooltip and the accessible name; the row stays one line;
- an aid that cannot apply to the text is not shown (pinyin for an English text).

## D-132 - A word nobody recorded is spoken by Azure neural TTS, once, under a 5 USD cap (LEX-010)

2026-10-05, explicit human decision on UX review LEX-010.
- **Commons first.** Recordings on Wikimedia Commons stay the first source.
- **Azure second, once.** A word with no recording is synthesised by Azure neural text-to-speech on the server
  (the paid Azure account), once. The audio is stored under the word's (identity, reading) key and played from
  storage afterwards; Azure is never asked again for that reading.
- **Chinese is told its reading.** The dictionary's tone-marked pinyin becomes SSML `phoneme` (numbered tones),
  so a character with several readings is said as this entry means it. Checked on 行, 长, 了, 还 and 得.
- **Spending.** Total cap 5 USD for word audio (`word_tts`, `WORD_TTS_SPEND_CAP_USD`), recorded in the AI
  ledger. The actual cost is reported after each batch.
- **Device voice is the fallback only.** It is used only when Azure fails, is offline or is at its cap, and it
  is labelled as the device's voice.
- **The learner sees the source:** a recording and its author, a synthesised voice, or the device's voice.

## D-133 - Reading friction decisions: notes as badges, icon Aids, Visual Skin stroke panel, common meaning

2026-10-05, explicit human decisions on UX review LEX-014, LEX-015, LEX-016 and LEX-018. Each one departs from
the pinned frame where the frame draws otherwise.

- **LEX-014 notes.**
  - At rest, a note is only its number at the sentence.
  - Tapping the number opens the frame's note card (the note, its sentence, "Edit in sentence"). Its head or
    the number folds it back.
  - The always-visible collapsed preview row the frame draws is not used.
- **LEX-015 Aids.**
  - The Reader's aids are named by icons the prototype draws (D-088's Lucide set), not by the word "Aids".
  - The trigger is the lightbulb with the number of aids on. Its accessible name and tooltip are
    "Reading aids · n".
  - The vocabulary lens uses whole-word, replacing the lane's own scan-text.
  - Where the prototype has no icon for a function, the closest one it draws is used.
- **LEX-016 stroke panel.**
  - The character selector and the three actions take the Visual Skin ZH stroke component's treatment:
    - neutral surface2 tiles with a border2 ring;
    - the practised character in full ink;
    - Watch strokes as the skin's secondary "Show stroke order";
    - Write it as tertiary;
    - Next character as ghost.
  - There is no default purple-outline control.
- **LEX-018 common meaning.**
  - The Word Quick Sheet shows the word's common meaning, in the support language, under "Meaning here".
  - It comes from the same short gloss call (`common_meaning`, cached with it); otherwise from a dictionary
    sense in the support language. It is never an English sense shown to a learner with another support
    language.
  - WordDetail gains `generalMeaning`; the pinned contract file is unchanged (UI_BACKEND_GAPS, RD-4).

## D-134 - Pinyin over Hanzi: words set apart, readings smaller, characters evenly spaced (LEX-019)

2026-10-06, explicit human decision on UX review LEX-019. It departs from frame 14's pinyin measurements, which
the Reviewer found hard to read even when matched exactly.

- With pinyin on, each word is one group whose columns share the width of its widest reading. A word's
  characters therefore stand evenly spaced, and each reading stays over its own character.
- Words are set apart by a small gap (0.3em), so word boundaries read in both the pinyin row and the Hanzi row.
- Pinyin is max(10.5px, .58em), below the frame's max(12.5px, .64em), with 1.5px either side. Two readings'
  letters are always at least 3px apart.
- Hanzi stay primary. Every word cue (kept word, key word, word type, highlight) stays on the Hanzi.

## D-135 - Orena's offer sentence is in the support language; My Library is offered only for a word that is in it

2026-10-06, explicit human direction on UX review LEX-006. It amends the 2026-09-28 practice of writing the
server's offer copy (learner_copy offer.*) in the interface layer.

- **Language.** The sentence that offers an action, such as "Bấm My Library để mở từ này", is support-layer text
  addressed to the learner. It is in the support language, like the rest of the reply. The button's `label` stays
  interface layer (D-080), and when the sentence names the button it quotes that label as the learner sees it.
- **My Library.** A `navigate` to My Library about a word, and any offer to open it there, is given only when the
  word is actually in the learner's library, as a tool read confirms. A word not saved gets no My Library button
  and no offer to open it.
- AGENT_CONTRACT §7 states both rules. The Intelligence lane implements them.


## D-136 - Reading flow approved under D-129; Listening is next

2026-10-06, explicit human approval.

- **Reading is approved.** The Reading flow matches the design step by step (D-129).
  - The Learning Experience Reviewer's final batch (UX_REVIEW_LOG.md, "Independent live verification", HEAD
    ce747d5) is UI VERIFIED with Experience PARTIAL.
  - Every UI issue LEX-003..LEX-028 is VERIFIED.
- **Still open, not blocking the approval:**
  - LEX-020: independent listening evidence for Word Detail pronunciation.
  - LEX-011: the original unavailable-branch locale, which no longer reproduces naturally.
  - Error-only branches not independently exercised: Summary Retry, the 45 s and 90 s timeouts.
  - Content items LEX-001/002, deferred to Admin-managed content.
- **Next:** the Listening flow, including Dictation and Shadowing, with the same D-129 rule (step-by-step design
  match, human final approval).

## D-137 - Listening flow decisions on the D-129 audit (L-01, L-02, L-11, L-13)

2026-10-06, explicit human decisions on the Listening audit.

- **L-01: two modes.** The Listening workspace keeps two modes, Listening and Shadowing (D-119). Frame 06's third
  tab, "Active", is not restored; the line actions stay behind "Work on this line". Hints name the modes the switch
  shows.
- **L-02: Compare room.** Shadowing stays the shared Pronunciation/Compare room of D-119 rather than frame 28's
  card.
- **L-11: suggested words.** When a line has no curated focus vocabulary, Vocabulary Focus suggests a few words
  from that line at the learner's own level, instead of an empty state.
- **L-13: estimated word timing.** Word highlight is completed, not skipped. Without verified word timestamps it
  highlights by estimated timing within the line and is labelled "· est." as the frame draws it. With verified
  timings it uses them and drops "est.".

## D-138 - Orena voice is a live conversation; spoken replies unlocked on phones

2026-10-06, explicit human direction ("Orena không có chức năng live talk và nó cũng đang chưa phát ra tiếng được").

- **Live talk.** Once the learner starts voice mode (the mic in the Home composer or the Contextual panel), Orena:
  - listens, and ends the turn itself when the learner stops speaking (a pause of about 1.3 s);
  - answers aloud;
  - listens again;
  - pauses after about 9 s with nothing said.

  Tapping Stop while Orena speaks or thinks ends the conversation; tapping while it listens sends at once. This
  replaces the frame's one-turn voice cycle (speaking, then idle).
- **Same contract.** It is the existing cascade: record, `POST /api/speech/transcribe`, an ordinary agent turn,
  then device speech. No real-time voice session (AGENT_CONTRACT §9) is built or called; that stays the
  Intelligence lane's.
- **Spoken replies on phones.** Mobile Safari speaks only from inside a tap. The learner's first tap on the mic or
  a suggestion unlocks device speech for the visit.
- **Recording format.** A recording's upload name follows the format the device recorded (an iPhone records mp4,
  not webm).

## D-139 - Speaking flow decisions on the D-129 audit (HD-1 to HD-14)

2026-10-07, explicit human decision on `docs/reviews/SPEAKING_DESIGN_AUDIT.md` ("theo đề xuất"), plus one
addition for Attempt History.

- **HD-1 Recommended (S-01).** Skill Hub Speak shows the Recommended card from the learner's weakest real attempt
  (line or mode) with its real reason; no card without attempts.
- **HD-2 hidden modes (S-04).** Of the modes the design draws and the app does not build, only Shadowing is
  offered, opening the shared D-119 room through the media chooser. The rest stay hidden (D-101 H9).
- **HD-3 Pronunciation entry (S-05).** Pronunciation opens the learner's last line directly; "Choose media" sits
  behind "…". The chooser opens directly only when there is no last line.
- **HD-4 source bar (S-08).** Previous / Next line at the bottom as frame 28; the line list and "Choose media" in
  a sheet behind "…".
- **HD-5 IPA and stress hint (S-10).** IPA from the assessment provider's phonemes where it returns them; the row
  is hidden otherwise (no dashes). Chinese keeps pinyin.
- **HD-6 translation line (S-11).** The meaning is revealed on tap, not shown by default.
- **HD-7 Attempt history in Compare (S-13).** The embedded Attempt history card is added as drawn.
- **Attempt History review (human addition).** Choosing an attempt in Attempt History opens Compare With Model for
  that attempt, so the learner can review it.
- **HD-8 Summary scope (S-15).** This session while it has tasks; the last 7 days when the session is empty.
- **HD-9 Linking (S-17).** Linking words are counted from the transcript through a language adapter (English and
  Chinese).
- **HD-10 Conversation difficulty (S-20).** B1 / B2 / C1 chips, passed into the conversation-turn prompt.
- **HD-11 End (S-22).** "End" sits in the composer row once at least one turn exists.
- **HD-12 coaching (S-23).** Inline now; the Contextual Orena panel entry is added later with the Orena work.
- **HD-13 Situation (S-25, S-26).** Each scenario carries an authored context field shown as the chip; the
  Intent / Clarity cards appear only when the coaching response carries real judgements.
- **HD-14 language layers (S-27).** Mic sheets and system notes are wholly in the interface language.

## D-140 - Compare's model pitch and timing are prepared once at content readiness

2026-10-07, explicit human decision ("mất đâu màn hình compare có biểu đồ so sánh từng từ và timing nữa", then
"Chuẩn bị 1 lần"). Since D-121 the model is the original segment played from the source, so Compare had no model
audio to measure and showed no model pitch or timing.

- **Prepared once.** At content readiness the server cuts each line's model clip from the admitted source and
  stores it as a source artifact, once per content revision, through the existing media asset store and execution
  owners. No provider is called.
- **Read on open.** Compare only reads the prepared clip and measures its pitch in the browser with the same
  tracker as the learner's take. Opening or reopening a line never cuts, fetches the source or prepares anything
  (D-121 stays in force); a line without a prepared clip shows the model plot as unavailable.
- **Word timing.** Verified word timestamps win. Without them the model's words are placed by estimate over the
  voiced part of the clip and labelled "est." (the D-137 L-13 rule).
- **Existing content** is prepared by an explicit, bounded backfill, not on navigation.

## D-141 - Speaking gaps: session identity proposed; historical timing and Clear deferred; close the basic slice

2026-10-07, explicit human decisions on the Speaking gaps (UI_BACKEND_GAPS S-13a, S-13b, S-15a).

- **Practice session identity: proposal approved.** Speaking Summary must count one practice session correctly across
  tabs, reloads and devices, so a server-side practice session identity is proposed
  (`docs/project/proposals/PRACTICE_SESSION_IDENTITY.md`). It is learner persistence: it goes through independent
  architecture review, and any schema or migration waits for the human's authorization (AGENTS.md §7).
- **Per-word timing for historical attempts: deferred.** The current take keeps its timing as now; learner
  persistence is not widened in the Product Completion phase (S-13a stays a gap).
- **Clear attempt history: deferred.** No destructive learner-data lifecycle in this Speaking batch (S-13b stays a
  gap).
- **Closing the slice.** Finish S-24, S-26, Similarity / Intonation and S-27, verify the real Speaking flow, send it
  to independent review. If it passes, the basic Speaking slice is closed and work returns to functional coverage of
  the whole of Orena; Speaking is not deepened further.

## D-142 - Practice session identity: product decisions on the proposal

2026-10-07, explicit human decisions on `docs/project/proposals/PRACTICE_SESSION_IDENTITY.md` (68cb2f2).

1. A practice session ends after 30 minutes of inactivity; qualifying activity refreshes the window. Time is the
   server's.
2. No new learner persistence only to count text-only or non-recorded activities in this slice. They count only if an
   existing durable server-side learner record already represents them, and never as pronunciation/audio attempts.
3. Only the current session summary is needed now; no historical session browsing.
4. No backfill: legacy attempts stay without a session identity; none is fabricated.
5. Read-time 30-minute clustering is not the canonical model for new activity. It may later serve as a legacy,
   read-only approximation; current cross-device correctness uses a persisted identity if the reviewed architecture
   permits it.

Review: the human reviews the architecture directly on the branch; the lane prepares a small proposal/implementation,
commits it clearly and reports the branch, SHAs and scope. No other reviewer is sought unless the human asks. Any
migration still waits for the human's authorization.

## D-143 - Release to :8000: one UI, one schema chain, one artifact, one deploy path

2026-10-08, explicit human decisions on `docs/project/RELEASE_8000_READINESS.md` (B1-B5), with the runtime policy and
deployment artifact around them.

1. **B5, release shape.** `/` and `/next` are not kept side by side. The new UI is the only UI; `/next` is a temporary
   namespace. Before the :8000 release the cutover is finished so that `/` runs the new UI. An old path that is still
   needed is PORTED or REDIRECTED; the rest is DELETED and tombstoned (`LEGACY_TOMBSTONES.md`). Supersedes the
   readiness document's shapes A and C.
2. **B1, migration 0016 and Reading data.** :8000 takes the canonical Reading migration `20260924_0016`. Old Reading
   data is not converted or backfilled into the new model: legacy rows stay as they are, in the read-only archive the
   revision creates. What is needed is a production-safe apply and rehearsal tool, not a script that turns old data
   into new.
3. **B2, the chain.** One production migration pack for the whole chain is prepared and reviewed on a restored copy of
   :8000; not twenty separate architecture reviews. 0015/0016 and 0029 get their own attention (gate / delta review).
   Nothing is applied to :8000 until the human has reviewed the evidence.
4. **B3/B4, limits, deletion, public access.** The first release keeps `ORENA_ACCOUNT_BACKBONE=off` and :8000
   restricted / invitation-only, not public. Account record limits, account deletion and upload limits therefore do
   not block a controlled trial; they must be finished before a public release.
5. **Runtime policy.** No further persistent Orena runtime is created. :8021 is dev/QA; :8000 is product-like
   acceptance; migration rehearsal uses a disposable restored-copy environment that is removed afterwards.
6. **Deployment artifact.** One UI, one schema chain, one release artifact, one deploy path. No agent opens a new port
   or runtime, and none keeps two product paths in parallel.

## D-144 - The release path to :8000 (completes D-143)

2026-10-08, explicit human instruction.

1. `codex/work` is the development and release-candidate branch; it is never deployed directly to :8000.
2. Before the merge it is allowed and desired to take a read-only backup of :8000, restore it into a disposable
   PostgreSQL environment, rehearse the full migration chain there with the exact release-candidate tree, and return
   the evidence for human review. Migrations are not applied to :8000 at this stage.
3. After the human approves the candidate and the rehearsal evidence: PR `codex/work -> main`, CI green, merge.
4. The release artifact (image) is built from the exact resulting `main` SHA.
5. The migration-pack chain digest and schema chain used in the rehearsal are checked against that SHA; if the merge
   changed anything migration- or runtime-relevant, the rehearsal is repeated before any production apply.
6. Only then: final production backup, the authorized migration chain applied to :8000, :8000 rebuilt/deployed from the
   exact `main` release image, readiness and smoke verification.
7. :8021 stays dev/QA only; it is never copied or moved to :8000. No further persistent Orena runtime; the rehearsal is
   disposable. The same release artifact is later deployed to the server.

Topology: `codex/work` (development + QA) -> release candidate -> restored-copy rehearsal -> human review -> CI / PR ->
`main` -> exact SHA -> immutable image -> :8000 product-like acceptance -> the same artifact on the server.

## D-145 - Voice utterances are turns; the input budget is a hard bound (contract v6)

2026-10-08. Review of PR #92 and #96 by the architecture reviewer; the lane's work approved; explicit human instruction.

1. **Contract v6.** Voice and text are one conversation, and each spoken utterance is one turn of it. The client numbers
   utterances per voice session (`utterance`, never the words); `/voice/tool` carries it, the new `/voice/turn` closes it
   at the vendor's turn end, `/voice/end` may carry a transcript tagged with it. The server counts each once and
   reconciles the transcript by that identity only. Additions are optional; a client at v5 or below is served as before
   (its spoken turns are not counted). `AGENT_CONTRACT.md` §9 and the version line carry it; no event, action or
   text-turn request changed.
2. **The input budget is a hard bound.** `agent/tokens.py` counts at most one token per UTF-8 byte (any language, any
   tokenizer), the shipped instruction as prose, a frame per message and a reserve. Under it the old default of 12,000
   left about 5.5 KB for history, summary and pasted text, so `AgentLimits.max_input_tokens_per_turn` is **48,000**, the
   initial controlled-release value (not 60,000). It is a cost decision and is revisited with usage data.
3. **Follow-ups, not blockers:** budgeting the voice instruction's own conversation history; retention for
   `agent.summary` rows; physical and live-microphone QA of the voice client.

## D-146 - :8000 is public, product-like staging; APP_ENV=staging; the environment is never a feature switch

2026-10-08. Explicit human instruction; supersedes every earlier reading of :8000 as a production runtime.

1. **Roles.** `codex/work` + :8021 = development / QA. `main` + :8000 + the public domain = product-like staging, for
   real-user testing and feedback. There is no final production runtime yet; production hardening and a feature freeze
   start only when the human says the product is being finalized.
2. **`APP_ENV=staging`** is a first-class public environment. Staging and production share every public security
   requirement (`DeploymentConfig.public`): non-local HTTPS `PUBLIC_BASE_URL` and callback, Google OAuth, secure session
   cookies, `SESSION_SECRET` of 32+ characters, security headers and origin protection (unchanged, keyed on HTTPS), no
   local-admin bypass (`ALLOW_LOCAL_ADMIN` ignored), no source mounts, developer docs/OpenAPI hidden.
3. **Not a feature switch.** `APP_ENV=production` no longer disables anything a flag enabled. `AGENT_ENABLED` is the
   Orena Intelligence switch everywhere (unset/false: absent; true: available); `AGENT_VOICE_ENABLED` stays separate.
   Developer tooling stays development-only (generated listening catalog, synthetic pronunciation scores, docs).
4. **Parity.** `main`/:8000 carries the approved learner capability set of `codex/work`/:8021. Differences are allowed
   only for developer diagnostics, test fixtures, and work not yet reviewed and merged to `main`.
5. **:8000 env (to apply after review, not before):** `APP_ENV=staging`, `AGENT_ENABLED=true`,
   `AGENT_VOICE_ENABLED=false`. No schema change.

## D-147 - No violet outlines; an edge is a thin strip of light (overrides the design)

2026-10-08, explicit human rule, repeated after earlier reviews (D-133 LEX-016 "no default purple-outline control";
`docs/UX_REVIEW_RULES.md` "viền bo tím/filled card kiểu SaaS không mặc nhiên hợp lệ"). Human: "màu tím đây là thứ đã
nhắn bao nhiêu lần là luật không được dùng … nếu cần border thì nó phải có dạng như 1 dải sáng mảnh. Dù UI design có
thì vẫn phải loại trừ lỗi này ra."

1. **No violet/purple border, outline or ring** on any learner or Admin control or card - at rest, on hover, when
   selected or active. This holds **even where the Claude Design frame draws one** (`border:1px solid var(--accent)`,
   `var(--tint2)`, a hue-coloured 1.5px outline, …); it is a recorded exception to D-067's "the design is the
   standard" and to the fidelity gate, not a deviation to report.
2. **An edge, where one is needed at all, is a thin strip of light:** `--edge-light` in `kit/tokens.css` (a 1px top
   highlight plus a near-invisible 1px inset, per theme), never a grey or coloured outline and never a thick border.
3. **State without outlines:** hover is elevation (`--sh2`); selection is fill and ink (e.g. `--accent-soft` with the
   text colour); a selected category is a deeper wash of its own hue.
4. **Not affected:** the keyboard focus ring (accessibility); progress rings and tracks, which are drawings, not edges.
5. First applied: Grammar Library (level tabs, category cards, chips, back, sort, clear, view toggle). Other surfaces
   are brought to this rule as they are touched; a reviewer scores a violet outline as P1.

## D-148 - One hover behaviour for every card; no box on a press

2026-10-08, explicit human rule ("nên nhất quán hành vi animation khi hover với card cũ").

1. Every clickable card in the learner UI hovers the way the existing cards do (kit `.o-card--hover`, Today's
   cards): `box-shadow` to `--sh2` and `transform: translateY(-1px)`, transitioned over 0.15s. A surface may add its
   own background step (a grey card to `--surface3`) but never a border (D-147) and never a different motion.
2. Pressing a card or control paints no box: touch browsers' tap-highlight is off for buttons, links, labels,
   summaries and `[role=button]` (kit `base.css`). The keyboard focus ring stays.
3. First applied: Grammar Library (continue, category, topic and list cards). Other surfaces follow as they are
   touched; a reviewer scores a card with a different hover, or a box on press, as P2 (P1 if it is a violet edge).

## D-149 - Pronunciation starts at the source chooser; "Choose source" is visible in the room

2026-10-08, explicit human decision, superseding D-139 HD-3 and the "Choose media" half of HD-4. Human: "Phần
Pronunciation bấm vào thay vì là vào nơi chọn nguồn phát âm thì lại cứ bị đưa vào phần attempt và bước để chọn nguồn
để tập nói thì nằm tuốt ở ô ... nhỏ."

1. Pronunciation (Practice Hub, Speak's Skill Hub) always opens the source chooser
   (`#/discover?tab=listen&practice=pronunciation`) first; it never drops the learner into an attempt on the last line.
2. In the speaking room the way to change source is a labelled header button, "Choose source", beside Attempt
   history - not an item in the "…" sheet. The "…" sheet keeps only the line list and "Listen".
3. The header's text buttons take D-147's light edge instead of a border2 outline.

## D-150 - Cards are flat like Practice Hub's tiles; the light edge is flat

2026-10-08, explicit human decision. Human: "các border của phần ngữ pháp đang bị sai … nó đang tạo cảm giác 3d nổi lên.
hãy làm giống với đặc tính của các card trong practice hub."

1. A card or card-like control is flat at rest, as Practice Hub's tiles: the surface, no resting shadow, no outline.
   Hover is `--sh2` with a 2px lift (Practice Hub's own), refining D-148's 1px; selection is fill (a selected
   category card is a deeper wash of its hue, still flat).
2. `--edge-light` (D-147) is a flat, even hairline of light (`inset 0 0 0 1px`, white at .6 in light, .06 in dark),
   never a top highlight, which read as a raised 3D card.
3. Applied: Grammar Library, and the D-147 sweep of the learner UI (kit, shell, every screen's CSS except Admin):
   full grey borders on controls and cards became the light edge; violet/grey state borders became fills; field
   focus is a neutral `--text3` edge with elevation instead of the violet border and `--ring` halo; violet marker
   bars and rings on selected rows/options were removed (their fill stays). Kept: dividers (single-side borders),
   fields' resting borders (UX_REVIEW_RULES: an input's edge is a legitimate special case), the spinner, the mic
   pulse and the keyboard focus ring.

## D-151 - Every card stands raised; the light page is a step darker

2026-10-09, explicit human decision, replacing D-150 point 1's flat rest. Human: "tất cả phải làm thẻ nổi. Đặc biệt
điều chỉnh lại bản màu ở chế độ sáng. màu nền và màu card đang gần như hòa vào nhau".

1. A card or card-like control is raised at rest: `--edge-light` now carries `--sh1` with the hairline, so everything
   that draws the edge stands off the page in both themes. Hover stays `--sh2` with the 2px lift (D-148/D-150);
   selection stays fill; no violet edge (D-147).
2. Light theme, smallest change that separates card from page: `--bg` #F5F5FA → #ECEDF4, `--sh1` alphas .04/.04 →
   .07/.07 with a 12px blur, and `--text3` #6E6E86 → #68687F so it keeps AA on the darker page (4.64:1). Recorded as
   deviations in `scripts/test_orena_kit.mjs`.

## D-152 - Skill order, the phone Practice Hub folds, quick theme switch, Settings pickers

2026-10-09, explicit human decisions.

1. Skills are ordered Listen → Speak → Read → Write → Vocabulary → Grammar on desktop and phone
   (`practice/model.js` `SKILL_ORDER`; the design's `SK` order is superseded).
2. On the phone, Practice Hub's skill sections fold to their heading (icon, name, number of activities) and open in
   place, so every skill is reachable without scrolling past the others; the desktop keeps the open sections.
3. A sun/moon button beside the bell (desktop top bar, phone header) switches light/dark in one tap; Settings keeps
   Light / Dark / System.
4. Settings: the Languages tab's three choices are pickers, as Support language already was (D-098); each Accent
   option shows its own colour beside its name.

## D-153 - Three plans with administrator-set prices and limits; Settings' Privacy tab; the new export pinned

2026-10-09, explicit human decisions. Human: "Tạo 3 option plan như thiết kế không được để 2 gói", then "Đổi catalog
thành 3 gói với giá và hạn mức tương tự thiết kế. Khi có kích hoạt billing thật thì có thể điều chỉnh sau. Nhưng phải
có phần UI để điều chỉnh giá trong admin và các hạn mức … lật lại thì có thể sửa giá và các hạn mức đi kèm. Và có thể
apply tính từ lúc thay đổi từ admin"; "Có theo thiết kế mới" (Settings); "Cho phép" (pin the export).

1. The plan catalogue (`writing_coach/product/catalog.py`) is Free / Plus / Pro (ranks 0-2) with the design's monthly
   and yearly prices in USD and VND. Limits use the existing feature keys: Free unchanged, Pro with Premium's former
   limits, Plus between them. A stored `premium` subscription is Pro; the frozen native `/api/product/me` still
   reports Plus and Pro as `premium` (its schema knows two ids).
2. An administrator edits every price and monthly limit in Platform Admin (`#/admin/plans`, `GET`/`PUT
   /api/product/admin/plans`, `require_admin`). The document is validated and stored as the `product.plan_catalog`
   `platform_settings` row (no new table or migration) and applies from the moment it is saved; each save writes an
   `audit_logs` row. A stored document that cannot be read is ignored, never half-applied.
3. Billing stays off (`billing_ready: false`): a price is what the product shows, not a charge. The billing module's
   price file is separate and must be aligned before billing is activated. This is an entitlement change: it needs
   the independent architecture review AGENTS.md requires before it reaches `main`.
4. Settings' "Plan & privacy" tab becomes Privacy, as the new design draws it.
5. The 2026-10-09 export is pinned: `screens/Orena.dc.html` (928 080 bytes, sha256 1abfa9cd…) and
   `screens/Orena-Admin.dc.html` (232 508 bytes, a70b3baa…); `PINS.tsv` updated, `SYNC_2026-10-09.md` records it.

## D-154 - An administrator sets an account's role and plan by hand

2026-10-09, explicit human decision. Human: "Tạo phần manual để admin khả năng mở giới hạn và set thành viên theo tài
khoản", then "Phần giới hạn là phân quyền user ấy không phải thay đổi giới hạn sử dụng".

1. Platform Admin's account page (`#/admin/users/:id`) has a "Role & plan" block: role Learner / Administrator
   (`users.role`), plan Free / Plus / Pro with an optional end date. `GET`/`PUT /api/product/admin/accounts/{id}/membership`,
   `require_admin`; each change writes an audit row and applies from the moment it is saved.
2. A plan set by hand is a `manual` subscription row (`provider="manual"`, status `active`, `current_period_end` the end
   date); past its date the account reads as Free with nothing to run. Free removes it. A subscription billing owns is
   never overwritten by hand (409). A missing `plans` row for Plus or Pro is inserted (the FK target).
3. Guards: an administrator cannot change their own role; an address in `PLATFORM_ADMIN_EMAILS` cannot be made a
   learner here (sign-in would restore it). Roles stay the two the platform has (`user`, `admin`); finer permissions
   would need a permission model of their own.
4. Usage limits are not edited per account (the human's correction); plan limits are D-153's.
5. Entitlement and role changes: the independent architecture review applies before `main`.
6. Review of #112 (delegated architecture review, REQUEST CHANGES on `5fc9b83e`), fixed: the catalogue's stale-save
   check is a compare-and-set inside the write transaction (PostgreSQL `SELECT ... FOR UPDATE`; the SQLite archive
   store `BEGIN IMMEDIATE`), so two editors from one version cannot both save; the membership change (role, plan) is one
   transaction that locks the account and subscription rows and re-checks billing ownership under the lock; and the
   audit row of a catalogue or membership change is written in the same transaction - a change that cannot be audited
   is rolled back, never kept unaudited (the separate, failure-swallowing audit calls are gone).

## D-155 - Vietnamese text in Plus Jakarta Sans everywhere

2026-10-09, explicit human decision. Human: "Chuyển font tiếng Việt về Gilroy", then "Có thể chuyển sang Poppins / Plus
Jakarta Sans cho free". Gilroy is a paid face and not in the repository; Poppins has no Vietnamese subset (its stacked
tones would fall back to another face). Vietnamese stays in Plus Jakarta Sans, now through `--font-ui`, so the places
that set Outfit themselves (the Reader's translation, note and badges) follow the language too.

## D-156 - Learner feedback is stored and read in Platform Admin; the stale review gate is gone

2026-10-09, explicit human decisions. Human: "Bổ sung thêm phần ghi nhận feedback từ user nữa trong admin", and the
P1 report "public staging user blocked by stale internal-review gate".

1. A review (1-5 stars, the screen's areas, up to 600 characters) is sent from the Feedback screen (`POST
   /api/feedback`, at most 10 a day per account) and stored as a `learner.feedback` `audit_logs` row linked to the
   account - no new table. The learner reads their own (`GET /api/feedback/mine`); Platform Admin reads all of them
   with totals, average, stars and areas (`GET /api/admin/feedback`, `#/admin/feedback`). Storing learner-authored
   text in `audit_logs` is a persistence choice the independent architecture review must confirm before `main`
   (a dedicated table and retention are the human's).
2. `static/orena/main.js` no longer stops a signed-in non-admin account with the internal-review notice and its
   dead `/account` link: every verified account runs the learner UI (new account -> Onboarding, completed -> Today);
   only `#/admin/...` addresses check the admin role (the No access frame). `/account` stays retired.

## D-157 - A card without artwork shows a generated poster, never a blank tile

2026-10-09, explicit human decision. Human: "nhớ có ảnh thumbnails … không được để 1 màu rỗng"; chose "Thiết kế lại ô bìa
mặc định". A media card with no image (and one whose image fails to load) draws a poster from data and tokens only:
the kind's hue as a gradient into a second hue chosen by the title (stable per title), two light circles, the
title's first letter or character large, and the kind's icon (`kit/components.js` `posterMarkup`). Per-item
illustrations under the Art Bible remain a later, separate decision (they need a cover field for Reading).

## D-158 - 27 public-domain Reading articles are published on :8000 as test content

2026-10-09, explicit human decision ("chọn lọc vài nội dung chất lượng … chuyển về main 8000 … làm test case",
"Bạn nhập thẳng vào container", "27 bài phạm vi công cộng"). :8000 already held all 52 Reading articles and 8
approved comprehension sets, identical to :8021, unpublished on 2026-10-08 pending the human's approval of content,
metadata, level, rights and presentation. Re-published through the admin route's own rules (publication blockers,
warnings, status, audit; actor `ops-content-transfer`): the 15 Project Gutenberg stories (EN) and the 12 Wikisource
texts (ZH) - public domain, 3 with approved question sets. The two source names lost their "[Mẫu kiểm thử] " prefix.
VOA Learning English and Wikinews stay unpublished (rights per text not confirmed). No provider call, no restart.
:8000 runs `main`: the poster covers (#111) and the staging learner-gate fix (#109) reach it only after they merge and :8000 is redeployed.

## D-159 - Learner feedback retention: deleted with the account, and after 24 months

2026-10-09, explicit human decision (asked by the delegated architecture review of #113: "Xóa khi xóa tài khoản + giữ
tối đa 24 tháng"). Reviews stay in `audit_logs` (`learner.feedback`) as the bounded MVP store.

1. With the account: `delete_feedback_for_account(user_key)` removes every review an account sent; the account-deletion
   runtime (still a reserved hold, AGENTS.md section 7) calls it when it deletes an account. A review whose account row
   is deleted becomes an orphan (`user_id` empty, no account key) and the sweep removes it.
2. After 24 months: a periodic job (`feedback_retention.py`). A daemon thread is started with the app; it sweeps at start and then
   daily, independent of traffic, through `delete_feedback_before()` in bounded batches (final review of #113: a
   send-triggered sweep does not enforce a maximum age). Deletion is a destructive lifecycle job, so the schedule
   starts only when `FEEDBACK_RETENTION_SWEEP` is on. Switching it on, for :8000 included, is the human's activation
   step.
3. Admin totals, average, star and area counts and filtered totals are SQL aggregates over every stored review.

## D-160 - Public entry: the design re-pinned, Landing, Terms and Privacy served, Donate out of scope

2026-10-09, explicit human instruction (the new design export of 2026-10-09 to be pinned and the public beta's
entry built from it). Same project as D-088.

1. **Re-pin.** `Orena.dc.html`, `Orena-Admin.dc.html` and `Onboarding.dc.html` are replaced by the new export (the
   only change in the first two is an optional Backdrop feature; in Onboarding, a midnight backdrop and a translucent
   aside), and `Orena-Landing`, `Orena-Terms`, `Orena-Privacy`, `Orena-Donate` and `assets/bg/*.jpg` are added
   (`SYNC_2026-10-10.md`, `PINS.tsv`).
2. **Public routing.** `GET /` is the Landing for a visitor who is not signed in when sign-in is on, and the learner
   shell for everyone else, as before; `/?app=1` is the shell for that visitor (Landing buttons and `/login` lead
   there, so no loop). `/landing`, `/terms` and `/privacy` are public, always served. `/api/*`, `/auth/*`, `/login`
   and Admin (`require_admin`) are unchanged.
3. **Human decisions recorded.** The Landing is English only and dark only, as designed. Terms and Privacy are the
   design's legal text, verbatim; Vietnamese default, English by `?lang=en`, Chinese shows English. The design's
   Pricing (D-153) is the source of truth for plans; quota work is another change. **Donate is out of scope** for
   this milestone (sample payment details): its link is not rendered. The Backdrop glass chrome is pinned, not
   built (`UI_BACKEND_GAPS.md` PUB-4).
4. **Mechanism.** The three pages are the design's own files run by its own runtime, generated by
   `scripts/build_public_pages.mjs` (links rewritten, assets moved to `/orena-assets/public/`, Donate removed);
   `scripts/test_orena_public_pages.mjs` fails on drift or on any change to the legal text (PUB-1).


## D-161 - Plan quotas: the design's meters, enforced on the server; writing reviews first

2026-10-09, explicit human decisions (in Vietnamese, relayed by the coordinating session), implemented on branch
`feat/quota-core` against the read-only contract "Orena plan quota enforcement" (2026-10-09). **Needs independent
architecture review before merge** (entitlement change; the quota repository's reviewed contract gains a mode).

1. **The design's Pricing is the plan source of truth** (`Orena.dc.html` `BILL_PLANS`). Catalogue v2
   (`writing_coach/product/catalog.py`): `orena.message` per day 20 / 200 / 1000; `writing.review` per month 2 / 10 / 50;
   `pronunciation.audio` 5 / 30 / 120 min and `media.import` 15 / 120 / 600 min per month, stored in seconds;
   `languages.target` a count cap 1 / 2 / 2. Windows and units are the code's (`METERS`); an administrator edits only
   the numbers and a meter's own parameters. `dictionary.lookup`, `vocabulary.save` and the v1 boolean flags are no
   longer plan entitlements (unmetered for every plan; cost telemetry unchanged). A stored v1 document is read with
   its prices kept and its old limits ignored; a save is always v2.
2. **One writing review** = each AI evaluation (`POST /api/evaluate`) or AI improve (`POST /api/improve`) that actually
   runs. An identical review served from the store (no AI call) is free; the local heuristic (`fallback-demo`) and a
   provider error settle 0. The review refresh (`/api/essays/{id}/review/refresh`) is not charged (default, pending).
3. **Orena message** (catalogue only in this change; wiring is a later slice): a text turn that calls a model = 1; the
   opening greeting and answers made without a model call are free; voice is charged by duration, the server mints
   the voice token only for the remaining allowance, and `params.voice_seconds_per_message` (default 60, editable)
   converts voice seconds to messages.
4. **Languages:** a Free learner already learning 2 languages keeps them; only adding one beyond the cap is refused
   (later slice).
5. **Windows follow the learner's timezone:** the day resets at local midnight, the month at local 00:00 on the 1st.
   The zone is the browser's (`X-Orena-Timezone` on the metered calls and the usage read), else the zone of the
   learner's last window, else UTC. No account column holds a timezone - adding one is a schema decision reserved to
   the human (AGENTS.md section 7), so the bucket's `window_id` records it: `D:<local date>@<zone>`,
   `M:<local yyyy-mm>@<zone>`, with the true UTC start and end stored on the bucket. A timezone change never resets or
   reopens the current window: an open window is kept whatever zone a request names, and a new window that would
   overlap the previous one starts where it ended and lasts at least 23 hours (a day) or 27 days (a month), so
   sequential zone hopping never yields extra windows. Concurrent requests naming different zones cannot either
   (architecture review of #116, P1-1): the reserve takes a transaction-scoped advisory lock on (incarnation, meter)
   and refuses (`window_superseded`, nothing written) a window another bucket of that meter already covers; the
   request re-reads the latest bucket and uses that window. `resets_at` (429 body, usage read) is the window's true
   end.
6. **Server-side, fail closed, no plan-id branches.** One path, `writing_coach/product/quota.py`: request -> user key ->
   account -> incarnation -> plan (strict catalogue read) -> entitlement -> window -> `reserve(limit_policy='current')`
   -> dispatch -> provider -> settle/release. Exhausted: HTTP 429 `quota_exhausted` with `{feature, used, limit, unit,
   window, resets_at, plan, upgrade}` and `Retry-After`; store, catalogue or incarnation unknown: 503
   `quota_unavailable`; never "unknown = unlimited". The provider is not called when a request is refused.
7. **Current limit, kept usage.** Buckets are plan-independent (`incarnation, meter, window`); the limit is the
   catalogue's at each reserve (`limit_policy='current'`, no schema change), so an upgrade or an admin edit applies to
   the next request with the window's usage kept, and a downgrade below usage is exhausted at once (stored limit =
   GREATEST(current, consumed + reserved)). `'frozen'` stays the default for every other caller.
8. **The switch** (default off everywhere), failing closed (review of #116, P2-1): `ORENA_QUOTA_ENFORCEMENT=off` is
   off; `=on` is on, and if no wired meter resolves (`ORENA_QUOTA_METERS` empty and the setting lists none) every wired
   meter answers 503 rather than running unmetered; unset, the admin setting `product.quota_enforcement`
   (`PUT /api/product/admin/quota`) decides, so a running sandbox can be switched without recreating it, and a setting
   that cannot be read in a process that never read it makes every wired meter answer 503. Meters enforced =
   `ORENA_QUOTA_METERS` or the setting's list, only meters this build wires (`writing.review` today). **:8000 must pin
   both environment variables**, so the setting is never the authority there. Enforcement needs PostgreSQL, the quota
   tables and an active account backbone; otherwise every enforced meter answers 503. Roll back = switch off (buckets
   stay for audit).
9. **Usage read = enforcement.** `/api/product/commerce` reads each enforced meter's used (consumed + reserved),
   limit and `resets_at` from the same buckets and catalogue; a meter nothing counts is `not_metered` and a store it
   cannot read is `unavailable` - never "0 used". `/api/product/me` (frozen native contract) is projected onto its
   strict feature shape. The local (auth-off) Plan screen now reads the account enforcement meters ("legacy"), not a
   second made-up account.
10. **Defaults pending the human** (constants in `quota.py`, easy to change): calendar windows as in 5 (the human
    answered: learner's timezone); review refresh not charged; abandoned dispatched work is settled at the reserved
    amount by a reconciler (`ABANDONED_SETTLES = "admitted"`, every 10 minutes, after 15 minutes); an administrator's
    downgrade applies immediately. Still open: pronunciation display rounding; the Plan screen's state for an
    unmetered meter and the in-room exhausted message (the design draws neither, `UI_BACKEND_GAPS.md` QTA-1/QTA-2);
    incarnation rows on a backbone-off deployment (:8000); a CI PostgreSQL service so the PostgreSQL proofs gate merges.
    **Recorded as the human's decision to confirm (review of #116, P2-3):** provider work that ran but whose output is
    unusable (`AIProviderError` -> the local heuristic or a 502) settles 0 - the learner got nothing - so that spend is
    bounded only by the per-process brake (`writing_ai`, 30 per 600 s per worker), which stays.
11. **Activation:** :8021 may be switched on (`writing.review`) after review; :8000 needs an explicit human GO and the
    architecture review of 6-8.

Independent architecture review: `docs/reviews/architecture/QUOTA_CORE_REVIEW_2026-10-09.md` (claude-opus-5-5,
Delegated Architecture Reviewer, REQUEST CHANGES on 4fbd15a2..40443ed1; fixes listed there).

If another branch (PR A) lands a D-161 first, this entry is renumbered to the next free number on merge.

## D-162 - Truthful public legal text, a deletion page, self-hosted fonts

2026-10-09, explicit human instructions (publish-readiness for Google Play: PUB-2). Supersedes D-160 item 3's
"the design's legal text, verbatim" and PUB-1/PUB-2 in `UI_BACKEND_GAPS.md`. Layout stays the design's.

1. **The repository owns the legal words** (human-authorised deviation from the pin). `docs/legal/public/` holds
   Privacy, Terms and Delete-account text in Vietnamese and English and `facts.json`; `scripts/build_public_pages.mjs`
   lays it out with the pinned design's markup; the gate compares the pages to it verbatim. Every changed sentence
   and its evidence is in `docs/legal/PUBLIC_POLICY_CHANGES_2026-10.md`. Nothing claims what the code does not do.
2. **Operator and contacts.** Operator/developer public name RallyX, Vietnam; no personal name, no address.
   Contacts `orena.legal@chillpickle.org` (legal, privacy) and `orena.support@chillpickle.org` (support, deletion).
3. **Account deletion.** A public page `/account-deletion` (no login): email the support address from the Google
   account's email; what is deleted and kept; processed by hand within 30 days at most. There is no in-app
   delete or export yet; the account-deletion runtime stays a later architecture task (AGENTS.md section 7).
   `docs/project/ACCOUNT_DELETION_RUNBOOK.md` is the operator's manual procedure and needs independent
   architecture review before first use (destructive).
4. **No vendor names.** Public text describes AI and speech providers by function (content needed for a feature is
   sent to service providers that process it on RallyX's behalf; the server does not keep learner audio). The
   vendor list is internal, in `docs/legal/GOOGLE_PLAY_DATA_SAFETY.md`.
5. **Facts.** Minimum age 13 (no technical age gate in the beta; Play target audience 13+, not Families). The two
   retention jobs will be ON at deploy: Orena Intelligence turn records 90 days, learner feedback 24 months
   (`AGENT_TURN_RETENTION_SWEEP=on`, `FEEDBACK_RETENTION_SWEEP=on` must be set before the policy is published).
   Backup retention is unknown (`scripts/runtime_backup.py` has no rotation) and the publish date is not set: both
   stay `null` and block `node scripts/build_public_pages.mjs --release`, which must pass before :8000.
   `ORENA_ACCOUNT_BACKBONE=on` on :8000, so drafts, conversations, notes, highlights, place and private imports
   are stored server-side for signed-in learners, and the policy says so.
6. **Fonts are self-hosted.** The learner shell and the public pages no longer load Google Fonts: the same
   families and weights are served from `static/orena/fonts/` (OFL licence texts committed, listed in
   `THIRD_PARTY_NOTICES.md`; re-fetched by `scripts/fetch_self_hosted_fonts.py`). The policy therefore needs no
   Google Fonts disclosure, and the public-pages gate forbids `fonts.googleapis.com` and `fonts.gstatic.com`.
7. **Links.** The sign-in consent line links Terms and Privacy Policy; Settings → Privacy links Privacy Policy,
   Terms and Delete account (new tab); the Landing footer gains "Delete account" in its own link style.
8. **Static legal pages (human, 2026-10-09).** Terms, Privacy and Delete account are server-rendered static HTML
   with the full text in the response and no JavaScript needed (crawlers and Play reviewers without JS read
   everything): one file per language, Vietnamese by default, English for `?lang=en` and for `?lang=zh`, the
   language switch is plain links, the design runtime and React are not loaded on them. The look is the design's
   (measured: same element counts, 0 px delta, same computed styles at 1920x1080 and 390x844). The Landing stays
   runtime-based (PUB-1, deferred). The gate checks the raw HTML of each language with scripts removed.
9. **Age.** Minimum age 13 (not 12). The pages say the service is for people 13 and over, no date of birth is
   collected, there is no technical age gate during the beta, and an account found to belong to someone under 13
   is deleted. Play target audience 13+, not Families.
10. **Backups: 30 days, enforced.** `scripts/runtime_backup.py rotate --dir <dir> --days 30 [--apply]` keeps the
    backup directory to 30 days: dry run by default; touches only regular files named `orena-*.dump` directly
    inside the given directory (never subfolders, symlinks, the deletion journal or anything else); removes a
    dump when it is at least 30 days old (the older of its mtime and the timestamp in its name); keeps the newest
    even if stale unless `--allow-empty`; logs every decision. Tested with a temporary directory (boundary at
    exactly 30 days). Verified read-only against the real `%USERPROFILE%\.orena\backups`. `facts.json`
    `retention.backup_days` is therefore 30. Applying it on the :8000 host (at least daily) is part of the
    human-gated deploy.
11. **Publish date.** `effective_date` stays null in the repository. The deploy step is `node
    scripts/build_public_pages.mjs --release --effective-date YYYY-MM-DD` with the date of the policy's first public
    deployment on :8000; the release check fails without it.


## D-163 - Orena messages enforced on the server: text turns and text discussion; voice refused until it is metered

2026-10-09, the human's decisions relayed by the coordinating session, implemented on branch
`feat/quota-orena-message` on top of D-161 (`feat/quota-core`). The number is assigned at merge. **Needs independent
architecture review before merge** (entitlement and commerce enforcement on the agent path; an implementer may not
self-approve).

1. **What is one Orena message.** A learner's text turn that calls a model is 1 message, per day in the learner's
   timezone (D-161 point 5), Free / Plus / Pro 20 / 200 / 1000 (catalogue). One turn may run several model rounds (a
   read tool, the evidence nudge, the answer nudge): it is still 1. The automatic opening greeting
   (`trigger: "open"`) and every answer produced without a model - an identity question, an offered place opened on
   "open it", the opening on a selection - are free and are never refused, even for a learner whose day is spent.
   **The greeting is bounded (architecture review of #118, P1-1; the human: it costs no learner quota, its real provider
   cost stays in telemetry, and reconnecting or refreshing must not yield unlimited free greetings).** The model writes at
   most `AgentLimits.model_openings_per_window` (1) greeting per account per `opening_window_seconds` (30 minutes), in a
   sliding-window limiter on `AgentRuntime` keyed by the account; each greeting round is capped at
   `opening_max_output_tokens` (200). Past the allowance the greeting is **built by the server** from the learner's
   snapshot (`greeting.built`) with the surface's default suggestions: no provider call, the same stream to the client,
   still 200, never refused, no quota. The bound is **per process** (like the other agent limiters) until the shared
   store backs it - required before :8000 runs more than one worker (`UI_BACKEND_GAPS.md` QTA-12). A greeting's real
   cost is recorded as before (`ai.operation`, `ai_cost_records`, and the `agent.turn` row with `opening: true`, its
   rounds, tokens and outcome - how free-greeting spend is read per account; a separate capability key was not added,
   the AI capability vocabulary being pinned).
   Learner-authored text no longer reaches the free opening prompt: it is shown each coach note's id and kind, never its
   text (review P2-1). A turn that asked no model and is unadmitted (an identity answer, "open it") skips the
   rolling-summary compaction, which would be a free model call; the upkeep waits for the next paid turn (review P2-2).
2. **Where it is admitted.** `agent/turn.py` calls an `admission` once, at the one point where the turn knows it will ask
   a model for a learner's message (after the decisions, before any event is released and before any provider round);
   `agent/api.py` reads that first event before it builds the response, so a refusal is a plain JSON 429 / 503 / 409 in
   the agent's error envelope and never an SSE frame. The ticket is dispatched at admission and settled when the turn
   ends, however it ends: **1** when a model round ran and the turn completed or the learner left (the provider did the
   work - walking away does not make it free), **0** when the turn ended in an error (provider unavailable, timeout, an
   empty answer: nothing usable - the learner pays nothing and the provider cost stays in telemetry, as for writing
   reviews, review of #116 P2-3) or before any model round. A stream dropped before it is read is closed by the
   generator's own `finally`; the reconciler (`SYNC_METERS` now includes `orena.message`) is only the backstop.
3. **Idempotency.** `Idempotency-Key` (one per learner message, kept through a rate-limit resend) keys the operation; a
   resend of a finished message is 409 `operation_finished` and is never charged twice; a deliberate retry is a new key.
   Without the header the server mints one (no dedup, no double count).
4. **`reading.discussion_turn` is an Orena message.** The text discussion (`POST /api/texts/discussion/turns`) is Orena
   answering the learner about a text - the tutor speaks as Orena ("Orena is thinking", "I'm attached to ...") - so it is
   metered as `orena.message`. Admitted after the stored-repeat check (a repeat of a `request_id` returns the stored
   exchange free) and before the turn cap and the provider; a full thread (409), a provider that cannot answer (503) and a
   repeat that lost the race settle 0. The body's `request_id` is the idempotency key. It is one constant
   (`text_discussion.QUOTA_METER`); `None` takes discussion out of the Orena messages if the human disagrees. The other
   model-backed learner helpers (translation, the reading summary, spoken-response coaching, dictionary explanations) are
   single-shot tools, not a conversation with Orena, and are not Orena messages.
5. **Voice is refused, not unmetered.** While `orena.message` is enforced, `POST /api/agent/voice/session` answers 503
   `quota_voice_not_metered` and mints no token (the client already falls back to text on any failed session); if
   enforcement cannot be read it answers the same 503 `quota_voice_not_metered` (fail closed; the client treats both alike). The other voice routes act on a session that
   `voice/session` created and the server calls no model on them, so there is no other way to a vendor token. Voice is
   charged by duration (`voice_seconds_per_message`) in a later change, which removes this refusal. A voice session
   opened before enforcement was switched on keeps its token until it expires (at most 15 minutes).
6. **Meter wiring.** `orena.message` joins `WIRED_METERS` / `SYNC_METERS`; the admin switch (`PUT
   /api/product/admin/quota {"enabled":true,"meters":["writing.review","orena.message"]}`) and `ORENA_QUOTA_METERS` can
   now enforce it. Off or unlisted: nothing changes (no bucket, no read). Store, catalogue or incarnation unreadable
   while it is on: 503, no provider call. The per-process 12 / min limiter and the daily USD cap stay as cost safety,
   separate from quota.
7. **Client.** The agent client sends `Idempotency-Key` and `X-Orena-Timezone` on a turn, tells the quota 429 from the
   contract's `rate_limited` 429 and from the language 409 by the body's envelope, and shows the server's figures in the
   reply's existing error place, in the retry button's place and style, with "See all plans" (`UI_BACKEND_GAPS.md`
   QTA-1). Plan & usage reads `orena.message` from the same buckets (used, limit, `resets_at`).
8. **Activation:** :8021 may enable `orena.message` after review; :8000 needs the explicit human GO and the
   architecture review of D-161 points 6-8 and of this entry.
9. **Accepted, recorded (review P3):** a refused discussion turn leaves an empty thread row and a refused agent turn an
   in-memory session (created before admission; harmless); a client that disconnects while its worker thread is inside the
   stream is settled when the generator is collected or by the reconciler, charging 1 as decided; a provider error after
   some text streamed settles 0, so a learner may have read partial text for free; a voice session opened before
   enforcement was switched on keeps its token for up to 15 minutes (switch on, expect that).

Independent architecture review: `docs/reviews/architecture/` of PR #118 (claude-opus-5-5, REQUEST CHANGES on
d8583d2b; P1-1 greeting bound, P1-2 contract v7, P2-1, P2-2 fixed here; D-164 below is the contract change).


## D-164 - AGENT_CONTRACT v7: the plan limit of Orena messages reaches the agent interface

2026-10-09, written on `feat/quota-orena-message` on the coordinator's instruction and the architecture review of #118
(P1-2); **the human confirmed** that the `/api/agent/*` changes and this bump belong in PR C, the UI lane owning the contract
(the Intelligence session was notified). The number is assigned at merge (D-145 is taken: v6).

`/api/agent/turn` can now answer statuses AGENT_CONTRACT v6 §2.1 did not allow (D-163), and D-086 forbids the Intelligence
lane from editing the contract, so the change is made by the UI lane in a reviewed commit: `contract_version: 7`,
consistently in `docs/project/AGENT_CONTRACT.md`, `writing_coach/agent/contract.py`, `static/orena/agent/contract.js`,
`static/orena/copy/surfaces.json` (regenerated) and the pin in `scripts/test_orena_surfaces.mjs`. The base already carries
v6 (D-145, PR #95: `POST /voice/turn`, `utterance` on `/voice/tool`). The contract header says "edit only on `codex/work`";
the UI-lane branches now target `main` directly (the human-approved flow for this milestone), so this PR carries the
change to `main` and the Intelligence lane receives it by merging forward.

1. **§2.1** gains the rows `429 quota_exhausted` (an object body, `Retry-After` = seconds to `resets_at`; told, never waited
   out or resent - told apart from the string `rate_limited`), `409 operation_in_progress | operation_finished |
   operation_conflict | account_not_ready` (a transport error with retry; never a language change - told apart from the
   string `target_language_mismatch`), `403 account_deleted | feature_not_in_plan` (a transport error, no retry) and `503
   quota_unavailable` (retry). Only a refused `rate_limited` 429 stays uncounted by the learner's window.
2. **§3** names the optional request headers `Idempotency-Key` (one per learner message) and `X-Orena-Timezone` (the day ends
   at the learner's local midnight), and **§3.3** what counts as an Orena message: a message turn that asks a model is one;
   the opening greeting and answers made without a model are free and never refused; the model writes at most one greeting
   per account per 30 minutes, past which the greeting is built from the snapshot as the same stream (§3.2).
3. **§9** names `503 quota_voice_not_metered` for `POST /api/agent/voice/session` while voice cannot be metered - a
   deliberate interim: live voice is blocked while `orena.message` is enforced, until the voice-minutes change. The quota's
   `Idempotency-Key` applies to `POST /api/agent/turn` (message) and the discussion route only; `/voice/turn` and
   `/voice/tool` neither require nor read it (their `utterance` token stays their identity), and the quota never touches
   them (tested).
4. **Compatibility.** No event, field, action or intent changed. The new statuses occur only where the server enforces the
   quota; a client that declares `contract_version` ≤ 6 sends neither header and reads a 429 as `rate_limited` - the
   shipped UI is v7 and reads the bodies (`static/orena/agent/transport.js`).
5. **Gates.** `scripts/test_orena_agent.mjs` asserts the §2.1 rows (in order), their categories, the headers, §3.3 and the
   voice 503 against the contract text and drives the transport through each; `tests/test_agent_contract_tables.py` fails if
   the quota gate can answer a category the contract does not name, or the voice refusal drifts.

## D-167 - Discover All is a sectioned overview

2026-10-09, explicit human decision (product owner). The number is assigned at merge. `feat/discover-all-sections`.

The decision, in the human's words: "Discover / All must not be one grid mixing every content type. All must be an
overview page organised by clear sections, so the user immediately sees: Read; Listen · Watch; Collections; Imported.
Each section shows only a few representative items and has 'See all'. The individual tabs are the full libraries of each
type. Goal: the user understands the app's content structure without clicking each tab."

1. **Supersedes the design's All.** `Orena.dc.html` (Discover frame, state script `tab:"All"`) draws All as one flat grid
   of every type in "For you" order; its only grouped form is the Sort control's "By level" / "By type" groups. The
   human's decision replaces that flat grid for the All tab (the design is the authority for look, the human for this
   structure; D-067). The tabs, the card, the filters and search are unchanged.
2. **Four sections, in the skill order (D-152):** Listen · Watch, Read, Collections, Imported - and the tab bar the same:
   All, Listen · Watch, Read, Collections, Imported. This supersedes the first wording of this decision (Read first), by
   the human's later instruction the same day. A section's heading is its tab's own label.
3. **Representative items = the tab's own first five**, in the order that tab lists them (`overviewSections` over
   `visibleEntries`; no "featured" ordering exists in any source). Read is therefore articles first, then books, as its tab
   lists them (Listen · Watch is the media library's own first five). Each section is one row: the cards that would wrap are `display:none` by the section's own width, and a
   phone shows two.
4. **Reuse, no new component.** The heading row is kit's `sectionHead` ("For you" / "See all", Today); the cards are
   `mediaCard` through the same `cardFor` as every tab. "See all" opens that tab in place - the same change the tab bar
   makes, no route, no history entry - and scrolls to the top of the page.
5. **Search and filters narrow every section alike.** A section with nothing to show is omitted, and a source that fails
   to load leaves only its own section out - except Imported, below. Each source is painted as it arrives. The practice
   choosers (`?practice=`) are not browsing and keep their one flat list.
6. **Imported is always drawn on All** (human, later the same day). With nothing imported, its row is one call to action
   ("Bring your own video, audio or text", en/vi/zh) with the same "+ Import" control as the page header, which opens the
   existing import flow; it has no "See all" (nothing to see). While a search or a filter narrows the page and nothing
   imported matches, the section is omitted like any other (a narrowed page is not an invitation to import).
7. **The VIP import control - an explicit human exception to D-147.** The header's "+ Import" and that call to action
   draw a running rainbow: a conic gradient (the skill and category hues of `tokens.css`, no colour of its own) turned by
   an animated `@property --vip-angle`, as a 3px ring around the unchanged accent fill (the label keeps its AA contrast)
   and as a soft blurred halo behind the button (opacity 0.55 on a dark page, 0.35 on a light one; QA on the first 2px
   hairline: too subtle). Ring and halo are pseudo-elements outside the layout (no layout shift, the halo ignores the
   pointer); under `prefers-reduced-motion` the ring is held still and the halo is static and fainter; the global keyboard
   focus ring is unchanged. D-147 (no violet or coloured outline) stands everywhere else; this
   exception is these two controls only (`discover.css`, `s-discover__vip`).
8. **Import is a featured function, found from every browsing place** (human, 2026-10-09: it is a money-making feature,
   so users should notice it and find it easily). The same VIP control (kit `vipButton`, the look of `components.css`
   `.o-btn--vip`) opens the same flow (`screens/import/open.js`) from: Discover's header and its Imported call to action;
   Today, as a featured card on the page's own card shell and icon tile with one line of value ("Learn from anything:
   import a video, audio or text", en/vi/zh) between Recommended and For you; and My Library's page header. On a phone the
   control is one tap from the Discover and Library headers (the header row wraps; no overflow at 360px). The rail and the
   phone bar keep the design's navigation set. D-147 stands everywhere except these VIP controls. The shared label is the
   shell's `importAction`.
9. **Gate.** `scripts/test_orena_screen_discover.mjs` section 13 renders the overview in English, Vietnamese and Chinese,
   and checks the order, the always-present Imported with its call to action, the VIP class on both import controls and the
   reduced-motion rule.

## D-166 - Onboarding backdrop (PUB-4)

Placeholder id; the number is assigned at merge. Human decision PUB-4 (2026-10-09), scope widened and then set to "make it like the design - the background shows fully, nothing blends into anything": the pinned Backdrop (photo per theme and device under the design's scrim, glass rail / top bar / phone bar at the design's alpha, Onboarding's own scrim and translucent aside) ships on the learner shell, the Admin shell and Onboarding, on by default with no learner control (non-UI kill switch `data-backdrop="off"`). No veil, no panel. Content surfaces stay solid; the chrome edge is `--edge-light` (D-147); a browser without `backdrop-filter` keeps the photo and gets a more opaque solid chrome.

AA over the photo is met by scoped text tokens in `kit/tokens.css`, not by hiding the photo: on the chrome `--text3` and `--accent` move 3-12% toward `--text`; on the page `--muted` and `--text3` move 46-78% toward `--text` (hierarchy flattens for text set on the bare photo, most in light; inside every solid surface - card, panel, sheet, menu, input - the base tokens are restored by the generated `shell/surfaces.css`); Onboarding's aside gets +.22 (dark) / +.32 (light) alpha at most. Accent TEXT uses a dedicated `--accent-on-photo` (every accent-coloured text rule reads `var(--accent-on-photo, var(--accent))`, set only in the backdrop scopes), so fills, bars and dots keep `--accent` and no exception remains. The glass never depends on the operating system: there is no `prefers-reduced-transparency` rule; only a browser that truly lacks `backdrop-filter` gets a more opaque solid chrome, and it keeps the photo. Proven by `scripts/test_orena_kit.mjs` (BACKDROP) from `scripts/fixtures/backdrop_extremes.json`; exact values and the open human choices are in `UI_BACKEND_GAPS.md` PUB-4. Colour stays owned by `kit/tokens.css`.


## D-165 - Pronunciation minutes enforced on the server: the take's real seconds, reserved before the paid request

2026-10-09, the human's decisions relayed by the coordinating session, implemented on branch `feat/quota-pronunciation` on
top of D-161 (quota core) and D-163 (`orena.message`). The number is assigned at merge. **Needs independent architecture
review before merge** (entitlement and commerce enforcement on a paid provider path; an implementer may not self-approve).

1. **What is metered.** `pronunciation.audio`: the length of a learner's take, never the number of clicks. The product unit
   is the minute, the store holds seconds (catalogue scale 60); Free / Plus / Pro 5 / 30 / 120 minutes a month are the
   catalogue's beta configuration and are not changed here. The month follows the learner's timezone (D-161 point 5). The
   only metered route is `POST /api/speech/pronunciation` - the one place Azure Speech pronunciation assessment is called
   (`speech_api._assess_metered`); no cache sits in front of it, every request with audio is a paid request.
2. **The seconds are known before the call.** The route decodes the take locally first (`AzureSpeechPronunciationProvider.
   prepare_audio`: ffmpeg to 16 kHz mono PCM, capped at `MAX_ASSESSED_SECONDS` = 60, no provider call) and measures it from
   the WAV's `data` chunk (the old `len - 44` formula over-counted ffmpeg's 78-byte header by a millisecond, which would
   charge a whole-second take one second more). It then reserves exactly `ceil(seconds)` (after millisecond rounding: 7.4 s
   is 8, 7.0004 s is 7, a half second is 1; at most 60), dispatches, calls Azure with the already-decoded audio (decoded
   once, not twice), and settles.
3. **Reserve -> provider -> settle.** Exhausted is decided on the reservation, all or nothing: a take needing more seconds
   than remain is `429 quota_exhausted` before the provider and is never partially assessed (a learner with 5 s left can
   still send a 4.2 s take). The 429 body is the core's (`used`, `limit` in seconds with `unit: second`, `display_unit:
   minute`, `scale: 60`, `resets_at`, `upgrade`). Enforcement unreadable (store, catalogue, switch) is `503 quota_unavailable`
   and is asked before the decode (`quota.require_ready`), so that refusal does no ffmpeg work. **A 429 (exhausted) or a 409
   (duplicate) is decided at the reservation, which needs the decoded length, so those still cost one local decode (up to 8
   MiB / 20 s of CPU, no provider call)**; the per-account `speech_ai` brake bounds that. Not enforced: the route is exactly
   the unmetered path (no read, no bucket).
4. **What a take costs the learner.** Success: the seconds Azure processed (equal to the decoded length, never more than
   reserved; the rest is released). Any provider failure - request failed, timeout, a result that cannot be used (malformed),
   undecodable audio - settles **0**, consistent with D-161 point 10 / D-163 point 2 (the learner got nothing; Azure's billed
   seconds stay in the AI cost ledger, not the allowance). The development stand-in (`score_kind != measured`) settles 0.
   **Human decision 2026-10-09 (`speech_api.NO_SPEECH_CHARGED = True` for the beta): a take Azure answered
   "no speech" is charged the seconds it processed** - it was processed and billed, it is not a service failure, and not
   charging it would make silent clips free provider spend (bounded only by the per-process `speech_ai` brake, 60 requests per
   10 minutes); set it to `False` to charge nothing. A provider that cannot measure ahead (no `prepare_audio`) reserves 60 s
   and settles on the length it reports, else the reserved bound (a measured result) or 0.
5. **Idempotency.** The operation is (account, meter, `Idempotency-Key`, a digest of the audio's SHA-256, language, line and
   mode): a retry of the same take under the same key is never charged twice (`409 operation_finished`, or
   `operation_in_progress` while the first is running, proven concurrently on PostgreSQL); other audio or another line under
   the same key is another operation. The learner client sends one key per take and keeps it when the answer was lost (no
   response) or the server says it already has the take, and takes a new one only after an answer of Orena's own that charged
   nothing (a failure, a refusal), so "assess the same take again" after a service failure is allowed and never blocked. A
   server that processed a take whose answer the client lost cannot replay the result (no audio or result store): the retry
   is refused instead of charged (`409 operation_finished`). **That answer is terminal for the key (architecture review of
   #119, P2-1):** the client maps `operation_finished` / `operation_conflict` to its own non-retryable failure
   (`already_assessed`), says "This recording was already processed. Record it again to get a new assessment." (EN/VI/ZH, a
   toast; `UI_BACKEND_GAPS.md` QTA-15) and offers nothing to resend; the learner records again - a new take, a new key, a new
   real assessment and a new charge. Replaying a stored result instead would be new persistence and is the human's decision
   (asked in parallel); none is built. `operation_in_progress` stays retryable with the same key.
6. **Not metered (and why).** Learner pronunciation assessment is the only paid call here. `POST /api/speech/transcribe`
   (Groq Whisper) is a separate speaking-input path - used by Free talk, Conversation, Situation, React, Reading transfer and
   Orena's push-to-talk, never by the Speak / Compare / Shadow pronunciation rooms - and is left **unmetered**; the Voice
   slice owns it (`UI_BACKEND_GAPS.md` QTA-13). Word text-to-speech (Azure `word_audio_azure`, Kokoro in `word_audio`) is
   audio *playback*, not a learner pronunciation assessment, and is left unmetered. Media-import transcription (Groq, in the
   worker) belongs to `media.import`. No new meter was invented.
7. **Cost telemetry stays separate.** Every Azure request already records one `ai.operation` / `ai_cost_records` row
   (capability `pronunciation_evaluator`, provider `azure-speech`, model `pronunciation-assessment`, the seconds Azure
   processed, USD from the list price in `ai/pricing.py`, per account); every Groq request records a `speech_asr` row. A local
   decode failure is now a row too. The Azure region and a provider-reported usage figure are not recorded (the telemetry
   allow-list has no field for them and Azure's answer reports no usage); a ledger field is a schema decision reserved to the
   human. The learner's allowance and the ledger share nothing: the allowance is what the learner is charged, the ledger is
   what Azure charges.
8. **Client.** `api.assessPronunciation` sends `Idempotency-Key` and `X-Orena-Timezone` (no JSON content type). The 429 is
   the server's refusal and is told apart from a service failure (`failureOf` kind `quota`, never retried); Speak, Compare
   and Shadowing show it as the Respond room's toast pattern with "See all plans" (`#/plan/pricing`), from the server's own
   figures, EN/VI/ZH: "You have used 1.1 of 5 pronunciation minutes this month." Minutes are shown exactly as Plan & usage
   shows them (`displayAmount`: whole when whole, otherwise one decimal; Vietnamese with a decimal comma). No client check
   and no new visual. Plan & usage reads the same buckets (seconds), shown as minutes.
9. **The route no longer blocks the event loop.** The decode, the quota calls and the provider request run in the thread pool
   (they were synchronous calls inside an `async` handler), on a limiter of their own (`PRONUNCIATION_MAX_CONCURRENT`, default
   8 of the pool's 40) so a burst of assessments queues instead of starving the synchronous routes. Provider resolution
   (stored-credential read) still runs on the loop, as before. The decoder strips the client file's tags
   (`-map_metadata -1 -fflags +bitexact`): only audio is sent to Azure.
10. **Meter wiring.** `pronunciation.audio` joins `WIRED_METERS` and `SYNC_METERS` (the reconciler settles an abandoned take
    at its reserved seconds, D-161 point 10, ABANDONED_SETTLES); `PUT /api/product/admin/quota {"enabled":true,"meters":
    ["writing.review","orena.message","pronunciation.audio"]}` and `ORENA_QUOTA_METERS` can enforce it. Roll back = switch off.
11. **Activation:** :8021 may enable `pronunciation.audio` after review; :8000 needs the explicit human GO and the
    architecture review of D-161 points 6-8.
12. **Accepted, recorded:** a take longer than 60 s is cut to 60 s by the decoder (as before this change) and is charged 60;
    a take is charged its whole seconds rounded up, so a learner may lose up to one second per take to rounding.

## D-168 - Media import minutes enforced on the server: the source's length, reserved before any work, settled by its job

2026-10-10, the human's decisions relayed by the coordinating session, implemented on branch `feat/quota-media-import` on
top of D-161 (quota core), D-163 and D-165. The number is assigned at merge. **Needs independent architecture review before
merge** (entitlement and commerce enforcement on a paid provider path; the reviewed core gains operation-id calls and a
per-meter reconciler threshold; an implementer may not self-approve).

1. **What is metered.** `media.import`: the minutes of SOURCE media a learner imports in their month, in the learner's
   timezone (D-161 point 5); Free / Plus / Pro 15 / 120 / 600 minutes, stored in seconds (catalogue scale 60, beta
   configuration, unchanged). The product unit is source minutes, never clicks and never provider work: an import that
   found free YouTube captions costs the learner the video's minutes exactly as one that needed speech recognition.
   Metered routes: `POST /api/media-learning/source` (a link; the only route the learner UI calls) and
   `POST /api/media-learning/upload` (a file); a direct media link goes through the same file path. Not metered: text (the
   learner's pasted text never leaves the device and has no duration), and every administrator import (shared library,
   operator cost). The older `POST /api/media-learning/import` (Groq timing + Supadata, no duration to charge, unused by the
   UI) and `POST /api/media-learning/translate` (a client-supplied transcript of any length to the paid translation
   provider, unused by the UI) answer 503 `quota_media_import_not_metered` while the meter is enforced
   (`quota.refuse_unmetered`). `/import/status` only polls a job an earlier `/import` started and is left as it is.
2. **The length is the server's.** A file: ffprobe of the stored bytes. A YouTube link: YouTube's own length from yt-dlp
   metadata (nothing downloaded, no paid provider); if that cannot be read, the length of the captions; if neither, 503
   `media_duration_unavailable` - an unreadable length is never free. Nothing the client sends is read. A reservation is
   `ceil(seconds)`, at least 1, at most `MEDIA_ASR_MAX_SECONDS` (5400, the pipeline's longest source). A file longer than
   that can never be transcribed, so it is refused (422 `media_upload_invalid`) instead of reserved.
3. **Reserve -> dispatch -> settle, across a background job.** The request reserves all or nothing: if it does not fit,
   `429 quota_exhausted` before anything is stored, fetched (for a link: before its page and captions are read) or heard;
   enforcement unreadable is `503 quota_unavailable`, asked (`media_quota.ready`) before the file is read or downloaded.
   The operation id is kept on the library entry (`source.quota_op`, `quota_units`; provenance, never in a learner payload).
   The pipeline job dispatches by id right before its first step (no live reservation, no paid work), and settles by id
   when it ends: **success (a usable transcript) = the source seconds** (captions: the whole reservation; speech
   recognition: the seconds it actually decoded, never more than reserved), **anything else = 0** (failed, unusable
   transcript, interrupted too often, removed by the learner); what Groq/Azure charged stays in the AI cost ledger. Audio
   longer than the reservation is stopped before it is heard (`duration_mismatch`).
4. **Restart and deferred settlement (architecture review of 5ce3567e, P1-1/P1-2).** The id lives on the entry. A job
   interrupted by a restart is re-queued by `recover()` and settles when it ends. `app.py` runs `recover()` only after the
   quota runtime is configured; a `recover()` that finds no quota store (the pipeline built earlier than the runtime, a
   deployment without PostgreSQL) leaves every metered import untouched - nothing dispatched, nothing settled, nothing
   slept on - and a later call takes it up. A settlement the store could not take is recorded on the entry as an intent
   (`quota_settle`, the units and outcome decided when the job ended) and written (a) by the next `recover()` and (b) **in
   a process that stays up, every 5 minutes** by `MediaPipeline.settle_pending` (`IntentSchedule`, 200 entries a tick,
   started with the reconciler). The reconciler is the last backstop and **asks the media index what an abandoned import
   decided** (`quota.configure_async_decision` -> `media_quota.decide`): a recorded intent is settled as decided, a
   finished entry as its outcome says (0 when it failed), an entry gone from the index 0 (`no-entry`); an entry marked settled
   whose row is still open is settled as its recorded outcome; an entry still queued or running is **left to its worker**
   (a restart after a long outage re-queues it, and a failure must still settle 0) and settled as admitted only once its row
   is `ASYNC_IN_PLAY_CEILING` = 24 hours old (ABANDONED_SETTLES, the last resort for a stuck job); an unreadable index
   leaves the row for the next tick. `reconcile_once` is scoped by meter with a threshold per group - synchronous meters after 15 minutes as
   before, `ASYNC_METERS` (`media.import`) only after `ASYNC_RECONCILE_AFTER` = 6 hours.
   `quota.dispatch_operation / settle_operation / release_operation` act by operation id for work that outlives its request.
   A settled personal import is never re-run by `pipeline.retry()` (that would be Whisper with no reservation); a new
   import is a new admission.
5. **Idempotency.** (The entry's provenance keeps `source_key`: `youtube:<id>`, or `file:<sha256 of the file's bytes>` - a
   content fingerprint kept for as long as the entry exists and removed with it, including on account deletion.) The same
   learner importing the same source again is answered with the entry they have, free, before anything is probed or fetched: a YouTube video (any link form, key `youtube:<id>`) or the same file bytes (`file:<sha256>`),
   in the same learning language, while that import is queued, running, ready or held (an entry stored but never queued,
   with no pipeline state and not published, is not one). A failed one settled 0, so importing
   again is a new, charged import. Concurrent requests for one source are serialised per (learner, source), so two cannot both
   be charged. This applies only where the meter is enforced; switched off, an import is exactly what it was.
6. **Switch and failure modes.** Off, or `media.import` not listed: no read, no bucket, no probe, nothing changed. Enforced
   and unreadable: 503 before any work. `WIRED_METERS` gains `media.import` (`ASYNC_METERS`, not `SYNC_METERS`).
   `PUT /api/product/admin/quota {"enabled":true,"meters":["writing.review","orena.message","pronunciation.audio","media.import"]}`
   and `ORENA_QUOTA_METERS` can enforce it. Roll back = switch off.
7. **Client.** `prepareMedia` and `mediaUpload` send the device timezone (no idempotency key). The Import sheet shows the
   429 as the toast with "See all plans" (the Respond room's pattern; the sheet closes on the way out), from the server's
   figures, EN/VI/ZH: "You have used 14.8 of 15 media import minutes this month." Plan & usage reads the same buckets.
8. **Cost telemetry.** Groq Whisper already records one `speech_asr` row per request (seconds, USD at the catalogue rate,
   10 s minimum). New: each Groq translation request records a `media_translation` row (provider, model, provider-reported
   tokens, USD; `openai/gpt-oss-120b` is now priced at the published $0.15 / $0.60 per million) and each Supadata transcript
   request a `media_transcript_fallback` row (unpriced - no published price in the repository, never zero). Rows of an
   operator's shared import carry no origin (not `learner`). Account attribution of rows written by the background worker
   is not available (the job has no request context); recorded as QTA-17 (e).
9. **Accepted, recorded:** a learner who removes an import before it finishes is charged nothing even if a provider already
   ran (bounded by the per-account request brakes and the spend ledger); an unreadable-metadata YouTube video with captions
   is charged the captions' length, which is a lower bound; a video longer than 90 minutes with captions is charged 90.
10. **Activation:** :8021 may enable `media.import` after review; :8000 needs the explicit human GO and the architecture
    review of D-161 points 6-8.

## D-169 - Voice charged by duration against `orena.message`, chunk by chunk; AGENT_CONTRACT v8; `/api/speech/transcribe` guarded

2026-10-10, the human's decisions relayed by the coordinating session, implemented on branch `feat/quota-voice` on top of
D-161 (quota core), D-163/D-164 (`orena.message`, contract v7) and D-165 (pronunciation). The number is assigned at merge
(`D-169` is a placeholder in this entry, the contract and the code comments). **Needs independent architecture review
before merge** (entitlement and commerce enforcement on a paid realtime provider path; an implementer may not
self-approve; the contract is changed by the UI lane on the human's instruction, as in D-164). First review of
`33782356` (claude-opus-5-5, Delegated Architecture Reviewer): REQUEST CHANGES on P1-1; the human decided the fix (points 2-4)
and the transcribe guard (point 8); the contract stays v8 (not merged yet).

1. **Voice is charged by duration against `orena.message`; no new meter.** One voice minute is one message:
   `params.voice_seconds_per_message` of the `orena.message` entitlement (catalogue; default 60; admin-editable 1..3600; beta
   configuration, not a pricing decision). A started unit counts whole: `ceil(seconds / voice_seconds_per_message)` messages.
   Cost telemetry stays separate from the allowance (point 6).
2. **A voice session is a chain of short vendor tokens (chunks), each charged whole when it is minted (review P1-1, P2-1,
   P2-2).** The server cannot see the vendor socket, and an ephemeral token cannot be revoked: a learner can call
   `/voice/end` at once and keep talking on the token they hold. So what the learner is charged for is what the server lets
   them hold. A chunk is `VOICE_CHUNK_UNITS` (2) x `voice_seconds_per_message` seconds - two minutes at the default, never
   under `VOICE_MIN_CHUNK_SECONDS` (60) whatever an administrator sets, never past what is left of the session's 900 s - and
   costs `ceil(seconds / voice_seconds_per_message)` messages (2 by default; the last 60 s of a session cost 1). Ending early
   refunds nothing: a minted chunk is charged. The first chunk of any session therefore costs at least one message (a session
   ended at once is not free), and at most one chunk is ever held, never a whole day's messages. Open-end-open-end can no
   longer hold more vendor time than the day pays for (a test reproduces the review's probe: 20 messages buy 1,200 s of
   tokens, not 9,900).
3. **Admission of each chunk (`quota.begin_voice`).** The server reads the learner's remaining messages in the day window and
   reserves `min(chunk messages, remaining)` under the bucket lock (the reserve of D-161, no SQL or schema change): not even
   one left is `429 quota_exhausted` and no token; enforcement unreadable (switch, store, catalogue, a conversion that is
   not a positive whole number) is `503 quota_unavailable` and no token. It dispatches immediately before the mint, mints the
   token for the seconds the reserved messages buy (a shorter chunk when fewer remain), and settles the whole chunk at once; a
   mint that fails settles 0. Two sessions at once cannot overspend (each reserves under the lock and re-counts after losing a
   race, up to six times; six lost races end as the 429 they are, review P3-1) - proved on PostgreSQL. A repeat of the first
   request's `Idempotency-Key` is `409 operation_finished` or `operation_in_progress`, never a second charge.
4. **Renewal: `POST /api/agent/voice/extend { voice_session_id, chunk, resumption? }` (contract section 9.6).** The client asks
   for the next chunk 12 s before the token it holds dies (`renew_in`, also at once on the vendor's `goAway`), opens the new
   socket beside the old one with the vendor's session resumption, moves the microphone and tool answers to it when its setup
   completes, and closes the old one. `chunk` is the index wanted: a repeat of the last request returns the same token and
   charges nothing, any other index is `409 voice_chunk_mismatch`, a session past its 900 s is `409 voice_session_over`; a failed
   or refused attempt does not use the index up. The vendor's resumption handle, which the client reports, is validated
   (`A-Za-z0-9._:=/+-`, at most 2,048 characters) and put into the new token's locked setup, so a client cannot make the vendor
   resume anything but what the server named. No message left (`429`), an unreadable limit (`503`) or any other refusal means no
   next chunk: the token held plays out, the learner is told once (the quota toast) and the session ends when it dies. A client
   that never renews, or vanishes, costs exactly the chunks it minted; the server forgets the session when its newest token
   dies. `/voice/end` only stops further chunks. The 900 s ceiling holds across the chunks. Messages not enforced: one token for
   the whole 900 s, no renewal (the old path).
5. **Precondition (a paid live check the human runs, not this change): that Gemini closes an already-open socket at the token's
   `expireTime`.** The change is NOT safe either way. Every chunk a learner can obtain is charged when it is minted, so a
   client that stops renewing is bounded by the chunk it holds - but only if the vendor ends the socket when the token dies.
   If it does not, usage per open is bounded only by the vendor's own audio-session limit (about 15 minutes), and a client that
   ignores its token's life can stay on one socket that long for the price of one chunk; only a server-proxied socket could
   bound that. **Voice together with `orena.message` enforcement therefore stays testers-only (:8021) until the live check
   confirms the vendor closes at `expireTime`.** Two more unverified vendor behaviours, checked by the same single run
   (`check_token_expiry.py`: one session, a token of about two minutes, one short text turn, one renewal carrying a handle,
   then silence; under a cent): (a) whether `sessionResumption` is accepted inside an ephemeral token's locked setup. There are
   two ways it can fail. The mint can be refused: voice is unavailable (503, the client's cascade) and nothing is charged. Or
   the mint succeeds and the vendor refuses the socket at connect time because of the field: then every metered session
   fails after its first chunk was charged, so `AGENT_VOICE_RESUMPTION=false` takes `sessionResumption` out of the setup (a
   renewal then carries on with the same instruction and a fresh context); (b) whether the handle is honoured on reconnect.
   Session resumption is part of the metered, chunked path only: with enforcement off the setup sent to the vendor is
   exactly what it was before this change.
6. **Provider cost telemetry stays separate from quota.** The ledger row (`agent_voice` / `gemini` / `gemini-3.8-live`,
   `audio_seconds`, USD from `ai/pricing.py`) is written, for a metered session, per chunk when its token is minted, at the seconds
   the token lives: the most the vendor can charge for it, whatever the learner does next (an unmetered session is recorded as
   before: its wall-clock seconds, at most the cap, when it ends or is swept) (it also closes the review's note that the ledger and
   the daily AI spend brake were undercounted by an early end). Gemini Live reports its real usage only to the client on the
   socket and the ledger has no field for tokens (a schema decision reserved to the human), so the token's life is the figure
   the server can know. The allowance is what the learner is charged; the ledger is what the vendor charges.
7. **Accepted, recorded.** (a) A refused microphone permission or a connection that never came up still costs the chunk's
   messages (the token existed); the client does not report "never connected" because a client report cannot lower a server
   charge. (b) A learner whose day has fewer messages than a chunk needs gets a shorter token and sees no countdown (the design
   draws none, `UI_BACKEND_GAPS.md` QTA-4). (c) Renewing 12 s before expiry means the next token overlaps the old one by
   about 12 s: the learner is charged for chunks of 120 s that cover about 108 s of conversation each (paid, not credited back: about 10% less usable talk, said in contract section 3.3). (d) The session registry
   is per process (R26): after a restart a renewal is a 404 and the client ends the session; with several workers a request can
   land on a worker that does not know the session (404). Keep one worker until the registry is shared. (e) `refuse_unmetered`
   stays in `quota.py` as a generic helper for the media-import slice; voice no longer calls it.
8. **`/api/speech/transcribe` (Groq Whisper, QTA-14): no new meter, but no longer unbounded (review P2-4).** Evidence it is not
   plan-metered: it is speech-to-text *input*; no caller scores pronunciation with it (`assessPronunciation` is called only by
   `capabilities/speaking-take.js`, the `pronunciation.audio` rooms); push-to-talk's transcript becomes a message turn that is
   already one `orena.message`, so metering the transcription too would charge twice; the five speaking rooms (Free talk,
   Conversation, Situation, React, Reading transfer) put the transcript in an editable draft; and Groq costs about 1/25 of an
   Azure pronunciation minute. The guard (human-approved), all on the route and none a plan limit: (a) one take is at most 300
   seconds, measured by the server (it decodes the upload with ffmpeg - a MediaRecorder webm carries no duration - and stops a
   second past the limit): `413 speech_asr_take_too_long`, undecodable audio `422 speech_asr_unprocessable_audio`; the upload is
   at most 12 MiB on this route (the provider's own 24 MiB `max_bytes` is untouched, because the media pipeline sends the same
   provider its own 600-second chunks); (b) one account sends at most 60 minutes of audio in any 24 hours
   (`SPEECH_ASR_DAILY_SECONDS`, default 3600), each take counted at least the provider's 10-second minimum, a sliding window kept
   **in this process** like the other per-account brakes (a restart resets it; N workers each keep their own; a ledger-backed
   count is the follow-up once the shared store backs the brakes): `429 speech_asr_daily_limit` with `Retry-After`; a failed
   provider call is not given back, it is a bound on spend; (c) Orena's push-to-talk sends `purpose=orena_voice`, and the server
   first checks, read-only and reserving nothing (`quota.check_available`), that at least one `orena.message` remains in the
   learner's day: `429 quota_exhausted` before any audio is read, `503 quota_unavailable` when that cannot be read. The message
   itself is charged when the transcript reaches the agent as a turn. The client shows the quota toast for that 429 and
   does not retry.
9. **AGENT_CONTRACT v8** (`contract_version: 8` in `docs/project/AGENT_CONTRACT.md`, `writing_coach/agent/contract.py`,
   `static/orena/agent/contract.js`, `static/orena/copy/surfaces.json` regenerated, the pin in `scripts/test_orena_surfaces.mjs`).
   Section 9: the session answer and `extend`'s carry `chunk`, `max_seconds` (this token's life, no longer the session cap),
   `session_max_seconds` (900), `renew_in` and `last`; section 9.6 `extend`; section 9.7 `end` (stops further chunks, refunds
   nothing); 429 `quota_exhausted`, 503 `quota_unavailable` and the 409/403 rows; section 3.3 what a voice session costs; the
   headers of section 3 apply to the session request and `X-Orena-Timezone` to `extend`. The interim `quota_voice_not_metered`
   of v7 is gone. A v7 client reads `max_seconds` as its session cap and so ends its voice session after one chunk (it then
   falls back to its cascade); no event, action or intent changed.
10. **Client.** `openVoiceSession` sends `Idempotency-Key` and `X-Orena-Timezone`; a `429 quota_exhausted` carries the server's
    figures and the voice screen shows them as the Respond room's toast with "See all plans" and does not start the device
    cascade; the 409 handling refreshes the learning language only for `target_language_mismatch`, never for `operation_*`
    (review P3-2). The live client keeps the cap timer of the token it holds, renews as in point 4 and tells the learner once
    when a renewal is refused; the push-to-talk transcription sends its purpose and shows the same toast. No visual was added
    (the design draws none, rule 43).
11. **Activation.** Voice is off on :8000 (`AGENT_VOICE_ENABLED=false`) and stays so; this works on :8021 once the switch lists
    `orena.message` and voice is enabled there (a paid Gemini Live call: the human's gate, after point 5's check). Switch off or
    `orena.message` not listed: the session is exactly the old unmetered path (one 900 s token, no renewal, no read, no bucket).
    Before QA check that the catalogue stored on :8021 has `voice_seconds_per_message` (a missing or invalid value fails
    closed: 503).


## D-170 - Target-language count enforced on the server: the languages an account holds, judged where it adds one

2026-10-10, the human's decisions relayed by the coordinating session, implemented on branch `feat/entitlement-languages`
on top of D-161 (quota core) and the meters that followed. The number is assigned at merge. **Needs independent
architecture review before merge** (entitlement enforcement; a change to the reviewed account-settings write path; an
implementer may not self-approve). No schema change, no migration.

1. **What is enforced.** `languages.target` is a COUNT entitlement of the plan catalogue (catalogue v2: Free / Plus / Pro 1 / 2 / 2,
   administrator-editable, stored `product.plan_catalog`; numbers unchanged). It is not a time-window bucket: no window, no
   reservation, nothing to settle, never admitted through `admit()` (`quota.admit("languages.target")` raises). The rule lives
   in `writing_coach/product/language_limit.py`.
2. **What "owned" means (server-derived, never client-declared).** The target languages an account HOLDS are the union of (a) its
   stored learning language (`users.learning_language`, set only by the two mutations below), (b) the language of every row it
   owns that is scoped to a language - every mapped table with `user_id` -> `users` and `language_code` (15 today: profiles,
   essays and revisions, grammar/listening/shadowing/speaking progress, saved words, library items and collections, vocabulary
   decks, text discussions, reading attempts/projections/legacy sessions; found from the ORM metadata, a drift test names them)
   and (c) its non-deleted works (drafts, conversations, notes) of its ACTIVE incarnation. Only languages the registry enables
   count. `persistence/language_ownership.py` reads it; nothing is stored for it.
3. **The rule.** Adding a language the account does not hold, when it holds the plan's limit or more, is refused: `403
   language_limit_reached`, context `{feature, limit, owned, languages, plan, upgrade: "#/plan/pricing"}`; a plan whose catalogue
   disables the entitlement answers `403 feature_not_in_plan`. Nothing changes server-side: the stored language, the settings
   version and the session are untouched, no row is created or deleted. Switching to a language the account already holds is
   always allowed - after a downgrade 2 -> 1 both languages stay switchable and nothing is deleted; only a third is refused.
4. **Where it is judged - every mutation that gives an account a learning language.** `POST /api/platform/language` (the Settings
   picker and onboarding) and `PATCH /api/account-settings` with `learning_language`. A switch without a settings token to a
   language not held is no longer session-only: it is written (against the token the server reads under the lock) so the
   adoption leaves a trace. The learner-profile PUT/PATCH writes the profile of the session's language and sets no learning
   language. The check and the write happen in ONE transaction with the `users` row locked `FOR UPDATE`
   (`PostgresAuthRepository.update_account_settings(guard=...)`): two concurrent additions of different new languages at
   limit - 1 admit one and refuse the other (proved on PostgreSQL; removing the lock fails the tests). A stale token is the 409 it
   always was, judged before the limit.
5. **Plan and catalogue.** The limit is read at each mutation from the strict catalogue and the account's effective plan
   (subscription -> catalogue), so an administrator's plan change applies to the next mutation and a catalogue edit as soon as the
   catalogue's own cache (5 s, in other workers) allows. A downgrade changes only what can be added.
6. **Failure modes.** The catalogue or the plan unreadable: ADDING fails closed (503 `quota_unavailable`, `context.reason`
   `catalogue` / `subscription`, retryable); switching to a language the account holds needs neither and still works. The store
   that holds the data cannot answer (no PostgreSQL, the switch unreadable, no ownership reader): the server cannot tell a held
   language from a new one, so every selection answers 503, like every other enforced entitlement. Never "unlimited".
7. **Switch.** The same switch as the meters: `ORENA_QUOTA_ENFORCEMENT` / `ORENA_QUOTA_METERS` and the admin setting
   `product.quota_enforcement` may list `languages.target`. `quota.WIRED_ENTITLEMENTS = ("languages.target",)`; `WIRED_METERS` is
   unchanged and is still every bucket meter, `ENFORCEABLE` is both; `GET /api/product/admin/quota` reports `wired_entitlements`.
   Off, or not listed: nothing here runs and both routes behave exactly as before. The unavailable state lists it too.
8. **Local mode.** Authentication off: the one local account ("legacy") is judged identically; its `users` row is created by its
   first settings write as before.
9. **A recreated account.** Held languages derive from the account's rows, its `users` column and its active incarnation. The
   deletion workflow (`deletion_enumeration.py`, not built, D-055) resets the column, deletes the rows and keeps the old
   incarnation as the barrier, so a recreated account holds nothing and adopts a language like a new one (tested by simulating
   that workflow). The seven tables that were missing (`essay_revisions`, `library_collections`,
   `reading_ability_projections`, `reading_attempts`, `reading_legacy_sessions`, `text_discussions`, `vocabulary_decks`) are
   now in `ACCOUNT_KEYED_TABLES`, and a test fails if a table `language_ownership` counts is not enumerated (review F4).
10. **Plan & usage.** `GET /api/product/commerce` reports `features["languages.target"]` with `used` = languages held, `limit`,
    `remaining`, `usage_state` `known` (`not_metered` when not enforced), no `resets_at`. A count at its cap is not "exhausted":
    what is held stays usable. The design draws no usage row for it (its Plan frame lists the four meters; the count is in the
    comparison table only), so none was added (rule 43); recorded as QTA-7 for the human.
11. **Client.** Onboarding and the Settings picker tell the server's refusal in EN/VI/ZH from its figures ("Your plan includes 1
    target language, and you already have 1. Choose one you already learn, or see the plans."), as the quota toast with "See all
    plans" (the Respond room's pattern); they count and decide nothing. The picker is unchanged.
12. **Accepted, recorded (QTA-7, QTA-18).** (a) Held is derived, not a record of adoption: a learner who deletes everything they
    wrote in a language and is not learning it frees that slot. (b) A stale session on a language the account no longer stores,
    written into after the account added others elsewhere, can create data in a language beyond the count; closing it needs an
    explicit adopted-languages record (a table or column: a schema decision reserved to the human). (c) The stored learning
    language counts, so a Free learner who picked a language and used nothing cannot change their mind to another new language;
    switching back to a held language works. (d) Native clients receive the same 403 envelope.
13. **Activation.** :8021 may list `languages.target` after review; :8000 needs the explicit human GO and the architecture review
    of D-161 points 6-8 (not the adopted-languages record of point 15, which a third language needs).
14. **Review of the first version (REQUEST CHANGES at bd6c01fa; F1, F2 fixed).** (F1) A token-less first choice by an account
    that never chose is, while enforced, written against the token the server reads under the lock, so the guard always judges
    it; the session is set only after a judged write or for a language the account holds. Two such choices racing admit one and
    refuse the other (403), proved on PostgreSQL with the reviewer's probe. (F2) While the count is enforced a session that has no
    language of its own does not remember "the account had not chosen": the middleware reads the stored language again (one
    primary-key read) until the session has one, so a session cannot keep writing in the default language after another session
    stored one; if that read fails a write answers 503 `quota_unavailable` (`context.reason: "language"`) and a read carries on.
    Not enforced: the old once-per-session lookup, unchanged. (F6) The plan's limit is read when the adoption is made, before the
    account row is locked; a failed read is raised only if the write adds a language. (F7) A plan whose catalogue disables
    `languages.target` (or whose limit is 0) refuses a new account's first language, so onboarding cannot complete on it:
    administrators must not disable it for a plan learners can be on.
15. **Precondition for a third target language (review F3).** With English and Chinese only, a stale session cannot take an account
    above what it legitimately held (the independent reviewer confirmed that activating `languages.target` with English and
    Chinese only does NOT need the record below). Before a THIRD target language is enabled in the registry, add (a) an
    explicit, monotonic adopted-languages record (a table or a JSON column on `users`: a schema change, a human gate and an
    independent architecture review) and (b) a per-request admission - the session's language must be one the account adopted -
    or bind the session language to the account's `settings_version`. Residual, accepted (P3): a session-only switch made
    before the switch was turned on survives up to the cookie's lifetime (14 days, `max_age`) and is a one-time grandfathering.
16. **Review of the second version (REQUEST CHANGES at f817b373; F8 fixed).** (F8) An account that never stored a learning
    language runs in the default language, which nothing had judged. While enforced, a mutating `/api/` request from such a
    session is refused with 409 `learning_language_required` (context `{feature: "languages.target"}`), unless the default
    language is one the account already holds (an English learner from before the count who never stored a choice) or the route
    writes no learner row. The exempt routes are listed in `language_limit.LANGUAGE_FREE_PREFIXES` (choosing the language, the
    account settings, sign-in, billing, plan administration, feedback) plus any route with an `admin` path segment; every other
    mutating route is covered by default, and a test enumerates the app's mutating routes and fails if the exempt set changes. A
    failed read of what the account holds answers 503 `quota_unavailable` (`reason: "language"`). This closes the in-flight write
    (the language is judged at the request's start) and the onboarding regression. Client: onboarding stores the learning
    language BEFORE any profile write - a support language picked first is shown at once and written only after a language is
    stored (`target-first.js`), the Continue on the Languages step stores the language the screen shows, and a 409
    `learning_language_required` is told as "Choose the language you are learning first." in EN/VI/ZH - so a Free learner can pick
    a support language and then Chinese (holds only Chinese). (F9) The limit is read when the adoption is made, before the row
    lock: a downgrade committed in that window can miss one in-flight adoption; the next mutation sees it (accepted). (F10) The
    middleware asks whether the count is enforced only for a request that has no language of its own and goes to `/api/`.

## D-171 - Pricing details reachable; a refused language opens the plans with the reason

2026-10-10, two learner reports, branch `fix/pricing-and-language-limit` on `origin/main` a514dba9. The number is assigned at merge.
Client only: no server, schema or catalogue change.

1. **"On the Pricing page I can't scroll down to see the details of what each plan includes."** Root cause:
   `static/orena/screens/plan/plan.css` made `.s-plan__scroll` (the Plans region, `overflow: auto`) a flex column whose sections
   could shrink (`flex-shrink: 1`), and `.s-pricing-compare` (the Compare plans table, `overflow: hidden`, line 334) has an
   automatic minimum height of 0. The column squeezed that card to its padding (measured at 1366x768: 16 px high, rows clipped
   to nothing; the region scrolled only 49 px) so the table of what each plan includes could never be reached. Fix: the region's
   sections keep their height (`.s-plan__scroll > * { flex: none }`) and the region scrolls. After: the Compare card is 344 px at
   1366x768, the region scrolls to its end (scrollHeight 1063 for 686), and on the phone (390x844) every card (449 px) and the
   table are reachable with no page scroll and no horizontal overflow. Plan & usage shares the region and the rule.
2. **The design draws Pricing as a long page; rule 49 keeps it a workspace.** The design lists `pricing` (and `billing`) in its
   focus list and draws one long column (hero, three cards, Compare plans, Questions). Rule 49 forbids a long page for a learning
   workspace, so the route stays focus with the header fixed and the column scrolling in its own region - the layout was
   already that; only the squeeze was wrong. No rule is loosened. Each card lists the five meters (messages a day, writing
   reviews a month, pronunciation minutes, media import minutes, target languages) with the catalogue's limits, and the Compare
   table has a row per meter with a value per plan, all from `GET /api/product/plans` (the Questions list and the popularity tags
   stay undrawn, as before - UI_BACKEND_GAPS "New export frames").
3. **"The message that I can't choose another language is hard to see and disappears quickly. It should open the pricing table
   right away, with the explanation of why there is this restriction."** A refusal of a target language (403
   `language_limit_reached`, or `feature_not_in_plan` for `languages.target`) from Settings or onboarding no longer shows a toast.
   `showLanguageLimitNotice(ctx, error, requested)` holds the server's context in memory (`plan/reason.js`) and navigates to
   `#/plan/pricing?reason=language`. Plans shows the kit's Banner (dismissible, sticky at the top of the region): "Free includes 1
   target language. You're learning English. To add Chinese, upgrade to Plus. Nothing was changed." - the limit, languages held
   and plan from the 403 `context`, the language tried from the caller, the plan to upgrade to from the catalogue (lowest plan
   above the learner's allowing more; "No plan includes more target languages right now." when none), names in the interface
   language, EN/VI/ZH. Dismissing it, or Back, leaves the learner on the language they have; nothing changed server-side and
   nothing is enforced on the client (the numbers are the server's). After a reload the address still says why and the sentence
   is built from the plans alone.
4. **Other quota refusals do not follow.** 429 `quota_exhausted` (writing reviews, Orena messages, pronunciation, media import)
   happens in the middle of a task; navigating to Plans would discard a take, an essay, an import sheet. They keep their in-room
   sentence with "See all plans" (QTA-1). The two kinds read correctly apart: a meter says what was used ("You have used 2 of 2
   writing reviews this month."), a count cap says what the plan includes and what the learner holds.
5. **Not a sheet.** The design's Billing Sheet is the change-plan / cancel / card flow with a price summary and a confirm; it
   has no place for a reason, so the explanation is the design's Banner on the Plans page rather than a new sheet.
6. Gates: `scripts/test_orena_screen_plan.mjs` (all five meters on every card and in the Compare table, EN/VI/ZH; the CSS guard
   for the region) and `scripts/test_language_limit_notice.mjs` (the refusal opens `#/plan/pricing?reason=language`, the
   explanation from the context in EN/VI/ZH, no client counting). The toast sentences `languageLimit` / `languageNotInPlan` are removed
   with their only caller.

## D-172 - Operational policies are edited in Admin

2026-10-11, explicit human requirement: "All tuning must be in Admin; changing something must never require touching code."
Implemented on branch `feat/admin-policies` (from `main` at a514dba9). Independent architecture review (Claude Opus 5.5,
Delegated Architecture Reviewer): APPROVE WITH CONDITIONS at b962e957, APPROVE at 567fec42
(`docs/reviews/architecture/ADMIN_POLICIES_REVIEW_2026-10-11.md`).

1. **One document.** The operational parameters the server carried as constants or environment reads that govern product
   behaviour, cost and limits are the `platform.policies` row of `platform_settings` (`writing_coach/policies.py`): versioned
   JSON `{version, values: {key: value}}`, a typed registry (kind, range, unit, default, optional environment variable),
   unknown keys rejected, defaults equal to the constants they replace (a test pins each one), an empty document is the
   defaults. The audit (`docs/project/UI_BACKEND_GAPS.md` "ADM-POL") classifies every parameter: 37 are operator policy (A), the
   rest are safety internals that stay in code with their reasons (B) or deployment/secret configuration that stays in the
   environment (C).
2. **Same contract as the plan catalogue (D-153).** Save is a compare-and-set on the stored version
   (`expected_updated_at`, 409 on a stale page) with the audit row (`platform.policies.update`: who, each key's from/to, what
   was confirmed) committed in the same transaction. Reads are cached 5 s per process; the process that saves sees it at once.
3. **Precedence: environment > Admin > default.** A variable that is explicitly set pins its policy (the policies that had
   one keep it - `AGENT_VOICE_ENABLED`, `AGENT_DAILY_SPEND_CAP_USD`, `FEEDBACK_RETENTION_SWEEP`, ...), the page shows it
   "locked by environment" and the server refuses to change it. Production pins stay authoritative.
4. **Read at use time, no restart.** Every class-(A) consumer reads the effective value when it acts: the agent limits
   through `LiveAgentLimits`, the limiters through callables, the daily spend guard, voice (`VoiceService` now always exists
   where the agent does; its session cap, chunk size and resumption are policies, while whether voice is on stays
   `AGENT_VOICE_ENABLED`, the human's activation gate), speech take/brake/concurrency/no-speech charge, media caps and
   estimates, route rate limits, feedback limit, the three retention jobs (the schedule threads always run and ask the switch;
   nothing is deleted unless it is on), the word-audio cap and the quota settlement choice. An empty document behaves exactly
   as before (the existing suites pass unchanged except where a test asserted the old start-up-only wiring).
5. **Danger.** A switch or period that deletes data, and a spend cap raised past its sane maximum (or removed), is 422
   `confirmation_required` until the request carries `confirm[key]: true`; the page asks in a dialog first, and the audit row
   records the confirmation.
6. **Fail-safe.** A settings store that cannot be read never raises into a request: the last values this process read stay in
   force (the defaults if it never read any), a warning is logged, and a failed read is cached as briefly as a good one so a
   down store is not asked on every request. (Deliberately stronger than "use the defaults": a blip must not lift an
   Admin-set spend cap back to none.) A stored value that is not valid now, or a key this build does not know, is ignored and
   logged, never half-applied. The quota enforcement switch keeps its own fail-closed rule (D-161 point 8) and is not a policy
   of this document.
7. **The quota switch joins the page.** `GET`/`PUT /api/product/admin/quota` (D-161) are reused, not duplicated; they gain
   `updated_at`/`updated_by` and an optional `expected_updated_at` (409), and the page shows the switch, its meters and who
   last changed it. Environment variables still win there.
8. **The page.** Admin > Operations > Policies & limits (`#/admin/operations/policies`, `screens/admin/policies.js`), kit
   blocks only, EN/VI/ZH, gate `scripts/test_orena_admin_policies.mjs`; routes added to the admin authorization matrix.
9. **Review of b962e957 (APPROVE WITH CONDITIONS), fixed in the next commit.** (P1-1) The agent daily spend cap is read
   strictly (`policies.value_strict`): a worker that has never read the settings store, or whose stored cap no longer
   validates, refuses turns (fails closed) instead of treating "unknown" as "no cap". (P1-2) A save without
   `expected_updated_at` is a compare-and-set against the version it just read (409 on a race), so a server-side merge
   can never revert a concurrent change. (P2-1) `voice.enabled` is not a policy: paid live voice stays the human's
   activation, `AGENT_VOICE_ENABLED`. (P2-2) `quota.abandoned_settles`, `speech.no_speech_charged` and `voice.chunk_units`
   (rules the human decided) need confirmation on any change (`danger: charging`). (P2-4) the media price estimates have
   a minimum above 0 (0 would disable the spend caps). (P2-5) Retention periods can only be shortened: their maximum is
   the published legal value (`docs/legal/public/facts.json`: 90 days agent turns, 24 months feedback; privacy: 13 months
   AI cost records). **Admin is now the activation point for the retention sweeps** (D-159: switching the feedback sweep on is
   the human's activation, :8000 included): both sweep variables are unset on :8000 today, so an administrator can switch
   deletion on there, confirmed and audited; pin `FEEDBACK_RETENTION_SWEEP` and `AGENT_TURN_RETENTION_SWEEP` in the :8000
   deploy to keep that gate in the environment. (P2-7) Only opening a session and the voice list are refused when voice
   is off; an open session can still be used and ended, and an unmetered session is billed at most its minted seconds. (P3)
   a store read error during a save is a 503. Follow-ups P2-3 (Agent Contract v8 drift) and P2-6 (synchronous settings
   read on the event loop) are recorded in `UI_BACKEND_GAPS.md` ADM-POL.
10. **Not done, recorded.** Provider wiring, keys, URLs and activation gates stay in the environment (C); `AGENT_ENABLED` as a
   runtime kill switch and the Groq/Azure model names as Admin settings are later slices; per-process limiters stay per worker.
11. **Design (rule 43), human decision 2026-10-11.** The pinned `Orena Admin.dc.html` draws no Policies page; the human
   approved this page built from the existing Admin kit blocks only, with no new visual pattern.
12. **Strict cap read refuses turns on a cold worker.** A worker that has never read the settings store refuses agent
   turns until it can, even on a deployment with no cap set; this is the safe direction (review P3 note).

## D-173 - First public-beta release of main 9bf88666 to :8000, with migration 20261008_0030

2026-10-11, explicit human authorizations, after release gates 1-4 passed (`docs/reviews/RELEASE_GATE_8021_2026-10-11.md`):
"Authorize deploy 9bf88666 to :8000" and "Cho phép áp migration 0030 lên :8000".

1. **Release.** Image `orena:main-9bf88666`, built from `git archive 9bf88666a6b521124f8adf4f8df301b93efcc093` after
   `node scripts/build_public_pages.mjs --release --effective-date 2026-10-11`. The repository keeps `effective_date`
   null; the stamped date exists only in the release tree and image (D-162).
2. **Migration.** `20261008_0030` (grammar content store, additive; independent review REV3) is applied to :8000 by
   `scripts/product_migration_pack.py apply` with `--authorization D-173`, after a fresh `product_backup.ps1` backup and a
   passing `product_migration_rehearsal.ps1` on a copy of that backup, with web and worker stopped.
3. **Pinned in the :8000 operator env.**
   - `AGENT_VOICE_ENABLED=false`: voice is off for the first release. ADM-POL P2-3 blocks voice activation.
   - `ORENA_QUOTA_ENFORCEMENT=on` and `ORENA_QUOTA_METERS` = all five meters.
   - `FEEDBACK_RETENTION_SWEEP=on` and `AGENT_TURN_RETENTION_SWEEP=on`. Pinning keeps these deletion gates in the
     environment rather than in Admin (D-172).
4. **Operator.** The human runs every :8000 step (D-127), using the operator script prepared by the Claude lane. Daily
   backup rotation (`runtime_backup.py rotate --days 30`) is scheduled after the deploy.

## D-174 - Grammar corpus published on :8000

2026-10-11, explicit human authorization ("cho phép"). The authorization answers the question whether the two Grammar packages
may be imported and published on :8000 through Admin.

1. **Packages.** These are the packages already published on :8021. The zips are kept outside Git in
   `%LOCALAPPDATA%\orena-product\content\grammar\2026-10-08\`:
   - `en-complete.zip`: batch `2026-10-08.en.complete`, package hash `66a941e6…`, 215 points.
   - `zh-complete.zip`: batch `2026-10-08.zh.complete`, package hash `6ae62b58…`, 380 points.
2. **Procedure.** The reviewed Admin path (`proposals/ADMIN_GRAMMAR_UI.md`), run by the human on :8000 (D-127), EN then
   ZH:
   1. `#/admin/imports/grammar` → Check (a dry run).
   2. Rights basis Orena original, attested (HG-3).
   3. Import.
   4. `#/admin/grammar` → Accept all shown, with a reason.
   5. Publish accepted, attested.

   The expected result is EN 215 and ZH 380 published, with the same package hashes as :8021.
3. **Why.** After migration 0030 (D-173), the learner Grammar surface on :8000 shows the honest empty state, because
   no package was imported. It needs no code change.

## D-175 - Phone Dictation keeps the Transcript while typing; the hint is an eye

2026-10-11, human bug report on the phone (Listening workspace, Dictation mode), branch `fix/mobile-dictation` on
`origin/main` 9bf88666. The number is assigned at merge. Client only: no server, schema or contract change.

1. **"While typing a word I cannot see the transcript below, and I cannot scroll."** Root cause: the typing state of
   mobile QA BUG-02 (`.s-listening.is-typing`, set while the answer box has focus and sized to `visualViewport`) set
   `display: none` on `.s-listening__transcript`, so the Transcript and its scroll region were gone for as long as the
   keyboard was open, and the space under the card stayed empty. Measured at 390x844 with the keyboard at half height
   (visible 422 px): before, Transcript `none` and 121 px of empty room under the card; after, the Transcript's rows
   fill everything under the card as their own scroll region - 212 px at 390x844 (296 px with a 40% keyboard), 160 px
   at 360x740, 124 px at 375x667 - and the current line is framed by the existing pane observer. While typing the room
   holds only the task (transport, answer, hint, Check) and those rows; the header (title, meta, mode switch and its
   Back), the picture, seek bar, the card's label and the Transcript's title and hint return when typing ends (the
   keyboard's own dismiss, or a tap outside the answer, ends typing; LEX-043's Back-closes-the-keyboard is therefore not
   reachable on the phone while typing). The Transcript takes what the task leaves (`min-height: 0`), so on the
   shortest screens it yields, never the answer box. No page scroll, no horizontal overflow in any measured state.
2. **"In Listening the transcript area is far too small to read."** In Dictation on the phone the picture (veiled while
   a line is unchecked) is the compact 96 px strip short phones already use, and when the card can run long (a checked
   line's comparison, or the hint's live strip) the Transcript keeps at least 30% of the body while the card's stage
   scrolls inside it, actions in view. Transcript body, before -> after: 390x844 unchecked 185 -> 285 px, checked 49 -> 164
   px; 360x740 unchecked 92 -> 181 px, checked 49 -> 132 px. Desktop is unchanged (1920x1080, 1366x768).
3. **"The hint should be an eye icon only, as little text as possible."** Human decision, deviating from frame 07, which
   draws the hint as a text button with its ladder note beside it. On the phone the hint is a 46 px button with Lucide
   `eye` (pinned `lucide-static@0.525.0`, already in `kit/icons.js`), its label ("Hint", "More hint (2/3)", "Hint 3/3 used",
   EN/VI/ZH) kept as its `aria-label`, tooltip and visually hidden text; the ladder note is no longer printed and is its
   `aria-describedby`; the put-away toggle (LEX-033) is a chevron (`chevron-up` / `chevron-down`) named the same way, so
   two eyes never sit side by side; Check is the one wide, filled action - the geometry of the result row (LEX-037). The
   desk keeps the frame's words.
4. Gate: `scripts/test_orena_dictation_workspace.mjs` (the eye and its names in EN/VI/ZH, the note as description, the
   phone hiding words and note and the desk hiding the glyph, no typing rule hiding the Transcript, the visible-viewport
   sizing, the Dictation share after the short-phone floors). Recorded in `UI_BACKEND_GAPS.md` "Phone Dictation".

## D-176 - Grammar "Accept all" is one server request, not a browser loop

2026-10-12, human bug report (public Admin: 380 Chinese points stopped when another Admin section was opened).
`POST /api/admin/grammar/review` takes `{version_ids (1..1000), decision, reason}` and applies each through the same store
method as the single route (its own transaction and history event, same rules), per item and not all-or-nothing, because a
refused version (closed, unknown, reason missing) must not block or hide the rest: the answer is `{reviewed, failed:
[{version_id, code, message}]}`. One audit row per batch (`admin.grammar_review_bulk`: decision, count, failed); the
per-version history events remain in the store. No schema change. The screen sends one request, so leaving it no longer
stops the work. Publishing stays all-or-nothing (`/publish`).

## D-177 - AI cost per account: migration 0026 promoted into the chain (source control only)

(Placeholder D-17H until merge. The migration's own docstring keeps "D-17H": the file is bound to the rehearsal's
execution digest, and editing it would void the rehearsal.)

Date: 2026-10-12. Human instruction 2026-10-12 ("Chuẩn bị bước 1 và 2 cho 0026"), after :8000 logged
"AI cost per account not recorded (ProgrammingError)": the AC-2 recorder (D-decision of 2026-10-04,
`proposals/AI_COST_PER_ACCOUNT.md`) shipped before its table, by design, and skips recording while `ai_cost_records` is
absent.

1. **Promotion.** `20261005_0026_ai_cost_records.py` moves from `migrations/proposed/` to `migrations/versions/` unchanged
   except its docstring; it becomes the single head, on `20261008_0030`. Revision id and file name are kept (no runtime has
   ever applied it). The proposed `20261005_0027_billing_orders.py` stays proposed and still chains on 0026.
2. **Reviews.** The 2026-10-05 independent review (APPROVE WITH CONDITIONS on `50e66c2` plus the uncommitted AC-2 files;
   conditions met in `e54a2aa3`) is not bound to a committed SHA, so a delta review of this promotion at its exact SHA is
   recorded in `docs/reviews/architecture/AI_COST_0026_REVIEW_2026-10-12.md` before merge.
3. **Rehearsal.** On a fresh backup of :8000, with `scripts/product_migration_rehearsal.ps1` against this tree (operator
   step, D-127); evidence recorded with the review.
4. **Not authorized here.** Merging, and applying 0026 to any runtime, are separate human gates. Once merged, every
   PostgreSQL runtime that takes the code must apply 0026 before it starts (startup refuses a schema below head), the same
   operator path as 0030 (D-173): backup, rehearsal, `product_migration_pack.py apply`.
5. **Legal text.** The published privacy page already states AI use and cost records are kept without content for 13
   months and deleted with the account (`docs/legal/public/privacy.*.json`, `account-deletion.*.json`); no public text
   changes. `docs/legal/DRAFT_PRIVACY.md` is a superseded draft and is not edited.
6. **Review outcome (Opus, delegated reviewer, at `af7b957b`): APPROVE WITH CONDITIONS**, no P0/P1. Required before merge
   and done in the next commit: (finding 1) account deletion keeps the `users` row, so the FK cascade never fires -
   `ai_cost_records` joins the deletion enumeration as `ACCOUNT_ID_KEYED_TABLES`, with a test, and the "deleted with the
   account by cascade" wording is corrected everywhere; (3-6) stale or forward-dated text fixed. Not blocking, recorded:
   one write error pauses recording for every account in that process for 5 minutes - revisit before any quota reads
   this table (2); the published "13 months" is literal while `ai_costs.retention_days` can shorten it (7); ORM
   `server_default` for provider/model (8); `scripts/rehearse_grammar_content_store.py` is a one-off 0030 record whose
   head checks fail if re-run (9). Conditions before apply on :8000: rehearsal on a fresh backup against the final merged
   tree; one maintenance window (stop, backup, plan, apply, deploy, start - the 0030 image refuses to start on a 0026
   database); rollback = `alembic downgrade 20261008_0030` (drops the records) or restore; after start, the warning stops
   and one priced call writes one row; the human's authorization recorded.

## D-178 - The vocabulary card is the existing vocabulary entry, shown differently

(Placeholder D-178 until merge.)

Date: 2026-10-12. Human decisions of 2026-10-12 (lane `claude/vocab-card-import`), after the request to bring the
EN/ZH flashcard design (Claude Design artifact "Flashcard từ vựng Anh – Trung", `docs/vocab/`) into the Words screens.

1. **No card entity.** A flashcard is a presentation of the existing `vocabulary_entries` row. No new table, column,
   migration, card API or card lifecycle. `vocabulary_entries` stays the source of truth; Save, `saved_words`, the
   scheduler, TTS (`/api/vocabulary/{word}/audio`), Word Detail, Collection Detail, search and Review are reused as they
   are. `docs/vocab/` (schema, README, the two samples) is committed as the authored-entry contract and test fixtures;
   `writing_coach/vocabulary_entry.schema.json` is its byte-identical runtime copy (a test holds the two equal).
2. **Typed `usage_notes`.** Entry-level card facts live as typed items in the existing JSON list `usage_notes`, with a
   closed `type`: `collocation | synonym | antonym | word_family | related | classifier | memory_tip | usage |
   common_mistake` (`writing_coach/vocabulary_usage_notes.py`). A legacy item with no type is `usage`. Free usage text is
   never presented as a common mistake: `/api/library/vocabulary/{word}/deep` `commonMistake` reads only
   `type: "common_mistake"` items and the payload gains `usage`. Example-level content (`highlight`, `reading`,
   `reading_highlight`, language-tagged `label`/`translation`/`explanation`) lives as keys of each `examples` item; a
   Chinese character's pinyin and Hán-Việt are orthography unit readings (`notation` `pinyin`/`han_viet`) - Hán-Việt
   never goes into `readings`, where a second reading would stop a saved word linking to its entry.
3. **Moderation stays per set.** pending_review → approved → published on the collection. The file's `status` is never
   read into server state; an authored import always lands pending review (no auto-publish, even with cleared rights).
   No per-entry moderation.
4. **Published duplicates are blocked.** An authored row matching an entry in any published set is refused as a
   conflict, listed in the preview and the import result: no overwrite, no membership snapshot, no unpublish. Overwrite
   or skip (default skip) applies only to entries in sets that are not published. Editing published content is a
   separate workflow under the existing lifecycle.
   **Identity (human review of PR #133).** The authored id is an editorial handle in `provenance.source_id`, not a
   sense: an authored entry's identity is `lang|term|pos|` with an empty sense, so ids never inflate identities. An
   authored row is the same lexical entry as any stored entry with the same language, normalized term and part of
   speech, whatever that entry's sense key (a CSV row's sense is its meaning fingerprint), or with no part of speech:
   one such entry is the duplicate (skip / overwrite / published conflict); several are an `ambiguous_conflict`,
   refused, because writing would have to pick one; the same id under another part of speech is an
   `identity_conflict`, refused. So the importer never creates a second entry for a (language, term, part of speech).
   Another part of speech is a distinct entry; retrieval is already deterministic and needs no new `ORDER BY`:
   `find_entry`, `list_entries_for_language` (and the saved-list resolver built on it) order by `identity_key`, and
   search and neighbours by term length then `identity_key`. The authored format has no sense field, so two senses of
   one word and part of speech cannot both be authored; adding one is a schema decision for the human.
   **Localizations after an overwrite.** Read precedence (`_merge_localization_rows`): an entry's own
   `short_meanings` win for every language they carry and a selected localization only fills a language they lack,
   so a localization of replaced content would keep showing in exactly those languages. In the overwrite's own
   transaction, localization rows derived from the old content (`source`, `dictionary`, `pivot_translation`) are
   deleted - the import's localization pass derives them again - and rows a person wrote or reviewed (`curated`,
   `reviewed_batch`) are kept but unselected and marked `validation.stale`, never shown until someone selects them
   again. No schema change.
5. **Pure mapper.** The learner-side `toVocabularyModel()` (PR 2) is a pure content mapper; saved state, review stage
   and due date are an optional decorator applied by the caller, so the Admin preview renders the same component and
   mapper with no learner context. Server side, `vocabulary_card_from_catalog_entry` carries no learner state and the
   saved-word projection keeps it under its own `memory` key (tested).
6. **Save and Review are separate.** Word Detail and the Feed offer Save, never a grade. A Review session contains only
   words already in `saved_words`; nothing is saved silently. Flow: card → Save → `saved_words` → scheduler → Review.
7. **Two review buttons.** "Not yet" → `again`, "Got it" → `got_it` on the existing
   `POST /api/library/vocabulary/{word}/review`. `unsure` stays in the API for compatibility and is not surfaced.
8. **Order.** PR 1 import adapter and projection support (this entry); PR 2 the shared `VocabularyCard` (modes `detail`,
   `feed`, `review-front`, `review-back`) beside the compact `VocabularyRow`; PR 3 the Admin preview derived from A14
   with the production card; PR 4 the two samples loaded on :8021 only. Open design items: `UI_BACKEND_GAPS.md`
   "Vocabulary card (D-178)".

## D-179 - One VocabularyCard: four modes, two review buttons, Save apart from Review

(Placeholder D-179 until merge.)

Date: 2026-10-12. Human decisions of 2026-10-12 for PR 2 of D-178 (lane `claude/vocab-card-ui`).

1. **One card, one mapper.** `static/orena/product/vocabulary-card.js#toVocabularyModel` is the only mapping from what a
   surface holds about a word (a saved item, a catalogue card, a raw entry, the list's seed, the Word Detail lookup) to
   what the card draws. It is pure content: no saved state, stage, due date or learner sentence goes in or comes out;
   `learnerState(item)` is a separate decorator the screen applies. `kit/vocabulary-card.js` draws it; the Admin preview
   (PR 3) renders the same component and mapper with no learner state.
2. **Layout is the human's flashcard reference; style is the theme.** The card's layout and information come from the
   human's design reference for this component, the Claude Design canvas "Flashcard từ vựng Anh – Trung" (artboards
   `Main.dc.html`, English, and `Chinese.dc.html`, Chinese): a two-face card - the front with the level and source,
   part of speech, headword, readings, meaning, word family and synonyms/antonyms (Chinese: per-character pinyin over
   the Hanzi, Hán Việt, meaning, radical, measure word, related words), the back with numbered examples, structure,
   collocations and the memory tip - turned by "See examples ->" / "<- Front". Colours, type and components are the
   current theme's (tokens, `o-tag`, `o-btn`, the kit's discs and highlight); the reference's accent, faces and the
   Chinese paper/seal look are not carried. A section with no data is left out. Modes: `detail` and `feed` (the two
   faces, starting on the front, with Save), `review-front` (the recall face: the word, its reading, part of speech,
   level and audio - nothing that answers), `review-back` (the two faces; the grades are outside the card). Compact
   rows stay rows (`VocabularyRow`, PR 2b); a rich card never replaces a row.
3. **Two review buttons.** "Not yet" sends `again`, "Got it" sends `got_it` (Vietnamese "Chưa nhớ" / "Đã nhớ", the human's wording 2026-10-12, used everywhere the grade is named), each labelled with the interval the
   scheduler reports for that card. `unsure` stays in `POST /api/library/vocabulary/{word}/review` and has no button;
   the session summary counts the two. Supersedes the three-button choice in Review's earlier surface report.
4. **Save is not Review.** Word Detail and the Feed offer Save and never a grade; a Review session
   contains only words already in `saved_words`; nothing is saved silently. Flow: card -> Save -> `saved_words` ->
   scheduler -> Review. The Review back draws no bookmark in this PR (human gate 2026-10-12: keep the remove toggle only if
   removing mid-session provably leaves the queue, session and scheduler intact). It did not yet: grading a word just
   removed answers `missing` and the screen shows a save-failure toast before moving on. So Save and remove stay in Word
   Detail and the Feed; a Review remove toggle is a follow-up that must first skip a removed word cleanly (UI_BACKEND_GAPS
   VC-11 in the vocabulary-card section).
5. **Content rules.** Highlights find the authored span (`match`/`occurrence`): Latin as a whole word, Hanzi where it
   stands; the pinyin span is lit only when it can be found, never the whole line. Support-language content shows only
   in the learner's support language; the meaning alone falls back to another language, tagged. No illustration, no
   frame. Tokens only; the ZH card differs by type and content order, not colour.
6. **Provenance.** Layout: the human's flashcard reference (point 2), recorded in the component's header. Style:
   tokens and kit components. Adaptations: the save disc joins the reference's top row; each IPA row has its own play
   disc (both play the word's one voice); collocations are `o-tag` chips; Chinese examples are numbered 一, 二 as the
   reference draws them; the meaning panel shows the kit's skeleton while the lookup is out and the word's
   own-language definition, tagged, when it is the only meaning. Open items: `UI_BACKEND_GAPS.md` "Vocabulary card
   (D-178)".

## D-180 - The vocabulary card wears its design's own palette (a scoped colour exception)

(Placeholder D-180 until merge.)

Date: 2026-10-12. Human decisions of 2026-10-12, PR 2c of D-178 (lane `claude/vocab-card-skin`): "the card must LOOK
like the design, not only follow its layout".

1. **Source.** The human's flashcard design, now pinned in `docs/design/vocab-card/` (`Main.dc.html` English,
   `Chinese.dc.html` Chinese, `MainDark.dc.html` / `ChineseDark.dc.html` importing them with `theme="dark"`). Its
   `renderVals` palettes - light "watercolor paper", dark "night violet", the Chinese card's `seal` - supersede the
   earlier blue/red screenshot.
2. **A deliberate exception, scoped.** The vocabulary card - and nothing else - takes that palette: card-scoped tokens
   `--vcard-*` (bg, surface, surface-alt, line, ink, ink2, ink3, accent, on-accent, gold, seal, on-seal, btn-bg,
   btn-ink) with the design's light and dark values exactly. This is a human-approved exception to "one palette, no
   colour skin" (AGENTS.md "Theme", D-089). The tokens still live in `kit/tokens.css`, the one colour owner, and
   the card's content reads no other colour token (gated). **Buttons keep the app's kit design** (the human,
   2026-10-12: "Các nút bấm là giữ nguyên thiết kế của app. Flashcard chỉ tập trung phần nội dung thôi"): the turn
   actions are the kit's `o-btn` primary / secondary, the play and save discs the app's icon-button colours, the
   stroke-practice button the kit's, and in Review the grades, Reveal and Hint keep the screen's own styles - no
   `--vcard-*` token on any button (gated). The skin is the content: card surface and rules, headword, readings,
   sections, tags and pills, chips, examples, highlights, the illustration frame. The rest of the app, and in Review
   the screen around the card, keeps the app's tokens.
3. **AA.** Every pair the design draws as text holds 4.5:1 in both themes as designed - no value changed
   (`scripts/test_orena_kit.mjs` VOCABULARY CARD, 16 pairs per theme). One deviation: the design's focus ring is a 2px
   gold outline, and light gold `#C9A24B` is 2.25:1 on the card surface (2.10:1 on the paper), under the 3:1 a focus
   indicator needs; the card keeps the kit's own focus ring instead (light `#5A55E3`, 4.46-5.12:1 on the card grounds;
   dark `#847FF6`, 5.74-6.03:1). Gold draws rules and borders only, never text (gated).
4. **Type.** No font download (human decision). English uses the app's sans; the Chinese card uses a local serif for
   Latin text (Noto Serif, Georgia) and a local Song stack for Hanzi (Noto Serif SC, Source Han Serif SC, Songti SC,
   STSong, SimSun), weight 900 where the system font has it.
5. **Shapes as drawn.** English: 1px line border, 20px radius, the accent C1 tag, the outlined part-of-speech pill.
   Chinese: the paper with 14px around a ruled frame - a 1.5px gold border and a 1px gold line inside it - 6px radius
   (approved: a gold rule, not a violet ring, D-147), the seal HSK tag, the 1.5px seal radical box. Highlights: English
   bold accent over a 2px accent underline; Chinese seal at 900, the pinyin span bold seal. Buttons: the app's kit
   buttons, not the design's (point 2).
6. **Illustrations.** A frame only when there is an image: an upload, or a library drawing named by the stored
   `provenance.illustration.ref` in `kit/vocabulary-art.js`. The two drawings are the design's own, ported as reference
   art for the two docs/vocab samples only; production artwork stays under the Art Bible (`assets/brand/orena/`) and
   comes from Admin upload (PR 3). No schema change, no upload path.
8. **Refinements after the lead's browser check (human decisions, 2026-10-12).**
   - *Chinese typography:* all content text on the Chinese card is serif, set on every element of the card (the app's
     `:lang(vi)` rule sets the interface face on each Vietnamese element, which an inherited family loses to). Hanzi-only
     text and the headword: `"Noto Serif SC","Source Han Serif SC","Songti SC",STSong,SimSun,NSimSun,serif`. Every other
     line - Vietnamese, English, pinyin, and mixed lines whose Hanzi fall through to the same Song stack - leads with
     `"Noto Serif",Cambria,"Times New Roman"`: SimSun and Georgia lack the pinyin tone letters (ǎ ǐ ǒ ǔ ǖ ǘ ǚ ǜ) and
     Vietnamese, and a missing letter fell back glyph by glyph ("huǒ" drawn as o and a detached caron); Cambria and
     Times New Roman ship on Windows and carry both. This orders mixed Vietnamese/Hanzi lines Latin-first, a deviation
     from "Song stack first for mixed text" for that reason. Only the controls keep the app's sans. No web font.
   - *Buttons:* superseded the same day by the human - every button keeps the app's kit design (point 2): the Review
     grades are the screen's own pre-2c "Chưa nhớ" (red soft) / "Đã nhớ" (accent fill), the card's turn actions
     `o-btn`, the discs the app's icon-button colours.
   - *No app palette on the content:* every content tag, chip and accent is `--vcard-*` - the level tag, the
     collocation chips, the meaning's language tag ("Tiếng Anh", drawn by the card; the screen only names the language),
     the mastery bars and the stroke-order tiles a screen places inside (no kit `o-tag`).
   - *Header as drawn:* the top row is the level tag (and source) on the left and the part of speech on the right, on
     one row (it may wrap at 360, the part of speech staying the last item). Play and Save leave the top row for a quiet
     action row under the reading (44px discs); the IPA rows are plain readings as the design draws them. Derivation:
     the design draws neither control, and of the options (under the reading, beside the turn action, top-right of the
     headword line) this one keeps the drawn hierarchy and the turn action alone in its foot.
9. **One viewport (human, 2026-10-12).** The card fits inside one viewport in every
   mode (Design Contract rule 49, CLAUDE.md 6b): each face is a head (the design's top row / the back's title line)
   and a foot (the turn action) that stay, around the only scroll region, its body. Before the body scrolls the card
   recomposes: spacing and the headword scale with the viewport's height as well as the card's width (the design's
   values the ceiling), the illustration frame shrinks with the height and drops out on a short card. Word Detail
   gives its card the visible height of the column below it on arrival (`fitVocabularyCards`, again on resize), so the
   card and its actions are in view without a page scroll, stopping above the floating phone bar and its orb; Review's
   and the feed's cards (focus routes, no phone bar) fill their slot. Review's Reveal and Hint keep the screen's own
   (app) button styles, per point 2.
10. **The card scales as one composition (human, 2026-10-12, after a phone review: "too big and coarse ... loses the
   card's designed look").** The design's 520px artboard is the reference: every content measurement - headword,
   readings, labels, meaning, body and example text, tags, pills, chips, radical box, padding, gaps, radii, the double
   rule's inset, the illustration's height - is `min(design px, design px / 5.2 cqi)`, i.e. the design value times
   s = min(1, card width / 520) (cqi = the card's own width). Desktop (a card 520px or wider) is exactly as drawn; a
   328px phone card is s = 0.63, the same card smaller (headword EN 37.8px, ZH 65.6px, meaning 13.9px, illustration
   EN 113.5px / ZH 94.6px). Readability floors only: body, meaning and example text 13px, labels and tags 11px, pinyin
   and IPA 12px. All content stays on a phone - the illustration no longer drops on a short card; a face taller than
   its card scrolls in its body only, head and foot fixed. Buttons are exempt (the app's kit sizes, 44px targets).
11. **A face never scrolls (human, 2026-10-12: "A card face must NEVER scroll internally, in any mode. The whole face
   must be fully visible on screen, especially on mobile").** Supersedes the body scroll of points 9 and 10. The card
   fits the composition to its box by "contain": s = min(widthScale, heightScale). The CSS gives the width scale
   (point 10); `fitVocabularyCards` measures the showing face's natural height at it and, when that is taller than the
   box, sets the height scale in three phases, measuring again each step: (1) spacing, gaps and radii (`--vc-ks`, to
   0.5) with the illustration (`--vc-ka`) following but held at 60% of its width-scaled height; (2) the type
   (`--vc-kt`, to 0.55) with the illustration shrinking in proportion (ka = 0.6 x kt); (3) spacing alone, to 0.3. It
   fits to a pixel inside the box, so a face is never left a hair over (lead's 360x740 check: the ZH front stopped at
   s 0.803 with `fits` no). `--vcard-s` / `data-vcard-s` record the achieved height scale, `data-vcard-fits` whether it
   fits. The radical box stays a square beside its text: it follows spacing down to a 32px floor (or its width-scaled
   size when smaller) and its glyph is sized from the box (36/56), so the glyph never runs onto the text. The face's need is
   its head, foot and the body's CONTENT (to its lowest child), not the body's scrollHeight: a card that fills a taller
   slot (Review's revealed face) has a stretched body, which read as always full and was shrunk while it fit (lead's
   check of e9e5f3d1: s 0.933, fits no); within a pixel of the box counts as inside. Hard floors, reached only when the box needs them: body, meaning and example text 11px, labels and
   tags 9.5px, pinyin and IPA 10px (point 10's 13/11/12 hold at full height). Every element stays, the illustration
   included; the buttons keep their kit sizes (44px+). It fits again on resize (Word Detail, Review, the feed), on
   turn (the other face) and once the web fonts arrive. No `overflow: auto/scroll` on the card, a face or its body
   (scripts/test_orena_vocabulary_card.mjs).
12. **Portrait on a wide screen (human, 2026-10-12, option 1).** At 1355x855 the Word Detail card was 820px wide and
   Review's 640px: a wide, short panel with a thin art band. The card is capped at `max-inline-size: 520px` - the
   design's artboard (docs/design/vocab-card/canvas.json, every board 520 x 880), the width where s = 1, so the cap adds
   no stretch the design does not draw - and centred (`margin-inline: auto`). Word Detail's Context and Evidence keep
   their layout; Review's session (header, card face, grades) takes the card's width when the row is a word card, so
   the grades line up with it (a cloze row keeps 640px); the feed's slot is already narrower; phones are unaffected.
7. **Kept.** Every D-179 behaviour (modes, the recall face, grades outside the card, no Review bookmark, meaning
   order, reading guards, the pure mapper), the copy packs, and rule 49 (a fluid card whose padding scales with its
   width, the design's values as the ceiling).

## D-181 - The phone shell hides on scroll

(Placeholder D-181 until merge.) Human decision, 2026-10-12.

On a phone, in the browsing places that have the phone header and the phone bar (Design Contract rule 47: the
non-focus routes - Today, Discover, a content detail, Orena, Practice and its skill hubs, Library, a collection, Word
Detail, Grammar, Progress, Profile, Coming soon), the header and
the bar - with the Orena orb - slide away while the page scrolls down and come back when it scrolls up, and always at
the top of the page.

- **Rule 47 is unchanged in what it decides:** which places have the chrome. A learning workspace (focus route) still
  has none, and the desktop rail and top bar never move. This decision only adds a scroll behaviour to the phone
  chrome where rule 47 draws it.
- **Mechanism (static/orena/shell/, a protected area; minimum change):** one scroll listener on the main column
  (`shell/chrome-scroll.js`, bound by `shell/frame.js`); the state is `data-chrome` on the shell root (absent at the
  top, `hidden`, `shown`); `shell/shell.css` lays the header and bar over the column on phone browsing places (the
  column keeps their room as padding, so a page at its top sits where it did) and hides them by a transform, so
  nothing reflows. Under `prefers-reduced-motion` there is no slide, only show / hide.
- **Accessible:** a control of the chrome that has the focus is never hidden (focus brings the chrome back); nothing is
  hidden at the top; every route arrives with the chrome in place (the router resets the state), so Word Detail's card
  fit (D-180) is measured with the chrome visible.
- **Open (UI_BACKEND_GAPS VC-17):** back over a page that is not at its top, the header takes the phone bar's chrome
  surface so the page does not run through its controls; the design draws the header only at rest.
- Gated in scripts/test_orena_shell.mjs (phone-only scope, the state attribute, the transform, reduced motion, the top
  reset, focus).
- **Word Detail arrives collapsed (human decision 2026-10-12, option 1).** With the chrome showing on arrival the
  card had about 474px at 360x740 (a thin illustration band, secondary text near its floors). On a phone, Word Detail
  (`#/word/:id`, `route.chrome = 'collapsed'`, `:root[data-chrome-start='collapsed']`) now opens with the header and
  the phone bar already hidden by the same `data-chrome="hidden"`; only the screen's own back row stays, at the top.
  While collapsed the column gives up the chrome's room (padding-top the status-bar inset, padding-bottom the
  home-indicator inset), so the card fits the whole height (card top to the window's bottom, less the inset and a
  16px gap). The chrome comes back on scroll up, on a pull (wheel / touch) or a tap on the page outside a control at
  the top, and when a chrome control takes the focus - the learner is never left without navigation. The rule when it
  comes back: the column takes the chrome's room again and the card **fits again** (the shell announces every change as
  `orena:chrome`; Word Detail re-runs `fitVocabularyCards`), so the header and bar never cover the card's actions.
  Every other browsing place keeps "visible at the top, hidden on scroll"; desktop and learning workspaces unchanged.
  Gated in scripts/test_orena_shell.mjs (only Word Detail arrives collapsed, only on a phone; the top stays collapsed
  until the learner reveals it; the reveal listeners) and scripts/test_orena_vocabulary_card.mjs (the collapsed fit
  has no bar and the column's whole height; it stops above the bar again when the chrome returns).

## D-182 - The vocabulary card is light in both app themes (its dark variant disabled)

Human decision, 2026-10-12.

- **The card is always light.** `VocabularyCard` renders with the design's LIGHT card palette whatever the app theme,
  on every surface: Word Detail, the Daily Feed, Review's recall and revealed faces (and Admin's preview, later). Under
  `:root[data-theme='dark']` the `--vcard-*` tokens resolve to their light values (`kit/tokens.css`); the content -
  serif Chinese, chips, highlights, the line drawings - reads only those. The shell and the app around the card keep
  following the learner's theme.
- **Disabled, not deleted.** The design's dark ("night violet") values are recorded in a comment in `kit/tokens.css`,
  applied nowhere, until the dark card is redesigned (UI_BACKEND_GAPS VC-18). D-180's two-theme palette stands
  otherwise.
- **Edge on a dark page.** In the dark app the card draws its own 1px line round itself (the Chinese card included),
  so the light card sits cleanly on the dark shell; never the app's violet (D-147), and no app accent or dark token is
  used to blend the card into dark.
- **Buttons.** The turn actions and discs stay the app's kit buttons (D-180) and follow the app theme, so in the dark
  app they are dark buttons on the light card. Measured (scripts/test_orena_kit.mjs): labels primary 4.54, secondary
  16.06, save disc 7.12, play disc 9.35, saved disc 8.40; fills against the card's surface / bg / surface-alt at least
  3.70:1 (the primary's, on surface-alt). No clash; nothing restyled.
- Gated: the card tokens equal the light values under `data-theme="dark"`; the recorded dark values are the design's;
  AA for card text is one set in both themes; the kit buttons hold AA (label) and 3:1 (fill on the card) in the dark
  app; the edge rule uses the card's line.

## D-183 - The vocabulary card's header, illustration and lead, as the human placed them

Human decisions, 2026-10-13, after reviewing the two real cards (resilient, 森林) on :8021.

- **Header.** The level tag, on the English card its source, and the part of speech sit together on the left; play
  and Save sit alone at the top right, drawn 34px (each still a 44px touch target: a 44px button whose 5px padding is
  unpainted and taken back by a -5px margin). The discs never leave the first line; the left group wraps in its own
  column when the card is narrow. The action row under the reading is gone.
- **Illustration.** It takes the room that row had: 220px (EN) / 190px (ZH) at a 520px card, was 180 / 150 - "the
  picture is what the card is remembered by". Still scaled by the card's width and contained to the viewport.
- **Chinese lead.** Meaning and Radical are two columns, in exactly the columns and column gap of the Measure word /
  Related words pair below, so Radical lines up with Related words and a longer meaning wraps in its own column.
- **One card, one size.** Both faces have the card's one height from the first paint: the fit measures both faces and
  keeps the taller (never past the box), and a turn keeps it.
- **Support language.** The QA account's support language is Vietnamese (the samples' translations, explanations,
  example labels and memory tips are Vietnamese); a learner whose support language has no translation still sees
  none - no other-language fallback for example content.
- Gated in `scripts/test_orena_vocabulary_card.mjs`.


## D-184 - Admin vocabulary import previews the production card

Human decision, 2026-10-13: PR 3 scope.

- The admin vocabulary import previews an authored entry file with the production VocabularyCard, beside the design's
  rows list (UI_BACKEND_GAPS VC-23). The preview response carries each ready row's normalized record (admin-only, no
  schema or route change); the card shows the authored content, before dictionary completion and localization.
- Duplicates skip / overwrite surfaces the importer's existing behaviour (the `duplicates` form field, default skip);
  a published-set conflict stays refused.
- Image upload is split out of this PR. The preview works without an image.
- Gated in `scripts/test_orena_screen_admin_areas.mjs`, `scripts/test_orena_vocabulary_card.mjs` and
  `tests/test_vocabulary_source_routes.py`.

## D-185 - Signed-out local-admin belongs to the request boundary, not to configuration (issue #137)

Placeholder id; the lead renumbers at merge. **Status: independently reviewed, APPROVED WITH CONDITIONS
(`docs/reviews/architecture/SEC_137_LOCAL_ADMIN_REVIEW_2026-10-13.md`, commit f7a9dc77); conditions addressed in
follow-up commits; the human accepted the residual risk below on 2026-10-13.** Not merged, not product approval.

- **Residual risk, accepted by the human 2026-10-13 as a documented residual risk.** The Docker-gateway trust rests
  on a self-declared `ORENA_PUBLISHED_BIND_HOST`; the app cannot observe the real publish. An operator who hand-edits
  the Docker publish from `127.0.0.1` to `0.0.0.0` without changing the variables the app reads defeats it (on Docker
  Desktop LAN traffic then arrives from the trusted gateway). This is a manual, unsupported misconfiguration, not a P1
  blocker, **on the conditions** that auth-off lanes are local/development only and every official launcher is
  test-locked to a loopback publish (`tests/test_local_boundary_deployment.py` scans all compose files and launch
  scripts; the primary boundary is the deployment config/launcher, the per-request peer check is the second layer, the
  startup refusal is defense-in-depth). **Follow-up, not in this change (GitHub issue #140):** a host-side runtime assertion - the
  launcher/preflight runs `docker inspect` (or equivalent) on the real published address and refuses or stops an
  auth-disabled lane bound to `0.0.0.0`, `::` or any non-loopback address. DNS rebinding (follow-up) and the
  `host.docker.internal` cross-network case remain documented residuals in `docs/SECURITY_BOUNDARY.md`.

- **Finding.** With sign-in off, `require_admin()` and the shared `legacy` learner scope were granted from
  deployment configuration (`APP_ENV`, `PUBLIC_BASE_URL`), and Compose published port 8000 on `0.0.0.0`: any LAN host
  (or a tunnel to a development runtime) was the local administrator. Config-local was read as request-local.
- **Decision.** Locality is decided per request from the transport peer (`writing_coach/core/request_boundary.py`):
  loopback, or the container's own default gateway when the operator declared a loopback-only publish
  (`ORENA_TRUST_DOCKER_PUBLISHED_PORT` with `ORENA_PUBLISHED_BIND_HOST` loopback; Docker's port proxy makes a host
  browser arrive from the gateway). A forwarding header, a public environment, a missing peer all mean not local.
  Host, Origin, `X-Forwarded-*` and `PUBLIC_BASE_URL` are never evidence. Configuration only restricts. A non-local
  request to an auth-disabled runtime gets 403 outside public pages. No switch grants a remote peer signed-out access.
- **Loopback-only (human, 2026-10-13).** Development with sign-in off is loopback-only: startup refuses any declared
  non-loopback exposure (PUBLIC_BASE_URL / GOOGLE_REDIRECT_URI host, `ORENA_PUBLISHED_BIND_HOST`,
  `ORENA_INSECURE_DEV_LAN_BIND_HOST`, the tunnel token); only localhost, 127.0.0.0/8, ::1 and ::ffff:127.x pass. The
  in-container listen address and `APP_BIND_HOST` are not exposure. LAN development now requires Google sign-in.
- **Default bind** is `127.0.0.1`; LAN needs `ORENA_INSECURE_DEV_LAN_BIND_HOST` and Google sign-in.
  `APP_BIND_HOST` no longer widens the publish. The public preflight (`validate_public_staging_readiness.py`, run by
  `start_public.ps1`) refuses development with sign-in off and the LAN opt-in.
- **Operational effect.** Containers started outside `compose.yaml` (`docker run`) must set the two trust variables
  to keep signed-out use from the host; otherwise they answer 403. Staging :8000 is unchanged (public, auth on).
- Full policy and threat model: `docs/SECURITY_BOUNDARY.md`. Not done here: non-root container, CSP/`innerHTML`
  inventory.

## D-186 - Official launchers assert Docker's real published address on the host (issue #140)

**Status: independently reviewed and APPROVED (Delegated Architecture Reviewer, Claude Opus 5.5, independent of the
implementer; docs/reviews/architecture/SEC_140_PUBLISH_ASSERT_REVIEW_2026-10-13.md, approved head `894046e8`); merge
authorized by the human on 2026-10-13 when CI is green. Architecture review is not product approval.**
Closes the follow-up recorded in D-185.

- **Decision.** After an official launcher starts the app container, a host-side check
  (`scripts/assert_published_loopback.py`, stdlib only) reads Docker's ACTUAL binding of the app port and refuses the
  lane when any binding is not loopback: it prints the container and the offending address, stops the container and
  exits non-zero. Rule: every binding of the app port (container 8000/tcp) must be 127.0.0.0/8, `::1` or `localhost`
  (the `is_loopback_host` rule); `0.0.0.0`, `::`, an empty `HostIp` (Docker's "all interfaces"), a private or any other
  address, an unpublished port, or an unreadable Docker answer is a refusal (fail closed).
- **Reads.** Only the container's `.NetworkSettings.Ports` and `.HostConfig.PortBindings`, each through a `--format`
  template. Never the whole config, never the environment; no secret is read or printed. Both documents are consulted
  so a stopped container or a hand-edited request is also caught.
- **LAN opt-in.** The only non-loopback path stays `ORENA_INSECURE_DEV_LAN_BIND_HOST` (D-185), which requires Google
  sign-in. A wrapper passes `--lan-opt-in` only when that variable is set in the launching shell, and the check then
  accepts a wide publish only if an unauthenticated `GET /api/me` on the loopback port answers 401 (sign-in is on); it
  does not read container env. A wide publish whose app answers signed-out is refused and stopped. An opt-in set only in
  `.env` is not seen by the wrapper and fails closed; export it in the shell.
- **Coverage.** All seven launchers of `tests/test_local_boundary_deployment.py`: `compose.yaml` (via `start_docker.ps1`,
  `start_dev.ps1`, `start_public.ps1`), `scripts/agent_e2e`, `scripts/agent_live`, `scripts/mobile_qa_runtime.ps1`,
  `scripts/product_restore_rehearsal.ps1`, `scripts/staging_update.ps1`, and `scripts/staging_8000_deploy.ps1`, which
  gets a READ-ONLY check (`--no-stop`) that fails loudly before success is declared; its publish, env and rollback are
  unchanged (human-operated, D-127). A test fails if a listed launcher does not run the assertion after its start.
- **Changed behaviour.** `start_dev.ps1` now runs `up -d --build` then `watch` (a blocking `up --watch` could not be
  followed by a check). `mobile_qa_runtime.ps1` runs detached under the name `orena-mobile-qa-<Port>`, checks, follows
  the log, and removes the container on exit (replacing `--rm`).
- **Not covered.** A container started by hand outside the official launchers; a publish edited after the check ran;
  `docker run` helpers not in the inventory. Same-host proxy, `host.docker.internal` and DNS-rebinding residuals of D-185
  are unchanged. See `docs/SECURITY_BOUNDARY.md`.

## D-187 - A scoped machine credential for vocabulary ingestion (issue #145)

**Status: ACCEPTED.** Changes authentication; independently reviewed (AGENTS.md "Architecture review authority").
Reviewer: Delegated Architecture Reviewer, Claude Opus 5.5, independent of the implementer. Review:
`docs/reviews/architecture/VOCAB_INGEST_TOKEN_REVIEW_2026-10-13.md`. History: CHANGES REQUIRED at 6ec68757 (P1-1, a
token could publish through a non-authored format), CHANGES REQUIRED at 96e23d35 (P1-2, a token re-import could rewrite
an existing published collection), **APPROVED at d4c3e135** with no remaining condition. The auth code
(`auth_support.py`, `writing_coach/service_auth.py`, the two routes in `app.py`, the token tests) is byte-identical to
d4c3e135 at merge. Code comments written before the merge call this decision "D-18X"; it is this entry. Human
merge authorization: 2026-10-13. Not product approval and not activation authorization: enabling it on a deployment
(setting `VOCAB_INGEST_TOKEN_SHA256`) stays a human gate.

Behaviour fixed by the reviews: no publish through the token on any source format (P1-1); `duplicates=overwrite` is
refused, skip only; for the service principal the route returns 422 before any write when the target collection
(supplied or derived id) exists and is not `pending_review` - published, unpublished and archived are all refused,
because a re-import would also move them back to `pending_review` and undo a moderator's decision (P1-2).

- **Finding.** `require_admin()` is session-based (a Google sign-in cookie), and `UserIsolationMiddleware` refuses any
  `/api/*` request without a session before a route runs. The only unattended path is the signed-out local admin, which
  is for the machine's own address only (D-185) and is never available to a public deployment (D-146). So a client with
  no browser - the n8n Vocabulary Generator of `integrations/n8n` - cannot preview or import authored vocabulary into a
  deployed Orena; the manual file import in Admin is the only route.
- **Decision.** One capability, one credential, nothing else:
  - Scope: `POST /api/admin/vocabulary/preview` and `POST /api/admin/vocabulary/import`, exactly. Defined once, in
    `writing_coach/service_auth.py` (`VOCABULARY_INGEST_PATHS`). Any other path or method with the same token is
    answered as an anonymous request (401).
  - Credential: `Authorization: Bearer <token>`. The server holds no secret: `VOCAB_INGEST_TOKEN_SHA256` lists the
    SHA-256 hex digest(s) of the allowed token(s), comma-separated to allow rotation. Compared by digest with
    `hmac.compare_digest` against every configured digest. Unset or malformed means the feature is off.
  - Revocation: remove the digest and restart. Nothing is logged by the credential code; the token is never stored.
  - Who the caller is: a fixed service principal (`service:vocabulary-ingest`, role `service`), never a user. Its request context has a user key of its own (not the shared `legacy` scope); it reads
    and writes no learner scope. `imported_by` of the receipt records it.
  - Lifecycle: for the service principal, on EVERY source format (CSV/TSV/XLSX/TXT/JSON/JSONL, authored or not), the
    import route forces `pending_review`, ignores `publish` and `publication_attested`, skips the cleared-rights +
    complete auto-publish rule and records no attestation. (The first version only forced it for authored entries, so a
    CSV with `publish` published: found by the review below and fixed.) `duplicates=overwrite` is refused with 422;
    the service principal only skips. Authored-entry rules (D-178) are as before.
  - Session administrators are untouched: a request without a bearer token takes the same path as before.
- **Where.** `UserIsolationMiddleware.dispatch` checks the token first, for those two paths only, and sets
  `request.state.service_principal`; `require_vocabulary_ingest` (used by those two routes only) returns it, else
  falls back to `require_admin`. `tests/test_vocabulary_ingest_token.py` walks every route of the app with a valid
  token and requires 401 for all but the two scoped POSTs.
- **Residual risks (accepted in review, tracked as follow-ups).** (1) A leaked token imports `pending_review` sets and previews the catalogue's
  duplicate status (it reveals which words exist, including published ones) until revoked; there is no per-token rate
  limit, expiry or audit actor beyond the fixed principal. (2) The token is a long-lived shared secret in the n8n
  credential store. (3) The middleware branch sits before language seeding and sets a service user key; confirm it cannot reach the `legacy`
  scope. (4) Whether a deployment that wants this should instead use a short-lived, per-client token with an expiry
  (a larger change, deliberately not done here). (5) The collection-state check and the write are separate calls;
closing that race needs the guard inside the `import_source` transaction.
- **Without the token.** File mode and a manual import through Orena Admin; see
  `integrations/n8n/README.md`.

## D-188 - A derived "General catalogue" collection per language (Option A)

**Status: ACCEPTED.** Changes what reaches learners; independently reviewed (Delegated Architecture Reviewer, Claude
Opus 5.5, independent of the implementer), `docs/reviews/architecture/VOCAB_GENERAL_CATALOGUE_REVIEW_2026-10-13.md`:
design APPROVED WITH CONDITIONS at 1c30c70d; code review APPROVED at a1f06e48; re-review of the published-snapshot fix
APPROVED at a8c06b59. Design: `docs/reviews/architecture/VOCAB_GENERAL_CATALOGUE_DESIGN_2026-10-13.md`. Human
decisions 2026-10-13: Option A, derived and persisted-only, D-111 sets count (H2), no "publish into General only" (H1),
kill switch on by default (H3), no cache (H4); merge authorized after CI and a 390x844 phone check. Verified on :8021
(PostgreSQL): every General item equals its published collection item. Remaining P2: the level filter matches any
qualifying membership while the card shows the chosen one.

- **Decision (human, Option A).** One automatically maintained "General catalogue" collection per learning language,
  shown to learners as an ordinary collection. Rejected: B (per-word review lifecycle, schema change), C (search and
  word page only). H1 rejected: there is no "publish into General only" act. H2 yes: D-111 rule-attested sets count.
- **Rule.** Derived at read time, never stored. An entry is in General(L) iff it has a membership in a collection of
  language L that is `published` AND whose admission passes `_publication_admission` (rights cleared, complete, approved,
  attested with a reviewer identity), evaluated defensively per collection (a malformed record does not qualify). It
  leaves the moment its last such set stops qualifying. A token import (D-187) never qualifies until a human publishes
  the set. No free (pending, unpublished, archived-only) word becomes reachable.
- **Scope: persisted only.** General(L) is the persisted, admission-valid subset. It is **not** "the union of words
  learners can reach": it excludes static seed collections (not rows of `vocabulary_entries`), words of a set that is
  `published` without a valid admission (F1), and the raw static paths of F3. The F1 and F3 fixes are separate and do
  not change this scope.
- **Withdrawal is by set, not by word or content.** A shared entry row has no rights field and `import_source` merges a
  pending set's data into an existing entry that has no published membership. So an entry first created or enriched by
  set B (later withdrawn for a rights reason) and then included in published set A is in General with B's text; A's
  attestation never covered it. This was already true of the word page and search; General makes it bulk-browsable.
  Accepted; pinned by a test so a later fix is a deliberate change. The emergency lever is the kill switch below.
- **Persistence.** No migration, no schema change, no stored row, no cache. Reserved id `orena-general-<language_code>`
  (NFKC, trim, case-folded prefix match), refused inside `import_source` and at the Admin import, the service-token import
  and the content-pack importer; a stored row under it is ignored (fail closed). Not editable, not exportable, no Admin row.
- **Content shown (fix after browser verification).** A General item is drawn from a QUALIFYING membership (a
  published collection with a valid admission), exactly as a real collection page draws from its own: that membership's
  `content_snapshot` is applied, and its level, framework and topic override the shared row's. The shared entry row is
  never shown when a qualifying snapshot exists, because text merged into it after a set's attestation (or left by a
  withdrawn set) is not covered by any qualifying attestation. When an entry has several qualifying memberships the
  choice is fixed: a membership carrying a snapshot comes first, then the lowest collection id (no publication time is
  stored, so "earliest published" is not available). A non-qualifying membership is never used. It is chosen set-wise per
  page (one query per 500 entries, no query per entry). The levels list and the level filter read the effective level
  of any qualifying membership (the membership's own level, else the entry's), as `_collection_stats` does, instead of
  the shared row's level alone; search and `general_contains` use the term, which a snapshot cannot change (same identity).
- **Kill switch.** The D-172 policy `vocabulary.general_catalogue_enabled` (default on, read per request). Off hides only
  General: absent from the list, detail 404; search, the word page and real collections unchanged.
- **Query.** One combined predicate (OR of chunked `EXISTS ... IN`), ordered `(normalized_term, identity_key)`; more than
  20,000 qualifying collections withholds General and logs rather than truncating. Keyset paging at about 100k entries
  per language.
- **Clients.** `system_kind: "general_catalogue"` plus an English fallback title; one copy key in EN, VI and ZH shared by
  Discover, Library and Collection Detail. General sorts last. No new component.

## D-189 - Reading source policy after the real-source trial (2026-10-13)

**Status: ACCEPTED (human decision, 2026-10-13).** Evidence: `docs/content/READ_SOURCE_CATALOG.md`,
`READ_SOURCE_TRIAL_2026-10-13.md`, `READ_SOURCE_LEARNER_UI_2026-10-13.md`, `READ_SOURCE_ACCEPTANCE_2026-10-13.md`.
This is not activation authorization: no source is published to production by this decision.

1. **Wikipedia / CC BY-SA:** accepted as policy, but the sources stay REJECT_TEMPORARY in the catalogue until extraction
   and attribution/licence handling meet the bar.
2. **NonCommercial (NC) sources:** never published into the commercial or paid Orena catalogue. Internal use only, or
   with an explicit separate permission.
3. **Traditional script:** allowed, but it must carry Traditional metadata and a label, and is never mixed silently with
   Simplified. Global Voices 中文 stays MANUAL_ONLY until the learner UI distinguishes the script.
4. **Attribution / source line:** required before any real corpus is published.
5. **Thumbnail:** not a publish blocker.
6. **The 8 :8021 trial publishes:** kept for the owner's review, then unpublished or archived.
7. **Next milestone, "Reading Sources - Production Readiness":** acceptance target is NASA, Global Voices EN and VOA 中文
   running end to end (source, poll/import, extraction, quality gate, review, publish, attribution, learner card,
   reader) with shippable content. Fix order:
   - P0: A provenance end to end, B the Admin Reading 403, C extraction corruption, D source cleanup, E quality admission.
   - P1: F manual reviewer level, G automatic level, H Chinese kinsoku, I simplified/traditional detection and label,
     J source-specific rules.
   - P2: K thumbnail, L long titles, M Wikipedia.

   The catalogue is not widened until the three sources pass; the next candidates are Chinese public-domain sources
   such as zh Wikisource.

## D-190 - Reading provenance; rights and attribution are audited warnings on a manual publish (2026-10-14)

**Status: ACCEPTED** (independent re-review 2026-10-14, merged once CI was green). A lifecycle change, reviewed
independently of the implementer. It carries out the human decision recorded as D-189 (2026-10-13): attribution or a source line is
required before any real corpus is published. Implemented on `claude/reading-provenance`, "Reading Sources - Production
Readiness" item P0-A.

- **Provenance object.** The learner Reading list (`GET /api/reading/articles`) and detail
  (`GET /api/reading/articles/{id}`) return `provenance`: `publisher` (the source record's name), `url` (the item's
  canonical address), `author`, `license` (`name`, `url`, split from the rights `license_note`), `attribution_required`
  (`required` / `not_required` / `unknown`) and `text` ("Originally published by Global Voices (by Peace News), CC BY
  3.0."). It is derived by one pure function (`writing_coach/reading_provenance.py`) from the source record, the source
  item and the effective rights (the immutable snapshot with the recorded rights answers folded over it). No migration,
  no schema change, no new stored field. A recorded rights answer on a published article bumps `content_revision`, so a
  cached copy revalidates.
- **Policy (amended by the human, 2026-10-14; amends D-105's hard rights gate).** An administrator can always publish a
  Reading text by hand, even when rights or attribution are unknown or denied. Rights and attribution are warnings, not a
  gate: `can_republish` / `can_adapt` denied or never answered (`rights_not_cleared`, `rights_unknown`,
  `adaptation_not_cleared`, `adaptation_unknown`), `attribution_required` unanswered (`attribution_unknown`), and, where the
  terms require attribution, a missing publisher, original address or licence (`provenance_missing`). Publishing over any of
  them needs a deliberate override in the request (`acknowledge_warnings: true`) and a non-empty `reason`. Without the
  override the route answers 409 `reading_rights_not_cleared` listing the warnings (`context.blockers`,
  `context.override_field`); with the override but no reason, 422 `reading_reason_required`. The warnings, reason and actor
  are recorded in the review event (`published_over_warnings`) and the admin audit record. The repository
  (`ReadingContentRepository.set_status`) never refuses for rights or attribution. **No automatic publication while rights
  or attribution are unclear:** the D-111 automatic admission keeps refusing `rights_not_cleared`, `attribution_unknown`
  and `attribution_missing`. Hard gates are reserved for technical or content-integrity faults (empty body, broken
  extraction, not an article), which are not part of this decision.
- **Provenance check.** The same function (`provenance_blockers`) yields the warnings and the automatic-admission refusal.
  It is stricter than the previous admission rule, under which an author name alone sufficed.
- **No retroactive unpublishing.** Published articles stay readable. `scripts/check_published_reading_provenance.py` is a
  read-only checker that lists the published articles that fall short and whether the latest publish decision recorded an
  override; it exits non-zero only for an incomplete credit with no recorded override. What to do with each is a human
  decision.
- **UI.** The publisher is the design's source line on the Discover card, the Content Detail hero and the Reader toolbar.
  The licence and the original link have no place in the pinned design's Reading frames; they reach the learner in
  Settings > Licences and data sources (`GET /api/licences`, whose Reading rows now credit the publisher). Recorded in
  `UI_BACKEND_GAPS.md`.
- **Independent review (2026-10-13).** Delegated Architecture Reviewer, Claude Opus 5.5, independent of the implementer, on
  b94f4129: APPROVED WITH CONDITIONS, `docs/reviews/architecture/READING_PROVENANCE_REVIEW_2026-10-13.md`. Conditions met
  on the same branch: the learner payload names only a recognised licence (Creative Commons or public domain, fixed
  spelling, Creative Commons address) and never the free-text `license_note`, which only sets `license.recorded` for the gate
  (P1-2); negative and leak tests; an exact, size-independent query-count test; `relatednessScore` compares the
  candidate's publisher before its author, on purpose. P1-1 (the `unknown` attribution policy) is left to the human.
  Follow-ups: a source rename should bump its published articles' `content_revision` (no rename path exists today, so
  nothing bumps), the check-then-write in `set_status` (P2-1), scheduling the checker (P2-3), and the Global Voices
  original-publisher fields after PR #157 merges.
- **Re-review (2026-10-14).** Delegated Architecture Reviewer, Claude Opus 5.5, independent of the implementer, on
  94e7374f (change b922f433): APPROVED WITH CONDITIONS - CI green before merge; follow-ups P2-1 (warnings read before the
  write), P2-2 (the repository accepts warnings without a reason; the route enforces it, the checker treats it as no
  override), P2-5 (the admin audit row is written after the review-event transaction). The reader's licence and
  original-link line was decided by the human on 2026-10-14 and is a separate change.

## D-191 - Reading quality admission: non-articles are not published without a reasoned override (2026-10-14)

**Status: ACCEPTED** (independent review, re-review after the merge with D-190, merged once CI was green). Changes the
Reading publish lifecycle. No schema or migration change.
Closes D10 of `docs/content/READ_SOURCE_TRIAL_2026-10-13.md` (milestone item P0-E, D-189).

1. **One definition.** `writing_coach/reading_page_quality.py` owns every quality signal, threshold and code. The
   extractor stores raw-page facts (`analysis.extraction.page_facts`); `quality_flags` turns them, the cleaned body and
   the extraction confidence into stable codes appended to `analysis.quality_issues`.
2. **Hard codes** (the page is not an article): `empty_body`, `media_page`, `index_page`, `bot_challenge`,
   `special_page`. `reading_admin_api.quality_blockers` returns them as `{code, gate: "quality"}`, and a reviewer's
   publish is refused `409 reading_quality_not_cleared`. An explicit `quality_override: true` with a reason publishes
   anyway and is audited (`admin.reading_article_quality_override`). **The two confirmations are independent:**
   `quality_override` never stands in for D-190's `acknowledge_warnings`, nor the reverse; an article with both kinds needs
   both flags and one reason. 409 precedence: `reading_quality_not_cleared` while the quality override is missing, else
   `reading_rights_not_cleared`; both list every blocker in `context.blockers` and the fields still to send in
   `context.override_fields`. The repository enforces only the quality gate (rights never refuse there), so the rights
   confirmation is a route-level, audited requirement; a quality override is not counted as a rights override by
   `scripts/check_published_reading_provenance.py`.
3. **Soft codes** (uncertain, still reviewable): `body_below_minimum`, `extraction_medium_confidence`, `generic_title`,
   plus the existing `too_short`, `too_long`, `language_*`, `repetitive`, `extraction_low_confidence`.
4. **D-111 is unchanged:** any quality issue, hard or soft, means `review`; automatic admission never publishes a
   flagged item.
5. **Empty body** keeps the existing refusal (`empty_source`, "no readable article"); the flag covers other entry paths.
6. **The repository is the last gate.** `ReadingContentRepository.set_status` refuses a publish over a hard code
   (`QualityRefused`) unless `quality_override=True` and a reason are given; the override, its codes and
   `QUALITY_VERSION` are recorded on the article's own status event. The route only translates the refusal, so
   `scripts/agent_e2e/harness.py` and any direct caller are stopped too.
7. **Tightened after review.** `media_page` is hard for ZH only under 260 Hanzi (trial non-articles: 216-245).
   `bot_challenge` needs a short page and a near-exact challenge phrase in the title (or a page under 40 units).
   `index_page` is hard only on a listing title, a listing address, or a listing-shaped body on a page with no
   article element and no prose; a dated listing alone is the soft `index_like`.
8. **Known limitation.** Fact-based codes exist only for URL-extracted pages. Pasted and uploaded text get only the
   body-derived codes, and articles stored before this change have no `page_facts`, so they are not blocked. The
   read-only `scripts/check_reading_quality_backlog.py` lists them; it cannot backfill, so a human decides each one.
9. **Review.** Independent architecture review of `ae8b96db`: APPROVED WITH CONDITIONS
   (`docs/reviews/architecture/READING_QUALITY_GATE_REVIEW_2026-10-13.md`, Delegated Architecture Reviewer, Claude Opus
   5.5). Conditions P1-1, P1-2 and P1-4 are addressed in the commit that records this line; P1-3 (merge with the
   provenance gate) is settled at merge. Follow-ups, not done: recompute body-derived codes when a body is edited, and a
   separate permission for the override.
   Re-review after the merge with D-190 (2026-10-14): Delegated Architecture Reviewer, Claude Opus 5.5, independent of the
   implementer, on 30ab15ff and 3d5a948f: APPROVED WITH CONDITIONS (CI green before merge; this entry's wording). The two
   confirmations are proven independent by route-level tests.

   Tightened 2026-10-14 (`claude/reading-quality-voa`, `reading-quality/3`): a live dry run found two VOA 中文 pages that
   point 7 let through. `voachinese.com/p/6197` (topic page: no article element, one prose paragraph, 193 Hanzi of
   teasers) is now a hard `index_page` through the generic rule "no article structure and a body under 400 Hanzi / 150
   words". `voachinese.com/p/9647` (player page with a programme rundown, 302 Hanzi) is now a hard `media_page` through
   "player markup, no article or main element (`no_semantic_container`) and a body under 600 Hanzi / 200 words". No source
   name is used; the limits sit below the shortest genuine article of the evidence set. Real VOA 中文, NASA and Global
   Voices articles stay clean (fixtures in `tests/fixtures/reading_quality/`). This changes the publish lifecycle, so it
   **requires an independent re-review** before the entry returns to ACCEPTED.
   Known false-positive class, accepted: a genuine short single-paragraph page with no article or main element
   (`index_page`), or a 260-600 Hanzi / 60-200 word article with an embedded player in a plain div (`media_page`), is
   hard-flagged and needs the audited `quality_override` with a reason; the same page inside `<article>` or `<main>` is
   not blocked. `no_semantic_container` is derived from the real absence of an article or main element for every
   extraction method, so a player page that fell back to whole-page extraction is caught too. Tests pin both cases.
   Stored rows: `scripts/check_reading_quality_backlog.py` recomputes from stored facts, so rows with
   `no_article_structure` may newly show `index_page`; rows without the new `no_semantic_container` fact are not
   caught by the media rule.
   Review of 8055ddbc: Delegated Architecture Reviewer, Claude Opus 5.5, independent of the implementer: APPROVED WITH
   CONDITIONS (CI green before merge; fixture attribution README; this entry). Addendum in
   `docs/reviews/architecture/READING_QUALITY_GATE_REVIEW_2026-10-13.md`. Re-review of 87968f7e (same reviewer role):
   APPROVE, no open P0/P1; merged once CI was green.

## D-192 - Reading publisher: the learner-facing name is separate from the internal source name (2026-10-14)

**Status: ACCEPTED** (independent review 2026-10-14, Delegated Architecture Reviewer, Claude Opus 5.5: APPROVED WITH CONDITIONS on 09bd6b60, re-review APPROVE on 47e19c05; merged once CI was green). Refines D-189/D-190. Lane B item 2 of Reading Production Readiness.

Problem: learners saw the admin's bookkeeping name as the publisher ("Global Voices (English) RSS - trial", "QA NASA news
releases (RSS)", "Direct URL"), in the Reader meta, Discover, Content Detail, the source footnote and `/api/licences`.

1. **Storage, no migration.** The source's learner-facing `public_name` lives in the existing `reading_sources.polling_policy`
   JSON (key `public_name`; that column held only `{}`). A dedicated column was not needed; if the policy column is ever
   given a real polling schema, move the key then (that would be a schema change needing independent review).
2. **One pure function** (`reading_provenance.resolve_publisher`) returns `(publisher, via)`. The internal source `name`
   is never an input. The site the text came from is, in order: the source `public_name`; for a built-in path
   (manual/URL/file) only, the name typed for that text; the page's `og:site_name`; the cleaned host of the item address
   (`voachinese.com`). The built-in labels ("Direct URL", "Manual paste", "File upload") and anything containing an address are
   never a name. Nothing known gives an empty publisher, which the D-190 gate reports as a missing credit.
3. **Republications.** When extraction provenance records a republication that names its original publisher, that
   publisher is the credit and the site is `via`: "Originally published by Radio Free Asia via Global Voices". The credit
   link and licence stay the item's own (the republisher's page). Only the publisher is drawn by clients today; `via` is
   carried in `provenance` and in `text`.
4. **Every learner payload** (list, detail, Discover, Content Detail, footnote, `/api/licences` text and source rows) reads
   the resolved name; the admin lists keep the internal name. Changing a source's public name moves `content_revision` of its
   published texts in the same transaction (D-190 follow-up P2-2).
5. **Admin.** `POST /api/admin/reading/sources/{id}/public-name`, a "Public name" field on the register form and on the
   source page. The pinned `Orena Admin.dc.html` draws no such field (`UI_BACKEND_GAPS.md`).
6. **Consequences for D-190 and the licences page.** Because the host is a fallback, the D-190 "publisher missing" provenance
   warning now fires only when no public name, no page site name and no host is known (a text with no address and no typed
   name); a bare host such as `nasa.gov` counts as the credit. Names are trimmed of whitespace and separators only, so
   balanced brackets and the full stop of an abbreviation survive ("Global Voices (English)", "Acme Inc.", "美国之音（VOA）").
   A `/api/licences` source row with neither a public name nor a base-URL host is omitted; its texts are still credited
   one by one in the text rows.

## D-193 - Per-item rights: a staff-only public-domain source does not vouch for wire copy (2026-10-14)

**Status: ACCEPTED** (2026-10-14). Independent review: Delegated Architecture Reviewer, Claude Opus 5.5, APPROVED WITH
CONDITIONS on bdb950a3, re-review APPROVE on 8f2ce5c3. The owner approved the rights policy as written on 2026-10-14,
including the current answers to the open questions: an inline citation in VOA prose still counts as staff writing, and
any byline (an institutional author such as "美国之音" and a contributor included) establishes staff authorship. Merged
once CI was green. No schema or migration change.
Answers catalogue question Q6 (VOA wire copy) in part; the part that stays human is listed at the end.

1. **Problem.** VOA's own staff output is US-government work and in the public domain, but VOA also carries and rewrites
   wire copy (Reuters, AP, AFP) and uses third-party photos, which are not. The VOA 中文 source's licence note made every
   VOA item read as "Public domain", and the learner credit line named it as the licence.
2. **Rule, as configuration.** `writing_coach/reading_rights_refinement.py` holds `SOURCE_RIGHTS_RULES`, keyed by host
   (same matching as `reading_source_cleanup.SOURCE_RULES`). The flag `public_domain_requires_staff_authorship` is set for
   `voanews.com` and `voachinese.com`. No code branches on a publisher's name; another source with the same condition gets
   the same flag. It is a code table, not an admin setting or a column, because the source row has no config column
   (`polling_policy` is a polling field and is unused).
3. **At ingest** (`ReadingContentEngine.process`, where a source's answers are inherited into the snapshot): for a flagged
   host the item is `withheld` when the extractor shows wire evidence, or when it has no byline (authorship cannot be
   established). Then `can_republish`, `can_adapt` and `license_note` are not copied from the source into the immutable
   snapshot. An absent key is the existing "unknown" (`rights_state`), so nothing new is stored and nothing is denied.
   Only keys whose origin is the source are withheld; an answer submitted for the article is kept. Otherwise the outcome is
   `kept` and the item inherits as before.
4. **Effects, all through existing mechanisms.** The review page shows D-190's `rights_unknown` warning (and the existing
   incomplete-credit warning, as no licence is recorded); an administrator publishes only with `acknowledge_warnings` and a
   reason, audited. D-111 refuses automatic admission (`rights_not_cleared`). `recognise_license` finds no "public domain"
   text, so the learner is shown no licence. An administrator can still record the answers on the review page.
5. **Evidence kept.** `source_items.metadata.rights_refinement` and `analysis.rights_refinement`: `outcome`, `reasons`
   (`wire_copy`, `no_staff_byline`), the matching lines (at most five, 120 characters each), and the withheld keys.
6. **Detection is deliberately narrow.** Wire evidence is, in Chinese, a line of at most 40 characters that names an agency
   and is a bracketed credit, a derivation note ("本文依据了美联社的报道", "综合", "编译", "来源：") or a credit label, or a
   dateline `（路透社）—`; in English, a line of at most 160 characters that ENDS on the agency in a credit form
   ("Reuters contributed to this report", "Some information for this report came from AP, Reuters and AFP", "reported by
   AP", "With reporting from Reuters", "adapted this story ... based on reporting from Agence France-Presse"); and a byline
   or attribution line that is an agency. Agencies: 路透社, 美联社, 法新社, 德新社, 彭博社, 新华社, 中央社, 共同社, 韩联社,
   纽约时报, Reuters, AP, AFP, dpa, Bloomberg, Kyodo, Yonhap, Xinhua, CNA, The New York Times (BBC, CNN and other
   non-public-domain outlets are not listed yet). A sentence in a staff story that
   cites an agency as a news source ("路透社说…", "对美联社说…", "澳大利亚联邦警察(AFP)") is VOA's own writing and is not
   evidence ("Reuters reported that ...", "told AP"). One-off measurement, not reproducible from the repository: 213 pages
   fetched from voachinese.com section pages on 2026-10-14 gave 2 with a derivation note, 13 with no byline (video, audio
   and index pages, which the quality gate already holds), and the rest kept. English was checked on a real Learning
   English page (the fixture); no wire-credit line was found on the current voanews.com front-page articles.
7. **Not covered.** Third-party photos and video are not text and are not inspected (catalogue Q1 / D-189). An inline mention
   of an agency is not treated as wire copy; whether to treat it as one is the human's call (below).
8. **Existing data is not modified.** Articles ingested before this change keep their snapshot. The read-only
   `scripts/check_published_reading_rights_refinement.py` judges the stored text now and lists published articles from a
   flagged source that show wire copy or no byline, with whether their effective rights still say "can republish".
9. **Human decisions left.** (a) Whether a published item that asserts public domain but shows wire copy is unpublished or
   given an answer on its review page (the eight trial publishes on :8021 should be run through the script first).
   (b) Whether VOA stories that cite an agency inline are acceptable as staff-written. (c) Whether VOA contributor
   bylines (non-staff names) establish staff authorship, and whether an institutional author ("美国之音", "VOA Learning
   English") counts as a byline: today it does, so a wire rewrite with an institutional author and no credit line is kept. (d) Image rights (Q1). (e) Who maintains the host table.
   Review (2026-10-14): Delegated Architecture Reviewer, Claude Opus 5.5, independent of the implementer, on bdb950a3:
   APPROVED WITH CONDITIONS (English credit forms, further agencies, engine-level origin test, explicit no-byline fixture,
   this entry's wording, renumbering from D-192 to D-193, CI green). The conditions are addressed in the following commit.
   Status stays PROPOSED: the owner approves the rights policy before merge.

## D-194 - Reading thumbnails: a picture needs the source's policy, an approval and a credit; a same-origin copy (2026-10-14)

**Status: ACCEPTED** (owner approved the image-rights policy on 2026-10-14; independent reviews below; no source is enabled
by this change; merged once CI was green). Was PROPOSED. Owner decisions of 2026-10-14 are carried out as written; nothing here turns a source on. No
schema or migration change. Closes U2 of `docs/content/READ_SOURCE_ACCEPTANCE_2026-10-13.md` (D-189 item 5 made the thumbnail
"not a publish blocker"; the human has since made it P1 ship-readiness).

1. **Rights (option B).** A learner sees a picture only when all three hold: (a) the source's image policy allows it
   (`reading_sources.polling_policy.image_policy.allowed`, the source's existing config JSON; absent means off, and no source is
   turned on by this change), (b) an administrator approved that specific candidate (an `image_set` review event), and (c) a
   credit exists (the approved credit, else the candidate's credit, else the learner-facing publisher of D-192, never the
   internal source name). Otherwise the generated letter tile. The rule is evaluated again on every list, detail and image
   read. **Withdrawal:** changing a source's image policy, and rejecting or clearing a picture, moves `content_revision` of the
   affected published articles in the same transaction, the image route stops serving at once (it re-evaluates the rule), and
   it is sent `Cache-Control: private, no-cache` with an ETag from the stored hash, so a browser revalidates every time.
2. **Same-origin copy, never hotlinked.** The candidate is fetched once, at approval, by `writing_coach/reading_images.fetch_image`
   through the existing SSRF guard `media_safe_fetch.fetch_bounded` (http/https only; ports 80/443 only, also on redirects;
   every resolved address must be globally routable, so private, loopback, link-local, metadata, CGNAT, IPv4-mapped IPv6 of
   those and multicast are refused; each redirect hop is re-validated; the connected address is re-checked against DNS
   rebinding; no cookies or credentials; the byte budget is enforced while reading; a total wall-clock deadline bounds the
   whole fetch), with a 5 MB cap, a content-type allowlist (JPEG, PNG, WebP, GIF) and a magic-byte check that ignores the
   declared type (so SVG and HTML are refused). The bytes are stored in the existing `BookAssetStore` under
   `reading-images/{article}/{sha256[:24]}.{ext}` and served by `GET /api/reading/articles/{id}/image` with `nosniff`, a
   `default-src 'none'; sandbox` CSP and `Cross-Origin-Resource-Policy: same-origin`. The learner payload carries
   `image: {url, credit, alt}` with that same-origin address only; a candidate's address never reaches a learner payload.
   The admin preview is also fetched by the server (and kept briefly per candidate so a page view does not refetch), so the
   administrator's browser never contacts the publisher. A failed approval deletes only a file that this call created.
3. **Approval is a recorded answer, no migration.** `image_set` (the approved picture, or `null` to clear) and `image_rejected`
   are `reading_review_events`, folded oldest first like a rights answer (`fold_image_events`). Candidates stay where the
   extractor put them (`metadata.extraction.media`) and are addressed by index, never by address. `polling_policy` now has two
   keys (`public_name`, `image_policy`) and one locked writer, `_update_source_policy`.
4. **Selection.** The og:image, then the lead image, then the article's images. A candidate is not offered when its declared
   or real short side is under 400px, its aspect is outside 1:2 to 2:1, or the same address is on two or more other items of
   the source (shared furniture such as a logo). Checked from the real bytes at approval when the page declared no size.
5. **D-111 is unchanged.** Automatic admission never reads images; a picture changes no admission outcome.
6. **Per-image licence is not modelled.** Approval is the administrator's act and is audited
   (`admin.reading_image_approved`, with the candidate host); the credit is shown, and the licence of an individual image is
   the administrator's judgement (NASA images are carved out of its general statement, Global Voices images are not CC BY by
   default, VOA is mixed). Which sources the owner turns on, and on what credit, is still the owner's call.
7. **Not done.** A superseded, cleared or rejected approved file stays in the asset store (content-addressed, small), so third
   party bytes remain on disk after a withdrawal even though nothing serves them.

**Independent reviews (2026-10-14).** Delegated Architecture Reviewer, Claude Opus 5.5, independent of the implementer:
8980cf3d APPROVED WITH CONDITIONS (merge with D-192, renumber to D-194, route count, CI green); 1d0cddbd APPROVED WITH
CONDITIONS (a per-chunk wall-clock bound on the fetch, a merge with main); 14257a23 APPROVE, no open P0/P1, CI green. Conditions
addressed on the branch: merged with main keeping the learner-facing publisher resolver, one locked `polling_policy` writer,
a per-chunk total fetch deadline and a locked preview cache, immediate withdrawal and cache semantics, delete-only-what-this-
call-created, the candidate host in the audit, and IPv4-mapped, non-default-port and peer-rebinding tests. The owner approved the
image-rights policy on 2026-10-14; no source is enabled by this PR. Browser measurement of the surface is done by the human
before merge.

Note (review of 1d0cddbd): the whole rule fails closed. If the registry row, the stored event or the asset file cannot be
read, the learner gets the letter tile or a 404, never a picture.

## D-195 - AI Cost Router, slice 1: word_translation, OpenRouter free pool, explicit operator failover (2026-10-14)

**Status: ACCEPTED** (2026-10-14). Independent review: Delegated Architecture Reviewer, Claude Opus 5.5, APPROVED WITH
CONDITIONS on 43ce4621, re-review APPROVE on f1f5c60c; merged once CI was green. Owner decisions of 2026-10-14 are in
the design `docs/project/proposals/AI_COST_ROUTER.md` (PR #165). Activation, the OpenRouter key and verifying the two
pinned model ids remain owner actions. No schema, no migration, no UI change. The capability ships
without a stored configuration, so it is disabled until the owner saves and enables one.

Owner decisions of 2026-10-14, recorded here before the tests that pinned the old rules change:

1. **The basic tap may call AI, through `word_translation` only, sending the word only.** The input is one word or phrase
   of at most three words and 40 characters (at most 8 Han characters), with the two languages and an optional part of
   speech; never the sentence, never the article. The tap's order is unchanged until it misses: catalogue, then CC-CEDICT
   or dictionaryapi, then the machine translators, then the `word_translation` seam of `ReadingLookupService` (PR #164),
   only when the capability is enabled, within the remaining tap budget. The seam is admitted through a bounded gate (a
   full gate is a miss, one call per word, a call that never started is cancelled, a failed word is cooled down for 60
   seconds, logs name the exception type only), and the adapter sends the word only, ignoring the sentence and the
   dictionary senses the seam is also given. If the budget passes, the call still finishes on its worker and fills the
   cache. The meaning is tagged `word_translation`. A per-account brake limits cache-miss calls; over it the learner gets
   the deterministic answer, never a 429. "Lookup never AI" (the docstring of `reading_lookup.py`, `tests/test_lookup_deterministic.py`,
   `tests/test_reading_lookup.py`) is replaced by: **AI is reached from a word tap only through `word_translation`, only
   on a deterministic miss, only when the capability is enabled.** Explain / "Why here?" (D-130.3, D-133) is unchanged and
   remains the only way a sentence reaches AI.
2. **OpenRouter, pinned `:free` models only, no credit.** The `openrouter/*` router ids (`openrouter/auto`,
   `openrouter/free`) are refused, so is any id without a vendor prefix, so is any model that is not `:free`, **so is any
   `:free` id that has no zero-rate entry in the price catalogue** (an unlisted free model is "unpriced" and the shared
   daily spend ledger would charge it 0.01 USD a call; the suffix is never priced as zero), at config validation and at
   the single wire choke point (`_post_chat`, and the stream). Requests send
   `provider.allow_fallbacks=false`: the router owns failover and the order is never random. A free endpoint may log
   prompts, so a provider marked `may_log_prompts` and any free model are refused for `learner_text` capabilities (the
   input-class rule, D-104); `word_translation` is `public_reference`. The key is entered by the owner (D-037 store or
   `OPENROUTER_API_KEY`); no agent handles it. Free models have explicit zero-rate price entries (pricing catalogue
   `2026-10-14.v3`), so the daily spend ledger no longer counts them as unpriced. Swapping in another free model means
   adding its zero-rate entry to `pricing.py` first.
3. **Lane.** The UI/Reading lane builds the router core in small PRs, each reviewed independently; the Intelligence lane
   calls it only through `route()` and keeps `agent_turn_*`.
4. **Order.** Slice 1 (this) before the Admin design addendum; the pool editor, config v2, the persistent cache and local
   tiers are later slices.
5. **Supersedes D-035's "primary-only" wording and clarifies D-010.** Operator-configured, ordered pools with tier labels,
   per-attempt timeouts, a total deadline, cooldown and full telemetry are **explicit failover**, not silent failover:
   D-010 forbids a *silent paid* failover, and this slice's pool is **enforced** free-or-local: config validation refuses a
   paid model, primary or standby, for `word_translation` (`free_only`) until the per-capability spend cap exists (PR 2),
   and every attempt is logged. An
   availability failure (429, 402, 5xx, timeout, unavailable) moves to the next entry; invalid output retries once and then
   moves on; terminal errors (disabled, unsupported, invalid configuration) are never failed over. A paid tier or an
   escalation still needs the owner's explicit configuration and a spend cap. The learner runtime already behaved this
   way since `a50f96a7` (2026-09-22); the pinned Admin design A5 says the standby is "used automatically when the primary
   fails".

MEMORY CONTRADICTION (settled by the owner's instruction above): D-035 and `docs/ORENA_AI_COST_REDUCTION_PLAN.md` §6-7
described a primary-only runtime; `routing.py` and `platform.py` implemented automatic failover to the standby.

**Mechanics (for the reviewer).** `route(capability_key, input, deadline=None)` in `writing_coach/ai/router/`; the pool runs
through `platform.generate_structured`, which gained `validate=`, `deadline=`, `invalid_retries=`, `attempt_timeout=`,
`router_version=` and `capability_mode=` (all inert by default). `timeout_seconds` is now a supported capability option
(G1) and `AIProviderError.status_code` is set by the providers (G4). The L1 cache is keyed without the model, with
single-flight and a 60-second negative cache. Telemetry gains `tier, phase, attempt, fallback_reason, http_status_class,
router_version` and an `ai.router.rollup` row per capability each minute; neither carries a word, a prompt or an answer.
`word_translation` is `opt_in`: outside the legacy-to-capability activation set (`activation_capabilities()`).

**Also changed, and stated for the reviewer.** `timeout_seconds` is now a supported capability option for **every** text
provider (it was refused before, so none is stored) and is applied per attempt; request timeouts now report
`error_class=provider_timeout` instead of `provider_unavailable` (still an availability failure). A validator rejection
(`invalid_output`) is not a provider-health failure and does not count toward the cooldown. This slice accepts no echo
of the input as a meaning (a proper noun would need the tagger's POS, which the word-only tap does not send). The
per-account brake table evicts the least recently used account only. The Admin copy names and explains the capability in
English, Vietnamese and Chinese.

**Review.** Independent architecture review of `43ce4621`: Claude Opus 5.5, Delegated Architecture Reviewer, independent
of the implementer: APPROVED WITH CONDITIONS. P1-1 (unlisted free model priced as unpriced) and P1-2 (free-only not
enforced) and P2-1, P2-2, P2-4, P2-5, P2-6, P2-7 are addressed in the commit that records this line; P2-3 (the `requests`
timeout is per socket operation, not a total) is noted, the tap is protected by the seam gate. No product approval is
implied; activation stays a separate owner action after the two model ids are verified against the live catalogue.

**Not verified.** The pinned ids `google/gemma-4-31b-it:free` and `qwen/qwen3-next-80b-a3b-instruct:free` could not be
checked against the live OpenRouter catalogue from the build environment; verify before activation (a retired id only
fails over). No live provider call was made.

**Amendment 2026-10-14 (models verified).** The ids were checked against the public OpenRouter catalogue
(`https://openrouter.ai/api/v1/models`, no key). `google/gemma-4-31b-it:free` is **verified**;
`qwen/qwen3-next-80b-a3b-instruct:free` **does not exist** and is removed. Pinned and zero-rated in `pricing.py`
(`2026-10-14.v4`): `google/gemma-4-31b-it:free` (primary), `google/gemma-4-26b-a4b-it:free` (standby, same family,
different weights) and `nvidia/nemotron-3-super-120b-a12b:free` (a second-vendor option). Other free ids the catalogue
lists are not selectable until their zero-rate entry is added. The "Not verified" paragraph above is superseded by this
note. An endpoint pasted as `.../chat/completions` is normalised to the base URL for every OpenAI-compatible provider.

**Amendment 2026-10-14 (live probe).** On :8021 the gemma models answered HTTP 429 (upstream rate limit) on every
probe, and the reasoning models returned an empty message at `max_tokens` 120. With OpenRouter's `reasoning.enabled`
false, `dots-studio/dots-3-note-preview:free`, `nvidia/nemotron-3.5-lightning:free` and
`nvidia/nemotron-3-super-120b-a12b:free` each answered a valid short Vietnamese gloss (en to vi and zh to vi). The two
new ids are zero-rated (pricing `2026-10-14.v5`) and the three are sent `reasoning: {enabled: false}` (a model that makes
reasoning mandatory, such as `liquid/lfm-2.5-2.6b`, is not listed). Free tiers are rate-limited by their upstream; the
pool should hold models from different upstream providers.

**Amendment 2026-10-14 (owner: Groq free standby now, a daily spend cap ready for a paid tier later).** Owner
decisions, in order: first "a cheap paid Groq standby behind a 0.50 USD daily cap", then "Groq only free models; the Groq
account is on the free plan", then "keep the cap mechanism for the future, free first". Built as both:

1. **Free first, in use now.** `groq / llama-3.1-8b-instant` is a zero-rate catalogue entry (pricing `2026-10-14.v6`,
   `TokenPricing.note`): source "owner-confirmed Groq free plan (no billing), 2026-10-14", listed as active on the public
   models page https://console.groq.com/docs/models. The public rate-limits page did not show a free-plan row for the
   model, so free-plan availability rests on the owner's confirmation. Because it is zero-rated it is tier `free`: the
   operator may save it as the standby of `word_translation` under the free rule, and the translate-ahead prefetch may
   use it. **Risk:** if billing is ever added to the Groq account these calls become billable while the ledger still
   records 0; the operator must revisit this entry (and the cap below) first. The existing paid Groq entries
   (`llama-3.3-70b-versatile`, `openai/gpt-oss-120b`, whisper), used by media translation and speech, are unchanged.
2. **Tier rule replaces `free_only`.** The primary must be free or local. The standby may be free or local, or paid only
   when the capability's cap policy is above zero and the pair is on the reviewed list
   (`paid_standby_models`: `groq / llama-3.3-70b-versatile`, priced 0.59 / 0.79 per million). Escalation and premium
   tiers are not part of the v1 document and stay refused. Input class stays `public_reference`.
3. **Per-capability daily cap, ready for a paid tier.** Policy `word_translation.daily_spend_cap_usd` (D-172 spend group,
   default 0.50, 0 to 100, confirm above 5, `WORD_TRANSLATION_DAILY_SPEND_CAP_USD`, EN/VI/ZH copy). Before each paid
   rung the chain asks `ai/spend_gate.paid_refused`: today's (UTC) spend of this one capability in the shared ledger
   (`ai_spend_since_for_capability`, unpriced successes counted at the guard's allowance) at or over the cap skips the
   rung, and so does a cap of 0, an unreadable cap policy, or an unreadable ledger (the SQLite archive store raises
   `NotImplementedError`): it fails closed. A skipped rung is logged with `fallback_reason=budget` and counted as
   `budget_skips`; the word is a miss, never an error. Free and local rungs are never gated. The cost of a paid call is
   recorded per call in the existing ledger. Saving a paid standby needs a cap above zero; the runtime does not
   revalidate that (a later cap of 0 skips the rung instead of disabling the capability).
4. **Prefetch never spends.** `route(..., paid_standby=False)` from the translate-ahead means a paid rung is never asked
   for background work, whatever the cap; a tap may. The prefetch's daily call caps are unchanged.

5. **Review.** Delegated Architecture Reviewer, Claude Opus 5.5, independent of the implementer, on `75112035`: APPROVE
   WITH CONDITIONS. P2-1 (the Admin standby test now follows the spend gate and refuses a paid model over the cap or with
   an unreadable ledger, without calling the provider), P2-2 (a retry after an invalid answer on a paid rung asks the gate
   again) and P2-4 (saving a paid standby reads the cap strictly and is refused when it is unreadable) are fixed in the
   commit that records this line. Noted, not changed: P2-3 (the billing-risk guard is documentation only), P2-5 (the
   per-capability ledger query scans the day's rows, at most once every 5 seconds per process), P2-6 (a failed paid call
   that Groq billed is invisible to the allowance). No product approval is implied.

**Amendment 2026-10-14 (live probe: the Groq key does not list `llama-3.1-8b-instant`).** On :8021 the key's catalogue lists
only `allam-2-7b`, `openai/gpt-oss-120b`, `openai/gpt-oss-20b` and `qwen/qwen3.8-27b`, so the pinned
`llama-3.1-8b-instant` answers 409 `model_unavailable` there (the entry stays, harmless, and is marked unavailable on this
key). Probed with the exact word_translation request on the free plan (pricing `2026-10-14.v7`), one call each:

| model | option | en to vi "infrastructure" | zh to vi "政府" |
| --- | --- | --- | --- |
| `qwen/qwen3.8-27b` | `reasoning_effort: none`, `reasoning_format: hidden` | "hạ tầng", 354 ms | "chính phủ", 322 ms |
| `qwen/qwen3.8-27b` | none | "hạ tầng", 674 ms | not probed |
| `openai/gpt-oss-20b` | `reasoning_effort: low`, `include_reasoning: false` | "hạ tầng", 589 ms | "chính phủ", 674 ms |
| `openai/gpt-oss-20b` | none | HTTP 400 "Failed to validate JSON" (thinking used the budget) | not probed |
| `openai/gpt-oss-120b` | `reasoning_effort: low` | "cơ sở hạ tầng", 812 ms | "chính phủ", 1304 ms |
| `allam-2-7b` | none | "công trình đầu tư, cơ sở vật lý" (wrong sense), 943 ms | "quốc gia" (wrong), 539 ms |

Chosen standby: `groq / qwen/qwen3.8-27b`, zero-rated with the same owner-confirmed free-plan note and revisit rule (Groq calls are recorded at $0 under the current
observed/configured free-plan setup, owner-confirmed on 2026-10-14; this is not guaranteed permanent pricing), sent
`reasoning_effort: none` and `reasoning_format: hidden` (`providers.GROQ_REQUEST_OPTIONS`, by id, like
`OPENROUTER_REASONING_OFF`). `openai/gpt-oss-120b` is already priced (0.15 / 0.60) for media translation and one
exact-match catalogue cannot hold two prices, so it is not zero-rated; `gpt-oss-20b` needs an option and is slower;
`allam-2-7b` answered wrongly. The operator saves `qwen/qwen3.8-27b` as the standby of `word_translation`.

**Supersedes / Superseded by:** Supersedes D-035 (primary-only wording); clarifies D-010.

## D-196 - Reading level: the reviewer's override is validated, folded over the automatic level and never overwrites it (2026-10-14)

**Status: ACCEPTED** (independent review 2026-10-14, Delegated Architecture Reviewer, Claude Opus 5.5: APPROVE on 976b346d; merged once CI was green). Production Readiness item 7a; the human's order was
"let the reviewer override first, then fix automatic CEFR/HSK classification" (defect D6, NASA release rated C2).

The override already existed (`reviewed_level` / `effective_level`, `POST /api/admin/reading/articles/{id}`, a `level_override`
review event, the segmented control on the article page). This decision closes the gaps and adds no storage and no migration:

1. `estimated_level` stays the classifier's and is never written by an admin, so the automatic classifier can be compared to
   reviewer corrections later. `effective_level` (override, else automatic) is the only level a learner list, filter or detail reads.
2. The level must be on the article's own scale (A1-C2 for English, HSK1-HSK6 for Chinese, the constants of
   `reading_processing`): the route answers 422 `reading_invalid_level` and the repository refuses with `ValueError`, so a script
   is stopped too. Before, any string was stored.
3. Setting the level it already has, or clearing an absent override, is not a change: no event, no revision bump.
4. A change records a review event (actor, optional reason, `from`/`to`) and bumps `content_revision`; clearing restores the
   automatic level. The bump follows the existing rule for every learner-visible field and applies to any status, not only
   published (a draft has no cached copy, so it is harmless and keeps one rule).
5. Admin UI: the pinned `Orena Admin.dc.html` already draws the control as "Keep estimate · {est}"; the label now carries the
   automatic level. The design draws no reason field; the API accepts a `reason` and the UI does not send one.

Not done here: improving the automatic classification (the next step).

## D-197 - Reading: Chinese script detection and the Traditional label (2026-10-14)

**Status: ACCEPTED** (independent review 2026-10-14, Delegated Architecture Reviewer, Claude Opus 5.5: APPROVE WITH CONDITION on f4522b43; the P1, attribution of the derived table, is fixed; merged once CI was green). Carries out D-189 (Traditional is allowed, labelled, never mixed with Simplified; Global Voices 中文 stays
MANUAL_ONLY until the UI distinguishes scripts). Reading Production Readiness item 8 (part). Not activation of any source.

1. **Detection.** `writing_coach/languages/chinese/script_detection.py`: a pure function over character evidence. The table of
   characters that exist in one script only (`script_chars.json`, 2,505 Simplified-only and 3,427 Traditional-only) is derived
   from the vendored CC-CEDICT pack by `scripts/build_chinese_script_table.py` (stdlib, offline; `--check` fails when stale and
   is a test). A character that some entry writes the same in both scripts (后, 台, 干) is excluded. No new dependency or dataset.
2. **Thresholds** (named constants). Fewer than `MIN_EVIDENCE` = 15 script-specific characters: `unknown` (real articles carry
   about one in four; headlines and snippets do not). Otherwise the minority script's share of the evidence at or under
   `NOISE_SHARE` = 10 percent: the majority wins (`zh-Hans` / `zh-Hant`), which tolerates a quoted name or title; above it: `mixed`.
   Measured on the repository's eight real VOA 中文 fixtures: all `zh-Hans`, 0 Traditional characters, 70-597 evidence each.
3. **Storage, no migration.** `analysis.script` in the existing article analysis JSON, set at ingest for Chinese only, and the same value in the source
   item's `metadata.script` (a measured fact beside `detected_language`). The learner list reads the latter from the source item it
   already joins for the credit, so it never reads `analysis_json` (the list-cost guard test holds, unchanged). The learner
   list and detail payloads carry `script` for a Chinese article (absent otherwise; an article with none stored reads `unknown`
   in the list and is detected from its body in the detail).
4. **Quality.** `script_mixed` is a SOFT issue (`QUALITY_VERSION` reading-quality/4): a reviewer sees it and automatic admission
   holds it; it never blocks a publish. Admin Reading shows the script in the evidence panel.
5. **Learner label.** "Traditional" / "Phồn thể" / "繁體" for `zh-Hant` only, on the Discover card tag list, the Content Detail
   hero meta and the Reader toolbar meta (`brief/ZH_SCRIPT_LABEL_2026-10-14.md`). Simplified is unlabelled; `mixed` and
   `unknown` draw nothing for the learner.
6. **Not done.** No script filter or grouping in Discover and no learner script preference (follow-up, `UI_BACKEND_GAPS.md`); no
   backfill of already-published articles' stored script; no browser verification (Docker was unavailable); the Global Voices
   中文 source is not unlocked by this change, which is a human gate. Existing Traditional articles stay unlabelled on Discover
   until their script is stored: backfill before activating any Traditional source.

## D-198 - Reading level: an interim, uncalibrated fix of the saturated automatic estimate (2026-10-14)

**Status: ACCEPTED** (interim; independent review 2026-10-14, Delegated Architecture Reviewer, Claude Opus 5.5: APPROVE WITH CONDITIONS on 25db05e8; the conditions are addressed in the following commit; merged once CI was green). Production Readiness item 7b (defect D6: a NASA press release rated C2, every VOA 中文 article HSK6). The owner chose
"C now, then A": this entry is C. It is an interim correction, not a calibrated classifier. It changes no schema, no stored row and no
dataset, and the reviewer override of D-196 keeps its precedence (`effective_level` = `reviewed_level`, else `estimated_level`; the
estimator never reads `reviewed_level`).

1. **Cause (measured).** `analyze_article` capped three signals so low that any news text saturated them: a ~100-word English list
   and a 39-character Chinese list make "uncommon" 53-88 percent for every real text; 8-letter words (names, acronyms and hyphenated
   compounds included) hit their cap at 22 percent; Chinese length was measured per full-stop sentence, and wire prose is one long
   comma-joined sentence. All eight Chinese fixtures were HSK6; the NASA release was C2.
2. **Change** (`writing_coach/reading_processing.py`, `LEVEL_VERSION = "reading-level/2"`, stored as `analysis.level_version`;
   an article without it was estimated by the original heuristic):
   - English signals ignore a capitalised word that does not open a sentence, an all-capitals word (acronym), a word touching a
     digit, and count a hyphenated compound as its parts and a contraction as its stem (`boy's` is `boy`; pieces of 1-2 letters are dropped, so `it's` vanishes). The sentence-length and long-word normalisers moved from
     26 to 30 words and from 22 to 30 percent so ordinary news no longer saturates them.
   - Chinese length is the mean clause length, clauses ending at `。！？；，、：…`. The stored `average_sentence_length` is unchanged.
   - Low confidence is deterministic: `confidence = min(1, words/400)*0.8 + 0.2 if at least 5 sentences`, below `LOW_CONFIDENCE`
     = 0.5 (about 250 words or fewer, or a few long words and few sentences) the band is capped at C1 (English) / HSK5 (Chinese).
   - `word_count`, `long_word_ratio`, `reading_time`, `confidence` and every stored field keep their meaning.
3. **Result on the fixtures** (provisional author judgements, not truth): NASA C2 to C1 (B2-C1), Global Voices C2 to C1, VOA EN
   C1 to B2; all Chinese news HSK6 to HSK5. Chinese stays one band wide for real news because the 39-character list still saturates its
   half of the score: no Chinese discrimination is possible without a list.
4. **Not done, by design.** The thresholds are uncalibrated (no CEFR/HSK list and no graded texts in the repository; the new
   normalisers were chosen against four English fixtures and are therefore a fit, not a measurement). No stored article is
   re-estimated; `scripts/report_reading_level_changes.py` is a read-only report of what would change, and re-estimating is an owner
   decision. Option A (word and character lists, a labelled calibration set, a dataset and licence decision) replaces this.
5. **Known limits, for the calibrated Option A.** (a) The score uses its own `scored_long` (share of 8+ letter words among the
   scored tokens), which differs from the stored `long_word_ratio` (all tokens); the stored field is unchanged and no longer drives
   the band. (b) A capitalised word after an abbreviation full stop (`Dr. Smith`, `U.S. Army`) is read as a sentence start and counted,
   so a few names still enter the signals. (c) `_EN_WORD` matches ASCII letters only, so accented Latin words (`cafe` with an accent,
   names) split into fragments; a calibrated tokenizer must handle them.

## D-199 - Reading level: coverage against graded word lists replaces the heuristic (reading-level/3) (2026-10-14)

**Status: ACCEPTED** (independent review 2026-10-14, Delegated Architecture Reviewer, Claude Opus 5.5: APPROVE WITH CONDITIONS on 538dc9ba; re-review APPROVE on 5215d1ba, no open P0/P1; merged once CI was green, with the owner decisions of item 6). Production Readiness item 7b, option A of D-198, chosen by the owner on
2026-10-14. Replaces the interim estimate of D-198. No schema change, no migration, no stored row changed; the reviewer
override of D-196 keeps its precedence (the estimator never reads `reviewed_level`). No AI call: the `level_estimation`
router capability (D-195) is not used.

1. **Data** (owner's choice; separate generated files, built offline by `scripts/build_reading_level_tables.py`, which has
   `--check` and keeps licence, citation, origin commit and source hashes in each JSON; rows added to `THIRD_PARTY_NOTICES.md`
   and `writing_coach/licences.py`):
   - CEFR-J Vocabulary Profile 1.5 (A1-B2), `level_words_cefrj.json`: free for research and commercial use with citation;
     copyright Tono Laboratory, TUFS.
   - Octanove Vocabulary Profile C1/C2 1.0, `level_words_octanove_c1c2.json`: **CC BY-SA 4.0, ShareAlike**; kept as its own
     file so the licence does not extend to the CEFR-J table or to code. Adapting that file keeps CC BY-SA 4.0.
   - HSK 3.0 words and characters, `level_words_hsk30.json`, from ivankra/hsk30 (MIT, commit 4ff9e391), chosen over
     drkameleon/complete-hsk-vocabulary because the latter folds in frequency data from sources without a clear licence.
     Only each entry's level is kept. Caveat recorded: the ivankra README says the data derives from the PRC Ministry of
     Education standard and that the MIT copyright claim is questionable; the owner has accepted the MIT declaration as the
     operative licence. Levels 7-9 are the advanced band beyond Orena's HSK1-6 scale.
2. **Estimator** (`writing_coach/reading_level.py`; `LEVEL_VERSION = "reading-level/3"`, stored as `analysis.level_version`).
   Names, acronyms, numbers and units never count (D-198's rules). English tokens are looked up with suffix rules and a small
   irregular-form table; Chinese is segmented with jieba, names/numbers/non-words are skipped by jieba tag, and an unlisted
   word falls back to its characters (their upper median; HSK 7-9 is a rank of its own, capped to HSK6 for learners). Band = the lowest band whose share of tokens above it is at most
   `TAU` (en 0.10, zh 0.08); a mean sentence length of 20+ words (en) or clause length of 14+ (zh) adds one band, an English
   mean of 5 or fewer takes one off. `confidence` = `min(1, scored/300)` discounted when a 0.7x-1.4x change of `TAU` moves
   the band; below `LOW_CONFIDENCE` (0.1, about 35 scored words) the band is capped at C1 / HSK5.
   `analysis.level_evidence` stores the scored count, cumulative coverage per band, the share beyond all lists, the lexical band,
   the sentence length and the top eight out-of-band words with their count - never the text. Admin Reading's evidence panel shows
   coverage and those words in the existing row component (EN/VI/ZH copy `rdEvCoverage`, `rdEvAboveBand`); confidence was already
   drawn ("N% sure").
3. **Calibration** (`tests/fixtures/level_gold/`, `scripts/eval_reading_level.py`). 61 labelled items (34 EN, 27 ZH): 36 VOA
   Learning English pages labelled by VOA's stated tier (Beginning = A1/A2 by programme, Intermediate = B1; the Advanced tier
   describes the learner, not the vocabulary, so it is unlabelled; ten pages that credit an agency were dropped), Orena-written
   samples per band, the real fixtures (NASA, Global Voices, VOA 中文), and 13 real easy Chinese texts (item 4).
   **Every label is PROVISIONAL; none is owner-approved.** Agreement with those labels, D-198 heuristic then this estimate on the
   same items: English exact 35.3 percent then 70.6, within one band 88.2 then 97.1; Chinese exact 22.2 then 66.7, within one
   band 85.2 then 92.6. The parameters were fitted on a subset of these items (three per language) so the figures are in-sample;
   a two-fold hold-out gave English 52.9/82.4 and 70.6/100 and Chinese 76.9/92.3 and 50.0/100. They are regression guards, not
   a claim of accuracy. Reviewer corrections will be read-only evidence once a database is at hand, not the sole truth.
4. **Result on real articles.**
   - English: NASA C2 to C1, Global Voices C2 to C1; VOA Learning English spreads over A1-C1.
   - Chinese news: the five VOA 中文 pages all read HSK6 (D-198: all HSK5). 80-93 percent of their words are in the HSK 1-6 lists,
     7-15 percent are HSK 7-9 and under 1 percent are in no list. HSK 7-9 is its own internal rank (shown to learners as HSK6, kept
     in the evidence as `hsk7_9`), and an unlisted word takes the upper-median band of its characters rather than the hardest, so
     the ceiling is the measurement and not an artefact of the fallback. Thresholds were not fitted to make news look easier.
   - Chinese easy real texts (owner's acceptance, 2026-10-14): 13 real texts with clear reuse rights, labelled PROVISIONAL by the
     author before the estimator ran: eight Tatoeba sentence sets (CC BY 2.0 FR) and five Chinese Wikipedia leads (CC BY-SA 4.0).
     Estimate: HSK3 x2, HSK4 x4, HSK5 x2, HSK6 x5 (D-198: HSK4 x7, HSK5 x6). Eight of thirteen read below HSK6 over four bands, so the
     criterion "real texts below HSK6 with a spread" is met on these. Agreement with the author's labels is 5 of 13 exact and 11
     of 13 within one band: short sentence sets of about 75 words can be pushed up a band by three or four rare words, and the
     encyclopedia leads read a band above the author's guess. Nothing was refitted for them.
5. **Known limits.** The labels are judgements (the VOA tier is coarse and its A1/A2 split is by programme, not measured); a
   text is graded on vocabulary and length only, not on grammar, so a grammatically complex text in plain words reads low
   (an author B2 sample reads A2); an English word absent from CEFR-J/Octanove (technical terms, many derived forms) counts as
   beyond C2, which is why a technical press release reads C1-C2; the suffix rules are heuristic; the Chinese threshold is
   strict for texts under about 100 words. Re-estimating stored rows is an owner decision:
   `scripts/report_reading_level_changes.py` (read-only) lists what would change under this version.
6. **Owner decisions (2026-10-14).** (a) The use of the CEFR-J list as a repackaged derived table, and of the HSK 3.0 list from
   ivankra/hsk30 (MIT, with the provenance caveat in item 1), are ACCEPTED in full by the owner; no further confirmation is needed.
   (b) The Chinese acceptance gap was to be closed by adding easy real Chinese texts and checking; item 4 records the result.

## D-200 - Translate ahead when a Reading article opens; a router answer keeps its label (2026-10-14)

**Status: ACCEPTED** (amends D-195). Independent review 2026-10-14, Delegated Architecture Reviewer, Claude Opus 5.5:
APPROVE WITH CONDITIONS on 1f3c63c5, re-review APPROVE on a358feac; P2-A/P2-B fixed in 58ac8c58; merged once CI was green. Owner decision of
2026-10-14: "translate ahead when an article opens", so the first tap on a word shows its support-language meaning at
once. No schema, no migration, no UI change, no new endpoint. The capability stays off until the owner enables
`word_translation`; with it off nothing here calls anyone.

Evidence: on the sandbox the primary free model answers in about 1.6-2 s and `TAP_BUDGET_SECONDS` is 2.0, so the first tap
on a new word missed its budget (no gloss); the call finished in the background and only the second tap was instant.

1. **Trigger.** `GET /api/reading/articles/{id}` (a 200 and a 304 revalidation) calls an `on_open` hook that only enqueues
   (`writing_coach/reading_prefetch.py`, `Prefetcher.schedule`, which never raises and reads no database); a hook failure
   is swallowed. The learner's support language and the capability's configuration are read on the worker, inside a copy of
   the request's context. The executor is shut down (queued jobs dropped) on app shutdown.
2. **Words (ordered by the D-199 word lists).** Word only, the same input as a tap (never a sentence or the article), same contract, validator, shared
   `public_reference` result cache and single flight. English: not on the common-word lists, not a name (capitalised away
   from a sentence start), acronym, number-adjacent word, contraction or hyphenated compound, at least 4 letters. Chinese:
   two or more Han characters that the tagger marks as noun, verb, adjective or adverb. Both are ordered by
   `reading_level.word_rank` (CEFR-J / Octanove, HSK 3.0; a word in no list is the hardest), then by length and order of
   appearance, and an A1 / HSK1 word is never planned. Only the first 6000 characters are planned. The estimator's stored
   evidence keeps only the top eight out-of-band words and the learner route does not expose it, so the lists are read
   directly instead.
3. **Deterministic layers first.** `ReadingLookupService.has_local_meaning` (catalogue meaning in the target language,
   CC-CEDICT for an English support language, an already-held translation) is checked first; such a word never reaches AI.
   It never touches the network, never creates a translation, never uses a tap's slots.
4. **Caps (config constants, no admin surface).** 40 words per article; 2 prefetch workers and 2 prefetch gate slots,
   separate from the tap's gate (a prefetch cannot take a tap's slot); 8 waiting articles; 1500 router calls a day per
   worker process (`tap.PREFETCH_DAILY_CALLS`); a per-article marker (article, revision, languages) with a 6-hour TTL in
   process (the router cache, 180 days, is what holds the answers; no persistent marker, so no migration), dropped when a
   batch stops early; three consecutive bad answers stop a batch. A stopped batch keeps a **10-minute retry-after marker**
   (not dropped), so reopening an article in a loop cannot drain the daily budget; opens within 30 s coalesce.
5. **Brake, cooldown and pacing (review P1-1).** Prefetch does not count against any learner's per-account brake and has its
   own budget. It must not degrade taps, so: (a) its router calls run on a **private** `ProviderHealth` (`route(...,
   health=)`, `generate_structured(health=)`), so a 429 it meets never cools the provider down for a tap (both pool entries
   share one provider id, so a shared record would take the tap's primary away); (b) it **yields**: while the shared record
   says a pool provider is cooling down, prefetch is paused and asks nobody; (c) it **pauses process-wide for 120 s after
   any availability failure** (a 429, a 5xx or a timeout on any attempt, even one the standby then answered, or the whole
   pool failing) and the batch stops; a validator refusing one word is not one; (d) it waits 0.5 s after every call that
   reached the provider (per worker), so a free tier's rate limit is not burned in a burst. A disabled capability stops it.
   Trade-off: a prefetch is blind to a rate limit that only a tap has hit until the shared record shows it, and the
   provider's own limit is shared by taps and prefetch regardless; (b) and the pause bound that.
6. **A tap on a word whose prefetch is in flight joins it** (the prefetch publishes its call in the same in-flight table the
   tap's gate uses) and is answered within its budget if the call finishes; a tap's timeout never cancels a prefetch.
7. **Telemetry.** Counts only, in the existing `ai.router.rollup` row of `word_translation`: `prefetch_articles`,
   `prefetch_requested`, `prefetch_served`, `prefetch_skipped`, `prefetch_failed`, `prefetch_calls`. No word, no article id.
8. **Label fix.** `project_word_detail` reported `meaningSource: "dictionary"` for every lookup meaning, so a cached router
   answer on the second tap was relabelled. The lookup's tag is now kept: `word_translation`. The UI reads only `context` /
   `contextual` / `none`, so nothing changes visibly. `tests/test_tap_basic_meaning.py` pinned the old label for the seam's
   answer and now pins the correct one. `AI_COST_ROUTER.md` sec. 2.9 said `meaningSource` stays `machine_translation`; the
   code never did that, and the response contract has no such value.
9. **Known limits.** The tap's selection keeps its case, so the router cache key is case-sensitive: the prefetch asks the
   lowercase form when the article has one, else the form as written. A word tapped in another inflection, or after the
   prefetch cap, still takes the tap path. The 120 s pause and the daily count are per worker process.
10. **Per-process limits (review P2-3).** The daily budget (1500), the 120 s pause, the markers and the router's result cache
    are per worker process, so the fleet ceiling is 1500 x workers a day and each worker repeats an article once. The
    router cache is an in-process LRU of 4096 entries and is lost on restart: a large prefetch can evict answers a learner
    tapped. A shared or persistent cache is a later router slice, not this decision.

**Amendment 2026-10-14 (first-tap misses on :8021, root causes).** Evidence: the final E2E on the sandbox (main `bfaeb34d`).
Read from `audit_logs` (`ai.operation`, `ai.router.rollup`; counts, latency and error classes only) and the server log.

1. **The prefetch ran.** The Reader opens an article with `GET /api/reading/articles/{id}` (`screens/reader/source.js`), which
   fires the hook. The rollups show it: one batch of 32 words (30 served) from 06:53:02, then batches that asked one word, met
   a 429 and stopped (`prefetch_requested 1, prefetch_failed 1, prefetch_skipped 39`, 06:57, 07:02). Nothing was logged
   because the batch only counted, and the root logger is at WARNING. `orena.prefetch` now speaks at INFO on its own handler
   (when the application configured none): one line per scheduled / refused open, and one counts-only line per job
   (`reading prefetch done|stopped|... language= planned= requested= served= failed= skipped=`; no word, no article id).
2. **The NASA misses were the provider, not the planner.** From 06:53:52 every call to both pool entries (two different
   upstreams) was an HTTP 429 until the end of the run, about 50 OpenRouter requests after the day's first. About 50 OpenRouter
   requests were made during the test day, after which the primary returned 429; the exact free-tier quota is not confirmed
   (the 429 body is not recorded, so the cause is an inference; the
   mapping now also reads OpenRouter's own `X-RateLimit-Limit` / `X-RateLimit-Remaining` headers into the existing
   `rate_limit` field of the operation row, so the next one is a fact). A 40-word batch with 0.5 s pacing spends that in under
   a minute. **Owner action:** a free pool cannot carry translate-ahead; fund the account or lower the per-article cap.
3. **The tap's budget.** A tap spends its 2.0 s on the tagger and the external dictionary (timeout 1.5 s; rare words are the
   ones it cannot answer, so they spend most of it) before the seam, which got what was left, floored at 0.25 s, while a free
   model answers in 0.7-1.7 s. Now: the dictionary's tap timeout is 1.0 s and the seam always waits at least
   `SEAM_MIN_WAIT_SECONDS = 1.8`. Worst case for a tap that reaches the seam is about 3 s (tagger, then the dictionary's
   1.0 s, then the seam's 1.8 s floor); a typical rare word is a fast dictionary miss plus one model call, 1.5-2.0 s. `TAP_BUDGET_SECONDS` stays 2.0 for every other layer.
4. **Why a re-tap answered nothing in 27 ms.** Two cooldowns exist by design after a failed call (the router's 60 s negative
   cache and the lookup gate's 60 s per-word cooldown) and a 429 failure is exactly that. But the gate's cooldown was also set
   by a *prefetch* failure, so a background 429 made the learner's tap on that word empty for a minute, against item 5 of this
   decision. A translate-ahead call's future is now marked background and never sets the tap's cooldown. A tap that times out
   still lets its call finish, and the late answer fills the router cache under the tap's own key; a test pins one provider
   call serving both the timed-out tap and the next.
5. **Not changed.** The cache key is still case-sensitive (item 9 above). `PREFETCH_DAILY_CALLS` and the pause stay.
6. **Owner decision 2026-10-14: free models only (no credit), so prefetch is sized conservatively against what was observed (about 50 requests before the primary returned 429; the quota is not confirmed).**
   `reading_prefetch.MAX_WORDS_PER_ARTICLE` is 8 (the hardest words by the D-199 rank; fewer if fewer qualify, replacing
   the 40 of item 4 above) and `tap.PREFETCH_DAILY_CALLS` is 25 per worker process (replacing 1500), which leaves the
   rest of the day for taps. Both are plain constants tuned to that observation on an unfunded OpenRouter account; the quota is not confirmed, and funding
   the account would allow raising them. A 429 whose `X-RateLimit-Remaining` is 0 (the allowance is spent, not a busy
   upstream) pauses prefetch until the next UTC day instead of 120 s. The `orena.prefetch` logger no longer touches the
   root logger at import (`propagate=False`; `install_log_handler()` runs at app start).

## D-201 - Reader sentence cut: numbers and abbreviations; old notes read through the old cut (2026-10-14)

Status: ACCEPTED. Independent review 2026-10-14, Delegated Architecture Reviewer, Claude Opus 5.5: CHANGES REQUESTED on the splitter half of PR #185 (7c33a767), APPROVE WITH CONDITIONS on PR #186 (f579951e); P2-1..P2-4 fixed in 27fc012b; no stored learner data migrated; merged once CI was green.

1. **The bug.** The Reader cut a paragraph at every full stop, so "USD 4.77 billion" rendered as two sentence spans
   ("USD 4." and "77 billion"). `product/reader-text.js#sentenceSpans` now ends a sentence at a dot only when whitespace
   follows it and it is not part of an abbreviation (rules in the code comment: titles, dotted abbreviations such as
   U.S./e.g./a.m., initials followed by a name, "No. 5", ellipsis before a lowercase word). "I." and a single capital
   before a common sentence starter ("Plan B. Next.") end a sentence; a domain or file name ("nasa.gov.") ends one.
   `!`, `?`, `。`, `！`, `？` and newlines always end one. English-only heuristics; Chinese is cut at its own marks, and a
   full-width decimal point (`．`) is not a terminator.
2. **Stored learner data is not touched.** Notes are keyed `kind:content:p{pi}s{si}:text` and highlights `segment|text`, so a
   changed cut would orphan items saved under the old one. Nothing is migrated or rewritten (learner data, owner gate).
   Instead `screens/reader/legacy-sentences.js#legacyAliases` computes the old cut (`legacySentenceSpans`, frozen) and maps
   each old sentence onto the one new sentence that contains it. The Reader, the sentence sheet and the completion count
   read a sentence's notes and highlights under its own key and under those old keys (a note once, by id), so an existing
   item still shows on the right sentence. New notes and highlights are written under the new key only; edit and delete
   act on the key where the note is stored; toggling a highlight off removes a legacy one too. A highlight saved on an old
   half-sentence now marks the whole new sentence. Account sync is unchanged (it carries keys as stored).
3. **Known limits.** Heuristics undersplit rather than oversplit ("the U.S. Army said" stays whole; "the U.S. The" splits).
   An unlisted abbreviation before a lowercase word ("Dept. of Health"), an initial before an initial ("J. K. Rowling")
   and "Apt." before a digit do not end a sentence; an unlisted abbreviation before a capital does. Only a 64-character
   window around each dot is read, so the cut is linear (50k characters in a few ms). An alias that equals another
   sentence's own key (a repeated sentence in an affected paragraph) is dropped The server's English splitter (`EN_SENTENCE_END`) needs
   whitespace after the dot already and only feeds statistics; it is unchanged. The aliases drop out when the old and new
   cut agree, so a text that never had a false break has no extra lookups.

## D-202 - Local English pronunciation from CMUdict (2026-10-14)

Status: ACCEPTED. Independent review 2026-10-14, Delegated Architecture Reviewer, Claude Opus 5.5: APPROVE on 9e6572c9; review follow-ups (unreadable-table warning, content digest verified by `--check`) done; merged once CI was green. Owner decision 2026-10-14: a free, local IPA source so the Word Quick Sheet always shows a reading for an English word without depending on the online dictionary; no paid service).

1. **Source and licence.** The official CMUdict (github.com/cmusphinx/cmudict, `cmudict.dict`, commit 74790861, SHA-256 pinned in the builder). Its licence is BSD-style (Copyright 1993-2015 Carnegie Mellon University): redistribution and use, with or without modification, are permitted provided the notice, conditions and disclaimer are retained or reproduced; commercial use is not restricted. The licence text ships as `writing_coach/languages/english/CMUDICT-LICENSE.txt`; `THIRD_PARTY_NOTICES.md` and `writing_coach/licences.py` carry a `cmudict` row.
2. **Table.** `scripts/build_english_ipa_table.py --source <cmudict.dict>` converts the first pronunciation of each word (ARPAbet to General American IPA; stress mark before the stressed syllable's onset by maximal onset, no mark on a one-syllable word; AH0 schwa, ER0 r-coloured schwa, ER1/ER2 r-coloured stressed vowel) into `cmudict_ipa.json.gz` (125,923 headwords, ~0.85 MB gzipped, licence and source metadata embedded). `--check` verifies the shipped table (metadata alone, or a full rebuild with `--source`). Keys are lowercase; entries with digits or other punctuation are dropped; alternates are not kept.
3. **Lookup.** In the English single-word branch of `reading_lookup.py`, `pronunciation` is the catalogue's, else the online dictionary's, else the local CMUdict reading (lazy, once, thread-safe). It adds no network call and no latency. Inflected forms are looked up exactly; no -s/-ed/-ing stripping, because a guessed ending can change the sound. A heteronym (read) takes its first pronunciation. An online-dictionary reading, when present, wins over the local one even though it may be British; the local reading is General American.
4. **Not covered.** Names and words absent from CMUdict get no local reading. The IPA is a rule-based rendering of a US pronunciation dictionary, not a recording and not British. No schema, learner data or Docker change.

## D-203 - Built-in learner content is test content; an Admin-controlled hide/show flag removes it from learners (2026-10-14)

Status: ACCEPTED (merged once CI was green). Independent review 2026-10-14, Delegated Architecture Reviewer, Claude Opus 5.5, on 8e7cdf92: ACCEPT WITH CONDITIONS, no P0/P1; P2-1 (fail closed on a never-read store) and P2-2 (cache the failure fallback, log once per window) fixed on this branch with tests (cold-start unreadable store, agent tool, licences page). Owner decision of 2026-10-14: code-owned built-in learner content, for
example the Listening lessons in `writing_coach/content/listening_catalog.v1.json`, is test-only and must be removable from the
product by the Admin through a server-side flag, never by editing code. No schema change, no migration.

1. **Inventory (what is code-owned and learner-visible).** Listening catalogue: six lessons (`en-daily-pen-in-my-bag`,
   `en-science-cosmic-calendar`, `zh-daily-what-is-this`, `zh-culture-nationalities`, `zh-culture-where-are-you-from`,
   `zh-technology-search-wikipedia`), five Wikimedia Commons sources, all `PUBLISHED`; loaded at import by `listening_catalog`
   and reached through `catalog_lesson(s)`, which feed the Listening library and open route, Speaking's shadowing list and model
   lines, a word's context clips, the learner collection, progress validation, the agent's lesson reads, the licences page and
   model-clip preparation. Speaking's own `speaking_catalog.v1.json` is empty (zero authored items). Vocabulary static seeds: zero
   published (the F3 gate holds; confirmed 0 published entries, en and zh). Reading articles, library books and word recordings are
   database or asset-store records, not repository content. The Grammar course (269 lessons) is the curriculum, not sample content,
   and is out of scope. Library book files under `data/reading_library_assets` are asset blobs for database rows and are not served
   without one.
2. **Storage.** One `platform_settings` row, `content.visibility`: `{"version": 1, "hidden": {"listening": [<lesson id>, ...]}}`
   (`writing_coach/content_visibility.py`), the same store and compare-and-set contract as `platform.policies` (D-172) and the plan
   catalogue (D-153). Absent means everything visible, so an unconfigured deployment changes nothing. Only an administrator hides
   an item; the repository's lesson is never written.
3. **Where it applies.** One filter, in `listening_catalog._learner_visible`, which `catalog_lesson` and `catalog_lessons` already
   share, so every learner path above honours it with no per-route copy; a direct open answers 404. The collection resolver now
   reads the catalogue at call time (it captured the list when built, which would have survived a hide until restart). The Admin
   reads `CATALOG` directly and lists hidden lessons as unpublished.
4. **Admin and audit.** `POST /api/admin/console/content/media/{id}/status` accepts `unpublished` / `published` for a built-in
   lesson (it already did for imported media); `archived` is refused (409). The save is a compare-and-set against the version just
   read (a concurrent change is a 409) and the audit row (`admin.content.visibility`: actor, item, from, to) commits in the same
   transaction; a no-op writes nothing and is recorded as `unchanged`. Admin UI: the existing Unpublish / Republish pair and
   status pill (`docs/design/canonical-ui/brief/BUILTIN_CONTENT_VISIBILITY_2026-10-14.md`).
5. **Consistency and failure.** A saved change applies at once in the saving worker and within 5 seconds in the others (the policies
   cache interval). **Fail closed:** if a store is installed, has never been read successfully in this process and the read fails,
   built-in lessons are treated as hidden until a read succeeds (test content must not reach production on a guess; the Admin list
   shows them hidden too). After one good read, a later failure keeps that value. A failed read is cached for the same 5 seconds and
   logged once per window. No store installed (unconfigured, tests) means nothing hidden. Listening routes carry no ETag, so no
   revision needs to move.
6. **Not covered, by design.** A learner's own saved progress for a hidden lesson stays stored and shows as unavailable without a
   title; it is not deleted. Default for genuinely curated items stays visible. Further kinds are added to
   `content_visibility.KINDS` only together with the filter on their learner paths.

## D-204 - Media import makes no per-word network lookup (2026-10-14)

Status: ACCEPTED (merged once CI was green). Independent review 2026-10-14, Delegated Architecture Reviewer, Claude Opus 5.5, on 552daf3f: ACCEPT, no P0/P1. Owner decision 2026-10-14, from the Video Sources Phase 0 runtime: lesson
preparation must never wait on a dictionary website. No schema change.

1. **Cause.** `lesson_payload` asked `lookup_dictionary(word, allow_ai=False, persist=False)` (api.dictionaryapi.dev, up to ~20 s
   or HTTP 522 per word) for every distinct word of an English transcript. A 63 s clip took 7 minutes and a 555 s clip 22 minutes
   in the segment stage, on a single worker.
2. **Rule.** During import, English pronunciation is the local CMUdict IPA (D-202, `ipa_for`) and empty on a miss. Word meaning
   and enrichment during import use local catalogue or cache only; a miss is left for the learner's own on-demand tap lookup,
   which is unchanged. Nothing in lesson preparation blocks on a dictionary. No worker or concurrency was added to hide latency.
3. **Readings.** New English readings are General American (CMUdict, D-202). Older stored lessons, and the cache-fed legacy
   path, may carry dictionaryapi.dev readings (often British); no migration or reprocess rewrites them.
4. **Word meaning.** Import does no word-meaning lookup at all; meaning is the learner's on-demand tap.
5. **Remaining network in the readiness path** (none per word): caption and metadata fetch, yt-dlp audio, ASR, the spend-capped
   line translation, and the `_prepare_model_clips` audio re-download.
6. **Where.** `app.py` wires `MediaPipeline(english_reading=ipa_for)`; `tests/test_media_import_offline_lexicon.py` fails if the
   import path makes any HTTP, socket or dictionary call. The line translation stage (`prepare_media_meanings`) is a separate,
   spend-capped provider stage and is not a word lookup; it is unchanged.

## D-205 - Media import records provenance, specific rejections and a stable outcome (2026-10-14)

Status: ACCEPTED (merged once CI was green). Independent review 2026-10-14, Delegated Architecture Reviewer, Claude Opus 5.5, on 89b89535: ACCEPT WITH CONDITIONS; conditions fixed on this branch (item 8); re-review APPROVE on 7207d922, no open P0/P1. Owner-approved P1s from the Video Sources Phase 0 runtime. No schema or
migration change: everything lives in existing JSON fields (`creator`, the `source` string map, `processing`).

1. **Provenance.** A YouTube import stores the channel (oEmbed `author_name`/`author_url`) as `creator` and in `source`
   (`creator`, `creator_url`, `platform`, `original_url`). A Wikimedia Commons import stores the author, the licence short name
   (in `license_name`, captured and not verified) and its URL (`license_url`); `license` keeps the "review provider terms before publishing" reminder, the platform and the File: page. Rights are untouched: unknown stays unknown and
   the item is held, never auto-published.
2. **Commons.** `commons.wikimedia.org/wiki/File:...` pages and `upload.wikimedia.org` files (including `.ogv`) resolve through
   one bounded Commons API request to the media URL, a readable title (the page's own name, else the filename without
   extension and underscores), the author and the licence. The item is a direct media file (`provider: direct`) so reprocess
   keeps working.
3. **Rejections say why.** Stable codes: `commons_not_a_file`, `commons_not_commons`, `commons_file_missing`,
   `commons_not_media`, `commons_unavailable`, `media_unreadable`, `unsupported_media_type` (now naming the suffix). The preview
   rows carry the same `category` as the import report, so the console no longer shows the generic "source could not be read".
4. **URL box.** Splits on line breaks and whitespace; a comma separates only where the next piece starts `http(s)://`.
5. **Outcome.** `processing.reason` (stable code) is stored with `processing.message` (English sentence); the admin record gains
   `outcome` = `processing | held | failed | ready` plus the reason, message and translation state, and a failed item no longer
   reads as the held "Review" pill. New code `captions_blocked`: the provider refused the captions and the audio route failed.
6. **Partial translation.** A line translation that reaches some lines is `partial` with `{done, total}` per language in
   `processing.translation_counts`; the item state is unchanged and the learner payload's `translation.status` is `partial`
   (not `unavailable`) when lines have a meaning. Only no lines at all is `failed`.
7. **Not drawn.** The design draws no translation-progress or partial-translation state in the Admin; none was invented. The
   data is on the record for the console to show when the design adds it.
8. **Review conditions, fixed.** Merged `main` (#209: `clean_asr_cues` runs after the `_speech` try/except). Commons requests send a
   Wikimedia-style User-Agent naming the project URL (no personal address), pin `allowed_hosts` (API: commons.wikimedia.org,
   download: upload.wikimedia.org) and use `redirects=1` (a renamed File: resolves; the filename is re-derived). A 403/429 from
   Commons is `commons_rate_limited`, any other failure `commons_unavailable`, never `unsafe_source`. The licence is kept apart from
   `license`; the credits rows and the listening source carry `license_name`/`license_url` (the credits page does not yet render the
   link: follow-up). `splitMediaUrls` also splits scheme-less `host/path` pieces after a comma and trims trailing `. ; ,` and an
   unmatched `)`; a URL with a literal space is still cut in two. A re-run clears `translation`/`translation_counts`. Tests: a
   captured CC licence stays `rights=unknown`/held, `<script>` in Artist is plain text, oversize and 429 responses.
9. **Follow-ups.** Re-importing an existing shared item with the same media id rewrites the whole entry (`source`, `creator`,
   `title`), as before but now with Commons-derived values; confirm whether a curated title should survive. The credits page link
   for `licence_url`. The Admin partial-translation state is in `UI_BACKEND_GAPS.md`.

## D-206 - Admin preview of held media in the learner player; full admin transcript; ZH tap verified (2026-10-15)

Status: ACCEPTED (merged as #214 once CI was green; independent review APPROVE on 9f9f5a6b, no open P0/P1). Video Sources
mini-trial P1-5, P1-6 and P2-10 (part). No schema or migration change, no new role, no change to the publish or
visibility policy.

1. **Preview of a held item.** `GET /api/media/admin/player/{media_id}` behind the existing `require_admin` answers the
   learner player's payload (`stored_media_payload`, one builder, `allow_unpublished=True`) for a *shared* entry in any
   state. A personal entry, an unknown id and a non-admin are refused (404, 404, 401/403). It only reads: publish and
   rights state are untouched. The learner routes (`/api/listening/library`, `/api/media/my`, the library listing) are
   unchanged and still answer 404 for an unpublished item, to everyone including an administrator. The held item's own
   bytes (`/api/media/files/...`) play for an administrator only. The Admin item page's "Open as learner" now shows for a
   held or unpublished *imported* item and opens `#/content/media:preview:<id>`; the media resolver maps `preview:<id>` to
   that route. The hint "Not visible to learners while it is not published" stays. A signed-out local developer session
   is an administrator under the existing guard, as for every other admin route.
2. **Transcript.** The Admin item page lists every segment (the 12-segment cap is removed) in its own scrolling region.
3. **ZH tap (P1-5).** Not broken. The Listening player never reads the stored `words` for a tap (only for timing); it draws
   one Han character per column and widens the tap through the local tagger over the line's *text* (`widenHanTap`, #209).
   New items store unspaced text, so jieba groups it (fixture lines shaped like the trial's: 中国, 政策, 洗手, 肥皂, 神龙,
   北京 ...). The old spaced item the trial tapped is old data and still opens single characters. Gates: a fixture of
   trial-shaped lines (single-character word arrays), kept equal to the live tagger by pytest and replayed through
   `widenHanTap` in `scripts/test_orena_reader_tap_word.mjs`.
4. **Source line (P2-10 part).** The Admin item page shows the decoded address. The failure reason and translation counts
   stay with PR-A.
5. **Not done / for the owner.** Opening a preview in the learner player writes the administrator's own continuation (and
   any practice progress) like any learner session; the player does not know it is a preview. Whether to suppress that is a
   product decision. The player's own tap-through was checked by gate and fixture, not in a browser on a real held item.

## D-207 - Line translation completes within a bounded continuation and a partial one says why (2026-10-15)

Status: ACCEPTED (merged as #215 once CI was green; independent review APPROVE on f870aacf, re-review APPROVE on fc3b24e9, no open P0/P1). Video Sources milestone, PR-A. No schema or migration change: the new value lives
in the existing `processing` JSON beside `translation_counts`.

1. **Root cause (from the code; the trial left no log line to confirm the provider's answer).** Translation is one call per
   language into `prepare_media_meanings`. The shared translator split the transcript into 24-line provider batches and stopped
   at the first batch that did not return (`break`), the service dropped the provider's reason, the pipeline recorded a log
   warning and never asked again, and Groq's HTTP 429 was folded into a generic `TranslationProviderError`. That reproduces every
   observed shape: the first batch(es) landed and the next was refused (24/47, 24/69, 48/113), or the first was refused (0/47, 0/130).
   A transcript over 8 batches (192 lines) was refused outright with an empty answer and no reason.
2. **Fix.** The provider error carries a stable `reason` (`rate_limited` with the provider's `Retry-After` /
   `x-ratelimit-reset-*` wait, `provider_error`, `provider_timeout`, `provider_auth`, `request_too_large`, `not_configured`,
   `malformed_result`); the service and the translator pass it up (`MediaTranslationResult.reason`, `TranslatedLines`,
   `MeaningOutcome.reason`). The pipeline continues the missing lines for at most `TRANSLATION_MAX_ROUNDS` (5) rounds per
   language: finished lines come from the persisted cache so a round requests only what is missing, a wait is the provider's
   own (capped at 60 s, 150 s in total, else 5 s), a round that progressed does not wait, and a terminal reason
   (`spend_cap`, `provider_auth`, `not_configured`, `too_large`, `request_too_large`) stops at once. Every round is checked
   against the AI spend cap with an estimate for the missing share only, so the cap is unchanged and no worker or provider is
   added. A long transcript is translated in windows of at most 192 lines across rounds instead of being refused.
   Two more stops end a run early: a `Retry-After` over 60 s stops at once with `rate_limited` instead of sleeping into the
   same refusal, and a round that adds no line and names no reason stops. Refused provider calls (HTTP 429, 401, 403) are
   still recorded once in the quota telemetry before the error is raised.
3. **Honest stop.** When it still ends partial or failed, `processing.translation_reason` holds the stable code (`rate_limited`,
   `provider_error`, `spend_cap`, `incomplete`, ...), cleared on success and on re-run; the admin `outcome.translation` returns
   `{state, reason, counts}`.
4. **Oversize file.** A file over the 64 MiB cap now fails with the stable code `media_too_large` and one sentence on every host
   (direct, archive.org, Commons), not `commons_unavailable` / "try again later". The cap is unchanged.
5. **Transcoded upload URL.** An `upload.wikimedia.org/.../commons/transcoded/...` rendition imports as a direct file without the
   Commons File lookup; the download stays pinned to the upload host with the project User-Agent. Original uploads and File:
   pages still resolve through Commons for provenance.
6. **Admin item page.** The failure reason is shown whenever the item failed, also with stored lines (Umu: `language_mismatch`),
   and the existing Details list gains a "Translation" row (state, per-language counts, stop reason). This reuses the page's
   banner and key/value patterns and adds no new component; D-205's open question (whether and where to show it) is answered
   by the human request that scoped this PR and recorded in `UI_BACKEND_GAPS.md`. Copy is EN/VI/ZH. `content-pages.js` called
   `banner` without importing it, so the processing banner threw on a queued item; the import is added.
7. **Owner decisions left open.** Raising the 64 MiB cap (not done). A control to retry only the missing lines of a finished item
   (reprocess still redoes everything). Whether the 5-round / 150 s bound suits the provider's real limits once a real batch is
   measured (no live provider was called; tests use fakes).

## D-208 - ASR transcripts: one Chinese script per item, and hallucinated segments removed (2026-10-15)

Status: ACCEPTED (merged as #218 once CI was green; independent review APPROVE-WITH-FOLLOWUPS on b2742791, re-review APPROVE on 2be1537e, no open P0/P1). Video Sources milestone, PR-B. No schema or migration change: the counts live in
`processing` (an existing JSON field) and the recogniser signals are optional fields on an in-memory dataclass.

1. **Script.** ASR cue text and the stored word arrays of a Chinese item are converted to the item's script before lines are cut:
   Simplified by default, Traditional for a `zh-Hant`/`zh-TW`/`zh-HK` language tag (`languages/chinese/script_conversion.py`).
   The table (`script_map.json`) is derived from the vendored CC-CEDICT pack by `scripts/build_chinese_script_table.py`, one
   character to one character, so lengths, timings and tap alignment are unchanged. No new dependency. Simplified to
   Traditional skips a character with more than one Traditional form (发, 后): it is left as written, never guessed.
   The provider already receives the language hint (`zh`); a Whisper language code cannot name a script, and a prompt hint
   would need a provider-interface change, so it is not added.
2. **Filter.** `media_asr_filter.screen_segments` runs on the joined segments of every ASR item (EN and ZH, one contract),
   never on captions. It always drops a subtitle-credit line or a bare sound tag, and a segment the recogniser doubts
   (`no_speech_prob` > 0.6 with `avg_logprob` < -1.0, or `compression_ratio` > 2.4; the Whisper skip thresholds). A stock
   sign-off ("Thank you", "The End", "I'm sorry", 谢谢) is dropped when it is long for its few words or the recogniser doubts
   it (`no_speech_prob` >= 0.3, `avg_logprob` < -1.0 or `compression_ratio` > 2.0). Context alone (10 s of silence beside it,
   an adjacent repeat) and a lone word at the tail after 2 s of silence drop only when the provider gave no confidence signal;
   when it did and shows no doubt, the segment is kept and flagged, so a real "Bye. Bye." or closing 好的 survives. A long
   segment with few words that matches nothing is kept and flagged. Words inside a dropped segment are removed with it. The
   phrase lists are `writing_coach/media_asr_hallucinations.json`, with a stated basis and a line per language.
3. **Recorded.** `processing.asr_filtered` and `processing.asr_flagged` are written on ready, held and failed outcomes of an ASR
   item (0 for captions). If everything is filtered the item fails `empty_transcript` with the count as the detail.
4. **ZH cut.** A recogniser cut with under 500 ms of silence after it is mid-sentence and no longer receives a full stop; a
   question particle still closes it.
5. **Known limits, review step.** Key-term recognition errors (大国空潮 for 大国空巢, BOA for VOA) and wrong-but-fluent
   mishearings cannot be found by rules and are not corrected; a transcript still needs a human read before rights are
   confirmed. A stock sign-off beside a long silence, an adjacent repeat, or a lone tail word is dropped only when the provider gave no confidence signal; with signals and no doubt it is kept and counted in `asr_flagged`. Real speech can still be lost where the recogniser itself doubts a stock phrase or the segment is long for its few words (a true "Thank you" given with low confidence). `asr_filtered` and `asr_flagged` let a reviewer see both. The admin does not yet render `asr_filtered`/`asr_flagged` (API only; `UI_BACKEND_GAPS.md`).
6. **More known limits.** (a) Ambiguous characters stay unconverted by design (麼, 著, 乾, 徵, 餘 and the like: 什麼 and 那麼 can
   remain Traditional inside a Simplified item), so a line can still mix scripts at those characters. (b) The Traditional
   path is currently unreachable: imports store only `zh`, so every Chinese ASR item is normalised to Simplified, including
   genuinely Traditional audio. No import option is added here; recorded as a gap in `UI_BACKEND_GAPS.md`. (c) The screen counts
   are cleared at the start of every run, so a caption-path re-run or an early stop shows 0.

## D-209 - `/api/media/files` serves a file only through the stored entry that owns it (2026-10-15)

Status: ACCEPTED (merged as #219 once CI was green; independent review APPROVE on e8105b2f, no open P0/P1). Fixes #216 (P2-2 of the #214 review). No schema or migration change, no new
role, no change to the publish or visibility policy: this enforces the existing rule that held content is not learner-visible.

1. **Problem.** The file route looked up `upload-<segment>` only. Direct-URL (including Wikimedia Commons) imports store under
   `media/direct-<sha256(url)>/`, so a held direct import was served to anyone who knew the path.
2. **Rule.** The route resolves the entry that owns `media/<directory>/...` by id candidates (`<directory>`, `upload-<directory>`)
   and, failing that, by the directory its recorded playback URL or thumbnail names, in either library. One rule then applies:
   published shared is everyone's (as before); held or unpublished shared is an administrator's only, learner and anonymous get
   404; personal is its owner's (same language), as before. If several entries claim a directory, all must allow the caller.
3. **No owner, no file.** A key no entry owns, and any key outside `media/`, is 404, administrators included. Checked first:
   thumbnails (recorded in the entry) and playback URLs live under an entry's directory. Model clips live under
   `speaking/model-clip/` (a private upload's under its own `media/<token>/model-clip/`) and are read through the speaking
   routes from the asset store, not through this one. Nothing legitimate relied on serving an orphan.
   Cache: only published shared files keep `public, max-age=31536000, immutable`; every other file is `private, no-store`, so a
   CDN cannot hold a held or personal file and hand it to someone else (the previous personal `private, max-age=3600` is now no-store).
4. **Traversal.** Every segment must match `[A-Za-z0-9_.-]+` and not be `.` or `..` before any lookup; the asset store's key
   validation is unchanged behind it. Tests: `tests/test_media_files_gate.py`.
5. **Left open.** `_remove_personal_entry` deletes `media/<provider_media_id>`, which is not a direct import's directory
   (`media/direct-<token>`); personal uploads are unaffected. Not changed here.

## D-210 - Admin preview of held media is read-only; Credits balance shows "—"; the 64 MiB media cap stays (2026-10-15)

Status: ACCEPTED (merged as #220 once CI was green; independent review APPROVE WITH CONDITIONS on caee5b01, re-review APPROVE on 1b34281d, no open P0/P1). Owner decisions of 2026-10-15; the first closes D-206 §5. No schema or
migration change, no new role, no change to the publish or visibility policy. D-208 and D-209 are in flight; this is the next
free number and is renumbered at merge if they land first.

1. **Preview of a held item writes nothing (owner 2026-10-15).** `#/listening/preview:<id>` (D-206, `GET /api/media/admin/player/{id}`)
   opens the real learner player, and the administrator is not a learner on that item: no place, progress, completion, streak,
   activity, practice or dictation attempt, saved word, note, highlight, response, review scheduling or record of where a word was met.
   Three independent walls, so the rule does not rest on one:
   - **Client, the room.** The Listening room derives "preview" from the address (`mediaRef(...).kind === 'preview'`). It does not
     remember a place (device or server), passes `readOnly` to the line practice (a check still marks the line; no draft, no attempt is
     stored), the word sheet and the Vocabulary Focus, and does not draw what would keep something: the word sheet's save icon and
     button and its link to the word page, the Vocabulary Focus "Save", the selected line's "Save phrase", and the links into Shadowing,
     React and Respond, which save. The design has no disabled state for these, so they are hidden, not greyed; nothing is added.
   - **Client, the request.** `infrastructure/preview-mode.js`: while the room is a preview, `request` refuses every call that stores
     learner state (a list of path prefixes, with the gate that lists them), whichever code makes it. Reads, lookups, tagging and
     translation are not on the list. The wall is open only while the address is still a preview, so a room that fails cannot leave the
     app read-only.
   - **Server.** `listening_api.media_state_writable` / `require_media_state_writable`, reusing `stored_media_entry` (the one
     visibility check): an id that names a stored media entry takes learner state only while that entry is visible to this learner,
     that is a published shared item or the learner's own personal import. A held, unpublished or archived shared item and another
     learner's import answer 404 `media_not_available`, whoever sends the write, in every spelling (`<id>`, `media:<id>`, `upload:<id>`,
     `preview:<id>` and prefixed forms). An id no stored entry names (a curated lesson, a text, a book) is unaffected. Applied to:
     `PUT /api/continue/{id}`, `POST /api/listening/progress`, `POST /api/listening/shadowing-progress`, `PUT /api/annotations/{id}`,
     `PUT /api/responses/{key}` (its `sourceId`), `POST /api/library/vocabulary/{word}/provenance` (its `sourceId`) and
     `POST /api/library/items` (its `source_id`). The owner's own personal import keeps writing (tested).
   - **Gap, stated (review #220 P2-2).** `POST /api/library/vocabulary` (save a word) and its review, restore and delete carry no media
     id (a word is the learner's, not the item's), so the server cannot tell a preview from a learner there: only the two client walls
     cover it. Accepted risk: it needs an administrator session and a client defect, and costs one word in the administrator's own library.
   - **Orena in a preview (review #220 P2-1, owner rule "no learner activity").** The room does not draw Explain; the word sheet does not
     draw "Ask deeper" (nor the save row) and shows the "why here" line as text, not a way into Orena. The request wall also refuses
     non-GET `/api/agent/*` and `/api/conversations/*`. This is the learner wall only; the Intelligence lane's server code is unchanged.
     A preview opened elsewhere in the shell (the Orena panel itself) therefore cannot take a turn while the address is a preview.
   - **Guard cost and failure (review #220 P2-3, P2-5).** The id spellings are peeled to the one bare id the store is keyed by: at most one
     store read per write, then `visible_to` on that entry. Media-shaped means any id the store could hold (its own `_ID` pattern, ':'
     included) outside the known non-media namespaces. Those namespaces (`article`, `book`, `text`, `url`, `reading`,
     `conversation`, `voice`, `expression`, `essay`, `grammar`, taken from the content kinds, the account-record source forms and
     `intent.js`) cost no read and are never refused by this guard, so Reading and Book writes do not depend on the media
     index's health; neither does an id the store could never hold (empty, spaces, over-long). For every other id the guard fails
     closed: a corrupt or unreadable index or an error refuses the write; a missing index is a fresh start. The read's issue
     travels with the read (`FileMediaLibraryStore.lookup` returns `(entry, issue)`), not through the shared `last_read_issue`
     that every concurrent read resets (re-review P2-A, P2-B).
   - **An item unpublished or archived while a learner is on it (review #220 P2-4).** Writes against it now answer 404
     `media_not_available`. The place write is already best effort and silent. The Dictation save treats that 404 as "not kept": no
     note, no retry, nothing loops, and the room stays usable (the line is still checked and shown). Reopening the item gives the
     normal unavailable state. A learner's earlier progress stays stored, unreachable until the item is republished.
   - **Existence oracle (review #220 P2-6), accepted low risk.** A write to a hidden id is a 404 while a write to an id nothing names
     succeeds, so a write is a faint existence check for a hidden media id. Closing it would refuse curated lesson and text ids that no
     store names. Media ids are digest-shaped and the listings already hide them at the same level.
   - Progress and streak are derived from the records above, so blocking the records blocks the derived figures.
2. **Credits balance shows "—" until a balance API exists (owner 2026-10-15).** More honest than hiding it or a fake 0. This confirms
   the Credits top-up client's `UI_BACKEND_GAPS.md` CT-2 handling (balance and ledger are admin-only; the hero and card read "—" beside
   the unit, never 0) and closes its P2-6 question: the glyph the design does not draw is accepted.
3. **The 64 MiB media cap is unchanged (owner 2026-10-15).** A file over the cap keeps failing with the stable code
   `media_too_large` (D-207 §4). Whether to raise the cap or to move to streaming / chunked processing is decided after the Phase 2
   size distribution of the Video Sources milestone is known, not before.

## D-211 - ZH Traditional to Simplified is completed from Unihan; a long transcript finishes translating by a bounded deferred continuation (2026-10-15)

Status: ACCEPTED (merged as #224 once CI was green; independent review APPROVE WITH CONDITIONS on 60b0e32b, re-review APPROVE on 11b6ee06, no open P0/P1). Video Sources milestone, mini-trial rerun blockers N1 and P1-2. No schema or migration
change: the new value lives in the existing `processing` JSON beside `translation_counts`. No learner UI, no new provider, no new
worker, the AI spend cap unchanged.

**A. Script normalisation (extends D-208 §1 and §6a).**
1. **Why each survivor survived (found by running the shipped converter on the trial's own character list).** At this commit
   `勵` already converts to `励` (it is in the CC-CEDICT one-to-one table), so the `勵` in the trial's VOA note is not reproducible
   from the code; the only character of the trial's list that the converter left was `麼`. `麼` is skipped on purpose by D-208: CC-CEDICT
   lists it as the traditional form of two Simplified entries (`么` and the variant `麽`), so the dictionary alone cannot choose.
   The other known leftovers are the characters that are Traditional and still Simplified: `著` (着 in 看著, 著 in 著名), `乾` (干 in
   乾淨, 乾 in 乾坤), `覆` (复 in 回覆, 覆 in 覆蓋), `徵` (征 in 徵求, 徵 the musical note), `瞭`, `藉`, `摺`, `夥`, `於`, `剋`,
   `苧`, `衹`, `麴`, and `餘` (余 or the variant 馀). D-208 left all of them as written; none is "missing from CC-CEDICT".
2. **Source and licence.** The Unicode Unihan `kSimplifiedVariant` field (Unicode 18.0.0, `Unihan_Variants.txt`, 2026-07-31), under the
   Unicode License v3 that already covers the Unihan data vendored in `lexicon_data/` (`UNICODE-LICENSE.txt`). OpenCC `STCharacters`
   (Apache 2.0) was not needed. Recorded in `THIRD_PARTY_NOTICES.md` and the `lexicon_data/README.md`. A generated data file, no runtime
   dependency: `lexicon_data/unihan_simplified_variants.json` (7,291 characters, the one field kept, with the source archive's SHA-256)
   is refreshed by `build_chinese_script_table.py --unihan-zip Unihan.zip`; the default run reads it offline, so the build is deterministic.
3. **Rule (all in `scripts/build_chinese_script_table.py`, `derive_variant_maps`).** A Traditional character that the CC-CEDICT table
   does not convert and for which Unihan names exactly one Simplified form in the original block (U+4E00 to U+9FA5, a glyph in every
   font) that no standard CC-CEDICT word uses as written is converted everywhere (64 characters: `麼` to `么`, `參` to `参`, `噁` to
   `恶`, `錄` to `录`, ...). Where the Simplified form depends on the word (Unihan names several, or the character is still Simplified
   in some words; 15 characters), the default is the form CC-CEDICT writes most often at that position for that Traditional character
   (the documented basis; `餘` is `余` in far more entries than `馀`), and the standard CC-CEDICT words of 2 to 4 characters that contain
   the character are kept as written (`著名`, `显著`, `乾坤`, `乾隆`, `覆盖`, `颠覆`, `狼藉`, `瞭望`). A word that CC-CEDICT also
   lists with the default form (`回覆` beside `回复`, `藉口` beside `借口`) is a variant spelling and does not protect the character. A
   character with no evidence or a tie (17, `unresolved` in the table: `阪`, `奬`, `藴`, ...) is left as written: a wrong character is
   worse than a script left mixed. The choice is made on the converted text, so `顯著` is found as `显著`; the recogniser's word array is
   converted as one running text so a word it splits (`著|名`) is judged whole.
4. **Still one character to one character.** Lengths, word timings and tap offsets are unchanged (tests). Simplified to Traditional is
   unchanged. `script_map.json` is now `orena.zh-script-map.v2` (a new `contextual_to_simplified` and `unresolved`); the reader
   tolerates a v1 file.
5. **Simplified text is never altered (independent review of #224, P1-1).** The context layer acts only near Traditional evidence:
   a character is judged only when a Traditional-only character (`script_detection`, the same table that classifies a text) lies in
   the same clause (stops and line breaks end a clause) within 30 characters. Text with none is returned as written, so 鲁迅著,
   乾卦, 宫商角徵羽 and 覆水 stay. The evidence is measured on the text before any conversion. Words and cues are judged by the same
   rule, so an item with a stray Traditional character does not change its Simplified clauses. A Traditional sentence with no
   Traditional-only character at all (看著我) is also left as written: with no evidence it cannot be told from Simplified.
   **Accepted limit (re-review P2-5):** the evidence is clause-scoped, so a context character in a Traditional cue whose clause has no
   Traditional-only character stays unconverted (他看著我 keeps 著). This is the accepted cost of never altering Simplified text; re-check it
   on VOA.
6. **Known limits.** The context judgement uses CC-CEDICT's words only: near Traditional evidence, any word CC-CEDICT does not list
   takes the default (a name written with `乾` or `著` can change; `於` is converted to `于`, right outside a surname). Not converted,
   with the reason: 諮 (Unihan gives 谘, the standard form is 咨) and 讎 (Unihan gives 雠, the standard is 仇), listed in the build
   script's `EXCLUDED`; 戱 is dropped because its target 戯 is itself converted. A conversion is a single step and the build fails if
   any target is also a key. Compatibility ideographs (U+F900 to U+FAFF, U+2F800 to U+2FA1F) are written as their unified form
   first (NFC of each is exactly one code point, tested), so 豈 and 龜 in compatibility form convert. "Length" here is code
   points: five astral keys map to a basic-block character, which changes the UTF-16 length, harmless because conversion runs before
   any offset is computed. `--check` fails when the table is stale or when a sentinel word (the trial survivors and the kept
   words, after a Traditional marker) does not convert as stated.

**B. Long transcripts finish translating (N1; extends D-207 §2).**
1. **Which limit (from the code and the repository's measurements; no provider call was made).** Groq answered the key with 1,000
   requests (per day) and **8,000 tokens per minute** (`ORENA_AI_COST_REDUCTION_PLAN.md`, read from its headers). A 24-line request
   reserves its prompt plus 2,048 completion tokens, about 2.8k of the 8k, so two or three requests fit in a minute: exactly the
   24/47, 24/69, 48/113 and 24/78 shapes, and `0/78` when the minute was already spent. Requests per minute (30 on the free tier) are
   not reached. The per-minute window refills within about a minute, so the right behaviour is to wait for it, not to give up after
   five rounds. D-207's in-job rounds also stop at once on a `Retry-After` over 60 s, which is where a long transcript was lost. A
   daily token allowance would show as a much longer wait; it cannot be told from the code, so a 429 now logs the response's
   `x-ratelimit-*` headers (counts and durations, no credential), and a wait over 300 s is never scheduled. I designed for both.
2. **Design.** After the existing bounded in-job rounds, a run that ends `rate_limited` records
   `processing.translation_continuation = {attempt, max_attempts, next_at, deadline, retry_after}`, sets `translation` to `deferred`,
   keeps `translation_reason = rate_limited` and the `translation_counts` so far, and arms a one-shot timer for the provider's own
   `Retry-After` (at least 20 s, 65 s when it gave none, at most 300 s). The timer only hands the job to the **existing single pool**
   (`workers=1`): no new worker, no concurrency. The continuation asks for only the lines the persisted cache lacks, in at most two
   rounds that do not sleep (the schedule is the wait), and either finishes (`ready`, continuation cleared), or defers again.
   Bounds: at most 6 attempts, 30 minutes from the first deferral, one wait at most 300 s. When a bound is reached, or the stop is
   anything but `rate_limited` (`spend_cap`, `provider_auth`, `provider_error`, ...), the continuation is cleared and the item ends
   `partial` or `failed` with the stable reason, as before. Every round checks the AI spend cap with an estimate for the missing
   share only (unchanged), so the cap holds across continuations.
3. **State is honest while it is pending.** The item's own state is untouched (a held item stays held, a learner import stays ready):
   a continuation never writes `state`, `stage` or `status`. `processing.translation` is `deferred`, the one existing value for "not
   complete yet"; it is distinguished from its other use (translation not configured) by the presence of `translation_continuation`
   and non-empty counts. The admin `outcome.translation` returns it as `continuation` only while pending. Lines already translated are
   readable at once (the cache). A re-run (reprocess) clears the continuation at its start and wins over a pending timer; a restart
   re-arms it from the record (`recover()`), so it survives the process. A timer honours `next_at`: one that fires early (its record
   was replaced by a later deferral) does nothing, the proper timer being armed. Before every provider round of a continuation the
   item is read again; archived, removed, cancelled, re-run or a different continuation stops the attempt before the call (review
   P2-1, P2-2).
4. **Owner decisions left open.** The 6 / 30 min / 300 s bounds suit one minute's allowance; a measured real batch should confirm them.
   No admin control to continue by hand and no learner-facing "translating" wording are added (no UI change; the admin Details row
   shows the state through `outcome.translation`). Smaller request windows were not adopted: the completion reservation (2,048) guards
   a reasoning model against `finish_reason=length`, and halving the window would only change how many requests share the minute.

## D-212 - The local annotate tagger answers any supported language (2026-10-15)

Status: ACCEPTED (merged as #222 once CI was green; independent review on 855d52c4: design approved, P1 test fixed in this commit). No schema or migration change. D-211 is reserved by the parallel normaliser/translation PR.

`POST /api/media-learning/annotate` is local, stateless and spends no AI, yet it answered 409 unless `source_language` was the
learner's current learning language. The administrator's preview of a held item (D-206, read-only by D-210) shows a language that
is not the viewer's, so a Chinese tap there could not be widened to the lexical word and stayed on one character (Video Sources
P1-5, still open after #209 and #214).

1. `/annotate` answers `en` and `zh` whoever asks; any other language is 422. The endpoints that call the AI provider (explain,
   register, conversation and the rest of `_validated_source_language`'s callers) keep the learning-language match, pinned by
   `tests/test_media_interaction.py`.
2. The Listening room asks the tagger through `taggerAllowed`: in a preview for any supported language, otherwise only in the
   learner's language, as before. The Reader is unchanged.
3. The preview entry page (Content Detail) draws no Save and no "..." (D-210).

## D-213 - The caption path keeps what it was given: reprocess never swaps captions for ASR, the fallback is visible, translation can be retried alone (2026-10-15)

Status: ACCEPTED (merged as #226 once CI was green; independent review APPROVE on 1aec46a8, no open P0/P1). No schema or migration change (`processing` and `source` are free-form records); no new provider; no cookie or proxy; the spend caps are unchanged; items stay held.

Evidence: the 2026-10-15 EN caption batch on the sandbox. Eight YouTube items imported on the provider-caption path at $0. Translation then ended `rate_limited`, and the only way to continue was admin `reprocess`, which re-ran the transcript step, fell back to Groq Whisper without saying so and replaced the human captions on all eight ($0.034). A reprocess that failed at the audio step turned items with a good transcript `failed`. YouTube probably answered the caption fetch with HTTP 429 from that IP (unproven). D-211's automatic continuation covers a translation that is rate limited; it does not cover one whose budget is exhausted, and nothing let an operator continue by hand.

1. **Reprocess keeps provider captions.** Before a re-run of an item that is `ready` or `held` with a transcript that passes the checks, `retry()` keeps a snapshot of its processing and status (`processing.previous`). If the stored transcript came from provider captions and the caption fetch now fails or yields nothing (a 429, a timeout, no track) or the captions fail the quality checks, the run stops with the stable reason `captions_unavailable` or `captions_unusable` before any ASR call, and the item is put back exactly as it was. The reason is recorded as `processing.reprocess_reason` (+ `reprocess_message`). An item that never had captions keeps today's fallback to ASR.
2. **The first-import fallback is visible.** The production YouTube adapter defers transcript recovery, so a refused caption fetch returned "no transcript" and looked identical to a video with no captions. The adapter now says so in its provenance (`caption_status: unavailable`), the importer stores it on the item's `source`, and the pipeline records `processing.caption_fallback` (`captions_unavailable` when the provider refused, `captions_unusable` when captions arrived but failed the checks) when it listens to the audio instead. A source with simply no captions records none. The admin media Details shows it as "Transcript source", in EN/VI/ZH, beside Translation (no new UI element).
3. **Manual versus auto is recorded.** The caption client already preferred a manual track; the track now carries `kind` (`manual` | `auto`), the provenance passes it on, and the item records `source.caption_kind` and `processing.caption_kind`. Only-auto is recorded as `auto`.
4. **The player payload origin is the real one.** `processing.origin` was written at the end of a run and the payload's `transcript_origin` when the lesson was stored, so a run that stopped between them left `provider_caption` beside `generated_asr`; the learner header then called human captions an automatic transcript. `_store_lesson` now writes both in one update.
5. **A failed reprocess does not destroy a good item.** Any stop of a re-run (transcript step, a transcript that fails its checks, a crash, too many interruptions) restores the snapshot instead of writing `failed`; the lesson was never replaced, so the transcript and the translation stand. A first import with no snapshot fails as before.
6. **Translate only.** `POST /api/admin/console/content/media/{id}/reprocess?scope=translation` (same `require_admin`, same-origin and audit as reprocess; `scope=all` is the default) asks again for the lines without a meaning and nothing else: no caption fetch, no ASR, no write to the lesson, the item's state or status. It restarts D-211's continuation budget, runs under the item's batch spend cap (unchanged), and answers 409 while the item is being processed or has no transcript. The admin media page enables the design's own "Translation only" option of the Reprocess block (`Orena-Admin.dc.html`: "keeps transcript"); "Keep manual transcript edits" stays disabled.
7. **The translation `source` label.** `listening_api` reported `curated-editorial` whenever the request itself made no provider call, so a generated translation read from the cache was labelled editorial. The source is now `media-translation` whenever any shown meaning is generated (now or earlier), and `curated-editorial` only for editorial meanings.
8. **Review follow-ups (same PR).** A restore re-arms the continuation timer it brings back (P2-1); a run cancelled by archive clears its snapshot (P2-3); D-211's continuation job runs under `system_funding("media_pipeline")` like `_job`.
9. **Accepted, known limits.** P2-2: a non-stop exception after `_store_lesson` (a store outage in the later writes) restores the old `processing` beside the new lesson, the one remaining way origin and payload can disagree; narrow, accepted. P2-4: any categorised import error from the caption fetch is recorded as `captions_unavailable` (safe, broader than "the provider refused"); a malformed-transcript mapping to `captions_unusable` is left for later.
10. **Owner decisions left open.** Whether a manual track already stored should also be protected against a reprocess that finds only an auto track (today the fresh captions replace it). Whether a held item with `captions_unavailable` should be retried automatically later (not added: it would be a new scheduler). Whether the 8 ASR-converted items of the batch are kept or re-imported.

## D-214 - Caption-only imports never fall back to ASR; the continuation waits as long as the provider asked, inside its budget (2026-10-15)

Status: ACCEPTED (merged as #227 once CI was green; independent review APPROVE on 117f22ec, no open P0/P1). No schema or migration change (`source` is a free-form record and the option lives there); no new provider; no cookie, proxy or bot bypass; the spend caps are unchanged; items stay held. No learner UI and no admin UI change (see 1.5).

Evidence: the 2026-10-15 EN caption batch, attempt 2 (`youtube-LlhdnpsADZs`, sandbox :8021 at 006ad0f7). The caption fetch was refused (HTTP 429), the importer fell back to Groq Whisper on its own ($0.0066, 595 s of audio) and the operator had no way to refuse that. Translation then ended `partial 72/114`, `rate_limited`, and `processing.translation_continuation` stayed `{}`.

**1. Caption-only import.**
1. **The option.** `transcript_policy` is `captions_or_asr` (the default, today's behaviour; unset means it) or `captions_only`. It is a field of the admin media import (`POST /api/admin/console/imports/media` and `POST /api/media-learning/admin/import`, which share the model): on the batch (`MediaImportIn.transcript_policy`, the default for every item) and on each item (`MediaImportItemIn.transcript_policy`, which wins). A value other than the two is refused (422).
2. **Where it is kept.** On the item's `source` (`source.transcript_policy`, written only for `captions_only` and only for a YouTube item: a file upload or a direct URL has no caption track and keeps its single route). Because it is on the item, a reprocess keeps it: a caption-only item is never sent to ASR by a re-run either.
3. **What it does.** In the transcript step, when the provider's captions are refused, absent or fail the quality checks, the run stops before `_speech`: no audio download, no yt-dlp, no ASR request, no ledger record and no ledger check. The item ends `failed` (status `review`, the state a first import with no transcript already has, retryable by Reprocess) with the stable reason `captions_unavailable` (refused, timed out, or no track) or `captions_unusable` (fetched but failed the checks), the existing codes of D-213; `processing.detail` carries the provider's category. The messages of those two codes no longer say "the stored caption transcript was kept" (untrue for a first import); they say speech recognition was not run and any stored captions were kept. EN/VI/ZH `impErr_*` copy updated to match.
4. **Do caption imports download audio? (answer for the owner).** Not for the transcript: a caption import (`origin=provider_caption`) never calls the downloader or ASR. The only audio download on a caption item is `_prepare_model_clips`, which runs after readiness for a personal item or one whose rights are `cleared`, to cut the model clips Compare measures (`media.model_clips_enabled`). It is best effort (failure is logged and never blocks readiness). A held, rights-unknown item (the whole trial) downloads nothing. When the transcript step stops, `_run` returns before that code, so a failed transcript never reaches it (tested). A caption-only item that succeeds and is cleared still cuts model clips from the audio; whether `captions_only` should also skip that is left to the owner (it is a YouTube request, not spend).
5. **Admin UI: API-only, gap recorded.** The pinned `Orena-Admin.dc.html` "Import media" form (A11, `urlBlocks`) draws a URL field, Preview and Import and nothing else: no place for a transcript option. Nothing was invented; the gap is in `UI_BACKEND_GAPS.md`. Batch import: the same model serves the batch, so one value covers a list.

**2. The continuation did not arm (systematic debugging).**
1. **Evidence.** The item record on :8021 (read-only): `translation=partial`, `counts vi 72/114`, `translation_reason=rate_limited`, `translation_continuation={}` (the key exists, so it ran D-211's code and `_run` reset it), origin `generated_asr`, status `archived` only later (the coordinator, after the run). The sandbox container log has exactly three of the 429 lines that D-211 added (they carry the quota headers but no media id, so the match to this item is by shape: 12-line requests, 72 of 114 done): `retry_after=8`, `retry_after=11`, then **`retry_after=521`** with `x-ratelimit-reset-tokens` 58 s and `x-ratelimit-remaining-requests` 991 of 1000. The per-minute token bucket (58 s) was not what the provider asked us to wait for: another allowance asked for 521 s.
2. **Root cause.** `_defer_translation` returned the outcome unchanged when the provider's ask exceeded `CONTINUATION_MAX_DELAY` (300 s, D-211 B.2: "a wait over 300 s is never scheduled", designed for a daily allowance asking for hours). 521 s is neither: it is 8 minutes 41 seconds, inside the continuation's own 1800 s budget, and a continuation could have run twice. The result was `partial` with no continuation and no trace. It is not specific to the ASR path (the ASR fallback only made it visible; a caption item with the same 429 would end the same way); the other candidates were checked and ruled out: the reason was kept (`translation_reason=rate_limited`), the in-job rounds ended on `rate_limited` (the stop reason is read from the last round), no timer was armed to be cleared (no record was written), and the item was archived after the result, not before.
3. **Fix.** `CONTINUATION_MAX_DELAY` is 900 s: one wait may be as long as the provider asked up to a quarter of an hour (twice inside the 30 minute budget); a longer ask (a daily allowance) is still never promised. Attempts (6), the 30 minute budget, the spend-cap check on every round and the single worker are unchanged. Regression test: the exact shape (caption fetch refused, ASR fallback, 72/114, `Retry-After: 521`) arms a continuation scheduled at 521 s with the item still held.
4. **Not proven.** Which allowance asked for 521 s is not known (the headers show the per-minute buckets only). If the real window turns out to be longer than 900 s the item still ends `partial` with `rate_limited` and Translation only (D-213 6) is the operator's way on.

**3. Review follow-ups (same PR).** P2-1: a test that a `captions_only` reprocess of an item with stored captions keeps them (the snapshot is restored, `reprocess_reason=captions_unavailable`, no audio, no spend). P2-2: the rate-limit and continuation log lines now carry the media id (no credential, no header value beyond counts). P2-3: a provider ask over `CONTINUATION_MAX_DELAY` is no longer silent: the item stays held and partial, `translation_reason` is the stable `rate_limited_long_wait` and `processing.translation_retry_after` keeps the ask; the admin Translation row words it in EN/VI/ZH (`impTrReason_rate_limited_long_wait`, the page already renders `translation_reason` codes).

**4. Known limits.** P2-4: a manual re-import of a held `captions_only` item by URL, without the policy, resets it to the default (`_from_url` rebuilds `source`); the Reprocess fallback re-import (admin_console_api) builds a fresh item too, but it only runs for a settled metered personal import, which cannot carry `captions_only`, so it is effectively unreachable. Not carried over. Separate follow-up issue (not this PR, pre-existing): `_translate` books spend at the pre-call estimate whenever a call counts as a provider call, including one the provider refused with 401/403/429, so a refused translation call is over-counted (conservative for the cap, fails safe).

**5. Owner decisions left open.** Whether `captions_only` becomes the default for the trial batch; whether it should also skip the model-clip audio download; a control in the Import media form (needs a design); whether a failed `captions_only` item should be re-queued automatically later (a scheduler, not added).


## D-215 - Admin media imports can take captions from Supadata: native mode only, credit-capped (2026-10-15)

Status: ACCEPTED (merged as #229 once CI was green; independent review CHANGES REQUESTED on baca0188, re-review APPROVE on 3bd92825, no open P0/P1; real-chunk timing to be measured on the first live sample). Owner direction 2026-10-15: paying users (Plus and above) may use it later only as a fallback after YouTube captions, tracked in #230. No schema or migration change (the provenance lives in `source` and `processing`, free-form records, and the request count is rows of the existing media spend ledger file); no new provider (Supadata is already integrated); no cookie, proxy or bot bypass; the spend caps are unchanged; items stay held. No new learner UI; the admin Policies page gains two rows with EN/VI/ZH copy.

Evidence: the :8021 host IP is throttled by YouTube on caption downloads (HTTP 429). A whole-machine VPN unblocks YouTube but Groq refuses the VPN exit (403), so translation and ASR fail. The owner's Supadata Free plan: 100 credits a month plus bonus, no auto-charge; native mode is 1 credit per transcript, generated transcripts 2 credits per minute, translation 30 per minute.

**1. The setting.** `media.caption_source` (policy; env `MEDIA_CAPTION_SOURCE` wins; enum): `youtube` (default, behaviour unchanged), `supadata_native`, `youtube_then_supadata_native`. A value that is not one of them is the default. It is read at each fetch, so a change needs no restart. `PolicyCaptionClient` (`media_providers/caption_source.py`) is the adapter's caption client; with `youtube` it only delegates.
**2. Native only.** The one Supadata call passes the constant `NATIVE_MODE`. `auto` (may generate) and `generate` are never sent and translation is never requested; tests assert the mode on every source value and outcome, on the wire through the real client, and that the module's code names no other mode. No track (an empty answer, or a language other than the one asked for) is "no captions": `captions_only` stops (`captions_unavailable`), otherwise the existing Groq ASR fallback runs. A refused request (HTTP error, timeout) is the D-213 visible fallback, as for YouTube.
**3. Provenance.** `origin=provider_caption`, `caption_provider=supadata` (empty for YouTube's own), `caption_kind=unknown` (Supadata does not say manual or auto, so neither is claimed), `caption_language` = the language Supadata returned. On the item's `source` at import and on `processing` for the transcript; the admin outcome's `transcript` carries `caption_provider` and `caption_language`. The page already shows a provider caption of unknown kind as "provider captions".
**4. Chunk granularity.** Supadata chunks are re-cut by the existing `segment_lines` like any cue (sentence and clause cuts, at most 140 characters and 9 s a line, proportional timing), so a merged chunk cannot fail the five checks on its length. Tested with chunks of 1, 4 and 8 sentences and the whole video in one chunk (fixture observations: a 356-character, 23.5 s chunk becomes 53-character, 3.6 s lines; all five checks pass). What real Supadata chunks look like is not observed here: no call was made. Timing inside a merged chunk is proportional, not measured, so line starts can be off by a fraction of a chunk.
**5. Credit guard.** `media.supadata_daily_requests` (policy, env `MEDIA_SUPADATA_DAILY_REQUESTS`, default 20, 0 turns Supadata off; group Spend). Each request is a ledger row of kind `supadata` (units 1, usd 0, written before the call so one that dies in flight still counts). At the cap the fetch is refused before any call with the stable reason `caption_quota` (a `caption_quota` item reason / fallback with EN/VI/ZH copy). The kind is outside the dollar caps (`KINDS`), so those sums and limits are unchanged. No automatic retry: one request per fetch, a definitive answer (a track, or none) is remembered 15 minutes so the import and the pipeline step that follows it do not pay twice for one video; an error is not remembered, and an operator Reprocess is the only retry.
**6. Scope: admin only.** The learner's acquisition service keeps today's YouTube-only adapter (`build_youtube_adapter()`); the policy caption client is built only into a second service that the admin importer (`import_urls`, `preview`, i.e. any `imported_by` other than `learner`) and the pipeline's caption step for `shared` items use. A learner's import, preview and personal item never call Supadata whatever `media.caption_source` is (tested: zero calls from a learner path, one from an admin import). The learner fallback service (`MEDIA_TRANSCRIPT_FALLBACK=supadata`, generate mode, 2 credits a minute) is unchanged and stays off (`none`). Review follow-ups (same PR): the cap check and record are one step under the ledger lock (`reserve_request`) and a per-(video, language) in-flight lock stops concurrent callers paying twice; the memo evicts its oldest entry; Supadata's 206/404/422 ("no transcript") are a definitive, remembered no-track while 401/403/429/5xx/timeouts are neither remembered nor retried; native calls are logged as capability `media_caption_supadata`; a bad `MEDIA_CAPTION_SOURCE` logs one warning and uses `youtube`. The cap is per process (the ledger lock is), so several server workers could each overshoot it.
**7. Owner decisions left open.** The daily cap value; whether `captions_only` is the default for the trial; whether a `supadata_native` import should skip the oEmbed call too (see the PR's list of remaining youtube.com requests).


## D-216 - A translation round that made no progress costs nothing; a request reserves only the room it needs; import writes are proven path-bound (2026-10-15)

Status: ACCEPTED (owner confirmed 2026-10-15; independent review APPROVE on b7e9b8bd, no open P0/P1; merged as #234 once CI was green). No schema or migration change. Follow-up: #235 (Groq daily allowance); the stall cause below is inferred, so #228 stays open until a live item completes.

Evidence: the 2026-10-15 Supadata trial on :8021 (`SUPADATA_TRIAL_2026-10-15.md`, issue #228). `youtube-4HGNqFdaD34` (49 cues) stayed at 24/49 for nine rounds, each booked at the pre-call estimate ($0.003326, `units` 0 in `processing-spend.json`). The web log, which carries the refusal headers since D-211, shows 5.5k to 8k of the 8000-token minute bucket and 992 or more of 1000 requests left at every refusal, `x-ratelimit-reset-tokens` of 1 to 19 s, and `retry-after` of 6 to 680 s: the minute bucket was not what refused. The 429 body was not logged, so the allowance is inferred (an allowance the headers do not show, most likely the daily token one) and is not proven.

**1. Root cause, booking (certain).** `MediaPipeline` was built in `app.py` without a `translation_sink`, so `usage` was always empty; the booking line `actual = actual or estimate` then recorded the estimate for every round whose result said `provider_calls`, a refusal included. Real tokens were never read and a refused round was charged like a served one. Now the provider reports the tokens an answer billed to a `usage_sink` (a context variable, set by the pipeline by default) and the pipeline books only that. A 401/403/429, a timeout and an answer without `usage` book 0. The cap is unchanged: it is still checked against the estimate before the call; what is recorded after is what the provider said it billed.

**2. Root cause, stall (inferred, fixed where the code owns it).** Every request reserved `max_completion_tokens` 2048 whatever it held, and a provider admits a request against the room left in an allowance for `prompt + max_completion_tokens`. A 12-line batch needs about 500 completion tokens; when an allowance was nearly spent the same batch was refused each time it was asked again, and the retry cadence followed `retry-after`. The reservation is now sized to the batch (two characters a token, floor 256, ceiling the configured value), and the pre-split size uses the short wire handles instead of the canonical hash ids, so a batch is not halved for ids that never travel. Test: a fake provider that admits only when `prompt + max_completion_tokens` fits 2300 tokens of room refuses every request of the old reservation and translates all 49 lines with the sized one. Whether this clears the live item depends on the provider's allowance having room at all; nothing in the code can complete a translation against an exhausted daily allowance. The 429 log now carries the provider's own sentence (which allowance, how much was used), so the next refusal names its limit.

**3. ZH import write failure (not reproduced; no defect found in the code).** Chinese and English imports were run through the real importer, store, asset store and pipeline with the repository mounted read-only and with an audit hook that refuses any write under the repository: both succeed, and nothing writes outside the configured paths (`tests/test_media_import_writes_only_configured_paths.py`). The failing request is not in the :8021 web access log (every other import POST of the session is), the worker log, or any other running container's log; the shared browser tab that sent it lost its session afterwards (401, no cookie), which fits a request that went to another origin. The likely cause is that the trial's request went to a read-only review container (:8025) through the shared tab, not to :8021. Treat the trial's P1 as unconfirmed on this code. To settle it, repeat the ZH import from a clean session against :8021 and read the access log.

**4. Owner decisions left open.** None new. Open question for the review: whether to log the provider's refusal body at WARNING for every 429 (done here, 240 characters) or only at the first of a run.

## D-217 - The ASR audio download is taken in Range pieces under a wall-clock bound; a translate-only retry clears the previous run's refusal (2026-10-15)

Status: ACCEPTED (owner confirmed 2026-10-15; independent review APPROVE on 3243b9ab, re-review APPROVE on b6674e2b, no open P0/P1; merged as #239 once CI was green). Follow-ups in #240. P2 follow-ups of that review are addressed in this PR (below). No schema or migration change, no new provider, no spend-cap change, no cookies or proxies.

Evidence: the 2026-10-15 Supadata trial on :8021 (`SUPADATA_TRIAL_2026-10-15.md`), two P1s, reproduced read-only in the worker container (3 attempts of the app's own download, no import, no write).

**1. ASR audio never downloaded (root cause certain).** `youtube-D_IcGTgWoZY` (no captions) stopped at `transcribe` with `audio_unavailable`. `YtDlpYouTubeAudioUrlResolver` resolves a googlevideo URL (format 140, 6,522,557 bytes, no `ratebypass`), and `download_bounded` fetched it with one plain GET. Measured on that URL from the worker with the app's own opener: status 200, then 1 MiB per 33 s (about 31 KiB/s; 6.5 MB would take about 210 s); the same URL with `Range: bytes=0-1048575` answered 206 and 1 MiB in 0.8 s. googlevideo throttles a non-ranged request, which `yt-dlp` avoids by fetching in 10 MiB Range pieces, so `yt-dlp` took 3 s. Nothing in the app bounded that: the 12 s timeout is per socket read and bytes kept arriving, so the download crawled until the worker was killed. Not the cause: SSRF host pinning, redirects, User-Agent, or an IP mismatch between resolve and download (the ranged request from the same process and address was fast). Fix: `download_bounded` takes `range_chunk_bytes` (each piece is a request through the same address checks; a host that ignores `Range` and answers 200 is read whole under the same budget; `Content-Range` above the cap is refused before a byte is read) and `total_timeout` (wall clock, checked every 64 KiB). `download_audio` uses 10 MiB pieces, a 240 s bound and the unchanged 64 MiB cap. Tests: `tests/test_media_asr_audio_and_stale_auth.py`.

**1b. Why the item failed in under 15 s while the probe saw a 200 s hang (inferred, not reproduced).** They are two runs of two code paths. The item had `duration_ms` 0, so the import-time duration probe had already failed (`probe_youtube_duration` swallows every error), and the pipeline's own `extract_info` in `download_audio` raised inside the same minute, which the pipeline turns into `audio_unavailable` without a trace. The probe in the worker, minutes later, resolved the metadata in 1.1 s (duration 403), so that failure was transient and its cause is unknown. `download_audio` and `_audio_source` now log the exception class and a short sentence, so the next one names itself. The hang above is what an item that gets past the metadata step meets.

**2. TED-Ed `provider_auth` (a stale display, not a stored or replayed error).** Nothing replays a provider error: `provider_auth` is raised only from a live 401/403 in `GroqTranslationProvider`, the in-process cache holds successes only, and the item stores no provider or model choice. `retry_translation` queued the job without resetting `translation`, `translation_reason` or `translation_retry_after`, so the item kept showing the previous run's `provider_auth` (a Groq 403 "Access denied" at 06:57 while the machine VPN was on) as the answer to the retry, and the trial read it 0.5 s after the request. The retry did run and succeeded: `processing-spend.json` booked a served call at 12:16:44 and `media_translation_cache` gained 48 rows for that asset at 12:16 (the item reads `ready`, 48/48). Fix: queueing the retry clears the outcome, the reason and the retry-after (the counts of lines already done stay); the job writes the real result. A 401/403 was also the one refusal that left no trace in the log: it now logs its status and the provider's sentence (no credential). Not found: any per-item provider, model or key.

**3. Not done / open.** A real 403 (an IP block) still ends the round as `provider_auth` and is terminal for that run, by design (D-211). Why the import-time probe failed for `D_IcGTgWoZY` is unknown; the new log line will say. ASR quality and hallucination screening on ZH remain untested until an item is re-run on a deployed fix.

**4. Review follow-ups (P2, addressed).** Each Range piece must start where the last ended (`Content-Range` first byte), the advertised total must agree across pieces and never be smaller than the bytes received, a 200 or a piece without `Content-Range` after the first fails, and the finished size must equal the advertised total; a 416 after bytes were written ends an exact-multiple file of unknown total. Any mismatch is an `UnsafeMediaFetch` and never a successful, corrupt or truncated file. The partial file is removed on any exception. The wall-clock test now asserts the "took too long" path. The audio failure logs carry the exception class and a message with every URL removed (`scrubbed_error`): a signed googlevideo URL is a short-lived capability and stays out of logs. Not changed: the clock is checked between 64 KiB reads and pieces, so one blocking read can overshoot by the per-socket timeout (12 s).

## D-218 - Media translation respects an output-tokens-per-minute allowance; a YouTube id may start with "-"; a caption reject names its check; media AI spend is rated per model; only Simplified Chinese captions are accepted (2026-10-15)

Status: ACCEPTED (owner confirmed 2026-10-16; independent review APPROVE on f4c4586b, no open P0/P1; merged as #243 once CI was green). Follow-ups in #244. No schema or migration change, no new provider, items stay held.

Evidence: the 2026-10-15 Orena Phase 2 sitting 2 on :8021 (`VIDEO_SOURCE_TRIAL_2026-10-15.md` "Sitting 2", `GROQ_MODEL_SWITCH_2026-10-15.md`), `GROQ_TRANSLATION_MODEL=qwen/qwen3.8-27b`.

**1. Root cause, OTPM stall (read from the 429 text).** Groq admits a request only while the output tokens used in the last minute plus the `max_completion_tokens` it reserves fit the model's OTPM limit (1000 for this model; the 8000 total tokens a minute is a different allowance). After the first 24 lines every continuation round was refused with `(OTPM): Limit 1000, Used 867-922, Requested 640`, and the code retried on the provider's `retry-after` (about 30 s, shorter than a minute), so each retry met a window still full. Fix: (a) the provider keeps a shared per-model window of what it reserved in the last 60 s (`OutputTokenWindow`), learns the limit from the refusal's own sentence (or from `GROQ_TRANSLATION_OUTPUT_TOKENS_PER_MINUTE` when an operator sets it; no model name is special-cased) and the provider's `Used` count; (b) batches are sized so one request reserves at most half the limit (`batch_output_ceiling`, used by `build_translation_batches(max_output_tokens=)` and by the provider's own split), so a batch is one rate-limit decision and arrives whole or not at all; (c) a request that does not fit is not sent: within a caller's pacing allowance (`translation_pacing`: the first run's existing 150 s wait budget, and 150 s per continuation, `CONTINUATION_PACING_SECONDS`) the provider sleeps for the window, otherwise it raises `rate_limited` carrying the exact wait; (d) after a real OTPM refusal nothing is sent for `max(retry-after, 62 s)`; (e) lines a batch finished before it stopped are kept (`_salvaged`) and not asked for twice. A round that sends nothing, or is refused, books nothing (D-216 unchanged); the D-211 bounds (attempts, 1800 s, 900 s per wait, 5 rounds) and the spend caps are unchanged. Test: `tests/test_media_otpm_pacing.py` runs a fake provider that enforces OTPM=1000 over a virtual clock; a 76-line item completes with at most one refusal, also when a refusal itself fills the window.

**2. Root cause, ids starting with "-".** `validate_entry` required `provider_media_id` to start with a letter or digit, but YouTube ids are `[A-Za-z0-9_-]{11}` and may start with `-` or `_`; the check ran after the Supadata request. Now a `youtube` row may start with `-`/`_` (other providers keep the stricter shape), and the caption client validates the video id, the library identity and the URL it will build before it reserves or sends a request (`ProviderUrlMalformed`). yt-dlp is driven as a library with the full `https://www.youtube.com/watch?v=...` URL, never the bare id, so a leading dash is never an option; a test pins it. Not changed: the parked PostgreSQL proposal `migrations/proposed/20261001_0024_media_entries.py` and its inert mirror carry the old pattern in `ck_media_entries_provider_ids`; it must allow a leading `-`/`_` for `provider = 'youtube'` before that migration is ever promoted.

**3. `captions_unusable` names its check.** The failing quality check and its own count are stored (`processing.detail`, and `caption_fallback_detail` on the ASR route), for example `segments: 242 lines; 242 captions, 242 lines`, and the admin Media detail shows them after the translated reason. Ids and numbers only, so no new copy.

**4. Ledger rate.** The media AI ledger rates a model with a published rate at it (`policies.MEDIA_AI_MODEL_RATES`), then the pricing catalogue, then the flat `media.ai_usd_per_million_tokens`; a zero rate never reaches the ledger. `qwen/qwen3.8-27b`: input $0.80, output $4.00 per million tokens, from the Groq model page https://console.groq.com/docs/model/qwen/qwen3.8-27b read 2026-10-15 (a Preview model; https://groq.com/pricing does not list it). The pre-call cap check still uses the flat estimate. Owner question: `ai/pricing.py` still carries `qwen/qwen3.8-27b` at 0 as an owner-confirmed free-plan model (D-195 amendment), which the AI cost report and `is_free_model` read; if the Groq account is billed, that entry should change too.

**5. OWNER DECISION (2026-10-15): only Simplified Chinese is accepted.** "Skip Traditional content; for now only Simplified learning content is accepted." Replaces the open question this entry first carried about captions tagged `zh-Hant` (D-208). When the admin pipeline takes a Chinese caption track, a track tagged `zh-Hant`, `zh-TW`, `zh-HK` or `zh-MO` is refused with the stable reason `zh_traditional_not_accepted` (setting `media.zh_scripts_accepted`: `simplified`, the default, or `any`; Admin Policies, EN/VI/ZH copy). YouTube's own tracks: the Traditional tags are dropped from the candidates before anything is fetched, and a Simplified or untagged track is preferred when both exist. Supadata: only the response reveals the language, so the one request is counted, the answer is recorded as the rejection (remembered, so the import and the pipeline step do not pay twice) and nothing is translated; in `youtube_then_supadata_native` a Traditional-only YouTube video does not go on to a paid request. The item stops in either transcript policy: no audio, no recognition, no translation, no spend. The reason is worded in the admin in EN/VI/ZH (`impErr_zh_traditional_not_accepted`). Speech-recognition output keeps being converted to Simplified (D-208). Limit: the guard reads the provider's language tag, not the characters, so a Traditional text under a plain `zh` tag is taken.


## D-219 - A per-provider free-tier flag: free-plan cost is stamped at record time and shown apart from real spend (2026-10-16)

Status: ACCEPTED (owner confirmed 2026-10-16; independent review REQUEST CHANGES on b9ea535a, re-review APPROVE on ed5a69e5, design re-check APPROVE on ed5a69e5, no open P0/P1; merged as #245 once CI was green). Follow-ups in #246. No schema or migration change, no new provider, no change to any spend cap.

Owner decision, 2026-10-16: "there should be a flag in the admin UI; if the free-tier flag is on, show that part of the cost in another colour or word it as free. If we later move to a paid plan, the real cost can be counted from then on."

**1. The flag.** Three ordinary admin policies in the `spend` group of `writing_coach/policies.py`: `cost.free_tier.groq` (default on), `cost.free_tier.supadata` (on), `cost.free_tier.gemini` (off). They are edited on the existing "Policies & limits" page (no new screen, EN/VI/ZH copy in `copy-policies.js`), take effect within the policy cache window, and are audited like every policy. A provider with no flag is not on a free plan.

**2. Stamping.** Every cost event records the provider and the flag in force at that moment: the media spend ledger event gains `provider` and `free_tier`; the `ai.operation` telemetry payload gains `free_tier` (an allow-listed boolean, `sanitize_telemetry`). A later toggle never rewrites an event. An event written before this change has no stamp and is reported as **unknown tier** — in neither real spend nor free-tier value — and still counts toward every cap. `schema_version` of the ledger file stays 1 (an added field is ignored by an older reader).

**3. `ai_cost_records` (per-account).** The table has no free-form column, and a column is a schema change, which is a human gate; none was added. Its tier is **derived**, not stamped: the admin per-account read cuts the window at each instant a free-tier flag changed (read from the `platform.policies.update` audit rows, `cost_tier.FlagTimeline`) and classifies each piece by the flag's state at its start. A flag pinned by the environment has no history and is its present value. Limits: the derivation is only as exact as the audit log; a record is classified by its provider, not by a stamp; and it needs the audit rows to be retained (they are not pruned today; only `agent.turn` rows are). Fail-safe rule (review of #245): the split has a third bucket, `usd_unknown`. It detects a MISSING flag history only, not a hole inside a non-empty history: a flag that is ON by an administrator's stored value but for which no audit row exists at all (a direct database edit, a lost row) is `unknown` for the whole window, never silently free. A provider that has some audit rows is trusted as complete, so a single lost row between retained ones is not detected; a flag that is OFF, or an untouched default, needs no history. More than 200 change points in a window leaves its last piece `unknown`. The whole audit history of the three flags is read (a handful of rows), so a change before the window is not mistaken for a missing row. A flag takes effect only after the policy cache window (5 s) and per process, while the audit row carries the save time, so records inside that gap are classified by the new value although the stamped stores stamped them under the old one: the derived split is approximate by that window. If the owner wants a stamped column, that is a migration for independent architecture review (open question).

**4. Pricing.** One source: `ai/pricing.py`. `TokenPricing` gains `list_input_per_million`/`list_output_per_million` (the public price of a model the account gets free); `qwen/qwen3.8-27b` carries D-218's $0.80/$4.00 there while its billed rate stays 0 (so `is_free_model`, routing tiers and prompt-logging rules are unchanged). `estimate_token_cost` and the media ledger now compute with the list rate; `policies.MEDIA_AI_MODEL_RATES` is removed and `policies.media_ai_model_rate` delegates to the catalogue (`list_rate`). A free-plan model with no published price (`llama-3.1-8b-instant`, OpenRouter `:free`) stays at 0 and has no list rate. Catalogue version `2026-10-16.v8`. An amount is therefore always the public price, free or not.

**5. Caps do not move.** Every cap (batch, daily, agent, per-capability) sums the computed amount regardless of the tier, so a free plan never turns a cap off and quotas stay protected. The flag only chooses the bucket an amount is reported in. Consequence the owner should expect (review of #245): `estimate_token_cost` now prices `qwen/qwen3.8-27b` at its list price ($0.80/$4.00) where it was 0, so every budget that sums `ai.operation` cost (the agent daily cap, the per-capability caps read through `ai_spend_since`) now counts qwen calls, and a feature routed to qwen reaches its cap earlier than before. That is the intent of "caps keep protecting the quota", but it is a behaviour change outside the media ledger. The tier stamp on `ai.operation` follows the provider's flag for a provider that has one (qwen is real spend once `cost.free_tier.groq` is off); `is_free_model` decides only for a provider without a flag. The media ledger keeps at most 20,000 events, so a 30- or 90-day figure can undercount once it rolls over.

**6. Display and totals.** Admin AI cost page (and the Token usage metric): "Real spend" sums only events stamped `free_tier=false`; "Free-tier value" is the list-price value of free-plan events and is never added to real spend; unstamped amounts are a third phrase. Free rows use the existing muted pill "Free tier" and the secondary phrase "Free tier · ~$0.12 at list price"; a free-only row reads "Free". The media ledger is shown as a "Media processing" block on the same page (`GET /api/admin/ai/costs` gains `media`). Supadata is paid in credits, so its rows show request counts, not dollars. The pinned admin design draws no cost page (D-128); recorded in `UI_BACKEND_GAPS.md`.

**7. Open questions, with the review's view (independent review of #245, Claude Opus 5.5).** (a) Stamped column vs derived: derived is acceptable now; it needs no migration and the audit rows are not pruned. Move to a stamped column only when per-account figures become billing evidence, or when the account/multi-device architecture adds a record migration anyway. No column in this PR. (b) `media.asr_usd_per_hour` (a policy) vs the audio catalogue: unify later in a separate small change; both are $0.04 per hour today, and the catalogue should be the default with the policy an override, with a test that the defaults are equal. (c) A list price for OpenRouter `:free` and zero-rate models: no. A list price must be a published price; they stay at 0 with no list rate (`list_rate` returns None) until a specific model gets a published price, as qwen did.

**8. Display (design review of #245).** The free-tier value uses the existing `ok` (green) tone, as the metric and as the "Free tier" pill, so it differs from the muted per-call pill; no new token. In a row the amount on the right is real spend only; free value is its own line "[Free tier] ~$X at list price", and an unstamped amount is its own line "[Before tier recording] $X", never shown as real spend. Every amount on the cost page has one precision (4 decimals). The metrics strip is two by two below 720 px. One Chinese term, 免费额度, on both pages.

## D-220 - Past usage with no tier stamp is placed by the flag's history: a paid provider's counts as real spend (2026-10-16)

Status: ACCEPTED (owner confirmed 2026-10-17; independent review APPROVE on 5a0375b3, no open P0/P1; merged as #248 once CI was green). No schema or migration change, no new provider, no change to any spend cap.

Owner report, 2026-10-16: on the :8021 sandbox the admin AI cost values were all 0 and the testing spend on Gemini and Azure (paid accounts) was not counted.

**Root cause (reproduced read-only on :8021).** D-219 §2 reported every event with no `free_tier` stamp (everything before 2026-10-16) as "unknown tier", in neither real spend nor free-tier value. In the sandbox 1,290 of the 1,301 `ai.operation` rows were unstamped, so "Real spend" read $0.00 although $1.25 of unstamped spend had been computed: Gemini $0.81, Groq $0.32, Azure Speech $0.11. The media ledger had the same shape (246 unstamped Groq events, $0.68, and 18 Supadata requests). Azure was never missing: its pronunciation and word-TTS calls are recorded by the same telemetry (37 and 15 events) and priced from `ai/pricing.py`; they were hidden by the same rule. The Policies and cost pages were reachable but buried (Policies as the last row of the Operations page, nothing on the AI or cost page).

**Rule.** An unstamped event is placed by the flag's history (`cost_tier.FlagTimeline.tier_at`, §3 of D-219), at the event's own time: a provider whose flag was OFF and never ON, or that has no flag (Azure Speech, OpenRouter), is **real**; a flag that was ON and never changed (the default, no stored value) is **free**; a flag that was ON by a stored administrator value with no audit row to explain it, an event that names no provider, and more than 200 change points stay **unknown**. A stamp always wins; a stamped event is never reclassified. Applied to both stores: `ai.operation` telemetry (the `/api/admin/ai/costs` rows, by piece between flag changes: `ai_unstamped_cost_rows` + `cost_tier.reclassify_unstamped`) and the media ledger (`SpendLedger.totals(tier_at=...)`). `ai_cost_records` per-account was already derived this way. `usd` is untouched, so every cap is unchanged; only the bucket an amount is reported in moves. The ledger file and `audit_logs` are not rewritten.

**Display.** The AI page and the AI cost page each offer "Policies & limits" in the page header (the existing page-head action pattern the Users page uses for Plans and Feedback), and the Operations page lists it first in its nav card (#247), so it has no header action there. The pinned admin design draws no policies or cost page (D-128), so this is the kit's own pattern, recorded in `UI_BACKEND_GAPS.md`.

**Limits.** The tier of a past event is a derivation, not evidence: if the owner was on a free Gemini plan during testing but the flag was never turned on, the past spend is reported as real. The owner's statement (Gemini and Azure are paid accounts) is the basis. Azure is priced in two places, both list-price estimates to reconcile against the Azure bill: pronunciation assessment at $1.32 per audio hour in `ai/pricing.py` (source: a Microsoft Learn Q&A page, not the price sheet), and word TTS at $16 per million characters in `writing_coach/word_audio_azure.py` (`PER_MILLION_CHARACTERS`). Review P2-1 (open): `_flag_timeline` reads the full policy history, uncached, on every cost-report call, and the unstamped placement can run up to about 201 piece queries; cache or bound it if the page gets polled.


## D-221 - AI cost completeness: every cost event names its environment; thinking tokens and the Gemini and Azure prices are corrected; the reconciliation against the provider console (2026-10-17)

Status: ACCEPTED (owner confirmed 2026-10-17; independent review APPROVE on 4737dbc0, no open P0/P1; merged as #252 once CI was green). No schema or migration change, no new provider or credential, no spend-cap change (the caps now count what is newly priced and recorded, below).

Owner report, 2026-10-17: the Google AI console showed VND 52,216 (about $2.0) against $0.92 real spend on the :8021 cost page (Gemini $0.81, Azure about $0.11). Owner decision: option (a), fix the in-app instrumentation, no new credentials. Option (b), Cloud Billing export, is a separate owner decision and is not in this entry.

**Measured on :8021, read-only (SELECT only on `audit_logs` `ai.operation` and `ai_cost_records`).** Gemini $0.8090 (agent_turn_fast $0.3033, agent_voice $0.2754, learner_dictionary $0.1415, learner_translation $0.0413, writing_evaluator $0.0221, reading_generator $0.0216, text_discussion $0.0038) plus Azure Speech $0.1143 (pronunciation $0.1137, word TTS $0.0006) = $0.9232. The other local databases hold almost nothing: `orena-foundation-postgres` two Gemini rows at $0 (2026-09-23), `orena-speaking-postgres` none, `orena-orchestrator-postgres` has no `audit_logs` table. :8000 and :8010 are human-gated and were not read.

**1. The gap is mostly environments (not measurable from here).** `$2.0 - $0.81 = about $1.19` of the console total is spend that :8021 did not record. The same Gemini key is used by :8000, :8010, :8011, other sandboxes, other lanes and scripts (`scripts/agent_live/run.py`, `scripts/voice_spike/server.py` read `GEMINI_API_KEY` and write to no ledger at all). Each web environment records into its own database and its own media ledger. Fix: every cost event carries an `environment` label (`writing_coach/cost_env.py`: `ORENA_ENV_LABEL`, else `ORENA_ENVIRONMENT_LABEL`, else the host and port of `PUBLIC_BASE_URL`, else `APP_ENV`), an allow-listed field of `ai.operation` (`sanitize_telemetry`) stamped at every writer (`_persist_operation_telemetry` and the control plane's probe rows) and on every media ledger event. The Admin cost page gains a block "Where this spend was made" (this server marked) and a gap row saying the provider's own total includes the other environments. `ai_cost_records` has no free column, so the per-account table cannot carry the tag; recorded as a gap (a column is a human gate). Events written before this change read as "Before the environment tag". Operational consequence: to make the console reconcile, set `ORENA_ENV_LABEL` on :8000 and :8010 (human-gated, not done here) and read each cost page; a script that spends the key records nowhere and can only be bounded by not sharing the key.

**2. Gemini call paths, each checked.** (a) `ai/providers.py` non-streaming `generate_json` and `generate_json_once`, reached by every `generate_structured` caller (dictionary, translation, writing evaluator, reading generator, text discussion, media interaction, reading summary, router): recorded with the reported token counts. (b) `stream_chat` for the agent turn (`stream_agent_turn`, `agent_turn_fast`): recorded per round, including an abandoned or abnormally finished round. (c) Gemini Live (`ai/live_voice.py` mints a one-use token; the browser opens the socket directly, `agent/voice_session.py`): recorded, but as wall-clock seconds of token life at $2.16 an hour, not as real tokens. Gemini Live reports `usageMetadata` (audio and text tokens in and out) only to the browser socket, which the server never sees, so it could not be instrumented server-side without a schema or a client report. It is kept as a ceiling (Google's audio-only floor is $0.005 + $0.018 a minute, $1.38 an hour with both sides streaming; the $2.16 ceiling also covers instruction, tool and re-read context tokens) and said so on the cost page. Proposed, not done (needs the Intelligence lane and a human decision on trusting a client figure): the client posts its final `usageMetadata` to `/api/agent/voice/end`. :8021 recorded 11 sessions, 452.3 s, $0.2754 at the ceiling; the audio-only floor for the same seconds is about $0.17. (d) The deprecated Admin selection test (`POST /api/admin/ai/test`) made a real completion with no cost row: now recorded as an operator test (`ai_connection_test`), not an account's spend; :8021 shows no such audit event, so it did not contribute to this gap. (e) Model catalogue discovery (`GET /models`) is free. (f) Embeddings, Gemini TTS and any other Gemini endpoint: none exist in the code. (g) Failed requests that were sent are already recorded as billable attempts.

**3. Thinking tokens.** Google prices Gemini 3.5 Flash-Lite output "including thinking tokens". Through the OpenAI-compatible endpoint the stored `usage` of every non-streaming Gemini row on :8021 has `total_tokens == prompt_tokens + completion_tokens` (230 rows, difference 0), so the endpoint's `completion_tokens` already counts thinking and the previous cost was not understated by it. Streaming rows stored no `total_tokens`, so that could not be checked for the 272 agent rounds. Defensive fix: `reported_completion_tokens` (`ai/base.py`) counts a total larger than prompt plus completion as thinking at the output rate, at all three adapter sites; it adds nothing when the completion already holds it. No Gemini call was made to test this (fakes only).

**4. Pricing, re-read 2026-10-17.** Source for Gemini: https://ai.google.dev/gemini-api/docs/pricing. `gemini-3.5-flash-lite` $0.30 in / $2.50 out confirmed. `gemini-3.1-flash-lite` was UNPRICED (3 rows on :8021, 213 tokens): now $0.25 in / $1.50 out (audio input $0.50 not modelled; Orena sends text). Gemini 3.8 Live per token: audio in $3.00, audio out $12.00, text in $0.75, text out $4.50 per million (25 audio tokens a second). Azure, from the Azure Retail Prices API (https://prices.azure.com/api/retail/prices, eastus, product Azure Speech): neural TTS "S1 Neural Text To Speech Characters" $15.00 per million (the code had $16.00: corrected, `PER_MILLION_CHARACTERS`); standard real-time speech to text $1.00 an hour plus the "Enhanced Feature Audio" $0.30 an hour is $1.30 for pronunciation assessment, against $1.32 in the catalogue: left at $1.32 because prosody assessment (on for en-US) may count as a second enhanced feature; no evidence either way, reconcile against the Azure invoice. Catalogue version `2026-10-17.v9`. The Azure pricing page (azure.microsoft.com) blanks its dollar amounts; the Retail Prices API is the source.

**5. Azure paths.** Pronunciation assessment (`speech_pronunciation.py`) and word TTS (`word_audio_azure.py`) are recorded; `AzureSpeechControlProvider.discover_models_live` calls `issueToken`, which is not billed. No Azure speech-to-text or other TTS path exists. Nothing was missing.

**6. Estimates vs reported usage.** `cost_state = 'estimated'` means priced from the catalogue; for every token call the counts are the provider's own. Not provider-reported: voice (wall-clock ceiling, above), Azure TTS (billed characters computed by Orena) and Azure pronunciation (the decoded take's seconds). Cached input tokens are billed at the full input rate (the provider bills them less), which overstates slightly.

**7. Reconciliation (:8021 against the console).** Console about $2.0; recorded $0.9232 (46%); not recorded in :8021 about $1.08. Candidates, none measurable from here: other environments sharing the key (:8000, :8010 gated; :8011, :8013, :8031 and other lanes' sandboxes not read), scripts that spend the key with no ledger, the Gemini Live spend above the ceiling or below it (range $0.17 to above $0.28 for :8021 alone), tax or conversion on the VND invoice (unverified), and the console's billing-day boundary. The per-environment tag turns this into a sum the owner can read once the other environments carry a label.

**8. Caps.** The caps are unchanged. They now count `gemini-3.1-flash-lite` calls (previously unpriced, so counted as zero by the daily ledger), thinking tokens the endpoint reports only in its total, and the Admin selection test as an operator test; word TTS is counted at $15 rather than $16 per million characters, so the word-TTS cap is reached slightly later. Nothing is removed from a cap.

**9. Open.** The environment label for :8000 and :8010 (human-gated); whether to have the client report Gemini Live `usageMetadata`; Cloud Billing export (owner option (b)); Azure prosody as a second enhanced feature.

## D-222 - Orena Memory: the limits of server-held memory (G1/G2), the test lane's pack clearance, the M5 challenger keys, and Gemini Live usage as a reconciliation figure (2026-10-17)

Status: ACCEPTED (owner wrote "D-222: ACCEPTED" on PR #265 at rev 4.1 `92224381`, 2026-10-17, after an independent re-review; CI green). Decision 1 records the limits of the owner's G1/G2 approval (rev 3 architecture review F12(a)); the owner agreed to decisions 2-4 in the Intelligence-lane session on 2026-10-17. No schema, migration, provider, credential or runtime change is made by this entry.

**1. Server-held memory, and its limits (G1/G2; rev 3 architecture review F12(a)).** The owner's approval of `learner_memories` (G1) and `orena_session_summaries` (G2) is an exception to the D-104 hold on Orena conversation/history persistence, and it is bounded: session **summaries only, never transcripts**; a summary holds learning-event codes and bounded learning items (`practised`, `focus`, `open_task`), nothing personal; short-term personal context is stored only as continuity items holding a code from a closed list, grounded in the learner's own message words, deletable, with a suppression key so a deleted fact does not return; every write, read and deletion is scoped by account incarnation and fails closed without one. The schema still needs its migration review, PostgreSQL rehearsal and the owner's authorisation (`ORENA_MEMORY.md` §4, §9). M3 also waits for the Agent Contract v9 §10 text on `codex/work`.

**2. Learner-pack clearance in the test lane (G8, partial).** Gemini is cleared for `learning_profile` data in the approved test lane: `AGENT_PROVIDER_DATA_CLASSES=gemini=learning_profile` with `AGENT_LEARNER_PACK=on` there. This clears the M1 learner pack only (A1, PR #263); it is not `full_memory`, and it does not apply to the public runtime (:8000), whose record stays empty until the owner sets it.

**3. M5 challenger keys.** The owner will provide API keys for the challenger chat models named by the UI-lane study on #256 (OpenAI gpt-6-luna, DeepSeek flash; Claude Haiku 5.5 also needs the Anthropic adapter, G6), entered only in the test lane's environment or Admin, never in the repository. M5 runs the capped benchmark (A2) with the same script per candidate. Each key and any paid plan remains a human gate per provider.

**4. Gemini Live `usageMetadata` is a reconciliation figure, never a limit.** The client may report a voice session's final `usageMetadata` to `POST /api/agent/voice/end`. The server records it beside its own wall-clock ceiling, labelled `client_reported`, rejecting (and counting) a report with a negative count or one above the ceiling's token equivalent for the session's server-measured seconds. Spend caps and quotas keep counting the server ceiling, so a client cannot lower what it is charged against a cap. Showing the figure on the cost page is UI-lane work.

## D-223 - AGENT_CONTRACT v9: server-held Orena Memory reaches the agent interface; the contract is edited by reviewed PR to `main` (2026-10-18)

Status: ACCEPTED (owner wrote "D-223: ACCEPTED" on 2026-10-18, after an independent review APPROVE on PR #271 and green CI). Drafted by the UI lane (`claude/agent-contract-v9`) at the request of the Intelligence lane (issue #256), because D-086 forbids the Intelligence lane from editing the contract. No schema, migration, provider, credential or runtime change is made by this entry; the server and UI changes it describes are separate slices (M2, M3, UI memory view) that wait for it.

It implements what `proposals/ORENA_MEMORY.md` rev 4.1 (§6, §8, §9, §10, §13 "Re-review of rev 4") and D-222 require of the contract (rev 3 review F12(b), F12(c)).

1. **`contract_version: 9`.** A client declares `contract_version >= 9` in the request to opt into server-applied notes. A v8 client is unchanged: it sends `coach_notes`, the device stores a note from `memory_update`, the server stores nothing. A note is never both on the device and on the server.
2. **`coach_notes` becomes optional (§3).** A v9 client stops sending it, or sends it empty, once the account holds the notes; the server ignores it for a v9 client whose memory is ON and server-backed.
3. **`memory_update` stays the one rendered event (§4, §5.4).** `stored` is a new field beyond rev 4.1 and D-222, agreed with the Intelligence lane (https://github.com/rallyx-0907/Orena-Coaching-App/pull/271#issuecomment-6247153997). For v9 it reports what the server already applied (`remember_note` / `forget_note` to `learner_memories`, explicit class); for v8 it stays the instruction for the device to store the note. A new field `stored: "server" | "device"` tells the client which (absent reads as `device`); the server sends `server` only when it actually wrote to `learner_memories`, and a `remove` with `stored=server` also deletes a device copy with the same id and the same text (an id alone could collide with an unrelated device note, whose id an earlier v8 reply minted). To have the device copy removed, the server's remove carries the note's `text` exactly as the device holds it; without `text`, or with different text (the match is exact, so text the server normalised or redacted will not match), the device keeps its note and the learner removes it in the memory view.
4. **§10 points at `/api/agent/memory`** (replacing "device memory, account store out of scope"): `GET` (items by kind with reason as code plus parameters, evidence digest, session summaries, switch), `DELETE .../items/{id}`, `POST .../items/{id}/pin` (M3), `DELETE .../sessions/{id}` (M3), `DELETE /api/agent/memory?scope=items|sessions|all`, `PUT .../settings {enabled}`. All behind `AGENT_ENABLED`, the learner's own session, scoped by account and incarnation, mutating routes with the other `/api/agent` POSTs' origin/CSRF handling; every route bumps the memory version. Conversation history stays device memory and transcripts are never stored (D-222 point 1).
5. **Memory OFF** (§10): nothing new is written; nothing from memory goes into a model call, and device coach notes are not sent; stored items stay until deleted; turning back on reuses them with no back-fill; delete and the switch still work while OFF.
6. **Device notes (G4)** (§10): the learner chooses once, per note or for all, "Keep in my account", "Keep on this device" or "Delete"; nothing is uploaded silently; a device note matching a server item (normalised text or slot) is shown once, as the server item, and the client stops sending it; until the learner chooses, device notes are sent as today, except with memory OFF or a provider below `full_memory`.
7. **G8, owner decision of 2026-10-18** (§5.4): below `full_memory`, coach notes are not sent to the model, `forget_note` is not offered and a forget or a replace is refused, and a learner who asks to change or forget a note gets `notes.unavailable` (a support-language segment, no `memory_update`); a new note the learner asks for is still kept (a later owner decision relayed by the Intelligence lane, reversing the earlier block of new notes in its PR #272). Documented, not decided here.
8. **`usage_metadata` on `POST /api/agent/voice/end` (§9)**: optional, client-reported Gemini Live usage, advisory and for reconciliation only, never billing authority (D-222 point 4).
9. **Where the contract is edited (owner decision).** The header said "edit only on `codex/work`". `origin/codex/work` has been dormant since 2026-10-08 (still v6) and v7 (D-164) and v8 (D-169) landed on `main` through reviewed pull requests from the UI lane. The header now says what is done: a reviewed PR to `main` from the UI lane bumps `contract_version` and records the change here; the Intelligence lane receives it by merging `main` forward; it is never edited on the Intelligence lane. This point needs the owner's acceptance like the rest.

Consequences. The contract text is pinned equal to the code constant, so this PR moves both constants to 9 itself: `static/orena/agent/contract.js`, the regenerated `static/orena/copy/surfaces.json` with its pin in `scripts/test_orena_surfaces.mjs`, and `writing_coach/agent/contract.py` (pushed by the Intelligence lane, whose consent is recorded at https://github.com/rallyx-0907/Orena-Coaching-App/pull/271#issuecomment-6247153997). The server change is the constant only: no behaviour changes, and nothing branches on version >= 9 yet. Everything the contract says is "pending" (the `/api/agent/memory` routes, `stored: "server"`, the server ignoring `coach_notes`) follows with slice M2, M3 for its own items. UI work still to do: the memory view, the device-note choice, and rendering `notes.unavailable` and `memory_update` for v9, against the design (`UI_BACKEND_GAPS.md`); and `session.js` must stop sending device notes while memory is OFF or the model is below `full_memory` once the switch exists (it sends them unconditionally today).

## D-224 - A media batch Groq cannot take goes to the platform AI router; media Groq reads the Admin-stored credential (2026-10-18)

Status: ACCEPTED (owner wrote "D-224: ACCEPTED" on 2026-10-18, after an independent review APPROVE on PR #276 and green CI). No schema or migration change: the two capabilities are rows of the existing `platform_settings` key-value store, opt-in like `word_translation` (D-195), and absent until the operator saves one in Admin. No new provider and no new credential kind. The spend caps, batch sizing, pacing budget and correction eligibility are unchanged.

Owner intent, 2026-10-18: a background process must not be blocked by one provider's limits. Groq is on its free tier with output tokens per minute capped and its pay-per-token tier paused; the owner will add OpenAI, DeepSeek and OpenRouter keys in Admin; Gemini (paid, key configured) is a product model.

**Why a decision.** `ARCHITECTURE_INVARIANTS.md` (AI Platform) says "No provider-to-provider fallback or silent paid-provider failover" and "Shared-media translation may select Groq or local Marian once from explicit configuration; a provider failure must stop rather than silently fail over". This entry is a narrow, explicit exception to those two lines for the media pipeline: after Groq refuses, the pipeline asks one other configured provider. The router's own `backup_provider` rung (a second provider inside one router call) would be a third engine and is NOT part of this exception: it is refused for these two capabilities (point 1). If a later decision admits it, it becomes part of the exception and needs a per-rung spend gate first. The entry also moves media toward the same invariants' other lines: media translation, correction and Groq credentials reach the control plane (per-capability provider and model chosen in Admin, stored encrypted credentials, one cost and telemetry path). The invariant text is NOT edited by the implementing PR; once the owner accepts, a follow-up docs PR amends the two lines above to name this exception.

**1. Capabilities.** `media_translation` and `media_transcript_correction` (`ai/capabilities.py`), structured text, configurable, opt-in (no row is needed to activate the runtime; `AI_RUNTIME_MODE` is not consulted: the router call selects the capability configuration explicitly). Default input class `learner_text`: a learner's private import is learner content (D-104), so a free tier and a prompt-logging provider (OpenRouter) are refused for them. Note that Groq itself, first in line for the same imports and on a free tier, is not routed through that check (pre-existing); the rule covers the router path only. **No backup provider** (`NO_BACKUP_CAPABILITIES`, refused at save time and ignored if stored): the media spend check is made at the price of the one (provider, model) the pipeline knows, and the router exposes neither a per-rung gate nor the usage of a billed rung that then failed, so a dearer backup rung could answer outside the media cap and its failed attempts could not be booked in the media ledger. A primary rung whose answer was billed and then judged invalid is likewise visible only in `ai_cost_records`, not in the media ledger (one attempt, no retry). Admin copy in EN, VI and ZH.

**2. When a batch is sent to the router.** Groq stays first. On Groq's own refusal, for THAT batch only: `rate_limited` with a named wait longer than the per-wait cap (60 s translation, 90 s correction) or than the pacing allowance has left; a daily quota (the same, its wait is hours); `request_too_large` after the batch can no longer shrink; `provider_error` (a 5xx); or Groq not configured. A short rate limit is waited out as before. `provider_auth` and `provider_timeout` are not capacity refusals and do not fall back. Correction also falls back when the one retry after a rate limit has been spent; translation falls back only on the long-wait rule (the translation loop retries by rounds). There is no automatic return: the next batch asks Groq again.

**3. What stays as D-218 and PR #261 guarantee.** The spend check runs before every router call (the fallback included), at the price of the configured router model (`ledger.check`), on top of Groq's own check before its attempt; the router answer is validated by the same checks as Groq's (`parse_translation_rows`, `parse_correction_rows`) and a correction by the same per-cue rules (`reject_cue_edit`, EN and ZH); usage is booked per call to the media ledger with the provider that answered, its `free_tier` stamp and its environment tag (D-219, D-221); an item whose correction did not finish stays held. The pipeline records which provider and model answered translation (`processing.translation_served`) and correction (`processing.transcript_corrections[].provider/model`), for item A12 and the cost page.

**4. When the fallback fails or is capped.** Groq's own refusal is raised unchanged, so its named wait still schedules the continuation (D-214). When the media spend cap refuses the router call: if Groq's refusal named a wait, that refusal stays the reason (the continuation still schedules) and the cap is recorded beside it (`processing.translation_fallback_blocked`, `processing.transcript_correction_fallback_blocked` = `spend_cap`); `spend_cap` becomes the reason only when Groq's refusal was terminal too. With no router capability configured, or its provider uncredentialed, the pipeline is Groq alone: today's behaviour exactly.

**5. Configuration.** `MEDIA_TRANSLATION_PROVIDER` accepts `groq` (Groq first, router fallback when configured), `ai` (router only, no Groq key needed) and `local`; an empty value keeps today's resolution. The router is used only inside the import pipeline's spend scope. In `ai` mode an on-demand call outside that scope (curated Listening translation) is refused (`not_configured`): neither capability has a daily cap policy, so an uncapped paid call is not allowed. A daily cap policy per capability (the `word_translation` pattern) would lift this and is a follow-up if the owner wants router translation on that path.

**6. Admin-stored Groq credential for media.** Media translation, correction and ASR read the key saved in Admin first, then `GROQ_API_KEY`, the order `ai/providers.py` uses; a stored credential with no key means the environment's. The lookup is cached for 30 seconds, so a key saved, rotated or deleted in Admin applies within that time with no restart, and a deleted key falls back to `GROQ_API_KEY`, never to the key the process started with. At start the store is read strictly: if it cannot be read and the environment has no key, the start fails loudly instead of choosing another engine for the life of the process. A later transient failure is logged (error class only) and the environment key applies. A process that started with no Groq key at all has no ASR provider object, so a first Groq key saved afterwards needs one restart for ASR (translation and correction see it at once). The key is never logged or stored by this layer.

**7. Two ledgers, one spend.** A router call is written to `ai_cost_records` (and telemetry) by the router and booked to the media spend ledger by the pipeline, so the media caps count it. They are two views of the same spend and must never be summed: the cost report keeps `totals` (`ai_cost_records`) and `media` (the media ledger) apart, pinned by a test.

**8. Out of scope.** ASR fallback (a later PR; ASR is audio, not structured text, and the router has no configurable speech capability). Learner quota (unchanged). Correction eligibility (unchanged: Admin shared imports only).

**Review.** Independent review of PR #276 at `dd5cee8e`: reviewer is an independent review subagent of the UI-lane coordinator acting as Delegated Architecture Reviewer (AGENTS.md section 1); outcome APPROVE WITH CHANGES, https://github.com/rallyx-0907/Orena-Coaching-App/pull/276#issuecomment-6247715149. Two P1 (the backup rung escaping the spend check; no cap in `ai` mode on the on-demand path) and eight P2 were found and are addressed in this entry and the following commit. The implementer did not review its own work. This review is not product approval.

**Open questions for the owner, with the reviewer's recommendations (recommendations only; the owner decides).**
1. `learner_text` blocks OpenRouter and free models for these capabilities. Recommendation: accept; keep `learner_text`, since translation serves personal imports. Splitting a `published_content` capability for Admin shared imports needs two keys per path; only if free capacity is needed for shared imports.
2. Fall back on `provider_auth` and `provider_timeout`? Recommendation: no. A revoked key should surface to the owner; a timeout after send may already be billed, so a second paid call risks double spend.
3. Amend the two invariant lines? Recommendation: yes, after acceptance, in a docs PR, wording the exception as above.
4. A separate cap per provider? Recommendation: no for now; one shared media cap is the safer default. A per-provider daily cap can come with a daily cap policy for the capabilities.
5. The router's backup rung: admit at the dearest rung, or refuse a backup. Recommendation (applied here): refuse a backup for these capabilities until a per-rung gate exists.
6. The on-demand path in `ai` mode: refuse outside a spend scope, or give each capability a daily cap policy. Recommendation (applied here): refuse; no uncapped paid path.

## D-225 - Agent Contract v9: unplaced device notes in server mode (resolves D-223 points 2/6) (2026-10-18)

Status: ACCEPTED (owner wrote "D-225: ACCEPTED" on 2026-10-18, after an independent review APPROVE on PR #279 and green CI). D-223 stays as accepted; this entry is appended, not an edit of it. The contract text in the same PR follows it and `contract_version` stays 9: no wire change.

Decision. D-223 is inconsistent with itself: point 2 says the server ignores `coach_notes` for a v9 client whose memory is ON and server-backed, point 6 (G4) says device notes the learner has not placed are sent as today until the learner chooses. This entry resolves the conflict in favour of point 6: point 2's "ignores" holds only for notes the learner has placed. `AGENT_CONTRACT.md` §3 (not §5.4) and D-223 point 2 carried the "ignores"; §3 is corrected.

It adopts the server-mode merge rules agreed between the UI and Intelligence lanes (orena-intelligence-82; PR #278, slice M2.3), which go beyond point 6 and need the owner's confirmation: the account's notes first, newest first; unplaced device notes fill the remaining room, highest weight first; the server drops a device note that matches a server item by `notes.same_note` or slot (or by id: the server item wins); the limits are the existing 20 notes and 2048 bytes; nothing is stored on the server and nothing is uploaded silently; a forget or replace of a device note is answered with `memory_update` and `stored: "device"` (replace is a device upsert under the same id, forget a device remove carrying the id only), refused below `full_memory`, until the memory view exists. The one case where the server proposes removing a device note the learner did not name: the learner explicitly asks to keep exactly what an unplaced device note says, and one reply carries a `stored: "server"` upsert plus a `stored: "device"` remove of the device copy by id (nothing is uploaded silently; usual gates; never below `full_memory`; The device remove is emitted only after the server upsert has been committed; if the server write fails, no remove is sent and the device keeps its note.); implemented by the Intelligence lane's PR #281. A v8 client is unchanged (D-223 point 1).

Facts stated in the contract: the per-note limit in a request is 400 characters on the server schema and in the client, and a device note is sent as is; `MAX_NOTE_CHARS` = 200 limits only a note the model writes. The server's byte measure is authoritative (UTF-8 length of the compact JSON of the validated notes, null fields included, about 30 bytes more per note than the client's `JSON.stringify`), so the client can under-count and a near-limit list can be refused. UI follow-up: the client must measure in the server's shape or keep a safety margin; this is a live defect today, v8 included. Also, the client already sends `coach_notes` unconditionally (`session.js`) and must still gate on memory OFF and below `full_memory`. The GET listing's evidence digest is marked pending until the memory view is designed. No runtime may enable M2 (`AGENT_MEMORY_HMAC_KEYS`) until M2.3 lands. D-224 is reserved by PR #276.

## D-226 - Orena Memory has one switch in Settings, default ON, and no list, view or delete UI (2026-10-18)

Status: ACCEPTED (owner wrote "D-226: ACCEPTED" on 2026-10-18, after an independent review APPROVE on PR #290 and green CI; the decision itself was relayed by the owner's delegate, whose delegation the owner confirmed).

Decision.
1. Orena Memory has exactly one learner control: a single switch, "Memory - Let Orena use your content to personalise" (Vietnamese "Trí nhớ", Chinese "记忆"). It is account-wide (the server keeps one state per account, not per language), default ON, read with `GET /api/agent/memory?language=<active learning language>` and written with one `PUT /api/agent/memory/settings {"enabled": bool}`.
2. There is no notes list and no per-note view or delete UI. A learner who wants their memory deleted asks by email to orena.legal@chillpickle.org.
3. Placement. The design draws no such switch, so it is placed as an existing toggle row: Settings, Privacy tab, directly under "Microphone access", in the same `listRow` + `s-settings-toggle` pattern (the design's `tog(...)` rows, `Orena.dc.html` line 3272, Privacy). No new visual (CLAUDE.md rules 4 and 7); recorded in `UI_BACKEND_GAPS.md`.
4. Failure behaviour. A server without memory (503 `memory_unavailable`) hides the row entirely. A failed save (503, 429, network) puts the switch back and shows Settings' existing save-failed line. When the switch is OFF the client sends no device `coach_notes`; this is hygiene only, the server already withholds notes and refuses to remember.
5. `screens/orena/memory-sheet.js` (the coach-notes list) stays unreferenced by any caller; deleting it is left to a follow-up decision.

## D-227 - Word tap: zero-cost choice among a word's stored senses (amends D-195 clause 1) (2026-10-18)

**Status: ACCEPTED** (2026-10-18, accepted by Hermes for the owner. The owner delegated D-entry acceptance to Hermes in the UI-lane session the same day: "mấy cái này có thể để hermes làm thay tôi không nhất thiết là cần tôi 'D-227: ACCEPTED'"). Implemented by PR #293 (refs #194); independent review APPROVE. No schema, no migration, no UI change, no contract change.

Owner decision of 2026-10-18 (via the delegate, delegation confirmed by the owner): a word tap keeps a neutral basic meaning; the contextual sense is picked only for an ambiguous polysemous word, at zero cost first.

1. A tap picks among the word's already-stored senses (the published vocabulary senses, the English dictionary senses, the CC-CEDICT entries) using the local tagger's part of speech for the word in its sentence and, for Chinese, the reading the tagger gave it there. A sense of the tagged class wins; among equals, one with a meaning in the support language wins.
2. No tag, a tie, or no match keeps the neutral first sense.
3. The sentence stays in-process and never reaches AI. The `word_translation` seam and its word-only input (D-195 clause 1) are unchanged, and it is still reached only when every deterministic layer missed.
4. No word-keyed cache holds the choice: the lookup is not cached by the word, so two sentences give two senses.
5. NOT included: the cheapest-model fallback with the sentence. It would change the capability contract and the cache key and needs its own decision.

## D-228 - Word tap: a cheap model chooses among a word's stored senses, only on a tie, only for shared published content (amends D-227 clause 3 and D-195 clause 1) (2026-10-18)

**Status: ACCEPTED** (2026-10-18, accepted by Hermes for the owner. D-entry acceptance was delegated by the owner in the UI-lane session the same day. Independent review APPROVE at 5bf4c929; CI green. Hermes also accepted that sentences from shared published content may reach free-tier providers that log prompts; content is public and holds no learner data. Private content stays local pending the owner. Enabling the capability in Admin waits for the owner.) No schema, no migration, no UI change. Implemented by PR #300.

**What the owner said, and what he did not.** Owner decision of 2026-10-18 (to the UI lane): "ưu tiên những model có đánh dấu free tier, nếu không tất cả đều lỗi hay không khả dụng mới dùng model tính phí rẻ nhất". That covers **free tier first, the cheapest paid last**. It does not cover sending a learner's own text to any AI. The coordinator's conservative decision, pending the owner's explicit OK: a sentence from **private** content (unverified or missing `content_id`, a personal import, the learner's own writing, anything that is learner text under D-104 / D-195 / D-224) is **not sent to any AI, free or paid**; the tap keeps the neutral sense and stays fully local. Only **verified shared published content** reaches the model. Whether a private sentence may go to a paid model that does not log prompts is an open question for the owner; until he answers, the answer is no.

**Amendments.** D-227 clause 3 ("the sentence stays in-process and never reaches AI") no longer holds for the sentence of verified shared published content, and for it only; for private content it holds as before. D-195 clause 1 (the tap sends the word only) is unchanged for `word_translation`; the sentence travels only through the new capability below.

1. **When.** Only when the zero-cost rules of D-227 tie: two or more stored senses (published vocabulary senses with a meaning in the support language, or the English dictionary's definitions when no localized meaning is in hand) that the tagger's class cannot tell apart. A decided sense, a single sense, no usable sentence, a disabled capability, or private content asks nobody; the tap shows the neutral first sense. The disabled check comes first, so a disabled capability reads no article and makes no worker hop.
2. **A new capability, `word_sense_choice`, not a change to `word_translation`.** `word_translation` keeps its word-only input and its `public_reference` class. The new contract takes the word, its sentence (at most 300 characters, cut from the passage around the tapped word; if the word stands in several different sentences of the passage the tapped one cannot be told, and the tap keeps the neutral sense), the tied senses (each sent cut to 160 characters; the index still maps to the stored sense), the languages and a cache scope; it answers `{"choice": N}`, an integer index into the senses given. Nothing but an index is read from the model, so it cannot invent a meaning. A non-integer, out-of-range or extra-field answer is invalid and the next model is asked; if none answers, the neutral sense stays. No second ask of the same model (`retry_invalid` = 0). Opt-in like `word_translation`: ships disabled; the operator saves and enables a row in Admin, and that row is only the switch.
3. **The pool is always the caller's.** `word_sense_choice` runs only on a caller-built pool and fails closed (`AICapabilityUnsupported`) when none, or an empty one, is given; it never falls back to the stored primary/backup chain, so a stored free-tier or prompt-logging provider is ignored. A pool passed for any other capability is refused. This is enforced in `route()` and in `generate_structured()` (`enforce_pool_rule`, allowlist `POOL_CAPABILITIES`).
4. **Which models, in which order** (shared content only). The configured cloud text models: (a) free tier first, at most 3, in the operator's order (provider order, then each provider's model list): a provider whose `cost.free_tier.<provider>` flag (D-219) is on, or a zero-rate catalogue model; (b) then the 2 cheapest priced paid models by the list price of one typical call (220 input and 8 output tokens). An unpriced model is never used. A rung that errors, is unavailable, is rate limited, times out or answers invalidly hands over to the next, through the existing chain (health, cooldown, per-attempt timeout, total deadline 4 s). "Shared" means the server verified the claim: `content_id` (new optional field of `POST /api/reading/lookup`, backward compatible) names a published article that contains the whole passage (`reading_cache_scope.scope_for`). Until the reader sends `content_id`, every tap is private and nothing is sent.
5. **Cost control.** A flagged free-tier provider is priced at list price (D-219) and therefore passes the same paid/funding gate as any paid model: it is admitted by `word_sense_choice.daily_spend_cap_usd` (new policy, default 0.25 USD, 0 disables; `ai/spend_gate`, fails closed on an unreadable ledger or cap), and under FUNDING_ENFORCEMENT=enforce an unfunded learner skips it (a `FundingRequired` is a quiet miss, not a warning on every tap). Only zero-rate catalogue models (for example OpenRouter ":free") are outside the cap. Every call is booked to the shared AI ledger and telemetry under the capability with its provider, model and tier. The per-account brake of the tap also applies. The global daily ceiling is the Intelligence lane's separate change and plugs in at `spend_gate`. Estimated cost of a fallback call: about 0.00004 USD at gpt-4o-mini (0.15/0.60 per million), 0.00007 at deepseek-chat, zero on a zero-rate model.
6. **Cache.** The router's in-process result cache, keyed by capability, contract and prompt version and (word, SHA-256 of the whitespace-collapsed case-folded sentence, support language, source language, content scope, SHA-256 of the senses), never the model and never the sentence text. TTL 30 days. Never persisted. A failure is remembered for about a minute so a failing word does not retry on every tap.
7. **Never blocks the sheet.** The call runs on the tap's seam gate (bounded admission, joined when already running, a cool-down after a failure) and waits at most `max(1.5 s, what is left of the tap budget)`; an overrun is a miss, and the call finishes on its worker and fills the cache for the next tap. Any exception is a miss.
8. **Not included.** Sending the sentence on `word_translation`, `/word-detail` ("Why here?", unchanged), choosing among Chinese CC-CEDICT readings (the tagger decides those), any private-content path to an AI, any live provider test (none was run; mocks only), and any UI change.

## D-231 - Gate 2 qualifiers: an estimated level, an estimated score and a "Report a problem" link reuse existing patterns (PRE-204, PRE-206) (2026-10-18)

**Status: ACCEPTED** (2026-10-18, accepted by Hermes for the owner. D-entry acceptance was delegated by the owner in the UI-lane session the same day. Independent review APPROVE on PR #299; CI green. D-228 and D-230 were left free for other lanes.) Implemented by the "Gate 2 qualifiers" PR. No schema, no migration, no new endpoint, no visual that the app does not already draw.

Rule: a small UI change that the design does not draw reuses an existing design pattern or component, and is recorded here and in `UI_BACKEND_GAPS.md`.

1. Estimated content level (PRE-204). Where a listening item's level is shown (Discover card tag, Listening header, Content hero and related list) and the catalogue only estimated it (`level_source` is `deterministic-estimate`, or only `estimated_level` is sent), the level reads "B2 · est." (Vietnamese "ước tính", Chinese "估计"), the same short qualifier the app already uses for an estimated word timing (`timingEstimated`). A reviewed level reads plain. The filter value is unchanged. Reading articles are NOT qualified: the learner list sends only `level` (the effective level), with no reviewed flag, so an estimate cannot be told from a reviewed level without a payload change (recorded as a gap).
2. Pronunciation scores (PRE-204). Speak's result and Compare's word detail carry one muted line under the score block, "Automatic estimate, for reference only." (Vietnamese "Điểm ước tính tự động, chỉ để tham khảo.", Chinese "自动估算分数，仅供参考。"), in the existing muted note style (`s-speak-asr`, `s-compare-note`).
3. Report path (PRE-206). The word sheet's "why here" answer, the sentence sheet's translation, a listening question's explanation, the writing evaluation and the speaking feedback carry one small text link, "Report a problem" (Vietnamese "Báo sai", Chinese "报告问题"), in the existing `o-btn--link` text-button style. It opens the existing Feedback screen with the area chosen and a one-line reference (surface, content id, word or sentence) at the start of the message. `POST /api/feedback` is unchanged: it takes no context field, so the reference travels in the message `text`; the learner sees it and can edit or delete it. Orena chat belongs to the Intelligence lane and is not touched.
4. No "AI may be wrong" hint is added: the app and the design have no such inline string (only the Terms line). The link and the Terms line carry it.

## D-229 - Light consent: a clickwrap line, a remembered-note line, and a plain privacy policy (2026-10-18)

Status: ACCEPTED by Hermes for the owner (D-entry acceptance was delegated by the owner in the UI-lane session on 2026-10-18). The decision itself is the owner's of 2026-10-18, relayed by the delegate Hermes.

Decision. Orena asks for consent the way common apps do, with no separate consent page and no checkbox.
1. Clickwrap. Under "Continue with Google" on the Welcome Account step, the small line the design already draws ("By continuing you agree to the Terms and Privacy Policy", Onboarding frame 02 Account, 12px, `--text3`, centred) names the two documents as links to the existing Terms and Privacy pages. Vietnamese: "Bằng việc tiếp tục, bạn đồng ý với Điều khoản sử dụng và Chính sách quyền riêng tư". The design's second sentence about recordings is not drawn.
2. Memory. The first time Orena stores a note on the account in a conversation (agent stream `memory_update`, `stored: "server"`, `op: "upsert"`), the reply carries one small line: "Orena remembered this - Manage in Settings" (Vietnamese "Orena đã ghi nhớ điều này - Quản lý trong Cài đặt", Chinese "Orena 已记住 - 在设置中管理"); the second part opens Settings, Privacy (the memory switch of D-226). A device note and a removal never show it. The design draws no such line, so it reuses the existing source/evidence chip and the error line's text-link button; no new visual.
3. Privacy policy. The Privacy Policy states: Orena as the controller of the data; what is collected; that the AI providers currently used for learner requests are Google (Gemini) and Groq, and Microsoft Azure Speech for pronunciation scoring, in one sentence that is easy to edit, followed by "Providers may change; when they do, we update this policy" (Hermes checked the presence of keys in the :8000 container environment: Google, Groq and Azure Speech are configured; OpenRouter, OpenAI and DeepSeek have no key, so they are not named and the page test forbids them until the owner answers; this supersedes the 2026-10-09 decision not to name vendors, for the three named only); that Orena memory is on by default, is switched in Settings, Privacy, and keeps notes written from the learner's own words; that notes Orena remembers are kept for up to 180 days (about 6 months) from the last time the learner asked Orena to remember them, after which Orena stops using and deletes them (Intelligence PR #292, merged; reading a note does not renew it, and the daily deletion sweep stays off until the owner sets AGENT_MEMORY_RETENTION_SWEEP=on) while learning history is kept while the account is active; that the microphone is used only when the learner taps record or starts voice, the browser asks permission, recordings go to the speech provider, and voice can be stopped at any time (no separate consent step exists today); the learner's rights; and the two contacts orena.legal@chillpickle.org (privacy) and orena.support@chillpickle.org (support). The policy has no version field (only the deploy-stamped effective date), so there is no version to bump; the effective date is stamped at deploy and is the version the consent evidence below must record.
4. Wording. No learner-facing "thử nghiệm", "pilot", "trial" or "beta" wording in the public legal pages or the learner copy (the Plan screen's subscription state "Trial / Dùng thử / 试用中" is a billing state, not a stage of the product, and stays).
5. Pending. A just-in-time voice consent step, and server-side consent evidence (which policy version and effective date the learner accepted, and when), follow after the owner's storage and schema decision. This decision adds no storage.

Consequences. `docs/legal/public/privacy.{en,vi}.json` and `terms.{en,vi}.json` are edited and the public pages rebuilt; `scripts/test_orena_public_pages.mjs` stops forbidding "Gemini" and "Groq" and asserts the provider sentence. There are no Chinese public legal files; the public pages are English and Vietnamese only.

## D-232 - Agent Contract v10: `daily_ai_limit`, a refusal for the system's daily AI budget and the agent's daily cap (2026-10-18)

Status: ACCEPTED (2026-10-18, accepted by Hermes for the owner. D-entry acceptance was delegated by the owner in the UI-lane session the same day. Independent review APPROVE; both review P2s fixed; CI green at a1fef517.) Drafted by the UI lane (`claude/agent-contract-v10`) at the Intelligence lane's request, because D-086 and D-223 point 9 leave contract edits to the UI lane. The server side is an Intelligence-lane pull request after #298 (the $5/day owner ceiling on AI spend); the client side is a UI-lane follow-up. This entry and its contract text change no behaviour by themselves.

1. **`contract_version: 10`.** A new refusal category `daily_ai_limit` (`AGENT_CONTRACT.md` §2.1): HTTP 429, `{"detail": {"category": "daily_ai_limit", "message", "retryable": false, "context": {"scope": "system" | "agent", "resets_at"}}}`, header `Retry-After: <whole seconds until resets_at, at least 1>`. `resets_at` is always the next UTC midnight (ISO 8601) for both scopes and `Retry-After` matches; clients treat `resets_at` as authoritative. Only a limit really reached is `daily_ai_limit`; a fault (the cap or the ledger unreadable) is `429 rate_limited` with `Retry-After: 60`, so clients apply the normal wait-and-resend. `message` is an English fallback ("Orena's AI is paused until the daily AI budget resets."); clients always show their own localized copy.
2. **Where.** `POST /api/agent/turn`, `/api/agent/voice/session` and `/api/agent/voice/extend` (§9). On `/voice/extend` the client lets the token it holds play out, then ends the session, as for `quota_exhausted`.
3. **Meaning.** Orena's AI is paused for everyone until `resets_at` because the system's daily AI budget (`scope: "system"`) or the agent's own daily cap (`scope: "agent"`) is reached. Nothing ran and nothing was charged; it does not count against the learner's own limits.
4. **Client rules.** Tell once; never wait out or resend (an explicit exception to the `rate_limited` wait-and-resend of §2.1); keep the learner's typed message; show one short line in the interface language that AI is back after `resets_at` in local time; no device-cascade fallback; no upgrade or plan link (it is not the learner's plan); features that need no Orena message keep working.
5. **Older clients.** A client that declares `contract_version` <= 9 is served exactly as under v9 and keeps receiving `rate_limited` for the same condition. The server reads the declared `contract_version` from the raw request body, and the spend check runs before validation (a schema-invalid v10 body is answered `429`, not `422`) and before anything runs or is metered. v9 behaviour stays documented.

Consequences. The contract text is pinned equal to the code constant, so this PR moves the version constant to 10 in `writing_coach/agent/contract.py`, `static/orena/agent/contract.js`, the regenerated `static/orena/copy/surfaces.json` and its pin in `scripts/test_orena_surfaces.mjs`, as D-223 did. Nothing branches on version >= 10 yet. The client handling ships in the same PR, because the client now declares v10: `transport.js` yields a `daily_ai_limit` error with no wait and no resend; the existing error line (`errorText`, no retry or plans button) and the voice toast show one sentence in English, Vietnamese and Chinese with `resets_at` in the learner's local time (`Intl.DateTimeFormat`, `screens/plan/quota-notice.js`); the learner's message stays as for `quota_exhausted`; a refused voice session does not fall back to the cascade; a refused `extend` lets the held token play out. No new visual: it reuses the failed-request line and toast. Recorded as the owner's standing decision for small UI (2026-10-18), so `UI_BACKEND_GAPS.md` is not changed. Node gates cover no resend, the copy in all three languages, and the voice session and renewal cases. Still to do: the Intelligence lane sends `daily_ai_limit` to v10 clients (PR #304, after #298).

## D-233 - Server consent evidence and voice consent: five nullable columns on `users`, proposed migration 0036, dormant until applied (2026-10-19)

Status: ACCEPTED (2026-10-19, accepted by Hermes for the owner; D-entry acceptance delegated by the owner on 2026-10-18; independent review APPROVE and architecture review APPROVE at 486905ea; PG17 rehearsal up/down/up PASS - docs/reviews/architecture/CONSENT_EVIDENCE_0036_REVIEW_2026-10-19.md, ORENA_PRE_MARKET_EVIDENCE/REHEARSAL_0036_2026-10-19.md). Migration 0036 stays PROPOSED; promotion to :8000 is the owner's gate. Resolves clause 5 of D-229 (the pending voice consent and consent evidence) and PRE-005.

1. **Storage.** `migrations/proposed/20261019_0036_consent_evidence.py` (parent `20261018_0035`) adds to `users`: `consent_version` varchar(32), `consent_accepted_at` timestamptz, `consent_language` varchar(16), `voice_consent` boolean NOT NULL DEFAULT false, `voice_consent_at` timestamptz; the first three and the last are nullable ("no record"). Additive, no backfill, no index, no rewrite (a constant default), under `lock_timeout`; its own operator step after a backup, like 0018. Account-wide, no history. `users` survives account deletion, so the deletion workflow resets all five (`deletion_enumeration.CONSENT_COLUMNS_TO_RESET`, `consent.reset_consent`); no deletion runtime exists yet (D-055).
2. **Version.** `consent_version` is the deploy-stamped effective date of the public legal pages (D-229 clause 3), given to the server as the environment variable `LEGAL_EFFECTIVE_DATE` (`YYYY-MM-DD`, the value passed to `build_public_pages.mjs --release --effective-date`); unset or malformed it is the literal `unstamped`. The deploy step must set both to the same date. `APP_ENV=production` refuses to start when it is unset or malformed (`core/deployment.py`), so production never records `unstamped`; development and staging stay lenient. `compose.yaml` passes it through.
3. **Recording.** The first successful Google sign-in of a NEW account (`upsert_user` reports `created_now`) records version, time and language, never overwriting a record, **only when the sign-in was started from the Welcome Account step**, whose clickwrap line was on screen: that step starts `/auth/google?...&account_step=1&lang=<interface language>`, the server keeps the flag in the signed session, and a direct visit to the sign-in address or a native redirect carries no flag and records nothing (such an account has no record, so it gets `consent_required: true` and the sheet below). `consent_language` is the interface language the Account step carried; the browser's `Accept-Language` is only the fallback when the flag has none. An account with no record gets `consent.consent_required: true` in `GET /api/session/bootstrap`; the client shows one sheet (Mic state sheet shape, "I agree" / "Đồng ý" / "我同意", links to Terms and Privacy; no page) and `POST /api/account-settings/consent {language}` records the current version. The scrim or Escape closes it without recording, so it returns at the next start.
4. **Voice.** `POST /api/account-settings/voice-consent {granted}` and `GET /api/account-settings/consent` (`voice_consent`). `/api/speech/transcribe` and `/api/speech/pronunciation` (the routes that carry audio to a provider; `/evaluation` and `/attempts` carry none) answer 403 `voice_consent_required` when the account's answer is a stored "no" and sign-in is on, and fail CLOSED (503 `consent_unavailable`, retryable) when the columns are known present but the answer cannot be read. A 403 reaching any room opens the same voice sheet at once (`infrastructure/api.js` handler) and marks the answer "no" until given. The client asks just in time, at the first recording of any room (`micGate`: "Cho phép Orena nghe giọng bạn?", "Cho phép" / "Để sau"), and Settings, Privacy has a "Ghi âm giọng nói" switch beside Memory. `/api/agent/voice/*` is the Intelligence lane's: this change only exposes the flag; whether and how that lane enforces it is for it to decide, and it was not touched.
5. **Dormant until applied.** No ORM column maps the five; `persistence/consent_store.py` reads and writes them with raw statements behind a column-presence check (kept when true, re-asked every 30 s when false). With the columns absent every read answers "no record", every write is a no-op returning false, the bootstrap flag is `consent_required: false, voice_consent: null`, the gate lets requests through, the client asks nothing and draws no switch. Merging the code therefore changes nothing on :8000 or :8021 until the migration is applied. After it is applied, existing accounts with no record are asked once, and every account's voice answer starts as "no", so learners are asked at their next recording.
6. **Existing users and the release.** Every existing account starts with `voice_consent = false`, so after the migration is applied speech transcription and pronunciation return 403 for all existing learners until each allows recording in the just-in-time sheet (asked at the next recording, or through Settings, Privacy). Release note: "Orena now asks your permission before recording your voice. You will be asked once, the next time you practise speaking; you can change it in Settings, Privacy." (`RELEASE_8000_READINESS.md` section 14.)
7. **Legal text.** `docs/legal/public/{privacy,terms}.{en,vi}.json` describe the consent record and the voice permission now; there are no Chinese public legal files. **Effective at promotion of 0036**: the text ships with this change, and the effective date is re-stamped at the :8000 release build (`--effective-date`, `LEGAL_EFFECTIVE_DATE`); the pages must not be published with the new text before the migration is applied, and the migration not applied without the new text. A new date does not re-ask existing accounts that have a record.
8. **Deletion.** `deletion_enumeration.CONSENT_COLUMNS_TO_RESET` and `consent.reset_consent` are the reset; no account-deletion runtime exists (`deletion_journal.py`: "not built"), so there is nothing to wire it into yet, and that workflow must call it. Open owner question for counsel: must consent evidence be retained after an account is deleted? Resetting erases the proof of what the learner accepted.
9. **Out of scope.** No consent history table, no re-consent on a new policy version (a changed `LEGAL_EFFECTIVE_DATE` does not re-ask), no export format, no change to `/api/agent/*`.

**Promotion (2026-10-19, PR BD).** `20261019_0036_consent_evidence.py` moved to `migrations/versions/` unchanged except its Status paragraph, as the single head on `20261018_0035`. Source control only: not applied to :8000 or any runtime until the owner approves the next migration; the promotion PR needs an independent architecture review before merge (reviewer, commit and outcome recorded in Git). Billing's proposed 0034 re-parents on 0036 if promoted later.

Consequences. Tests: `tests/test_consent_evidence.py` (migration up and down on a populated SQLite table, absent-column degradation, sign-in recording, bootstrap flag, endpoints, 403 gate, deletion reset), `scripts/test_orena_consent.mjs`; the PostgreSQL proof is `tests/test_consent_evidence_postgres.py` (skipped without `ORENA_TEST_POSTGRES_URL`).

## D-234 - Media content packs: published shared media moves between environments by the existing content-pack format (2026-10-19)

Status: ACCEPTED (2026-10-19, accepted by Hermes for the owner). Drafted by the UI lane (`claude/content-pack-media`) on the owner's decision of 2026-10-19 to have an official, `$0` tool for moving published content (:8021 to :8000 now, the VPS later).

1. **One format.** `media_item` joins the content-pack kinds (`CONTENT_PACKS.md`). A pack with media is `version` 2 and carries binary files under `assets/<asset key>` listed in the manifest with sha256 and size; a pack without media is still `version` 1. A reader refuses a newer version, an unlisted file, a hash mismatch, a traversal path and an asset outside `media/` and `speaking/model-clip/`. The manifest records the source label, `app_version`, `source_commit` and the published entries left out.
2. **Export** reads shared-library entries with `status == published` only. A published entry whose playback is a local upload, or whose thumbnail file is missing, is left out with a reason. QA or test fixtures are left out by id prefix, because the store has no tag for them.
3. **Import** (Admin route `POST /api/admin/content-packs/{plan,import}` and `scripts/media_content_pack.py`, one implementation in `writing_coach/media_pack.py`) is idempotent by `media_id`: `new`, `unchanged`, `conflict` (kept) or `refused`; replacing a conflicting item needs `overwrite`. A dry run (the route `plan`, the CLI default) decides exactly as a real run and writes nothing. It never calls a provider and never starts a job; an item arrives ready with its stored transcript and translations. It is published only when its rights are cleared with a licence note and its transcript passes the deterministic checks; otherwise it arrives unpublished and the report says why. The Admin import is audited; the CLI appends a line to `media-pack-imports.jsonl`.
4. **No schema change**, no Docker, no provider. Reading and vocabulary keep their existing path; vocabulary still arrives `pending_review` (D-111).

5. **Translations travel from the cache Listening reads (2026-10-19 correction).** A cue's stored meaning lives in the learning cache (`media_translation_cache`, keyed by asset id, segment id, text fingerprint, language and translating provider/model), not on the media record, so an export that read only the record carried none. Export reads that cache for every support language present and carries each meaning with its provenance, creation time and source model. The cache holds hashed keys and cannot be listed, so the candidate models are enumerated from the AI ledger (`audit_logs` `ai.operation`, capability `media_translation`, distinct provider/model: the one record of every model that ever translated, whatever the configuration says now); `--provider-model` is an override, and an unreadable ledger leaves the override and the configured model. Across the models the newest `generated_at` wins for each cue. Export and `--dry-run` print coverage per item and in total; below 100% they warn and exit 3 (the Admin route answers 409 `pack_translation_coverage_incomplete`) unless `--allow-partial` / `allow_partial`.
6. **Imported meanings are model-independent (coupling to the read path).** Import writes each meaning into the target's learning cache under the identity `pack-import` (`media_meaning.IMPORTED_IDENTITY`) instead of the target's current provider/model. `media_meaning.resolve_segment_meanings` looks under the current identity first, then under `pack-import` for the same asset, segment, text fingerprint and language, before any provider call, so changing the translating model later does not re-translate (cost) what was imported. This is a cache read: no new table, no PostgreSQL schema. The cache is derived, regenerable data and not learner data: it holds no learner, account or progress record. Import is additive and idempotent, a held row is kept unless `overwrite`, and a re-export carries imported rows on.
7. **Derived text is an explicit, default-off switch (Hermes for the owner, 2026-10-19).** Whether the transcript and its translation shown beside the 46 YouTube videos may be moved as derivative text is the owner's call; he answered "bật" on 2026-10-19 10:31 (D-239, with source credit and takedown conditions). Before that answer, export carries media metadata, rights, level, playback and assets only; transcript cues, word timing, readings and translations travel only with `--include-derived-text` (CLI) / `include_derived_text` (Admin route), default off. Off, an imported item has no usable transcript and arrives `unpublished`, and an overwrite never removes a local transcript. On, the coverage gate applies. `--dry-run` and the preview state the mode.
8. **Live correction (2026-10-19).** The cache key's model part is `default` for today's providers (they expose no `.model`), so export always probes `<provider class>:default` besides the ledger's models; and an item with a transcript whose stored translations are absent counts as expected cues with none stored (a failure), never `0/0`.

Consequences. Packs larger than the 50 MB upload limit go through the CLI (limit 2 GiB). Local-upload media and book bytes are not packed (rights and size); that stays a later decision. Asset keys are bound to their item (its thumbnail, its computed model clips, or its own media/<id>/ directory) and never overwrite bytes that another entry holds; source keys that name an owner, user or internal bookkeeping are dropped and a learner key in a lesson keeps the entry out; an overwrite keeps a local archived or unpublished status. The media index writer takes a cross-process file lock so the CLI and the server do not lose each other's writes.

## D-236 - Voice chat with Orena is for Plus and Pro; Free chats in text (2026-10-19)

**Status:** ACCEPTED, the owner's decision (Discord, 2026-10-19).

**Owner decision** (Discord, 2026-10-19, quoted by Hermes): "Phần voice chat của agent thì chỉ gói trả phí mới dùng được, Free thì không nhé." In English: the agent's voice chat is for paid plans only; Free does not get it.

1. **Entitlement.** The plan catalogue has a new on/off entitlement, `orena.voice`. It is off for Free and on for Plus and Pro by the code's defaults, and an administrator may change it in the catalogue. A stored catalogue that does not name it keeps those defaults, so no data change is needed. Voice time is still charged as Orena messages (`voice_seconds_per_message`, D-169).
2. **Server check (`product/plan_features.py`).**
   - It reads the strict catalogue and the account's effective plan. A plan an administrator granted (D-154) counts.
   - It holds whether or not usage limits are enforced, because it is a product rule.
   - A plan or catalogue that cannot be read refuses with 503 `quota_unavailable` (fail closed).
   - A server with no plan system (tests, a bare development server) lets voice through.
3. **Routes.**
   - `POST /api/agent/voice/session` and `/voice/extend` answer **403 `feature_not_in_plan`**, with `context.feature: "orena.voice"`, the plan and `upgrade`. This comes after the 404 of an absent voice and before any spend limit, window or token.
   - On a downgrade mid-session, the next chunk is refused and the client ends the session when the token it holds dies.
   - `GET /api/agent/voice/voices` gains `"entitled": true | false | null`, so the client offers the upgrade before the tap. `null` means the plan cannot be read right now, which is not a "no". The 403 stays the authority.
4. **Unchanged.** Text chat on Free, with its own message quota. Speaking practice and pronunciation scoring.
5. **Other lanes.** The UI lane writes the Agent Contract v11 row (the feature value, `entitled`, the extend behaviour), the upgrade sheet, and the Pricing and Plan rows in VI/EN/ZH (PRE-401). The Billing lane maps the entitlement into the Polar products. For the pilot, billing is off, so an administrator grants a plan by hand (D-154) to test voice.

## D-235 - Agent Contract v11: voice chat is a Plus and Pro benefit; the system AI pause reaches every surface through one header (2026-10-19)

Status: ACCEPTED (2026-10-19, accepted by Hermes for the owner; D-entry acceptance delegated by the owner on 2026-10-18; independent review APPROVE; server #315/#317 merged). Drafted by the UI lane (`claude/ai-paused-voice-plan`), because D-086 and D-223 point 9 leave contract edits to the UI lane. It records the UI and contract side of two owner decisions of 2026-10-19; the server side is the Intelligence lane's (PR #315, merged: `X-Orena-AI-Paused`, and PR #317, its voice-entitlement pull request, which records D-236 and which this entry follows). This entry depends on both: merge the client after them.

1. **Decision A - at the $5/day system AI ceiling, AI features lock until the reset with a clear message; non-AI features keep working.** Contract text (`AGENT_CONTRACT.md` §2.1): any response the ceiling refused, whatever route, status or body, carries `X-Orena-AI-Paused: <resets_at, ISO UTC>`; a fault carries no header. Client: `infrastructure/api.js` reads it once for every route (`infrastructure/ai-paused.js`) and each surface shows the existing line (`pausedMessage`: "Hôm nay Orena tạm dừng AI, sẽ có lại sau {time}", no-time fallback) in the place it already shows a failed request, with no retry button and no way to the plans. Surfaces: Reader (translation, summary), Listening (meaning, Vocabulary Focus), the word sheet and sentence sheet (meaning, "why here", translation, structure, vocabulary), the Writing room's review, and the Respond, Discussion, Situation, Free-talk and Reading-transfer rooms. No new visual.
2. **Decision B - Orena voice chat is Plus and Pro only; Free keeps text chat; Speaking practice is unchanged.** `contract_version: 11`: `403 feature_not_in_plan` gains `context.feature` `orena.voice` on `voice/session` and `voice/extend`; `GET /api/agent/voice/voices` answers `200` with `entitled` (false for Free). Client: any voice entry of a Free learner (the desk rail's mic, the full-screen voice, the Home and panel voice rows) opens one sheet, built on the Mic state sheet's shape: one sentence ("Voice chat with Orena is included in Plus and Pro.", in the three languages) and one button to the plans route; the server's 403 on session is handled the same way (no cascade fallback), and on extend the held token plays out and the session ends. Pricing lists "Voice chat with Orena" as a benefit and a compare row, driven by an `orena.voice` entitlement in `GET /api/product/plans`; the catalogue does not carry that entitlement yet (server follow-up), so the row appears when it does. Plan & usage draws usage meters only, so it gains no row.
3. **Consequences.** The contract text is pinned equal to the code constant, so the version moves to 11 in `writing_coach/agent/contract.py`, `static/orena/agent/contract.js`, the regenerated `static/orena/copy/surfaces.json` and its pin in `scripts/test_orena_surfaces.mjs`, as D-232 did. Recorded as the owner's standing decision for small UI (2026-10-18): the upsell reuses an existing sheet and route, so `UI_BACKEND_GAPS.md` is not changed.

## D-237 - A daily cap on each learner's voice minutes with Orena (2026-10-19)

**Status:** ACCEPTED. Hermes decided for the owner on 2026-10-19; the owner may change the number.

**Why.** Measured on :8021 (`ORENA_PRE_MARKET_EVIDENCE/COST_PRE402_403.md`), a voice chunk costs about $0.025 per 2 minutes. One Pro learner using the whole message allowance as voice would cost about $12–30 a day. That alone would trip the $5 system ceiling (#298) and lock AI for everyone.

1. **The limit.** The `orena.voice` entitlement (D-236) is now seconds of voice chat per UTC day: 15 minutes (900 s) for Plus and Pro by the code's defaults, and an administrator edits it in the plan catalogue. Free still has no voice. The $5 system ceiling is unchanged.
2. **What is counted.** The voice seconds the server records per learner, the `agent.voice_seconds` usage events. They are recorded **when each token is minted**, for every session, metered or not; an unmetered session was counted only at its end before (review of #325). The cap therefore holds whether or not usage limits are enforced, and an open session is seen by the next check.
3. **At the cap.** `POST /api/agent/voice/session` and `/voice/extend` answer **429 `quota_exhausted`** with `context.feature: "orena.voice"`, plus `used`, `limit`, `unit: second`, `display_unit: minute`, `scale: 60`, `window: day`, `resets_at` (the next UTC midnight) and `plan`. This is the existing contract shape, with **no `upgrade`**, because Plus and Pro have the same minutes. It affects this learner only; nothing else is locked. **Every token is clamped to the seconds left today**, so the cap is not passed; parallel opens can race past it by at most their clamped tokens. Usage that cannot be read refuses with 503 `quota_unavailable` (fail closed). The day is the UTC day; `orena.message`'s day follows the learner's zone. A stored limit under a minute, which is the on/off placeholder an editor saved under D-236, reads as the default.
4. **The client** (UI lane) shows its own line for `feature: "orena.voice"`, e.g. "you have used today's voice minutes", and text chat goes on.
5. **Contract v13 (UI lane).** `last: true` is also a session's normal end and an unmetered session's only chunk, so a client could not tell the learner that the day's minutes ran out inside a chunk. Every chunk answer (`/voice/session`, `/voice/extend`) gains `day_limit_reached: bool`, true only when that token was clamped to the seconds left today (server: #328). The client lets that chunk play out, then tells the line of point 4 once, with the figure from the plan's `orena.voice` limit, and does not offer to restart voice.

## D-238 - Legal documents and app-information pages exist in English only (2026-10-19)

**Status:** ACCEPTED (owner, 2026-10-19, relayed by Hermes).

**Owner decision** (relayed by Hermes, 2026-10-19 08:44): "Tất cả văn bản pháp lý hay thông tin về app các thứ thì để tiếng Anh, không cần làm nhiều ngôn ngữ." In English: all legal documents and app-information text stay in English; they do not need several languages.

1. **One language.** The Privacy Policy, Terms of Service, Refund Policy and Delete account page exist in English only. Every interface language (English, Vietnamese, Chinese) opens the English page. `/terms`, `/privacy` and `/account-deletion` always answer the English page; a `?lang=` on the address is tolerated and ignored, so old links work. The per-language note added for Chinese (#309, "本页面目前仅提供英文版本") is removed: the rule is uniform and needs no note.
2. **Retired text.** The Vietnamese legal sources (`docs/legal/public/*.vi.json`, the Vietnamese sections of `docs/legal/DRAFT_*.md`) and the built `templates/orena/public/*.vi.html` are deleted (Git history keeps them); nothing loads them. The public pages' language switch is not drawn. The in-app Refund Policy (`#/legal/refund`) reads the English draft for every interface language, and the Terms and Privacy addresses in the app go to the public pages.
3. **Interface copy stays translated**, including the sign-in line under the Google button; only the links in it open the English page. Outside an English interface, the link labels in that line, in the consent sheet and in Settings, Privacy get a plain "(English)" after the label (`static/orena/legal/links.js`; no new visual).
4. **Content of the English text.** It states the 180-day retention of Orena memory notes (PRE-005) and, since this decision, that voice chat with Orena is a feature of the Plus and Pro plans with a daily limit of voice minutes (D-236, D-237).
5. **Consent language.** The `consent_language` that D-233 records is the language of the clickwrap the learner saw (the interface language); the document they agreed to is always the English text, whatever that value is.
6. **Supersedes** the `UI_BACKEND_GAPS.md` entry "Chinese legal text is pending" (resolved here), and the earlier rule that the public legal text is kept in Vietnamese and English in parallel (D-162).

**Not in this decision.** Dataset and licence credits shown by the Licences sheet come from the API and are unchanged. No pricing or checkout screen links to a legal page today; when one does it uses `legalHref`/`legalLabel`.

## D-239 - Transcripts and translations beside the YouTube videos may be shown publicly, with source credit, fast takedown and a Creative Commons preference (2026-10-19)

**Status:** ACCEPTED (owner, 2026-10-19 10:31, relayed by Hermes).

**Owner decision** (Discord, relayed by Hermes): the owner answered "bật" (on) to the question in D-234 item 7. In English: the transcripts and Vietnamese translations shown beside the 46 YouTube videos may be moved to :8000 and shown publicly (`--include-derived-text` ON), on three conditions.

1. **Source credit.** Each video clearly shows its source: the channel name and a link to the original video on YouTube, in the Listening room and on Content detail, using the design's existing source pattern (the source name in the item's meta line) with one link. The credit reads the provider metadata the payload already carries (`catalog.source.creator`, `provenance_url` / `source_url`, else `asset.source_url`; `static/orena/product/media-credit.js`); nothing new is fetched. The link opens in a new tab with `rel="noopener noreferrer"`; "Watch the original" / "Xem video gốc" / "观看原视频" is interface copy. An item with no stored channel name shows the link alone; only an https address on www.youtube.com, youtube.com, m.youtube.com or youtu.be becomes the link; any other address (http, another host, a script scheme) draws no link and the channel name stays as text. The design draws no link, so this one anchor is an owner-mandated addition, not a design pattern.
2. **Fast takedown.** The English Terms (section 7) say content owners can request removal at orena.legal@chillpickle.org (the legal contact already in the Terms). The admin runbook "Taking one video down" in `RELEASE_8000_READINESS.md` unpublishes one video, which removes its transcript and translations from every learner route, using the existing status route; a state change, no hard delete, no learner data touched. There is no per-item purge of the derived translation cache rows (hashed keys); that is left to a later decision.
3. **Record and rule for the future.** This entry. Future imports prefer Creative Commons-licensed videos (the round-2 source-selection rule); the 46 existing videos stay on the terms above.

Supersedes the "pending" state of D-234 item 7: the switch stays default-off in the tool, and the owner's answer is that it is turned on for the :8021 to :8000 move of these videos.

**Not in this decision.** No new provider call, no schema change, no change to the rights gate (an item still publishes only with rights cleared).

## D-240 - Every learner-visible content item has a thumbnail (2026-10-19)

**Status:** ACCEPTED (owner, 2026-10-19 11:28, relayed by Hermes).

**Owner decision** (Discord, relayed by Hermes): "Bài nào cũng cần có ảnh thumbnail hết nhé, không được để trống." In English: every article needs a thumbnail, none may be left blank.

1. **Rule.** A Reading article, a vocabulary collection, a book and a media item have a thumbnail before a learner can see them. Publishing one without a thumbnail is refused, with no override: a Reading article by `set_status` (409 `thumbnail_required`), a vocabulary collection by `set_collection_status`, a media item by the admin status route (409 `thumbnail_required`). The two paths that publish by themselves make a cover instead of publishing bare: the Reading engine's automatic admission, and a vocabulary collection published by the import pipeline. A book's import stores the EPUB's cover, else a typographic one. Items published before the rule are not unpublished; `scripts/audit_thumbnails.py` (read-only, with a `published` flag for media) lists them per kind and `scripts/backfill_typographic_covers.py` (dry run unless `--apply`) gives each a typographic cover.
2. **Source order.** (1) a source image with clear rights, (2) a free library image with its licence, (3) a typographic cover. No AI image generation without a cost decision from the owner.
3. **Typographic cover.** Deterministic and $0: an SVG made on the server from the title, language and topic, 640x400 (the 16:10 the media card and the hero draw), painted only with colours that `static/orena/kit/tokens.css` declares (the skill hues, the kind's hue as the first colour, `--accent-ink`), the title as escaped text. It is the poster the app already draws for a coverless card, made once and stored. It is stored in the runtime asset root (`READING_LIBRARY_ASSET_ROOT` for Reading, vocabulary and books; `MEDIA_LIBRARY_ASSET_ROOT` for media) and served from our own origin with a sandbox Content-Security-Policy; alt text is the title; it needs no credit. A static (repository-less) vocabulary collection is served the same cover on request.
4. **Provenance, no schema change.** `{kind: source_image|library_image|typographic, source_url, author, licence, licence_url}` is kept in a Reading `image_set` event, a vocabulary collection's `provenance["thumbnail"]`, a media entry's `source` (`thumbnail_*`) and a book's manifest. A picture's credit is "author · licence" and uses the existing image-credit line; a typographic cover has none (the payload says `typographic`).
5. **Attach from a URL.** Admin routes download a picture server-side into the asset root: `image/*` only and at most 5 MB, through the existing SSRF guard, only from `nasa.gov`, `noaa.gov`, `nih.gov`, `gutenberg.org` (and their sub-domains), `upload.wikimedia.org`, `images.unsplash.com` and `images.pexels.com`, only with the licence fields given and a licence of public domain, CC0, CC BY, CC BY-SA, Unsplash or Pexels. Audited. Fetching real pictures for the existing articles is a later step; this is the mechanism.
6. **Content packs.** The thumbnail travels with the item (provenance in the item, a downloaded picture's bytes in the pack). On import a picture is verified (host, licence, hash, bytes) and an item that carries an invalid one fails; an item that carries none, or a typographic one, gets the deterministic typographic cover (never bytes from the pack).
7. **Provider-hosted media.** YouTube items keep their provider-served `i.ytimg.com` thumbnail and the publish rule accepts it. Orena does not copy it.

**Owner question (open).** May Orena copy a YouTube video's thumbnail into its own asset root? It may conflict with YouTube's terms, so nothing was copied; the embeds keep the provider-served thumbnail.

**Not in this decision.** No schema change, no provider, no AI image, no network call at publish time, and no unpublishing of existing items. Real pictures for the existing articles (NASA, Wikimedia and the like) are attached later with the route above.

**Amendment 2026-10-20 (owner report relayed by Hermes: every fable card showed a "T", the title was cut by the duration pill and "EN" hidden by the type pill).** Point 3 is narrowed to what the pinned Discover card draws over a picture (the type and duration pills only): the typographic cover prints no title and no topic/language label (the title stays its accessible name), its glyph is the first letter of the first meaningful word (a leading English article and quotes skipped; Chinese skips punctuation only), placed clear of both pills, and its second hue is chosen by the topic from the same token list (by the title when there is none). Existing covers are remade with `scripts/backfill_typographic_covers.py --regenerate-typographic` (dry run unless `--apply`; only a cover whose provenance kind is typographic; a real picture is never touched). Gap recorded in `UI_BACKEND_GAPS.md` ("Discover: the cover of a text-only item").

## D-241 - Account deletion: the D-054 gate is lifted for the reviewed operator tool (2026-10-19)

**Status:** ACCEPTED (owner, 2026-10-19 16:26, relayed by Hermes: "tôi thấy cứ làm theo đề xuất" - approving the
recommendation to lift the gate as the architecture reviewer proposed).

1. **What is lifted.** D-054's gate blocked every runtime path that marks an incarnation deleted until (a) each deletion
   is journaled outside the database as it happens and (b) the owner-table deletion exists and is replayed after a
   restore. Both are built and passed independent architecture review (PR #380, the tool; PR #386, the journal and
   the replay; `docs/reviews/architecture/ACCOUNT_DELETION_TOOL_REVIEW_2026-10-19.md`). Exactly one module may now
   write a deleted status: `writing_coach/persistence/account_deletion.py`.
2. **How it is used.** `scripts/account_deletion.py` is a dry run by default; `--apply` deletes one account in one
   transaction and requires the journal (`ORENA_DELETION_LOG`, off the database's volume, copied off-host with the
   backups). After any restore, `runtime_backup.py suppress --log` replays every logged deletion before serving.
   `docs/project/ACCOUNT_DELETION_RUNBOOK.md` is the procedure.
3. **Still a human step.** The first real deletion on a public runtime is announced to Hermes and the owner first;
   every deletion answers a learner's request within the 30 days the public page promises.
4. **Payment records are kept.** The schema keeps billing and credit history append-only; the tool keeps them, and
   the public deletion page says so ("Payment and billing records are kept as required for accounting and legal
   purposes", owner, same decision).

**Not in this decision.** Re-registration (D-055) stays closed: nothing may call `mark_deleted`, `register_new` or
`_allocate` outside the repository. No runtime deletion path for learners (the tool is the operator's). No schema change.

## D-242 - Deploy dependencies are pinned with a constraints file (2026-10-19)

**Status:** ACCEPTED (Hermes for the owner, 2026-10-19 17:12).

1. **Decision.** `constraints.txt` pins the full resolved dependency set of `requirements.txt` exactly (FastAPI 0.147.0,
   the version CI passed on after #398). The Dockerfile and the `python-gates` and `pytest` CI jobs install with
   `-c constraints.txt`, so the image that passes on :8000 is rebuilt identically for the VPS and CI tests what ships.
2. **Guard.** `scripts/validate_constraints.py` runs in `python-gates` and fails when a `requirements.txt` package is
   not pinned. `requirements.txt` keeps its ranges as the intent; the constraints file is the resolved truth.
3. **Updating.** Only by a reviewed PR that changes the pins alone (`docs/project/CI_FAST_PATH.md`).

**Not in this decision.** No hashes, no change to the application code or the Python version.

**Exception (2026-10-20, PR #448 "BW", #446; independent review and coordinator):** the new `tzdata==2026.5` pin lands
with its root-cause fix rather than in a pins-only PR. `GET /api/learner-activity` refused the `Asia/Saigon` that iOS
reports (422), because python:3.12-slim (Debian bookworm) ships the legacy zone names only in `tzdata-legacy`; the
`tzdata` package, added to `requirements.txt` in the same PR, is that fix. No existing pin changed. Point 3 stands for
every other pin change.

## D-243 - Import has one way in: the design's Create lesson card (2026-10-19)

**Status:** ACCEPTED (explicit owner instruction, 2026-10-19: "phần import trong learner app — tôi đã đưa thiết kế và
bạn cũng đã làm rồi mà sao giờ vẫn giữ cái nút import cũ"). The number is assigned at merge.

1. **Supersedes D-167 points 6-8.** The pinned design (`Orena.dc.html`, 2026-10-15 pin) draws exactly one entry to the
   Import sheet: Discover's "Create lesson" card (and the sheet's own Back to its type step). Today, My Library and the
   Discover overview draw no import control. The old entries are deleted, with their code (Design Contract rule 44):
   Today's featured import card, My Library's header "+ Import", the Discover All overview's always-drawn Imported
   section with its "+ Import" call to action, the kit `vipButton` and its rainbow `.o-btn--vip` CSS (the D-147 exception
   of D-167 point 7 ends with it), and their words (`shell.importAction`, `today.importValue`, `discover.importAction`,
   `discover.importCta`).
2. **Discover All.** Imported is a section like the others: left out when nothing is imported. A learner with nothing at
   all sees the page's empty state, with the Create lesson card above it.
3. **My Library's head is the design's:** the title and its one muted line ("Everything you've saved, met, or need to come
   back to.", en/vi/zh).
4. **Unchanged.** The Create lesson card (including its practice-chooser variant, CL-7), the Import sheet, its steps and the
   recorded gaps CL-1 to CL-7. The practice choosers keep the card per CL-7.
5. **Gate.** `scripts/test_orena_screen_discover.mjs` refuses every old entry, control and string, and asserts Discover is the
   only screen that opens the import flow.

## D-244 - Orena does not download YouTube audio for speech recognition (2026-10-19)

**Status:** ACCEPTED (Hermes for the owner, 2026-10-19, after the PRE-201 rights recheck).

1. **Decision.** From now on Orena never downloads a YouTube video's audio to run speech recognition. A new YouTube video
   is transcribed only from captions the provider offers through the existing caption path (YouTube's own track, or
   Supadata in native mode, D-215). A Creative Commons licence does not by itself open the audio route: listening to a CC
   video would need its licence and the provider's terms to allow the download, and that is a separate owner decision.
   Nothing in this change downloads audio for a CC video.
2. **Where it is enforced.** `MediaPipeline._transcript` (`writing_coach/media_transcript_pipeline.py`): for a YouTube
   item whose captions are absent or unusable, every transcript policy now stops before any audio download, recognition
   or spend. `captions_or_asr` (D-214) keeps its meaning only for sources with no caption track. Reasons: no track, or a
   track too poor to use, is `youtube_no_channel_captions` ("YouTube video without channel captions: Orena does not
   download YouTube audio (rights decision 2026-10-19)"; admin copy en/vi/zh, `impErr_youtube_no_channel_captions`), with
   the caption cause as its language-neutral detail; a caption fetch the provider refused this time keeps
   `captions_unavailable`, and the daily caption cap keeps `caption_quota`. A reprocess of an existing YouTube item obeys
   the same rule and restores the stored transcript. `captions_blocked` is no longer produced.
3. **Still allowed.** Speech recognition of a file the learner or admin uploaded, and of a non-YouTube source whose rights
   allow it, is unchanged.
4. **Provenance.** Every newly stored transcript records `transcript_provenance` beside `transcript_origin` (in the lesson
   payload and in `processing`, shown as `transcript.provenance` in the admin outcome): `channel_captions` (a track a
   person made, `caption_kind` manual), `machine_captions` (the provider's generated track, `auto`),
   `captions_unknown_kind`, or `orena_asr`. For an item stored before this, the admin outcome derives it from the origin
   and caption kind.
5. **Existing transcripts.** The 17 Chinese YouTube transcripts made by speech recognition before this decision are
   accepted for the pilot only. They must be reviewed (kept on a recorded basis, re-sourced from captions, or withdrawn)
   before G-6.

**Not in this decision (owner decisions left open).** The model-clip cut (D-140, `_prepare_model_clips` and
`scripts/backfill_model_clips.py`) still downloads a published YouTube item's audio to cut Compare clips; it runs no
speech recognition. The older learner route `POST /api/media/import` can still start Supadata `mode=generate` (a
provider-side transcript) where plan limits are not enforced. Both fall outside "audio for speech recognition by Orena"
as decided here and are reported for a decision rather than changed.

**Amendment 2026-10-20 (Hermes for the owner; #418): for YouTube, only the captions the channel already provides.** The
two items left open above are decided.
1. **Model clips.** A YouTube item gets no model clips, and its audio is never downloaded for them. Readiness
   (`MediaPipeline._prepare_model_clips`) and the backfill (`writing_coach/model_clip_backfill.py`,
   `scripts/backfill_model_clips.py`) skip it with the reason `youtube_no_audio_download (D-244)`: a skip, never an
   error. The backfill report counts it under `skipped` with the reason on the item; the admin outcome carries it as
   `model_clips_skipped`. Uploads and other allowed sources are cut as before. Compare reads a missing clip as it
   always has (its model plot is unavailable); no learner UI changes.
2. **Supadata.** `mode=generate`, and `auto` (which may generate), are never requested for a YouTube URL, under any
   plan or policy. `SupadataTranscriptClient` refuses them before any request (`SupadataYouTubeGenerationRefused`) and
   defaults to `native`; the YouTube adapter's inline fallback and the older learner route's fallback service
   (`POST /api/media-learning/import`) ask in native mode only. A YouTube video with no channel captions there ends
   as `youtube_no_channel_captions` (the admin reason D-244 already defines). The live learner route
   (`POST /api/media-learning/source`, and `GET /api/media/my/{id}` while it is polled) now answers a failed item with
   that reason as `import_job.failure_kind` too, so the Import sheet says it in its existing error slot
   (`error_youtube_no_channel_captions`, en/vi/zh) on either route. A non-YouTube source keeps its fallback.

## D-245 - The six built-in sample Listening lessons are retired; the built-in catalogue is empty (2026-10-20)

**Status:** ACCEPTED (explicit owner instruction, typed 2026-10-20: remove the original sample lessons like "A pen in my
bag" and the similar Chinese ones, they have no real learning value; extended the same day to "The cosmic calendar" and
怎么搜索维基百科). The number is assigned at merge.

1. **Retired.** `en-daily-pen-in-my-bag`, `zh-daily-what-is-this`, `zh-culture-nationalities`,
   `zh-culture-where-are-you-from`, `en-science-cosmic-calendar` and `zh-technology-search-wikipedia` leave
   `writing_coach/content/listening_catalog.v1.json`, with their five Wikimedia Commons sources. The manifest keeps
   `schema_version` 1 with empty `sources` and `lessons`, which the loader already accepts. No media or illustration
   file was bundled for them (playback streams from Commons), so no asset is deleted.
2. **Learner data stays.** No row is deleted and no migration runs. A progress row, saved place, take, annotation or
   content-visibility row that names a retired id stays in place and resolves as a lesson that is not on the shelf
   already does (D-203): absent from every list, `404` when opened (`/api/listening/library/{id}`,
   `/api/speaking/model-audio/{id}/...`), nothing resolved by the progress and collection resolvers, never a 500. A
   saved Continue entry that names one opens the router's existing "gone" page.
3. **Zero built-in lessons is a valid state.** Listening, Discover and Today show no catalogue section (or their existing
   empty state); the Speaking library carries only its authored items; word clips, the model-clip backfill
   (`include_catalog`), agent suggestions and the licences page read an empty list. Media an administrator imports
   still fills the same library.
4. **Tests.** Tests that exercised catalogue lessons run on a fixture-local copy of the retired manifest
   (`tests/fixtures/listening_catalog.fixture.v1.json`, loaded by the `fixture_listening_catalog` fixture in
   `conftest.py`) with their assertions unchanged; `tests/test_listening_catalog_empty.py` pins the empty shipped
   catalogue and the graceful lookups. The catalogue-reading Node gates check the fixture beside the shipped manifest.
   Tombstone: `LEGACY_TOMBSTONES.md`, "The built-in sample Listening lessons".

## D-246 - An EN->VI dictionary pack from the English Wiktionary's Vietnamese translations (2026-10-20)

**Status:** ACCEPTED (Hermes for the owner, 2026-10-20, on the evaluation
`ORENA_PRE_MARKET_EVIDENCE/EN_VI_DICTIONARY_PACK_EVALUATION_2026-10-20.md`, candidate 1a). The number is assigned at merge.

1. **Source.** The English Wiktionary's Vietnamese translation tables (`lang_code` `vi`) of its English entries, as
   extracted by Wiktextract and published by kaikki.org in its per-language English file
   (`kaikki.org-dictionary-English.jsonl.gz`, extraction of 2026-10-03 from the enwiktionary dump of 2026-09-02; the
   input's SHA-256 is in the pack index). Vietnamese Wiktionary and the Hồ Ngọc Đức / FVDP dictionary are **not** used
   (GPL data and informal relicensing); a word the pack lacks falls through to the next layer of the word tap (local
   translation, then the `word_translation` seam and its cache).
2. **Licence and the share-alike boundary.** CC BY-SA 4.0 (the GFDL side is not used), the same model already accepted
   for CC-CEDICT: the pack, and any adaptation of it, stays CC BY-SA 4.0 and ships with its licence text, provenance
   and modification notice (`writing_coach/languages/english/vi_lexicon_data/`). The share-alike reaches that data only;
   Orena's code and its other data files are separate works. Attribution ("Wiktionary contributors; extraction by Tatu
   Ylonen's Wiktextract (kaikki.org)") is shown where CC-CEDICT's is: the learner Licences and data sources page
   (`writing_coach/licences.py`, id `wiktionary-en-vi`), `THIRD_PARTY_NOTICES.md`, the pack's README and its index
   `sources` record.
3. **Scope.** The full set, not a subset by level: 16,660 headwords, 20,239 senses, 29,271 Vietnamese translations,
   0.65 MB packed (CC-CEDICT's pack is 5.5 MB). Each Vietnamese translation keeps the English sense label of its
   table. Vietnamese text is trimmed, NFC, de-duplicated, and dropped when empty or not in Vietnamese orthography.
   On the evaluation's 30-word B1-B2 sample it covers 27 (missing: launch, supply, solar).
4. **Use.** It is the vendored EN->VI pack of the bilingual pack seam (#423, `writing_coach/bilingual_dictionary.py`):
   catalogue -> pack -> local translation -> `word_translation`. A pack hit costs no AI call. The sense shown is the one
   whose part of speech matches the word's in its sentence (none of that class is a miss), then the one whose sense
   label shares words with the sentence, otherwise the common sense (senses are ordered by how many languages
   translate them). A registered or dropped-in pack for the pair still wins.
5. **Build and update.** `scripts/build_en_vi_pack.py --kaikki <file> --release <date>` streams the input (never loads
   it whole), is stdlib only and deterministic, and is also the update script; `--check` verifies the committed pack.
   The raw download stays outside the repository and is deleted after a build.
6. **The D-124 subset stays.** `writing_coach/localization_data/vi_glosses.json.gz` is not superseded: it also carries
   the Vietnamese Wiktionary data the vocabulary-localization sources read (`WiktionaryVietnameseSource`, and the zh->vi
   pivot through a chosen English sense), which this pack deliberately excludes. Those sources remain non-default, as
   D-124 left them; retiring that subset is a separate decision.

## D-247 - Automatic provider fallback for learner AI, never silent (2026-10-20)

**Status:** ACCEPTED (owner, Discord 2026-10-20 19:00 and 19:15, relayed by Hermes: "Không tự fallback được model
sao?" - "nên có cơ chế fallback qua các model khác để tiếp tục và có thông báo trong admin để biết"; DeepSeek and
OpenRouter approved as fallbacks 19:25).

**Why.** On :8000 the Gemini project hit its monthly spending cap; every Gemini call failed and Orena chat answered
"busy". The owner keeps the cap (no spend before publication) and wants learner AI to continue on another model.

1. **Amends the 2026-09-27 ruling** ("No provider-to-provider silent paid failover", line 148) and the matching
   `ARCHITECTURE_INVARIANTS.md` line: a learner AI call may fall back to a second provider. Never silently: every
   switch is recorded (`provider_switch` in the AI operation telemetry: from, to, reason, trigger), the shared breaker
   holds a failing provider down (PR BZ), and Admin shows which provider is down and why.
2. **Gates:** every rung passes funding and the system daily ceiling, and its cost is recorded in the AI ledger like
   any call. The agent's own cap and the per-learner quota are checked once per turn, at admission, so a fallback never
   charges the learner twice. The system's own ceiling is not a provider failure: it neither opens the breaker nor
   triggers a fallback.
3. **D-104 stands:** learner text never goes to a free tier or a provider that may log prompts. Both agent rungs pass
   the learner-text guard; a fallback that would break the rule is refused (`agent_fallback_route`, the Admin route).
4. **Orena chat (the agent):** the second rung is `agent.fallback_route` (Admin, `PUT /api/admin/agent/fallback-route`;
   else `AGENT_FALLBACK_ROUTE`). It is taken only before the first rung yields anything - a provider error at the
   start, or the breaker holding it down - so no learner sees half an answer from one model and the rest from another.
   Under G8 it is offered only when cleared for at least the first rung's data class.
5. **Structured capabilities** keep their own rules: a capability routed by the capability router uses its configured
   backup rung (Admin › AI); learner `generate_structured` on the legacy selection is unchanged by this entry.

**Not in this decision.** Raising any provider's spend cap (the owner's), new paid providers beyond those approved,
and a fallback after the first token.

## D-248 - Monetisation v2: VND plans, an exam pass, a no-card trial, content gating and server entitlement (2026-10-20)

**Status:** ACCEPTED (Hermes for the owner, 2026-10-20: "implement without further approval"). Basis:
`ORENA_PRE_MARKET_EVIDENCE/founder/STRATEGY_2026-10-20.md` and the UI-lane plan
`ORENA_PRE_MARKET_EVIDENCE/MONETISATION_V2_UI_PLAN_2026-10-20.md` (findings F1-F7, gaps G1-G12, PRs MV2-0..MV2-7). This is a product decision, not activation
authorization: prices, offers and checkout reach `:8000` only through the existing Billing gates (gate 7a/7b), and
every schema step named below stays a human gate.

1. **Plans and prices (VND).** Plan ids stay `free`, `plus`, `pro` (D-153).
   - **Plus** 79.000 a month or 690.000 a year. **Pro** 159.000 a month or 1.390.000 a year.
   - **Exam pass** 199.000 for 3 months, one payment, **not auto-renewing**. It is an offer that grants an existing
     plan for its period, not a fourth plan.
   - **Student price** 49.000 a month (Plus), verified by a student email; the verification rule and its store belong
     to Billing.
   - **Trial:** 7 days of Plus, no card, **one per Google account**. It is a server grant (`trialing`, `paid_through` =
     start + 7 days); the once-per-account record needs `promotional_grants` (proposed migration 0034), which is a
     human schema gate.
2. **Cost guard.** A hidden per-learner AI cost ceiling at **60% of the plan's net revenue** (after the gateway's and
   the merchant of record's fees and tax), and a **Free AI pool of USD 0.50 a day** across all Free learners. Neither
   figure is shown to learners; both reuse the existing cost telemetry (`ai_cost_records`, D-MON-007) and the quota
   admission. At the ceiling a paid learner's calls **degrade to an economy model, then refuse only at the hard
   ceiling** (with the existing quota responses).
3. **Payment.** **VietQR through SePay** for the exam pass, the yearly plans and Credits top-ups; **Polar (card)** for
   the monthly subscriptions. This supersedes:
   - the 9.99/79.99 (Plus) and 19.99/159.99 (Pro) USD prices of **D-MON-032** and **D-MON-038** (2) (gate 7b, C5);
   - D-MON-032's "only Polar sells plans": a yearly plan and the exam pass are sold as one-time prepaid periods on
     SePay (the D-MON-031 mechanism, at the new prices; D-MON-031's own prices stay withdrawn);
   - the VND figures above apply to the VietQR/SePay offers (exam pass, yearly plans, student price, top-ups);
   - the catalogue defaults of **D-153** (Plus 199.000/1.590.000, Pro 399.000/3.190.000).
   The Polar products and `billing/price_integrity.py` follow the new prices in the Billing lane.

   **OPEN, owned by the Billing lane (not resolved here):** Polar charges in USD only, and D-MON-005/015 require the
   price shown to equal the price charged (D-MON-034 shows plan prices in USD for that reason; Hermes' spec also says
   "USD only for Polar"). For the card/Polar monthly plans, either the displayed price is the USD amount Polar charges,
   or the monthly plan moves to VietQR. Until Billing records which, no VND price is shown for a Polar charge.
4. **Content gating** (the tier is computed on the server from rules, plus a bounded list of stored exceptions in
   `platform_settings`; no schema in phase 1). A **stored per-item tier column** (on `reading_articles`,
   `vocabulary_collections` or `grammar_points`, or a `content_access` table) is a **human schema gate**, like the
   trial record in §1: it may only be proposed (`migrations/proposed/`), with independent architecture review, never
   applied by an agent. This narrows D-MON-001's "generous Free core" for Reading and sets.
   - **Reading:** about **30% of each (language, level) is Free**, by a stable per-article bucket with a floor, plus
     **2 more articles a week free on rotation** (deterministic per ISO week). The rest is Plus. Title, cover and the
     first paragraph of a locked article stay visible.
   - **YouTube and other media:** watching and **the channel's own captions stay free for every plan, unlimited**. Only
     Orena's learning tools around the player are gated (Free: tap-to-look-up on 3 videos a week; Plus: full
     translation, scored shadowing, dictation, save to review). Basis: YouTube API Services Developer Policies
     **III.F.3.a** ("API Clients must not charge users to watch content in an embedded YouTube player") and the
     Developer Policies Guide ("You also cannot charge people a fee for services that are offered free of charge on
     YouTube"). So: the player is never blocked, YouTube's captions are never paid, no paywall, lock or sheet is drawn
     over the player, no Plus/Pro badge sits on a YouTube item's card or cover, and the offer is marketed as tools,
     never as access to videos.
   - **Sets (vocabulary collections, grammar functions):** the **first item of each set is Free**; the rest is Plus. A
     learner's own decks are never gated. Mock tests are deferred until they exist.
5. **Badges and frames.** A Plus/Pro corner badge is Pricing's tag pill. A tier frame is a **fill, never an outline**
   (**D-147**): the edge stays `--edge-light`; Plus is a `--spark-soft` wash and Pro an `--accent-soft` wash (plan G2).
   The locked state uses the design's lock-in-a-well (Lucide `lock`); the upgrade sheet is built from the Coming-soon
   sheet shape (plan G4).
6. **Server entitlement.** Every route that returns a gated body checks the plan on the server and answers **`403
   plan_required`** with `{content_kind, content_id, required_plan, plan, upgrade, trial_available, preview}`. The client
   never computes a tier. The check fails closed (an unreadable plan is 503, never an upgrade prompt), an unpublished id
   is still 404 before any 403, and a gated body is never publicly cacheable (`Cache-Control: private`; plan F6).
7. **Conflicts, resolved.**
   - **NC content: D-189 wins.** D-189 §2 says NonCommercial sources are never published into the commercial or paid
     catalogue. Orena's Free tier is part of a commercial service, so an NC item is **removed (unpublished)**, not kept
     Free. It may stay only with the publisher's written permission. An item whose rights are unclear is not gateable
     and goes to the Admin review queue. Audit: `ORENA_PRE_MARKET_EVIDENCE/MV2_NC_AUDIT_8000_2026-10-20.md`.
   - **Pricing copy:** the Pricing frame's line "Every plan includes all reading, listening, speaking, writing and review
     practice. Plans differ in how much Orena can analyse for you." is rewritten to match this decision (in EN, VI and
     ZH). Recorded in `UI_BACKEND_GAPS.md`.
8. **Open for counsel (before paid launch).** Storing captions fetched through Supadata (native mode) indefinitely cuts
   against YouTube API Services Developer Policies **III.E.6** (no scraping, directly or indirectly) and **III.E.4.c**
   (stored data deleted or refreshed after 30 days). Monetising raises the stakes. It is an owner/counsel gate; it does
   not block the UI work.
9. **Voice minutes, the weekly report and contract v14 (MV2-6a, UI lane, 2026-10-21).** The plan catalogue's
   `orena.voice` meter is **monthly** (it was daily under D-237): Plus 6000 s (about 100 minutes) and Pro 18000 s a month
   by the code's defaults, Free off; an administrator still edits them. A stored limit under a minute (the D-236
   placeholder) now reads as the plan's default in the catalogue itself, so Admin's editor has no constant of its own. A
   save records the window each limit was set for; a stored limit set under another window than the meter's current one
   (a document without one counts as `day` for voice) does not apply - the code's default does, the Admin view names it, and
   an operator re-saves. Stored data is never migrated (review of #477, P1). A new
   on/off plan feature, **`progress.weekly_report`**, is off for Free and on for Plus and Pro. Every client line about
   voice minutes reads the window from the data ("this month" / "today", EN/VI/ZH). Agent Contract **v14** records, as
   implemented on `main`, `GET /api/agent/voice/allowance` (#469), `GET /api/agent/progress/weekly` (#471, #476) and the
   administrators-only, experimental `POST /api/agent/band/writing` (#470, future entitlement `band.estimate`). The
   Intelligence lane counts voice seconds over the meter's window with `resets_at` on the 1st (#478); the server's 403
   `feature_not_in_plan` for `progress.weekly_report` is left to it.
10. **Amendment 2026-10-21 (MV2-5): the Free review limit.** The founder's spec (`founder/MONETIZATION_V2_SPEC.md`,
   Hermes' Monetisation v2, relayed from the owner) gives Free "Tra từ nghĩa Việt; ôn tập tối đa 30 từ; 5 lượt AI
   coach/ngày"; this decision omitted the review limit, and the coordinator directed it built (review of #485). A Free
   learner's active review holds at most **30 words** (policy `access.free_review_words`, Admin › Policies): their
   earliest saved words. Every other saved word is **kept, never deleted**, still listed and looked up, and enters review
   when the plan reaches Plus. Grading a word outside the window is 403 `plan_required`; the review reads say
   `review_limit {limit, saved, held}` and the Review room shows the quota notice with "See all plans". Like every MV2
   gate it applies only while `access.enforced` is on. In the same review, a word kept from a vocabulary set is a set item:
   a save naming a set the plan does not reach is 403 `plan_required` (a save naming no set is a free, non-set save), and keeping a word never unlocks its set's card.

Design gaps G1-G12 are recorded in `docs/project/UI_BACKEND_GAPS.md` ("Monetisation v2").

## D-249 - A daily voice sub-cap under the monthly voice minutes (2026-10-21)

**Status:** ACCEPTED (Hermes for the owner, 2026-10-21 04:20). Basis: `ORENA_PRE_MARKET_EVIDENCE/COST_PRE402_403.md` §7.

**Why.** D-248 (MV2-6a, #477) moved the voice cap from 15 minutes a day (D-237) to a month: Plus 6000 s, Pro 18000 s. With
no daily cap, one Pro learner could talk for five hours in a day, at the measured voice cost about $3.75 (mean) to $9.15
(p95). That is more than the system's daily AI ceiling on :8000 ($2, alert at 80%), which then pauses paid AI for every
learner until UTC midnight.

1. **Two caps, both counted.** Each learner's voice seconds are capped per month (the `orena.voice` limit) **and** per UTC
   day (`daily_seconds`). A session may use the smaller of what is left in each. Tokens are clamped to it.
2. **Defaults:** Plus 1200 s (20 minutes) a day, Pro 1800 s (30 minutes; about $0.38 to $0.92 at p95). Free has no
   voice; its stored figure (1200) only gives an editor a number if voice is ever turned on.
3. **Editable in Admin › Plans.** Both are per plan:
   - the monthly cap is the `orena.voice` limit;
   - the daily cap is the entitlement's `daily_seconds` parameter, an integer from 60 to 86400.

   A saved catalogue without `daily_seconds` uses the code's default.
4. **Refusal.** At either cap the learner gets 429 `quota_exhausted` (`feature: "orena.voice"`).
   - `context.window` is `"day"` or `"month"`; `resets_at` is the next UTC midnight or the 1st of next month. When both
     caps are used up, the month is reported, as it is the longer wait.
   - A daily total that cannot be read is answered 503 (fail closed).
5. **Energy bar.** `GET /api/agent/voice/allowance` adds:
   - `daily: {limit, used, left, resets_at}`, or `null` when there is no daily cap;
   - `available`, what a new session may use now.

   The window fields are unchanged.
6. **Variables.**
   - `catalog.VOICE_SECONDS_PER_MONTH` and `catalog.VOICE_SECONDS_PER_DAY`: the defaults.
   - `catalog.METERS["orena.voice"].params["daily_seconds"]`: the bounds, 60 to 86400.
   - `plan_features.DAILY`: the parameter's name.
   - The daily total is read from `product_repository.daily_usage` (UTC day); the month from `monthly_usage`.

## D-250 - Reading publishes only clear rights; the D-190 override is withdrawn (2026-10-21)

**Status:** ACCEPTED (Hermes for the owner, 2026-10-21 05:40: PRE-203 "SIẾT" - Reading is not published while its
rights are not cleared, with no override). Amends **D-190** (and D-189's "the admin can always publish"); restores
D-105's hard gate for articles.

1. **No override.** An article is published only when `reading_rights_gate.rights_blockers` is empty:
   - republish `allowed`;
   - for an adapted text, adapt `allowed`;
   - where attribution is required, a complete credit;
   - the attribution question answered.

   `acknowledge_warnings` no longer overrides anything. The route still accepts the field, ignored, so a client that
   sends it is not refused 422 before the UI lane removes it.
2. **Refusal.**
   - The admin route answers 409 `reading_rights_not_cleared` with `context.blockers`; `override_fields` lists only
     `quality_override`.
   - The repository refuses too (`RightsRefused`), so a script or harness that publishes directly is stopped.
   - Order: thumbnail (D-240), then quality (D-191, which keeps its own reasoned override), then rights.
3. **Records.**
   - Nothing is recorded as "published over warnings" any more.
   - The publish audit keeps `rights_basis` and drops `warnings` and `acknowledged_warnings`.
   - `publication_warnings` in the response is always `[]`.
4. **Nothing published is taken down by this gate.** `scripts/check_published_reading_rights_gate.py` (read-only) lists
   every published article the gate would refuse now, and whether it went out over D-190's warnings. What to do with
   each is a human decision.
5. **Books are not covered here.** Their rights fields and publish gate need a schema change, proposed separately (a
   human gate).

## D-251 - No app-wide AI cap: a daily AI cost cap per learner, by plan; the system total is a monitor (2026-10-21)

**Status:** ACCEPTED (the owner, typed in the UI-lane terminal, 2026-10-21). His words, verbatim:

> "không có trần chung cho app, chỉ có trần cho từng người dùng theo gói. chứ khóa vậy thì nhiều người dùng hơn thì lại
> bị hạn chế thì sao? pilot cũng hoạt động giống với product đừng làm mọi thứ chỉ để test. pilot là pilot bản product"

(There is no app-wide cap; limits apply only per learner, by plan. A shared lock would restrict everyone as the number
of learners grows. The pilot behaves exactly like production; nothing is configured just for testing.)

**Supersedes:** the system-wide fail-closed daily AI spend ceiling (owner 2026-10-18, D-232 / D-235's
`X-Orena-AI-Paused`, and PRE-502 R2's "production refuses to start without a ceiling" in the form that ceiling had), and
D-248 point 2's "Free AI pool of USD 0.50 a day across all Free learners" (never implemented; it is withdrawn, not
built). D-248 point 2's hidden per-learner ceiling stands and is implemented here.

1. **No mechanism pauses AI for every learner because of the whole system's spend.** The system total
   (`AI_DAILY_SPEND_CEILING_USD`, Admin `ai.daily_spend_ceiling_usd`, warning at `ai.daily_spend_warn_ratio`) is a
   **monitor**: it is still computed from the whole AI ledger, it logs the warning at the ratio and, at the threshold,
   raises a high-severity alert in the log, the provider health signal (`ai/health_signal.py`, the :8000 health.log line,
   #452) and Admin's overview banner. It never refuses a request. `X-Orena-AI-Paused` is no longer sent, and the
   `daily_ai_limit` refusal with `scope: "system"` is no longer sent; the category stays listed in the Agent Contract.
2. **Each learner has a daily AI cost cap by plan** (`ai/learner_cost.py`), counted from the per-account ledger that
   already exists (`ai_cost_records`, AC-2) - no new table, no schema change. A provider whose free-tier flag is on
   costs nothing and is not counted. Defaults, policies in Admin > Policies > Spend caps:
   - Free USD 0.02 a day (`ai.learner_cost.daily_usd_free`);
   - Plus and Pro: 60% of the monthly price over 30 days at `ai.learner_cost.vnd_per_usd` (assumed 26,000 VND a dollar)
     and `ai.learner_cost.revenue_share` (0.6): Plus 79.000 d -> about USD 0.061, Pro 159.000 d -> about USD 0.122, until
     an administrator stores a USD figure. D-248 says "net revenue"; the list price is used until net is known.
3. **Degrade, then refuse** (D-248's own order). At the cap a learner's paid calls go to the economy model
   (`ai.learner_cost.economy_model`, default `gemini/gemini-3.1-flash-lite`); free and local rungs run as before. At the
   hard ceiling (the cap x `ai.learner_cost.hard_ratio`, 1.5) only free and local models answer that learner until UTC
   midnight; a request with nothing else is the existing 429 `quota_exhausted` (`feature: "ai.daily_cost"`, `window:
   "day"`, `resets_at`; a Free learner also gets `upgrade`). No figure is shown (D-248: hidden). Zero-cost paths are never
   capped. A fault (an unreadable per-account ledger) degrades that learner and refuses nobody; an unreadable plan takes
   the Free cap.
4. **The per-capability daily caps** (`word_translation`, `word_sense_choice`, and the routed backups of
   `writing_evaluator`, `writing_improver`, `text_discussion`) measure **the request's own learner**. Work with no
   signed-in account (a background job) is not a learner and is still measured over the capability.
5. **The pilot runs as production.** Every public runtime (staging and production) refuses to start unless every plan's
   per-learner cap resolves above zero (and the hard ratio is at least 1) **and** the monitor's threshold is set in the
   environment (PRE-502 R2, restated). It stays impossible to run with no per-learner limit.
6. **Left to their owners.** The agent's own cap (`agent.daily_spend_cap_usd`, `agent/budget.py`) and the `daily_ai_limit`
   path of `agent/api.py` belong to the Intelligence lane, which makes them per learner with
   `learner_cost.learner_cost_state(user_key)` (`ok` | `degrade` | `refuse`, and `.economy`). The media pipeline's day
   cap (`media.daily_cap_usd`) and Supadata's daily request count are operator-pipeline and provider-credit limits, and
   word audio's lifetime cap falls back to the free voice; each is reported to the owner, not changed here.
7. **Published text.** No published legal document (docs/legal/public) promises a system spend ceiling; none changes.
8. **What a learner's total counts** (independent review of #487, CHANGES REQUESTED, and Hermes for the owner):
   - priced calls only. A call without a price counts **0** for the learner, never an allowance, and raises one monitor
     alert a day ("unpriced provider in use"). The system monitor still counts it at its 0.01 USD allowance. An accounting
     gap never throttles a learner.
   - no local model (`ollama`, cost 0) and no free-tier provider.
   - no feature with its own plan meter: `agent_voice` (voice minutes, D-249), `pronunciation_evaluator` (pronunciation
     minutes), `speech_asr` (the daily recognition brake), `word_tts` (`audio.tts`). They stay in the system monitor.
   - calls in flight: each paid rung reserves its list-price estimate until it returns. Cost rows the per-account recorder
     could not write are kept, retried and counted meanwhile (an ALERT is logged; nothing is dropped silently).
   - system costs (no signed-in account, an administrator's own runs) reach the monitor only, never a learner cap.
   - a public runtime also refuses to start when the per-account ledger is not wired and readable.
9. **Recorded gap: Ollama Cloud has no confirmed per-token price.** It is credits-based and publishes none (#454 review),
   so no number is invented: its rows are `unpriced`, count 0 in a learner's cap (a Free learner calling it 20 times is
   never degraded or refused, `tests/test_learner_cost_cap.py`) and count the allowance in the system monitor. When the
   owner confirms a price or a covered-credit rate, it is added to `ai/pricing.py` and is then counted.
