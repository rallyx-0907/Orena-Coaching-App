"""Admin media imports can take captions from Supadata, native mode only and credit-capped (D-215, PROPOSED).

Evidence: the :8021 host IP is throttled by YouTube on caption downloads (HTTP 429), a whole-machine VPN unblocks YouTube but
Groq refuses the VPN exit, and the owner's Supadata Free plan has 100 credits a month. Native mode is one credit a request;
`auto` may generate (two credits a minute) and translation is thirty, so only native is ever sent.
Every provider here is a fake: nothing reaches YouTube or Supadata."""
from __future__ import annotations

import inspect
from dataclasses import replace
from pathlib import Path

import pytest
import requests

from tests.test_media_caption_only import Audio, SpyLedger
from tests.test_media_caption_path import URL, Asr, _world
from tests.test_media_ingestion import VIDEO_ID, FakeCaptionClient, FakeMetadataClient
from writing_coach import media_transcript_pipeline as mtp
from writing_coach import policies
from writing_coach.media_ingestion import MediaIngestionService, ProviderRequestFailed, ProviderTimedOut
from writing_coach.media_providers import caption_source
from writing_coach.media_providers.caption_source import (
    NATIVE_MODE,
    CaptionNotConfigured,
    CaptionQuotaReached,
    PolicyCaptionClient,
)
from writing_coach.media_providers.supadata import (
    SupadataTranscript,
    SupadataTranscriptChunk,
    SupadataTranscriptClient,
    SupadataTranscriptMalformed,
    SupadataTranscriptRequestFailed,
    SupadataTranscriptTimedOut,
)
from writing_coach.media_providers.youtube import YouTubeCaptionSnippet, YouTubeCaptionTrack
from writing_coach.media_recovery_policy import build_youtube_adapter
from writing_coach.media_segmentation import Cue, first_failure, segment_lines, validate_lines
from writing_coach.media_spend import KIND_SUPADATA, SpendLedger

SPOKEN = [
    "Good morning and welcome to the show.", "Today we are talking about how bees make honey.",
    "A single bee visits many flowers each day.", "The nectar is carried back to the hive.",
    "Other bees fan it with their wings until it thickens.", "The honey is then sealed in wax cells.",
    "Winter comes and the colony lives on that store.", "Thank you for watching and see you next time.",
]


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi")
    monkeypatch.delenv("MEDIA_CAPTION_SOURCE", raising=False)
    monkeypatch.delenv("MEDIA_SUPADATA_DAILY_REQUESTS", raising=False)
    monkeypatch.delenv("SUPADATA_API_KEY", raising=False)

    def no_network(*_args, **_kwargs):
        raise AssertionError("no test may reach a network")

    monkeypatch.setattr(requests.sessions.Session, "request", no_network)


def transcript(language="en", chunks=None):
    chunks = chunks if chunks is not None else [
        SupadataTranscriptChunk(text, i * 3000, 2500, language) for i, text in enumerate(SPOKEN)]
    return SupadataTranscript(language=language, chunks=tuple(chunks))


class FakeSupadata:
    """Records every request, with its mode. `answer` is a transcript, None (no track), or an exception to raise."""

    def __init__(self, answer=None):
        self.answer, self.calls = answer, []

    def fetch(self, url, language, *, mode="auto"):
        self.calls.append((url, language, mode))
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer

    @property
    def modes(self):
        return {mode for _url, _language, mode in self.calls}


def youtube_track(language="en", kind="manual"):
    return YouTubeCaptionTrack(
        source_language=language, kind=kind,
        snippets=tuple(YouTubeCaptionSnippet(text, i * 3.0, 2.5) for i, text in enumerate(SPOKEN)))


def client_for(tmp_path, source, *, youtube=None, supadata=None, cap=20):
    ledger = SpendLedger(tmp_path / "spend.json")
    youtube = youtube if youtube is not None else FakeCaptionClient(None)
    policy_client = PolicyCaptionClient(youtube, supadata, lambda: ledger, source=lambda: source, daily_cap=lambda: cap)
    return policy_client, youtube, ledger


