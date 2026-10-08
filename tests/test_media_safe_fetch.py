"""The network boundary for media URLs an administrator imports or previews.

Every address a URL resolves to must be globally routable, every redirect is
checked again, and - because DNS can answer differently the second time it is
asked - the connection itself is checked where it lands, before a request is
sent. No test here needs the internet: names are resolved through a patched
resolver or are numeric.
"""
from __future__ import annotations

import socket
import threading

import pytest

from writing_coach import media_safe_fetch
from writing_coach.media_safe_fetch import UnsafeMediaFetch, fetch_bounded, validate_public_http_url

PUBLIC = "93.184.216.34"


def _resolve_to(monkeypatch, *addresses: str) -> None:
    def fake(host, port, *args, **kwargs):
        return [
            (socket.AF_INET6 if ":" in address else socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))
            for address in addresses
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/hosts",
        "ftp://media.example/clip.mp3",
        "gopher://media.example/clip.mp3",
        "data:audio/mpeg;base64,AAAA",
        "javascript:alert(1)",
        "http:///clip.mp3",
        "https://user:secret@media.example/clip.mp3",
        "https://media.example:8443/clip.mp3",
        " https://media.example/clip.mp3",
        "",
    ],
)
def test_only_plain_public_http_urls_are_accepted(url, monkeypatch):
    _resolve_to(monkeypatch, PUBLIC)
    with pytest.raises(UnsafeMediaFetch):
        validate_public_http_url(url)


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1", "127.1", "2130706433", "0x7f000001", "017700000001",  # loopback, in the forms resolvers accept
        "0.0.0.0", "10.0.0.5", "172.16.3.4", "192.168.1.1",  # this network and RFC 1918
        "169.254.169.254", "169.254.1.1",  # link-local, cloud metadata included
        "100.64.0.1",  # carrier-grade NAT
        "224.0.0.1",  # multicast
        "[::1]", "[fe80::1]", "[fc00::1]", "[::ffff:127.0.0.1]", "[::ffff:169.254.169.254]",
    ],
)
def test_private_loopback_link_local_and_mapped_addresses_are_refused(host):
    with pytest.raises(UnsafeMediaFetch):
        validate_public_http_url(f"http://{host}/clip.mp3")


def test_localhost_by_name_is_refused():
    with pytest.raises(UnsafeMediaFetch):
        validate_public_http_url("http://localhost/clip.mp3")


def test_a_name_that_resolves_to_any_private_address_is_refused(monkeypatch):
    _resolve_to(monkeypatch, "10.1.2.3")
    with pytest.raises(UnsafeMediaFetch):
        validate_public_http_url("https://media.example/clip.mp3")
    _resolve_to(monkeypatch, PUBLIC, "192.168.0.10")
    with pytest.raises(UnsafeMediaFetch):
        validate_public_http_url("https://media.example/clip.mp3")


def test_a_public_name_is_accepted(monkeypatch):
    _resolve_to(monkeypatch, PUBLIC)
    assert validate_public_http_url("https://media.example/clip.mp3") == "https://media.example/clip.mp3"


def test_a_redirect_to_a_private_address_or_a_new_scheme_is_refused(monkeypatch):
    handler = media_safe_fetch._CheckedRedirects(max_redirects=3)
    for target in ("http://127.0.0.1/admin", "http://169.254.169.254/latest/meta-data/", "file:///etc/hosts"):
        with pytest.raises(UnsafeMediaFetch):
            handler.redirect_request(None, None, 302, "Found", {}, target)


def test_redirects_are_bounded(monkeypatch):
    _resolve_to(monkeypatch, PUBLIC)
    handler = media_safe_fetch._CheckedRedirects(max_redirects=1)
    from urllib.request import Request

    request = Request("https://media.example/a.mp3")
    handler.redirect_request(request, None, 302, "Found", {}, "https://media.example/b.mp3")
    with pytest.raises(UnsafeMediaFetch):
        handler.redirect_request(request, None, 302, "Found", {}, "https://media.example/c.mp3")


class _Listener:
    """A local TCP service that records whatever a client sends it."""

    def __init__(self) -> None:
        self.received: list[bytes] = []
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(1)
        self.server.settimeout(3)
        self.port = self.server.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self) -> None:
        try:
            connection, _ = self.server.accept()
        except OSError:
            return
        connection.settimeout(2)
        try:
            data = connection.recv(4096)
            if data:
                self.received.append(data)
                connection.sendall(b"HTTP/1.0 200 OK\r\nContent-Type: audio/mpeg\r\nContent-Length: 2\r\n\r\nok")
        except OSError:
            pass
        finally:
            connection.close()

    def close(self) -> None:
        self.thread.join(5)
        self.server.close()


def test_a_connection_that_lands_on_a_private_address_sends_nothing(monkeypatch):
    # DNS rebinding: the name was public when it was checked and private when
    # the connection is made. Validation is bypassed here to stand for that
    # first answer; only the connection-time check is left to refuse.
    listener = _Listener()
    monkeypatch.setattr(media_safe_fetch, "validate_public_http_url", lambda url, **_: url)
    try:
        with pytest.raises(UnsafeMediaFetch):
            fetch_bounded(f"http://127.0.0.1:{listener.port}/clip.mp3")
    finally:
        listener.close()
    assert listener.received == [], "no request reached the private service"


def test_the_connection_check_admits_a_public_peer(monkeypatch):
    class _Socket:
        closed = False

        def getpeername(self):
            return (PUBLIC, 443)

        def close(self):
            self.closed = True

    sock = _Socket()
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: sock)
    assert media_safe_fetch._connect_public(("media.example", 443), 5) is sock
    assert sock.closed is False


def test_the_connection_check_closes_a_private_peer(monkeypatch):
    class _Socket:
        closed = False

        def getpeername(self):
            return ("10.0.0.7", 443)

        def close(self):
            self.closed = True

    sock = _Socket()
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: sock)
    with pytest.raises(UnsafeMediaFetch):
        media_safe_fetch._connect_public(("media.example", 443), 5)
    assert sock.closed is True


def test_a_response_larger_than_the_budget_is_refused_while_reading(monkeypatch):
    class _Response:
        headers = type("H", (), {"get_content_type": staticmethod(lambda: "audio/mpeg")})()

        def __init__(self) -> None:
            self.sent = 0

        def read(self, size):
            self.sent += size
            return b"x" * size

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    response = _Response()
    monkeypatch.setattr(media_safe_fetch, "_open", lambda url, **kwargs: response)
    with pytest.raises(UnsafeMediaFetch):
        fetch_bounded("https://media.example/clip.mp3", max_bytes=1024)
    assert response.sent <= 2 * 1025, "the budget stops the read, not the end of the stream"
