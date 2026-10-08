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


FINGERPRINTS = {"users": "a" * 32, "reading_sessions": "b" * 32, "reading_attempts": "c" * 32}
COLUMNS = {"users": ["id", "email"], "reading_sessions": ["id", "user_id"], "reading_attempts": ["id", "session_id"]}


def _backup(tmp_path: Path, *, created: datetime | None = None, cluster: str = "7000000000000000001",
            fingerprints: bool = True) -> dict:
    dump = tmp_path / "database.dump"
    dump.write_bytes(b"PGDMP fake dump")
    files = tmp_path / "files.tar.gz"
    files.write_bytes(b"fake archive")
    manifest = {
        "format": "orena-runtime-backup", "version": 3,
        "created_at": (created or datetime.now(UTC)).isoformat(),
        "database": "becoming", "cluster": cluster, "schema_revision": "20260908_0005",
        "table_counts": {"alembic_version": 1, "users": 3, "reading_sessions": 4, "reading_attempts": 9},
        **({"table_fingerprints": FINGERPRINTS, "table_columns": COLUMNS} if fingerprints else {}),
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


def test_apply_needs_a_passed_rehearsal_of_this_dump_chain_and_execution_code(tmp_path):
    manifest = _backup(tmp_path)
    good = {"passed": True, "dump_sha256": pack.dump_sha(manifest), "chain_digest": "d" * 64, "head": "20261007_0029",
            "execution_digest": "x" * 64, "fingerprints_checked": True}
    gate = {"manifest": manifest, "digest": "d" * 64, "head": "20261007_0029", "execution": "x" * 64}
    pack.check_rehearsal(good, **gate)
    cases = [
        (None, "missing"),
        ({**good, "passed": False}, "did not pass"),
        ({**good, "dump_sha256": "0" * 64}, "different dump"),
        ({**good, "chain_digest": "e" * 64}, "different migration chain"),
        ({**good, "head": "20261004_0025"}, "different migration chain"),
        ({**good, "execution_digest": "y" * 64}, "different migration-execution code"),
        ({k: v for k, v in good.items() if k != "execution_digest"}, "different migration-execution code"),
        ({**good, "fingerprints_checked": False}, "did not verify table contents"),
    ]
    for rehearsal, reason in cases:
        with pytest.raises(pack.Refused, match=reason):
            pack.check_rehearsal(rehearsal, **gate)


def _surface(root: Path) -> None:
    for pattern in pack.EXECUTION_SURFACE:
        path = root / pattern.replace("*", "20260101_0001_x")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"# {pattern}\n".encode())


def test_the_execution_digest_covers_every_file_that_runs_a_migration(tmp_path):
    files = pack.execution_files()
    for required in ("scripts/product_migration_pack.py", "scripts/reading_canonical_cutover.py",
                     "scripts/bootstrap_runtime_schema.py", "migrations/env.py", "alembic.ini", "requirements.txt",
                     "writing_coach/persistence/runtime.py", "migrations/versions/20260924_0016_adaptive_reading.py"):
        assert required in files, required
    _surface(tmp_path)
    first = pack.execution_digest(tmp_path)
    (tmp_path / "migrations/env.py").write_bytes(b"# migrations/env.py\r\n")
    assert pack.execution_digest(tmp_path) == first, "line endings do not count"
    for name in ("scripts/product_migration_pack.py", "scripts/reading_canonical_cutover.py", "requirements.txt"):
        original = (tmp_path / name).read_bytes()
        (tmp_path / name).write_bytes(original + b"changed = True\n")
        assert pack.execution_digest(tmp_path) != first, f"a change to {name} changes the digest"
        (tmp_path / name).write_bytes(original)
    assert pack.execution_digest(tmp_path) == first
    (tmp_path / "scripts/reading_canonical_cutover.py").unlink()
    with pytest.raises(pack.Refused, match="does not have"):
        pack.execution_digest(tmp_path)


def test_fingerprints_follow_the_renames_and_see_a_changed_table():
    applied = ["20260924_0015", "20260924_0016"]
    expected = pack.renamed(FINGERPRINTS, applied)
    assert expected == {"users": "a" * 32, "reading_legacy_sessions": "b" * 32, "reading_legacy_attempts": "c" * 32}
    assert pack.renamed(COLUMNS, applied)["reading_legacy_sessions"] == ["id", "user_id"]
    assert pack.fingerprint_differences(expected, dict(expected)) == []
    assert pack.fingerprint_differences(expected, {**expected, "users": "f" * 32}) == ["users"]
    assert pack.fingerprint_differences(expected, {"users": "a" * 32}) == ["reading_legacy_attempts",
                                                                          "reading_legacy_sessions"]