# -- 1. native mode only -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("source", ["supadata_native", "youtube_then_supadata_native"])
@pytest.mark.parametrize("answer", [transcript(), None, SupadataTranscriptRequestFailed(), SupadataTranscriptTimedOut(),
                                    SupadataTranscriptMalformed()])
def test_supadata_is_only_ever_asked_for_native_mode(tmp_path, source, answer):
    supadata = FakeSupadata(answer)
    client, _youtube, _ledger = client_for(tmp_path, source, supadata=supadata)
    try:
        client.fetch_track(VIDEO_ID, "en")
    except (ProviderRequestFailed, ProviderTimedOut):
        pass
    assert supadata.calls and supadata.modes == {NATIVE_MODE} == {"native"}


def test_the_real_client_puts_mode_native_on_the_wire(tmp_path):
    """Through the real SupadataTranscriptClient and a fake HTTP session: the query string says native, nothing else."""
    sent = []

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"lang": "en", "content": [{"text": "Hello there everyone.", "offset": 0, "duration": 2000, "lang": "en"}]}

    class Session:
        def get(self, url, **kwargs):
            sent.append((url, kwargs["params"]))
            return Response()

    real = SupadataTranscriptClient("a-test-key", session=Session())
    client, _youtube, _ledger = client_for(tmp_path, "supadata_native", supadata=real)
    track = client.fetch_track(VIDEO_ID, "en")
    assert [params["mode"] for _url, params in sent] == ["native"]
    assert sent[0][1]["url"] == URL and sent[0][1]["lang"] == "en"
    assert track is not None and track.provider == "supadata"


def test_the_module_cannot_name_another_mode():
    text = Path(inspect.getsourcefile(caption_source)).read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    body = code.split('"""', 2)[2]  # past the docstring, which explains why the other modes are never used
    assert '"auto"' not in body and '"generate"' not in body and "translate" not in body
    assert body.count("mode=") == 1 and "mode=NATIVE_MODE" in body


# -- 2. each caption_source ---------------------------------------------------------------------------------------------


def test_youtube_source_never_calls_supadata_and_returns_youtubes_track(tmp_path):
    supadata = FakeSupadata(transcript())
    youtube = FakeCaptionClient(youtube_track())
    client, _y, ledger = client_for(tmp_path, "youtube", youtube=youtube, supadata=supadata)
    track = client.fetch_track(VIDEO_ID, "en")
    assert track.provider == "" and track.kind == "manual" and supadata.calls == [] and ledger.requests_today() == 0


def test_supadata_native_source_never_asks_youtube(tmp_path):
    youtube = FakeCaptionClient(youtube_track())
    supadata = FakeSupadata(transcript())
    client, _y, _l = client_for(tmp_path, "supadata_native", youtube=youtube, supadata=supadata)
    track = client.fetch_track(VIDEO_ID, "en")
    assert youtube.calls == [] and len(supadata.calls) == 1
    assert track.provider == "supadata" and track.kind == "unknown" and track.source_language == "en"
    assert supadata.calls[0][0] == URL


def test_youtube_then_supadata_prefers_youtube_and_spends_nothing_when_it_has_captions(tmp_path):
    supadata = FakeSupadata(transcript())
    client, youtube, ledger = client_for(tmp_path, "youtube_then_supadata_native",
                                         youtube=FakeCaptionClient(youtube_track()), supadata=supadata)
    assert client.fetch_track(VIDEO_ID, "en").provider == "" and supadata.calls == [] and ledger.requests_today() == 0


@pytest.mark.parametrize("youtube", [FakeCaptionClient(None), FakeCaptionClient(None, error=ProviderRequestFailed()),
                                     FakeCaptionClient(None, error=ProviderTimedOut())])
def test_youtube_then_supadata_asks_supadata_when_youtube_gives_no_track(tmp_path, youtube):
    supadata = FakeSupadata(transcript())
    client, _y, ledger = client_for(tmp_path, "youtube_then_supadata_native", youtube=youtube, supadata=supadata)
    track = client.fetch_track(VIDEO_ID, "en")
    assert track.provider == "supadata" and len(supadata.calls) == 1 and ledger.requests_today() == 1


