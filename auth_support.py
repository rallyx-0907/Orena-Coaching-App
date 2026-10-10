import hashlib
import base64
import json
import os
import secrets
import shutil
import time
from pathlib import Path
from threading import Lock
from typing import Any
from collections.abc import Callable
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token as google_id_token
from google_auth_oauthlib.flow import Flow
from itsdangerous import TimestampSigner
from pydantic import BaseModel, StrictStr
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX, current_language_code
from writing_coach.core.storage import resolve_language_db_path
from writing_coach.core.language_registry import DEFAULT_LANGUAGE, all_languages, enabled_language
from writing_coach.core.deployment import DeploymentConfig, resolve_deployment_config
from writing_coach import account_settings
from writing_coach.persistence.auth_repository import AuthRepository

ROOT = Path(__file__).resolve().parent
LEGACY_DB_PATH = Path(os.getenv("WRITING_DB", ROOT / "data" / "writing.db"))
AUTH_DB_PATH = Path(os.getenv("AUTH_DB", LEGACY_DB_PATH.parent / "auth.db"))
USER_DATA_ROOT = Path(os.getenv("USER_DATA_ROOT", LEGACY_DB_PATH.parent / "users"))

DEPLOYMENT: DeploymentConfig = resolve_deployment_config()
APP_ENV = DEPLOYMENT.app_env
PUBLIC_BASE_URL = DEPLOYMENT.public_base_url
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_REDIRECT_URI = DEPLOYMENT.google_redirect_uri
SESSION_SECRET = os.getenv("SESSION_SECRET", "").strip()
BOOTSTRAP_OWNER_EMAIL = os.getenv("BOOTSTRAP_OWNER_EMAIL", "").strip().casefold()
PLATFORM_ADMIN_EMAILS = {
    x.strip().casefold()
    for x in os.getenv("PLATFORM_ADMIN_EMAILS", "").split(",")
    if x.strip()
}
if BOOTSTRAP_OWNER_EMAIL:
    PLATFORM_ADMIN_EMAILS.add(BOOTSTRAP_OWNER_EMAIL)

AUTH_ENABLED = DEPLOYMENT.auth_enabled
COOKIE_SECURE = DEPLOYMENT.cookie_secure
SESSION_BOOTSTRAP_VERSION = "orena.session-bootstrap.v1"
NATIVE_SESSION_VERSION = "orena.native-session.v1"
NATIVE_REDIRECT_URI = "orena://auth/callback"
NATIVE_HANDOFF_TTL_SECONDS = 300

if AUTH_ENABLED and GOOGLE_REDIRECT_URI.startswith("http://"):
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

_user_key = USER_KEY_CTX
_language_key = LANGUAGE_CODE_CTX
_db_initializer: Callable[[], None] | None = None
_initialized_user_dbs: set[str] = set()
_native_handoffs: dict[str, tuple[str, float, str]] = {}
_native_handoff_lock = Lock()


def user_db_path(
    user_key: str,
    legacy_db: Path | None = None,
    language_code: str | None = None,
) -> Path:
    legacy_db = legacy_db or LEGACY_DB_PATH
    lang = enabled_language(language_code or current_language_code()).db_namespace or DEFAULT_LANGUAGE
    return resolve_language_db_path(
        user_key=user_key,
        language_code=lang,
        legacy_db=legacy_db,
        user_data_root=USER_DATA_ROOT,
        auth_enabled=AUTH_ENABLED,
    )


def current_db_path(legacy_db: Path | None = None) -> Path:
    return user_db_path(
        _user_key.get(),
        legacy_db=legacy_db,
        language_code=_language_key.get(),
    )

_auth_repository: AuthRepository | None = None

def _installed_auth_repository() -> AuthRepository:
    if _auth_repository is None:
        raise RuntimeError("Auth repository has not been installed by the persistence runtime.")
    return _auth_repository

def configure_auth_repository(repository: AuthRepository) -> None:
    global _auth_repository
    _auth_repository = repository


def init_auth_db() -> None:
    _installed_auth_repository().initialize(PLATFORM_ADMIN_EMAILS)


def auth_user(google_sub: str) -> dict[str, Any] | None:
    return _installed_auth_repository().get_user(google_sub)


