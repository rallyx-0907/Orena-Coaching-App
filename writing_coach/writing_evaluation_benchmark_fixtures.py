"""Curated, original offline fixtures for the Writing quality benchmark."""

from __future__ import annotations

from writing_coach.writing_evaluation_benchmark import (
    BenchmarkConstraints,
    BenchmarkKind,
    ScoreBand,
    WritingBenchmarkCase,
)


ENGLISH_BENCHMARK_CASES = (
    WritingBenchmarkCase(
        case_id="en-clean-agreement",
        language="en",
        kind=BenchmarkKind.CLEAN,
        target_level="B1",
        task_prompt="Describe one habit in your family.",
        learner_text="My brother works from home every Friday.",
        constraints=BenchmarkConstraints(
            protected_correct_fragments=("My brother works",),
            max_error_count=0,
        ),
        rationale="A short correct sentence anchors agreement precision and pairwise scoring.",
        comparison_id="en-agreement-pair",
        comparison_role="stronger",
        comparison_dimensions=("grammar",),
    ),
    WritingBenchmarkCase(
        case_id="en-beginner-clear",
        language="en",
        kind=BenchmarkKind.BEGINNER_TEXT,
        target_level="A1",
        task_prompt="Write two sentences about a daily drink.",
        learner_text="I like tea. I drink it every morning.",
        constraints=BenchmarkConstraints(
            protected_correct_fragments=("I like tea.", "I drink it every morning."),
            max_error_count=0,
            score_bands=(ScoreBand("grammar", 55, 100),),
        ),
        rationale="Simple language should not be penalized merely for being beginner-level.",
    ),
    WritingBenchmarkCase(
        case_id="en-obvious-agreement",
        language="en",
        kind=BenchmarkKind.OBVIOUS_ERROR,
        target_level="B1",
        task_prompt="Describe one habit in your family.",
        learner_text="My brother work from home every Friday.",
        constraints=BenchmarkConstraints(required_error_categories=frozenset({"agreement"})),
        rationale="A single clear agreement error should be found with exact evidence.",
        comparison_id="en-agreement-pair",
        comparison_role="weaker",
        comparison_dimensions=("grammar",),
    ),
    WritingBenchmarkCase(
        case_id="en-obvious-mixed-form",
        language="en",
        kind=BenchmarkKind.OBVIOUS_ERROR,
        target_level="B2",
        task_prompt="Describe a colleague's interests and communication style.",
        learner_text="She is teacher who is interested on science and speaks confidence.",
        constraints=BenchmarkConstraints(
            required_error_categories=frozenset({"article", "preposition", "word_form"})
        ),
        rationale="The text contains visible article, preposition, and word-form problems.",
    ),
    WritingBenchmarkCase(
        case_id="en-awkward-naturalness",
        language="en",
        kind=BenchmarkKind.NATURALNESS,
        target_level="B2",
        task_prompt="Describe your reaction to a productive meeting.",
        learner_text="The meeting gave me a positive feeling in a way that was good.",
        constraints=BenchmarkConstraints(
            required_error_categories=frozenset({"naturalness", "word_choice"})
        ),
        rationale="The sentence is understandable but awkward rather than plainly ungrammatical.",
    ),
    WritingBenchmarkCase(
        case_id="en-task-one-reason",
        language="en",
        kind=BenchmarkKind.TASK_ACHIEVEMENT,
        target_level="B1",
        task_prompt="Give two reasons why a public park improves a neighborhood.",
        learner_text="A park gives children a safe place to play.",
        constraints=BenchmarkConstraints(
            score_bands=(ScoreBand("task_achievement", 0, 70),),
        ),
        rationale="The prose is correct but supplies only one of two requested reasons.",
    ),
    WritingBenchmarkCase(
        case_id="en-weak-coherence",
        language="en",
        kind=BenchmarkKind.COHERENCE,
        target_level="B2",
        task_prompt="Explain how you prepare for an important presentation.",
        learner_text="I check my slides. My neighbor owns a red bicycle. I practice the opening.",
        constraints=BenchmarkConstraints(score_bands=(ScoreBand("coherence", 0, 65),)),
        rationale="Correct individual sentences include an irrelevant interruption.",
    ),
    WritingBenchmarkCase(
        case_id="en-fashion-false-positive",
        language="en",
        kind=BenchmarkKind.FALSE_POSITIVE_TRAP,
        target_level="B1",
        task_prompt="Write one sentence about a personal interest.",
        learner_text="I care about fashion because clothes can express personality.",
        constraints=BenchmarkConstraints(
            protected_correct_fragments=("I care about fashion",),
            max_error_count=0,
        ),
        rationale="A known-correct care-about construction must not be 'corrected'.",
    ),
    WritingBenchmarkCase(
        case_id="en-strong-argument",
        language="en",
        kind=BenchmarkKind.STRONG_TEXT,
        target_level="C1",
        task_prompt="Argue briefly for one practical way to reduce traffic.",
        learner_text=(
            "Cities should expand reliable bus lanes because faster service attracts drivers. "
            "As ridership grows, streets become quieter and safer for everyone."
        ),
        constraints=BenchmarkConstraints(
            protected_correct_fragments=("faster service attracts drivers",),
            max_error_count=1,
            score_bands=(ScoreBand("coherence", 70, 100),),
        ),
        rationale="A concise, coherent argument should not attract many dubious corrections.",
    ),
    WritingBenchmarkCase(
        case_id="en-evidence-integrity",
        language="en",
        kind=BenchmarkKind.EVIDENCE_INTEGRITY,
        target_level="B1",
        task_prompt="Describe how you travel to work.",
        learner_text="I take the early bus and arrive before eight.",
        constraints=BenchmarkConstraints(protected_correct_fragments=("arrive before eight",)),
        rationale="Every cited fragment must occur literally in this compact source.",
    ),
    WritingBenchmarkCase(
        case_id="en-target-a2",
        language="en",
        kind=BenchmarkKind.TARGET_LEVEL_BIAS,
        target_level="A2",
        task_prompt="Explain one benefit of keeping a weekly plan.",
        learner_text="A weekly plan helps me rank urgent tasks and protect time for difficult work.",
        constraints=BenchmarkConstraints(expected_demonstrated_levels=("B1", "B2")),
        rationale="Identical work should retain its demonstrated level under a lower target.",
        target_pair_id="en-target-stability",
    ),
    WritingBenchmarkCase(
        case_id="en-target-c1",
        language="en",
        kind=BenchmarkKind.TARGET_LEVEL_BIAS,
        target_level="C1",
        task_prompt="Explain one benefit of keeping a weekly plan.",
        learner_text="A weekly plan helps me rank urgent tasks and protect time for difficult work.",
        constraints=BenchmarkConstraints(expected_demonstrated_levels=("B1", "B2")),
        rationale="Identical work should retain its demonstrated level under a higher target.",
        target_pair_id="en-target-stability",
    ),
)


