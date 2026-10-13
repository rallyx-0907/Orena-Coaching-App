# Security boundary: who is "the local developer"

Invariant: **local-admin is a property of the actual trusted request boundary, not a hostname or configuration hint.**

Issue #137 (P1) showed the failure that escaped the 2026-10-04 security review: `_local_admin_allowed()` looked only
at deployment configuration (`APP_ENV`, `PUBLIC_BASE_URL`), and Compose published the port on every interface. With
sign-in off, any machine that could reach port 8000 was then the local administrator and shared the one `legacy`
learner scope. Config-local does not imply request-local.

## Layers

1. **Primary boundary: the deployment config and launcher.** Every official launcher publishes the app on loopback
   (`127.0.0.1`) by default; the only route to anything wider is the insecure-named `ORENA_INSECURE_DEV_LAN_BIND_HOST`.
   This is test-locked across all compose files and launch scripts, not left to environment variables inside the app.
2. **Second layer: the host-side publish assertion (issue #140).** After each official launcher starts the app
   container, `scripts/assert_published_loopback.py` reads Docker's actual port bindings (only the two port fields,
   never the container config or environment) and stops the container, with a clear message and a non-zero exit, when
   any binding of the app port is not loopback. See "Host-side publish assertion".
3. **Third layer: the app's per-request peer check** (below), which keeps a remote caller from being treated as local.
4. **Defense-in-depth: the startup refusal** of an unauthenticated development runtime configured for the public.

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
LAN address). The name is deliberate: the port is then exposed to the network. An auth-disabled runtime with this
opt-in refuses to start (startup refusal below), so a LAN runtime needs Google sign-in. There is no switch that grants
a remote peer signed-out access.

## Public and tunnel path fails closed

`python scripts/validate_public_staging_readiness.py --env-file .env` refuses a non-public `APP_ENV` with sign-in off
("Refusing to expose a development runtime with authentication disabled"), a non-loopback `APP_BIND_HOST`, and any
set `ORENA_INSECURE_DEV_LAN_BIND_HOST`. `start_public.ps1` runs it before `docker compose --profile public up`.
Behind a tunnel, a development runtime would also refuse the caller at request time (forwarding headers, non-local
peer), so the preflight is not the only layer.

## Lane runtimes

A signed-out runtime started with `docker run` (for example the :8011 sandbox `orena-foundation-web`) answers 403 to
the host browser after this change until it is recreated (only the human restarts Docker) with all of:
`-p 127.0.0.1:PORT:8000`, `-e ORENA_PUBLISHED_BIND_HOST=127.0.0.1`, `-e ORENA_TRUST_DOCKER_PUBLISHED_PORT=1`, and a
loopback `PUBLIC_BASE_URL` (an HTTPS or public origin with sign-in off is refused at startup). :8021 (sign-in on) and
:8000 staging are unchanged. The boot line and the once-per-address refusal log say which part is missing.

## Host-side publish assertion

The app cannot see where Docker publishes its port; the host can. After `docker compose up` or `docker run`, each
official launcher runs `python scripts/assert_published_loopback.py --container <id> --port 8000`:

- Reads only the container's `.NetworkSettings.Ports` and `.HostConfig.PortBindings`, each through a `--format`
  template. Never the container config or environment.
