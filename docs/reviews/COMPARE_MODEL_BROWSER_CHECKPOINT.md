# Compare With Model correction — 2026-10-03

## Current browser checkpoint — fresh result after authorized QA recovery

Fresh Chinese acceptance follow-up: user recorded directly. Real Azure 75/100,
Accuracy84/Fluency69/Completeness83, 14.3 s speech, 23 provider words. Pinyin,
learner contours and timing rendered; first 这 has You0.00–0.30s versus
Model0.00–0.25s. History in a separate fresh tab shows 18:13 Speaking75 and
opens `zh-daily-what-is-this` / `commons-zh-lesson-7-dialogue-1:000`.
Evidence: `evidence/compare-zh-real-result-2026-10-03.png`.
Browser control works again; earlier extension block below is historical.
Model pitch is unavailable across the two inspected word pages on this source.
Read-only ffmpeg/YIN probe of the public cached model source at half-second
intervals found periodicity minima mostly above0.3, versus the extractor's0.15
threshold (one probe0.174). This supports a source-confidence limitation, not a
learner weakness; it does not establish a complete acoustic root cause.
Model timing and source audio remain available. Improving source-pitch extraction
is deferred under the human's instruction to note difficult pitch limitations.

The real result exposed contradictory pronunciation labels on word这: provider
ErrorTypeNone was shown as Passed while the approved score status67 was Not passed.
Panel and Details now share one status projection, retaining actual phoneme/error
evidence separately. RED/GREEN verdict regression and Compare gates pass locally.
The live rich-result tab has not been reloaded, so this correction still needs a
fresh-take browser check; no claim that the existing loaded tab was hot-patched.

Follow-up: Back recovery fixed with the existing account-backed media continuation:
Compare records `speaking_compare` plus canonical segment; Today and Practice Hub
resolve that to the real Compare route. Scripted Speaking resumes its same segment.
Practice Hub now offers Pronunciation for real transcript-backed clips, preserving
the preferred authored-sentence source when available. No new schema or learner-data
authority. Browser verified Back → Today → Continue and Hub → Compare, exact
`segment=commons-royalsociety-cosmic-calendar:000`; Hub visibly labels Compare.
Evidence: `evidence/speaking-resume-hub-2026-10-03.png`.

Fresh server History shows two real 86 results, at 17:44 and 17:50; selecting the
latest opens the correct media/segment Attempt History, count2/best86/change0.
Audio-free server history is distinct from tab-only recording retention (D-076).
Chinese Hub → Pronunciation opens `zh-daily-what-is-this`; Compare preparation
renders all pinyin with contextual `bù`/`bú` and tone tokens. Punctuation loss in
Compare's recorder was corrected; browser verified the full Chinese sentence.
No fresh Chinese learner assessment claimed. Brave extension then required an
update, blocking further browser control; original profile was EN, current test
scope ZH. The human's EN result tab was never reloaded or navigated.

Deferred pitch limitation: the existing YIN measurement requires a periodic signal
within 70–450 Hz, 40 ms analysis windows, and rejects voiced runs shorter than
60 ms; contour rendering also breaks silence and sudden jumps. Short/quiet/noisy
or predominantly unvoiced word spans can legitimately have no drawable contour.
This is not a pronunciation failure. Do not relax evidence gates or manufacture
curves to fill the missing tiles. Improving extraction/confidence is deferred;
actual timing, word/phoneme scores and playback remain usable independently.
No acoustic diagnosis of this user's individual missing frames is claimed.

2026-10-03: user recorded directly in the fresh Compare tab. Azure result: 86,
Accuracy 85, Fluency 100, Completeness 81, 5 seconds speech. All 16 source IPA
readings render. Selecting `starting` shows genuine paired Model/You pitch;
Timing shows Model 1.24–1.77 s and You 0.94–1.45 s, 0.02 s shorter. Pronunciation
shows actual Azure phonemes/scores (including ŋ 17), not a synthetic curve.
Some short words lack measurable pitch: explicit unavailable state remains.
Model → You Play visibly changes to Stop then returns to Play without browser
errors. Hear yours exercised; acoustic output was not independently listened to.
390×844 uses two paged tiles, no document horizontal overflow, persistent playback
and retry controls; long details occupy the existing named internal scroll region.
Screenshots: `evidence/compare-real-pitch-2026-10-03.png`,
`evidence/compare-real-mobile-2026-10-03.png`.

Local scoped Python: 70 passed, 2 dependency deprecation warnings; Ruff passed.
Previously run Node reference/audio/Compare/Speaking/memory/copy/ESM/foundation gates
passed, including fresh Speaking-resume/Practice/Today/Continue gates. No CI or
full-product completion claimed. Fresh ZH assessment, skin variants and durable
PostgreSQL restart verification remain open; extension update blocks UI control.

QA recovery: old PostgreSQL used tmpfs and was empty after restart. Human explicitly
authorized a new durable `orena-next-verify-postgres` volume and reviewed schema
`20260930_0023`; old container preserved, web :8021 runs, worker stays stopped.
No old QA records recovered, no :8000 changes, no automatic schema startup/import.
Earlier take83/history below is historical evidence, not the current database.

## Implementation follow-up plan (human: finish form and function against the design)

1. Connect deterministic IPA/pinyin readings to record tokens, word tiles and
   selected Word Detail, without contextual generation or fabricated phonetics.
2. Analyse the real source clip using the existing pronunciation provider to
   obtain word boundaries only when canonical boundaries are absent. Keep this
   reference analysis separate from learner attempts and scoped to source/account.
