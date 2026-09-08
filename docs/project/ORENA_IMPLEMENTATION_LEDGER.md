# Orena implementation ledger — I1 to I7

Implementation under the locked GPT-6 backbone (`27edeb0`). Sequence and exit
gates come from `ORENA_BACKBONE_INTEGRATION_GATES.md`; this file records what
was actually built, what it is verified against, and what each package
deliberately left gated. Package F remains human acceptance and is not claimed
here by anyone.

Owner: Opus, implementation. Architecture questions go back to Codex/GPT-6
rather than being answered by inventing a contract.

---

## I1 — Account, learner profile and preferences

**Specification:** `ORENA_ACCOUNT_DATA_ARCHITECTURE` §§1-3.
**Exit gate:** scoped read/patch and logout/incarnation scenarios; no theme WIP
edits.
**Status:** implemented, ungated adapters only.

### What a learner gets

Saving one preference no longer rewrites the others, and two devices editing
preferences no longer silently overwrite each other. The endpoint that existed
took a whole profile with a default for every field, so a client sending only
the setting it meant to change reset the rest to product defaults — and the web
client's read-modify-write meant whichever save landed second won, with no sign
that anything was lost. A save now names only what it changes, against the
version it read; a save made against a version someone else has already moved
is refused, the current values are fetched and shown, and applying again is the
learner's decision rather than an automatic overwrite.

### What was built

`writing_coach/account_profile.py` — pure decisions, no storage or session:

- **Scope** is `reference_backbone.Scope`, not a second shape meaning the same
  thing. `scope_of(account_row, language)` derives it from verified identity;
  a missing account or a missing learning language is refused rather than
  defaulted, because language-scoped resources authorize on both.
- **Incarnation** is server-owned. `incarnation_of` derives the access epoch
  from facts the account row already carries, so a deleted-and-recreated
  account produces a different epoch and everything scoped to the old one stops
  matching. This is not the durable deletion barrier, which needs the gated
  migration; it is the part that can be honest without one.
- **Effective settings** as `{value, source, version}` with the documented
  precedence — session override, saved preference, declared default. A stored
  value that is no longer valid falls back to the default and *says so* rather
  than being served as though the learner had chosen it.
- **Defaults** live in the registry, not in room constants. Support language
  resolves through `core/support_languages` rather than a second copy of the
  rule.
- **Patch semantics**: named fields only; an absent field keeps its saved
  value; an unsupported field, an invalid value, an empty patch and a stale
  version each refuse and write nothing, with a stable reason key so a surface
  can say something true in either interface language.

Runtime seam in `writing_coach/becoming_memory.py`, `PATCH
/api/learner-profile` in `app.py`, `patchLearnerProfile` in the web client.

### Deliberate limits

- **No schema.** The profile has no version column and none is authorized, so
  the concurrency token is the record's own `updated_at`. `patch_profile`
  compares versions for equality and cannot mint a non-integer successor, so
  the caller supplies it — the module does not hold a clock.
- **Two settings in the contract have no column**: a declared target level and
  an account-wide interface language. Both are declared in the registry, both
  read and override correctly, and a patch for either is refused as
  `not_yet_stored` rather than accepted and dropped on the way to the
  repository. They need the gated additive migration.
- **The durable deletion barrier is not implemented.** Incarnation changes
  correctly on recreation; denying reactivation until an explicit
  re-registration flow needs storage that is not authorized here.
- **Theme untouched.** `theme_preset` is read and written back unchanged and is
  not a member of the settings registry, per the gate's "no theme WIP edits"
  and the architecture's reservation of theme presentation to its own owner.
- **`PUT /api/learner-profile` is unchanged**, because `mobile/` calls it and
  native is frozen. Its whole-profile replace semantics are documented at the
  endpoint. The web client no longer uses it.

### Evidence

- `scripts/test_orena_account_profile.py` — 32 stdlib counterexamples, CI
  registered. Scope derivation and refusal, incarnation change on recreation,
  results refused across account/incarnation/language, precedence and invalid
  fallback for effective settings, account-wide versus language-scoped
  membership, and every patch refusal.
- `tests/test_orena_account_profile_runtime.py` — 9 pytest cases over the
  repository seam with a fake profile repository: the flat shape existing
  surfaces consume survives, a patch preserves what it does not name, the
  version advances, a stale writer gets 409 and writes nothing, theme preset is
  untouched, and an absent profile is created from the empty version.
- Browser at `127.0.0.1:8011`: read returns `{value, source, version}` per
  setting; a patch naming `pinyin` leaves goal, style and theme preset intact;
  a write against a moved version returns 409 `version_conflict` and changes
  nothing; the preferences dialog saves normally, and on a concurrent change
  keeps the other writer's value, refreshes itself and lets the learner apply
  again.
- Python suite in the app image: 799 passed / 20 failed. The 20 are the
  inherited governance-document failures recorded in `CURRENT_HANDOFF.md`;
  failure sets are byte-identical to a clean `git archive HEAD` tree, so this
  package adds 9 passing tests and no regression.
- 32 Node gates pass, ESM graph 51 modules, both validators OK. `ruff check`
  clean on both touched Python modules; the two findings in `app.py` are
  present at HEAD and are not from this change.

### Open for GPT-6

Nothing blocking. Two contract items are storage-gated rather than unclear, and
are named above so the migration slice knows what is waiting for it.
