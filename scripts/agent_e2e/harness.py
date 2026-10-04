"""The agent's E2E pass inside the throwaway stack's web container (INTELLIGENCE_RECONCILIATION_D4.md section 5).

Runs with the stack's own environment (PostgreSQL at Alembic head, the one development learner, sign-in off) and
the real app: every seed goes through the app's routes, or - where the route needs a provider (an essay review, a
scored speaking take) - through the same repository the route writes with, under the same request context. Agent
turns go through POST /api/agent/turn; only the provider is replaced, by a scripted one that calls each read tool,
so no provider is reached and nothing is billed. What the tool read is checked against what was seeded: the
learner's own rows, in the turn's language only.

    docker compose -p orena-agent-e2e exec web python scripts/agent_e2e/harness.py

Prints one JSON object (the per-check results) and exits 0 when every check passed, 1 otherwise. Standard library
plus the app's own dependencies; nothing is written outside the throwaway database.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
import uuid
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import app  # noqa: E402  - the real app, on the stack's PostgreSQL
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from writing_coach.agent import api as agent_api  # noqa: E402
from writing_coach.agent.fake_provider import FakeAgentTurnProvider, reply  # noqa: E402
from writing_coach.agent.provider import ToolCallRequest, TurnFinished  # noqa: E402
from writing_coach.agent.tools import LearnerScope  # noqa: E402
from writing_coach.agent.turn import learner_context  # noqa: E402

USER = "legacy"  # the one development learner when sign-in is off
LANGS = {"en": "en", "zh": "zh-CN"}  # session language -> contract target
WORDS = {"en": ["serendipity", "opportunity", "reluctant"], "zh": ["机会", "学习", "朋友"]}
ESSAYS = {"en": ("Yesterday I go to the market.", "tense", "go"), "zh": ("我觉得市场比超市更有意思的。", "particle", "更有意思的")}
D4_TABLES = ("works", "work_turns", "library_items", "language_provenance", "learner_imports", "annotations")

results: list[dict] = []
UNAVAILABLE = None  # the tool_result summary of a read that did not answer (set from the copy at start)


def check(name: str, ok: bool, **detail) -> bool:
    results.append({"check": name, "ok": bool(ok), **detail})
    return bool(ok)


def sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for frame in body.split("\n\n"):
        if not frame.strip():
            continue
        lines = dict(line.split(": ", 1) for line in frame.splitlines() if ": " in line)
        if "event" in lines:
            events.append((lines["event"], json.loads(lines.get("data") or "{}")))
    return events


def table_counts() -> dict:
    engine = app._persistence_runtime.engine
    counts = {}
    with engine.connect() as connection:
        for table in (*D4_TABLES, "usage_events"):
            try:
                counts[table] = connection.execute(text(f'SELECT count(*) FROM "{table}"')).scalar_one()
            except Exception:  # a table this schema does not have
                connection.rollback()
                counts[table] = None
    return counts


def scripted(rounds) -> None:
    """The app's own runtime - tools, capabilities, sessions, limits, meter - with a scripted provider."""

    agent_api.configure_agent(replace(BASE_RUNTIME, provider=FakeAgentTurnProvider(list(rounds))))


def turn(client: TestClient, lang: str, message: str | None, context: dict | None = None, *, trigger="message",
         session_id: str | None = None, version: int = 5) -> tuple[int, list[tuple[str, dict]], str]:  # fmt: skip
    body = {
        "contract_version": version, "trigger": trigger,
        "client": {"ui_version": "agent-e2e", "supported_actions": ["navigate", "save_word", "start_review"],
                   "supported_intents": ["vocabulary.review_due", "writing.revision"]},
        "context": {"surface": "home", "locale": {"interface": "vi", "support": "vi", "target": LANGS[lang],
                                                    "content": LANGS[lang]}, **(context or {})},
    }  # fmt: skip
    if message is not None:
        body["message"] = message
    if session_id:
        body["session_id"] = session_id
    response = client.post("/api/agent/turn", json=body)
    events = sse(response.text) if response.status_code == 200 else []
    return response.status_code, events, response.text[:300]


def tool_turn(client: TestClient, lang: str, tool: str, args: dict, context: dict | None = None) -> dict:
    scripted([(ToolCallRequest("c1", tool, args), TurnFinished(0, 5, "tool_calls")), reply("Ok.")])
    status, events, raw = turn(client, lang, "Xem giúp mình.", context)
    names = [name for name, _ in events]
    result = next((data for name, data in events if name == "tool_result"), {})
    return {"status": status, "events": names, "summary": result.get("summary"),
            "evidence": names.count("evidence"), "raw": raw if status != 200 else None}  # fmt: skip


def invoke(lang: str, tool: str, args: dict):
    scope = LearnerScope(user_key=USER, language=lang, interface="vi")
    with learner_context(scope):
        return BASE_RUNTIME.tools.invoke(tool, scope, args)


