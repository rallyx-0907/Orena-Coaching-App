# The agent's live run

`run.py` drives a throwaway sandbox (`compose.yaml`, project `orena-agent-live`, on
127.0.0.1:8013, or :8015 when :8013 is taken) with a real provider. It is the
[PROVIDER] gate: it will not run without `--approved` and the human-approved
`--cap-usd`, and it takes the sandbox down however it ends (done, failed, cost cap,
Ctrl+C, terminated).

```bash
python scripts/agent_live/run.py --plan
python scripts/agent_live/run.py --approved --cap-usd 0.30 --gemini-env <.env holding GEMINI_*> --flows coaching,notes
```

Only `GEMINI_*` is read from the env file, and nothing from it is printed. Results go
to a JSON file outside the repository (`--out`).

## The live-provider lock (shared by every lane)

Lanes on one machine share one Docker runtime and one provider quota, so they queue
on a single lock before any real provider call:

```text
%USERPROFILE%\.orena\live-provider.lock
```

It sits outside every repository and is never committed.

**The file.** It holds one JSON object:

```json
{"lane": "feature/orena-intelligence", "pid": 12345, "host": "MACHINE",
 "started_at": "2026-09-28T09:15:02.123456+00:00", "cap_usd": 0.3, "purpose": "scripts/agent_live/run.py"}
```

| Field | Meaning |
| --- | --- |
| `lane` | the branch or worktree that holds it |
| `pid` | the Windows process id that will release it. In Git Bash use `cat /proc/$$/winpid`, not `$$` |
| `host` | the machine name; `pid` is only judged on the same host |
| `started_at` | when it was taken, UTC, ISO 8601 |
| `cap_usd` | the approved cost cap of the run |
| `purpose` | a short free text |

**The rules.**

1. **Take it** before starting a sandbox or calling a real provider. Create the file
   exclusively (`O_CREAT|O_EXCL`; in PowerShell `New-Item` without `-Force`). If it
   already exists, it is held.
2. **Release it** in the same `finally`/`trap` that takes your sandbox down, after the
   sandbox is down. Remove it only if it is still your record.
3. **Held:** look again every 30 s, for at most 30 min. Then stop and tell the human.
   Never stop another lane's containers.
4. **Orphan:** the lock may be removed, and the removal reported in the run's result,
   in two cases. Either its holder on this host is no longer running, or it has been
   held for more than 60 min. Re-read it just before removing, and leave it if it has
   changed.

`run.py` does all of this through `lock.py`, and lists what happened in the result's
`"lock"` field. Another lane can wrap any command with it:

```bash
python scripts/agent_live/lock.py status
python scripts/agent_live/lock.py run --lane <lane> --cap-usd 0.20 -- <command ...>
```
