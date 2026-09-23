# Thư viện của tôi + entry identity — architecture review request

Raised by Claude (`claude`/`codex/work` lane), following the path I2, I3, the
Vocabulary Source Catalog, the Reading Library and the Reading Content Engine
took: an additive Alembic migration proposed for independent architecture
review. **Nothing is applied.** The migration is
`migrations/proposed/20260923_0013_my_library_and_entry_identity.py`, which
Alembic does not read; the live head on this lane is `20260922_0012`.

**This lane does not approve it** (AGENTS "Architecture review authority": an
implementer may not self-approve its own high-risk architecture changes, and
schema/migration work requires independent review). Human schema/runtime
authorization is a separate gate after that and belongs to the human.

## 1. Why this exists

The human decided on 2026-09-23 what the two libraries are: **Vocabulary is the
shared content library** a learner takes words from, and **Thư viện của tôi is
the learner's personal library** of what they kept and what their learning
produced — referencing source content plus the learner's own state and
metadata, not duplicating content.

The audit against the implementation is
`docs/project/MY_LIBRARY_DATA_CONTRACT_AUDIT.md`. The content side already
matches; two things block the learner side, and this migration is the smallest
schema that unblocks them.

The first slice of the room shipped without them (`9ac6774`): it lists, counts,
searches and opens what the learner kept, over the owners that already exist.
Everything the frame draws that it could not build — the due card, the merged
review queue, the state pill, the mark button, collections, multi-select, the
detail overlay — is waiting on this.

## 2. What is proposed

### A. `saved_words` learns which entry, and which reading

Three additive columns: `entry_id` (FK `vocabulary_entries`, `SET NULL`),
`entry_identity_key` (durable, denormalised) and `reading_key`.

Today a saved word copies the catalogue's fields and is re-joined to it **by
normalised text** at read time (`writing_coach/becoming_library.py`,
`_catalog_resolver`). Text is not identity:

- 行 is `xíng` (to walk, a row) or `háng` (a trade, a line); 重 is `zhòng`
  (heavy) or `chóng` (again); 长 is `cháng` or `zhǎng`. One written form, two
  entries or two readings of one entry. Joined by characters, a learner's
  saved 行 resolves to whichever row the index returns.
- `vocabulary_entries` already models this — `identity_key` is unique,
  `sense_key` is inside it, and `readings` is a list. The text join discards
  all three.
- **Per-word pronunciation audio has to be keyed to a reading**, so it cannot
  be built on the text join at all. This is the foundation the human named for
  it, and the reason the audio work waits on this review rather than going
  first.

`entry_id` is the live link; `entry_identity_key` is what survives a catalogue
re-import that replaces a row with an equal one under a new UUID, and is what a
later audio record is keyed by. `ck_saved_words_entry_identity` holds that a
linked row always carries the durable key. A hand-saved word, or one from no
catalogue, carries neither and stays exactly as valid as it is today.

### B. `library_items`, `library_collections`, `library_collection_members`

`library_items` is `ContentMembership` from
`docs/product/ORENA_COLLECTION_ARCHITECTURE.md` §2: the learner's relationship
to a thing — never a copy of it. No body, no title, no snippet; those stay with
the owner and are read through `source_id`, or through `saved_word_id` for a
word.

Two shapes are load-bearing and are the main thing to review:

- **A word is linked, not named.** `saved_word_id` `ON DELETE CASCADE` under a
  biconditional check with `kind = 'word'`. Deleting a word removes its
  relationship with it, and no word row can drift onto a `source_id` string
  that means nothing. Every other kind carries `source_id` — the routing
  identity the app already opens things with — and a check holds it non-empty.
- **"One collection, one kind" is a database guarantee.** The frame says "mỗi
  bộ một loại". `library_collections` and `library_items` each carry a
  redundant `UNIQUE (id, kind)`; `library_collection_members` carries `kind`
  and references both by `(id, kind)`. A cross-kind membership cannot be
  written.

Uniqueness is two partial unique indexes rather than one constraint, because
`source_id` is empty for the whole `word` kind.

### C. What is deliberately *not* in it

- **No second review scheduler.** `library_items` has no `next_review_at`.
  Words are scheduled in `saved_words` and stay there. What the merged queue
  gets from this round is `pinned_at` — "mục bạn đánh dấu lên trước, sau đó
  theo hạn SRS" — which is exactly the ordering the design asks for, over the
  schedules that already exist. What a schedule would mean for a passage or a
  recording is a product question nobody has answered, and inventing one here
  would be the duplication this table exists to prevent.
- **No migration of `saved_words` into `library_items`.** A word keeps its
  owner. Whether saved words should eventually become `kind='word'` rows with
  their schedule moved is a data migration with its own risk, and belongs to
  its own review.
- **No backfill of `entry_id` / `entry_identity_key`.** Resolving three
  thousand existing saved words to catalogue entries is a data decision — which
  sense, which reading, and what to do when the text matches two entries — not
  a schema one. The columns arrive empty; the read path behaves exactly as it
  does today for a row that carries neither.
