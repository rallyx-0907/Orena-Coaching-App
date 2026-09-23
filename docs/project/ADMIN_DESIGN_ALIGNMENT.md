# Admin: canonical design ↔ console ↔ backend

The Platform Admin design is the target
(`docs/design/canonical-ui/screens/Orena-Admin-Control-Center.dc.html`, pinned
2026-09-23). The console is the implementation state, and the backend is what
it can honestly answer with. This file is the third column: where those three
disagree, and which way the disagreement is meant to be resolved.

Rule, from the human's brief and `DESIGN_CONTRACT.md`: **a capability missing
from the backend is a backend gap, never a reason to delete the control from
the design.** The runtime enables only what the backend supports; the design
keeps the whole shape.

## Backend gaps — designed, not answerable yet

| Design | What exists | What is missing |
| --- | --- | --- |
| P95 latency per capability route | `avg_latency_ms` over the control plane's sample window | a percentile. The column shows the mean, labelled as the mean |
| Per-account learning activity, 30 days, in the accounts list | the same measures in the account detail | a per-row series on `/console/users`; a sparkline would be one request per row |
| Change an account's role | role is read and filtered | no endpoint changes it. The control is present and disabled |
| One paginated imports feed across books, media, vocabulary and Reading | two feeds: `/console/imports/history` (offset) and `/admin/reading/jobs` (cursor) | a unified feed. Merging two paginations client-side would skip rows, so they are two tables under one filter |
| Worker identity, heartbeat age, concurrency in Operations | **closed, with a named limit.** `ReadingJobRepository.workers()` groups the claims: identity, how much each holds, how long since it reported, and `working` / `stale` / `idle` against the reaper's own window | a worker that has never taken a job is invisible, because this counts claims rather than keeping a registry. A registry table is a schema decision, so Operations says which number it is showing (`derived_from_claims`) instead of implying it is every process |
| Error budget over 30 days, and incidents | AI operation telemetry and readiness indicators | no budget or incident record exists |
| Global search across users, articles and jobs | per-area search on users and content | nothing searches Reading articles or jobs; §46.11 requires it to be server-side, paginated and indexed when it arrives |
| Source polling controls | the source registry, the rights gate and the CHECK that stops an unapproved source polling | the poller. Shown, disabled, marked future |
| Reading coverage by level and topic | published articles carry level and topic | no coverage aggregate. Future in the design; not built |

## Backend capabilities the design does not yet show

Judged by the brief's test: does it help an operator understand, decide, act or
recover? If it only describes how something is built, it stays internal.

| Capability | Why it belongs in the design | Status |
| --- | --- | --- |
| A job that lost its worker (`worker_lost`) and one that ran out of attempts (`attempts_exhausted`) | both are recoverable states an operator acts on differently — one is a retry, the other is a decision | shown in the Reading job list today; proposed for the design's job detail |
| The immutability refusal (SQLSTATE 23514 from the snapshot trigger) | tells an operator that a correction was refused *by the database*, not lost | not surfaced yet |
| Cross-source duplicate content (`ix_reading_source_items_hash_any`) | prevents publishing the same text twice under two sources | **in the Reading preview, naming the other source.** A count is not a decision; the rights that make a second copy legitimate are the source's, so the source is named |
| `content_revision` | what a learner's cached copy revalidates against; explains why an edit is or is not visible yet | internal, not proposed |
| The three built-in sources (manual, URL, file) | explains why manual pastes dedupe against each other | internal, not proposed |

## Resolved since the first pass

Recorded here rather than deleted, because the reason each was a gap is the
reason the fix is shaped the way it is.

| Was | Now |
| --- | --- |
| Worker identity, heartbeat, concurrency | derived from the claims (above), with the limit named |
| Rights read as a single boolean, so "nobody answered" and "refused" drew the same cell | `rights_state` answers `allowed` / `denied` / `unknown` per question, and attribution answers as an obligation (`required` / `not_required`) rather than a permission. The submission form no longer defaults an unanswered question to `False`, which was recording a refusal nobody made |
| Learning targets could be kept or dropped but not ordered, while the canonical design orders them | `POST /articles/{id}/target-order` writes `rank` for the whole list at once; a partial or foreign order is refused rather than silently renumbering the rest. The console moves one step at a time so a keyboard, a screen reader and a phone can all do it |
| The duplicate warning counted copies | it names the source each copy sits under |
| The Add Content form sent `can_republish: false` whenever its checkbox was unticked, so the server's tri-state was defeated one layer up | the question is a three-answer select whose default is unanswered, and the submit client omits an absent field rather than posting an empty string the server cannot tell from an answer. The console gate reads the payload, because a route test calls the API directly and never sees the form |
| `POST /articles/{a}/targets/{t}` looked the target up by its own id alone, so article A's URL could decide article B's target — the write landing on B while the audit entry and the revision bump landed on A | the article is part of the target's identity in the same statement; a crossed pair is a 404 that moves nothing |
| The progress tray lived inside the Reading view, so it vanished on a section change and only counted jobs | `tray.js` holds it for the console, the frame renders it above and outside the section host, and one timer refreshes it. Each row carries what was submitted, its state, how far the engine has got and what that means; a finished job stays a minute, then leaves |

