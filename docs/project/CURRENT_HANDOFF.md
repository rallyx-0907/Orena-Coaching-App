# Current Handoff

## Governance

Purpose: compact recovery context. Change when the active stage or verified
facts change. Do not store secrets or unverified claims. Authority: current
human instruction, Orena Constitution, Content Architecture, approved brand,
D-046. No human approval or production readiness is implied.

## Current branch / lane

`codex/work`, Orena WEB Golden Star plus real learning capabilities. Do not
restore the intentionally deleted learner product. Native mobile / Expo /
React Native is frozen. Current human instruction authorizes full-stack WEB
work on the capabilities themselves, not only on the foundation.

## DONE

D-046 authority clarification and the product reset are committed. Shared
media, transcript, dictation, recording, provider and evidence primitives
survive. Discovery, intentional Practice, learner imports, continuation,
expression and saved language converge on static/orena. PostgreSQL APIs remain.

Golden Star foundation: readable type scale; first-paint system/light/dark
theme; shared page intro, intention navigation, response composer,
continuation shelf, draft status. Tinted panels carry their own ink in both
themes (--sage/coral/night/sun-surface with paired --on-*).
progressReporter() gives everything that leaves the device one voice and an
always-wired retry; savedLanguageLink() makes every vocabulary save offer the
way into Recall. ORENA_WEB_EXTENSION_GUIDE.md records what a surface inherits.

## Learning capabilities

- **Follow** is an intention, not a corridor to an exercise: it opens no
  practice panel, so a learner can consume a whole media item without being
  pushed into Dictation. It tracks the spoken word where an asset ships word
  timing and refuses timing it cannot reconcile with the canonical line.
- **Dictation** hints show structure and earned words as anchors, stopping one
  character short of any word. Hint state is per visit, never evidence.
- **Reading** adapts the real session envelope (`becoming_reading.py`, reused,
  not rebuilt), labels generated versus built-in provenance, joins kept
  passages into the collection, and offers optional comprehension whose every
  result names the words in the passage that settle it. `reading` is its own
  intention beside Follow.
- **Writing** renders the full evaluator payload the surface used to discard:
  weighted dimensions, CEFR, delta against the last revision, strengths quoted
  from the learner, issues carrying why/how/priority. An issue whose quote is
  not in the learner's text is dropped. Register exploration
  (`POST /api/dictionary/registers`) shows one meaning across five registers
  with the signals that place each and when each is wrong - not a rewrite
  button, no version presented as correct. Every version sent for review is
  kept with its revision number and score.
- **Speaking** is its own experience: situation or the learner's own prompt,
  record, transcript, evidence, guidance, retry. Free expression carries no
  reference line, so alignment is *not applicable* rather than *not measured*,
  and the evaluator and the persistence boundary both refuse content alignment
  without a reference. Measured evidence (ui/voice-evidence.js) and coaching
  (ui/spoken-coaching.js, `POST /api/dictionary/spoken-response`) are separate
  panels making separate claims; coaching reads the transcript, never the
  audio, quotes only words the learner said, and does not score.
- **One contextual explanation system** serves reading, listening, writing,
  speaking and practice (ui/understanding.js). It names which of six things is
  wrong rather than saying "wrong". USAGE_JUDGEMENTS, JUDGEMENT_KEYS and the
  spoken-coaching schema are one vocabulary, checked against each other.

## Last verified batch

Local execution only; no CI claim.

- Twenty-one Node gates PASS. Browser ESM graph: 37 modules. Memory and
  architecture validators OK.
- Full Python in the app image: 753 passed / 20 failed, exactly the inherited
  baseline.
- Browser sweep light/dark at 1440/929/390 in EN and ZH: no overflow, no text
  below its contrast threshold, no pointer target under 24px.
- Journeys against the real server: media -> Follow -> Dictation -> hints ->
  compare/persist -> look closer -> keep phrase -> Recall; reading request ->
  passage -> highlight -> explanation -> comprehension -> evidence in the
  passage; writing review -> revisions -> registers; speaking take ->
  transcript -> evidence -> coaching -> develop as writing.

## Runtime / safety

Only operate isolated `orena-foundation-web` at 127.0.0.1:8011 and its own
`orena-foundation-postgres` / network. Database is temporary. Restart that
container after Python changes; the worktree is mounted, but uvicorn does not
reload. Do not operate production 8000, preview 8010, Cloudflare or volumes.
No provider keys activated: writing review, contextual explanation, registers
and spoken coaching all return 503 honestly. Pronunciation may be
demo-labelled. No microphone acceptance has run; do not claim it.

Dependency-heavy tests use the application image: mount the repo read-only,
tmpfs /rundata, and point WRITING_DB, AUTH_DB, PLATFORM_DB and PRODUCT_DB
there. PERSISTENCE_BACKEND=sqlite is test-only, never a runtime fallback. The
learning language is session-scoped, so switch it from inside the page. Stage
explicit task files only; never docs/visual-references.

## NEXT EXACT TASK

GPT-6 review of the capability direction, then an operator pass with a
microphone and a provider activated - neither exists in this runtime - then
human browser review.

## IN PROGRESS

Nothing. Reading, Writing review and Speaking are integrated and reviewable.

## PENDING

Two things this runtime cannot exercise, both covered by contract tests and by
rendering rather than a live path: microphone paths need an operator pass with
real hardware; and with no provider activated, explanation, writing review,
registers and spoken coaching were driven against injected responses for the
rich case and the real endpoint for the unavailable case, so a provider run
should confirm the judgement vocabulary and the grounding rules behave as the
prompts ask.

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
- Speaking conversation architecture is unbuilt. The per-take envelope is
  honest and fully surfaced, and coaching is grounded, but nothing holds
  context across turns. The eventual agent needs a state model designed.
- Reading library breadth: without a provider the API answers every request
  with one built-in passage per language, which the surface labels honestly.
  Sourcing real public-domain and licensed material is a rights decision.
- Non-CI r8/r10/r11 matrices refer to deleted learner wrappers; admin gates to
  the missing operator host; r20 is frozen native. Do not weaken active tests
  or delete archived evidence to make those green.

## Baseline test evidence

Baselines 5827f6a and f966b28 both have 753 Python passes and the same 20
failures in test_governance_contract.py, test_media_ingestion.py and
test_media_learning.py (historical prose/source-format assertions). Not new
regressions; never claim an all-green suite.

## HUMAN GATES

Final browser review; production, data, migration, provider, credential,
OAuth/DNS/Cloudflare, billing and release operations; destructive history.
Ordinary local web iteration and recovery commits are authorized. Only the
human approves product direction.