- **No `note` kind owner and no `book` ownership.** `note` is in the kind list
  so that adding its owner later is a code change rather than a schema change;
  nothing writes it yet.
- **No model mirror in `writing_coach/persistence/models.py`.** The mirror the
  hermetic suite uses lands with approval, not before it, so that nothing in
  `versions/`-shaped code exists for an unapproved proposal.

## 3. Rehearsal

Rehearsed against a throwaway PostgreSQL 16 (`postgres:16-alpine`, no volume,
port 55433, container removed afterwards) by pointing Alembic's
`version_locations` at `migrations/proposed` alongside `migrations/versions`:
`upgrade head` → `downgrade -1` → `upgrade head`. Result and the constraint
probes are in §5.

## 4. What the reviewer is asked to judge

1. Is `entry_identity_key` the right durability boundary, or should the link be
   the FK alone with re-import handled by keeping the row?
2. Is `reading_key` as a free string correct, given that no portable constraint
   can check it against a JSON list — and is the application-side invariant
   named in §6 sufficient?
3. The biconditional `kind = 'word'` ↔ `saved_word_id IS NOT NULL`, with
   `CASCADE`: correct, or does it make `library_items` two tables wearing one
   name?
4. The composite `(id, kind)` references: worth the redundant column, or
   over-constrained for something the application could check?
5. `state` as a nullable override of the owner's answer: is "NULL means ask the
   owner" a contract a reader can be relied on to honour?
6. Is a relation with `pinned_at` but no schedule a stable place to stand, or
   does the merged queue need the schedule to live in one table from the start?
7. Isolation and failure semantics of a pin/unpin and an add-to-collection
   under concurrency, given `version`.
8. Anything here that would be harder to change later than it looks.

## 5. Rehearsal record

Against `postgres:16-alpine` on port 55433, with `version_locations` pointing
at `migrations/versions` and `migrations/proposed`. `head` is ambiguous in that
configuration - the Reading Content Engine proposal branches at `0009` - so the
rehearsal names its own revision.

```
alembic heads            -> 20260922_0010 (head), 20260923_0013 (head)
upgrade 20260923_0013    -> current: 20260923_0013 (head)
downgrade 20260922_0012  -> current: 20260922_0012
upgrade 20260923_0013    -> current: 20260923_0013 (head)
```

Then `scripts/rehearse_my_library_schema.py`, which is in the repository so the
reviewer can re-run it. Twenty probes, each asserting the constraint it expects
by name:

| | |
| --- | --- |
| REFUSED | a linked saved word without its durable identity |
| REFUSED | an entry link with an empty identity key (`ck_saved_words_entry_identity`) |
| ACCEPTED | an entry link that carries its identity and its reading |
| ACCEPTED | a hand-saved word with neither |
| REFUSED | a word row with no saved word behind it (`ck_library_items_word_link`) |
| REFUSED | a reading row that points at a saved word (`ck_library_items_word_link`) |
| REFUSED | a non-word row with no source (`ck_library_items_source`) |
| REFUSED | a kind nobody draws (`ck_library_items_kind`) |
| ACCEPTED | the word the learner kept |
| REFUSED | keeping the same word twice (`ux_library_items_word`) |
| ACCEPTED | a passage the learner started |
| REFUSED | starting the same passage twice (`ux_library_items_source`) |
| ACCEPTED | keeping the passage as well as starting it |
| ACCEPTED | a collection of words |
| REFUSED | a collection with no name (`ck_library_collections_title`) |
| ACCEPTED | a word in a collection of words |
| REFUSED | a passage in a collection of words (`fk_library_member_collection`) |
| REFUSED | a passage smuggled in under the collection's kind (`fk_library_member_item`) |
| CASCADED | deleting a saved word removes its relationship and its membership |
| CASCADED | deleting the account removes what it kept and leaves the catalogue |

The rehearsal database was removed afterwards. Nothing was run against the
sandbox, preview or production runtimes.

**Not rehearsed, and named as such:** concurrency. The `version` counter and
the behaviour of a pin/unpin racing an add-to-collection were not exercised;
question 7 asks the reviewer whether they need to be before this lands, as the
commerce quota proposal's deadlock matrix was.

## 6. Where the application-side invariants live

Named here so the reviewer can see that what SQL cannot hold is held
somewhere, and so that a later implementer knows where to put it:

- `reading_key` must be one of the entry's own `readings` at write time. The
  write path is `writing_coach/becoming_library.py::save_library_vocabulary`,
  which already resolves the catalogue entry; the check belongs there, with the
  entry in hand.
- `state` is written only when the learner sets it; the read path treats NULL
  as "ask the owner" (for a word, `review_stage >= 3` is mastered, as
  `LIBRARY_MASTERED_STAGE` already defines).
- `version` is checked by the writer: an update carries the version it read and
  fails the write if it has moved, as `patch_learner_profile` already does for
  the profile.

## 7. Review rounds

_Nothing yet. This section records reviewer identity, reviewed commit, verdict
and what each round changed, as the earlier requests do._
