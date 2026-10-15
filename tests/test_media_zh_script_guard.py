"""Only Simplified Chinese provider captions are accepted, for now (D-218, owner decision 2026-10-15).

"Skip Traditional content; for now only Simplified learning content is accepted." A Chinese caption track tagged zh-Hant,
zh-TW, zh-HK or zh-MO is refused with `zh_traditional_not_accepted` before anything is translated or recognised; a Simplified
or untagged track is preferred when the video offers both; the setting `media.zh_scripts_accepted` can relax it. Fakes only."""
from __future__ import annotations

import pytest

from tests.test_media_caption_only import _first_import
from tests.test_media_caption_path import Ingestion
from tests.test_media_caption_source import FakeSupadata, client_for, transcript
from tests.test_media_ingestion import VIDEO_ID
from writing_coach import media_transcript_pipeline as mtp
from writing_coach import policies
from writing_coach.admin_content import media_outcome
from writing_coach.media_ingestion import MediaImportCategory, MediaImportError
from writing_coach.media_providers.youtube import (
    PublicYouTubeCaptionClient, REASON_ZH_TRADITIONAL, TraditionalChineseNotAccepted, is_traditional_chinese_tag,
)


@pytest.fixture
def setting(monkeypatch):
    """Set `media.zh_scripts_accepted` for a test; every other policy reads as it does."""
    real = policies.value

    def set_to(value):
        monkeypatch.setattr(policies, "value", lambda key, **kw: value if key == "media.zh_scripts_accepted" else real(key, **kw))

    return set_to


@pytest.mark.parametrize("tag, traditional", [
    ("zh-Hant", True), ("zh-TW", True), ("zh-HK", True), ("zh-MO", True), ("zh_tw", True), ("ZH-hant-TW", True),
    ("zh", False), ("zh-Hans", False), ("zh-CN", False), ("zh-SG", False), ("en", False), ("en-GB", False), ("", False),
])
def test_which_tags_are_traditional(tag, traditional):
    assert is_traditional_chinese_tag(tag) is traditional


def test_the_default_setting_is_simplified_only():
    assert policies.default("media.zh_scripts_accepted") == "simplified"
    assert policies.BY_KEY["media.zh_scripts_accepted"].choices == ("simplified", "any")


# ---- YouTube's own tracks: nothing is fetched, nothing is paid -----------------------------------------------------------

def _api(*codes):
    class Fetched(list):
        def __init__(self, code):
            super().__init__([type("S", (), {"text": "你好世界", "start": 0.0, "duration": 1.0})()])
            self.language_code = code

    class Track:
        is_generated = False

        def __init__(self, code):
            self.language_code = code

        def fetch(self):
            api.fetched.append(self.language_code)
            return Fetched(self.language_code)

    class Listing:
        tracks = [Track(code) for code in codes]

        def __iter__(self):
            return iter(self.tracks)

        def find_manually_created_transcript(self, languages):
            for track in self.tracks:
                if track.language_code in languages:
                    return track
            raise AssertionError("no track")

    class Api:
        fetched: list[str] = []

        def list(self, video_id):
            return Listing()

    api = Api()
    return api


def test_a_video_with_only_a_traditional_track_is_refused_before_any_fetch(setting):
    api = _api("zh-TW")
    with pytest.raises(TraditionalChineseNotAccepted) as refused:
        PublicYouTubeCaptionClient(api=api).fetch_track(VIDEO_ID, "zh")
    assert refused.value.reason == REASON_ZH_TRADITIONAL == "zh_traditional_not_accepted" and api.fetched == []


def test_a_simplified_track_is_preferred_when_both_are_offered(setting):
    api = _api("zh-TW", "zh-Hans", "zh-Hant")
    track = PublicYouTubeCaptionClient(api=api).fetch_track(VIDEO_ID, "zh")
    assert track.source_language == "zh-Hans" and api.fetched == ["zh-Hans"]
    api = _api("zh-HK", "zh")
    assert PublicYouTubeCaptionClient(api=api).fetch_track(VIDEO_ID, "zh").source_language == "zh"


def test_the_setting_can_relax_it(setting):
    setting("any")
    api = _api("zh-TW")
    assert PublicYouTubeCaptionClient(api=api).fetch_track(VIDEO_ID, "zh").source_language == "zh-TW"


def test_english_is_never_affected(setting):
    assert PublicYouTubeCaptionClient(api=_api("en")).fetch_track(VIDEO_ID, "en").source_language == "en"


