# A daily cap on each learner's voice minutes (D-237, PR #325): independent review (2026-10-19)

- **Reviewer:** Claude (Opus 5.5), independent and read-only.

## Round 1: reviewed commit `031ea540`, outcome **CHANGES REQUIRED**

| ID | Finding | Disposition |
| --- | --- | --- |
| P1-1 | An unmetered session (messages not enforced) was counted only when it ended. Open sessions read as 0, so a learner could open many and pass the cap. | **Fixed.** Its seconds are counted when the token is minted, and `_bill` no longer counts them again. Every token is clamped to the seconds left today. |
| P1-2 | A catalogue saved under D-236 holds `orena.voice` limit 1, which would read as one second a day. The Admin editor could not edit the minutes. | **Fixed on the server.** A limit under a minute reads as the default. The UI lane's #326 makes the Admin row a minutes field. The stored catalogues on :8021 and :8000 hold no such value (checked by the UI lane). |
| P2-1 | A failed usage write went unnoticed. | **Fixed.** It logs at error level. |
| P2-2 | Parallel opens race the cap. | **Accepted.** Each token is clamped, so the overshoot is bounded and documented in D-237. |
| P2-4 | The voice cap uses the UTC day, while `orena.message` uses the learner's zone. | **Documented** in D-237. |
| P2-5 | The 429 for `feature: "orena.voice"` has no contract line, and it offered `upgrade`. | `upgrade` is dropped. The contract line belongs to the UI lane (D-086). |
| P2-6 | The learner is charged for minted time, not used time. | **Accepted**, as in D-169. Conservative. |

## Round 2: reviewed commit `c6fdaade` (fix `a7019b79`), outcome **APPROVE**

There is no P0 or P1. Follow-ups made with this record:
- A chunk clamped to the last seconds of the day is marked `last`, so no renewal is refused mid-session.
- The D-237 field list no longer names `upgrade`.

Left as is: a released ticket after a 0-seconds race relies on `require_voice_time` raising. If it ever returned, the worst case is a one-second, uncharged token.

## PR #328 (`day_limit_reached`): reviewed commit `1b06f419`, outcome **CHANGES REQUIRED**, now resolved

- **P1, fixed.** The field was in no contract version. The UI lane landed Agent Contract v13 (#330, `5acfb9d9`), which names it in §9.1 and in the §9 extend answer. #328 merged that main and now cites v13.
- **P2, fixed.** The exact boundary (left == seconds) is pinned by a test.
- **P2, open.** No metered extend-clamp test, and no test of a replayed extend.
