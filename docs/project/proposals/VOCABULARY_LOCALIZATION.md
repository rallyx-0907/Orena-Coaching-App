# Vocabulary localization: one sense, many support languages

**Status:** PROPOSED, revision 2 (2026-10-04), after the independent review
`VOCABULARY_LOCALIZATION.REVIEW.md` (APPROVE WITH CONDITIONS on rev 1; responses in §9).
Direction is the human's (2026-10-04, recorded as D-124);
the schema in §5 needs independent architecture review and the human's authorization before
it moves from `migrations/proposed/` into `versions/` (`AGENTS.md` "Architecture review
authority"). Everything outside §5 is buildable on the existing schema and is marked so.

## 1. The product, stated once

```
canonical vocabulary sense  →  meaning in the learner's support language  →  card / SRS
```

- A **sense** exists once, independent of any support language. It is today's
  `vocabulary_entries` row: `identity_key = language | normalized term | POS | sense key`.
- A **localization** is a separate, reusable record keyed by **(sense, support language)**:
  the short meaning a learner whose support language is X reads for that sense.
- A **card** is rendered at read time from the sense plus the localization for the learner's
  current support language. Nothing about the learner's language is copied into the sense, and
  nothing about the sense's meaning is copied into the learner's record.

Lifecycle:

```
import corpus → normalize / sense identity → obtain localizations → validate → persist
→ publish → render (read-only, zero provider tokens)
```

Adding a support language is: register a localization source for the (target, support) pair
→ materialize its glosses. No product code, no learner UI change, no corpus duplication.

No paid model is part of ingestion, localization, publication, opening, review or SRS. The
learner-requested contextual explanation (Word Detail's "meaning in this sentence", Explain)
stays a separate optional capability and never writes corpus data. No decorative content
(hooks, mnemonics, stories, CTAs) is generated for a card because a field exists.

## 2. What exists today, measured

| Place | What it holds | Problem against §1 |
| --- | --- | --- |
| `vocabulary_entries.short_meanings` (JSON) | `[{language, text, origin}]` | Already sense × language, but embedded in the sense row. A published sense is an immutable snapshot (`import_source`, `published_entry_immutable`), so **a new support language cannot be added to a published collection** without a new version. |
| `vocabulary_collection_memberships.metadata.content_snapshot` | a copy of the sense's content when the shared entry was already published | Same: localizations frozen into a per-collection copy. |
| `saved_words.translation_vi`, `saved_words.definition` | text copied from the sense when the learner saved it | The learner's record carries one language's meaning. Changing support language or improving a gloss never reaches saved words. `vi` is in the column name. |
| `writing_coach/languages/*/vocabulary_collections.json` | 156 hand-authored curated entries with `support_translations: {vi, en}` | Fine as a curated localization source; the projection special-cases `vi`. |
| `vocabulary_cards.vocabulary_card_from_saved_word` | turns `translation_vi` into a `vi` meaning | Hard-codes `vi`. |
| New UI: `screens/collection/actions.js`, `review/model.js`, `word/model.js`, `library/model.js`, `quick-sheet/model.js`, `product/recall-modes.js` | write or read `translation_vi` | The client chooses and freezes a language. |
| Admin import | source columns only; `meaning_language` names the source's meaning language | Correct as source metadata; no localization stage. |
| Lookup (`reading_lookup.py`) | catalog meaning in the target language → dictionary → machine translation | Already the right order; MT result is per-request, never persisted. |

Why imported words miss support-language meanings: the importer is source-only by design, no
localization stage exists, there was no vendored dictionary (cost plan P1 unbuilt until
2026-10-04), and the only runtime fallback is per-tap translation that is not persisted (and on
:8021 the local translator is not provisioned, so it answers nothing).

## 3. Localization sources, in priority order

Each source is an adapter `(target_language, support_language) → gloss | None` with a stable
`source` id and `source_version`. The pipeline asks them in order and keeps the first that
passes validation. Order:

1. **Source corpus** — the imported list's own meaning when its language is stated. Never
   overwritten.
2. **Curated** — hand-authored packs (the 156 `support_translations` entries).
3. **Open bilingual lexical data** — direct dictionary data for the pair.
   - zh → en: **CC-CEDICT** (vendored 2026-10-04, `writing_coach/languages/chinese/lexicon_data`,
     CC BY-SA 4.0, 121,043 headwords). Built.
   - en → vi, zh → vi: no vendored bilingual data yet. Candidates are open datasets
     (Wiktionary translation tables via kaikki.org, CC BY-SA 4.0; FreeDict eng-vie). Each is a
     data/licence choice recorded before vendoring.
4. **Offline pivot translation** — the repository's own free Marian service
   (`services/local_translation`: en→vi, zh→vi, zh→en, en→zh), given the **dictionary sense as
   context, never a bare headword** (cost plan §2 finding: a bare 服 came back wrong). zh → vi
   translates CC-CEDICT's English sense with `opus-mt-en-vi`. Batch, at preparation time only.
   Its models must be provisioned once (free download); quality is sampled before a pair is
   enabled.
5. **None** — the card shows the sense's best available localization in another language,
   labelled by language, and Admin reports the gap. Never a model call.

A paid provider is not in this list. An operator may run a one-time, reviewed precompute for a
pair (cost plan P1 Tier 1) only as an explicit, separately authorized batch whose output lands
in the same localization store with `source = <that batch>`; it is never part of normal
ingestion.

## 4. Validation (deterministic)

A gloss is kept only when: non-empty after whitespace collapse; at most 160 characters; not an
echo of the headword; script fits the support language (no Han in a non-CJK support language,
Han present for zh); not a bookkeeping sense (`CL:`, `variant of`, `see …`); the source is
licensed for publication. A rejected candidate falls through to the next source and is counted
in the preparation report.

## 5. Schema (PROPOSED — needs rehearsal and authorization)

New table, content-owned (not learner-owned), rev 2:

```
vocabulary_sense_localizations
  id               uuid pk
  entry_id         uuid not null  → vocabulary_entries.id  ON DELETE CASCADE
  support_language varchar(20) not null      -- normalized primary tag
  gloss            text not null
  source           varchar(80) not null      -- 'source-list' | 'curated' | 'cc-cedict' | 'local_marian' | 'legacy-…'
  source_version   varchar(120) not null     -- dataset release / model id; never empty
  method           varchar(40) not null      -- source | curated | dictionary | pivot_translation | reviewed_batch
  selected         boolean not null default false
  selection_reason text not null default ''
  validation       jsonb (PostgreSQL) / json (SQLite) not null   -- rule version, checks; audit only
  created_at, updated_at timestamptz not null
  unique (entry_id, support_language, source)
  unique (entry_id, support_language) WHERE selected      -- one selected gloss per sense × language
  check (support_language, gloss, source, source_version all non-empty); check (method in …)
```

- **Alternates and audit (review P1-2).** Each source's gloss is its own row; exactly one is
  `selected`. Re-selecting is an operator action that writes `selection_reason`; the replaced row
  stays, so the rows are the history. Precedence (source list > curated > dictionary > pivot) is
  decided in code, never by insert order.
- **Additive to published content.** Inserting a localization mutates neither the sense row nor a
  published membership snapshot, so a new support language reaches a published collection without
  a new version. ON DELETE CASCADE removes a retired entry's localizations with it (entries are
  never deleted by the application today; `saved_words.entry_id` is SET NULL).
- **Backfill** (rev 2): `short_meanings` items in a support language other than the sense's own,
  tags normalized to their primary subtag; origins mapped explicitly (`source`, `curated`,
  `dictionary`; `prepared` → `legacy-prepared`, unverified; others → `legacy-unknown`); duplicates
  kept as alternates with the highest-priority origin selected; over-length legacy glosses kept and
  marked; entries read in chunks. One transaction; re-runnable only after a downgrade.
- `short_meanings` stays the **source corpus's** own meanings and stops being where
  support-language glosses accumulate once the table is live.
- `saved_words.translation_vi` / `definition` are **not dropped** (learner data, `AGENTS.md` §7).
- No extra `(support_language, entry_id)` index (review P2-5): the read path is
  `entry_id IN (…) AND support_language = ? AND selected`, served by the partial unique index.
- **Rollout (review P3-3).** Schema first, as an operator step after a backup; then code. Until the
  table exists, or while it is empty, the read path uses `short_meanings` exactly as today.

Proposed revision: `migrations/proposed/20261004_0025_vocabulary_sense_localizations.py`, parented
on the current head `20260930_0023`; re-parented on 0024 at promotion if that proposal is
promoted first (the tables are independent).

## 6. Read path

Built 2026-10-04 (no schema): the server already returns each saved word and catalogue card with
the sense's localizations, every one tagged by language (`short_meanings[]`,
`support_translations{}`). One shared, pure function, `static/orena/product/vocabulary-meaning.js`,
chooses for the learner's current support language: the sense's localization → the learner's own
note → the sense's localization in another language (tagged) → none. Review, Word and My Library
use it; Collection "Add all" no longer copies a support-language meaning into the saved word. The
learner record's older `translation_vi` is read only as the Vietnamese localization, after the
sense's own. Once the table exists, the server fills the same tagged list from it; the client does
not change. Pure read; no provider.