# --- seeding ---------------------------------------------------------------------------------------------------


def seed(client: TestClient, lang: str) -> dict:
    seeded: dict = {}
    client.post("/api/platform/language", json={"language": lang})
    for word in WORDS[lang]:
        response = client.post("/api/library/vocabulary", json={"word": word})
        check(f"seed.{lang}.word.{word}", response.status_code in (200, 201), status=response.status_code)
    scope = LearnerScope(user_key=USER, language=lang)
    with learner_context(scope):
        text_, category, fragment = ESSAYS[lang]
        error = {"fragment": fragment, "suggestion": fragment, "explanation_vi": "…", "category": category}
        essay = app._learning_repository.create_essay(
            {
                "created_at": "2026-10-03T08:00:00+00:00", "prompt": "", "text": text_, "word_count": 8,
                "target_cefr": "", "grammar": 60.0, "vocabulary": 60.0, "coherence": 60.0, "task_achievement": 60.0,
                "naturalness": 60.0, "overall": 60.0, "cefr_estimate": "B1", "evaluator": "e2e", "summary_vi": "",
                "strengths_json": "[]", "strength_evidence_json": "[]", "priorities_json": "[]",
                "errors_json": json.dumps([error], ensure_ascii=False),
            }
        )  # fmt: skip
        seeded["essay_id"] = str(essay["id"])
        flagged = WORDS[lang][1]
        attempt = app._specialized_learning_repository.create_speaking_attempt_record(
            {
                "created_at": "2026-10-03T08:00:00+00:00", "language": lang, "take_id": f"s1:1:{uuid.uuid4().hex}",
                "asset_id": f"e2e-{lang}", "segment_id": "s1", "reference_text": flagged, "transcript_text": flagged,
                "dimensions": {"pronunciation": 70.0}, "provenance": {},
                "evidence": {"pronunciation": {"words": [{"word": flagged, "accuracy_score": 40.0,
                                                          "error_type": "Mispronunciation", "phonemes": []}]}},
            }
        )  # fmt: skip
        seeded["attempt_id"] = str(attempt["id"])
        seeded["flagged_word"] = flagged
    # Listening: a catalogue lesson in this language, a line scored by the server (through the route) and one
    # legacy client-sourced row (repository), which the agent must not state as verified (F-2).
    from writing_coach.listening_catalog import catalog_lessons, lesson_metadata

    lesson = next((item for item in catalog_lessons() if str(lesson_metadata(item)["language"]).startswith(lang)), None)
    if lesson is not None:
        metadata = lesson_metadata(lesson)
        seeded["lesson_id"] = lesson.lesson_id
        spoken = metadata.get("spoken_text_by_segment") or {}
        if spoken:
            segment_id, line_text = next(iter(spoken.items()))
            response = client.post("/api/listening/progress", json={
                "asset_id": metadata["media_object_id"], "lesson_id": lesson.lesson_id, "segment_id": segment_id,
                "presentation": "checked", "revealed": False, "checked_attempt_count": 1, "last_answer": line_text})  # fmt: skip
            check(f"seed.{lang}.listening.route", response.status_code in (200, 201), status=response.status_code,
                  body=response.text[:200])  # fmt: skip
        else:  # a catalogue lesson without per-line text: no server score is possible, the legacy row still is
            check(f"seed.{lang}.listening.route", True, note="lesson has no spoken text per line; route seed skipped")
        with learner_context(scope):
            app._specialized_learning_repository.save_listening_progress_record(
                {"asset_id": metadata["media_object_id"], "segment_id": "legacy-line", "presentation": "checked",
                 "revealed": False, "checked_attempt_count": 2, "best_accuracy_percent": 100.0, "best_exact": True,
                 "last_answer": "", "updated_at": "2026-10-03T08:00:00+00:00"})  # fmt: skip
    # Grammar: a point the agent itself finds (search), completed through the app's own route function.
    try:
        found = invoke(lang, "search_grammar_points", {"query": {"en": "present", "zh": "是"}[lang], "limit": 5})
        points = found.data.get("points") or []
        if points:
            seeded["grammar_id"] = points[0]["grammar_id"]
            with learner_context(scope):
                app.api_complete_grammar(seeded["grammar_id"])
        check(f"seed.{lang}.grammar", bool(points), found=len(points))
    except Exception as exc:  # recorded, the pass goes on
        check(f"seed.{lang}.grammar", False, error=repr(exc)[:300])
    return seeded


