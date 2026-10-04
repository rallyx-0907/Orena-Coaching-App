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

## The live-provider locks: one per quota group (shared by every lane)

Lanes on one machine share one Docker runtime, but only lanes that use the same provider quota need to queue.
There is one lock per quota group, outside every repository, and nothing about them is committed:

| Lock | Quota group | Held by |
| --- | --- | --- |
| `%USERPROFILE%\.orena\live-gemini-text.lock` | Gemini text models | agent live runs (`run.py`), Grammar Lab's evaluator |
| `%USERPROFILE%\.orena\live-gemini-live.lock` | Gemini Live models | the voice spike (`scripts/voice_spike/server.py`) |
| `%USERPROFILE%\.orena\live-deepseek.lock` | DeepSeek | whoever runs against DeepSeek |

A process holds exactly the locks of the groups it uses, no more. If it uses more than one, it takes them in the
order of the table and releases them in reverse, so two lanes never wait on each other. The single
`live-provider.lock` of before is retired.

**The file.** Each lock holds one JSON object. This is the format the Grammar Lab lane defined:

```json
{"lane": "feature/orena-intelligence", "pid": 12345, "acquired_at": "2026-10-04T06:13:48.760421+00:00",
 "heartbeat_at": "2026-10-04T06:15:48.120004+00:00", "cost_ceiling_usd": 0.30}
```

| Field | Meaning |
| --- | --- |
| `lane` | the lane that holds it (this runner: the branch) |
| `pid` | the process that will release it. On Windows this is the Windows process id; in Git Bash use `cat /proc/$$/winpid`, not `$$` |
| `acquired_at` | when it was taken, ISO 8601, UTC |
| `heartbeat_at` | rewritten by the holder every 60 s while it holds the lock, ISO 8601, UTC |
| `cost_ceiling_usd` | the human-approved cost cap of the run (0 on a free tier) |

**The rules.** They are the same for every group.

1. **Take it** before starting a sandbox or calling a real provider in that group, by creating the file
   atomically with `O_CREAT|O_EXCL`. If the file already exists, it is held.
2. **Release it** in the same `finally`/`trap` that takes your sandbox down, after the sandbox is down. Remove it
   only when its `lane` and `pid` are the ones you wrote.
3. **Held:** look again every 30 s, for at most 30 min. Then stop and report the lane and PID that hold it. If
   another group's lock was already taken, give it back. Never stop another lane's containers.
4. **Heartbeat:** while holding a lock, rewrite its `heartbeat_at` every 60 s (write to a temporary file, then
   replace). Only the lane and PID that wrote the lock may do this.
5. **Orphan:** whether a lock is an orphan depends on whose it is:
   - **another lane's lock** is an orphan only when `heartbeat_at` is more than 10 min old. Its PID is never
     checked: it may live in WSL or a container, where it means nothing on this host;
   - **your own lock** is an orphan when its PID is no longer alive (Windows: `OpenProcess`; POSIX:
     `os.kill(pid, 0)`), or when its `heartbeat_at` is more than 10 min old;
   - **a lock in the old format**, with no `heartbeat_at`, falls back to `acquired_at` against 60 min.

   Remove it and record `orphan lock removed: lane=<lane> reason=dead-pid|stale`, then try again at once.
   Re-read the file just before removing it, and leave it alone if it has changed.

These are the Grammar Lab lane's rules (`grammar_lab/sandbox/live_provider_lock.py`), kept exactly.

`run.py` holds `gemini-text` through `lock.py` and lists what happened in the result's `"lock"` field. Another lane
can wrap any command with it; repeat `--group` for each group the command uses:

```bash
python scripts/agent_live/lock.py status
python scripts/agent_live/lock.py run --lane <lane> --group gemini-text --cost-ceiling-usd 0.20 -- <command ...>
```
