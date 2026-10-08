from grammar_lab.pipeline.content_store import load_point
from grammar_lab.pipeline.seed import apply_seed
from grammar_lab.pipeline.validate import LAB_ROOT


def test_zh_seed_overlay_keeps_native_title_and_pinyin_validator_safe() -> None:
    point_id = "zh.bi_yidian_deduo"
    point = load_point("zh", point_id, LAB_ROOT)
    assert point is not None

    seeded = apply_seed(point, "zh", point_id, LAB_ROOT)
    assert seeded is not None

    native = seeded["header"]["native_title"]
    pinyin = seeded["header"]["native_title_pinyin"]
    assert not any(ch.isspace() for ch in native), native
    assert len(pinyin) == len(native), (native, pinyin)
