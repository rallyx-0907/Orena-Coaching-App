# Orena Intelligence lane: handoff to the next agent (2026-10-18)

This handoff covers the Orena Memory work under issue #256. It is written for an agent that takes the work over with no access to the earlier conversation. Read it after the bounded restore (AGENTS.md §2) and before touching anything in this lane.

Authority stays where AGENTS.md puts it:
- the design is in `docs/project/proposals/ORENA_MEMORY.md` (rev 4.1);
- the owner's decisions are in `docs/project/DECISION_LOG.md` (D-222);
- the code and tests on `main` are the technical truth.

If this file and one of those disagree, the authority wins and the disagreement is a defect to report.

## 1. Lane rules (the owner's brief, still binding)

**Branches and merging**
- Start every task from the newest main: `git fetch origin && git switch -c claude/intelligence-<task> origin/main`.
- Before opening or updating a PR, merge `origin/main` into the branch. Never rebase shared history. Re-run the gates after the merge.
- One small, focused PR per slice.
- Every PR needs an independent review and green CI. A decision also needs the owner's explicit "D-xxx: ACCEPTED".
- Open PRs only. Never merge them yourself.

**Scope you may edit**
- `writing_coach/agent/**`
- the `/api/agent/*` routes
- the agent and voice providers (`ai/live_voice.py`, `agent/voice_session.py`)
- the learner-context and memory layer
- chat model routing

**Do not touch.** The UI lane owns these files. If you need a change there, open a GitHub issue instead.
- `static/orena/**`, `templates/**`, `docs/design/**`
- `writing_coach/media_*.py`, `media_providers/**`, `media_spend.py`
- `cost_tier.py`, `cost_env.py`, `ai/pricing.py`, the cost and report code in `ai/platform.py`
- `policies.py`, `billing/**`

**Shared documents**
- `DECISION_LOG.md` is append-only. Take the next free D-number from `origin/main` when you commit, and renumber yours if it collides.
- `UI_BACKEND_GAPS.md` is append-only. Never edit an existing entry.

**Human gates: stop and ask the owner before any of these**
- a new table, column or migration, or a new kind of learner data stored on the server;
- a new provider, credential or paid plan;
- changes to auth or roles, publish or rights policy, or bulk data mutation;
- trusting client-reported usage;
- merging.

**Runtime**
- Never use or restart the owner's sandboxes on :8000, :8010 or :8021.
- Use CI and the hermetic test setup in AGENTS.md §9.
- Never print or commit a secret.

**Reporting**
- Report to the owner in Vietnamese, short and results-first.
- Write PR and review comments in English, ending with the Claude Code footer.

## 2. What is merged (all on `main`)

| PR | What it delivered |
| --- | --- |
| #259 M0 | Cache-stable prompt layout (`AGENT_PROMPT_LAYOUT`, default `legacy`), one model pinned per conversation, turn telemetry. Live benchmark: legacy stays the default. |
| #260 M1 | Learner pack (`writing_coach/agent/memory_pack.py`, `orena-pack/1`) built from profile and evidence, with provenance for every claim. Off by default (`AGENT_LEARNER_PACK`). |
| #262 A2 | Capped live benchmark: answers, pack on/off, `CostLedger`. |
| #263 A1 | Provider data classes (`writing_coach/agent/data_class.py`, `AGENT_PROVIDER_DATA_CLASSES`). |
| #265 | Proposal rev 4.1 plus D-222 (ACCEPTED): limits on G1/G2, test-lane clearance, M5 keys, `usageMetadata` used for reconciliation only. |
| #266 M2-prep 1/2 | `memory_keys.py` (versioned HMAC keys), `memory_slots.py` (EN/ZH/VI matchers that map to closed codes, with negation guard and grounding), `memory_summary.py` (summary validator). |
| #267 M2-prep 2a | `memory_store.py`: the `MemoryRepository` port and an `InMemoryMemoryStore` fake that implement the rev 4.1 semantics; `memory_section()`; pack sections for memory; `orena-pack/2`. |
| #268 M2-prep 2b | G8 gate covering `learner_pack`, `coach_notes`, `conversation_history` and `chat_context` (`context_gate.py`), plus `ProviderNotCleared`. |
| #269 M2-prep 2c | Draft migration `migrations/proposed/20261018_0035_orena_memory.py`, proposed only, plus `scripts/rehearse_orena_memory_schema.py` (35 PASS on a throwaway PostgreSQL 16). |

Issue #264 is open: the UI lane needs an Admin field for each provider's data class.

## 3. Where things stand in code

### Learner pack (M1)

- Off by default.
- A pack is sent only to a provider cleared for `learning_profile`.
- `PackBuilder.memory` (the memory reader) is **unset in the app**, because no store exists until the M2 migration is promoted. Without a memory reader, the bytes are exactly M1's.

### G8 (`data_class.py`)

The gate applies only when a record exists and `AGENT_LEARNER_PACK=on`.

