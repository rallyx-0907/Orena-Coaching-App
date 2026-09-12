# Orena Content Architecture

Status: AUTHORITATIVE PRODUCT CONTENT CONTRACT

This document defines how meaningful content enters, moves through, and connects
the learner-facing Orena experience.

It operates under:

`docs/product/ORENA_PRODUCT_CONSTITUTION.md`

The Constitution defines why Orena exists and what the product should feel like.

This document defines the durable content model that supports that experience,
together with two companion contracts it depends on:

- `docs/product/ORENA_UNDERSTANDING_ENGINE.md` — the horizontal mental-model
  explanation capability shared across every domain below;
- `docs/product/ORENA_VOCABULARY_ARCHITECTURE.md` — the Vocabulary Library and
  Orena Vocabulary Card model, including orthography.

Amended by D-049, corrected by D-050 (`docs/project/DECISION_LOG.md`),
integrating `docs/product/ORENA_PHILOSOPHY_AMENDMENT_CONTENT_UNDERSTANDING.md`.
D-050 corrects an over-modeling in the first integration: Orena has **five**
canonical content domains, not six — Understanding is a horizontal capability
over them, not a domain of its own. See §10.

---

# 1. Core principle

Orena should contain a world of language worth exploring.

A learner should not need to bring their own material before Orena becomes
interesting or useful.

Orena should provide meaningful content, contexts, situations, media, ideas,
stories, conversations, and prompts that learners can discover.

At the same time, learners should be able to bring language they genuinely care
about into Orena.

The durable model is:

Discover in Orena
OR
Bring your own
→ enter a meaningful experience
→ understand
→ notice
→ use
→ remember
→ re-encounter.

Orena-curated content and learner-imported content must not become two
disconnected products.

Where technically and pedagogically appropriate, both should use the same
learning capabilities, learner memory, evidence, vocabulary, grammar,
progression, and continuation model.

### Orena is not one universal content schema

Orena contains **five canonical learning-content domains** — Reading,
Writing, Listening, Speaking, and Vocabulary — each with its own content
model and learner experience, sharing common platform infrastructure for
ingestion, provenance, publishing, indexing, recommendation, moderation, and
search.

A shared **Understanding Engine** (§10) sits horizontally across all five,
answering "why does this work" questions with a mental model rather than a
memorized translation or rule. It is a capability every domain calls, not a
sixth library a learner browses.

> Separate learning domains, shared platform infrastructure, one horizontal
> Understanding Engine.

Do not force Reading, Writing, Listening, Speaking, and Vocabulary into one
universal content schema. They are different learning objects. §4 defines what
they actually share.

---

# 2. Content origins

Every meaningful content object should have a truthful origin.

The primary origins are:

## Curated

Content selected, licensed, authored, commissioned, linked, embedded, or
otherwise intentionally provided by Orena.

Examples may include:

- conversations;
- stories;
- cultural material;
- articles;
- short-form media;
- public-domain or appropriately licensed excerpts;
- situations;
- prompts;
- ideas;
- learning collections.

## Generated

Content created or adapted by Orena for a learner, level, topic, context, or
learning need.

Generated content must be presented truthfully.

A generated passage must not pretend to be a real newspaper article, published
book excerpt, quotation from a real person, or other external source.

## Imported

Content the learner intentionally brings into Orena.

Examples may include:

- pasted text;
- article URLs;
- supported media URLs;
- learner-created prompts;
- personal text;
- other supported sources.

## Saved

Content or language the learner has chosen to keep, continue, revisit, or learn
from.

Saved is a learner relationship to content, not a separate content origin.

---

# 3. Discover and bring your own

Discovery and importing are complementary content paths, not an exhaustive
list of learner intentions. Orena also supports direct intentional practice,
continuation, and revisiting language. A learner may choose Dictation, Shadowing,
Speaking, Writing, Grammar, or Recall directly, then choose or resume meaningful
material. The same content identities, capability primitives, and learner
evidence serve every entry path. No discovery prerequisite or separate
practice-only content repository is required.

## Discover

Orena presents worthwhile things to enter, understand, explore, or respond to.

Discovery may be shaped by:

- learning language;
- learner level;
- interests;
- topic;
- previous experiences;
- learner evidence;
- vocabulary;
- grammar;
- pronunciation needs;
- difficulty;
- duration;
- content type;
- unfinished experiences;
- useful re-encounters.

Discovery should not feel like browsing a catalog of learning features.

### Discover and Home are distribution surfaces, not canonical storage

