"""Startup refusal and launcher publish lock for the signed-out local boundary (issue #137, architecture review C1/C2).

The primary boundary is the deployment config: every official launcher publishes the app on loopback, and this file
locks that. The per-request peer check is the second layer; the startup refusal is defense-in-depth."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from writing_coach.core.deployment import resolve_deployment_config

ROOT = Path(__file__).resolve().parents[1]
LOOPBACK = {"127.0.0.1", "::1", "[::1]", "localhost"}
SIGN_IN = {"GOOGLE_CLIENT_ID": "i", "GOOGLE_CLIENT_SECRET": "s", "SESSION_SECRET": "x" * 40}


def development(**values: str) -> dict[str, str]:
    return {"APP_ENV": "development", **values}


# ---- startup refusal: development + sign-in off + configured for public exposure ------------------------------------


@pytest.mark.parametrize(
    "extra",
    [
        {"PUBLIC_BASE_URL": "https://orena.example.com"},
        {"PUBLIC_BASE_URL": "http://orena.example.com:8000"},
        {"PUBLIC_BASE_URL": "http://8.8.8.8:8000"},
        {"PUBLIC_BASE_URL": "http://127.0.0.1:8000", "CLOUDFLARE_TUNNEL_TOKEN": "tunnel-token-value"},
    ],
)
def test_an_unauthenticated_development_runtime_configured_for_the_public_refuses_to_start(extra) -> None:
    with pytest.raises(RuntimeError, match="Refusing to start") as raised:
        resolve_deployment_config(development(**extra))
    assert "tunnel-token-value" not in str(raised.value)


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"PUBLIC_BASE_URL": "http://127.0.0.1:8021"},
        {"PUBLIC_BASE_URL": "http://localhost:8011"},
        {"PUBLIC_BASE_URL": "http://127.0.0.1:8000", "CLOUDFLARE_TUNNEL_TOKEN": ""},
        {"PUBLIC_BASE_URL": "https://lane.example.com", **SIGN_IN},
    ],
)
def test_local_development_and_signed_in_runtimes_still_start(values) -> None:
    resolve_deployment_config(development(**values))


# Development with sign-in off is LOOPBACK-ONLY: any declared non-loopback exposure refuses startup. What is declared
# is PUBLIC_BASE_URL, GOOGLE_REDIRECT_URI, ORENA_PUBLISHED_BIND_HOST, ORENA_INSECURE_DEV_LAN_BIND_HOST and the tunnel
# token. The in-container listen address (uvicorn 0.0.0.0, APP_BIND_HOST) is not exposure and is never read.
LOOPBACK_ONLY_ALLOWED = [
    {"PUBLIC_BASE_URL": "http://localhost:8000"},
    {"PUBLIC_BASE_URL": "http://LOCALHOST:8000"},
    {"PUBLIC_BASE_URL": "http://127.0.0.1:8000"},
    {"PUBLIC_BASE_URL": "http://127.1.2.3:8000"},
    {"PUBLIC_BASE_URL": "http://[::1]:8000"},
    {"PUBLIC_BASE_URL": "http://[::ffff:127.0.0.1]:8000"},
    {"ORENA_PUBLISHED_BIND_HOST": "127.0.0.1"},
    {"ORENA_PUBLISHED_BIND_HOST": "::1"},
    {"ORENA_PUBLISHED_BIND_HOST": "[::1]"},
    {"ORENA_PUBLISHED_BIND_HOST": "localhost"},
    {"ORENA_INSECURE_DEV_LAN_BIND_HOST": ""},
    {"ORENA_INSECURE_DEV_LAN_BIND_HOST": "127.0.0.1"},
    {"CLOUDFLARE_TUNNEL_TOKEN": ""},
    {"APP_BIND_HOST": "0.0.0.0"},  # the in-container listen address is not exposure
    {"APP_BIND_HOST": "127.0.0.1"},
]
LOOPBACK_ONLY_REFUSED = [
    {"PUBLIC_BASE_URL": "http://192.168.1.20:8000"},
    {"PUBLIC_BASE_URL": "http://10.0.0.5:8000"},
    {"PUBLIC_BASE_URL": "http://172.16.0.9:8000"},
    {"PUBLIC_BASE_URL": "http://172.31.255.1:8000"},
    {"PUBLIC_BASE_URL": "http://100.64.0.7:8000"},  # CGNAT
    {"PUBLIC_BASE_URL": "http://169.254.1.1:8000"},  # link-local
    {"PUBLIC_BASE_URL": "http://[fe80::1]:8000"},
    {"PUBLIC_BASE_URL": "http://[fd00::1]:8000"},  # unique-local fc00::/7
    {"PUBLIC_BASE_URL": "http://[fc00::1]:8000"},
    {"PUBLIC_BASE_URL": "http://8.8.8.8:8000"},
    {"PUBLIC_BASE_URL": "http://[2001:4860:4860::8888]:8000"},
    {"PUBLIC_BASE_URL": "http://0.0.0.0:8000"},
    {"PUBLIC_BASE_URL": "http://mybox:8000"},  # single label
    {"PUBLIC_BASE_URL": "http://mybox.local:8000"},
    {"PUBLIC_BASE_URL": "http://mybox.lan:8000"},
    {"PUBLIC_BASE_URL": "http://mybox.internal:8000"},
    {"PUBLIC_BASE_URL": "http://orena.example.com:8000"},
    {"PUBLIC_BASE_URL": "https://orena.example.com"},
    {"PUBLIC_BASE_URL": "http://127.0.0.1:8000", "CLOUDFLARE_TUNNEL_TOKEN": "tunnel-token-value"},
    {"PUBLIC_BASE_URL": "http://127.0.0.1:8000", "ORENA_PUBLISHED_BIND_HOST": "0.0.0.0"},
    {"PUBLIC_BASE_URL": "http://127.0.0.1:8000", "ORENA_PUBLISHED_BIND_HOST": "192.168.1.5"},
    {"PUBLIC_BASE_URL": "http://127.0.0.1:8000", "ORENA_PUBLISHED_BIND_HOST": "::"},
    {"PUBLIC_BASE_URL": "http://127.0.0.1:8000", "ORENA_INSECURE_DEV_LAN_BIND_HOST": "0.0.0.0"},
    {"PUBLIC_BASE_URL": "http://127.0.0.1:8000", "ORENA_INSECURE_DEV_LAN_BIND_HOST": "192.168.1.5"},
    {"PUBLIC_BASE_URL": "http://127.0.0.1:8000", "ORENA_INSECURE_DEV_LAN_BIND_HOST": "mybox.local"},
]


@pytest.mark.parametrize("values", LOOPBACK_ONLY_ALLOWED, ids=lambda v: str(v))
def test_development_without_sign_in_allows_loopback_declarations(values) -> None:
    resolve_deployment_config(development(**values))


@pytest.mark.parametrize("values", LOOPBACK_ONLY_REFUSED, ids=lambda v: str(v))
def test_development_without_sign_in_refuses_any_non_loopback_declaration(values) -> None:
    with pytest.raises(RuntimeError, match="Refusing to start") as raised:
        resolve_deployment_config(development(**values))
    assert "tunnel-token-value" not in str(raised.value)


@pytest.mark.parametrize("values", [v for v in LOOPBACK_ONLY_REFUSED if v.get("PUBLIC_BASE_URL", "").startswith("http")],
                         ids=lambda v: str(v))
def test_development_with_sign_in_may_face_the_lan_or_the_public(values) -> None:
    """LAN development needs Google sign-in; with it the same declarations start."""
    resolve_deployment_config(development(**values, **SIGN_IN))


def test_a_non_loopback_redirect_origin_is_refused_too() -> None:
    # The redirect URI must match the origin, so a mismatch is refused earlier; a matching one is the origin's host.
    with pytest.raises(RuntimeError):
        resolve_deployment_config(development(
            PUBLIC_BASE_URL="http://127.0.0.1:8000", GOOGLE_REDIRECT_URI="http://192.168.1.5:8000/auth/google/callback"))


@pytest.mark.parametrize(
    ("shape", "env", "starts"),
    [
        ("dev, sign-in off, localhost", {"APP_ENV": "development", "PUBLIC_BASE_URL": "http://localhost:8011"}, True),
        ("dev, sign-in off, public", {"APP_ENV": "development", "PUBLIC_BASE_URL": "https://orena.example.com"}, False),
        ("dev, sign-in on, public", {"APP_ENV": "development", "PUBLIC_BASE_URL": "https://orena.example.com", **SIGN_IN}, True),
        ("staging, sign-in off, public", {"APP_ENV": "staging", "PUBLIC_BASE_URL": "https://orena.example.com"}, False),
        ("staging, sign-in on, public (:8000)", {"APP_ENV": "staging", "PUBLIC_BASE_URL": "https://orena.example.com", **SIGN_IN}, True),
        ("dev, sign-in on, loopback (:8021)", {"APP_ENV": "development", "PUBLIC_BASE_URL": "http://127.0.0.1:8021", **SIGN_IN}, True),
    ],
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_startup_matrix(shape: str, env: dict[str, str], starts: bool) -> None:
    if starts:
        resolve_deployment_config(env)
    else:
        with pytest.raises(RuntimeError):
            resolve_deployment_config(env)


def test_staging_without_sign_in_is_refused_by_the_staging_contract() -> None:
    with pytest.raises(RuntimeError, match="Google authentication must be configured"):
        resolve_deployment_config({"APP_ENV": "staging", "PUBLIC_BASE_URL": "https://orena.example.com"})


# ---- every official launcher publishes the app on loopback (the primary boundary) -----------------------------------

OPT_IN = "${ORENA_INSECURE_DEV_LAN_BIND_HOST:-127.0.0.1}"

# Every official launcher that publishes the app's port, and the host it publishes on by default. A new launcher that
# publishes the port must be added here on purpose; one that is not listed fails the inventory test.
LAUNCHERS = {
    "compose.yaml": [OPT_IN],  # the only route to a non-loopback publish is the insecure-named opt-in, loopback default
    "scripts/agent_e2e/compose.yaml": ["127.0.0.1"],
    "scripts/agent_live/compose.yaml": ["127.0.0.1"],
    "scripts/mobile_qa_runtime.ps1": ["127.0.0.1"],
    "scripts/product_restore_rehearsal.ps1": ["127.0.0.1"],
    "scripts/staging_8000_deploy.ps1": ["127.0.0.1"],  # :8000 staging, human-operated; already loopback
    "scripts/staging_update.ps1": ["127.0.0.1"],  # :8011 staging update; was every interface, now loopback
}
# Launchers that start the stack through compose.yaml and publish no port of their own.
COMPOSE_WRAPPERS = ("start_docker.ps1", "start_dev.ps1", "start_public.ps1", "stop_docker.ps1")


def _resolve(text: str) -> str:
    text = re.sub(r"\$\{[^}:]+:-([^}$]*)\}", r"\1", text)
    return re.sub(r"\$\{\w+\}", "0", text)


def _specs(path: Path) -> list[str]:
    """The raw publish specs (host:port:container) a launcher declares."""
    text = path.read_text(encoding="utf-8")
    specs: list[str] = []
    if path.suffix in {".yaml", ".yml"}:
        lines = text.splitlines()
        for number, line in enumerate(lines):
            if line.strip() != "ports:":
                continue
            indent = len(line) - len(line.lstrip())
            for item in lines[number + 1:]:
                stripped = item.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if not stripped.startswith("- ") or len(item) - len(item.lstrip()) <= indent:
                    break
                specs.append(stripped[2:].strip().strip("\"'"))
    else:
        for match in re.findall(r"""(?:--publish|(?<![\w-])-p)['"]?[,\s]+['"]?([^\s'"`,]+)""", text):
            if re.search(r":\d+$", match):
                specs.append(match)
    return specs


def _host(spec: str) -> str | None:
    """The host part of a publish spec as written (the opt-in expression stays whole); None when there is none."""
    masked = spec.replace(OPT_IN, "OPTIN")
    masked = re.sub(r"\$\{[^}]*\}", "0", masked)  # port variables (and their defaults) are not the host
    match = re.match(r"^(?:(?P<host>.+):)?(?P<hp>[^:]+):(?P<cp>\d+)$", masked)
    if not match or not match.group("host"):
        return None
    return OPT_IN if match.group("host") == "OPTIN" else match.group("host")


def _launchers() -> dict[str, list[str]]:
    paths: set[Path] = set(ROOT.glob("compose*.y*ml")) | set(ROOT.glob("scripts/**/compose*.y*ml"))
    paths |= set(ROOT.glob("start_*.ps1")) | set(ROOT.glob("start_*.sh")) | set(ROOT.glob("start_*.bat"))
    paths |= set(ROOT.glob("scripts/**/*.ps1")) | set(ROOT.glob("scripts/**/*.sh"))
    found: dict[str, list[str]] = {}
    for path in sorted(paths):
        specs = _specs(path)
        if specs:
            found[path.relative_to(ROOT).as_posix()] = specs
    return found


def test_the_launcher_inventory_is_complete() -> None:
    found = _launchers()
    assert set(found) == set(LAUNCHERS), f"unlisted or missing launchers: {sorted(set(found) ^ set(LAUNCHERS))}"
    for name in COMPOSE_WRAPPERS:
        assert not _specs(ROOT / name), f"{name} publishes a port itself; list it in LAUNCHERS"


@pytest.mark.parametrize("name", sorted(LAUNCHERS))
def test_every_launcher_publishes_on_loopback_by_default(name: str) -> None:
    specs = _specs(ROOT / name)
    assert specs, name
    hosts = [_host(spec) for spec in specs]
    assert None not in hosts, f"{name}: a publish without a host binds every interface: {specs}"
    assert set(hosts) == set(LAUNCHERS[name]), f"{name}: publishes on {hosts}"
    for host in hosts:
        assert _resolve(host) in LOOPBACK, f"{name}: {host} is not loopback by default"
        # The only variable a publish host may use is the explicit, insecure-named LAN opt-in.
        assert "$" not in host or host == OPT_IN


def test_the_lan_opt_in_is_insecure_named_and_off_by_default() -> None:
    assert OPT_IN.startswith("${ORENA_INSECURE_DEV_LAN_BIND_HOST:-")
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert not re.search(r"^ORENA_INSECURE_DEV_LAN_BIND_HOST=\S", example, re.M)


# ---- the declared bind host of the gateway trust equals where the port is published ---------------------------------


def _declared(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [_resolve(m) for m in re.findall(r"ORENA_PUBLISHED_BIND_HOST(?::\s*|=)([^\s`'\",]+)", text)]


def _launchers_that_trust_the_gateway() -> list[str]:
    return sorted(
        name for name in LAUNCHERS
        if "ORENA_TRUST_DOCKER_PUBLISHED_PORT" in (ROOT / name).read_text(encoding="utf-8")
    )


def test_the_launchers_that_trust_the_gateway_are_the_auth_off_dev_ones() -> None:
    assert _launchers_that_trust_the_gateway() == [
        "compose.yaml", "scripts/agent_e2e/compose.yaml", "scripts/agent_live/compose.yaml",
        "scripts/mobile_qa_runtime.ps1", "scripts/staging_update.ps1",
    ]


@pytest.mark.parametrize("name", _launchers_that_trust_the_gateway())
def test_every_gateway_trusting_launcher_publishes_where_it_declares(name: str) -> None:
    declared = _declared(ROOT / name)
    hosts = [_resolve(_host(spec) or "") for spec in _specs(ROOT / name)]
    assert declared and hosts, name
    assert set(declared) == set(hosts), f"{name}: declares {declared} but publishes on {hosts}"


def test_compose_derives_the_declaration_and_the_publish_from_one_expression() -> None:
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert f"ORENA_PUBLISHED_BIND_HOST: {OPT_IN}" in text
    assert f'"{OPT_IN}:8000:8000"' in text


# ---- every official launcher asserts Docker's REAL published address after it starts the app (issue #140) -----------
# The publish above is what the launcher asks for; this is what Docker reports back, read on the host.

ASSERT = "assert_published_loopback.py"
# launcher -> (the file that starts the app container, the text that starts it)
START_AND_ASSERT = {
    "compose.yaml": ("start_docker.ps1", "docker compose up -d --build"),
    "scripts/agent_e2e/compose.yaml": ("scripts/agent_e2e/run.py", 'compose(env, "up", "-d")'),
    "scripts/agent_live/compose.yaml": ("scripts/agent_live/run.py", 'self._compose("up", "-d")'),
    "scripts/mobile_qa_runtime.ps1": ("scripts/mobile_qa_runtime.ps1", "docker compose run -d"),
    "scripts/product_restore_rehearsal.ps1": ("scripts/product_restore_rehearsal.ps1", "$webStarted = Invoke-Docker"),
    "scripts/staging_8000_deploy.ps1": ("scripts/staging_8000_deploy.ps1", "-p 127.0.0.1:8000:8000"),
    "scripts/staging_update.ps1": ("scripts/staging_update.ps1", "& docker @run"),
}
# compose.yaml is started by three wrappers; each must assert after its own `up`.
COMPOSE_STARTERS = {
    "start_docker.ps1": "docker compose up -d --build",
    "start_dev.ps1": "docker compose -f compose.yaml -f compose.dev.yaml up -d --build",
    "start_public.ps1": "docker compose --profile public up -d --build",
}


def test_the_assertion_inventory_covers_every_launcher() -> None:
    assert set(START_AND_ASSERT) == set(LAUNCHERS)


@pytest.mark.parametrize("launcher", sorted(START_AND_ASSERT))
def test_every_launcher_asserts_the_real_publish_after_starting_the_app(launcher: str) -> None:
    runner, start = START_AND_ASSERT[launcher]
    text = (ROOT / runner).read_text(encoding="utf-8")
    assert start in text, f"{runner}: expected to start the app with {start!r}"
    assert ASSERT in text, f"{runner} never runs {ASSERT}"
    # The python runners call a helper that runs the script; the call must follow the start.
    call = "assert_loopback(env, port)" if "agent_e2e" in runner else "self.assert_loopback()" if "agent_live" in runner else ASSERT
    assert call in text[text.index(start):], f"{runner}: {call} must run after the start"


@pytest.mark.parametrize("wrapper", sorted(COMPOSE_STARTERS))
def test_every_compose_wrapper_asserts_after_its_up(wrapper: str) -> None:
    text = (ROOT / wrapper).read_text(encoding="utf-8")
    start = COMPOSE_STARTERS[wrapper]
    assert start in text, wrapper
    assert ASSERT in text[text.index(start):], f"{wrapper}: assertion must follow the compose up"
    assert "exit 1" in text[text.index(ASSERT):], f"{wrapper}: a refusal must exit non-zero"
    assert "up --watch" not in text, f"{wrapper}: a blocking foreground up would never reach the assertion"


def test_wrappers_enable_the_lan_opt_in_only_from_the_named_variable() -> None:
    for wrapper in COMPOSE_STARTERS:
        text = (ROOT / wrapper).read_text(encoding="utf-8")
        assert "$env:ORENA_INSECURE_DEV_LAN_BIND_HOST" in text and "--lan-opt-in" in text


def test_the_8000_staging_check_is_read_only() -> None:
    text = (ROOT / "scripts/staging_8000_deploy.ps1").read_text(encoding="utf-8")
    line = next(row for row in text.splitlines() if ASSERT in row)
    assert "--no-stop" in line


def test_the_assertion_agrees_with_the_app_loopback_rule() -> None:
    import importlib.util

    from writing_coach.core.deployment import is_loopback_host

    spec = importlib.util.spec_from_file_location("assert_published_loopback", ROOT / "scripts" / ASSERT)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    for host in ["127.0.0.1", "127.9.9.9", "::1", "[::1]", "localhost", "LOCALHOST", "::ffff:127.0.0.1", "", "0.0.0.0", "::",
                 "192.168.1.5", "10.0.0.1", "fe80::1", "8.8.8.8", "mybox.local", "0:0:0:0:0:0:0:1"]:
        assert guard.is_loopback_host(host) == is_loopback_host(host), host
