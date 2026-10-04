# Content packs: export and import of approved content between environments

Status: PROPOSAL (document only, nothing implemented). Author lane: Claude. Date: 2026-10-04.
Origin: human request, 2026-10-04. Move a test-sample set, or approved content, between the lane dev
(:8021), the local product (:8000, where real content is added through Admin) and a future VPS.

Rules this proposal obeys: D-111 (auto-publish only when rights are cleared and validators pass;
unknown rights go to review), Design Contract rules 43-44 (no invented UI), AGENTS.md section 7
(learner data and account sync are reserved) and section 10 (Postgres authoritative, no raw
cross-store writes). Line citations are against branch `codex/work` at f14a12d.

## 0. What exists today (cited)

| Kind | Store and identity | Rights carried | Source |
| --- | --- | --- | --- |
| Reading source | `reading_sources`, unique `slug` | `state`, `automation_allowed`, `can_republish`, `can_adapt`, `attribution_required`, `license_note`, `approved_by/at` | `persistence/models.py:937-975` |
| Reading snapshot | `reading_source_items`, unique `(source_id, content_hash)`, `source_native_id`, `revision`, `supersedes_id` | `rights_snapshot_json`, `original_author`, `canonical_url`, `original_published_at` | `models.py:1015-1060`, `reading_content_repository.py:512-640` |
| Reading article | `reading_articles`, one per source item; status draft / needs_review / published / rejected / archived; `content_revision` | answers overlaid by `reading_review_events` (`rights_set`), read via `overlay_rights` | `models.py:1063-1135`, `reading_content_repository.py:173-256, 867` |
| Targets | `reading_article_targets`, ranked, `admin_approved/rejected` | none | `models.py:1137-1168` |
| Comprehension | `reading_comprehension_sets` (bound by `article_body_sha256`) and `..._questions` (evidence_text/start/end) | none | `models.py:1297-1403`, `reading_evidence_repository.py:129-146, 322-420, 540` |
| Book | `reading_books` and `reading_book_chapters`, unique `source_hash` of the EPUB bytes; assets by key (`original_asset_key`, `cover_asset_key`, chapter `content_asset_key`) | **no rights column** | `persistence/reading_library_repository.py:105-135`, `reading_library_api.py:131-145, 248`, `migrations/versions/20260916_0009_reading_library.py` |
| Media | `MediaLibraryEntry` (id `media_id`, `source`, `creator`, `canonical_url`, `status`, `lesson`, `processing`); JSON `FileMediaLibraryStore` in `app.py:~629`; Postgres twin `MediaEntry`+`MediaEntryPayload` | `source` mapping only; no explicit republish flag | `media_library_store.py:43-76, 196-300`, `persistence/media_models.py:46-128`, `persistence/media_library_repository.py` |
| Vocabulary | `vocabulary_collections` (text id, `catalog_status`, `provenance`), `vocabulary_entries` (unique `identity_key`), memberships, `vocabulary_sense_localizations` (gloss, source, method, selected, validation) | `provenance` JSON (`_publication_admission`, `vocabulary_repository.py:244`) | `models.py:510-660`, `vocabulary_repository.py:530, 612, 931` |

Existing admission logic to reuse, not copy: `reading_admission.automatic_admission`
(`reading_admission.py:34`), `publication_blockers` / `publication_warnings` used by
`POST /articles/{id}/status` (`reading_admin_api.py:744-818`), the grounding check at set approval
(`reading_evidence_repository.py:540`), `MediaLibraryStore.upsert` -> `validate_entry`
(`media_library_store.py:280`), and the vocabulary `import_source` pipeline (`vocabulary_repository.py:612`).
Existing one-off scripts: `scripts/import_media_index.py` (JSON index to Postgres, explicit
`--database-url`, `--apply` / `--verify-only`), `scripts/build_listening_dev_catalog.py` (builds the dev
catalog manifest). The pack feature replaces neither; it is the Admin-driven, cross-kind path.

## 1. Pack format

A pack is a zip, extension `.orenapack`, content type `application/zip`.

```
manifest.json
items/reading/sources/<slug>.json
items/reading/articles/<article-key>.json      (source item + article + targets + approved sets)
items/books/<book-key>.json
items/media/<media_id>.json
items/vocabulary/collections/<collection_id>.json   (collection + entries + localizations)
assets/books/<book-key>/original.epub | cover.<ext> | chapters/<n>.json
assets/media/<media_id>/<thumb|audio|...>
```

