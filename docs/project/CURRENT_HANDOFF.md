# Current Handoff

## Governance

Purpose: compact recovery context, updated after verification. Change when the
active stage or verified facts change. Do not store secrets or unverified claims.
Product authority: current
human instruction, Orena Constitution, Content Architecture, approved brand,
D-046. No human approval or production readiness is implied.

## Current branch / lane

`codex/work`, Orena WEB Golden Star. Continues 7c98fad, the interrupted Golden
Star run; do not restore the intentionally deleted learner product. Native
mobile / Expo / React Native is frozen. Latest human instruction explicitly
authorizes this continuation beyond the earlier REVIEWABLE checkpoint.

## DONE

D-046 authority clarification and physical product reset are committed. Shared
media, transcript, dictation, recording, provider and evidence primitives survive.
Discovery, intentional Practice, learner imports, continuation, expression and
saved language converge on the new static/orena product. PostgreSQL APIs remain.

Current Golden Star work: shared readable typography and interaction foundation;
first-paint system/light/dark theme adapter; shared page intro, Practice intention
navigation, contextual response composer, continuation shelf and draft status;
Practice media previews with honest source/context; expression with original
context and generated situation starters; persistent draft excerpts; account
vocabulary save -> Recall links. Recovery evidence captures one baseline so
repeated saves cannot double-count attempts. Recall refresh retries do not submit
an already-saved grade twice. Approved world scene replaces the white-backed
mascot crop; a generated extraction was rejected and is not a product asset.

Shared foundation completed after 7c98fad: every tinted panel carries its own
ink in both themes (--sage/coral/night/sun-surface with paired --on-* ink), so
a panel is never a colour a screen pairs by hand; work that leaves the device
reports through progressReporter(), which speaks in one voice, will not write
onto a view the learner left, and wires any retry it renders; savedLanguageLink()
makes every vocabulary save offer the same way into Recall, which the story
margin previously lacked entirely; disabled controls no longer lift or press;
the companion frame is derived from the artwork ratio, retiring a mascot-era
crop whose phone override was still fighting it. Extension guidance now exists
at docs/product/ORENA_WEB_EXTENSION_GUIDE.md.

## Last verified batch

Local execution only; no CI claim.

- Golden Star foundation test PASS, now also computing every panel/ink contrast
  pairing from the token block and holding the reporter contract in EN and ZH.
  Both new guards verified to fail when their fix is reverted.
- All twelve CI Node gates PASS. Browser ESM graph: 24 modules linked.
- Project-memory and architecture validators OK.
- Full Python in the app image: 753 passed / 20 failed, exactly the inherited
  baseline, unchanged by this run.
- Browser acceptance: eleven routes x light/dark x 1440/800/390 in EN and ZH.
  No horizontal overflow, no text below its contrast threshold, no pointer
  target under 24px. The sweep previously found whole-caption failures on
  Explore in both themes.
- Journeys driven against the real server: media -> Follow -> Dictation ->
  compare/persist -> look closer -> keep phrase -> Recall hand-off -> thread
  shelf; story -> margin phrase -> Recall; free Writing with target level ->
  truthful 503; a blocked vocabulary write, its retry, and its success.

## NEXT EXACT TASK

The archetype references and the shared foundation are in place and swept. Next:
one operator pass on microphone paths (record, pronunciation, voice feedback),
which no run has executed; then human browser review. Do not expand capability
breadth before that review. If review approves, the open decisions in OPEN P1
are what unblock the remaining non-CI gates.

## IN PROGRESS

Nothing. The Golden Star foundation is integrated, swept and reviewable.

## Runtime / safety

Only operate isolated `orena-foundation-web` at 127.0.0.1:8011 and its own
`orena-foundation-postgres` / network. Database is temporary; workspace mounted
read-only. Do not operate production 8000, preview 8010, Cloudflare or volumes.
No provider keys activated. Writing review returns 503 honestly. Pronunciation
may be demo-labelled. No microphone acceptance has run; do not claim it.

Dependency-heavy tests use the application Docker image. For ephemeral tests,
mount repo read-only, tmpfs /rundata and set WRITING_DB, AUTH_DB, PLATFORM_DB,
PRODUCT_DB there; PERSISTENCE_BACKEND=sqlite is test-only, never runtime fallback.
Git metadata is outside the writable worktree: staging/checkpoint commits need
normal sandbox escalation. Stage explicit task files only. Do not stage or remove
docs/visual-references. No production operations or destructive history.

## PENDING

Microphone paths need one operator pass with real hardware; their guards are
source contracts, not execution. Then final human review.

## BLOCKED

None.

## OPEN P0

None identified.

## OPEN P1

- Platform Admin lost its host when templates/index.html was removed. Admin APIs
  and static/admin.js remain. Preserve this operational capability without
  restoring the historical learner shell. Prior handoff incorrectly treated any
  local repair as requiring a human gate; production activation remains gated.
- Grammar has three generated authored patterns per language joined by stable
  Concept ID. Latest Golden Star scope explicitly prefers reference quality over
  full breadth; no broad authoring pass belongs here.
- Microphone, real pronunciation and provider feedback require later operator
  verification; no paid activation belongs to this mission.
- Historical non-CI r8/r10/r11 matrices refer to deleted learner wrappers; admin
  gates refer to the missing operator host; r20 is frozen native. Do not weaken
  active primitive tests or delete archived evidence to make those runners green.

## Baseline test evidence

Pristine integrated baseline 5827f6a and f966b28 both have 753 Python passes and
20 identical failures in test_governance_contract.py, test_media_ingestion.py,
test_media_learning.py (historical prose/source-format assertions). Do not call
these new regressions or claim an all-green full suite.

## HUMAN GATES

Final Golden Star browser review; production/data/migration/provider/credential,
OAuth/DNS/Cloudflare/billing/release operations; destructive history. Ordinary
local web iteration and recovery commits are authorized. Only the human approves
product direction.
