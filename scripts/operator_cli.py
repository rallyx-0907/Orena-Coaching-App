"""What the operator data CLIs share (PR BU): the actor rule, the database URL rule and the JSON report.

Each operator CLI (`media_reprocess.py`, `reading_relevel.py`, `reading_source_admin.py`, `vocab_correct_example.py`)
is a dry run unless `--apply` is given, writes only through existing application functions, requires `--actor` and
records it in the item's own trail, deletes nothing, and prints one JSON report with exact counts. None of them prints
a secret or a database URL: the URL comes from `--url` or `POSTGRES_RUNTIME_URL` and is only ever handed to SQLAlchemy.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Callable, Mapping
from typing import Any

# Who acted, as it is recorded beside the change: an e-mail, a name or a tag such as `hermes-for-owner`.
_ACTOR = re.compile(r"^[^\s\x00-\x1f][^\x00-\x1f]{0,158}$")
VIA_KEY = "via"


class OperatorRefused(Exception):
    """A stable, printable refusal: the CLI says why in its JSON and exits 2. Never carries a URL or a secret."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def require_actor(raw: str | None) -> str:
    actor = (raw or "").strip()
    if not actor or not _ACTOR.match(actor):
        raise OperatorRefused("actor_required", "pass --actor with who is acting (it is recorded with every change)")
    return actor


def database_url(raw: str | None) -> str:
    url = (raw or "").strip() or os.getenv("POSTGRES_RUNTIME_URL", "").strip()
    if not url:
        raise OperatorRefused("no_database", "pass --url or set POSTGRES_RUNTIME_URL")
    return url


def audit_recorder(engine: Any) -> Callable[..., None]:
    """`audit_logs`, through the repository the Admin routes record with (`AdminConsoleRepository.record_event`)."""
    from writing_coach.persistence.admin_repository import AdminConsoleRepository

    return AdminConsoleRepository(engine).record_event


def emit(report: Mapping[str, Any]) -> None:
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


def refused(script: str, error: OperatorRefused | Exception) -> int:
    if isinstance(error, OperatorRefused):
        emit({"script": script, "mode": "refused", "error": error.code, "detail": error.detail})
    else:  # the kind of failure only: a driver message can carry a host or a URL
        emit({"script": script, "mode": "refused", "error": type(error).__name__})
    return 2


def stderr(message: str) -> None:
    print(message, file=sys.stderr)