- Passes only when every binding of 8000/tcp is loopback (127.0.0.0/8, `::1`, `localhost`: the `is_loopback_host`
  rule). Refuses `0.0.0.0`, `::`, an empty `HostIp` (Docker's all interfaces), any other address, an unpublished port
  and an unreadable Docker answer. A mixed IPv4 + IPv6 list passes only if every entry does.
- On refusal it names the container and address, stops the container and exits non-zero (2 refused, 3 unreadable); the
  launcher exits non-zero (the Python runners raise).
- The LAN opt-in (`ORENA_INSECURE_DEV_LAN_BIND_HOST` set in the launching shell) lets a wide publish pass only when an
  unauthenticated `GET /api/me` on the loopback port answers 401, i.e. sign-in is on. The wrapper does not read
  container env. An opt-in only in `.env` fails closed.
- Launchers: `start_docker.ps1`, `start_dev.ps1`, `start_public.ps1` (compose.yaml), `scripts/agent_e2e/run.py`,
  `scripts/agent_live/run.py`, `scripts/mobile_qa_runtime.ps1`, `scripts/product_restore_rehearsal.ps1`,
  `scripts/staging_update.ps1`. `scripts/staging_8000_deploy.ps1` (human-operated) gets a read-only `--no-stop` check
  that fails before success is declared and changes nothing else.
- Not covered: a container started by hand or by a script outside this inventory; a publish edited after the check
  ran (it is a point-in-time check at launch); every other residual below.

## Startup refusal and diagnostics

Development with sign-in off is **loopback-only**. `resolve_deployment_config` (so the app and the preflight alike)
refuses to start when `APP_ENV` is not staging/production, Google sign-in is off, and any declared exposure is not
loopback. Declared means: the host of `PUBLIC_BASE_URL` and of `GOOGLE_REDIRECT_URI`, `ORENA_PUBLISHED_BIND_HOST`
(where the container's port is published), `ORENA_INSECURE_DEV_LAN_BIND_HOST`, and `CLOUDFLARE_TUNNEL_TOKEN` in the
process environment. Only `localhost`, 127.0.0.0/8, `::1` and `::ffff:127.x` are loopback. Refused: every other address
(private 10/172.16/192.168, CGNAT 100.64/10, link-local, unique-local fc00::/7, `0.0.0.0`, `::`, public v4/v6) and
every other name (single-label, `.local`, `.lan`, `.internal`, public names), whatever the scheme.

`APP_BIND_HOST` and the uvicorn listen address inside the container are deliberately **not** read: a container must
listen on 0.0.0.0 in its own network namespace, and what can reach it is decided by the publish, which is the declared
`ORENA_PUBLISHED_BIND_HOST`. `docker compose --profile public up` run directly, without `start_public.ps1`, therefore
cannot serve an unauthenticated development runtime configured for exposure; request-time denial remains the second
layer. LAN development therefore **requires Google sign-in**; LAN with sign-in off is refused at startup.

With sign-in off, the app logs one boot line naming the gateway-trust state (on/off, gateway address, declared bind
host) and logs each refused non-local peer address once per process, with a hint when the refused peer is the
container gateway but the trust is off. Addresses only; no headers, no secrets.

The forwarding-header list also includes `Via`, `Client-IP`, `X-Client-IP`, `X-Cluster-Client-IP`, `X-Forwarded`,
`Forwarded-For`, `X-Forwarded-Server`, `X-Original-Forwarded-For`, `Fastly-Client-IP`, `X-Envoy-External-Address`.

## Known residuals and follow-ups (architecture review 2026-10-13)

- **Self-declared bind host.** The app cannot observe how Docker publishes the port; `ORENA_PUBLISHED_BIND_HOST` is
  configuration. An operator who hand-edits the publish from `127.0.0.1` to `0.0.0.0` (a `compose.override.yaml`, a
  `ports:` edit, a `docker run -p 0.0.0.0:...`) without changing the variables the app reads defeats it, and on Docker
  Desktop LAN traffic to such a publish arrives from the trusted gateway. This is a manual, unsupported
  misconfiguration. **Accepted by the human on 2026-10-13 as a documented residual risk**, on these conditions:
  signed-out lanes are local/development only, and every official launcher is test-locked to a loopback publish
  (`tests/test_local_boundary_deployment.py` scans all of them). It is not a P1 blocker.
- **Host-side runtime assertion (GitHub issue #140): done for the official launchers** (see "Host-side publish
  assertion"); a hand-started container outside them remains uncovered. A stronger in-app alternative: a per-run secret injected by the launch
  script and checked against a header only a trusted local forwarder adds.
- **Same-host reverse proxy.** A proxy on the same host that forwards to a loopback or gateway address and adds no
  forwarding header makes remote callers look local. Never front an auth-off runtime with a reverse proxy.
- **Other containers via `host.docker.internal`.** A container on another network that dials the host's published
  loopback port arrives from the gateway and is trusted. Accepted residual risk of the published-port rule.
- **DNS rebinding (follow-up, no code yet).** A page in the developer's browser can rebind its name to 127.0.0.1;
  the peer is then loopback with a foreign `Host`. `Host` can safely restrict locality (loopback names, the
  `PUBLIC_BASE_URL` host, `host.docker.internal`); not implemented here.

## Tests

`tests/test_request_boundary.py` (policy, spoofed Host/Origin/X-Forwarded-For, config-local is not request-local, real
ASGI requests with a client address), `tests/test_deployment_config.py` (default bind), and
`tests/test_public_staging_readiness.py` (preflight refusal), `tests/test_assert_published_loopback.py` (the publish
decision and command-line contract) and the assertion inventory in `tests/test_local_boundary_deployment.py`.

## Not covered here (follow-ups)

Running the container as non-root, and a global Content-Security-Policy with an inventory of `raw()`/`innerHTML`.
