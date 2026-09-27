"""Deterministic English morphology tables for ``rule_table`` blocks (SPEC §5.1).

Pure spelling-rule functions plus a compact irregular-verb table covering the
vocabulary A1-A2 grammar points actually use. ``generate.py`` calls these for
the deterministic half of a point (verb/noun/adjective forms); the LLM never
invents a spelling rule.

Irregular verbs not in :data:`IRREGULAR_VERBS` are not guessed: callers get
``None`` back from :func:`past_simple`/:func:`past_participle` and should
either pick a different example verb or ask the LLM for that one row
explicitly, rather than silently emitting a wrong deterministic form.
"""

from __future__ import annotations

import re

VOWELS = set("aeiou")
SIBILANT_ENDINGS = ("s", "x", "z", "ch", "sh", "ss", "o")

# base -> (past simple, past participle). Common A1-A2 verbs only; see module docstring.
IRREGULAR_VERBS: dict[str, tuple[str, str]] = {
    "be": ("was/were", "been"),
    "have": ("had", "had"),
    "do": ("did", "done"),
    "go": ("went", "gone"),
    "get": ("got", "gotten"),
    "make": ("made", "made"),
    "know": ("knew", "known"),
    "see": ("saw", "seen"),
    "come": ("came", "come"),
    "take": ("took", "taken"),
    "give": ("gave", "given"),
    "find": ("found", "found"),
    "think": ("thought", "thought"),
    "tell": ("told", "told"),
    "say": ("said", "said"),
    "become": ("became", "become"),
    "leave": ("left", "left"),
    "feel": ("felt", "felt"),
    "bring": ("brought", "brought"),
    "buy": ("bought", "bought"),
    "build": ("built", "built"),
    "begin": ("began", "begun"),
    "keep": ("kept", "kept"),
    "hold": ("held", "held"),
    "write": ("wrote", "written"),
    "stand": ("stood", "stood"),
    "hear": ("heard", "heard"),
    "let": ("let", "let"),
    "mean": ("meant", "meant"),
    "set": ("set", "set"),
    "meet": ("met", "met"),
    "run": ("ran", "run"),
    "pay": ("paid", "paid"),
    "sit": ("sat", "sat"),
    "speak": ("spoke", "spoken"),
    "lie": ("lay", "lain"),
    "lead": ("led", "led"),
    "read": ("read", "read"),
    "grow": ("grew", "grown"),
    "lose": ("lost", "lost"),
    "fall": ("fell", "fallen"),
    "send": ("sent", "sent"),
    "understand": ("understood", "understood"),
    "draw": ("drew", "drawn"),
    "break": ("broke", "broken"),
    "spend": ("spent", "spent"),
    "cut": ("cut", "cut"),
    "rise": ("rose", "risen"),
    "drive": ("drove", "driven"),
    "wear": ("wore", "worn"),
    "choose": ("chose", "chosen"),
    "eat": ("ate", "eaten"),
    "sing": ("sang", "sung"),
    "drink": ("drank", "drunk"),
    "swim": ("swam", "swum"),
    "fly": ("flew", "flown"),
    "sleep": ("slept", "slept"),
    "teach": ("taught", "taught"),
}

# base -> (comparative, superlative). Irregular adjectives.
IRREGULAR_ADJECTIVES: dict[str, tuple[str, str]] = {
    "good": ("better", "best"),
    "bad": ("worse", "worst"),
    "far": ("farther", "farthest"),
    "little": ("less", "least"),
    "many": ("more", "most"),
    "much": ("more", "most"),
}


def _is_consonant(ch: str) -> bool:
    return ch.isalpha() and ch not in VOWELS


def _syllable_count(word: str) -> int:
    """Approximate syllable count: runs of consecutive vowels (y counts as one)."""
    return len(re.findall(r"[aeiouy]+", word)) or 1


def _cvc(word: str) -> bool:
    """One-syllable word ending consonant-vowel-consonant, not w/x/y.

    Doubling the final consonant (stop -> stopped) only applies to a single
    stressed syllable; a two-syllable word stressed on the first syllable
    (visit -> visited, not visitted) must not double. Multi-syllable words
    stressed on the last syllable (prefer -> preferred) exist too, but are
    rare in A1-A2 vocabulary, so this stays a syllable-count heuristic.
    """
    if len(word) < 3 or _syllable_count(word) != 1:
        return False
    c1, v, c2 = word[-3], word[-2], word[-1]
    return _is_consonant(c1) and v in VOWELS and _is_consonant(c2) and c2 not in "wxy"


