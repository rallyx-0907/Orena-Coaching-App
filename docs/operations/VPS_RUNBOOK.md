# Moving Orena to a VPS (completion plan item 6)

:8000 on this machine is the product (D-127). This runbook moves it to a Linux VPS **from a backup**, so the
VPS starts with exactly the data :8000 had. Every step is the human's: a lane never runs a command on :8000 or
on the VPS. The backup and the restore are rehearsed (§6) before the real move.

## 0. Before you start (gates)

- A VPS: Ubuntu 24.04 LTS, 2 vCPU, 4 GB RAM, 60 GB SSD at minimum. PostgreSQL, web, worker and media fit.
  Choose a region near the learners (Singapore for Vietnam).
- The domain, plus DNS and Cloudflare access (a human gate).
- Google OAuth: add `https://<domain>/auth/google/callback` to the OAuth client's redirect URIs (a human gate).
- A maintenance window. Learners who write during the move lose that writing unless :8000 is stopped first
  (§3.1).

## 1. Prepare the VPS (once)

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install ca-certificates curl git ufw unattended-upgrades
curl -fsSL https://get.docker.com | sudo sh            # Docker Engine + compose plugin
sudo usermod -aG docker "$USER"                         # log out and back in
sudo ufw default deny incoming && sudo ufw allow OpenSSH && sudo ufw enable
```

- Do not open 8000 to the internet. The app binds to `127.0.0.1` (`APP_BIND_HOST=127.0.0.1`), and the public
  door is the Cloudflare tunnel (§4) or a reverse proxy on 443.
- SSH: use keys only, and set `PasswordAuthentication no` in `/etc/ssh/sshd_config`.

## 2. Code and settings

```bash
git clone <repository> orena && cd orena && git checkout main
cp .env.example .env && chmod 600 .env
```

Fill in `.env` and never commit it. Copy each value from :8000's `.env` by hand; never print it to a shared
screen or log.

| Variable | Value on the VPS |
| --- | --- |
| `APP_ENV` | `production` |
| `PUBLIC_BASE_URL` | `https://<domain>` |
| `GOOGLE_REDIRECT_URI` | `https://<domain>/auth/google/callback` |
| `SESSION_SECRET` | at least 32 characters (the app refuses less). Keep :8000's value to keep everyone signed in, or a new one to sign everyone out once |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | the same OAuth client |
| `AI_PROVIDER_SECRETS_KEY` | **the same as :8000**, or the saved provider keys cannot be decrypted (re-enter them in Admin > AI if lost) |
| `POSTGRES_RUNTIME_URL`, `POSTGRES_PASSWORD` | a new strong password for the VPS database |
| `APP_BIND_HOST` | `127.0.0.1` |
| `PLATFORM_ADMIN_EMAILS`, `BOOTSTRAP_OWNER_EMAIL` | as on :8000 |
| `ORENA_ACCOUNT_BACKBONE`, `BILLING_*`, `AGENT_*` | as on :8000; billing stays off until its own gates |

Build from this checkout. **The image carries the migration chain**, so an image built from another checkout
expects another schema revision and the app refuses to start. The rehearsal caught exactly this: an old image
expecting 0012 against a 0025 database.

```bash
docker compose build writing-coach
```

## 3. Move the data

### 3.1 On :8000 (the human, Windows)

Stop writes if you want a perfect cut. Run `docker compose stop writing-coach reading-worker` on :8000; this
keeps PostgreSQL running. Then take the backup:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\product_backup.ps1 `
  -Postgres ai-writing-coach-postgres-1 -DbUser becoming -DbName becoming -DataVolume ai-writing-coach-data
powershell -ExecutionPolicy Bypass -File scripts\product_restore_rehearsal.ps1 -Backup <BACKUP folder>   # must say RESTORE=PASS
scp -r <BACKUP folder> <user>@<vps>:~/orena-backup
```

