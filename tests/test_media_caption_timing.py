"""Caption timing follows the speech, and a transcript whose timing does not is never published (P0 2026-10-20).

Evidence: Passport Rush (`youtube-ZncA70OAgPw`) on :8000. Its automatic YouTube captions roll: each cue stays on screen
until the cue after next starts. The line builder took that display window as speech and pushed every following line's
start to the previous line's inflated end, so the subtitle ran up to two seconds late and "Everyone's already here." was
squeezed into 6800-7200 ms. The fixture holds the track's raw cues, the same track's json3 word offsets (the truth for
when each word is spoken) and the lines :8000 served. Nothing here reaches a network, a downloader or a recogniser.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from writing_coach.media_caption_timing import (
    KIND_AUTO,
    KIND_MANUAL,
    KIND_UNKNOWN,
    REASON_CAPTION_TIMING,
    TIMING_KEY,
    TIMING_NEXT_START,
    TimingThresholds,
    caption_timing_report,
    classify_caption_kind,
    clip_to_next_start,
)
from writing_coach.media_segmentation import Cue, segment_lines

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "media_caption_timing_passport_rush.json").read_text(encoding="utf-8"))


def _raw_cues() -> list[Cue]:
    return [Cue(c["start_ms"], c["start_ms"] + c["duration_ms"], c["text"]) for c in FIXTURE["cues"]]


def _stored_lines() -> list[Cue]:
    return [Cue(line["start_ms"], line["end_ms"], line["text"]) for line in FIXTURE["stored_8000_lines"]]


def _spoken_at(first_word: str, after_ms: int = 0) -> int:
    """When the track says this word is spoken (json3 `tOffsetMs`), the truth a line's start is measured against."""
    return next(w["start_ms"] for w in FIXTURE["json3_words"] if w["text"].lstrip(">").strip() == first_word and w["start_ms"] >= after_ms)


def _line(lines: list[Cue], prefix: str) -> Cue:
    return next(line for line in lines if line.text.replace(">> ", "").startswith(prefix))


# -- the root cause, reproduced -----------------------------------------------------------------------------------


def test_the_old_cut_reproduces_the_lines_8000_served():
    lines = segment_lines(_raw_cues(), "en")
    served = _stored_lines()[:9]
    assert [(line.start_ms, line.end_ms, line.text) for line in lines[:9]] == [
        (line.start_ms, line.end_ms, line.text) for line in served]
    late = _line(lines, "Of course")
    assert late.start_ms - _spoken_at("Of") == 2000   # two seconds behind the voice


def test_the_lines_8000_served_fail_the_gate():
    report = caption_timing_report(_stored_lines(), language="en", caption_kind=classify_caption_kind(KIND_UNKNOWN, _stored_lines()),
                                   retimed=False)
    assert not report.passed and report.reason == REASON_CAPTION_TIMING
    assert "not_retimed" in report.failed and "defects" in report.failed
    assert report.counts["fast"] >= 3 and report.counts["short_dense"] >= 1


# -- the fix ---------------------------------------------------------------------------------------------------------


def test_cues_end_no_later_than_the_next_start_and_lines_start_with_the_voice():
    clipped, changed = clip_to_next_start(_raw_cues())
    assert changed >= 7
    assert all(cue.end_ms <= later.start_ms for cue, later in zip(clipped, clipped[1:], strict=False) if later.start_ms > cue.start_ms)
    lines = segment_lines(clipped, "en")
    for prefix, word in (("Well", "Well,"), ("Everyone", "Everyone's"), ("Of course", "Of"), ("Yeah", "Yeah,")):
        line = _line(lines, prefix)
        assert abs(line.start_ms - _spoken_at(word)) <= 150, (prefix, line, _spoken_at(word))
    report = caption_timing_report(lines, language="en", caption_kind=KIND_AUTO, retimed=True)
    assert report.passed, report.as_dict()


def test_clipping_is_idempotent_and_leaves_parallel_cues_alone():
    once, _ = clip_to_next_start(_raw_cues())
    twice, changed = clip_to_next_start(once)
    assert twice == once and changed == 0
    parallel, changed = clip_to_next_start([Cue(0, 2000, "a"), Cue(0, 1800, "b"), Cue(1500, 3000, "c")])
    assert changed == 2 and [cue.end_ms for cue in parallel] == [1500, 1500, 3000]


# -- caption kind ----------------------------------------------------------------------------------------------------


