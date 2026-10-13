"""Whether a request comes from this machine's own developer (issue #137, security review 2026-10-04).

Signed-out "local developer" behaviour (the local administrator, the shared ``legacy`` learner scope) is a property of
the *actual trusted request boundary*, never of a hostname or a configuration hint. This module decides it from the
transport peer of the connection, and from nothing a caller can write into a request:

* ``Host``, ``Origin``, ``Referer``, ``X-Forwarded-*``/``Forwarded`` and ``PUBLIC_BASE_URL`` are never evidence of
  locality. The presence of a forwarding header is evidence of the opposite (a proxy or tunnel sits in front).
* Configuration here can only narrow what is local; it can never make a remote peer local. The single widening, the
  Docker published-port case below, names a peer that is not the caller's to choose (the container's own default
  gateway) and is valid only together with a loopback publish.

The policy, in order (any failing step is "not local"):

1. A public runtime (staging, production) has no signed-out local developer at all.
2. A request carrying a forwarding header is not local (a tunnel or reverse proxy forwarded it).
3. A peer that is a loopback address (127.0.0.0/8, ::1, IPv4-mapped loopback) is local.
4. Otherwise the peer is local only if ALL of these hold: ``ORENA_TRUST_DOCKER_PUBLISHED_PORT`` is on, the port is
   published on a loopback host (``ORENA_PUBLISHED_BIND_HOST``), and the peer is exactly this container's own IPv4
   default gateway (the address Docker's port proxy connects from). Inside a container a browser on the host arrives
   from that gateway, not from 127.0.0.1. When the publish is not loopback (``0.0.0.0``, a LAN address) the gateway is
   also where LAN traffic appears to come from, so the trust is void and the request is refused.

No peer (a unix socket, a missing scope entry) or an unparsable one is not local: the check fails closed."""

from __future__ import annotations

import ipaddress
import os
import socket
import struct
from collections.abc import Mapping
from functools import lru_cache
from typing import Any

from writing_coach.core.deployment import is_public_environment

# Operator opt-in, valid only with a loopback publish. compose.yaml sets it together with the loopback publish.
TRUST_DOCKER_PUBLISHED_PORT_ENV = "ORENA_TRUST_DOCKER_PUBLISHED_PORT"
# Where the container's port is published on the host (compose.yaml writes the host it really publishes on).
PUBLISHED_BIND_HOST_ENV = "ORENA_PUBLISHED_BIND_HOST"

_TRUTHY = {"1", "true", "yes", "on"}
_LOOPBACK_BIND_HOSTS = {"127.0.0.1", "::1", "localhost"}

# Headers a proxy or tunnel adds. A direct local request from a browser carries none of them.
FORWARDING_HEADERS = (
    "forwarded",
    "x-forwarded-for",
    "x-forwarded-host",
    "x-forwarded-proto",
    "x-forwarded-port",
    "x-real-ip",
    "x-original-forwarded-for",
    "cf-connecting-ip",
    "cf-ray",
    "cf-visitor",
    "true-client-ip",
)


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() in _TRUTHY


def _parse_ip(host: object) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        address = ipaddress.ip_address(str(host or "").strip())
    except ValueError:
        return None
    mapped = getattr(address, "ipv4_mapped", None)
    return mapped if mapped is not None else address


def is_loopback_peer(host: object) -> bool:
    address = _parse_ip(host)
    return address is not None and address.is_loopback


def default_gateway(route_table: str | None = None) -> str | None:
    """The IPv4 default gateway of this network namespace (the container's), from /proc/net/route; None if unknown.

    ``route_table`` is the file's text, passed by tests; otherwise it is read once per call site from /proc."""
    if route_table is None:
        route_table = _read_route_table()
    best: tuple[int, str] | None = None
    for line in route_table.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 8 or fields[1] != "00000000":
            continue
        try:
            flags = int(fields[3], 16)
            metric = int(fields[6])
            gateway = socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
        except (ValueError, struct.error, OSError):
            continue
        if not flags & 0x2 or gateway == "0.0.0.0":  # RTF_GATEWAY
            continue
        if best is None or metric < best[0]:
            best = (metric, gateway)
    return best[1] if best else None


@lru_cache(maxsize=1)
def _read_route_table() -> str:
    try:
        with open("/proc/net/route", encoding="ascii") as handle:
            return handle.read()
    except OSError:
        return ""


def docker_published_port_trusted(environ: Mapping[str, str] | None = None) -> bool:
    """Whether the operator turned the published-port trust on AND the publish really is loopback-only."""
    values = os.environ if environ is None else environ
    if not _truthy(values.get(TRUST_DOCKER_PUBLISHED_PORT_ENV)):
        return False
    return str(values.get(PUBLISHED_BIND_HOST_ENV, "")).strip().casefold() in _LOOPBACK_BIND_HOSTS


def peer_host(scope: Mapping[str, Any]) -> str | None:
    """The transport peer of an ASGI connection scope (``scope["client"]``), or None."""
    client = scope.get("client")
    if not client:
        return None
    try:
        return str(client[0])
    except (IndexError, TypeError):
        return None


def request_is_local(
    peer: object,
    headers: Mapping[str, str] | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    route_table: str | None = None,
) -> bool:
    """Whether a request from ``peer`` with ``headers`` is this machine's own developer. See the module policy."""
    values = os.environ if environ is None else environ
    if is_public_environment(values.get("APP_ENV")):
        return False
    if headers is not None and {str(name).casefold() for name in headers.keys()} & set(FORWARDING_HEADERS):
        return False
    if is_loopback_peer(peer):
        return True
    if not docker_published_port_trusted(values):
        return False
    address = _parse_ip(peer)
    gateway = default_gateway(route_table)
    return address is not None and gateway is not None and str(address) == gateway
