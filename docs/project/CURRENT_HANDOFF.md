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

`ORENA_STATUS.md` says what each capability does and refuses to claim. What
recovery needs is where the invariants live:

- **Listening** `ui/encounter.js` - Follow opens no practice panel; a question
  pauses the voice; "the end" is the end of the excerpt, not the asset.
- **Reading** `content/reading.js` - `readable()` is the gate every adapter
  ends at; `reading-library.js` admits a published text only with cleared
  rights, an https evidence URL, a verification date, edition and changes.
  Comprehension is optional and its absence is stated, never fabricated.
- **Writing** `ui/writing-review.js` - renders the evaluator payload and
  `revision_delta()`. A quote not in the learner's text is dropped; the stated
  task reaches the evaluator.
- **Speaking** `product/conversation.js` - free expression has no reference
  line, so alignment is *not applicable*, not *not measured*; evaluator and
  persistence both refuse it without one. Measured evidence and coaching stay
  separate panels, and only the learner's own turns carry coaching.
- **Grammar and Vocabulary** `ui/expression.js`, `content/patterns.js` - both
  reach the shared explanation with their own context; each pattern carries a
  contrast reasoned in en/zh/vi; `grammar-shelf.js` extends the catalog.
- **Kept language** `product/memory.js`, `keptProvenance()` - the library has
  no column for where a word was met, so origin, place, sentence and reason
  live beside it in device memory, written only after the account save.
- **Recall** `product/recall.js` - the question follows the phrase's history;
  every occurrence is withheld until reveal. Seeing a card is not recall.
- **Continuation** `ui/patterns.js` - a thread is named by its shape, not only
  its intention; a conversation reports how far it got.
- **Presentation** - workspace, brand and hint invariants live in
  `ORENA_WEB_EXTENSION_GUIDE.md`, where a surface reads what it inherits.
- **One explanation system** `ui/understanding.js` - USAGE_JUDGEMENTS,
  JUDGEMENT_KEYS, spoken-coaching schema and authored contrasts are one
  vocabulary. Every follow-up keeps its selection and passage.

## Last verified batch

Local execution only; no CI claim.
- Thirty Node gates plus the reference gate PASS. ESM graph: 48 modules.
  Both validators OK.
- Full Python in the app image: 790 passed / 20 failed (see below). The rich
  provider paths - registers, spoken coaching, generated reading, contextual
  explanation - run against an injected provider; their grounding rules were
  mutation-checked.
- Browser at 390/1440/1920 in EN and ZH, light/dark on representative rooms:
  no overflow, no pointer target under 24px, no dead controls.
- Journeys driven in the browser: see the ledger's "Functional core", which
  records what is real, what is provider-held, and the evidence for each.

## Runtime / safety

Only operate isolated `orena-foundation-web` at 127.0.0.1:8011 and its own
`orena-foundation-postgres` / network; its database is temporary. Restart it
after Python changes - the worktree is mounted, uvicorn does not reload. Do not
operate production 8000, preview 8010, Cloudflare or volumes. No provider keys:
the AI surfaces return 503 honestly. Pronunciation may be demo-labelled. No
microphone acceptance has run; do not claim it.

Dependency-heavy tests: `ai-writing-coach:local`, read-only repo, tmpfs /rundata,
four *_DB vars there; command in AGENTS.md. SQLite is test-only, never runtime.
Switch learning language in-page. Stage task files only, never visual references.

## NEXT EXACT TASK

COMPLETE THE ORENA GOLDEN STAR REFERENCE IMPLEMENTATION, with role ownership
explicit: Codex owns system architecture; Opus implements feature detail.
Read `docs/product/ORENA_REFERENCE_ARCHITECTURE.md` for the blueprint, shared
context/outcome boundaries and ordered implementation packages. Proposed
interfaces are not deployed facts or human acceptance. Preserve the restored
eleven destinations; Collection remains deferred.

Codex next: define the account/evidence architecture package and cross-domain
contracts identified in section 8, without schema/runtime changes. Opus next:
finish the Encounter WIP, then implement reference compositions and canonical
journeys against the blueprint. Provider/microphone and final human visual
acceptance remain held; neither a small feature fix nor a review replaces the
Golden Star mission.

## IN PROGRESS

Golden Star is IMPLEMENTING. The three earlier capability findings are closed.
Opus's `8af067f` WIP added word exploration in Encounter. Codex's follow-up is
partially checked and explicitly handed back to Opus, not accepted: see the
WIP section in `GOLDEN_STAR_COMPLETION.md`. Codex has stopped feature detail.

## PENDING

Microphone hardware and live-provider validation remain pending. Deterministic
provider-injected coverage does not establish live prompt quality.

## BLOCKED

None.

## OPEN P0

None identified.

## OPEN P1

- Platform Admin lost its host when templates/index.html was removed; its APIs
  and static/admin.js remain but admin.js bails at its #page-admin guard, so it
  is inert. Preserve it without restoring the historical shell.
- Grammar breadth: authored patterns joined by stable Concept ID, extended by
  `grammar-shelf.js` rather than a second syllabus.
- Cross-device continuity: device memory by design; the account architecture is
  a reserved hold (AGENTS.md, "Architecture holds").
- Reading library breadth: contract, rights fields and admission gate are in
  place with two seed texts. Growing the catalogue is a rights decision per
  text. Without a provider the API answers every request with one built-in
  passage per language, labelled as such.
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