def test_a_track_of_unknown_kind_is_read_as_automatic_from_its_markers_or_its_rolling_pattern():
    assert classify_caption_kind(KIND_UNKNOWN, _raw_cues()) == KIND_AUTO
    assert classify_caption_kind("", _stored_lines()) == KIND_AUTO   # ">>" and "[music]"
    rolling = [Cue(i * 2000, i * 2000 + 4000, "plain words here") for i in range(6)]
    assert classify_caption_kind(KIND_UNKNOWN, rolling) == KIND_AUTO
    tidy = [Cue(i * 3000, i * 3000 + 2500, "A tidy sentence.") for i in range(6)]
    assert classify_caption_kind(KIND_UNKNOWN, tidy) == KIND_UNKNOWN
    assert classify_caption_kind(KIND_MANUAL, _raw_cues()) == KIND_MANUAL   # the provider's own word stands


# -- the gate's criteria ---------------------------------------------------------------------------------------------


def _even(texts: list[str], step: int = 3000, length: int = 2600) -> list[Cue]:
    return [Cue(i * step, i * step + length, text) for i, text in enumerate(texts)]


GOOD = [f"This is spoken line number {i} of the clip." for i in range(60)]


def test_a_clean_manual_track_passes():
    assert caption_timing_report(_even(GOOD), language="en", caption_kind=KIND_MANUAL).passed


def test_overlap_out_of_order_and_empty_lines_fail_at_once():
    for broken in (
        [Cue(0, 3000, GOOD[0]), Cue(2500, 5000, GOOD[1])],
        [Cue(3000, 5000, GOOD[0]), Cue(0, 2000, GOOD[1])],
        [Cue(0, 0, GOOD[0])],
    ):
        assert "order" in caption_timing_report(broken, language="en").failed


def test_fast_and_short_dense_lines_over_the_share_fail():
    lines = _even(GOOD)
    squeezed = [replace(line, end_ms=line.start_ms + 400) if i % 10 == 0 else line for i, line in enumerate(lines)]
    report = caption_timing_report(squeezed, language="en", caption_kind=KIND_MANUAL)
    assert "defects" in report.failed and report.counts["short_dense"] == 6
    one = [replace(line, end_ms=line.start_ms + 400) if i == 5 else line for i, line in enumerate(lines)]
    assert caption_timing_report(one, language="en").passed   # one borderline line is tolerated
    strict = TimingThresholds(max_defect_share=0.0)
    assert caption_timing_report(squeezed, language="en", limits=strict).counts["fast"] == 6


def test_a_long_silence_in_the_middle_of_a_sentence_is_a_defect():
    lines = [Cue(0, 2000, "and then we walked down to the"), Cue(30_000, 32_000, "river where the boats were"),
             Cue(33_000, 35_000, "waiting for us all."), Cue(36_000, 38_000, "It was cold."),
             Cue(60_000, 62_000, "Next morning came.")]
    report = caption_timing_report(lines, language="en", limits=TimingThresholds(max_defect_share=0.0))
    assert report.counts["gap_mid_sentence"] == 1   # the gap after a full stop is a pause, not a defect


def test_chinese_uses_its_own_reading_speed():
    fast = [Cue(i * 3000, i * 3000 + 600, "我们今天一起去公园散步吧") for i in range(10)]
    report = caption_timing_report(fast, language="zh", caption_kind=KIND_MANUAL)
    assert not report.passed and report.counts["fast"] == 10 and report.counts["short_dense"] == 10
    calm = [Cue(i * 3000, i * 3000 + 2500, "我们今天一起去公园散步吧") for i in range(10)]
    assert caption_timing_report(calm, language="zh", caption_kind=KIND_MANUAL).passed


def test_an_automatic_track_that_was_not_re_timed_fails():
    report = caption_timing_report(_even(GOOD), language="en", caption_kind=KIND_AUTO, retimed=False)
    assert report.failed == ("not_retimed",)


# -- the gate where it runs ------------------------------------------------------------------------------------------


def _passport_entry(**overrides):
    from tests.test_media_lifecycle import _entry
    from writing_coach.media_transcript_pipeline import ORIGIN_CAPTION, build_transcript, lesson_payload

    base = replace(_entry("youtube-ZncA70OAgPw"), media_type="video", provider="youtube", provider_media_id="ZncA70OAgPw",
                   canonical_url="https://www.youtube.com/watch?v=ZncA70OAgPw", duration_ms=286_293, status="published",
                   playback={"provider": "youtube", "kind": "embed", "url": "https://www.youtube-nocookie.com/embed/ZncA70OAgPw"},
                   source={**_entry().source, "provider": "youtube", "rights": "cleared", "license": "Cleared for the test",
                           "caption_kind": KIND_UNKNOWN, "caption_provider": "supadata"})
    payload = lesson_payload(base, build_transcript(base.media_id, "en", _stored_lines()), ORIGIN_CAPTION, 286_293)
    entry = replace(base, lesson={"lesson_id": base.media_id, "payload": payload, "status": "PUBLISHED"},
                    processing={"state": "ready", "stage": "ready", "origin": "content-pack"})
    return replace(entry, **overrides)


