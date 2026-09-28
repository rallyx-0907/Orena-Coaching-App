"""Grammar Lab CLI: ``python -m grammar_lab.pipeline.cli <command>``.

Phase 0 ships ``validate`` and ``export-error-tags``. Phase 1 adds
``generate``, ``verify``, ``route`` and ``report`` (SPEC §7). ``coverage``
stays a phase-3 stub: it needs a populated inventory, which SPEC §4 defers.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import typer

from grammar_lab.pipeline.content_store import load_point, load_points, save_point
from grammar_lab.pipeline.evaluator_client import EvaluatorClient
from grammar_lab.pipeline.export_error_tags import export_error_tags
from grammar_lab.pipeline.generate import GenerateOutcome, Generator
from grammar_lab.pipeline.llm_client import LLMClient, LLMError
from grammar_lab.pipeline.report_step import build_report, render_html
from grammar_lab.pipeline.route import DEFAULT_THRESHOLD_BY_LANG, apply_route, route_point
from grammar_lab.pipeline.run_context import new_run_id, resolve_run_id, run_dir, write_step
from grammar_lab.pipeline.validate import ERROR_TAGS_PATH, LAB_ROOT, LANGS, apply_flags, validate_lang
from grammar_lab.pipeline.verify import VerifyFlag, VerifyReport, verify_point

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


@app.command()
def generate(
    lang: str = typer.Option(..., "--lang", help=f"Target language: {', '.join(LANGS)}."),
    l1: str = typer.Option("vi", "--l1", help="Learner L1 (informational; blocks cover every L1 in the set manifest)."),
    ids: str = typer.Option(..., "--ids", help="Comma-separated point ids, e.g. en.past_simple,en.there_is_are."),
    provider: str = typer.Option("anthropic", "--provider", help="LLM provider: anthropic | openai | gemini | groq | deepseek."),
    model: str = typer.Option("claude-haiku-4-5-20251001", "--model", help="Model id for that provider."),
    regenerate_note: str = typer.Option(
        "", "--regenerate-note",
        help="Admin note for regenerating an already-approved point (SPEC §6); required to touch one.",
    ),
    with_story: bool = typer.Option(
        False, "--with-story",
        help="Also generate the daily-theme story block (STORY_SPEC.md) and bump the point to schema_version 0.3.",
    ),
    root: Path = typer.Option(LAB_ROOT, "--root"),
) -> None:
    """SPEC §5.1: code-generated rule_table + LLM-generated blocks + templated check items."""
    if lang not in LANGS:
        raise typer.BadParameter(f"expected one of {', '.join(LANGS)}", param_hint="--lang")
    outcomes = []
    with LLMClient(provider, model) as llm:
        generator = Generator(lang=lang, l1=l1, llm=llm, root=root)
        for point_id in (p.strip() for p in ids.split(",") if p.strip()):
            try:
                outcomes.append(generator.generate(point_id, regenerate_note=regenerate_note or None, with_story=with_story))
            except LLMError as exc:
                # A failed call can still have been billed (e.g. DeepSeek's reasoning
                # tokens on an empty-content response) -- exc.usage carries that spend.
                wasted_cost = exc.usage.cost_usd(model) if exc.usage is not None else None
                outcomes.append(GenerateOutcome(point_id, "error", reason=str(exc), cost_usd=wasted_cost))
    total_cost = sum(o.cost_usd for o in outcomes if o.cost_usd is not None)
    for outcome in outcomes:
        cost = f"${outcome.cost_usd:.4f}" if outcome.cost_usd is not None else ("cached" if outcome.cached else "n/a")
        typer.echo(f"{outcome.status:16} {outcome.point_id:40} {cost}  {outcome.reason}")
    typer.echo(f"generate --lang {lang}: {len(outcomes)} point(s), ~${total_cost:.4f} this run")
    run_id = new_run_id()
    write_step(root, run_id, "generate", {
        "run_id": run_id, "lang": lang, "provider": provider, "model": model,
        "outcomes": [
            {"point_id": o.point_id, "status": o.status, "reason": o.reason, "cost_usd": o.cost_usd, "cached": o.cached}
            for o in outcomes
        ],
    })
    if any(o.status == "error" for o in outcomes):
        raise typer.Exit(1)


@app.command()
def verify(
    lang: str = typer.Option(..., "--lang", help=f"Target language: {', '.join(LANGS)}."),
    evaluator_url: str = typer.Option(
        ..., "--evaluator-url",
        help="Base URL of a writing-evaluator instance you are allowed to operate. "
             "Never the public orena.chillpickle.org tunnel: that is production, a human gate "
             "(AGENTS.md Safety). Point this at a sandbox, e.g. http://localhost:8020 "
             "(grammar_lab/sandbox/).",
    ),
    blind_provider: str = typer.Option("gemini", "--blind-provider", help="Must differ from generate's --provider."),
    blind_model: str = typer.Option("gemini-3.5-flash-lite", "--blind-model"),
    evaluator_rate_limit_key: str = typer.Option(
        "gemini", "--evaluator-rate-limit-key",
        help="Shares a rate limiter with --blind-provider when the sandbox's engine and the "
             "blind-solve model draw on the same provider quota (grammar_lab/sandbox/ defaults "
             "to Gemini for both). Pass '' to disable if the sandbox uses an unmetered provider.",
    ),
    ids: str = typer.Option("", "--ids", help="Comma-separated point ids to verify (default: every point)."),
    root: Path = typer.Option(LAB_ROOT, "--root"),
) -> None:
    """SPEC §5.3: engine pitfall match, clean examples, blind solve. Skips points that fail validate."""
    if lang not in LANGS:
        raise typer.BadParameter(f"expected one of {', '.join(LANGS)}", param_hint="--lang")
    report = validate_lang(lang, root)
    dirty_ids = {report.point_files[file] for file in {i.file for i in report.issues} if file in report.point_files}
    points = load_points(lang, root)
    if ids:
        wanted = {p.strip() for p in ids.split(",") if p.strip()}
        points = {point_id: point for point_id, point in points.items() if point_id in wanted}
    results: dict[str, dict] = {}
    evaluator = EvaluatorClient(evaluator_url, rate_limit_key=evaluator_rate_limit_key or None)
    with evaluator, LLMClient(blind_provider, blind_model) as blind_solver:
        for point_id, point in points.items():
            if point_id in dirty_ids:
                results[point_id] = {"flags": [], "skipped": "validate_failed"}
                continue
            verify_report = verify_point(point, evaluator=evaluator, blind_solver=blind_solver)
            results[point_id] = {
                "flags": [{"code": f.code, "detail": f.detail} for f in verify_report.flags],
                "checked_pitfalls": verify_report.checked_pitfalls,
                "checked_examples": verify_report.checked_examples,
                "checked_checks": verify_report.checked_checks,
            }
            verdict = "OK" if verify_report.ok else f"{len(verify_report.flags)} flag(s)"
            typer.echo(f"{point_id:40} {verdict}")
    run_id = new_run_id()
    write_step(root, run_id, "verify", {
        "run_id": run_id, "lang": lang, "evaluator_url": evaluator_url,
        "blind_provider": blind_provider, "blind_model": blind_model, "points": results,
    })
    typer.echo(f"verify --lang {lang}: {len(results)} point(s) checked")


@app.command()
def route(
    lang: str = typer.Option(..., "--lang", help=f"Target language: {', '.join(LANGS)}."),
    threshold: float = typer.Option(None, "--threshold", help="Default: SPEC §5.4's starting value per language."),
    gold_set_passed: bool = typer.Option(
        False, "--gold-set-passed",
        help="This lang/L1 has been through the gold-set review of SPEC §5.4 point 1-2. "
             "Without it every point is flagged regardless of score (SPEC §5.4 rule 2).",
    ),
    run: str = typer.Option("latest", "--run", help="verify run to route on."),
    root: Path = typer.Option(LAB_ROOT, "--root"),
) -> None:
    """SPEC §5.4: score, auto_ok/flagged, 10% sampling. Writes status/flags back into content/."""
    if lang not in LANGS:
        raise typer.BadParameter(f"expected one of {', '.join(LANGS)}", param_hint="--lang")
    if threshold is None:
        threshold = DEFAULT_THRESHOLD_BY_LANG.get(lang, 0.8)
    verify_run_id = resolve_run_id(root, run)
    verify_data = json.loads((run_dir(root, verify_run_id) / "verify.json").read_text(encoding="utf-8"))
    if verify_data["lang"] != lang:
        raise typer.BadParameter(f"run {verify_run_id} verified {verify_data['lang']!r}, not {lang!r}", param_hint="--run")

    validate_report = validate_lang(lang, root)
    issue_codes_by_id: dict[str, set[str]] = {}
    for issue in validate_report.issues:
        point_id = validate_report.point_files.get(issue.file)
        if point_id:
            issue_codes_by_id.setdefault(point_id, set()).add(issue.code)

    outcomes: dict[str, dict] = {}
    for point_id, entry in verify_data["points"].items():
        point = load_point(lang, point_id, root)
        if point is None:
            continue
        verify_report = None if entry.get("skipped") else VerifyReport(
            point_id, [VerifyFlag(f["code"], f["detail"]) for f in entry["flags"]],
        )
        outcome = route_point(
            point_id, validate_issue_codes=issue_codes_by_id.get(point_id, set()),
            verify_report=verify_report, threshold=threshold, gold_set_passed=gold_set_passed,
            target_lang=point.get("target_lang"), has_story=any(b["type"] == "story" for b in point["blocks"]),
        )
        save_point(lang, apply_route(point, outcome), root)
        outcomes[point_id] = {"score": outcome.score, "status": outcome.status, "flags": outcome.flags}
        typer.echo(f"{point_id:40} score={outcome.score:.2f} -> {outcome.status}")

    run_id = new_run_id()
    write_step(root, run_id, "route", {
        "run_id": run_id, "lang": lang, "threshold": threshold, "gold_set_passed": gold_set_passed,
        "verify_run_id": verify_run_id, "points": outcomes,
    })
    typer.echo(f"route --lang {lang}: {len(outcomes)} point(s), threshold={threshold}, gold_set_passed={gold_set_passed}")


@app.command()
def report(
    lang: str = typer.Option(..., "--lang", help=f"Target language: {', '.join(LANGS)}."),
    run: str = typer.Option("latest", "--run"),
    root: Path = typer.Option(LAB_ROOT, "--root"),
) -> None:
    """SPEC §5.5: status counts, flag rates, API cost, average review time. Writes JSON + HTML."""
    run_id = resolve_run_id(root, run)
    data = build_report(root, run_id, lang)
    out_dir = run_dir(root, run_id)
    (out_dir / "report.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    (out_dir / "report.html").write_text(render_html(data), encoding="utf-8", newline="\n")
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
    typer.echo(f"wrote {out_dir / 'report.json'} and {out_dir / 'report.html'}")


if __name__ == "__main__":
    app()
