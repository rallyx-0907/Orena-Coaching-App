# Independent architecture review: the Vocabulary Deck

Status: **APPROVED** (round 1, §7), landed and applied to dev/sandbox only.
Migration: `migrations/versions/20260923_0014_vocabulary_decks.py`
Requested by: Claude lane (`claude/<task>`, working in `codex/work`)
Date: 2026-09-23
Reviewed commit: the tree at `eea6cf4`

`AGENTS.md`, "Architecture review authority": a schema/migration change
requires independent architecture review, and an implementer may not
self-approve its own. This is that request.

---

## 1. What changed the picture

The human's decision of 2026-09-23:

> Deck và My Library Collection là hai domain khác nhau. Deck là
> learning/review set của Vocabulary; Collection chỉ tổ chức item trong My
> Library.

The Vocabulary work shipped earlier the same day (`4f7b197`, frames 22–25)
used `library_collections` with `kind='word'` as the deck store. That is the
wrong domain. This request is the correction, not a new feature.

## 2. Why no existing table can hold a Deck

| Table | Why not |
| --- | --- |
| `library_collections` | My Library's relationship layer. `ORENA_COLLECTION_ARCHITECTURE.md` §1: "Collection is a query/projection across those owners and work, not a new authoritative copy". A study set is authoritative about its own membership. |
| `vocabulary_collections` | Its own docstring: "Collections are content, not learner state. A collection can be imported once and read by many learners." No owner column, and adding one would make shared content learner-scoped. |
| `saved_words` | One row per word. A set is not a property of a word; a word is in several sets. |

`ORENA_VOCABULARY_ARCHITECTURE.md` §1 lists "learner-created collections" among
what **Vocabulary** must support. There is no table for them today.

## 3. The proposal in one paragraph

Two tables in the Vocabulary domain: `vocabulary_decks` (owner, language,
title, cover token, version, timestamps) and `vocabulary_deck_members`
(deck, saved word, position, added_at). Ownership scope, uniqueness and
cascade all follow what `saved_words` and `library_items` already do. Nothing
is moved, copied or deleted from any existing table.

## 4. The decisions this request is asking a reviewer to test

1. **Domain placement.** Is a learner-owned study set Vocabulary's, given that
   Collection Architecture calls itself a projection layer? The proposal says
   yes.
2. **`cover` as a token, not a colour.** The frame draws a colour chooser. The
   column stores one of six names under a check constraint, so `theme.css`
   stays the only owner of what a colour *is* and a palette change is forced to
   be a migration. Alternative considered and rejected: a hex column, which
   would put colour values in learner data and outside the one colour owner
   (`ARCHITECTURE_INVARIANTS.md`, theme).
3. **`saved_word_id` with `CASCADE`.** A set is a set of the learner's words,
   so deleting a word leaves the sets. The alternative - keying membership on
   `entry_identity_key` so a set survives deleting and re-saving - was
   considered and rejected as the default: it would let a set contain words the
   learner no longer has, which is a different product promise than the frames
   make.
4. **Undo and membership.** `restore_library_record` restores a deleted word
   with its schedule (the ten-second undo). With `CASCADE`, restoring the word
   does **not** restore which sets it was in. This proposal deliberately does
   not solve that. Options for the reviewer: (a) accept the loss and say so in
   the undo copy; (b) carry memberships in the undo payload, which is a code
   change, not a schema one; (c) soft-delete membership, which is schema. The
   proposal's author prefers (b) and did not build it, because the choice is
   the reviewer's.
5. **Existing dev rows.** `4f7b197` created word-kind collections in the
   sandbox. The proposal leaves them where they are. Is a one-off carry-over
   wanted, or is leaving them as My Library collections correct?

## 5. What is blocked until this is reviewed

Frames 22–25 (save to a set, add word, create set) are wired to the Deck
contract in the code and answer `503 decks_unavailable` while the tables do not
exist. They are deliberately **not** wired back to `library_collections`: the
human's decision is that this is the wrong domain, and shipping the wrong
domain again to keep a screen green would be the worse failure.

## 6. Not requested here

- No production authorization is sought. Dev and sandbox only, and only after
  review.
