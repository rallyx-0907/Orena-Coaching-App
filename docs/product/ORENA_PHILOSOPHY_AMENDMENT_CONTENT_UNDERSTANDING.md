# Orena Philosophy Amendment — Content Libraries, Understanding Engine, and Vocabulary Cards

**Status:** Product philosophy / architecture direction  
**Purpose:** Add this document to Orena's roadmap/specs when GPT-6 resumes.  
**Important:** This is not an implementation plan for adding a few sample lessons. It defines how Orena should think about learning content and explanation as a product.

---

## 1. Core Product Principle

Orena is not a collection of isolated learning tools and it is not a single generic media library.

Orena should contain **multiple canonical learning-content domains**, each with its own content model and learner experience, while sharing common infrastructure for ingestion, provenance, publishing, indexing, recommendation, moderation, and search.

The principle is:

> **Separate learning domains, shared platform infrastructure, one shared Understanding Engine.**

Do not force Reading, Writing, Listening, Speaking, Vocabulary, and language explanations into one universal content schema.

They are different learning objects and should remain different.

---

## 2. Canonical Learning Domains

### 2.1 Reading Library

Reading should be a real library, not a handful of hard-coded stories.

It may contain:

- books;
- book chapters;
- news;
- newspapers and magazine-style articles;
- blogs;
- essays;
- short stories;
- literature;
- learner-friendly articles;
- user-imported documents;
- Orena-authored content;
- other legally reusable reading sources.

A Reading item should preserve information such as:

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

Reading content should later be searchable, filterable, recommended, collected, and publishable into Orena's learner-facing feeds.

---

### 2.2 Writing Prompt Bank

Writing does not primarily need a large media library.

It needs a high-quality **Prompt Bank**.

A Writing Prompt can include:

- topic;
- context;
- learner goal;
- optional hints;
- expected length;
- mode or genre;
- constraints where relevant;
- evaluation profile/rubric.

Examples of categories:

- journal;
- story;
- reflection;
- argument;
- email;
- workplace writing;
- academic writing;
- description;
- exam-style tasks where appropriate.

Writing prompts should help the learner know **what to express**, while evaluation should remain grounded in the exact submitted text and the intended writing mode.

---

### 2.3 Listening Library

Listening is its own media domain.

It may contain:

- audio;
- podcasts;
- interviews;
- speeches;
- news audio;
- YouTube videos;
- short-form videos;
- TikTok-like short clips where rights and integration allow;
- movie or TV scenes where legally usable;
- user-imported media;
- Orena-authored listening material.

Listening metadata may include:

- source;
- media URL or asset reference;
- duration;
- speakers;
- transcript;
- timestamps/segments;
- accent;
- speech speed;
- noise level;
- difficulty;
- topic;
- rights/provenance.

Listening content must not be treated as merely "Reading with audio."

---

### 2.4 Speaking Library

Speaking is not just Listening reused.

It should contain its own learning objects such as:

- example dialogues;
- role-play situations;
- guided speaking tasks;
- pronunciation exercises;
- situational conversations;
- shadowing exercises;
- model speaking videos;
- speaking prompts.

A Speaking exercise may **reference** a Listening item when useful, especially for shadowing, but the two domains remain distinct.

Example relationship:

`SpeakingExercise -> may reference ListeningItem`

not:

`SpeakingLibrary = ListeningLibrary`

---

### 2.5 Vocabulary Library

Vocabulary should be a real curated library of **Orena Vocabulary Cards**, not only a flat word list.

It should support:

- topic-based collections;
- curated collections;
- Orena-created collections;
- imported collections;
- learner-created collections;
- words extracted from Reading or Listening;
- professional/domain-specific collections;
- language-specific card formats.

Examples:

- Airport English;
- Workplace English;
- Technology;
- Emotions;
- HSK topic collections;
- Phrasal verbs;
- Industrial Automation English.

Vocabulary should be capable of growing independently from other libraries.

---

### 2.6 Language Knowledge / Explanation Library

Orena should maintain a reusable knowledge layer for language concepts.

Examples:

- words;
- phrases;
- grammar patterns;
- particles;
- prepositions;
- phrasal verbs;
- semantic contrasts;
- pronunciation concepts;
- writing conventions;
- usage differences;
- language-specific structures.

This knowledge layer supports the Understanding Engine and prevents every explanation from being improvised from scratch.

---

## 3. The Orena Understanding Engine

This is one of Orena's most important differentiators.

Orena should eventually allow the learner to ask about **almost anything in the target language** and receive an explanation designed to create a mental model rather than a memorized translation or rule.

The chatbot is only one interface to this engine.

The actual capability should be reusable throughout Reading, Listening, Speaking, Writing, Vocabulary, and other future learning experiences.

---

