# Compare With Model correction — 2026-10-03

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
