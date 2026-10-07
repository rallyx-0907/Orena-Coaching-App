# Trying "sign in and use the app" on :8021 (new UI, `/next`)

Status: code and tests are done; nothing is configured. OAuth credentials, redirect URIs and turning
authentication on are human gates. With `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` unset the app behaves as it did.

## What the human does

1. **OAuth client.** In the Google Cloud console, reuse an existing Web-application OAuth client or create one
   (consent screen scopes `openid`, `email`, `profile`; add your Google account as a test user while the app is in
   Testing).
2. **Authorised redirect URIs** (exact, one per origin you want to use):
   - `http://localhost:8021/auth/google/callback`
   - `https://calis-pc.taila8a28f.ts.net/auth/google/callback`
3. **Pick one origin per run.** The server derives its callback from `PUBLIC_BASE_URL` and refuses a
   `GOOGLE_REDIRECT_URI` on another origin, so one container signs in on one origin. Use the localhost one for the
   desktop, the tailnet name (HTTPS, so the session cookie is `Secure`) for a phone.
4. **Hand the lane these values** (names only here; give the values in your own terminal or message, never in a doc):

| Variable | Purpose |
| --- | --- |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Both or neither. **`AUTH_ENABLED` is true exactly when both are set** (`core/deployment.py`). |
| `GOOGLE_REDIRECT_URI` | Optional; if set it must equal `PUBLIC_BASE_URL/auth/google/callback`. |
| `PUBLIC_BASE_URL` | `http://localhost:8021` or `https://calis-pc.taila8a28f.ts.net`. |
| `SESSION_SECRET` | Required once auth is on (32+ characters when `APP_ENV=production`). Any long random string. |
| `APP_ENV` | `development` is right for a lane runtime (`production` demands HTTPS, a non-local host and a 32+ character secret). |
| `BOOTSTRAP_OWNER_EMAIL` | Your Google email. It makes the account an administrator and is the only email that can claim legacy SQLite data. |
| `PLATFORM_ADMIN_EMAILS` | Optional, comma separated. |

   The new UI shows non-administrators a plain "limited" notice (the internal-review gate), so the account you sign
   in with must be `BOOTSTRAP_OWNER_EMAIL` or in `PLATFORM_ADMIN_EMAILS`.

## What happens to the data already on :8021

With auth off, every request runs as the local key `legacy`. Learner records live in PostgreSQL under that key
(`orena-next-verify-postgres`); a Google account has its own key (its Google `sub`).

`maybe_claim_legacy_data(email, google_sub)` runs at every sign-in and acts only when all of these hold:
`BOOTSTRAP_OWNER_EMAIL` is set, the signing-in email equals it (case-insensitive), the account's English SQLite file does
not exist yet, and the legacy `WRITING_DB` file exists. It then copies that one file. **It does not move PostgreSQL
rows.** Account settings, the learner profile, drafts, conversations, notes, imports and everything else under `legacy`
stay under `legacy`; the first Google sign-in starts an empty account (Welcome, then setup). Turning auth off again
shows the `legacy` data as before. Moving PostgreSQL data between keys is learner-data persistence, reserved (AGENTS
section 7); recorded as SIGN-3 in `UI_BACKEND_GAPS.md`. Decision for the human: accept a fresh account for the trial
(recommended), or ask for a reviewed claim proposal.

## What the lane does once the values arrive

1. Read the current `orena-next-verify-web` container's image, mounts, network and variable *names* (values are never
   printed), then recreate it with the same image, mounts, network and variables **plus** the names above. The
   PostgreSQL and media volumes are reused untouched, and no migration runs (nothing here changes the schema).
2. Check `GET /next` answers 200 signed out and `GET /api/me` answers 401, then sign in once in a browser tab.
3. The worker container, :8000, :8010 and every other runtime are not touched.

## What the learner sees

- Signed out, `/next` opens Welcome: **Get started** goes to Account in create mode, **I already have an account**
  goes to Account in log-in mode. **Continue with Google** goes to `/auth/google?next=...`.
- Return targets: Get started returns to `/next#/welcome?step=languages`; an existing account returns to `/next#/`,
  where the entry rule opens Today (profile exists) or Welcome (it does not).
- Signed in: the Account step shows the identity card. Profile > Sign out ends the session and returns to `/next`.
- A 401 from any request while the app is open sends the learner to Welcome.
- The server accepts a `next` target only if it is `/next` or continues with `/`, `?` or `#`, with no scheme, `//`,
  backslash, whitespace or control character, at most 512 characters; anything else becomes `/next`.

Not built: the email and password form (SIGN-1 in `UI_BACKEND_GAPS.md`).
