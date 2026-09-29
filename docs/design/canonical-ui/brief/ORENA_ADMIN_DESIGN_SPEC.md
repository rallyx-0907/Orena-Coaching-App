# Orena Platform Admin — Complete Design Specification

**Version:** 2026-09-26  
**Purpose:** self-contained UI/UX specification for the Orena Platform Admin design project.  
**Coverage source:** current behavior/capabilities audited from `admin/control-center`, plus the previously approved Admin product scope.  
**Audience:** UI/UX design agent. The design agent is not expected to read Git, backend code, API docs, or prior conversations.

---

# 0. Core contract

This document is the design source for **Platform Admin**.

There are two independent sources of truth:

- **The approved new Orena prototype owns presentation.**
- **This Admin specification owns Admin capability, behavior, information architecture, states, and operator flows.**

The current/legacy Admin UI must **not** be treated as the visual target. It is useful only as evidence of currently supported behavior.

The new Admin must use the **same visual system as the newly approved Orena prototype**, adapted for operator tooling:

- same typography family and visual language;
- same color/surface system;
- same button/input/icon language;
- same light/dark design logic;
- same overall polish and commercial quality;
- but higher information density than the learner app;
- less decorative artwork;
- stronger scanability, status visibility and operational hierarchy.

Do not copy the old dark-violet Admin appearance simply because it existed before.

## Design principle

> **Prototype owns presentation. Admin spec owns capability and behavior.**

A capability described as **WORKING** must have complete usable UI.

A capability described as **DEFERRED / FUTURE** may be represented when needed to preserve the intended product shape, but it must look unavailable/future and must not pretend to work.

Internal implementation details that do not help an operator **understand, decide, act, or recover** do not need UI.

---

# 1. Product role

Platform Admin is an operational control center inside Orena, visible only to authorized Admin users.

It is **not** part of the learner navigation and must use its own Admin shell.

The Admin must let an operator:

- understand whether Orena is healthy;
- see what requires attention;
- inspect users and learning activity at an appropriate aggregate level;
- configure and test AI providers/models/capability routes;
- manage Books, Media, Vocabulary and Reading content;
- import new content;
- review and publish Reading content;
- manage Reading sources;
- review generated Reading comprehension sets/questions;
- inspect import and processing jobs;
- retry recoverable failures;
- inspect runtime, workers, queues and operational failures;
- access future controls without confusing them with working controls.

Admin must remain an **operator tool**, not a marketing dashboard and not a learner-facing experience.

---

# 2. Admin information architecture

Keep exactly six top-level Admin areas:

1. **Overview**
2. **AI & Models**
3. **Users**
4. **Content**
5. **Imports**
6. **Operations**

Do not create Reading as a seventh top-level section. Reading lives inside **Content**.

Do not create Practice Generator as a new Admin app. It lives inside **Content**.

## Global Admin flow

```text
ADMIN ENTRY
→ OVERVIEW

OVERVIEW
├─ Needs Attention → exact problem area
├─ AI issue → AI & Models
├─ content waiting → Content / relevant queue
├─ failed import → Imports / Job Detail
└─ worker/runtime issue → Operations

AI & MODELS
├─ Providers
│  ├─ Configure / Update Credential
│  ├─ Test
│  ├─ Detail
│  └─ Remove Credential
└─ Capability Routing
   ├─ Primary Provider / Model
   ├─ Standby Provider / Model
   ├─ Enable / Disable
   ├─ Test primary / standby
   └─ Save

USERS
→ User List
→ User Detail

CONTENT
├─ All / Content Home
├─ Books
│  └─ Book Detail
├─ Media
│  └─ Media Detail
├─ Vocabulary
│  └─ Vocabulary Detail
├─ Reading
│  ├─ Overview
│  ├─ Needs Review
│  │  └─ Review Detail
│  ├─ Published
│  ├─ Rejected
│  ├─ Archived
│  ├─ Sources
│  │  └─ Source Detail
│  ├─ Add Content
│  └─ Comprehension Sets / Question Review
└─ Practice Generator
   ├─ Home / Templates
   ├─ Setup / Editor
   ├─ Generated Samples
   └─ Review / Publish Version

IMPORTS
├─ Books
├─ Media
├─ Vocabulary
├─ Reading
├─ Sources
├─ Reading Jobs
└─ History

OPERATIONS
├─ Readiness / Runtime
├─ AI telemetry
├─ Learner-impact failures
├─ Reading engine / queues
├─ Workers
├─ Source polling
└─ Actionable errors / slow operations
```

---

# 3. A0 — Admin Shell

## Desktop

Admin uses a dedicated shell. Do not show the learner rail inside Admin.

Persistent Admin navigation contains:

- Overview
- AI & Models
- Users
- Content
- Imports
- Operations

Top utility area may include:

