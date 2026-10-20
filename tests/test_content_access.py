"""Content access (D-248 §4-§6, MV2-1): `writing_coach/product/content_access.py`.

Proved here, hermetically (SQLite Reading engine, in-memory settings and quota doubles):

  1. tiering is deterministic: the same item always gets the same tier; about 30% of a level is Free, with a floor;
     publishing more never takes a Free article away; the weekly rotation is stable within a week and changes across
     weeks; the first item of a set is Free;
  2. the Reading read: 403 `plan_required` for Free (with title, cover and first paragraph), 200 for Plus, a trial and
     an administrator's grant; a 404 still comes before any 403; a paid body is `Cache-Control: private`;
  3. a video is never gated: the payload keeps the player and the channel's captions; only Orena's tools are tiered;
  4. the weekly look-up meter counts one video once a week and refuses the fourth video;
  5. admin overrides apply and are audited; a video can never be made paid;
  6. the access events are counted without content.
"""
from __future__ import annotations

import asyncio
import math
import random
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from policy_support import MemoryPolicyStore, installed
from writing_coach.product import catalog, content_access, quota
from writing_coach.product.content_access import Item
from writing_coach.product.entitlement import resolve

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _isolated():
    previous = quota.runtime()
    content_access.configure()
    yield
    content_access.configure()
    quota.configure_quota(**{field: getattr(previous, field) for field in
                             ("repository", "incarnations", "plan_for", "settings", "reason", "env", "clock")})


def _plan_for(plan):
    """A quota runtime whose effective plan is `plan` (a catalogue Plan, or a callable of the user key)."""
    runtime = quota.runtime()
    runtime.plan_for = (lambda user_key, strict=True: plan) if not callable(plan) else plan
    return runtime


def _ids(count, prefix="a"):
    return [(f"{prefix}{index:05d}", NOW - timedelta(days=count - index)) for index in range(count)]


# ======================================================================================= 1. deterministic tiering ==

def test_the_same_item_always_gets_the_same_tier():
    pool = _ids(400)
    first = content_access.reading_free_ids(pool, free_percent=30, rotation_per_week=2, week="2026-W43")
    again = content_access.reading_free_ids(list(reversed(pool)), free_percent=30, rotation_per_week=2, week="2026-W43")
    assert first == again, "order of the pool does not matter"
    assert content_access.bucket("a00042") == content_access.bucket("a00042")


@pytest.mark.parametrize("size", [100, 1000, 5000])
def test_about_thirty_percent_of_a_level_is_free(size):
    free, rotation = content_access.reading_free_ids(_ids(size), free_percent=30, rotation_per_week=2, week="2026-W43")
    share = len(free) / size
    assert 0.25 <= share <= 0.35, share
    assert len(rotation) == 2 and not (rotation & free), "the rotation comes from the Plus pool"


@pytest.mark.parametrize("size", [1, 2, 3, 7])
def test_a_small_level_still_has_its_floor(size):
    free, _rotation = content_access.reading_free_ids(_ids(size), free_percent=30, rotation_per_week=0, week="2026-W43")
    assert len(free) >= max(1, math.ceil(content_access.split_share(30) * size))


def test_a_single_publish_never_takes_a_free_article_away():
    """Property (review of #466, P1): over many random pools, n from 1, publishing one newer article - in the hash
    bucket or not - never turns a Free article Plus."""
    rng = random.Random(466)
    for trial in range(3000):
        size = 1 + trial % 60
        pool = [(uuid.UUID(int=rng.getrandbits(128)).hex, NOW - timedelta(hours=size - index)) for index in range(size)]
        before, _ = content_access.reading_free_ids(pool, free_percent=30, rotation_per_week=0, week="2026-W43")
        added = (uuid.UUID(int=rng.getrandbits(128)).hex, NOW + timedelta(minutes=1))
        after, _ = content_access.reading_free_ids(pool + [added], free_percent=30, rotation_per_week=0, week="2026-W43")
        assert before <= after, (size, before - after)
    only, _ = content_access.reading_free_ids([("only", NOW)], free_percent=30, rotation_per_week=0, week="2026-W43")
    assert only == {"only"}, "a level of one article has it Free"