CHINESE_BENCHMARK_CASES = (
    WritingBenchmarkCase(
        case_id="zh-clean-word-order",
        language="zh",
        kind=BenchmarkKind.CLEAN,
        target_level="HSK2",
        task_prompt="请写一句话介绍你的学习习惯。",
        learner_text="我每天学习汉语。",
        constraints=BenchmarkConstraints(
            protected_correct_fragments=("我每天学习汉语",),
            max_error_count=0,
        ),
        rationale="A natural basic sentence anchors Chinese word-order precision.",
        comparison_id="zh-word-order-pair",
        comparison_role="stronger",
        comparison_dimensions=("grammar",),
    ),
    WritingBenchmarkCase(
        case_id="zh-beginner-clear",
        language="zh",
        kind=BenchmarkKind.BEGINNER_TEXT,
        target_level="HSK1",
        task_prompt="请写两句介绍你的爱好。",
        learner_text="我喜欢看书。我也喜欢听音乐。",
        constraints=BenchmarkConstraints(
            protected_correct_fragments=("我喜欢看书", "我也喜欢听音乐"),
            max_error_count=0,
            score_bands=(ScoreBand("grammar", 55, 100),),
        ),
        rationale="Short beginner Chinese should be evaluated on correctness, not complexity alone.",
    ),
    WritingBenchmarkCase(
        case_id="zh-obvious-word-order",
        language="zh",
        kind=BenchmarkKind.OBVIOUS_ERROR,
        target_level="HSK2",
        task_prompt="请写一句话介绍你的学习习惯。",
        learner_text="我每天汉语学习。",
        constraints=BenchmarkConstraints(required_error_categories=frozenset({"word_order"})),
        rationale="A clear word-order issue should be identified with literal Chinese evidence.",
        comparison_id="zh-word-order-pair",
        comparison_role="weaker",
        comparison_dimensions=("grammar",),
    ),
    WritingBenchmarkCase(
        case_id="zh-obvious-aspect",
        language="zh",
        kind=BenchmarkKind.OBVIOUS_ERROR,
        target_level="HSK4",
        task_prompt="请写一句话介绍昨天的旅行。",
        learner_text="我昨天去过了北京。",
        constraints=BenchmarkConstraints(required_error_categories=frozenset({"aspect", "particle"})),
        rationale="The stacked aspect markers create a stable particle/aspect problem.",
    ),
    WritingBenchmarkCase(
        case_id="zh-measure-collocation",
        language="zh",
        kind=BenchmarkKind.OBVIOUS_ERROR,
        target_level="HSK4",
        task_prompt="请介绍你买的东西和做的决定。",
        learner_text="我买了三个书，也做了一张重要的决定。",
        constraints=BenchmarkConstraints(
            required_error_categories=frozenset({"measure_word", "collocation"})
        ),
        rationale="The sentence contains clear measure-word and collocation problems.",
    ),
    WritingBenchmarkCase(
        case_id="zh-awkward-naturalness",
        language="zh",
        kind=BenchmarkKind.NATURALNESS,
        target_level="HSK5",
        task_prompt="请写一句话表达你对这个计划的看法。",
        learner_text="对于这个计划，我进行一个很满意的感觉。",
        constraints=BenchmarkConstraints(
            required_error_categories=frozenset({"naturalness", "collocation", "word_choice"})
        ),
        rationale="The meaning is recoverable, but the expression is translation-like and unnatural.",
    ),
    WritingBenchmarkCase(
        case_id="zh-task-one-reason",
        language="zh",
        kind=BenchmarkKind.TASK_ACHIEVEMENT,
        target_level="HSK4",
        task_prompt="请说明公园改善社区的两个原因。",
        learner_text="公园让孩子们有安全的地方玩。",
        constraints=BenchmarkConstraints(score_bands=(ScoreBand("task_achievement", 0, 70),)),
        rationale="The response gives one valid reason but does not complete the two-part task.",
    ),
    WritingBenchmarkCase(
        case_id="zh-transit-false-positive",
        language="zh",
        kind=BenchmarkKind.FALSE_POSITIVE_TRAP,
        target_level="HSK3",
        task_prompt="请写一句话介绍你的上班方式。",
        learner_text="我每天坐地铁去上班。",
        constraints=BenchmarkConstraints(
            protected_correct_fragments=("我每天坐地铁去上班",),
            max_error_count=0,
        ),
        rationale="A natural Chinese transport construction must not receive a false correction.",
    ),
    WritingBenchmarkCase(
        case_id="zh-strong-argument",
        language="zh",
        kind=BenchmarkKind.STRONG_TEXT,
        target_level="HSK6",
        task_prompt="请简要说明城市为什么应该增加公交专用道。",
        learner_text="城市应该增加公交专用道，因为稳定快捷的服务能吸引更多乘客，从而缓解拥堵。",
        constraints=BenchmarkConstraints(
            protected_correct_fragments=("从而缓解拥堵",),
            max_error_count=1,
            score_bands=(ScoreBand("coherence", 70, 100),),
        ),
        rationale="A compact, cohesive Chinese argument should not attract speculative corrections.",
    ),
    WritingBenchmarkCase(
        case_id="zh-evidence-integrity",
        language="zh",
        kind=BenchmarkKind.EVIDENCE_INTEGRITY,
        target_level="HSK3",
        task_prompt="请介绍你早上怎么去学校。",
        learner_text="我七点坐公交车去学校。",
        constraints=BenchmarkConstraints(protected_correct_fragments=("七点坐公交车",)),
        rationale="Chinese evidence must be copied literally rather than invented or translated.",
    ),
    WritingBenchmarkCase(
        case_id="zh-target-hsk2",
        language="zh",
        kind=BenchmarkKind.TARGET_LEVEL_BIAS,
        target_level="HSK2",
        task_prompt="请说明每周计划的一个好处。",
        learner_text="每周计划能帮我分清任务的轻重缓急，也能留出时间处理难题。",
        constraints=BenchmarkConstraints(expected_demonstrated_levels=("HSK4", "HSK5")),
        rationale="Identical Chinese work should retain its demonstrated level under a lower target.",
        target_pair_id="zh-target-stability",
    ),
    WritingBenchmarkCase(
        case_id="zh-target-hsk7-9",
        language="zh",
        kind=BenchmarkKind.TARGET_LEVEL_BIAS,
        target_level="HSK7-9",
        task_prompt="请说明每周计划的一个好处。",
        learner_text="每周计划能帮我分清任务的轻重缓急，也能留出时间处理难题。",
        constraints=BenchmarkConstraints(expected_demonstrated_levels=("HSK4", "HSK5")),
        rationale="Identical Chinese work should retain its demonstrated level under a higher target.",
        target_pair_id="zh-target-stability",
    ),
)


