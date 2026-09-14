"""Shared, language-neutral orthography contracts.

Orthography is a capability of a Vocabulary Card, not a Chinese-only model.
Language adapters provide facts; this module only validates their shape and
truthfulness boundaries. In particular, an orthographic unit owns a list of
readings rather than one pronunciation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypeAlias


class OrthographyContractError(ValueError):
    """Raised when an orthography payload cannot make a truthful claim."""


OrthographicUnit: TypeAlias = dict[str, Any]
Orthography: TypeAlias = dict[str, Any]

_FACTS = frozenset(
    {"stroke_count", "radical", "components", "stroke_order", "etymology"}
)
_KNOWN_PROVENANCE_TEXT = frozenset(
    {"source", "reference", "revision", "version", "evidence_type"}
)
_EXPLANATION_KINDS = frozenset(
    {"mental_model", "mnemonic", "linguistic_explanation", "verified_etymology"}
)


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OrthographyContractError(f"{path} must be a mapping.")
    return value


def _list(value: Any, path: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise OrthographyContractError(f"{path} must be a list.")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OrthographyContractError(f"{path} must be non-empty text.")
    return value.strip()


def _present(value: Any, path: str) -> None:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise OrthographyContractError(f"{path} must contain a value.")


def _metadata(value: Any, path: str) -> None:
    if isinstance(value, str):
        if not value.strip():
            raise OrthographyContractError(f"{path} must not be blank.")
        return
    if isinstance(value, Mapping) and value:
        return
    raise OrthographyContractError(f"{path} must be text or a non-empty mapping.")


def validate_provenance(
    value: Any, path: str, *, trusted_required: bool = False
) -> None:
    provenance = _mapping(value, path)
    if not any(
        isinstance(provenance.get(key), str) and provenance[key].strip()
        for key in ("source", "reference")
    ):
        raise OrthographyContractError(
            f"{path} needs a source or reference provenance."
        )

    for key in _KNOWN_PROVENANCE_TEXT:
        if key in provenance:
            _text(provenance[key], f"{path}.{key}")
    for key in ("rights", "license"):
        if key in provenance:
            _metadata(provenance[key], f"{path}.{key}")
    if "trusted" in provenance and not isinstance(provenance["trusted"], bool):
        raise OrthographyContractError(f"{path}.trusted must be bool.")
    if trusted_required and provenance.get("trusted") is not True:
        raise OrthographyContractError(
            f"verified etymology requires trusted provenance at {path}."
        )


def _validate_binding(value: Any, path: str) -> None:
    binding = _mapping(value, path)
    _text(binding.get("kind"), f"{path}.kind")
    if not any(
        key != "kind" and item not in (None, "")
        for key, item in binding.items()
    ):
        raise OrthographyContractError(
            f"{path} must identify a sense or context being bound."
        )


def _validate_reading(value: Any, path: str) -> None:
    reading = _mapping(value, path)
    _text(reading.get("value"), f"{path}.value")
    _text(reading.get("notation"), f"{path}.notation")
    bindings = reading.get("bindings", [])
    for index, binding in enumerate(_list(bindings, f"{path}.bindings")):
        _validate_binding(binding, f"{path}.bindings[{index}]")
    if reading.get("provenance") is not None:
        validate_provenance(reading["provenance"], f"{path}.provenance")


def _validate_fact(name: str, value: Any, path: str) -> None:
    fact = _mapping(value, path)
    if "value" not in fact:
        raise OrthographyContractError(f"{path}.value is required.")
    _present(fact["value"], f"{path}.value")
    if name == "stroke_count" and (
        isinstance(fact["value"], bool)
        or not isinstance(fact["value"], int)
        or fact["value"] < 1
    ):
        raise OrthographyContractError(f"{path}.value must be a positive integer.")
    if name == "components":
        components = _list(fact["value"], f"{path}.value")
        for index, component in enumerate(components):
            component_map = _mapping(component, f"{path}.value[{index}]")
            _text(component_map.get("surface"), f"{path}.value[{index}].surface")
    if name == "stroke_order":
        representation = _mapping(fact["value"], f"{path}.value")
        _text(representation.get("representation"), f"{path}.value.representation")
    validate_provenance(
        fact.get("provenance"),
        f"{path}.provenance",
        trusted_required=name == "etymology",
    )


def _validate_unit(value: Any, path: str) -> None:
    unit = _mapping(value, path)
    _text(unit.get("surface"), f"{path}.surface")
    _text(unit.get("script"), f"{path}.script")
    _text(unit.get("unit_kind"), f"{path}.unit_kind")
    if "pronunciation" in unit:
        raise OrthographyContractError(
            f"{path}.pronunciation is not allowed; use the readings list."
        )
    for index, reading in enumerate(_list(unit.get("readings", []), f"{path}.readings")):
        _validate_reading(reading, f"{path}.readings[{index}]")
    facts = _mapping(unit.get("facts", {}), f"{path}.facts")
    unknown = set(facts) - _FACTS
    if unknown:
        raise OrthographyContractError(
            f"{path}.facts contains unsupported fields: {sorted(unknown)}"
        )
    for name, fact in facts.items():
        _validate_fact(str(name), fact, f"{path}.facts.{name}")


def validate_orthography(orthography: Mapping[str, Any]) -> None:
    """Validate a generic orthography payload without generating any facts."""

    payload = _mapping(orthography, "orthography")
    _text(payload.get("script"), "orthography.script")
    units = _list(payload.get("units"), "orthography.units")
    for index, unit in enumerate(units):
        _validate_unit(unit, f"orthography.units[{index}]")


def explanation_kinds() -> frozenset[str]:
    """Return the stable four-way explanation vocabulary for card validators."""

    return _EXPLANATION_KINDS