# ---- Supadata: only the response reveals the language ------------------------------------------------------------------

def test_a_supadata_traditional_answer_is_recorded_and_stops_there(tmp_path, setting):
    supadata = FakeSupadata(transcript(language="zh-TW"))
    client, _youtube, ledger = client_for(tmp_path, "supadata_native", supadata=supadata)
    with pytest.raises(TraditionalChineseNotAccepted):
        client.fetch_track(VIDEO_ID, "zh")
    assert len(supadata.calls) == 1 and ledger.requests_today() == 1   # the one request the response needed, counted
    with pytest.raises(TraditionalChineseNotAccepted):                 # the import and the pipeline step do not pay twice
        client.fetch_track(VIDEO_ID, "zh")
    assert len(supadata.calls) == 1 and ledger.requests_today() == 1


def test_a_supadata_simplified_answer_is_taken_and_the_setting_relaxes_it(tmp_path, setting):
    client, _y, _l = client_for(tmp_path / "a", "supadata_native", supadata=FakeSupadata(transcript(language="zh")))
    assert client.fetch_track(VIDEO_ID, "zh").source_language == "zh"
    setting("any")
    client, _y, _l = client_for(tmp_path / "b", "supadata_native", supadata=FakeSupadata(transcript(language="zh-TW")))
    assert client.fetch_track(VIDEO_ID, "zh").source_language == "zh-TW"


def test_youtube_then_supadata_does_not_spend_a_paid_request_on_a_traditional_only_video(tmp_path, setting):
    supadata = FakeSupadata(transcript(language="zh"))
    client, _y, ledger = client_for(tmp_path, "youtube_then_supadata_native",
                                    youtube=PublicYouTubeCaptionClient(api=_api("zh-TW")), supadata=supadata)
    with pytest.raises(TraditionalChineseNotAccepted):
        client.fetch_track(VIDEO_ID, "zh")
    assert supadata.calls == [] and ledger.requests_today() == 0


# ---- the pipeline: a stable reason, no audio, no recognition, no translation, in either transcript policy -----------------

class Refused:
    """What the importer hands the pipeline when the caption client refused: an unavailable track and its reason."""

    def import_media(self, *_a):
        raise MediaImportError(MediaImportCategory.PROVIDER_FAILURE) from TraditionalChineseNotAccepted()


@pytest.mark.parametrize("policy", [mtp.POLICY_CAPTIONS_ONLY, mtp.POLICY_DEFAULT, None])
def test_the_item_stops_with_the_reason_and_spends_nothing(tmp_path, policy):
    store, entry, pipeline, audio, ledger = _first_import(tmp_path / str(policy), Refused(), policy=policy)
    pipeline._run(store, None, entry.media_id, "b1", None)
    stored = store.get(entry.media_id)
    assert stored.processing["state"] == "failed" and stored.processing["reason"] == "zh_traditional_not_accepted"
    assert stored.processing["message"] == mtp.reason_message("zh_traditional_not_accepted") != ""
    assert audio.calls == 0 and ledger.recorded == [] and ledger.checked == [] and stored.lesson is None
    assert media_outcome(stored)["reason"] == "zh_traditional_not_accepted"


def test_the_importers_unavailable_provenance_carries_the_reason_to_the_same_stop(tmp_path):
    refused = Ingestion(cues=None, provenance={"caption_status": "unavailable", "caption_error": "zh_traditional_not_accepted"})
    store, entry, pipeline, audio, ledger = _first_import(tmp_path, refused)
    pipeline._run(store, None, entry.media_id, "b1", None)
    assert store.get(entry.media_id).processing["reason"] == "zh_traditional_not_accepted" and audio.calls == 0


def test_the_admin_has_words_for_the_reason_and_the_setting_in_all_three_languages():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "static" / "orena" / "screens" / "admin"
    imports = (root / "copy-imports.js").read_text(encoding="utf-8")
    policy = (root / "copy-policies.js").read_text(encoding="utf-8")
    assert imports.count("impErr_zh_traditional_not_accepted:") == 3
    for key in ("pol_media_zh_scripts_accepted:", "polHelp_media_zh_scripts_accepted:",
                "polChoice_media_zh_scripts_accepted_simplified:", "polChoice_media_zh_scripts_accepted_any:"):
        assert policy.count(key) == 3, key
