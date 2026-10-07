from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import grammar_lab.pipeline.generate as generate_module
from grammar_lab.pipeline.content_store import load_point
from grammar_lab.pipeline.generate import Generator
from grammar_lab.pipeline.jsonio import read_yaml
from grammar_lab.pipeline.llm_client import LLMClient, LLMResult
from grammar_lab.pipeline.seed import apply_seed
from grammar_lab.pipeline.validate import FUNCTIONS_PATH, LAB_ROOT


class RecordingCacheClient(LLMClient):
    """Cache-only client that records the first full v0.4 lesson candidate."""

    def __init__(self, provider: str, model: str) -> None:
        super().__init__(
            provider,
            model,
            cache_only=True,
            deepseek_empty_attempts=1,
        )
        self.full_candidate: dict[str, Any] | None = None

    def complete(self, **kwargs: Any) -> LLMResult:
        result = super().complete(**kwargs)
        if kwargs.get("schema_name") == "grammar_point_v04" and self.full_candidate is None:
            self.full_candidate = copy.deepcopy(result.data)
        return result


def _metadata_snapshot(point: dict[str, Any] | None) -> dict[str, Any] | None:
    if point is None:
        return None
    keys = (
        "schema_version",
        "id",
        "target_lang",
        "level",
        "function",
        "point_type",
        "header",
        "prereqs",
        "contrasts",
        "error_tags",
        "sequence",
        "aliases",
        "source_refs",
        "source_anchors",
    )
    return {key: copy.deepcopy(point.get(key)) for key in keys if key in point}


def build_bundle(
    *,
    lang: str,
    provider: str,
    model: str,
    report_path: Path,
    root: Path,
) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    point_entries = report.get("points") or {}
    unresolved_ids = [
        point_id
        for point_id, entry in point_entries.items()
        if isinstance(entry, dict)
        and isinstance(entry.get("cache_probe"), dict)
        and entry["cache_probe"].get("status") == "error"
    ]

    functions_data = read_yaml(root / FUNCTIONS_PATH)
    functions = {
        item["id"]: item
        for item in (functions_data or {}).get("functions", [])
        if isinstance(item, dict) and item.get("id")
    }

    # Export must never mutate corpus files or the function registry, even if a
    # cached candidate unexpectedly validates under newer code.
    original_save = generate_module.save_point
    original_register = generate_module.register_realization
    generate_module.save_point = lambda *args, **kwargs: None
    generate_module.register_realization = lambda *args, **kwargs: False

    exported: list[dict[str, Any]] = []
    try:
        for point_id in unresolved_ids:
            entry = point_entries[point_id]
            seeded = apply_seed(load_point(lang, point_id, root), lang, point_id, root)
            client = RecordingCacheClient(provider, model)
            try:
                generator = Generator(
                    lang=lang,
                    l1="vi",
                    llm=client,
                    root=root,
                    max_full_attempts=1,
                    paid_repairs=False,
                )
                outcome = generator.generate(point_id)
                replay_reason = outcome.reason
                replay_status = outcome.status
            except Exception as exc:  # export evidence; never hide an exception
                replay_status = "exception"
                replay_reason = f"{type(exc).__name__}: {exc}"
            finally:
                client.close()

            function_id = seeded.get("function") if isinstance(seeded, dict) else None
            exported.append(
                {
                    "point_id": point_id,
                    "category": (entry.get("cache_probe") or {}).get("category"),
                    "stabilization_reason": (entry.get("cache_probe") or {}).get("reason"),
                    "deferred": bool(entry.get("deferred")),
                    "replay_status": replay_status,
                    "replay_reason": replay_reason,
                    "metadata": _metadata_snapshot(seeded),
                    "function": copy.deepcopy(functions.get(function_id)) if function_id else None,
                    "candidate": client.full_candidate,
                }
            )
    finally:
        generate_module.save_point = original_save
        generate_module.register_realization = original_register

    counts: dict[str, int] = {}
    for item in exported:
        key = str(item.get("category") or "unknown")
        counts[key] = counts.get(key, 0) + 1

    return {
        "format": "orena.grammar-exceptions.v1",
        "lang": lang,
        "provider": provider,
        "model": model,
        "source_report": str(report_path),
        "provider_calls_authorized": False,
        "exception_count": len(exported),
        "by_category": dict(sorted(counts.items())),
        "points": exported,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export unresolved Grammar Lab cached candidates for offline final review. Never calls a provider."
    )
    parser.add_argument("--lang", default="zh")
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--model", default="deepseek-flash")
    parser.add_argument("--root", type=Path, default=LAB_ROOT)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    report = args.report or (args.root / ".cache" / "stabilization" / f"{args.lang}.json")
    out = args.out or (args.root / ".cache" / "stabilization" / f"{args.lang}.exceptions.json")
    bundle = build_bundle(
        lang=args.lang,
        provider=args.provider,
        model=args.model,
        report_path=report,
        root=args.root,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    cached = sum(1 for item in bundle["points"] if item.get("candidate") is not None)
    missing = bundle["exception_count"] - cached
    print(
        f"exported {bundle['exception_count']} exception(s): {cached} cached candidate(s), "
        f"{missing} cache miss(es); provider calls authorized: NO"
    )
    print(f"bundle: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
