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
from collections import OrderedDict, deque
from datetime import UTC, datetime, timedelta

from writing_coach.ai import routing
from writing_coach.ai.base import AICapabilityError, AIProviderError
from writing_coach.ai.router import router as router_module
from writing_coach.ai.router.contract import RouterInputInvalid
from writing_coach.core.request_context import current_user_key

CAPABILITY = "word_translation"
# At most this many cache-miss calls per account in the window; over it the tap keeps its deterministic answer.
BRAKE_LIMIT = 20
BRAKE_WINDOW_SECONDS = 60.0
_BRAKE_ACCOUNTS_MAX = 5000

# Translate-ahead (D-199) is paid for from its own budget, never from a learner's brake and never from a tap's: at
# most this many cache-miss router calls a day per worker process, and after the provider side reports itself
# unavailable (every pool entry failed or is cooling down, a 429 among them) it asks nobody for PAUSE_SECONDS.
#
# Tuned for an UNFUNDED OpenRouter free tier (about 50 free-model requests a day for the whole account, shared with
# taps and Admin tests; owner decision 2026-10-14: free models only): at most 25 prefetch calls a day per process,
# which leaves the rest for taps. Funding the account (1000 a day) allows raising this and
# `reading_prefetch.MAX_WORDS_PER_ARTICLE`; both are plain constants.
PREFETCH_DAILY_CALLS = 25
PREFETCH_PAUSE_SECONDS = 120.0

# Background calls keep their own provider-health record: a 429 that a prefetch meets cools down the prefetch's view of
# the provider, never the one a learner's tap reads (the pool entries share a provider id, so a shared record would
# let a background burst take the tap's primary away). Prefetch in turn yields whenever the shared record says the
# provider is cooling down, and pauses after ANY failed attempt, even one a standby then answered.
_prefetch_health = routing.ProviderHealth(lambda: routing.monotonic())

_lock = threading.Lock()
_spent: OrderedDict[str, deque] = OrderedDict()
_prefetch_day = ""
_prefetch_calls = 0
_prefetch_paused_until = 0.0


class PrefetchRefused(Exception):
    """Translate-ahead is not allowed to ask right now (paused after a provider failure, or over the day's budget)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def reset_state() -> None:
    global _prefetch_day, _prefetch_calls, _prefetch_paused_until
    with _lock:
        _spent.clear()
        _prefetch_day, _prefetch_calls, _prefetch_paused_until = "", 0, 0.0
    _prefetch_health.reset()


def prefetch_enabled() -> bool:
    """Whether the `word_translation` capability is enabled (the configuration the router reads, briefly held)."""

    try:
        router_module.load_config(CAPABILITY)
    except AICapabilityError:
        return False
    return True


def prefetch_paused() -> bool:
    with _lock:
        return _prefetch_paused_until > router_module._clock()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _seconds_to_next_utc_day() -> float:
    now = _utc_now()
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(PREFETCH_PAUSE_SECONDS, (tomorrow - now).total_seconds())


def pause_prefetch(seconds: float | None = None) -> None:
    global _prefetch_paused_until
    with _lock:
        until = router_module._clock() + (PREFETCH_PAUSE_SECONDS if seconds is None else seconds)
        _prefetch_paused_until = max(_prefetch_paused_until, until)


def _allowance_spent(error: BaseException) -> bool:
    """A 429 that says the account has no requests left (`X-RateLimit-Remaining: 0`), as opposed to a busy upstream."""

    limit = getattr(error, "rate_limit", None) or {}
    return getattr(error, "status_code", None) == 429 and limit.get("requests_remaining") == 0


def _admit_prefetch_call() -> None:
    """Count one cache-miss call against the day's budget, or refuse. Counts only; never a word."""

    global _prefetch_day, _prefetch_calls
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    with _lock:
        if _prefetch_paused_until > router_module._clock():
            raise PrefetchRefused("paused")
        if today != _prefetch_day:
            _prefetch_day, _prefetch_calls = today, 0
        if _prefetch_calls >= PREFETCH_DAILY_CALLS:
            raise PrefetchRefused("daily_cap")
        _prefetch_calls += 1


def _braked(account: str) -> bool:
    """Count one cache-miss call against the account; True when it is over its allowance (not counted then)."""

    now = router_module._clock()
    with _lock:
        window = _spent.get(account)
        if window is None:
            window = _spent[account] = deque()
            while len(_spent) > _BRAKE_ACCOUNTS_MAX:
                _spent.popitem(last=False)  # the least recently used account only; the others keep their counts
        _spent.move_to_end(account)
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


def word_translation_prefetch(selection: str, source: str, target: str) -> str | None:
    """`WordTranslationPrefetchSeam` for `ReadingLookupService` (D-199): translate one word ahead of any tap.

    The same contract, validator, shared cache and single flight as a tap (`public_reference`, the word only), but
    no learner is charged: the per-account brake is not touched, and its own daily budget and pause apply instead.
    A cached answer costs nothing. Raises `PrefetchRefused` (paused / over the day's budget), a disabled capability's
    `AICapabilityError`, and the provider error; the caller stops its batch on those and counts the rest as one failure.
    """

    raw = {"text": selection, "source_language": source, "target_language": target}
    try:
        held = router_module.peek(CAPABILITY, raw)
        if held is not None:
            return _meaning(held)
        _yield_to_taps()
        _admit_prefetch_call()
        router_module.count_event(CAPABILITY, "prefetch_calls")
        routed = router_module.route(CAPABILITY, raw, health=_prefetch_health, paid_standby=False)  # free pool only
        if routed.fell_back:  # a rate limit or a timeout on the way: slow down even though an answer came
            pause_prefetch()
        return _meaning(routed)
    except AIProviderError as exc:
        if _allowance_spent(exc):
            pause_prefetch(_seconds_to_next_utc_day())  # the day's free allowance is gone: ask nobody until it resets
        elif _pool_unavailable(exc):
            pause_prefetch()
        raise
    except RouterInputInvalid:
        return None


def _yield_to_taps() -> None:
    """Refuse (and pause) while the shared health record says a pool provider is cooling down: that is the tap's pool."""

    config = router_module.load_config(CAPABILITY)
    shared = routing.provider_health.snapshot()
    for provider in {config.provider, config.backup_provider}:
        state = shared.get(provider, {}) if provider else {}
        if state.get("cooling_down") and state.get("seconds_remaining", 0) > 0:  # an expired entry does not count
            pause_prefetch()
            raise PrefetchRefused("pool_cooling_down")


def _pool_unavailable(error: BaseException) -> bool:
    """The pool itself failed or is cooling down (a 429, a 5xx, a timeout, every entry skipped), as opposed to one word
    that no entry could answer validly or "this word failed a moment ago" (no attempt was made)."""

    attempts = list(getattr(error, "attempts", ()) or ())
    return bool(attempts) and all(getattr(a, "reason", "") != "invalid_output" for a in attempts)


def prefetch_should_stop(error: BaseException) -> bool:
    """Whether a batch of translate-ahead calls should stop on `error`: paused, over budget, the capability turned off,
    or the whole pool unavailable. A single word that failed or answered badly does not stop the batch."""

    if isinstance(error, (PrefetchRefused, AICapabilityError)):
        return True
    return isinstance(error, AIProviderError) and _pool_unavailable(error)