def upsert_auth_user(info: dict[str, Any]) -> dict[str, Any]:
    try:
        return _installed_auth_repository().upsert_user(info, PLATFORM_ADMIN_EMAILS)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def _local_admin_allowed(environ: Any = None) -> bool:
    """Signed-out "local developer" admin is for a machine's own address only (security review 2026-10-04).

    With authentication off, every visitor used to be an administrator outside production. A deployment whose
    public address is not this machine's (a domain, a LAN address) - or one that only forgot APP_ENV - now
    gets no admin at all, unless the operator says ALLOW_LOCAL_ADMIN=1 on purpose. A public runtime (staging or
    production, D-146) never has one, whatever ALLOW_LOCAL_ADMIN says."""

    from urllib.parse import urlsplit

    from writing_coach.core.deployment import is_public_environment

    values = os.environ if environ is None else environ
    if is_public_environment(values.get("APP_ENV")):
        return False
    if str(values.get("ALLOW_LOCAL_ADMIN", "")).strip().casefold() in {"1", "true", "yes", "on"}:
        return True
    base = str(values.get("PUBLIC_BASE_URL", "")).strip()
    host = (urlsplit(base).hostname or "") if base else "localhost"
    return host in {"localhost", "127.0.0.1", "::1"}


LOCAL_ADMIN_ALLOWED = _local_admin_allowed()


def require_admin(request: Request) -> dict[str, Any]:
    if not AUTH_ENABLED:
        if DEPLOYMENT.public:
            raise HTTPException(503, "Authentication is not configured for this public deployment.")
        if not LOCAL_ADMIN_ALLOWED:
            raise HTTPException(503, "Authentication is not configured for this address.")
        return {"google_sub":"local-admin","email":"local","name":"Local developer","role":"admin"}
    sub = str(request.session.get("user_sub") or "")
    user = auth_user(sub)
    if not user:
        raise HTTPException(401, "Authentication required")
    if str(user.get("role") or "user") != "admin":
        raise HTTPException(403, "Platform administrator access required")
    return user

def google_flow(code_verifier: str | None = None) -> Flow:
    config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(
        config,
        scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
        ],
        code_verifier=code_verifier,
        autogenerate_code_verifier=(code_verifier is None),
    )
    flow.redirect_uri = GOOGLE_REDIRECT_URI
    return flow


def maybe_claim_legacy_data(email: str, google_sub: str) -> bool:
    if not BOOTSTRAP_OWNER_EMAIL or email.strip().casefold() != BOOTSTRAP_OWNER_EMAIL:
        return False
    target = user_db_path(google_sub, language_code="en")
    if target.exists() or not LEGACY_DB_PATH.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LEGACY_DB_PATH, target)
    return True


LEARNER_UI_ROOT = "/"
# The new UI's address before the cutover (D-091, D-143). A return target still carrying it - a sign-in begun
# before the cutover, an old bookmark - lands on the same place at `/`.
FORMER_UI_PREFIX = "/next"
_NEXT_TARGET_MAX = 512


def safe_next_target(value: str | None, *, default: str = LEARNER_UI_ROOT) -> str:
    """The only place a sign-in or sign-out may send the browser afterwards: the learner UI at `/`.

    A strict allowlist, not a blocklist: the value must be a relative path that is `/` itself or continues
    with `?` or `#` (a hash route is how the learner UI addresses its places); `/next`, the UI's address
    before the cutover, is read as `/`. No scheme, no host (so no `//`), no backslash (browsers read it as
    `/`), no control character or whitespace (header injection, CRLF), nothing over 512 characters.
    Anything else is `default`. It is never echoed unvalidated, so it cannot be an open redirect."""
    candidate = value if isinstance(value, str) else ""
    if not candidate or len(candidate) > _NEXT_TARGET_MAX:
        return default
    if any(ord(char) <= 0x20 or ord(char) == 0x7F for char in candidate) or "\\" in candidate:
        return default
    if "//" in candidate or "://" in candidate or not candidate.startswith("/"):
        return default
    if candidate.startswith(FORMER_UI_PREFIX):
        rest = candidate[len(FORMER_UI_PREFIX):]
        if rest and rest[0] not in "/?#":
            return default
        candidate = LEARNER_UI_ROOT + rest.lstrip("/")
    rest = candidate[len(LEARNER_UI_ROOT):]
    if rest and rest[0] not in "?#":
        return default
    return candidate


def ensure_user_db() -> None:
    if _db_initializer is None:
        return
    path = current_db_path()
    key = str(path.resolve())
    if key in _initialized_user_dbs:
        return
    _db_initializer()
    _initialized_user_dbs.add(key)


