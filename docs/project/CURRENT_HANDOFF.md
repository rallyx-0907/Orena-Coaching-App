# Current Handoff

## Governance

Purpose: compact recovery context. Change when the active stage or verified
facts change. Do not store secrets or unverified claims. Authority: current
human instruction, Orena Constitution, Content Architecture, approved brand,
D-046. No human approval or production readiness is implied.

## Current branch / lane

`codex/work`, Orena WEB Golden Star plus real learning capabilities. Do not
restore the intentionally deleted learner product. Native mobile / Expo /
React Native is frozen. Current human instruction authorizes full-stack WEB work
on the capabilities themselves, not only on the foundation.

## DONE

Recovery checkpoint (2026-09-07): continued the unfinished Reading diff from
`cf2f8b1`, without restarting the accepted Golden Star. Reading now adapts the
real session envelope, requests an explicit language-profile level, presents
generated/built-in provenance, joins kept passages into the collection, and
offers optional comprehension with passage evidence and shared understanding.
EN browser: created a B1 built-in passage and persisted a 3/4 check with one
intentional wrong answer; no proficiency claim. Reading Node contracts,
product/foundation gates, ESM graph and backend Reading self-test passed.
Continue immediately with independent Speaking; final ZH/responsive browser
acceptance remains in this same mission. Native mobile remains frozen.

D-046 authority clarification and the physical product reset are committed.
Shared media, transcript, dictation, recording, provider and evidence
primitives survive. Discovery, intentional Practice, learner imports,
continuation, expression and saved language converge on static/orena.
PostgreSQL APIs remain.

Golden Star foundation: readable type scale; first-paint system/light/dark
theme; shared page intro, intention navigation, response composer, continuation
shelf, draft status. Tinted panels carry their own ink in both themes
(--sage/coral/night/sun-surface with paired --on-*). progressReporter() gives
everything that leaves the device one voice and an always-wired retry;
savedLanguageLink() makes every vocabulary save offer the way into Recall.
Disabled controls are inert; the companion frame derives from the artwork
ratio. docs/product/ORENA_WEB_EXTENSION_GUIDE.md records what a new surface
inherits and the checks it owes.

## Learning capabilities added

- Follow tracks the spoken word where an asset ships word timing, refusing
  timing it cannot reconcile with the canonical line (capabilities/
  word-timeline.js). Shipped assets carry none and render exactly as before.
- Dictation hints show structure and the words already earned as anchors, and
  stop one character short of completing any word. Hint state is per visit and
  is never evidence; revealing the answer stays the recorded act.
- One contextual explanation system serves reading, listening, writing and
  practice (ui/understanding.js). It names which of six things is wrong rather
  than saying "wrong", carries examples and realistic counter-examples, and
  answers follow-ups without losing the selection or its context. Reading and
  Listening open it from a real highlight; every writing correction offers
  "Why is it said this way?". USAGE_JUDGEMENTS and JUDGEMENT_KEYS are one
  vocabulary, checked against each other.
- Writing keeps every version sent for review with its revision number and
  score, and continues the server's essay series across visits. Restoring an
  earlier version first keeps the unsent work.
- Speaking renders the evaluator's envelope as three separate statements -
  measured, aligned against the reference, derived guidance - each naming its
  source, with unmeasured dimensions saying so and proficiency never claimed
  from one recording (ui/voice-evidence.js).

## Last verified batch

Local execution only; no CI claim.

- Seventeen Node gates PASS, four of them new capability contracts. Browser ESM
  graph: 28 modules. Memory and architecture validators OK.
- Full Python in the app image: 753 passed / 20 failed, exactly the inherited
  baseline, unchanged including after the media_interaction contract change.
- Browser sweep light/dark at 1440/929/390 in EN and ZH, now including dialog
  content: no overflow, no text below its contrast threshold, no pointer target
  under 24px.
- Journeys against the real server: media -> Follow -> Dictation -> hints ->
  compare/persist -> look closer -> keep phrase -> Recall -> thread shelf;
  reading highlight -> explanation -> follow-ups; writing review -> revisions
  -> restore; import -> encounter -> collection. Word-level Follow verified
  both ways, fallback and tracking.

## NEXT EXACT TASK

GPT-6 review of the capability direction, then an operator pass with a
microphone and with a provider activated - neither exists in this runtime -
then human browser review. Do not expand capability breadth before that review.
The OPEN P1 decisions unblock the remaining non-CI gates and the two
specified-but-unbuilt capabilities.

## IN PROGRESS

Nothing. Foundation and first capabilities are integrated and reviewable.

## Runtime / safety

Only operate isolated `orena-foundation-web` at 127.0.0.1:8011 and its own
`orena-foundation-postgres` / network. Database is temporary; workspace mounted
read-only. Restart that container after Python changes. Do not operate
production 8000, preview 8010, Cloudflare or volumes. No provider keys
activated: writing review and contextual explanation return 503 honestly.
Pronunciation may be demo-labelled. No microphone acceptance has run; do not
claim it. Browser state seeded during acceptance was cleared.

Dependency-heavy tests use the application image: mount the repo read-only,
tmpfs /rundata, and point WRITING_DB, AUTH_DB, PLATFORM_DB and PRODUCT_DB
there. PERSISTENCE_BACKEND=sqlite is test-only, never a runtime fallback. The
active learning language is session-scoped, so switch it from inside the page.
Stage explicit task files only; never docs/visual-references.

## PENDING

Two things this runtime cannot exercise, both covered by contract tests and by
rendering rather than a live path: microphone paths (record, pronunciation,
voice feedback) need an operator pass with real hardware; and with no provider
activated, explanation and writing review were driven against injected
responses for the rich case and the real endpoint for the unavailable case, so
a provider run should confirm the judgement vocabulary and follow-ups behave as
the prompt asks.

## BLOCKED

None.

## OPEN P0

None identified.

## OPEN P1

- Platform Admin lost its host when templates/index.html was removed. Its APIs
  and static/admin.js remain, but admin.js bails at its #page-admin guard, so
  it is inert. Preserve the capability without restoring the historical learner
  shell; production activation stays gated.
- Grammar has three authored patterns per language joined by stable Concept ID.
  Scope prefers reference quality over breadth; no broad authoring pass here.
- Writing register/style exploration is specified but unbuilt. Showing one
  meaning across conversational, professional, formal, academic and technical
  registers, teaching why each sounds as it does, is asked for. The explanation
  contract carries a `register` field, which is the seam it would grow from,
  but no surface offers the comparison and no endpoint produces it. Whether it
  is its own capability or an extension of the explanation surface is a product
  decision, not a gap to fill by guessing.
- Speaking conversation architecture is unbuilt. The per-take envelope is
  honest and now fully surfaced, but nothing holds context across turns. The
  eventual language agent needs a state model designed, not improvised.
- Reading library breadth: the architecture anticipates many sources and
  licences; the shipped library is three generated texts plus the curated media
  catalog. Sourcing is a product and rights decision.
- Non-CI r8/r10/r11 matrices refer to deleted learner wrappers; admin gates to
  the missing operator host; r20 is frozen native. Do not weaken active tests
  or delete archived evidence to make those green.

## Baseline test evidence

Baselines 5827f6a and f966b28 both have 753 Python passes and the same 20
failures in test_governance_contract.py, test_media_ingestion.py and
test_media_learning.py (historical prose/source-format assertions). Do not call
these new regressions or claim an all-green suite.

## HUMAN GATES

Final browser review; production, data, migration, provider, credential,
OAuth/DNS/Cloudflare, billing and release operations; destructive history.
Ordinary local web iteration and recovery commits are authorized. Only the
human approves product direction.