def seed_reading(lang: str) -> str | None:
    from writing_coach.persistence.reading_content_repository import ReadingContentRepository
    from writing_coach.persistence.reading_evidence_repository import QuestionInput, ReadingEvidenceRepository, body_sha256

    engine = app._persistence_runtime.engine
    content, evidence = ReadingContentRepository(engine), ReadingEvidenceRepository(engine)
    content.ensure_built_in_sources()
    body = {"en": "Tom missed the early train. He waited forty minutes on a cold platform. The next one was full.",
            "zh": "小明没赶上早班火车。他在寒冷的站台上等了四十分钟。下一班车也满了。"}[lang]  # fmt: skip
    snapshot = content.record_source_item(
        source_id=content.built_in_source_id("manual"), source_native_id="", canonical_url="", title="E2E",
        author="", published_at=None, language=lang, body=body, content_hash=uuid.uuid4().hex * 2,
        metadata={}, rights={"can_republish": True},
    )  # fmt: skip
    article = content.create_article(
        source_item_id=snapshot["id"], title=f"E2E {lang}", body=body, excerpt="", language=lang, topic="travel",
        estimated_level="B1", estimated_confidence=0.7, word_count=20, reading_time_seconds=60, analysis={}, targets=[],
    )  # fmt: skip
    content.set_status(article["id"], "published", actor="admin")
    built = evidence.create_set(
        article["id"], expected_body_sha256=body_sha256(content.get_article(article["id"])["body"]),
        support_language="vi", generator_version="e2e/1", model="stub",
        questions=[QuestionInput("detail", "How long?", ["forty", "ten"], 0, "x", {"en": "forty minutes", "zh": "四十分钟"}[lang])],
        validation={}, actor="admin",
    )  # fmt: skip
    evidence.transition(built["id"], "needs_review", actor="admin")
    for question in built["questions"]:
        evidence.decide_question(built["id"], question["id"], decision="approve", actor="admin")
    evidence.transition(built["id"], "approved", actor="admin")
    with learner_context(LearnerScope(user_key=USER, language=lang)):
        evidence.submit_attempt(set_id=built["id"], operation_id=uuid.uuid4().hex,
                                answers={q["id"]: 0 for q in built["questions"]}, support_language="vi")  # fmt: skip
    return f"article:{article['id']}"


# --- the pass --------------------------------------------------------------------------------------------------


