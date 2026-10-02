# S2 Listening / Media basic browser checkpoint

## Reported corrections — 2026-10-02 (D-116)

MILESTONE=S2_MEDIA_CORRECTIONS STATUS=REVIEWABLE COMMIT=recorded in CURRENT_PRODUCT_STATE.yaml
WEB_URL=http://127.0.0.1:8021/next
WEB_ROUTE=#/listen/upload%3Asource-e6d16be65134460e9cfbe6f3b0921483
HOW_TO_REACH_IT=My Library > imported media > Listening > Active > Dictation / Shadowing / word lookup
EN_PARITY=real B0p5SdkBydU transcript and VI meanings on desktop and 390x844
ZH_PARITY=reported source has 89/89 VI meanings; desktop and 390x844 verified
CROSS_CAPABILITY_STATUS=owner/language/support-scoped ready media reused by Listening, Dictation, Shadowing, React and speaking source consumers; contextual Agent remains gated

WHAT_CHANGED=Idle play/time chrome hides while playing; Listening disables provider controls. Import uses actual processing stages/progress and says Orena AI without paid-resource wording (supersedes D-115 presentation only). Shared loading uses an indeterminate bar when no measured completion exists; DESIGN_CONTRACT records the global convention. Partial translation batches remain cached; retries request missing meanings only. Stored media receives the selected support language. Derived translation/dictionary cache now uses existing durable media storage, not /rundata; PostgreSQL learner authority is unchanged. Five-minute session reuse avoids repeated preparation across connected rooms, while deletion checks also cover joined in-flight callers.

Lookup paints deterministic dictionary content first, with an explicit loading state beforehand and non-destructive contextual enrichment. Chinese stroke previews and animated median-path direction work. Encounter pronunciation resolves a validated term/explicit reading without creating a catalogue identity. Browser 好 / hǎo played actual Commons audio (currentTime 1.04, readyState 4, error null), with CC BY attribution. Stroke Watch showed a directional path animation.

Fixed-speed word highlighting is removed. New ASR results retain genuine word timestamps; existing reported imports have none and the control is truthfully disabled. Imports display reviewed level if present, otherwise explicitly source-declared HSK/CEFR or unassessed; no automatic validated level assessment is claimed. Chinese long lines override the old shared nowrap selector. Phone Active shows the full sentence/VI meaning and wrapped actions: page width=scrollWidth=390, height=scrollHeight=844, action bottom=660. Transcript scrolling stays within its viewport panel. EN phone also displays full selected text/meaning without page overflow.

ACTUAL_BROWSER_EVIDENCE=Exact ZH source retained 89 meanings after reload and sandbox web restart; Dictation/Shadowing return retained meanings. Playing idle: chrome false, play/time opacity 0, embed controls=0. EN transcript and VI meaning verified on desktop/phone. Chinese target language restored and viewport override reset.

Screenshots: [ZH phone](evidence/s2-media-corrections-2026-10-02/zh-phone-active.jpg), [playback](evidence/s2-media-corrections-2026-10-02/zh-playing.jpg), [lookup/audio/strokes](evidence/s2-media-corrections-2026-10-02/zh-lookup-audio-strokes.jpg), [EN translated](evidence/s2-media-corrections-2026-10-02/en-translated.jpg), [EN phone](evidence/s2-media-corrections-2026-10-02/en-phone-active.jpg).

TESTS=Local full Python suite before final pronunciation delta: 2744 passed / 370 skipped. Final audio/detail delta: 50 passed; Media/meaning/pipeline/detail batch: 71 passed. Ruff and relevant Listening/Quick Sheet/Dictation/Shadowing/stroke/session/copy/ESM gates passed. CI-listed Node gates: 122/123; Word line 110 is date-dependent on 2026-10-02 and fails identically on a clean HEAD archive. No assertion weakened; no CI PASS claimed.

WHAT_THE_HUMAN_SHOULD_REVIEW=Player chrome, import progress, dictionary loading/meaning, pronunciation/stroke direction, line wrapping, persistent VI meanings and room return. Remaining basic limitations: old media needs actual word timing before per-word highlight; undeclared levels stay unassessed; private failed jobs still require re-import. Next major basic gap: Admin content lifecycle, then canonical Grammar and integrated Intelligence/Agent. No public readiness/human approval claimed. Earlier dated evidence below remains historical.

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

## Core support meaning and processing UI correction (2026-10-02)

Human clarified that support-language translation is core Listening and requested
visible processing/resource disclosure. This supersedes treating the failed VI
translation above as an acceptable completed slice.

Groq returned `json_validate_failed` for the real long-ID transcript. Three-line
requests worked. Translation now uses bounded completion-aware splitting and
request-local handles for long provenance IDs, mapping every output back to its
canonical segment. Invalid, missing and duplicate results are rejected; bounded
smaller requests may recover, without another provider or fabricated meanings.

Real browser evidence on :8021: the exact B0p5SdkBydU video displayed Vietnamese
meanings under transcript rows and in Now playing. Reload retained them. A second
real Import displayed the paid speech-recognition notice from the `transcribe`
stage, then opened a processing Listening workspace and transitioned to the
translated transcript automatically. The 390x844 viewport showed video, controls
and translated transcript with its own scroll region. Desktop unavailable-state
bounds measured contained within the Transcript panel, not over the player.
Processing uses the existing spinner/status UI; Listening's load state explains
support meaning preparation and conditional paid processing. Failed jobs do not
claim active AI work. No fake percentage or completed translation is shown.

Screenshots: `youtube-B0p5SdkBydU-translated.jpg`,
`youtube-support-meaning-reload.jpg`, `youtube-paid-processing.jpg`,
`transcript-state-fixed.jpg`, `transcript-processing-phone.jpg` in the existing
evidence folder. The phone artifact captured the completed translated state.

Local focused tests: 66 passed (provider, bounds, identity, Media meanings/cache,
shared Reading translator); Ruff passed. Copy EN/VI/ZH, Listening workspace,
Media readiness and browser ESM331 passed. EN/VI desktop/phone runtime was
verified in this correction; prior ZH browser evidence remains unchanged.
An initial diagnostic was rejected by automatic approval review; after proving
the container's internal port maps only to :8021 and the public-video translation
scope, the same diagnostic was authorized. No rejected action was bypassed.
