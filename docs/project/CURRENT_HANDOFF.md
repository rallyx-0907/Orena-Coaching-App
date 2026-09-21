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
visual authority. Paper is retired; the code still carries Ink/Paper and D-065
compositions until each surface migrates, then they are deleted. Governance is
updated: Decision Log, tombstone, Design Contract, AGENTS Theme, product state,
and `UI_BACKEND_GAPS.md` (the one tracker, absorbing the Phase 1-3 audit).

## Last verified batch

Pytest `1136 passed, 118 skipped` and the CI `.mjs` gates were last run before
D-065; D-066 changes no code, so they are not re-run for it. Each slice reruns
them. Project-memory and architecture validators pass locally after D-066. No CI
claim.

## IN PROGRESS

Migration slices, in order, each through UI, contract, API, service,
persistence, reload, errors and tests: (1) Word and Sentence Sheet, (2) Writing
review and revision, (3) Listening and Dictation, (4) Reading comprehension per
question, (5) catalogue Search. Then learner persistence, progress measurement,
pronunciation providers. Rules that bind every slice (D-066): a metric with no
measurement renders 0 in its canonical component and is never stored as data;
no fake pronunciation result; basic lookup stays deterministic while "meaning
in this sentence" may use AI; vocabulary review has three grades and keeps
learner history; loading/empty/error follow the baseline or the existing
pattern, invented visuals are out of scope; accessibility never redesigns.

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
does not approve it. Durable raw learner audio needs its own privacy review.

## OPEN P0

None identified.

## OPEN P1

- Ink/Paper and D-065 compositions remain in code until each surface migrates.
- The baseline has no design for Profile, My Content, Admin, Onboarding,
  Loading/Empty/Error, Modal/Drawer or tablet: existing implementation stays.
- `#/language` renders "temporarily unavailable" only in long multi-room sweeps
  at short dwell; never isolated (0/130). Self-recovers.
- Cross-device continuity: device memory current; account sync gated.
- Content: Reading breadth is a rights decision per text; Vocabulary packs stay
  gated until published; the listening catalogue holds 7 lessons.
- Non-CI r8/r10/r11 matrices retired; r20 frozen native.

## HUMAN GATES

Final browser review; production, data, migration apply, provider, credential,
OAuth/DNS/Cloudflare, billing and release operations; destructive history.
Local web iteration and checkpoint commits on `codex/work` are authorized. Only
the human approves product direction.

## NEXT EXACT TASK

Slice 1, Word and Sentence Sheet, on the baseline's Dark Glass foundation (the
foundation lands with it: tokens from `docs/design/canonical-ui/tokens.json`,
one theme, no hybrid). Operate only sandbox `orena-foundation-web`:8011; restart
after Python changes; never production 8000, preview 8010, Cloudflare or volumes.