def test_a_publish_during_the_week_never_reshuffles_its_rotation():
    week = content_access.iso_week(NOW)
    pool = _ids(400)
    _, picks = content_access.reading_free_ids(pool, free_percent=30, rotation_per_week=2, week=week)
    rng = random.Random(7)
    for _ in range(50):
        pool = pool + [(uuid.UUID(int=rng.getrandbits(128)).hex, NOW + timedelta(minutes=rng.randrange(1, 5000)))]
        _, later = content_access.reading_free_ids(pool, free_percent=30, rotation_per_week=2, week=week)
        assert later == picks


def test_the_rotation_is_stable_within_a_week_and_changes_across_weeks():
    pool = _ids(500)
    weeks = [content_access.iso_week(NOW + timedelta(weeks=n)) for n in range(6)]
    picks = [content_access.reading_free_ids(pool, free_percent=30, rotation_per_week=2, week=week)[1] for week in weeks]
    assert picks[0] == content_access.reading_free_ids(pool, free_percent=30, rotation_per_week=2, week=weeks[0])[1]
    assert len({frozenset(pick) for pick in picks}) == len(weeks), "every week rotates"
    # The ISO week turns on Monday 00:00 UTC.
    assert content_access.iso_week(datetime(2026, 10, 25, 23, 59, tzinfo=UTC)) == "2026-W43"
    assert content_access.iso_week(datetime(2026, 10, 26, 0, 0, tzinfo=UTC)) == "2026-W44"


def test_decide_reads_the_pool_and_the_policies():
    pool = _ids(300)
    content_access.configure(reading_pool=lambda language, level: pool if (language, level) == ("en", "B1") else [],
                             clock=lambda: NOW)
    with installed():
        decisions = {item_id: content_access.decide(Item("reading", item_id, "en", "B1")) for item_id, _ in pool}
        assert {d.tier for d in decisions.values()} == {"free", "plus"}
        assert sum(d.rotation for d in decisions.values()) == 2
        free_share = sum(d.tier == "free" for d in decisions.values()) / len(pool)
        assert 0.24 <= free_share <= 0.38
    with installed(MemoryPolicyStore({"access.reading_free_percent": 100})):
        content_access.clear_caches()
        assert all(content_access.access_tier(Item("reading", item_id, "en", "B1")) == "free" for item_id, _ in pool)


def test_the_first_item_of_a_set_is_free_and_the_rest_plus():
    with installed():
        assert [content_access.access_tier(Item("vocab_set", f"c1-{n}", position=n)) for n in range(3)] == \
            ["free", "plus", "plus"]
        assert content_access.access_tier(Item("grammar", "g1", position=0)) == "free"
    with installed(MemoryPolicyStore({"access.set_free_items": 2})):
        assert content_access.access_tier(Item("mock_test", "m", position=1)) == "free"


def test_a_video_is_always_free_to_watch():
    with installed():
        assert content_access.decide(Item("media", "yt-1")).as_dict() == {"tier": "free", "reason": "viewing",
                                                                          "rotation": False}


# ============================================================================================ 2. the Reading read ==

ARTICLE = (
    "The river rose overnight and the fields were flooded by morning.\n\n"
    "Farmers moved their animals to higher ground before the water reached the road. "
    "The council opened the hall to families whose homes were cut off by the water. "
    "By Tuesday the level had fallen and volunteers began to clear the worst of the mud. "
    "Nobody was hurt, but several families will not return home before the end of the month. "
)


