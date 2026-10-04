# Content readiness repair

Goal: implement the human's 2026-10-03 readiness instruction on codex/work.

Architecture: preserve Shared Media Learning. Hear model consumes its canonical
playback and exact segment, rather than a second Speaking acquisition path.
Source-derived translation and reference reads cannot execute providers.
Preparation explicitly materializes configured derivatives through the existing
pipeline and existing storage; learner assessment stays a separate operation.

1. Reproduce entry-triggered calls with EN/ZH regression tests, then change
   speaking-source.js, compare-reference.js and Compare to consume canonical
   playback/words/readings. Keep selected-line return and recorder unchanged.
2. Make Listening reads cache/editorial-only. Wire preparation to the existing
   persisted meaning cache, including private imports. Verify read/reopen is
   independent of browser cache lifetime and provider availability.
3. Remove acquisition/paid reference execution from Speaking source reads.
   Preserve access/revocation checks and explicit unavailable measurements.
4. Record the durable rule in Content Architecture, Content Execution Architecture,
   Design Contract and Decision Log. Preserve the existing uncommitted design edit.
5. Run local contract/Python gates, instrument sandbox browser EN/ZH journeys,
   independent review, and checkpoint verified evidence and current handoff.

Constraints: no schema migration, native work, production activation or source
retention change. Inspect active Docker clients/containers before operating the
shared sandbox; isolate test data and never operate another lane's runtime.

Review focus: old ready imports; YouTube embeds versus local video; transcript
without word timings; unavailable support-language derivative; revoked private
content; repeated segment text; desktop/phone primary controls.

Execution: inline under the current explicit fix instruction. This repository's
memory contract owns recovery; this plan is a task brief, not another memory system.
