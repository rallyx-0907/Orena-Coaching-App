"""Small, deliberately strict network boundary for imported media URLs.

Media import accepts URLs supplied by people.  Resolving and checking every
redirect here keeps provider and direct-media code from accidentally gaining an
SSRF path when a new source type is added later.  The address a connection
actually reaches is checked too, because a name can resolve to a public address
when it is validated and a private one when it is connected (DNS rebinding).
"""
from __future__ import annotations

import http.client
import ipaddress
import socket
from pathlib import Path
from typing import Final
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPHandler, HTTPRedirectHandler, HTTPSHandler, Request, build_opener

MAX_MEDIA_BYTES: Final[int] = 64 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS: Final[float] = 12.0


class UnsafeMediaFetch(ValueError):
    """A URL/fetch failure whose text is safe to return to a learner."""


def _unsafe(message: str) -> UnsafeMediaFetch:
    return UnsafeMediaFetch(message)


def _is_public_address(raw: str) -> bool:
    """True only for a globally routable address.

    `is_global` is the single question this boundary asks, rather than a list of
    ranges to keep in step with the IANA registry: it already excludes RFC1918,
    loopback, link-local, unique-local, TEST-NET, reserved space and — measured
    on this interpreter — the carrier-grade NAT range 100.64.0.0/10, which
    `is_private` alone reports as public. Multicast is the exception that must
    stay explicit, because `is_global` is True for 224.0.0.0/4.
    """
    address = ipaddress.ip_address(raw)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_global and not address.is_multicast


def validate_public_http_url(
    url: str,
    *,
    allowed_hosts: frozenset[str] | None = None,
    allowed_ports: frozenset[int] | None = None,
) -> str:
    """Validate a public HTTP URL and every address returned by its DNS lookup."""
    if not isinstance(url, str) or not url or url != url.strip():
        raise _unsafe("Enter a valid public media URL.")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise _unsafe("Enter a valid public media URL.") from exc
    host = (parsed.hostname or "").casefold().rstrip(".")
    if (
        parsed.scheme not in {"http", "https"}
        or not host
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise _unsafe("Enter a valid public media URL.")
    default_port = 80 if parsed.scheme == "http" else 443
    if port is not None and port != default_port and (allowed_ports is None or port not in allowed_ports):
        raise _unsafe("This media address is not allowed.")
    if allowed_hosts is not None and host not in {item.casefold().rstrip(".") for item in allowed_hosts}:
        raise _unsafe("This media address is not allowed.")
    try:
        addresses = socket.getaddrinfo(host, port or default_port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as exc:
        raise _unsafe("This media address could not be reached.") from exc
    if not addresses:
        raise _unsafe("This media address could not be reached.")
    try:
        addresses_are_public = all(_is_public_address(item[4][0]) for item in addresses)
    except ValueError as exc:
        raise _unsafe("This media address could not be reached.") from exc
    # Kept outside the `except ValueError` above on purpose: UnsafeMediaFetch
    # *is* a ValueError, so a refusal raised inside that block would be replaced
    # by the vaguer "could not be reached" and the learner would be told the
    # wrong thing about their own URL.
    if not addresses_are_public:
        raise _unsafe("This media address is not allowed.")
    return url


class _CheckedRedirects(HTTPRedirectHandler):
    """Re-check redirect targets because a safe first hop proves nothing later."""

    def __init__(self, *, max_redirects: int, allowed_hosts: frozenset[str] | None = None) -> None:
        super().__init__()
        self._max_redirects = max_redirects
        self._allowed_hosts = allowed_hosts
        self._count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        self._count += 1
        if self._count > self._max_redirects:
            raise _unsafe("The media address redirected too many times.")
        validate_public_http_url(newurl, allowed_hosts=self._allowed_hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _connect_public(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, *args, **kwargs):
    """Connect, then keep the connection only if it reached a public address.

    Runs where http.client opens its socket, after the TCP handshake and
    before a single request byte is written, so whatever DNS answered the
    second time, nothing is sent to a private or local service.
    """
    sock = socket.create_connection(address, timeout, source_address)
    try:
        public = _is_public_address(sock.getpeername()[0])
    except (OSError, ValueError, IndexError, TypeError):
        public = False
    if not public:
        sock.close()
        raise _unsafe("This media address is not allowed.")
    return sock


class _PublicHTTPConnection(http.client.HTTPConnection):
    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self._create_connection = _connect_public


class _PublicHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self._create_connection = _connect_public


class _PublicHTTPHandler(HTTPHandler):
    def http_open(self, req):  # type: ignore[no-untyped-def]
        return self.do_open(_PublicHTTPConnection, req)


class _PublicHTTPSHandler(HTTPSHandler):
    def https_open(self, req):  # type: ignore[no-untyped-def]
        return self.do_open(_PublicHTTPSConnection, req, context=self._context)


def _open(url: str, *, timeout: float, max_redirects: int):
    validate_public_http_url(url)
    opener = build_opener(
        _PublicHTTPHandler(), _PublicHTTPSHandler(), _CheckedRedirects(max_redirects=max_redirects)
    )
    request = Request(url, headers={"User-Agent": "OrenaMediaImport/1.0"})
    try:
        return opener.open(request, timeout=timeout)
    except UnsafeMediaFetch:
        raise
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise _unsafe("The media address could not be fetched.") from exc


def _content_type(response) -> str:  # type: ignore[no-untyped-def]
    return (response.headers.get_content_type() or "").casefold()


def fetch_bounded(
    url: str,
    *,
    max_bytes: int = MAX_MEDIA_BYTES,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    content_types: frozenset[str] = frozenset(),
    max_redirects: int = 3,
) -> tuple[bytes, str]:
    """Fetch a small response while enforcing a byte budget during reads."""
    if max_bytes <= 0 or timeout <= 0 or max_redirects < 0:
        raise ValueError("fetch limits must be positive")
    with _open(url, timeout=timeout, max_redirects=max_redirects) as response:
        content_type = _content_type(response)
        if content_types and content_type not in {item.casefold() for item in content_types}:
            raise _unsafe("This media type is not supported.")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(min(1024 * 1024, max_bytes + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise _unsafe("This media file is too large.")
            chunks.append(chunk)
    return b"".join(chunks), content_type


def download_bounded(
    url: str,
    destination: Path,
    *,
    max_bytes: int = MAX_MEDIA_BYTES,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_redirects: int = 3,
) -> int:
    """Stream a direct-media source to a caller-owned local temporary path."""
    if max_bytes <= 0 or timeout <= 0 or max_redirects < 0:
        raise ValueError("fetch limits must be positive")
    total = 0
    try:
        with _open(url, timeout=timeout, max_redirects=max_redirects) as response:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("wb") as output:
                while True:
                    chunk = response.read(min(1024 * 1024, max_bytes + 1))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        output.close()
                        destination.unlink(missing_ok=True)
                        raise _unsafe("This media file is too large.")
                    output.write(chunk)
    except UnsafeMediaFetch:
        raise
    except OSError as exc:
        raise _unsafe("The media address could not be fetched.") from exc
    return total
