# Architecture review - Signed-out local-admin decided by the request peer (issue #137)

- Reviewer role: **Delegated Architecture Reviewer** (AGENTS.md "Architecture review authority").
- Reviewer model: Claude Opus 5.5 (independent of the implementer). I did not write this change.
- Reviewed: branch `claude/sec-137-local-admin`, commit `f7a9dc77` ("Security: signed-out local-admin is decided by the request peer, not configuration (#137)"), diff `origin/main..f7a9dc77` (16 files, +605/-16).
- Date: 2026-10-13. Read-only review: no Docker, no app run, no browser. Not product approval and not activation authorization.

## VERDICT: APPROVED WITH CONDITIONS

The core design is sound. Locality is decided per request from the ASGI transport peer, forwarding headers revoke it, Host/Origin/PUBLIC_BASE_URL never grant it, a missing or unparsable peer fails closed, and config can only restrict. I found no remaining config-only grant of local-admin or of the `legacy` scope. The conditions below (C1-C3) must be met or explicitly accepted by the human in DECISION_LOG before merge. No P0.

## Evidence

- `python -m py_compile` on all touched Python: pass. `validate_project_memory.py` and `validate_architecture.py`: exit 0. `ruff check` on touched files: one finding, `UP035` at `scripts/validate_public_staging_readiness.py:10` (`typing.Mapping`), a line this commit did not touch.
- Whole-repo grep of `LOCAL_ADMIN_ALLOWED`, `_local_admin_allowed`, `local-admin`: the only grants are `auth_support.py` `require_admin` (`:162-167`), `/api/me`, `/api/session/bootstrap`, both now through `request_is_local_admin`. Other hits (`account_costs.py:37`, `billing_api.py:77`, `product/api.py:289`, `reading_canonical_cutover.py:78`) only read the resulting key, they do not grant.
- No WebSocket route exists in the app (`grep`), so non-HTTP scopes do not reach the middleware; the only WebSocket code is client-side scripts.
- **pytest was NOT run** (no dependencies on this host). Tests were reviewed by reading. Nothing here is CI evidence.

## What was verified (focus 1, 4, 5)

- `request_boundary.request_is_local` order is correct: public env, then forwarding header, then loopback (IPv4-mapped unwrapped through `_parse_ip`), then the gateway rule. `peer_host` returns None for `client=None`; `"localhost"` and `""` are not addresses and deny.
- `UserIsolationMiddleware` (`auth_support.py:616-664`) computes `foreign_signed_out` once and returns 403 for every non-public path, including non-`/api` pages. A public environment with auth off is also denied (stricter than before).
- :8021 (Google on): `foreign_signed_out = not AUTH_ENABLED and ...` short-circuits; behaviour unchanged. :8000 (staging, auth on): unchanged. Compose publish default on :8000 was already loopback via the staging `.env`.
- uvicorn `--proxy-headers` (default, trusts 127.0.0.1 only) can rewrite `scope["client"]` from `X-Forwarded-For`, but the header stays present so the request is revoked. Safe.
- Tests drive real ASGI scopes through `httpx.ASGITransport(client=...)` with the production middleware and guard, and include the required `test_config_local_does_not_imply_request_local`, Host/Origin/Referer spoof, forwarded-header, IPv6, mapped-loopback and `None` peer cases. The only existing assertions changed (`test_deployment_config.py`) asserted the old `0.0.0.0` default, which was the bug. Nothing was weakened.
- Root `conftest.py` defaults TestClient to 127.0.0.1. It cannot mask the denial tests, which use httpx `ASGITransport` with their own client. Residual risk is limited to other TestClient tests that would now pass as local (intended). If Starlette's TestClient lacked `client`, the fixture no-ops and signed-out tests would fail loudly, not pass.
- `python-multipart>=0.0.31` is in place. `docs/SECURITY_BOUNDARY.md` states the invariant. D-18X is a labelled placeholder.

## Findings

