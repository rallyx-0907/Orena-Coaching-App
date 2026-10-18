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

import ipaddress
import logging
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


# The request count of each group is operator policy (Platform Admin, D-172); the tuple above holds the defaults and
# the window. A group not named here keeps its tuple.
RATE_POLICY_KEYS: dict[str, str] = {
    "writing_ai": "rate.writing_ai_per_10min",
    "essay_ai": "rate.essay_ai_per_10min",
    "dictionary_ai": "rate.dictionary_ai_per_10min",
    "speech_ai": "rate.speech_ai_per_10min",
    "reading_ai": "rate.reading_ai_per_10min",
    "media_learning": "rate.media_learning_per_hour",
}


def _effective_limit(name: str, limit: int) -> int:
    key = RATE_POLICY_KEYS.get(name)
    if key is None:
        return limit
    from writing_coach import policies

    return int(policies.value(key))


def rate_group(method: str, path: str) -> tuple[str, int, int] | None:
    """(group, requests, window seconds) of the group this request counts against, with the requests the effective
    policy allows now."""
    found = _rate_group(method, path)
    if found is None:
        return None
    name, limit, window = found
    return name, _effective_limit(name, limit), window


# Routes inside a counted prefix that count themselves, because only their body says whether a request is AI-backed:
# word-detail is deterministic unless it carries a contextual ask (writing_coach/word_detail.py counts that one).
SELF_COUNTED_PATHS = frozenset({"/api/dictionary/word-detail"})


def _rate_group(method: str, path: str) -> tuple[str, int, int] | None:
    if method.upper() not in STATE_CHANGING or path.rstrip("/") in SELF_COUNTED_PATHS:
        return None
    for name, prefixes, limit, window in RATE_GROUPS:
        # A prefix ending in "#" matches that exact path only (`/import`, not its `/import/status` poll).
        exact = {prefix[:-1] for prefix in prefixes if prefix.endswith("#")}
        if path in exact or path.startswith(tuple(prefix for prefix in prefixes if not prefix.endswith("#"))):
            return name, limit, window
    return None


# ---- a per-client-IP brake on sign-in (open-public readiness item d) ----------------------------------------------
# The sign-in start and callback are GETs and the native exchange carries no session, so the per-account groups above
# never see them. They are limited per client address instead; the count of each is operator policy (Platform Admin).
# The answer is the same 429 the per-account groups give, whatever the account: no limit message says who exists.

SIGNIN_GROUPS: tuple[tuple[str, str, frozenset[str], int, int], ...] = (
    # (group, policy key, (method, path) pairs as "METHOD path", default requests, window seconds)
    ("signin_start", "rate.signin_start_per_10min", frozenset({"GET /auth/google"}), 120, 600),
    ("signin_callback", "rate.signin_callback_per_10min", frozenset({"GET /auth/google/callback"}), 200, 600),
    ("signin_exchange", "rate.signin_exchange_per_10min", frozenset({"POST /api/auth/native/exchange"}), 200, 600),
)


def signin_group(method: str, path: str) -> tuple[str, int, int] | None:
    """(group, requests the effective policy allows now, window seconds) for a sign-in request, or None."""
    from writing_coach import policies

    request_key = f"{method.upper()} {path.rstrip('/') or '/'}"
    for name, policy_key, requests, default, window in SIGNIN_GROUPS:
        if request_key in requests:
            try:
                limit = int(policies.value(policy_key))
            except Exception:
                limit = default
            return name, limit, window
    return None


def _ip(value: object) -> str | None:
    try:
        address = ipaddress.ip_address(str(value or "").strip())
    except ValueError:
        return None
    mapped = getattr(address, "ipv4_mapped", None)
    return str(mapped if mapped is not None else address)


def client_address(peer: object, headers: Mapping[str, str]) -> str:
    """The address a sign-in request counts against.

    The transport peer is the truth. Only when that peer is itself a non-public (private, loopback, link-local) hop (the
    Cloudflare tunnel's connector, Docker's port proxy) is `CF-Connecting-IP` read, because only then is it set by the
    edge and not by the caller; a directly connected public peer cannot choose its own key. `X-Forwarded-For` is
    never read: any client can write it. With no usable address the key is a single shared "unknown" bucket, which
    fails closed rather than open."""
    # Trusting a non-public peer assumes the app port is bound to loopback / reached only through the tunnel (so a
    # caller cannot be the "private hop" itself), and that uvicorn's FORWARDED_ALLOW_IPS is never set to "*".
    direct = _ip(peer)
    if direct is None:
        return "unknown"
    address = ipaddress.ip_address(direct)
    if not address.is_global:
        edge = _ip(headers.get("cf-connecting-ip"))
        if edge is not None:
            return edge
        _warn_shared_bucket_once(direct)
    return direct


_WARNED_SHARED_BUCKET: list[bool] = []


def _warn_shared_bucket_once(peer: str) -> None:
    """A non-public peer with no edge address means every caller shares one sign-in bucket: say so once per process."""
    if _WARNED_SHARED_BUCKET:
        return
    _WARNED_SHARED_BUCKET.append(True)
    logging.getLogger("orena.request_boundary").warning(
        "sign-in rate limit: a non-public peer (%s) arrived without CF-Connecting-IP, so callers behind it share one "
        "bucket; check the tunnel / proxy configuration", peer)
