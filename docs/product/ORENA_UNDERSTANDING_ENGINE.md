# Orena Understanding Engine

Status: AUTHORITATIVE PRODUCT/ARCHITECTURE CONTRACT

This document defines Orena's mental-model explanation capability and the
Language Knowledge Graph that supports it. It operates under
`docs/product/ORENA_PRODUCT_CONSTITUTION.md` and extends the existing
`Understanding` capability already named in `ORENA_REFERENCE_ARCHITECTURE.md`
§6-7 and `ORENA_EVIDENCE_ARCHITECTURE.md` §1 (`ui/understanding.js`, source-bound
explanation evidence). This is a deepening of that seam, not a parallel system.

Origin: `docs/product/ORENA_PHILOSOPHY_AMENDMENT_CONTENT_UNDERSTANDING.md`,
accepted as D-049 in `docs/project/DECISION_LOG.md`.

---

## 1. What this capability is for

Orena should let a learner ask about almost anything in the target language and
receive an explanation built to create a mental model, not a memorized
translation or an isolated grammar rule.

A chatbot-style question box is one interface to this capability. The
capability itself must be reusable from Reading, Listening, Speaking, Writing,
Vocabulary, Grammar, and any future learning experience through the same
source-bound `Understanding` seam `ORENA_REFERENCE_ARCHITECTURE.md` §3 already
defines (`ExperienceContext.focus`: exact selection plus the context that
contains it). An explanation is never generated from a bare word alone when a
source context exists.

This is a horizontal Orena capability. It must not become a chatbot feature
isolated from the rest of the product.

---

## 2. Explanation philosophy

Orena must not default to:

- dictionary-definition dumping;
- long lists of unrelated meanings;
- grammar-rule memorization presented as the whole answer;
- translation-only explanations;
- "because English/Chinese works that way";
- fabricated etymology;
- opaque linguistic jargon offered without intuition.

The question the engine tries to answer is:

> What mental model would make this usage feel natural?

Preferred explanation flow, used as a guide rather than a rigid template every
answer must fill:

1. identify what is actually confusing about this instance;
2. give the core idea;
3. offer a visual, physical, or semantic mental model;
4. connect this usage to other usages that share the same underlying idea;
5. contrast nearby concepts when that removes real confusion;
6. show natural examples;
7. name the common wrong model a learner might otherwise form;
8. optionally offer a small comprehension check;
9. let the learner save the concept into their Language Knowledge collection.

### Worked example: "off"

A poor approach lists unconnected translations (off = turn off; off = a day
away from work; off = leave; and so on) and stops there — memorization without
understanding.

A useful Orena explanation instead names a core image and connects usages to
it: imagine two things connected, attached, or in the same state; **off**
carries separation, removal, departure, or disconnection from that state.
*Take off your coat* separates it from the body. *The plane takes off*
separates from the ground. *A day off* separates from the work routine. *Turn
the light off* disconnects the device from its active state.

The point is not that this image is the historically true origin of every
sense. It is a useful, honest mental model — see §4 for the rule that keeps it
honest.

---

## 3. The engine is shared, not per-capability

The same capability answers the same kind of question regardless of where it
was asked:

| Capability | Trigger | What the engine receives |
| --- | --- | --- |
| Reading | Learner highlights *gave in* and asks why | The phrase, its sentence, and surrounding paragraph |
| Listening | Learner asks about *up for it* from a subtitle | The phrase and the segment/transcript context |
| Vocabulary | Learner asks why *off* works across a card's examples | The card's headword and its stored examples |
| Writing | Feedback flags *I very like this*; learner asks why | The flagged span and the learner's own sentence |
| Speaking | Learner asks why *go home* has no "to" | The learner's turn and the flagged span |

Every entry path resolves through the existing `ExperienceContext`/`resolve()`
seam (`ORENA_REFERENCE_ARCHITECTURE.md` §3, `ORENA_BACKBONE_CONTRACTS.md` §2-3).
No capability owns a private copy of the explanation engine, and no capability
may bypass exact-context capture to ask about "a word" detached from where the
learner encountered it.

Read-only explanation never creates a graded attempt; saving a concept and
receiving feedback on a submission remain separate, explicit learner actions,
per `ORENA_REFERENCE_ARCHITECTURE.md` §3's existing rule.

---

## 4. Accuracy rule: mental model vs. verified fact

Orena may use core-image mental models, structural decomposition, and
memorable stories when they genuinely help a learner retain something.

The engine must always distinguish, and must never blur:

- a **useful mental model or mnemonic** — an explanatory device chosen because
  it helps understanding, not because it is claimed to be historically true;
- **verified etymology or structural fact** — sourced from an actual
  linguistic reference, not generated as a plausible-sounding story.

A mnemonic must never be presented as historical fact merely because it is
memorable. If a learner explicitly asks for true word origin, the answer must
come from an actual etymological source and say so plainly when no verified
source is available, rather than generating a confident-sounding invention.