def test_the_entry_gate_holds_the_passport_rush_record_and_passes_other_origins():
    from writing_coach.media_transcript_pipeline import ORIGIN_ASR, caption_timing_gate

    ok, detail, report = caption_timing_gate(_passport_entry())
    assert not ok and report is not None and "not_retimed" in detail
    asr = _passport_entry()
    asr = replace(asr, lesson={**asr.lesson, "payload": {**asr.lesson["payload"], "transcript_origin": ORIGIN_ASR}})
    assert caption_timing_gate(asr)[0]


def test_a_content_pack_carrying_mistimed_captions_arrives_held_for_timing_review(tmp_path):
    from writing_coach import media_pack
    from writing_coach.book_asset_store import FilesystemBookAssetStore
    from writing_coach.content_packs import build_pack, read_pack
    from writing_coach.media_library_store import FileMediaLibraryStore

    source = FileMediaLibraryStore(tmp_path / "src")
    source_assets = FilesystemBookAssetStore(tmp_path / "src-assets")
    source_assets.put("media/youtube-ZncA70OAgPw/thumb.jpg", b"\xff\xd8\xff jpeg")
    source.upsert(_passport_entry(thumbnail={"kind": "asset", "ref": "media/youtube-ZncA70OAgPw/thumb.jpg"}))
    items, blobs, excluded = media_pack.build_media_items(source, source_assets, clip_keys=lambda _e: [], include_derived_text=True)
    assert items, excluded
    pack = read_pack(build_pack(items, created_by="t", environment="t", app_version="v", filters={}, assets=blobs))
    target = FileMediaLibraryStore(tmp_path / "dst")
    report = media_pack.apply_media_items(pack, target, FilesystemBookAssetStore(tmp_path / "dst-assets"), dry_run=False,
                                          clip_keys=lambda _e: [])
    arrived = target.get("youtube-ZncA70OAgPw")
    assert report[0]["held"] == f"transcript_{REASON_CAPTION_TIMING}" and arrived.status == "unpublished"
    assert arrived.processing["state"] == "held" and arrived.processing["reason"] == REASON_CAPTION_TIMING


def test_the_pipeline_never_publishes_a_mistimed_item_whatever_path_publishes_it(tmp_path):
    from tests.test_media_import_pipeline_reasons import _Ledger
    from writing_coach import media_transcript_pipeline as mtp
    from writing_coach.media_library_store import FileMediaLibraryStore

    store = FileMediaLibraryStore(tmp_path / "index")
    entry = replace(_passport_entry(), status="review", processing={"state": "running"})
    store.upsert(entry)
    pipeline = mtp.MediaPipeline(ledger=_Ledger(), workers=1)
    after = pipeline._write_processing(store, entry, state=mtp.STATE_READY, reason="", status="published")
    assert after.status == "review" and after.processing["state"] == mtp.STATE_HELD
    assert after.processing["reason"] == REASON_CAPTION_TIMING and after.processing["message"]


def test_a_failed_re_run_puts_the_item_back_exactly_as_it_was(tmp_path):
    # A re-time sweep whose caption fetch fails (or meets the quota) must leave the published item where it was; only
    # new captions that fail the gate hold an item.
    from tests.test_media_import_pipeline_reasons import _Ledger
    from writing_coach import media_transcript_pipeline as mtp
    from writing_coach.media_library_store import FileMediaLibraryStore

    store = FileMediaLibraryStore(tmp_path / "index")
    entry = _passport_entry()
    store.upsert(replace(entry, status="processing", processing={
        "state": "running", "previous": {**entry.processing, "_status": "published"}}))
    pipeline = mtp.MediaPipeline(ledger=_Ledger(), workers=1)
    assert pipeline._restore_previous(store, entry.media_id, "captions_unavailable")
    after = store.get(entry.media_id)
    assert after.status == "published" and after.processing["state"] == "ready"
    assert after.processing["reprocess_reason"] == "captions_unavailable"


class _Ingestion:
    def __init__(self, cues, provenance):
        from types import SimpleNamespace

        self._answer = SimpleNamespace(
            media_object=SimpleNamespace(transcript=SimpleNamespace(segments=[
                SimpleNamespace(start_ms=c.start_ms, end_ms=c.end_ms, original_text=c.text) for c in cues])),
            provenance=provenance)

    def import_media(self, *_args):
        return self._answer


