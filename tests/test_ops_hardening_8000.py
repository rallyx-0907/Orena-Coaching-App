"""Deploy blockers B3/B4/B8 (audit 2026-10-18): real readiness, no query strings in logs, CSP Report-Only."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest
from dataclasses import replace

from fastapi.testclient import TestClient

import app as app_module
from writing_coach.core.access_log import QueryStringScrubFilter, configure_access_log, log_request, scrub_text, scrub_url
from writing_coach.core.http_security import CSP_REPORT_ONLY, hardening_headers, inline_script_hashes


@pytest.fixture(autouse=True)
def _fresh_readiness_cache():
    app_module._readiness_cache.update(key=None, at=0.0, reason=None)


class _DownEngine:
    def connect(self):
        raise RuntimeError("could not connect to server at db.internal.example:5432 password=hunter2")


class _UpEngine:
    def connect(self):
        class _Connection:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def execute(self, statement):
                assert str(statement) == "SELECT 1"

        return _Connection()


def test_readiness_is_503_with_a_stable_reason_and_no_detail_when_the_database_is_down(monkeypatch):
    monkeypatch.setattr(app_module, "_persistence_runtime", replace(app_module._persistence_runtime, engine=_DownEngine()))
    answer = TestClient(app_module.app).get("/api/readiness")
    assert answer.status_code == 503
    body = answer.json()
    assert body["ready"] is False and body["reason"] == "database_unavailable"
    assert "db.internal" not in answer.text and "hunter2" not in answer.text


def test_readiness_is_200_when_the_database_answers(monkeypatch):
    monkeypatch.setattr(app_module, "_persistence_runtime", replace(app_module._persistence_runtime, engine=_UpEngine()))
    answer = TestClient(app_module.app).get("/api/readiness")
    assert answer.status_code == 200 and answer.json()["ready"] is True


def test_access_log_line_has_method_path_status_duration_and_no_query(caplog):
    configure_access_log()
    logger = logging.getLogger("orena.access")
    logger.propagate = True  # caplog listens on the root logger
    try:
        with caplog.at_level("INFO", logger="orena.access"):
            log_request("GET", "/auth/google/callback?state=abc&code=SECRET", 302, 12.4)
    finally:
        logger.propagate = False
    line = caplog.records[-1].getMessage()
    assert line == "GET /auth/google/callback 302 12ms" and "SECRET" not in line


def test_uvicorn_access_filter_drops_the_query_string():
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                               ("1.2.3.4:5", "GET", "/auth/google/callback?code=SECRET", "1.1", 302), None)
    QueryStringScrubFilter().filter(record)
    assert "SECRET" not in record.getMessage() and "/auth/google/callback " in record.getMessage()


def test_url_scrub_keeps_scheme_host_path_only():
    assert scrub_url("https://user:pw@feeds.example.org:8443/a/b.xml?token=T#frag") == "https://feeds.example.org:8443/a/b.xml"
    assert scrub_text("GET https://x.example/f?k=V failed (https://y.example/p?q=W)") == "GET https://x.example/f failed (https://y.example/p)"


def test_html_pages_carry_a_report_only_csp_and_json_does_not():
    client = TestClient(app_module.app)
    page = client.get("/privacy?lang=en")
    policy = page.headers[CSP_REPORT_ONLY.lower()]
    for part in ("default-src 'self'", "frame-ancestors 'none'", "https://www.youtube-nocookie.com", "https://www.youtube.com"):
        assert part in policy
    assert page.headers["content-security-policy"] == "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    assert CSP_REPORT_ONLY.lower() not in client.get("/api/health").headers
    assert CSP_REPORT_ONLY in hardening_headers({"content-type": "text/html; charset=utf-8"}, https=False)
    assert inline_script_hashes() and all(policy.count(h) == 1 for h in inline_script_hashes())


def test_csp_allows_the_live_voice_socket_and_workers():
    policy = hardening_headers({"content-type": "text/html"}, https=False)[CSP_REPORT_ONLY]
    assert "connect-src 'self' wss://generativelanguage.googleapis.com" in policy
    assert "worker-src 'self' blob:" in policy


def test_readiness_answer_is_cached_for_a_moment(monkeypatch):
    calls = []
    monkeypatch.setattr(app_module, "_probe_readiness", lambda: calls.append(1))
    client = TestClient(app_module.app)
    assert client.get("/api/readiness").status_code == 200 and client.get("/api/readiness").status_code == 200
    assert len(calls) == 1


def test_health_check_parses_the_real_backup_log_line_format():
    script = (Path(__file__).resolve().parents[1] / "scripts" / "health_check_8000.ps1").read_text(encoding="utf-8")
    assert "'^\S+ exit \d+: '" in script and "'^\S+ exit 0: '" in script
    sample = "2026-10-18T14:35:59Z exit 0: backup complete: orena-8000-20261018T143559Z.dump, orena-8000-data-20261018T143559Z.tar.gz"
    assert re.match(r"^\S+ exit \d+: ", sample) and re.match(r"^\S+ exit 0: ", sample)
    assert not re.match(r"^\S+ exit 0: ", "2026-10-18T14:35:59Z exit 1: dump failed")


def test_health_check_reads_the_ai_spend_warning_lines_the_guard_really_logs():
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "health_check_8000.ps1").read_text(encoding="utf-8")
    guard = (root / "writing_coach" / "agent" / "budget.py").read_text(encoding="utf-8")
    # The two phrases the script greps are the guard's own log formats.
    assert '"%s daily spend near cap:' in guard and '"%s daily spend cap reached:' in guard
    assert "'daily spend near cap:'" in script and "'daily spend cap reached:'" in script
    # Read-only (docker logs), today's UTC lines, once per UTC day and level, through the shared alert path.
    assert "docker.exe logs $spendContainer --since $sinceUtc" in script
    assert "$state.spendDay" in script and "$state.spendLevel" in script
    assert script.count("Raise-Alert") >= 3
    # Not a health failure: the branch never adds to $failures.
    branch = script[script.index("# 6. The daily AI spend ceiling"):script.index("# Alerting: after")]
    assert "$failures" not in branch
    for sample in ("system daily spend near cap: 4.0100 of 5.00 USD (80%)", "system daily spend cap reached: 5.0100 of 5.00 USD"):
        assert re.search(r"daily spend (near cap|cap reached):", sample)


# ---- pre-deploy hardening ---------------------------------------------------------------------------------------


def test_the_deploy_script_refuses_to_start_without_the_runtime_safety_keys():
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "staging_8000_deploy.ps1").read_text(encoding="utf-8")
    for key in ("AI_DAILY_SPEND_CEILING_USD", "AI_DAILY_SPEND_WARN_RATIO", "LEGAL_EFFECTIVE_DATE",
                "AGENT_MEMORY_HMAC_KEYS", "AGENT_MEMORY_RETENTION_SWEEP"):
        assert f"'{key}'" in script
    # The check runs before anything is started, fails through Fail (exit 1), and never prints a value.
    check = script[script.index("$runtimeKeys"):script.index("if ($names['APP_ENV']")]
    assert script.index("$runtimeKeys") < script.index("docker.exe")
    assert "Fail " in check and "Write-Host" not in check
    assert "function Fail" in script and "exit 1" in script


def test_enforced_csp_carries_the_always_safe_directives_beside_the_report_only_policy():
    added = hardening_headers({"content-type": "text/html; charset=utf-8"}, https=True)
    enforced = added["Content-Security-Policy"]
    for directive in ("object-src 'none'", "base-uri 'self'", "form-action 'self'", "frame-ancestors 'none'"):
        assert directive in enforced
    assert "script-src" not in enforced and CSP_REPORT_ONLY in added
    # A non-HTML answer carries neither; a route's own enforced policy is kept.
    assert "Content-Security-Policy" not in hardening_headers({"content-type": "application/json"}, https=True)
    assert "Content-Security-Policy" not in hardening_headers(
        {"content-type": "text/html", "Content-Security-Policy": "sandbox"}, https=True)


def test_nothing_in_the_shipped_pages_posts_a_form_elsewhere_or_frames_us():
    root = Path(__file__).resolve().parents[1]
    for folder in ("templates", "static"):
        for page in (root / folder).rglob("*.html"):
            text = page.read_text(encoding="utf-8")
            for action in re.findall(r"<form[^>]*\baction=[\"']([^\"']+)", text, re.IGNORECASE):
                assert not re.match(r"https?://", action), f"{page}: form posts to {action}"


def _ops(name):
    return (Path(__file__).resolve().parents[1] / "scripts" / name).read_text(encoding="utf-8")


def test_both_registrations_run_headless_with_a_fallback_and_stay_under_the_user():
    for name in ("register_health_check_8000.ps1", "register_daily_backup_8000.ps1"):
        text = _ops(name)
        assert "conhost.exe" in text and "--headless powershell.exe" in text
        assert "Version.Build -lt 22000" in text
        assert "conhost.exe --headless cmd /c exit" in text
        assert "-WindowStyle Hidden" in text  # the fallback
        assert "SYSTEM" not in text and "-Password" not in text and "-RunLevel" not in text


def test_no_msg_exe_and_toast_is_off_by_default():
    root = Path(__file__).resolve().parents[1]
    for script in (root / "scripts").glob("*8000*.ps1"):
        assert "msg.exe" not in script.read_text(encoding="utf-8"), script.name
    health = _ops("health_check_8000.ps1")
    assert "[switch]$NoToast" in health and "if ($NoToast) { return $false }" in health
    register = _ops("register_health_check_8000.ps1")
    assert "[switch]$Toast" in register and "' -NoToast'" in register


def test_maintenance_flag_and_no_backup_yet_do_not_count_as_failures():
    health = _ops("health_check_8000.ps1")
    assert "maintenance.flag" in health
    paused = health[health.index("if (Test-Path -LiteralPath $MaintenanceFlag)"):health.index("# 1-2.")]
    assert "'paused'" in paused and "exit 0" in paused and "$state.failures" not in paused
    start = health.index("$backupStatus = 'no_backup_yet'")
    skipped = health[start:health.index("} else {", start)]
    assert "Check " not in skipped


def test_state_json_keeps_its_keys_and_only_adds_paused_and_last_status():
    health = _ops("health_check_8000.ps1")
    init = re.search(r"\$state = @\{(.*?)\}\r?\n", health).group(1)
    keys = [k.strip().split(" = ")[0] for k in init.split(";")]
    assert keys[:4] == ["failures", "restarts", "spendDay", "spendLevel"]
    assert keys[4:] == ["paused", "last_status"]
    assert "$state.last_status = 'ok'" in health and "$state.last_status = 'unhealthy'" in health


def test_powershell_scripts_parse_when_powershell_is_available():
    import shutil
    import subprocess

    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("no PowerShell on this host")
    root = Path(__file__).resolve().parents[1] / "scripts"
    for name in ("health_check_8000.ps1", "register_health_check_8000.ps1", "register_daily_backup_8000.ps1"):
        command = ("$e=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%s',[ref]$null,[ref]$e);"
                   "if($e.Count){$e|%%{$_.Message};exit 1}" % (root / name))
        done = subprocess.run([exe, "-NoProfile", "-Command", command], capture_output=True, text=True)
        assert done.returncode == 0, done.stdout + done.stderr

def test_the_deploy_script_validates_the_runtime_keys_with_the_apps_own_rules():
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "staging_8000_deploy.ps1").read_text(encoding="utf-8")
    check = script[script.index("$runtimeKeys"):script.index("if ($names['APP_ENV']")]
    assert "TryParseExact" in check and "'yyyy-MM-dd'" in check and "InvariantCulture" in script
    assert "twice" in check and "shorter than 32" in check and "[1-9][0-9]{0,3}" in check
    assert "-cnotmatch '^(on|off)$'" in check
    assert "FEEDBACK_RETENTION_SWEEP" in check and "AGENT_TURN_RETENTION_SWEEP" in check and "Write-Warning" in check
    assert "Write-Host" not in check


def test_pronunciation_body_cap_follows_an_operator_raised_provider_limit(monkeypatch):
    from writing_coach.core.http_security import body_limit

    for name in ("AZURE_PRONUNCIATION_MAX_BYTES", "DEMO_PRONUNCIATION_MAX_BYTES"):
        monkeypatch.delenv(name, raising=False)
    assert body_limit("POST", "/api/speech/pronunciation") == 16 * 1024 * 1024
    monkeypatch.setenv("AZURE_PRONUNCIATION_MAX_BYTES", str(4 * 1024 * 1024))
    assert body_limit("POST", "/api/speech/pronunciation") == 16 * 1024 * 1024
    monkeypatch.setenv("AZURE_PRONUNCIATION_MAX_BYTES", str(24 * 1024 * 1024))
    assert body_limit("POST", "/api/speech/pronunciation") == 25 * 1024 * 1024
    monkeypatch.setenv("AZURE_PRONUNCIATION_MAX_BYTES", "not-a-number")
    assert body_limit("POST", "/api/speech/pronunciation") == 16 * 1024 * 1024
