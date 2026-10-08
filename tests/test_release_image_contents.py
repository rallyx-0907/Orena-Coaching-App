"""The release image holds every file the learner UI asks the server for.

:8000 runs the image with no source mounted (D-144), so a file the code serves from the repository but the
Dockerfile does not copy is a 404 in production while a mounted sandbox looks fine. Found on the 6d7ebff0 release:
/orena-brand/logo/*.svg answered 404 and the welcome screen drew an empty logo.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRAND_URL = re.compile(r"/orena-brand/([A-Za-z0-9_./-]+\.[a-z0-9]+)")


def _copied_sources() -> list[str]:
    sources = []
    for line in (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "COPY" and not parts[1].startswith("--"):
            sources.extend(part.rstrip("/") for part in parts[1:-1])
    return sources


def _in_image(relative: str, sources: list[str]) -> bool:
    return any(relative == source or relative.startswith(source + "/") for source in sources)


def _referenced_brand_files() -> set[str]:
    found = set()
    for folder in ("static", "templates"):
        for path in (ROOT / folder).rglob("*"):
            if path.suffix in {".js", ".mjs", ".html", ".css"}:
                found.update(BRAND_URL.findall(path.read_text(encoding="utf-8", errors="ignore")))
    return found


def test_every_brand_file_a_page_references_is_in_the_image():
    sources = _copied_sources()
    referenced = _referenced_brand_files()
    assert referenced, "the learner UI references its brand marks under /orena-brand/"
    for name in sorted(referenced):
        relative = f"assets/brand/orena/{name}"
        assert (ROOT / relative).is_file(), f"{relative} is referenced but does not exist"
        assert _in_image(relative, sources), f"{relative} is referenced but the Dockerfile does not copy it"


def test_the_server_roots_the_learner_ui_reads_are_in_the_image():
    sources = _copied_sources()
    for relative in ("app.py", "auth_support.py", "writing_coach", "templates/orena/index.html", "static/orena",
                     "migrations", "alembic.ini", "scripts/product_migration_pack.py"):
        assert _in_image(relative, sources), f"{relative} is not in the image"