The five design studies that were deferred — the Book and Media preview
drawers (03), the mobile panel layouts (02), the progress tray after Add
content (04), the credential flow (05) and the no-access page (08) — are
implemented.

## Parity: every control in the canonical design

The rule for this table is the human's: **a control is not done because it is
visible, and not done because it is disabled.** Each one is either *working* -
it calls a real endpoint and the result is real - or *deferred*, which is a
recorded decision with the reason beside it, not an omission.

| Control (canonical design) | State | Where it stands |
| --- | --- | --- |
| Six areas, one route | working | `#/admin?id=<area>`; Reading is a Content view, and the old `?id=reading` link still resolves |
| Loading / empty / error / unavailable / pending | working | `states.js`; the baseline itself records these as INCOMPLETE, so the structure is ours and the words are in `copy.js` in both languages |
| Capability routing: edit a route | working | `PUT /ai/config/{key}` |
| Capability routing: test a route, test its standby | working | `POST /ai/test/{key}`; returns a structured refusal with telemetry when unconfigured |
| Provider: test connection | working | `POST /ai/credentials/{id}/test`; verified live against Ollama (3 models, 51 ms) |
| Provider: save a key, verify before saving | working | `PUT /ai/credentials/{id}`. Verified end to end with a real Groq key on 2026-09-23: verify → save → test the *stored* key (4 live models) → remove. The key appears in no API response, nowhere in the container log, and not in plaintext under `/data` - it is encrypted with `AI_PROVIDER_SECRETS_KEY`, which compose now passes through |
| Provider: remove, with consequences and type-to-confirm | working | `DELETE /ai/credentials/{id}` |
| Accounts: list, filter, detail, retention | working | `/console/users*` |
| Accounts: change role | **deferred** | no endpoint writes a role. The control is present and disabled with the gap named |
| Accounts: 30-day activity per row | **deferred** | the measure exists in the detail; a per-row series would be one request per row |
| Content: list, filter, preview | working | `/console/content*` |
| Content: book archive | working | `POST /content/book/{id}/archive` |
| Content: vocabulary publish | working | `POST /content/vocabulary/{id}/publish`. Its admission gate still refuses on rights - see the conflict below |
| Content: media unpublish / archive / republish / restore | working | `POST /content/media/{id}/status`, audited, no deletion in the flow. Verified end to end on a real YouTube import: every transition keeps the 60-segment transcript, and the learner's Listening library gains and loses the item as the state changes |
| Content: media reprocess | working | `POST /content/media/{id}/reprocess`; the "what to keep" options are shown disabled and named as a gap |
| Reading: queue, published, rejected, archived, sources | working | `/admin/reading/*` |
| Reading: submit text / URL / file | working | `POST /admin/reading/jobs`, multipart |
| Reading: review, edit level and topic, publish, reject, unpublish | working | `POST /admin/reading/articles/{id}`, `.../status` |
| Reading: keep / drop a learning target | working | `POST .../targets/{id}`, scoped to the article |
| Reading: order the learning targets | working | `POST .../target-order`, whole order per write |
| Reading: rights as decision support | working | three answers, three weights, Publish never blocked |
| Reading: cross-source duplicate warning | working | names the other source |
| Reading: source polling | **deferred** | the registry, the rights gate and the CHECK exist; no poller. Shown, disabled, marked future |
| Reading: coverage by level and topic | **deferred** | no aggregate exists |
| Imports: history, Reading jobs, retry, job detail | working | two feeds under one filter |
| Imports: one unified feed | **deferred** | merging two paginations client-side would skip rows |
| Progress tray after Add content | working | floating, outside the section, one clock, leaves on its own |
| Operations: readiness, activation, system, AI telemetry, impact | working | `/admin/readiness-summary`, `/admin/ai/operations`, `/admin/product-activity` |
| Operations: worker identity, heartbeat, concurrency | working | derived from the claims, with the limit named |
| Operations: error budget and incidents | **deferred** | no budget or incident record exists |
| P95 per capability | **deferred** | the control plane records a mean; the column shows the mean, labelled as the mean |
| Global search | **deferred** | per-area search exists; nothing searches Reading articles or jobs |
| Admin without the role | working | study 08's page |
| The console's own frame: no learner rail, Back to Orena | working | decided by the human on 2026-09-23; `UI_BACKEND_GAPS.md` records it as DECIDED, not as a conflict |

