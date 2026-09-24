"""The canonical Reading cutover (D-075, D-076) - admin sandbox only.

Four read-mostly steps around `alembic upgrade 20260924_0014`, for the
operator who runs it:

    python scripts/reading_canonical_cutover.py target --confirm-sandbox <database>
    python scripts/reading_canonical_cutover.py inventory --confirm-sandbox <database>
    python scripts/reading_canonical_cutover.py status --confirm-sandbox <database>
    python scripts/reading_canonical_cutover.py reset-legacy --confirm-sandbox <database> \\
        --expect-cluster <system identifier> --expect-sessions N --expect-attempts M

`target` names the database it would touch (password redacted) and the
PostgreSQL cluster behind it, and refuses production and preview. `inventory` is the archive query of
`ADAPTIVE_READING_SCHEMA_PROPOSAL.md` §1, before or after the upgrade (it reads
whichever names the database has), with a *hint* per account of whether it
looks like test or development data - never a decision. `status` reports the
revision, the canonical Reading tables' row counts and the triggers.

`reset-legacy` empties the legacy archive, and only when the human has seen
the inventory and decided it is test or development data (D-076): it refuses
unless the counts it finds are exactly the counts passed, so it can only
delete what was reported. Text discussions keep their rows and lose the link
(`ON DELETE SET NULL`). Meaningful learner history is kept read-only instead:
do not run this for it.

The database is `--url`, or `POSTGRES_RUNTIME_URL`. Run inside the sandbox
application container so that its environment is the one checked. The target
is refused unless every one of these holds, so no single mistake - a pasted
URL, an inherited environment, the wrong container - reaches production:

* `APP_ENV` is not production, and neither `PUBLIC_BASE_URL` nor `--app-url` is
  on port 8000 (production) or 8010 (preview);
* the URL is not production's: neither the host nor the database of the
  production compose default (`compose.yaml`, parity-tested);
* `--confirm-sandbox` names the database, the URL names the same one, and the
  server, once connected, says it is that database;
* `reset-legacy` - the one command that deletes - is also pinned to the
  PostgreSQL cluster `target` printed (`--expect-cluster`, the cluster's
  `system_identifier`), so it deletes only in the cluster the operator looked
  at.

Nothing here prints a secret.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REFUSED_PORTS = {8000, 8010}
# The production runtime's database, as `compose.yaml` defaults it
# (`POSTGRES_RUNTIME_URL`): its host and database are refused by name.
# `tests/test_reading_canonical_cutover_scripts.py` keeps these equal to it.
PRODUCTION_HOST = "postgres"
PRODUCTION_DATABASE = "becoming"
TEST_KEYS = {"legacy", "local-admin", "sandbox-learner"}
TEST_EMAIL_SUFFIXES = (".invalid", "@example.com", "@example.org", "@localhost")

INVENTORY = """
SELECT u.user_key, u.email, u.role, u.created_at AS account_created,
       s.language_code, count(DISTINCT s.id) AS sessions,
       count(a.id) AS attempts, min(s.created_at) AS first_at, max(s.created_at) AS last_at
  FROM {sessions} s
  JOIN users u ON u.id = s.user_id
  LEFT JOIN {attempts} a ON a.session_id = s.id
 GROUP BY u.user_key, u.email, u.role, u.created_at, s.language_code
 ORDER BY max(s.created_at) DESC