This rule applies identically to character decomposition for Chinese and any
other script (see `docs/product/ORENA_VOCABULARY_ARCHITECTURE.md` §4): a
radical/component story that aids memory is labeled as a memory aid, not
presented as the character's documented history, unless it is.

This is the same truthful-generation discipline `ORENA_CONTENT_ARCHITECTURE.md`
§2 and §17 already require of generated content; the Understanding Engine is
not exempt from it merely because its output is conversational.

---

## 5. The Language Knowledge Graph

The engine should accumulate reusable conceptual knowledge instead of
regenerating every answer independently from nothing.

A knowledge entry can hold, where relevant:

- the concept identity (a word, phrase, pattern, particle, preposition, or
  grammar structure);
- a core semantic image, when one is established and useful;
- known extensions/usages that share that core idea;
- related or contrasting concepts (`ON <-> OFF`);
- example sentences and the sources they came from;
- the distinction from §4: which parts are verified fact and which are
  mnemonic;
- language and, where relevant, script.

Conceptual shape, illustrative only:

```text
OFF
├── core semantic image: separation / removal / departure / deactivation
├── take off / get off / cut off / day off / I'm off  (usages sharing the image)
└── related: ON (contrast)
```

A concept does not need one forced "master meaning" to be useful. The graph
exists to preserve explanation patterns and relationships that genuinely help,
not to reduce every sense of a word to a single oversimplified rule.

### Relationship to existing Language Knowledge ownership

`ORENA_BACKBONE_CONTRACTS.md` §1 already names a **Language knowledge** domain
owner (`linguistic behavior and canonical Concept IDs`, anchored today at
`writing_coach/languages/` and the static Grammar KB). The Language Knowledge
Graph is that domain's canonical object model, broadened beyond grammar
concept IDs to the fuller set above. It does not replace stable Grammar
Concept IDs (`ARCHITECTURE_INVARIANTS.md` "Closed-stage protection", R5): a
grammar pattern's Concept ID remains its identity; the graph adds the
explanatory layer around it and around non-grammar concepts (words, phrases,
particles, contrasts) that R5 never covered.

The graph is shared infrastructure per
`docs/product/ORENA_CONTENT_ARCHITECTURE.md` §4 ("Shared infrastructure,
separate domains"): every learning domain may read from it and contribute
verified or reviewed entries to it; no domain forks a private copy.

---

## 6. Evidence and what saving a concept means

Saving an Understanding Engine explanation into a learner's Language Knowledge
collection is a **kept relationship**, using the same kind of relationship
`ORENA_COLLECTION_ARCHITECTURE.md` already defines for saved words and phrases
(`My Language`). It is not itself a demonstration of use or recall; Active
Recall remains the owner of whether saved language is retrievable later, per
`ORENA_EVIDENCE_ARCHITECTURE.md` §1's existing `Understanding` and `My
Language` rows.

`Understanding` evidence stays exactly what `ORENA_EVIDENCE_ARCHITECTURE.md`
§1 already says: source-bound explanation and an optional learner question.
Receiving an explanation is not evaluated learner performance. This document
adds the Knowledge Graph the explanation draws on; it does not change what
counts as evidence.

---

## 7. Implementation notes for later architecture work

Not authorized by this document: any new persistence, schema, or provider
activation. This is a product/architecture contract, matching the status of
`ORENA_REFERENCE_ARCHITECTURE.md` and its companions.

When implementation is scheduled (see `docs/project/ROADMAP.md`, "Content
Domains & Understanding Engine"), the ordered seam is:

1. a pure decision layer for what an explanation request needs before calling
   any provider — exact selection present, context contains selection, a
   distinguishable mental-model-vs-fact response shape — mirroring how
   `writing_coach/reference_backbone.py` already separates pure decisions from
   persistence for the account/commerce backbone;
2. a read-through Knowledge Graph lookup before generation, so a concept
   already explained well is reused rather than regenerated inconsistently;
3. generation as a fallback/enrichment path when no adequate entry exists,
   written back to the graph only after a review/moderation step appropriate
   to its confidence (a first-seen mnemonic is not the same trust level as a
   sourced etymological fact);
4. the existing per-capability entry points (Reading, Listening, Vocabulary,
   Writing, Speaking) each call the same seam rather than each capability
   building its own explanation prompt from scratch.

Any schema this needs is a new proposal under the existing architecture-review
gate (`AGENTS.md` §1): an implementer does not self-approve it, the same
constraint already governing the I2/I3 backbone schema proposals.

---

## 8. Review question

Before presenting Understanding Engine work as reviewable, ask:

Does the explanation start from what is actually confusing, or does it dump
information regardless of the question asked?

Does it clearly separate a mental model from a verified fact whenever both are
present?

Can the same explanation be reached from at least two different capabilities
without a capability-specific reimplementation?

Does it degrade honestly (no fabricated confident answer) when the graph has
no entry and generation is unavailable?
