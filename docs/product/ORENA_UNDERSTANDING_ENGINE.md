# Orena Understanding Engine

Status: AUTHORITATIVE PRODUCT/ARCHITECTURE CONTRACT

This document defines Orena's mental-model explanation capability. It operates
under `docs/product/ORENA_PRODUCT_CONSTITUTION.md` and extends the existing
`Understanding` capability already named in `ORENA_REFERENCE_ARCHITECTURE.md`
§6-7 and `ORENA_EVIDENCE_ARCHITECTURE.md` §1 (`ui/understanding.js`, source-bound
explanation evidence). This is a deepening of that seam, not a parallel system.

Origin: `docs/product/ORENA_PHILOSOPHY_AMENDMENT_CONTENT_UNDERSTANDING.md`,
accepted as D-049 in `docs/project/DECISION_LOG.md`, corrected by D-050. **D-050
supersedes this document's own earlier revision and the amendment's §2.6/§7,
§17 framing**: the Understanding Engine is a horizontal capability over
Orena's five content domains, not a sixth domain, and it is not built on a
required precomputed knowledge repository. See §5.

---

## 1. What this capability is for

Orena should let a learner ask about almost anything in the target language
and receive an explanation built to create a mental model, not a memorized
translation or an isolated grammar rule.

Conceptually:

```text
Reading / Writing / Listening / Speaking / Vocabulary
                    |
           Understanding Engine
```

The engine is a **horizontal capability shared across Orena's five content
domains** (`docs/product/ORENA_CONTENT_ARCHITECTURE.md` §1) — it is not a
sixth learner-facing content library, and a learner does not "browse" it the
way they browse a Reading or Vocabulary library. A chatbot-style question box
is one interface to it; the capability itself is reachable from Reading,
Listening, Speaking, Writing, and Vocabulary alike through the same
source-bound `Understanding` seam `ORENA_REFERENCE_ARCHITECTURE.md` §3 already
defines (`ExperienceContext.focus`: exact selection plus the context that
contains it). An explanation is never generated from a bare word alone when a
source context exists.

This is a horizontal Orena capability. It must not become a chatbot feature
isolated from the rest of the product, and it must not be reframed as a
seventh piece of stored content learners retrieve.

---

## 2. Principle: AI-first, not database-first

The engine is:

> AI-first, context-grounded, format-constrained, cache/retrieval-assisted.

It is **not**:

> database-first, or built on a required precomputed knowledge repository.

An explanation is generated live from the learner's exact context using the
Orena Explanation Contract (§3), not looked up from a pre-built answer store.
At the scale Orena targets, pre-storing an answer for every possible question
a learner might ask is neither feasible nor the right model — most questions
are about an exact sentence, an exact media segment, or an exact draft, which
cannot be fully anticipated in advance.

Caching and retrieval exist to make repeated or similar questions cheaper and
more consistent, never to replace context-grounded generation:

```text
context -> cache/retrieval check -> AI explanation -> validation -> response
        -> reusable cache where appropriate
```

An exact-context question is still generated from the learner's real
sentence, media segment, draft, or speech turn even when a cache exists;
cache/retrieval may supply a reusable fragment (a known-good core image for a
word, a previously validated contrast) that generation composes into the
context-specific answer, not a substitute for reading the context at all.

A structured knowledge store **may** be introduced later if it proves useful
for consistency or cost — see §5. It is an optional optimization, never a
prerequisite for the engine to function, and never itself a canonical
learner-facing content domain.

---

## 3. The Orena Explanation Contract

An explanation response has a bounded, format-constrained shape rather than
free-form prose of arbitrary structure. Fields, used as a guide rather than a
rigid template every answer must fill:

- **core idea** — the single thing actually confusing about this instance;
- **mental model / intuitive image** — a visual, physical, or semantic image
  that makes the usage feel natural, when one genuinely helps;
- **why the form works here** — grounded in the learner's exact context, not
  a generic rule recited regardless of what they asked about;
- **related usages** — other instances that share the same underlying idea,
  where that connection is real and useful;
- **contrasts** — a nearby concept that removes real confusion when
  distinguished, not contrast for its own sake;