- **Governed:**
  - **Learner pack:** sent only to providers cleared for `learning_profile`.
  - **Coach notes:** only to `full_memory`. Below that, the note tools are neither offered nor accepted. A learner who asks about notes gets `notes.unavailable` (owner decision 2026-10-18). My extension of that decision also blocks *new* notes; the owner has not confirmed this, so it is listed as an open question in section 6.
  - **Chat context state carried from earlier turns:** only to `learning_profile`. This covers tool summaries, the focus and pasted text, and a reused selection.
  - **Conversation history:** a conversation is never continued on a provider cleared for less than the highest class it has already sent (`data_class_sent`). This is checked before a route is pinned.
- **Not governed yet** (`NOT_YET_GOVERNED`): the opening snapshot, learner text, and tool results. G8 is not complete until these are covered.
- **M2 must use two edges that already exist:**
  - `gating_on(..., memory_on=True)` once a memory switch exists;
  - `pack_class(with_memory=True)`, which returns `full_memory`, checked before a memory-bearing pack is built.

### Memory store (`memory_store.py`)

This is the contract the PostgreSQL repository must honour.

**Port methods:** `state`, `probe`, `snapshot`, `items`, `summaries`, `set_enabled`, `add_explicit`, `delete_item`, `delete_all`, `checkpoint`, `finalise`, `delete_summary`.

**Semantics**
- Scope is incarnation plus user. With no incarnation, nothing is stored.
- Every change bumps the version.
- When memory is switched OFF, nothing new is written, but delete and the switch still work.
- Suppression keys are HMACs of slot + code, survive a bulk delete, and survive a key rotation.
- A deleted session leaves a tombstone for the whole session.
- Checkpoints are monotonic per session and per language.
- Finalisation after 30 idle minutes is stored and bumps the version.
- `snapshot` is one consistent read.

**Pinning or promotion is deliberately absent.** It arrives with M3. The schema already has the `code` column to support it.

### Draft migration 0035

- **Tables:** `learner_memories` (with `code`), `learner_memory_suppressions`, `learner_memory_state`.
- **Parent:** 0033. Re-parent it at promotion onto the head of that day.
- **Not yet built:** ORM, repository and deletion enumeration. Those come in the promotion PR.

## 4. Local setup and gates

**Host Python** has no project dependencies.
- In the cloud session I used a venv with `requirements.txt` plus pytest, xdist and ruff.
- Locally, use the Docker recipe in AGENTS.md §9.

**Commands**

```bash
PERSISTENCE_BACKEND=sqlite python -m pytest -q -p no:cacheprovider -n auto test_app.py tests
ruff check <files you touched>
python scripts/validate_project_memory.py
python scripts/validate_architecture.py
```

**Facts to know before reading results**
- The full suite has **20 inherited failures**, all in tagger/lookup tests (`test_linguistic_annotation`, `test_reading_lookup`, `test_tap_basic_meaning`, `test_media_interaction`, `test_ai_runtime`, `test_lookup_seam_admission`). Any failure outside that set is yours.
- Delete `data/languages/` after a test run; the tests leave it behind.
- Run the **full** suite before every push, not only the files you changed. An early-return bug that only the full suite caught broke 312 tests once.
- Stage files by name. The bash guard blocks a blanket `git add`.

**PostgreSQL tests and rehearsal**
- These need a throwaway PostgreSQL 16 (`initdb` + `pg_ctl` on a spare port with a socket directory, a database name containing `rehearsal`).
- Run `scripts/rehearse_orena_memory_schema.py "<url>"`, then remove the cluster.
- CI has no PostgreSQL, so those tests skip there.

## 5. Next work, in order

### Step 0: decisions only the owner can make. Ask before starting.

1. **Authorisation to promote migration 0035** into `migrations/versions/` and apply it. This is a human gate: a new table and new learner data stored on the server. The owner must also name the runtime (for example, the test lane only). The migration still needs its independent review at promotion and a PostgreSQL up/down/up rehearsal.
2. **Agent Contract v9 on `codex/work`.** The UI lane owns the contract; this lane never edits it. Open an issue asking for:
   - `coach_notes` to become optional;
   - a client to declare `contract_version >= 9` to receive server-applied notes;
   - §10 to point at `/api/agent/memory`.

   M2's server-applied notes and M3 are both blocked on this.
3. **Confirm or reverse** whether creating a *new* note is also blocked below `full_memory` (see section 6).

### Step 1: M2 promotion PR (once 0 is granted)

1. `git mv` the migration into `versions/` and re-parent it.
2. Add ORM models with SQLite parity. CI uses `Base.metadata.create_all`, so partial indexes and JSONB need SQLite-compatible fallbacks.
3. Add the tables to `deletion_enumeration.py` and its test.
4. Build a PostgreSQL `MemoryRepository` under `writing_coach/persistence/` that passes **the same contract tests** as `InMemoryMemoryStore`. Parametrise `tests/test_agent_memory_store.py` over both implementations.
   - Each method must be one transaction.
   - The checkpoint takes the state row `FOR SHARE`, checks the incarnation is active, does a tombstone-aware upsert, then a suppression check (rev 4.1 §4.2).
