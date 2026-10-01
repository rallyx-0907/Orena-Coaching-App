"""Grammar Lab CLI: ``python -m grammar_lab.pipeline.cli <command>``.

Phase 0 ships ``validate`` and ``export-error-tags``. Phase 1 adds
``generate``, ``verify``, ``route`` and ``report`` (SPEC §7). ``import-canonical`` converts the locked
canonical catalog v1 into the runtime catalogue and ``coverage`` reports it against the content on disk.
"""

from __future__ import annotations

import contextlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import sys
import time
from pathlib import Path

import typer

from grammar_lab.pipeline.apply_feedback import apply_feedback as run_apply_feedback
from grammar_lab.pipeline.apply_feedback import dedupe, feedback_stats, parse_files
from grammar_lab.pipeline.content_store import load_point, load_points, save_point
from grammar_lab.pipeline import engine_grade, live_lock
from grammar_lab.pipeline.evaluator_client import EvaluatorClient
from grammar_lab.pipeline.export_error_tags import export_error_tags
from grammar_lab.pipeline.generate import GenerateOutcome, Generator, PROMPT_VERSION_V04
from grammar_lab.pipeline.llm_client import LLMClient, LLMError
from grammar_lab.pipeline.preview import DEFAULT_OUT_DIR as DEFAULT_PREVIEW_DIR
from grammar_lab.pipeline.preview import serve as serve_preview
from grammar_lab.pipeline.preview import write_preview
from grammar_lab.pipeline.report_step import build_report, render_html
from grammar_lab.pipeline.review_export import levels_present, review_path, write_review
from grammar_lab.pipeline.route import DEFAULT_THRESHOLD_BY_LANG, apply_route, route_point
from grammar_lab.pipeline.canonical import catalog_is_current, load_canonical, write_catalog
from grammar_lab.pipeline.coverage import coverage_report, render_text as render_coverage
from grammar_lab.pipeline.corpus import generation_items, matches_generation_provenance, normalize_langs, plan_corpus, render_text as render_corpus, stratified_items
from grammar_lab.pipeline.seed import GenerationBlocked, audit_seed_semantics, check_generation_gate, select_ids, sync_seed_metadata
from grammar_lab.pipeline.export_package import ExportError, export_package, package_to_zip, validate_package
from grammar_lab.pipeline.export_profile import (
    PROFILE_SCHEMA_PATH, derive_profile_schema, load_internal_schema, profile_drift,
)
from grammar_lab.pipeline.jsonio import write_json
from grammar_lab.pipeline.r5_map import load_dropped_r5_ids
from grammar_lab.pipeline.ui_fixtures import DEMO_POINTS, fixture_dir, write_fixtures as write_ui_fixtures
from grammar_lab.pipeline.run_context import new_run_id, resolve_run_id, run_dir, write_step
from grammar_lab.pipeline.validate import ERROR_TAGS_PATH, LAB_ROOT, LANGS, apply_flags, validate_generated_point, validate_lang
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


@app.command("sync-metadata")
def sync_metadata_command(
    check: bool = typer.Option(False, "--check", help="Write nothing; exit 1 when content/function metadata is stale."),
    root: Path = typer.Option(LAB_ROOT, "--root"),
) -> None:
    """Apply seed metadata to existing content and rebuild function planned/realized lists."""
    result = sync_seed_metadata(root, check=check)
    if not check:
        fixture_changed = write_ui_fixtures(root)
        typer.echo(f"sync-metadata: UI fixtures {'refreshed' if fixture_changed else 'current'}")
    typer.echo(
        f"sync-metadata: changed points {result['changed_point_count']}, "
        f"function registry {'stale' if result['registry_changed'] else 'current'}"
    )
    raise typer.Exit(0 if (result["ok"] or not check) else 1)

@app.command("seed-audit")
def seed_audit_command(
    lang: str = typer.Option("all", "--lang", help="all | en | zh."),
    as_json: bool = typer.Option(False, "--json", help="Print machine-readable findings."),
    root: Path = typer.Option(LAB_ROOT, "--root"),
) -> None:
    """Report obvious semantic-review debt in seed metadata. Exit 1 when found."""
    try:
        langs = normalize_langs(lang)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--lang") from exc
    findings: list[dict[str, str]] = []
    for code in langs:
        for finding in audit_seed_semantics(code, root):
            findings.append({"lang": code, **finding})
    if as_json:
        typer.echo(json.dumps(findings, ensure_ascii=False, indent=2))
    else:
        counts: dict[tuple[str, str], int] = {}
        for finding in findings:
            key = (finding["lang"], finding["code"])
            counts[key] = counts.get(key, 0) + 1
        for (code, issue), count in sorted(counts.items()):
            typer.echo(f"{code}: {issue}: {count}")
        typer.echo(f"seed-audit: {len(findings)} finding(s)")
    raise typer.Exit(1 if findings else 0)