def _validate_native_redirect_uri(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "orena"
        or parsed.netloc != "auth"
        or parsed.path != "/callback"
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(400, "Invalid native authentication redirect.")
    return value


def _validate_native_code_challenge(value: str) -> str:
    challenge = value.strip()
    if len(challenge) != 43 or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for char in challenge):
        raise HTTPException(400, "Invalid native authentication challenge.")
    return challenge


def issue_native_handoff(user_sub: str, code_challenge: str) -> str:
    """Issue a short-lived, one-use opaque handoff for the native client."""
    challenge = _validate_native_code_challenge(code_challenge)
    now = time.time()
    with _native_handoff_lock:
        for code, (_, expires_at, _) in list(_native_handoffs.items()):
            if expires_at <= now:
                _native_handoffs.pop(code, None)
        code = secrets.token_urlsafe(32)
        _native_handoffs[code] = (str(user_sub), now + NATIVE_HANDOFF_TTL_SECONDS, challenge)
        return code


def _consume_native_handoff(code: str, code_verifier: str | None) -> str | None:
    with _native_handoff_lock:
        entry = _native_handoffs.pop(code, None)
    if not entry or entry[1] <= time.time() or not code_verifier:
        return None
    verifier = code_verifier.strip()
    if not verifier:
        return None
    expected_challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("utf-8")).digest()).rstrip(b"=").decode("ascii")
    if not secrets.compare_digest(expected_challenge, entry[2]):
        return None
    return entry[0]


def _native_session_cookie(user_sub: str) -> str:
    payload = base64.b64encode(
        json.dumps({"user_sub": user_sub, "session_id": secrets.token_urlsafe(16)}).encode("utf-8")
    )
    return TimestampSigner(SESSION_SECRET or "local-single-user-mode").sign(payload).decode("utf-8")


PUBLIC_PAGE_PATHS = frozenset({"/landing", "/terms", "/privacy", "/account-deletion"})

router = APIRouter()


@router.get("/login")
def login_page(request: Request):
    # The learner UI signs in from its own Welcome screen (D-143); this address only sends there.
    if not AUTH_ENABLED or request.session.get("user_sub"):
        return RedirectResponse(LEARNER_UI_ROOT, status_code=302)
    # `?app=1` is the shell for a visitor who is not signed in: `/` alone is the public Landing for them.
    return RedirectResponse(f"{LEARNER_UI_ROOT}?app=1#/welcome", status_code=302)


SIGN_IN_HOST_MOVED = "canonical"


def _move_to_sign_in_host(request: Request) -> RedirectResponse | None:
    """Google returns to GOOGLE_REDIRECT_URI, and the OAuth state lives in the session cookie of the host the
    sign-in started on. Started anywhere else (http://localhost:8000 on the server itself), the callback finds no
    state. So the start moves to the redirect URI's host first, with nothing written to the session. It moves at
    most once: a proxy that rewrites Host would otherwise loop, and then the start proceeds as before."""
    target = urlparse(GOOGLE_REDIRECT_URI)
    here = str(request.headers.get("host") or "").casefold()
    if not target.netloc or not here or here == target.netloc.casefold():
        return None
    if request.query_params.get(SIGN_IN_HOST_MOVED) is not None:
        return None
    query = [(key, value) for key, value in request.query_params.multi_items() if key != SIGN_IN_HOST_MOVED]
    query.append((SIGN_IN_HOST_MOVED, "1"))
    return RedirectResponse(f"{target.scheme}://{target.netloc}/auth/google?{urlencode(query)}", status_code=302)


@router.get("/auth/google")
def auth_google(
    request: Request,
    native_redirect_uri: str | None = None,
    native_code_challenge: str | None = None,
    next: str | None = None,
):
    if not AUTH_ENABLED:
        raise HTTPException(503, "Google authentication is not configured.")
    moved = _move_to_sign_in_host(request)
    if moved is not None:
        return moved
    # Where the new UI wants to land after a successful sign-in. Validated here and stored in the signed
    # session, never read back from the callback's query, so a forged callback cannot choose it.
    if next:
        request.session["post_auth_next"] = safe_next_target(next)
    else:
        request.session.pop("post_auth_next", None)
    if native_redirect_uri:
        request.session["native_redirect_uri"] = _validate_native_redirect_uri(native_redirect_uri)
        if not native_code_challenge:
            raise HTTPException(400, "Native authentication challenge is required.")
        request.session["native_code_challenge"] = _validate_native_code_challenge(native_code_challenge)
    flow = google_flow()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    request.session["oauth_nonce"] = nonce
    url, _ = flow.authorization_url(
        state=state,
        nonce=nonce,
        access_type="online",
        include_granted_scopes="true",
        prompt="select_account",
    )

    if not flow.code_verifier:
        raise HTTPException(500, "OAuth PKCE verifier was not generated.")
    request.session["oauth_code_verifier"] = flow.code_verifier

    return RedirectResponse(url, status_code=302)