`manifest.json`: `format` ("orena-content-pack"), `version` (1, integer; import refuses higher),
`pack_id` (uuid), `created_at`, `source_environment` {`label` (free text, e.g. "lane-8021"),
`app_version`/git sha, `schema_head` (alembic revision)}, `created_by` (admin email), `filters`
(the export request, section 4), `kinds` (list), `counts` per kind, `files` (array of
`{path, sha256, bytes}` for EVERY non-manifest file), `pack_sha256` (sha256 of the sorted
`path:sha256` lines, so the whole pack has one identity), `warnings` (for example "3 books carry no rights").
The manifest is the only file not hashed; it carries no secrets and no URLs of the exporting host.

Every item file has the envelope `{kind, schema_version, natural_key, content_hash, exported_status, data}`.

### Per-kind `data`

- Reading source: `slug, name, source_type, base_url, languages, topic_hints, state, automation_allowed,
  can_republish, can_adapt, attribution_required, license_note, approved_by, approved_at`.
  Polling state (`polling_*`, `last_*`, `last_error`) excluded; `polling_enabled` is imported as false.
- Reading article: `source_native_id, canonical_url, original_title, original_author, original_published_at,
  original_language, original_content, content_hash, metadata_json, rights_snapshot_json`, plus the
  EFFECTIVE rights (the `overlay_rights` result: can_republish, can_adapt, attribution_required,
  license_note, and who/when answered them), plus article `title, body, excerpt, language, topic, subtopic,
  estimated_level, reviewed_level, effective_level, word_count, reading_time_seconds, is_adapted,
  adaptation_json, analysis_json, content_kind, content_revision`, targets (all fields but ids and timestamps),
  and approved comprehension sets with approved questions (`question_type, prompt, options_json,
  correct_index, explanation, evidence_text`; evidence offsets are exported for diagnosis but recomputed
  on import) and `article_body_sha256`, `generator_version`, `model` (name only).