**Projection order with snapshots (review P1-1).** Localizations are not part of the membership
snapshot contract, and `_VOCABULARY_CONTENT_SNAPSHOT_FIELDS` never gains a localization field. A
card is projected as: entry row → membership `content_snapshot` (if any) → additive merge of the
**selected** localization rows, per support language. A snapshot's own item for a language is kept
over the table row only as an explicit collection-scoped override; otherwise the table row is added
for any language the snapshot lacks. A test covers a published entry shown through a snapshot plus a
newly inserted `vi` row.

## 7. What is buildable before §5 is approved

- The localization source registry, validation and preparation report (§3, §4) — built against
  a `LocalizationStore` port. Until the table exists, the store writes into `short_meanings` of
  **unpublished** senses only (today's rule) and reports published senses as "needs the
  localization table".
- §6's read path over today's data, and moving the UI off `translation_vi` for catalog-linked
  words (done 2026-10-04).
- CC-CEDICT completion at import and in lookup (done 2026-10-04).
- Provisioning the free Marian models on the lane runtime and sampling pivot quality for
  zh→vi and en→vi before any pair is enabled.

## 8. Open questions for the human

1. Which open dataset (if any) is accepted for en→vi and zh→vi direct glosses before falling
   back to offline pivot translation (licence: CC BY-SA vs GPL).
2. Visible attribution for CC-CEDICT (CC BY-SA 4.0 §3(a)): the pinned design draws no credit
   line on cards; where it appears (Word Detail footer, an About/credits page) is a design
   decision. Required before public release.
3. Whether a one-time paid Tier-1 precompute is ever wanted for quality, as a separately
   authorized batch.

## 9. Review responses (rev 2)

| Finding | Response |
| --- | --- |
| P1-1 snapshot vs table order | §6: entry → snapshot → additive merge of selected rows; snapshot never carries localizations; test required with the read-path change. |
| P1-2 single row, no audit | §5: rows keyed by source, one `selected`, `selection_reason`; replaced rows kept. |
| P2-1 origin mapping | Explicit map incl. `curated`; `legacy-prepared` (unverified) and `legacy-unknown`; non-empty `source_version` enforced by CHECK. |
| P2-2 hygiene | Primary-tag normalization, origin priority on duplicates (alternates kept), over-length marked. |
| P2-3 idempotency wording, volume | Reworded; chunked reads and inserts; rehearsal at 100k required (condition 4, open). |
| P2-4 JSON type | JSONB on PostgreSQL, JSON on SQLite; audit only. |
| P2-5 index | Dropped; the partial unique index serves the read path. |
| P2-6 chain | Parented on 0023; re-parent on 0024 at promotion if needed; README updated at promotion. |
| P3-1 cascade | Recorded in §5. |
| P3-2 `translation_vi` writes | Recorded as a human decision: `accbbfb` stopped copying a support-language meaning into the saved word on Collection "Add all" (D-124). The old UI at `/` reads `definition \|\| translation_vi`, so a word added that way in `/next` shows no Vietnamese line in the old UI until the cutover. |
| P3-3 rollout | §5 rollout; read path tolerates absent/empty table. |

Rehearsal (2026-10-04, throwaway PostgreSQL 16 on tmpfs, chain 0001→0023 then 0025): 100,000
seeded entries with mixed origins/tags/over-length/unknown items → upgrade 5.3 s, 166,668 rows,
133,334 selected (exactly the expected split); probes refused a second selected row for one
sense × language, an empty `source_version` and an unknown `method`; down/up restored the same
counts. The rehearsal first caught an untyped backfill table that could not bind JSONB, fixed in
rev 2. SQLite cannot run the Alembic chain (0010 alters constraints), so the SQLite test backend
gets the table from the ORM mirror when the read path is built. Open before promotion: the human's
authorization, scoped to :8021.