@pytest.fixture()
def inline(monkeypatch):
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "")


def test_a_reprocess_re_times_the_rolling_captions_classifies_them_and_publishes(tmp_path, inline):
    from tests.test_media_import_pipeline_reasons import _Ledger
    from writing_coach import media_transcript_pipeline as mtp
    from writing_coach.media_library_store import FileMediaLibraryStore

    store = FileMediaLibraryStore(tmp_path / "index")
    store.upsert(replace(_passport_entry(), duration_ms=60_000, status="review",
                         processing={"state": "held", "reason": REASON_CAPTION_TIMING}))
    ingestion = _Ingestion(_raw_cues(), {"caption_kind": KIND_UNKNOWN, "caption_provider": "supadata", "caption_language": "en"})
    pipeline = mtp.MediaPipeline(ledger=_Ledger(), workers=1, ingestion=ingestion)
    assert pipeline.retry(store, None, "youtube-ZncA70OAgPw")
    after = store.get("youtube-ZncA70OAgPw")
    payload = after.lesson["payload"]
    assert payload["caption_kind"] == KIND_AUTO and payload[TIMING_KEY] == TIMING_NEXT_START
    lines = mtp.lines_from_payload(payload)
    assert abs(_line(lines, "Of course").start_ms - _spoken_at("Of")) <= 150
    assert mtp.caption_timing_gate(after)[0]
    assert after.processing["reason"] != REASON_CAPTION_TIMING


def test_the_scan_reports_in_a_dry_run_and_holds_only_with_apply(tmp_path, monkeypatch, capsys):
    from scripts import media_timing_scan
    from writing_coach.media_library_store import FileMediaLibraryStore

    store = FileMediaLibraryStore(tmp_path / "index")
    store.upsert(_passport_entry())
    out = tmp_path / "health" / "scan.json"
    assert media_timing_scan.main(["--root", str(tmp_path / "index"), "--out", str(out), "--health-line"]) == 1
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["mode"] == "dry_run" and report["failing"] == 1 and report["items"][0]["retime"] == "reprocess"
    assert store.get("youtube-ZncA70OAgPw").status == "published"   # a dry run changes nothing
    assert "FAIL media-timing" in capsys.readouterr().out
    assert media_timing_scan.main(["--root", str(tmp_path / "index"), "--out", str(out), "--apply"]) == 0
    held = store.get("youtube-ZncA70OAgPw")
    assert held.status == "review" and held.processing["reason"] == REASON_CAPTION_TIMING
    assert held.lesson["payload"] == _passport_entry().lesson["payload"]   # the transcript is left as it was


# -- review follow-ups: no false holds on ordinary speech, and line identities survive a re-time ---------------------


def test_ordinary_quick_dialogue_and_mandarin_are_not_short_dense():
    english = [Cue(i * 2000, i * 2000 + 800, text) for i, text in enumerate(
        ["Wait for me.", "Okay, got it.", "Are you sure?", "I don't know.", "Come on, hurry!"] * 4)]
    report = caption_timing_report(english, language="en", caption_kind=KIND_MANUAL, limits=TimingThresholds(max_defect_share=0.0))
    assert report.counts["short_dense"] == 0 and report.passed, report.as_dict()
    mandarin = [Cue(i * 2000, i * 2000 + 800, text) for i, text in enumerate(
        ["好的，没问题。", "我知道了。", "对对对。", "你先走吧。", "真的吗？", "快点儿！"] * 4)]
    report = caption_timing_report(mandarin, language="zh", caption_kind=KIND_MANUAL, limits=TimingThresholds(max_defect_share=0.0))
    assert report.counts["short_dense"] == 0 and report.passed, report.as_dict()
    squeezed = [Cue(0, 700, "我们今天下午一起去公园散步吧")]   # 13 Han in 0.7 s: nobody speaks that fast
    assert caption_timing_report(squeezed, language="zh").counts["short_dense"] == 1


STRICT = TimingThresholds(max_defect_share=0.0)


