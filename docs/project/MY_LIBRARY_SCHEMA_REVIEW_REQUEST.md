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

`entry_id` is the live link. `entry_identity_key` was justified here by a claim
round 1 checked and falsified: the only import path there is
(`vocabulary_repository.py` ~511-624) looks an entry up **by identity key** and
merges in place, so `entry_id` already survives a re-import. The column stays
for the reason that does hold — it is the content-addressable identity a later
per-word audio record is keyed by, so audio is not tied to a surrogate id — and
as the hedge if a replace-rather-than-merge import is ever built. **Open
question for whoever owns vocabulary import: is such a path planned?** If it
never is, the column is a natural key the audio work wants anyway; if it is,
the column is required. Round 1 could not resolve this and neither can this
lane.

`ck_saved_words_entry_identity` holds that a linked row always carries the
durable key. A hand-saved word, or one from no catalogue, carries neither and
stays exactly as valid as it is today.

**A boundary this does not cross** (round 1, P3-1): `uq_saved_word_scope` is
unchanged, so one written form is still one saved row per learner and language.
This lets a learner's saved 行 say *which* sense it is; it does not let them
keep xíng and háng as two rows. That needs the unique constraint recomposed — a
later migration with its own review, not a gap in this one.

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

After round 1 the rehearsal is **24 probes**: the twenty above plus the four
round 1 asked for or found —

| | |
| --- | --- |
| ACCEPTED | a link to an ambiguous entry with no reading (recording the gap the write path must close, P2-2) |
| REFUSED | a word row that also carries a source string (`ck_library_items_source`, now a biconditional, P3-3) |
| RACED | two writers keeping the same word: one row, the other refused on `ux_library_items_word` |
| RACED | two writers pinning it: one update, one no-op, `version` 2 — no lost write |

The two races are real threads on real connections, not a simulation. Round 1
ran them ad hoc and resolved question 7 in the proposal's favour; they are in
the repository's rehearsal script now so the next change to this schema has to
keep them passing.

## 6. Where the application-side invariants live

Named here so the reviewer can see that what SQL cannot hold is held
somewhere, and so that a later implementer knows where to put it:

- `reading_key` must be one of the entry's own `readings` at write time, **and
  must be non-empty whenever that list holds more than one reading**. Round 1
  showed why the second half matters: a saved 重 can be linked to a
  two-reading entry with `reading_key = ''` and the database accepts it — the
  exact ambiguity the column exists to close, left open, because no portable
  constraint can read a JSON list. The write path is
  `writing_coach/becoming_library.py::save_library_vocabulary`, which already
  resolves the catalogue entry, so the check belongs there with the entry in
  hand, and it lands **with a regression test**: a link to an ambiguous entry
  and no reading must be refused. The rehearsal now carries a probe recording
  that the database itself accepts it, so nobody mistakes the schema for the
  guarantee.
- `state` is written only when the learner sets it; the read path treats NULL
  as "ask the owner" (for a word, `review_stage >= 3` is mastered, as
  `LIBRARY_MASTERED_STAGE` already defines).
- `version` is checked by the writer: an update carries the version it read and
  fails the write if it has moved, as `patch_learner_profile` already does for
  the profile. Round 1 verified this holds under a real race, and the rehearsal
  now carries that probe.
- The ordered read of a collection sorts by `(position, created_at)`. `position`
  has no unique constraint — keeping one would mean renumbering every member on
  every reorder — so ties are possible and the order is only deterministic if
  the reader breaks them (round 1, P3-4). The index carries both columns.

## 7. Review rounds

### Round 1 — APPROVED WITH REQUIRED CHANGES, addressed

| | |
| --- | --- |
| Reviewer | Delegated Independent Architecture Reviewer — fresh Claude subagent, no implementation context (AGENTS "Architecture review authority"; GPT-6/Codex unavailable) |
| Reviewed commit | `dc8b340` on `codex/work` |
| Verdict | **APPROVED WITH REQUIRED CHANGES** — two P2, four P3 |
| Method | Read the contracts, the audit, this request, the migration and the rehearsal; then **ran** the rehearsal independently on its own throwaway PostgreSQL 16 (`orena-review-pg-0013`, port 55434, removed afterwards), reproducing all 20 probes, and wrote three further probes of its own. Wrote nothing to the repository. |

**The DDL was found correct**: constraints, cascades and indexes do what the
docstring claims. The required changes were to the rationale and to the
application invariants riding on the schema — with one free tightening.

**P2-1 — the `entry_identity_key` rationale was false.** The proposal justified
the column by catalogue re-import replacing rows under new UUIDs. There is no
such path: `vocabulary_repository.py` looks an entry up by `identity_key` and
merges in place. *Fixed*: the migration docstring and §2.A now say so, keep the
column for the reason that does hold (the audio key), and record the open
question — is a replace-import path planned? — for whoever owns import. The
reviewer could not resolve it and neither can this lane.

**P2-2 — `reading_key` was not required where it matters.** The reviewer linked
a saved 重 to a real two-reading entry with `reading_key = ''` and the database
accepted it: the ambiguity the column exists to close, left open. *Fixed*: §6's
invariant is now "required when the entry is ambiguous", enforced at
`save_library_vocabulary` and landing **with a regression test**; the rehearsal
carries a probe that records what the database alone permits, so the schema is
never mistaken for the guarantee.

**P3-1 — `uq_saved_word_scope` still means one written form, one saved row.**
D1 says which sense a saved word is; it does not let a learner keep xíng and
háng apart. *Recorded* as a named boundary in §2.A and the docstring rather
than left implied by the 行/重/长 examples.

**P3-2 — no `CONCURRENTLY` / `NOT VALID` discipline.** Sub-second at today's
few thousand rows and confirmed so by the reviewer's own run; a real concern
only at the size AGENTS §7 reserves. *Recorded* in the docstring as the
discipline the migration that gets there will need.

**P3-3 — `ck_library_items_source` was one-directional.** A word row could
carry a stray `source_id`. *Fixed*: it is a biconditional now, with its own
probe.

**P3-4 — `position` has no tie-break.** *Fixed*: the index carries
`(collection_id, position, created_at)` and §6 states that the ordered read
sorts by both.

**Question 7 (concurrency) was resolved in the proposal's favour** by the
reviewer running the races rather than reasoning about them: the partial unique
index decides an insert race cleanly, and the `version` CAS decides an update
race with no lost write. Both probes are now in
`scripts/rehearse_my_library_schema.py`.

**Unverifiable, and left open:** whether a replace-rather-than-merge catalogue
import is planned (P2-1), and production-scale lock behaviour, which no
throwaway database can falsify (P3-2).

Re-rehearsed after these changes at `upgrade → downgrade → upgrade` with all
24 probes passing. **Still not approved for application**: human schema/runtime
authorization is a separate gate.