- environment/runtime status;
- current Admin account;
- contextual global status;
- **Back to Orena** / Back to learner app;
- global Admin search only when/if it becomes supported.

## Mobile

Must remain fully usable at ~390px width.

Use:

- compact Admin header;
- drawer or compact section switcher;
- full-screen detail views where desktop uses a drawer/split view;
- no horizontal page zoom.

## No-access state — WORKING

When a logged-in account does not have Admin access, show a dedicated no-access screen instead of exposing partial Admin UI.

It should clearly say:

- Admin access is required;
- current user cannot enter;
- action to return to learner Orena.

Do not show technical authorization implementation details.

---

# 4. Global progress tray — WORKING

Admin has a global processing/progress tray that persists across Admin sections.

It is especially important for Reading processing jobs created from Add Content.

Each active/recent item should communicate:

- what was submitted;
- current state;
- current processing stage;
- progress meaning;
- failure state when relevant;
- link/action to inspect job;
- automatic cleanup after finished jobs have remained visible long enough to be understood.

The tray must not disappear merely because the Admin navigates to another top-level section.

This is a global Admin component, not a Reading-only widget.

---

# 5. A1 — Overview

## Purpose

Answer immediately:

- Is the system healthy?
- What needs operator attention?
- Is content waiting for action?
- Are AI providers/capabilities degraded?
- Are imports/jobs/workers failing?

## Summary metrics

Show only from real data when available:

- Total users
- Active learners
- New users
- Published content
- Content waiting for review/action
- Failed imports/jobs
- AI health/readiness
- Worker/Reading engine health

## Needs Attention — highest priority region

Each row contains:

- issue/problem;
- severity/status;
- affected domain;
- relevant subject/provider/source when useful;
- time/recency;
- direct action/link.

Examples:

- AI provider test failed;
- Reading items waiting for review;
- import jobs failed;
- worker heartbeat stale;
- source/runtime unavailable.

Every issue must route to the **exact place where it can be inspected or acted on**.

## Summary visualizations

May include, where real data exists:

- registration trend;
- active learner trend;
- new vs returning learners;
- learning activity by domain;
- language profile distribution;
- content by type/language;
- AI success/failure;
- import/job status.

Overview is a summary, not a raw log viewer.

## States

- Loading
- No data
- Partial unavailable
- Service degraded
- Healthy

Do not hide an entire panel simply because one source of data is unavailable. Explain partial availability.

---

# 6. A2–A5 — AI & Models

## Purpose

Operate Orena's AI control plane:

- provider configuration;
- provider credentials;
- available model catalog;
- capability routing;
- primary and standby/fallback routes;
- health/testing;
- usage/failure telemetry.

## Provider list — WORKING

Each provider shows:

- provider name;
- Configured / Not configured / Not required state;
- connection state;
- model count where known;
- last test;
- health/readiness;
- credential source/state where useful.

Actions:

- Configure
- Update Credential
- Test Provider
- Open Detail
- Remove Credential

## Credential behavior — WORKING

Credentials are write-only.

After a key/secret is saved:

- never show the raw secret again;
- show a clear `Configured` state;
- Update replaces the stored secret;
- Remove is destructive and requires confirmation;
- removing a provider should communicate consequences to routes that depend on it;
- support a **verify-before-save** flow;
- type-to-confirm may be used for credential removal because of its operational impact.

## Provider Detail — WORKING

Show:

- status;
- endpoint/base URL when applicable;
- model catalog / available models;
- default model when applicable;
- credential state;
- last test;
- latency;
- recent success/failure;
- last error;
- usage when telemetry exists.

## Capability Routing — WORKING

Each capability row shows:

- capability name;
- enabled/disabled;
- implementation type/status;
- provider;
- primary model;
- standby/fallback provider and model where supported;
- health;
- average latency when telemetry exists;
- recent failures;
- request/usage evidence when available.

Capabilities may include:

- Translation
- Dictionary
- Writing Evaluation
- Reading Analysis
- Topic Classification
- Level Estimation
- Learning Target Extraction
- Adaptation
- Question Generation
- Speaking/feedback capabilities when routed through AI

Actions:

- edit route;
- change provider;
- change model;
- set standby;
- enable/disable;
- Test primary;
- Test standby;
- Save.

## Test states — WORKING

Provide explicit states:

- Testing
- Success
- Failure
- Not configured
- Model unavailable
- Provider unavailable

A test result may show:

- provider/model tested;
- latency;
- short validation output;
- expandable error/request detail when useful.

## Status semantics

These states must be visually distinct:

- **Configured** — credentials/config exist.
- **Operational** — system can route/use it.
- **Healthy** — recent evidence indicates success.
- **No data** — insufficient telemetry.
- **Failed / Degraded** — recent operational evidence shows a problem.

Never imply `Configured = Healthy`.

