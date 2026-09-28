"""Coaching read tools (Slice 3): the learner's snapshot, what their records show is hard, what to do next.

Every number here is one a record holds. A domain that cannot be read is
`null` with its state named, never 0; a measure nothing records is absent,
never estimated (human direction 2026-09-28; spec §24). Nothing is averaged
across domains and no level is computed (R4). Names are the interface
language's, never internal keys (agent/labels.py).

- `build_learning_snapshot` - spec §24 over the app's own `/api/learner-summary`
  (30-day window) and the review queue's due count: per domain its state, its
  activity count and its latest measurements. A demonstration evaluator's
  number is not a measurement and is left out. The opening turn (S13) is built
  on it by the server, not by a model call.
- `get_learning_weaknesses` - deterministic counts over the learner's records:
  writing error categories that recur, words the pronunciation provider
  flagged more than once, dictation lines not yet matched or revealed, reading
  checks answered wrong, saved words forgotten repeatedly. Grammar has no
  mistake store: it is `null`, said so, not guessed.
- `get_recommended_next_activities` - the order is the backend's, never the
  model's: due words first, then the app's cross-skill cue (`/api/cross-skill-cue`,
  deterministic). Each carries the facts behind it and the ids a `navigate`
  may name; the model only explains.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict

from writing_coach import becoming_library
from writing_coach.agent.labels import (
    ACTIVITY,
    DOMAIN,
    DOMAIN_STATUS,
    MEASURE,
    category_label,
    label,
    pronunciation_label,
)
from writing_coach.agent.read_tools import BOTH, WritingHistoryReader, _clip, _fit
from writing_coach.agent.skill_tools import (
    ReadingEvidence,
    SpeakingAttempts,
    _empty,
    flagged,
)
from writing_coach.agent.tools import AgentTool, LearnerScope, ToolEvidence, ToolPermission, ToolResult

LearnerSummaryReader = Callable[[str], Mapping[str, Any]]  # learner_summary_api.summary(window)
CrossSkillCueReader = Callable[[], Mapping[str, Any]]  # app.becoming_cross_skill_cue_get()
ListeningRecent = Callable[[int], Sequence[Mapping[str, Any]]]  # list_recent_listening_progress_records(limit)

WINDOW = "30d"
# The spec's names (§24) for the summary's domains: `language` is the snapshot's vocabulary.
SNAPSHOT_DOMAINS = {"reading": "reading", "listening": "listening", "speaking": "speaking", "writing": "writing",
                    "language": "vocabulary", "grammar": "grammar"}  # fmt: skip
RECURRING = 2  # a pattern is "recurring" from its second record on
VOCABULARY_PAGE = 200
MAX_ITEMS = 5


def _unavailable_summary(window: str) -> Mapping[str, Any]:
    raise RuntimeError("the learner summary is not configured")


def _no_cue() -> Mapping[str, Any]:
    return {"available": False}


class NoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- the snapshot ----------------------------------------------------------------------------


def _measurement(observation: Mapping[str, Any], interface: str) -> dict[str, Any] | None:
    """One observation as the model may retell it; None for a number that is not a measurement."""

    if observation.get("synthetic"):
        return None
    value = observation.get("value")
    if isinstance(value, Mapping):  # speaking dimensions, or a reading check's {correct, total}
        if set(value) >= {"correct", "total"}:
            value = {"correct": value.get("correct"), "total": value.get("total")}
        else:
            value = {label(MEASURE, name, interface) or name: score for name, score in value.items()}
    return {
        "measure": label(MEASURE, observation.get("measure"), interface),
        "value": value,
        "assisted": observation.get("assisted"),  # None: not recorded; True: the answer was shown first
        "observed_at": observation.get("observedAt"),
    }


def snapshot(summary: Mapping[str, Any], due: int | None, target: str, interface: str) -> dict[str, Any]:
    domains = summary.get("domains") if isinstance(summary.get("domains"), Mapping) else {}
    skills: dict[str, Any] = {}
    recent: list[dict[str, Any]] = []
    for key, name in SNAPSHOT_DOMAINS.items():
        domain = domains.get(key)
        if not isinstance(domain, Mapping):
            continue
        status = str(domain.get("status") or "unavailable")
        entry: dict[str, Any] = {"name": label(DOMAIN, name, interface), "state": label(DOMAIN_STATUS, status, interface)}
        if status == "unavailable":
            entry.update(activity=None, latest=None)  # unknown is not zero
        else:
            activity = domain.get("activity") if isinstance(domain.get("activity"), Mapping) else {}
            entry["activity"] = {
                "what": label(ACTIVITY, activity.get("label"), interface),
                "count": activity.get("count"),
                "at_least": activity.get("countKind") == "at_least",  # a bounded read: the count is a lower bound
                "last_at": activity.get("lastObservedAt"),
            }
            latest = [m for m in (_measurement(o, interface) for o in domain.get("observations") or ()) if m]
            entry["latest"] = latest
            recent += [{"skill": entry["name"], **m} for m in latest if m.get("observed_at")]
        skills[name] = entry
    recent.sort(key=lambda item: str(item.get("observed_at")), reverse=True)
    return {
        "target": target,
        "window_days": 30,
        "skill_summary": skills,
        "review_due": due,  # None when the review queue could not be read
        "recent_sessions": recent[:MAX_ITEMS],
        "note": "No overall level: skills are not averaged into one score. A missing value was not measured.",
    }


def _due_count() -> int | None:
    try:
        counts = becoming_library.library_summary().get("summary") or {}
        return int(counts.get("due") or 0)
    except Exception:
        return None


def learning_snapshot(read_summary: LearnerSummaryReader, learner: LearnerScope) -> dict[str, Any]:
    """The snapshot the tool returns and the opening turn is built on."""

    try:
        summary = read_summary(WINDOW)
    except Exception:
        summary = {"domains": {key: {"status": "unavailable"} for key in SNAPSHOT_DOMAINS}}
    return snapshot(summary, _due_count(), learner.contract_language, learner.interface)


def _snapshot_tool(read_summary: LearnerSummaryReader) -> Callable[[LearnerScope, NoArguments], ToolResult]:
    def handler(learner: LearnerScope, args: NoArguments) -> ToolResult:
        data = learning_snapshot(read_summary, learner)
        current = [key for key, entry in data["skill_summary"].items() if entry.get("latest")]
        return ToolResult(
            summary=f"snapshot of {len(data['skill_summary'])} skills over 30 days; review due {data['review_due']}",
            data=data,
            evidence=tuple(
                ToolEvidence(
                    id=f"skill_{key}",
                    source="learner_summary",
                    ref={"domain": key, "window": WINDOW},
                    excerpt={"activity": data["skill_summary"][key]["activity"]},
                )
                for key in current
            ),
            count=len(current),
        )

    return handler


# --- weaknesses: counts over records, nothing inferred -----------------------------------------


def weaknesses(
    *,
    history: Mapping[str, Any] | None,
    attempts: Sequence[Mapping[str, Any]] | None,
    listening: Sequence[Mapping[str, Any]] | None,
    reading: Sequence[Mapping[str, Any]] | None,
    vocabulary: Sequence[Mapping[str, Any]] | None,
    interface: str,
) -> dict[str, Any]:
    """Each skill: the patterns its records show at least twice, with their counts; None when unread."""

    found: dict[str, Any] = {}
    if history is None:
        found["writing"] = None
    else:
        found["writing"] = [
            {"category": category_label(item.get("category"), interface), "times": int(item.get("total") or 0),
             "recent_times": int(item.get("newer") or 0)}  # fmt: skip
            for item in sorted(history.get("items") or (), key=lambda i: -int(i.get("total") or 0))
            if int(item.get("total") or 0) >= RECURRING
        ][:MAX_ITEMS]
    if attempts is None:
        found["speaking"] = None
    else:
        words: Counter[str] = Counter()
        kinds: dict[str, Counter[str]] = {}
        for attempt in attempts:
            evidence = attempt.get("evidence") if isinstance(attempt.get("evidence"), Mapping) else {}
            pronunciation = evidence.get("pronunciation") if isinstance(evidence.get("pronunciation"), Mapping) else {}
            for word in pronunciation.get("words") or ():
                if isinstance(word, Mapping) and flagged(word) and word.get("word"):
                    words[str(word["word"])] += 1
                    kinds.setdefault(str(word["word"]), Counter())[str(word.get("error_type"))] += 1
        found["speaking"] = [
            {"word": word, "times_flagged": times,
             "most_often": pronunciation_label(kinds[word].most_common(1)[0][0], interface)}  # fmt: skip
            for word, times in words.most_common(MAX_ITEMS)
            if times >= RECURRING
        ]
    if listening is None:
        found["listening"] = None
    else:
        worked = [row for row in listening if int(row.get("checked_attempt_count") or 0) or row.get("revealed")]
        found["listening"] = {
            "lines_worked_on": len(worked),
            "not_yet_exact": sum(1 for row in worked if not row.get("best_exact")),
            "answer_revealed": sum(1 for row in worked if row.get("revealed")),
        } if worked else []  # fmt: skip
    if reading is None:
        found["reading"] = None
    else:
        answered = [row for row in reading if int(row.get("total") or 0) > 0]
        wrong = [row for row in answered if int(row.get("correct_count") or 0) < int(row.get("total") or 0)]
        found["reading"] = {
            "checks_answered": len(answered),
            "with_wrong_answers": len(wrong),
            "questions_wrong": sum(int(r.get("total") or 0) - int(r.get("correct_count") or 0) for r in wrong),
        } if answered else []  # fmt: skip
    if vocabulary is None:
        found["vocabulary"] = None
    else:
        forgotten = sorted((row for row in vocabulary if int(row.get("lapse_count") or 0) >= RECURRING),
                           key=lambda row: -int(row.get("lapse_count") or 0))  # fmt: skip
        found["vocabulary"] = [
            {"word": _clip(row.get("word"), 60), "times_forgotten": int(row.get("lapse_count") or 0)}
            for row in forgotten[:MAX_ITEMS]
        ]
    found["grammar"] = None  # no store of mistakes per grammar point: not measured, not guessed
    return found


def _read(read: Callable[[], Any]) -> Any:
    try:
        return read()
    except Exception:
        return None  # not readable here: unknown, never "no weakness"


def _weaknesses_tool(
    history: WritingHistoryReader,
    attempts: SpeakingAttempts,
    listening: ListeningRecent,
    reading: ReadingEvidence,
) -> Callable[[LearnerScope, NoArguments], ToolResult]:
    def handler(learner: LearnerScope, args: NoArguments) -> ToolResult:
        vocabulary_page = _read(lambda: becoming_library.list_library_vocabulary(limit=VOCABULARY_PAGE))
        data = weaknesses(
            history=_read(history),
            attempts=_read(lambda: list(attempts(50))),
            listening=_read(lambda: list(listening(100))),
            reading=_read(lambda: list(reading(30))),
            vocabulary=(vocabulary_page or {}).get("items") if vocabulary_page is not None else None,
            interface=learner.interface,
        )
        named = {key: label(DOMAIN, key, learner.interface) for key in data}
        found = [key for key, value in data.items() if value]
        return ToolResult(
            summary=f"recurring patterns in {len(found)} skills",
            data={
                "by_skill": {named[key]: value for key, value in data.items()},
                "note": "Counts of what the records show at least twice. null: not measured here - never 'no problem'.",
            },
            evidence=tuple(
                ToolEvidence(id=f"weak_{key}", source="learner_summary", ref={"domain": key, "kind": "recurring"},
                             excerpt={"items": len(data[key]) if isinstance(data[key], list) else 1})  # fmt: skip
                for key in found
            ),
            count=len(found),
        )

    return handler


# --- next activities: the backend's order, the model's words -----------------------------------


def recommendations(due: int | None, cue: Mapping[str, Any], interface: str) -> list[dict[str, Any]]:
    """In order: due words, then the app's cross-skill cue. Each with its facts and the ids it may be opened by."""

    out: list[dict[str, Any]] = []
    if due:
        out.append({"rank": 1, "activity": label(DOMAIN, "vocabulary", interface), "why": {"words_due": due},
                    "open": {"intent": "vocabulary.review_due"}, "action": {"type": "start_review", "scope": "due"}})  # fmt: skip
    action = cue.get("action") if cue.get("available") is True and isinstance(cue.get("action"), Mapping) else None
    if action:
        kind = str(action.get("kind"))
        opened: dict[str, Any] | None = None
        if kind == "review" and action.get("essay_id"):
            opened = {"intent": "writing.review", "essay_id": str(action["essay_id"])}
        elif kind == "reading" and action.get("article_id"):
            opened = {"intent": "reading.workspace", "content_id": f"article:{action['article_id']}"}
        elif kind == "speaking" and action.get("asset_id"):
            opened = {"intent": "speaking.workspace", "content_id": str(action["asset_id"])}
        # A listening cue names a media asset, not the lesson the UI opens: it is said in words, not navigated.
        domain = {"review": "writing"}.get(kind, kind)
        out.append({"rank": len(out) + 1, "activity": label(DOMAIN, domain, interface),
                    "why": {"from_your_record": _clip(cue.get("evidence"), 160)}, "open": opened})  # fmt: skip
    return out


