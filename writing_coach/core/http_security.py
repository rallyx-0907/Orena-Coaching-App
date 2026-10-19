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

import base64
import hashlib
import ipaddress
import json
import logging
import os
import re
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

STATE_CHANGING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
GUARDED_PREFIXES = ("/api/", "/auth/")
# Machine endpoints that authenticate themselves (a gateway's signed event) and so need no browser origin even
# when a cookie happens to ride along. Nothing else is exempt.
MACHINE_PREFIXES = ("/api/billing/webhooks/",)
# The native app's code exchange (off by default, 404) has no browser origin and no session cookie by design.
EXEMPT_PATHS = frozenset({"/api/auth/native/exchange"})
SESSION_COOKIE = "writing_coach_session"

HARDENING_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), geolocation=(), microphone=(self)",
}
HSTS = "max-age=31536000; includeSubDomains"


def origin_refusal(method: str, path: str, headers: Mapping[str, str]) -> str | None:
    """Why this request must be refused, or None. `headers` are the request's, lower-cased keys."""

    if method.upper() not in STATE_CHANGING or not path.startswith(GUARDED_PREFIXES) or path in EXEMPT_PATHS or path.startswith(MACHINE_PREFIXES):
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
    if fetch_site:
        return None
    # Neither header: a script or a test client carries no session cookie and passes (its route has its own
    # credential, or none). A request that does carry the session cookie is a cookie-authenticated change and
    # must say where it came from.
    cookies = headers.get("cookie") or ""
    if any(part.strip().startswith(SESSION_COOKIE + "=") for part in cookies.split(";")):
        return "origin_missing"
    return None


CSP_REPORT_ONLY = "Content-Security-Policy-Report-Only"
_PAGES = Path(__file__).resolve().parents[2] / "templates" / "orena"
_INLINE_SCRIPT = re.compile(r"<script(?![^>]*src=)(?![^>]*type=\"text/x-dc\")[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)


@lru_cache(maxsize=1)
def inline_script_hashes() -> tuple[str, ...]:
    """CSP hashes of the executable inline <script> blocks the shipped pages carry (the legal pages' table of
    contents). Computed from the templates, so an edit to one cannot leave a stale hash behind."""

    found: set[str] = set()
    for page in sorted(_PAGES.rglob("*.html")):
        for match in _INLINE_SCRIPT.finditer(page.read_text(encoding="utf-8")):
            digest = hashlib.sha256(match.group(1).encode("utf-8")).digest()
            found.add("'sha256-" + base64.b64encode(digest).decode("ascii") + "'")
    return tuple(sorted(found))


CSP_ENFORCED = "Content-Security-Policy"
# The directives that never break a page we serve (no plugins, no <base>, no form posts to another origin, never
# framed). The full policy stays Report-Only until a browser sweep.
ENFORCED_DIRECTIVES = "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"


def content_security_policy_report_only() -> str:
    """The Report-Only policy for HTML pages (deploy audit B8, 2026-10-18); documented in RELEASE_8000_READINESS.md.

    'unsafe-eval' is there for the public Landing, whose design-component runtime (support.js) builds functions;
    'unsafe-inline' styles for the design's inline style attributes; https: images and media for covers and
    learner-imported content; the Polar checkout loads from cdn.jsdelivr.net. Enforcement is a follow-up."""

    scripts = " ".join(("'self'", "'unsafe-eval'", "https://cdn.jsdelivr.net", "https://www.youtube.com", *inline_script_hashes()))
    return "; ".join((
        "default-src 'self'",
        f"script-src {scripts}",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob: https:",
        "media-src 'self' blob: https:",
        "font-src 'self' data:",
        "connect-src 'self' wss://generativelanguage.googleapis.com",
        "worker-src 'self' blob:",
        "frame-src https://www.youtube.com https://www.youtube-nocookie.com https://*.polar.sh",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ))


def hardening_headers(existing: Mapping[str, str], *, https: bool) -> dict[str, str]:
    """The headers to add: every hardening header the response does not already carry."""

    present = {key.casefold() for key in existing}
    added = {name: value for name, value in HARDENING_HEADERS.items() if name.casefold() not in present}
    if https and "strict-transport-security" not in present:
        added["Strict-Transport-Security"] = HSTS
    content_type = next((v for k, v in existing.items() if k.casefold() == "content-type"), "")
    if content_type.casefold().startswith("text/html") and CSP_REPORT_ONLY.casefold() not in present:
        added[CSP_REPORT_ONLY] = content_security_policy_report_only()
        if CSP_ENFORCED.casefold() not in present:
            added[CSP_ENFORCED] = ENFORCED_DIRECTIVES
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
    # Consent answers (D-233): a learner answers a handful of times; each write is one row update, so this only stops a loop.
    ("consent", ("/api/account-settings/consent", "/api/account-settings/voice-consent"), 60, 600),
    # A learner's place in content (#323). Each write is one row UPDATE, and nothing else bounds them: `settle` (paused,
    # left) and a changed `segment` both write at once, so a script could force one per request. Real clients are
    # frequent: Listening writes on every transcript line (2-3 s auto-caption cues) and on every play/pause, and an
    # account's tabs and devices share this bucket - so the floor is one write per 0.5 s, sustained, which only a loop
    # reaches. A refused place write fails silently on the client (the device copy stays right), so err high.
    ("place", ("/api/continue/",), 1200, 600),
    ("media_learning", ("/api/media-learning/upload", "/api/media-learning/source", "/api/media-learning/translate",
                        "/api/media-learning/import#"), 30, 3600),
    # PRE-502 R3: AI-backed routes that were in no group. Each is generous for a learner (a word lookup about once a
    # second, sustained) and only stops one account looping a paid provider - which, with the system daily ceiling
    # shared by everyone, would otherwise pause AI for every learner until midnight.
    ("reading_lookup", ("/api/reading/lookup#",), 600, 600),
    ("media_explain", ("/api/media-learning/explain#",), 120, 600),
    ("discussion_ai", ("/api/texts/discussion/turns#",), 60, 600),
    # A model reference line with no canonical timings asks the pronunciation provider (cached afterwards).
    ("speaking_reference", ("/api/speaking/model-reference/",), 300, 600),
)

