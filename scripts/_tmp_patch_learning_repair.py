from pathlib import Path

path = Path('grammar_lab/pipeline/generate.py')
text = path.read_text(encoding='utf-8')

old = '''_GENERATION_STRUCTURE_DERIVATIVE_CODES = {
    "example.formula_role_missing",
    "example.span_role_not_in_formula",
    "example.span_slot_mismatch",
    "personal_production.rule_invalid",
    "personal_production.rule_role_not_in_formula",
    "personal_production.rule_rejects_sample",
    "personal_production.rule_rejects_example",
}
'''
new = '''_GENERATION_STRUCTURE_DERIVATIVE_CODES = {
    "example.formula_role_missing",
    "example.span_role_not_in_formula",
    "example.span_slot_mismatch",
    "personal_production.rule_invalid",
    "personal_production.rule_role_not_in_formula",
    "personal_production.rule_rejects_sample",
    "personal_production.rule_rejects_example",
    "formula.slot_has_joiner",
}
'''
assert old in text, 'structure derivative anchor missing'
text = text.replace(old, new, 1)

old = '''def can_repair_generation_structure(issues: list[Any]) -> bool:
    """Any raw v13 binding failure must be repaired before buying another lesson."""
    return any(
        str(getattr(issue, "code", "")).startswith("generation.")
        for issue in issues
    )
'''
new = '''def can_repair_generation_structure(issues: list[Any]) -> bool:
    """Route raw binding failures and invalid in-slot joiners to structure repair."""
    return any(
        str(getattr(issue, "code", "")).startswith("generation.")
        or str(getattr(issue, "code", "")) == "formula.slot_has_joiner"
        for issue in issues
    )
'''
assert old in text, 'can_repair_generation_structure anchor missing'
text = text.replace(old, new, 1)

old = '''- Keep a slot abstract where the examples vary lexically (S, V, N, NP, clause, etc.).
- English contractions are surface units when splitting them would overlap or reorder bindings.
'''
new = '''- Keep a slot abstract where the examples vary lexically (S, V, N, NP, clause, etc.).
- Never put `+` inside a slot text or option. The UI draws `+` between slots. If the current
  label encodes sequential pieces such as quantity+noun or 得+complement, represent those as
  truthful separate slots and bind each exact surface constituent in sentence order.
- English contractions are surface units when splitting them would overlap or reorder bindings.
'''
assert old in text, 'structure prompt anchor missing'
text = text.replace(old, new, 1)

anchor = '\ndef semantic_repair_hints('
assert anchor in text, 'semantic_repair_hints anchor missing'
insert = r'''

V04_LEARNING_BLOCK_REPAIR_MAX_TOKENS = 1800
_GENERATION_LEARNING_BLOCK_CODES = {
    "common_mistake.same_wrong_right",
    "error_tag.common_mistake_unlisted",
    "quick_practice.blank_invalid",
    "quick_practice.answer_tagged",
    "quick_practice.distractor_untagged",
    "quick_practice.distractor_misspelling",
}


def generation_learning_block_repair_issues(issues: list[Any]) -> list[Any]:
    """Return only bounded learner-exercise defects safe for block-only repair."""
    return [
        issue for issue in issues
        if str(getattr(issue, "code", "")) in _GENERATION_LEARNING_BLOCK_CODES
    ]


def can_repair_generation_learning_blocks(issues: list[Any]) -> bool:
    """True when at least one common-mistake or quick-practice block needs repair."""
    return bool(generation_learning_block_repair_issues(issues))


def _generation_learning_patch_schema(
    full_schema: dict[str, Any], issues: list[Any],
) -> dict[str, Any]:
    codes = {str(getattr(issue, "code", "")) for issue in issues}
    properties: dict[str, Any] = {}
    if any(code.startswith("common_mistake.") or code.startswith("error_tag.common_mistake") for code in codes):
        properties["common_mistakes"] = copy.deepcopy(full_schema["properties"]["common_mistakes"])
    if any(code.startswith("quick_practice.") for code in codes):
        properties["quick_practice"] = copy.deepcopy(full_schema["properties"]["quick_practice"])
    if not properties:
        raise ValueError("learning-block patch requested without a repairable block")
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def _generation_learning_context(data: dict[str, Any], issues: list[Any]) -> dict[str, Any]:
    selected = generation_learning_block_repair_issues(issues)
    codes = {str(getattr(issue, "code", "")) for issue in selected}
    context: dict[str, Any] = {
        "issues": [
            {"code": issue.code, "path": issue.path, "message": issue.message}
            for issue in selected[:12]
        ],
        "summary": data.get("summary"),
        "when_to_use": data.get("when_to_use"),
        "formula": data.get("formula"),
        "negative": data.get("negative"),
        "question": data.get("question"),
        "examples": [
            {"text": example.get("text"), "form": example.get("form")}
            for example in data.get("examples") or []
        ],
    }
    if any(code.startswith("common_mistake.") or code.startswith("error_tag.common_mistake") for code in codes):
        context["common_mistakes"] = data.get("common_mistakes")
    if any(code.startswith("quick_practice.") for code in codes):
        context["quick_practice"] = data.get("quick_practice")
    return context


def request_generation_learning_patch(
    llm: LLMClient,
    *,
    point_id: str,
    target_lang: str,
    data: dict[str, Any],
    issues: list[Any],
    full_schema: dict[str, Any],
) -> Any:
    """Repair only learner mistake/practice blocks; grammar lesson prose stays immutable."""
    selected = generation_learning_block_repair_issues(issues)
    patch_schema = _generation_learning_patch_schema(full_schema, selected)
    system = """You repair ONLY the bounded learner-exercise blocks of an already-written grammar lesson.
The grammar formula, explanations, examples, translations, title, summary, comparisons and personal-production task are immutable.
Return only the block(s) requested by the JSON schema.

Rules:
- common_mistakes: wrong and right must be genuinely different. The wrong sentence must demonstrate a real learner grammar error matching its error_tag; the right sentence must be grammatical and teach the same intended point. Do not invent a spelling-only error.
- quick_practice: every q contains exactly one literal ___ blank. Keep exactly three items. The answer index points to the genuinely correct option; that correct option has error_tag null. Every wrong option must be a plausible grammar error and carry the matching non-null error_tag.
- Preserve the lesson's grammar scope and difficulty. Use the unchanged examples/formula as evidence; do not broaden the lesson or rewrite unrelated content.
- For Chinese, write natural unspaced Chinese around the blank; pinyin hints may be omitted because code derives pinyin deterministically.
"""
    user = (
        f"Repair learner blocks for {point_id} ({target_lang}).\n"
        + json.dumps(
            _generation_learning_context(data, selected),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return llm.complete(
        system=system,
        user=user,
        json_schema=patch_schema,
        schema_name="grammar_point_v04_learning_patch",
        max_tokens=V04_LEARNING_BLOCK_REPAIR_MAX_TOKENS,
    )


def apply_generation_learning_patch(
    data: dict[str, Any], patch: dict[str, Any],
) -> dict[str, Any]:
    """Replace only explicitly returned common-mistake/quick-practice blocks."""
    allowed = {"common_mistakes", "quick_practice"}
    if not patch or any(key not in allowed for key in patch):
        raise ValueError("learning patch contains unsupported keys")
    out = copy.deepcopy(data)
    for key, value in patch.items():
        out[key] = copy.deepcopy(value)
    return out
'''
text = text.replace(anchor, insert + anchor, 1)

