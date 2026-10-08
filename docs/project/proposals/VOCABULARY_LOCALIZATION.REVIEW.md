# Review: VOCABULARY_LOCALIZATION.md revision 1 (migration 20261004_0025)

**Reviewer:** independent delegated architecture reviewer, a fresh-context agent with no part in
writing the change (`AGENTS.md` "Architecture review authority"). Read-only; no database run.
**Reviewed commit:** `accbbfb` (codex/work), 2026-10-04.
**Verdict:** APPROVE WITH CONDITIONS. The (sense, support language) model matches D-124; the
table is additive, content-owned, and holds no learner data. Architecture review is not the
human's authorization (condition 6).

## Findings (condensed; author responses in revision 2 of the proposal, §9)

| # | Sev | Finding | Required change |
| --- | --- | --- | --- |
| P1-1 | P1 | `_apply_content_snapshot` replaces `short_meanings` wholesale, so the order of the snapshot and the table rows decides whether a published snapshot hides every new localization or leaks frozen content. The proposal does not say which wins. | State that localizations are outside the snapshot contract. Order: entry row → snapshot → additive merge of localization rows per language, with a snapshot item for that language winning only as a deliberate collection-scoped override. Snapshot fields never gain a localization field. Test this with a snapshot plus a new `vi` row. |
| P1-2 | P1 | Unique `(entry_id, support_language)` holds one row; "replacing is an operator action with a recorded reason" has no column or history, and precedence lives only in prose. | Add a replacement audit, or key on `(entry_id, support_language, source)` with a `selected` flag; enforce precedence in code. |
| P2-1 | P2 | The backfill origin map misses `curated`, writes unknown origins verbatim (length risk), claims `pivot_translation` for the generic `prepared` origin, and leaves `source_version` empty. | Map `curated`; whitelist or mark unknown origins (`legacy-unknown`); `prepared` → `legacy-prepared`, unverified; set a non-empty `source_version` marker. |
| P2-2 | P2 | Language tags are not normalized (`vi-VN`, `zh-CN`); the first duplicate wins with no origin priority; there is no gloss length cap. | Normalize tags; prefer source over curated over dictionary over prepared; count skipped duplicates; cap or accept the length explicitly. |
| P2-3 | P2 | "Idempotent" is overstated: the migration re-runs only after a downgrade; `bulk_insert` loads every entry at once. | Reword; process in chunks; rehearse at volume. |
| P2-4 | P2 | JSON vs JSONB choice is unstated (0024 uses JSONB on PostgreSQL). | State it, or use JSONB on PostgreSQL. |
| P2-5 | P2 | The `(support_language, entry_id)` index does not serve the read path, which the unique index already covers. | Drop it, or justify it by the gap report. |
| P2-6 | P2 | `down_revision` chains on the unapproved 0024 proposal; the proposed-migrations README is stale. | Re-parent on `20260930_0023` (merge order decides the final chain), or gate on 0024; update the README at promotion. |
| P3-1 | P3 | ON DELETE CASCADE silently removes a retired entry's localizations. | Record it. Acceptable. |
| P3-2 | P3 | Stopping `translation_vi` writes on catalogue saves is a learner-record behaviour change: the old UI at `/` reads `definition \|\| translation_vi`. | Record it separately for the human. |
| P3-3 | P3 | Startup refuses a schema that is not at head. | Schema first (operator step, after backup), then code. Read code must work with the table absent or empty. |

## Conditions for promotion

1. P1-1 resolved: written projection order, and the snapshot + new-language test.
2. P1-2 resolved: an audit, or the source-keyed rows with a `selected` flag.
3. P2-1 and P2-2 backfill fixes.
4. Rehearsal up/down/up on throwaway PostgreSQL 16 and SQLite, at 100k entries, with constraint probes (D4 rehearsal pattern).
5. The 0024 chain settled, and `migrations/proposed/README.md` updated.
6. The human's authorization, scoped to the lane runtime only. An implementer may not self-approve.
7. The read path works with the table absent or empty.