def test_a_long_gap_after_music_or_a_finished_thought_is_not_a_defect():
    music = [Cue(0, 2000, "So we went down to the"), Cue(2000, 20_000, "[music]"), Cue(40_000, 42_000, "river at night."),
             Cue(43_000, 45_000, "It was cold.")]
    assert caption_timing_report(music, language="en", limits=STRICT).counts["gap_mid_sentence"] == 0
    after_music = [Cue(0, 2000, "[music] and then we went to the"), Cue(30_000, 32_000, "river at night."),
                   Cue(33_000, 35_000, "It was cold.")]
    assert caption_timing_report(after_music, language="en", limits=STRICT).counts["gap_mid_sentence"] == 0
    capital = [Cue(0, 2000, "We stopped there,"), Cue(30_000, 32_000, "Later that week we left."), Cue(33_000, 35_000, "Fine.")]
    assert caption_timing_report(capital, language="en", limits=STRICT).counts["gap_mid_sentence"] == 0


def test_an_unpunctuated_lowercase_automatic_track_never_reads_pauses_as_mid_sentence():
    raw = [Cue(0, 2000, "so we went down to the"), Cue(30_000, 32_000, "river and then we"), Cue(50_000, 52_000, "came back home")]
    assert caption_timing_report(raw, language="en", limits=STRICT).counts["gap_mid_sentence"] == 0


def test_a_long_chinese_pause_is_not_a_defect_unless_the_clause_is_open():
    pause = [Cue(0, 2000, "他走了"), Cue(30_000, 32_000, "我们都很难过。"), Cue(33_000, 35_000, "后来呢？")]
    assert caption_timing_report(pause, language="zh", limits=STRICT).counts["gap_mid_sentence"] == 0
    stop = [Cue(0, 2000, "他走了。"), Cue(30_000, 32_000, "我们都很难过。")]
    assert caption_timing_report(stop, language="zh", limits=STRICT).counts["gap_mid_sentence"] == 0
    open_clause = [Cue(0, 2000, "他说，"), Cue(30_000, 32_000, "明天再来。"), Cue(33_000, 35_000, "好。")]
    assert caption_timing_report(open_clause, language="zh", limits=STRICT).counts["gap_mid_sentence"] == 1


def test_a_re_time_keeps_every_unchanged_lines_identity():
    from writing_coach.media_transcript_pipeline import build_transcript, carry_segment_ids

    old = build_transcript("youtube-ZncA70OAgPw", "en", _stored_lines())
    previous = {"transcript": {"segments": [{"segment_id": s.segment_id, "original_text": s.original_text} for s in old.segments]}}
    clipped, _ = clip_to_next_start(_raw_cues())
    new = build_transcript("youtube-ZncA70OAgPw", "en", segment_lines(clipped, "en"))
    old_ids = {s.segment_id for s in old.segments}
    assert sum(s.segment_id not in old_ids for s in new.segments) >= 9   # what re-timing alone does to the ids
    kept, carried = carry_segment_ids(previous, new)
    texts = [s.original_text for s in old.segments]
    by_text = {s.original_text: s.segment_id for s in old.segments if texts.count(s.original_text) == 1}
    shared = [s for s in kept.segments if s.original_text in by_text]
    assert carried >= 9 and len(shared) >= 9
    assert all(s.segment_id == by_text[s.original_text] for s in shared)
    assert len({s.segment_id for s in kept.segments}) == len(kept.segments)
    assert [s.start_ms for s in kept.segments] == [s.start_ms for s in new.segments]   # the new times stand
    changed = replace(new.segments[0], original_text="A corrected first line.")
    alone, count = carry_segment_ids(previous, replace(new, segments=(changed,)))
    assert count == 0 and alone.segments[0].segment_id == changed.segment_id


def test_a_reprocess_keeps_the_ids_learner_references_point_at(tmp_path, inline):
    from tests.test_media_import_pipeline_reasons import _Ledger
    from writing_coach import media_transcript_pipeline as mtp
    from writing_coach.media_library_store import FileMediaLibraryStore

    store = FileMediaLibraryStore(tmp_path / "index")
    entry = replace(_passport_entry(), duration_ms=60_000, status="review",
                    processing={"state": "held", "reason": REASON_CAPTION_TIMING})
    store.upsert(entry)
    rows = entry.lesson["payload"]["transcript"]["segments"]
    texts = [s["original_text"] for s in rows]
    before = {s["original_text"]: s["segment_id"] for s in rows if texts.count(s["original_text"]) == 1}
    ingestion = _Ingestion(_raw_cues(), {"caption_kind": KIND_UNKNOWN, "caption_provider": "supadata", "caption_language": "en"})
    assert mtp.MediaPipeline(ledger=_Ledger(), workers=1, ingestion=ingestion).retry(store, None, entry.media_id)
    after = store.get(entry.media_id).lesson["payload"]["transcript"]["segments"]
    kept = [s for s in after if s["original_text"] in before]
    assert len(kept) >= 9 and all(s["segment_id"] == before[s["original_text"]] for s in kept)
