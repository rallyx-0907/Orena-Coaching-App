# Listening entry correction — implementation plan

Human direction (2026-10-04): Listening practice means listening and answering
questions; Dictation must choose content; Pronunciation and Shadowing must not
appear as duplicate functions. Execute inline in codex/work; native frozen.

1. Add regression tests for one Pronunciation entry, content chooser routes,
   Dictation selection, and ready comprehension sets. Confirm failure first.
2. Extend the existing Listening catalog's lesson metadata with optional authored,
   source-grounded comprehension questions. Validate IDs, choices, correct answer,
   and cited segments within the canonical excerpt at catalog admission. Persist
   them in the same versioned manifest, not a second content store. No providers.
3. Generalize the existing Discover practice chooser by intent (pronunciation,
   dictation, listening). Admit matching ready content; preserve selected segment.
4. Add a listening-question workspace using canonical original media playback and
   the pinned Check Understanding question/option/feedback composition. No new
   learner persistence or mastery/evidence claim; current exercise result only.
5. Verify EN/ZH real choice → play → answer → feedback → next/reopen and Dictation
   alternate selection, phone viewport, source-read call instrumentation, existing
   Node/Python gates, independent review; record verified limitations and checkpoint.

Provenance: Orena.dc.html Practice Hub + Discover content-card patterns; Check
Understanding frame's question, options, verdict and docked next control adapted
with the shared original media player. Existing Follow remains reachable for media
exploration; the Practice Listening door opens only question-ready lessons.