@router.get("/auth/google/callback")
def auth_google_callback(request: Request):
    if not AUTH_ENABLED:
        raise HTTPException(503, "Google authentication is not configured.")
    error = request.query_params.get("error")
    if error:
        raise HTTPException(400, f"Google login was cancelled or failed: {error}")

    expected_state = str(request.session.get("oauth_state") or "")
    returned_state = str(request.query_params.get("state") or "")
    if not expected_state or not secrets.compare_digest(expected_state, returned_state):
        raise HTTPException(400, "Invalid OAuth state.")

    code = str(request.query_params.get("code") or "")
    if not code:
        raise HTTPException(400, "Google did not return an authorization code.")

    code_verifier = str(request.session.get("oauth_code_verifier") or "")
    if not code_verifier:
        raise HTTPException(
            400,
            "OAuth session expired or PKCE verifier is missing. Please start Google login again.",
        )

    flow = google_flow(code_verifier=code_verifier)
    flow.fetch_token(code=code)
    raw_id_token = flow.credentials.id_token
    if not raw_id_token:
        raise HTTPException(400, "Google did not return an ID token.")

    info = google_id_token.verify_oauth2_token(raw_id_token, GoogleAuthRequest(), GOOGLE_CLIENT_ID)
    expected_nonce = str(request.session.get("oauth_nonce") or "")
    if expected_nonce and str(info.get("nonce") or "") != expected_nonce:
        raise HTTPException(400, "Invalid OpenID Connect nonce.")
    if not bool(info.get("email_verified")):
        raise HTTPException(403, "Google email is not verified.")

    user = upsert_auth_user(info)
    maybe_claim_legacy_data(str(user.get("email") or ""), str(user.get("google_sub") or ""))
    native_redirect_uri = str(request.session.get("native_redirect_uri") or "")
    native_code_challenge = str(request.session.get("native_code_challenge") or "")
    stored_next = str(request.session.get("post_auth_next") or "")
    request.session.clear()
    request.session["user_sub"] = str(user["google_sub"])
    if native_redirect_uri:
        handoff = issue_native_handoff(str(user["google_sub"]), native_code_challenge)
        return RedirectResponse(
            f"{native_redirect_uri}?{urlencode({'code': handoff})}",
            status_code=302,
        )
    # Re-validated on the way out: the stored value was checked when it went in, and a session is a cookie.
    return RedirectResponse(safe_next_target(stored_next, default="/") if stored_next else "/", status_code=302)


class NativeSessionExchangeIn(BaseModel):
    code: StrictStr
    code_verifier: StrictStr | None = None


@router.post("/api/auth/native/exchange")
def api_native_session_exchange(payload: NativeSessionExchangeIn, request: Request, response: Response) -> dict[str, str]:
    """Exchange the one-use browser handoff for a server-signed session cookie."""
    response.headers["Cache-Control"] = "no-store"
    if not AUTH_ENABLED:
        raise HTTPException(503, "Google authentication is not configured.")
    user_sub = _consume_native_handoff(payload.code.strip(), payload.code_verifier)
    if not user_sub or not auth_user(user_sub):
        raise HTTPException(401, "Authentication handoff is invalid or expired.")
    request.session.clear()
    request.session["user_sub"] = user_sub
    return {"version": NATIVE_SESSION_VERSION, "session_cookie": _native_session_cookie(user_sub)}


@router.post("/auth/logout")
def auth_logout(request: Request, next: str | None = None):
    request.session.clear()
    if next:
        # The new UI says where it wants to be after signing out; it navigates there itself.
        return {"ok": True, "next": safe_next_target(next)}
    return {"ok": True}


