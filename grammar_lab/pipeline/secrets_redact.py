"""Defense-in-depth redaction for text that might echo a credential back.

Never trust that a provider or a sandbox app cannot reflect a secret into an
error body (a stack trace, an echoed header). This does not replace sending
keys correctly (headers, never bodies or URLs); it is the last line before
any provider/HTTP error text is raised, printed, or logged.
"""

from __future__ import annotations

import os

_WATCHED_ENV_VARS = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "DEEPSEEK_API_KEY",
)

REDACTED = "***REDACTED***"


def redact(text: str) -> str:
    """Replace any exact occurrence of a currently-set watched key value."""
    for name in _WATCHED_ENV_VARS:
        value = os.environ.get(name, "").strip()
        if value and value in text:
            text = text.replace(value, REDACTED)
    return text
