# CLAUDE.md

@AGENTS.md

`AGENTS.md` is the shared Orena operating contract for every agent lane, and it
is imported above — authority, cold start, lanes, Superpowers, platform scope,
product invariants, architecture holds, workflow, recovery, validation,
completion and safety all live there. Read it, do not restate it.

**This file is only the Claude Code layer**, and it is authoritative for none of
the above. Claude-specific tooling, hooks, slash commands, shell and platform
gotchas, and the operation of this harness legitimately belong here — that is
what this file is for.

Four things never do, because they are shared across lanes and `AGENTS.md` owns
them: shared Orena **product direction**, shared **engineering workflow**,
shared **validation policy**, and shared **recovery and governance behaviour**.
Anything here that starts stating one of those is a duplicate — delete it and
read `AGENTS.md` instead.

References below name `AGENTS.md` headings rather than section numbers, because
the numbering has drifted before.

Claude's lane is `claude/<task>` (`AGENTS.md`, "Lanes").

---

## Slash commands and skills

Shipped in `.claude/`, invoked with `/`. Each is a convenience wrapper around
behaviour `AGENTS.md` already defines — never a substitute for it, and never a
prerequisite:

| Command | Wraps |
| --- | --- |
| `/resume-orena` | The bounded restore, `AGENTS.md` "Cold start" — live Git checks, then `PROJECT_MEMORY.md`'s canonical sequence. `/load-context` is a compatibility alias. |
| `/validate-gate` | The validation sequence, `AGENTS.md` "Validation and completion", reporting exact results. |
| `/completion-report` | The completion report required by `AGENTS.md` "Validation and completion" and `REVIEW_POLICY.md`. |
| `/governance-update` | The repository-memory transaction, as defined in `PROJECT_MEMORY.md`. |

These wrap the existing system. They are not a second memory or governance
system, and nothing may be recorded through them that `PROJECT_MEMORY.md` does
not already own.

## Hooks and guards

`.claude/settings.json` wires three guards. They are advisory tooling, not the
rule — the rules are `AGENTS.md` "Product invariants" and "Safety":

- `guard_git_docker.py` (PreToolUse/Bash) — blocks volume-destroying compose
  flags, blanket `git add`, destructive resets, force-push to `main`, and
  deletion of `docs/visual-references/**`.
- `guard_secrets.py` (PreToolUse/Bash) — blocks commands that would echo `.env`
  values, dump a container environment, or print credential material.
- `warn_protected.py` (PostToolUse/Write|Edit) — warns when a protected area was
  edited, so you state why and verify immediately.

**Gotcha:** the Bash guards match the whole command string, including text
inside heredocs and arguments. A script that merely *mentions* a forbidden
command — a grep pattern, a doc string, a test fixture — is blocked as though it
ran it. Move that text into a file with the Write tool and read it from there.

The guards' messages cite `AGENTS.md` section numbers; several predate the
current numbering. Trust the section *name* they describe, not the number.

## Docker and runtime notes

Concrete detail for the runtime boundaries and shared-runtime rule in
`AGENTS.md` "Safety" — the rule is there, the local specifics are here:

- On this machine the off-limits runtimes are production on **8000** and
  preview on **8010**; the shared named volumes are `ai-writing-coach-data` and
  `ai-writing-coach-postgres-data`; the lanes are the worktrees `...-v030`,
  `...-claudecode` and `...-codex`. `docker ps` shows which are live before you
  start anything.
- The worktree is mounted into the sandbox container, but **uvicorn does not
  reload**: restart the container after Python changes. Static JS and CSS are
  served from disk — force-reload the page, since a stale stylesheet reads
  exactly like a broken layout.

## Shell and platform gotchas

- Two shells are available and take different syntax: PowerShell (primary) and
  Git Bash. Pick one per command; do not mix.
- Heredocs collapse a backslash-n escape into a real newline. Writing JS or
  Python source through a shell heredoc silently corrupts regexes, f-strings
  and `join()` calls that depend on that escape. Use the Write/Edit tools for
  source files, or build the backslash via `chr(92)`.
- Long `grep`/`find` sweeps over the repository root time out — use the Grep
  tool (ripgrep), which skips `.git` and `node_modules`.
- Screenshots and scratch output belong in the session scratchpad, never in the
  working tree. Playwright writes into `.playwright-mcp/` under the repository;
  clean it up before staging.

<!-- Do not paste the agent contract into this file. The single import on line 3
     already loads it; a previous Codex import appended a full copy, which
     loaded the contract twice into every session. -->
