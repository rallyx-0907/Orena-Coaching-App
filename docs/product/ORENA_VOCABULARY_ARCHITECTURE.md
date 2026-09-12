# Orena Vocabulary Library and Card Architecture

Status: AUTHORITATIVE PRODUCT/ARCHITECTURE CONTRACT

This document defines Vocabulary as a canonical learning domain and the Orena
Vocabulary Card as its learning-object model. It operates under
`docs/product/ORENA_PRODUCT_CONSTITUTION.md` and
`docs/product/ORENA_CONTENT_ARCHITECTURE.md`.

Origin: `docs/product/ORENA_PHILOSOPHY_AMENDMENT_CONTENT_UNDERSTANDING.md`,
accepted as D-049 in `docs/project/DECISION_LOG.md`.

Relationship to existing contracts: `ORENA_COLLECTION_ARCHITECTURE.md` already
owns the **relationship** layer — `LanguageItemRef`, saved-word identity,
encounter provenance, and retrieval/pagination for "My Language". This document
owns what the saved **object** itself contains. Collection points at a
Vocabulary Card; it does not define one.

---

## 1. Core principle

Vocabulary is a real, curated library of Orena Vocabulary Cards, not only a
flat word list and not only a byproduct of saving words while reading.

Vocabulary must support:

- topic-based collections (Airport English, Workplace English, Technology,
  Emotions, Phrasal Verbs, HSK topic sets, Industrial Automation English, and
  similar);
- Orena-curated collections;
- imported collections where supported;
- learner-created collections;
- words and phrases extracted from Reading or Listening encounters;
- professional/domain-specific collections;
- language-specific card formats (§4).

Vocabulary must be able to grow independently of the other domains. A learner
should be able to explore and build vocabulary depth without that depth
depending on how much Reading or Listening content currently exists.

---

## 2. The Orena Vocabulary Card

A card is richer than `word -> translation`. Depending on language and
available material, a card may hold:

- headword;
- pronunciation notation (IPA, Pinyin, or the relevant system);
- pronunciation audio;
- meaning(s), with sense boundaries kept distinct rather than merged into one
  string;
- a core semantic image or mental model, drawn from the Language Knowledge
  Graph (`docs/product/ORENA_UNDERSTANDING_ENGINE.md` §5) when one exists and
  genuinely helps — a card is not required to invent one;
- natural examples;
- collocations;
- related or contrasting expressions;
- common learner traps (a documented wrong assumption, not an invented one);
- images, where sourced appropriately;
- source encounters — where this word was actually met, reusing
  `EncounterProvenance` (`ORENA_COLLECTION_ARCHITECTURE.md` §2) rather than a
  second provenance model;
- learner-created examples;
- links into relevant Understanding Engine explanations;
- memory/practice state, owned by the existing Active Recall scheduler
  (`ORENA_EVIDENCE_ARCHITECTURE.md` §1, §4) — a card references that state, it
  does not fork a second one.

Not every field applies to every language or every card. A card must not
invent a value merely to fill an unused field; an absent field is absent, not
a placeholder.

---

## 3. Card identity and the existing saved-word seam

A Vocabulary Card is the canonical library object; the learner's saved
relationship to it is the existing `LanguageItemRef`/`SavedWord` object
(`ORENA_COLLECTION_ARCHITECTURE.md` §1-2,
`writing_coach/persistence/models.py:SavedWord`). Enriching the card model
does not change that a save is a relationship, not a new origin, and does not
change existing word normalization/identity rules — this document adds what
the referenced object may contain; it does not reopen how saving, occurrence
identity, or review scheduling already work.

Where a learner has no card yet for a word they saved (today's baseline
behavior), the saved relationship remains valid on its own. A richer card
becomes available progressively as the library grows; a learner is never
blocked from saving a word merely because no full card exists yet.

---

## 4. Orthography is a first-class card capability

For a writing system where the visual form matters to learning (Chinese
Hanzi today; generalizing later to Japanese Kanji/Kana, Korean Hangul
composition, Arabic joining forms, and other scripts as they are added), a
card may carry a dedicated **orthography** section.

The internal capability name is the general `orthography`, never a
language-hardcoded name such as `chinese_stroke_order`. A script-specific
renderer is a language adapter over this one capability
(`ORENA_PRODUCT_CONSTITUTION.md` §22, `ARCHITECTURE_INVARIANTS.md`
"Multilingual product": language adapters exist only for genuine linguistic
differences, and every adapter still implements the same shared capability).

For Chinese, an orthography section may hold:

- the Hanzi;
- Pinyin;
- pronunciation audio;
- stroke count;
- radical;
- character components;
- stroke order;
- animated stroke writing;
- step-by-step stroke practice mode;
- tracing practice;
- free-writing practice;
- handwriting feedback, later, and only as an explicit accepted extension —
  this document specifies the data shape, not a commitment to ship automated
  handwriting scoring.

Illustrative shape for a multi-character word:

```text
休息  (xiūxi)
├── meaning / usage
├── examples
└── orthography
    ├── 休 — radical, components, stroke count, stroke order
    └── 息 — radical, components, stroke count, stroke order
```

### Accuracy rule

Character decomposition, radical stories, and visual mnemonics may be used
when they genuinely aid memory. `docs/product/ORENA_UNDERSTANDING_ENGINE.md`
§4's rule applies without exception: verified character etymology, modern
structural decomposition, and learner mnemonic are three different things and
must be labeled as what they are. A memorable radical story is never
presented as documented history merely because it is easy to remember.

---

## 5. Shared infrastructure, not a private pipeline

Vocabulary reuses the same shared infrastructure every domain reuses
(`ORENA_CONTENT_ARCHITECTURE.md` §4): ingestion/ admission
(`ORENA_CONTENT_EXECUTION_ARCHITECTURE.md` §1, §3 for anything requiring
generation or an external source), rights/provenance, search, tagging,
recommendation, and asset storage for pronunciation audio and images.

Vocabulary does not need its own parallel job/execution model. A card that
requires generation (an example sentence, a mental-model image, pronunciation
audio) is one more consumer of the existing expensive-operation contract, with
its own capability identity.

---

## 6. Scale and quality

The target is a substantial default library over time — hundreds to
thousands of cards across curated collections — not one or two sample
collections kept "deliberately small" indefinitely. See
`docs/product/ORENA_CONTENT_ARCHITECTURE.md` §18 (Content scale) for the
shared principle: a smaller curated library is better than a large noisy one,
but smallness is not itself a goal once curation capacity exists.

Growing the library is batch/incremental work, not a one-card-at-a-time
manual edit to a hardcoded array — the same infrastructure principle
`ORENA_CONTENT_ARCHITECTURE.md` §18 sets for every domain.

---

## 7. Review question

Does this card help the learner retain and reuse the word, or does it only
restate a translation?

Does an orthography section, where present, distinguish verified fact from
mnemonic?

Would a second script (Japanese, Korean, Arabic) reuse this same capability
without a rewrite?

Is the collection this card belongs to something a learner would recognize as
curated, or does it read as an arbitrary leftover from implementation
convenience?