5. Wire it into the app:
   - `memory_scope` from the active incarnation;
   - `AGENT_MEMORY_HMAC_KEYS` read at start, with fail-closed behaviour and the `check_in_use` start check;
   - `PackBuilder.memory` set to `memory_section`;
   - a per-turn `probe` that rebuilds the pack when the version changes;
   - `gating_on(memory_on=...)` and `pack_class(with_memory=True)`.
6. Add routes under `/api/agent/memory` (§6):
   - list, with reason codes rather than prose;
   - delete an item;
   - delete all;
   - delete a session;
   - the switch.

   Use the same CSRF/origin handling as the other `/api/agent` POST routes.
7. Server-applied `remember_note`/`forget_note` **only** for clients that send `contract_version >= 9`. A v8 client keeps today's device-only behaviour.
8. Before merge, show the M2 "Must show" items from §9: two-worker/device deletion, switch semantics, dedupe against device notes, and suppression.

### After M2 (each is its own reviewed slice)

- **M2b:** `memory_signals` plus the inferred rules (§3.3). Each rule stays off until the owner records its false-positive bound. The rule matchers are already in `memory_slots.py`.
- **M3:** session summaries and the `agent_session_summary` capability.
  - Validate with `memory_summary.py` and ground with `memory_slots.grounded`.
  - Add pin/promotion using the `code` column.
  - Needs: D-222 limits, contract v9 §10, and its own migration revision.
- **M4:** the pack for writing review (behind a flag, with a writing benchmark) and for text discussion.
- **M5:** the challenger benchmark (gpt-6-luna, DeepSeek flash, Claude Haiku 5.5, which needs an Anthropic adapter per G6) using the A2 script. It needs the keys the owner provides in the test lane.
- **D-222 #4:** `POST /api/agent/voice/end` accepts the client's final Gemini Live `usageMetadata` for reconciliation only. Store it bounded and labelled `client_reported`; caps keep the server ceiling. Not built yet. Showing it on the cost page is UI-lane work (open an issue).
- **G8 remainder:** opening snapshot, learner text, tool results.
- **M1 follow-ups:** sounds and tones from phoneme labels, recent titles, the R5 concept for writing categories.

## 6. Open questions for the owner

- **New coach notes below `full_memory`:** the owner chose "keep the design, disable editing notes". The code also blocks *creating* a new note, for one simple rule. This needs confirming or reversing.
- **Test lane setup:** it needs `AGENT_LEARNER_PACK=on` and `AGENT_PROVIDER_DATA_CLASSES=gemini=learning_profile`. With that record, coach notes are no longer sent to Gemini. To keep them, the owner would clear Gemini for `full_memory`.

## 7. What independent reviews caught (avoid repeating these)

- **Negation:** "I'm not an engineer" stored the opposite fact. Check negation across the **whole sentence**, before and after the cue, on every matcher path.
- **Bounds:** apply them to the value you will store (after resolution), and measure the final stored size in UTF-8 bytes.
- **Version consistency:** a memory read must come from one version-consistent snapshot. Every change, including idle finalisation, bumps the version. A cheap per-turn probe must reveal changes that only the passage of time causes.
- **Language:** scope by language everywhere, including scrubbing summaries after a delete.
- **Deferred APIs:** remove a deferred API from the port **and** from the fake. A contract test now asserts this.
- **G8 enforcement:** enforce at the mutation and tool boundary, not only in the prompt text. Check clearance **before** persisting a route. Count every governed payload actually sent, including chat context, towards the conversation's class.
- **CHECKs with NULL:** a NULL comparison makes a CHECK pass; use explicit `IS NOT NULL`.
- **Representation:** keep the closed code separate from the learner's words (the `code` column).

## 8. File map

| Concern | Files |
| --- | --- |
| Design and decisions | `docs/project/proposals/ORENA_MEMORY.md`, `ORENA_MEMORY_M1.md`, `ORENA_MEMORY_M0_BENCHMARK.md`, `docs/project/DECISION_LOG.md` (D-222) |
| Pack | `writing_coach/agent/memory_pack.py`, `tests/test_agent_learner_pack.py` |
| G8 | `writing_coach/agent/data_class.py`, `context_gate.py`, `turn.py` (`_gate_data_classes`, `_choose_route`, `_record_data_class_sent`), `voice_session.py`, `outputs.py` (`notes_available`), `tests/test_agent_data_class.py` |
| Memory prep | `writing_coach/agent/memory_keys.py`, `memory_slots.py`, `memory_summary.py`, `memory_store.py`, `tests/test_agent_memory_prep.py`, `tests/test_agent_memory_store.py` |
| Schema | `migrations/proposed/20261018_0035_orena_memory.py`, `scripts/rehearse_orena_memory_schema.py`, `tests/test_orena_memory_migration_draft.py` |
| Benchmark | `scripts/agent_prompt_cache_benchmark.py`, `tests/test_agent_prompt_cache_benchmark.py` |
