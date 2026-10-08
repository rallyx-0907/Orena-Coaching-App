# Review request: grammar content store, revision 3 (3a) and proposed migration 0030

**Requested of:** an independent architecture reviewer: the Principal Architect role (GPT-6/Codex preferred) or a
Delegated Architecture Reviewer who did not write any of the files below (AGENTS section 1). The author of revision 3
may not review or approve it, and neither may an agent the author dispatches. Codex's automated PR review of `3f971976`
was a code review; its two P1s are answered in revision 3a (proposal section 18a). This request is for the separate
architecture verdict.

**Issue:** #99. **PR:** #100 (`codex/work` -> `main`). **Review the head commit of PR #100** and record its SHA in the
verdict. Gate: no Store/API code, no promotion of the migration and no apply anywhere until this review approves and the
human authorizes (proposal section 20).

## What to review

| File | What it is |
| --- | --- |
| `docs/project/proposals/GRAMMAR_CONTENT_STORE.md` | Revision 3 (3a). Start with section 0a (stale assumptions corrected from revision 2), 17 (R3-1..R3-7, the questions for you), 18/18a (review responses), 19 (contract boundary), 20 (evidence, next gate). |
| `migrations/proposed/20261008_0030_grammar_content_store.py` | The proposed revision: eight tables, constraints, two PostgreSQL triggers, downgrade. Parent `20261007_0029`. |
| `scripts/rehearse_grammar_content_store.py` | The throwaway-PostgreSQL rehearsal (twelve groups). |
| `scripts/check_grammar_export_contract.py` | Boundary reconciliation with Grammar Lab at `3579ece8` (read with `git show`, parsed with `ast`). |
| `tests/test_grammar_content_store_migration.py` | Hermetic SQLite tests (CI), including the guards that no Store code and no point JSON exist before the gate. |
| `docs/project/proposals/GRAMMAR_CONTENT_STORE.REHEARSAL.md` | The recorded run (local, not CI). |

Revision 2 was approved (`GRAMMAR_CONTENT_STORE.REVIEW.md`) and its decisions are D-106; they are not reopened. Review the
**delta**: the refresh against `main` (`a2342e62`, schema `20261007_0029`), the migration file itself, and the evidence.

## Questions the review should answer

1. Is the migration correct and safe as written: additive only; no lock on, foreign key to, or change of an existing table;
   cycle-free; downgrade drops only its own objects; the triggers and CHECKs enforce what sections 3 and 6 claim; nothing
   learner-owned?
2. Is section 0a right that each listed revision 2 assumption is stale on `main` / Grammar Lab `3579ece8`, and is anything
   stale that it missed?
3. Does the trust boundary (section 5) match the export contract at `3579ece8`: profile id, schema version, pinned profile
   hash, closed manifest, semantic `package_hash`, `en`/`zh`, `r5_map`, closed-schema validation, cross checks?
4. Decisions R3-1..R3-7 (section 17), in particular R3-3 (stronger database rules than revision 2) and R3-7 (review verdict
   separated from serving state, so rollback works).
5. Is the rehearsal evidence sufficient for promotion (section 20), given that it ran locally on PostgreSQL 16.15 with
   synthetic, profile-valid content and not on a restored copy of any runtime? What, if anything, must run on the D-143/D-144
   restored-copy rehearsal before :8000?
6. Anything that must be resolved before the Store/API implementation (steps 2 and 5) may start.

## How to reproduce (optional; disposable database only)

```
python -m venv /tmp/gcs-venv && /tmp/gcs-venv/bin/pip install -r requirements.txt pytest jsonschema pyyaml
git fetch origin feature/grammar-lab-pipeline            # makes 3579ece8 available to git show
/tmp/gcs-venv/bin/python scripts/check_grammar_export_contract.py
PERSISTENCE_BACKEND=sqlite /tmp/gcs-venv/bin/python -m pytest -q tests/test_grammar_content_store_migration.py
# a THROWAWAY PostgreSQL 16 whose database name contains "rehears", "throwaway" or "scratch" (the script refuses others):
/tmp/gcs-venv/bin/python scripts/rehearse_grammar_content_store.py "postgresql+psycopg://...@127.0.0.1:<port>/orena_grammar_rehearsal"
```

Never point the rehearsal at :8000, :8010, :8011, :8021 or any shared volume.

## Recording the verdict

Append a section "Review of revision 3" to `docs/project/proposals/GRAMMAR_CONTENT_STORE.REVIEW.md` with: reviewer role and
independence statement, reviewed commit SHA, files read, what was run (and what was not; no PASS without execution), findings
by severity (`REVIEW_POLICY.md`), and the verdict (APPROVE / APPROVE WITH CONDITIONS / REQUEST CHANGES). An architecture
verdict is not product approval and does not authorize promoting or applying the migration; that stays the human's.
