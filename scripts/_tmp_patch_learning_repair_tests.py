from pathlib import Path

path = Path('grammar_lab/tests/test_generate.py')
text = path.read_text(encoding='utf-8')

old = '''    # Use a semantic failure outside the targeted formula/span/rule repair
    # surface so this test continues to exercise the full-candidate retry path.
    bad["quick_practice"][0]["q"] = "He goes to school."
'''
new = '''    # Keep this outside every bounded repair surface so this test continues
    # to exercise the fresh full-candidate retry path.
    bad["formula"][0]["options"] = [{"text": "He"}, {"text": "He"}]
'''
assert text.count(old) == 1, 'semantic retry anchor missing'
text = text.replace(old, new, 1)

old = '''    bad = copy.deepcopy(CANNED_V04)
    bad["quick_practice"][0]["q"] = "He goes to school."
    calls: list[httpx.Request] = []
'''
new = '''    bad = copy.deepcopy(CANNED_V04)
    bad["formula"][0]["options"] = [{"text": "He"}, {"text": "He"}]
    calls: list[httpx.Request] = []
'''
assert text.count(old) >= 1, 'hard-cap anchor missing'
text = text.replace(old, new, 1)

old = '''    # Keep this failure outside targeted repair: the contract under test is
    # three fresh full semantic attempts with no persisted bad draft.
    bad["quick_practice"][0]["q"] = "He goes to school."
'''
new = '''    # Keep this failure outside bounded repair: the contract under test is
    # three fresh full semantic attempts with no persisted bad draft.
    bad["formula"][0]["options"] = [{"text": "He"}, {"text": "He"}]
'''
assert text.count(old) == 1, 'three-attempt anchor missing'
text = text.replace(old, new, 1)

old = '''        elif tool_name == "emit_grammar_point_v04_structure_patch":
            payload = patch
        else:
            raise AssertionError(tool_name)
'''
new = '''        elif tool_name == "emit_grammar_point_v04_structure_patch":
            payload = patch
        elif tool_name == "emit_grammar_point_v04_learning_patch":
            payload = {"quick_practice": copy.deepcopy(good_structure["quick_practice"])}
        else:
            raise AssertionError(tool_name)
'''
pos = text.find('def test_generate_v04_mixed_structural_issue_repairs_structure_before_full_retry')
assert pos >= 0, 'mixed structural test missing'
tail = text[pos:]
assert old in tail, 'mixed handler not found in test tail'
tail = tail.replace(old, new, 1)
text = text[:pos] + tail

old = '''    assert outcome.status == "error"
    # The first extra provider action must be the small structure patch, not a
    # second full lesson.
    assert calls[:2] == [
        "emit_grammar_point_v04",
        "emit_grammar_point_v04_structure_patch",
    ]
'''
new = '''    assert outcome.status == "written", outcome.reason
    # Repair stays bounded: structure first, then only the implicated learner
    # block. No second full lesson is requested.
    assert calls == [
        "emit_grammar_point_v04",
        "emit_grammar_point_v04_structure_patch",
        "emit_grammar_point_v04_learning_patch",
    ]
'''
assert old in text, 'mixed repair assertion anchor missing'
text = text.replace(old, new, 1)

path.write_text(text, encoding='utf-8')