@pytest.fixture()
def reading():
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from writing_coach import reading_admin_api as admin_api
    from writing_coach import reading_articles_api as learner_api
    from writing_coach.persistence.models import Base
    from writing_coach.persistence.reading_content_repository import ReadingContentRepository
    from writing_coach.persistence.reading_job_repository import ReadingJobRepository
    from writing_coach.reading_content_engine import ReadingContentEngine

    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    content = ReadingContentRepository(engine)
    content.ensure_built_in_sources()
    jobs = ReadingJobRepository(engine)
    service = ReadingContentEngine(content=content, jobs=jobs)

    def guard(request):
        return {"google_sub": "sub-admin", "email": "admin@example.com", "role": "admin"}

    admin_api.configure_reading_admin(admin_guard=guard, content=content, jobs=jobs, engine=service,
                                      audit=lambda *a, **k: None)
    learner_api.configure_reading_articles(content, language_supported=lambda code: code in {"en", "zh"})
    admin_app, learner_app = FastAPI(), FastAPI()
    admin_app.include_router(admin_api.router)
    learner_app.include_router(learner_api.router)
    settings = MemoryPolicyStore()
    events: list[dict] = []
    content_access.configure(
        store=settings,
        reading_pool=lambda language, level: content.published_pool(language=language, level=level or None),
        record_usage=lambda **kw: events.append(kw), clock=lambda: NOW)

    def publish(title="Rain returns"):
        response = call(admin_app, "POST", "/api/admin/reading/jobs",
                        data={"kind": "text", "text": ARTICLE, "title": title, "language": "en",
                              "can_republish": "true", "attribution_required": "false"})
        assert response.status_code == 202
        article_id = service.process(jobs.claim("worker-1"))["article_id"]
        call(admin_app, "POST", f"/api/admin/reading/articles/{article_id}/status", json={"status": "published"})
        return article_id

    yield SimpleNamespace(app=learner_app, publish=publish, settings=settings, events=events, content=content)
    admin_api.configure_reading_admin(admin_guard=None)
    learner_api.configure_reading_articles(None)


def call(app, method, path, **kwargs):
    headers = {"origin": "http://testserver"} if method.upper() != "GET" else {}

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, headers=headers, **kwargs)

    return asyncio.run(run())


def _make_plus(reading, article_id):
    content_access.save_overrides({"set": {f"reading:{article_id}": "plus"}}, updated_by="a@x", actor="sub-admin")


def _trialing(user_key, strict=True):
    """Billing's 7-day trial grant: `trialing` reads as Plus (product/entitlement.py)."""
    return resolve(legacy=None, billing={"state": "trialing", "plan_id": "plus", "paid_through":
                                         (datetime.now(UTC) + timedelta(days=7)).isoformat()},
                   now=datetime.now(UTC)).plan(strict=strict)


def _admin_granted(user_key, strict=True):
    """An administrator's hand-set plan (D-154: provider `manual`)."""
    legacy = SimpleNamespace(status="active", provider="manual", plan_id="plus", current_period_end=None)
    return resolve(legacy=legacy, billing=None, now=datetime.now(UTC)).plan(strict=strict)


def test_free_is_refused_a_plus_body_with_the_preview(reading):
    article_id = reading.publish()
    _make_plus(reading, article_id)
    _plan_for(catalog.FREE)
    with installed(MemoryPolicyStore({"access.enforced": True})):
        response = call(reading.app, "GET", f"/api/reading/articles/{article_id}")
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["category"] == "plan_required" and detail["retryable"] is False
    context = detail["context"]
    assert (context["required_tier"], context["kind"], context["item_id"]) == ("plus", "reading", article_id)
    assert (context["required_plan"], context["content_kind"], context["content_id"]) == ("plus", "reading", article_id)
    assert context["plan"] == "free" and context["upgrade"] == "#/plan/pricing"
    assert context["trial_available"] is None, "Billing's seam is absent: not known, never a guess"
    preview = context["preview"]
    assert preview["title"] == "Rain returns"
    assert preview["first_paragraph"] == "The river rose overnight and the fields were flooded by morning."
    assert "Farmers" not in str(context), "nothing past the first paragraph"
    assert reading.events == [{"user_key": "legacy", "feature": "access.locked_view:reading", "amount": 1}]


@pytest.mark.parametrize("plan_for", [lambda u, strict=True: catalog.PLUS, lambda u, strict=True: catalog.PRO,
                                      _trialing, _admin_granted], ids=["plus", "pro", "trial", "admin-granted"])
