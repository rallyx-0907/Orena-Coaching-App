"""Pronunciation is bound to a reading, or there is none.

The rule these hold: a word whose reading is still ambiguous gets no audio.
行 is xíng or háng; a recording of the wrong one attached to a saved word
teaches the wrong word every time it is played, and nothing in the row says so.

No test here touches the network. The voices are fakes shaped like the real
ones, and one of them records what it was asked, so "the cache asked nobody the
second time" is an assertion rather than a hope.
"""
from __future__ import annotations

import json

import pytest

from writing_coach.book_asset_store import FilesystemBookAssetStore
from writing_coach.word_audio import (
    CommonsVoice,
    KokoroVoice,
    Spoken,
    WordAudioLibrary,
    _free,
)

EN_IDENTITY = "en:harbour:sense-1"
ZH_IDENTITY = "zh:行:xing2"


class CountingVoice:
    """A voice with one clip, that remembers every time it was asked."""

    name = "counting"

    def __init__(self, *, answers: bool = True, media_type: str = "audio/ogg"):
        self.asked: list[dict] = []
        self._answers = answers
        self._media_type = media_type

    def speak(self, *, term, language, reading, single_reading):
        self.asked.append(
            {"term": term, "language": language, "reading": reading, "single": single_reading}
        )
        if not self._answers:
            return None
        return Spoken(
            audio=b"OggS-not-really-but-bytes",
            media_type=self._media_type,
            source=f"https://example.test/{term}-{reading or 'plain'}.ogg",
            licence="CC BY-SA 4.0",
            attribution=f"A Speaker · CC BY-SA 4.0 · Wikimedia Commons ({reading or term})",
            voice="fake",
        )


@pytest.fixture()
def library(tmp_path):
    def build(*voices):
        return WordAudioLibrary(FilesystemBookAssetStore(tmp_path / "assets"), tuple(voices))

    return build


# --- The rule -----------------------------------------------------------

def test_an_ambiguous_reading_gets_no_audio_and_asks_nobody(library):
    """The case the whole feature exists for: 行 with no reading recorded."""

    voice = CountingVoice()
    found = library(voice).pronounce(
        identity_key=ZH_IDENTITY, term="行", language="zh", reading="", single_reading=False
    )
    assert found is None
    assert voice.asked == [], "an ambiguous word must not even be looked up"


def test_a_reading_the_learner_kept_is_spoken(library):
    voice = CountingVoice()
    found = library(voice).pronounce(
        identity_key=ZH_IDENTITY, term="行", language="zh", reading="háng", single_reading=False
    )
    assert found is not None
    assert found.reading == "háng"
    assert voice.asked[0]["reading"] == "háng", "the voice is told which reading"


def test_two_readings_of_one_word_are_two_recordings(library):
    """A cache keyed on the word alone would give xíng's clip to háng."""

    voice = CountingVoice()
    shelf = library(voice)
    xing = shelf.pronounce(
        identity_key=ZH_IDENTITY, term="行", language="zh", reading="xíng", single_reading=False
    )
    hang = shelf.pronounce(
        identity_key=ZH_IDENTITY, term="行", language="zh", reading="háng", single_reading=False
    )
    assert xing.key != hang.key
    assert [entry["reading"] for entry in voice.asked] == ["xíng", "háng"]


def test_a_word_with_one_reading_needs_none(library):
    """English mostly has one reading, and naming it is not required."""

    voice = CountingVoice()
    found = library(voice).pronounce(
        identity_key=EN_IDENTITY, term="harbour", language="en", reading="", single_reading=True
    )
    assert found is not None and found.reading == ""
    assert voice.asked[0]["single"] is True


def test_a_word_with_no_catalogue_identity_gets_no_audio(library):
    voice = CountingVoice()
    assert library(voice).pronounce(
        identity_key="", term="harbour", language="en", reading="", single_reading=True
    ) is None
    assert voice.asked == []


# --- The cache ----------------------------------------------------------

def test_the_second_time_asks_nobody(library):
    voice = CountingVoice()
    shelf = library(voice)
    first = shelf.pronounce(
        identity_key=EN_IDENTITY, term="harbour", language="en", reading="", single_reading=True
    )
    second = shelf.pronounce(
        identity_key=EN_IDENTITY, term="harbour", language="en", reading="", single_reading=True
    )
    assert first.key == second.key
    assert len(voice.asked) == 1, "the clip was fetched once and kept"
    assert shelf.audio_bytes(second.key) == b"OggS-not-really-but-bytes"


def test_what_is_kept_beside_the_bytes_is_what_may_be_played(tmp_path):
    store = FilesystemBookAssetStore(tmp_path / "assets")
    shelf = WordAudioLibrary(store, (CountingVoice(),))
    found = shelf.pronounce(
        identity_key=EN_IDENTITY, term="harbour", language="en", reading="", single_reading=True
    )
    record = json.loads(store.get(found.key.replace(".ogg", ".json")).decode("utf-8"))
    assert record["license"] == "CC BY-SA 4.0"
    assert "A Speaker" in record["attribution"] and "Wikimedia Commons" in record["attribution"]
    assert record["source"].startswith("https://")
    assert record["fetchedAt"]


def test_a_record_whose_bytes_went_missing_is_not_a_cache_hit(tmp_path):
    store = FilesystemBookAssetStore(tmp_path / "assets")
    voice = CountingVoice()
    shelf = WordAudioLibrary(store, (voice,))
    found = shelf.pronounce(
        identity_key=EN_IDENTITY, term="harbour", language="en", reading="", single_reading=True
    )
    store.delete(found.key)
    again = shelf.pronounce(
        identity_key=EN_IDENTITY, term="harbour", language="en", reading="", single_reading=True
    )
    assert again is not None
    assert len(voice.asked) == 2, "a record pointing at nothing is not a hit"


