"""Rehearse the real import -> attest -> accept -> publish path with Grammar Lab export packages, on a throwaway
PostgreSQL migrated to head (GRAMMAR_CONTENT_STORE.md rev 3a sections 5-9; migration 20261008_0030).

The packages are produced by Grammar Lab's own exporter (`python -m grammar_lab.pipeline.cli export-package ... --zip`)
from the approved corpus; this script reads the zips you pass and copies nothing into the application source. It
drives the real routers (`/api/admin/grammar/*`, `/api/grammar/v1/*`) on a bare app over the real store, with the
admin guard and the session language as the only seams. Refuses any database that is not clearly throwaway.

    python scripts/rehearse_grammar_corpus_import.py "$REHEARSAL_URL" en.zip zh.zip [--report out.md]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from alembic import command  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from rehearse_learner_records_schema import refuse_unless_empty, refuse_unless_throwaway  # noqa: E402
from writing_coach import grammar_admin_api, grammar_api  # noqa: E402
from writing_coach.persistence.grammar_store_repository import GrammarStoreRepository  # noqa: E402
from writing_coach.persistence.runtime import _runtime_alembic_config  # noqa: E402

ORIGIN = {"origin": "http://testserver"}
RESULTS: list[tuple[str, bool, str]] = []
TIMINGS: list[tuple[str, float]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)


def timed(label: str, call):
    start = time.monotonic()
    value = call()
    TIMINGS.append((label, round(time.monotonic() - start, 3)))
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url")
    parser.add_argument("packages", nargs="+", type=Path)
    parser.add_argument("--report", default="")
    args = parser.parse_args()
    refuse_unless_throwaway(args.url)
    engine = create_engine(args.url, future=True)
    refuse_unless_empty(engine)
    cfg = _runtime_alembic_config()
    cfg.set_main_option("sqlalchemy.url", args.url.replace("%", "%%"))
    timed("upgrade empty -> head", lambda: command.upgrade(cfg, "head"))
    with engine.connect() as connection:
        head = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
        server = connection.execute(text("SHOW server_version")).scalar()
    check("database migrated to the chain head 20261008_0030", head == "20261008_0030", f"{head}; PostgreSQL {server}")

    store = GrammarStoreRepository(engine)
    language = {"value": "en"}
    grammar_admin_api.configure_grammar_admin(admin_guard=lambda _r: {"email": "rehearsal-admin"}, store=store)
    grammar_api.configure_grammar_api(store, None, language=lambda: language["value"])
    app = FastAPI()
    app.include_router(grammar_admin_api.router)
    app.include_router(grammar_api.router)
    client = TestClient(app)

    for path in args.packages:
        data = path.read_bytes()
        upload = {"upload": (path.name, data, "application/zip")}
        dry = timed(f"{path.name}: dry run", lambda upload=upload: client.post(
            "/api/admin/grammar/imports/validate", headers=ORIGIN, files=upload))
        report = dry.json()
        lang = report.get("language")
        check(f"{path.name}: dry run validates clean (closed profile, cross checks, r5_map, labels) and writes nothing",
              dry.status_code == 200 and report.get("ok") and not client.get("/api/admin/grammar/imports").json()[
                  "batches"][len(args.packages):], f"lang={lang} points={report.get('point_count')} "
                                                   f"problems={report.get('problem_count')}")
        committed = timed(f"{path.name}: commit (one transaction)", lambda upload=upload, report=report: client.post(
            "/api/admin/grammar/imports", headers=ORIGIN, files=upload,
            data={"package_hash": report["package_hash"], "rights_basis": "orena_original",
                  "rights_attestation": "Rehearsal: Grammar Lab approved corpus, catalogue codes only."}))
        batch = committed.json().get("batch", {})
        check(f"{path.name}: committed as one imported batch, every point new, rights cleared by the batch attestation",
              committed.status_code == 201 and batch.get("counts", {}).get("new") == report.get("point_count"),
              f"counts={batch.get('counts')}")
        again = client.post("/api/admin/grammar/imports", headers=ORIGIN, files=upload,
                            data={"package_hash": report["package_hash"]})
        check(f"{path.name}: re-upload answers already_imported", again.status_code == 200 and again.json()[
            "already_imported"])
        points = client.get("/api/admin/grammar/points", params={"language": lang, "limit": 1000}).json()["points"]

        def accept_all(points=points):
            items = []
            for point in points:
                version = client.get(f"/api/admin/grammar/points/{point['id']}").json()["versions"][0]
                answer = client.post(f"/api/admin/grammar/versions/{version['id']}/review", headers=ORIGIN,
                                     json={"decision": "accept"})
                assert answer.status_code == 200, answer.text
                items.append({"point_id": point["id"], "version_id": version["id"]})
            return items

        items = timed(f"{path.name}: accept {len(points)} versions (one request each)", accept_all)
        published = timed(f"{path.name}: bulk publish {len(items)} points (one transaction)", lambda items=items: client.post(
            "/api/admin/grammar/publish", headers=ORIGIN, json={"items": items, "attested": True}))
        check(f"{path.name}: bulk publish of the whole language is accepted (references resolve in the result)",
              published.status_code == 200 and len(published.json().get("published", [])) == len(items),
              published.text[:300] if published.status_code != 200 else f"{len(items)} published")
        language["value"] = lang
        catalog = client.get("/api/grammar/v1/points")
        body = catalog.json()
        check(f"{path.name}: learner catalogue serves every published point with its function labels and levels",
              catalog.status_code == 200 and len(body["points"]) == len(items) and all(
                  f["title"] for f in body["functions"]) and body["levels"],
              f"points={len(body['points'])} functions={len(body['functions'])} levels="
              f"{[lv['value'] for lv in body['levels']]} etag={catalog.headers.get('etag')}")
        sample = body["points"][0]["id"]
        point = client.get(f"/api/grammar/v1/points/{sample}").json()
        check(f"{path.name}: a point body is served whitelisted (no source_refs) with its content hash",
              point["point"]["id"] == sample and "source_refs" not in point["point"] and len(point["content_hash"]) == 64)
        rows = client.get("/api/admin/grammar/r5-map", params={"language": lang}).json()["rows"]
        primary = next((r for r in rows if r["is_primary"]), None)
        dropped = next((r for r in rows if r["disposition"] == "dropped"), None)
        if primary:
            resolved = client.get(f"/api/grammar/v1/points/{primary['r5_id']}").json()
            check(f"{path.name}: an old R5 id redirects to its primary point", resolved.get("redirect") ==
                  primary["point_id"], f"{primary['r5_id']} -> {resolved}")
            composite = client.get(f"/api/grammar/v1/points/{lang}:grammar:v2:{primary['r5_id']}").json()
            check(f"{path.name}: the stored composite key resolves the same way", composite.get("redirect") ==
                  primary["point_id"])
        if dropped:
            check(f"{path.name}: a dropped R5 id answers dropped", client.get(
                f"/api/grammar/v1/points/{dropped['r5_id']}").json().get("dropped") is True, dropped["r5_id"])
        coverage = client.get("/api/admin/grammar/coverage", params={"language": lang}).json()
        check(f"{path.name}: R5 coverage (ids with neither a published primary nor a drop)", True,
              f"r5_rows={len(rows)} unresolved={len(coverage['unresolved'])} complete={coverage['complete']}")
        tag = next((t for p in body["points"] for t in p["error_tags"]), None)
        if tag:
            hits = client.get("/api/grammar/v1/by-error", params={"error_tag": tag}).json()["points"]
            check(f"{path.name}: by-error finds published points for a real error tag", bool(hits), f"{tag}: {len(hits)}")

    grammar_admin_api.configure_grammar_admin(admin_guard=None)
    grammar_api.configure_grammar_api(None)
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)} PASS, {len(failed)} FAIL")
    for label, seconds in TIMINGS:
        print(f"  {seconds:8.3f} s  {label}")
    if args.report:
        lines = ["| # | Check | Result | Detail |", "| --- | --- | --- | --- |"]
        lines += [f"| {i} | {label} | {'PASS' if ok else 'FAIL'} | {detail.replace('|', '/')} |"
                  for i, (label, ok, detail) in enumerate(RESULTS, 1)]
        lines += ["", "| Step | Seconds |", "| --- | --- |"] + [f"| {label} | {s} |" for label, s in TIMINGS]
        Path(args.report).write_text(json.dumps({"server": server}) + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
