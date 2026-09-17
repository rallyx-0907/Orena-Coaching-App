# ORENA — AGENT CONTRACT

This repository contains Orena's implementation, verified technical state,
product direction, and historical decisions.

Agents must distinguish between:

1. **Product intent** — what Orena should become.
2. **Technical truth** — what currently exists and is verified.
3. **Engineering constraints** — what must remain safe and stable.

Do not derive all three from the same source.

**This file is a router, not a second copy of the repository's governance.** It
points at the documents that own each domain and holds only the rules that live
nowhere else. Where this file and a linked authority disagree about that
authority's own domain, the linked authority wins and the disagreement is a
defect to report — not a choice to make quietly.

---

# 1. Authority

`docs/project/PROJECT_MEMORY.md` owns the precedence model. It defines the
product-intent chain, the separate implementation-fact chain, and the
`MEMORY CONTRADICTION` report format. Read it rather than reasoning from this
file's summary of it.

In short, and without superseding it:

- **Product intent** — explicit current human instruction, then
  `docs/product/ORENA_PRODUCT_CONSTITUTION.md`.
- **Technical truth** — actual code, tests, runtime evidence and verified Git
  state, before any document.

Existing code proves what currently exists. It does not define what Orena
should become. A gap between implementation and the Product Constitution is
normally an implementation gap, not a reason to preserve old UX. A material
contradiction *between technical sources* is different: report it, and do not
silently pick the convenient one.

Domain owners:

| Domain | Authority |
| --- | --- |
| Learner-facing product, UX, learning flow, AI behaviour | `docs/product/ORENA_PRODUCT_CONSTITUTION.md` |
| Content, discovery, import, learner content | `docs/product/ORENA_CONTENT_ARCHITECTURE.md` |
| Durable learner-facing design rules, web and native | `docs/project/DESIGN_CONTRACT.md` |
| What a web surface inherits and owes | `docs/product/ORENA_WEB_EXTENSION_GUIDE.md` |
| Brand, mascot, illustration, generated art | `assets/brand/orena/` |
| Current capability behaviour and review state | `docs/product/ORENA_STATUS.md` |
| Invariants that must not drift | `docs/project/ARCHITECTURE_INVARIANTS.md` |
| Current execution state, lane, blockers, gates | `docs/project/CURRENT_HANDOFF.md` |
| Retired and forbidden directions | `docs/project/LEGACY_TOMBSTONES.md` |
| Durable decisions (append-only) | `docs/project/DECISION_LOG.md` |
| Review verdicts, severity, completion evidence | `docs/project/REVIEW_POLICY.md` |
| How Orena is validated | `.github/workflows/ci.yml` and `scripts/`, summarised in §9 |

Do not duplicate any of these inside this file.

Harness files — `CLAUDE.md` for Claude Code, and any future equivalent — carry
convenience commands and harness-specific tooling only. They are never
authoritative for anything in the table above, and no agent should need to read
another harness's file to work in this repository.

## Learner-facing UI work: mandatory reads

Before any learner-facing product, UX, UI, visual, content-discovery, Library,
Reading, Listening, Speaking, Writing, Practice, Vocabulary / My Language or
navigation task, read and obey:

- `docs/product/ORENA_PRODUCT_CONSTITUTION.md`;
- `docs/product/ORENA_CONTENT_ARCHITECTURE.md`;
- `docs/project/DESIGN_CONTRACT.md`, including its acceptance gates;
- `assets/brand/orena/` for anything visual — it is the Art Bible and the only
  art-direction authority;
- the current verified state the cold start in §2 already requires.

Precedence for these tasks: explicit current human instruction → the Product
Constitution → the Content Architecture → the Design Contract → current
verified product state → the task brief → existing implementation. Legacy UI
and screenshots are evidence of what was built, never design authority. If a
requested change would violate a contract, stop and surface the conflict before
implementing it.

The rules themselves live in those files and are not repeated here.

## Architecture review authority

Architecture authority is **role-based, not model-name-based**. The role is
what carries the authority; which model happens to fill it does not.

- **GPT-6/Codex is the preferred Principal Architect.**
- When unavailable, a sufficiently capable independent model may act as
  **Delegated Architecture Reviewer**, after reading current Git HEAD, the
  architecture contracts and the handoff.
- Reviewer identity, reviewed commit and outcome **must be recorded in Git**.
- **An implementer may not self-approve its own high-risk architecture
  changes.**
- Schema/migration, payment/entitlement, account deletion and destructive
  lifecycle changes **require independent architecture review**.