# --- The fallback -------------------------------------------------------

def test_the_second_voice_speaks_only_when_the_first_has_nothing(library):
    silent = CountingVoice(answers=False)
    fallback = CountingVoice(media_type="audio/wav")
    found = library(silent, fallback).pronounce(
        identity_key=EN_IDENTITY, term="harbour", language="en", reading="", single_reading=True
    )
    assert found is not None and found.media_type == "audio/wav"
    assert len(silent.asked) == 1 and len(fallback.asked) == 1


def test_when_no_voice_has_it_there_is_no_audio_rather_than_some_audio(library):
    found = library(CountingVoice(answers=False), CountingVoice(answers=False)).pronounce(
        identity_key=EN_IDENTITY, term="harbour", language="en", reading="", single_reading=True
    )
    assert found is None


def test_an_unconfigured_kokoro_says_so_instead_of_speaking():
    voice = KokoroVoice(url="")
    assert voice.configured is False
    assert voice.speak(term="harbour", language="en", reading="", single_reading=True) is None


def test_a_configured_kokoro_is_told_the_reading():
    asked: list[dict] = []

    def post(url: str, body: bytes) -> bytes:
        asked.append(json.loads(body.decode("utf-8")))
        return b"RIFF-not-really-but-bytes"

    voice = KokoroVoice(url="http://kokoro.test/speak", post=post)
    spoken = voice.speak(term="行", language="zh", reading="háng", single_reading=False)
    assert spoken is not None and spoken.voice == "kokoro"
    assert asked == [{"text": "行", "reading": "háng", "language": "zh"}]


# --- What Commons is allowed to answer with -----------------------------

def _commons(existing, extra=None):
    """A Commons that holds exactly `existing` and answers like the real API.

    It matters that this only answers for titles it was actually asked for:
    the app builds the filenames a pronunciation would have and asks whether
    they exist, so a fake that answers for anything would make every refusal
    look like an acceptance.
    """

    metadata = extra or {
        "LicenseShortName": {"value": "CC BY-SA 4.0"},
        "Artist": {"value": "<a href='#'>A Speaker</a>"},
    }

    def call(params):
        if params.get("list") == "search":
            # Lingua Libre's names cannot be guessed, so the real API is asked;
            # this returns whatever is held whose name looks like one.
            return {"query": {"search": [
                {"title": title} for title in existing if title.split(":", 1)[-1].startswith("LL-")
            ]}}
        asked = params.get("titles", "").split("|")
        pages = {}
        for index, title in enumerate(asked):
            if title not in existing:
                pages[str(index)] = {"title": title, "missing": ""}
                continue
            pages[str(index)] = {
                "title": title,
                "imageinfo": [{
                    "url": f"https://upload.wikimedia.test/{title.split(':', 1)[1]}",
                    "extmetadata": metadata,
                }],
            }
        return {"query": {"pages": pages}}

    return CommonsVoice(call=call, fetch=lambda url: b"OggS-bytes")


@pytest.mark.parametrize(
    "title,term,language,single,reading,accepted",
    [
        # Named by convention: asked for directly, and found.
        ("File:En-us-harbour.ogg", "harbour", "en", True, "", True),
        ("File:En-harbour.ogg", "harbour", "en", True, "", True),
        # Lingua Libre carries a speaker, so it is searched for, not guessed.
        ("File:LL-Q1860 (eng)-Vealhurl-harbour.wav", "harbour", "en", True, "", True),
        # Another language's recording of the same spelling is not this word.
        ("File:Fr-harbour.ogg", "harbour", "en", True, "", False),
        # Several readings: a clip named only for the character could be
        # either reading, so it is refused.
        ("File:Zh-行.ogg", "行", "zh", False, "háng", False),
        # One named for the reading is the sound the learner kept.
        ("File:Zh-háng.ogg", "行", "zh", False, "háng", True),
        ("File:LL-Q9192 (cmn)-Luilui6666-xíng.wav", "行", "zh", False, "xíng", True),
        # And it has to be the right reading.
        ("File:Zh-xíng.ogg", "行", "zh", False, "háng", False),
    ],
)
def test_a_file_is_only_used_when_it_binds_to_this_reading(
    title, term, language, single, reading, accepted
):
    voice = _commons({title})
    spoken = voice.speak(term=term, language=language, reading=reading, single_reading=single)
    assert (spoken is not None) is accepted


def test_a_file_that_is_not_freely_licensed_is_left_where_it_is():
    voice = _commons(
        {"File:En-us-harbour.ogg"},
        {"LicenseShortName": {"value": "All rights reserved"}},
    )
    assert voice.speak(term="harbour", language="en", reading="", single_reading=True) is None


def test_the_author_and_the_licence_come_back_with_the_bytes():
    voice = _commons(
        {"File:En-us-harbour.ogg"},
        {
            "LicenseShortName": {"value": "CC BY-SA 3.0"},
            "Artist": {"value": "<a href='#'>Vealhurl</a>"},
        },
    )
    spoken = voice.speak(term="harbour", language="en", reading="", single_reading=True)
    assert spoken is not None
    assert spoken.licence == "CC BY-SA 3.0"
    assert spoken.attribution == "Vealhurl · CC BY-SA 3.0 · Wikimedia Commons"


@pytest.mark.parametrize(
    "licence,free",
    [
        ("CC BY-SA 4.0", True), ("CC0", True), ("Public domain", True), ("CC BY 3.0", True),
        ("All rights reserved", False), ("Fair use", False), ("", False),
    ],
)
def test_which_licences_may_be_played(licence, free):
    assert _free(licence) is free