## 4. Explanation Philosophy

Orena should not default to:

- dictionary-definition dumping;
- long lists of unrelated meanings;
- grammar-rule memorization;
- translation-only explanations;
- "because English/Chinese works that way";
- fabricated etymology;
- opaque linguistic jargon without intuition.

Instead, Orena should try to answer:

> **What mental model would make this usage feel natural?**

The preferred explanation flow is:

1. identify what is actually confusing;
2. give the core idea;
3. create a visual/physical/semantic mental model;
4. connect apparently different usages;
5. contrast nearby concepts when useful;
6. show natural examples;
7. reveal the common wrong model;
8. optionally give a small comprehension check;
9. allow the learner to save the concept.

---

## 5. Example of the Explanation Philosophy: "off"

A poor teaching approach is:

- off = tắt;
- off = nghỉ;
- off = rời khỏi;
- off = cất cánh;
- off = bỏ ra.

That produces memorization without understanding.

A better Orena explanation may introduce a useful core image:

> Imagine two things that are connected, attached, touching, or participating in the same state.  
> **OFF often carries the image of separation, removal, departure, or disconnection from that state.**

Then connect usages:

- **take off your coat**  
  The coat is attached to/on the body -> remove/separate it.

- **the plane takes off**  
  The plane leaves physical contact with the ground.

- **day off**  
  The person is separated from normal work duty for that day.

- **I'm off**  
  The speaker is leaving the current place/situation.

- **turn the light off**  
  The device is disconnected from its active state.

The purpose is not to claim that one invented story is the true historical origin of every use.

The system must distinguish between:

- **a useful mental model or mnemonic**, and
- **verified historical etymology**.

If the learner asks for true word origin, the explanation should rely on an actual etymological source rather than an AI-generated story.

---

## 6. The Understanding Engine Must Be Shared Across Orena

Examples:

### Reading
Learner highlights:

> He eventually **gave in**.

Then asks:

> Why does "give in" mean this?

Orena receives the phrase plus sentence/paragraph context and explains it.

### Listening
Subtitle:

> I'm not **up for it** tonight.

Learner asks what "up for it" really means and why.

### Vocabulary
A learner sees a card for `off` and asks:

> Why does "off" work in all of these expressions?

The same Understanding Engine responds.

### Writing
Learner writes:

> I very like this.

Feedback flags the phrase and the learner asks:

> Why can't I say this?

The same engine explains the underlying structure.

### Speaking
Learner says:

> I went to home.

They ask:

> Why is there no "to" in "go home"?

Again, the same engine answers.

The engine should therefore be a horizontal Orena capability, not a separate chatbot feature isolated from the rest of the app.

---

## 7. Language Knowledge Graph

The Understanding Engine should accumulate reusable conceptual knowledge rather than generate every answer independently.

Example:

```text
OFF
├── core semantic image
├── physical separation
├── removal
├── departure
├── deactivation
├── figurative extensions
├── take off
├── get off
├── cut off
├── day off
└── I'm off
```

Related concepts can also be linked:

```text
ON <-> OFF
```

or:

```text
GET
├── acquisition
├── change of state
├── arrival
├── understanding
└── causation
```

This does not mean every concept must have one oversimplified "master meaning."

It means Orena should preserve useful semantic relationships and explanation patterns when they genuinely help learners understand.

---

## 8. Orena Vocabulary Card Philosophy

An Orena Vocabulary Card should be richer than a traditional flashcard.

It should not be limited to:

`word -> translation`

Depending on language and content, a card may contain:

- headword;
- pronunciation;
- audio;
- meaning;
- core semantic image / mental model;
- natural examples;
- collocations;
- related expressions;
- semantic contrasts;
- images;
- common learner traps;
- source encounters;
- learner-created examples;
- links to relevant explanations;
- memory/practice state.

The format should be extensible by language.

---

## 9. Orthography Is a First-Class Part of Vocabulary Cards

For languages where writing form is an important part of vocabulary learning, the Orena Card should have a dedicated **Orthography / Writing** section.

This is especially important for Chinese and should later generalize to other writing systems.

For Chinese, a card should be able to show:

- Hanzi;
- Pinyin;
- pronunciation audio;
- stroke count;
- radical;
- character components;
- stroke order;
- animated stroke writing;
- step-by-step stroke mode;
- tracing practice;
- free-writing practice;
- later, optional handwriting feedback.

Example conceptual structure:

```text
休息
├── pronunciation: xiūxi
├── meaning / usage
├── examples
└── orthography
    ├── 休
    │   ├── radical
    │   ├── components
    │   ├── stroke count
    │   └── stroke order
    └── 息
        ├── radical
        ├── components
        ├── stroke count
        └── stroke order
```

The internal schema should prefer a general capability such as:

```text
orthography
```

rather than hard-coding only:

```text
chinese_stroke_order
```

This allows future support for:

- Chinese Hanzi;
- Japanese Kanji/Kana;
- Arabic joining/forms;
- Korean Hangul composition;
- other script-specific learning experiences.

---

## 10. Character Explanations: Accuracy Rule

Orena may use character decomposition, visual mnemonics, and stories when they genuinely help memory.

However, it must clearly distinguish:

- verified character etymology;
- modern structural decomposition;
- learner mnemonic.

A mnemonic must never be presented as historical fact merely because it sounds memorable.

This is the same accuracy rule used by the Understanding Engine more generally.

---

## 11. Shared Infrastructure, Separate Schemas

The learning domains should remain separate but can share infrastructure such as:

- source registry;
- ingestion framework;
- rights/provenance tracking;
- moderation;
- publishing;
- indexing;
- search;
- recommendation;
- user collections;
- tagging;
- level estimation;
- asset storage;
- feed distribution.

Conceptually:

```text
                 ORENA CONTENT PLATFORM
                         |
        -----------------------------------------
        |              Shared Infrastructure    |
        | ingestion / rights / search / feed   |
        -----------------------------------------
          |        |        |        |        |
       Reading   Writing Listening Speaking Vocabulary
                                                |
                                      Language Knowledge
                                                |
                                      Understanding Engine
```

Do not interpret "shared infrastructure" as "one universal content schema."

---

## 12. Cross-Domain Relationships Are Allowed

Separate domains may reference each other.

Examples:

- a Speaking shadowing activity may reference a Listening clip;
- a Vocabulary Card may reference a sentence from a Reading item;
- a Reading item may expose words into a learner's Vocabulary collection;
- a Writing prompt may reference a Reading topic;
- an Understanding explanation may be saved into the learner's knowledge collection;
- a Listening transcript may provide examples for Vocabulary.

The relationship is:

> **linked learning objects**

not:

> **the same object forced to serve every learning domain**.

---

## 13. Feed and Discover Philosophy

Discover/Home feeds should not own hard-coded content.

They should surface publishable content from the relevant domain libraries.

Possible feed sources include:

- Reading items;
- Listening items;
- Speaking exercises;
- Vocabulary collections;
- Writing prompts;
- newly published Orena content;
- learner-relevant recommendations.

A feed is a distribution/recommendation layer, not the canonical storage location for learning content.

---

## 14. Content Scale Philosophy

The target is not "add one or two example stories."

Orena should eventually feel like it has a substantial learning world to explore.

Each domain should be capable of containing hundreds or thousands of useful items over time.

The implementation should therefore support:

- batch ingestion;
- incremental publishing;
- pagination/cursor loading;
- background processing;
- failure isolation;
- retryable jobs;
- rights/provenance;
- deduplication;
- moderation/review;
- scalable asset storage.

However, scale must not be achieved by filling the product with low-quality content.

> **A smaller curated library is better than a massive noisy dump.**

---

## 15. Important Product Distinction

Media libraries answer:

> "What can I learn from?"

The Understanding Engine answers:

> "Why does this language work like this?"

Vocabulary Cards answer:

> "How do I retain and reuse what I learned?"

These are complementary but distinct product capabilities.

Orena should combine all three.

---

## 16. Roadmap Consequence

When integrating this philosophy into the roadmap, do not reduce it to a task such as:

> Add more stories to Discover.

Instead, the roadmap should explicitly account for:

1. the six learning/knowledge domains;
2. shared content-platform infrastructure;
3. Orena Understanding Engine;
4. Language Knowledge Graph;
5. Orena Vocabulary Card specification;
6. orthography/stroke-order capabilities;
7. domain-specific ingestion and publishing;
8. large default libraries over time;
9. cross-domain references;
10. Discover/Home as distribution surfaces rather than canonical storage.

---

## 17. Recommended Product Priority

A reasonable high-level priority is:

1. **Understanding Engine foundation**
2. **Language Knowledge Graph**
3. **Orena Vocabulary Card specification**
4. **Orthography / stroke-order support**
5. **Canonical schemas for each content domain**
6. **Shared ingestion/publishing infrastructure**
7. **Default library bootstrapping**
8. **Discover/Home recommendation and distribution**
9. **Cross-domain learning loops**

The exact technical implementation and optimization remain engineering/reviewer responsibilities.

Human review should focus on:

- product philosophy;
- architecture meaning;
- learning behavior;
- policy;
- learner-visible UX.

---

## 18. Non-Negotiable Principle

Orena should help learners move from:

> "I memorized that this expression means X."

to:

> "I can see why this expression works, and I can recognize the same idea somewhere else."

That shift from memorization to mental-model-based understanding should remain one of Orena's defining product principles.