The backup folder holds learners' data. Copy it only over SSH, keep it access-controlled, and delete the copy
on the VPS after §5.

### 3.2 On the VPS

```bash
cd ~/orena
B=~/orena-backup
sha256sum "$B/database.dump" "$B/files.tar.gz"     # compare with manifest.json "files"
docker compose up -d postgres                      # creates the named volumes, empty
until docker compose exec -T postgres pg_isready -U becoming -d becoming; do sleep 1; done
docker compose cp "$B/database.dump" postgres:/tmp/database.dump
docker compose exec -T postgres pg_restore -U becoming -d becoming --no-owner --no-acl /tmp/database.dump
docker compose exec -T postgres rm /tmp/database.dump
docker compose run --rm --no-deps -v "$B:/backup:ro" writing-coach sh -c "tar xzf /backup/files.tar.gz -C /data"
```

Check the restore against the backup:

- `select version_num from alembic_version` must equal `schema_revision` in `manifest.json`.
- Spot-check row counts against `table_counts`, for example `users`, `reading_articles` and `audit_logs`:
  `docker compose exec -T postgres psql -U becoming -d becoming -c "select count(*) from users"`.

If the checkout is newer than the backup's revision, migrate now, exactly as in `PRODUCT_8000_UPDATE.md`
step 5. Startup never migrates (D-002).

## 4. Start and open the door

```bash
docker compose up -d writing-coach reading-worker
curl -fsS http://127.0.0.1:8000/api/health
```

- **Cloudflare tunnel** (recommended: no open port). Set `CLOUDFLARE_TUNNEL_TOKEN` in `.env` and start the
  tunnel with `docker compose --profile public up -d cloudflared` (the `cloudflared` service in `compose.yaml`).
  Point the domain at the tunnel in Cloudflare.
- **Or a reverse proxy**: Caddy on 443 forwarding to `127.0.0.1:8000`. Caddy obtains the certificate itself.

`scripts/validate_public_staging_readiness.py --env-file .env` must pass before the door opens.

## 5. Check, then switch

- Sign in with Google at `https://<domain>`. Then open one Reading text, one Listening item, and Admin >
  Overview; its content counts must match :8000's.
- Check the responses carry the security headers: `curl -sI https://<domain>/api/health` shows `strict-transport-security`.
- Keep :8000 stopped (not removed) for a week as the way back. Its volumes are untouched.
- Delete `~/orena-backup` on the VPS. Keep the Windows copy as the rollback point.

## 6. Backups on the VPS (daily)

`scripts/product_backup.ps1` is PowerShell. On the VPS, the same backup is `pg_dump -Fc` plus a tar of the
data volume. Copy them off the machine every day, for example to object storage. Keep 7 daily and 4 weekly
copies. Once a month, run `scripts/product_restore_rehearsal.ps1` on a downloaded copy: a backup that has
never been restored is not a backup.

## 7. Rollback

If the VPS is wrong at §5, start :8000 again with `docker compose start writing-coach reading-worker` on the
Windows machine, and point DNS back. Nothing was written to :8000 after the backup, if writes were stopped in
§3.1.

## Rehearsal record

2026-10-05 (lane, :8021 sample data, never :8000):

1. `product_backup.ps1` backed up :8021 (read-only).
2. `product_restore_rehearsal.ps1` restored it into a new PostgreSQL and a new web container on 127.0.0.1:8031,
   all throwaway, and booted Orena on it.

**RESTORE=PASS**, 10 checks:

- integrity of both files;
- revision 20261004_0025 and 57 tables restored exactly;
- `/api/health`;
- Admin > Overview;
- the Reading library, 24 texts listed in English (55 in the backup);
- the media library, 6 items;
- 142 of 142 files on /data;
- the schema unchanged by startup.

The first attempt failed for a real reason that this runbook now covers: the old image's migration chain
expected 0012.

**The same rehearsal on a :8000 backup is the human's** (§3.1), before the real move.
