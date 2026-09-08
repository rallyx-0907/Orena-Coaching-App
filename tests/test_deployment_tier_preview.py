"""Preview is a deployment tier, not a relaxed production.

Two variables answer two different questions, and conflating them is exactly how
unreviewed content reaches real learners:

    APP_ENV                runtime and security posture
    ORENA_DEPLOYMENT_TIER  which catalog content may be exposed at all

A preview deployment runs APP_ENV=production on purpose, so it exercises real
HTTPS, real Google auth and real PostgreSQL. What makes it a preview is the
tier, and the tier decides visibility SERVER-SIDE. Hiding a card in JavaScript
is not access control: the lesson endpoint is reachable directly.

Production tier must fail closed — not "hidden", but absent from the process.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from writing_coach.core.deployment import (
    DEPLOYMENT_TIER_ENV,
    TIER_PREVIEW,
    TIER_PRODUCTION,
    resolve_deployment_tier,
)
from writing_coach.listening_catalog import (
    CATALOG_MANIFEST,
    load_catalog,
    preview_catalog_enabled,
)

ROOT = Path(__file__).resolve().parents[1]
PILOT_SOURCE_LIST = ROOT / "writing_coach/content/listening_sources_en_pilot_dialogue.csv"


# --- the tier itself ---------------------------------------------------------

def test_the_tier_defaults_to_production_when_unset() -> None:
    """A deployment that forgets the variable shows reviewed content only."""

    assert resolve_deployment_tier({}) == TIER_PRODUCTION
    assert resolve_deployment_tier({DEPLOYMENT_TIER_ENV: ""}) == TIER_PRODUCTION
    assert resolve_deployment_tier({DEPLOYMENT_TIER_ENV: "   "}) == TIER_PRODUCTION


def test_an_unrecognised_tier_is_refused_not_guessed() -> None:
    """A typo must not silently decide what learners can see, either way."""

    for bad in ("prod", "staging", "dev", "PREVIEW-", "true"):
        with pytest.raises(RuntimeError, match=DEPLOYMENT_TIER_ENV):
            resolve_deployment_tier({DEPLOYMENT_TIER_ENV: bad})


def test_the_tier_is_case_and_whitespace_tolerant() -> None:
    assert resolve_deployment_tier({DEPLOYMENT_TIER_ENV: " Preview "}) == TIER_PREVIEW
    assert resolve_deployment_tier({DEPLOYMENT_TIER_ENV: "PRODUCTION"}) == TIER_PRODUCTION


def test_app_env_does_not_decide_the_tier() -> None:
    """The whole point: production security, preview content."""

    env = {"APP_ENV": "production", DEPLOYMENT_TIER_ENV: TIER_PREVIEW}
    assert resolve_deployment_tier(env) == TIER_PREVIEW
    assert preview_catalog_enabled(env) is True

    # And development alone does not turn preview content on.
    assert preview_catalog_enabled({"APP_ENV": "development"}) is False


def test_the_deployment_config_carries_the_tier() -> None:
    from writing_coach.core.deployment import resolve_deployment_config

    base = {
        "APP_ENV": "production",
        "PUBLIC_BASE_URL": "https://preview.example.org",
        "GOOGLE_CLIENT_ID": "id", "GOOGLE_CLIENT_SECRET": "secret",
        "SESSION_SECRET": "s" * 32,
    }
    assert resolve_deployment_config(base).preview is False
    preview = resolve_deployment_config({**base, DEPLOYMENT_TIER_ENV: TIER_PREVIEW})
    assert preview.preview is True
    # Preview does NOT relax production security posture.
    assert preview.production is True
    assert preview.cookie_secure is True
    assert preview.auth_enabled is True


# --- the catalog overlay -----------------------------------------------------

def preview_artifact(tmp_path: Path) -> Path:
    """A real preview artifact, built through the real generator."""

    from writing_coach.listening_source_import import write_manifest

    source_id = "youtube:previewvid01"
    manifest = {
        "schema_version": 1,
        "sources": [{
            "source_media_id": source_id,
            "source_url": "https://www.youtube.com/watch?v=previewvid01",
            "source_provider": "youtube", "source_type": "external-video",
            "source_title": "A preview scene", "source_creator": "Preview Channel",
            "language": "en", "duration_ms": 60000,
            "playback": {"provider": "youtube", "kind": "embed",
                         "url": "https://www.youtube-nocookie.com/embed/previewvid01"},
            "poster_url": "https://i.ytimg.com/vi/previewvid01/hqdefault.jpg",
            "rights": {"license_name": "Provider terms (development candidate)",
                       "license_url": "https://www.youtube.com/t/terms",
                       "provenance_url": "https://www.youtube.com/watch?v=previewvid01",
                       "allowed_usage_type": "development-embed-only",
                       "review_status": "rights_review"},
            "segments": [
                {"segment_id": f"{source_id}:{i:03d}", "order": i,
                 "start_ms": i * 5000, "end_ms": (i + 1) * 5000,
                 "original_text": f"A spoken line number {i}."}
                for i in range(8)
            ],
            "transcript": {"origin": "generated_asr", "revision": 1, "language": "en",
                           "quality_state": "generated_unreviewed",
                           "provider": "supadata", "model": ""},
        }],
        "lessons": [{
            "lesson_id": "preview-en-scene-001", "source_media_id": source_id,
            "excerpt_start_ms": 0, "excerpt_end_ms": 40000,
            "title": "A preview scene", "description": "Preview candidate.",
            "topic": "movie", "subtopics": ["movie"], "tags": ["dev-candidate"],
            "estimated_level": "B1", "reviewed_level": None,
            "level_evidence": {"source": "importer-heuristic-v1", "confidence": "low",
                               "review_note": "not reviewed"},
            "available_modes": ["listen", "dictation", "shadowing"],
            "status": "DEV_CANDIDATE", "curation_state": "proposed",
            "artwork": "movie", "vocabulary": [], "sections": ["new"],
        }],
    }
    path = tmp_path / "listening_catalog.preview.json"
    # A preview artifact names its own inputs, like every generated catalog.
    write_manifest(manifest, path, source_lists=[PILOT_SOURCE_LIST])
    return path


def test_production_tier_never_loads_the_preview_artifact(tmp_path) -> None:
    """Fail closed: absent from the process, not merely filtered out."""

    path = preview_artifact(tmp_path)
    _sources, lessons = load_catalog(
        base_path=CATALOG_MANIFEST, dev_path=tmp_path / "absent.json",
        env={"APP_ENV": "production"}, preview_path=path)

    assert "preview-en-scene-001" not in {lesson.lesson_id for lesson in lessons}

    from writing_coach.listening_catalog import PREVIEW_LESSON_IDS
    assert PREVIEW_LESSON_IDS == frozenset()


def test_preview_tier_loads_it_and_marks_it_as_preview(tmp_path) -> None:
    path = preview_artifact(tmp_path)
    _sources, lessons = load_catalog(
        base_path=CATALOG_MANIFEST, dev_path=tmp_path / "absent.json",
        env={"APP_ENV": "production", DEPLOYMENT_TIER_ENV: TIER_PREVIEW},
        preview_path=path)

    ids = {lesson.lesson_id for lesson in lessons}
    assert "preview-en-scene-001" in ids

    import writing_coach.listening_catalog as catalog
    assert catalog.PREVIEW_LESSON_IDS == frozenset({"preview-en-scene-001"})

    lesson = next(item for item in lessons if item.lesson_id == "preview-en-scene-001")
    # Preview content is not relabelled to get itself displayed.
    assert lesson.content_status == "DEV_CANDIDATE"
    assert lesson.curation_state == "proposed"
    assert lesson.reviewed_level is None
    assert lesson.source.rights_review_status == "rights_review"
    # It uses the same model as everything else - no second Listening type.
    assert lesson.media_object.transcript is not None
    assert lesson.source.transcript_origin == "generated_asr"
    assert lesson.source.transcript_quality_state == "generated_unreviewed"


def test_a_tampered_preview_artifact_is_refused(tmp_path) -> None:
    path = preview_artifact(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["lessons"][0]["title"] = "Edited by hand"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="rejected"):
        load_catalog(base_path=CATALOG_MANIFEST, dev_path=tmp_path / "absent.json",
                     env={"APP_ENV": "production", DEPLOYMENT_TIER_ENV: TIER_PREVIEW},
                     preview_path=path)


def test_the_preview_overlay_cannot_redefine_reviewed_content(tmp_path) -> None:
    """An overlay may only ADD. Reviewed content is never overwritten."""

    from writing_coach.listening_source_import import write_manifest

    base_sources, base_lessons = load_catalog(env={})
    victim = base_lessons[0]

    payload = json.loads(preview_artifact(tmp_path).read_text(encoding="utf-8"))
    payload["lessons"][0]["lesson_id"] = victim.lesson_id
    payload["lessons"][0]["title"] = "Hijacked"
    path = tmp_path / "hijack.json"
    write_manifest({"schema_version": 1, "sources": payload["sources"],
                    "lessons": payload["lessons"]}, path,
                   source_lists=[PILOT_SOURCE_LIST])

    _sources, lessons = load_catalog(
        base_path=CATALOG_MANIFEST, dev_path=tmp_path / "absent.json",
        env={"APP_ENV": "production", DEPLOYMENT_TIER_ENV: TIER_PREVIEW},
        preview_path=path)

    kept = next(item for item in lessons if item.lesson_id == victim.lesson_id)
    assert kept.media_object.asset.title == victim.media_object.asset.title
    assert kept.media_object.asset.title != "Hijacked"


def test_an_artifact_that_names_no_inputs_is_refused(tmp_path) -> None:
    """Provenance is required even when WHICH inputs are expected is relaxed."""

    from writing_coach.listening_dev_artifact import verify_manifest_integrity
    from writing_coach.listening_source_import import write_manifest

    path = tmp_path / "anonymous.json"
    payload = json.loads(preview_artifact(tmp_path).read_text(encoding="utf-8"))
    write_manifest({"schema_version": 1, "sources": payload["sources"],
                    "lessons": payload["lessons"]}, path)

    problem = verify_manifest_integrity(
        json.loads(path.read_text(encoding="utf-8")), expected_source_lists=())
    assert "records no source lists" in problem


# --- authorization, server-side ----------------------------------------------

def install_preview_lesson(monkeypatch, tmp_path):
    """Load a preview lesson into the live catalog, as a preview deployment does."""

    import writing_coach.listening_catalog as catalog

    path = preview_artifact(tmp_path)
    sources, lessons = load_catalog(
        base_path=CATALOG_MANIFEST, dev_path=tmp_path / "absent.json",
        env={"APP_ENV": "production", DEPLOYMENT_TIER_ENV: TIER_PREVIEW},
        preview_path=path)
    monkeypatch.setattr(catalog, "CATALOG", lessons)
    monkeypatch.setattr(catalog, "CATALOG_SOURCES", sources)
    monkeypatch.setattr(catalog, "PREVIEW_LESSON_IDS", frozenset({"preview-en-scene-001"}))
    return "preview-en-scene-001"


def client():
    from fastapi.testclient import TestClient
    import app as orena_app
    return TestClient(orena_app.app)


def test_production_tier_cannot_retrieve_a_preview_lesson(monkeypatch, tmp_path) -> None:
    """Even if the lesson is somehow in memory, production tier refuses it."""

    lesson_id = install_preview_lesson(monkeypatch, tmp_path)
    monkeypatch.delenv(DEPLOYMENT_TIER_ENV, raising=False)

    response = client().get(f"/api/listening/library/{lesson_id}")
    assert response.status_code == 404, "production tier must not serve preview content"

    listed = client().get("/api/listening/library").json()
    assert lesson_id not in {item["lesson_id"] for item in listed["items"]}


def test_preview_tier_refuses_an_unauthorized_caller(monkeypatch, tmp_path) -> None:
    """Signing in is not enough. Preview content is unreviewed, with open rights."""

    lesson_id = install_preview_lesson(monkeypatch, tmp_path)
    monkeypatch.setenv(DEPLOYMENT_TIER_ENV, TIER_PREVIEW)

    import writing_coach.listening_api as listening_api

    def not_admin(request):
        raise PermissionError("Platform administrator access required")

    monkeypatch.setattr("auth_support.require_admin", not_admin)
    monkeypatch.setattr(listening_api, "preview_visible", lambda request: False)

    assert client().get(f"/api/listening/library/{lesson_id}").status_code == 404
    listed = client().get("/api/listening/library").json()
    assert lesson_id not in {item["lesson_id"] for item in listed["items"]}


def test_preview_tier_allows_an_authorized_admin(monkeypatch, tmp_path) -> None:
    lesson_id = install_preview_lesson(monkeypatch, tmp_path)
    monkeypatch.setenv(DEPLOYMENT_TIER_ENV, TIER_PREVIEW)

    import writing_coach.listening_api as listening_api
    monkeypatch.setattr(listening_api, "preview_visible", lambda request: True)

    response = client().get(f"/api/listening/library/{lesson_id}")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["transcript"]["segments"], "the same canonical model, not a copy"
    assert payload["catalog"]["transcript_state"] == "ready"
    # Still unreviewed, still not published.
    assert payload["catalog"]["published_state"] == "dev_candidate"
    assert payload["catalog"]["reviewed_level"] is None
    assert payload["catalog"]["transcript_quality_state"] == "generated_unreviewed"

    listed = client().get("/api/listening/library", params={"language": "en"}).json()
    assert lesson_id in {item["lesson_id"] for item in listed["items"]}


def test_preview_authorization_is_not_client_side(monkeypatch, tmp_path) -> None:
    """The lesson endpoint is reachable directly; the check must live there."""

    from pathlib import Path as _Path
    source = (_Path(__file__).resolve().parents[1]
              / "writing_coach/listening_api.py").read_text(encoding="utf-8")
    assert "include_preview=preview_visible(request)" in source
    assert source.count("preview_visible(request)") >= 2, \
        "both the listing and the single-lesson endpoint must be gated"


# --- the preview marker is scoped to people, not to the deployment ----------

def test_a_normal_learner_never_sees_a_preview_marker(monkeypatch) -> None:
    """One runtime serves normal learners and admin dogfooding at once.

    A deployment-wide badge would tell every learner they are on a preview when,
    for them, they are not: they see the ordinary product. So the marker follows
    the same admin check that gates the content.
    """

    monkeypatch.setenv(DEPLOYMENT_TIER_ENV, TIER_PREVIEW)
    import writing_coach.listening_api as listening_api
    monkeypatch.setattr(listening_api, "preview_visible", lambda request: False)
    import app as orena_app
    monkeypatch.setattr(orena_app, "preview_visible", lambda request: False)

    body = client().get("/").text
    assert "orena-preview-badge" not in body, "a normal learner sees the normal product"


def test_an_authorized_admin_sees_the_marker(monkeypatch) -> None:
    monkeypatch.setenv(DEPLOYMENT_TIER_ENV, TIER_PREVIEW)
    import app as orena_app
    monkeypatch.setattr(orena_app, "preview_visible", lambda request: True)

    body = client().get("/").text
    assert 'class="orena-preview-badge"' in body
    assert body.count("orena-preview-badge") == 1
    assert "</body>" in body


def test_production_tier_shows_no_marker_to_anyone(monkeypatch) -> None:
    monkeypatch.delenv(DEPLOYMENT_TIER_ENV, raising=False)
    assert "orena-preview-badge" not in client().get("/").text


def test_the_marker_uses_the_same_gate_as_the_content(monkeypatch) -> None:
    """One check, not two that can drift apart."""

    from pathlib import Path as _Path
    root = _Path(__file__).resolve().parents[1]
    app_source = (root / "app.py").read_text(encoding="utf-8")
    assert "if preview_visible(request):" in app_source
    assert "resolve_deployment_tier() == TIER_PREVIEW" not in app_source,         "the shell must not decide visibility on tier alone"
    # The pinned session contract keeps its exact key set.
    assert "orena-preview-badge" not in (root / "auth_support.py").read_text(encoding="utf-8")


def test_one_runtime_serves_both_audiences(monkeypatch, tmp_path) -> None:
    """The single-runtime topology: same process, different answers per caller."""

    lesson_id = install_preview_lesson(monkeypatch, tmp_path)
    monkeypatch.setenv(DEPLOYMENT_TIER_ENV, TIER_PREVIEW)
    import writing_coach.listening_api as listening_api
    import app as orena_app

    # A normal learner: ordinary product, no preview lesson, no marker.
    monkeypatch.setattr(listening_api, "preview_visible", lambda request: False)
    monkeypatch.setattr(orena_app, "preview_visible", lambda request: False)
    assert client().get(f"/api/listening/library/{lesson_id}").status_code == 404
    assert "orena-preview-badge" not in client().get("/").text
    learner_items = {item["lesson_id"]
                     for item in client().get("/api/listening/library").json()["items"]}
    assert lesson_id not in learner_items
    assert learner_items, "the learner still gets the real catalog"

    # An admin on the SAME runtime: preview content and the marker.
    monkeypatch.setattr(listening_api, "preview_visible", lambda request: True)
    monkeypatch.setattr(orena_app, "preview_visible", lambda request: True)
    assert client().get(f"/api/listening/library/{lesson_id}").status_code == 200
    assert "orena-preview-badge" in client().get("/").text