## Telemetry — WORKING WHEN DATA EXISTS

Can show:

- requests;
- success/failure rate;
- average latency;
- provider health;
- capability health;
- recent failures;
- model usage;
- tokens;
- cost;
- quota when real telemetry exposes it.

### Important limitation

P95 latency is **not currently available**. Current telemetry can expose an average/mean. If shown, label it honestly as average/mean.

**P95 = DEFERRED.**

---

# 7. A6–A7 — Users

## A6 User List — WORKING

Purpose: find and inspect accounts.

Show:

- Name
- Masked email
- Role
- Target language(s)
- Joined
- Last active
- Status
- Plan if available/relevant

Filters:

- Search
- Role
- Language
- Activity/status
- Plan if supported

Sorting:

- joined/newest;
- oldest;
- activity;
- name where useful.

Above/around the list, the Users area may show:

- total accounts;
- admins;
- new users 7d / 30d;
- active users 7d / 30d;
- new vs returning segments;
- registrations trend;
- active learner trend;
- language distribution.

## A7 User Detail — WORKING

Show:

- account identity;
- masked account info;
- role;
- status;
- plan when available;
- language profiles;
- goals/styles/support language;
- last activity;
- usage/activity summary;
- relevant learning evidence summary at an administrative aggregate level.

Do **not** surface private learner-authored content merely to fill a dashboard.

## User admin actions

Only expose actions that actually exist.

### Change role — DEFERRED

The current system reads and filters role but has no role-write endpoint.

If the design needs to show role management for future shape:

- show it disabled/unavailable;
- label the limitation;
- do not make it appear functional.

### Per-account 30-day sparkline in list — DEFERRED

The activity exists in detail, but a row-level 30-day series is not currently supported efficiently.

Do not fake it.

---

# 8. A8 — Content Home

## Purpose

One Admin library/control surface for Orena content.

Content domains:

- Books
- Media
- Vocabulary
- Reading
- Practice Generator

An `All` mode/filter may aggregate content where useful; it does not need to be a large tile if the prototype uses another pattern.

Each domain should surface counts/statuses relevant to operator action.

Reading should make waiting-for-review count visible.

Shared controls where relevant:

- Search
- Language
- Status
- Rights
- Sort

Do not turn every domain into an identical card wall. Use rows/tables/lists when scanability is better.

---

# 9. A9–A10 — Books

## Book List — WORKING

Show:

- cover;
- title;
- author;
- language;
- chapter count;
- word count;
- status;
- source/import context where useful.

Actions reflect actual lifecycle:

- Preview
- Archive
- Restore when archived

Do not invent Delete.

## Book Detail — WORKING

Show:

- cover;
- metadata;
- chapters;
- import/source info;
- status;
- learner availability;
- creation/import facts.

Actions:

- learner preview where possible;
- Archive / Restore according to state.

Archive/restore is lifecycle management, not deletion.

---

# 10. A11–A12 — Media

## Media List — WORKING

Show:

- thumbnail;
- title;
- provider/source;
- language;
- duration;
- transcript state;
- level/topic when available;
- status;
- issues such as missing transcript.

## Media Detail — WORKING

Show:

- metadata;
- source/provenance;
- thumbnail/player preview;
- transcript state;
- processing state;
- language;
- level/topic;
- import/reprocess history/context where available;
- learner preview.

## Lifecycle actions — WORKING

Depending on state:

- Preview
- Reprocess
- Unpublish
- Republish
- Archive
- Restore

Important behavioral rule:

Lifecycle changes must not imply transcript/provenance deletion. Unpublish/archive changes learner availability, not the existence of underlying imported evidence.

### Reprocess options

The current system supports reprocess. Any finer “what to keep” options that are not backed by the system must appear disabled/gap-labeled rather than pretending to work.

---

# 11. A13–A14 — Vocabulary

## Vocabulary Collections — WORKING

Show:

- collection name;
- language;
- framework;
- level;
- topic;
- item count;
- rights;
- completeness;
- status;
- origin/source.

Pending review/draft must be visually obvious.

## Vocabulary Detail — WORKING

Show:

- collection metadata;
- cover/art when available;
- items;
- source/provenance;
- rights;
- completeness;
- status;
- learner preview.

Actions according to supported lifecycle:

- Preview
- Publish
- Unpublish
- Archive
- Restore
- Republish

## Vocabulary publish admission — CURRENT HARD GATE

Vocabulary publication is currently stricter than Reading.

Publishing requires:

- an allowed/publishable rights state;
- completeness/readiness information;
- explicit admin attestation.

If server admission refuses publication, the UI must explain that it is a server-side admission rule.

Do not silently loosen this behavior in design.

---

# 12. A15 — Reading Overview

Reading is a major operational workspace inside Content.

Show eight operational indicators where data exists:

- Published
- Needs Review
- Processing / Queued
- Rejected
- Archived
- Failed jobs
- Active sources
- Source errors

Each metric is actionable and opens the relevant filtered list/state.

Quick actions:

- Add Content
- Review Queue
- Sources
- View Jobs

Also show a compact **Next in review** list so an Admin can continue editorial work quickly.

Do not show full article bodies on Overview.

---

# 13. A16, A18–A20 — Reading lists

Reading views:

- Needs Review
- Published
- Rejected
- Archived
- Sources

## Common list behavior

Support:

- Search
- Level filter
- pagination/cursor when applicable
- concise scan-friendly rows

Do not show full article body, full source snapshot, or all AI output in a list.

## Needs Review

Each row may include:

- title;
- source/topic;
- language;
- estimated/effective level;
- word count;
- reading time;
- learning target count where available;
- rights state;
- warnings;
- status.

Actions:

- Preview
- Review
- Publish
- Reject

## Published

Show:

- title;
- level;
- topic;
- source;
- published date;
- usage/activity when available.

Actions:

- Preview
- Edit metadata
- Unpublish
- Archive
- Comprehension Sets / generated questions where applicable

**Unpublish is not delete.** It moves the article out of learner visibility and back to an editable/reviewable lifecycle state.

## Rejected

Show:

- title;
- source;
- reject reason;
- rejected at/by.

Actions:

- Preview
- Restore to Review
- Archive

Rejected content remains part of history and must not be visually treated as “never existed.”

## Archived

Show:

- title;
- former status;
- source;
- archived at;
- reason.

Actions:

- Preview
- Restore where supported

---

# 14. A17 — Reading Review Detail

This is the primary editorial workspace.

## Desktop composition

Prefer a wide-screen comparison layout:

**Processed Article | Original Source**

The approved Orena prototype controls the exact visual treatment, but the comparison relationship must remain clear.

## Mobile composition

Use tabs/stacking such as:

- Article
- Source
- Targets
- Evidence

Primary actions must remain reachable without horizontal page zoom.

## Processed Article

Show/edit as supported:

- Title
- Body
- Topic
- Estimated level
- Reviewed/overridden level
- Reading time
- Source attribution
- Status

Current editorial behavior supports editing title/topic/level/body and saving changes.

## Original Source

Read-only.

Show:

- original title;
- author;
- canonical/source URL;
- publication/source facts;
- original content snapshot;
- rights information;
- duplicate-source information where relevant.

Processed edits must not visually imply that the original snapshot changed.

## Cross-source duplicate warning — WORKING

When identical content exists under another source, name/show the other source rather than merely showing a duplicate count.

The purpose is to help an Admin make a rights/provenance decision.

## Learning Targets — WORKING

Each target can include:

- word/phrase;
- type;
- context;
- meaning;
- approve/keep or remove/drop;
- order/rank.

Supported actions:

- approve/keep;
- remove/drop;
- edit allowed target fields/meaning;
- add target;
- reorder.

New target must correspond to content in the article where the system enforces that rule; validation errors must be understandable.

Reorder must be accessible with keyboard/mobile-friendly controls, not drag-only.

## Processing Evidence

Collapsed by default.

May show:

- detected language;
- estimated level;
- topic;
- duplicate evidence;
- suggested learning targets;
- warnings;
- adapted/not adapted;
- processor/model version;
- validation evidence relevant to review.

Do not expose chain-of-thought or hidden model reasoning.

## Rights — WORKING DECISION SUPPORT

Use a tri-state answer such as:

- Unknown
- Allow / Allowed
- Deny / Denied

Rights must always be visible in review.

### Critical behavior

**Reading rights must NOT hard-block Publish.**

Rights are decision support. The UI may show warning severity and consequences, but Publish remains an Admin decision.

This is intentionally different from Vocabulary's current server-side publish admission gate.

## Actions

- Save/edit article fields
- Publish
- Unpublish where appropriate
- Reject
- Archive

Reject requires a reason.

Archive requires confirmation.

After completing a review action, the UI may automatically open the next item in the review queue.

---

# 15. A21 — Add Reading Content

Entry from Reading.

Three inputs:

- URL
- Text
- File

## URL

Fields may include:

- URL
- Language auto/optional
- Title/author when needed
- source information
- rights answer
- license note/attribution information when relevant

## Text

Fields may include:

- Body
- Title
- Author
- Language
- Source name/URL
- Rights

## File

Supported design should communicate accepted file types based on actual runtime support.

Current Reading Add Content UI supports text-style content files such as `.txt`, `.md`, `.html`, `.htm` where available.

## Submission behavior — WORKING

Submit creates a background job.

States:

- Queued
- Running / Processing
- Completed / Ready for Review
- Failed

Do not keep the Add Content modal/page blocked for the entire processing time.

After enqueue:

- allow Add Another;
- allow Close/Navigate elsewhere;
- expose View Job;
- progress continues in the global Admin progress tray.

---

# 16. A22–A23 — Reading Sources

## Source List — WORKING

Each source can show:

- Source name
- Base URL / slug
- Source type
- Language(s)
- Topic hints
- Rights state
- Automation allowed
- Source state
- Polling enabled/disabled
- Last checked
- Last success
- Last error

Source lifecycle states currently include:

- needs review
- approved
- active
- paused
- blocked
- rejected
- archived

Actions according to state:

- View
- Add
- Approve / Activate
- Pause
- Block / Reject
- Archive

## Source Detail — WORKING PARTIAL + FUTURE CONTROLS

Show:

- identity;
- base URL;
- source type;
- languages;
- topic hints;
- rights/attribution policy;
- automation permission;
- polling policy;
- checkpoint/history facts;
- last success/error;
- imported/published/rejected counts where available.

## Polling

The source registry and rights gate exist, but a complete recurring poller is not yet available.

Therefore:

- polling controls may be shown for intended product shape;
- unavailable controls must be disabled;
- mark them clearly as Future/Unavailable;
- do not imply that an active scheduler is running when it is not.

---

# 17. NEW — Reading Comprehension Sets / Question Review

This capability exists in the current Admin backend and must be added to the design even though it was missing from the earlier A0–A34 checklist.

It belongs under a **Published Reading article**.

## Entry

From a published Reading article:

**Comprehension Sets / Questions**

## Generate set — WORKING

Admin can generate a comprehension set for a **published article only**.

Input/context includes support language where required.

If the article is not published, generation is refused and UI must explain why.

Generation creates a draft set. It does not auto-publish learner questions.

## Set statuses

Support the lifecycle:

- Draft
- Needs Review
- Approved
- Rejected
- Archived

## Question review — WORKING

Admin reviews each generated question and makes a decision.

The design must support:

- question text;
- answer/options depending on question type;
- grounding/context evidence needed to judge quality;
- validation state/warnings;
- approve/reject decision for each question;
- clear reviewed/unreviewed state.

Do not show hidden model reasoning.

## Set actions — WORKING

- Generate
- Open/View
- Approve set
- Reject set
- Archive set
- Discard draft

Reject requires a reason.

Approved learner-visible content must remain clearly distinct from draft/review content.

A set must not appear learner-visible merely because it was generated.

## Stale/article-changed condition

If article content changed after generation and the set can no longer be safely applied, show a clear stale/conflict state and guide the Admin to regenerate/retry rather than silently using outdated questions.

---

# 18. A24–A27 — Practice Generator

This remains part of the approved Admin product scope even where current implementation coverage is incomplete.

## Generator Home / Template List

Fields may include:

- template name;
- skill;
- intent;
- level range;
- version;
- status.

## Template Editor / Generate Practice Setup

Define as supported by product/backend:

- skill;
- target intent;
- variables;
- context;
- constraints;
- time limit;
- required semantic elements;
- rubric;
- feedback type.

## Generate Samples

Show several generated tasks for review.

Admin can:

- inspect;
- regenerate;
- revise setup/template;
- approve version.

## Publish Version

Published template/version becomes available to learner task generation when the backend supports that path.

Anything not actually supported yet must be shown as future/unavailable rather than mocked as working.

---

# 19. A28–A30 — Imports

Imports is broader than a generic jobs table.

Design explicit domain flows.

## Imports home / chooser

Provide entry choices for:

- Books
- Media
- Vocabulary
- Reading
- Sources
- Reading Jobs
- History

## Books import — WORKING

Current flow supports EPUB-style book import.

Design for:

- choose one/multiple files;
- choose language;
- queued/in-progress rows;
- success;
- duplicate;
- failed;
- summary;
- View in Content after import.

Do not imply duplicates are errors when they are an expected result.

## Media import — WORKING

Support two major paths:

### URL/source import

- enter source URL;
- preview source;
- show thumbnail/source/duration/transcript availability;
- allow editing supported metadata before import, such as title/level;
- import;
- show outcome.

### File upload

- choose file;
- language/metadata as supported;
- upload/import;
- show outcome.

Import states must distinguish missing transcript and other actionable issues.

## Vocabulary import — WORKING

Flow includes:

- choose file(s);
- preview;
- column/field mapping;
- validation;
- collection metadata;
- learning language;
- meaning/support language;
- framework;
- level;
- topic;
- collection id when appropriate;
- rights status;
- completeness;
- optional publish-after-import;
- attestation when publishing;
- per-file outcome.

## Reading import — WORKING

Use the Add Content flow:

- URL
- Text
- File

After enqueue, continue through the global progress tray / Reading Jobs rather than blocking the form.

## Source registration — WORKING

Admin can register a content source separately from importing one article.

After create:

- source begins in a review state;
- allow opening the source registry;
- automation/polling must obey source rights/state constraints.

## Reading Jobs — WORKING

Each job row may show:

- Job ID or human-readable identity;
- input/job type;
- source;
- created time;
- current stage;
- attempt / max attempts;
- status;
- result/error.

Statuses:

- Queued
- Running
- Completed
- Failed

Stages may include:

- Fetching
- Normalizing
- Deduplicating
- Analyzing
- Building Candidate

Actions:

- View
- Retry when eligible

Important recoverable states include:

- worker lost;
- attempts exhausted.

Design Job Detail so the operator can understand why recovery differs.

## Job Detail — WORKING

Show:

- input;
- source;
- timeline/stages;
- current stage;
- attempts;
- result source item;
- result article;
- short error summary;
- retry eligibility.

Do not dump a raw stack trace by default.

## Import History — WORKING

Show across supported domains:

- type/domain;
- source;
- result;
- created/completed time;
- duplicate/success/failed/partial-like state as applicable.

Filters:

- Domain
- Status
- Date
- Source

### Unified feed limitation — DEFERRED

Current systems use more than one underlying pagination model for generic history and Reading Jobs.

Do not fake one perfectly unified infinite feed if it would be dishonest.

It is acceptable to show two coordinated tables/views under one Imports area until a true unified backend feed exists.

---

# 20. A31–A34 — Operations

Operations is for system/runtime operation, not content editing.

## A31 Runtime / Readiness — WORKING

Show relevant non-secret facts such as:

- app/runtime mode;
- persistence backend;
- schema state/current vs expected;
- account backbone/state;
- media store state;
- reading library/store state;
- vocabulary store state;
- audit log state;
- AI credential store state;
- AI runtime/activation mode.

Never expose secrets.

## AI Operations — WORKING

Show operational telemetry when available:

- capability;
- health;
- request count;
- failure rate;
- average latency;
- tokens;
- cost;
- quota/state when available.

Do not label average latency as P95.

## Learner-impact failures — WORKING

Show which AI/capability failures have affected learner-facing workflows.

This is an operator prioritization view, not a raw log.

Each row may show:

- capability;
- failures;
- degraded events;
- link to AI & Models.

## Reading Engine / Queue — WORKING

Show:

- queued;
- running;
- failed;
- published count;
- engine availability/state.

## A32 Workers — WORKING WITH LIMITATION

Show where data exists:

- worker identity;
- state;
- running/held work;
- last heartbeat/heartbeat age;
- concurrency/derived concurrency facts.

Important limitation:

Current worker information is **derived from job claims**, not a complete worker registry.

A worker that has never held a job may not appear.

The UI must communicate that limitation rather than implying the list is every process in the deployment.

## A33 Source Polling — FUTURE/PARTIAL

Show intended source polling area if useful:

- active sources;
- due sources;
- last poll;
- failures;
- next poll.

But the complete poller is not currently implemented.

Controls such as Run now / interval should be disabled and clearly marked Future where unsupported.

## A34 Errors / Slow Operations — WORKING/PARTIAL

Show actionable events, for example:

- failed Reading jobs;
- AI failures;
- import failures;
- worker failures;
- relevant slow/degraded operations when telemetry exists.

Each row should lead to the place where the operator can act.

Do not turn this into a raw log viewer.

### Error budget / incidents — DEFERRED

No real error-budget or incident record exists yet.

Do not fabricate them.

---

# 21. Reading Coverage — FUTURE

Keep as a future design concept under Reading/Operations only if useful.

Purpose:

> Show where the Reading corpus is under-covered or over-concentrated.

Primary analysis:

**Language × Level × Topic**

Possible future metrics:

- published count;
- source concentration;
- recent growth;
- under-covered categories.

Current backend does not expose a canonical coverage aggregate.

Therefore mark as Future/Unavailable and do not present fake live numbers as real.

---

# 22. Global Admin search — DEFERRED

Per-area search currently exists for areas such as Users and Content.

A true server-side, indexed global search across:

- users;
- Reading articles;
- jobs;
- other Admin objects

is not currently available.

Do not fake global search with a cosmetic field that cannot search the full platform.

If visually included, mark unavailable/future.

---

# 23. Common interaction rules

## Lists

Lists optimize for scanability.

Do not show everything in a list row.

Avoid:

- full article body;
- full source snapshot;
- all model output;
- raw logs;
- all audit events.

## Detail

Click/tap a row to open:

- drawer for quick inspection; or
- full detail page/workspace when editing/review is required.

## Advanced technical information

Place deep technical data inside expandable areas such as:

- Advanced
- Details
- Processing Evidence

Collapsed by default.

## Destructive / consequential actions

Require appropriate confirmation for actions such as:

- Remove credential
- Reject
- Archive
- Unpublish
- Block source
- Discard generated set