## A contract this round did not resolve

The human's decision is that rights are decision support and must not hard-block
Publish. That is now true everywhere it was ours to decide: the Reading engine
never gated publication on rights and the console now says which of the three
answers it is looking at beside a Publish that stays enabled.

**One place still refuses.** `POST /content/vocabulary/{id}/publish` returns 422
unless `rights_status` is one of `PUBLISHABLE_RIGHTS` and the admission is
attested. That gate is a recorded admission contract, not a UI habit, and
`AGENTS.md` says a change that would violate a contract is surfaced rather than
made quietly. So it is surfaced here: **loosening it is a decision for the
human**, and until then the vocabulary publish form states the refusal as the
server's, not as the console's opinion.

## Production architecture blocker: media storage is single-instance

**`FileMediaLibraryStore` is not production-scalable and must not be treated as
if it were.** It is one JSON file rewritten whole on every change, guarded by a
`threading.Lock` that exists only inside one process. That is honest for a
single container and wrong for anything else:

- **two instances lose writes.** Each reads the index, adds its own row and
  writes the file back; the second write erases the first. The existing lock
  makes this safe between threads of one process and does nothing between
  processes or hosts.
- **every write is O(whole catalog).** The file is re-serialised and its
  integrity hash recomputed for a single status change.
- **assets are local paths.** `FilesystemBookAssetStore` under
  `MEDIA_LIBRARY_ASSET_ROOT` assumes one filesystem that every instance can
  see.

**Do not paper over this with a cross-container file lock.** A lock on a shared
mount trades a lost write for a stuck deployment, keeps the O(catalog) rewrite,
and leaves the asset path assumption untouched - it would make the blocker
harder to see without removing it.

### Migration path (not started; needs approval)

Two independent moves, in this order:

1. **Metadata and lifecycle into the shared persistence.** The entry is already
   a flat dataclass with a stable `media_id`, three lifecycle states and a JSON
   `lesson` payload, so it maps onto one table with a JSON column and reads
   through a repository exactly as the Reading engine's content does. The
   store's Protocol (`list` / `get` / `upsert` / `delete`) is the seam: a
   PostgreSQL implementation satisfies it without a caller changing. `list`
   already defaults to `status="published"`, so the learner-visibility rule
   survives the move by construction.
2. **Assets into persistent or object storage.** `BookAssetStore` is already an
   interface with a filesystem implementation; an object-store implementation
   behind the same interface removes the single-filesystem assumption. Playback
   URLs are built from the asset key, not from a path, so they do not change.

Neither is opened in this Admin round. Both are schema/architecture decisions
under `AGENTS.md` "Architecture holds" and need the human's authorization and
an independent architecture review first.

## The media storage deployment contract

The application's defaults are repo-relative, which suits a checkout and is
wrong for a container: an image with the code mounted read-only cannot write
them, and one without a volume loses everything on the next recreate. That is
not a sandbox quirk, so it is not fixed with a sandbox workaround -
`compose.yaml` declares the contract for every deployment:

| Variable | Value | What is lost without it |
| --- | --- | --- |
| `MEDIA_LIBRARY_ROOT` | `/data/media_library` | the index: every imported item, its transcript and its lifecycle state |
| `MEDIA_LIBRARY_ASSET_ROOT` | `/data/media_library_assets` | the stored bytes of any directly imported file and its poster |
| `READING_LIBRARY_ASSET_ROOT` | `/data/reading_library_assets` | uploads waiting between the request that accepted them and the worker |

`/data` is the persistent volume the deployment already uses for its databases.
`.env.example` names all three with no values.

Verified on the lane sandbox: with the item left `unpublished`, a container
restart *and* a full recreate both keep the index, the 60-segment transcript
and the lifecycle state, and the learner's library gains it again on Restore.

## Known gaps in the design itself

From `UI_BASELINE.md`, and not defects of ours: Admin is an INCOMPLETE template,
Modal/Drawer, EmptyState and LoadingSkeleton do not exist as components, the
loading / empty / error states have no canonical version, and there is **no
tablet breakpoint** - the baseline draws exactly two frames, 1920x1080 and
390x844. The console's intermediate steps are therefore ours, declared once
against its own container width rather than the window's, and recorded here as
an implementation decision rather than a reading of the design.