def test_the_fingerprint_reads_only_the_backed_up_columns_in_order():
    sql = pack.fingerprint_sql("users", ["id", 'odd"name'])
    assert 'ROW(t."id", t."odd""name")::text' in sql
    assert 'FROM public."users" t' in sql
    assert "string_agg(h, '' ORDER BY h)" in sql


def _state(monkeypatch, manifest, *, counts, fingerprints, revision="20260908_0005"):
    chain = ["20260908_0005", "20260911_0006", "20260924_0015", "20260924_0016", "20261007_0029"]
    monkeypatch.setattr(pack, "_head", lambda: chain[-1])
    monkeypatch.setattr(pack, "_chain", lambda: chain)
    monkeypatch.setattr(pack, "_pending", lambda actual, head: chain[chain.index(actual) + 1:])
    monkeypatch.setattr(pack, "revision_on", lambda connection: revision)
    monkeypatch.setattr(pack, "table_counts", lambda connection: counts)
    seen = {}

    def fingerprints_of(connection, columns):
        seen.update(columns)
        return fingerprints

    monkeypatch.setattr(pack, "table_fingerprints", fingerprints_of)
    return pack.check_state(object(), manifest=manifest), seen


def test_an_update_with_unchanged_row_counts_is_refused(tmp_path, monkeypatch):
    """Regression (human review 2026-10-08, finding 1): counts alone miss an UPDATE or a delete+insert."""
    manifest = _backup(tmp_path)
    counts = {"users": 3, "reading_sessions": 4, "reading_attempts": 9}
    (actual, steps, checked), _ = _state(monkeypatch, manifest, counts=counts, fingerprints=dict(FINGERPRINTS))
    assert actual == "20260908_0005" and steps[0] == "20260911_0006" and checked is True
    for changed in ("users", "reading_attempts"):
        with pytest.raises(pack.Refused, match=f"contents changed since the backup although row counts did not.*{changed}"):
            _state(monkeypatch, manifest, counts=counts, fingerprints={**FINGERPRINTS, changed: "0" * 32})


def test_a_resumed_run_compares_contents_under_the_renames_over_the_backed_up_columns(tmp_path, monkeypatch):
    manifest = _backup(tmp_path)
    counts = {"users": 3, "reading_legacy_sessions": 4, "reading_legacy_attempts": 9, "reading_attempts": 0}
    fingerprints = {"users": "a" * 32, "reading_legacy_sessions": "b" * 32, "reading_legacy_attempts": "c" * 32}
    (actual, steps, checked), seen = _state(monkeypatch, manifest, counts=counts, fingerprints=fingerprints,
                                            revision="20260924_0016")
    assert (actual, steps, checked) == ("20260924_0016", ["20261007_0029"], True)
    assert seen["reading_legacy_sessions"] == ["id", "user_id"], "only the columns the backup had"
    with pytest.raises(pack.Refused, match="reading_legacy_sessions"):
        _state(monkeypatch, manifest, counts=counts,
               fingerprints={**fingerprints, "reading_legacy_sessions": "0" * 32}, revision="20260924_0016")


def test_a_backup_without_fingerprints_is_only_count_checked_and_cannot_be_applied(tmp_path, monkeypatch):
    manifest = _backup(tmp_path, fingerprints=False)
    counts = {"users": 3, "reading_sessions": 4, "reading_attempts": 9}
    (_, _, checked), _ = _state(monkeypatch, manifest, counts=counts, fingerprints={})
    assert checked is False
    (tmp_path / "rehearsal.json").write_text(json.dumps({"passed": True}), encoding="utf-8")
    monkeypatch.setattr(pack, "identity", lambda url: {"database": "becoming", "cluster": "7000000000000000001"})
    with pytest.raises(pack.Refused, match="records no content fingerprints"):
        pack.production_checks("postgresql+psycopg://u:p@h/becoming", tmp_path, confirmed="becoming",
                               cluster="7000000000000000001", max_age=12)


def _gate(tmp_path, monkeypatch, *, confirmed="becoming", cluster="7000000000000000001", age=None, server=None):
    created = datetime.now(UTC) - timedelta(hours=age) if age is not None else None
    manifest = _backup(tmp_path, created=created)
    rehearsal = {"passed": True, "dump_sha256": pack.dump_sha(manifest), "chain_digest": pack.chain_digest(),
                 "head": "HEAD", "execution_digest": pack.execution_digest(), "fingerprints_checked": True}
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
