from pathlib import Path


generate_path = Path("grammar_lab/pipeline/generate.py")
text = generate_path.read_text(encoding="utf-8")

anchor = "def normalize_generated_structure(data: dict[str, Any], zh: bool) -> dict[str, Any]:\n"
assert anchor in text
helper = r'''def normalize_generated_missing_question_variant(data: dict[str, Any], zh: bool) -> dict[str, Any]:
    """Reuse the proven base pattern when a Chinese question variant is omitted.

    Some lexical/word-order points use the same taught pattern inside statements and
    questions. DeepSeek can label an example as ``question`` while omitting the
    structurally identical ``question`` formula, which makes assembly emit no spans.

    Recover only for Chinese, only when the question variant is absent, at least one
    affirmative example proves the base formula, and every question example already
    binds that same base formula completely and in order. No bindings or learner-facing
    text are invented. English stays fail-closed because question formation can reorder
    or add auxiliaries.
    """
    out = copy.deepcopy(data)
    if not zh or out.get("question"):
        return out

    formula = out.get("formula") or []
    if not formula:
        return out

    indexed_examples = list(enumerate(out.get("examples") or []))
    affirmative = [(index, example) for index, example in indexed_examples if example.get("form") == "affirmative"]
    questions = [(index, example) for index, example in indexed_examples if example.get("form") == "question"]
    if not affirmative or not questions or not any(example.get("bindings") for _index, example in questions):
        return out

    proof_pattern = {"formula": formula, "variants": {"question": formula}}

    affirmative_proven = False
    for index, example in affirmative:
        _assembled, problems = assemble_generated_example(
            example, proof_pattern, True, lambda value: value, index
        )
        if not problems:
            affirmative_proven = True
            break
    if not affirmative_proven:
        return out

    for index, example in questions:
        _assembled, problems = assemble_generated_example(
            example, proof_pattern, True, lambda value: value, index
        )
        if problems:
            return out

    production = out.get("personal_production") or {}
    if production.get("target_form") == "question":
        rules = (production.get("pattern_rule") or {}).get("slots") or []
        if any(
            type(rule.get("slot_index")) is not int
            or not 0 <= rule["slot_index"] < len(formula)
            for rule in rules
        ):
            return out

    out["question"] = copy.deepcopy(formula)
    return out


'''
text = text.replace(anchor, helper + anchor, 1)
old = '''    out = normalize_generated_nested_context_slots(out, zh)\n    out = normalize_generated_formula_order(out, zh)\n'''
new = '''    out = normalize_generated_nested_context_slots(out, zh)\n    out = normalize_generated_missing_question_variant(out, zh)\n    out = normalize_generated_formula_order(out, zh)\n'''
assert old in text
text = text.replace(old, new, 1)
generate_path.write_text(text, encoding="utf-8")

rescue_path = Path("scripts/grammar_rescue_agent.ps1")
rescue = rescue_path.read_text(encoding="utf-8")
old = "- Run focused pytest only. Inspect git diff before finishing.\n"
new = (
    "- Run focused pytest only. Inspect git diff before finishing.\n"
    "- Inside Codex, run focused tests with `python -m pytest`; the outer wrapper has already verified `python` is on PATH.\n"
    "- Do not use `.venv`, `py`, or a hard-coded Python interpreter path.\n"
)
assert old in rescue
rescue = rescue.replace(old, new, 1)
rescue_path.write_text(rescue, encoding="utf-8")
