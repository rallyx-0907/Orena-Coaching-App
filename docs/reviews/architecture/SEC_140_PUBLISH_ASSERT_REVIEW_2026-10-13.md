# Architecture review - Host-side assertion of Docker's real publish address (issue #140)

- Reviewer role: **Delegated Architecture Reviewer** (AGENTS.md "Architecture review authority").
- Reviewer model: Claude Opus 5.5 (independent of the implementer). I did not write this change.
- Reviewed: branch `claude/sec-140-publish-assert`, commit `c825370a`, diff `origin/main..c825370a` (14 files, +546/-9). Follow-up of #137 (reviewed separately).
- Date: 2026-10-13. Read-only review; no Docker, app or network used. Not product approval and not activation authorization.

## VERDICT: APPROVED WITH CONDITIONS

The script is sound: it reads only the two port fields, decides with the app's loopback rule, fails closed on unpublished or unreadable answers, and has no injection path. One condition (P1-1) must be fixed before merge: three launchers that run under `$ErrorActionPreference = 'Continue'` fail OPEN if `python` is not on PATH.

## Evidence

- `python -m pytest -q --noconftest tests/test_assert_published_loopback.py tests/test_local_boundary_deployment.py`: **149 passed** (local execution, not CI).
- `py_compile` on the script and both Python runners: ok. `ruff check scripts/assert_published_loopback.py`: clean. `validate_project_memory.py`: exit 0. PowerShell parser: 0 errors in all 7 edited `.ps1` files.

## Verified

1. **Reads and decision (scripts/assert_published_loopback.py).** `PORT_TEMPLATES` (line 28) are the only Docker reads: `{{json .NetworkSettings.Ports}}` and `{{json .HostConfig.PortBindings}}`; a test asserts `--format` is last and no `.Config`/`Env` appears. The loopback rule equals `writing_coach.core.deployment.is_loopback_host` and a test pins agreement. Missing or empty `HostIp` is returned as `""` and refused; mixed v4/v6 must all pass; null/unpublished ports, other ports and udp are not counted, and "nothing published" is refused; a failed read or bad JSON gives exit 3. Exit codes 0/2/3 as documented. Both documents are unioned, so a hand-edited request in `HostConfig` is caught even when the container is not running.
2. **No injection.** `subprocess.run` is always called with a list, never `shell=True`; the container name is a single argv element. The wrappers pass `$webId` from `compose ps -q`, and `--probe-url` is a constant `http://127.0.0.1:8000/api/me` in the wrappers. A name starting with `-` would be read by docker as an option, but names come from launchers, not input.
3. **LAN opt-in proof is sound for its purpose.** With auth off, `/api/me` answers 200 (local) or 403 (non-local middleware refusal); 401 comes from the middleware's "Authentication required" path, which exists only when `AUTH_ENABLED`. So 401 on `/api/me` shows sign-in is on. The probe cannot name an attacker URL (fixed by the wrappers). A different process answering on that loopback port is a theoretical gap only. The opt-in is applied only when the launching shell exports the variable; set only in `.env`, the check fails closed (documented).
4. **Launchers.** Every launcher in `LAUNCHERS` runs the check after start: compose wrappers (`start_docker/dev/public.ps1`), `agent_e2e/run.py` and `agent_live/run.py` (raise on non-zero), `mobile_qa_runtime.ps1`, `product_restore_rehearsal.ps1`, `staging_update.ps1`, `staging_8000_deploy.ps1`. `mobile_qa_runtime.ps1`: `run -d --name` plus `docker logs -f`, with `rm -f` in `finally` replacing `--rm`, also removes the container when the assertion throws; the pre-run `rm -f` only targets `orena-mobile-qa-<Port>`. No lost cleanup found.
5. **:8000 (`staging_8000_deploy.ps1`).** The diff is exactly four lines: two comment lines, a read-only `--no-stop` call and a `Fail` after readiness. Publish (`-p 127.0.0.1:8000:8000`), env, rollback and replacement logic are untouched. A `Fail` there does not stop or change anything. Plainly: by that point the previous containers are already stopped and renamed and the new one is already serving ready staging, so a `Fail` leaves :8000 exactly as it would be on success, only with exit 1 and the last two status lines skipped. It is not worse than before, but a false failure (a read error) would tell the operator a healthy deploy failed. Because this script publishes the literal loopback address, the check can only trip on a read error.

## Findings

### P1-1 - Fail-open when `python` is missing (three `Continue` scripts)
- Where: `scripts/staging_8000_deploy.ps1` (the new `& python` line near the end), `scripts/staging_update.ps1` (after the web container start), `scripts/product_restore_rehearsal.ps1` (after the web start); each sets `$ErrorActionPreference = 'Continue'` (lines 31, 50, 30).
- Issue: if `python` is not found, PowerShell raises a non-terminating error and does not update `$LASTEXITCODE`; the script then tests the stale value from the previous native command (typically 0), so the assertion silently passes. The `Stop`-mode scripts (`start_*.ps1`, `mobile_qa_runtime.ps1`) terminate and fail closed. The "fails closed" claim is therefore false for these three.
- Required: set `$global:LASTEXITCODE = 1` immediately before each `& python ...` call (or test `Get-Command python` and Fail/Die first) so a missing interpreter is a refusal. Add a test that each such script resets or guards `LASTEXITCODE` before the call.

