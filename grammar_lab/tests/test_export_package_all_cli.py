from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from grammar_lab.pipeline.cli import app
from grammar_lab.pipeline.jsonio import read_json
from grammar_lab.tests.test_export_package import build_lab


def test_export_package_all_exports_complete_catalog_and_r5_split(tmp_path: Path) -> None:
    root = build_lab(tmp_path, "en")
    out = root / "all-package"

    result = CliRunner().invoke(
        app,
        [
            "export-package",
            "--lang",
            "en",
            "--all",
            "--out",
            str(out),
            "--set-version",
            "test.all",
            "--source-commit",
            "0" * 40,
            "--root",
            str(root),
        ],
    )

    assert result.exit_code == 0, result.output
    manifest = read_json(out / "package.json")
    assert [point["id"] for point in manifest["points"]] == ["en.alpha", "en.beta", "en.gamma"]
    split = [row for row in manifest["r5_map"] if row["r5_id"] == "r3"]
    assert {row["point_id"] for row in split} == {"en.beta", "en.gamma"}
    assert {row["disposition"] for row in split} == {"split_primary", "split_secondary"}
