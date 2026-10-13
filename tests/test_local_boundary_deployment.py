"""Startup refusal and publish consistency for the signed-out local boundary (issue #137, architecture review C1/C2)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from writing_coach.core.deployment import resolve_deployment_config

ROOT = Path(__file__).resolve().parents[1]
LOOPBACK = {"127.0.0.1", "::1", "localhost"}


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
        {"PUBLIC_BASE_URL": "http://192.168.1.20:8000"},
        {"PUBLIC_BASE_URL": "http://mybox.local:8000"},
        {"PUBLIC_BASE_URL": "http://127.0.0.1:8000", "CLOUDFLARE_TUNNEL_TOKEN": ""},
        # A lane runtime with sign-in on (:8021) is not refused, whatever its origin.
        {"PUBLIC_BASE_URL": "https://lane.example.com", "GOOGLE_CLIENT_ID": "i", "GOOGLE_CLIENT_SECRET": "s",
         "SESSION_SECRET": "x" * 40},
    ],
)
def test_local_development_and_signed_in_runtimes_still_start(values) -> None:
    resolve_deployment_config(development(**values))


def test_staging_with_sign_in_still_starts() -> None:
    resolve_deployment_config({
        "APP_ENV": "staging", "PUBLIC_BASE_URL": "https://orena.example.com", "GOOGLE_CLIENT_ID": "i",
        "GOOGLE_CLIENT_SECRET": "s", "SESSION_SECRET": "x" * 40,
    })


# ---- the declared bind host of the gateway trust equals where the port is published --------------------------------


def _resolve(text: str) -> str:
    text = re.sub(r"\$\{[^}:]+:-([^}$]*)\}", r"\1", text)
    return re.sub(r"\$\{\w+\}", "0", text)


def _declared_and_published(path: Path) -> tuple[list[str], list[str]]:
    text = path.read_text(encoding="utf-8")
    declared = [_resolve(m) for m in re.findall(r"ORENA_PUBLISHED_BIND_HOST(?::\s*|=)([^\s`]+)", text)]
    specs = re.findall(r'-\s*"([^"]+:\d+:8000)"', text) + re.findall(r'--publish\s+"([^"]+)"', text)
    hosts = [_resolve(spec).rsplit(":", 2)[0] for spec in specs]
    return declared, hosts


def _launchers_that_trust_the_gateway() -> list[Path]:
    found: list[Path] = []
    for pattern in ("compose*.yaml", "scripts/**/*.yaml", "scripts/**/*.yml", "scripts/**/*.ps1", "scripts/**/*.sh"):
        for path in ROOT.glob(pattern):
            if "ORENA_TRUST_DOCKER_PUBLISHED_PORT" in path.read_text(encoding="utf-8", errors="ignore"):
                found.append(path)
    return sorted(found)


def test_the_launchers_that_trust_the_gateway_are_the_known_ones() -> None:
    names = {p.relative_to(ROOT).as_posix() for p in _launchers_that_trust_the_gateway()}
    assert {"compose.yaml", "scripts/agent_e2e/compose.yaml", "scripts/mobile_qa_runtime.ps1"} <= names


@pytest.mark.parametrize("path", _launchers_that_trust_the_gateway(), ids=lambda p: p.name)
def test_every_gateway_trusting_launcher_publishes_where_it_declares_and_on_loopback(path: Path) -> None:
    declared, hosts = _declared_and_published(path)
    assert declared and hosts, f"{path.name}: no declared bind host or no published port found"
    assert set(declared) == set(hosts), f"{path.name}: declares {declared} but publishes on {hosts}"
    assert set(hosts) <= LOOPBACK


def test_compose_derives_the_declaration_and_the_publish_from_one_expression() -> None:
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    expression = "${ORENA_INSECURE_DEV_LAN_BIND_HOST:-127.0.0.1}"
    assert f"ORENA_PUBLISHED_BIND_HOST: {expression}" in text
    assert f'"{expression}:8000:8000"' in text
