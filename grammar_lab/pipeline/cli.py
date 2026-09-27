"""Grammar Lab CLI: ``python -m grammar_lab.pipeline.cli <command>``.

Phase 0 ships ``validate`` and ``export-error-tags``. generate, verify, route,
coverage and report arrive in phase 1 (SPEC §7).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import typer

from grammar_lab.pipeline.export_error_tags import export_error_tags
from grammar_lab.pipeline.validate import ERROR_TAGS_PATH, LAB_ROOT, LANGS, apply_flags, validate_lang

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Orena Grammar Lab pipeline.")


@app.callback()
def main() -> None:
    """Orena Grammar Lab pipeline."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


@app.command()
def validate(
    lang: str = typer.Option(..., "--lang", help=f"Target language: {', '.join(LANGS)}."),
    root: Path = typer.Option(LAB_ROOT, "--root", help="Grammar Lab root (default: this package)."),
    mark: bool = typer.Option(False, "--mark", help="Write status=flagged and validate:<code> flags into failing files."),
    as_json: bool = typer.Option(False, "--json", help="Print the report as JSON."),
) -> None:
    """Deterministic checks of SPEC §5.2. Exit code 1 when any issue is found."""
    if lang not in LANGS:
        raise typer.BadParameter(f"expected one of {', '.join(LANGS)}", param_hint="--lang")
    started = time.perf_counter()
    report = validate_lang(lang, root)
    elapsed = time.perf_counter() - started
    changed = apply_flags(report, root) if mark else []
    if as_json:
        typer.echo(json.dumps({
            "lang": lang,
            "points": report.points,
            "ok": report.ok,
            "seconds": round(elapsed, 3),
            "issues": [issue.to_dict() for issue in report.issues],
            "marked": changed,
        }, ensure_ascii=False, indent=2))
    else:
        for issue in report.issues:
            typer.echo(f"{issue.reason}  {issue.file}  {issue.path}  {issue.message}")
        for file in changed:
            typer.echo(f"marked  {file}")
        verdict = "OK" if report.ok else f"{len(report.issues)} issue(s)"
        typer.echo(f"validate --lang {lang}: {report.points} point(s), {verdict} in {elapsed:.2f}s")
    raise typer.Exit(0 if report.ok else 1)


@app.command("export-error-tags")
def export_error_tags_command(
    repo_root: Path = typer.Option(LAB_ROOT.parent, "--repo-root", help="Orena repository root holding writing_coach/."),
    output: Path = typer.Option(LAB_ROOT / ERROR_TAGS_PATH, "--output", help="Where to write error_tags.json."),
) -> None:
    """Export the writing evaluator's closed error label lists to schema/error_tags.json."""
    data = export_error_tags(repo_root, output)
    for target_lang, entry in data["languages"].items():
        typer.echo(f"{target_lang}: {len(entry['tags'])} tags from {entry['source_file']}")
    typer.echo(f"wrote {output}")


if __name__ == "__main__":
    app()
