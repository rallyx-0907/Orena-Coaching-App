"""Manual account deletion (PRE-502 R4; docs/project/ACCOUNT_DELETION_RUNBOOK.md). DESTRUCTIVE with --apply.

Dry run by default: a READ ONLY plan of what deleting one account removes, by table, with row counts. Nothing is changed.

    python -m scripts.account_deletion --email learner@example.com            # dry run (POSTGRES_RUNTIME_URL)
    python -m scripts.account_deletion --user-key <google sub>                 # the same, by sign-in key
    python -m scripts.account_deletion --email ... --apply                     # delete, in one transaction
    python -m scripts.account_deletion --email ... --apply --commerce keep     # when the account has commerce rows

Nobody applies it against a public runtime until the independent architecture review named in the runbook is
recorded in Git. The URL is never printed; prefer the environment variable to --url (shell history).
Exit codes: 0 done, 1 refused or failed (nothing changed), 2 bad input or no such account.
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    who = parser.add_mutually_exclusive_group(required=True)
    who.add_argument("--email")
    who.add_argument("--user-key")
    parser.add_argument("--apply", action="store_true", help="delete (default: dry run)")
    parser.add_argument("--commerce", choices=("delete", "keep"), default=None,
                        help="required with --apply when the account has commerce rows")
    parser.add_argument("--url", default=None, help="database URL; default POSTGRES_RUNTIME_URL")
    args = parser.parse_args(argv)
    url = args.url or os.environ.get("POSTGRES_RUNTIME_URL", "")
    if not url:
        print("no database URL: set POSTGRES_RUNTIME_URL or pass --url", file=sys.stderr)
        return 2
    import sqlalchemy

    from writing_coach.persistence.account_deletion import DeletionRefused, apply_plan, next_steps, plan_summary

    engine = sqlalchemy.create_engine(url, future=True)
    try:
        if not args.apply:
            summary = plan_summary(engine, email=args.email, user_key=args.user_key)
            if summary is None:
                print("no such account", file=sys.stderr)
                return 2
            print(json.dumps({"dry_run": True, "plan": summary}, ensure_ascii=False, indent=2))
            return 0
        try:
            plan = apply_plan(engine, email=args.email, user_key=args.user_key, commerce=args.commerce)
        except DeletionRefused as refused:
            print(f"refused, nothing changed: {refused}", file=sys.stderr)
            return 1 if str(refused) != "no such account" else 2
        print(json.dumps({"applied": True, "plan": plan.summary(), "next_steps": next_steps(plan.account.user_key)},
                         ensure_ascii=False, indent=2))
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
