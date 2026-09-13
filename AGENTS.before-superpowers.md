# ORENA — AGENT CONTRACT

This repository contains Orena's implementation, verified technical state, product direction, and historical decisions.

Agents must distinguish between:

1. **Product intent** — what Orena should become.
2. **Technical truth** — what currently exists and is verified.
3. **Engineering constraints** — what must remain safe and stable.

Do not derive all three from the same source.

---

# 1. Product authority

For learner-facing product, UX, UI, content, navigation, learning-flow, visual direction, AI behavior, capability integration, progression, or learner-experience decisions, the authoritative source is:

`docs/product/ORENA_PRODUCT_CONSTITUTION.md`

Product-intent precedence:

1. explicit current human instruction;
2. `docs/product/ORENA_PRODUCT_CONSTITUTION.md`;
3. `docs/product/ORENA_CONTENT_ARCHITECTURE.md` for content, discovery, import, and learner-content decisions;
4. `assets/brand/orena/` for approved brand, mascot, logo, illustration, and generated brand-art decisions;
5. explicitly approved current experience / feature specification;
6. `docs/product/ORENA_STATUS.md`;
7. current technical constraints;
8. existing implementation;
9. historical product assumptions and documentation.

Existing code proves what currently exists.

It does not automatically define what Orena should become.

Do not duplicate the Product Constitution inside this file.

---

# 2. Technical truth

For questions about what is actually implemented, persisted, tested, deployed, or operationally verified, use:

1. repository implementation, tests, and verified Git state;
2. `docs/project/PROJECT_STATE.md`;
3. `docs/project/CURRENT_HANDOFF.md`;
4. `docs/project/ARCHITECTURE_INVARIANTS.md`;
5. `docs/project/DECISION_LOG.md`;
6. `docs/project/ROADMAP.md`;
7. historical documentation.

Product intent must never be used to pretend functionality already exists.

Existing implementation must never override current product intent merely because it is older.

A difference between current implementation and the Product Constitution is normally an implementation gap, not a reason to preserve old UX.

A material contradiction between technical sources is different: report it and do not silently choose the convenient source.

---

# 3. Required reading

Before substantial learner-facing work, read:

1. `AGENTS.md`
2. `docs/product/ORENA_PRODUCT_CONSTITUTION.md`
3. `docs/product/ORENA_CONTENT_ARCHITECTURE.md`
4. `docs/product/ORENA_STATUS.md`
5. `docs/project/PROJECT_STATE.md`
6. `docs/project/ARCHITECTURE_INVARIANTS.md`
7. `docs/project/CURRENT_HANDOFF.md`
8. `docs/project/DOMAIN_BOUNDARIES.md`
9. the relevant current feature / experience specification
10. the relevant implementation and tests

For learner-facing visual, brand, logo, mascot, illustration, app-icon,
empty-state, onboarding-art, or generated brand imagery work, additionally read:

11. `assets/brand/orena/README.md`
12. `assets/brand/orena/BRAND_MASCOT_GUIDE.md`
13. `assets/brand/orena/AGENT_GENERATION_CONTRACT.md`
14. `assets/brand/orena/references/00_MASTER_REFERENCE_APPROVED.png`

The approved master brand reference is the visual authority.

Do not redesign the Orena mascot from memory or invent a new brand identity when
approved references exist.

Reuse an existing action, expression, or scene where appropriate before
generating new artwork.

Any newly generated mascot or brand artwork must preserve the approved
character identity, proportions, palette, facial construction, tail language,
and illustration style.

---

# 4. Branch and implementation independence

`main` is the stable and verified branch.

Experimental or active development must occur on the explicitly assigned development branch.

For the current Codex lane, use:

`codex/work`

Do not automatically create another branch or worktree when `codex/work` is the assigned lane.

The Codex implementation is intentionally independent from the Claude comparison implementation.

Do not inspect, copy, imitate, merge, or cherry-pick learner-facing implementation from the Claude comparison branch unless explicitly instructed by the human.

The branches may share:

- Product Constitution;
- requirements;
- acceptance criteria;
- language-learning rules;
- engineering constraints.

Implementation must remain independent.

---

# 5. Before making changes

Before meaningful work:

1. inspect `git status`;
2. verify current branch and HEAD;
3. inspect relevant implementation;
4. inspect relevant tests;
5. identify the current product milestone where applicable;
6. identify the verified technical baseline;
7. run appropriate baseline validation when feasible.

Do not restart already completed work from scratch.

Do not recreate stable subsystems merely because another implementation style is possible.

Preserve useful technical foundations when they continue to support the current Product Constitution.

---

# 6. Development workflow

Technical work:

INSPECT
→ PLAN
→ IMPLEMENT
→ RUN
→ VERIFY
→ REGRESSION CHECK
→ CHECKPOINT

Meaningful learner-facing work:

INSPECT
→ DEFINE THE EXPERIENCE
→ IMPLEMENT ONE COHERENT VERTICAL SLICE
→ RUN
→ VERIFY FUNCTION
→ REGRESSION CHECK
→ MAKE WEB-REVIEWABLE
→ UPDATE PRODUCT STATUS
→ HUMAN REVIEW CHECKPOINT

