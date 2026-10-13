# Security boundary: who is "the local developer"

Invariant: **local-admin is a property of the actual trusted request boundary, not a hostname or configuration hint.**

Issue #137 (P1) showed the failure that escaped the 2026-10-04 security review: `_local_admin_allowed()` looked only
at deployment configuration (`APP_ENV`, `PUBLIC_BASE_URL`), and Compose published the port on every interface. With
sign-in off, any machine that could reach port 8000 was then the local administrator and shared the one `legacy`
learner scope. Config-local does not imply request-local.

## What "local" means now

Signed-out developer behaviour (the `local-admin` administrator, the shared `legacy` learner scope) is decided per
request, from the transport peer of the connection, in `writing_coach/core/request_boundary.py`. It is applied by
`require_admin`, `/api/me`, `/api/session/bootstrap` and `UserIsolationMiddleware` in `auth_support.py`.

A request is local only if every step passes:

1. The runtime is not public. Staging and production never have a signed-out developer (D-146).
2. The request carries no forwarding header (`Forwarded`, `X-Forwarded-*`, `X-Real-IP`, `CF-*`, `True-Client-IP`).
   A proxy or tunnel put it there; the caller is not at this machine.
3. The peer is a loopback address (127.0.0.0/8, `::1`, IPv4-mapped loopback), or
4. all of: `ORENA_TRUST_DOCKER_PUBLISHED_PORT` is on, `ORENA_PUBLISHED_BIND_HOST` is a loopback address, and the peer
   is exactly this container's IPv4 default gateway.

Never evidence of locality: `Host`, `Origin`, `Referer`, `X-Forwarded-For` or `PUBLIC_BASE_URL`. A missing or
unparsable peer (a unix socket) is not local.

Configuration may only restrict. `LOCAL_ADMIN_ALLOWED` (public environment, non-local `PUBLIC_BASE_URL`, optional
`ALLOW_LOCAL_ADMIN`) is a necessary condition for the administrator and never sufficient: the request must also be
local. A non-local request to an auth-disabled development runtime gets 403 on every route that is not a public page.

## The Docker case

The app normally runs in a container with the port published (`127.0.0.1:8021->8000`). A browser on the host reaches
it through Docker's port proxy, so inside the container the peer is the bridge gateway (for example `172.29.0.1`),
not `127.0.0.1`. Refusing it would break every signed-out local workflow; trusting private ranges would let the LAN in.

Rule 4 trusts one address, the container's own default gateway read from `/proc/net/route`, and only while the
operator's published port is the boundary: the host side of the publish is loopback. Threat model:

- Another LAN machine cannot connect to a loopback publish, so the gateway peer is a process on this host.
- If the publish were `0.0.0.0`, LAN traffic would arrive from the same gateway address, so the trust is void
  (`ORENA_PUBLISHED_BIND_HOST` not loopback) and those requests are denied.
- Another container on the Compose network has its own address, not the gateway, and is denied. A process on the host
  that connects to the published port is the developer's machine by definition.
- The trust variables are operator configuration. An operator who declares a loopback publish while publishing on a
  LAN address defeats it; `compose.yaml` derives both values from the one publish setting so they cannot disagree.
- Not a defence against a malicious process already on the developer's machine; that is outside this boundary.

`compose.yaml` sets `ORENA_PUBLISHED_BIND_HOST` to the host it really publishes on and the trust flag to on. A
`docker run` that does not set them gets rule 3 only and fails closed. A runtime started with `-p 127.0.0.1:PORT:8000`
that wants signed-out local use sets `ORENA_PUBLISHED_BIND_HOST=127.0.0.1 ORENA_TRUST_DOCKER_PUBLISHED_PORT=1`.

## Default bind and the LAN opt-in

The published port defaults to `127.0.0.1`. `APP_BIND_HOST` is the staging contract's loopback value and no longer
widens the publish. To reach a dev runtime from another machine, set `ORENA_INSECURE_DEV_LAN_BIND_HOST=0.0.0.0` (or a
LAN address). The name is deliberate: the port is then exposed to the network. Signed-out use is still refused for
those callers (they are not local), so a LAN runtime needs Google sign-in. There is no switch that grants a remote
peer signed-out access.

## Public and tunnel path fails closed

`python scripts/validate_public_staging_readiness.py --env-file .env` refuses a non-public `APP_ENV` with sign-in off
("Refusing to expose a development runtime with authentication disabled"), a non-loopback `APP_BIND_HOST`, and any
set `ORENA_INSECURE_DEV_LAN_BIND_HOST`. `start_public.ps1` runs it before `docker compose --profile public up`.
Behind a tunnel, a development runtime would also refuse the caller at request time (forwarding headers, non-local
peer), so the preflight is not the only layer.

## Tests

`tests/test_request_boundary.py` (policy, spoofed Host/Origin/X-Forwarded-For, config-local is not request-local, real
ASGI requests with a client address), `tests/test_deployment_config.py` (default bind), and
`tests/test_public_staging_readiness.py` (preflight refusal).

## Not covered here (follow-ups)

Running the container as non-root, and a global Content-Security-Policy with an inventory of `raw()`/`innerHTML`.