@app.command("import-canonical")
def import_canonical(
    lang: str = typer.Option("", "--lang", help="en | zh (default: both)."),
    check: bool = typer.Option(False, "--check", help="Write nothing; exit 1 when a catalogue file is stale or missing."),
    root: Path = typer.Option(LAB_ROOT, "--root"),
) -> None:
    """Convert inventory/canonical_v1/ into inventory/catalog_<lang>.yaml, deterministically (idempotent)."""
    langs = [lang] if lang else ["en", "zh"]
    for code in langs:
        if code not in ("en", "zh"):
            raise typer.BadParameter("expected en or zh", param_hint="--lang")
    stale = False
    for code in langs:
        total = len(load_canonical(code, root)["items"])
        if check:
            current = catalog_is_current(code, root)
            stale = stale or not current
            typer.echo(f"import-canonical --lang {code}: {total} point(s), {'current' if current else 'STALE'}")
        else:
            changed = write_catalog(code, root)
            typer.echo(f"import-canonical --lang {code}: {total} point(s), {'written' if changed else 'unchanged'}")
    raise typer.Exit(1 if stale else 0)


@app.command()
def coverage(
    lang: str = typer.Option(..., "--lang", help=f"Target language: {', '.join(LANGS)}."),
    as_json: bool = typer.Option(False, "--json", help="Print the report as JSON."),
    root: Path = typer.Option(LAB_ROOT, "--root"),
) -> None:
    """Canonical catalogue vs content on disk: canonical / generated / validated / approved, per level."""
    if lang not in LANGS:
        raise typer.BadParameter(f"expected one of {', '.join(LANGS)}", param_hint="--lang")
    report = coverage_report(lang, root)
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2) if as_json else render_coverage(report))


@app.command("corpus-plan")
def corpus_plan_command(
    lang: str = typer.Option("all", "--lang", help="all | en | zh."),
    as_json: bool = typer.Option(False, "--json", help="Print the full point-by-point plan as JSON."),
    root: Path = typer.Option(LAB_ROOT, "--root"),
) -> None:
    """Plan a resumable whole-corpus run without bypassing metadata review gates."""
    try:
        langs = normalize_langs(lang)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--lang") from exc
    plan = plan_corpus(langs, root)
    typer.echo(json.dumps(plan, ensure_ascii=False, indent=2) if as_json else render_corpus(plan))


