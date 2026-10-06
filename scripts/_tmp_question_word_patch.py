from pathlib import Path

path = Path("grammar_lab/pipeline/generate.py")
text = path.read_text(encoding="utf-8")
anchor = '\ndef normalize_generated_structure(data: dict[str, Any], zh: bool) -> dict[str, Any]:\n'
assert anchor in text
helper = r'''

_ZH_QUESTION_WORD_SURFACES = frozenset({
    "谁", "什么", "哪", "哪儿", "哪里", "几", "多少", "怎么", "怎么样", "为什么",
    "什么时候", "多久", "多长时间", "多大", "多高", "多远", "哪天", "哪年", "几点",
})


def _question_frame_label(example: Any, kind: str) -> Any:
    labels = {
        "before": {
            "vi": "phần đứng trước từ để hỏi",
            "en": "context before the question word",
            "zh-Hans": "疑问词前的成分",
        },
        "question": {
            "vi": "từ để hỏi ở đúng vị trí của phần cần hỏi",
            "en": "question word in the missing information's original position",
            "zh-Hans": "疑问词保留在原来的位置",
        },
        "after": {
            "vi": "phần đứng sau từ để hỏi",
            "en": "context after the question word",
            "zh-Hans": "疑问词后的成分",
        },
    }
    if isinstance(example, dict):
        return {locale: labels[kind].get(locale, labels[kind]["en"]) for locale in example}
    if isinstance(example, str):
        return labels[kind]["vi"]
    return labels[kind]["vi"]


def normalize_generated_question_word_frame(data: dict[str, Any], zh: bool) -> dict[str, Any]:
    """Repair zh.question_words into an in-place question-word position frame.

    Chinese interrogative pronouns stay where the missing information belongs. A
    cached candidate may instead force every question into S-V-O; locatives such
    as ``你在哪儿工作？`` then bind ``哪儿`` inside ``在哪儿工作``. Reordering cannot
    make that analysis truthful, so this point-specific normalizer represents the
    actual invariant directly: context before + question word + context after.

    The repair remains fail-closed unless every question example contains exactly
    one recognised interrogative binding, at least one example proves a strict
    overlap with another binding, and question-form production rules constrain only
    recognised interrogative literals.
    """
    out = copy.deepcopy(data)
    if not zh:
        return out

    formula = out.get("question") or []
    examples = [example for example in out.get("examples", []) if example.get("form") == "question"]
    if not formula or not examples:
        return out

    production = out.get("personal_production") or {}
    production_rule = production.get("pattern_rule") or {}
    production_slots = (
        production_rule.get("slots") or []
        if production.get("target_form") == "question"
        else []
    )
    if production.get("target_form") == "question":
        for rule in production_slots:
            values = rule.get("any_of") or []
            if (
                rule.get("regex")
                or not values
                or any(target_text(str(value), True) not in _ZH_QUESTION_WORD_SURFACES for value in values)
            ):
                return out

    records: list[tuple[dict[str, Any], str, str, str]] = []
    overlap_witness = False
    question_values: list[str] = []

    for example in examples:
        text = target_text(str(example.get("text", "")), True)
        bindings = example.get("bindings") or []
        question_bindings = [
            binding
            for binding in bindings
            if target_text(str(binding.get("text", "")), True) in _ZH_QUESTION_WORD_SURFACES
        ]
        if len(question_bindings) != 1:
            return out

        question_binding = question_bindings[0]
        q_surface = target_text(str(question_binding.get("text", "")), True)
        positions: list[int] = []
        start = text.find(q_surface)
        while start >= 0:
            positions.append(start)
            start = text.find(q_surface, start + 1)
        if len(positions) != 1:
            return out
        q_start = positions[0]
        q_end = q_start + len(q_surface)

        for binding in bindings:
            if binding is question_binding:
                continue
            surface = target_text(str(binding.get("text", "")), True)
            if not surface:
                continue
            starts: list[int] = []
            begin = text.find(surface)
            while begin >= 0:
                starts.append(begin)
                begin = text.find(surface, begin + 1)
            if len(starts) != 1:
                continue
            begin = starts[0]
            finish = begin + len(surface)
            if begin <= q_start and q_end <= finish and (begin < q_start or q_end < finish):
                overlap_witness = True

        prefix = text[:q_start].strip()
        suffix = text[q_end:].strip().rstrip("？?。.!！").strip()
        if not prefix and not suffix:
            return out
        records.append((example, prefix, q_surface, suffix))
        if q_surface not in question_values:
            question_values.append(q_surface)

    if not overlap_witness:
        return out

    sample_label = formula[0].get("label") if formula else ""
    out["question"] = [
        {
            "text": "…",
            "role": "other",
            "label": _question_frame_label(sample_label, "before"),
            "optional": True,
            "options": [],
        },
        {
            "text": "疑问词",
            "role": "other",
            "label": _question_frame_label(sample_label, "question"),
            "optional": False,
            "options": [{"text": value} for value in question_values],
        },
        {
            "text": "…",
            "role": "other",
            "label": _question_frame_label(sample_label, "after"),
            "optional": True,
            "options": [],
        },
    ]

    for example, prefix, q_surface, suffix in records:
        rewritten: list[dict[str, Any]] = []
        if prefix:
            rewritten.append({"slot_index": 0, "text": prefix})
        rewritten.append({"slot_index": 1, "text": q_surface})
        if suffix:
            rewritten.append({"slot_index": 2, "text": suffix})
        example["bindings"] = rewritten

    if production.get("target_form") == "question":
        for rule in production_slots:
            rule["slot_index"] = 1
        production_rule["ordered"] = True

    return out
'''
text = text.replace(anchor, helper + anchor, 1)

old = '            data = normalize_generated_structure(result.data, zh)\n'
new = (
    '            candidate_data = normalize_generated_question_word_frame(result.data, zh) '
    'if point_id == "zh.question_words" else result.data\n'
    '            data = normalize_generated_structure(candidate_data, zh)\n'
)
assert text.count(old) == 1
text = text.replace(old, new, 1)

old = '                structure_data = normalize_generated_structure(result.data, zh)\n'
new = (
    '                candidate_structure_data = normalize_generated_question_word_frame(result.data, zh) '
    'if point_id == "zh.question_words" else result.data\n'
    '                structure_data = normalize_generated_structure(candidate_structure_data, zh)\n'
)
assert text.count(old) == 1
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
