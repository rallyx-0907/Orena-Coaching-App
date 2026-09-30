"""What makes two writing reviews the same review.

A review is expensive. It is also deterministic in everything that matters: the
same words, judged against the same task, at the same level, in the same two
languages, by the same evaluator contract, are the same review - and asking a
provider for it twice buys nothing and costs tokens every time.

So an evaluation carries the identity of what produced it, and a request
carries the identity of what it is asking for. When they match, the stored
answer is the answer.

Five things decide it, and each is here because getting it wrong shows:

  text            the words themselves. One character different is a new
                  revision and a real new review.
  learning        which language the learner is writing. Already the essay's
                  own scope, kept here so an identity is self-contained.
  support         which language the answer is written in. This is the one a
                  device-side guess got wrong before: a Vietnamese review
                  replayed under Chinese support is not this learner's review,
                  even though every other field matches.
  target          the level the review aims at, which changes the judgement.
  prompt          what the piece is for - the title and the learner's own
                  statement of the task. Two identical paragraphs written as a
                  lab report and as a note to a friend deserve different
                  readings, and the evaluator is told which.

And `contract`, which is not about this piece at all: it is the version of the
evaluator agreement itself. When the schema, the rubric or the prompt builder
changes in a way that would produce a different answer, that version changes,
every stored identity stops matching, and reviews are earned again rather than
served stale.

Identity is a hash because it is compared, not read. The parts are hashed
separately and then together, so a change in any one of them changes the
result and no concatenation ambiguity can make two different requests collide.
"""

from __future__ import annotations

import hashlib
from typing import Any

# The evaluator agreement this identity belongs to.
#
# Raise this when a change would make a stored review the wrong answer to the
# same question: the response schema, the rubric or its weights, the system
# prompt, or how the request is built. Do not raise it for a change that cannot
# alter the answer - every raise costs every learner their stored reviews.
#
# The version is effective per language pair (D-103 point 7): a change that alters the answer
# for some pairs only moves those pairs, so a learner of any other pair keeps their stored reviews
# and is never re-graded for a change that cannot touch them.
#
# v2.7 (2026-09-29): a Chinese finding explained in a support language other than Chinese is no
# longer dropped for quoting the character it teaches (support_prose_admits, 871e2b9). It alters
# the answer only when the learning language is Chinese and the explanation language is not.
EVALUATOR_CONTRACT_VERSION = "writing-evaluation-v2.7"
PREVIOUS_EVALUATOR_CONTRACT_VERSION = "writing-evaluation-v2.6"


def _language_key(code: str) -> str:
    return str(code or "").strip().casefold().replace("_", "-").split("-", 1)[0]


def v27_affects(learning_language: str, support_language: str) -> bool:
    """The pairs v2.7 changes: Chinese learning language, explanation language not Chinese."""
    return _language_key(learning_language) == "zh" and _language_key(support_language) != "zh"


def contract_version_for(learning_language: str, support_language: str) -> str:
    """The evaluator contract version in effect for one language pair."""
    if v27_affects(learning_language, support_language):
        return EVALUATOR_CONTRACT_VERSION
    return PREVIOUS_EVALUATOR_CONTRACT_VERSION

_IDENTITY_KEY = "review"


def _digest(*parts: str) -> str:
    hasher = hashlib.sha256()
    for part in parts:
        encoded = str(part or "").encode("utf-8")
        # The length prefix is what stops ("ab", "c") and ("a", "bc") from
        # hashing alike.
        hasher.update(str(len(encoded)).encode("ascii"))
        hasher.update(b":")
        hasher.update(encoded)
    return hasher.hexdigest()


def review_identity(
    *,
    text: str,
    learning_language: str,
    support_language: str,
    target_level: str = "",
    prompt: str = "",
    contract_version: str | None = None,
) -> dict[str, str]:
    """The identity of one review, as it is asked for and as it is stored.

    Without an explicit `contract_version` the version in effect for this language pair is used
    (`contract_version_for`), so an unaffected pair keeps matching its stored reviews.
    """
    if contract_version is None:
        contract_version = contract_version_for(learning_language, support_language)
    normalized_learning = str(learning_language or "").casefold().replace("_", "-")
    normalized_support = str(support_language or "").casefold().replace("_", "-")
    normalized_target = str(target_level or "").strip().upper()
    return {
        "contract": str(contract_version),
        "learning_language": normalized_learning,
        "support_language": normalized_support,
        "target_level": normalized_target,
        "text_hash": _digest(text or ""),
        "prompt_hash": _digest(prompt or ""),
        "fingerprint": _digest(
            contract_version,
            normalized_learning,
            normalized_support,
            normalized_target,
            text or "",
            prompt or "",
        ),
    }


def identity_of_stored(module_data: Any) -> dict[str, str]:
    """The identity a stored essay was reviewed under, or an empty one.

    Essays written before reviews carried an identity have none, and an empty
    identity matches nothing - which is the safe answer: they are re-reviewed
    when asked for rather than served as though their language were known.
    """
    if not isinstance(module_data, dict):
        return {}
    stored = module_data.get(_IDENTITY_KEY)
    return {str(k): str(v) for k, v in stored.items()} if isinstance(stored, dict) else {}


def same_review(wanted: dict[str, str], stored: dict[str, str]) -> bool:
    """Whether a stored evaluation answers the review being asked for."""
    if not wanted or not stored:
        return False
    return bool(wanted.get("fingerprint")) and wanted["fingerprint"] == stored.get("fingerprint")