# Reads that can reach a paid provider (PRE-502 R3): counted although a GET changes nothing. Exact paths only.
# `/api/dictionary` falls back to the AI dictionary for Chinese on a cache miss.
READ_RATE_GROUPS: tuple[tuple[str, frozenset[str], int, int], ...] = (
    ("dictionary_lookup", frozenset({"/api/dictionary"}), 600, 600),
)
# Reads with an id in the path, matched by (prefix, suffix): a word's audio, which may synthesise speech on a cache miss
# (behind a shared spend cap), and its deep explanation, which may call the model on a cache miss.
READ_RATE_PATTERNS: tuple[tuple[str, str, str, int, int], ...] = (
    ("word_audio", "/api/library/vocabulary/", "/audio", 600, 600),
    ("word_deep", "/api/library/vocabulary/", "/deep", 300, 600),
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
    if method.upper() == "GET":
        bare = path.rstrip("/")
        for name, paths, limit, window in READ_RATE_GROUPS:
            if bare in paths:
                return name, limit, window
        for name, prefix, suffix, limit, window in READ_RATE_PATTERNS:
            if bare.startswith(prefix) and bare.endswith(suffix) and len(bare) > len(prefix) + len(suffix):
                return name, limit, window
        return None
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


# ---- a global request body cap ------------------------------------------------------------------------------
# Every state-changing /api/ or /auth/ request is limited to DEFAULT_BODY_LIMIT; the upload routes below carry
# their own, at their existing per-file caps (times the files a request may hold). Enforced on the declared
# Content-Length and again on the bytes actually received (a chunked body declares nothing).

DEFAULT_BODY_LIMIT = 2 * 1024 * 1024
_MIB = 1024 * 1024
UPLOAD_BODY_LIMITS: tuple[tuple[str, int], ...] = (
    # (path prefix, bytes)
    ("/api/admin/console/imports/books", 256 * _MIB),  # EPUB, 80 MiB each
    ("/api/admin/console/imports/media-upload", 256 * _MIB),  # media, 64 MiB each
    ("/api/admin/content-packs/", 64 * _MIB),  # pack, 50 MiB
    ("/api/admin/grammar/imports", 40 * _MIB),  # grammar package, 32 MiB
    ("/api/admin/reading/jobs", 40 * _MIB),
    ("/api/admin/vocabulary/", 128 * _MIB),  # source files, 25 MiB each
    ("/api/reading/library/import", 256 * _MIB),  # EPUB, 80 MiB each
    ("/api/media-learning/upload", 96 * _MIB),  # media, 64 MiB
    ("/api/media/admin/upload", 256 * _MIB),
    ("/api/speech/transcribe", 32 * _MIB),  # recording, operator-set cap up to 24 MiB
    ("/api/speech/pronunciation", 16 * _MIB),  # recording, 8 MiB by default; see pronunciation_body_limit
)
_PRONUNCIATION_PATH = "/api/speech/pronunciation"
_PRONUNCIATION_MAX_BYTES_ENV = ("AZURE_PRONUNCIATION_MAX_BYTES", "DEMO_PRONUNCIATION_MAX_BYTES")
_PRONUNCIATION_FORM_OVERHEAD = _MIB  # the reference text and multipart framing beside the recording


def pronunciation_body_limit() -> int:
    """The pronunciation route's body cap: the 16 MiB default, or more when an operator raised a provider's
    `*_PRONUNCIATION_MAX_BYTES`, so the request boundary never refuses a recording the provider would accept."""
    limit = dict(UPLOAD_BODY_LIMITS)[_PRONUNCIATION_PATH]
    for name in _PRONUNCIATION_MAX_BYTES_ENV:
        try:
            configured = int(os.environ.get(name) or 0)
        except ValueError:
            continue
        limit = max(limit, configured + _PRONUNCIATION_FORM_OVERHEAD)
    return limit


def body_limit(method: str, path: str) -> int | None:
    """The largest body this request may carry, or None when the cap does not apply (reads, other prefixes)."""
    if method.upper() not in STATE_CHANGING or not path.startswith(GUARDED_PREFIXES):
        return None
    for prefix, limit in UPLOAD_BODY_LIMITS:
        if path.startswith(prefix):
            return pronunciation_body_limit() if prefix == _PRONUNCIATION_PATH else limit
    return DEFAULT_BODY_LIMIT


class BodyTooLarge(Exception):
    pass


class BodyLimitMiddleware:
    """Pure ASGI middleware: 413 before a route reads an oversized body."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        limit = body_limit(scope.get("method", ""), scope.get("path", "")) if scope.get("type") == "http" else None
        if limit is None:
            await self.app(scope, receive, send)
            return
        declared = next((v for k, v in scope.get("headers", ()) if k == b"content-length"), None)
        try:
            too_big = declared is not None and int(declared) > limit
        except ValueError:
            too_big = False
        if too_big:
            await self._refuse(send)
            return
        received = 0
        started = False
        refused = False

        async def counted_receive():
            nonlocal received, refused
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit and not started:
                    # Answer now: the framework would turn the exception below into a 500 first.
                    refused = True
                    await self._refuse(send)
                    raise BodyTooLarge
            return message

        async def tracking_send(message):
            nonlocal started
            if refused:
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counted_receive, tracking_send)
        except Exception:
            if not refused:
                raise

    @staticmethod
    async def _refuse(send):
        from writing_coach.core.errors import error_detail

        body = json.dumps({"detail": error_detail("body_too_large", "This request is larger than Orena accepts.",
                                                  retryable=False)}).encode("utf-8")
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
