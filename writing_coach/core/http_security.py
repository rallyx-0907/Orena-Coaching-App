"""Request integrity and response hardening for every route (security review, 2026-10-04).

Two small rules the whole app keeps, so no route has to remember them:

1. **A browser may change something only from this site.** A state-changing request (POST, PUT, PATCH,
   DELETE) under `/api/` or `/auth/` is refused when the browser says it came from somewhere else: an `Origin`
   whose host is not this request's host, an `Origin` of `null`, or - with no `Origin` - a
   `Sec-Fetch-Site` of `cross-site` or `same-site`. The session cookie is SameSite=Lax, which stops a
   cross-site form but not a sibling subdomain; this closes that. A request with neither header (a script, a
   test client, the native app's own exchange) is not a browser's cross-site request and passes, as it does
   for the admin console's own check, which stays the stricter one.
2. **Every response carries the hardening headers** a browser needs to refuse framing, MIME sniffing and
   referrer leaks, and HSTS once the site is served over HTTPS. A route that set its own value keeps it.
"""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlsplit

STATE_CHANGING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
GUARDED_PREFIXES = ("/api/", "/auth/")
# Callers that are not a browser page by design (the native app's code exchange).
EXEMPT_PATHS = frozenset({"/api/auth/native/exchange"})

HARDENING_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), geolocation=(), microphone=(self)",
}
HSTS = "max-age=31536000; includeSubDomains"


def origin_refusal(method: str, path: str, headers: Mapping[str, str]) -> str | None:
    """Why this request must be refused, or None. `headers` are the request's, lower-cased keys."""

    if method.upper() not in STATE_CHANGING or not path.startswith(GUARDED_PREFIXES) or path in EXEMPT_PATHS:
        return None
    origin = (headers.get("origin") or "").strip()
    host = (headers.get("host") or "").strip().casefold()
    if origin:
        if origin == "null":
            return "origin_null"
        try:
            netloc = urlsplit(origin).netloc.casefold()
        except ValueError:
            return "origin_unreadable"
        return None if netloc and netloc == host else "origin_mismatch"
    fetch_site = (headers.get("sec-fetch-site") or "").strip().casefold()
    if fetch_site in {"cross-site", "same-site"}:
        return "cross_site_request"
    return None


def hardening_headers(existing: Mapping[str, str], *, https: bool) -> dict[str, str]:
    """The headers to add: every hardening header the response does not already carry."""

    present = {key.casefold() for key in existing}
    added = {name: value for name, value in HARDENING_HEADERS.items() if name.casefold() not in present}
    if https and "strict-transport-security" not in present:
        added["Strict-Transport-Security"] = HSTS
    return added


# ---- a per-account brake on paid and heavy routes ----------------------------------------------------------
# Interim, per process (the agent's own limiter is the same kind): every AI-backed or upload route is limited
# per signed-in account until the per-account quota with its ledger (AC-2) is built. A limit is generous for a
# learner and stops a script looping a paid provider. Matched on the path prefix, state-changing methods only.

RATE_GROUPS: tuple[tuple[str, tuple[str, ...], int, int], ...] = (
    # (group, path prefixes, requests, window seconds)
    ("writing_ai", ("/api/evaluate", "/api/improve", "/api/translate", "/api/tasks/generate", "/api/practice/next"), 30, 600),
    ("essay_ai", ("/api/essays/",), 30, 600),
    ("dictionary_ai", ("/api/dictionary/",), 120, 600),
    ("speech_ai", ("/api/speech/transcribe", "/api/speech/pronunciation", "/api/speech/evaluation"), 60, 600),
    # On-demand Reading answers (a sentence's meaning, a summary): cached after the first, so a learner's own use
    # stays far below this; it only stops a script walking a corpus through the provider.
    ("reading_ai", ("/api/reading/translate", "/api/reading/summary"), 300, 600),
    ("media_learning", ("/api/media-learning/upload", "/api/media-learning/source", "/api/media-learning/translate",
                        "/api/media-learning/import#"), 30, 3600),
)


def rate_group(method: str, path: str) -> tuple[str, int, int] | None:
    if method.upper() not in STATE_CHANGING:
        return None
    for name, prefixes, limit, window in RATE_GROUPS:
        # A prefix ending in "#" matches that exact path only (`/import`, not its `/import/status` poll).
        exact = {prefix[:-1] for prefix in prefixes if prefix.endswith("#")}
        if path in exact or path.startswith(tuple(prefix for prefix in prefixes if not prefix.endswith("#"))):
            return name, limit, window
    return None