### P1-1 - The Docker gateway trust rests on a self-declared variable (focus 2)
- Where: `writing_coach/core/request_boundary.py:104-109` (`docker_published_port_trusted`), `compose.yaml` (`ORENA_PUBLISHED_BIND_HOST`, `ORENA_TRUST_DOCKER_PUBLISHED_PORT:-1`), `docs/SECURITY_BOUNDARY.md` threat model.
- Issue: the app cannot observe how the port is really published. `ORENA_PUBLISHED_BIND_HOST` is configuration that grants trust. It is derived from the same compose variable as the `ports:` line, so the stock compose file cannot disagree with itself, but a `compose.override.yaml`, a hand-edited `ports:`, or a `docker run -p 0.0.0.0:...` with the two variables copied from a doc lets a LAN host through. On Docker Desktop (Windows/WSL2) LAN traffic to a `0.0.0.0` publish also arrives from the bridge gateway, which is exactly the address trusted (the :8021 log shows `172.29.0.1`). The issue says config must never grant and accepts "an equally strong trusted-boundary mechanism"; a declaration is weaker than a peer check. The doc is honest about it. It is acceptable only as the narrowest practical trust, not as equal strength.
- Required: (a) a test that parses `compose.yaml` (and `scripts/agent_e2e/compose.yaml`) and asserts that the host in each `ports:` entry for the app equals the `ORENA_PUBLISHED_BIND_HOST` value and is loopback by default, so the two cannot drift silently; (b) make the loopback-only stance verifiable at startup where possible: log one line at boot naming the trust state (never a secret) so a LAN-published runtime is visible; (c) record in D-18X that this is an accepted declared-boundary mechanism with the override/hand-edit residual risk, and that the human accepts it. A stronger mechanism (not required now) would be a per-run random secret injected by the operator launch script and checked against a header added only by a trusted local forwarder, or a socket the host alone can reach.

### P1-2 - The public path is refused only by `start_public.ps1`; a plain `docker compose --profile public up` bypasses it (focus 3)
- Where: `start_public.ps1` (new preflight call), `compose.yaml` `cloudflared` service, no startup refusal in `auth_support.py`/`app.py`/`writing_coach/core/deployment.py`.
- Issue: the issue asks for refusal by "preflight/startup, not merely discouraged". A direct compose command starts the tunnel in front of a development, auth-off runtime without any check. Request-time denial does limit the damage: cloudflared reaches the app from its own container IP and adds `CF-*` headers, so no admin or `legacy` access results, and only public pages are served. That makes the practical exposure low, but the acceptance criterion ("cannot expose by accident") is met by the runtime layer, not the preflight layer the issue named.
- Required (either): (a) add an in-app startup refusal or loud error when `APP_ENV` is non-public, auth is disabled, and the process is configured for a public origin (`PUBLIC_BASE_URL` with a non-local host or `https`) or the tunnel profile is evidently active; or (b) the human records in D-18X that request-time denial is accepted as the fail-closed layer for the direct-compose path. Also add a compose-level guard on `cloudflared` (for example a required-variable interpolation that fails without a staging marker) if (a) is not taken.

### P2-1 - Forwarding-header denylist is incomplete, and a same-host reverse proxy with no headers is "local"
- Where: `request_boundary.py` `FORWARDING_HEADERS`.
- Issue: `Via`, `X-Client-IP`, `Client-IP`, `X-Cluster-Client-IP`, `X-Envoy-External-Address`, `Fastly-Client-IP`, `X-Forwarded-Server` are not listed. A host nginx that proxies to `127.0.0.1:8021` with default settings sends none of the listed headers, so remote users become loopback. This is inherent to peer-based locality and is outside the issue's stated scenarios, but it should be documented and the list extended.
- Required: extend the list; add a line to `docs/SECURITY_BOUNDARY.md` that a reverse proxy on the same host must never front an auth-off runtime.

### P2-2 - DNS rebinding is not addressed (pre-existing, cheap to restrict)
- Where: `request_boundary.request_is_local` does not look at `Host`.
- Issue: a web page in the developer's browser can rebind its domain to 127.0.0.1; the peer is then loopback with `Host: evil.example`, and the page reads local-admin APIs. Host cannot grant locality, but it can safely restrict it (loopback names/IPs or the configured host only).
- Required: as a follow-up (not blocking this change), reject signed-out local-admin when `Host` is not loopback, `localhost`, `host.docker.internal`, or the `PUBLIC_BASE_URL` host.

### P2-3 - Other containers can still reach a loopback publish through the host on Docker Desktop
- Where: `compose.yaml` (`extra_hosts: host.docker.internal:host-gateway`), `SECURITY_BOUNDARY.md` ("a process on the host ... is the developer's machine by definition").
- Issue: a container on a different network that dials `host.docker.internal:<port>` can arrive through the port proxy from the gateway and be trusted. The doc reasoning covers same-network containers only.
- Required: add this case to the threat model as an accepted residual risk.

### P2-4 - Operational risk is documented but not mitigated for existing lane runtimes
- Where: `DECISION_LOG.md` D-18X "Operational effect"; `scripts/start_orena_sandbox.ps1` and `persist_orena_sandbox_db.ps1` untouched.
- Issue: any runtime started with `docker run` and auth off (the 8011 sandbox web container, `orena-foundation-web`, was created outside compose) answers 403 to the host browser until recreated with the two variables, and an operator will read that as an outage. The change updates `mobile_qa_runtime.ps1` and the agent_e2e compose, but not these. `start_orena_sandbox.ps1` only restarts existing containers, so it cannot fix it.
- Required: add a CURRENT_HANDOFF note listing the lanes to recreate and the exact variables; and when the app refuses a gateway-peer request because the trust is off, log the peer and reason once (no secrets) so the 403 is diagnosable.