3. Match model/learner words by their character ranges in the same reference,
   including repeats and multi-character ZH words. Overlay measured pitch,
   show both timing rows and play the actual model word clip.
4. Correct source-audio resolution for supported imports using existing access
   and language/publication guards. Never serve cached deleted/private sources.
5. Verify actual EN/ZH browser journeys, phonetics, paired plots/timing,
   recording, tabs, word playback, history return, desktop/mobile and themes;
   compare the pinned screen and both Visual Skin references before completion.

MILESTONE=Speaking Compare prototype correction
STATUS=IMPLEMENTING (browser review checkpoint; remaining acceptance below)
COMMIT=the Git commit containing this checkpoint
WEB_URL=http://127.0.0.1:8021/next
WEB_ROUTE=#/speak/media%3Aen-science-cosmic-calendar/compare
HOW_TO_REACH_IT=Listening line -> Speaking -> Compare with model
EN_PARITY=real microphone/Azure result exercised
ZH_PARITY=shared implementation and en/vi/zh copy checked; live ZH result not exercised
CROSS_CAPABILITY_STATUS=Listening source/Compare/Attempt History retained

## Design provenance and correction

Composition: pinned `Orena.dc.html` frame 16 wrapper and embedded
`Compare-With-Model.dc.html`. Treatment: `Orena Visual Skin (2).html` and
`Orena Visual Skin ZH.html`, through existing shared semantic tokens. Current
approved brand assets remain unchanged. No token or palette owner added.

The old large whole-sentence pitch graph and plain score tiles replaced the
prototype's paired per-word Model/You plots. The corrected screen restores
those slots, connects selection to Word Detail and Pitch/Tone, Timing and
Pronunciation, and keeps the existing recording, assessment and playback paths.
The frame subtitle is restored; attempt pills sit beside the header actions.
Always-visible implementation/privacy prose is removed; the existing microphone
consent disclosure remains.

Viewport adaptation: word tiles retain the prototype's per-word minimum widths
and duration-based growth, but use bounded groups with previous/next actions
instead of its overflowing horizontal strip. Every word remains reachable.
The actual row width, including scrollbar space, determines grouping. Playback
follows the active word's group. Pagination preserves keyboard focus, falling
back to the selected word at an end; icon-only mobile playback retains its label.

Plots use real decoded audio and provider word intervals. A missing/insufficient
voiced interval displays a neutral dash. No model word intervals exist in this
source contract, so Model word plots/timing remain explicitly unavailable.
No prototype synthetic curves, scores or coaching claims were copied.

## Actual browser evidence

On :8021, real user microphone recording and Azure Speech assessment:
- First attempts returned no-speech; the UI showed a retryable learner message,
  never a manufactured result.
- The user recorded directly and received overall 83, accuracy 80, fluency 92,
  completeness 81; the recognized sentence and per-word evidence were visible.
- Sixteen words reachable in desktop groups 1–9 and 10–16. Selecting the next
  group changed Word Detail to `cheering`, score 94. Timing showed the real
  16.40–16.84 second interval; Pronunciation showed measured phoneme scores.
- Pitch on `cheering` rendered its measured curve. Other insufficient intervals
  showed unavailable. Model slots remained unavailable throughout.
- Yours only, speed 1.25 and Play/Stop visibly transitioned; no claim about
  physical speaker audibility is made.
- At 1910x855, root client/scroll width 1180/1180, tiles 1130/1130.
  At 390x844, root 350/350, tiles 300/300; two words per group, tabs and playback
  reachable inside the named scrolling region. Temporary viewport override reset.
- Attempt History showed the new 83 server-backed record beside older 74/72
  records. This verifies evidence continuity, not audio retention after reload.

Screenshots: [desktop](evidence/compare-model-desktop-2026-10-03.png),
[mobile Word Detail](evidence/compare-model-mobile-2026-10-03.png).

The screenshots/browser journey precede the final review correction to precise
tile minimums, playback-following groups and keyboard/mobile labels. Those final
changes have local contract/ESM checks and independent read-only review, but need
a fresh browser result. The live take was left open rather than discarded by
reload. No result fixture or fake microphone was injected.

## Verification and limits

Local execution, each PASS (no skipped test cases): Compare mapping, copy
(45 tables / 2593 keys), Library screen, Speaking take lifecycle, Speaking
attempt retention, foundation; browser ESM graph (332 modules); project-memory
validator. No CI claim or full backend suite claim for this UI-only change.
Independent reviewer `/root/review_compare_ui` inspected unstaged changes from
`a061cc2bb66044596d911ec6fa8650f0ab0a118c`; word sizing/focus findings addressed.
No known remaining P0/P1 code finding; complete browser fidelity is not claimed.

Remaining: fresh-browser acceptance of final sizing/focus changes, live ZH result
and light/other-accent comparison. Mobile still stacks detail within its named
scroll region; all feedback is not simultaneously visible in one viewport.
Model word plots need genuine source word timing, not invented alignment.
Session-only audio does not survive reload under the existing retention setting;
server History retains evidence. No persistence/schema/retention change made.

Protected-area change: Compare presentation only, explicitly requested by the
human. Backend/provider credentials, Library, shared tokens/brand and Docker
untouched. No deployment, production action or app version bump. Files changed:
Compare screen/model/copy/CSS, its Node gate, current state/handoff/product status,
this checkpoint and two screenshots. `PROJECT_STATE.md` unchanged. User-owned
`DESIGN_CONTRACT.md` remains unstaged and is not part of this change.
