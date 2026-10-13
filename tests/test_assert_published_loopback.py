"""The host-side assertion of Docker's real publish address (issue #140): the pure decision over Docker's JSON, and the
command-line contract with a stubbed Docker. Stdlib only; no Docker is run."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("assert_published_loopback", ROOT / "scripts/assert_published_loopback.py")
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def ports(*hosts: str, port: str = "8000/tcp") -> dict:
    return {port: [{"HostIp": host, "HostPort": "8000"} for host in hosts]}


@pytest.mark.parametrize(
    "document",
    [
        ports("127.0.0.1"),
        ports("::1"),
        ports("127.0.0.1", "::1"),  # Docker's usual dual-stack loopback pair
        ports("127.1.2.3"),
        ports("localhost"),
        ports("::ffff:127.0.0.1"),
        {**ports("127.0.0.1"), "5432/tcp": [{"HostIp": "0.0.0.0", "HostPort": "5432"}]},  # another port is not the app's
        {**ports("127.0.0.1"), "8000/udp": [{"HostIp": "0.0.0.0", "HostPort": "8000"}]},  # udp is not the app's
    ],
)
def test_loopback_only_bindings_pass(document) -> None:
    ok, _addresses, reason = guard.evaluate([document, None])
    assert ok, reason


@pytest.mark.parametrize(
    "hosts",
    [
        ("0.0.0.0",),
        ("::",),
        ("",),  # Docker's JSON for "all interfaces"
        ("192.168.1.20",),
        ("10.0.0.5",),
        ("8.8.8.8",),
        ("fe80::1",),
        ("127.0.0.1", "0.0.0.0"),  # mixed: one loopback entry does not excuse another
        ("::1", "::"),
        ("127.0.0.1", ""),
        ("mybox.local",),
    ],
)
def test_any_non_loopback_binding_is_refused(hosts) -> None:
    ok, _addresses, reason = guard.evaluate([ports(*hosts)])
    assert not ok
    assert "non-loopback" in reason


def test_a_missing_hostip_key_means_all_interfaces() -> None:
    ok, addresses, _reason = guard.evaluate([{"8000/tcp": [{"HostPort": "8000"}]}])
    assert not ok
    assert addresses == [""]


@pytest.mark.parametrize("document", [None, {}, {"8000/tcp": None}, {"8000/tcp": []}, {"9000/tcp": [{"HostIp": "127.0.0.1"}]}, "x", []])
def test_an_unpublished_port_is_refused_because_nothing_can_be_verified(document) -> None:
    ok, addresses, reason = guard.evaluate([document, None])
    assert not ok and addresses == []
    assert "not published" in reason


def test_either_document_can_reveal_a_wide_publish() -> None:
    # NetworkSettings.Ports says loopback, HostConfig.PortBindings (what was asked for) says every interface.
    ok, _a, _r = guard.evaluate([ports("127.0.0.1"), ports("0.0.0.0")])
    assert not ok
    # Not running: NetworkSettings.Ports is null, the configured bindings still decide.
    assert guard.evaluate([None, ports("127.0.0.1")])[0]
    assert not guard.evaluate([None, ports("")])[0]


def test_another_container_port_is_checked_when_asked() -> None:
    document = ports("127.0.0.1", port="9000/tcp")
    assert guard.evaluate([document], port=9000)[0]
    assert not guard.evaluate([document], port=8000)[0]


# ---- the command line, with Docker stubbed -----------------------------------------------------------------------


class FakeDocker:
    def __init__(self, network, host_config) -> None:
        self.answers = {guard.PORT_TEMPLATES[0]: network, guard.PORT_TEMPLATES[1]: host_config}
        self.calls: list[list[str]] = []

    def __call__(self, command, **_kwargs):
        self.calls.append(list(command))
        if command[1] == "inspect":
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(self.answers[command[-1]]), stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")


def run(monkeypatch, capsys, fake, *args):
    monkeypatch.setattr(guard.subprocess, "run", fake)
    code = guard.main(["--container", "orena-web", *args])
    return code, capsys.readouterr()


def test_loopback_passes_and_stops_nothing(monkeypatch, capsys) -> None:
    fake = FakeDocker(ports("127.0.0.1"), ports("127.0.0.1"))
    code, out = run(monkeypatch, capsys, fake)
    assert code == 0
    assert not any(call[1] == "stop" for call in fake.calls)


def test_a_wide_publish_is_refused_names_the_container_and_address_and_stops_it(monkeypatch, capsys) -> None:
    fake = FakeDocker(ports("0.0.0.0"), ports("0.0.0.0"))
    code, out = run(monkeypatch, capsys, fake)
    assert code == 2
    assert "orena-web" in out.err and "0.0.0.0" in out.err
    assert ["docker", "stop", "orena-web"] in fake.calls


def test_no_stop_is_read_only(monkeypatch, capsys) -> None:
    fake = FakeDocker(ports("0.0.0.0"), ports("0.0.0.0"))
    code, _out = run(monkeypatch, capsys, fake, "--no-stop")
    assert code == 2
    assert not any(call[1] == "stop" for call in fake.calls)


def test_docker_reads_only_the_port_fields_never_the_whole_config(monkeypatch, capsys) -> None:
    fake = FakeDocker(ports("127.0.0.1"), ports("127.0.0.1"))
    run(monkeypatch, capsys, fake)
    inspects = [call for call in fake.calls if call[1] == "inspect"]
    assert inspects and all(call[-2] == "--format" for call in inspects)
    for call in inspects:
        assert ".Config" not in call[-1] and "Env" not in call[-1]
        assert "Ports" in call[-1] or "PortBindings" in call[-1]


def test_an_unreadable_docker_fails_closed_and_stops(monkeypatch, capsys) -> None:
    def broken(command, **_kwargs):
        return subprocess.CompletedProcess(command, 1 if command[1] == "inspect" else 0, stdout="", stderr="boom")

    code, out = run(monkeypatch, capsys, broken)
    assert code == 3
    assert "REFUSED" in out.err


def test_the_lan_opt_in_needs_sign_in_on(monkeypatch, capsys) -> None:
    wide = FakeDocker(ports("0.0.0.0"), ports("0.0.0.0"))
    monkeypatch.setattr(guard, "signed_in_required", lambda url, wait_seconds=60.0: True)
    code, _out = run(monkeypatch, capsys, wide, "--lan-opt-in", "--probe-url", "http://127.0.0.1:8000/api/me")
    assert code == 0 and not any(call[1] == "stop" for call in wide.calls)

    monkeypatch.setattr(guard, "signed_in_required", lambda url, wait_seconds=60.0: False)
    wide = FakeDocker(ports("0.0.0.0"), ports("0.0.0.0"))
    code, out = run(monkeypatch, capsys, wide, "--lan-opt-in", "--probe-url", "http://127.0.0.1:8000/api/me")
    assert code == 2 and ["docker", "stop", "orena-web"] in wide.calls
    assert "sign-in" in out.err


def test_the_lan_opt_in_without_a_probe_is_refused(monkeypatch, capsys) -> None:
    wide = FakeDocker(ports("0.0.0.0"), ports("0.0.0.0"))
    code, _out = run(monkeypatch, capsys, wide, "--lan-opt-in")
    assert code == 2


def test_the_lan_opt_in_never_rescues_an_unpublished_or_unreadable_container(monkeypatch, capsys) -> None:
    monkeypatch.setattr(guard, "signed_in_required", lambda url, wait_seconds=60.0: True)
    fake = FakeDocker(None, None)
    code, _out = run(monkeypatch, capsys, fake, "--lan-opt-in", "--probe-url", "http://127.0.0.1:8000/api/me")
    assert code == 2