WRITING_BENCHMARK_CASES = ENGLISH_BENCHMARK_CASES + CHINESE_BENCHMARK_CASES

_PASSING_SUGGESTIONS = {
    "en-obvious-agreement": "My brother works from home every Friday.",
    "en-obvious-mixed-form": "She is a teacher who is interested in science and speaks confidently.",
    "en-awkward-naturalness": "The meeting left me feeling positive.",
    "zh-obvious-word-order": "我每天学习汉语。",
    "zh-obvious-aspect": "我昨天去过北京。",
    "zh-measure-collocation": "我买了三本书，也做了一个重要的决定。",
    "zh-awkward-naturalness": "我对这个计划很满意。",
}


def benchmark_case(case_id: str) -> WritingBenchmarkCase:
    for case in WRITING_BENCHMARK_CASES:
        if case.case_id == case_id:
            return case
    raise KeyError(case_id)


def known_passing_result(case: WritingBenchmarkCase) -> dict[str, object]:
    """Return a deterministic normalized-shape result satisfying ``case``."""

    scores = {
        "grammar": 75.0,
        "vocabulary": 75.0,
        "coherence": 75.0,
        "task_achievement": 75.0,
        "naturalness": 75.0,
    }
    for band in case.constraints.score_bands:
        scores[band.dimension] = (band.minimum + band.maximum) / 2

    errors: list[dict[str, object]] = []
    if case.constraints.required_error_categories:
        category = sorted(case.constraints.required_error_categories)[0]
        errors.append(
            {
                "category": category,
                "fragment": case.learner_text,
                "explanation_vi": "Bằng chứng lỗi rõ ràng trong câu gốc.",
                "suggestion": _PASSING_SUGGESTIONS[case.case_id],
                "mini_rule_vi": "Dùng cấu trúc phù hợp với ngữ cảnh.",
                "confidence": 0.9,
            }
        )

    level = (
        case.constraints.expected_demonstrated_levels[0]
        if case.constraints.expected_demonstrated_levels
        else case.target_level
    )
    return {
        **scores,
        "band_status": "estimated",
        "cefr_estimate": level,
        "summary_vi": "Bài viết được đánh giá theo bằng chứng trong văn bản.",
        "strengths_vi": [],
        "priorities_vi": [],
        "strength_evidence": [],
        "errors": errors,
    }


def known_failing_result(case: WritingBenchmarkCase) -> dict[str, object]:
    """Return a deterministic result that fails literal-evidence integrity."""

    result = known_passing_result(case)
    errors = list(result["errors"])
    errors.append(
        {
            "category": "other",
            "fragment": "invented fragment absent from learner text",
            "explanation_vi": "Bằng chứng này không có trong bài.",
            "suggestion": "A different sentence",
            "mini_rule_vi": "Chỉ trích dẫn nguyên văn.",
            "confidence": 0.9,
        }
    )
    result["errors"] = errors
    return result
