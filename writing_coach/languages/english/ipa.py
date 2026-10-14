"""English pronunciation from CMUdict: a local, free, offline IPA source (D-202, PROPOSED).

`arpabet_to_ipa` converts one CMUdict pronunciation to General American IPA; `scripts/build_english_ipa_table.py`
runs it over the official `cmudict.dict` and writes `cmudict_ipa.json.gz`; `ipa_for` reads that table (lazy, once,
thread-safe). Deterministic, no network, no provider.

Stress rule (documented, deliberately simple): the primary (1) or secondary (2) mark goes before the onset of
the stressed syllable. Syllable boundaries come from the maximal-onset principle: between two vowels the longest
consonant tail that is a legal English onset starts the next syllable, the rest closes the previous one. A word of
one syllable carries no mark. Unstressed AH is schwa, unstressed ER is r-coloured schwa; stressed ER is the
r-coloured stressed vowel.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)
CONVERTER_VERSION = "arpabet-ipa/1"
TABLE_PATH = Path(__file__).resolve().parent / "cmudict_ipa.json.gz"

_VOWELS = {
    "AA": "ɑ", "AE": "æ", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ", "EH": "ɛ", "EY": "eɪ", "IH": "ɪ", "IY": "i",
    "OW": "oʊ", "OY": "ɔɪ", "UH": "ʊ", "UW": "u",
}
_CONSONANTS = {
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "F": "f", "G": "ɡ", "HH": "h", "JH": "dʒ", "K": "k", "L": "l",
    "M": "m", "N": "n", "NG": "ŋ", "P": "p", "R": "ɹ", "S": "s", "SH": "ʃ", "T": "t", "TH": "θ", "V": "v",
    "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}
_LEGAL_ONSETS_2 = {
    ("P", "L"), ("P", "R"), ("P", "Y"), ("B", "L"), ("B", "R"), ("B", "Y"), ("T", "R"), ("T", "W"), ("T", "Y"),
    ("D", "R"), ("D", "W"), ("D", "Y"), ("K", "L"), ("K", "R"), ("K", "W"), ("K", "Y"), ("G", "L"), ("G", "R"),
    ("G", "W"), ("G", "Y"), ("F", "L"), ("F", "R"), ("F", "Y"), ("V", "Y"), ("TH", "R"), ("TH", "W"), ("SH", "R"),
    ("S", "P"), ("S", "T"), ("S", "K"), ("S", "M"), ("S", "N"), ("S", "L"), ("S", "W"), ("S", "F"), ("S", "Y"),
    ("HH", "Y"), ("M", "Y"), ("N", "Y"), ("L", "Y"), ("S", "V"),
}
_LEGAL_ONSETS_3 = {
    ("S", "P", "L"), ("S", "P", "R"), ("S", "P", "Y"), ("S", "T", "R"), ("S", "T", "Y"), ("S", "K", "L"),
    ("S", "K", "R"), ("S", "K", "W"), ("S", "K", "Y"),
}


def _is_vowel(phone: str) -> bool:
    return phone[-1:].isdigit()


def _onset_length(cluster: list[str]) -> int:
    """How many phones, from the right of a between-vowel consonant cluster, open the next syllable."""
    if not cluster:
        return 0
    if len(cluster) >= 3 and tuple(cluster[-3:]) in _LEGAL_ONSETS_3:
        return 3
    if len(cluster) >= 2 and tuple(cluster[-2:]) in _LEGAL_ONSETS_2:
        return 2
    return 0 if cluster[-1] == "NG" else 1


def _vowel_ipa(phone: str) -> str:
    base, stress = phone[:-1], phone[-1]
    if base == "AH":
        return "ə" if stress == "0" else "ʌ"
    if base == "ER":
        return "ɚ" if stress == "0" else "ɝ"
    return _VOWELS[base]


def arpabet_to_ipa(phones: list[str]) -> str:
    """One CMUdict pronunciation (`["IH2", "N", "F", "R", "AH0", ...]`) to IPA, without slashes."""
    nuclei = [i for i, phone in enumerate(phones) if _is_vowel(phone)]
    if not nuclei:
        return "".join(_CONSONANTS[phone] for phone in phones)
    starts = [0]  # index in `phones` where each syllable begins (its onset)
    for left, right in zip(nuclei, nuclei[1:], strict=False):
        starts.append(right - _onset_length(phones[left + 1:right]))
    marks = {"0": "", "1": "ˈ", "2": "ˌ"}
    out: list[str] = []
    for syllable, nucleus in enumerate(nuclei):
        begin = starts[syllable]
        end = starts[syllable + 1] if syllable + 1 < len(starts) else len(phones)
        if len(nuclei) > 1:
            out.append(marks[phones[nucleus][-1]])
        for index in range(begin, end):
            phone = phones[index]
            out.append(_vowel_ipa(phone) if _is_vowel(phone) else _CONSONANTS[phone])
    return "".join(out)


_lock = threading.Lock()
_table: dict[str, str] | None = None


def _load() -> dict[str, str]:
    global _table
    if _table is None:
        with _lock:
            if _table is None:
                try:
                    with gzip.open(TABLE_PATH, "rt", encoding="utf-8") as handle:
                        payload: dict[str, Any] = json.load(handle)
                    _table = {str(k): str(v) for k, v in payload.get("ipa", {}).items()}
                except (OSError, ValueError) as exc:
                    # Logged once: the table is cached empty, so lookups degrade to no local reading.
                    _log.warning("English IPA table unreadable (%s); local pronunciations are unavailable", exc)
                    _table = {}
    return _table


def table_digest(table: dict[str, str]) -> str:
    """SHA-256 of the table's canonical JSON, embedded as `tableSha256` and verified by the builder's --check."""
    return hashlib.sha256(json.dumps(table, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def metadata() -> dict[str, Any]:
    with gzip.open(TABLE_PATH, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    meta = {key: value for key, value in payload.items() if key != "ipa"}
    meta["actualTableSha256"] = table_digest(payload.get("ipa", {}))
    return meta


def ipa_for(word: str) -> str:
    """`/ˈɪnfɹəˌstɹʌktʃɚ/` for an English word, or "" when CMUdict has none.

    Exact lowercase form only (curly apostrophe folded). No stripping of -s/-ed/-ing: the sound of an ending
    changes with the stem, so a guessed inflection would be wrong as often as right.
    """
    key = " ".join(str(word or "").replace("’", "'").casefold().split())
    if not key or " " in key:
        return ""
    value = _load().get(key, "")
    return f"/{value}/" if value else ""
