"""The word tap's last layer: the router behind `ReadingLookupService(word_translation=...)` (D-195).

    word_translation_seam(selection, sentence, definitions, source, target) -> str | None

The seam is asked only after the catalogue and the dictionaries missed, and `reading_lookup` runs it behind its own
gate (bounded admission, one call per word, cancelled if it never started, a cool-down after a failure) and within
the tap budget. This adapter sends **the word only** to the `word_translation` capability: the sentence and the
dictionary senses the seam also receives are ignored, never forwarded (the owner's decision, 2026-10-14; a sentence
reaches AI only through Explain / "Why here?"). A disabled or unconfigured capability, a selection that is not a word
or short phrase, an unsupported language pair, every provider failing and a learner over the per-account brake are all
a miss (None) - never an error, never a 429.

When the tap's wait ends first, the call is not abandoned: it finishes on the seam's worker and fills the router's
cache, so the next tap on the word is instant.
"""

from __future__ import annotations

import threading
from collections import defaultdict, deque

from writing_coach.ai.base import AICapabilityError, AIProviderError
from writing_coach.ai.router import router as router_module
from writing_coach.ai.router.contract import RouterInputInvalid
from writing_coach.core.request_context import current_user_key

CAPABILITY = "word_translation"
# At most this many cache-miss calls per account in the window; over it the tap keeps its deterministic answer.
BRAKE_LIMIT = 20
BRAKE_WINDOW_SECONDS = 60.0
_BRAKE_ACCOUNTS_MAX = 5000

_lock = threading.Lock()
_spent: dict[str, deque] = defaultdict(deque)


def reset_state() -> None:
    with _lock:
        _spent.clear()


def _braked(account: str) -> bool:
    """Count one cache-miss call against the account; True when it is over its allowance (not counted then)."""

    now = router_module._clock()
    with _lock:
        if len(_spent) > _BRAKE_ACCOUNTS_MAX:
            _spent.clear()
        window = _spent[account]
        while window and window[0] <= now - BRAKE_WINDOW_SECONDS:
            window.popleft()
        if len(window) >= BRAKE_LIMIT:
            return True
        window.append(now)
        return False


def _meaning(result) -> str | None:
    meaning = str((result.output or {}).get("meaning") or "").strip()
    return meaning or None


def word_translation_seam(
    selection: str, sentence: str, definitions: list[str], source: str, target: str
) -> str | None:
    """`WordTranslationSeam` for `ReadingLookupService`. `sentence` and `definitions` are deliberately unused."""

    raw = {"text": selection, "source_language": source, "target_language": target}
    try:
        held = router_module.peek(CAPABILITY, raw)  # also the "enabled?" check: a disabled capability serves nothing
        if held is not None:
            return _meaning(held)
        if _braked(current_user_key()):
            return None
        return _meaning(router_module.route(CAPABILITY, raw))
    except (RouterInputInvalid, AICapabilityError, AIProviderError):
        return None
