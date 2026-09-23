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

Local, after the Vocabulary lane closed at `ea5373f`: pytest
`1938 passed, 118 skipped`. Every `.mjs` gate passes except
`test_orena_admin_console.mjs` and `test_orena_vocabulary_theme_tokens.mjs`,
both failing before this lane began (checked against a clean tree at `589ae50`)
and both inherited, not regressions. ESM graph (108 modules), memory and
architecture validators pass. **No CI claim** - local execution. Browser-checked
on :8011 against the migrated sandbox.

## IN PROGRESS

The D-067 fidelity pass, surface by surface: read the frame from the design
project at its source, measure it, compare the running app, fix, gate.

**Migrated to their frames** at 1920x1080 and 390x844, in EN, VI and ZH: the
shell, Library, the Listening workspace and Dictation (DC-5 stored, migration
`20260921_0010`, D-069), the Quick Sheet, Writing (workspace, review, revision,
entry), Home (top bar, Continue strip, six rails), the Reading workspace, and
**Vocabulary, closed 2026-09-23 at `ea5373f`** - 30 of its 32 frames running on
real reads, frames 16-17 being the Speaking lane's. A screen's ground is the UI
Baseline's lit indigo (D-071). Each surface's detail, and what it could not
resolve, is logged in `UI_BACKEND_GAPS.md`.

**Not migrated (legacy)**: Progress, the Reading library's own frame, and
Speaking (its own lane). The old top bar and the Practice hub go with them.
Not the frame yet within Writing: "Lưu nhận xét" (no meaning for it yet) and
the Writing-feedback context sheet.

Rules that bind every slice (D-066): a metric with no measurement renders 0 in
its canonical component and is never stored as data; no fake pronunciation
result; basic lookup stays deterministic while "meaning in this sentence" may
use AI; vocabulary review has three grades and keeps learner history;
loading/empty/error follow the baseline or the existing pattern, invented
visuals are out of scope; accessibility never redesigns.

Backbone lane (Opus), D-054 delegation: sandbox only, chain `20260912_0007`,
flag on, backbone `active` (runbook section 7). Writing drafts kept with the
account there (`4e1f0a5`). I4 `/api/collection`. Deletion gated (D-055). No
I1-I7 claim implies human approval.

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
does not approve it. Two have now been through that gate and are applied to
**dev and sandbox only**: `20260923_0013` (My Library, entry identity) and
`20260923_0014` (Vocabulary decks, reviewed by Claude Sonnet 5 as Delegated
Architecture Reviewer at commit `9f94ad54`). Neither is authorized for
production. Durable raw learner audio needs its own privacy review.

## OPEN P0

None identified.

## OPEN P1

- D-065 compositions (rail, Progress, cards) remain until each surface migrates.
  Home and Vocabulary are done; Progress and the Reading library frame are not.
- The baseline has no design for Profile, My Content, Admin, Onboarding,
  Loading/Empty/Error, Modal/Drawer or tablet: existing implementation stays.
- `#/language` renders "temporarily unavailable" only in long multi-room sweeps
  at short dwell; never isolated (0/130). Self-recovers.
- Cross-device continuity: device memory current; account sync gated.
- Content: Reading breadth is a rights decision per text; Vocabulary packs stay
  gated until published; the listening catalogue holds 6 lessons.
- Chinese character parts (radical/components) are curated for 42 characters;
  89 of the static Chinese catalogue's 131 have none and draw no section. Every
  declared radical is machine-checked against the vendored stroke pack.
- No populated Vocabulary frame draws a way to add a word by hand, so frames
  23-24 are reached from frame 29 (the empty room) and frame 22's set picker.
  Drawing another door is the human's decision, and was declined 2026-09-23.
- Non-CI r8/r10/r11 matrices retired; r20 frozen native.

## HUMAN GATES

Final browser review; production, data, migration apply, provider, credential,
OAuth/DNS/Cloudflare, billing and release operations; destructive history.
Local web iteration and checkpoint commits on `codex/work` are authorized. Only
the human approves product direction.

## NEXT EXACT TASK

**Vocabulary is closed; pick up the fidelity pass where it now stands.** What
is left of the D-067 surface-by-surface migration, in the order this file has
always carried it:

1. **Reading** - slice 4 (comprehension per question) and the Reading
   library's own frame, which is still the legacy composition.
2. **Progress** - not migrated at all; `Orena Progress.dc.html` is pinned in
   the cache.
3. **Speaking** - another lane's, including Vocabulary frames 16-17.

Then delete the legacy pieces each migration leaves behind, along with the
stale `verify_writing_*_browser.mjs` scripts and unused copy keys.

The method does not change (D-067): read the frame from the design project at
its source, measure it, compare the running app, fix, gate. Invent nothing the
source does not draw; record what cannot be resolved in `UI_BACKEND_GAPS.md`.

Still waiting on the human, unchanged: DC-5 (store hint use?), the taxi lesson,
the logo (the frame's violet square, or the orange mascot), the Vietnamese pack
keeping the design's English product names, the phone search that expands on
focus and the library's "load more", the DM Mono to Roboto Mono fallback for
Vietnamese, the disabled "Kiểm tra hiểu" action (no listening items yet), and
the rights block kept under the workspace (the frame draws none).

Operate only sandbox `orena-foundation-web`:8011; restart after Python changes.
For AI-backed checks select Gemini there (`PUT /api/admin/ai/config`,
`gemini-3.5-flash-lite`; the key is already in the sandbox env, never print
it): the Ollama default takes 17-54 s per call. Never production 8000, preview
8010, Cloudflare or volumes.
