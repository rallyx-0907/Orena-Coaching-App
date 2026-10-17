"""Transcript correction is accepted per cue, paced on a rate limit, and never blocks the item (2026-10-17 live trial)."""
from dataclasses import replace

import pytest

from tests.test_media_learner_upload import _tone
from tests.test_media_lifecycle import _entry
from writing_coach import media_transcript_pipeline as pipeline_module
from writing_coach.book_asset_store import FilesystemBookAssetStore
from writing_coach.media_library_store import FileMediaLibraryStore
from writing_coach.media_segmentation import Cue
from writing_coach.media_source_import import MediaSourceImporter
from writing_coach.media_spend import SpendLedger
from writing_coach.media_transcript_pipeline import MediaPipeline, reject_cue_edit
from writing_coach.media_transcript_quality import repair_english_caption_text
from writing_coach.media_translation import TranslationProviderError
from writing_coach.speech_asr import SpeechAsrResult, SpeechAsrSegment, asr_text_has_junk


def _world(tmp_path, corrector, language="en", name="w"):
    entry = replace(_entry(f"item-{name}", language=language), status="processing", processing={
        "state": "running", "transcript_correction_eligibility": "new_admin_import"})
    store = FileMediaLibraryStore(tmp_path / f"index-{name}")
    store.upsert(entry)
    pipeline = MediaPipeline(ledger=SpendLedger(tmp_path / f"spend-{name}.json"), corrector=corrector)
    slept = []
    pipeline._sleep = slept.append
    return store, entry, pipeline, slept


class Echo:
    """A corrector whose answer for each cue is chosen by a callable (text -> (text, reason))."""
    model = "configured-text-model"

    def __init__(self, edit=lambda text: (text, "No change.")):
        self.edit, self.calls = edit, []

    def correct(self, *, cues, **_kwargs):
        self.calls.append(tuple(cue.text for cue in cues))
        answers = [self.edit(cue.text) for cue in cues]
        return {"texts": [a[0] for a in answers], "reasons": [a[1] for a in answers], "provider": "groq", "model": self.model}


def _english(count):
    return [Cue(i * 3000, i * 3000 + 2500, f"cue number {i} has some plain words") for i in range(count)]


# -- P1-1 per-cue acceptance -------------------------------------------------------------------------

def test_one_dropped_word_rejects_only_that_cue_and_keeps_the_other_repairs(tmp_path):
    def edit(text):
        if text.startswith("cue number 1 "):
            return "Cue number 1 has plain words.", "capitalised"          # dropped "some"
        return text.capitalize() + ".", "restored punctuation"
    store, entry, pipeline, _ = _world(tmp_path, Echo(edit))
    lines, meta = pipeline._correct_transcript(store, entry, "b", _english(3), origin=pipeline_module.ORIGIN_CAPTION)
    assert [line.text for line in lines] == ["Cue number 0 has some plain words.", "cue number 1 has some plain words",
                                              "Cue number 2 has some plain words."]
    assert meta["transcript_correction_state"] == "partial"
    assert meta["transcript_correction_detail"] == "lexemes_changed"
    assert [(row["index"], row["code"]) for row in meta["transcript_correction_rejected"]] == [(1, "lexemes_changed")]
    assert [row["index"] for row in meta["transcript_corrections"]] == [0, 2]
    assert store.get(entry.media_id).processing["transcript_correction_state"] == "partial"


