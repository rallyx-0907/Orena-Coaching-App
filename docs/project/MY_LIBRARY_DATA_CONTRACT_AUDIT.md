# Vocabulary (shared) vs Thư viện của tôi (personal): backend audit and data contract

Status: audit + contract, 2026-09-23. Authority for the intent: explicit human
instruction of 2026-09-23 ("Vocabulary là thư viện nội dung chung … My Library
mới là thư viện cá nhân … ưu tiên reference tới source content + user-specific
state/metadata, tránh duplicate dữ liệu không cần thiết") and
`docs/product/ORENA_COLLECTION_ARCHITECTURE.md`, which already names the logical
contracts (`ContentMembership`, `LanguageItemRef`, `EncounterProvenance`,
`CollectionEntry`). This file does not restate that spec; it records what the
implementation actually is today, where it disagrees, and the order in which
the disagreement is closed.

Nothing here decides schema. §5 of the Collection Architecture sets the order -
typed query adapters over existing stores first, account membership and
provenance repositories **after the schema gate** - and AGENTS "Architecture
review authority" requires independent review for schema/migration work, which
the implementer may not self-approve.

---

## 1. What exists today

**Shared content already has a clean home.** `vocabulary_collections`,
`vocabulary_entries`, `vocabulary_collection_memberships` and
`vocabulary_source_imports` carry no `user_id` and no learner state;
`VocabularyCollection`'s own docstring says "Collections are content, not
learner state". The Reading Content Engine tables and `reading_books` /
`reading_book_chapters` are the same shape, and the reading library repository
already states that its ids are "the stable identities a learner-facing locator
(a future I4 `ContentMembership.sourceRef` …) is meant to reference".

So the content side of the human's instruction is **already true**: Vocabulary
is a shared catalogue, admin-curated, rights-gated, with a stable identity per
entry (`vocabulary_entries.identity_key`, unique, and `sense_key` inside it).

**Learner state is spread across one table per capability**, each keyed by
`user_id` + `language_code`:

| Kind the design draws | Where it lives now | Has its own SRS? |
| --- | --- | --- |
| Từ & cụm từ | `saved_words` | yes (`review_stage`, `next_review_at`) |
| Ngữ pháp | `grammar_progress` | no |
| Bài đọc | `reading_sessions` / `reading_attempts` | no |
| Listening | `listening_progress` | no |
| Bài viết | `essays` / `essay_revisions` | no |
| Bài nói | `speaking_attempts` | no |
| Sách | `reading_books` progress (device) | no |
| **Ghi chú** | **nowhere** | — |

## 2. The three real disagreements

**D1 - a saved word copies the catalogue instead of referencing it.**
`saved_words` stores `phonetic`, `part_of_speech`, `definition` and
`translation_vi` as its own columns, and `writing_coach/becoming_library.py`
re-joins each row to the catalogue **by normalised text** at read time
(`_catalog_resolver`). Two costs follow, and both are already visible:

- the copy can disagree with the catalogue, and nothing detects it;
- text is not identity. `vocabulary_entries` distinguishes senses and readings
  (`identity_key`, `sense_key`, `readings`), and the text join throws that
  away - which is exactly why per-word audio for Chinese cannot be bound to the
  right reading today (§4).

The fix is a reference (`entry_id` / `identity_key`) on the learner's row, with
the copied fields kept only as the *learner's own* override or as the snapshot
of a word that has no catalogue entry at all. That is a schema change.

**D2 - there is no cross-kind "kept" relation.** My Library draws one library
over eight kinds, one review queue across all of them, per-kind collections and
one item detail with its origin. Today each kind is its own table with its own
shape, `saved_words` is the only one with a review schedule, and nothing records
"the learner kept this" for a reading, a listening moment, a take or a book.
`ContentMembership` is the named owner for this and does not exist yet.

**D3 - Ghi chú has no owner at all.** The design draws notes as a first-class
kind. No table, no endpoint, no model. It cannot be adapted from anything.

## 3. The contract, in the terms the two documents already use

One relation, referencing sources, holding only what is the learner's:

```
LibraryItem = {
  id, account, learning_language,
  kind,                    # word | grammar | reading | listening | note |
                           # writing | speaking | book
  source_ref,              # {domain, id} - the shared content's own identity,
                           # e.g. {vocabulary_entry, <identity_key>},
                           # {reading_article, <id>}, {reading_book, <id>}
  own_ref,                 # {domain, id} for a learner-made artifact (a take,
                           # an essay, a note) - never a copy of its body
  relationship,            # kept | started | imported  (ContentMembership)
  state,                   # learning | marked | mastered  (the frame's chips)
  review { stage, successful_recalls, lapse_count,
           last_reviewed_at, next_review_at },
  learner_fields,          # only what the learner wrote: note, focus, override
  created_at, updated_at, version
}

LibraryCollection = { id, account, learning_language, kind, title, created_at }
LibraryCollectionMember = { collection_id, item_id, position }
```

Three rules this contract exists to keep:

1. **No body is copied.** A word's meanings, a reading's text, a book's
   chapters stay in the content domain and are read through `source_ref`. What
   the learner wrote is theirs and lives in `learner_fields` or the owning
   capability's table.
2. **One collection, one kind** - the frame says so ("mỗi bộ một loại").
3. **Removing a kept item removes the relationship, never the source, the
   learner's own response or the review evidence** (Collection Architecture §4).

`saved_words` becomes the `kind = word` rows of this relation, not a second
store beside it; its `next_review_at` is already the shape `review` needs, so
the existing scheduler and the existing review UI carry over unchanged.

## 4. Per-word audio (the same instruction, item C)

The catalogue stores pronunciations as **text only**
(`vocabulary_entries.pronunciations` = `[{text, kind, origin}]`). There is no
audio for a word anywhere: `listening_progress` and `speaking_attempts` are
explicitly "audio-free", and the only binary store in the repository is
`writing_coach/book_asset_store.py`, for book assets.

What the instruction asks for therefore needs: a per-word audio record bound to
an **entry identity and its reading** (not to raw text), a real-audio source
(Wiktionary / Wikimedia Commons) with `source`, `license` and `attribution`
stored beside the bytes, a local TTS fallback (Kokoro preferred), and a cache
keyed so nothing is generated twice. `book_asset_store.py` is the existing
pattern to follow rather than a second asset mechanism.

Bound to a reading, not to text: `vocabulary_entries.readings` already carries
them, so the record's key is `(identity_key, reading)` - which is only reachable
once D1 gives the learner's row that identity.

## 5. Order of work

1. **Typed query adapters over existing stores** (Collection Architecture §5,
   no schema): one read model that answers My Library's lists, its counts, its
   search and its item detail from the tables in §1, marking kinds it cannot
   answer as unavailable rather than inventing rows. Ghi chú (D3) is
   unavailable by definition.
2. **My Library UI** on its canonical frames, over that adapter.
3. **The schema gate**: `LibraryItem` / collections (D2), the entry reference on
   a saved word (D1), and the word-audio record (§4). These go to independent
   architecture review before they land; this lane does not self-approve them.
4. Only after My Library is reachable: remove the learner's own-word rows from
   the Vocabulary room, which the new Vocabulary frames no longer draw (rule
   44). Not before - 1 619 saved words must never be unreachable.

## 6. What this changes in the interface

The new Vocabulary frames draw the **catalogue only**: packs, filters, progress
per pack. The learner's own saved words are not there. The My Library frame
adds a sixth rail destination ("Thư viện của tôi") beside Home, Library,
Vocabulary, Progress and Profile. Both are the design's own drawing and settle
the question left open on 2026-09-23 in `UI_BACKEND_GAPS.md` ("where do the
learner's own words live") - they live in My Library.

## 7. Out of this lane

Admin Control Center and Speaking: the human assigned both to other lanes on
2026-09-23. Nothing in this audit is to be implemented for either.
