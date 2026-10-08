"""What the agent package must never do, checked on its source (spec §3, D2, D6, D7)."""

from __future__ import annotations

import ast
from pathlib import Path

from writing_coach.ai.capabilities import AIOperation, all_capabilities

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "writing_coach" / "agent"
SOURCES = sorted(PACKAGE.glob("*.py"))


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_the_package_exists_with_its_parts():
    names = {path.stem for path in SOURCES}
    for part in (
        "contract", "schemas", "locale", "events", "learner_copy", "errors", "tools", "limits",
        "session", "provider", "fake_provider", "capability_registry", "tool_plan", "decision",
        "context", "redaction", "voice", "outputs", "prompts", "turn", "api", "runtime",
        "read_tools", "platform_provider",
    ):  # fmt: skip
        assert part in names


def test_no_database_network_or_model_runtime_imports():
    forbidden = ("sqlalchemy", "psycopg", "sqlite3", "requests", "httpx", "urllib", "socket",
                 "writing_coach.persistence", "torch", "transformers", "ollama", "openai", "google.genai")  # fmt: skip
    for path in SOURCES:
        for name in _imports(path):
            assert not any(name == bad or name.startswith(bad + ".") for bad in forbidden), (path.name, name)


def test_no_provider_key_is_read_here():
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        assert "os.environ" not in text and "getenv" not in text, path.name
        assert "_API_KEY" not in text, path.name


def test_the_router_is_mounted_once_behind_its_flag():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert app.count("app.include_router(agent_router)") == 1
    assert "if agent_enabled(os.environ, production=APP_ENV == \"production\")" in app
    assert '"/api/agent' not in app  # the routes are the agent package's own, not app.py's


def test_the_flag_is_documented_off():
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "AGENT_ENABLED=false" in example


def test_the_agent_keys_are_defined_and_inert():
    assert AIOperation.AGENT_TURN == "agent_turn"
    assert AIOperation.CONVERSATIONAL_SPEECH == "conversational_speech"
    assert AIOperation.TEXT_TO_SPEECH == "text_to_speech"
    agent_operations = {AIOperation.AGENT_TURN, AIOperation.CONVERSATIONAL_SPEECH, AIOperation.TEXT_TO_SPEECH}
    keys = {d.key: d for d in all_capabilities() if d.operation in agent_operations}
    assert set(keys) == {"agent_turn_fast", "agent_turn_deep", "conversational_speech", "text_to_speech"}
    # Reserved until a reviewed activation (rulings R1, 2026-09-27): not configurable, no fallback.
    for definition in keys.values():
        assert definition.provider_backed and not definition.configurable and not definition.implemented
        assert {policy.value for policy in definition.allowed_fallback_policies} == {"none"}
