"""Gate 1 live re-run (D1; PRE-104/105/110) on a running Orena, as one named test account, through the app's own code.

Approved by the owner (2026-10-19 06:30: the cost and the re-run; budget cap $0.30); run by Hermes for him. It does the
four D1 checks the owner would otherwise do signed in (OWNER_ADMIN_STEPS_8000_2026-10-19 §C.5):

1. one Orena chat turn, answered with a `done` that carries the `trace_id` the "Báo sai" link reports against;
2. a word sheet's "Why here?" (`POST /api/dictionary/word-detail`, depth full, contextual);
3. one Writing review (`POST /api/evaluate`) - it is stored on the test account, as a learner's would be;
4. a Listening meaning (`POST /api/media-learning/explain`).

Plus F1 (the system spend lock is readable and not tripped) and the spend of the run itself.

How it runs: inside the application container, importing the app, with each check called as the app's route function
under that account's learner context (the same context its signed-in requests run in). No session is made or forged,
no SQL is written by hand, no secret is read or printed. The account is found by its email through the app's own model.

    # dry run (the default): resolves the account, reads the spend lock, says what it would do; no AI call
    python scripts/gate1_live_check.py --email <test account email> --language en
    # the run itself
    python scripts/gate1_live_check.py --email <test account email> --language en --execute \\
        --actor "hermes-supervisor (on behalf of Calis)"

Prints one JSON object (no learner text beyond the fixed probe sentences, no email in full). Exit 0 every check passed
(or a clean dry run), 1 a check failed, 2 refused before running (no account, ceiling reached, over budget).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BUDGET_USD = 0.30  # the owner's cap for the whole D1 re-run
ESTIMATE_USD = 0.02  # four calls at the measured unit costs (COST_PRE402_403 §1), with room
LANGS = {"en": "en", "zh": "zh-CN"}
PROBE = {
    "en": {"sentence": "Tom missed the early train, so he waited forty minutes on a cold platform.", "word": "missed",
           "essay": ("Describe a journey that did not go as planned.",
                     "Last winter I missed the early train to work. I waited on the platform for forty minutes and "
                     "the next train was full, so I arrived late. Now I always leave home ten minutes earlier.")},
    "zh": {"sentence": "小明没赶上早班火车，他在寒冷的站台上等了四十分钟。", "word": "赶上",
           "essay": ("写一次不顺利的旅行。",
                     "去年冬天我没赶上早班火车。我在站台上等了四十分钟，下一班车也满了，所以我上班迟到了。"
                     "现在我每天都早十分钟出门。")},
}


def _mask(email: str) -> str:
    name, _, domain = email.partition("@")
    return f"{name[:2]}***@{domain}" if domain else "***"


def _account(app: Any, email: str) -> dict[str, Any] | None:
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from writing_coach.persistence.models import User

    engine = app._persistence_runtime.engine
    if engine is None:
        return None
    with Session(engine) as session:
        user = session.scalars(select(User).where(func.lower(User.email) == email.strip().casefold())).first()
        return None if user is None else {"user_key": user.user_key, "role": user.role}


def _spend() -> dict[str, Any]:
    from writing_coach.ai import spend_gate

    return spend_gate.ceiling_status()


def _check(results: list[dict], name: str, run) -> None:
    started = time.monotonic()
    try:
        ok, detail = run()
    except Exception as exc:  # noqa: BLE001 - recorded, the run goes on
        ok, detail = False, {"error": type(exc).__name__, "status": getattr(exc, "status_code", None),
                             "category": (getattr(exc, "detail", None) or {}).get("category")
                             if isinstance(getattr(exc, "detail", None), dict) else None}  # fmt: skip
    results.append({"check": name, "ok": bool(ok), "ms": int((time.monotonic() - started) * 1000), **detail})


def _chat(lang: str):
    from writing_coach.agent import api as agent_api
    from writing_coach.agent.contract import CONTRACT_VERSION
    from writing_coach.agent.schemas import TurnRequest
    from writing_coach.agent.tools import LearnerScope

    runtime = agent_api.current_runtime()
    if runtime is None:
        return False, {"reason": "agent_off"}
    body = TurnRequest.model_validate({
        "contract_version": CONTRACT_VERSION, "trigger": "message",
        "message": {"en": "What does 'missed the train' mean?", "zh": "“没赶上”是什么意思？"}[lang],
        "client": {"ui_version": "gate1-live-check", "supported_actions": ["navigate"], "supported_intents": []},
        "context": {"surface": "home", "locale": {"interface": "vi", "support": "vi", "target": LANGS[lang],
                                                  "content": LANGS[lang]}},
    })  # fmt: skip
    learner = LearnerScope.from_request_context()
    names, trace, error = [], None, None
    for event in runtime.run(body, learner, should_stop=lambda: False,
                             admission=agent_api._message_admission(body, learner)):  # fmt: skip
        names.append(event.name)
        wire = event.to_wire()
        if event.name == "done":
            trace = wire.get("trace_id")
        if event.name == "error":
            error = wire.get("class")
    answered = "segment_delta" in names or "segment_end" in names
    return (answered and trace is not None and error is None,
            {"events": sorted(set(names)), "trace_id_present": trace is not None, "error_class": error})


def _why_here(lang: str):
    from writing_coach.word_detail import WordDetailIn, word_detail

    probe = PROBE[lang]
    answer = word_detail(WordDetailIn(text=probe["word"], context=probe["sentence"], source_language=lang,
                                      target_language="vi", depth="full", contextual=True))  # fmt: skip
    why = str((answer.get("deeper") or {}).get("whyHere") or "").strip()
    return bool(why), {"why_here_present": bool(why)}


def _review(app: Any, lang: str, run_id: str):
    prompt, text = PROBE[lang]["essay"]
    # the run's id makes the text new, so a stored review of an earlier run is not reused: the provider answers
    result = app.api_evaluate(app.EssayIn(prompt=prompt, text=f"{text} ({run_id})"))
    evaluator = str(result.get("evaluator") or "")
    ok = bool(evaluator) and "fallback" not in evaluator and not result.get("reused")
    return ok, {"evaluator": evaluator or None, "reused": bool(result.get("reused")),
                "level": result.get("level_estimate")}


def _listening_meaning(lang: str):
    from writing_coach.media_interaction import MediaExplainIn, explain_media_text_route

    probe = PROBE[lang]
    answer = explain_media_text_route(MediaExplainIn(text=probe["sentence"], source_language=lang,
                                                     target_language="vi", context=probe["sentence"]))  # fmt: skip
    summary = str(answer.get("summary") or "").strip()
    return bool(summary), {"summary_present": bool(summary)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--email", required=True, help="the test account's email (printed masked)")
    parser.add_argument("--language", choices=sorted(LANGS), required=True)
    parser.add_argument("--execute", action="store_true", help="run the checks (paid AI calls); default: dry run")
    parser.add_argument("--actor", default="", help="who runs it, recorded in the output")
    args = parser.parse_args(argv)

    import app  # the running app's code and configuration, on its own database

    report: dict[str, Any] = {"run_id": uuid.uuid4().hex[:12], "actor": args.actor or None, "language": args.language,
                              "account": _mask(args.email), "execute": args.execute}  # fmt: skip
    account = _account(app, args.email)
    if account is None:
        report["refused"] = "no such account"
        print(json.dumps(report, ensure_ascii=False))
        return 2
    report["role"] = account["role"]
    before = _spend()
    report["spend_before"] = before
    cap = before.get("ceiling_usd")
    spent = before.get("spent_usd")
    # F1: the system spend lock reads and is not tripped (a reached ceiling refuses the run before any call)
    f1_ok = cap is not None and spent is not None and not before.get("reached")
    report["f1_spend_lock_readable"] = f1_ok
    if before.get("reached"):
        report["refused"] = "the system's daily AI ceiling is reached"
        print(json.dumps(report, ensure_ascii=False))
        return 2
    if cap is not None and spent is not None and float(spent) + ESTIMATE_USD > float(cap):
        report["refused"] = "this run could take the day past the ceiling"
        print(json.dumps(report, ensure_ascii=False))
        return 2
    plan = ["chat_turn", "why_here", "writing_review (stored on the test account)", "listening_meaning"]
    if not args.execute:
        report |= {"would_run": plan, "estimate_usd": ESTIMATE_USD, "budget_usd": BUDGET_USD}
        print(json.dumps(report, ensure_ascii=False))
        return 0

    from writing_coach.agent.tools import LearnerScope
    from writing_coach.agent.turn import learner_context

    results: list[dict] = []
    with learner_context(LearnerScope(user_key=account["user_key"], language=args.language)):
        _check(results, "chat_turn", lambda: _chat(args.language))
        _check(results, "why_here", lambda: _why_here(args.language))
        _check(results, "writing_review", lambda: _review(app, args.language, report["run_id"]))
        _check(results, "listening_meaning", lambda: _listening_meaning(args.language))
    after = _spend()
    report |= {"results": results, "spend_after": after}
    if before.get("spent_usd") is not None and after.get("spent_usd") is not None:
        report["run_spend_usd"] = round(float(after["spent_usd"]) - float(before["spent_usd"]), 4)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if all(item["ok"] for item in results) and f1_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