"""


def redacted(url: str) -> str:
    parsed = urlparse(url)
    if parsed.password:
        netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
        parsed = parsed._replace(netloc=netloc)
    return urlunparse(parsed)


def _port(url: str) -> int | None:
    try:
        return urlparse(url).port
    except ValueError:
        return None


def database_name(url: str) -> str:
    return urlparse(url).path.lstrip("/")


def refusal(*, url: str, app_url: str, environ: dict[str, str], confirmed: str = "") -> str | None:
    """Why this target is not the admin sandbox, or None when it may be.
    Static - nothing is connected to here; `identity_refusal` checks what the
    server itself says."""
    if not url:
        return "no database: pass --url or set POSTGRES_RUNTIME_URL"
    parsed = urlparse(url)
    if not parsed.scheme.startswith("postgresql"):
        return "the runtime is PostgreSQL; this is not a PostgreSQL URL"
    if (parsed.hostname or "").casefold() == PRODUCTION_HOST or database_name(url) == PRODUCTION_DATABASE:
        return (f"that is the production runtime's database ({PRODUCTION_HOST}/{PRODUCTION_DATABASE}, the "
                "compose default): this authorization is for the admin sandbox only (D-076)")
    if not confirmed:
        return f"pass --confirm-sandbox <database> naming the sandbox's database ({redacted(url)})"
    if confirmed != database_name(url):
        return (f"--confirm-sandbox names {confirmed!r} but the URL is database {database_name(url)!r}: "
                "nothing was touched")
    if str(environ.get("APP_ENV", "")).strip().casefold() == "production":
        return "APP_ENV is production: this authorization is for the admin sandbox only (D-076)"
    for name, value in (("PUBLIC_BASE_URL", environ.get("PUBLIC_BASE_URL", "")), ("--app-url", app_url)):
        if value and _port(value) in REFUSED_PORTS:
            return f"{name} is on port {_port(value)} - production (8000) and preview (8010) keep every gate"
    return None


def identity(url: str) -> dict[str, str]:
    """What the server says it is: the database, and the cluster behind it
    (`system_identifier`, fixed when the cluster was created - another
    container, or a restore into another cluster, has a different one)."""
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    engine = _engine(url)
    try:
        with engine.connect() as connection:
            found = {"database": str(connection.execute(text("SELECT current_database()")).scalar_one()),
                     "cluster": ""}
            try:
                found["cluster"] = str(connection.execute(
                    text("SELECT system_identifier FROM pg_control_system()")).scalar_one())
            except DBAPIError:
                pass  # not readable by this role: `reset-legacy` then refuses
    finally:
        engine.dispose()
    return found


def identity_refusal(found: dict[str, str], *, confirmed: str, expect_cluster: str | None) -> str | None:
    """Why the connected server is not the one confirmed, or None."""
    if found.get("database") != confirmed:
        return (f"connected to database {found.get('database')!r}, not the confirmed {confirmed!r}: "
                "nothing was touched")
    if expect_cluster is not None:
        if not found.get("cluster"):
            return "this role cannot read the cluster's system identifier, so it cannot be pinned: nothing deleted"
        if found["cluster"] != expect_cluster.strip():
            return (f"the cluster is {found['cluster']}, not the {expect_cluster.strip()} `target` reported: "
                    "nothing was touched")
    return None


def mask_email(email: str) -> str:
    local, _, domain = str(email or "").partition("@")
    if not domain:
        return "" if not local else f"{local[:1]}•••"
    return f"{local[:1]}•••@{domain}"


def looks_like_test(user_key: str, email: str) -> bool:
    email = str(email or "").casefold()
    return user_key in TEST_KEYS or email == "" or email.endswith(TEST_EMAIL_SUFFIXES)


def _engine(url: str):
    from sqlalchemy import create_engine

    return create_engine(url, future=True)


def _tables(connection) -> set[str]:
    from sqlalchemy import inspect

    return set(inspect(connection).get_table_names())


def _names(tables: set[str]) -> tuple[str, str] | None:
    if {"reading_legacy_sessions", "reading_legacy_attempts"} <= tables:
        return "reading_legacy_sessions", "reading_legacy_attempts"
    if {"reading_sessions", "reading_attempts"} <= tables and "reading_comprehension_sets" not in tables:
        return "reading_sessions", "reading_attempts"
    return None


def inventory(url: str) -> int:
    from sqlalchemy import text

    engine = _engine(url)
    with engine.connect() as connection:
        names = _names(_tables(connection))
        if names is None:
            print("No legacy Reading tables in this database: nothing to inventory.")
            return 0
        sessions, attempts = names
        rows = connection.execute(text(INVENTORY.format(sessions=sessions, attempts=attempts))).all()
        totals = connection.execute(text(
            f"SELECT (SELECT count(*) FROM {sessions}), (SELECT count(*) FROM {attempts})")).one()
        orphans = connection.execute(text(
            f"SELECT count(*) FROM {sessions} s LEFT JOIN users u ON u.id = s.user_id WHERE u.id IS NULL")).scalar_one()
        discussions = 0
        if "text_discussions" in _tables(connection):
            discussions = connection.execute(text(
                "SELECT count(*) FROM text_discussions WHERE reading_session_id IS NOT NULL")).scalar_one()
    engine.dispose()
    print(f"Legacy Reading archive ({sessions} / {attempts})")
    print(f"  sessions {totals[0]}, attempts {totals[1]}, accounts {len({row.user_key for row in rows})}, "
          f"sessions with no account row {orphans}, text discussions linked {discussions}")
    if not rows:
        print("  empty")
        return 0
    print("  account (masked)                  role   language  sessions  attempts  first -> last            looks like")
    all_test = True
    for row in rows:
        test = looks_like_test(row.user_key, row.email)
        all_test = all_test and test
        who = f"{row.user_key[:10]}… {mask_email(row.email)}" if len(row.user_key) > 10 else \
            f"{row.user_key} {mask_email(row.email)}"
        print(f"  {who:<34} {row.role:<6} {row.language_code:<9} {row.sessions:>8}  {row.attempts:>8}  "
              f"{str(row.first_at)[:10]} -> {str(row.last_at)[:10]}  {'test/dev' if test else 'LEARNER?'}")
    print()
    print("  hint: " + ("every account looks like test or development data" if all_test else
                        "some accounts may be real learners - keep their history read-only"))
    print("  The decision is the human's (D-076). To reset test data only after reporting this:")
    print(f"  reset-legacy --confirm-sandbox {database_name(url)} --expect-cluster <from target> "
          f"--expect-sessions {totals[0]} --expect-attempts {totals[1]}")
    return 0


def status(url: str) -> int:
    from sqlalchemy import text

    engine = _engine(url)
    with engine.connect() as connection:
        tables = _tables(connection)
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none() \
            if "alembic_version" in tables else None
        print(f"revision {revision}")
        for table in ("reading_articles", "reading_comprehension_sets", "reading_comprehension_questions",
                      "reading_attempts", "reading_ability_projections", "reading_legacy_sessions",
                      "reading_legacy_attempts"):
            count = connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() \
                if table in tables else "absent"
            print(f"  {table:<34} {count}")
        if connection.dialect.name == "postgresql":
            triggers = connection.execute(text(
                "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
                "WHERE NOT t.tgisinternal AND c.relname LIKE 'reading_%'")).scalar_one()
            print(f"  reading lifecycle triggers         {triggers}")
    engine.dispose()
    return 0


def reset_legacy(url: str, *, expect_sessions: int, expect_attempts: int) -> int:
    from sqlalchemy import text

    engine = _engine(url)
    with engine.begin() as connection:
        if _names(_tables(connection)) != ("reading_legacy_sessions", "reading_legacy_attempts"):
            print("refused: the legacy archive exists only after 20260924_0014 is applied")
            return 2
        connection.execute(text(
            "LOCK TABLE reading_legacy_sessions, reading_legacy_attempts IN SHARE ROW EXCLUSIVE MODE"))
        found = connection.execute(text(
            "SELECT (SELECT count(*) FROM reading_legacy_sessions), (SELECT count(*) FROM reading_legacy_attempts)"
        )).one()
        if tuple(found) != (expect_sessions, expect_attempts):
            print(f"refused: the archive holds {found[0]} sessions / {found[1]} attempts, not the "
                  f"{expect_sessions} / {expect_attempts} the inventory reported. Run inventory again.")
            return 2
        # Attempts cascade from their sessions; discussions keep their rows.
        connection.execute(text("DELETE FROM reading_legacy_sessions"))
        left = connection.execute(text("SELECT count(*) FROM reading_legacy_attempts")).scalar_one()
        if left:
            raise SystemExit(f"refused: {left} legacy attempts had no session; nothing was deleted")
    engine.dispose()
    print(f"Legacy archive reset: {expect_sessions} sessions and {expect_attempts} attempts removed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("command", choices=("target", "inventory", "status", "reset-legacy"))
    parser.add_argument("--url", default="", help="defaults to POSTGRES_RUNTIME_URL")
    parser.add_argument("--app-url", default="", help="the sandbox's base URL, checked against 8000 / 8010")
    parser.add_argument("--confirm-sandbox", default="", metavar="DATABASE",
                        help="required: the admin sandbox's database name (D-076)")
    parser.add_argument("--expect-cluster", default=None, metavar="SYSTEM_IDENTIFIER",
                        help="reset-legacy: the cluster `target` printed")
    parser.add_argument("--expect-sessions", type=int)
    parser.add_argument("--expect-attempts", type=int)
    args = parser.parse_args(argv)
    url = args.url or os.getenv("POSTGRES_RUNTIME_URL", "")
    reason = refusal(url=url, app_url=args.app_url, environ=dict(os.environ), confirmed=args.confirm_sandbox)
    if reason:
        print(f"refused: {reason}")
        return 2
    if args.command == "reset-legacy" and not args.expect_cluster:
        print("refused: reset-legacy needs --expect-cluster, the system identifier `target` printed")
        return 2
    found = identity(url)
    reason = identity_refusal(found, confirmed=args.confirm_sandbox,
                              expect_cluster=args.expect_cluster if args.command == "reset-legacy" else None)
    if reason:
        print(f"refused: {reason}")
        return 2
    if args.command == "target":
        print(f"target {redacted(url)}")
        print(f"database {found['database']}  cluster {found['cluster'] or '(not readable by this role)'}")
        print(f"APP_ENV={os.getenv('APP_ENV', '')!r} PUBLIC_BASE_URL={os.getenv('PUBLIC_BASE_URL', '')!r}")
        return 0
    if args.command == "inventory":
        return inventory(url)
    if args.command == "status":
        return status(url)
    if args.expect_sessions is None or args.expect_attempts is None:
        print("refused: reset-legacy needs --expect-sessions and --expect-attempts from the inventory")
        return 2
    return reset_legacy(url, expect_sessions=args.expect_sessions, expect_attempts=args.expect_attempts)


if __name__ == "__main__":
    raise SystemExit(main())
