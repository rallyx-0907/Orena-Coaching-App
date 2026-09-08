"""The transcript acquisition producer: never invent, never relabel, never re-buy.

This script is the half of the offline ingestion path that talks to providers.
It runs where provider access works and writes a canonical handoff file that a
blocked build host can consume. Because it is the only place that decides what a
transcript IS, three properties have to hold no matter which provider answered:

* a source that cannot be acquired is reported and skipped, never filled in;
* speech recognition output is never recorded as the provider's own captions;
* an already-acquired transcript is never bought again.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _script():
    spec = importlib.util.spec_from_file_location(
        "acquire_listening_transcripts", ROOT / "scripts/acquire_listening_transcripts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ACQUIRE = _script()

CSV = """candidate_id,language,category,source_family,title,source_url,desired_excerpt_count,min_excerpt_seconds,max_excerpt_seconds,preferred_modes,level_hint,caption_check,embed_check,content_suitability_review,production_rights_review,notes
zh-001,zh,animation,Family,A scene,https://www.youtube.com/watch?v=aaaaaaaaaaa,1-2,15,90,listen,,x,x,x,x,
zh-002,zh,animation,Family,Another,https://www.youtube.com/watch?v=bbbbbbbbbbb,1-2,15,90,listen,,x,x,x,x,
"""


@pytest.fixture
def sources(tmp_path):
    path = tmp_path / "sources.csv"
    path.write_text(CSV, encoding="utf-8")
    return path


def run(monkeypatch, sources, out, order, **kwargs):
    """Run main() with a chosen acquisition chain."""

    monkeypatch.setattr(ACQUIRE, "ACQUIRERS", order)
    argv = ["acquire", str(sources), "--out", str(out)]
    for key, value in kwargs.items():
        argv += [f"--{key.replace('_', '-')}", str(value)]
    monkeypatch.setattr("sys.argv", argv)
    return ACQUIRE.main()


def segments(count: int = 3):
    return [{"start_ms": i * 4000, "end_ms": (i + 1) * 4000, "original_text": f"line {i}"}
            for i in range(count)]


def test_an_unacquirable_source_is_reported_never_invented(monkeypatch, sources, tmp_path, capsys):
    out = tmp_path / "t.json"
    order = (("a", lambda v, l: None), ("b", lambda v, l: None))
    run(monkeypatch, sources, out, order)

    assert json.loads(out.read_text(encoding="utf-8")) == {}, "no transcript may be fabricated"
    assert "UNACQUIRED" in capsys.readouterr().out


def test_a_failing_provider_falls_through_to_the_next(monkeypatch, sources, tmp_path):
    out = tmp_path / "t.json"

    def broken(video_id, language):
        raise RuntimeError("provider exploded")

    def works(video_id, language):
        return {"origin": "generated_asr", "language": "zh", "provider": "groq",
                "model": "whisper", "segments": segments()}

    run(monkeypatch, sources, out, (("broken", broken), ("works", works)))
    written = json.loads(out.read_text(encoding="utf-8"))
    assert set(written) == {"aaaaaaaaaaa", "bbbbbbbbbbb"}
    assert all(entry["origin"] == "generated_asr" for entry in written.values())


def test_an_already_acquired_transcript_is_never_bought_again(monkeypatch, sources, tmp_path):
    out = tmp_path / "t.json"
    out.write_text(json.dumps({
        "aaaaaaaaaaa": {"origin": "provider_caption", "language": "zh",
                        "provider": "youtube", "model": "", "segments": segments()},
    }), encoding="utf-8")

    calls: list[str] = []

    def counting(video_id, language):
        calls.append(video_id)
        return {"origin": "generated_asr", "language": "zh", "provider": "groq",
                "model": "whisper", "segments": segments()}

    run(monkeypatch, sources, out, (("counting", counting),))

    assert calls == ["bbbbbbbbbbb"], "the already-acquired source must not be re-acquired"
    written = json.loads(out.read_text(encoding="utf-8"))
    assert len(written) == 2, "the file is merged, not replaced"
    # And the existing entry keeps its own provenance rather than being restamped.
    assert written["aaaaaaaaaaa"]["origin"] == "provider_caption"


def test_limit_bounds_how_much_is_acquired(monkeypatch, sources, tmp_path):
    out = tmp_path / "t.json"
    calls: list[str] = []

    def counting(video_id, language):
        calls.append(video_id)
        return {"origin": "generated_asr", "language": "zh", "provider": "groq",
                "model": "", "segments": segments()}

    run(monkeypatch, sources, out, (("counting", counting),), limit=1)
    assert len(calls) == 1, "--limit must bound paid acquisition"


def test_segments_without_real_timing_are_dropped_not_repaired() -> None:
    rows = [
        {"text": "good", "start_ms": 0, "end_ms": 1000},
        {"text": "   ", "start_ms": 1000, "end_ms": 2000},      # no text
        {"text": "backwards", "start_ms": 3000, "end_ms": 3000},  # zero length
        {"text": "  spaced   out  ", "start_ms": 4000, "end_ms": 5000},
    ]
    kept = ACQUIRE._segments(rows)
    assert [s["original_text"] for s in kept] == ["good", "spaced out"]
    assert all(s["end_ms"] > s["start_ms"] for s in kept)


def test_supadata_output_is_never_labelled_provider_captions(monkeypatch) -> None:
    """Supadata's auto mode does not say whether it read captions or generated them.

    Guessing the flattering answer would let machine text reach a learner as the
    source's own captions, so it stays generated_asr.
    """

    class Chunk:
        def __init__(self, text, offset):
            self.text, self.offset_ms, self.duration_ms = text, offset, 2000

    class Transcript:
        language = "zh"
        chunks = (Chunk("你好", 0), Chunk("再见", 2000))

    class FakeClient:
        def __init__(self, *a, **k): pass
        def fetch(self, *a, **k): return Transcript()

    import writing_coach.media_providers.supadata as supadata
    monkeypatch.setattr(supadata, "SupadataTranscriptClient", FakeClient)
    monkeypatch.setenv("SUPADATA_API_KEY", "test-key")

    entry = ACQUIRE.from_supadata("aaaaaaaaaaa", "zh")
    assert entry["origin"] == ACQUIRE.GENERATED_ASR
    assert entry["origin"] != ACQUIRE.PROVIDER_CAPTION
    assert entry["provider"] == "supadata"
    assert len(entry["segments"]) == 2


def test_native_captions_are_the_only_path_that_claims_provider_captions(monkeypatch) -> None:
    class Snippet:
        def __init__(self, text, start):
            self.text, self.start_seconds, self.duration_seconds = text, start, 2.0

    class Track:
        source_language = "en"
        snippets = (Snippet("hello there", 0.0), Snippet("general kenobi", 2.0))

    class FakeClient:
        def __init__(self, *a, **k): pass
        def fetch_track(self, *a, **k): return Track()

    import writing_coach.media_providers.youtube as youtube
    monkeypatch.setattr(youtube, "PublicYouTubeCaptionClient", FakeClient)

    entry = ACQUIRE.from_native_captions("aaaaaaaaaaa", "en")
    assert entry["origin"] == ACQUIRE.PROVIDER_CAPTION
    assert entry["segments"][0] == {"start_ms": 0, "end_ms": 2000,
                                    "original_text": "hello there"}


def test_the_handoff_shape_is_what_the_offline_adapter_consumes(monkeypatch, sources, tmp_path):
    """Producer and consumer must agree, or the handoff is theatre."""

    from writing_coach.listening_source_import import OfflineTranscriptAdapter

    out = tmp_path / "t.json"
    run(monkeypatch, sources, out, (("ok", lambda v, l: {
        "origin": "generated_asr", "language": "zh", "provider": "groq",
        "model": "whisper", "segments": segments(8)}),))

    payload = json.loads(out.read_text(encoding="utf-8"))
    adapter = OfflineTranscriptAdapter(payload)
    acquisition = adapter.acquire("https://www.youtube.com/watch?v=aaaaaaaaaaa", "zh")

    assert acquisition.media_object.transcript is not None
    assert len(acquisition.media_object.transcript.segments) == 8
    assert acquisition.transcript_status == "generated"
    assert acquisition.playback.url
