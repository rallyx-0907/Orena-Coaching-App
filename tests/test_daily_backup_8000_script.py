"""Static guards for the :8000 daily backup script (it is never run by tests; the human operates :8000, D-127)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP = (ROOT / "scripts" / "daily_backup_8000.ps1").read_text(encoding="utf-8")
REGISTER = (ROOT / "scripts" / "register_daily_backup_8000.ps1").read_text(encoding="utf-8")


def _code(text: str) -> str:
    return text[text.index("#>") + 2:]


def test_backup_script_is_read_only_toward_the_runtime() -> None:
    code = _code(BACKUP)
    for forbidden in ("down -v", "volume rm", "volume prune", "system prune", "docker stop", "docker rm ", "docker kill", "docker restart"):
        assert forbidden not in code, forbidden
    assert "${DataVolume}:/data:ro" in code


def test_backup_script_verifies_the_dump_and_checks_resources_first() -> None:
    code = _code(BACKUP)
    assert "pg_restore --list" in code
    assert "--format=custom" in code
    assert code.index("FreePhysicalMemory") < code.index("docker inspect") < code.index("pg_dump")
    assert "[double]$MinFreeRamGB = 2" in code
    assert "[int]$KeepDays = 14" in code


def test_backup_script_never_reads_credentials_and_retention_is_scoped() -> None:
    code = _code(BACKUP)
    assert "PASSWORD" not in code.upper()
    assert ".Config.Env" not in code
    assert "orena-8000-2*.dump" in code and "orena-8000-data-2*.tar.gz" in code


def test_register_script_prints_unless_apply() -> None:
    code = _code(REGISTER)
    assert "[switch]$Apply" in code
    assert code.index("if (-not $Apply)") < code.index("Invoke-Expression")
    assert "03:30" in code
