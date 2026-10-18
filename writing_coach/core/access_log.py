"""Request log without query strings (deploy audit B4, 2026-10-18).

uvicorn's own access log prints the full request target, so `/auth/google/callback?state=..&code=..` reached
`docker logs`. The Dockerfile now starts uvicorn with `--no-access-log`; `log_request` writes the one line operators
need (method, path, status, duration) and never the query string. The same scrub is installed as a filter on
`uvicorn.access`, so a runtime started without the flag still cannot print a query.
"""

from __future__ import annotations

import logging
import re
import sys

ACCESS_LOGGER = "orena.access"


def strip_query(target: str) -> str:
    """The request target without its query string or fragment."""

    return str(target).split("?", 1)[0].split("#", 1)[0]


class QueryStringScrubFilter(logging.Filter):
    """Rewrites a uvicorn access record (client, method, target, version, status) so the target has no query."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            record.args = (*args[:2], strip_query(args[2]), *args[3:])
        return True


def configure_access_log() -> logging.Logger:
    """The access logger: its own stdout handler (the web loggers sit below the root level), idempotent."""

    logger = logging.getLogger(ACCESS_LOGGER)
    if not any(getattr(h, "_orena_access", False) for h in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler._orena_access = True  # type: ignore[attr-defined]
        handler.setFormatter(logging.Formatter("%(asctime)s access %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    uvicorn_access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, QueryStringScrubFilter) for f in uvicorn_access.filters):
        uvicorn_access.addFilter(QueryStringScrubFilter())
    return logger


def log_request(method: str, path: str, status: int, duration_ms: float) -> None:
    logging.getLogger(ACCESS_LOGGER).info("%s %s %d %.0fms", method, strip_query(path), status, duration_ms)


def scrub_url(url: str) -> str:
    """scheme://host/path of a URL: no userinfo, query or fragment (a feed or article URL may carry a token)."""

    from urllib.parse import urlsplit

    try:
        parts = urlsplit(str(url))
        host = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
    except ValueError:
        return "<unreadable url>"
    if not parts.scheme or not host:
        return strip_query(str(url))[:200]
    return f"{parts.scheme}://{host}{port}{parts.path}"


_URL_IN_TEXT = re.compile(r"https?://[^\s'\"<>)\]]+", re.IGNORECASE)


def scrub_text(text: str) -> str:
    """Every URL inside a message reduced to scheme://host/path (exception text often embeds the request URL)."""

    return _URL_IN_TEXT.sub(lambda found: scrub_url(found.group(0)), str(text))


def quiet_http_client_loggers() -> None:
    """httpx/httpcore/urllib3 print every outbound URL at INFO/DEBUG; a worker with root INFO must not show them."""

    for name in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)
