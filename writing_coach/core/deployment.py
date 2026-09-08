"""Deployment configuration shared by authentication and operational endpoints."""

from __future__ import annotations

import os
import ipaddress
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit


LOCAL_ORIGIN = "http://127.0.0.1:8000"
CALLBACK_PATH = "/auth/google/callback"

# APP_ENV and the deployment tier answer two different questions, and conflating
# them is how unreviewed content reaches production learners:
#
#   APP_ENV                 runtime and security posture (HTTPS, auth, cookies,
#                           fail-fast guards). Preview runs APP_ENV=production
#                           precisely so it exercises real security.
#   ORENA_DEPLOYMENT_TIER   product publication tier: which catalog content this
#                           deployment may expose at all.
#
# A preview deployment is production-like runtime behaviour with restricted
# unreviewed content. It is NOT production publication.
DEPLOYMENT_TIER_ENV = "ORENA_DEPLOYMENT_TIER"
TIER_PRODUCTION = "production"
TIER_PREVIEW = "preview"
DEPLOYMENT_TIERS = frozenset({TIER_PRODUCTION, TIER_PREVIEW})


def resolve_deployment_tier(env: Mapping[str, str] | None = None) -> str:
    """The product deployment tier, defaulting safely to production.

    Unset means production: the safe answer, so a deployment that forgets the
    variable shows reviewed content only. An unrecognised value is refused at
    startup rather than quietly coerced, because a typo like "Preview " must not
    silently decide what learners can see - in either direction.
    """

    values = os.environ if env is None else env
    raw = str(values.get(DEPLOYMENT_TIER_ENV, "")).strip().casefold()
    if not raw:
        return TIER_PRODUCTION
    if raw not in DEPLOYMENT_TIERS:
        raise RuntimeError(
            f"{DEPLOYMENT_TIER_ENV} must be one of {sorted(DEPLOYMENT_TIERS)}.")
    return raw


@dataclass(frozen=True)
class DeploymentConfig:
    app_env: str
    public_base_url: str
    google_redirect_uri: str
    auth_enabled: bool
    cookie_secure: bool
    tier: str = TIER_PRODUCTION

    @property
    def production(self) -> bool:
        return self.app_env == "production"

    @property
    def preview(self) -> bool:
        """Whether this deployment may expose designated preview content."""

        return self.tier == TIER_PREVIEW


def _parse_http_url(value: str, *, label: str):
    try:
        parsed = urlsplit(value.strip())
        # Accessing .port validates non-numeric and out-of-range ports.
        port = parsed.port
    except ValueError as exc:
        raise RuntimeError(f"{label} contains an invalid port or host.") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError(f"{label} must be an absolute http(s) origin.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeError(f"{label} must not contain credentials, query parameters, or fragments.")
    hostname = parsed.hostname
    if not hostname:
        raise RuntimeError(f"{label} must include a hostname.")
    return parsed, hostname.casefold(), port


def _normal_origin(value: str, *, label: str) -> str:
    parsed, hostname, port = _parse_http_url(value, label=label)
    if parsed.path not in {"", "/"}:
        raise RuntimeError(f"{label} must be an origin without a path.")
    host = f"[{hostname}]" if ":" in hostname else hostname
    if port is not None and port != {"http": 80, "https": 443}[parsed.scheme.casefold()]:
        host = f"{host}:{port}"
    return f"{parsed.scheme.casefold()}://{host}"


def _normal_callback(value: str, *, label: str) -> str:
    parsed, hostname, port = _parse_http_url(value, label=label)
    if parsed.path != CALLBACK_PATH:
        raise RuntimeError(f"{label} must end with {CALLBACK_PATH}.")
    host = f"[{hostname}]" if ":" in hostname else hostname
    if port is not None and port != {"http": 80, "https": 443}[parsed.scheme.casefold()]:
        host = f"{host}:{port}"
    return f"{parsed.scheme.casefold()}://{host}{CALLBACK_PATH}"


def _is_local_or_unsafe_host(url: str) -> bool:
    hostname = str(urlsplit(url).hostname or "").casefold().rstrip(".")
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return address.is_loopback or address.is_unspecified


def resolve_deployment_config(env: Mapping[str, str] | None = None) -> DeploymentConfig:
    """Resolve non-secret deployment settings with production fail-fast guards."""
    values = os.environ if env is None else env
    raw_env = str(values.get("APP_ENV", "development")).strip().casefold() or "development"
    aliases = {"dev": "development", "public": "production", "prod": "production"}
    app_env = aliases.get(raw_env, raw_env)
    if app_env not in {"development", "production"}:
        raise RuntimeError("APP_ENV must be development or production.")

    raw_origin = str(values.get("PUBLIC_BASE_URL", "")).strip()
    if not raw_origin:
        if app_env == "production":
            raise RuntimeError("PUBLIC_BASE_URL is required when APP_ENV=production.")
        raw_origin = LOCAL_ORIGIN
    public_base_url = _normal_origin(raw_origin, label="PUBLIC_BASE_URL")

    client_id = str(values.get("GOOGLE_CLIENT_ID", "")).strip()
    client_secret = str(values.get("GOOGLE_CLIENT_SECRET", "")).strip()
    if bool(client_id) != bool(client_secret):
        raise RuntimeError("Google OAuth requires both GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")
    auth_enabled = bool(client_id and client_secret)

    raw_override = str(values.get("GOOGLE_REDIRECT_URI", "")).strip()
    google_redirect_uri = (
        _normal_callback(raw_override, label="GOOGLE_REDIRECT_URI")
        if raw_override
        else f"{public_base_url}{CALLBACK_PATH}"
    )
    if google_redirect_uri != f"{public_base_url}{CALLBACK_PATH}":
        raise RuntimeError("GOOGLE_REDIRECT_URI must use the same origin as PUBLIC_BASE_URL.")

    if app_env == "production":
        if urlsplit(public_base_url).scheme != "https" or _is_local_or_unsafe_host(public_base_url):
            raise RuntimeError("Production PUBLIC_BASE_URL must be a non-local HTTPS origin.")
        if urlsplit(google_redirect_uri).scheme != "https" or _is_local_or_unsafe_host(google_redirect_uri):
            raise RuntimeError("Production Google callback must be a non-local HTTPS URL.")
        if not auth_enabled:
            raise RuntimeError("Google authentication must be configured when APP_ENV=production.")
        if not str(values.get("SESSION_SECRET", "")).strip():
            raise RuntimeError("SESSION_SECRET is required when APP_ENV=production.")
    elif auth_enabled and not str(values.get("SESSION_SECRET", "")).strip():
        raise RuntimeError("SESSION_SECRET is required when Google authentication is enabled.")

    return DeploymentConfig(
        app_env=app_env,
        public_base_url=public_base_url,
        google_redirect_uri=google_redirect_uri,
        auth_enabled=auth_enabled,
        cookie_secure=urlsplit(public_base_url).scheme == "https",
        tier=resolve_deployment_tier(values),
    )