- Existing human authorization gates remain unchanged. Architecture review is
  not product approval and is not activation authorization.

---

# 2. Cold start

Chat history is not project state, from any agent or any session. Start every
implementation or review session from the repository.

"Continue Orena", or any resumption, means **the bounded restore** — two steps,
in this order:

**1. Verify live Git state.** Never skipped, never taken from a document:

```text
git branch --show-current
git rev-parse HEAD
git status --short
git log -5 --oneline
```

**2. Read `PROJECT_MEMORY.md`'s canonical sequence, and only that.** It is
deliberately bounded: `PROJECT_STATE.md`, `ARCHITECTURE_INVARIANTS.md`,
`DOMAIN_BOUNDARIES.md` and archived handoffs are supporting evidence consulted
when relevant, not default startup context.

That behaviour is the contract. A harness may offer a shortcut that performs it
— Claude Code ships `/resume-orena` — and an agent with such a shortcut may use
it. An agent without one, **including Codex, performs the two steps directly**.
The shortcut is a convenience, never a prerequisite: no agent is blocked, and no
restore is incomplete, because a particular harness command is unavailable.

For learner-facing **visual, brand, mascot, illustration, app-icon, empty-state
or onboarding-art** work, additionally read:

1. `assets/brand/orena/README.md`
2. `assets/brand/orena/BRAND_MASCOT_GUIDE.md`
3. `assets/brand/orena/AGENT_GENERATION_CONTRACT.md`
4. `assets/brand/orena/references/00_MASTER_REFERENCE_APPROVED.png`

The approved master reference is the visual authority. Do not redesign the
Orena mascot from memory or invent a brand identity when approved references
exist. Reuse an existing action, expression or scene before generating new
artwork. Newly generated artwork must preserve the approved character identity,
proportions, palette, facial construction, tail language and illustration
style.

---

# 3. Lanes

`main` is stable and verified. Never develop on it, never auto-merge to it.

Two agent lanes work this repository independently:

- **Codex** — `codex/work`
- **Claude** — `claude/<task>`

`git worktree list` shows the lanes as separate checkouts. When a lane is
assigned, work in it. Do not create another branch or worktree because a
workflow habit suggests one.

The two implementations are **intentionally independent**. Do not inspect,
copy, imitate, merge or cherry-pick learner-facing implementation from the
other lane unless the human explicitly instructs it.

The lanes may share: Product Constitution, requirements, acceptance criteria,
language-learning rules, engineering constraints. Implementation must not be
shared.

---

# 4. Superpowers

The `superpowers` plugin is installed and its bootstrap loads at session start,
so `superpowers:using-superpowers` fires without being invoked. Its process
skills are welcome here: `systematic-debugging` before proposing a fix,
`test-driven-development` when implementing, `verification-before-completion`
before any success claim, `writing-plans` and `executing-plans` for multi-step
work.

`verification-before-completion` and `requesting-code-review` reinforce this
repository's own rules and should be used freely.

Four skills meet Orena constraints that override them. This is not a reason to
skip the skill — it is the boundary to respect while using it:

| Skill | Orena constraint that wins |
| --- | --- |
| `using-git-worktrees` | Lanes are pre-assigned (§3). Use the existing worktree; do not create one. |
| `finishing-a-development-branch` | Never auto-merge to `main` and never declare human approval (§9). Checkpoint and hand to the human. |
| `dispatching-parallel-agents`, `subagent-driven-development` | Three worktrees share one Docker runtime and one set of named volumes. Only one lane may operate Docker at a time (§10). Parallel agents must not run containers or the test image concurrently. |
| `brainstorming` | Product direction comes from the human and the Product Constitution (§1). Brainstorm *how* to implement approved intent; do not invent learner-facing direction. |

Superpowers orchestrates **engineering methodology** around Orena's existing
governance and recovery system. It does not replace it and does not introduce a
second one. `PROJECT_MEMORY.md` remains the only project-memory system: restore
through §2, record through §11. A skill that would have you keep state
somewhere else, or re-derive project context from conversation, is being used
wrongly.

A skill's generic advice never overrides a human gate, a persistence
invariant, or a protected contract.

---

# 5. Platform scope

**Web is the active surface.** Full-stack web work — backend, domain,
`static/orena`, `templates/orena` — is authorized inside the assigned lane.

**Native mobile / Expo / React Native is frozen.** Do not implement, refactor
or extend `mobile/`. The mobile invariants in `ARCHITECTURE_INVARIANTS.md`
remain binding for whenever it thaws; they are not an invitation to work there
now.

