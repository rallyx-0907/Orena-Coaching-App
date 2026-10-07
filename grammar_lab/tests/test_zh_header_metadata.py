from grammar_lab.pipeline.generate import _header_metadata
from grammar_lab.pipeline.validate import ZH_HANS, _ZH_SPACE


def test_zh_existing_header_native_title_matches_whitespace_contract() -> None:
    existing = {
        "target_lang": ZH_HANS,
        "level": {"framework": "HSK", "value": "3"},
        "header": {
            "title": {"vi": "Liên động"},
            "native_title": "连动句“去/来 + 动词”",
        },
    }
    header = _header_metadata(existing, ["vi"])
    assert header["native_title"] == "连动句“去/来+动词”"
    assert _ZH_SPACE.search(header["native_title"]) is None


def test_zh_legacy_title_native_title_matches_whitespace_contract() -> None:
    existing = {
        "target_lang": ZH_HANS,
        "level": {"framework": "HSK", "value": "4"},
        "title": {"vi": "Cấu trúc 所", ZH_HANS: "“所 + V”结构入门"},
    }
    header = _header_metadata(existing, ["vi"])
    assert header["native_title"] == "“所+ V”结构入门"
    assert _ZH_SPACE.search(header["native_title"]) is None