def test_chinese_homophone_fixes_pass_per_cue_where_the_old_global_ratio_rejected_all(tmp_path):
    raw = ["我们渡舰过河去", "床弦上有一道刻痕", "他的舰掉进了水里", "船夫在岸边看着他们", "这是第五句不需要修改的话",
           "这是第六句不需要修改的话", "这是第七句不需要修改的话", "这是第八句不需要修改的话", "这是第九句不需要修改的话",
           "这是第十句不需要修改的话", "这是第十一句不需要修改的话", "这是第十二句不需要修改的话"]
    fixes = {raw[0]: "我们渡江过河去", raw[1]: "船舷上有一道刻痕", raw[2]: "他的剑掉进了水里", raw[3]: "今天天气真好我们出去玩吧"}
    store, entry, pipeline, _ = _world(tmp_path, Echo(lambda t: (fixes.get(t, t), "homophone" if t in fixes else "No change.")), "zh")
    lines = [Cue(i * 3000, i * 3000 + 2500, text) for i, text in enumerate(raw)]
    out, meta = pipeline._correct_transcript(store, entry, "b", lines, origin=pipeline_module.ORIGIN_ASR)
    assert [line.text for line in out[:3]] == [fixes[raw[0]], fixes[raw[1]], fixes[raw[2]]]
    assert out[3].text == raw[3]                                   # the rewrite is refused, the rest stand
    assert meta["transcript_correction_state"] == "partial"
    assert [(row["index"], row["code"]) for row in meta["transcript_correction_rejected"]] == [(3, "edit_ratio_exceeded")]
    assert len([row for row in meta["transcript_corrections"] if row["reason_code"] == "model_edit"]) == 3


@pytest.mark.parametrize("language,before,after,code", [
    ("zh", "我们渡舰过河去", "我们渡江过河去", ""),                    # one homophone character
    ("zh", "船一正", "船身", ""),                                      # two characters in a three-character cue
    ("zh", "舰", "剑", ""),                                            # a one-character cue may change that character
    ("zh", "我们渡舰过河去", "我们渡舰过河去。", ""),                   # punctuation is not a Han edit
    ("zh", "我们渡舰过河去", "今天天气真不错啊朋友", "edit_ratio_exceeded"),   # a rewrite
    ("zh", "他的舰掉了", "他的剑掉了" + "啊" * 400, "malformed_result"),
    ("zh", "你好吗", "  ", "empty_cue"),
    ("en", "Hello world", "Hello, world.", ""),
    ("en", "Hello world", "Hello.", "lexemes_changed"),
    ("en", "Beyoncé sings", "Beyonc sings", "lexemes_changed"),
])
def test_reject_cue_edit_rule(language, before, after, code):
    assert reject_cue_edit(language, before, after) == code


def test_chinese_allowance_is_a_quarter_of_the_cue_capped_at_four():
    base = "甲乙丙丁戊己庚辛壬癸" * 4                                     # 40 Han characters
    assert reject_cue_edit("zh", base, "子丑寅卯" + base[4:]) == ""        # 4 changed: at the cap
    assert reject_cue_edit("zh", base, "子丑寅卯辰" + base[5:]) == "edit_ratio_exceeded"


# -- P2-5 noise ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw,clean", [
    (">> [music]", ""), ("[crying] I am fine", "I am fine"), ("so [gasps] it ran [door creaks] away", "so it ran away"),
    ("(music)", ""), ("hello (applause) there", "hello there"), ("see [1] and (Paris) now", "see [1] and (Paris) now"),
    ("it is (yes) true", "it is (yes) true"), (">>> Then he left", "Then he left"),
])
def test_english_noise_rule_is_bounded(raw, clean):
    assert repair_english_caption_text(raw) == clean


def test_noise_only_cues_are_dropped_and_do_not_abort_the_repair(tmp_path):
    cues = [Cue(0, 1000, ">> [music]"), Cue(1000, 3000, ">> Hello there everyone"), Cue(3000, 4000, "[crying]"),
            Cue(4000, 6000, "and welcome back")]
    store, entry, pipeline, _ = _world(tmp_path, Echo(lambda t: (t[0].upper() + t[1:] + ".", "restored punctuation")))
    lines, meta = pipeline._correct_transcript(store, entry, "b", cues, origin=pipeline_module.ORIGIN_CAPTION)
    assert [line.text for line in lines] == ["Hello there everyone.", "And welcome back."]
    assert meta["transcript_correction_state"] == "applied"
    rows = {row["index"]: row for row in meta["transcript_corrections"]}
    assert rows[0]["after"] == "" and rows[0]["reason_code"] == "noise_removed"
    assert rows[2]["reason_code"] == "noise_removed"
    assert rows[1]["reason_code"] == "model_edit" and rows[1]["reason"] == "restored punctuation"