def test_when_neither_has_captions_a_youtube_refusal_is_still_a_refusal(tmp_path):
    client, _y, _l = client_for(tmp_path, "youtube_then_supadata_native",
                                youtube=FakeCaptionClient(None, error=ProviderRequestFailed()), supadata=FakeSupadata(None))
    with pytest.raises(ProviderRequestFailed):
        client.fetch_track(VIDEO_ID, "en")
    quiet, _y, _l = client_for(tmp_path / "q", "youtube_then_supadata_native", youtube=FakeCaptionClient(None),
                               supadata=FakeSupadata(None))
    assert quiet.fetch_track(VIDEO_ID, "en") is None  # YouTube said "no track" and so did Supadata


def test_an_unknown_source_value_is_the_default_behaviour(tmp_path):
    supadata = FakeSupadata(transcript())
    client, _y, _l = client_for(tmp_path, "something-else", youtube=FakeCaptionClient(youtube_track()), supadata=supadata)
    assert client.fetch_track(VIDEO_ID, "en").provider == "" and supadata.calls == []


def test_supadata_chosen_but_not_configured_is_a_stable_reason(tmp_path):
    client, _y, ledger = client_for(tmp_path, "supadata_native", supadata=None)
    with pytest.raises(CaptionNotConfigured) as caught:
        client.fetch_track(VIDEO_ID, "en")
    assert caught.value.reason == "caption_unconfigured" and ledger.requests_today() == 0


def test_the_default_is_youtube_and_the_environment_overrides_it(monkeypatch):
    assert policies.default("media.caption_source") == "youtube" and policies.value("media.caption_source") == "youtube"
    assert caption_source.caption_source() == "youtube"
    for value in policies.BY_KEY["media.caption_source"].choices:
        monkeypatch.setenv("MEDIA_CAPTION_SOURCE", value)
        assert caption_source.caption_source() == value
    monkeypatch.setenv("MEDIA_CAPTION_SOURCE", "generate")  # not a choice: the default, never an unknown mode
    assert caption_source.caption_source() == "youtube"
    assert policies.default("media.supadata_daily_requests") == 20
    monkeypatch.setenv("MEDIA_SUPADATA_DAILY_REQUESTS", "3")
    assert policies.value("media.supadata_daily_requests") == 3


# -- 3. the daily credit guard ------------------------------------------------------------------------------------------


def test_the_daily_cap_refuses_without_a_call_and_each_call_is_one_row(tmp_path):
    supadata = FakeSupadata(transcript())
    client, _y, ledger = client_for(tmp_path, "supadata_native", supadata=supadata, cap=2)
    client.fetch_track("aaaaaaaaaaa", "en")
    client.fetch_track("bbbbbbbbbbb", "en")
    with pytest.raises(CaptionQuotaReached) as refused:
        client.fetch_track("ccccccccccc", "en")
    assert refused.value.reason == "caption_quota" and len(supadata.calls) == 2  # the third sent nothing
    rows = [event for event in ledger._read() if event["kind"] == KIND_SUPADATA]
    assert len(rows) == 2 and all(row["units"] == 1 and row["usd"] == 0 and row["provider"] == "supadata" for row in rows)
    assert ledger.summary()["supadata_requests_today"] == 2
    ledger.check("asr", "b", 0.01)  # the dollar caps are untouched by request rows
    assert ledger.limits() == {"asr": 5.0, "ai": 10.0, "day": 25.0}


def test_a_cap_of_zero_turns_supadata_off(tmp_path):
    supadata = FakeSupadata(transcript())
    client, _y, _l = client_for(tmp_path, "supadata_native", supadata=supadata, cap=0)
    with pytest.raises(CaptionQuotaReached):
        client.fetch_track(VIDEO_ID, "en")
    assert supadata.calls == []


def test_a_cap_in_youtube_then_supadata_does_not_stop_youtube_captions(tmp_path):
    client, _y, _l = client_for(tmp_path, "youtube_then_supadata_native", youtube=FakeCaptionClient(youtube_track()),
                                supadata=FakeSupadata(transcript()), cap=0)
    assert client.fetch_track(VIDEO_ID, "en").provider == ""


