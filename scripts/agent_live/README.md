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
on a single lock before any real provider call. The Grammar Lab lane defined the
format first. Every lane uses it exactly as written here.

```text
%USERPROFILE%\.orena\live-provider.lock
```

It sits outside every repository and is never committed. It holds one JSON object:

```json
{"lane": "feature/orena-intelligence", "pid": 12345, "acquired_at": "2026-09-28T06:13:48.760421+00:00", "cost_ceiling_usd": 0.3}
```

| Field | Meaning |
| --- | --- |
| `lane` | the lane that holds it (this runner: the branch) |
| `pid` | the process that will release it. On Windows this is the Windows process id; in Git Bash use `cat /proc/$$/winpid`, not `$$` |
| `acquired_at` | when it was taken, ISO 8601, UTC |
| `cost_ceiling_usd` | the human-approved cost cap of the run |

**The rules.**

1. **Take it** before starting a sandbox or calling a real provider, by creating the
   file atomically with `O_CREAT|O_EXCL`. If the file already exists, it is held.
2. **Release it** in the same `finally`/`trap` that takes your sandbox down, after the
   sandbox is down. Remove it only when its `lane` and `pid` are the ones you wrote.
3. **Held:** look again every 30 s, for at most 30 min. Then stop and report the lane
   and PID that hold it. Never stop another lane's containers.
4. **Orphan:** a lock is an orphan when either:
   - its `pid` is no longer alive (Windows: `OpenProcess`; POSIX: `os.kill(pid, 0)`), or
   - `acquired_at` is more than 60 min ago.

   Remove it and record `orphan lock removed: lane=<lane> reason=dead-pid|stale`, then
   try again at once. Re-read the file just before removing it, and leave it alone if
   it has changed.

`run.py` does all of this through `lock.py` and lists what happened in the result's
`"lock"` field. Another lane can wrap any command with it:

```bash
python scripts/agent_live/lock.py status
python scripts/agent_live/lock.py run --lane <lane> --cost-ceiling-usd 0.20 -- <command ...>
```
