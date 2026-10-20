"""Guards for the :8000 daily backup script. Tests run only its -DryRun; the human operates :8000 (D-127)."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

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
    assert "[int]$KeepCount = 14" in code


def test_backup_script_never_reads_credentials_and_retention_is_scoped() -> None:
    code = _code(BACKUP)
    assert "PASSWORD" not in code.upper()
    assert ".Config.Env" not in code
    assert "orena-8000-2*.dump" in code and "orena-8000-data-2*.tar.gz" in code


def test_register_script_prints_unless_apply() -> None:
    code = _code(REGISTER)
    assert "[switch]$Apply" in code
    assert "Invoke-Expression" not in code
    assert code.index("if (-not $Apply)") < code.index("Register-ScheduledTask -TaskName $TaskName")
    assert "-AllowStartIfOnBatteries" in code and "-DontStopIfGoingOnBatteries" in code and "-WindowStyle Hidden" in code
    assert "03:30" in code


def test_data_step_failure_never_deletes_the_dump_and_no_unpinned_pull() -> None:
    code = _code(BACKUP)
    step = code[code.index("# --- 5."):code.index("# --- 6.")]
    assert "Cleanup-Partial" not in step
    assert "$tarCode -eq 1" in step  # live volume: "file changed as we read it" is a warning
    assert "$dumpName" in step and "is kept" in step
    assert code.index("if ($dataFailed) { Finish 1") > code.index("# --- 6.")
    assert "'alpine'" not in code and "postgres:17-alpine" in code
    assert "docker image inspect" in code


# --- PR BV: RAM floors, retries, exit codes, offsite copy -------------------------------------------------------

def test_dump_and_tar_have_their_own_ram_floors_and_the_tar_never_stops_the_app() -> None:
    code = _code(BACKUP)
    assert "[double]$MinFreeRamGBDump = 0.8" in code and "[double]$MinFreeRamGB = 2" in code
    assert code.index("Wait-ForRam $MinFreeRamGBDump 'dump'") < code.index("Get-Command docker")
    step = code[code.index("# --- 5."):code.index("# --- 6.")]
    assert "Wait-ForRam $MinFreeRamGB 'data volume copy'" in step
    for forbidden in ("docker pause", "docker stop", "compose stop", "compose down"):
        assert forbidden not in code, forbidden


def test_low_ram_waits_and_retries_until_the_cut_off() -> None:
    code = _code(BACKUP)
    assert "[string]$RetryUntil = '06:00'" in code and "[int]$RetryEveryMinutes = 30" in code
    wait = code[code.index("function Wait-ForRam"):code.index("# --- guard rails")]
    assert "while ($true)" in wait and "Start-Sleep -Seconds ($RetryEveryMinutes * 60)" in wait
    assert "$next -gt $cutoff" in wait and "return $false" in wait
    assert "if ((Get-Date) -ge $cutoff) { $cutoff = $null }" in code  # started after the cut-off: one attempt


def test_every_skip_or_failure_exits_non_zero_through_one_logged_exit_path() -> None:
    code = _code(BACKUP)
    assert len(re.findall(r"(?m)^\s*exit \$code$", code)) == 1  # only Finish exits
    assert not re.search(r"(?m)(^|[;{])\s*exit \d", code)
    assert 'Finish 2 ("skipped: free RAM' in code
    tail = code[code.index("if ($dataFailed) { Finish 1"):]
    assert tail.index("Finish 1") < tail.index("Finish 4") < tail.index("Finish 2") < tail.index("Finish 0")
    # The health check reads the last "exit N:" line; the waiting lines must never look like one.
    assert 'Log ("waiting:' in code and "exit {0}: {1}" in code


def test_offsite_copy_encrypts_by_key_path_only_and_prunes_offsite_only() -> None:
    code = _code(BACKUP)
    assert r"'orena-product\offsite-backup.key'" in code and r"'OneDrive\Orena-Backups'" in code
    assert "--symmetric --cipher-algo AES256 --passphrase-file $OffsiteKeyFile" in code
    assert "--passphrase " not in code
    for reads_key in ("Get-Content -LiteralPath $OffsiteKeyFile", "Copy-Item -LiteralPath $OffsiteKeyFile",
                      "ReadAllText($OffsiteKeyFile", "Get-Content $OffsiteKeyFile"):
        assert reads_key not in code
    send = code[code.index("function Send-Offsite"):code.index("$artefacts = @($dumpFile)")]
    assert "SHA256SUMS.txt" in send and "[int]$OffsiteKeepCount = 14" in code
    assert "Get-ChildItem -LiteralPath $OffsiteDir" in send and "Get-ChildItem -LiteralPath $BackupDir" not in send
    assert "if (-not $problem -and $OffsiteKeepCount -ge 1)" in send  # no pruning after a failure
    verify = send[send.index("if ($VerifyOffsite)"):]
    assert "--decrypt" in verify and "finally" in verify and "Remove-Item -LiteralPath $plain" in verify


def _dry_run(tmp_path: Path, ram: float, *extra: str) -> tuple[int, str]:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("no PowerShell on this host")
    backups = tmp_path / "backups"
    args = [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
            str(ROOT / "scripts" / "daily_backup_8000.ps1"), "-DryRun", "-SimulateFreeRamGB", str(ram),
            "-BackupDir", str(backups), "-OffsiteDir", str(tmp_path / "offsite"),
            "-OffsiteKeyFile", str(tmp_path / "missing.key"), "-MinFreeDiskGB", "0",
            "-RetryUntil", "00:00", *extra]  # a cut-off already past: one attempt, no retry
    done = subprocess.run(args, capture_output=True, text=True, timeout=120)
    assert not backups.exists() and not (tmp_path / "offsite").exists()  # a dry run writes nothing, no backup.log
    return done.returncode, done.stdout + done.stderr


def test_dry_run_exit_codes_follow_the_thresholds(tmp_path: Path) -> None:
    code, out = _dry_run(tmp_path, 3.0, "-NoOffsite")
    assert code == 0, out
    code, out = _dry_run(tmp_path, 1.0, "-NoOffsite")  # enough for the dump (0.8), not for the tar (2)
    assert code == 2 and "data volume copy would be skipped" in out, out
    code, out = _dry_run(tmp_path, 0.5, "-NoOffsite")
    assert code == 2 and "skipped: free RAM 0.5 GB stayed below 0.8 GB" in out, out
    code, out = _dry_run(tmp_path, 3.0)  # offsite on, key file missing
    assert code == 4 and "offsite key file is missing" in out, out
    assert "DRY-RUN" in out
