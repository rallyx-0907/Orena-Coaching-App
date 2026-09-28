"""Run a command with specific variables injected from a ``.env`` file.

Reads only the named variables (never dumps the file, never prints a value)
and execs the given command with them added to its own environment. This is
how a key vault kept outside the repo (e.g. another checkout's ``.env``)
reaches ``docker compose`` for the evaluator sandbox without the value ever
appearing in this file, in git, in shell history, or on the command line of
the child process (compose reads it back out of its own inherited
environment, never as an argument).

Usage::

    python with_env_from_dotenv.py <path-to-.env> NAME1,NAME2 -- <command...>

Exit code 2 and a message naming (only) the missing variable names if any
requested name is absent or empty in the file; the wrapped command never
runs in that case.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def read_dotenv_values(path: str, names: set[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    with open(path, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\r\n")
            match = _LINE.match(line)
            if not match:
                continue
            name, value = match.group(1), match.group(2)
            if name not in names:
                continue
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if value:
                found[name] = value
    return found


def main(argv: list[str]) -> int:
    if "--" not in argv:
        print("usage: with_env_from_dotenv.py <.env path> NAME1,NAME2 -- <command...>", file=sys.stderr)
        return 2
    split = argv.index("--")
    dotenv_path, names_csv = argv[:split]
    command = argv[split + 1 :]
    names = {name.strip() for name in names_csv.split(",") if name.strip()}

    values = read_dotenv_values(dotenv_path, names)
    missing = sorted(names - values.keys())
    if missing:
        print(f"not present (or empty) in {dotenv_path}: {missing}", file=sys.stderr)
        return 2

    env = {**os.environ, **values}
    return subprocess.run(command, env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