def test_paid_trial_and_granted_plans_read_the_body_privately(reading, plan_for):
    article_id = reading.publish()
    _make_plus(reading, article_id)
    _plan_for(plan_for)
    with installed(MemoryPolicyStore({"access.enforced": True})):
        response = call(reading.app, "GET", f"/api/reading/articles/{article_id}")
    assert response.status_code == 200
    assert "Farmers" in response.json()["body"]
    assert response.headers["cache-control"].startswith("private")
    assert "public" not in response.headers["cache-control"] and response.headers["vary"] == "Cookie"


def test_a_plus_body_is_private_even_while_enforcement_is_off(reading):
    article_id = reading.publish()
    _make_plus(reading, article_id)
    _plan_for(catalog.FREE)
    with installed():
        response = call(reading.app, "GET", f"/api/reading/articles/{article_id}")
    assert response.status_code == 200, "off refuses nothing"
    assert response.headers["cache-control"].startswith("private")


def test_a_free_body_is_private_too_because_its_tier_can_change(reading):
    """A Free body today may be Plus after Monday's rotation or an override: no shared cache may outlive that."""
    article_id = reading.publish()
    content_access.save_overrides({"set": {f"reading:{article_id}": "free"}}, actor="sub-admin")
    _plan_for(catalog.FREE)
    with installed(MemoryPolicyStore({"access.enforced": True})):
        response = call(reading.app, "GET", f"/api/reading/articles/{article_id}")
    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("private") and response.headers["vary"] == "Cookie"
    assert "etag" in response.headers, "revalidation stays cheap"


def test_the_practice_set_of_a_plus_article_is_refused_the_same_way(reading):
    from writing_coach import reading_practice_api

    article_id = reading.publish()
    _make_plus(reading, article_id)

    class Practice:
        def served_set(self, article_id, support_language):
            return {"questions": []}

        def article_is_published(self, article_id):
            return True

    reading_practice_api.configure_reading_practice(Practice(), support_language=lambda: "vi")
    try:
        _plan_for(catalog.FREE)
        with installed(MemoryPolicyStore({"access.enforced": True})):
            with pytest.raises(HTTPException) as refused:
                reading_practice_api.article_set(article_id, SimpleNamespace(headers={}))
            assert refused.value.status_code == 403 and refused.value.detail["category"] == "plan_required"
            _plan_for(catalog.PLUS)
            assert reading_practice_api.article_set(article_id, SimpleNamespace(headers={}))["set"] == {"questions": []}
    finally:
        reading_practice_api.configure_reading_practice(None, support_language=None)


