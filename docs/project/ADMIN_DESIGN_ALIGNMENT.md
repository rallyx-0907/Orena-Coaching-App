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
| Worker identity, heartbeat age, concurrency in Operations | queue depth by state | the worker's own registry. `reading_ingestion_jobs` holds `claimed_by` and `heartbeat_at` per job, but nothing aggregates them into "which workers are alive" |
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
| Cross-source duplicate content (`ix_reading_source_items_hash_any`) | prevents publishing the same text twice under two sources | surfaced in the Reading preview; proposed for the design |
| `content_revision` | what a learner's cached copy revalidates against; explains why an edit is or is not visible yet | internal, not proposed |
| The three built-in sources (manual, URL, file) | explains why manual pastes dedupe against each other | internal, not proposed |

## Deferred

Design studies not yet implemented, with nothing blocking them but time:
the 560px Book and Media preview drawers in their canonical shape, the
mobile panel layouts (02), the progress tray after Add content (04), the
credential screens' exact copy (05 — the actions exist), and the no-access
page (08 — the server already refuses, the page is the console's generic one).