@router.get("/api/me")
def api_me(request: Request) -> dict[str, Any]:
    if not AUTH_ENABLED:
        admin = LOCAL_ADMIN_ALLOWED
        return {"authenticated":True,"mode":"local","name":"Local user","email":"","picture":"","role":"admin" if admin else "user","is_admin":admin}
    sub = str(request.session.get("user_sub") or "")
    user = auth_user(sub)
    if not user:
        raise HTTPException(401, "Authentication required")
    role = str(user.get("role") or "user")
    return {
        "authenticated": True,
        "mode": "google",
        "name": user.get("name") or user.get("email"),
        "email": user.get("email") or "",
        "picture": user.get("picture") or "",
        "language": current_language_code(),
        "role": role,
        "is_admin": role == "admin",
    }


@router.get("/api/session/bootstrap")
def api_session_bootstrap(request: Request, response: Response) -> dict[str, Any]:
    """Return the compact authenticated session contract for web/mobile clients."""
    response.headers["Cache-Control"] = "no-store"
    if not AUTH_ENABLED:
        role = "admin" if LOCAL_ADMIN_ALLOWED else "user"
        mode = "local"
    else:
        sub = str(request.session.get("user_sub") or "")
        user = auth_user(sub)
        if not user:
            raise HTTPException(401, "Authentication required")
        role = str(user.get("role") or "user")
        mode = "google"

    settings = account_settings.read_account_settings()
    stored_language = str((settings or {}).get("learning_language") or "")
    if stored_language and not request.session.get("language"):
        # A session that looked once and found nothing (`language_checked`) must not keep the default after the
        # account stores a choice elsewhere: bootstrap already reads the stored value, so it seeds the session
        # here and the flag goes (implementation review delta, P2-3).
        request.session["language"] = enabled_language(stored_language).code
        request.session.pop("language_checked", None)
    active = enabled_language(
        request.session.get("language") or current_language_code() or DEFAULT_LANGUAGE
    ).code
    options = [
        {"code": item.code, "name": item.name, "native_name": item.native_name}
        for item in all_languages()
        if item.enabled
    ]
    return {
        "version": SESSION_BOOTSTRAP_VERSION,
        "authenticated": True,
        "mode": mode,
        "user": {"role": role, "is_admin": role == "admin"},
        # `stored`: the account has chosen a learning language (so a new session keeps it). False
        # means never chosen, and the entry rule opens Welcome rather than assuming the default.
        "language": {
            "active": active,
            "options": options,
            "stored": bool(settings and settings["learning_language"]),
        },
    }

class _AccountLanguageUnreadable(Exception):
    """The account's stored learning language could not be read while the target-language count is enforced."""