def third_person_singular(verb: str) -> str:
    """he/she/it form of the present-simple verb."""
    if verb in {"be"}:
        return "is"
    if verb in {"have"}:
        return "has"
    if verb.endswith(SIBILANT_ENDINGS) or verb.endswith(("sh", "ch")):
        return verb + "es"
    if len(verb) >= 2 and verb[-1] == "y" and _is_consonant(verb[-2]):
        return verb[:-1] + "ies"
    return verb + "s"


def plural_noun(noun: str) -> str:
    """Regular plural of a countable noun."""
    if noun.endswith(("s", "x", "z", "ch", "sh")):
        return noun + "es"
    if len(noun) >= 2 and noun[-1] == "y" and _is_consonant(noun[-2]):
        return noun[:-1] + "ies"
    if noun.endswith("f"):
        return noun[:-1] + "ves"
    if noun.endswith("fe"):
        return noun[:-2] + "ves"
    return noun + "s"


def present_participle(verb: str) -> str:
    """-ing form."""
    if verb.endswith("ie"):
        return verb[:-2] + "ying"
    if verb.endswith("ee") or verb.endswith("oe"):
        return verb + "ing"
    if verb.endswith("e") and not verb.endswith("ee"):
        return verb[:-1] + "ing"
    if _cvc(verb) and not verb.endswith(("w", "x", "y")):
        return verb + verb[-1] + "ing"
    return verb + "ing"


def _regular_past(verb: str) -> str:
    if verb.endswith("e"):
        return verb + "d"
    if len(verb) >= 2 and verb[-1] == "y" and _is_consonant(verb[-2]):
        return verb[:-1] + "ied"
    if _cvc(verb) and not verb.endswith(("w", "x", "y")):
        return verb + verb[-1] + "ed"
    return verb + "ed"


def past_simple(verb: str) -> str | None:
    """Past-simple form, or ``None`` for an irregular verb this table does not cover."""
    if verb in IRREGULAR_VERBS:
        return IRREGULAR_VERBS[verb][0]
    if _looks_irregular(verb):
        return None
    return _regular_past(verb)


def past_participle(verb: str) -> str | None:
    """Past-participle (V3) form, or ``None`` for an irregular verb this table does not cover."""
    if verb in IRREGULAR_VERBS:
        return IRREGULAR_VERBS[verb][1]
    if _looks_irregular(verb):
        return None
    return _regular_past(verb)


# Verbs outside IRREGULAR_VERBS that are still irregular (so callers do not
# silently get a wrong regular guess for them).
_KNOWN_OTHER_IRREGULAR = {
    "put", "hit", "cost", "hurt", "shut", "quit", "split", "spread",
    "catch", "fight", "win", "shoot", "sell", "feed",
}


def _looks_irregular(verb: str) -> bool:
    return verb in _KNOWN_OTHER_IRREGULAR


def comparative(adjective: str) -> str:
    if adjective in IRREGULAR_ADJECTIVES:
        return IRREGULAR_ADJECTIVES[adjective][0]
    one_syllable_or_simple_two = len(adjective) <= 6
    if adjective.endswith("y") and _is_consonant(adjective[-2:-1] or " "):
        return adjective[:-1] + "ier"
    if one_syllable_or_simple_two and _cvc(adjective):
        return adjective + adjective[-1] + "er"
    if one_syllable_or_simple_two and adjective.endswith("e"):
        return adjective + "r"
    if one_syllable_or_simple_two:
        return adjective + "er"
    return "more " + adjective


def superlative(adjective: str) -> str:
    if adjective in IRREGULAR_ADJECTIVES:
        return IRREGULAR_ADJECTIVES[adjective][1]
    comp = comparative(adjective)
    if comp.startswith("more "):
        return "most " + comp[len("more "):]
    return comp[:-2] + "est" if comp.endswith("er") else comp + "st"