- **common misunderstanding** — the wrong model a learner might otherwise
  form;
- **natural examples**;
- **optional quick check** — a small comprehension prompt, not required.

The learner may save the resulting explanation into their Language collection
(`ORENA_CONTENT_ARCHITECTURE.md` §12, "My Language") as a kept relationship,
the same kind of relationship already defined for saved words and phrases.

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

## 4. Accuracy rule: four things that must never be blurred

Orena may use core-image mental models, structural decomposition, and
memorable stories when they genuinely help a learner retain something. The
engine must always distinguish, and must never blur, four different kinds of
statement:

- a **mental model** — a deliberately simplified image or intuition chosen to
  make a usage feel natural, understood by both engine and learner as a
  teaching device rather than a claim about how the language "really" works;
- a **mnemonic** — a memory aid (a character-decomposition story, a shape
  association) chosen because it is memorable, not because it is claimed to
  be true;
- a **linguistic explanation** — an actual grounded account of grammar,
  semantics, or usage (e.g., aspect, transitivity, register) that is
  linguistically defensible even though it is not a historical claim;
- **verified etymology / history** — a sourced claim about a word's or
  character's actual documented origin.

A mnemonic or mental model must never be presented as verified etymology or
history merely because it is memorable or intuitive. If a learner explicitly
asks for true word origin, the answer must come from an actual etymological
source (§5) and say so plainly when no verified source is available, rather
than generating a confident-sounding invention.

This rule applies identically to character decomposition for Chinese and any
other script (see `docs/product/ORENA_VOCABULARY_ARCHITECTURE.md` §4): a
radical/component story that aids memory is labeled as a mnemonic, not
presented as the character's documented history, unless it is.

This is the same truthful-generation discipline `ORENA_CONTENT_ARCHITECTURE.md`
§2 and §16 already require of generated content; the Understanding Engine is
not exempt from it merely because its output is conversational.

---

## 5. The explanation support layer, not a required Knowledge Graph

The engine is supported by a layer of resources that reduce cost and improve
consistency, without being a prerequisite for it to work at all:

- **trusted linguistic references** — dictionary, corpus, and etymology
  sources consulted when a claim needs grounding, especially for §4's
  verified-etymology case;
- **reusable explanation patterns** — a validated core image or contrast that
  worked well before, reused rather than regenerated inconsistently, without
  claiming it is the only valid explanation;
- **caching** — a previously generated, validated explanation for the same or
  a near-identical context, served instead of regenerating it;
- **retrieval** — fetching a relevant reference or prior explanation to
  ground a new generation, not to replace it;
- **quality/grounding validation** — a check that a generated explanation's
  factual claims (etymology, linguistic rule) are actually supported before
  it is shown or cached, and that §4's four categories are not blurred.

None of this constitutes a sixth canonical content domain, and none of it is
a database that must exist before the engine can answer a question. A small
Orena deployment can run the engine with no cache and no reference layer at
all — correctly, if more slowly and at higher cost per question — by
generating every answer fresh and being honest about which of §4's four
categories each part of the answer is.

**A structured knowledge graph is an optional future optimization**, not a
prerequisite: if a specific concept (a preposition, a common contrast) proves
to be asked about often enough that a curated, reviewed entry measurably
improves consistency or cost, that entry may be added to a lightweight
reference store consulted during retrieval. This is never required before the
engine can be built or shipped, and it is never presented to the learner as a
library they browse — it is implementation-detail plumbing behind the
explanation contract in §3.

### Relationship to existing Language Knowledge ownership

`ORENA_BACKBONE_CONTRACTS.md` §1 already names a **Language knowledge** domain
owner (`linguistic behavior and canonical Concept IDs`, anchored today at
`writing_coach/languages/` and the static Grammar KB). The Understanding
Engine's explanation capability extends that owner's responsibility — it
answers open-ended "why does this work" questions using linguistic
explanation (§4) grounded where needed by that owner's existing linguistic
behavior — without adding a new mandatory data store on top of it. It does
not replace stable Grammar Concept IDs (`ARCHITECTURE_INVARIANTS.md`,
"Closed-stage protection", R5): a grammar pattern's Concept ID remains its
identity; the engine may reference it as grounding for a linguistic
explanation without duplicating the curriculum.

