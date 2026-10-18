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
        return text.capitalize() + ".", "punctuation"
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


@pytest.mark.parametrize("before,after,code", [
    ("这是VOA新闻", "这是BOA新闻", "lexemes_changed"),                 # an entity swapped: not a recognition repair
    ("价格是2025元", "价格是2026元", "lexemes_changed"),               # a figure changed
    ("我们用GPT-5写作", "我们用GPT-6写作", "lexemes_changed"),
    ("这是VOA新闻", "这是新闻", "lexemes_changed"),                    # a word dropped
    ("这是新闻", "这是VOA新闻", "lexemes_changed"),                    # a word invented
    ("我们渡舰过河", "我们渡江过河", ""),                              # a Han repair is still accepted
    ("这是VOA新闻", "这是 VOA 新闻。", ""),                            # punctuation and spacing are free
    ("这是VOA新闻", "这是voa新闻", ""),                                # case is not a different word
    ("我们渡舰用VOA", "我们渡江用VOA", ""),                            # a Han repair beside an untouched entity
])
def test_chinese_cues_keep_their_latin_words_and_numbers(before, after, code):
    assert reject_cue_edit("zh", before, after) == code


# -- batches fit the provider's output-token allowance (live trial, 2026-10-17) -------------------------------

def _hsk_cues(count):
    # short Chinese cues like the live HSK1 item: 51 cues of about 9 characters
    return [Cue(i * 2000, i * 2000 + 1800, f"我今年{i:02d}岁我家有三口人。") for i in range(count)]


def test_a_batch_is_cut_to_the_provider_output_allowance_not_sent_whole(tmp_path):
    """The live item (51 short ZH cues, Groq OTPM limit 1000) answered `finish_reason: length` and was refused as malformed,
    because a 24-cue batch needs about 870 output tokens and the reservation cap had become 500."""
    sizes = []

    class Narrow(Echo):
        def batch_output_ceiling(self):
            return 500

        def correct(self, *, cues, **kwargs):
            sizes.append(len(cues))
            assert pipeline_module.estimate_correction_output_tokens(cues) <= 500
            return super().correct(cues=cues, **kwargs)

    store, entry, pipeline, _ = _world(tmp_path, Narrow(), "zh")
    cues = _hsk_cues(51)
    lines, meta = pipeline._correct_transcript(store, entry, "b", cues, origin=pipeline_module.ORIGIN_ASR)
    assert meta["transcript_correction_state"] == "applied" and meta["transcript_correction_detail"] == ""
    assert sum(sizes) == 51 and max(sizes) < 24 and len(sizes) > 3
    assert [line.text for line in lines] == [cue.text for cue in cues]            # every cue came back, in order


def test_the_ceiling_is_read_again_for_the_retry_after_a_rate_limit(tmp_path):
    """The provider learns its allowance from its first refusal: a batch sized for no limit is narrowed when it is retried."""
    state = {"ceiling": None, "calls": []}

    class Learns(Echo):
        def batch_output_ceiling(self):
            return state["ceiling"]

        def correct(self, *, cues, **kwargs):
            state["calls"].append(len(cues))
            if len(state["calls"]) == 1:
                state["ceiling"] = 500                                              # the refusal taught it the limit
                raise TranslationProviderError("limited", reason="rate_limited", retry_after=16.0)
            assert pipeline_module.estimate_correction_output_tokens(cues) <= 500
            return super().correct(cues=cues, **kwargs)

    store, entry, pipeline, slept = _world(tmp_path, Learns(), "zh")
    lines, meta = pipeline._correct_transcript(store, entry, "b", _hsk_cues(24), origin=pipeline_module.ORIGIN_ASR)
    assert slept == [16.0]
    assert state["calls"][0] == 24 and state["calls"][1] < 24 and sum(state["calls"][1:]) == 24
    assert meta["transcript_correction_state"] == "applied" and len(lines) == 24


def test_an_unknown_allowance_leaves_the_batch_as_it_was(tmp_path):
    corrector = Echo()                                  # no `batch_output_ceiling`: nothing narrows the batch
    store, entry, pipeline, _ = _world(tmp_path, corrector, "zh")
    pipeline._correct_transcript(store, entry, "b", _hsk_cues(30), origin=pipeline_module.ORIGIN_ASR)
    assert [len(call) for call in corrector.calls] == [24, 6]