@app.command("generate-corpus")
def generate_corpus_command(
    lang: str = typer.Option("all", "--lang", help="all | en | zh; all runs EN then ZH in canonical order."),
    l1: str = typer.Option("vi", "--l1", help="Learner L1 passed to each point generator."),
    provider: str = typer.Option("anthropic", "--provider", help="anthropic | openai | gemini | groq | deepseek."),
    model: str = typer.Option("claude-haiku-4-5-20251001", "--model", help="Model id for the selected provider."),
    deepseek_thinking: str = typer.Option(
        "off", "--deepseek-thinking", help="Only for DeepSeek: off | low | high."
    ),
    with_story: bool = typer.Option(False, "--with-story", help="Also generate the optional story block."),
    story_mode: str = typer.Option("everyday", "--story-mode", help="Story mode passed to Generator."),
    cost_ceiling_usd: float = typer.Option(
        1.0, "--cost-ceiling-usd",
        help=(
            "Global soft ceiling for this corpus invocation. Parallel workers already started in the same "
            "batch are allowed to finish, so a run may exceed the ceiling by at most one batch."
        ),
    ),
    max_points: int = typer.Option(
        0, "--max-points",
        help="Optional bound for one invocation; 0 means every selected point until cost ceiling.",
    ),
    sample_per_level: int = typer.Option(
        0, "--sample-per-level",
        help="Smoke mode: take the first N selected candidates from every language/level group; 0 disables.",
    ),
    workers: int = typer.Option(
        5, "--workers",
        help="Concurrent LLM calls. Default 5; use 1 for the old serial behavior. Allowed range: 1-16.",
    ),
    regenerate_existing: bool = typer.Option(
        False, "--regenerate-existing",
        help="Also regenerate existing reviewed content so the final corpus passes through one prompt/schema pipeline.",
    ),
    regenerate_note: str = typer.Option(
        "", "--regenerate-note",
        help="Required only if --regenerate-existing reaches approved points; drafts do not need a note.",
    ),
    root: Path = typer.Option(LAB_ROOT, "--root"),
) -> None:
    """Generate a resumable corpus in bounded parallel batches.

    By default only missing ready points are selected. --regenerate-existing
    also includes already-generated reviewed points, which is the final
    595-point normalization pass. Default-safe metadata is never bypassed.

    Calls run in batches of --workers. The next batch starts only after the
    previous one finishes, keeping cost accounting bounded while hiding most
    provider latency.
    """
    try:
        langs = normalize_langs(lang)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--lang") from exc
    if max_points < 0:
        raise typer.BadParameter("must be >= 0", param_hint="--max-points")
    if sample_per_level < 0:
        raise typer.BadParameter("must be >= 0", param_hint="--sample-per-level")
    if workers < 1 or workers > 16:
        raise typer.BadParameter("must be between 1 and 16", param_hint="--workers")

    initial_plan = plan_corpus(langs, root)
    candidates = generation_items(initial_plan, include_generated=regenerate_existing)
    normalized_skipped = 0
    if regenerate_existing and not regenerate_note:
        already_normalized = {
            point_id
            for lang_code in langs
            for point_id, point in load_points(lang_code, root).items()
            if matches_generation_provenance(
                point, provider=provider, model=model, prompt_version=PROMPT_VERSION_V04
            )
            and not validate_generated_point(lang_code, point, root)
        }
        before = len(candidates)
        candidates = [item for item in candidates if item[2] not in already_normalized]
        normalized_skipped = before - len(candidates)
    if sample_per_level:
        candidates = stratified_items(candidates, sample_per_level)
    if max_points:
        candidates = candidates[:max_points]
    typer.echo(render_corpus(initial_plan))
    mode = "ready + generated needing normalization" if regenerate_existing else "ready"
    typer.echo(
        f"generate-corpus: {len(candidates)} {mode} point(s) selected; "
        f"{normalized_skipped} already normalized skipped; "
        f"workers={workers}, provider={provider}, model={model}"
    )
    if not candidates:
        return

    outcomes: list[GenerateOutcome] = []

    def run_one(lang_code: str, point_id: str) -> GenerateOutcome:
        try:
            check_generation_gate(lang_code, [point_id], root)
            # One client per in-flight point: no HTTP client or response state is
            # shared across worker threads. The provider quota lock is held by
            # the outer corpus run, and the LLM cache remains content-addressed.
            with LLMClient(provider, model, deepseek_thinking=deepseek_thinking) as llm:
                generator = Generator(
                    lang=lang_code, l1=l1, llm=llm, root=root, allow_default_safe=False
                )
                return generator.generate(
                    point_id,
                    regenerate_note=regenerate_note or None,
                    with_story=with_story,
                    story_mode=story_mode,
                )
        except GenerationBlocked as exc:
            return GenerateOutcome(point_id, "blocked_metadata", reason=str(exc))
        except LLMError as exc:
            wasted_cost = exc.usage.cost_usd(model) if exc.usage is not None else None
            return GenerateOutcome(point_id, "error", reason=str(exc), cost_usd=wasted_cost)
        except Exception as exc:
            return GenerateOutcome(point_id, "error", reason=f"{type(exc).__name__}: {exc}")

    with live_lock.hold([provider], cost_ceiling_usd), ThreadPoolExecutor(
        max_workers=workers, thread_name_prefix="grammar-generate"
    ) as pool:
        cursor = 0
        while cursor < len(candidates):
            spent = sum(o.cost_usd for o in outcomes if o.cost_usd is not None)
            if spent >= cost_ceiling_usd:
                break

            batch = candidates[cursor:cursor + workers]
            batch_outcomes: list[GenerateOutcome | None] = [None] * len(batch)
            future_to_index = {
                pool.submit(run_one, lang_code, point_id): index
                for index, (lang_code, _level, point_id) in enumerate(batch)
            }
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                batch_outcomes[index] = future.result()
            outcomes.extend(outcome for outcome in batch_outcomes if outcome is not None)
            cursor += len(batch)

            batch_spent = sum(
                outcome.cost_usd for outcome in batch_outcomes
                if outcome is not None and outcome.cost_usd is not None
            )
            total_spent = sum(o.cost_usd for o in outcomes if o.cost_usd is not None)
            typer.echo(
                f"generate-corpus: batch {cursor - len(batch) + 1}-{cursor}/{len(candidates)} finished; "
                f"batch USD {batch_spent:.4f}, total USD {total_spent:.4f}"
            )

    total_cost = sum(o.cost_usd for o in outcomes if o.cost_usd is not None)
    for outcome in outcomes:
        cost = "$" + f"{outcome.cost_usd:.4f}" if outcome.cost_usd is not None else (
            "cached" if outcome.cached else "n/a"
        )
        typer.echo(f"{outcome.status:20} {outcome.point_id:48} {cost}  {outcome.reason}")
    typer.echo(
        f"generate-corpus: attempted {len(outcomes)}/{len(candidates)} selected point(s), "
        f"USD {total_cost:.4f} spent (soft ceiling USD {cost_ceiling_usd}, workers {workers}); re-run to resume"
    )

    demo_ids = set(DEMO_POINTS.values())
    if any(o.status == "written" and o.point_id in demo_ids for o in outcomes):
        changed = write_ui_fixtures(root)
        typer.echo(f"generate-corpus: UI fixtures {'refreshed' if changed else 'already current'}")

    run_id = new_run_id()
    write_step(root, run_id, "generate_corpus", {
        "run_id": run_id,
        "langs": list(langs),
        "provider": provider,
        "model": model,
        "deepseek_thinking": deepseek_thinking if provider == "deepseek" else None,
        "with_story": with_story,
        "story_mode": story_mode if with_story else None,
        "cost_ceiling_usd": cost_ceiling_usd,
        "max_points": max_points,
        "sample_per_level": sample_per_level,
        "workers": workers,
        "regenerate_existing": regenerate_existing,
        "regenerate_note": bool(regenerate_note),
        "already_normalized_skipped": normalized_skipped,
        "initial_counts": initial_plan["counts"],
        "selected": len(candidates),
        "outcomes": [
            {
                "point_id": o.point_id,
                "status": o.status,
                "reason": o.reason,
                "cost_usd": o.cost_usd,
                "cached": o.cached,
            }
            for o in outcomes
        ],
    })
    if any(o.status in {"error", "blocked_metadata"} for o in outcomes):
        raise typer.Exit(1)