Discover and Home must surface publishable content from the domain libraries
in §5-§9. They must not own hard-coded canonical content of their own — a
fixed list of sample items baked into the entry surface is a temporary
implementation seam, never the target content strategy. `ORENA_EVIDENCE_
ARCHITECTURE.md` §4 already establishes that Discover ranks/filters existing
evidence-backed candidates rather than inventing them; the same rule applies
to which items exist to be ranked. See `docs/project/LEGACY_TOMBSTONES.md`
for the specific superseded pattern this corrects.

## Bring your own

The learner may introduce content that matters to them.

Where supported, Orena should transform that content into the same kinds of
learning experiences used by Orena-provided content.

Importing content is an extension of the Orena world.

It must not become a disconnected utility mode.

---

# 4. Shared infrastructure, separate domains

Reading, Writing, Listening, Speaking, and Vocabulary keep their own content
models (§5-§9). They may share infrastructure such as:

- source/rights registry and provenance tracking (§2, §16);
- the ingestion and admission contract
  (`ORENA_CONTENT_EXECUTION_ARCHITECTURE.md` §1, already covering origin/
  access/readiness axes and admission checks for any source type, not only
  media);
- the expensive-operation/job contract for anything requiring generation or
  external acquisition (`ORENA_CONTENT_EXECUTION_ARCHITECTURE.md` §3);
- moderation and review before publication;
- search, tagging, level estimation, and recommendation;
- user collections (`ORENA_COLLECTION_ARCHITECTURE.md`);
- asset storage for media, images, and audio;
- feed/distribution surfaces (§3).

The five domains sit beside one shared horizontal capability — the
Understanding Engine (§10) — which every domain calls rather than each
building its own explanation logic:

```text
                     ORENA CONTENT PLATFORM
                              |
      --------------------------------------------------
      |     shared: ingestion / rights / search / feed  |
      --------------------------------------------------
        |        |         |         |          |
     Reading  Writing   Listening  Speaking  Vocabulary
        |________|_________|_________|__________|
                              |
                    Understanding Engine (horizontal)
                 (docs/product/ORENA_UNDERSTANDING_ENGINE.md)
```

"Shared infrastructure" never means "one universal content schema." A content
object may include, where relevant to its own domain:

- stable identity;
- title;
- description;
- learning language;
- content language;
- content type;
- topic;
- learner level or difficulty;
- source;
- origin;
- author / creator where applicable;
- provenance;
- rights / license information where applicable;
- duration;
- thumbnail or visual identity;
- body text;
- transcript;
- timestamped segments;
- support-language meaning;
- relevant metadata;
- learner relationship such as saved / started / completed.

This is the set infrastructure (search, indexing, feeds) may need to read
across domains — it is not a schema every domain must fully populate, and a
domain's own object may carry fields this list does not name (§5-§9). Do not
invent metadata merely to fill a shared field.

Cross-domain relationships between separate objects are allowed and expected
(§13); a shared field list is not a reason to merge two domains into one
object.

---

# 5. Writing content — the Writing Prompt Bank

Writing does not primarily need a large media library. It needs a
high-quality **Prompt Bank**.

Orena should contain a discoverable world of writing opportunities rather than
only a form for selecting an exercise type.

A Writing Prompt may include, where relevant:

- topic;
- context;
- learner goal;
- optional hints;
- expected length (an invitation, never a target the demonstrated band is
  forced toward);
- mode or genre;
- constraints where relevant;
- an evaluation profile/rubric reference.

Possible categories include journal, story, reflection, argument, email,
workplace writing, academic writing, description, and exam-style tasks where
appropriate — alongside the existing situations, opinions, messages, and
personalized-continuation prompts already part of the product.

Writing should also support learner-owned starting points such as:

- free writing;
- a custom prompt;
- a topic or idea the learner chooses;
- something the learner wants to reply to;
- continuation of an existing draft.

Existing internal Writing modes may support these experiences. They should not
automatically define the learner-facing information architecture.

A Writing experience should be able to create evidence useful for later:

- grammar;
- vocabulary;
- recall;
- reading;
- speaking;
- future personalized content.

Writing prompts help the learner know **what to express**; evaluation stays
grounded in the exact submitted text and the intended writing mode, per the
existing R3/R4 evaluator contract.

---

# 6. Reading content — the Reading Library

Reading should be a real library, not a handful of hard-coded stories kept
"deliberately small" indefinitely.

Where sourcing and rights permit, it may contain:

- books;
- book chapters;
- news, newspapers, and magazine-style articles;
- blogs;
- essays;
- short stories and literature;
- learner-friendly articles;
- appropriately licensed or public-domain excerpts;
- culture, people, places, conversations, and written dialogue;
- quotes or short thoughts;
- level-appropriate collections;
- generated or adapted reading material;
- user-imported documents.