def test_a_failed_call_is_counted_and_never_repeated(tmp_path):
    supadata = FakeSupadata(SupadataTranscriptRequestFailed())
    client, _y, ledger = client_for(tmp_path, "supadata_native", supadata=supadata)
    with pytest.raises(ProviderRequestFailed):
        client.fetch_track(VIDEO_ID, "en")
    assert len(supadata.calls) == 1 and ledger.requests_today() == 1


def test_one_video_is_paid_for_once_within_the_memo_window(tmp_path):
    now = {"t": 0.0}
    supadata = FakeSupadata(None)
    ledger = SpendLedger(tmp_path / "spend.json")
    client = PolicyCaptionClient(FakeCaptionClient(None), supadata, lambda: ledger, source=lambda: "supadata_native",
                                 daily_cap=lambda: 20, clock=lambda: now["t"])
    assert client.fetch_track(VIDEO_ID, "en") is None and client.fetch_track(VIDEO_ID, "en") is None  # import, then pipeline
    assert len(supadata.calls) == 1
    now["t"] = caption_source.MEMO_SECONDS + 1
    client.fetch_track(VIDEO_ID, "en")
    assert len(supadata.calls) == 2


# -- 4. through the adapter and the pipeline: no track, provenance ----------------------------------------------------


def make_world(tmp_path, source, monkeypatch, *, supadata, youtube=None, cap=20, policy=None):
    monkeypatch.setenv("MEDIA_CAPTION_SOURCE", source)
    ledger = SpendLedger(tmp_path / "spend.json")
    adapter = build_youtube_adapter(metadata_client=FakeMetadataClient(), caption_client=PolicyCaptionClient(
        youtube if youtube is not None else FakeCaptionClient(None), supadata, lambda: ledger, daily_cap=lambda: cap))
    ingestion = MediaIngestionService(adapters=(adapter,), source_language_supported=lambda code: code in {"en", "zh"})
    store, entry, pipeline = _world(tmp_path, ingestion=ingestion, asr=Asr())
    audio, spy = Audio(), SpyLedger()
    pipeline._youtube_audio, pipeline._ledger = audio, spy
    source_fields = {**entry.source, "caption_kind": "", "caption_status": ""}
    if policy:
        source_fields[mtp.SOURCE_TRANSCRIPT_POLICY] = policy
    first = replace(entry, status="processing", processing={"state": "running"}, source=source_fields, lesson=None)
    store.upsert(first)
    return store, first, pipeline, audio, spy, ledger


def test_native_captions_become_a_provider_caption_transcript_with_honest_provenance(tmp_path, monkeypatch):
    supadata = FakeSupadata(transcript())
    store, entry, pipeline, audio, spy, ledger = make_world(tmp_path, "supadata_native", monkeypatch, supadata=supadata)
    pipeline._run(store, None, entry.media_id, "b1", None)
    stored = store.get(entry.media_id)
    processing = stored.processing
    assert processing["origin"] == mtp.ORIGIN_CAPTION == "provider_caption"
    assert processing["caption_provider"] == "supadata"
    assert processing["caption_kind"] == "unknown" and processing["caption_kind"] not in {"manual", "auto"}
    assert processing["caption_language"] == "en"
    assert processing["caption_fallback"] == "" and processing["state"] == "held"
    assert supadata.modes == {"native"} and len(supadata.calls) == 1 and ledger.requests_today() == 1
    assert audio.calls == 0 and spy.recorded == []  # no audio, no ASR spend
    from writing_coach.admin_content import media_outcome
    shown = media_outcome(stored)["transcript"]
    assert (shown["origin"], shown["caption_provider"], shown["caption_kind"], shown["caption_language"]) == (
        "provider_caption", "supadata", "unknown", "en")


