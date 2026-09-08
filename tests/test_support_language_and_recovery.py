"""L2.5: support-language separation and no-caption recovery contracts.

These exist because two durable product rules were repeatedly lost:

* Orena is globally designed. Meaning arrives in the learner's SUPPORT language,
  which is not the learning language, not the UI locale, and not Vietnamese.
* A playable video without captions is a valid media source, not an unsupported
  one. Missing captions start recovery; they do not reject the video.

The assertions are written so that reintroducing either mistake fails here
rather than in a human QA session months later.
"""

from __future__ import annotations

from pathlib import Path

from writing_coach.media_api import (
    TRANSCRIPT_ORIGIN_NONE,
    TRANSCRIPT_ORIGIN_PROVIDER,
    transcript_origin,
)
from writing_coach.media_recovery_policy import (
    DEFER_TRANSCRIPT_RECOVERY,
    INLINE_PROVIDER_FALLBACK,
    build_youtube_adapter,
)
from writing_coach.core.support_languages import (
    AVAILABLE_SUPPORT_LANGUAGES,
    configured_default,
    is_available,
    normalize_language_tag,
    resolve_support_language,
)

REPO = Path(__file__).resolve().parents[1]


# --- A: the three language concepts are distinct -----------------------------

def test_support_language_is_not_hardcoded_to_vietnamese() -> None:
    """Vietnamese is one option among many, never the built-in answer."""

    # A learner who has chosen gets what they chose, whatever it is.
    for chosen in ("ja", "es", "ko", "pt", "vi", "zh"):
        assert resolve_support_language(chosen) == chosen

    # Nothing known: the configured neutral default, and it is not Vietnamese.
    assert resolve_support_language() == configured_default()
    assert resolve_support_language() != "vi"

    # An operator may set the deployment default; it is configuration, not a
    # guess about any individual learner.
    assert resolve_support_language(env={"DEFAULT_SUPPORT_LANGUAGE": "ja"}) == "ja"
    # An unavailable configured default falls back rather than being served.
    assert resolve_support_language(env={"DEFAULT_SUPPORT_LANGUAGE": "xx"}) == "en"

    assert {"en", "vi", "zh", "ja", "ko", "es"} <= set(AVAILABLE_SUPPORT_LANGUAGES)


def test_resolution_order_is_profile_then_request_then_default() -> None:
    # The stored preference wins over a request-scoped value.
    assert resolve_support_language("ja", "es") == "ja"
    # With no profile, an explicit valid selection is honoured.
    assert resolve_support_language("", "es") == "es"
    # A well-formed but unsupported tag falls through instead of pretending.
    assert resolve_support_language("", "xh") == configured_default()
    # Junk never becomes a language.
    for junk in (None, "", "   ", "e", "toolongtag!", 42):
        assert normalize_language_tag(junk) in {"", "42"} or not is_available(junk)


def test_bcp47_identity_is_preserved_not_flattened_to_an_enum() -> None:
    assert normalize_language_tag("pt-BR") == "pt-br"
    assert normalize_language_tag("ZH_Hant") == "zh-hant"
    # Storage keeps the identity even where translation coverage does not exist
    # yet; availability is a capability boundary checked at resolution time.
    assert normalize_language_tag("xh") == "xh"
    assert is_available("xh") is False


def test_two_learners_same_language_different_support_language() -> None:
    """F11: one canonical transcript, two different meaning languages."""

    learner_a = resolve_support_language("ja")
    learner_b = resolve_support_language("es")
    assert learner_a != learner_b
    # Neither learner's choice changes what the other receives, and neither is
    # the product's default.
    assert (learner_a, learner_b) == ("ja", "es")


def test_support_language_is_distinct_from_ui_locale() -> None:
    """F13: a learner may read the interface in one language and meanings in another."""

    # Resolution never consults a UI locale: the same profile yields the same
    # support language regardless of what the interface is set to.
    assert resolve_support_language("ja") == "ja"
    assert resolve_support_language("ja", "en") == "ja"