def test_deterministic_only_edit_has_a_noise_reason_not_no_change(tmp_path):
    store, entry, pipeline, _ = _world(tmp_path, Echo())
    _, meta = pipeline._correct_transcript(store, entry, "b", [Cue(0, 2000, ">> hello there my friends")],
                                           origin=pipeline_module.ORIGIN_CAPTION)
    assert meta["transcript_corrections"][0]["reason_code"] == "noise_removed"
    assert meta["transcript_corrections"][0]["reason"] == ""


def test_chinese_bracketed_text_is_never_stripped(tmp_path):
    text = "他说【笑】然后走了出去很远"
    store, entry, pipeline, _ = _world(tmp_path, Echo(), "zh")
    lines, meta = pipeline._correct_transcript(store, entry, "b", [Cue(0, 2000, text)], origin=pipeline_module.ORIGIN_ASR)
    assert lines[0].text == text and meta["transcript_corrections"] == []


def test_noise_is_stripped_even_when_the_provider_is_unavailable(tmp_path):
    class Off:
        configured = False

        def correct(self, **_kw):
            raise AssertionError("not configured")
    store, entry, pipeline, _ = _world(tmp_path, Off())
    lines, meta = pipeline._correct_transcript(store, entry, "b", [Cue(0, 2000, ">> [music] hello again my friends")],
                                               origin=pipeline_module.ORIGIN_CAPTION)
    assert lines[0].text == "hello again my friends"
    assert meta["transcript_correction_state"] == "unavailable"
    assert meta["transcript_correction_detail"] == "corrector_unconfigured"


# -- P1-3 pacing ---------------------------------------------------------------------------------------

class Flaky(Echo):
    def __init__(self, failures):
        super().__init__(lambda t: (t, "No change."))
        self.failures, self.attempts = list(failures), 0

    def correct(self, *, cues, **kwargs):
        self.attempts += 1
        if self.failures:
            failure = self.failures.pop(0)
            if failure is not None:
                raise failure
        return super().correct(cues=cues, **kwargs)


def _limit(wait):
    return TranslationProviderError("limited", reason="rate_limited", retry_after=wait)


def test_a_named_rate_limit_wait_is_slept_once_and_the_batch_is_retried(tmp_path):
    corrector = Flaky([None, _limit(62.0)])           # batch 1 ok, batch 2 refused once, then served
    store, entry, pipeline, slept = _world(tmp_path, corrector)
    lines, meta = pipeline._correct_transcript(store, entry, "b", _english(30), origin=pipeline_module.ORIGIN_CAPTION)
    assert slept == [62.0] and corrector.attempts == 3
    assert meta["transcript_correction_state"] == "applied" and len(lines) == 30


def test_a_wait_beyond_the_cap_is_not_slept_and_keeps_the_accepted_batch(tmp_path):
    def edit(text):
        return text.capitalize(), "capitalised"
    corrector = Flaky([None, _limit(600.0)])
    corrector.edit = edit
    store, entry, pipeline, slept = _world(tmp_path, corrector)
    lines, meta = pipeline._correct_transcript(store, entry, "b", _english(30), origin=pipeline_module.ORIGIN_CAPTION)
    assert slept == [] and corrector.attempts == 2
    assert meta["transcript_correction_state"] == "partial" and meta["transcript_correction_detail"] == "rate_limited"
    assert lines[0].text.startswith("Cue") and lines[29].text.startswith("cue")      # batch 1 kept, batch 2 raw


def test_the_retry_is_bounded_to_one_per_batch(tmp_path):
    corrector = Flaky([_limit(62.0), _limit(62.0), _limit(62.0)])
    store, entry, pipeline, slept = _world(tmp_path, corrector)
    _, meta = pipeline._correct_transcript(store, entry, "b", _english(30), origin=pipeline_module.ORIGIN_CAPTION)
    assert slept == [62.0] and corrector.attempts == 2
    assert meta["transcript_correction_state"] == "failed" and meta["transcript_correction_detail"] == "rate_limited"