Do not disappear into several major learner-facing milestones before showing a reviewable result.

Prefer coherent vertical slices over large invisible batches.

---

# 7. Web review gate

Tests are necessary but not sufficient for meaningful learner-facing work.

A learner-facing milestone becomes `REVIEWABLE` only when the product owner can open the application in a browser and experience the implementation.

Provide:

WEB_URL=
WEB_ROUTE=
HOW_TO_REACH_IT=
COMMIT=
EN_PARITY=
ZH_PARITY=
TESTS=

Do not call learner-facing work complete merely because it exists in:

- backend code;
- an API;
- tests;
- an isolated component;
- a static mockup;
- an unreachable route;
- mobile-only implementation.

After a meaningful milestone reaches `REVIEWABLE`, present it to the human before beginning another major learner-facing milestone.

---

# 8. Product review states

Use:

`PLANNED`

Identified but not yet implemented.

`IMPLEMENTING`

Implementation exists or is underway but is not ready for human browser review.

`REVIEWABLE`

Functional, validated, reachable through the web product, and ready for human review.

`APPROVED`

The human product owner has reviewed and accepted the product direction.

`BLOCKED`

A genuine blocker prevents the next meaningful checkpoint.

Agents may set:

- PLANNED
- IMPLEMENTING
- REVIEWABLE
- BLOCKED

Only the human may establish product approval.

---

# 9. Multilingual contract

English and Chinese are first-class Orena learning languages.

Shared learner-facing behavior should use shared language-neutral contracts.

Use language adapters only for genuine linguistic differences.

Do not implement a shared product feature fully for English and postpone equivalent Chinese capability unless explicitly authorized.

Product parity means equivalent capability and quality, not identical linguistic implementation.

Detailed product and learning principles belong in the Product Constitution rather than being duplicated here.

---

# 10. Regression discipline

A previously fixed problem must not silently return.

Check relevant areas including:

- schema and type correctness;
- EN/ZH parity;
- terminology;
- navigation;
- learner state;
- state restoration;
- responsive layout;
- accessibility;
- light/dark behavior;
- contextual language feedback;
- natural translation;
- cross-capability handoffs;
- previous regression fixes.

If a new change breaks stable behavior:

1. identify the latest relevant change;
2. isolate the root cause;
3. roll back that change when genuinely required;
4. implement the minimum root-cause correction;
5. verify the original behavior;
6. run regression checks;
7. only then continue.

Never weaken validators merely to make a failing batch pass.

---

# 11. No hardcoding

Do not hardcode around:

- failures;
- tests;
- users;
- languages;
- IDs;
- environment-specific paths;
- migration records;
- API responses;
- temporary UI state.

Prefer:

- explicit contracts;
- configuration;
- repository abstractions;
- deterministic mappings;
- reusable primitives;
- shared abstractions;
- root-cause fixes.

---

# 12. Protected technical contracts

Stable technical infrastructure and reviewed contracts are protected against incidental modification.

Protected does not mean permanently frozen learner-facing presentation.

A deliberate product task may evolve existing presentation when required by the Product Constitution.

Protected technical areas include where applicable:

- persistence contracts;
- learner-data ownership;
- stable Grammar Concept IDs and source contracts;
- canonical Media Learning contracts;
- shared language-neutral APIs;
- reusable responsive/layout primitives;
- accessibility behavior;
- production infrastructure;
- rollback evidence.

When modifying a protected technical area:

1. state why;
2. make the minimum coherent change;
3. validate it immediately;
4. check dependent flows.

Do not modify frontend/layout incidentally as part of unrelated backend work.

Reuse shared primitives before creating page-specific infrastructure.

Avoid one-off visual or state-management hacks that bypass established reusable contracts.

`docs/visual-references/**` must not be deleted as cleanup or staged unless explicitly within scope.

---

# 13. Persistence safety

PostgreSQL is the authoritative runtime.

SQLite is frozen rollback/archive only.

Mandatory:

- no dual-write;
- no reverse sync from PostgreSQL to SQLite;
- no silent SQLite fallback;
- no startup auto-import;
- no destructive production-data mutation without authorization;
- no deleting PostgreSQL volumes as cleanup;
- no deleting SQLite archives as cleanup;
- no blindly recreating persistent data;
- no unapproved production schema migration;
- no billing or subscription enforcement outside explicit scope.

Do not automatically upgrade a non-empty PostgreSQL runtime.

Any already-verified empty-database bootstrap behavior documented in `PROJECT_STATE.md` may remain unless an accepted architecture decision changes it.

Historical migration tooling may remain for tests, archive inspection, rollback evidence, or documented migration history.

Its existence does not change persistence authority.

---

# 14. Git safety

Forbidden unless explicitly approved:

- `git clean -fd`;
- arbitrary `git add -A`;
- destructive `git reset --hard`;
- force-push to stable branches;
- automatic merge to `main`;
- deleting unrelated untracked files;
- rewriting verified history.