Web and native are surfaces over the same learning architecture and share
backend contracts, learner model, curriculum ownership, evidence and language
behaviour. Parity means equivalent capability, not pixel-identical
implementation. Major learner-facing direction must never develop invisibly
inside native code.

---

# 6. Product invariants

`ARCHITECTURE_INVARIANTS.md` holds the full set. These are the ones agents
break most often.

**Multilingual.** English and Chinese are first-class. A shared feature is
implemented once through a language-neutral contract; language adapters are for
genuine linguistic differences only. Do not implement a shared feature fully
for English and postpone the Chinese equivalent unless explicitly authorized —
`REVIEW_POLICY.md` scores that a P1. Support text ships in its own writing
system, with its diacritics intact.

**No hardcoding.** Do not hardcode around failures, tests, users, languages,
IDs, environment-specific paths, migration records, API responses or temporary
UI state. Prefer explicit contracts, configuration, repository abstractions,
deterministic mappings, reusable primitives and root-cause fixes.

**Theme.** Orena has a canonical multi-theme visual system, not a light/dark
switch. A theme has an identity (`paper`, `night-ink`, `deep-forest`,
`sage-field`) and, separately, an appearance (`light` or `dark`); never treat
the two as the same thing, and never assume there are two of anything.

- Colour has one owner: `static/orena/theme.css`. A foundation layer names the
  approved palette, grouped by family; a semantic block per theme says what
  each colour is *for*. Components read only semantic tokens. Do not add a
  second `:root` colour block anywhere - that is the defect this replaced.
- Themes derive from approved palettes under `assets/brand/`. Do not invent a
  colour skin, and do not recolour canonical mascot or brand artwork.
  `pattern/color-pallate.png` is exploratory theme reference only: it is not
  the canonical palette, and its gradients are not approved UI colours.
- Orena Orange `#FF7A3D` is the brand colour and stays canonical. It measures
  2.34 on Paper Ivory, so on light grounds it is fill and illustration only;
  `--accent` carries the contrast-safe text and action role. Never change a
  brand value to make one component pass contrast - assign it a decorative
  role instead.
- Every theme must pass AA for body text, secondary text, controls, links and
  tinted panels. `scripts/test_orena_foundation.mjs` enforces this for every
  registered theme.
- A new approved theme is registered - a block in `theme.css`, an entry in
  `theme.js`, a name and note in `ui/copy.js` for EN and ZH. It is never a new
  component, a component fork, or a rewrite of the settings UI.
- Content artwork - covers, thumbnails, scenes, illustration - may be more
  vivid than the interface, under the Art Bible. That licence is artwork's
  alone and changes nothing above: it creates no second colour owner, exempts
  no UI or text from AA, and no component invents colour outside the semantic
  tokens. `DESIGN_CONTRACT.md` rule 16 governs the boundary (D-057).

**Protected areas.** Journey, Review, Library / Active Recall UI, shared layout
primitives, the shared CSS/JS design system, R5 Grammar contracts and Concept
IDs, canonical Media Learning contracts, accessibility behaviour, and
`docs/visual-references/**`. Protected means *not incidentally*, not frozen
forever: a deliberate product task may evolve presentation when the Product
Constitution requires it. When you must touch one — state why, make the minimum
coherent change, validate it immediately, check dependent flows.

Reuse shared primitives before building page-specific infrastructure. Do not
change frontend or layout as a side effect of backend work. Never stage or
delete `docs/visual-references/**` outside an explicit scope.

---

# 7. Architecture holds

These are open questions the human has reserved. Implement around them; do not
resolve them.

- **Learner-data persistence, schema and account sync.** GPT-6 will define the
  canonical multi-user / account architecture for the ~100,000-user target. Do
  not make new persistence, schema or account-sync decisions for learner-owned
  data, and do not deepen local-device persistence as though it were final.
  Kept-language provenance, conversations, drafts and continuation are device
  memory *by design*, not by omission.
- **Native mobile** — frozen (§5).
- **Platform Admin** — its APIs and `static/admin.js` survive but are inert
  since the historical shell was removed. Preserve it; do not restore the old
  shell to give it a host.
- **Reading library breadth** — the contract, rights fields and admission gate
  exist. Adding a text is a rights decision per text, not an implementation
  task.

`CURRENT_HANDOFF.md` carries the live P1 list; this section carries only the
holds that change what an agent may decide.

---

# 8. Working: slices, recovery, regression

