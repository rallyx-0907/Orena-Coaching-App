# CLAUDE.md

@AGENTS.md

`AGENTS.md` is the shared Orena operating contract for every agent lane, and it
is imported above — authority, cold start, lanes, Superpowers, platform scope,
product invariants, architecture holds, workflow, recovery, validation,
completion and safety all live there. Read it, do not restate it.

**This file is the Claude Code layer**: how this harness reads the design, what
it must do before it calls a learner surface done, its tooling, hooks, slash
commands and platform gotchas. It is authoritative for none of the shared
product direction, engineering workflow, validation policy or recovery
behaviour, which `AGENTS.md` owns. It **is** authoritative for the Claude
lane's UI method below, because that method is a change from the human
(D-067) and older habits must not outlive it.

References below name `AGENTS.md` headings rather than section numbers, because
the numbering has drifted before.

Claude's lane is `claude/<task>` (`AGENTS.md`, "Lanes").

---

## The UI: read the design at its source, measure, invent nothing (D-067, D-088)

These replace every earlier habit about learner-facing UI. Any UI rule you
remember from before 2026-09-21 — from a code comment, an older decision, the
old Design Contract, a previous session — is void where it disagrees with the
design. If it is not in the design, it is not a reason to add or keep UI.

**1. Read the source, not a copy of a copy.** The design is the Claude Design
project `e6dc1cb2-72d0-40b4-a916-5dcd47e17cc0` (D-088), pinned byte for byte in
`docs/design/canonical-ui/screens/` (`SYNC_2026-09-27.md`). `DesignSync`
(`ToolSearch select:DesignSync`; only `list_files` and `get_file`) truncates a
file at 256 KiB: `Orena.dc.html` is 832 KB, so a `get_file` read of it silently
stops at the Profile frame, before the phone bar, every sheet and the state
script. Read it from the pin; to check for a newer revision, compare the first
256 KiB and ask the human for an export. Before a learner-facing task read the
surface's frame(s), the state script's handlers for them (end of
`Orena.dc.html`), `docs/design/canonical-ui/IMPLEMENTATION_MAP.md`, and the
brief (`docs/design/canonical-ui/brief/`) for intent. Never work from memory of
the design or from last session's screenshot.

**2. Serve and render the frames to compare.** `file://` is blocked in the
Playwright tool. Serve the pin:
`cd docs/design/canonical-ui/screens && python -m http.server 8765 --bind 127.0.0.1`
(stop it afterwards), open `Orena.dc.html`, switch Desktop/Mobile and Light/Dark
with the prototype strip, and locate a frame by `[data-screen-label="…"]`. The
desktop frame fills the window below the 48px strip (true scale); the phone
frame is 390x844, 1:1.

**3. Measure, do not eyeball.** For each element the source draws, read its
computed style from the source frame and from the running app and compare:
`font-size`, `font-weight`, `font-family`, `letter-spacing`, `color`, box
height, `border-radius`, background, ring, gap, padding, icon and its fill. List
every difference. A surface is done when the list is empty or every remaining
item is a recorded human decision (Design Contract, rules 42 and the fidelity
gate). "Looks close" has been wrong before: nav rows were 14px/42 against 17px/57,
and the mono label rendered in the wrong face.

**4. Invent nothing, delete the old.** Do not add a button, chip, hint, notice,
badge, heading, empty/loading/error visual, confirmation line, animation or
copy the source does not draw (rules 43 and 39). Do not restyle an interaction
the source does not draw — delete it and its code (rule 44). Behaviour with no
place in the source goes where the source's patterns say (behind "⋯", in a
sheet) or is reported to the human as a decision. If you are unsure whether the
source draws something, look it up in the source before adding it.

**4b. The design's words are sample content (D-068).** Layout, colour, type and
component style are the standard; the frame's copy, lessons and numbers are not.
Every label is in the learner's language setting, translated. The logo and the
Orena Intelligence mark are the design's (D-090).

**5. Icons are official.** Lucide, from `lucide-static` at the release pinned in
`static/orena/kit/icons.js`. The design's own paths are partly hand-typed
variants of Lucide icons; identify each by name and take the package's path.
Never type a path from memory; fetch, compare, replace. Add an icon the design
uses and the app lacks from the package.

**6. Verify in a browser, every language, real touch.** Desktop at 1920x1080
and a phone context created with `hasTouch`/`isMobile` (CDP touch events for a
swipe), in English, Vietnamese and Chinese, and in the light and dark themes,
in the same batch. Per rule 47, the desktop rail is always present; the
desktop top bar, and the phone header and bar, exist only on the browsing
places rule 47 lists. Every route in the design's focus list is a learning
workspace without the top bar, phone header and phone bar (the rail stays):
check the room you touch is on the right side of that line. The cutover is
done (D-143): the learner UI is the only UI, at `/`.

**6b. The workspace is the viewport (Design Contract rule 49, D-078).** A learning workspace
never scrolls as a page: measure it at 1920x1080, 1366x768, 390x844 and 360x740 with content as
long as it gets (a long line, many attempts, a long transcript) - no page scroll, no horizontal
overflow, primary controls inside the viewport, long content scrolling only in its own region.
Recompose when it does not fit; never loosen the rule for an implementation reason.

**7. Record what you cannot resolve.** A conflict between the design and the
brand, an unpinned file, a gap the design marks incomplete, a backend that
cannot supply a component: write it in `docs/project/UI_BACKEND_GAPS.md` and
tell the human. Do not resolve it by choosing.

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
- The sandbox is `orena-foundation-web` on **8011**. The worktree is mounted into
  it, but **uvicorn does not reload**: restart the container after Python
  changes. Static JS and CSS are served from disk — force-reload the page, since
  a stale stylesheet reads exactly like a broken layout.
- For AI-backed checks select Gemini in the sandbox (`PUT
  /api/admin/ai/config` with `gemini-3.5-flash-lite`; the key is already in the
  sandbox environment — check it as a boolean, never print it). The Ollama
  default takes 17-54 s per call. Changing the learner's language pair for a
  Chinese check is a stored profile change: put it back to English → Vietnamese
  afterwards.

## Shell and platform gotchas

- Two shells are available and take different syntax: PowerShell (primary) and
  Git Bash. Pick one per command; do not mix. In Git Bash, prefix a `docker`
  command that takes a container path with `MSYS_NO_PATHCONV=1`.
- Heredocs collapse a backslash-n escape into a real newline. Writing JS or
  Python source through a shell heredoc silently corrupts regexes, f-strings
  and `join()` calls that depend on that escape. Use the Write/Edit tools for
  source files, or build the backslash via `chr(92)`.
- Long `grep`/`find` sweeps over the repository root time out — use the Grep
  tool (ripgrep), which skips `.git` and `node_modules`.
- Screenshots and scratch output belong in the session scratchpad, never in the
  working tree. Playwright writes into `.playwright-mcp/` under the repository
  and, if given a bare filename, into the working directory itself; clean both
  up before staging.