A Reading item should preserve, where applicable:

- title;
- author;
- publisher/source;
- language;
- genre;
- topic;
- reading level;
- estimated reading time;
- body/chapter structure;
- images and footnotes where applicable;
- publication date;
- rights/provenance.

Generated text is one source of Reading content. It must not be treated as the
whole Reading product.

Reading content should be searchable, filterable, recommendable, collectible,
and publishable into Orena's learner-facing feeds through the shared
infrastructure in §4, not a Reading-only mechanism.

A Reading experience may naturally lead into:

read
→ understand
→ inspect language
→ vocabulary
→ grammar discovery
→ comprehension
→ reflection / discussion / writing
→ learner evidence
→ recall.

Reading should not exist only as text followed by disconnected multiple-choice
questions.

---

# 7. Listening content — the Listening Library

Listening is its own media domain. It must not be treated as merely "Reading
with audio."

Listening should provide a discoverable media world. Media also supports
intentional practice and continuation. Every prepared media encounter must
offer synchronized Follow: playback selects the current timestamped original
segment and its support-language meaning together; transcript selection
seeks, and replay and speed changes preserve alignment. Chinese is primary,
with optional contextual Pinyin. Follow remains usable without requiring an
exercise. Deeper practice uses that same source and segment identity rather
than creating Listening-mode or Studio-specific sessions.

Where sourcing and rights permit, Listening may contain:

- short conversations, everyday speech, stories;
- animation moments;
- film/television moments where legally usable;
- podcasts, interviews, speeches, news audio;
- short-form video, including platform-style short clips where rights and
  integration allow;
- cultural or emotionally meaningful moments;
- practical situations;
- other useful short-form media;
- user-imported media.

A discoverable media item should support relevant metadata such as:

- learning language;
- topic;
- learner level;
- content type;
- source;
- duration;
- speakers;
- accent;
- speech speed;
- noise level;
- thumbnail;
- transcript;
- timestamped segments;
- provenance;
- rights/license information where applicable.

The media experience may naturally support:

listen / watch
→ follow
→ understand
→ inspect transcript
→ replay
→ segment practice
→ dictation / reconstruction
→ vocabulary
→ shadowing
→ speaking / response
→ future recall.

Learners should also be able to bring supported media into Orena:

supported media URL
→ media preparation
→ transcript / segments
→ same Listening experience.

"Add a video" is therefore an input path into Listening. It is not the
definition of Listening itself.

---

# 8. Speaking content — the Speaking Library

Speaking is not just Listening reused. It should contain its own learning
objects, such as:

- example dialogues;
- role-play situations;
- guided speaking tasks;
- pronunciation exercises;
- situational conversations;
- shadowing exercises;
- model speaking videos;
- speaking prompts.

Speaking should reuse the shared media/content world where appropriate rather
than creating an unnecessary parallel media repository — but the domain
relationship is a **reference**, not an identity merge:

`SpeakingExercise -> may reference ListeningItem`

not:

`SpeakingLibrary = ListeningLibrary`

Possible source contexts include conversations, dialogue, character lines,
interviews, speeches, everyday situations, stories, learner-imported media,
content encountered through Listening or Reading, and personalized prompts.

Possible Speaking experiences include shadowing, imitation, repetition with
variation, response, role-play, retelling, description, conversation, and free
expression.

For shared media, the same content identity should be able to support:

Listening
→ understanding
→ transcript
→ shadowing
→ Speaking
→ feedback.

Learner-imported media should participate in this same flow where supported.

---

# 9. Vocabulary content — the Vocabulary Library

Vocabulary is a real curated library, not only a flat word list or a byproduct
of saving words while reading.

The full model — Orena Vocabulary Cards, topic collections, orthography for
Chinese and future scripts, and the relationship to existing saved-word
identity — is defined in:

`docs/product/ORENA_VOCABULARY_ARCHITECTURE.md`

The pattern below still governs how vocabulary connects to real use, and
remains valid for both dedicated Vocabulary practice and vocabulary that
emerges from encounters in other domains:

Encounter
→ Notice
→ Understand
→ Use
→ Re-encounter
→ Recall
→ Master.

Vocabulary must be able to grow independently of Reading and Listening
content, per `ORENA_VOCABULARY_ARCHITECTURE.md` §1 and §6.

---

# 10. The Orena Understanding Engine (horizontal, not a domain)