Technical work:

```text
INSPECT → PLAN → IMPLEMENT → RUN → VERIFY → REGRESSION CHECK → CHECKPOINT
```

Learner-facing work:

```text
INSPECT → DEFINE THE EXPERIENCE → IMPLEMENT ONE COHERENT VERTICAL SLICE → RUN
→ VERIFY FUNCTION → REGRESSION CHECK → MAKE WEB-REVIEWABLE
→ UPDATE PRODUCT STATUS → HUMAN REVIEW CHECKPOINT
```

Prefer coherent vertical slices. Do not disappear into several major
learner-facing milestones before showing a reviewable result.

**Resuming interrupted work.** Another agent's run may end mid-slice. Read the
recent commits and the working tree to find the first unfinished point and
continue from it. Do not restart completed work, re-audit what is already
verified, revert valid decisions, recreate stable subsystems because a
different style is possible, or start a competing direction. Finish the partial
work coherently before opening anything new. Preserve technical foundations
that still serve the Product Constitution.

**Regression.** A previously fixed problem must not silently return. Check
schema and type correctness, EN/ZH parity, terminology, navigation, learner
state and restoration, responsive layout, accessibility, light/dark,
contextual feedback, natural translation, cross-capability handoffs, and
previous regression fixes.

When a change breaks stable behaviour: identify the latest relevant change →
isolate the root cause → roll it back if genuinely required → implement the
minimum root-cause correction → verify the original behaviour → run regression
checks → only then continue.

**Never weaken a validator, assertion or comparison to make a failing batch
pass.**

---

# 9. Validation and completion

`.github/workflows/ci.yml` is the canonical definition of the gate. It runs the
project-memory and architecture validators, the listening-catalog check, the
browser ESM graph, the `.mjs` contract gates, then
`pytest -q test_app.py tests` with `PERSISTENCE_BACKEND=sqlite`. When the local
sequence and CI disagree, CI defines the gate and the local recipe is what is
wrong.

**`PERSISTENCE_BACKEND=sqlite` is the isolated CI and test backend only.** It
exists so the suite runs hermetically, against a throwaway database, with no
server to stand up. It says nothing about the application runtime and changes no
persistence authority: PostgreSQL remains authoritative for the running product,
and SQLite remains frozen rollback/archive only, under the Safety section's
persistence invariant. Seeing this flag in CI is never evidence that SQLite is a supported
runtime, a fallback, or a migration target.

## Running it locally

Host Python has **no project dependencies**. Stdlib validators and the Node
gates run on the host; anything needing pytest, SQLAlchemy, Alembic or psycopg
runs in the application image with the repository mounted read-only:

```bash
MSYS_NO_PATHCONV=1 docker run --rm \
  -e PERSISTENCE_BACKEND=sqlite -e POSTGRES_RUNTIME_URL= \
  -e GOOGLE_CLIENT_ID= -e GOOGLE_CLIENT_SECRET= -e GOOGLE_REDIRECT_URI= \
  -e APP_ENV=development -e PUBLIC_BASE_URL=http://localhost:8000 \
  -e WRITING_DB=/rundata/w.db -e AUTH_DB=/rundata/a.db \
  -e PLATFORM_DB=/rundata/p.db -e PRODUCT_DB=/rundata/pr.db \
  --tmpfs /rundata \
  -v "<abs-windows-path>:/workspace:ro" -w /workspace \
  ai-writing-coach:local \
  sh -lc "pip install -q pytest; python -m pytest -q -p no:cacheprovider test_app.py tests"
```

Five environment traps, none of which are application defects:

- The image does not ship pytest (`requirements.txt` omits it) — install it in
  the ephemeral container, as above.
- Git Bash rewrites `-w /workspace` into `C:/Program Files/Git/workspace`.
  Prefix with `MSYS_NO_PATHCONV=1` and pass the volume source as a Windows path.
- `docker compose run ... writing-coach` also works, but compose injects
  `POSTGRES_RUNTIME_URL`, which fails
  `test_invalid_and_postgres_fail_without_bundle` locally while it passes in
  CI. Clear it. Plain `docker run` avoids the injection entirely.
