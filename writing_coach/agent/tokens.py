"""A hard upper bound on the tokens of a text, for the input budget; independent of the provider's tokenizer.

The budget (`AgentLimits.max_input_tokens_per_turn`) is a cost and context bound, so it must not be undercounted for any
input - English, Chinese, Vietnamese, or an adversarial string of digits and punctuation. Every tokenizer in use (BPE
with a byte fallback) emits at least one byte per token, so the number of UTF-8 bytes is an upper bound that holds for
every language and every provider. It over-counts (about 4x for English prose) and the budget trims early: that is the
price of a bound that cannot be exceeded.

The one exception is text the repository itself ships (the fixed instruction): its tokenisation is not adversarial, so
it is counted as prose with a wide margin (`PROSE_CHARS_PER_TOKEN`).
"""

from __future__ import annotations

from collections.abc import Iterable

PROSE_CHARS_PER_TOKEN = 3  # our own English instruction runs about 4.3; counted at 3
FRAME_TOKENS = 8  # a message's role and delimiters
RESERVE_TOKENS = 256  # the provider's own framing of the request


def estimate_tokens(text: str) -> int:
    """The tokens of `text`, at most: its UTF-8 bytes."""

    return len(text.encode("utf-8"))


def prose_tokens(text: str) -> int:
    return (len(text) + PROSE_CHARS_PER_TOKEN - 1) // PROSE_CHARS_PER_TOKEN


def messages_tokens(contents: Iterable[str], *, fixed: str | None = None) -> int:
    """The bound for a request's messages (their texts); `fixed` is the one text counted as shipped prose."""

    return sum((prose_tokens(c) if fixed is not None and c == fixed else estimate_tokens(c)) + FRAME_TOKENS
               for c in contents)


def fit_chars(text: str, tokens: int) -> int:
    """How many leading characters of `text` fit in `tokens` by the bound above."""

    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if estimate_tokens(text[:middle]) <= tokens:
            low = middle
        else:
            high = middle - 1
    return low