---

## 6. The engine is shared, not per-capability

The same capability answers the same kind of question regardless of where it
was asked:

| Domain | Trigger | What the engine receives |
| --- | --- | --- |
| Reading | Learner highlights *gave in* and asks why | The phrase, its sentence, and surrounding paragraph |
| Listening | Learner asks about *up for it* from a subtitle | The phrase and the segment/transcript context |
| Vocabulary | Learner asks why *off* works across a card's examples | The card's headword and its stored examples |
| Writing | Feedback flags *I very like this*; learner asks why | The flagged span and the learner's own sentence |
| Speaking | Learner asks why *go home* has no "to" | The learner's turn and the flagged span |

Every entry path resolves through the existing `ExperienceContext`/`resolve()`
seam (`ORENA_REFERENCE_ARCHITECTURE.md` §3, `ORENA_BACKBONE_CONTRACTS.md` §2-3).
No domain owns a private copy of the explanation engine, and no domain may
bypass exact-context capture to ask about "a word" detached from where the
learner encountered it.

Read-only explanation never creates a graded attempt; saving an explanation
and receiving feedback on a submission remain separate, explicit learner
actions, per `ORENA_REFERENCE_ARCHITECTURE.md` §3's existing rule.

---

## 7. Evidence and what saving an explanation means

Saving an Understanding Engine explanation into a learner's "My Language"
collection is a **kept relationship**, using the same kind of relationship
`ORENA_COLLECTION_ARCHITECTURE.md` already defines for saved words and phrases.
It is not itself a demonstration of use or recall; Active Recall remains the
owner of whether saved language is retrievable later, per
`ORENA_EVIDENCE_ARCHITECTURE.md` §1's existing `Understanding` and `My
Language` rows.

`Understanding` evidence stays exactly what `ORENA_EVIDENCE_ARCHITECTURE.md`
§1 already says: source-bound explanation and an optional learner question.
Receiving an explanation is not evaluated learner performance.

---

## 8. Implementation notes for later architecture work

Not authorized by this document: any new persistence, schema, or provider
activation. This is a product/architecture contract, matching the status of
`ORENA_REFERENCE_ARCHITECTURE.md` and its companions.

When implementation is scheduled (see `docs/project/ROADMAP.md`, "Golden Star
/ Content Domain program"), the ordered seam is:

1. a pure decision layer validating what an explanation request needs before
   calling any provider — exact selection present, context contains
   selection, a distinguishable §4 category shape in the expected response —
   mirroring how `writing_coach/reference_backbone.py` already separates pure
   decisions from persistence for the account/commerce backbone; this is the
   Orena Explanation Contract's request/response validation, not a database;
2. generation against that contract, calling the existing per-domain entry
   points (Reading, Listening, Vocabulary, Writing, Speaking) through one
   shared seam rather than each domain building its own explanation prompt;
3. caching and retrieval (§5) added only once real usage shows repeated or
   near-identical questions worth short-circuiting — not built speculatively
   ahead of that evidence;
4. a structured reference store (§5's optional Knowledge Graph) considered
   only as a later, separately justified optimization on top of (3), never a
   blocking prerequisite for (1)-(2).

Any schema this needs — including (3) and (4) — is a new proposal under the
existing architecture-review gate (`AGENTS.md` §1): an implementer does not
self-approve it, the same constraint already governing the I2/I3 backbone
schema proposals.

---

## 9. Review question

Before presenting Understanding Engine work as reviewable, ask:

Does the explanation start from the learner's exact context, or does it
answer a generic version of the question?

Does it clearly separate mental model, mnemonic, linguistic explanation, and
verified etymology whenever more than one is present, per §4?

Can the same explanation be reached from at least two different domains
without a domain-specific reimplementation?

Does it degrade honestly (no fabricated confident answer) when no grounding
is available and generation alone cannot support a claim?

Is any proposed knowledge store justified by actual repeated-question
evidence, or is it being built ahead of need (§5)?