Use stronger confirmation for actions that can break runtime routing or are difficult to reverse.

## Status changes

After an action:

- update the row/detail state immediately;
- provide success/error feedback;
- keep the user in a predictable location;
- where useful, advance to the next review item.

## Bulk selection

Only use bulk actions where the operation is safe and meaningful.

Do not introduce bulk destructive workflows merely because tables exist.

---

# 24. Mandatory common states

Every applicable list/detail/workflow must have designed states, not only a happy path.

## Loading

- skeleton/table placeholder;
- preserve approximate layout;
- do not flash misleading zeros.

## Empty

Explain:

- what is empty;
- why it may be empty;
- next operator action.

## Error

Show:

- concise error message;
- Retry;
- request ID when useful for support/debugging;
- link to Operations where appropriate.

## Unavailable

Examples:

- provider not configured;
- telemetry unavailable;
- backend capability absent;
- feature intentionally deferred.

Unavailable must not look like `0` or `Healthy`.

## Running / Pending

For:

- provider test;
- import;
- reading job;
- reprocess;
- generation.

## Success

Use toast/banner/state change and reflect the new row/detail state.

## Confirmation

Provide confirmation for destructive/consequential actions.

---

# 25. Desktop requirements

Design for real operator work at widths up to **1920px**, not only 1440px.

Do not stretch content into unreadably long lines.

Use where appropriate:

- practical max content widths;
- split views;
- side/detail panels;
- sticky action areas;
- dense but readable tables;
- responsive multi-column panels.

Reading Review Detail should make useful use of wide screens for the Processed Article vs Original Source relationship.

---

# 26. Mobile requirements

Admin is not mobile-first, but it must remain fully usable.

At ~390px:

- navigation remains accessible;
- tables become compact rows/cards;
- wide split views become stacked/full-screen/tabs;
- filters may open in a sheet;
- primary actions remain reachable;
- sticky bottom actions are acceptable for editorial workflows;
- no horizontal page zoom;
- long technical metadata should wrap/truncate intentionally;
- do not compress desktop density until labels/actions become unreadable.

Reading Review mobile should provide clear access to:

- Article
- Source
- Targets
- Evidence

---

# 27. Visual direction for the new Admin

Admin must now follow the **approved new Orena visual prototype**, not the old Admin theme.

The same visual identity should be recognizable across Learner and Admin, while the Admin adapts toward operational clarity.

## Target feeling

- modern;
- calm;
- commercially polished;
- soft but not playful;
- trustworthy;
- clear;
- professional;
- approachable;
- high-information without feeling cramped.

## Admin-specific adaptation

Prioritize:

- clarity;
- scanability;
- hierarchy;
- status differentiation;
- consistent tables/rows;
- compact actions;
- predictable details;
- moderate information density.

Use less decorative artwork than Learner.

Avoid:

- enterprise-dashboard generic styling;
- neon cyberpunk;
- excessive glassmorphism;
- turning every data point into a card;
- tiny typography and cramped controls;
- huge whitespace that makes operator scanning inefficient;
- inconsistent one-off styling between Admin areas.

## Component system

Use one shared Admin component language for:

- navigation;
- rows/tables;
- cards/panels where needed;
- buttons;
- inputs/selects;
- chips/status tags;
- filters;
- drawers;
- modals;
- confirmation dialogs;
- progress tray;
- skeletons;
- empty/error/unavailable states;
- toast/banner feedback.

Light and dark modes should remain coherent with the approved Orena prototype.

---

# 28. What must NOT be exposed

Do not design UI for:

- raw API secrets after save;
- chain-of-thought;
- hidden model reasoning;
- raw stack traces by default;
- internal database constraints unless they produce an operator-actionable refusal;
- internal hashes/revisions unless directly useful in a review/debug detail;
- arbitrary private learner-authored content;
- implementation-only service wiring that does not help an Admin act.

Advanced evidence can be available on demand, but default views must stay decision-oriented.

---

# 29. Known backend/product limitations the design must represent honestly

These are not reasons to delete the intended feature shape.

## DEFERRED / FUTURE

- Account role change
- Per-account 30-day activity sparkline in list
- Perfect unified paginated import feed
- Global Admin search
- Complete recurring source poller
- Reading Coverage aggregate
- Error budget / incident record
- P95 latency telemetry

Where such controls are useful for the complete product shape:

- display disabled/unavailable;
- mark `Future`, `Unavailable`, or equivalent;
- explain why briefly;
- never simulate successful behavior.

---

# 30. Important behavioral distinctions

## Reading rights vs Vocabulary rights

Do not unify these incorrectly.

### Reading

Rights = **decision support**.

Unknown/Denied may trigger warnings, but **must not hard-block Admin Publish**.

### Vocabulary

Current server behavior = **publication admission gate**.

Rights/completeness/attestation can refuse publication.

