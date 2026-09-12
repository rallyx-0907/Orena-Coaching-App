# Domain Boundaries

These are conceptual bounded domains for coordinated multi-agent work. Folder
layout is evidence but not the sole definition of ownership; the current
repository does not map every domain perfectly to one directory.

An agent should stay within its assigned domain unless it explicitly declares
a cross-domain dependency.

## 1. Identity & Account

Owns authentication integration, account identity, sessions, roles, platform
administrator authorization, and account lifecycle boundaries. It does not own
learning evaluation or AI provider selection.

## 2. Learning Domain

Owns learner-facing pedagogy, evidence, practice, progress, and language-aware
learning behavior.

Subdomains:

- Writing
- Speaking
- Reading
- Listening
- Grammar
- Vocabulary / Library
- Media Learning (shared)
- Learning Memory / Progress

Shared flows apply to EN and ZH. Language-specific adapters are limited to
genuine linguistic behavior. Learning data that is conceptually scoped to a
language remains isolated by user and learning language.

### Shared Media Learning boundary

Media Learning owns reusable media-source metadata, source-language
transcripts, timestamped segment identity, and support-language translations.
It serves Listening, Speaking Shadowing, Vocabulary / Library, and Grammar so
those subdomains do not independently ingest or represent the same external
media.

Shared media content is provider-neutral and learner-neutral. Listening
progress, Shadowing attempts, saved vocabulary, learned segments, and exercise
outcomes remain outside this boundary and stay scoped to the user and learning
language. Provider adapters, acquisition, AI transcription or translation,
learner progress, and feature UI are not implied by this foundational boundary.
Chinese Pinyin may be added later through a language adapter; it is not the
canonical original transcript.

### Shared Language Knowledge / Understanding boundary

The Understanding Engine and Language Knowledge Graph
(`docs/product/ORENA_UNDERSTANDING_ENGINE.md`) are shared the same way Media
Learning is shared: Reading, Listening, Speaking, Writing, Grammar, and
Vocabulary / Library consume one explanation capability and one knowledge
layer rather than each building its own. Vocabulary / Library's canonical
learning-object model (the Orena Vocabulary Card) is defined in
`docs/product/ORENA_VOCABULARY_ARCHITECTURE.md`; orthography/stroke-order is
part of that model, not a separate subdomain.

## 3. AI Platform

Owns:

- provider adapters;
- AI capability catalog;
- capability configuration;
- AI routing;
- AI diagnostics and admin control plane.

Does not own:

- Social;
- generic identity and account behavior;
- deterministic non-AI learning logic unless directly required by an AI
  integration boundary.

The AI Platform must not invent per-language capability IDs for shared
workloads. Credentials remain server-managed and outside persisted capability
configuration and diagnostics.

## 4. Social Domain — FUTURE

Future conceptual ownership:

- Rooms
- Friends
- Messaging
- Presence
- Reactions
- Blocking
- Moderation

Social is not implemented merely because this boundary is documented. It is
not an AI capability. AI may assist future Social functions, but core Social
must continue when AI is unavailable.

## 5. Notifications — FUTURE / SHARED

Owns future notification intent, delivery policy, and user preferences across
domains. Domain events may request notifications, but delivery concerns should
not be embedded independently in every domain. No implementation is implied by
this document.

## 6. Platform Infrastructure

Owns shared technical infrastructure:

- PostgreSQL and repository/runtime infrastructure;
- jobs and background execution;
- realtime transport;
- observability;
- deployment and hosting infrastructure.

This domain provides infrastructure contracts without absorbing product-domain
business rules.

## Cross-domain change protocol

Before changing another domain, an agent must:

1. identify the cross-domain dependency;
2. list files outside its owned domain;
3. explain why the dependency cannot be handled within the owning domain;
4. minimize the external changes;
5. run regression tests for both domains;
6. update `CURRENT_HANDOFF.md` if task responsibility moves between agents.

Cross-domain persistence, authentication, deployment, frontend, or release
changes may also cross a human gate. A folder name alone does not grant domain
ownership or authorization.
