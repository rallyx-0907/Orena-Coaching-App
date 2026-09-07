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

D-046 and the product reset are committed; the shared media, transcript,
dictation, recording, provider and evidence primitives survive, and the learner
surfaces converge on static/orena. PostgreSQL APIs remain.

Golden Star foundation: shared page intro, intention navigation, response
composer, continuation shelf, draft status, progressReporter(). Tinted panels
carry their own ink in both themes, including secondary text on them - the
recurring defect is an ambient colour outranking a component's own pairing.
ORENA_WEB_EXTENSION_GUIDE.md records what a surface inherits.

## Learning capabilities

`ORENA_STATUS.md` carries what each capability does and refuses to claim. What
matters for recovery is where the invariants live:

- **Listening** `ui/encounter.js` - Follow opens no practice panel; a question
  pauses the voice; the end of an *excerpt* is what "reached the end" means.
- **Reading** `content/reading.js` - `readable()` is the gate every adapter
  ends at, carrying rights in the shape media uses; sessions come from
  `becoming_reading.py`, reused not rebuilt. `reading-library.js` admits a
  published text only with cleared rights, an https evidence URL, a
  verification date, edition and changes - never anything generated or
  imported. Comprehension is optional: a text without questions says so on the
  row and in the encounter, none are fabricated, and the count comes from the
  API so "none" differs from "not loaded".
- **Writing** `ui/writing-review.js` - renders the evaluator payload and
  `revision_delta()`, both of which the surface used to discard. A quote not in
  the learner's text is dropped; the stated task travels to the evaluator.
  `product/revision.js` refuses an ambiguous quotation rather than guessing
  which occurrence a learner meant.
- **Speaking** `ui/voice-response.js`, `product/conversation.js` - free
  expression has no reference line, so alignment is *not applicable*, not *not
  measured*; evaluator and persistence both refuse it without one. Measured
  evidence and coaching are separate panels making separate claims. A
  conversation is an ordered exchange the product owns; `conversation.py` is
  stateless and rejects a stale reply. The partner never coaches, so the
  learner's own turns carry that action - partner turns do not, and the
  handler refuses one.
- **Grammar and Vocabulary** `ui/expression.js`, `content/patterns.js` - both
  reach the shared explanation with their own context; each pattern carries a
  contrast reasoned in en/zh/vi. `product/grammar-shelf.js` extends the catalog
  without a second syllabus.
- **Continuation** `ui/patterns.js` - a thread is named by its shape, not only
  its intention: a conversation and a single take are both Speaking about the
  same situation and must not render alike.
- **One explanation system** `ui/understanding.js` - USAGE_JUDGEMENTS,
  JUDGEMENT_KEYS, the spoken-coaching schema and the authored contrasts are one
  vocabulary, checked against each other.

## Last verified batch

Local execution only; no CI claim.
- Twenty-six Node gates PASS. ESM graph: 44 modules. Both validators OK.
- Full Python in the app image: 787 passed / 20 failed (see below). The rich
  provider paths - registers, spoken coaching, generated reading, contextual
  explanation - run against an injected provider; their grounding rules were
  mutation-checked.
- Browser sweep light/dark at 1440/390 in EN and ZH: no overflow, no text
  below its contrast threshold, no pointer target under 24px.
- Journeys against the real server: Follow -> Dictation -> compare/persist ->
  look closer -> keep phrase -> Recall; follow to the end -> again / read
  through; reading request -> highlight -> explanation -> comprehension ->
  evidence in the passage; writing review -> revision comparison -> registers;
  speaking take -> evidence -> coaching -> develop as writing; grammar example
  and kept word -> explanation.

## Runtime / safety

Only operate isolated `orena-foundation-web` at 127.0.0.1:8011 and its own
`orena-foundation-postgres` / network; its database is temporary. Restart that
container after Python changes - the worktree is mounted, but uvicorn does not
reload. Do not operate production 8000, preview 8010, Cloudflare or volumes.
No provider keys activated: the AI surfaces return 503 honestly. Pronunciation
may be demo-labelled. No microphone acceptance has run; do not claim it.

Dependency-heavy tests run in the `ai-writing-coach:local` image (repo mounted
read-only, tmpfs /rundata, the four *_DB vars pointed there; CLAUDE.md has the
command). PERSISTENCE_BACKEND=sqlite is test-only, never a runtime fallback.
The learning language is session-scoped: switch it inside the page. Stage
explicit task files only; never docs/visual-references.

## NEXT EXACT TASK

GPT-6 review of the capability direction, then an operator pass with a
microphone and a live provider - neither exists here - then human browser
review.

## IN PROGRESS

Nothing. GPT-6's conversation ledger, published library, revision workbench and
grammar shelf are finished and committed. That run could not launch a browser,
which is how published texts reached the top of Reading with no comprehension
and no explanation of why; browser acceptance has since run in EN and ZH.

## PENDING

Microphone capture needs real hardware and cannot run here. The AI surfaces
have deterministic provider-injected coverage of their grounding rules; a live
provider run should still confirm the prompts produce what those rules
expect.

## BLOCKED

None.

## OPEN P0

None identified.

## OPEN P1

- Platform Admin lost its host when templates/index.html was removed. Its APIs
  and static/admin.js remain, but admin.js bails at its #page-admin guard, so
  it is inert. Preserve it without restoring the historical shell; production
  activation stays gated.
- Grammar breadth: three authored patterns per language, joined by stable
  Concept ID. Reference quality over breadth remains the scope choice.
- Conversation state is now implemented; cross-device conversation persistence
  and streaming/voice synthesis remain future work, not implied capabilities.
- Reading library breadth: the contract, rights fields and admission gate are
  in place, with two seed texts. Growing the catalogue is a rights decision per
  text, not an engineering one. Without a provider the API answers every
  request with one built-in passage per language, which the surface labels as
  such.
- Non-CI r8/r10/r11 matrices refer to deleted learner wrappers; admin gates to
  the missing operator host; r20 is frozen native. Do not weaken active tests
  for them.

## Baseline test evidence

The 20 Python failures are inherited: baselines 5827f6a and f966b28 show the
same ones in test_governance_contract.py, test_media_ingestion.py and
test_media_learning.py (historical prose/source-format assertions). Never claim
an all-green suite.

## HUMAN GATES

Final browser review; production, data, migration, provider, credential,
OAuth/DNS/Cloudflare, billing and release operations; destructive history.
Local web iteration and checkpoint commits are authorized. Only the human
approves product direction.