- No change to `saved_words`, the SRS scheduler, or the `(identity_key,
  reading)` contract.
- No change to My Library's own collections, which keep doing what Collection
  Architecture says they do.

---

## 7. Review round 1 — the record (2026-09-23)

**VERDICT: APPROVED.**
**Reviewer:** Claude Sonnet 5, acting as Delegated Architecture Reviewer
(`AGENTS.md`, "Architecture review authority" — the Principal Architect role is
role-based, and a sufficiently capable independent model may fill it).
**Reviewed commit:** `9f94ad540da318d640791b6b3ba1263bf9b6e274`, tree clean.
**Human schema/runtime authorization:** given 2026-09-23 for **dev and sandbox
only**, explicitly not production, conditional on this approval.

### What the reviewer verified, not assumed

- The revision chain: `down_revision = 20260923_0013` matches the actual head,
  and does not collide with the unrelated chain also sitting in `proposed/`.
- **`models.py` against the migration, field by field** — columns, types,
  nullability, FK targets and `ondelete`, check constraints, uniques, indexes,
  and that `DECK_COVERS` is the same tuple as the migration's `COVERS`. The
  previous round's defect class (a partial index declared for one dialect only)
  cannot occur here because this migration declares no partial indexes.
- **Every citation in §2 of this request, against its source document.** All
  three quotations are exact, and the domain-placement argument holds.
- The cover palette: the six names are exactly the six `data-cover` selectors in
  `rooms.css`, and the frontend sources its palette from the API's `covers`
  field, which is `list(DECK_COVERS)` — one source of truth, no hex in learner
  data.
- Cross-tenant reachability: no DB constraint spans `vocabulary_decks.user_id`
  and `saved_words.user_id`, and the repository closes that at the application
  layer by scoping both lookups to `(user_id, language_code)` — verified by the
  two tests that try to reach another learner's and another language's set.
- Optimistic concurrency is actually enforced, and membership writes correctly
  do not touch `version`, because the promise is about title and cover.
- The read order is deterministic under a position tie.
- `tests/test_deck_repository.py`: **17 passed**, local execution in the
  hermetic container — not CI evidence.
- That the 503-until-migrated behaviour is real: the router is included and
  `configure_decks` is called, so the routes are reachable rather than dead.
- **Against the architecture hold** (`AGENTS.md` §7): this does not conflict.
  The hold reserves the canonical multi-user/account architecture, not ordinary
  single-account schema evolution, and `20260923_0013` already established this
  path — independent review, then a separate explicit human authorization for
  dev/sandbox.

### Findings, and what was done with each

| | Finding | Disposition |
| --- | --- | --- |
| **P2** | Undo does not restore deck membership: `restore_library_record` puts the word back but knows nothing of `vocabulary_deck_members`, so a learner who deletes a word that was in a set and undoes gets the word back without its sets, silently. The reviewer agreed CASCADE is the right schema choice and recommended **option (b)** from §4.4 — carry memberships in the undo payload, a code change, not a schema one. | **Taken.** Built immediately after landing, as the human also directed. Not a blocker for the migration. |
| **P3** | `version` has no `CHECK (version >= 1)`, unlike the sibling `library_items.version`. | **Taken** before landing. |
| **P3** | `ix_vocabulary_decks_scope` and `ix_vocabulary_deck_members_deck` omit the tie-break columns the read paths order by, so ordering is a sort rather than an index scan. | **Taken** before landing — both indexes now carry them. |
| **P3** | Title uniqueness is not case-folded, so "Reise" and "reise" can coexist. | **Deliberately left.** `uq_library_collection_title` has the identical property; changing one without the other would make two sibling tables disagree for no product reason. Recorded here instead. |

### Out of scope, per the reviewer

- Whether the `4f7b197` dev-only word-kind `library_collections` rows should be
  carried over — a data/product question, left to the human. **Answered
  2026-09-23:** do not convert; only sandbox/test records created by the wrong
  Save-to-deck implementation are to be handled separately, and on inspection
  there are none (both sandbox rows pre-date `4f7b197` by hours and were made
  through My Library's own "new set", so they are ordinary Collections).
- UI fidelity of the deck screens against the design — assessed elsewhere.
