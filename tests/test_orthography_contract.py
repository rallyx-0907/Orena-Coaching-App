from __future__ import annotations

import pytest

from writing_coach.orthography import OrthographyContractError, validate_orthography


def test_accepts_non_chinese_units_and_multiple_context_bound_readings() -> None:
    validate_orthography(
        {
            "script": "arabic",
            "units": [
                {
                    "surface": "ع",
                    "script": "arabic",
                    "unit_kind": "letter-form",
                    "readings": [
                        {
                            "value": "ʿ",
                            "notation": "latin",
                            "bindings": [{"kind": "context", "text": "عَلَم"}],
                        },
                        {
                            "value": "a",
                            "notation": "latin",
                            "bindings": [{"kind": "context", "text": "عَلِمَ"}],
                        },
                    ],
                }
            ],
        }
    )


def test_accepts_assertion_level_provenance_and_extensible_metadata() -> None:
    validate_orthography(
        {
            "script": "han",
            "units": [
                {
                    "surface": "学",
                    "script": "han",
                    "unit_kind": "character",
                    "facts": {
                        "stroke_count": {
                            "value": 8,
                            "provenance": {
                                "source": "vendor",
                                "version": "1",
                                "evidence_type": "dataset",
                                "license": "MIT",
                            },
                        },
                        "components": {
                            "value": [{"surface": "子"}],
                            "provenance": {
                                "reference": "editorial-record",
                                "revision": "r2",
                            },
                        },
                    },
                }
            ],
        }
    )


def test_rejects_verified_etymology_without_trusted_provenance() -> None:
    with pytest.raises(OrthographyContractError, match="trusted provenance"):
        validate_orthography(
            {
                "script": "han",
                "units": [
                    {
                        "surface": "学",
                        "script": "han",
                        "unit_kind": "character",
                        "facts": {
                            "etymology": {
                                "value": "a story",
                                "provenance": {"source": "none"},
                            }
                        },
                    }
                ],
            }
        )


def test_rejects_missing_or_guessed_factual_provenance() -> None:
    with pytest.raises(OrthographyContractError, match="provenance"):
        validate_orthography(
            {
                "script": "han",
                "units": [
                    {
                        "surface": "学",
                        "script": "han",
                        "unit_kind": "character",
                        "facts": {"stroke_count": {"value": 8}},
                    }
                ],
            }
        )


def test_accepts_trusted_verified_etymology_as_a_distinct_assertion() -> None:
    validate_orthography(
        {
            "script": "han",
            "units": [
                {
                    "surface": "学",
                    "script": "han",
                    "unit_kind": "character",
                    "facts": {
                        "etymology": {
                            "value": "Documented historical account.",
                            "provenance": {
                                "reference": "scholarly-reference",
                                "trusted": True,
                                "evidence_type": "etymological-source",
                            },
                        }
                    },
                }
            ],
        }
    )


def test_rejects_a_singular_unit_pronunciation_field() -> None:
    with pytest.raises(OrthographyContractError, match="readings list"):
        validate_orthography(
            {
                "script": "han",
                "units": [{
                    "surface": "行",
                    "script": "han",
                    "unit_kind": "character",
                    "pronunciation": "háng",
                }],
            }
        )