class UserIsolationMiddleware(BaseHTTPMiddleware):
    @staticmethod
    def _seeded_language(request: Request, path: str, enforced: bool = False) -> str:
        """The account's stored learning language, for a session that has none (D4 I2).

        Read only when the session carries no language, and then written into the session, so every
        later request reads the cookie as before. It seeds; it never overrides a session that chose.

        `enforced` (D-16R, the target-language count is on): "this account has not chosen" is not remembered in the
        session. Another session may store a language at any moment, and a session that kept running in the default
        language would write rows the guard never judged; so it asks again, one primary-key read per request, until it
        has a language of its own (review F2). A failed read then raises `_AccountLanguageUnreadable`.
        """
        checked = request.session.get("language_checked") and not enforced
        if request.session.get("language") or checked or not path.startswith("/api/"):
            return ""
        key = UserIsolationMiddleware._account_key(request)
        if not key:
            return ""
        try:
            stored = account_settings.stored_learning_language(key)
        except Exception as error:  # an unreadable account row must not take a read down ...
            if enforced:  # ... but a write must not run in a language nobody checked
                raise _AccountLanguageUnreadable from error
            return ""
        if stored:
            request.session["language"] = stored
        else:
            # Nothing to seed. Say so in the session, so an account that has never chosen costs one lookup per
            # session and not one per request (proposal I2: no per-request database read).
            request.session["language_checked"] = True
        return stored

    @staticmethod
    def _account_key(request: Request) -> str:
        return str(request.session.get("user_sub") or "") if AUTH_ENABLED else "legacy"

    @staticmethod
    def _language_count_enforced() -> bool:
        try:
            from writing_coach.product import language_limit

            return language_limit.enforced()
        except Exception:
            return False

    @staticmethod
    def _unreadable_response() -> JSONResponse:
        from writing_coach.core.errors import error_detail

        return JSONResponse(
            {"detail": error_detail(
                "quota_unavailable", "Usage limits cannot be checked right now. Please try again in a moment.",
                retryable=True, context={"reason": "language"})},
            status_code=503,
        )

    @staticmethod
    def _language_gate(request: Request, path: str) -> JSONResponse | None:
        """While the count is enforced: a write from an account with no stored learning language runs in the default
        language, which nothing has judged. It is refused (409 `learning_language_required`) unless that language is one
        the account already holds (an English learner from before the count, who never stored a choice) or the route
        writes no learner row (review F8). Fails closed (503) when what the account holds cannot be read."""
        from writing_coach.product import language_limit

        key = UserIsolationMiddleware._account_key(request)
        if not key or language_limit.writes_no_learner_rows(path):
            return None
        try:
            held = language_limit.held_by(key)
        except Exception:
            return UserIsolationMiddleware._unreadable_response()
        if DEFAULT_LANGUAGE in held:
            return None
        refusal = language_limit.required_error()
        return JSONResponse({"detail": refusal.detail}, status_code=refusal.status_code)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Only a request that has no language of its own, to an /api/ route, can need the count (review F10).
        undecided = not request.session.get("language") and path.startswith("/api/")
        enforced = self._language_count_enforced() if undecided else False
        mutating = request.method not in {"GET", "HEAD", "OPTIONS"}
        try:
            seeded = self._seeded_language(request, path, enforced)
        except _AccountLanguageUnreadable:
            if mutating:
                return self._unreadable_response()
            seeded = ""
        if enforced and mutating and not seeded and not request.session.get("language"):
            refused = self._language_gate(request, path)
            if refused is not None:
                return refused
        requested_language = enabled_language(
            request.session.get("language") or seeded or DEFAULT_LANGUAGE
        ).code

        public = (
            path == "/login"
            # The learner UI's shell, so its Welcome screen can draw before anyone is signed in. It carries
            # no learner data: everything it then asks for is an /api route, and those stay protected.
            or path == LEARNER_UI_ROOT
            or path == FORMER_UI_PREFIX
            # The public pages: Landing, Terms, Privacy. They carry no learner data and no /api route.
            or path in PUBLIC_PAGE_PATHS
            or path.startswith("/orena-brand/")
            or path == "/api/health"
            or path == "/api/readiness"
            or path == "/api/platform/languages"
            or path == "/api/auth/native/exchange"
            # A payment gateway's signed event has no session: its signature is the proof (billing_api.py).
            or path.startswith("/api/billing/webhooks/")
            or path.startswith("/auth/")
            or path.startswith("/static/")
            or path.startswith("/orena-assets/")
            or path == "/favicon.ico"
        )

        if not AUTH_ENABLED:
            user_token = _user_key.set("legacy")
            language_token = _language_key.set(requested_language)
            try:
                # Local development still uses per-language SQLite scopes.  A
                # language switch can therefore point the request at a new
                # database path after startup; initialize that scope before
                # any handler attempts to read or write it.
                if _db_initializer is not None:
                    _db_initializer()
                return await call_next(request)
            finally:
                _language_key.reset(language_token)
                _user_key.reset(user_token)

        if public:
            language_token = _language_key.set(requested_language)
            try:
                return await call_next(request)
            finally:
                _language_key.reset(language_token)

        user_sub = str(request.session.get("user_sub") or "")
        if not user_sub:
            if path.startswith("/api/"):
                return JSONResponse({"detail": "Authentication required"}, status_code=401)
            return RedirectResponse(f"{LEARNER_UI_ROOT}#/welcome", status_code=302)

        user_token = _user_key.set(user_sub)
        language_token = _language_key.set(requested_language)
        try:
            ensure_user_db()
            return await call_next(request)
        finally:
            _language_key.reset(language_token)
            _user_key.reset(user_token)

def install_auth(app: FastAPI, db_initializer: Callable[[], None]) -> None:
    global _db_initializer
    _db_initializer = db_initializer
    init_auth_db()
    app.include_router(router)
    app.add_middleware(UserIsolationMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=SESSION_SECRET or "local-single-user-mode",
        session_cookie="writing_coach_session",
        max_age=60 * 60 * 24 * 14,
        same_site="lax",
        https_only=COOKIE_SECURE,
    )