def _recommend_tool(read_cue: CrossSkillCueReader) -> Callable[[LearnerScope, NoArguments], ToolResult]:
    def handler(learner: LearnerScope, args: NoArguments) -> ToolResult:
        cue = _read(read_cue) or {}
        items = recommendations(_due_count(), cue, learner.interface)

        def build(keep: int) -> ToolResult:
            kept = items[:keep]
            return ToolResult(
                summary=f"{len(items)} next activities, in the backend's order",
                data={
                    "next": kept,
                    "note": "The order is decided here from the records; explain it, do not reorder or add to it.",
                },
                evidence=tuple(
                    ToolEvidence(id=f"next{item['rank']}", source="learner_summary",
                                 ref={"rank": item["rank"], **({"intent": item["open"]["intent"]} if item.get("open") else {})},
                                 excerpt={"why": item["why"]})  # fmt: skip
                    for item in kept
                ),
                count=len(items),
            )

        return _fit(build, len(items))

    return handler


def coaching_tools(
    *,
    learner_summary: LearnerSummaryReader = _unavailable_summary,
    cross_skill_cue: CrossSkillCueReader = _no_cue,
    writing_history: WritingHistoryReader,
    speaking_attempts: SpeakingAttempts = _empty,
    listening_recent: ListeningRecent = _empty,
    reading_evidence: ReadingEvidence = _empty,
) -> tuple[AgentTool, ...]:
    return (
        AgentTool(
            name="build_learning_snapshot",
            description="The learner's 30-day snapshot per skill: state, activity count, latest measurements, and "
            "how many words are due. No overall level; a missing value was not measured.",
            input_model=NoArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by="writing_coach.learner_summary:learner_summary",
            languages=BOTH,
            label_key="tool.build_learning_snapshot",
            handler=_snapshot_tool(learner_summary),
        ),
        AgentTool(
            name="get_learning_weaknesses",
            description="What the learner's own records show more than once, per skill, with counts: recurring "
            "writing errors, words flagged in speaking, dictation lines not yet exact, reading answers wrong, words "
            "forgotten. null means not measured.",
            input_model=NoArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by="writing_coach.agent.coaching:weaknesses",
            languages=BOTH,
            label_key="tool.get_learning_weaknesses",
            handler=_weaknesses_tool(writing_history, speaking_attempts, listening_recent, reading_evidence),
        ),
        AgentTool(
            name="get_recommended_next_activities",
            description="What to do next, in an order decided from the records (due words first, then the app's "
            "cross-skill cue), with the facts behind each and the ids to open it by. Explain it; do not reorder.",
            input_model=NoArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by="writing_coach.cross_skill_transfer:select_cross_skill_cue",
            languages=BOTH,
            label_key="tool.get_recommended_next_activities",
            handler=_recommend_tool(cross_skill_cue),
        ),
    )