@app.command("export-profile")
def export_profile_command(
    write: bool = typer.Option(False, "--write", help="Write schema/export_profile.schema.json from the internal schema."),
    root: Path = typer.Option(LAB_ROOT, "--root"),
) -> None:
    """Derive the production export-profile schema; without --write, exit 1 when the committed one has drifted."""
    if write:
        write_json(root / PROFILE_SCHEMA_PATH, derive_profile_schema(load_internal_schema(root)))
        typer.echo(f"wrote {root / PROFILE_SCHEMA_PATH}")
        raise typer.Exit(0)
    drift = profile_drift(root)
    typer.echo(f"export-profile: {drift or 'current'}")
    raise typer.Exit(1 if drift else 0)


def _git(root: Path, *args: str) -> str | None:
    import subprocess

    try:
        done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip()


@app.command("export-package")
def export_package_command(
    lang: str = typer.Option(..., "--lang", help=f"Target language: {', '.join(LANGS)}."),
    ids: str = typer.Option("", "--ids", help="Comma-separated approved point ids."),
    level: str = typer.Option("", "--level", help="Instead of --ids: every catalogue point of this level."),
    out: Path = typer.Option(..., "--out", help="New, empty output directory for the package."),
    set_version: str = typer.Option(..., "--set-version", help="Label of this batch, e.g. 2026-10-01.en.A1."),
    zip_it: bool = typer.Option(False, "--zip", help="Also write <out>.zip (deterministic) for the Admin upload."),
    with_dropped: bool = typer.Option(False, "--with-dropped", help="List the R5 ids the conversion map removes as dropped."),
    source_commit: str = typer.Option("", "--source-commit", help="Default: git HEAD of the lab checkout."),
    allow_dirty: bool = typer.Option(False, "--allow-dirty", help="Export from a dirty lab tree (recorded in the manifest)."),
    root: Path = typer.Option(LAB_ROOT, "--root"),
) -> None:
    """Build and validate the approved export package. Calls no provider; fails closed, writing nothing on error."""
    if lang not in LANGS:
        raise typer.BadParameter(f"expected one of {', '.join(LANGS)}", param_hint="--lang")
    if bool(ids) == bool(level):
        raise typer.BadParameter("give exactly one of --ids and --level")
    point_ids = [p.strip() for p in ids.split(",") if p.strip()] or select_ids(lang, level, root)
    commit = source_commit or _git(root, "rev-parse", "HEAD")
    dirty = bool(_git(root, "status", "--porcelain", "--", "."))
    if not commit:
        typer.echo("export blocked: cannot determine the source commit; pass --source-commit", err=True)
        raise typer.Exit(2)
    if dirty and not allow_dirty:
        typer.echo("export blocked: the lab tree has uncommitted changes (commit them, or pass --allow-dirty)", err=True)
        raise typer.Exit(2)
    dropped = None
    if with_dropped:
        dropped = load_dropped_r5_ids(lang, root.parent / "docs" / "grammar_lab" / "r5_conversion_map.tsv")
    try:
        result = export_package(lang, point_ids, root, out, set_version=set_version, source_commit=commit,
                                source_dirty=dirty, dropped=dropped)
    except ExportError as exc:
        for problem in exc.problems:
            typer.echo(f"export blocked: {problem}", err=True)
        raise typer.Exit(2) from exc
    if zip_it:
        package_to_zip(result.out_dir, out.with_suffix(".zip"))
    typer.echo(f"export-package --lang {lang}: {len(result.points)} point(s), package_hash {result.package_hash}, {out}")


