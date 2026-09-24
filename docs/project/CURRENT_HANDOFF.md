# Current Handoff

## Governance

Purpose: compact recovery context. Change when the active stage or verified
facts change. Do not store secrets or unverified claims. Authority: current
human instruction, the Canonical UI Baseline (D-066) for how a learner surface
looks, behaves and what data it shows, then Orena Constitution, Content
Architecture, approved brand, D-046. No human approval or production readiness
is implied.

## Current branch / lane

`codex/work`, in the `-codex` worktree, Orena WEB: integrate the Canonical UI
Baseline. By explicit instruction (D-066) work goes directly on this branch:
no new branch or worktree, logical commits, stage only each step's files. Do
not restore the deleted learner product. Native mobile stays frozen.

## DONE

D-046 and the product reset. D-066 accepted 2026-09-21: the frozen Dark Glass
baseline, pinned in `docs/design/canonical-ui/`, replaces D-059 and D-065 as
visual authority. Paper, sepia and the theme picker are already gone from the
code (`d0820ba`); the D-065 compositions remain until each surface migrates, then
they are deleted. Governance is
updated: Decision Log, tombstone, Design Contract, AGENTS Theme, product state,
and `UI_BACKEND_GAPS.md` (the one tracker, absorbing the Phase 1-3 audit).

## Last verified batch

Local, after slices 1-3 and the bug passes: pytest `1173 passed, 118 skipped`; every CI
`.mjs` gate passes except `test_m3_pronunciation_contract.mjs`, failing since
D-065 removed the score (Speaking slice); ESM graph, memory and architecture
validators pass. No CI claim. Browser-checked on :8011 (vi, EN text; zh word via API;
touch swipe, phone sheet and library in a touch-enabled context), not READY.

## IN PROGRESS

Migration slices, in order, each through UI, contract, API, service,
persistence, reload, errors and tests: (1) Word and Sentence Sheet and (2) Writing
review and revision - built and browser-checked, remaining checks in the tracker's
log; the Dark Glass foundation landed with (1); (3) Listening and Dictation - 3a the Library and 3b the workspace details and the Dictation screen built (per-character pinyin from the backend), open: DC-5 and the taxi lesson need a human decision, (4) Reading
comprehension per question, (5) catalogue Search. Then learner persistence, progress measurement,
pronunciation providers. Rules that bind every slice (D-066): a metric with no
measurement renders 0 in its canonical component and is never stored as data;
no fake pronunciation result; basic lookup stays deterministic while "meaning
in this sentence" may use AI; vocabulary review has three grades and keeps
learner history; loading/empty/error follow the baseline or the existing
pattern, invented visuals are out of scope; accessibility never redesigns.

Speaking lane (`feature/speaking`, `D:\Orena-Speaking`, sandbox :8013; not merged, not pushed):
REVIEWABLE. The source design (D-075) is the Speaking UI: library, workspace, word detail, compare,
summary, shadowing, states, free talk and its result, measured at 1920/390 in EN/VI/ZH (SP-1..15,
S1-S23, D-076). Azure (scripted + unscripted), Groq ASR and Gemini ran for real
(`docs/operations/SPEAKING_AZURE_E2E_2026-09-23.md`). D-077..D-080 applied (three language layers; every copy key declares its layer, AUDIT-1b closed). Human: S24 (Grammar's way in).

Backbone lane (Opus), D-054 delegation: sandbox only, chain `20260912_0007`,
flag on, backbone `active` (runbook section 7). Writing drafts kept with the
account there (`4e1f0a5`). I4 `/api/collection`. Deletion gated (D-055). No
I1-I7 claim implies human approval.

Fidelity pass (D-067, measured against the design at its source): built to their frames at 1920x1080 and
390x844, in EN, VI and ZH - the shell, Library, Listening workspace, Dictation (steps, one screen on a desk and a
phone, DC-5 stored: migration `20260921_0010` in the sandbox, D-069), the Quick Sheet, the Writing workspace,
review (two panes; Draft / Review tabs on a phone), revision (three columns) and entry (`#/writing`). A screen's
ground is the UI Baseline's lit indigo (D-071). Bugs 7-15 are fixed. Writing review and revision are the frames too (findings marked in the draft, one primary action, three-column
comparison). Not the frame yet: "Lưu nhận xét" (no meaning for it yet), the Writing-feedback context sheet.
Home is its frames too (top bar, Continue strip, six rails; the old Discover composition deleted).
The Reading workspace is one screen with the frame's bar. Not migrated (legacy): Progress, Speaking, Vocabulary, the Reading library's own frame; the old top bar and the Practice hub go
with them.

## PENDING

Source Import and Vocabulary catalog: human schema/runtime authorization for
`20260916_0008`, then PostgreSQL rehearsal. R3 Gemini live gate passed 4/4;
Ollama `qwen3:8b` leaks target script in nested support answers. Pronunciation
needs a configured Azure or SpeechSuper provider (credentials are a human gate).

## BLOCKED

Production/preview deploy and activation past the sandbox: separate human gate,
not authorized. A learner-owned schema or migration is authored against
`ORENA_ACCOUNT_DATA_ARCHITECTURE.md` and needs a recorded independent
architecture review before it is applied to a shared runtime; the implementer
does not approve it. Durable raw learner audio needs its own privacy review.

## OPEN P0

None identified.

## OPEN P1

- D-065 compositions (rail, Home, Progress, cards) remain until each surface migrates.
- The baseline has no design for Profile, My Content, Admin, Onboarding,
  Loading/Empty/Error, Modal/Drawer or tablet: existing implementation stays.
- `#/language` renders "temporarily unavailable" only in long multi-room sweeps
  at short dwell; never isolated (0/130). Self-recovers.
- Cross-device continuity: device memory current; account sync gated.
- Content: Reading breadth is a rights decision per text; Vocabulary packs stay
  gated until published; the listening catalogue holds 6 lessons.
- Non-CI r8/r10/r11 matrices retired; r20 frozen native.

## HUMAN GATES

Final browser review; production, data, migration apply, provider, credential,
OAuth/DNS/Cloudflare, billing and release operations; destructive history.
Local web iteration and checkpoint commits on `codex/work` are authorized. Only
the human approves product direction.

## NEXT EXACT TASK

Human decisions (`UI_BACKEND_GAPS.md`, S3b log): DC-5 (store hint use?), the taxi lesson, the logo (the
frame's violet square, or the orange mascot), the Vietnamese pack keeping the design's English product
names, the phone search that expands on focus and the library's "load more", the DM Mono to Roboto
Mono fallback for Vietnamese, the disabled "Kiểm tra hiểu" action (no listening items yet), the
rights block kept under the workspace (the frame draws none). Then continue the fidelity pass surface
by surface with the D-067 method (read the frame from the design project, measure it, compare the
running app, fix, gate): Writing (workspace first: rebuild the frame's composition around the existing draft, review and revision plumbing; the intention field, level select and starters need a place from the source or a recorded decision), then migrate Home, Reading (slice
4, comprehension per question), Speaking, Vocabulary, Progress, and delete the legacy pieces each
leaves behind. Also the stale `verify_writing_*_browser.mjs` scripts and unused copy keys.
Operate only sandbox `orena-foundation-web`:8011; restart
after Python changes. For AI-backed checks select Gemini there (`PUT /api/admin/ai/config`,
`gemini-3.5-flash-lite`; the key is already in the sandbox env, never print it): the
Ollama default takes 17-54 s per call; never production 8000, preview 8010, Cloudflare or volumes.
