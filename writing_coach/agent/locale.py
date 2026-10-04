"""Language codes at the agent's edge (D-079 layers, contract §3).

The contract speaks BCP-47 and writes Chinese as `zh-CN` only; the backend's
registries key Chinese as `zh`. That one difference is mapped here, in both
directions, and nowhere else in the agent. Which codes each layer accepts is
read from the registry that owns the layer, not listed again:

- target: the enabled learning languages (`core.language_registry`);
- support: the languages Orena can explain in (`core.support_languages`);
- interface: the languages the interface is written in (`account_profile`);
- content: the language of the material in view, target or support.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from writing_coach.account_profile import ACCOUNT_SETTINGS
from writing_coach.core.language_registry import all_languages
from writing_coach.core.support_languages import AVAILABLE_SUPPORT_LANGUAGES

_CONTRACT_BY_INTERNAL = MappingProxyType({"zh": "zh-CN"})
_INTERNAL_BY_CONTRACT = MappingProxyType({v: k for k, v in _CONTRACT_BY_INTERNAL.items()})


class UnsupportedLanguage(ValueError):
    """A code outside the contract, or outside the layer it was sent for."""


def to_contract(internal: str) -> str:
    return _CONTRACT_BY_INTERNAL.get(internal, internal)


def to_internal(contract_code: str) -> str:
    if contract_code in _CONTRACT_BY_INTERNAL:
        # `zh` is an internal code; the contract accepts only `zh-CN`.
        raise UnsupportedLanguage(f"{contract_code!r} is not a contract language code")
    return _INTERNAL_BY_CONTRACT.get(contract_code, contract_code)


def target_languages() -> frozenset[str]:
    return frozenset(to_contract(profile.code) for profile in all_languages() if profile.enabled)


def support_languages() -> frozenset[str]:
    return frozenset(to_contract(code) for code in AVAILABLE_SUPPORT_LANGUAGES)


def interface_languages() -> frozenset[str]:
    allowed = ACCOUNT_SETTINGS["interface_language"].allowed or ()
    return frozenset(to_contract(code) for code in allowed)


def content_languages() -> frozenset[str]:
    return target_languages() | support_languages()


LAYERS = ("interface", "support", "target", "content")
_LAYER_SETS = MappingProxyType(
    {
        "interface": interface_languages,
        "support": support_languages,
        "target": target_languages,
        "content": content_languages,
    }
)


def require_layer_language(layer: str, contract_code: str) -> str:
    """Return the code when the layer accepts it; raise otherwise."""

    allowed = _LAYER_SETS[layer]()
    if contract_code not in allowed:
        raise UnsupportedLanguage(f"{contract_code!r} is not a {layer} language")
    return contract_code


@dataclass(frozen=True)
class InternalLocale:
    """The request's four layers in the codes the backend's services use."""

    interface: str
    support: str
    target: str
    content: str | None