- Compose likewise injects the Google OAuth pair, turning `AUTH_ENABLED` on so
  unauthenticated route tests answer 401 where CI sees 200/503. Clearing the
  pair alone then trips the `APP_ENV=production` guard, so clear
  `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and `GOOGLE_REDIRECT_URI` **and**
  set `APP_ENV=development` with a local `PUBLIC_BASE_URL`. Without this,
  `tests/test_r17_admin_routes.py` and `tests/test_reference_data_cache.py`
  fail for environment reasons only.
- `node --experimental-vm-modules scripts/validate_browser_esm_graph.mjs`
  requires that flag; without it the failure reads like a source error
  (`vm.SourceTextModule is not a constructor`), not a missing flag.

Some suite failures are inherited. Take the current expected count from
`CURRENT_HANDOFF.md` rather than a historical number, and before calling a
failure a regression, reproduce it against a clean tree —
`git archive HEAD | tar -x -C <tmpdir>` — and compare the failure sets.

Ruff is lint-only (`ruff.toml`), is not in `requirements.txt`, and lints the
files you touched: `ruff check <path>`. There is no `package.json`; `.mjs` gates
run under bare `node`.

A harness may wrap this sequence in a shortcut — Claude Code ships
`/validate-gate`. As with the restore in §2, the shortcut is convenience; the
sequence above is the contract.

## Reading a failure

Distinguish source failure, packaging failure, execution-environment failure,
dependency failure, data-compatibility failure and real application
regression. Do not patch application logic to hide an environment problem.
Before treating a direct Python script failure as an application regression,
check import-root and `sys.path` behaviour and prefer module execution.

**Never claim CI PASS without CI evidence. Label local runs as local
execution.** Success requires validating the changed flow, not writing code.

## Web review gate

Tests are necessary and not sufficient. A learner-facing milestone is
`REVIEWABLE` only when the product owner can open a browser and experience it.
It is not complete because it exists in backend code, an API, tests, an
isolated component, a static mockup, an unreachable route, or mobile only.

## Review states

`PLANNED` · `IMPLEMENTING` · `REVIEWABLE` · `BLOCKED` — an agent may set these.

`APPROVED` — **only the human establishes product approval.**

## Report

`REVIEW_POLICY.md` defines the required completion evidence; report it in full.

Learner-facing work additionally reports:

```text
MILESTONE=      STATUS=       COMMIT=
WEB_URL=        WEB_ROUTE=    HOW_TO_REACH_IT=
EN_PARITY=      ZH_PARITY=    CROSS_CAPABILITY_STATUS=
TESTS=
WHAT_CHANGED=
WHAT_THE_HUMAN_SHOULD_REVIEW=
```

After a milestone reaches `REVIEWABLE`, present it to the human before starting
another major learner-facing milestone.

Never merge to `main` automatically. Never declare human product approval.

---

# 10. Safety

`ARCHITECTURE_INVARIANTS.md` owns persistence, Git, operations, secrets and
human gates in full. Non-negotiable, restated because the cost of getting them
wrong is unrecoverable:

- **Persistence** — PostgreSQL is authoritative; SQLite is frozen
  rollback/archive only. No dual-write, no reverse sync, no silent fallback, no
  startup import, no automatic startup Alembic.
- **Volumes** — never `docker compose down -v`; never delete persistent volumes
  or SQLite archives as cleanup.
- **Shared runtime** — three worktrees share one Docker runtime and one set of
  named volumes. Confirm no other lane is operating it before you do.
- **Git** — no `git clean -fd`, no arbitrary `git add -A`, no destructive
  `git reset --hard`, no force-push to stable branches, no rewriting verified
  history. Stage only files belonging to the current coherent change.
- **Secrets** — never print, commit or document secret *values*. Variable names
  are fine. Copy `.env.example` to `.env`; `start_docker.ps1` does this.
- **Runtime boundaries** — operate only the sandbox `CURRENT_HANDOFF.md`
  names. Production, preview, Cloudflare, DNS, OAuth and paid providers are
  human gates.

Stop for explicit human authorization before any gate in
`ARCHITECTURE_INVARIANTS.md § Human gates`. Normal learner-facing iteration
inside the assigned lane is **not** a gate, even when current UI differs from
the Product Constitution.

An existing Docker warning is not automatically an application failure.

---

# 11. Repository memory

Essential Orena knowledge lives in the repository, never in Codex session
history, Claude conversation history, ChatGPT memory, or one developer's
recollection.

`PROJECT_MEMORY.md` defines which document records what, who may edit it, and
what triggers a change. Follow its memory transaction: update current memory
only when verified truth changed, run `python scripts/validate_project_memory.py`,
then commit.

A new competent agent entering this repository must be able to determine
Orena's current product direction, current technical reality, the active
milestone, the next human-review checkpoint, and the constraints that must
remain safe — without asking anyone.
