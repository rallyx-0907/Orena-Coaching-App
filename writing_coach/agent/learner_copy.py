"""Server-written learner copy, each key declaring its language layer (D-080).

The agent's own words - `error.message`, `tool_call.label`, a capability's
title - are copy, not model output (spec §13). Every key names its layer, and
the text is chosen from the pack of that layer: `interface` for names and
labels, `support` for explanations and states. There is no default layer, and
no `target` copy (material never lives in copy). A support language without a
pack reads English, never the interface language (D-080).

Packs are keyed by contract codes (`zh-CN`, not `zh`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

FALLBACK_LANGUAGE = "en"
PACK_LANGUAGES = ("en", "vi", "zh-CN")


class CopyLayer(StrEnum):
    INTERFACE = "interface"
    SUPPORT = "support"


@dataclass(frozen=True)
class CopyEntry:
    layer: CopyLayer
    texts: Mapping[str, str]


def _entry(layer: CopyLayer, texts: dict[str, str]) -> CopyEntry:
    missing = [code for code in PACK_LANGUAGES if not texts.get(code)]
    if missing or set(texts) - set(PACK_LANGUAGES):
        raise ValueError(f"copy entry needs exactly {PACK_LANGUAGES}")
    return CopyEntry(layer, MappingProxyType(dict(texts)))


CATALOG: Mapping[str, CopyEntry] = MappingProxyType(
    {
        "error.provider_unavailable": _entry(
            CopyLayer.SUPPORT,
            {
                "en": "Orena is busy. Please try again shortly.",
                "vi": "Orena đang bận, thử lại sau nhé.",
                "zh-CN": "Orena 正忙，请稍后再试。",
            },
        ),
        "error.voice_unavailable": _entry(
            CopyLayer.SUPPORT,
            {
                "en": "Voice isn't available right now. Let's continue in text.",
                "vi": "Giọng nói tạm thời không dùng được. Mình tiếp tục bằng chữ nhé.",
                "zh-CN": "语音暂时不可用，我们先用文字继续。",
            },
        ),
        "error.internal": _entry(
            CopyLayer.SUPPORT,
            {
                "en": "Something went wrong. Please try again.",
                "vi": "Orena gặp sự cố. Thử lại nhé.",
                "zh-CN": "出了点问题，请重试。",
            },
        ),
    }
)


def layer_language(layer: CopyLayer, *, interface: str, support: str) -> str:
    return interface if layer is CopyLayer.INTERFACE else support


def text(key: str, *, interface: str, support: str) -> tuple[str, str]:
    """Return `(language, text)` for a key, read from its own layer's pack."""

    entry = CATALOG[key]
    language = layer_language(entry.layer, interface=interface, support=support)
    if language in entry.texts:
        return language, entry.texts[language]
    return FALLBACK_LANGUAGE, entry.texts[FALLBACK_LANGUAGE]
