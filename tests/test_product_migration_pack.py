"""The production migration pack's gates (D-143), without a database: what it refuses and how it compares rows."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("product_migration_pack", ROOT / "scripts" / "product_migration_pack.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pack = _load()


def _backup(tmp_path: Path, *, created: datetime | None = None, cluster: str = "7000000000000000001") -> dict:
    dump = tmp_path / "database.dump"
    dump.write_bytes(b"PGDMP fake dump")
    files = tmp_path / "files.tar.gz"
    files.write_bytes(b"fake archive")
    manifest = {
        "format": "orena-runtime-backup", "version": 2,
        "created_at": (created or datetime.now(UTC)).isoformat(),
        "database": "becoming", "cluster": cluster, "schema_revision": "20260908_0005",
        "table_counts": {"alembic_version": 1, "users": 3, "reading_sessions": 4, "reading_attempts": 9},
        "files": [{"name": name, "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                  for name, path in (("database.dump", dump), ("files.tar.gz", files))],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def test_chain_digest_ignores_line_endings_and_sees_content(tmp_path):
    (tmp_path / "a_0001.py").write_bytes(b"x = 1\n")
    (tmp_path / "b_0002.py").write_bytes(b"y = 2\n")
    first = pack.chain_digest(tmp_path)
    (tmp_path / "a_0001.py").write_bytes(b"x = 1\r\n")
    assert pack.chain_digest(tmp_path) == first
    (tmp_path / "b_0002.py").write_bytes(b"y = 3\n")
    assert pack.chain_digest(tmp_path) != first
    (tmp_path / "c_0003.py").write_bytes(b"")
    assert pack.chain_digest(tmp_path) != first


def test_the_real_chain_has_a_digest():
    assert len(pack.chain_digest()) == 64


def test_counts_follow_the_reading_cutover_renames():
    recorded = {"alembic_version": 1, "users": 3, "reading_sessions": 4, "reading_attempts": 9}
    assert pack.expected_counts(recorded, ["20260911_0006"]) == {"users": 3, "reading_sessions": 4, "reading_attempts": 9}
    after = pack.expected_counts(recorded, ["20260924_0015", "20260924_0016", "20260930_0017"])
    assert after == {"users": 3, "reading_legacy_sessions": 4, "reading_legacy_attempts": 9}
    # The canonical reading_attempts the cutover creates is a new table, not a changed one.
    found = {"users": 3, "reading_legacy_sessions": 4, "reading_legacy_attempts": 9, "reading_attempts": 0}
    assert pack.count_differences(after, found) == []
    assert pack.count_differences(after, {**found, "users": 4}) == ["users: backup 3, now 4"]
    assert pack.count_differences(after, {"users": 3}) == [
        "reading_legacy_attempts: backup 9, now absent", "reading_legacy_sessions: backup 4, now absent"]


def test_backup_files_must_match_the_manifest(tmp_path):
    manifest = _backup(tmp_path)
    pack.check_backup_files(tmp_path, manifest)
    (tmp_path / "database.dump").write_bytes(b"PGDMP changed")
    with pytest.raises(pack.Refused, match="database.dump does not match"):
        pack.check_backup_files(tmp_path, manifest)
    (tmp_path / "database.dump").unlink()
    with pytest.raises(pack.Refused, match="missing"):
        pack.check_backup_files(tmp_path, manifest)


def test_a_folder_without_a_backup_manifest_is_refused(tmp_path):
    with pytest.raises(pack.Refused, match="manifest.json is missing"):
        pack.load_manifest(tmp_path)
    (tmp_path / "manifest.json").write_text('{"format": "something-else"}', encoding="utf-8")
    with pytest.raises(pack.Refused, match="not an orena-runtime-backup"):
        pack.load_manifest(tmp_path)
    # PowerShell 5 writes UTF-8 with a byte-order mark.
    (tmp_path / "manifest.json").write_bytes(b"\xef\xbb\xbf" + json.dumps({"format": "orena-runtime-backup"}).encode())
    assert pack.load_manifest(tmp_path)["format"] == "orena-runtime-backup"


def test_backup_age_is_measured_from_its_creation(tmp_path):
    manifest = _backup(tmp_path, created=datetime(2026, 10, 8, 0, 0, tzinfo=UTC))
    assert pack.backup_age_hours(manifest, now=datetime(2026, 10, 8, 13, 30, tzinfo=UTC)) == pytest.approx(13.5)


def test_apply_needs_a_passed_rehearsal_of_this_dump_and_this_chain(tmp_path):
    manifest = _backup(tmp_path)
    good = {"passed": True, "dump_sha256": pack.dump_sha(manifest), "chain_digest": "d" * 64, "head": "20261007_0029"}
    pack.check_rehearsal(good, manifest=manifest, digest="d" * 64, head="20261007_0029")
    cases = [
        (None, "missing"),
        ({**good, "passed": False}, "did not pass"),
        ({**good, "dump_sha256": "0" * 64}, "different dump"),
        ({**good, "chain_digest": "e" * 64}, "different migration chain"),
        ({**good, "head": "20261004_0025"}, "different migration chain"),
    ]
    for rehearsal, reason in cases:
        with pytest.raises(pack.Refused, match=reason):
            pack.check_rehearsal(rehearsal, manifest=manifest, digest="d" * 64, head="20261007_0029")


def _gate(tmp_path, monkeypatch, *, confirmed="becoming", cluster="7000000000000000001", age=None, server=None):
    created = datetime.now(UTC) - timedelta(hours=age) if age is not None else None
    manifest = _backup(tmp_path, created=created)
    rehearsal = {"passed": True, "dump_sha256": pack.dump_sha(manifest), "chain_digest": pack.chain_digest(),
                 "head": "HEAD"}
    (tmp_path / "rehearsal.json").write_text(json.dumps(rehearsal), encoding="utf-8")
    monkeypatch.setattr(pack, "_head", lambda: "HEAD")
    monkeypatch.setattr(pack, "identity", lambda url: server or {"database": "becoming", "cluster": "7000000000000000001"})
    return pack.production_checks("postgresql+psycopg://u:p@h/becoming", tmp_path, confirmed=confirmed, cluster=cluster,
                                  max_age=12)


def test_production_gates_pass_only_for_the_backed_up_database_and_cluster(tmp_path, monkeypatch):
    manifest, found = _gate(tmp_path, monkeypatch)
    assert found["database"] == "becoming" and manifest["schema_revision"] == "20260908_0005"


@pytest.mark.parametrize("kwargs, reason", [
    ({"confirmed": "postgres"}, "not the backup's database"),
    ({"cluster": "7000000000000000002"}, "not the cluster the backup recorded"),
    ({"age": 13}, "h old"),
    ({"server": {"database": "becoming", "cluster": "7000000000000000009"}}, "nothing was touched"),
    ({"server": {"database": "other", "cluster": "7000000000000000001"}}, "nothing was touched"),
])
def test_production_gates_refuse(tmp_path, monkeypatch, kwargs, reason):
    with pytest.raises(pack.Refused, match=reason):
        _gate(tmp_path, monkeypatch, **kwargs)


def test_the_commands_refuse_without_their_arguments(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("POSTGRES_RUNTIME_URL", raising=False)
    assert pack.main(["plan", "--backup", str(tmp_path)]) == 2
    assert "no database" in capsys.readouterr().out
    url = "postgresql+psycopg://u:p@h/becoming"
    assert pack.main(["apply", "--url", url, "--backup", str(tmp_path)]) == 2
    assert "--confirm-production" in capsys.readouterr().out
    assert pack.main(["rehearse", "--url", url, "--backup", str(tmp_path)]) == 2
    assert "--confirm-rehearsal" in capsys.readouterr().out
    assert pack.main(["apply", "--url", url, "--backup", str(tmp_path), "--confirm-production", "becoming",
                      "--expect-cluster", "1"]) == 2
    assert "--authorization" in capsys.readouterr().out