def run() -> None:
    client = TestClient(app.app)
    check("capabilities", client.get("/api/agent/capabilities?interface=vi").status_code == 200)
    before = table_counts()
    seeded = {}
    for lang in LANGS:
        try:
            seeded[lang] = seed(client, lang)
        except Exception as exc:  # recorded; the turns below still run on what was seeded
            check(f"seed.{lang}", False, error=repr(exc)[:300], trace=traceback.format_exc()[-600:])
            seeded.setdefault(lang, {})
        try:
            seeded[lang]["reading"] = seed_reading(lang)
        except Exception as exc:  # recorded, not hidden
            check(f"seed.{lang}.reading", False, error=repr(exc)[:300])
    after_seed = table_counts()
    results.append({"check": "seeded", "ok": True, "seeded": seeded})

    for lang in LANGS:
        client.post("/api/platform/language", json={"language": lang})
        s = seeded[lang]
        other = "zh" if lang == "en" else "en"
        plan = [
            ("get_due_review_summary", {}, None),
            ("get_due_vocabulary", {"limit": 10}, None),
            ("get_saved_word_state", {"words": [WORDS[lang][0]]}, None),
            ("get_word_detail", {"text": WORDS[lang][0]}, None),
            ("get_writing_history_summary", {}, None),
            ("get_pronunciation_history", {}, None),
            ("get_reading_progress", {}, None),
            ("build_learning_snapshot", {}, None),
            ("get_learning_weaknesses", {}, None),
            ("get_recommended_next_activities", {}, None),
        ]  # fmt: skip
        if s.get("essay_id"):
            in_view = {"surface": "writing.review", "essay_id": s["essay_id"]}
            plan += [("get_current_writing_evaluation", {"essay_id": s["essay_id"]}, in_view),
                     ("get_writing_feedback_items", {"essay_id": s["essay_id"]}, in_view)]  # fmt: skip
        if s.get("attempt_id"):
            plan += [("get_pronunciation_attempt", {"attempt_id": s["attempt_id"]}, None),
                     ("get_pronunciation_word_detail", {"attempt_id": s["attempt_id"], "word": s["flagged_word"]}, None)]  # fmt: skip
        if s.get("lesson_id"):
            plan += [("get_current_listening_context", {"content_id": s["lesson_id"]}, None),
                     ("get_listening_attempt", {"content_id": s["lesson_id"]}, None)]  # fmt: skip
        if s.get("reading"):
            plan.append(("get_current_reading_context", {"content_id": s["reading"]}, None))
        if s.get("grammar_id"):
            plan += [("get_grammar_point", {"grammar_id": s["grammar_id"]}, None),
                     ("search_grammar_points", {"query": str(s["grammar_id"]).split("-")[-1] or "a"}, None)]  # fmt: skip
        for tool, args, context in plan:
            try:
                outcome = tool_turn(client, lang, tool, args, context)
                ok = (outcome["status"] == 200 and "tool_result" in outcome["events"] and outcome["events"][-1] == "done"
                      and outcome["summary"] != UNAVAILABLE)  # a refused or failed read is not a pass
                check(f"turn.{lang}.{tool}", ok, **outcome)
            except Exception as exc:
                check(f"turn.{lang}.{tool}", False, error=repr(exc)[:300], trace=traceback.format_exc()[-600:])

        # What the tools read is this learner's, in this language only (checked on the data, not the summary).
        history = invoke(lang, "get_writing_history_summary", {})
        check(f"scope.{lang}.writing", history.data.get("revision_count", 0) >= 1, data=history.data)
        if s.get("attempt_id"):
            attempt = invoke(lang, "get_pronunciation_attempt", {"attempt_id": s["attempt_id"]})
            check(f"scope.{lang}.speaking.own", attempt.data.get("found") is True)
            crossed = invoke(other, "get_pronunciation_attempt", {"attempt_id": s["attempt_id"]})
            check(f"scope.{lang}.speaking.other_language_sees_nothing", crossed.data == {"found": False}, data=crossed.data)
        saved = invoke(lang, "get_saved_word_state", {"words": list(WORDS[lang])})
        check(f"scope.{lang}.words.saved", saved.count >= 3, count=saved.count, data=saved.data)
        if s.get("lesson_id"):
            listening = invoke(lang, "get_listening_attempt", {"content_id": s["lesson_id"]})
            lines = {line.get("item_id"): line for line in listening.data.get("lines", [])}
            legacy = lines.get("legacy-line") or {}
            check(f"scope.{lang}.listening.client_score_not_verified (F-2)",
                  legacy.get("verified") is False and legacy.get("exact") is None, line=legacy)  # fmt: skip
        if s.get("reading"):
            elsewhere = invoke(other, "get_current_reading_context", {"content_id": s["reading"]})
            check(f"scope.{lang}.reading.other_language_sees_nothing", elsewhere.data == {"found": False}, data=elsewhere.data)

    # Contract behaviour through the route, without a model.
    client.post("/api/platform/language", json={"language": "en"})
    status, _, raw = turn(client, "zh", "Bạn là ai?")
    check("route.409_target_language_mismatch", status == 409, status=status, body=raw)
    scripted([])
    status, events, _ = turn(client, "en", "Bạn là ai?", {"address": {"self": "chị", "user": "em", "lang": "vi"}})
    text_ = next((d.get("text", "") for n, d in events if n == "segment_end"), "")
    check("route.S15_identity_with_address", status == 200 and text_.startswith("Chị là Orena") and "của em" in text_, text=text_)
    session = next((d.get("session_id") for n, d in events if n == "session"), None)
    client.post("/api/platform/language", json={"language": "zh"})
    status, events, raw = turn(client, "zh", "Bạn là ai?", session_id=session)
    check("route.language_switch_same_session (F-6)", status == 200, status=status, body=raw)

    counts = table_counts()
    agent_rows = {k: (counts[k] - after_seed[k]) if counts[k] is not None and after_seed[k] is not None else None
                  for k in counts}  # fmt: skip
    check("no_learner_record_written_by_agent_turns",
          all(agent_rows.get(t) in (0, None) for t in D4_TABLES), delta=agent_rows)  # fmt: skip
    check("metering_rows_written", (agent_rows.get("usage_events") or 0) > 0, delta=agent_rows.get("usage_events"))
    results.append({"check": "counts", "ok": True, "before": before, "after_seed": after_seed, "after_turns": counts})

    # 429 last: it uses up the learner's turn budget.
    scripted([])
    codes = [turn(client, "zh", "Bạn là ai?")[0] for _ in range(60)]
    check("route.429_rate_limited", 429 in codes, codes=sorted(set(codes)))


if __name__ == "__main__":
    from writing_coach.agent import learner_copy

    UNAVAILABLE = learner_copy.text("result.unavailable", interface="vi", support="vi")[1]
    BASE_RUNTIME = agent_api._runtime
    if BASE_RUNTIME is None:
        print(json.dumps({"error": "the agent is off in this stack (AGENT_ENABLED)"}))
        sys.exit(2)
    try:
        run()
    except Exception as exc:
        check("harness", False, error=repr(exc)[:400], trace=traceback.format_exc()[-1200:])
    failed = [r["check"] for r in results if not r["ok"]]
    print(json.dumps({"backbone": os.environ.get("ORENA_ACCOUNT_BACKBONE", ""), "failed": failed, "results": results},
                     ensure_ascii=False, default=str))  # fmt: skip
    sys.exit(1 if failed else 0)
