# CI fast path

`.github/workflows/ci.yml` is the gate (`AGENTS.md` section 9). This note is how to work against it without
waiting on it for every tweak.

## While iterating: run only what you touched

Run these locally; none of them replaces CI.

- One Python test file or test: in the application image (see `AGENTS.md` section 9 for the full `docker run`),
  replace the pytest target, for example `python -m pytest -q -p no:cacheprovider tests/test_reading_library.py`
  or `-k <expression>`. Add `-n 3` (after `pip install pytest-xdist`) for several files.
- One or a few Node gates: `sh scripts/run_node_gates.sh scripts/test_orena_kit.mjs` (any listed gates; no
  arguments runs all of `scripts/node_gates.txt`, four at a time, `JOBS=8` for more).
- Project memory: `python scripts/validate_project_memory.py` and `python scripts/validate_architecture.py` (host,
  stdlib only, seconds).

Pick the tests by what you changed: the module's own tests, tests that import it (`grep -rl <module> tests`), and
the Node gate for the screen you edited. If unsure, run more, not fewer.

## Before you push: batch

Every push to a pull request starts a CI run (a newer push cancels the older one, but it still costs a run). Fix
several things locally, run the relevant checks above once, then push once.

## What CI does

- `python-gates`, `node-gates`, `pytest` and `docker-build` run concurrently; wall time is the slowest job.
- The required status check on `main` is the aggregate job `test`. It needs all the others and passes only if each
  succeeded (`docker-build` may be skipped on a Markdown-only change). A failed, cancelled or unexpectedly skipped
  job fails `test`.
- `pytest` uses pytest-xdist with `--dist loadfile`: a test file runs entirely on one worker. Each worker has its
  own SQLite files (`WRITING_DB`, `AUTH_DB`, `PLATFORM_DB`, `PRODUCT_DB`) and temp directory, set in `conftest.py`.
  A serial run (no `-n`) is unchanged.
- Parametrized test ids must be identical in every worker. Do not put `uuid4()`, timestamps or random values in
  `@pytest.mark.parametrize` values or ids; xdist aborts with "Different tests were collected".
- A test must not depend on files another test left, on a fixed port, or on a shared path outside `tmp_path`.
- A pull request that changes only `*.md` files runs the validators, the Node gates and only the test files that
  mention `docs/` or `.md`. Everything else, and every push to `main`, runs the complete suite.

## Not done on purpose: affected-tests-only on a PR

Running only the tests a diff "affects" would be faster again, but a selection that misses a dependency (dynamic
imports, JSON/data files, templates, fixtures, cross-module contracts) lets a regression reach `main` unseen. It
would only be acceptable beside a full run that still gates the merge. That is a policy change for the human.

## Pinned dependencies (D-242)

`constraints.txt` holds the exact `name==version` of the full resolved set of `requirements.txt` (transitive
dependencies included), resolved on the Dockerfile's base image (`python:3.12-slim`). The Dockerfile and the
`python-gates` and `pytest` CI jobs install with `-c constraints.txt`, so CI tests what ships and the image is rebuilt
identically. `python scripts/validate_constraints.py` (a `python-gates` step) fails if a `requirements.txt` package is
missing from it or a line is not an exact pin.

Update it only deliberately, in a reviewed PR that changes nothing else: in a throwaway `python:3.12-slim` container run
`pip install -r requirements.txt && pip freeze`, drop `pip`, `setuptools` and `wheel`, replace the pins, and let the
full CI run. A new package in `requirements.txt` needs its pin (and its dependencies') in the same PR.