### P2-1 - `stop()` result unchecked
- `scripts/assert_published_loopback.py` `stop()`/`main()`: a failed or timed-out container stop is ignored and "Stopped container" is printed regardless; `subprocess.TimeoutExpired` from `stop` is uncaught (a traceback, exit 1, still non-zero). Required: check the return code, print the truth, catch the timeout.

### P2-2 - `start_dev.ps1` behaviour change
- `up --watch` becomes `up -d --build` then `watch`: logs are no longer streamed, and Ctrl+C now ends watch but leaves the containers running. Not a security issue; note it in the script header or follow the logs.

### P2-3 - Point-in-time check, brief window
- The container is already serving when the check runs; a wide publish is reachable for the seconds before the stop, and a publish edited later is not seen. Documented as point-in-time. Acceptable for this residual; the startup refusal and peer check remain layers.

### P2-4 - `staging_update.ps1` refusal leaves the lane down
- On refusal the new container is stopped while the previous one is already renamed and stopped, so :8011 has no running web until the operator acts. The message names the previous container. Same shape as the script's other `Die` paths; state it in the doc.

### P2-5 - Tests: logic is real, launcher coverage is text-inventory
- The decision, exit codes, `--no-stop`, fail-closed reads and the LAN opt-in are tested against a stubbed Docker (real behaviour). Launcher wiring is checked by text order (start text precedes the assertion call), and the :8000 test only checks `--no-stop` is on the line. That is the expected level without Docker; nothing was weakened or removed. No test exercises the PowerShell paths, which is why P1-1 went unseen.

### P2-6 - Placeholder
- D-18X must be renumbered at merge, and its status line should record this review.

## Conditions to merge

- C1: fix P1-1 and add the guard test. C2: P2-1. P2-2 to P2-6 may follow, tracked.

## Not verified

- Only the two stdlib-friendly test files were run, with `--noconftest`; the full suite and CI were not run.
- Real Docker output shapes (Docker Desktop `HostIp` values, dual-stack pairs, host network mode) were reasoned from Docker's documented JSON, not observed. `docker compose watch` semantics after `up -d` were not run.
- PowerShell scripts were parsed, not executed.

Architecture review is not product approval and is not activation authorization.

---

## Re-review of 894046e8 (2026-10-13)

Scope: `git diff d5e76d60..894046e8` (11 files). Read-only; local run of the two test files with `--noconftest`: **160 passed**; py_compile, ruff, `validate_project_memory.py` and the PowerShell parser (0 errors in all 7 scripts) are clean. Nothing was executed against Docker, and CI was not run.

- **P1-1 - met.** All seven call sites (`start_docker`, `start_dev`, `start_public`, `mobile_qa_runtime`, `product_restore_rehearsal`, `staging_update`, `staging_8000_deploy`) now set `$global:LASTEXITCODE = 1` on the line before the call and run python only inside `if (Get-Command python -ErrorAction SilentlyContinue)`; the else branch leaves the code at 1, so a missing interpreter is a refusal, and each script checks the code right after (`Get-Command` does not alter it; in `product_restore_rehearsal.ps1` the code is read on the next line). The :8000 change in `staging_8000_deploy.ps1` is only that guard (2 insertions, 1 deletion around the same `--no-stop` call); publish, env and rollback are untouched. The new parametrized test `test_every_powershell_call_site_fails_closed_without_python` fails if the reset line, the `Get-Command` guard or the exit-code check is removed (it asserts the line directly before the call and the guard text on the call line). Its "code is checked after" assertion is loose (any `$LASTEXITCODE` within five lines); acceptable.
- **P2-1 - met.** `stop()` returns "" on success or a reason for non-zero exit, timeout or OSError; `main` prints `STOP FAILED ... may still be publishing ... stop it by hand` and returns **4**, and prints "Stopped container" only on success. Tests cover success, non-zero, timeout and OSError, and assert "Stopped" never appears on failure. Every launcher treats any non-zero code as a refusal (exit 4 included).
- **P2-2 - left documented** in SECURITY_BOUNDARY.md (Ctrl+C after `watch` is not a clean stop). Remaining P2-3 to P2-6 stay tracked; D-18X must still be renumbered at merge.

### Final verdict: APPROVED

No remaining condition. **Approved head for merge: 894046e8** (script, launchers, tests and docs are exactly this SHA; later commits may touch this review file only). Not product approval and not activation authorization.