Orena should eventually let a learner ask about almost anything in the target
language and receive an explanation designed to build a mental model rather
than a memorized translation or rule — reusable from Reading, Listening,
Speaking, Writing, and Vocabulary alike, through the same source-bound
explanation seam already named `Understanding` in
`ORENA_REFERENCE_ARCHITECTURE.md` §6-7 and `ORENA_EVIDENCE_ARCHITECTURE.md`
§1.

**This is a horizontal capability, not a sixth content domain.** It has no
learner-browsable library of its own; a learner reaches it by asking about
something inside Reading, Writing, Listening, Speaking, or Vocabulary, never
by opening "Understanding" as a destination. It is AI-first and
context-grounded — generated live from the learner's exact context — not
built on a required precomputed knowledge store. The full explanation
philosophy, the Orena Explanation Contract, the four-way accuracy rule
(mental model / mnemonic / linguistic explanation / verified etymology, never
blurred), and the optional (not required) explanation support layer are
defined in:

`docs/product/ORENA_UNDERSTANDING_ENGINE.md`

Media libraries answer "what can I learn from?" Vocabulary Cards answer "how
do I retain and reuse what I learned?" The Understanding Engine answers "why
does this language work like this?" These are complementary, distinct
capabilities; Orena combines all three rather than collapsing them into one.

---

# 11. Grammar

Grammar and vocabulary are not separate content worlds that must compete with
Reading, Listening, Writing, or Speaking. They frequently emerge from real
learner encounters, following the same Encounter → Notice → Understand → Use
→ Re-encounter → Recall → Master pattern named in §9.

Dedicated Grammar practice may exist where valuable. It remains connected to
actual language, learner evidence, and future use whenever possible, and
stays anchored to the closed R5 stable Grammar Concept IDs
(`ARCHITECTURE_INVARIANTS.md`, "Closed-stage protection"). The Understanding
Engine (§10) may draw on Grammar Concept IDs to ground a linguistic
explanation; it does not duplicate or replace the curriculum.

---

# 12. Explore, My Content, My Language, and Recall

These concepts must remain distinct.

## Explore

The world of content, contexts, media, ideas, situations, and experiences that
Orena makes available to discover.

## My Content

Things the learner has imported, saved, started, followed, or intentionally
kept as content.

Examples:

- saved media;
- imported media;
- saved articles;
- imported text;
- unfinished reading;
- saved prompts;
- personal content.

## My Language

Language the learner has collected or demonstrated through learning.

Examples:

- vocabulary (Orena Vocabulary Cards and saved words alike);
- phrases;
- collocations;
- idioms;
- grammar patterns;
- recurring mistakes;
- pronunciation evidence;
- useful expressions;
- saved Understanding Engine explanations.

## Recall

The mechanism that brings useful learned language back at appropriate times.

Recall is not the same thing as Explore or My Content.

Existing learner-facing terminology may evolve as product design develops, but
the conceptual separation must remain clear.

---

# 13. Cross-domain relationships

Content should be able to participate naturally in more than one learning
capability when doing so improves the experience, and separate domain objects
may reference each other explicitly:

- a Speaking shadowing activity may reference a Listening clip;
- a Vocabulary Card may reference a sentence from a Reading item;
- a Reading item may expose words into a learner's Vocabulary collection;
- a Writing prompt may reference a Reading topic;
- an Understanding Engine explanation may be saved into the learner's My
  Language collection;
- a Listening transcript may provide examples for Vocabulary.

The relationship is:

> linked learning objects

not:

> the same object forced to serve every learning domain.

Example continuity, unchanged from the existing product model:

A short conversation
→ listen
→ inspect transcript
→ save a phrase
→ understand its grammar
→ shadow a line
→ respond aloud
→ encounter the phrase later
→ recall it
→ use it independently.

Do not mechanically force every capability into every content object.
Integration must have a learner reason.

---

# 14. Personalization

Orena may use learner evidence to influence discovery.

Relevant evidence may include:

- content already experienced;
- unfinished content;
- saved vocabulary;
- recurring grammar issues;
- pronunciation difficulties;
- comprehension history;
- interests;
- learner level;
- successful recall;
- unsuccessful recall;
- recent Writing;
- recent Speaking;
- previous content choices.

Personalization should reduce friction and create meaningful continuation. It
should not require the learner to configure a large recommendation system
manually.

---

# 15. English and Chinese

English and Chinese are first-class throughout the content system.

Equivalent product quality is required for discovery, curated or provided
content, generated content, imported content where the source type is
supported, metadata, learner collections, continuation, and cross-capability
learning — and, per D-049/D-050, for Vocabulary Card depth, orthography
support, and Understanding Engine explanation quality alike.