def test_an_unknown_article_is_a_404_before_any_403(reading):
    _plan_for(catalog.FREE)
    with installed(MemoryPolicyStore({"access.enforced": True})):
        response = call(reading.app, "GET", "/api/reading/articles/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_a_plan_that_cannot_be_read_is_503_never_an_upgrade(reading):
    article_id = reading.publish()
    _make_plus(reading, article_id)

    def down(user_key, strict=True):
        raise RuntimeError("subscription store down")

    _plan_for(down)
    with installed(MemoryPolicyStore({"access.enforced": True})):
        response = call(reading.app, "GET", f"/api/reading/articles/{article_id}")
    assert response.status_code == 503 and response.json()["detail"]["category"] == "quota_unavailable"


def test_the_list_carries_each_cards_tier_and_stays_cacheable(reading):
    plus_id = reading.publish("Rain returns")
    _make_plus(reading, plus_id)
    _plan_for(catalog.FREE)
    with installed(MemoryPolicyStore({"access.enforced": True})):
        response = call(reading.app, "GET", "/api/reading/articles", params={"language": "en"})
    assert response.status_code == 200
    card = next(item for item in response.json()["items"] if item["id"] == plus_id)
    assert card["access"] == {"tier": "plus", "rotation": False}
    assert "body" not in card
    assert response.headers["cache-control"].startswith("public"), "the tiers are the same for every learner"


def test_the_summary_of_a_plus_body_is_refused_the_same_way(reading, monkeypatch):
    from writing_coach import reading_translation_api

    article_id = reading.publish()
    _make_plus(reading, article_id)
    _plan_for(catalog.FREE)
    payload = reading_translation_api.ReadingSummaryIn(source_language="en", target_language="vi", article_id=article_id)
    with installed(MemoryPolicyStore({"access.enforced": True})):
        with pytest.raises(HTTPException) as refused:
            reading_translation_api._summary_source(payload)
    assert refused.value.status_code == 403 and refused.value.detail["category"] == "plan_required"
    _plan_for(catalog.PLUS)
    with installed(MemoryPolicyStore({"access.enforced": True})):
        text, _shared = reading_translation_api._summary_source(payload)
    assert "Farmers" in text


# ======================================================================================== 3. videos are never gated ==

@pytest.fixture()
def curated(fixture_listening_catalog, tmp_path, monkeypatch):
    from writing_coach import listening_api
    from writing_coach.media_library_store import FileMediaLibraryStore

    monkeypatch.setattr(listening_api, "get_learner_profile", lambda: {"native_language": "vi"})
    previous = listening_api._media_store
    listening_api.configure_listening_media_library(FileMediaLibraryStore(tmp_path / "media_library"))
    yield
    listening_api.configure_listening_media_library(previous)


def test_a_free_learner_keeps_the_player_and_captions_and_loses_only_orenas_translation(curated):
    from writing_coach.listening_api import open_listening_library_lesson

    _plan_for(catalog.FREE)
    with installed():
        ungated = open_listening_library_lesson("en-daily-pen-in-my-bag", "vi")
    with installed(MemoryPolicyStore({"access.enforced": True})):
        gated = open_listening_library_lesson("en-daily-pen-in-my-bag", "vi")
    assert "access" not in ungated, "while enforcement is off the payload is unchanged"
    assert gated["playback"] == ungated["playback"], "the player is never gated"
    assert gated["transcript"] == ungated["transcript"], "the captions are never paid"
    assert "translations" not in gated and gated["translation"]["locked"] is True
    assert gated["access"]["viewing"] == "free"
    assert gated["access"]["tools"]["lookup"] == {"tier": "free", "locked": False}
    assert gated["access"]["tools"]["dictation"] == {"tier": "plus", "locked": True}
    _plan_for(catalog.PLUS)
    with installed(MemoryPolicyStore({"access.enforced": True})):
        paid = open_listening_library_lesson("en-daily-pen-in-my-bag", "vi")
    assert paid.get("translations") == ungated.get("translations")
    assert not any(tool["locked"] for tool in paid["access"]["tools"].values())


@pytest.mark.parametrize("tool", ["translation", "shadowing_score", "dictation", "save_to_review"])
def test_the_plus_tools_are_refused_to_free_and_open_to_plus(tool):
    _plan_for(catalog.FREE)
    with installed(MemoryPolicyStore({"access.enforced": True})):
        with pytest.raises(HTTPException) as refused:
            content_access.require_media_tool(tool, "yt-1")
        context = refused.value.detail["context"]
        assert refused.value.status_code == 403 and refused.value.detail["category"] == "plan_required"
        assert (context["kind"], context["item_id"], context["tool"]) == ("media_tool", "yt-1", tool)
        _plan_for(catalog.PLUS)
        content_access.require_media_tool(tool, "yt-1")


def test_scored_shadowing_cannot_skip_its_video_link():
    from writing_coach.speech_api import _require_practice_access

    _plan_for(catalog.FREE)
    with installed():
        _require_practice_access("", "")  # off: an old client is not refused
    with installed(MemoryPolicyStore({"access.enforced": True})):
        for practice, media_id, expected in (("", "", "pronunciation_practice_required"),
                                             ("shadowing", "", "pronunciation_media_required"),
                                             ("karaoke", "", "pronunciation_practice_invalid")):
            with pytest.raises(HTTPException) as refused:
                _require_practice_access(practice, media_id)
            assert refused.value.status_code == 422 and refused.value.detail["category"] == expected
        with pytest.raises(HTTPException) as refused:
            _require_practice_access("shadowing", "yt-1")
        assert refused.value.status_code == 403 and refused.value.detail["context"]["tool"] == "shadowing_score"
        with pytest.raises(HTTPException):
            _require_practice_access("speaking", "yt-1")  # a take that names a video is a video tool
        _require_practice_access("speaking", "")  # Speaking practice is not gated
        _plan_for(catalog.PLUS)
        _require_practice_access("shadowing", "yt-1")


def test_the_dictation_route_refuses_free_before_writing():
    from writing_coach import listening_api

    _plan_for(catalog.FREE)
    payload = listening_api.ListeningProgressIn(asset_id="yt-1", segment_id="s1")
    with installed(MemoryPolicyStore({"access.enforced": True})):
        with pytest.raises(HTTPException) as refused:
            listening_api.save_listening_progress(payload)
    assert refused.value.status_code == 403 and refused.value.detail["context"]["tool"] == "dictation"


# ============================================================================================ 4. the weekly meter ==

def _metered(plan, *, clock=lambda: NOW):
    from tests.test_quota_gate import FakeIncarnations, FakeQuotaRepository, MemorySettings

    repository = FakeQuotaRepository()
    quota.configure_quota(repository=repository, incarnations=FakeIncarnations(),
                          plan_for=lambda user_key, strict=True: plan, settings=MemorySettings(),
                          env={quota.FLAG: "on", quota.METERS_FLAG: "media.tools_weekly"}, clock=clock)
    return repository


def test_the_weekly_window_is_an_iso_week():
    window = quota.window_for("week", now=datetime(2026, 10, 21, 12, tzinfo=UTC), zone_name="UTC", previous=None)
    assert window.window_id == "W:2026-10-19@UTC"
    assert (window.start, window.end) == (datetime(2026, 10, 19, tzinfo=UTC), datetime(2026, 10, 26, tzinfo=UTC))
    local = quota.window_for("week", now=datetime(2026, 10, 25, 18, tzinfo=UTC), zone_name="Asia/Ho_Chi_Minh",
                             previous=None)
    assert local.window_id == "W:2026-10-26@Asia/Ho_Chi_Minh", "Monday has begun in Vietnam"


def test_free_looks_up_on_three_videos_a_week_and_one_video_counts_once():
    repository = _metered(catalog.FREE)
    with installed(MemoryPolicyStore({"access.enforced": True})):
        for media_id in ("v1", "v2", "v1", "v3", "v2", "v3"):
            content_access.require_media_tool("lookup", media_id)
        with pytest.raises(HTTPException) as refused:
            content_access.require_media_tool("lookup", "v4")
    assert refused.value.status_code == 429
    detail = refused.value.detail
    assert detail["category"] == "quota_exhausted" and detail["context"]["feature"] == "media.tools_weekly"
    assert (detail["context"]["used"], detail["context"]["limit"]) == (3, 3)
    bucket = next(iter(repository.buckets.values()))
    assert bucket["consumed"] == 3 and bucket["window_id"].startswith("W:")


def test_the_next_week_opens_three_more_videos():
    moment = {"now": NOW}
    _metered(catalog.FREE, clock=lambda: moment["now"])
    content_access.configure(clock=lambda: moment["now"])
    with installed(MemoryPolicyStore({"access.enforced": True})):
        for media_id in ("v1", "v2", "v3"):
            content_access.require_media_tool("lookup", media_id)
        moment["now"] = NOW + timedelta(days=7)
        for media_id in ("v1", "v4", "v5"):
            content_access.require_media_tool("lookup", media_id)


def test_plus_is_never_metered_and_a_video_override_frees_its_tools():
    repository = _metered(catalog.PLUS)
    with installed(MemoryPolicyStore({"access.enforced": True})):
        for media_id in ("v1", "v2", "v3", "v4", "v5"):
            content_access.require_media_tool("lookup", media_id)
    assert repository.calls == [], "the full tools count nothing"

    store = MemoryPolicyStore()
    content_access.configure(store=store)
    content_access.save_overrides({"set": {"media:v9": "free"}}, actor="sub-admin")
    repository = _metered(catalog.FREE)
    with installed(MemoryPolicyStore({"access.enforced": True})):
        content_access.require_media_tool("dictation", "v9")
        content_access.require_media_tool("lookup", "v9")
    assert repository.calls == []


def test_the_word_detail_route_counts_a_video_by_its_contract_content_id(monkeypatch):
    from writing_coach import word_detail

    seen = []
    monkeypatch.setattr(content_access, "require_media_tool", lambda tool, media_id, **kw: seen.append((tool, media_id)))
    monkeypatch.setattr(word_detail, "word_detail", lambda payload: {"ok": True})
    payload = word_detail.WordDetailIn(text="pen", context="a pen in my bag", source_language="en",
                                       target_language="vi", depth="sheet", content_id="media:yt-1")
    word_detail.word_detail_route(payload, SimpleNamespace())
    payload = word_detail.WordDetailIn(text="pen", context="a pen in my bag", source_language="en",
                                       target_language="vi", depth="sheet", content_id="article:x")
    word_detail.word_detail_route(payload, SimpleNamespace())
    assert seen == [("lookup", "yt-1")]


# ============================================================================================ 5. admin overrides ==

def test_overrides_apply_and_every_change_is_audited():
    store = MemoryPolicyStore()
    content_access.configure(store=store, reading_pool=lambda language, level: _ids(50))
    with installed():
        content_access.save_overrides({"set": {"reading:a00001": "plus", "vocab_set:c1": "free"}},
                                      updated_by="admin@x", actor="sub-admin")
        assert content_access.access_tier(Item("reading", "a00001", "en", "B1")) == "plus"
        assert content_access.decide(Item("reading", "a00001", "en", "B1")).reason == "override"
        assert content_access.access_tier(Item("vocab_set", "c1", position=5)) == "free"
        content_access.save_overrides({"remove": ["vocab_set:c1"]}, actor="sub-admin")
        assert content_access.access_tier(Item("vocab_set", "c1", position=5)) == "plus"
    assert [audit["action"] for audit in store.audits] == ["product.content_access.update"] * 2
    assert store.audits[0]["actor"] == "sub-admin"
    assert store.audits[0]["payload"]["changes"]["reading:a00001"] == {"from": None, "to": "plus"}
    assert store.audits[1]["payload"]["changes"] == {"vocab_set:c1": {"from": "free", "to": None}}


def test_a_video_can_never_be_made_paid_and_bad_keys_are_refused():
    content_access.configure(store=MemoryPolicyStore())
    for change in ({"set": {"media:yt-1": "plus"}}, {"set": {"book:x": "free"}}, {"set": {"reading:x": "gold"}},
                   {"set": {"reading:": "free"}}, {"drop": []}):
        with pytest.raises(content_access.OverridesInvalid):
            content_access.save_overrides(change, actor="a")


def test_a_stale_editor_conflicts_instead_of_overwriting():
    from writing_coach.persistence.platform_repository import SettingConflict

    store = MemoryPolicyStore()
    content_access.configure(store=store)
    content_access.save_overrides({"set": {"reading:a": "free"}}, actor="a")
    with pytest.raises(SettingConflict):
        content_access.save_overrides({"set": {"reading:b": "free"}, "expected_updated_at": None}, actor="b")


def test_the_admin_routes_require_an_administrator_and_audit(monkeypatch):
    from fastapi.testclient import TestClient

    from writing_coach.product import api as product_api

    store = MemoryPolicyStore()
    content_access.configure(store=store)
    app = FastAPI()
    app.include_router(product_api.router)
    client = TestClient(app)

    def refuse(request):
        raise HTTPException(403, "Platform administrator access required")

    monkeypatch.setattr(product_api, "require_admin", refuse)
    assert client.get("/api/product/admin/content-access").status_code == 403
    assert client.put("/api/product/admin/content-access", json={"set": {"reading:a": "plus"}},
                      headers={"origin": "http://testserver"}).status_code == 403
    monkeypatch.setattr(product_api, "require_admin", lambda request: {"google_sub": "sub-admin", "email": "a@x"})
    with installed():
        saved = client.put("/api/product/admin/content-access", json={"set": {"reading:a": "plus"}},
                           headers={"origin": "http://testserver"})
        assert saved.status_code == 200 and saved.json()["overrides"] == {"reading:a": "plus"}
        assert client.put("/api/product/admin/content-access", json={"set": {"media:a": "pro"}},
                          headers={"origin": "http://testserver"}).status_code == 422
        snapshot = client.get("/api/product/admin/content-access").json()
    assert snapshot["policies"]["access.reading_free_percent"] == 30 and snapshot["enforced"] is False
    assert store.audits[0]["action"] == "product.content_access.update" and store.audits[0]["actor"] == "sub-admin"


# ================================================================================================= 6. analytics ==

def test_events_are_counted_without_content(monkeypatch):
    from fastapi.testclient import TestClient

    from writing_coach.product import api as product_api

    events = []
    content_access.configure(record_usage=lambda **kw: events.append(kw))
    app = FastAPI()
    app.include_router(product_api.router)
    client = TestClient(app)
    headers = {"origin": "http://testserver"}
    assert client.post("/api/product/access/events", json={"event": "upgrade_sheet_open", "source": "reader"},
                       headers=headers).json() == {"recorded": True}
    assert client.post("/api/product/access/events", json={"event": "locked_view", "source": "reading"},
                       headers=headers).status_code == 422, "the server counts locked views where it refuses"
    assert client.post("/api/product/access/events", json={"event": "trial_start", "source": "A title!"},
                       headers=headers).status_code == 422
    assert content_access.trial_started("legacy", "sheet") is True
    assert [event["feature"] for event in events] == ["access.upgrade_sheet_open:reader", "access.trial_start:sheet"]


def test_the_trial_seam_says_what_billing_answers():
    content_access.configure_trial(lambda user_key: True)
    error = content_access.plan_required(user_key="u", kind="reading", item_id="a", required_tier="plus", plan="free")
    assert error.detail["context"]["trial_available"] is True
    content_access.configure_trial(None)


# ================================================================================ 7. what the learner UI draws (MV2-3) ==

def test_the_learner_access_read_says_enforcement_tier_and_trial():
    _plan_for(catalog.FREE)
    with installed(MemoryPolicyStore({"access.enforced": True})):
        assert content_access.learner_access("u") == {"enforced": True, "tier": "free", "trial_available": None}
    content_access.configure_trial(lambda user_key: True)
    _plan_for(catalog.PLUS)
    with installed(MemoryPolicyStore({"access.enforced": False})):
        assert content_access.learner_access("u") == {"enforced": False, "tier": "plus", "trial_available": True}
    content_access.configure_trial(None)


def test_an_unreadable_plan_draws_no_lock():
    def unreadable(user_key, strict=True):
        raise HTTPException(503, {"category": "quota_unavailable"})

    _plan_for(unreadable)
    with installed(MemoryPolicyStore({"access.enforced": True})):
        assert content_access.learner_access("u")["tier"] is None


def test_the_commerce_read_carries_the_content_access_block(monkeypatch):
    from fastapi.testclient import TestClient

    from writing_coach.product import api as product_api

    monkeypatch.setattr(product_api, "accountCommerce", lambda user_key: {"available": True, "readiness": "known"})
    _plan_for(catalog.FREE)
    app = FastAPI()
    app.include_router(product_api.router)
    with installed(MemoryPolicyStore({"access.enforced": True})):
        body = TestClient(app).get("/api/product/commerce").json()
    assert body["readiness"] == "known"
    assert body["content_access"] == {"enforced": True, "tier": "free", "trial_available": None}


def test_the_next_recommended_article_carries_its_access_block(monkeypatch):
    from writing_coach import reading_practice_api

    monkeypatch.setattr(content_access, "decide", lambda item, now=None: content_access.Decision("plus", "rule"))
    choice = {"set": {"id": "s1", "article": {"id": "a1", "language": "en", "level": "B1"}}, "recommendation": "r"}
    decorated = reading_practice_api._with_access(choice)
    assert decorated["set"]["article"]["access"] == {"tier": "plus", "rotation": False}
    assert decorated["recommendation"] == "r" and "access" not in choice["set"]["article"]
    assert reading_practice_api._with_access(None) is None
