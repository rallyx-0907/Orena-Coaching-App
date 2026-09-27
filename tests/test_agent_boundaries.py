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
        "context", "redaction", "voice",
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


def test_no_router_is_installed_in_slice_1a():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "writing_coach.agent" not in app
    assert "/api/agent" not in app


def test_the_three_operations_exist_and_no_capability_uses_them_yet():
    assert AIOperation.AGENT_TURN == "agent_turn"
    assert AIOperation.CONVERSATIONAL_SPEECH == "conversational_speech"
    assert AIOperation.TEXT_TO_SPEECH == "text_to_speech"
    agent_operations = {AIOperation.AGENT_TURN, AIOperation.CONVERSATIONAL_SPEECH, AIOperation.TEXT_TO_SPEECH}
    # The four keys wait for their Admin console labels (human ruling 2026-09-27, option C).
    assert not [definition.key for definition in all_capabilities() if definition.operation in agent_operations]