@app.command("validate-package")
def validate_package_command(
    path: Path = typer.Argument(..., help="A package directory."),
    root: Path = typer.Option(LAB_ROOT, "--root"),
) -> None:
    """Validate a built package from its files alone. Exit 1 on any problem."""
    problems = validate_package(path, root)
    for problem in problems:
        typer.echo(problem)
    typer.echo(f"validate-package: {'OK' if not problems else f'{len(problems)} problem(s)'}")
    raise typer.Exit(1 if problems else 0)


@app.command("ui-fixtures")
def ui_fixtures(root: Path = typer.Option(LAB_ROOT, "--root")) -> None:
    """(Re)write fixtures/ui/: the EN and ZH reference points for the learner UI renderer."""
    changed = write_ui_fixtures(root)
    typer.echo(f"ui-fixtures: {'written' if changed else 'unchanged'} in {fixture_dir(root)}")


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
    ids: str = typer.Option("", "--ids", help="Comma-separated point ids, e.g. en.past_simple,en.there_is_are."),
    level: str = typer.Option("", "--level", help="Instead of --ids: every seed of this level (A1, HSK2, ...), in catalogue order."),
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
    deepseek_thinking: str = typer.Option(
        "off", "--deepseek-thinking",
        help="Only meaningful with --provider deepseek: off | low | high. Reasoning shares max_tokens "
             "with the final answer, so low/high add headroom automatically (llm_client.py docstring).",
    ),
    story_mode: str = typer.Option(
        "everyday", "--story-mode",
        help="Only meaningful with --with-story: history | everyday (VOICE.md §7). 'history' is not "
             "wired in yet -- no vetted facts source exists in this repo.",
    ),
    cost_ceiling_usd: float = typer.Option(
        1.0, "--cost-ceiling-usd",
        help="Stop starting new points once this much has been spent this run; the real cost is reported.",
    ),
    allow_default_safe_metadata: bool = typer.Option(
        False, "--allow-default-safe-metadata",
        help="Generate on points whose metadata is a default_safe placeholder (never reviewed). Off by default.",
    ),
    root: Path = typer.Option(LAB_ROOT, "--root"),
) -> None:
    """SPEC §5.1: code-generated rule_table + LLM-generated blocks + templated check items."""
    if lang not in LANGS:
        raise typer.BadParameter(f"expected one of {', '.join(LANGS)}", param_hint="--lang")
    if bool(ids) == bool(level):
        raise typer.BadParameter("give exactly one of --ids and --level")
    point_ids = [p.strip() for p in ids.split(",") if p.strip()]
    if level:
        point_ids = select_ids(lang, level, root)
        if not point_ids:
            raise typer.BadParameter(f"no catalogue points at level {level}", param_hint="--level")
    try:  # before the lock and before any client exists: nothing can be spent on a catalogue we do not trust
        check_generation_gate(lang, point_ids, root, allow_default_safe=allow_default_safe_metadata)
    except GenerationBlocked as exc:
        typer.echo(f"generate blocked: {exc}", err=True)
        raise typer.Exit(2) from exc
    outcomes = []
    with live_lock.hold([provider], cost_ceiling_usd), LLMClient(provider, model, deepseek_thinking=deepseek_thinking) as llm:
        generator = Generator(lang=lang, l1=l1, llm=llm, root=root, allow_default_safe=allow_default_safe_metadata)
        for point_id in point_ids:
            spent = sum(o.cost_usd for o in outcomes if o.cost_usd is not None)
            if spent >= cost_ceiling_usd:
                outcomes.append(GenerateOutcome(point_id, "skipped_ceiling", reason=f"cost ceiling ${cost_ceiling_usd} reached"))
                continue
            try:
                outcomes.append(generator.generate(
                    point_id, regenerate_note=regenerate_note or None, with_story=with_story, story_mode=story_mode
                ))
            except LLMError as exc:
                # A failed call can still have been billed (e.g. DeepSeek's reasoning
                # tokens on an empty-content response) -- exc.usage carries that spend.
                wasted_cost = exc.usage.cost_usd(model) if exc.usage is not None else None
                outcomes.append(GenerateOutcome(point_id, "error", reason=str(exc), cost_usd=wasted_cost))
    total_cost = sum(o.cost_usd for o in outcomes if o.cost_usd is not None)
    for outcome in outcomes:
        cost = f"${outcome.cost_usd:.4f}" if outcome.cost_usd is not None else ("cached" if outcome.cached else "n/a")
        typer.echo(f"{outcome.status:16} {outcome.point_id:40} {cost}  {outcome.reason}")
    typer.echo(
        f"generate --lang {lang}: {len(outcomes)} point(s), ${total_cost:.4f} spent this run "
        f"(ceiling ${cost_ceiling_usd}; cached calls cost nothing)"
    )
    run_id = new_run_id()
    write_step(root, run_id, "generate", {
        "run_id": run_id, "lang": lang, "provider": provider, "model": model,
        "deepseek_thinking": deepseek_thinking if provider == "deepseek" else None,
        "story_mode": story_mode if with_story else None,
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
    blind_solve: bool = typer.Option(
        False, "--blind-solve/--no-blind-solve",
        help="Also run the checks that need the other-family model (blind-solve, formula coverage, distractor "
             "plausibility, R5 corrections). Off by default since 2026-09-29.",
    ),
    blind_provider: str = typer.Option(
        "gemini", "--blind-provider", help="Only with --blind-solve; must be another family than generate's provider.",
    ),
    blind_model: str = typer.Option("gemini-3.5-flash-lite", "--blind-model"),
    evaluator_rate_limit_key: str = typer.Option(
        "gemini", "--evaluator-rate-limit-key",
        help="Shares a rate limiter with --blind-provider when the sandbox's engine and the "
             "blind-solve model draw on the same provider quota (grammar_lab/sandbox/ defaults "
             "to Gemini for both). Pass '' to disable if the sandbox uses an unmetered provider.",
    ),
    ids: str = typer.Option("", "--ids", help="Comma-separated point ids to verify (default: every point)."),
    deepseek_thinking: str = typer.Option(
        "off", "--deepseek-thinking",
        help="Only meaningful with --blind-provider deepseek: off | low | high (see generate --help).",
    ),
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
    # The app grades in its session's language; selecting it per client keeps zh checks graded as zh.
    evaluator = EvaluatorClient(evaluator_url, learning_language=lang, rate_limit_key=evaluator_rate_limit_key or None)
    if blind_solve:
        same_family = sorted({
            point_id for point_id, point in points.items()
            if str((point.get("provenance") or {}).get("model", "")).split(":")[0] == blind_provider
        })
        if same_family:
            raise typer.BadParameter(
                f"{blind_provider} generated {', '.join(same_family[:3])}{' ...' if len(same_family) > 3 else ''}; the "
                "checking model must be another family than the generating one", param_hint="--blind-provider",
            )
    blind_context = LLMClient(blind_provider, blind_model, deepseek_thinking=deepseek_thinking) if blind_solve else None
    with evaluator, (blind_context or contextlib.nullcontext()) as blind_solver:
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
                "checked_story_sentences": verify_report.checked_story_sentences,
                "checked_common_mistakes": verify_report.checked_common_mistakes,
                "checked_quick_practice": verify_report.checked_quick_practice,
                "checked_formula": verify_report.checked_formula,
                "unverified": verify_report.unverified,
                "r5_source_errors": verify_report.r5_source_errors,
            }
            verdict = "OK" if verify_report.ok else f"{len(verify_report.flags)} flag(s)"
            if verify_report.unverified:
                verdict += f", {len(verify_report.unverified)} not verifiable by the engine"
            if verify_report.r5_source_errors:
                verdict += f", {len(verify_report.r5_source_errors)} R5 source error(s) confirmed"
            typer.echo(f"{point_id:40} {verdict}")
    run_id = new_run_id()
    write_step(root, run_id, "verify", {
        "run_id": run_id, "lang": lang, "evaluator_url": evaluator_url,
        "blind_solve": blind_solve,
        "blind_provider": blind_provider if blind_solve else None, "blind_model": blind_model if blind_solve else None,
        "deepseek_thinking": deepseek_thinking if blind_solve and blind_provider == "deepseek" else None,
        "points": results,
    })
    typer.echo(f"verify --lang {lang}: {len(results)} point(s) checked")


@app.command("engine-grade")
def engine_grade_command(
    lang: str = typer.Option(..., "--lang", help=f"Target language: {', '.join(LANGS)}."),
    level: str = typer.Option(..., "--level", help="A1, B2, HSK3, ... -- the reviewed level about to go into the app."),
    evaluator_url: str = typer.Option(
        ..., "--evaluator-url",
        help="Base URL of a writing-evaluator sandbox you are allowed to operate (never production).",
    ),
    ids: str = typer.Option("", "--ids", help="Only these point ids (default: every point of the level)."),
    yes: bool = typer.Option(False, "--yes", help="Run the engine calls. Without it: print the estimate and stop."),
    cost_ceiling_usd: float = typer.Option(2.0, "--cost-ceiling-usd", help="Refuse to run when the estimate exceeds this."),
    root: Path = typer.Option(LAB_ROOT, "--root"),
) -> None:
    """Grade only common_mistakes and quick_practice with the engine, after the estimated cost is shown."""
    if lang not in LANGS:
        raise typer.BadParameter(f"expected one of {', '.join(LANGS)}", param_hint="--lang")
    wanted = level.removeprefix("HSK") if lang == "zh" else level
    points = {pid: p for pid, p in load_points(lang, root).items() if p["level"]["value"] == wanted}
    if ids:
        keep = {p.strip() for p in ids.split(",") if p.strip()}
        points = {pid: p for pid, p in points.items() if pid in keep}
    if not points:
        raise typer.BadParameter(f"no points at level {level}", param_hint="--level")
    grade_plan = engine_grade.plan(points)
    cost = f"~${grade_plan.cost_usd:.2f}" if grade_plan.cost_usd is not None else "unknown"
    typer.echo(
        f"engine-grade {lang} {level}: {grade_plan.points} point(s), {grade_plan.calls} engine call(s), "
        f"estimated cost {cost} (about {engine_grade.ENGINE_CALL_TOKENS[0]} tokens in / "
        f"{engine_grade.ENGINE_CALL_TOKENS[1]} out per call, {engine_grade.ENGINE_MODEL}; not measured)"
    )
    if not yes:
        typer.echo("estimate only; pass --yes to run")
        return
    if grade_plan.cost_usd is not None and grade_plan.cost_usd > cost_ceiling_usd:
        raise typer.BadParameter(
            f"estimate ${grade_plan.cost_usd:.2f} is over the ceiling ${cost_ceiling_usd}", param_hint="--cost-ceiling-usd",
        )
    results: dict[str, dict] = {}
    with EvaluatorClient(evaluator_url, learning_language=lang, rate_limit_key="gemini") as evaluator:
        for point_id, point in points.items():
            report = engine_grade.grade_point(point, evaluator=evaluator)
            results[point_id] = {
                "flags": [{"code": f.code, "detail": f.detail} for f in report.flags],
                "checked_common_mistakes": report.checked_common_mistakes,
                "checked_quick_practice": report.checked_quick_practice,
                "unverified": report.unverified,
            }
            verdict = "OK" if report.ok else f"{len(report.flags)} flag(s)"
            if report.unverified:
                verdict += f", {len(report.unverified)} not verifiable by the engine"
            typer.echo(f"{point_id:40} {verdict}")
    run_id = new_run_id()
    write_step(root, run_id, "verify", {
        "run_id": run_id, "lang": lang, "evaluator_url": evaluator_url, "blind_solve": False, "scope": "engine-grade",
        "estimated_calls": grade_plan.calls, "estimated_cost_usd": grade_plan.cost_usd, "points": results,
    })
    typer.echo(f"engine-grade --lang {lang}: {len(results)} point(s) graded (run {run_id})")


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
            unverified=entry.get("unverified", []),
        )
        outcome = route_point(
            point_id, validate_issue_codes=issue_codes_by_id.get(point_id, set()),
            verify_report=verify_report, threshold=threshold, gold_set_passed=gold_set_passed,
            target_lang=point.get("target_lang"),
            has_story=any(b["type"] == "story" for b in point.get("blocks", [])),
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


@app.command("review-export")
def review_export(
    lang: str = typer.Option(..., "--lang", help=f"Target language: {', '.join(LANGS)}."),
    level: str = typer.Option("", "--level", help="A1, B2, HSK3, ... (default: every level with points)."),
    root: Path = typer.Option(LAB_ROOT, "--root"),
) -> None:
    """Write grammar_lab/review/<lang>/<level>.md for review by an external model (two passes, JSONL feedback)."""
    if lang not in LANGS:
        raise typer.BadParameter(f"expected one of {', '.join(LANGS)}", param_hint="--lang")
    for label in [level] if level else levels_present(lang, root):
        path = write_review(lang, label, root, root / "review")
        typer.echo(f"wrote {path} ({path.stat().st_size:,} bytes)")


@app.command("apply-feedback")
def apply_feedback_command(
    lang: str = typer.Option(..., "--lang", help=f"Target language: {', '.join(LANGS)}."),
    level: str = typer.Option(..., "--level", help="The level the feedback files are about (A1, HSK1, ...)."),
    files: list[Path] = typer.Option(..., "--files", help="One or more JSONL feedback files (repeat the option)."),
    provider: str = typer.Option("deepseek", "--provider"),
    model: str = typer.Option("deepseek-flash", "--model"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse, de-duplicate and show the plan and estimated cost; call no model."),
    allow_approved: bool = typer.Option(False, "--allow-approved", help="Also touch approved points."),
    cost_ceiling_usd: float = typer.Option(0.5, "--cost-ceiling-usd", help="Stop regenerating once this much is spent."),
    root: Path = typer.Option(LAB_ROOT, "--root"),
) -> None:
    """Fold external-review feedback into a level: de-duplicate, regenerate the flagged blocks, validate, log."""
    if lang not in LANGS:
        raise typer.BadParameter(f"expected one of {', '.join(LANGS)}", param_hint="--lang")
    if dry_run:
        result = run_apply_feedback(lang, level, files, llm=LLMClient(provider, model), root=root, dry_run=True)
    else:
        with LLMClient(provider, model) as llm:
            result = run_apply_feedback(
                lang, level, files, llm=llm, root=root, allow_approved=allow_approved, cost_ceiling_usd=cost_ceiling_usd,
            )
    for outcome in result.outcomes:
        typer.echo(f"{outcome.status:8} {outcome.item.id:36} {outcome.item.block:22} {outcome.reason}")
    for bad in result.unparsed:
        typer.echo(f"unparsed {bad['where']}: {bad['reason']}")
    counts: dict[str, int] = {}
    for outcome in result.outcomes:
        counts[outcome.status] = counts.get(outcome.status, 0) + 1
    label = "estimated" if dry_run else "spent"
    typer.echo(f"apply-feedback {lang} {level}: {counts}, {len(result.unparsed)} unparsed line(s), "
               f"{result.calls} model call(s), {label} ~${result.cost_usd:.4f}")
    if not dry_run:
        typer.echo(f"log: {review_path(lang, level, root / 'review').with_suffix('.applied.json')}")


@app.command("feedback-stats")
def feedback_stats_command(
    files: list[Path] = typer.Option(..., "--files", help="JSONL feedback files."),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Group feedback (after de-duplication) by type: knowledge / scope / wording / format."""
    items, unparsed = parse_files(files)
    items, merged = dedupe(items)
    stats = feedback_stats(items)
    stats["merged_duplicates"] = len(merged)
    stats["unparsed"] = len(unparsed)
    if as_json:
        typer.echo(json.dumps(stats, ensure_ascii=False, indent=2))
        return
    typer.echo(f"{stats['total']} item(s), {stats['merged_duplicates']} duplicate(s) merged, {stats['unparsed']} unparsed")
    for title in ("by_type", "by_severity", "by_block"):
        typer.echo(f"{title}: " + ", ".join(f"{k}={v}" for k, v in stats[title].items()))


@app.command()
def preview(
    root: Path = typer.Option(LAB_ROOT, "--root"),
    out: Path = typer.Option(DEFAULT_PREVIEW_DIR, "--out", help="Where index.html is written (gitignored)."),
    serve: bool = typer.Option(False, "--serve", help="Serve the preview read-only on 127.0.0.1 after building it."),
    port: int = typer.Option(8031, "--port"),
) -> None:
    """Internal content-review preview of every schema v0.4 point -- not a learner UI."""
    path = write_preview(root, out)
    typer.echo(f"wrote {path}")
    if serve:
        typer.echo(f"serving http://127.0.0.1:{port}/ (Ctrl+C to stop)")
        serve_preview(out, port)


if __name__ == "__main__":
    app()
