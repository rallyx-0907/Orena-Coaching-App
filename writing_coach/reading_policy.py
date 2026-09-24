"""The canonical Reading model's policies: judging answers, moving ability,
choosing the next article.

Pure functions, no I/O, deterministic: the same inputs always give the same
outputs, so every rule here is testable by fixing its inputs (D-075). Each
policy is versioned, and the version is stored beside what it decided:
`evaluator_version` and `ability_policy_version` on every attempt,
`selection_policy_version` on every attempt a selection served, and
`policy_version` on the ability projection. Changing a rule means a new
version string, never a silent change under an old one.

No ML. The ability rule is a bounded, Elo-style step on a level scale: the
learner's ability and a passage's difficulty are numbers on the same axis (one
unit per CEFR/HSK level), the expected score is logistic in their gap, and the
estimate moves by a step that shrinks as evidence accumulates.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

EVALUATOR_VERSION = "reading-eval/1"
ABILITY_POLICY_VERSION = "reading-ability/1"
SELECTION_POLICY_VERSION = "reading-select/1"
SUBMIT_COMMAND = "reading.attempt.submit"

# One unit per level, the same axis for English and Chinese. HSK 7-9 is one
# band above HSK 6. A level that is not here cannot be measured under this
# policy: the attempt still commits, its measurement NULL ("not measured").
_LEVEL_DIFFICULTY: Mapping[str, float] = {
    "A1": 1.0, "A2": 2.0, "B1": 3.0, "B2": 4.0, "C1": 5.0, "C2": 6.0,
    "HSK1": 1.0, "HSK2": 2.0, "HSK3": 3.0, "HSK4": 4.0, "HSK5": 5.0, "HSK6": 6.0,
    "HSK7-9": 7.0,
}
# Where an account with no measured evidence starts: A2 / HSK2. A declared
# level is a goal, never measured proficiency (ORENA_ACCOUNT_DATA_ARCHITECTURE
# §1), so it is deliberately not used as the prior.
INITIAL_ABILITY = 2.0
_ABILITY_FLOOR, _ABILITY_CEILING = 0.5, 7.5


def passage_difficulty(level: str) -> float | None:
    """The difficulty a level maps to under `ABILITY_POLICY_VERSION`."""
    return _LEVEL_DIFFICULTY.get(str(level or "").strip().upper())


# -- the evaluator -----------------------------------------------------------


@dataclass(frozen=True)
class Judged:
    """One question, judged: the answer the learner chose and whether it is right."""

    question_id: str
    question_type: str
    selected_index: int
    correct: bool

    def as_answer(self) -> dict[str, object]:
        return {"question_id": self.question_id, "selected_index": self.selected_index, "correct": self.correct}


def judge(questions: Sequence[Mapping[str, object]], selected: Mapping[str, int]) -> list[Judged]:
    """`EVALUATOR_VERSION`: an answer is right when it names the correct option.

    `questions` are the set's approved questions in rank order; `selected` maps
    each question id to the chosen option index. The caller has already checked
    that `selected` names exactly these questions with an index in range.
    """
    return [
        Judged(
            question_id=str(question["id"]),
            question_type=str(question["question_type"]),
            selected_index=int(selected[str(question["id"])]),
            correct=int(selected[str(question["id"])]) == int(question["correct_index"]),
        )
        for question in questions
    ]


def request_digest(set_id: str, selected: Mapping[str, int]) -> str:
    """SHA-256 over the canonical command - the guard against an operation id
    reused with different input. Never the identity: two distinct attempts with
    the same answers are two attempts."""
    canonical = json.dumps(
        {
            "command": SUBMIT_COMMAND,
            "set_id": str(set_id),
            "answers": sorted((str(key), int(value)) for key, value in selected.items()),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# -- the ability policy --------------------------------------------------------


@dataclass
class AbilityState:
    """What a replay of an account's attempts under one policy has produced."""

    ability: float = INITIAL_ABILITY
    consumed_through_ordinal: int = 0
    # question type -> [correct, total]
    by_question_type: dict[str, list[int]] = field(default_factory=dict)


@dataclass(frozen=True)
class Measurement:
    policy_version: str
    passage_difficulty: float
    ability_before: float
    ability_after: float


def measure(state: AbilityState, *, passage_level: str, correct: int, total: int) -> Measurement | None:
    """`ABILITY_POLICY_VERSION`: one bounded step toward the evidence.

    None when the level has no difficulty under this policy - the attempt is
    still evidence, and a later policy may measure it on replay.
    """
    difficulty = passage_difficulty(passage_level)
    if difficulty is None or total <= 0:
        return None
    before = state.ability
    expected = 1.0 / (1.0 + math.exp(-(before - difficulty)))
    # The step shrinks with the evidence behind the estimate: the attempts
    # already consumed, measured or not - a count the checkpoint carries, so a
    # rebuild reproduces it exactly.
    step = max(0.25, 1.2 / math.sqrt(1.0 + state.consumed_through_ordinal))
    after = min(_ABILITY_CEILING, max(_ABILITY_FLOOR, before + step * (correct / total - expected)))
    return Measurement(ABILITY_POLICY_VERSION, difficulty, round(before, 6), round(after, 6))