Stage only files belonging to the current coherent change.

Do not stage `docs/visual-references/**` unless the current task explicitly includes them.

Leave checkpoints reviewable.

---

# 15. Docker and shared runtime safety

Never use:

`docker compose down -v`

for normal development or operations.

Do not delete persistent volumes as cleanup.

Before operating a shared runtime:

- confirm another development lane is not actively using the same runtime or persistent data;
- preserve PostgreSQL data;
- preserve rollback/archive data;
- avoid changing Cloudflare, DNS, OAuth, secrets, or production runtime behavior unless explicitly scoped.

An existing Docker warning is not automatically an application failure.

---

# 16. Secrets

Never print, commit, or document secret values, including:

- API keys;
- database passwords;
- credential-bearing URLs;
- OAuth client secrets;
- Cloudflare tunnel tokens;
- session secrets;
- authorization headers;
- signing credentials.

Environment variable names may be documented.

Secret values remain in approved operator-controlled stores.

---

# 17. Testing and execution environment

Use the application's actual dependency/runtime environment for tests requiring project dependencies.

When Docker provides the application dependency environment, run dependency-heavy validators in the appropriate application container.

Distinguish:

- source failure;
- packaging failure;
- execution-environment failure;
- dependency failure;
- data-compatibility failure;
- real application regression.

Do not patch application logic merely to hide environment problems.

Do not claim CI PASS without actual CI evidence.

Label local test results as local execution.

Before treating a direct Python script failure as an application regression, check import-root and `sys.path` behavior and prefer module execution where appropriate.

---

# 18. Web and mobile

Web and native/mobile are product surfaces over the same Orena learning architecture.

They share:

- authoritative backend/domain contracts;
- learner model;
- curriculum ownership;
- learning evidence;
- language behavior;
- core product philosophy.

Product parity does not mean pixel-identical implementation.

Platform-specific UX may differ when appropriate.

Meaningful product direction must remain observable to the product owner through a browser-reviewable surface.

Do not let major learner-facing direction develop invisibly for long periods only inside native code.

---

# 19. Repository context updates

`docs/product/ORENA_PRODUCT_CONSTITUTION.md`

Change only when the human accepts a durable Orena product-philosophy change.

`docs/product/ORENA_STATUS.md`

Update when active product milestone, review state, browser route, human approval, or next reviewable slice changes.

`docs/project/PROJECT_STATE.md`

Update only after implementation/runtime facts are verified.

Its application/runtime baseline SHA is a verified-state marker, not merely the latest Git HEAD.

`docs/project/CURRENT_HANDOFF.md`

Update when active engineering stage, ownership, blockers, human gates, or next checkpoint materially change.

`docs/project/DECISION_LOG.md`

Append when a durable product or architecture decision changes.

Never silently rewrite past decisions.

`docs/project/ARCHITECTURE_INVARIANTS.md`

Change only when an explicit accepted architecture decision supersedes an invariant.

`docs/project/ROADMAP.md`

Change only for approved roadmap or status transitions.

---

# 20. Human gates

Stop for explicit human authorization before:

- production PostgreSQL/data mutation;
- production runtime activation or cutover;
- unapproved schema/Alembic migration;
- Cloudflare or DNS changes;
- Google OAuth configuration changes;
- secret/credential changes;
- paid-provider activation;
- billing, quota, or subscription enforcement;
- destructive Git operations;
- persistent-volume deletion;
- public product release;
- production mobile/store signing or release;
- rollback-path removal;
- unresolved P0;
- repeated unresolved P1 findings requiring broader redesign;
- ambiguous irreversible architecture decisions.

Normal learner-facing product iteration inside the assigned development lane does not require a stop merely because current UI differs from the Product Constitution.

---

# 21. Completion report

For technical work report:

- files changed and why;
- tests/validators actually run;
- passed / failed / skipped;
- remaining blockers;
- protected technical areas changed;
- persistence/runtime impact;
- deployment impact;
- application/frontend version impact;
- `PROJECT_STATE.md` impact;
- `CURRENT_HANDOFF.md` impact;
- whether a Decision Log entry was required;
- Git status;
- commit SHA.

For meaningful learner-facing work additionally report:

MILESTONE=
STATUS=
COMMIT=

WEB_URL=
WEB_ROUTE=
HOW_TO_REACH_IT=

EN_PARITY=
ZH_PARITY=
CROSS_CAPABILITY_STATUS=
TESTS=

WHAT_CHANGED=
WHAT_THE_HUMAN_SHOULD_REVIEW=

Never merge to `main` automatically.

Never declare human product approval automatically.

---

# 22. Repository memory principle

Essential Orena knowledge must live in the repository.

Do not rely on:

- previous Codex session history;
- Claude conversation history;
- ChatGPT memory;
- one developer remembering an old decision.

A new competent agent should be able to enter the repository and determine:

- Orena's current product direction;
- current technical reality;
- active milestone;
- next human-review checkpoint;
- engineering constraints that must remain safe.
