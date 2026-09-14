# Vocabulary Card and Orthography Foundation

## Goal

Extend Orena's existing saved-word Vocabulary seam with a pure, language-neutral
Vocabulary Card and orthography contract that can represent rich vocabulary,
polyphonic readings, and truthful script facts without adding persistence.

## Scope

This slice changes domain contracts, pure adapters, and tests only. The existing
saved-word relationship and Active Recall state remain authoritative. No schema,
migration, provider activation, database operation, container operation, I2/I3
change, learner-facing route, UI/theme redesign, or shared status-document change
is included.

## Design

`VocabularyCard` remains a dictionary-shaped projection so current library and UI
consumers continue to work. Its identity and memory fields continue to come from
the existing saved-word/library owners. Rich optional fields are preserved as
one-to-many collections: senses/meanings, examples, collocations, related
expressions, traps, source encounters, learner examples, and references into the
horizontal Understanding capability.

The orthography contract is shared and rooted at `OrthographicUnit`, not
`grapheme`. A unit can expose `surface`, `script`, and `unit_kind`; a language
adapter may use `character`, `syllable`, `block`, `form`, or another appropriate
unit kind without changing the shared contract. Each unit has zero or more
`readings`, and every reading may carry pronunciation notation, a context/sense
binding, and provenance. There is deliberately no singular pronunciation field
on an orthographic unit.

Orthographic facts are independently optional assertions. Stroke count, radical,
components, stroke-order representation, and related etymology/history claims
carry assertion-level provenance that can be extended with source/reference,
revision/version, evidence type, and rights/license metadata. Missing data is
omitted or marked unavailable; it is never synthesized. Verified etymology is
accepted only with trusted provenance. Mental models, mnemonics, linguistic
explanations, and verified etymology/history are typed optional artifacts or
references, not required card fields and not interchangeable.

The Chinese adapter reuses `writing_coach.languages.chinese.stroke_order` for
vendored, deterministic stroke paths/counts. It may attach supplied trusted
radical, component, reading, or etymology assertions, but does not infer any of
them. The same shared contract remains usable by future Hanzi/Kanji/Kana,
Hangul, Arabic, and other adapters.

## Verification

Tests will prove rich card preservation, generic non-Chinese units, multiple
context-bound readings, assertion-level provenance, optional explanation
artifacts, rejection of unprovenanced verified etymology, truthful unavailable
facts, and compatibility with the existing Chinese stroke-order owner. Tests
will run locally where dependencies are available; no DB or container is needed.