def apply(state: AbilityState, *, ordinal: int, passage_level: str, judged: Iterable[Judged]) -> Measurement | None:
    """Fold one attempt into the state, in ordinal order. The caller guarantees
    `ordinal == state.consumed_through_ordinal + 1` - applying an attempt twice
    or out of order is exactly what the checkpoint exists to prevent."""
    if ordinal != state.consumed_through_ordinal + 1:
        raise ValueError(
            f"attempt {ordinal} cannot follow checkpoint {state.consumed_through_ordinal}"
        )
    items = list(judged)
    correct = sum(1 for item in items if item.correct)
    result = measure(state, passage_level=passage_level, correct=correct, total=len(items))
    for item in items:
        tally = state.by_question_type.setdefault(item.question_type, [0, 0])
        tally[0] += 1 if item.correct else 0
        tally[1] += 1
    if result is not None:
        state.ability = result.ability_after
    state.consumed_through_ordinal = ordinal
    return result


# -- the selection policy -------------------------------------------------------


@dataclass(frozen=True)
class Candidate:
    article_id: str
    set_id: str
    level: str
    published_at: str
    question_types: frozenset[str]


@dataclass(frozen=True)
class Choice:
    article_id: str
    set_id: str
    target_difficulty: float
    probe: bool
    weak_types: tuple[str, ...]
    policy_version: str = SELECTION_POLICY_VERSION


RECENT_WINDOW = 3
PROBE_EVERY = 5
BAND = 1.0


def weak_types(by_question_type: Mapping[str, Sequence[int]]) -> tuple[str, ...]:
    """Question types answered correctly less than 60% of the time, over at
    least two questions, weakest first (ties by name)."""
    rows = [
        (tally[0] / tally[1], name)
        for name, tally in by_question_type.items()
        if len(tally) == 2 and tally[1] >= 2 and tally[0] / tally[1] < 0.6
    ]
    return tuple(name for _, name in sorted(rows))


def choose(
    *,
    ability: float,
    by_question_type: Mapping[str, Sequence[int]],
    recent_accuracy: Sequence[float],
    next_ordinal: int,
    candidates: Sequence[Candidate],
    attempted_article_ids: Iterable[str],
) -> Choice | None:
    """`SELECTION_POLICY_VERSION`: the next article, by ability, recent
    performance and skill weakness - never by chance.

    1. Ability is the starting target difficulty.
    2. Recent performance moves it: the mean accuracy of the last
       `RECENT_WINDOW` attempts at or above 0.8 moves it up half a level, at or
       below 0.4 down half a level.
    3. Every `PROBE_EVERY`-th attempt is a probe one level above.
    4. Candidates within `BAND` of the target are preferred; if none are, the
       nearest are taken.
    5. Inside that set, a candidate covering more of the learner's weak question
       types ranks first, then the one nearest the target, then the most
       recently published, then the smallest id.

    Articles the learner has already attempted are not offered again. None when
    nothing is left to offer.
    """
    seen = {str(value) for value in attempted_article_ids}
    pool = [
        (candidate, difficulty)
        for candidate in candidates
        if candidate.article_id not in seen
        and (difficulty := passage_difficulty(candidate.level)) is not None
    ]
    if not pool:
        return None
    target = ability
    window = list(recent_accuracy)[:RECENT_WINDOW]
    if window:
        mean = sum(window) / len(window)
        if mean >= 0.8:
            target += 0.5
        elif mean <= 0.4:
            target -= 0.5
    probe = next_ordinal > 0 and next_ordinal % PROBE_EVERY == 0
    if probe:
        target += 1.0
    weak = weak_types(by_question_type)
    in_band = [item for item in pool if abs(item[1] - target) <= BAND]
    if not in_band:
        nearest = min(abs(item[1] - target) for item in pool)
        in_band = [item for item in pool if abs(item[1] - target) == nearest]

    # Stable sorts, least significant key first: id, then newest published,
    # then nearest the target, then most weak types covered.
    ranked = sorted(in_band, key=lambda item: item[0].article_id)
    ranked.sort(key=lambda item: item[0].published_at, reverse=True)
    ranked.sort(key=lambda item: abs(item[1] - target))
    ranked.sort(key=lambda item: -sum(1 for name in weak if name in item[0].question_types))
    chosen, _ = ranked[0]
    return Choice(
        article_id=chosen.article_id,
        set_id=chosen.set_id,
        target_difficulty=round(target, 6),
        probe=probe,
        weak_types=weak,
    )
