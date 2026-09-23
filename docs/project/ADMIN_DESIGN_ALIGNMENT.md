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

## Deferred

Design controls that are present and disabled, with the backend gap named
beside them: source polling (07), P95 per capability, role change, the unified
imports feed, global search, Reading coverage, and the error budget. None is
deleted from the design; each waits on the backend capability its row above
describes.
