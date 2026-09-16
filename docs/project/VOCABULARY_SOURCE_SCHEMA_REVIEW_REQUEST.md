# Vocabulary source content schema review request

Status: `PENDING INDEPENDENT ARCHITECTURE REVIEW`

This proposal supports the Vocabulary Source Import vertical slice. It is
shared content persistence, not learner-owned state. It is intentionally not
active: the migration remains in `migrations/proposed/20260916_0008_vocabulary_content_catalog.py`.

## Why static content is no longer sufficient

The requested flow is Admin upload → mapping → validation → persistence →
learner Library after refresh. A static catalog cannot retain an Admin upload,
support repeated imports, or serve shared content independently of a deployed
code release. Platform settings are not a content-domain store and would not
provide the required collection/entry/membership scale.

## Proposed shared tables

- `vocabulary_collections`: stable learner-facing collection identity,
  language/framework/level/topic, publication status, and collection
  provenance.
- `vocabulary_entries`: one language-neutral lexical entry with term,
  language-aware pronunciations/readings, short meanings, detailed definitions,
  examples, usage, orthography, level metadata, and field origin markers.
- `vocabulary_collection_memberships`: many-to-many placement so one entry can
  be present in Oxford/Common, TOEIC, and another collection without copied
  lexical records.
- `vocabulary_source_imports`: one audit/result row per source in a batch,
  including mapping, hash, counts, warnings, and failure details.

The identity key is language-aware: NFC is preserved, Latin case is folded,
Chinese simplified/traditional forms are not silently collapsed, POS remains a
dimension, and a supplied sense key or source meaning fingerprint separates
homographs. This is intentionally a bounded MVP identity policy, not a full
lexical database.

## Deliberately out of scope

No new SavedWord-equivalent table, learner progress table, review scheduler,
AI enrichment pipeline, account sync, or generated-content writer is included.
Learner save/review continues through the existing `saved_words` /
`vocabulary_learning` path. Source values are retained as source values;
future enrichment can add a separate origin without overwriting them.

## Required gate before activation

1. Independent architecture review of the model, identity constraints,
   deletion behaviour, batch transaction boundary, and PostgreSQL indexes.
2. Human authorization for the shared vocabulary schema/runtime migration.
3. Rehearsal against a throwaway PostgreSQL database, then moving the proposal
   into `migrations/versions/` and applying it to the named sandbox runtime.

Until those steps happen, Admin preview is available but Admin import returns
an explicit `503 vocabulary_schema_unavailable`; no upload is silently written
to static files or platform settings.
