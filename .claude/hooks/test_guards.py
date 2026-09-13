"""The Bash guards deny what they claim to deny, and allow ordinary work.

These hooks are the last thing between a careless command and a secret in a
transcript, and until now nothing checked them. They are pure functions of a
command string, so they are cheap to test properly: feed the hook the payload
Claude Code would feed it and read the decision back.

Claude-layer tooling, so it lives beside the hooks rather than in the shared
CI gate (CLAUDE.md draws that line). Run it directly:

    python .claude/hooks/test_guards.py
"""
from pathlib import Path
import json
import subprocess
import sys
import unittest

HOOKS = Path(__file__).resolve().parent


def decide(hook: str, command: str) -> str:
    """'deny' or 'allow' - the hook stays silent when it permits a command."""
    result = subprocess.run(
        [sys.executable, str(HOOKS / hook)],
        input=json.dumps({'tool_input': {'command': command}}),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(f'{hook} crashed on {command!r}: {result.stderr}')
    if not result.stdout.strip():
        return 'allow'
    payload = json.loads(result.stdout)
    return payload['hookSpecificOutput']['permissionDecision']


class SecretsGuard(unittest.TestCase):
    def deny(self, command):
        self.assertEqual(decide('guard_secrets.py', command), 'deny', command)

    def allow(self, command):
        self.assertEqual(decide('guard_secrets.py', command), 'allow', command)

    def test_reading_dotenv_is_denied(self):
        self.deny('cat .env')
        self.deny('head -5 .env.local')

    def test_the_example_file_carries_no_values_and_stays_readable(self):
        self.allow('cat .env.example')

    def test_counting_a_key_proves_presence_without_printing_it(self):
        self.allow("grep -c '^GROQ_API_KEY=' .env")

    def test_grepping_dotenv_for_content_is_denied(self):
        self.deny('grep GROQ .env')

    def test_compose_env_dump_is_denied(self):
        self.deny('docker compose exec writing-coach printenv')

    # The four below are the gap this file was written for. A live GROQ_API_KEY
    # reached a transcript through `docker inspect --format '{{.Config.Env}}'`,
    # which the guard did not cover: it only knew about `docker compose exec`.
    def test_plain_docker_exec_env_dump_is_denied(self):
        self.deny('docker exec orena-foundation-web env')
        self.deny('docker exec orena-foundation-web printenv')

    def test_inspecting_the_env_block_is_denied(self):
        self.deny("docker inspect orena-foundation-web --format '{{range .Config.Env}}{{println .}}{{end}}'")
        self.deny("docker inspect web --format '{{.Config.Env}}'")

    def test_a_bare_inspect_dumps_env_inside_its_json_and_is_denied(self):
        # No --format means the whole config, Env included.
        self.deny('docker inspect orena-foundation-web')
        self.deny('docker inspect orena-foundation-web | grep -i mounts')

    def test_inspecting_a_named_non_secret_field_is_ordinary_work(self):
        # The guard must not make container debugging impossible.
        self.allow("docker inspect orena-foundation-web --format '{{.HostConfig.PortBindings}}'")
        self.allow("docker inspect orena-foundation-postgres --format '{{.HostConfig.Tmpfs}}'")
        self.allow("docker inspect web --format '{{range .Mounts}}{{.Source}}{{end}}'")

    def test_ordinary_docker_work_is_untouched(self):
        self.allow('docker ps -a')
        self.allow('docker start orena-foundation-postgres')
        self.allow('docker logs orena-foundation-web')

    def test_echoing_a_known_secret_variable_is_denied(self):
        self.deny('echo $GROQ_API_KEY')


class GitDockerGuard(unittest.TestCase):
    def deny(self, command):
        self.assertEqual(decide('guard_git_docker.py', command), 'deny', command)

    def allow(self, command):
        self.assertEqual(decide('guard_git_docker.py', command), 'allow', command)

    def test_volume_destroying_compose_is_denied(self):
        self.deny('docker compose down -v')

    def test_blanket_staging_is_denied(self):
        self.deny('git add -A')

    def test_staging_named_paths_is_ordinary_work(self):
        self.allow('git add scripts/start_orena_sandbox.ps1 docs/project/CURRENT_HANDOFF.md')

    def test_stopping_the_sandbox_is_ordinary_work(self):
        self.allow('docker compose down')
        self.allow('docker stop orena-foundation-web')


if __name__ == '__main__':
    unittest.main(verbosity=2)