Equivalent quality does not require identical content catalogs or linguistic
processing. Language-specific differences should be handled through
appropriate language behavior rather than by creating two disconnected
products.

---

# 16. Provenance and rights

Orena must represent external content truthfully.

For curated or external material, preserve appropriate source and provenance
information.

Content acquisition and presentation must respect applicable rights and
provider constraints.

Where full copyrighted material cannot appropriately be stored or redistributed,
the product should prefer permitted approaches such as:

- licensed content;
- public-domain content;
- creator-authorized content;
- provider-supported embedding or linking;
- learner-provided content used within supported boundaries;
- metadata plus source handoff;
- generated or transformed learning material that does not falsely claim an
  external source.

Do not fabricate attribution.

Do not present generated content as externally published content.

---

# 17. Content scale philosophy

The target is not "add one or two example items." Orena should eventually
feel like it has a substantial learning world to explore, with each domain
capable of containing hundreds or thousands of useful items over time.

This requires, at the shared-infrastructure level (§4,
`ORENA_CONTENT_EXECUTION_ARCHITECTURE.md`):

- batch ingestion;
- incremental publishing;
- pagination/cursor loading (`ORENA_COLLECTION_ARCHITECTURE.md` §3 already
  specifies this for retrieval; content growth must not outrun it);
- background processing;
- failure isolation and retryable jobs (`ORENA_CONTENT_EXECUTION_ARCHITECTURE.md`
  §3's job states already define this);
- rights/provenance tracking (§16);
- deduplication;
- moderation/review before publication;
- scalable asset storage.

However, scale must not be achieved by filling the product with low-quality
content:

> A smaller curated library is better than a massive noisy dump.

A hand-authored array of a few sample items (as every domain's current
implementation still is, in whole or in part) is a legitimate *starting
seam*, not the target end-state. Growing a domain's library is expected to
move to the batch/reviewed pipeline above as curation capacity allows, not to
continue indefinitely as one-at-a-time manual edits. See
`docs/project/LEGACY_TOMBSTONES.md` for the specific pattern this retires as a
strategy (owning hard-coded content in the Discover/Home entry surface); it
does not retire hand-authored generated content itself, which remains a valid
`origin: generated` source under §2.

This same "do not pre-build ahead of evidence" discipline applies to the
Understanding Engine's optional support layer (`ORENA_UNDERSTANDING_ENGINE.md`
§5): generate from context first, add caching/reference structure only once
real usage justifies it.

---

# 18. Product acceptance contract

A mature Orena content experience should answer both:

> What is here that I want to discover?

and:

> Can I bring something I care about into this experience?

Not every individual screen needs both controls.

The product as a whole must support both models.

The content world is incomplete if Orena only provides tools and waits for the
learner to supply everything.

The content world is also incomplete if learners cannot meaningfully connect
their own interests and materials to the learning system.

---

# 19. Implementation principle

Existing code proves current implementation state.

It does not define the final content architecture.

Existing foundations should be reused when compatible.

Under the human-authorized reset in D-046, reuse means clean capability
primitives and infrastructure. Historical screen/session wrappers, skill-first
routes, mode selectors, and competing product specifications must be physically
removed, extracting and testing useful logic first. Git history is the archive;
an active legacy directory is not an acceptable substitute.

Examples include:

- Writing evaluation and learner evidence;
- Reading session and comprehension contracts;
- shared Media Learning;
- transcript segments;
- Listening reconstruction;
- Shadowing;
- Speaking evaluation;
- Vocabulary / Library — today's saved-word/recall implementation is the
  seam `ORENA_VOCABULARY_ARCHITECTURE.md` builds Vocabulary Cards on top of,
  not a system to discard;
- Grammar concepts and the static Grammar KB — existing linguistic behavior
  the Understanding Engine's explanations may ground against
  (`ORENA_UNDERSTANDING_ENGINE.md` §5), not a system it forks;
- `ui/understanding.js` — the seam the Understanding Engine deepens;
- learner memory and progress.

Do not rebuild these merely to satisfy this document.

The product task is to connect stable foundations into the content world
described here.

---

# 20. Review question

For meaningful learner-facing content work, ask:

Does this implementation make Orena feel richer in things worth discovering,
while also making it possible for the learner to connect language they
personally care about?

If it only exposes another learning tool, the experience is incomplete.

Does this content live in its owning domain's library, or did it get added
directly to an entry-surface array because that was the fastest path? If the
latter, it needs to move (§3, §17).

If this introduces an "Understanding" or "Language Knowledge" screen a
learner browses directly, or a database that must be populated before
explanations can work, it has drifted from §10 — Understanding is a
capability every domain calls, not a destination.
