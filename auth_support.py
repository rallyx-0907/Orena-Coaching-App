import hashlib
import base64
import json
import os
import secrets
import shutil
import time
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Callable
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
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


def require_admin(request: Request) -> dict[str, Any]:
    if not AUTH_ENABLED:
        if DEPLOYMENT.production:
            raise HTTPException(503, "Production authentication is not configured.")
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


router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if not AUTH_ENABLED:
        return RedirectResponse("/", status_code=302)
    if request.session.get("user_sub"):
        return RedirectResponse("/", status_code=302)
    template = (ROOT / "templates" / "login.html").read_text(encoding="utf-8")
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip() if (ROOT / "VERSION").exists() else "dev"
    return HTMLResponse(template.replace("{{APP_VERSION}}", version))


@router.get("/auth/google")
def auth_google(
    request: Request,
    native_redirect_uri: str | None = None,
    native_code_challenge: str | None = None,
):
    if not AUTH_ENABLED:
        raise HTTPException(503, "Google authentication is not configured.")
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
    request.session.clear()
    request.session["user_sub"] = str(user["google_sub"])
    if native_redirect_uri:
        handoff = issue_native_handoff(str(user["google_sub"]), native_code_challenge)
        return RedirectResponse(
            f"{native_redirect_uri}?{urlencode({'code': handoff})}",
            status_code=302,
        )
    return RedirectResponse("/", status_code=302)


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
def auth_logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/api/me")
def api_me(request: Request) -> dict[str, Any]:
    if not AUTH_ENABLED:
        return {"authenticated":True,"mode":"local","name":"Local user","email":"","picture":"","role":"admin","is_admin":True}
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
        role = "admin"
        mode = "local"
    else:
        sub = str(request.session.get("user_sub") or "")
        user = auth_user(sub)
        if not user:
            raise HTTPException(401, "Authentication required")
        role = str(user.get("role") or "user")
        mode = "google"

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
        "language": {"active": active, "options": options},
    }

class UserIsolationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        requested_language = enabled_language(
            request.session.get("language") or DEFAULT_LANGUAGE
        ).code

        public = (
            path == "/login"
            or path == "/api/health"
            or path == "/api/readiness"
            or path == "/api/platform/languages"
            or path == "/api/auth/native/exchange"
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
            return RedirectResponse("/login", status_code=302)

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