def test_no_vietnamese_default_survives_in_the_web_client() -> None:
    """The four defaults the audit named must stay gone."""

    store = (REPO / "static/becoming/store.js").read_text(encoding="utf-8")
    api = (REPO / "static/becoming/api.js").read_text(encoding="utf-8")
    assert "||'vi'" not in store and '|| "vi"' not in store
    assert "||'vi'" not in api and '|| "vi"' not in api
    assert "['vi','en','zh']" not in store, "the three-language enum must not come back"
    assert "AVAILABLE_SUPPORT_LANGUAGES" in store

    listening_api = (REPO / "writing_coach/listening_api.py").read_text(encoding="utf-8")
    assert 'Query(default="vi"' not in listening_api
    assert "resolve_support_language" in listening_api


def test_the_persistent_profile_carries_the_support_language() -> None:
    """A2: one store, and it is the profile - not browser local storage."""

    memory = (REPO / "writing_coach/becoming_memory.py").read_text(encoding="utf-8")
    # The stored field is no longer an enum of three, and no longer defaults to
    # Vietnamese; an empty value means "not chosen yet".
    assert 'pattern=r"^(vi|en|zh)$"' not in memory
    assert '"native_language": "vi"' not in memory
    # The profile exposes the resolved value so clients do not each re-derive it.
    assert '"support_language": resolve_support_language(' in memory


# --- B/E: no-caption media, and one recovery policy --------------------------

def test_curated_and_my_media_share_one_recovery_policy() -> None:
    """F/E: a caption-less video must mean the same thing on both paths."""

    # Recovery is deferred and inline provider fallback is off, so acquisition
    # returns the asset and playback rather than raising on missing captions.
    assert DEFER_TRANSCRIPT_RECOVERY is True
    assert INLINE_PROVIDER_FALLBACK is False

    # `enable_fallback` is not stored; it decides whether the adapter holds an
    # inline fallback client. No client means recovery is orchestrated by the
    # fallback service instead of happening inside acquisition.
    adapter = build_youtube_adapter()
    assert adapter._defer_transcript_recovery is True
    assert adapter._fallback_transcript_client is None

    # A caller cannot quietly opt into a different definition.
    forced = build_youtube_adapter(enable_fallback=True, defer_transcript_recovery=False)
    assert forced._defer_transcript_recovery is True
    assert forced._fallback_transcript_client is None

    # Both entry points construct it through the shared factory.
    app_source = (REPO / "app.py").read_text(encoding="utf-8")
    importer = (REPO / "scripts/build_listening_dev_catalog.py").read_text(encoding="utf-8")
    assert "build_youtube_adapter()" in app_source
    # The importer builds it through the shared factory too. It is reached via a
    # default argument (so tests can inject a fake adapter) rather than a literal
    # call site, so the invariant to assert is that the shared factory is what it
    # falls back to - together with the "no adapter of its own" check below.
    assert "from writing_coach.media_recovery_policy import build_youtube_adapter" in importer
    assert "adapter_factory or build_youtube_adapter" in importer
    assert "YouTubeMediaProviderAdapter(" not in app_source, "runtime must not build its own policy"
    assert "YouTubeMediaProviderAdapter(" not in importer, "importer must not build its own policy"


def test_generated_transcript_provenance_is_disclosed() -> None:
    """B5: never present an AI transcript as the source's own captions."""

    class Timing:
        source = "groq"

    assert transcript_origin(None) == TRANSCRIPT_ORIGIN_NONE
    assert transcript_origin(object()) == TRANSCRIPT_ORIGIN_PROVIDER
    assert transcript_origin(object(), Timing()) == "generated_asr"

    media_api = (REPO / "writing_coach/media_api.py").read_text(encoding="utf-8")
    # The Supadata path labels itself rather than inheriting "provider_caption".
    assert "TRANSCRIPT_ORIGIN_SUPADATA if job.source" in media_api
    assert '"transcript_origin": transcript_origin(' in media_api