### P2-5 - D-18X placeholder and scope
- The decision id must be renumbered by the lead at merge and its status updated from "proposed" to reflect this review. Scope is otherwise tight; the non-root container and CSP items from the issue are explicitly deferred and recorded.

## Conditions to merge

- C1: P1-1 (a) compose-consistency test and (c) the recorded acceptance in D-18X.
- C2: P1-2 resolved by (a) or accepted by the human in writing in D-18X.
- C3: P2-4 handoff note. P2-1 to P2-3 may follow in a separate commit but must be tracked.

## Could not verify

- pytest and CI were not run (no dependencies on this host); the new and existing tests were reviewed by reading only.
- Real Docker behaviour (which source address Docker Desktop, userland-proxy and iptables modes present for host, LAN and cross-network traffic) was reasoned from the existing :8021 access log and Docker's documented behaviour, not measured.
- The behaviour of `cloudflared` header injection was assumed from Cloudflare's documented `CF-Ray`/`CF-Connecting-IP` behaviour.
- Staging :8000 and :8021 runtime behaviour was inferred from code paths, not observed.

Architecture review is not product approval and is not activation authorization.

---

## Re-review of 907ab88d (2026-10-13)

Reviewer: Delegated Architecture Reviewer, Claude Opus 5.5 (independent of the implementer). Scope: `git diff 72f371d9..907ab88d` (9 files). Read-only; pytest, Docker and the app were not run, so everything below is from reading code and tests.

### Conditions

- **C1 - met, risk acceptance still open.** `tests/test_local_boundary_deployment.py` discovers every launcher that mentions `ORENA_TRUST_DOCKER_PUBLISHED_PORT` (compose, agent_e2e compose, `mobile_qa_runtime.ps1`, scripts), asserts declared bind host == published host and loopback, and pins the known set, so a new launcher is picked up automatically. `compose.yaml` is pinned to a single expression for declaration and publish. The boot line (`trust_state_line`, called from `install_auth` when auth is off) names trust state, gateway and declared host and carries no secret (tested). D-18X says the residual risk is "pending human acceptance (not accepted)". That wording is correct and I hold the same position (below).
- **C2 - met.** `resolve_deployment_config` now refuses when `not public and not auth_enabled` and `public_exposure_markers` is non-empty (HTTPS origin, public host or address, tunnel token). It cannot refuse staging/production (`public` skips it), :8021 (auth on skips it, tested with an https origin), or plain local dev (empty URL, loopback, RFC1918, `.local`/`.lan`, dotless names all yield no marker). It runs after the origin/callback checks, so the existing "same origin" and bad-URL tests still raise their original errors. The one changed existing test (`test_same_origin_explicit_callback_override_is_supported`) used an https dev origin with no sign-in, which is exactly the configuration now refused; it gained Google credentials and a session secret and its assertion is unchanged. Legitimate, not weakened. Limit: `CLOUDFLARE_TUNNEL_TOKEN` is not passed to the app container by `compose.yaml`, so that marker only fires if the token is in the app's own environment; in the compose path the effective marker is a public `PUBLIC_BASE_URL`. A plain `compose --profile public up` with a dev loopback origin still starts, and is protected only by request-time denial (non-local peer and CF-* headers). I accept this as the fail-closed layer for that residual (P2, tracked).
- **C3 - met.** `SECURITY_BOUNDARY.md` gains the lane-runtime section, `CURRENT_HANDOFF.md` points to it, and a refused peer is logged once per address (cap 32, address only, no headers; tested with an Authorization header present). The log names the two variables to set when the peer is the gateway and trust is off.
- **P2-1 met** (extra headers revoke locality, tested). **P2-2/P2-3 met** as documented threat-model entries (DNS rebinding remains a follow-up, not fixed). **P2-5 met** (D-18X status updated; id still a placeholder to renumber at merge).

### Final verdict: APPROVED WITH CONDITIONS

Remaining conditions before merge:

1. **Human decision on the declared-bind-host residual risk (P1-1, unchanged in substance).** The mitigations reduce drift in the repository's own launchers, but the app still cannot observe how the port is really published; a hand-edited `ports:`, a `compose.override.yaml` or a `docker run -p 0.0.0.0:` that copies the two variables grants LAN callers local-admin on Docker Desktop. I do not consider this accepted. It needs the human's explicit acceptance (or a decision to require the stronger per-run-secret mechanism), recorded in D-18X, before merge.
2. Renumber D-18X at merge and update its status line.
3. Tracked follow-ups, not blocking: Host-header restriction against DNS rebinding; `CLOUDFLARE_TUNNEL_TOKEN` is not visible to the app container.

Not product approval and not activation authorization. Reviewed commit: 907ab88d.