old = '''            targeted_repair_used = False
            structure_repair_exhausted = False
'''
new = '''            targeted_repair_used = False
            learning_repair_used = False
            structure_repair_exhausted = False
'''
assert old in text, 'repair flags anchor missing'
text = text.replace(old, new, 1)

anchor = '''            # Remaining semantic failures can still be confined to formula ordering,
            # stored example spans and the deterministic production rule. Repair that
            # small surface before paying for a fresh full lesson.
            if can_target_repair(issues):
'''
assert anchor in text, 'semantic repair loop anchor missing'
block = '''            # Mistake/practice defects are learner-content bugs, but they do not justify
            # buying a fresh full lesson. Repair only the implicated small block(s).
            if can_repair_generation_learning_blocks(issues):
                learning_repair_used = True
                learning_issues = generation_learning_block_repair_issues(issues)
                try:
                    learning_patch = request_generation_learning_patch(
                        self.llm,
                        point_id=point_id,
                        target_lang=existing["target_lang"],
                        data=result.data,
                        issues=learning_issues,
                        full_schema=schema,
                    )
                except LLMError as exc:
                    if exc.usage is not None:
                        patch_cost = exc.usage.cost_usd(self.llm.model)
                        if patch_cost is None:
                            cost_known = False
                        else:
                            total_cost += patch_cost
                    all_cached = False
                else:
                    patch_cost = _incremental_result_cost(learning_patch)
                    if patch_cost is None:
                        cost_known = False
                    else:
                        total_cost += patch_cost
                    all_cached = all_cached and learning_patch.cached
                    try:
                        learning_data = apply_generation_learning_patch(
                            result.data, learning_patch.data
                        )
                    except ValueError:
                        pass
                    else:
                        result = replace(result, data=learning_data)
                        point, contract_issues = assemble(result)
                        issues = [
                            *contract_issues,
                            *validate_generated_point(self.lang, point, self.root),
                        ]
                        if not issues:
                            save_point(self.lang, point, self.root)
                            register_realization(point, self.root)
                            return GenerateOutcome(
                                point_id, "written",
                                cost_usd=(total_cost if cost_known and total_cost else None),
                                cached=all_cached,
                            )

            # Remaining semantic failures can still be confined to formula ordering,
            # stored example spans and the deterministic production rule. Repair that
            # small surface before paying for a fresh full lesson.
            if can_target_repair(issues):
'''
text = text.replace(anchor, block, 1)

old = '''                f"semantic validation failed after {attempts_used} full attempt(s)"
                + (" plus targeted repair" if targeted_repair_used else "")
                + f": {last_problem}"
'''
new = '''                f"semantic validation failed after {attempts_used} full attempt(s)"
                + (" plus learning-block repair" if learning_repair_used else "")
                + (" plus targeted repair" if targeted_repair_used else "")
                + f": {last_problem}"
'''
assert old in text, 'final reason anchor missing'
text = text.replace(old, new, 1)

old = '''            if targeted_repair_used or structure_repair_exhausted or (contract_failure and attempt >= 2):
                break
'''
new = '''            if targeted_repair_used or learning_repair_used or structure_repair_exhausted or (contract_failure and attempt >= 2):
                break
'''
assert old in text, 'retry guard anchor missing'
text = text.replace(old, new, 1)

path.write_text(text, encoding='utf-8')
