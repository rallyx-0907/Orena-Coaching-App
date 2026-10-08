# BECOMING Public PostgreSQL Staging Contract

## Authoritative architecture

Production-like staging uses this path:

```text
Internet -> Cloudflare HTTPS -> Cloudflare Tunnel -> writing-coach:8000 -> PostgreSQL
```

PostgreSQL is the authoritative product runtime. Staging requires both:

```env
PERSISTENCE_BACKEND=postgresql
POSTGRES_RUNTIME_URL=postgresql+psycopg://...
```

`POSTGRES_SHADOW_URL` is reserved for historical migration, rehearsal, and
parity tooling. It is not a runtime selector and cannot replace
`POSTGRES_RUNTIME_URL`. Startup verifies PostgreSQL connectivity and the
existing Alembic head, then fails closed if either check fails. Startup does
not migrate, import, fall back to SQLite, dual-write, or reverse-sync.

The retained SQLite volume is frozen rollback/archive evidence. Do not delete
or modify it as part of staging startup.

## Required public configuration

Store real values only in the deployment environment or an ignored local
`.env`; never commit them.

```env
# staging: public, product-like (:8000, D-146); production is reserved for the final product.
APP_ENV=staging
APP_BIND_HOST=127.0.0.1
PUBLIC_BASE_URL=https://staging.example.com
SESSION_SECRET=replace-locally
GOOGLE_CLIENT_ID=replace-locally
GOOGLE_CLIENT_SECRET=replace-locally
PERSISTENCE_BACKEND=postgresql
POSTGRES_RUNTIME_URL=replace-locally
CLOUDFLARE_TUNNEL_TOKEN=replace-locally
```

The example hostname and replacement markers are not deployable credentials.
Do not paste real secret values into commands, logs, tickets, or review files.

For production-like staging, create an ignored local `.env` from the example
and replace only its local staging values. Set `APP_BIND_HOST=127.0.0.1` there.
Run the secret-safe preflight against that explicit source before starting:

```powershell
python scripts/validate_public_staging_readiness.py --env-file .env
if ($LASTEXITCODE -ne 0) { throw 'Public staging preflight failed.' }
```

The preflight reports only requirement names and PASS/FAIL status. It never
prints the Google client secret, session secret, database URL, or tunnel token.
The explicit env file is the complete validation source: process environment
values do not override or supplement it. It accepts `KEY=value`, blank lines,
and `#` comments; duplicate keys use the last assignment.

## Google OAuth contract

The canonical callback is always:

```text
PUBLIC_BASE_URL + /auth/google/callback
```

For example, the placeholder origin above resolves to
`https://staging.example.com/auth/google/callback`. Register the real staging
callback as an Authorized redirect URI in Google Cloud Console.

`GOOGLE_REDIRECT_URI` remains an optional compatibility override. When set, it
must normalize to the same `PUBLIC_BASE_URL` origin and end exactly in
`/auth/google/callback`.

Production fails closed when the public origin is absent, HTTP, or local; when
either Google OAuth credential is absent; or when `SESSION_SECRET` is absent.
OAuth state, PKCE, nonce, verified-email checks, and secure cookies remain
mandatory. Health and readiness output never exposes OAuth configuration.

## Cloudflare Tunnel contract

Cloudflared reaches `writing-coach:8000` over the Compose network. The host
application port is loopback-bound with `APP_BIND_HOST=127.0.0.1`; no inbound
router port-forward is required. PostgreSQL and Ollama must not be published to
the Internet. Configure the named tunnel outside this repository to route the
real staging hostname to `http://writing-coach:8000`.

Cloudflare Access is not part of this stage. Do not hardcode a real hostname in
source or Compose configuration.

## Exact staging start order

The PostgreSQL schema and imported data were accepted during the completed
cutover. Do not rerun migration, import, rehearsal, or parity commands here.

### A. Validate configuration

```powershell
python scripts/validate_public_staging_readiness.py --env-file .env
if ($LASTEXITCODE -ne 0) { throw 'Public staging preflight failed.' }
```

### B. Start PostgreSQL

```powershell
docker compose --profile postgres up -d postgres
```

### C. Verify PostgreSQL health

```powershell
docker compose --profile postgres exec postgres sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL is not healthy; staging aborted.' }
```

Do not proceed until PostgreSQL is healthy. Do not run Alembic automatically;
the application performs a read-only revision equality check during startup.

### D. Start or recreate the application

```powershell
docker compose --profile postgres up -d --build --force-recreate writing-coach
```

If the runtime URL, connection, or Alembic revision is wrong, the application
must remain unavailable rather than fall back to SQLite.

### E. Verify local health and readiness

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/readiness
```

Require successful responses with production environment and authentication
enabled. These endpoints intentionally omit secrets and database URLs.

### F. Start Cloudflare Tunnel

```powershell
docker compose --profile public up -d cloudflared
```

### G. Verify public HTTPS

```powershell
Invoke-RestMethod "$env:PUBLIC_BASE_URL/api/health"
Invoke-RestMethod "$env:PUBLIC_BASE_URL/api/readiness"
```

Require HTTPS success through the configured public hostname.

### H. Verify Google login

Open the public HTTPS origin in a browser. Complete Google login and confirm the
callback returns to `/`. Treat state, callback, cookie, or login failure as a
staging failure.

### I. Verify authenticated application behavior

Using the existing signed-in browser session:

1. Confirm `/api/product/me` succeeds against the PostgreSQL runtime.
2. Open the canonical `/` application.
3. Smoke Writing without changing its BETA release state.
4. Switch between English and Chinese and confirm the same session/deployment
   contract applies.
5. Confirm Library, Journey, and Profile load normally.

### J. Accept or stop staging

Accept staging only after every prior check passes. If any check fails, stop
the public tunnel and application, preserve PostgreSQL for diagnosis, and keep
the SQLite archive untouched:

```powershell
docker compose stop cloudflared writing-coach
```

Do not switch public staging to SQLite, delete either volume, import again, or
reverse-sync data to make a failed check pass.

## Local development exception

An isolated developer/test process may explicitly use
`PERSISTENCE_BACKEND=sqlite`. That mode is not the deployed product authority
and is never a production fallback. Host binding beyond loopback is permitted
only for an intentional local LAN/Tailscale workflow with an appropriate local
origin; public staging remains loopback-only behind Cloudflare Tunnel.

The checked-in `.env.example` intentionally uses this working developer mode:
`APP_ENV=development`, `APP_BIND_HOST=0.0.0.0`,
`PUBLIC_BASE_URL=http://127.0.0.1:8000`, and explicit SQLite. It does not alter
the PostgreSQL-authoritative staging contract above.

## Health and readiness data policy

- `GET /api/health` exposes liveness/status fields only.
- `GET /api/readiness` exposes `ready`, `environment`, and `auth_enabled` only.

Neither endpoint returns database URLs or passwords, OAuth credentials,
session secrets, callback configuration, API keys, or Cloudflare tokens.