- Book: `title, author, description, learning_language, source_kind, source_hash, word_count`, chapters
  (`ordinal, title, word_count, content` as an asset), asset files, and a new optional `rights` object
  (see section 7; absent in v1 exports from today's schema, which is itself recorded as "rights unknown").
- Media: all `MediaLibraryEntry` fields (`media_id, media_type, provider, provider_media_id, canonical_url,
  title, creator, duration_ms, language, level, source, library, lesson (transcript, segments, meanings),
  thumbnail`), `status` at export, plus `rights` derived from `source`. `playback` is exported only as
  provider references (YouTube ids) or relative asset paths, never as absolute local paths.
  `processing` is dropped except its final stage name.
- Vocabulary: collection (`id, language_code, title, framework, level, level_range, topic, origin, provenance`),
  entries (all content columns, `identity_key`, `provenance`, `content_origins`), memberships with `position`,
  and localizations (`support_language, gloss, source, source_version, method, selected, selection_reason,
  validation`). `catalog_status` is exported as `exported_status` only.

### Always excluded

Learner data of any kind (attempts, ability projections, notes, drafts, discussions, receipts, user ids,
`owner_token`, personal imports, `learner-imported` content); secrets, API keys, tokens, env values, signed
URLs and local filesystem paths; review history beyond the final publication decision (`reading_review_events`
rows are summarised to `{decision, actor_label, at, reason}` for the last publish/rights act; no full trail);
AI telemetry (`agent.turn`, spend ledger, `processing` attempts/spend/checks, job rows, `validation_json` raw
model output beyond the pass/fail summary); archived/rejected items unless explicitly requested.
A pack builder test greps every JSON for `user_id`, `email`, `token`, `key`, `secret` patterns and fails the
build on a hit.

## 2. Identity and dedupe

Database ids differ per environment and must never be the identity. Identity is a natural key plus a content hash.

| Kind | Natural key | Content hash (sha256 over canonical JSON, sorted keys, UTF-8, no volatile fields) |
| --- | --- | --- |
| Reading source | `slug` | rights + name + languages |
| Reading article | `(source.slug, source_native_id)`; fallback `(source.slug, content_hash of original_content)` which matches the existing unique index | original content hash AND article body hash, kept separately |
| Book | `source_hash` (sha256 of the EPUB bytes) | same; a re-import already dedupes on it |
| Media | `media_id` (stable, regex-checked at `media_library_store.py:~25`) | entry fields without `created_at/status/processing` |
| Vocabulary collection | collection `id`; entries by `identity_key` | collection + member entries + localizations |

Pack-local ids may be kept in the file as `origin_id` for traceability and cross-references inside the pack
(article to target to set), but they are rewritten to fresh uuids on import (Reading uses uuid keys; the
vocabulary collection text id is kept because it is already a natural slug-like id).

Per item the planner computes one outcome:

1. `new`: natural key absent. Create.
2. `identical`: key and hash equal. Skip silently (idempotency).
3. `changed`: key present, hash differs. Policy applies.
4. `conflict_rights`: key present, rights differ (the safest-to-lose data). Always shown, never silent.
5. `duplicate_other_source`: same body hash under another source. Allowed (rights are per source,
   `find_duplicate_content`, `reading_content_repository.py:640`) but flagged.

Policy options for `changed`:
- `skip` (keep local). Safe, no information lost.
- `new_revision`: reuse the engine's own mechanism. For Reading, `record_source_item` already stamps the
  old snapshot `superseded_at` and inserts a new snapshot with `supersedes_id` and bumped `revision`
  (`reading_content_repository.py:512-540`); the article then re-enters the pipeline and `content_revision`
  bumps, which makes approved comprehension sets stale (`stale_sets_for_body`, `reading_evidence_repository.py:146`).
  Media and Vocabulary have no revision chain: media is `upsert`; vocabulary merges via `import_source`.
- `replace`: overwrite in place. Needs an explicit second confirmation, is audited with before and after hash,
  and is unavailable for published items whose incoming rights are weaker than local ones.

**Recommended default: `skip` for everything already present, and `new_revision` only when the admin chooses
it per item.** `replace` is never a default. Rights tightening wins automatically: if the pack says
`can_republish=false` and local says true, the item is flagged `conflict_rights` and the safe choice (local
item unpublished pending review) is proposed, because losing a takedown is worse than losing a typo fix.

## 3. Import pipeline

Principle: a pack never bypasses an engine. Rows are created by the repositories and engines that Admin uses
today, so every validator and the D-111 rule run exactly as for a fresh import.

1. **Upload** to a temporary upload area (same pattern as `ReadingContentEngine._store_upload`,
   `reading_content_engine.py:160`). Size caps in section 6.
2. **Open safely.** Reuse the EPUB hardening idiom (`epub_import.py:187-232`): reject absolute paths, `..`,
   backslashes, drive letters, NUL, symlink entries, duplicate names, case-folded collisions; enforce
   entry count, per-entry and total uncompressed byte budgets (compression-ratio guard against zip bombs);
   only whitelisted extensions (`.json`, `.epub`, `.jpg/.png/.webp`, `.mp3/.m4a/.opus`). Extract nothing to
   disk by name: stream each member into memory or a generated temp name.
3. **Verify.** Parse `manifest.json`, check `format/version`, `schema_head` not newer than this app, every
   file listed with matching sha256 and bytes, no unlisted files. Fail the whole pack on any mismatch.
4. **Validate shape** of every item JSON against its schema (pydantic models shared with export, versioned),
   including language in the enabled set and id regexes.
5. **Plan (dry run).** For each item compute the outcome (section 2) and the **admission decision** by
   calling the real functions: `automatic_admission` for articles (with the source as it WOULD exist after
   the pack's source item is applied); `validate_entry` for media; the vocabulary collection publication
   admission; book import has no admission today (see section 7). Decision values:
   `would_publish` (rights cleared and validators pass), `would_review` (unknown rights or validator failure,
   with reasons, e.g. `rights_not_cleared`, `attribution_unknown`), `would_skip` (identical, or policy skip),
   `blocked` (invalid: bad hash, bad schema, missing asset). The plan is a read-only response; nothing is written.
   The plan is signed with the pack sha256 and the target's content-state token, so Commit refuses a stale plan.
6. **Commit** the plan the admin confirmed, per item, in this order: assets first (copy to
   `FilesystemBookAssetStore` / `_media_library_assets` under the new keys; verify sha256 after writing),
   then rows in dependency order (sources, then source items, then articles+targets, then books, media,
   vocabulary). Reading rows go through `record_source_item` and `create_article(..., automatic_admission=...)`
   so status is decided by the engine, never copied from `exported_status`. An exported `published` item whose
   rights or validators fail HERE lands in review, exactly as D-111 says; `exported_status` is advisory only.
7. **Comprehension sets re-run grounding.** A set is never imported as approved. It is re-created through
   `ReadingEvidenceRepository.create_set` with `locate_evidence` recomputing offsets against the imported
   body and `body_sha256` re-derived; the answer, grounding and duplicate validators run, and the set
   auto-approves only if all pass (D-111 item 1), else `needs_review`. If the body hash differs from the
   pack's `article_body_sha256` the set is dropped and reported.
8. **Idempotency.** `pack_id` plus per-item content hash: re-running a commit on the same pack yields all
   `identical`. A `content_pack_imports` run record (see section 7 for where it lives) stores `pack_id`, plan
   hash, per-item result, actor, so a repeat returns the stored result.
9. **Partial failure and rollback.** Per-item transactions (one item = assets then one DB transaction); a
   failed item deletes its own newly written assets (the same best-effort cleanup the EPUB path uses, see
   `book_asset_store.py:61`), records `failed` with a category, and the run continues. There is no cross-item
   atomicity: a pack of 500 articles must not fail for item 499. The admin can "retry failed" (reruns only those
   items from the stored plan). Whole-run rollback is `archive` of everything the run created, listed from the
   run record (archive, never delete, matching the books admin recovery at `reading_library_api.py:395`).
10. **Audit.** One `admin.content_pack_export` / `admin.content_pack_import` row in `audit_logs` per run with
   counts and `pack_id`, plus per-item audit via the existing actions (`admin.reading_article_*`) because the
   engines emit them.

## 4. Export filters

Request body (all optional, combined with AND): `kinds` (reading, books, media, vocabulary), `languages`
(`en`, `zh`, ...), `source_slugs` and `source_slug_prefix` (for example `sample-` selects every `sample-*`
source on :8021, with a match preview before export), `status` (default `["published"]`; `needs_review`,
`archived` only when asked and then imported as review, never published), `updated_after` / `updated_before`,
`level` range, `ids` (explicit list), and `include_assets` (default true). Vocabulary exports a whole
collection (never loose entries); a Reading source filter pulls its articles; a book filter by `source_hash`
or title. The preview returns counts and byte size before the pack is built. Learner-imported (private) content
is not selectable, ever.

## 5. Admin UX (existing kit only)

Placement: the new Admin (pinned `Orena Admin.dc.html`, `static/orena/admin/`) has Reading and Content
areas with an Imports screen (`static/orena/admin/imports.js`) and an Operations area. The pack feature is two
actions inside the existing Imports screen, so no new frame: an "Export pack" action and an "Import pack"
action, built from the screen's existing button, list-row, sheet, progress and status-chip components. If the
design has no such affordance in that frame, record it in `docs/project/UI_BACKEND_GAPS.md` and ask the human
before adding it (CLAUDE.md rules 4 and 7). This proposal draws no new component.

Export steps: open Export pack sheet; pick kinds, language, source (typed prefix or list), status, date; see
the preview counts; Build; the job row shows progress; Download (signed, same-origin, expiring link).
Import steps: choose file; Upload and Verify (progress); Review plan (a list grouped by kind with an outcome
chip per row: New, Same, Changed, Needs review, Blocked; counts on top; the admission reason in the row detail);
choose the conflict policy (default Skip); Confirm; progress per kind; Result summary with Retry failed and a
link to the Review queue. States: empty (no pack), uploading, verifying, plan-ready, verification-failed
(manifest or hash named), nothing-to-import (all identical), partial-failure, done, expired plan, unavailable
(backend lacks the store, e.g. SQLite fallback). All copy is sparse and localised EN/VI/ZH (rule 50, D-068).
Admin copy lives in `static/orena/admin/copy.js`.

## 6. API (admin-only, same-origin, audited)

All routes under `/api/admin/content-packs`, guarded by `require_admin`, `_same_origin`, `no-store`
(the pattern of `reading_admin_api.py:442-480`), writing the audit row on every request that changes state.

| Route | Purpose |
| --- | --- |
| `POST /exports/preview` | filters in, counts and bytes out; synchronous |
| `POST /exports` | create export job (202); returns `job_id` |
| `GET /exports/{job_id}` , `GET /exports/{job_id}/download` | status; streamed zip, expiring |
| `POST /imports` | multipart upload; verifies and plans; returns `import_id` and plan (202 for large packs) |
| `GET /imports/{import_id}` | state, plan page (cursor), per-item results |
| `POST /imports/{import_id}/commit` | body: policy, per-item overrides, plan hash; 202 |
| `POST /imports/{import_id}/retry` , `POST /imports/{import_id}/archive` | retry failed; archive what the run created |

Synchronous: preview, status reads, small verify. Background job: build, verify of large packs, plan, commit,
using the existing job mechanism (the Reading jobs table and worker, `reading_admin_api.py:480-629`, and the
`ReadingIngestionJob` row at `models.py:1188`, extended or paralleled; see section 7). A single worker per
environment, one pack at a time (`409` if busy), to keep the shared runtime rule.

Proposed limits (configurable by env, defaults for review): upload 500 MB, 20,000 files, 2 GB uncompressed,
compression ratio 100:1, single JSON 10 MB, single asset 120 MB, 5,000 items per pack. Export links expire in
1 hour; temp packs deleted after 24 hours. Rate limit 1 export and 1 import per admin at a time.

## 7. Migration need (flag for independent review)

Core pack feature: **no schema change** is required for Reading, Media or Vocabulary. Items are written
through existing tables, and the import-run record can live in files beside the existing job store or in
`audit_logs` payloads for v1.

Two optional changes, each needing independent architecture review (AGENTS.md section 1, schema/migration):

1. **Book rights column.** `reading_books` has none (`reading_library_repository.py:105-135`; the migration
   `20260916_0009`). Without it a pack cannot carry or enforce rights for books, so on import every book
   would be treated as rights unknown. Options: (a) add nullable `rights_json` JSON (can_republish,
   can_adapt, attribution_required, license_note, answered_by/at) to `reading_books` (additive, no backfill,
   default null = unknown); (b) keep books out of auto-publish and carry only a free `license_note` in the pack
   manifest without enforcing it. Recommend (a), because the D-111 rule cannot be honoured for books otherwise.
   Needs a migration after head `20261004_0025`, a human schema authorization, and independent review.
2. **Import-run table** (`content_pack_runs`, `content_pack_run_items`) for idempotency and per-item results,
   instead of files. Recommend file/audit-based v1 and a table only if the human wants history.

Media has no rights field either, but `source` is a free mapping; v1 reads `source.license`/`source.rights`
if present, else rights unknown, and the media admission treats unknown as review (D-111 item 3).

## 8. Effort, tests, risks, questions

Effort (S under 1 day, M 2-4 days, L about a week; one engineer):
- Pack schema, manifest, hashing, zip-safe reader/writer, learner-data scrub test: M
- Reading exporter and importer incl. sources, rights, targets, set re-grounding: L
- Vocabulary exporter and importer (collections, entries, localizations): M
- Media exporter and importer (JSON store and Postgres, assets, transcripts): L
- Books exporter and importer (assets, chapters, dedupe by hash): M (plus S for rights column if approved)
- Plan/dry-run engine with admission decisions and policy: M
- Job runner, audit, limits, retry/archive: M
- Admin UI in Imports screen, 3 languages, states: M
- Tests and cross-environment rehearsal (8021 to a scratch 8011, Gemini sandbox): M

Test plan:
- Unit: canonical hash stability; manifest verify (tamper one byte, extra file, missing file); zip-slip
  (`../x`, absolute, backslash, symlink, duplicate, bomb); learner-data scrub; rights round-trip equality.
- Engine: import into an empty DB gives the same published set; second import is all `identical`;
  changed body creates a revision and stales sets; unknown rights always land in review; weaker local rights
  are not overwritten; a set with a body mismatch is dropped.
- Failure: kill mid-commit, retry finishes; failed item cleans its assets; busy returns 409.
- Contract: SQLite is rejected as unavailable (Postgres authoritative); EN and ZH parity (CJK bodies,
  evidence offsets recomputed), VI support text with diacritics.
- Browser: the Imports flows at 1920x1080 and 390x844, EN/VI/ZH, light/dark, no page scroll (rule 49 is for
  learning workspaces; Admin must still avoid horizontal overflow).
- Rehearsal: export `sample-*` from :8021, import into the sandbox, diff counts and effective rights.

Risks:
- Rights laundering: a pack could assert `can_republish=true` for a text whose source rights are not cleared.
  Mitigation: the target's source policy must also permit (`automatic_admission` checks both the source and
  the snapshot), and packs from an unknown `source_environment` land as review unless the admin ticks "trust
  this pack's rights" (open question 2).
- Large media assets (disk, time); version drift across `schema_head`; partial imports surprising admins;
  slug collisions between a sample source and a real source (different rights under one slug); loss of local
  edits under Replace; export of content a rights holder asked to remove (an archive or takedown must travel:
  archived items are exportable as `takedown` markers when the filter asks).
- Vocabulary localization `selected` flags can change meaning if the target already has other selected glosses.

Open questions for the human:
1. Approve the optional `reading_books.rights_json` column (section 7)? Until then books import as rights unknown, review only.
2. Should a pack's rights answers be trusted when its source environment is another Orena you control, or must
   every cleared item still pass the target's own source policy (recommended: both must clear)?
3. Default conflict policy `skip` (recommended) versus `new_revision`?
4. Are media audio/video bytes ever packed, or only provider references and transcripts (rights and size)?
5. Do sample (`sample-*`) sources travel to :8000 at all, or are they refused by default to keep test content out of the product?
6. Limits: are 500 MB and 5,000 items right for a future VPS?
7. Is a persisted import history (table) wanted, or is the audit log enough?
8. Does the Admin design want an explicit Packs entry in the rail, or stay inside Imports (recommended)?