@pytest.mark.parametrize("ceiling,expected_min", [(None, 24), (0, 24), (10_000, 24), (500, 1), (1, 1)])
def test_fit_correction_batch_always_keeps_at_least_one_cue(ceiling, expected_min):
    batch = [(i, cue) for i, cue in enumerate(_hsk_cues(24))]
    fitted = pipeline_module.fit_correction_batch(batch, ceiling)
    assert len(fitted) >= expected_min and fitted == batch[:len(fitted)]
    if ceiling in (None, 0, 10_000):
        assert fitted == batch


def test_the_estimate_covers_what_the_live_provider_measured():
    """24 Chinese cues, 630 text bytes: the provider reported 869 completion tokens. The estimate must not be lower."""
    cues = [Cue(0, 1, "x" * 26) for _ in range(24)]                                # 26 bytes each = 624 bytes
    assert pipeline_module.estimate_correction_output_tokens(cues) >= 869


# -- per-wait cap inside the provider (review of 54c8f608) ----------------------------------------------

def test_one_provider_wait_never_exceeds_the_per_wait_cap_even_when_the_window_is_blocked_longer(tmp_path, monkeypatch):
    """The provider's own pacing (`_reserve_output`) sleeps for the output-token window. It only knows the budget it is
    handed, so a correction must hand it min(per-wait cap, what is left of the total), never the whole total."""
    from writing_coach import media_translation as mt
    from writing_coach.media_translation import GroqTranslationProvider

    clock = [10_000.0]
    sleeps: list[float] = []
    monkeypatch.setattr(mt, "_monotonic", lambda: clock[0])
    monkeypatch.setattr(mt, "_pause", lambda seconds: (sleeps.append(seconds), clock.__setitem__(0, clock[0] + seconds)))
    mt.reset_output_windows()
    posts: list[int] = []
    monkeypatch.setattr(mt.requests, "post", lambda *_a, **_k: posts.append(1) or (_ for _ in ()).throw(AssertionError("sent")))
    provider = GroqTranslationProvider("k", model="blocked-model", output_tokens_per_minute=1000)
    mt.output_window("blocked-model").block_until(clock[0] + 120.0)     # an earlier refusal asked for 120 s

    store, entry, pipeline, slept = _world(tmp_path, provider)
    pipeline._sleep = slept.append
    lines, meta = pipeline._correct_transcript(store, entry, "b", _english(3), origin=pipeline_module.ORIGIN_CAPTION)
    mt.reset_output_windows()

    assert sleeps == [] and slept == []                                  # a 120 s wait is not slept: it exceeds 90 s
    assert posts == []                                                    # and the request was never sent
    assert meta["transcript_correction_state"] == "failed" and meta["transcript_correction_detail"] == "rate_limited"
    assert [line.text for line in lines] == [cue.text for cue in _english(3)]


def test_waits_inside_the_provider_draw_on_the_shared_total(tmp_path):
    """What a call sleeps inside the provider is spent from the same 150 s allowance the outer retry draws on."""
    from writing_coach import media_translation as mt

    seen: list[float] = []

    class Spends(Echo):
        def correct(self, *, cues, **kwargs):
            budget = mt._PACING.get()
            seen.append(budget.remaining)
            budget.remaining -= 80.0                                       # the provider slept 80 s inside this call
            return super().correct(cues=cues, **kwargs)

    corrector = Spends()
    store, entry, pipeline, _ = _world(tmp_path, corrector)
    _, meta = pipeline._correct_transcript(store, entry, "b", _english(30), origin=pipeline_module.ORIGIN_CAPTION)
    assert seen == [90.0, 70.0]                  # capped at 90 s for the first call; 150 - 80 = 70 s left for the second
    assert meta["transcript_correction_state"] == "applied"


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
    store, entry, pipeline, _ = _world(tmp_path, Echo(lambda t: (t[0].upper() + t[1:] + ".", "punctuation")))
    lines, meta = pipeline._correct_transcript(store, entry, "b", cues, origin=pipeline_module.ORIGIN_CAPTION)
    assert [line.text for line in lines] == ["Hello there everyone.", "And welcome back."]
    assert meta["transcript_correction_state"] == "applied"
    rows = {row["index"]: row for row in meta["transcript_corrections"]}
    assert rows[0]["after"] == "" and rows[0]["reason_code"] == "noise_removed"
    assert rows[2]["reason_code"] == "noise_removed"
    assert rows[1]["reason_code"] == "model_edit" and rows[1]["reason"] == "punctuation"


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
        return text.capitalize(), "capitalization"
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
