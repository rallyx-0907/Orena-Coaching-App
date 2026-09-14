"""Backend contract for learner support-language output."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


class UnsupportedSupportLanguage(ValueError):
    """Raised when a requested support language is outside the product contract."""


@dataclass(frozen=True)
class SupportLanguageDefinition:
    """Prompt-safe metadata for one supported learner-facing language."""

    code: str
    translation_label: str
    script_family: str = "latin"


# Orena is globally designed. Every entry needs a translation_label because the
# label is what the translation prompt is built from, so this list is the real
# capability boundary - it is not the data model, and it is not a claim that any
# learner speaks any of these.
_DEFINITIONS = (
    SupportLanguageDefinition("en", "English"),
    SupportLanguageDefinition("vi", "Vietnamese"),
    SupportLanguageDefinition("zh", "Simplified Chinese", "cjk"),
    SupportLanguageDefinition("ja", "Japanese", "cjk"),
    SupportLanguageDefinition("ko", "Korean", "cjk"),
    SupportLanguageDefinition("es", "Spanish"),
    SupportLanguageDefinition("fr", "French"),
    SupportLanguageDefinition("de", "German"),
    SupportLanguageDefinition("pt", "Portuguese"),
    SupportLanguageDefinition("ru", "Russian"),
    SupportLanguageDefinition("id", "Indonesian"),
    SupportLanguageDefinition("th", "Thai"),
)

SUPPORT_LANGUAGES: Mapping[str, SupportLanguageDefinition] = MappingProxyType(
    {definition.code: definition for definition in _DEFINITIONS}
)


def all_support_languages() -> tuple[SupportLanguageDefinition, ...]:
    return _DEFINITIONS


def support_language(code: str | None) -> SupportLanguageDefinition | None:
    normalized = str(code or "").strip().casefold()
    return SUPPORT_LANGUAGES.get(normalized)


def normalize_support_language(code: str | None) -> str:
    definition = support_language(code)
    if definition is None:
        raise UnsupportedSupportLanguage("Choose a valid support language.")
    return definition.code


def support_language_uses_cjk(code: str | None) -> bool:
    """Return whether support copy may contain the CJK script family."""

    definition = support_language(code)
    return bool(definition and definition.script_family == "cjk")


# --- Resolution -------------------------------------------------------------
#
# LEARNING_LANGUAGE, SUPPORT_LANGUAGE and UI_LOCALE are three distinct concepts.
# This resolves the second one, and it is the only place that decides it.

import os  # noqa: E402
import re  # noqa: E402

# BCP-47-shaped, deliberately broader than the list above: a learner's stored
# identity is a language, not an enum of today's translation coverage.
BCP47 = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$")

DEFAULT_SUPPORT_LANGUAGE_ENV = "DEFAULT_SUPPORT_LANGUAGE"
NEUTRAL_SUPPORT_LANGUAGE = "en"

AVAILABLE_SUPPORT_LANGUAGES: tuple[str, ...] = tuple(
    definition.code for definition in _DEFINITIONS
)


def normalize_language_tag(value: object) -> str:
    """A BCP-47-shaped tag in canonical lower case, or "" when unusable."""

    code = str(value or "").strip().replace("_", "-").casefold()
    return code if BCP47.fullmatch(code) else ""


def is_available(value: object) -> bool:
    """Whether Orena can currently produce support text in this language."""

    return normalize_language_tag(value) in AVAILABLE_SUPPORT_LANGUAGES


def configured_default(env: object = None) -> str:
    """The deployment's neutral default. Configuration, not an inference."""

    values = os.environ if env is None else env
    candidate = normalize_language_tag(values.get(DEFAULT_SUPPORT_LANGUAGE_ENV, ""))
    return candidate if candidate in AVAILABLE_SUPPORT_LANGUAGES else NEUTRAL_SUPPORT_LANGUAGE


def resolve_support_language(
    profile_value: object = None,
    requested: object = None,
    env: object = None,
) -> str:
    """Stored profile preference, then an explicit selection, then the default.

    A well-formed but unsupported tag falls through rather than being served as
    if Orena could translate into it.
    """

    for candidate in (profile_value, requested):
        code = normalize_language_tag(candidate)
        if code and code in AVAILABLE_SUPPORT_LANGUAGES:
            return code
    return configured_default(env)
