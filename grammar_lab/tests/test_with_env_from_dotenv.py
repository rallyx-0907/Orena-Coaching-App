from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "sandbox" / "with_env_from_dotenv.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("with_env_from_dotenv", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


module = _load_module()


def write_env(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_reads_only_the_requested_names(tmp_path: Path) -> None:
    path = write_env(tmp_path / ".env", "A=1\nB=2\nC=3\n")
    assert module.read_dotenv_values(path, {"A", "C"}) == {"A": "1", "C": "3"}


def test_strips_matching_quotes(tmp_path: Path) -> None:
    path = write_env(tmp_path / ".env", 'A="quoted value"\nB=\'single quoted\'\n')
    assert module.read_dotenv_values(path, {"A", "B"}) == {"A": "quoted value", "B": "single quoted"}


def test_skips_comments_and_blank_lines(tmp_path: Path) -> None:
    path = write_env(tmp_path / ".env", "# a comment\n\nA=1\n")
    assert module.read_dotenv_values(path, {"A"}) == {"A": "1"}


def test_empty_value_is_not_returned(tmp_path: Path) -> None:
    path = write_env(tmp_path / ".env", "A=\nB=2\n")
    assert module.read_dotenv_values(path, {"A", "B"}) == {"B": "2"}


def test_name_not_present_is_absent_from_result(tmp_path: Path) -> None:
    path = write_env(tmp_path / ".env", "A=1\n")
    assert module.read_dotenv_values(path, {"A", "MISSING"}) == {"A": "1"}


def test_main_exits_2_and_reports_missing_names_only(tmp_path: Path, capsys) -> None:
    path = write_env(tmp_path / ".env", "A=distinctive-secret-value-42\n")
    code = module.main([str(path), "A,MISSING", "--", "python3", "-c", "1"])
    assert code == 2
    captured = capsys.readouterr()
    assert "MISSING" in captured.err
    assert "distinctive-secret-value-42" not in captured.err  # value of A never printed


def test_main_runs_the_command_with_the_value_injected(tmp_path: Path) -> None:
    path = write_env(tmp_path / ".env", "GREETING_TEST_VAR=hello-value\n")
    script = tmp_path / "print_env.py"
    script.write_text(
        "import os, sys\n"
        "sys.exit(0 if os.environ.get('GREETING_TEST_VAR') == 'hello-value' else 1)\n",
        encoding="utf-8",
    )
    code = module.main([str(path), "GREETING_TEST_VAR", "--", sys.executable, str(script)])
    assert code == 0
