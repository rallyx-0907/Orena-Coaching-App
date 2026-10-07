from pathlib import Path

path = Path("grammar_lab/pipeline/generate.py")
text = path.read_text(encoding="utf-8")

start = text.index("def _header_metadata(existing: dict[str, Any], locales: list[str]) -> dict[str, Any]:")
end = text.index("\n\ndef resolve_spans(", start)
replacement = '''def _header_metadata(existing: dict[str, Any], locales: list[str]) -> dict[str, Any]:
    """Prompt-facing structural metadata, carried over exactly from the catalogue.

    Keep this byte-for-byte stable with the canonical source because it participates in
    the provider cache key. Learner-facing Chinese normalization happens only when the
    assembled point is stored.
    """
    if "header" in existing:
        header = existing["header"]
        return {"title": header["title"], "native_title": header["native_title"], "level": dict(existing["level"])}
    title = existing["title"]
    native = title.get(existing["target_lang"]) or title.get("en") or title["vi"]
    return {
        "title": {locale: title[locale] for locale in locales if locale in title} or {"vi": title["vi"]},
        "native_title": native,
        "level": dict(existing["level"]),
    }


def _stored_header_metadata(header: dict[str, Any], zh: bool) -> dict[str, Any]:
    """Normalize only the learner-facing stored header, never prompt/cache input."""
    out = copy.deepcopy(header)
    out["native_title"] = target_text(str(out["native_title"]), zh)
    return out
'''
text = text[:start] + replacement + text[end:]

anchor = '''            generation_problems.extend(production_problems)
            repair_personal_production_rule(personal_production, pattern, examples, zh)

            point = {
'''
if anchor not in text:
    raise SystemExit("v0.4 point assembly anchor not found; refusing unsafe patch")
text = text.replace(
    anchor,
    '''            generation_problems.extend(production_problems)
            repair_personal_production_rule(personal_production, pattern, examples, zh)
            stored_header = _stored_header_metadata(header, zh)

            point = {
''',
    1,
)

old = '**header, "summary": loc(data["summary"]),'
if text.count(old) != 1:
    raise SystemExit(f"expected one stored header expansion, found {text.count(old)}")
text = text.replace(old, '**stored_header, "summary": loc(data["summary"]),', 1)

old = 'pinyin_from_pairs(header["native_title"], data.get("native_title_pinyin_pairs"))'
if text.count(old) != 1:
    raise SystemExit(f"expected one native-title pinyin call, found {text.count(old)}")
text = text.replace(
    old,
    'pinyin_from_pairs(stored_header["native_title"], data.get("native_title_pinyin_pairs"))',
    1,
)
path.write_text(text, encoding="utf-8")

test = Path("grammar_lab/tests/test_zh_header_metadata.py")
test.write_text(
    '''from grammar_lab.pipeline.generate import _header_metadata, _stored_header_metadata
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
''',
    encoding="utf-8",
)
