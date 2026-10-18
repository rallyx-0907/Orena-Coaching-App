"""Deployment configuration shared by authentication and operational endpoints."""

from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit


LOCAL_ORIGIN = "http://127.0.0.1:8000"
CALLBACK_PATH = "/auth/google/callback"

# development: a developer's machine or a lane runtime (:8021). staging: public and product-like (:8000 and the public
# domain), where people test the product. production: the final product, which does not exist yet (D-146). Staging and
# production are both public and keep every public security requirement; neither is a switch that turns features off -
# a learner capability is on where its own flag says so.
ENVIRONMENTS = ("development", "staging", "production")
PUBLIC_ENVIRONMENTS = frozenset({"staging", "production"})
_ALIASES = {"dev": "development", "stage": "staging", "public": "production", "prod": "production"}


def environment_name(value: object) -> str:
    """The canonical name of an APP_ENV value (unset is development); unknown names come back unchanged."""
    raw = str(value or "").strip().casefold() or "development"
    return _ALIASES.get(raw, raw)


def is_public_environment(value: object) -> bool:
    """Whether an APP_ENV value names a public deployment (staging or production)."""
    return environment_name(value) in PUBLIC_ENVIRONMENTS


@dataclass(frozen=True)
class DeploymentConfig:
    app_env: str
    public_base_url: str
    google_redirect_uri: str
    auth_enabled: bool
    cookie_secure: bool

    @property
    def public(self) -> bool:
        """Reachable by people who are not the developer: every public security requirement applies."""
        return self.app_env in PUBLIC_ENVIRONMENTS

    @property
    def production(self) -> bool:
        """The final product only. Not a feature switch (D-146)."""
        return self.app_env == "production"

    @property
    def developer_docs(self) -> bool:
        """/docs, /redoc and /openapi.json are developer tooling, never served publicly."""
        return not self.public


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


def is_loopback_host(host: object) -> bool:
    """Whether a declared host is this machine's own loopback: ``localhost``, 127.0.0.0/8, ::1, ::ffff:127.x.

    Nothing else counts: not a private, link-local, CGNAT or unique-local address, not any other name."""
    text = str(host or "").strip().casefold().rstrip(".")
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    if text == "localhost":
        return True
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return False
    mapped = getattr(address, "ipv4_mapped", None)
    return (mapped or address).is_loopback


def public_exposure_markers(public_base_url: str, values: Mapping[str, str]) -> list[str]:
    """Every declared exposure beyond this machine's loopback (issue #137): development with sign-in off is loopback-only.

    Declared means configuration naming where the runtime is reached: PUBLIC_BASE_URL, GOOGLE_REDIRECT_URI,
    ORENA_PUBLISHED_BIND_HOST (where the container's port is published), ORENA_INSECURE_DEV_LAN_BIND_HOST and the
    tunnel token. The in-container listen address (uvicorn on 0.0.0.0, APP_BIND_HOST) is not read: a container must
    listen on every interface inside its own network namespace, and what reaches it is decided by the publish above.
    Only names are returned, never values."""
    markers: list[str] = []
    origins = {"PUBLIC_BASE_URL": public_base_url, "GOOGLE_REDIRECT_URI": str(values.get("GOOGLE_REDIRECT_URI", "")).strip()}
    for name, origin in origins.items():
        if origin and not is_loopback_host(urlsplit(origin).hostname):
            markers.append(f"{name} is not a loopback host")
    for name in ("ORENA_PUBLISHED_BIND_HOST", "ORENA_INSECURE_DEV_LAN_BIND_HOST"):
        declared = str(values.get(name, "")).strip()
        if declared and not is_loopback_host(declared):
            markers.append(f"{name} is not a loopback host")
    if str(values.get("CLOUDFLARE_TUNNEL_TOKEN", "")).strip():
        markers.append("CLOUDFLARE_TUNNEL_TOKEN is set")
    return markers


def resolve_deployment_config(env: Mapping[str, str] | None = None) -> DeploymentConfig:
    """Resolve non-secret deployment settings with fail-fast guards for public (staging, production) runtimes."""
    values = os.environ if env is None else env
    app_env = environment_name(values.get("APP_ENV", "development"))
    if app_env not in ENVIRONMENTS:
        raise RuntimeError("APP_ENV must be development, staging or production.")
    public = app_env in PUBLIC_ENVIRONMENTS

    raw_origin = str(values.get("PUBLIC_BASE_URL", "")).strip()
    if not raw_origin:
        if public:
            raise RuntimeError(f"PUBLIC_BASE_URL is required when APP_ENV={app_env}.")
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

    if public:
        if urlsplit(public_base_url).scheme != "https" or _is_local_or_unsafe_host(public_base_url):
            raise RuntimeError(f"PUBLIC_BASE_URL must be a non-local HTTPS origin when APP_ENV={app_env}.")
        if urlsplit(google_redirect_uri).scheme != "https" or _is_local_or_unsafe_host(google_redirect_uri):
            raise RuntimeError(f"The Google callback must be a non-local HTTPS URL when APP_ENV={app_env}.")
        if not auth_enabled:
            raise RuntimeError(f"Google authentication must be configured when APP_ENV={app_env}.")
        if not str(values.get("SESSION_SECRET", "")).strip():
            raise RuntimeError(f"SESSION_SECRET is required when APP_ENV={app_env}.")
        if len(str(values.get("SESSION_SECRET", "")).strip()) < 32:
            # A short secret lets anyone forge a session cookie, an administrator's included.
            raise RuntimeError(f"SESSION_SECRET must be at least 32 characters when APP_ENV={app_env}.")
        if app_env == "production" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(values.get("LEGAL_EFFECTIVE_DATE", "")).strip()):
            # D-233: a consent record names the Terms/Privacy version accepted. Production never records "unstamped";
            # the deploy states the date it passed to build_public_pages.mjs --effective-date.
            raise RuntimeError("LEGAL_EFFECTIVE_DATE (YYYY-MM-DD) is required when APP_ENV=production.")
    elif auth_enabled and not str(values.get("SESSION_SECRET", "")).strip():
        raise RuntimeError("SESSION_SECRET is required when Google authentication is enabled.")

    if not public and not auth_enabled:
        # Fail closed at startup (issue #137): a development runtime with sign-in off is the developer's alone. If its
        # configuration says it faces the public, refuse to start rather than serve it.
        markers = public_exposure_markers(public_base_url, values)
        if markers:
            raise RuntimeError(
                "Refusing to start: APP_ENV=" + app_env + " with Google authentication disabled is loopback-only "
                "but is configured for exposure (" + "; ".join(markers) + "). Use Google sign-in (LAN or public), "
                "or declare only localhost/127.0.0.1/::1."
            )

    return DeploymentConfig(
        app_env=app_env,
        public_base_url=public_base_url,
        google_redirect_uri=google_redirect_uri,
        auth_enabled=auth_enabled,
        cookie_secure=urlsplit(public_base_url).scheme == "https",
    )
