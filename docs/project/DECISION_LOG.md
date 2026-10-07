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
