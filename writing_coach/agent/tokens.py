"""A token estimate for the hard input budget that does not undercount other writing systems.

`len(text) / 4` is about right for English and far too small for Chinese, where a character is one token or more. The
provider's own tokenizer is not reliably available (each vendor counts differently, and some only after the call), so
the budget uses a conservative estimate by script: it may over-count, so a turn is trimmed a little early, and it must
not under-count, so a turn never goes over the cost and context bound it was given.
"""

from __future__ import annotations

CJK_TOKENS_PER_CHAR = 2  # Han, kana, Hangul, full-width forms: one to two tokens each in common tokenizers
ACCENTED_CHARS_PER_TOKEN = 2  # other non-ASCII (Vietnamese and other accented Latin, Cyrillic, ...): multi-byte pieces
ASCII_CHARS_PER_TOKEN = 4

_CJK = (
    (0x2E80, 0x2FDF), (0x3000, 0x30FF), (0x3100, 0x312F), (0x3190, 0x31FF), (0x3400, 0x4DBF), (0x4E00, 0x9FFF),
    (0xAC00, 0xD7AF), (0xF900, 0xFAFF), (0xFE30, 0xFE4F), (0xFF00, 0xFFEF), (0x20000, 0x2FA1F),
)  # fmt: skip


def _is_cjk(code: int) -> bool:
    return any(low <= code <= high for low, high in _CJK)


def estimate_tokens(text: str) -> int:
    """An upper-leaning estimate of the tokens in `text`."""

    if text.isascii():
        return (len(text) + ASCII_CHARS_PER_TOKEN - 1) // ASCII_CHARS_PER_TOKEN
    ascii_chars = cjk = other = 0
    for char in text:
        code = ord(char)
        if code < 128:
            ascii_chars += 1
        elif _is_cjk(code):
            cjk += 1
        else:
            other += 1
    return (
        (ascii_chars + ASCII_CHARS_PER_TOKEN - 1) // ASCII_CHARS_PER_TOKEN
        + cjk * CJK_TOKENS_PER_CHAR
        + (other + ACCENTED_CHARS_PER_TOKEN - 1) // ACCENTED_CHARS_PER_TOKEN
    )


def fit_chars(text: str, tokens: int) -> int:
    """How many leading characters of `text` fit in `tokens` by the estimate above."""

    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if estimate_tokens(text[:middle]) <= tokens:
            low = middle
        else:
            high = middle - 1
    return low
