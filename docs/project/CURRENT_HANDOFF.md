# Current Handoff

## Governance

Purpose: compact recovery context. Change when the active stage or verified
facts change. Do not store secrets or unverified claims. Authority: current
human instruction, Orena Constitution, Content Architecture, approved brand,
D-046. No human approval or production readiness is implied.

## Current branch / lane

`codex/work`, Orena WEB Golden Star plus real learning capabilities. Do not
restore the deleted learner product. Native mobile / Expo / React Native is
frozen. Human instruction authorizes full-stack WEB work on the capabilities
themselves, not only on the foundation.

## DONE

D-046 and the product reset are committed. Shared media, transcript,
dictation, recording, provider and evidence primitives survive. Discovery,
Practice, learner imports, continuation, expression and saved language converge
on static/orena. PostgreSQL APIs remain.

Golden Star foundation: shared page intro, intention navigation, response
composer, continuation shelf, draft status, progressReporter(). Tinted panels
carry their own ink in both themes (--sage/coral/night/sun-surface with paired
--on-*), including secondary text on them - the recurring defect is an ambient
colour outranking a component's own pairing.
ORENA_WEB_EXTENSION_GUIDE.md records what a surface inherits.

## Learning capabilities

- **Pure Listening** is complete on its own terms. Follow opens no practice
  panel; asking what a line means pauses the voice and says so; reaching the
  end is recognised - not scored, opening no exercise - and offers hearing it
  again or reading it through; the transcript can show every line's meaning
  from translations the lesson already ships. It tracks the spoken word where
  an asset ships word timing.
- **Dictation** hints show structure and earned words as anchors, stopping one
  character short of any word. Hint state is per visit, not evidence.
- **Reading** is its own intention beside Follow. It adapts the real session
  envelope (`becoming_reading.py`, reused not rebuilt), labels generated versus
  built-in provenance, and offers optional comprehension whose every result
  names the words in the passage that settle it. `content/reading.js` declares
  the readable contract; `readable()` is the gate every adapter ends at, with
  rights in the same shape media uses - a book needs an adapter, not a
  redesign.
- **Writing** renders the evaluator payload the surface used to discard:
  dimensions, CEFR, strengths quoted from the learner, issues with why/how/
  priority; a quote not in their text is dropped.
  `revision_delta()` was likewise reduced to one number - the review now shows
  which problems went, stayed, arrived and were reworked, with movement on the
  dimensions that moved. The learner can state what they are writing, which
  travels as the evaluator's writing task so domain choices are not marked as
  mistakes. Register exploration (`POST /api/dictionary/registers`) shows one
  meaning across five registers with the signals placing each and when each is
  wrong - not a rewrite button, no version presented as correct.
- **Speaking** is its own experience: situation or the learner's own prompt,
  record, transcript, evidence, guidance, retry. Free expression has no
  reference line, so alignment is *not applicable* rather than *not measured*,
  and evaluator and persistence both refuse alignment without one. Measured
  evidence (ui/voice-evidence.js) and coaching (ui/spoken-coaching.js,
  `POST /api/dictionary/spoken-response`) are separate panels making separate
  claims; coaching reads the transcript, never the audio, quotes only words the
  learner said, and does not score.
- **One contextual explanation system** serves every capability
  (ui/understanding.js), naming which of six things is wrong rather than saying
  "wrong". USAGE_JUDGEMENTS, JUDGEMENT_KEYS and the spoken-coaching schema are
  one vocabulary, checked against each other.

## Last verified batch

Local execution only; no CI claim.
- Twenty-two Node gates PASS. ESM graph: 37 modules. Both validators OK.
- Full Python in the app image: 758 passed / 20 failed (see below).
- Browser sweep light/dark at 1440/390 in EN and ZH: no overflow, no text
  below its contrast threshold, no pointer target under 24px.
- Journeys against the real server: Follow -> Dictation -> compare/persist ->
  look closer -> keep phrase -> Recall; follow to the end -> again / read
  through; reading request -> highlight -> explanation -> comprehension ->
  evidence in the passage; writing review -> revision comparison -> registers;
  speaking take -> evidence -> coaching -> develop as writing.

## Runtime / safety

Only operate isolated `orena-foundation-web` at 127.0.0.1:8011 and its own
`orena-foundation-postgres` / network; its database is temporary. Restart that
container after Python changes - the worktree is mounted, but uvicorn does not
reload. Do not operate production 8000, preview 8010, Cloudflare or volumes.
No provider keys activated: writing review, explanation, registers and spoken
coaching all return 503 honestly. Pronunciation may be demo-labelled. No
microphone acceptance has run; do not claim it.

Dependency-heavy tests run in the `ai-writing-coach:local` image (repo mounted
read-only, tmpfs /rundata, the four *_DB vars pointed there; CLAUDE.md has the
command). PERSISTENCE_BACKEND=sqlite is test-only, never a runtime fallback.
The learning language is session-scoped, so switch it inside the page. Stage
explicit task files only; never docs/visual-references.

## NEXT EXACT TASK

GPT-6 review of the capability direction, then an operator pass with a
microphone and a provider activated - neither exists in this runtime - then
human browser review.

## IN PROGRESS

Nothing. Listening, Reading, Writing and Speaking are integrated and
reviewable.

## PENDING

The two paths this runtime cannot exercise, both covered by contract tests and
by rendering rather than a live call: microphone capture needs real hardware,
and the AI surfaces were driven against injected responses for the rich case
and the real endpoint for the unavailable one. A provider run should confirm
the judgement vocabulary and grounding rules behave as the prompts ask.

## BLOCKED

None.

## OPEN P0

None identified.

## OPEN P1

- Platform Admin lost its host when templates/index.html was removed. Its APIs
  and static/admin.js remain, but admin.js bails at its #page-admin guard, so
  it is inert. Preserve it without restoring the historical learner shell;
  production activation stays gated.
- Grammar has three authored patterns per language joined by stable Concept ID.
  Scope prefers reference quality over breadth.
- Speaking conversation architecture is unbuilt. The per-take envelope is
  honest and coaching is grounded, but nothing holds context across turns. The
  eventual agent needs a state model designed.
- Reading library breadth: the contract and rights fields are in place, so a
  new source needs an adapter. No catalog was added - sourcing real
  public-domain and licensed material is a rights decision. Without a provider
  the API answers every request with one built-in passage per language, which
  the surface labels as such.
- Non-CI r8/r10/r11 matrices refer to deleted learner wrappers; admin gates to
  the missing operator host; r20 is frozen native. Do not weaken active tests
  or delete archived evidence for them.

## Baseline test evidence

The 20 Python failures are inherited: baselines 5827f6a and f966b28 show the
same ones in test_governance_contract.py, test_media_ingestion.py and
test_media_learning.py (historical prose/source-format assertions). Not new
regressions; never claim an all-green suite.

## HUMAN GATES

Final browser review; production, data, migration, provider, credential,
OAuth/DNS/Cloudflare, billing and release operations; destructive history.
Ordinary local web iteration and checkpoint commits are authorized. Only the
human approves product direction.
