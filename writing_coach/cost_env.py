"""Which Orena environment recorded a cost event (D-221, PROPOSED).

One provider key is spent from many places: the staging and preview runtimes, the sandboxes, other agent lanes and
scripts. Every environment records into its own database and its own media ledger, so a provider's console bill
(the sum over all of them) can never match one environment's cost page. Each cost event therefore carries a short
label of the environment that wrote it, and the cost page shows which environment it is reading.

The label is, in order: `ORENA_ENV_LABEL` (an operator's explicit name), `ORENA_ENVIRONMENT_LABEL` (the content-pack
export's name, when set), the host and port of `PUBLIC_BASE_URL` (a sandbox is told apart by its port), then
`APP_ENV`. It is never a secret and never learner data: a short lowercase token, or `unknown`.
"""
from __future__ import annotations

import os
import re
from collections.abc import Mapping
from urllib.parse import urlsplit

UNKNOWN = "unknown"
PATTERN = re.compile(r"[a-z0-9][a-z0-9._:-]{0,39}")


def _token(value: object) -> str | None:
    text = str(value or "").strip().casefold()
    return text if PATTERN.fullmatch(text) else None


def label(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env
    for name in ("ORENA_ENV_LABEL", "ORENA_ENVIRONMENT_LABEL"):
        token = _token(source.get(name))
        if token:
            return token
    try:
        parts = urlsplit(str(source.get("PUBLIC_BASE_URL") or "").strip())
        host = (parts.hostname or "").casefold()
        port = f":{parts.port}" if parts.port else ""
    except ValueError:
        host, port = "", ""
    token = _token(f"{host}{port}") if host else None
    return token or _token(source.get("APP_ENV")) or UNKNOWN