def test_provider_reason_codes_are_kept(tmp_path):
    corrector = Flaky([TranslationProviderError("no", reason="provider_auth")])
    store, entry, pipeline, _ = _world(tmp_path, corrector)
    _, meta = pipeline._correct_transcript(store, entry, "b", _english(3), origin=pipeline_module.ORIGIN_CAPTION)
    assert meta["transcript_correction_detail"] == "provider_auth"


# -- P1/P2-4 title prompt ------------------------------------------------------------------------------

def test_junk_signature_is_full_width_digits_symbols_and_letters_only():
    assert asr_text_has_junk("他说０然后＝走了") and asr_text_has_junk("ＡＢ")
    assert not asr_text_has_junk("他说，然后走了。你好！真的吗？（好）：对；")


def _asr_pipeline(tmp_path, monkeypatch, seconds, responder, title="画蛇添足"):
    from writing_coach import media_thumbnail
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    monkeypatch.setattr(media_thumbnail, "_TEMP_ROOT", tmp_path)
    prompts = []

    class Asr:
        def transcribe_bytes(self, body, **kwargs):
            prompts.append(kwargs.get("prompt"))
            text = responder(kwargs.get("prompt"))
            return SpeechAsrResult("test", "fixture", "zh", text, (SpeechAsrSegment(text, 0, int(seconds * 1000) - 500),), ())
    store = FileMediaLibraryStore(tmp_path / "index")
    ledger = SpendLedger(tmp_path / "spend.json")
    pipeline = MediaPipeline(ledger=ledger, asr=Asr())
    importer = MediaSourceImporter(None, store, FilesystemBookAssetStore(tmp_path / "assets"), pipeline=pipeline)
    path = tmp_path / "voice.wav"
    path.write_bytes(_tone(seconds))
    importer.import_upload(path, filename=f"{title}.wav", language="zh", imported_by="learner", library="personal", owner_key="a")
    return prompts


GOOD = "每天早上我都去附近的市场买菜。阿姨总是很热情。"


def test_title_prompt_is_sent_for_short_audio(tmp_path, monkeypatch):
    prompts = _asr_pipeline(tmp_path, monkeypatch, 10, lambda _p: GOOD)
    assert len(prompts) == 1 and prompts[0] and "画蛇添足" in prompts[0]


def test_title_prompt_is_not_sent_for_long_audio(tmp_path, monkeypatch):
    from writing_coach.speech_asr import ASR_PROMPT_MAX_SECONDS
    prompts = _asr_pipeline(tmp_path, monkeypatch, ASR_PROMPT_MAX_SECONDS + 10, lambda _p: GOOD)
    assert prompts and all(prompt is None for prompt in prompts)


def test_a_prompted_chunk_with_full_width_junk_is_heard_again_without_the_prompt(tmp_path, monkeypatch):
    prompts = _asr_pipeline(tmp_path, monkeypatch, 10, lambda p: "每天早上我都去０市场＝买菜。阿姨总是很热情。" if p else GOOD)
    assert len(prompts) == 2 and prompts[0] and prompts[1] is None
    stored = FileMediaLibraryStore(tmp_path / "index").list(library="personal", status=None)[0]
    text = "".join(s["original_text"] for s in stored.lesson["payload"]["transcript"]["segments"])
    assert "０" not in text and "＝" not in text and stored.processing["cost_usd"] > 0


def test_the_correction_incomplete_hold_has_a_stored_message_and_words_in_all_three_languages():
    from pathlib import Path

    assert pipeline_module.reason_message(pipeline_module.REASON_CORRECTION_INCOMPLETE)
    imports = (Path(__file__).resolve().parents[1] / "static" / "orena" / "screens" / "admin" / "copy-imports.js").read_text(encoding="utf-8")
    assert imports.count("impErr_transcript_correction_incomplete:") == 3