def test_a_youtube_caption_import_still_records_no_other_provider(tmp_path, monkeypatch):
    store, entry, pipeline, audio, spy, _ledger = make_world(
        tmp_path, "youtube", monkeypatch, supadata=FakeSupadata(transcript()), youtube=FakeCaptionClient(youtube_track()))
    pipeline._run(store, None, entry.media_id, "b1", None)
    processing = store.get(entry.media_id).processing
    assert processing["origin"] == "provider_caption" and processing["caption_kind"] == "manual"
    assert processing["caption_provider"] == "" and processing["caption_language"] == ""


def test_the_import_records_the_supadata_provenance_on_the_item(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_CAPTION_SOURCE", "supadata_native")
    ledger = SpendLedger(tmp_path / "spend.json")
    adapter = build_youtube_adapter(metadata_client=FakeMetadataClient(), caption_client=PolicyCaptionClient(
        FakeCaptionClient(None), FakeSupadata(transcript()), lambda: ledger))
    service = MediaIngestionService(adapters=(adapter,), source_language_supported=lambda code: code in {"en", "zh"})
    acquisition = service.import_media(URL, "en", "en")
    assert acquisition.provenance["caption_provider"] == "supadata" and acquisition.provenance["caption_kind"] == "unknown"
    assert acquisition.provenance["caption_language"] == "en"


@pytest.mark.parametrize("source", ["supadata_native", "youtube_then_supadata_native"])
def test_no_native_track_with_captions_only_stops_before_audio_and_spends_nothing(tmp_path, monkeypatch, source):
    supadata = FakeSupadata(None)
    store, entry, pipeline, audio, spy, ledger = make_world(
        tmp_path, source, monkeypatch, supadata=supadata, policy=mtp.POLICY_CAPTIONS_ONLY)
    pipeline._run(store, None, entry.media_id, "b1", None)
    stored = store.get(entry.media_id)
    assert stored.processing["state"] == "failed" and stored.processing["reason"] == "captions_unavailable"
    assert stored.status == "review" and stored.lesson is None
    assert audio.calls == 0 and spy.recorded == [] and spy.checked == []
    assert supadata.modes == {"native"} and ledger.requests_today() == 1  # the pipeline did not ask twice for one video


@pytest.mark.parametrize("policy", [None, mtp.POLICY_DEFAULT])
@pytest.mark.parametrize("answer, reason", [(None, mtp.REASON_YOUTUBE_NO_CAPTIONS),
                                            (SupadataTranscriptRequestFailed(), "captions_unavailable")])
def test_no_native_track_with_the_default_policy_no_longer_falls_back_to_asr(tmp_path, monkeypatch, policy, answer, reason):
    """Rights decision 2026-10-19 (D-244): a YouTube video with no captions is not heard; it stops with the rights reason,
    and a refused request keeps its own retryable reason. No audio is downloaded and nothing is spent."""
    supadata = FakeSupadata(answer)
    store, entry, pipeline, audio, spy, _ledger = make_world(
        tmp_path / f"{policy}-{reason}", "supadata_native", monkeypatch, supadata=supadata, policy=policy)
    pipeline._speech = lambda *_a: pytest.fail("speech recognition was run for a YouTube video")
    pipeline._run(store, None, entry.media_id, "b1", None)
    processing = store.get(entry.media_id).processing
    assert processing["state"] == "failed" and processing["reason"] == reason and "origin" not in processing
    assert audio.calls == 0 and spy.recorded == []


def test_a_refused_native_request_is_a_visible_fallback_in_the_default_and_a_stop_in_captions_only(tmp_path, monkeypatch):
    refused = FakeSupadata(SupadataTranscriptRequestFailed())
    store, entry, pipeline, audio, _spy, _l = make_world(
        tmp_path / "only", "supadata_native", monkeypatch, supadata=refused, policy=mtp.POLICY_CAPTIONS_ONLY)
    pipeline._run(store, None, entry.media_id, "b1", None)
    assert store.get(entry.media_id).processing["reason"] == "captions_unavailable" and audio.calls == 0
    assert len(refused.calls) == 1  # one request, not repeated


def test_past_the_daily_cap_the_stable_reason_is_caption_quota_and_nothing_is_called(tmp_path, monkeypatch):
    supadata = FakeSupadata(transcript())
    store, entry, pipeline, audio, spy, ledger = make_world(
        tmp_path, "supadata_native", monkeypatch, supadata=supadata, cap=0, policy=mtp.POLICY_CAPTIONS_ONLY)
    pipeline._run(store, None, entry.media_id, "b1", None)
    stored = store.get(entry.media_id)
    assert stored.processing["state"] == "failed" and stored.processing["reason"] == "caption_quota"
    assert stored.processing["message"] and mtp.reason_message("caption_quota")
    assert supadata.calls == [] and ledger.requests_today() == 0 and audio.calls == 0 and spy.recorded == []


def test_past_the_daily_cap_the_default_policy_stops_with_the_cap_and_does_not_listen(tmp_path, monkeypatch):
    # Since D-244 the default policy no longer listens to a YouTube video in place of its captions.
    supadata = FakeSupadata(transcript())
    store, entry, pipeline, audio, _spy, _l = make_world(tmp_path, "supadata_native", monkeypatch, supadata=supadata, cap=0)
    pipeline._speech = lambda *_a: pytest.fail("speech recognition was run for a YouTube video")
    pipeline._run(store, None, entry.media_id, "b1", None)
    processing = store.get(entry.media_id).processing
    assert processing["state"] == "failed" and processing["reason"] == "caption_quota"
    assert supadata.calls == [] and audio.calls == 0


# -- 5. merged chunks and the five checks ---------------------------------------------------------------------------


def _observe(chunks, duration_ms):
    cues = [Cue(c.offset_ms, c.offset_ms + c.duration_ms, c.text) for c in chunks]
    lines = segment_lines(cues, "en")
    checks = validate_lines(lines, language="en", duration_ms=duration_ms)
    return cues, lines, checks


@pytest.mark.parametrize("name, size", [("one sentence per chunk", 1), ("four sentences merged", 4), ("the whole video in one chunk", 8)])
def test_merged_supadata_chunks_still_pass_the_five_checks(name, size, capsys):
    sentences = SPOKEN * 3                                         # 24 sentences, 72 s
    chunks = []
    for start in range(0, len(sentences), size):
        text = " ".join(sentences[start:start + size])
        chunks.append(SupadataTranscriptChunk(text, start * 3000, size * 3000 - 500, "en"))
    cues, lines, checks = _observe(chunks, len(sentences) * 3000)
    print(f"{name}: chunks={len(cues)} chunk_chars(max)={max(len(c.text) for c in cues)} "
          f"chunk_seconds(max)={max(c.end_ms - c.start_ms for c in cues) / 1000:.1f} -> lines={len(lines)} "
          f"line_chars(max)={max(len(l.text) for l in lines)} line_seconds(max)={max(l.end_ms - l.start_ms for l in lines) / 1000:.1f}")
    assert [check["id"] for check in checks] == ["non_empty", "language", "coverage", "segments", "repetition"]
    assert first_failure(checks) == "", checks
    assert all(len(line.text) <= 140 for line in lines)
    assert all(line.end_ms - line.start_ms <= 9000 for line in lines)


def test_a_merged_chunk_keeps_its_words_and_its_order():
    chunk = SupadataTranscriptChunk(" ".join(SPOKEN), 0, 24000, "en")
    _cues, lines, _checks = _observe([chunk], 24000)
    assert " ".join(line.text for line in lines).split() == " ".join(SPOKEN).split()
    assert all(a.end_ms <= b.start_ms for a, b in zip(lines, lines[1:], strict=False))


# -- 6. scope: Supadata is the admin pipeline's only (review of #229, P1-2) --------------------------------------------


def _two_services(tmp_path):
    """The learner's acquisition service (today's YouTube-only adapter) and the admin one (the policy client)."""
    supadata = FakeSupadata(transcript())
    ledger = SpendLedger(tmp_path / "spend.json")

    def languages(code):
        return code in {"en", "zh"}

    learner_captions = FakeCaptionClient(youtube_track())
    learner = MediaIngestionService(adapters=(build_youtube_adapter(
        metadata_client=FakeMetadataClient(), caption_client=learner_captions),), source_language_supported=languages)
    admin = MediaIngestionService(adapters=(build_youtube_adapter(
        metadata_client=FakeMetadataClient(),
        caption_client=PolicyCaptionClient(FakeCaptionClient(None), supadata, lambda: ledger)),),
        source_language_supported=languages)
    return learner, admin, supadata, ledger, learner_captions


def _importer(tmp_path, learner, admin):
    from writing_coach.book_asset_store import FilesystemBookAssetStore
    from writing_coach.media_library_store import FileMediaLibraryStore
    from writing_coach.media_source_import import MediaSourceImporter
    return MediaSourceImporter(learner, FileMediaLibraryStore(tmp_path / "index"), FilesystemBookAssetStore(tmp_path / "assets"),
                               admin_ingestion=admin)


def test_a_learner_import_makes_zero_supadata_calls_and_an_admin_import_makes_one(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_CAPTION_SOURCE", "supadata_native")
    learner, admin, supadata, ledger, learner_captions = _two_services(tmp_path)
    importer = _importer(tmp_path, learner, admin)
    entry, _ = importer._from_url(URL, language="en", imported_by="learner", persist_media=True)
    assert supadata.calls == [] and ledger.requests_today() == 0 and learner_captions.calls  # YouTube's own client
    assert entry.source.get("caption_provider", "") == ""
    admin_entry, _ = importer._from_url(URL, language="en", imported_by="admin@example.test", persist_media=True)
    assert len(supadata.calls) == 1 and supadata.modes == {"native"} and ledger.requests_today() == 1
    assert admin_entry.source["caption_provider"] == "supadata" and admin_entry.source["caption_kind"] == "unknown"


def test_a_learner_path_never_previews_through_supadata_but_the_admin_preview_does(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_CAPTION_SOURCE", "supadata_native")
    learner, admin, supadata, _ledger, _captions = _two_services(tmp_path)
    importer = _importer(tmp_path, learner, admin)
    importer._from_youtube(URL, language="en", imported_by="learner")
    assert supadata.calls == []
    importer.preview(URL, language="en")   # the admin console's preview
    assert len(supadata.calls) == 1


def test_the_pipeline_asks_the_admin_service_for_shared_items_and_the_learner_one_for_personal_items(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_CAPTION_SOURCE", "supadata_native")
    learner, admin, supadata, _ledger, _captions = _two_services(tmp_path)
    store, entry, pipeline = _world(tmp_path, ingestion=learner, asr=Asr(), admin_ingestion=admin)
    cues, _error, kind, provider, _language = pipeline._captions(replace(entry, library="personal"))
    assert cues and provider == "" and kind == "manual" and supadata.calls == []
    cues, _error, kind, provider, language = pipeline._captions(replace(entry, library="shared"))
    assert cues and provider == "supadata" and kind == "unknown" and language == "en" and len(supadata.calls) == 1


def test_app_builds_the_learner_adapter_plain_and_gives_only_the_admin_importer_the_policy_adapter():
    app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert "adapters=(build_youtube_adapter(),)" in app_source
    assert app_source.count("PolicyCaptionClient(") == 1
    assert "admin_ingestion=_admin_media_ingestion_service" in app_source
    assert 'capability="media_caption_supadata"' in app_source


# -- 7. concurrency, memo, definitive answers, telemetry, env -------------------------------------------------------------


def test_concurrent_callers_cannot_overshoot_the_cap_or_double_pay(tmp_path):
    import threading
    import time as _time

    class Slow(FakeSupadata):
        def fetch(self, url, language, *, mode="auto"):
            _time.sleep(0.02)
            return super().fetch(url, language, mode=mode)

    supadata = Slow(transcript())
    client, _y, ledger = client_for(tmp_path, "supadata_native", supadata=supadata, cap=3)
    refused = []

    def run(video):
        try:
            client.fetch_track(video, "en")
        except CaptionQuotaReached:
            refused.append(video)

    videos = [chr(97 + i % 8) * 11 for i in range(24)]     # 8 videos, each asked for by 3 threads at once
    threads = [threading.Thread(target=run, args=(video,)) for video in videos]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(supadata.calls) == 3 == ledger.requests_today()   # the cap, exactly
    assert len({url for url, _lang, _mode in supadata.calls}) == 3     # one paid call per video: no double-pay


def test_reserve_request_is_check_and_record_in_one_step(tmp_path):
    import threading
    ledger = SpendLedger(tmp_path / "spend.json")
    granted = []

    def take():
        try:
            ledger.reserve_request(5)
            granted.append(1)
        except Exception:  # noqa: BLE001
            pass

    threads = [threading.Thread(target=take) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(granted) == 5 == ledger.requests_today()


def test_the_memo_evicts_the_oldest_answer_not_all_of_them(tmp_path):
    supadata = FakeSupadata(None)
    client, _y, _l = client_for(tmp_path, "supadata_native", supadata=supadata, cap=1000)
    ids = [f"v{n:010d}" for n in range(caption_source.MEMO_MAX + 1)]
    for video in ids:
        client.fetch_track(video, "en")
    assert len(client._memo) == caption_source.MEMO_MAX
    paid = len(supadata.calls)
    client.fetch_track(ids[-1], "en")   # the newest is still remembered
    assert len(supadata.calls) == paid
    client.fetch_track(ids[0], "en")    # the oldest was evicted, so it is asked again
    assert len(supadata.calls) == paid + 1


def _session(status):
    class Response:
        status_code = status

        @staticmethod
        def json():
            return {}

    class Session:
        calls = 0

        def get(self, *_a, **_k):
            Session.calls += 1
            return Response()

    return Session


@pytest.mark.parametrize("status", [206, 404, 422])
def test_supadata_saying_no_transcript_is_a_definitive_no_track_that_is_not_paid_for_again(tmp_path, status):
    session = _session(status)
    client, _y, ledger = client_for(tmp_path, "supadata_native", supadata=SupadataTranscriptClient("a-test-key", session=session()))
    assert client.fetch_track(VIDEO_ID, "en") is None and client.fetch_track(VIDEO_ID, "en") is None
    assert session.calls == 1 and ledger.requests_today() == 1   # a Reprocess does not re-spend


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_real_errors_are_not_remembered_and_not_retried(tmp_path, status):
    session = _session(status)
    client, _y, _l = client_for(tmp_path, "supadata_native", supadata=SupadataTranscriptClient("a-test-key", session=session()))
    with pytest.raises(ProviderRequestFailed):
        client.fetch_track(VIDEO_ID, "en")
    assert session.calls == 1          # no automatic retry
    assert client._memo == {}          # and not remembered: the operator's Reprocess asks again


def test_native_caption_calls_are_logged_under_their_own_capability(monkeypatch):
    from writing_coach.ai import audio_telemetry
    seen = []
    monkeypatch.setattr(audio_telemetry, "record_audio_operation", lambda capability, **kwargs: seen.append(capability))

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"lang": "en", "content": [{"text": "Hello there everyone.", "offset": 0, "duration": 2000}]}

    class Session:
        def get(self, *_a, **_k):
            return Response()

    SupadataTranscriptClient("k", session=Session(), capability="media_caption_supadata").fetch(URL, "en", mode="native")
    SupadataTranscriptClient("k", session=Session()).fetch(URL, "en", mode="native")
    assert seen == ["media_caption_supadata", "media_transcript_fallback"]


def test_a_bad_caption_source_value_logs_one_warning_then_uses_the_default(monkeypatch, caplog):
    monkeypatch.setenv("MEDIA_CAPTION_SOURCE", "supadata-native")
    policies._WARNED_ENV.discard("MEDIA_CAPTION_SOURCE")
    with caplog.at_level("WARNING", logger="writing_coach.policies"):
        assert [caption_source.caption_source() for _ in range(3)] == ["youtube"] * 3
    warnings = [r for r in caplog.records if "MEDIA_CAPTION_SOURCE" in r.getMessage()]
    assert len(warnings) == 1
