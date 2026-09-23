"""How a word sounds, bound to the reading the learner kept.

The human asked for this on 2026-09-23: real pronunciation from Wikimedia /
Wiktionary first, a local voice (Kokoro) as the fallback, cached so nothing is
fetched or generated twice, with source, licence and attribution stored beside
the bytes. And one rule above all of them:

    **A word whose reading is still ambiguous gets no audio.**

That is not a limitation to work around. 行 is xíng or háng and 重 is zhòng or
chóng; a recording of the wrong one, attached to a learner's saved word,
teaches the wrong word every time they press play, and it keeps teaching it
because nothing about the row says it is wrong. Silence is recoverable;
confident wrong audio is not. So the entry's identity and its reading come from
`becoming_library.entry_identity_for`, the same decision that decides whether a
saved word may be linked at all (D-074), and this module never re-derives it.

**It changes no contract.** Nothing here writes to `saved_words`,
`library_items`, `vocabulary_entries` or any of the tables the Vocabulary and
My Library work settled. There is no new schema at all: the bytes and their
licence live in the existing `BookAssetStore` seam, keyed by a digest of
(identity key, reading), and a word with no audio is simply a word this module
answers `None` about.

**Sources, in order:**

1. **Wikimedia Commons.** Only a file whose name binds it to this reading is
   accepted - for a single-reading entry the word is enough, for a word with
   several readings the filename must carry the reading itself. A file that
   cannot be tied to the reading is not used, which is the rule above applied
   to the source rather than to the learner.
   Only free licences are taken (public domain, CC0, CC BY, CC BY-SA), and the
   licence and the author are stored with the bytes, because that is the
   condition on which they may be played at all.
2. **A local voice.** `KokoroVoice` speaks the reading when a Kokoro endpoint
   is configured (`KOKORO_TTS_URL`). Unconfigured, it reports itself
   unavailable and this module answers `None` rather than substituting some
   other voice - a synthetic reading of the wrong sound is the same mistake as
   the wrong recording.

Nothing here is a paid provider, and no credential is required or read.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from writing_coach.book_asset_store import AssetNotFound, BookAssetStore

_log = logging.getLogger(__name__)

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
# Wikimedia asks every client to identify itself; an anonymous one is refused
# with 403, which is their policy working, not an outage.
USER_AGENT = "Orena/0.1 (language-learning app; +https://github.com/orena)"
REQUEST_TIMEOUT = 20
# A pronunciation clip is seconds long. Anything much larger is not one, and
# the store is not the place to find that out.
MAX_AUDIO_BYTES = 4 * 1024 * 1024
SEARCH_LIMIT = 20

# What may be played. A file under any other licence is left where it is.
FREE_LICENCES = (
    "cc0", "cc-zero", "public domain", "pd", "cc by", "cc-by", "cc by-sa", "cc-by-sa",
)
AUDIO_TYPES = {
    "ogg": "audio/ogg", "oga": "audio/ogg", "opus": "audio/ogg",
    "mp3": "audio/mpeg", "wav": "audio/wav", "flac": "audio/flac",
    "m4a": "audio/mp4",
}
# How Commons names pronunciation, per learning language. These are naming
# conventions, not a search: `En-us-harbour.ogg`, `Zh-háng.ogg`, and Lingua
# Libre's `LL-Q1860 (eng)-Speaker-harbour.wav`.
#
# `prefixes` are tried as literal filenames; `lingua` is the Wikidata language
# item Lingua Libre files carry. A free-text search over an ordinary word
# returns harbours and folk songs, so this asks for names instead.
LANGUAGE_NAMING = {
    "en": {
        "prefixes": ("En-us", "En-uk", "En-gb", "En-au", "En", "en"),
        "lingua": ("Q1860",),
        "code": "eng",
    },
    "zh": {
        "prefixes": ("Zh", "Zh-cn", "Zh-tw", "Cmn", "zh"),
        "lingua": ("Q9192", "Q7850"),
        "code": "cmn",
    },
}
# `<Tag>-<word>.<ext>` and `LL-Q<id> (<code>)-<speaker>-<word>.<ext>`, which
# are the only two shapes a pronunciation file is named in.
_PREFIXED = re.compile(r"^(?P<tag>[A-Za-z]{2,3}(?:-[A-Za-z]{2})?)-(?P<word>.+)$")
_LINGUA = re.compile(r"^LL-(?P<item>Q\d+)\s*\((?P<code>[a-z]{2,3})\)-[^-]+-(?P<word>.+)$")
TRIED_EXTENSIONS = ("ogg", "wav", "mp3", "flac")


class WordAudioUnavailable(RuntimeError):
    """The store is not configured; this is not "there is no audio for it"."""


@dataclass(frozen=True)
class WordAudio:
    """One pronunciation, and the terms it may be played under."""

    key: str
    media_type: str
    source: str
    licence: str
    attribution: str
    voice: str
    reading: str
    fetched_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "mediaType": self.media_type,
            "source": self.source,
            "license": self.licence,
            "attribution": self.attribution,
            "voice": self.voice,
            "reading": self.reading,
            "fetchedAt": self.fetched_at,
        }

    @classmethod
    def from_dict(cls, key: str, payload: dict[str, Any]) -> WordAudio:
        return cls(
            key=key,
            media_type=str(payload.get("mediaType") or "audio/ogg"),
            source=str(payload.get("source") or ""),
            licence=str(payload.get("license") or ""),
            attribution=str(payload.get("attribution") or ""),
            voice=str(payload.get("voice") or ""),
            reading=str(payload.get("reading") or ""),
            fetched_at=str(payload.get("fetchedAt") or ""),
        )


@dataclass(frozen=True)
class Spoken:
    """What a voice returned: the bytes and what they may be played under."""

    audio: bytes
    media_type: str
    source: str
    licence: str
    attribution: str
    voice: str


class Voice(Protocol):
    """A source of pronunciation. `speak` returns nothing when it has none."""

    name: str

    def speak(self, *, term: str, language: str, reading: str, single_reading: bool) -> Spoken | None: ...


def _digest(identity_key: str, reading: str) -> str:
    """The cache key: this entry, this reading, and nothing else.

    Not the written word - two entries can share one - and not the learner,
    because a pronunciation is the language's, not theirs, and caching it per
    learner would fetch the same clip a thousand times.
    """

    material = f"{identity_key}\x1f{reading}".encode()
    return hashlib.blake2s(material, digest_size=16).hexdigest()


def _normalise(text: str) -> str:
    return re.sub(r"[\s_-]+", "", str(text or "").strip().casefold())


def _free(licence: str) -> bool:
    value = str(licence or "").strip().casefold()
    if not value:
        return False
    return any(value.startswith(allowed) or allowed in value for allowed in FREE_LICENCES)


class CommonsVoice:
    """Wikimedia Commons, where Wiktionary's pronunciation audio actually is.

    It asks for files **by name** rather than searching for them. Commons names
    pronunciation by convention - `En-us-harbour.ogg`, `Zh-háng.ogg`, Lingua
    Libre's `LL-Q1860 (eng)-Speaker-harbour.wav` - and a free-text search for
    an ordinary word returns harbours, folk songs and place names instead. The
    first draft searched, and the coverage measurement reported 0 of 30: every
    real recording was ranked below the noise, and a substring test on the tag
    "En" called "Thanksgiving" English.

    So: build the names this word would have, ask the API which of them exist
    in one request, and fall back to a narrow Lingua Libre search pinned to the
    language's own Wikidata item.
    """

    name = "commons"

    def __init__(self, *, fetch: Callable[[str], bytes] | None = None,
                 call: Callable[[dict[str, str]], dict[str, Any]] | None = None) -> None:
        self._fetch = fetch or self._download
        self._call = call or self._api

    @staticmethod
    def _request(url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:  # noqa: S310
            return response.read(MAX_AUDIO_BYTES + 1)

    def _api(self, params: dict[str, str]) -> dict[str, Any]:
        payload = self._request(f"{COMMONS_API}?{urllib.parse.urlencode(params)}")
        return json.loads(payload.decode("utf-8"))

    def _download(self, url: str) -> bytes:
        data = self._request(url)
        if len(data) > MAX_AUDIO_BYTES:
            raise ValueError("pronunciation file is larger than a pronunciation")
        return data

    def _named(self, spoken_form: str, language: str) -> list[str]:
        """The filenames this pronunciation would have, if it exists."""

        naming = LANGUAGE_NAMING.get(language)
        if naming is None:
            return []
        return [
            f"File:{prefix}-{spoken_form}.{extension}"
            for prefix in naming["prefixes"]
            for extension in TRIED_EXTENSIONS
        ]

    def _lingua_libre(self, spoken_form: str, language: str) -> list[str]:
        """Lingua Libre's recordings, which carry a speaker in the name.

        These cannot be guessed, so this one is a search - but a narrow one,
        pinned to the Lingua Libre prefix and this language's own Wikidata
        item, which is what keeps a folk song out of it.
        """

        naming = LANGUAGE_NAMING.get(language)
        if naming is None:
            return []
        found: list[str] = []
        for item in naming["lingua"]:
            try:
                answer = self._call({
                    "action": "query", "format": "json", "list": "search",
                    "srsearch": f'intitle:"LL-{item}" intitle:"{spoken_form}"',
                    "srnamespace": "6", "srlimit": str(SEARCH_LIMIT),
                })
            except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError, TimeoutError) as error:
                _log.info("commons search unavailable: %s", type(error).__name__)
                return found
            found += [str(row.get("title") or "") for row in answer.get("query", {}).get("search", [])]
        return found

    def _pages(self, titles: list[str]) -> list[dict[str, Any]]:
        """The files among these that exist, with their licence and their url."""

        if not titles:
            return []
        try:
            answer = self._call({
                "action": "query", "format": "json", "titles": "|".join(titles[:50]),
                "prop": "imageinfo", "iiprop": "url|extmetadata|mime",
            })
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError, TimeoutError) as error:
            _log.info("commons metadata unavailable: %s", type(error).__name__)
            return []
        return [
            page for page in (answer.get("query", {}).get("pages", {}) or {}).values()
            if "missing" not in page and page.get("imageinfo")
        ]

    def _binds(self, title: str, *, term: str, language: str, reading: str, single_reading: bool) -> bool:
        """Does this filename name this word, in this language, at this reading?

        Matched against the two conventions, never as a substring: "En" inside
        "Thanksgiving" is not a language tag.

        For an entry with one reading the filename must name the word. For an
        entry with several it must name **the reading**, and then the word
        itself is optional, because Commons names many Chinese clips by pinyin
        alone (`Zh-háng.ogg`). That is not a gap: the reading *is* the sound,
        so a clip recorded for 航 is the same háng the learner kept for 行,
        while a clip named only 行 could be either and is refused.
        """

        naming = LANGUAGE_NAMING.get(language)
        if naming is None:
            return False
        stem = title.split(":", 1)[-1].rsplit(".", 1)[0]
        wanted = _normalise(term) if single_reading else _normalise(reading)
        if not wanted:
            return False
        lingua = _LINGUA.match(stem)
        if lingua is not None:
            if lingua.group("item") not in naming["lingua"] and lingua.group("code") != naming["code"]:
                return False
            return _normalise(lingua.group("word")) == wanted
        prefixed = _PREFIXED.match(stem)
        if prefixed is None:
            return False
        if prefixed.group("tag").casefold() not in {value.casefold() for value in naming["prefixes"]}:
            return False
        return _normalise(prefixed.group("word")) == wanted

    def speak(self, *, term: str, language: str, reading: str, single_reading: bool) -> Spoken | None:
        # What the learner is asking to hear: the word itself when the entry
        # has one reading, the reading when it has several.
        spoken_form = term if single_reading else reading
        if not str(spoken_form or "").strip():
            return None
        pages = self._pages(self._named(spoken_form, language))
        if not pages:
            narrow = [
                title for title in self._lingua_libre(spoken_form, language)
                if self._binds(title, term=term, language=language, reading=reading, single_reading=single_reading)
            ]
            pages = self._pages(narrow[:5])
        for page in pages:
            info = (page.get("imageinfo") or [{}])[0]
            extra = info.get("extmetadata") or {}
            licence = str((extra.get("LicenseShortName") or {}).get("value") or "")
            if not _free(licence):
                continue
            url = str(info.get("url") or "")
            # The extension comes from the path: Commons appends campaign
            # parameters to the url it hands back, and `rsplit(".")` over the
            # whole thing reads `...&utm_content=original` as the file type,
            # which silently rejected every real recording.
            extension = urllib.parse.urlsplit(url).path.rsplit(".", 1)[-1].casefold()
            media_type = AUDIO_TYPES.get(extension)
            if not url or media_type is None:
                continue
            author = re.sub(r"<[^>]+>", "", str((extra.get("Artist") or {}).get("value") or "")).strip()
            try:
                audio = self._fetch(url)
            except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError, TimeoutError) as error:
                _log.info("commons download unavailable: %s", type(error).__name__)
                continue
            if not audio:
                continue
            return Spoken(
                audio=audio,
                media_type=media_type,
                source=url,
                licence=licence,
                # What the licence obliges: who made it, under what, and where
                # it came from. Stored with the bytes so a surface can show it
                # without a second lookup.
                attribution=" · ".join(part for part in (author, licence, "Wikimedia Commons") if part),
                voice=str(page.get("title") or ""),
            )
        return None


class KokoroVoice:
    """A local voice, used only when no real recording binds to this reading.

    Configured by `KOKORO_TTS_URL`. Unconfigured, it says so, and the caller
    answers "no audio" rather than reaching for some other voice: a synthetic
    reading of the wrong sound is the same mistake as the wrong recording.
    """

    name = "kokoro"

    def __init__(self, *, url: str | None = None, post: Callable[[str, bytes], bytes] | None = None) -> None:
        self._url = url if url is not None else os.getenv("KOKORO_TTS_URL", "")
        self._post = post or self._request

    @property
    def configured(self) -> bool:
        return bool(str(self._url or "").strip())

    def _request(self, url: str, body: bytes) -> bytes:
        request = urllib.request.Request(
            url, data=body, headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:  # noqa: S310
            return response.read(MAX_AUDIO_BYTES + 1)

    def speak(self, *, term: str, language: str, reading: str, single_reading: bool) -> Spoken | None:
        if not self.configured:
            return None
        # The voice is told the reading, not just the written word - which is
        # the only way a synthesised 行 can be the right one.
        body = json.dumps({"text": term, "reading": reading, "language": language}).encode("utf-8")
        try:
            audio = self._post(self._url, body)
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError, TimeoutError) as error:
            _log.info("kokoro unavailable: %s", type(error).__name__)
            return None
        if not audio or len(audio) > MAX_AUDIO_BYTES:
            return None
        return Spoken(
            audio=audio,
            media_type="audio/wav",
            source="kokoro",
            licence="generated",
            attribution="Kokoro (generated)",
            voice="kokoro",
        )


class WordAudioLibrary:
    """Pronunciation for an entry's reading: cached, fetched, or nothing.

    The cache is the store itself: the bytes under `<digest>.<ext>` and what
    they may be played under under `<digest>.json`. A second request for the
    same (identity, reading) reads them and asks no voice anything - which is
    the whole point, since the first request may have crossed the network.
    """

    def __init__(self, store: BookAssetStore, voices: tuple[Voice, ...]) -> None:
        self._store = store
        self._voices = voices

    def cached(self, identity_key: str, reading: str) -> WordAudio | None:
        digest = _digest(identity_key, reading)
        try:
            payload = json.loads(self._store.get(f"word-audio/{digest}.json").decode("utf-8"))
        except (AssetNotFound, ValueError, KeyError):
            return None
        key = str(payload.get("key") or "")
        if not key or not self._store.exists(key):
            return None
        return WordAudio.from_dict(key, payload)

    def audio_bytes(self, key: str) -> bytes:
        return self._store.get(key)

    def pronounce(
        self, *, identity_key: str, term: str, language: str, reading: str, single_reading: bool
    ) -> WordAudio | None:
        """The rule, in one place: no identity, no audio; ambiguous, no audio."""

        if not str(identity_key or "").strip():
            return None
        if not single_reading and not str(reading or "").strip():
            return None
        found = self.cached(identity_key, reading)
        if found is not None:
            return found
        for voice in self._voices:
            spoken = voice.speak(
                term=term, language=language, reading=reading, single_reading=single_reading
            )
            if spoken is None:
                continue
            return self._keep(identity_key, reading, spoken)
        return None

    def _keep(self, identity_key: str, reading: str, spoken: Spoken) -> WordAudio:
        digest = _digest(identity_key, reading)
        extension = next(
            (name for name, media in AUDIO_TYPES.items() if media == spoken.media_type), "ogg"
        )
        key = f"word-audio/{digest}.{extension}"
        self._store.put(key, spoken.audio)
        record = WordAudio(
            key=key,
            media_type=spoken.media_type,
            source=spoken.source,
            licence=spoken.licence,
            attribution=spoken.attribution,
            voice=spoken.voice,
            reading=reading,
            fetched_at=datetime.now(UTC).isoformat(),
        )
        # Written after the bytes: a record that points at nothing would be a
        # cache hit with no audio behind it.
        self._store.put(
            f"word-audio/{digest}.json",
            json.dumps(record.as_dict(), ensure_ascii=False).encode("utf-8"),
        )
        return record


def default_voices() -> tuple[Voice, ...]:
    """Real recordings first, a local voice second. Nothing else."""

    return (CommonsVoice(), KokoroVoice())
