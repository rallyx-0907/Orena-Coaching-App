"""Internal content-review preview for schema v0.4 points (GRAMMAR_CONTENT_CONTRACT.md).

Renders every v0.4 point the way the contract describes -- formula slots coloured by role,
the timeline/word_order/morphology illustration, examples highlighted with the same palette,
two-column compare, wrong/right, clickable quick practice -- plus each point's validate
issues and latest verify flags. It is for a human reviewing *content*, not a learner UI:
the app's learner surfaces follow the Claude Design project (D-067), which this never
touches.

One self-contained HTML file (template in grammar_lab/preview/template.html, data inlined),
served read-only on 127.0.0.1 by ``grammar_lab preview --serve``.
"""

from __future__ import annotations

import functools
import http.server
import json
import time
from pathlib import Path
from typing import Any

from grammar_lab.pipeline.content_store import load_points
from grammar_lab.pipeline.validate import LAB_ROOT, LANGS, validate_lang

TEMPLATE_PATH = LAB_ROOT / "preview" / "template.html"  # a code asset: always this checkout's, whatever --root is
DEFAULT_OUT_DIR = LAB_ROOT / "preview" / "out"
DATA_PLACEHOLDER = "__DATA__"


def _latest_verify_by_point(root: Path, lang: str) -> dict[str, dict[str, Any]]:
    """point id -> {run_id, flags} from the newest verify run that checked that point, so a
    run over a few regenerated points does not hide the others' earlier results."""
    reports = root / "reports"
    runs = sorted(reports.glob("*/verify.json")) if reports.is_dir() else []
    latest: dict[str, dict[str, Any]] = {}
    for path in reversed(runs):  # run ids sort chronologically
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("lang") != lang:
            continue
        for point_id, entry in data.get("points", {}).items():
            if point_id not in latest and not entry.get("skipped"):
                latest[point_id] = {"run_id": data["run_id"], "flags": entry.get("flags", [])}
    return latest


def load_preview_data(root: Path = LAB_ROOT) -> dict[str, Any]:
    langs: dict[str, Any] = {}
    for lang in LANGS:
        if not (root / "content" / lang).is_dir():
            continue
        report = validate_lang(lang, root)
        issues_by_id: dict[str, list[dict[str, str]]] = {}
        for issue in report.issues:
            point_id = report.point_files.get(issue.file)
            if point_id:
                issues_by_id.setdefault(point_id, []).append(
                    {"code": issue.code, "path": issue.path, "message": issue.message}
                )
        verify = _latest_verify_by_point(root, lang)
        entries, skipped = [], []
        for point_id, point in sorted(load_points(lang, root).items()):
            if point.get("schema_version") != "0.4" or "header" not in point:
                skipped.append(point_id)
                continue
            entries.append({
                "point": point,
                "check": {"validate": issues_by_id.get(point_id, []), "verify": verify.get(point_id)},
            })
        langs[lang] = {"points": entries, "skipped": skipped}
    return {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "langs": langs}


def build_html(data: dict[str, Any], template: str) -> str:
    # Inlined in <script type="application/json">: "</" must not close the script element early.
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return template.replace(DATA_PLACEHOLDER, payload)


def write_preview(root: Path = LAB_ROOT, out_dir: Path = DEFAULT_OUT_DIR) -> Path:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "index.html"
    path.write_text(build_html(load_preview_data(root), template), encoding="utf-8")
    return path


def serve(out_dir: Path, port: int) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out_dir))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        server.serve_forever()
