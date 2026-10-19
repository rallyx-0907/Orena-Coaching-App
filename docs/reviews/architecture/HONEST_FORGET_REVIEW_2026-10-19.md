# A forget is never claimed when none happened (PR #322): independent review (2026-10-19)

- **Reviewer:** Claude (Opus 5.5), independent and read-only.
- **Reviewed commit:** `f42c6e2d`.
- **Outcome:** **APPROVE**, with no P0 or P1.

In text turns, every path ends with the server's own line: the claims are held (`hold_all`), discarded on the nudge, and replaced at the end. That holds for a model that ignores the request, for every refused `forget_note`, and for G8, which uses `notes.unavailable`.

| ID | Finding | Disposition |
| --- | --- | --- |
| P2-a | Voice offered `forget_note`, but a spoken turn derives no "asked" note, so every voice forget was refused. The voice model could therefore claim a forget that never happened. | **Fixed.** `forget_note` is no longer offered in voice. A voice rule says a note cannot be forgotten in voice, so the model points to the text chat and never claims it. Test: `test_voice_never_offers_forget_note_so_it_cannot_claim_a_forget`. |
| P2-b | Partial forgets (one of two notes) or a forget mixed with a keep count as "changed", so the model's text is not checked. | **Deferred** (rare). Fix: compare the removed ids with the asked ones when the intent is forget. |
| P2-c | The copy promised a deletion ("…and I'll delete it"). | **Fixed.** It now just asks the learner to say it once more (EN/VI/ZH). |
| P2-d | The test did not prove that nothing was streamed early. | **Fixed.** It also asserts `== deltas(events)`. Cases for a refused `forget_note` and for EN/ZH remain open. |
