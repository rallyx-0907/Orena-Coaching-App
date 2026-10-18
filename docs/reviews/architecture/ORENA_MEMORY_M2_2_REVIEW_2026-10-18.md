# Orena Memory M2.2: wiring, routes and server-applied notes, independent review (2026-10-18)

- **Reviewer:** Claude (Opus 5.5), independent and read-only.
- **Reviewed commit:** `ee99bf82` on `claude/intelligence-m2-wire`.
- **Outcome:** **CHANGES REQUIRED**, with two P1s. Both are fixed in the commit that adds this record, and each fix has a test that went red and then green.

| ID | Finding | Disposition |
| --- | --- | --- |
| P1-1 | The G8 gate and the class recording followed the learner pack, not memory. With the pack off, server notes were sent without raising the conversation's class, so a re-pin to a `none` provider would continue the conversation. A failed probe also sent device notes. | **Fixed.** Both follow "this server has Orena Memory". A failed probe reads as OFF, so it fails closed. Tests: `test_with_the_pack_off_server_notes_raise_the_conversation_and_a_lower_provider_is_refused` and `test_a_failed_probe_fails_closed_for_device_notes`. |
| P1-2 | With memory OFF, `remember_note` still kept a note on the device. | **Fixed.** With memory OFF it is refused for v8 and v9 alike (`memory.off`). Test: `test_with_memory_off_remember_writes_nothing_anywhere[8,9]`. |
| P2-1 | A store failure in reading the notes, or in keeping or forgetting one, could fail the turn. | **Fixed.** Each failure is caught and the turn goes on (`memory.unavailable`). Test: `test_a_store_error_never_breaks_the_turn`. |
| P2-2 | A server correction could lose the old note without reporting it. | **Fixed.** The old note is deleted first and its remove event is always emitted, even when the new note then fails. Test: `test_a_correction_that_cannot_be_kept_still_reports_the_removed_note`. |
| P2-3 | A correction counts twice against `MAX_NOTE_UPDATES`. | **Deferred, minor.** It only refuses a third note change in the same turn. |
| P2-4 | A note is written during the rounds but announced at the end, so a turn that fails after the write leaves it unannounced. | **Deferred.** The note is in the memory listing, and the next turn's pack shows it. |
| P2-5 | The GET `language` parameter was not validated. | **Fixed.** A contract or internal code is accepted, anything else gets 422, and a store error gets 503. Test: `test_the_listing_language_is_validated`. |
| P2-6 | Server notes were not capped at the request limits. | **Fixed.** Newest first, within `MAX_COACH_NOTES` and `MAX_COACH_NOTES_BYTES`. Test: `test_server_notes_reaching_the_model_keep_the_request_caps`. |
| P2-7 | `ensure_active` ran on every server-mode turn. | **Fixed.** `ServerNotes` resolves the scope only when a note is written. |
| P2-8 | The mutating routes had no rate limit. | **Fixed.** They share the agent's read window (`_read_allowed`). |
| P2-9 | The GET route has no evidence digest. Also, in v9 server mode, device notes the learner has not placed are not sent: contract §3 says the server ignores them, §10 says they are "sent as today" until the learner chooses. | **Recorded.** The evidence digest is deferred. The §3/§10 contradiction is reported to the UI lane, which owns the contract. |
| P2-10 | A v8 client's pack now carries the account's explicit notes, when memory is ON and the model is cleared. | **Documented in the PR.** v8 is unchanged at the event level: no server write and no `stored`. |

## M2.3 (PR #281): independent review, 2026-10-18

- **Reviewer:** Claude (Opus 5.5), independent and read-only.
- **Reviewed commit:** `416a21ef`.
- **Outcome:** **APPROVE**. No P0 or P1.

| ID | Finding | Disposition |
| --- | --- | --- |
| P2-1 | The first device note that did not fit stopped the fill. | **Fixed.** A smaller note after it may still fit. |
| P2-2 | Ties in weight were broken by id. | **Fixed.** A stable sort keeps the client's order among equal weights. |
| P2-3 | A stale `_with_memory` docstring. | **Fixed.** |
| P2-4 | Device notes were not deduped against each other. | **Fixed.** |
| P2-5 | A server-kept note could stay on the device as well. | **Fixed.** Keeping the words of an unplaced device note moves the note to the account, and the device drops its copy (`stored: "device"` remove). Test: `test_keeping_the_words_of_an_unplaced_device_note_moves_it_to_the_account`. |
| P2-6 | Test gaps. | **Fixed for the unit level** with `test_with_device_notes_orders_dedupes_and_fits_what_room_is_left`. A device-routed forget or replace in voice is untested, because voice derives no "asked" note for any client (pre-existing, tracked separately). |
