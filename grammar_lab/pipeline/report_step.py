"""``report`` step (SPEC §5.5): status counts, flag rates, API cost, review time.

Reads whatever ``generate``/``verify``/``route`` wrote to ``reports/<run_id>/``
for the run being reported on, plus the *current* state of ``content/<lang>/``
for status counts and review time (those reflect the latest state on disk,
not one run's snapshot -- a human may have approved points since).
"""

from __future__ import annotations

import html
from collections import Counter
from pathlib import Path
from typing import Any

from grammar_lab.pipeline.content_store import load_points
from grammar_lab.pipeline.run_context import read_step


def build_report(root: Path, run_id: str, lang: str) -> dict[str, Any]:
    points = load_points(lang, root)
    status_counts = Counter(point["status"] for point in points.values())

    generate_data = read_step(root, run_id, "generate")
    verify_data = read_step(root, run_id, "verify")
    route_data = read_step(root, run_id, "route")

    total_cost = None
    if generate_data:
        costs = [o["cost_usd"] for o in generate_data.get("outcomes", []) if o.get("cost_usd") is not None]
        if costs:
            total_cost = round(sum(costs), 4)

    flag_rate: dict[str, float] = {}
    if verify_data:
        per_point = verify_data.get("points", {})
        n = len(per_point) or 1
        code_counts: Counter[str] = Counter()
        for entry in per_point.values():
            for flag in entry.get("flags", []):
                code_counts[flag["code"]] += 1
        flag_rate = {code: round(count / n, 4) for code, count in code_counts.items()}

    route_status_counts: dict[str, int] = {}
    if route_data:
        route_status_counts = dict(Counter(entry["status"] for entry in route_data.get("points", {}).values()))

    review_seconds = [
        point["review"]["seconds"] for point in points.values()
        if point.get("review") and point["review"].get("seconds") is not None
    ]
    avg_review_seconds = round(sum(review_seconds) / len(review_seconds), 1) if review_seconds else None

    return {
        "run_id": run_id,
        "lang": lang,
        "generated_at_run_id": run_id,
        "status_counts": dict(status_counts),
        "route_status_counts": route_status_counts,
        "verify_flag_rate": flag_rate,
        "api_cost_usd": total_cost,
        "avg_review_seconds": avg_review_seconds,
        "points_checked_by_verify": len(verify_data.get("points", {})) if verify_data else 0,
    }


def render_html(report: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape(str(value))

    def rows(mapping: dict[str, Any]) -> str:
        if not mapping:
            return "<tr><td colspan=2><em>none</em></td></tr>"
        return "".join(f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>" for k, v in sorted(mapping.items()))

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Grammar Lab report {esc(report['run_id'])} ({esc(report['lang'])})</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
table {{ border-collapse: collapse; margin-bottom: 2rem; }}
td, th {{ border: 1px solid #ccc; padding: 4px 10px; text-align: left; }}
h2 {{ margin-top: 2rem; }}
</style></head>
<body>
<h1>Grammar Lab report</h1>
<p>run <code>{esc(report['run_id'])}</code> &middot; lang <code>{esc(report['lang'])}</code></p>

<h2>Status (current content/)</h2>
<table>{rows(report['status_counts'])}</table>

<h2>Route outcome (this run)</h2>
<table>{rows(report['route_status_counts'])}</table>

<h2>Verify flag rate (fraction of checked points, this run)</h2>
<table>{rows(report['verify_flag_rate'])}</table>

<h2>Cost and review time</h2>
<table>
<tr><td>API cost (this run)</td><td>{esc(report['api_cost_usd']) if report['api_cost_usd'] is not None else 'n/a'}</td></tr>
<tr><td>Average review time (seconds, all reviewed points)</td><td>{esc(report['avg_review_seconds']) if report['avg_review_seconds'] is not None else 'n/a (nothing reviewed yet)'}</td></tr>
<tr><td>Points checked by verify (this run)</td><td>{esc(report['points_checked_by_verify'])}</td></tr>
</table>
</body></html>
"""
