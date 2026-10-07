from grammar_lab.pipeline.generate import _header_metadata, _stored_header_metadata
from grammar_lab.pipeline.validate import ZH_HANS, _ZH_SPACE


def test_prompt_header_metadata_preserves_existing_native_title_for_cache_key() -> None:
    existing = {
        "target_lang": ZH_HANS,
        "level": {"framework": "HSK", "value": "3"},
        "header": {
            "title": {"vi": "Liên động"},
            "native_title": "连动句“去/来 + 动词”",
        },
    }
    header = _header_metadata(existing, ["vi"])
    assert header["native_title"] == "连动句“去/来 + 动词”"


def test_stored_zh_header_normalizes_native_title_without_mutating_prompt_header() -> None:
    header = {
        "title": {"vi": "Liên động"},
        "native_title": "连动句“去/来 + 动词”",
        "level": {"framework": "HSK", "value": "3"},
    }
    stored = _stored_header_metadata(header, True)
    assert header["native_title"] == "连动句“去/来 + 动词”"
    assert stored["native_title"] == "连动句“去/来+动词”"
    assert _ZH_SPACE.search(stored["native_title"]) is None


def test_prompt_legacy_title_is_preserved_but_stored_copy_matches_whitespace_contract() -> None:
    existing = {
        "target_lang": ZH_HANS,
        "level": {"framework": "HSK", "value": "4"},
        "title": {"vi": "Cấu trúc 所", ZH_HANS: "“所 + V”结构入门"},
    }
    header = _header_metadata(existing, ["vi"])
    assert header["native_title"] == "“所 + V”结构入门"
    stored = _stored_header_metadata(header, True)
    assert stored["native_title"] == "“所+ V”结构入门"
    assert _ZH_SPACE.search(stored["native_title"]) is None
