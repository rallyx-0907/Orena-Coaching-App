from __future__ import annotations

import pytest

from grammar_lab.rules.en_morphology import (
    comparative,
    past_participle,
    past_simple,
    plural_noun,
    present_participle,
    superlative,
    third_person_singular,
)


@pytest.mark.parametrize("verb,expected", [
    ("work", "works"),
    ("go", "goes"),
    ("do", "does"),
    ("watch", "watches"),
    ("wash", "washes"),
    ("fix", "fixes"),
    ("buzz", "buzzes"),
    ("study", "studies"),
    ("play", "plays"),
    ("have", "has"),
    ("be", "is"),
])
def test_third_person_singular(verb: str, expected: str) -> None:
    assert third_person_singular(verb) == expected


@pytest.mark.parametrize("noun,expected", [
    ("cat", "cats"),
    ("bus", "buses"),
    ("box", "boxes"),
    ("brush", "brushes"),
    ("city", "cities"),
    ("boy", "boys"),
    ("knife", "knives"),
    ("leaf", "leaves"),
])
def test_plural_noun(noun: str, expected: str) -> None:
    assert plural_noun(noun) == expected


@pytest.mark.parametrize("verb,expected", [
    ("work", "working"),
    ("make", "making"),
    ("run", "running"),
    ("play", "playing"),
    ("lie", "lying"),
    ("see", "seeing"),
    ("study", "studying"),
])
def test_present_participle(verb: str, expected: str) -> None:
    assert present_participle(verb) == expected


@pytest.mark.parametrize("verb,past,participle", [
    ("work", "worked", "worked"),
    ("study", "studied", "studied"),
    ("stop", "stopped", "stopped"),
    ("live", "lived", "lived"),
    ("go", "went", "gone"),
    ("have", "had", "had"),
    ("eat", "ate", "eaten"),
    ("visit", "visited", "visited"),
])
def test_past_simple_and_participle(verb: str, past: str, participle: str) -> None:
    assert past_simple(verb) == past
    assert past_participle(verb) == participle


def test_unmapped_irregular_verb_returns_none_rather_than_a_wrong_guess() -> None:
    assert past_simple("sell") is None
    assert past_participle("hit") is None


@pytest.mark.parametrize("adjective,comp,sup", [
    ("cheap", "cheaper", "cheapest"),
    ("big", "bigger", "biggest"),
    ("nice", "nicer", "nicest"),
    ("happy", "happier", "happiest"),
    ("tall", "taller", "tallest"),
    ("beautiful", "more beautiful", "most beautiful"),
    ("good", "better", "best"),
    ("bad", "worse", "worst"),
    ("far", "farther", "farthest"),
])
def test_comparative_and_superlative(adjective: str, comp: str, sup: str) -> None:
    assert comparative(adjective) == comp
    assert superlative(adjective) == sup
