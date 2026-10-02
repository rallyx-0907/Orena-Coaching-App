# S2 Listening / Media basic browser checkpoint

2026-10-02. Scope: basic product coverage in the approved /next UI, not technical perfection or public readiness.

MILESTONE=S2_MEDIA_BASIC STATUS=REVIEWABLE COMMIT=see current verified application commit
WEB_URL=http://127.0.0.1:8021/next WEB_ROUTE=#/discover
HOW_TO_REACH_IT=Discover > + Import > File or URL / Media > Import & process
EN_PARITY=real English audio import, transcript, meanings and reload verified
ZH_PARITY=real Chinese audio import, transcript, pinyin, meanings, Dictation and Shadowing entry verified
CROSS_CAPABILITY_STATUS=Listening > Dictation, Shadowing, saved phrase, Vocabulary Focus and contextual Orena entry

## Browser evidence

- Imported existing QA speech samples through the real File chooser, not injected API/UI fixtures.
- ZH market audio became a private stored lesson with two ASR transcript segments. Playback reached its real end. Active line > Dictation compared the typed answer to the real transcript (14/24 matching units); this is comparison feedback, not a claimed verified learner score. Back returned to the same source.
- Shadowing opened with the correct source/segment and offered model-plus-record. The microphone consent sheet and Not now branch were verified. No real microphone recording/assessment is claimed in this run.
- Save phrase showed Phrase saved. Explain opened contextual Orena carrying the exact sentence. Agent remains contract/mock gated; no live explanation or personalized recommendation is claimed.
- EN morning audio import produced three real timed segments, then support meanings appeared. Full reload kept the stored source/transcript. 390x844 Active mode exposed the selected line and practice actions; Vocabulary Focus truthfully said no prepared focus terms. Viewport override reset afterwards.
- Learner YouTube URL import (Me at the zoo) produced four automatic transcript segments and opened the embed. Normal Orena Play after player readiness played through 0:19, synchronized the current line, and showed Media completed. A forced iframe click was rejected by automatic approval review; it was not bypassed. Playback was subsequently verified through the normal product button.
- Automatic transcript and estimated word timing are labeled. Processing has no invented percentage; unusable transcripts show unavailable and Refresh status, not a fake retry/result.

Screenshots: `evidence/s2-media-basic-2026-10-02/` (ZH Dictation/Shadowing, EN desktop/phone, YouTube/completed).

## Runtime / implementation

Caption-first acquisition with ASR fallback now connects imports to the existing Listening contract. Deterministic transcript gates and explicit cleared rights govern shared publication. Unknown rights stay review-held. Catalogue excludes unusable transcripts. Stored private imports retain account/language ownership; YouTube references are covered by owned deletion. Atomic job updates cannot resurrect deleted records or republish archived work. URL/file batches share their processing-spend batch.

No schema/migration, production activation, credential change or volume deletion. Only the authorized :8021 web was restarted; reading worker does not load the Media pipeline. Independent code review: S2_MEDIA_BASIC_CODE_REVIEW.md (APPROVE, no unresolved P0/P1).

## Local verification

- Canonical pytest: 2738 passed, 370 skipped, 19 warnings (isolated SQLite test backend, 157.83s).
- 123 canonical Node gates: 122 passed; inherited Word Detail due-date assertion failed as previously recorded in S4. No validator/assertion weakened.
- Browser ESM graph: 331 modules linked. Project memory/architecture and stdlib contract checks passed. Development listening catalogue check reported its declared no-snapshot skip.
- Changed Media modules Ruff: passed. Media readiness/Listening/copy checks passed. No CI PASS claimed.

## Basic-scope limits / next slice

No live microphone assessment verified; that existing provider/permission-dependent path is not presented as a scored result. Private failed imports can refresh/re-import; same-record learner retry is a follow-up. Shared upload rights editing is the next Admin content-control gap: unknown rights remain held, never blanket-published. Generic podcast/direct-audio URL admission in the current Import UI remains constrained by its existing YouTube-only URL validator; File import is usable for those media.

Next major basic product gap: Admin control-center content lifecycle, especially source-scoped rights/review/publish controls. Preserve accepted Books/Progress. Do not deepen Listening fidelity/cross-device/rare-edge/performance while major app coverage remains missing.

## YouTube import regression correction (2026-10-02)

User-reported URL `https://www.youtube.com/watch?v=B0p5SdkBydU` reproduced
`audio_unavailable`: yt-dlp 2026.07.04 extracted audio URLs that returned HTTP 403,
including with provider headers. Updating the pinned dependency to 2026.08.19
allowed the existing guarded downloader to retrieve 5,166,354 bytes without
changing URL/security gates. The same version was installed in the authorized
:8021 web container and it was restarted; future image builds use requirements.txt.

Real browser journey: Discover > Import > URL / Media > Import & process >
Listening processing > Refresh status > automatic timed transcript. The exact
video played past 0:22 and the selected transcript line followed playback.
Stored source: `source-76c2b30dbf6340f3bebc6af32ef3ca1f`. This EN video used ASR;
VI translation failed and remains unavailable, not fabricated. No new ZH/mobile
verification is claimed for this dependency correction; preceding S2 evidence
remains unchanged. Existing failed imports require re-import, not an implied retry.

Local focused regression with the updated dependency: 29 tests passed
(YouTube resolver, Media pipeline integration, Media import reasons).
Screenshot: `evidence/s2-media-basic-2026-10-02/youtube-B0p5SdkBydU-fixed.jpg`.
This fixes the reported import blocker; it does not expand S2 completion claims.