The UI must represent this difference clearly.

## Unpublish vs Delete

Across applicable content:

- Unpublish means not learner-visible.
- Archive means lifecycle/history state.
- Neither implies deletion of source/provenance/transcript/history unless explicitly stated.

## Configured vs Healthy

Do not conflate them.

## Empty vs Unavailable

- Empty = system worked and there is nothing to show.
- Unavailable = system cannot provide the data/capability.

They must look semantically different.

---

# 31. Screen checklist for Design

The design project must include enough frames/states to understand all major flows.

## Shell

- A0 Admin Shell desktop
- A0 Admin Shell mobile
- No-access state
- Global progress tray

## Overview

- A1 Overview
- Needs Attention
- healthy / degraded / partial unavailable examples

## AI & Models

- A2 AI & Models Home
- A3 Provider Configure
- A4 Provider Detail
- A5 Capability Routing
- Provider test running/success/failure
- Capability primary test
- Capability standby test
- Credential remove confirmation + consequences
- Provider/model unavailable states

## Users

- A6 Users List
- Users summary/retention/activity
- A7 User Detail
- Disabled future role-change treatment

## Content

- A8 Content Home
- A9 Books
- A10 Book Detail
- A11 Media
- A12 Media Detail
- A13 Vocabulary Collections
- A14 Vocabulary Detail

## Reading

- A15 Reading Overview
- A16 Needs Review
- A17 Review Detail desktop
- A17 Review Detail mobile
- A18 Published
- A19 Rejected
- A20 Archived
- A21 Add Content URL/Text/File
- A22 Sources
- A23 Source Detail
- Duplicate-source warning
- Rights Unknown/Allow/Deny treatments
- Target review/reorder
- Reading Job detail/retry

## Reading Comprehension — new required design coverage

- Comprehension sets list/entry from article
- Generate set
- Draft/Needs Review set
- Question review
- Question approved/rejected states
- Set approved/rejected/archived
- Reject reason
- Discard draft confirmation
- Stale/article-changed state

## Practice Generator

- A24 Generator Home / Templates
- A25 Setup / Template Editor
- A26 Generated Samples
- A27 Review / Publish Version
- Future/unavailable treatment where backend is missing

## Imports

- A28 Imports Home/Chooser
- Books import queue/results
- Media URL preview/import
- Media file upload
- Vocabulary preview/mapping/import
- Reading URL/Text/File submission
- Source registration
- Reading Jobs
- A29 Job Detail
- A30 History
- duplicate/success/failure states

## Operations

- A31 Runtime / Readiness
- AI telemetry
- Learner-impact failures
- Reading Engine state
- A32 Workers
- A33 Source Polling future state
- A34 Actionable Errors / Slow Operations
- unavailable/partial telemetry states

## Common states

- Loading
- Empty
- Error
- Unavailable
- Running/Pending
- Success
- Retry
- Confirmation
- Desktop table → mobile row/card transformation

---

# 32. Acceptance criteria for the design project

The Admin design is complete only when:

1. Every **WORKING operator-facing capability** in this document has an appropriate UI surface.
2. No current capability is omitted simply because it was missing from an older A0–A34 design brief.
3. Reading Comprehension Set/Question review is included.
4. Books, Media and Vocabulary lifecycle actions are represented accurately.
5. AI provider credentials, provider test and capability routing/standby behavior are represented completely.
6. Import flows are domain-specific rather than reduced to a generic job list.
7. Operations represents readiness, AI telemetry, learner-impact failures, Reading engine and worker evidence.
8. Deferred/future features are visibly distinct from working controls.
9. Reading rights do not hard-block Publish.
10. Vocabulary publication still communicates its stricter admission requirements.
11. Loading/empty/error/unavailable/running/success states are designed.
12. Desktop and mobile representative states exist.
13. The Admin visually belongs to the **new approved Orena prototype/design system**.
14. The Admin does not inherit the old UI's cramped sizing, tiny typography or legacy theme simply because those existed before.
15. The result feels like a real commercial operations product, not a component showcase or conceptual dashboard.

---

# 33. Final mental model

```text
ORENA LEARNER
= learning experience

ORENA PLATFORM ADMIN
= operating the learning platform

OVERVIEW
= what needs attention now

AI & MODELS
= who/what powers each AI capability and whether it works

USERS
= account and learning-activity administration

CONTENT
= what learners can consume/practice and its lifecycle

READING REVIEW
= editorial decision workspace

COMPREHENSION REVIEW
= human gate for generated Reading questions

IMPORTS
= bring content into Orena and follow processing/recovery

OPERATIONS
= runtime, AI, queues, workers and actionable failures
```

The Admin should always help an operator answer four questions:

1. **What is happening?**
2. **What needs my attention?**
3. **What decision/action can I take?**
4. **Where do I go next?**

