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
import time
from pathlib import Path
from typing import Final
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPHandler, HTTPRedirectHandler, HTTPSHandler, Request, build_opener

MAX_MEDIA_BYTES: Final[int] = 64 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS: Final[float] = 12.0


class UnsafeMediaFetch(ValueError):
    """A URL/fetch failure whose text is safe to return to a learner."""


TOO_LARGE_MESSAGE: Final[str] = "This media file is too large."


def _unsafe(message: str, status_code: int | None = None, *, too_large: bool = False) -> UnsafeMediaFetch:
    failure = UnsafeMediaFetch(message)
    # Set when the byte budget was exceeded, so a caller names that reason in a stable code, not by matching prose.
    failure.too_large = too_large
    # The HTTP status the host answered with, when it did: lets a caller tell "rate limited" from "unreachable".
    failure.status_code = status_code
    return failure


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


def _open(
    url: str, *, timeout: float, max_redirects: int, allowed_hosts: frozenset[str] | None = None, user_agent: str = "",
    headers: dict[str, str] | None = None,
):
    validate_public_http_url(url, allowed_hosts=allowed_hosts)
    opener = build_opener(
        _PublicHTTPHandler(), _PublicHTTPSHandler(), _CheckedRedirects(max_redirects=max_redirects, allowed_hosts=allowed_hosts)
    )
    request = Request(url, headers={"User-Agent": user_agent or "OrenaMediaImport/1.0", **(headers or {})})
    try:
        return opener.open(request, timeout=timeout)
    except UnsafeMediaFetch:
        raise
    except HTTPError as exc:
        raise _unsafe("The media address could not be fetched.", exc.code) from exc
    except (URLError, TimeoutError, OSError) as exc:
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
    total_timeout: float | None = None,
    allowed_hosts: frozenset[str] | None = None,
    user_agent: str = "",
) -> tuple[bytes, str]:
    """Fetch a small response while enforcing a byte budget during reads.

    `timeout` bounds each socket operation; `total_timeout`, when given, bounds the whole read in wall-clock
    time, so a server that drips bytes cannot hold the caller for longer (the overshoot is at most one
    socket operation)."""
    if max_bytes <= 0 or timeout <= 0 or max_redirects < 0:
        raise ValueError("fetch limits must be positive")
    with _open(url, timeout=timeout, max_redirects=max_redirects, allowed_hosts=allowed_hosts, user_agent=user_agent) as response:
        content_type = _content_type(response)
        if content_types and content_type not in {item.casefold() for item in content_types}:
            raise _unsafe("This media type is not supported.")
        chunks: list[bytes] = []
        total = 0
        started = time.monotonic()
        # With a wall-clock bound the body is read in small pieces that return as soon as any bytes
        # arrive (`read1`), so the deadline is checked per piece and a server that drips one byte at a time
        # cannot hold the caller inside a single large blocking read. Without it nothing changes.
        read_piece = None
        if total_timeout is not None:
            # `read1` returns as soon as any bytes arrive; a response without it is read in the same small pieces.
            read_piece = getattr(response, "read1", None) or response.read
        while True:
            if total_timeout is not None and time.monotonic() - started > total_timeout:
                raise _unsafe("The media address took too long to answer.")
            if read_piece is not None:
                chunk = read_piece(min(8192, max_bytes + 1 - total))
            else:
                chunk = response.read(min(1024 * 1024, max_bytes + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise _unsafe(TOO_LARGE_MESSAGE, too_large=True)
            chunks.append(chunk)
    return b"".join(chunks), content_type


_READ_PIECE_BYTES: Final[int] = 64 * 1024


def _content_range(value: str) -> tuple[int | None, int | None]:
    """(first byte, full length) of a `Content-Range: bytes 0-99/1234` header; None for what is absent, `*` or malformed."""
    unit, _, rest = (value or "").strip().partition(" ")
    span, _, total = rest.partition("/")
    first, _, last = span.partition("-")
    start = int(first) if unit.casefold() == "bytes" and first.strip().isdigit() and last.strip().isdigit() else None
    return start, (int(total) if start is not None and total.strip().isdigit() else None)


def download_bounded(
    url: str,
    destination: Path,
    *,
    max_bytes: int = MAX_MEDIA_BYTES,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_redirects: int = 3,
    allowed_hosts: frozenset[str] | None = None,
    user_agent: str = "",
    range_chunk_bytes: int | None = None,
    total_timeout: float | None = None,
) -> int:
    """Stream a direct-media source to a caller-owned local temporary path.

    `range_chunk_bytes`, when given, takes the file in `Range` pieces of that size, each one a request through the same
    address checks. A host that throttles a plain GET (googlevideo serves a non-ranged request at about 30 KiB/s) answers a
    ranged one at full speed, which is also how `yt-dlp` fetches it; a host that ignores `Range` and answers 200 is read
    whole under the same byte budget. `total_timeout` bounds the whole download in wall-clock time (`timeout` only bounds
    one socket operation, which a slow drip never trips). The byte budget is enforced as bytes arrive in every mode."""
    if max_bytes <= 0 or timeout <= 0 or max_redirects < 0:
        raise ValueError("fetch limits must be positive")
    if range_chunk_bytes is not None and range_chunk_bytes <= 0:
        raise ValueError("fetch limits must be positive")
    total = 0
    started = time.monotonic()

    def check_clock() -> None:
        if total_timeout is not None and time.monotonic() - started > total_timeout:
            raise _unsafe("The media address took too long to answer.")

    def fail_too_large(output) -> None:  # type: ignore[no-untyped-def]
        output.close()
        destination.unlink(missing_ok=True)
        raise _unsafe(TOO_LARGE_MESSAGE, too_large=True)

    def copy(response, output, limit: int) -> int:  # type: ignore[no-untyped-def]
        """Write up to `limit` bytes of this body (None-bounded by the budget); returns how many arrived."""
        got = 0
        while True:
            check_clock()
            chunk = response.read(min(_READ_PIECE_BYTES if total_timeout is not None else 1024 * 1024, max_bytes + 1 - (total + got)))
            if not chunk:
                return got
            got += len(chunk)
            if total + got > max_bytes:
                fail_too_large(output)
            output.write(chunk)
            if got >= limit:
                return got

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as output:
            if range_chunk_bytes is None:
                with _open(url, timeout=timeout, max_redirects=max_redirects, allowed_hosts=allowed_hosts, user_agent=user_agent) as response:
                    total += copy(response, output, max_bytes + 1)
                return total
            known_length: int | None = None
            while known_length is None or total < known_length:
                check_clock()
                span = f"bytes={total}-{total + range_chunk_bytes - 1}"
                try:
                    response_cm = _open(url, timeout=timeout, max_redirects=max_redirects, allowed_hosts=allowed_hosts,
                                        user_agent=user_agent, headers={"Range": span})
                except UnsafeMediaFetch as refused:
                    # 416 after bytes were written: the file ended exactly on a piece boundary (a total of `*`). With a
                    # known total the check after the loop decides whether that was the end.
                    if total and getattr(refused, "status_code", None) == 416:
                        break
                    raise
                with response_cm as response:
                    if getattr(response, "status", 200) != 206:
                        if total:
                            raise _unsafe("The media address could not be fetched.")
                        total += copy(response, output, max_bytes + 1)  # the host ignored Range: the whole body, same budget
                        return total
                    start, advertised = _content_range(response.headers.get("Content-Range", ""))
                    if start is None and total:
                        raise _unsafe("The media address could not be fetched.")  # cannot prove this piece follows the last
                    if start is not None and start != total:
                        raise _unsafe("The media address could not be fetched.")  # not the piece asked for: corrupt audio
                    if advertised is not None:
                        if advertised > max_bytes:
                            fail_too_large(output)
                        if known_length is not None and advertised != known_length:
                            raise _unsafe("The media address could not be fetched.")
                        known_length = advertised
                    got = copy(response, output, range_chunk_bytes)
                    total += got
                    if known_length is not None and total > known_length:
                        raise _unsafe("The media address could not be fetched.")  # the advertised total was a lie
                    if got == 0 or (known_length is None and got < range_chunk_bytes):
                        break
            if known_length is not None and total != known_length:
                raise _unsafe("The media address could not be fetched.")  # stopped short: truncated audio
    except OSError as exc:
        destination.unlink(missing_ok=True)
        raise _unsafe("The media address could not be fetched.") from exc
    except BaseException:
        # Whatever ended it - a refusal, a bug, an interrupt - no partial file stays behind.
        destination.unlink(missing_ok=True)
        raise
    return total
