# Grammar contract and renderer integration checkpoint

MILESTONE=S5 prerequisites; STATUS=IMPLEMENTING, not learner REVIEWABLE.
COMMIT=0d5732c7634ae06f0072a9f7c928589f1cc44b1f
BASE=81150167a53bf0244a31a99cc051468da26bc269
Contract integration=32234f23a91f3596dfe25f97b9b803f2c0f97826
Fixture integration=4d93d8309052cb8d7265f5734ce66d4427c39163
WEB_URL=http://127.0.0.1:8021/next#/grammar
WEB_ROUTE=grammar, grammar/:id
HOW_TO_REACH_IT=Practice Hub -> Grammar; existing empty state remains.
EN_PARITY=10 upstream drafts exercise real models; ZH_PARITY=3 upstream drafts,
canonical zh-Hans locale/script recognized. CROSS_CAPABILITY_STATUS=Existing
Grammar seam retained; no R5 fallback, source job, learner store or new model.

## Scope and decisions

D-111.4 authorized integration of PR67/68 after independent review/gates.
Git fetched exact PR heads: 6fef39b and 2b7657c. GitHub API read returned401;
no remote merge or PR-state claim. Integration is local codex/work only.
Only those bounded branches were integrated, not the large upstream pipeline.

MEMORY CONTRADICTION
Conflicting implementation: PR67 GCC section9 retained aliases on all split pieces.
Governing product rule: accepted D-106 puts alias only on the primary split point.
Likely stale side: contract wording. Human decision required: none; D-106 settled it.
Independent review initially REQUEST CHANGES P1; bounded correction implements
primary-only aliases, provenance-only secondaries, explicit r5_map dispositions,
all-aliased completion for merged points and maps independent of publish state.
Reviewer rechecked and closed P1 before the integration commit.

Real regression tests failed before adapter fixes: zh/zh-Hans guidance returned
English despite an available authored Chinese value; a canonical multi-L1 array
selected the first mistake rather than the matching learner-specific one.
Renderer now maps the authored zh-Hans key locally, labels Chinese material zh,
and selects L1 entries by array membership, retaining scalar compatibility.
The same Grammar seam serves Library and Concept, with no UI composition changes.

The thirteen imported files are test fixtures, all draft_ai. Their manifest says
sample=true and approved=false. Tests cover all13 model projections and refusal
by grammarPoint/grammarCatalog. No approved learner content was generated or
published. Missing EN explanations in a draft never fall back silently to VI.

## Verification

Local execution: seven commands passed, zero failed/skipped:

- node scripts/test_orena_screen_grammar.mjs (all13 fixtures and draft rejection)
- node scripts/test_orena_language_layers.mjs
- node scripts/test_orena_grammar.mjs
- node scripts/test_orena_shell.mjs
- node scripts/test_orena_listening_entries.mjs
- node scripts/test_orena_listening_questions.mjs
- node --experimental-vm-modules scripts/validate_browser_esm_graph.mjs (339 modules)

No new Python/backend execution path changed; no full Python/CI run claimed.
Project-memory validation: PASS. Architecture validation: PASS1.4.0.
git diff --check: PASS. No fresh browser lesson is claimed: published
content and Grammar API still do not exist. The adapters are model-tested,
not visually accepted. Fidelity gate remains OPEN; frames44/47 retained without
geometry/token/art changes. No new artwork, physical-phone or theme QA claimed.

Exact implementation files: docs/project/GRAMMAR_CONTENT_CONTRACT.md;
scripts/test_orena_screen_grammar.mjs; static/orena/product/grammar-source.js;
static/orena/screens/grammar-concept/model.js; tests/fixtures/grammar_content_samples/
README.md, functions.json, index.json and points/{en.articles.a_an,
en.articles.the,en.comparatives,en.conditional_first,en.past_simple,
en.plural_nouns.regular,en.present_continuous.now,en.present_perfect.experience,
en.present_simple.third_person_s,en.there_is_are,zh.ba_construction,
zh.guo_experience,zh.le_completion}.json.

Protected area: canonical Grammar contract/renderer deliberately corrected for
accepted content shape. No R5 IDs rewritten or historical progress deleted.
Persistence/schema/runtime/version/deployment changes: NONE. No Docker operation
other than read-only validators. Native untouched. No paid provider call.
PROJECT_STATE.md unchanged; CURRENT_PRODUCT_STATE.yaml, CURRENT_HANDOFF.md and
ORENA_STATUS.md updated. New Decision Log entry not required: implements D-106/111.
Human-owned DESIGN_CONTRACT.md stays modified and unstaged; own documentation
checkpoint contains this report/plan and the three current-state documents only.

Independent reviewer /root/grammar_contract_review: APPROVE, base8115016 through
exact commit0d5732c7634ae06f0072a9f7c928589f1cc44b1f; zeroP0/P1, two nonblockingP2.
PR68 APPROVE; PR67 APPROVE after D-106 delta. Reviewer read the exact diff and
did not rerun tests/Docker, relying on the reported local evidence.
P2 follow-ups: grammar-source's contractText comment still describes the old locale
rules; fixture point-level schema_version is not listed in GCC metadata while
the Store proposal places it in the manifest. Reconcile before closed-schema
Store intake; do not promote fixtures to bypass the discrepancy.

## Next exact work

Prepare/review/rehearse the approved Grammar Store additive migration before
runtime application, then Store/importer/Admin API and publication; switch the
existing learner seam only after approved EN/ZH batches are in the store.
The proposal's suggested0024 identifier collides with the already proposed media
metadata0024; select/review a coherent chain before promotion. No migration was
written, moved to versions or applied in this batch. The existing proposed README
claim of no open proposal is stale relative to its media migration file; neither
establishes a deployed schema. Runtime remains0023.
WHAT_THE_HUMAN_SHOULD_REVIEW=No new lesson yet; this checkpoint clears contract
and renderer prerequisites, not basic Grammar capability completion.
