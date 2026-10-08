"""The V1 read-only tools, mapped to the services that will back them (spec §8).

This is a plan, not a registry: nothing here runs. Each tool names the
existing callable that does the work (`backed_by`) and, for an adapter, the
other existing callables it joins (`composes`). Both are "module:attribute" and
a test imports every one of them, so the plan cannot name a service that does
not exist. A tool with no backing service is a `gap`: it has no `backed_by`,
and `docs/project/UI_BACKEND_GAPS.md` must list it (spec §8, D15) before
anyone writes a service for it.

Verified against the code on 2026-09-27 (lane feature/orena-intelligence).
Where the spec's §8 table named a module that cannot serve one learner - an
admin-only aggregate, a retired Reading engine, a content validator - the plan
names what can.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from writing_coach.agent.contract import EVIDENCE_SOURCES

Verdict = Literal["backed", "adapter", "gap"]
BOTH = ("en", "zh-CN")

_SPECIALIZED = "writing_coach.persistence.specialized_repository:PostgresSpecializedLearningRepository"
_READING_EVIDENCE = "writing_coach.persistence.reading_evidence_repository:ReadingEvidenceRepository"


@dataclass(frozen=True)
class PlannedTool:
    name: str
    verdict: Verdict
    backed_by: str | None
    note: str
    composes: tuple[str, ...] = ()
    languages: tuple[str, ...] = BOTH
    evidence_source: str | None = None
    linguistic_reason: str | None = None

    def __post_init__(self) -> None:
        if (self.verdict == "gap") != (self.backed_by is None):
            raise ValueError(f"{self.name}: a gap has no backed_by, and only a gap")
        if self.verdict == "gap" and self.composes:
            raise ValueError(f"{self.name}: a gap composes nothing")
        if self.evidence_source is not None and self.evidence_source not in EVIDENCE_SOURCES:
            raise ValueError(f"{self.name}: unknown evidence source {self.evidence_source!r}")
        if set(self.languages) != set(BOTH) and not self.linguistic_reason:
            raise ValueError(f"{self.name}: one-language tool without a linguistic reason")


_PLAN = (
    # --- where the learner is: the request's own context (Tier 1) ------------
    PlannedTool(
        "get_app_context",
        "backed",
        "writing_coach.agent.context:build_tier1",
        "Tier 1 context from the request; a tool only so the model can re-read it.",
    ),
    PlannedTool(
        "get_current_selection",
        "backed",
        "writing_coach.agent.context:build_tier1",
        "The selection in view, or the session's last one.",
    ),
    PlannedTool(
        "get_current_learning_activity",
        "backed",
        "writing_coach.agent.context:build_tier1",
        "activity_type and the ids in view.",
    ),
    # --- overview and coaching -------------------------------------------------
    PlannedTool(
        "get_learning_overview",
        "backed",
        "writing_coach.learner_summary:learner_summary",
        "Called in-process with the sources GET /api/learner-summary uses. Not product_activity or "
        "readiness_summary: both are admin-only aggregates across learners.",
        composes=("writing_coach.learner_summary_api:runtime_sources",),
        evidence_source="learner_summary",
    ),
    PlannedTool(
        "get_skill_progress",
        "adapter",
        "writing_coach.learner_summary:learner_summary",
        "One domain of the summary; its 'language' domain is the snapshot's 'vocabulary'. Speaking adds "
        "speaking_progress (PostgreSQL only).",
        composes=(f"{_SPECIALIZED}.speaking_progress",),
        evidence_source="learner_summary",
    ),
    PlannedTool(
        "get_recent_learning_activity",
        "adapter",
        "writing_coach.learner_summary:learner_summary",
        "Merge and sort the domains' observations; no further reads.",
        evidence_source="learner_summary",
    ),
    PlannedTool(
        "build_learning_snapshot",
        "adapter",
        "writing_coach.learner_summary:learner_summary",
        "Spec §24 without current_level (human ruling 2026-09-27); review_due from the review queue; "
        "producer redacted before any provider sees it.",
        composes=("writing_coach.persistence.library_repository:LibraryRepository.review_queue",),
        evidence_source="learner_summary",
    ),
    PlannedTool(
        "get_learning_weaknesses",
        "adapter",
        "writing_coach.agent.coaching:weaknesses",
        "Slice 3 (human direction 2026-09-28): deterministic counts over the learner's own records - recurring "
        "writing error categories, provider-flagged words, dictation lines, reading checks, forgotten words. "
        "No strength or trend (growth stays unavailable); grammar has no mistake store and stays null.",
        composes=(
            "writing_coach.writing_analytics:parse_persisted_error_events",
            f"{_SPECIALIZED}.list_speaking_attempt_records",
            f"{_SPECIALIZED}.list_recent_listening_progress_records",
            f"{_READING_EVIDENCE}.list_evidence",
            "writing_coach.becoming_library:list_library_vocabulary",
        ),
        evidence_source="learner_summary",
    ),
    PlannedTool(
        "get_recommended_next_activities",
        "adapter",
        "writing_coach.cross_skill_transfer:select_cross_skill_cue",
        "The deterministic cue GET /api/cross-skill-cue already composes from the four domains.",
        composes=(
            "writing_coach.becoming_memory:get_review_cue",
            f"{_READING_EVIDENCE}.list_evidence",
            f"{_SPECIALIZED}.list_recent_listening_progress_records",
            f"{_SPECIALIZED}.list_speaking_attempt_records",
        ),
        evidence_source="learner_summary",
    ),
    # --- vocabulary --------------------------------------------------------------
    PlannedTool(
        "get_due_review_summary",
        "backed",
        "writing_coach.becoming_library:library_summary",
        "Counts by state for the current learner and language.",
        evidence_source="vocabulary.review",
    ),
    PlannedTool(
        "get_due_vocabulary",
        "backed",
        "writing_coach.becoming_library:list_library_vocabulary",
        "Called with status='due'; order alone only sorts.",
        evidence_source="vocabulary.review",
    ),
    PlannedTool(
        "get_word_detail",
        "adapter",
        "writing_coach.becoming_library:catalog_entry_for",
        "The catalogue entry and the saved state, read-only. Not word_detail.py: every call there reaches a "
        "provider and writes operation telemetry.",
        composes=("writing_coach.becoming_library:saved_vocabulary_state",),
        evidence_source="vocabulary.review",
    ),
    PlannedTool(
        "get_saved_word_state",
        "backed",
        "writing_coach.becoming_library:saved_vocabulary_state",
        "A word absent from the result is not saved.",
        evidence_source="vocabulary.review",
    ),
    # --- speaking ----------------------------------------------------------------
    PlannedTool(
        "get_pronunciation_attempt",
        "adapter",
        f"{_SPECIALIZED}.list_speaking_attempt_records",
        "No get-by-id exists: list, then pick the attempt. PostgreSQL only. Never the POST route.",
        evidence_source="speech.pronunciation",
    ),
    PlannedTool(
        "get_pronunciation_history",
        "backed",
        f"{_SPECIALIZED}.list_speaking_attempt_records",
        "Recent attempts with their stored evidence.",
        composes=(f"{_SPECIALIZED}.speaking_progress",),
        evidence_source="speech.pronunciation",
    ),
    PlannedTool(
        "get_pronunciation_word_detail",
        "adapter",
        f"{_SPECIALIZED}.list_speaking_attempt_records",
        "One word of a stored attempt. 'Flagged' is the provider's error_type, never a threshold (D-084); "
        "syllables and timings are not persisted.",
        evidence_source="speech.pronunciation",
    ),
    PlannedTool(
        "get_tone_analysis",
        "gap",
        None,
        "No measured tone exists: the provider's syllable tone is the reference label, and toneActual "
        "stays empty until a provider measures pitch (D-084).",
        languages=("zh-CN",),
        evidence_source="speech.pronunciation",
        linguistic_reason="Lexical tone is a property of Chinese syllables.",
    ),
    PlannedTool(
        "get_stress_analysis",
        "gap",
        None,
        "No per-word stress exists: only one overall prosody score, requested for en-US and off by default.",
        languages=("en",),
        evidence_source="speech.pronunciation",
        linguistic_reason="Lexical stress placement is an English feature Chinese does not share.",
    ),
    # --- writing -----------------------------------------------------------------
    PlannedTool(
        "get_current_writing_evaluation",
        "backed",
        "writing_coach.persistence.learning_repository:PostgresLearningRepository.get_essay",
        "The stored review of essay_id, projected as the Writing review contract.",
        composes=("writing_coach.writing_contract:project_review",),
        evidence_source="writing.evaluation",
    ),
    PlannedTool(
        "get_writing_feedback_items",
        "adapter",
        "writing_coach.persistence.learning_repository:PostgresLearningRepository.get_essay",
        "Only the review's issues (and strengths), sliced in, never the whole row.",
        composes=("writing_coach.writing_contract:project_issue",),
        evidence_source="writing.evaluation",
    ),
    PlannedTool(
        "get_writing_history_summary",
        "adapter",
        "writing_coach.writing_analytics:parse_persisted_error_events",
        "The error categories across the learner's versions, through the app's own /api/error-memory read.",
        evidence_source="writing.evaluation",
    ),
    # --- grammar -----------------------------------------------------------------
    PlannedTool(
        "get_grammar_point",
        "adapter",
        "writing_coach.languages.runtime:active_grammar_by_id",
        "Course entry and knowledge for the active language, as the grammar routes compose them.",
        composes=("writing_coach.languages.runtime:active_grammar_knowledge_by_id",),
        evidence_source="grammar.catalog",
    ),
    PlannedTool(
        "search_grammar_points",
        "adapter",
        "writing_coach.languages.runtime:active_grammar_course",
        "A filter over the small static course and its lookup tags; no index.",
        composes=("writing_coach.languages.runtime:active_grammar_knowledge_by_id",),
        evidence_source="grammar.catalog",
    ),
    PlannedTool(
        "get_grammar_mistakes_summary",
        "gap",
        None,
        "No per-pattern mistake store: grammar progress is completion only, and essays keep heuristic "
        "category links, not grammar ids.",
        evidence_source="writing.evaluation",
    ),
    # --- reading -----------------------------------------------------------------
    PlannedTool(
        "get_current_reading_context",
        "adapter",
        "writing_coach.persistence.reading_content_repository:ReadingContentRepository.get_published_article",
        "The article in view, or the library chapter for reading.library; both are shared content.",
        composes=(
            "writing_coach.persistence.reading_library_repository:PostgresReadingLibraryRepository.get_chapter",
            f"{_READING_EVIDENCE}.served_set",
        ),
        evidence_source="reading.comprehension",
    ),
    PlannedTool(
        "get_reading_progress",
        "adapter",
        f"{_READING_EVIDENCE}.list_evidence",
        "Attempts and scores only. Not ability(): it refreshes a stored projection, a write.",
        evidence_source="reading.comprehension",
    ),
    PlannedTool(
        "get_reading_mistakes",
        "gap",
        None,
        "No public read of which questions a learner answered wrong across attempts.",
        evidence_source="reading.comprehension",
    ),
    PlannedTool(
        "get_word_context_in_reading",
        "gap",
        None,
        "No service derives the sentence around a word from a content id; the client can send the "
        "sentence as selected_item.text.",
        evidence_source="reading.comprehension",
    ),
    # --- finding content to open (R29) -------------------------------------------
    PlannedTool(
        "find_content",
        "adapter",
        "writing_coach.listening_api:listening_library",
        "The learner's library pages, in the session's language: the listening library (curated and imported) and "
        "the published reading articles, filtered by level, topic and title words; each item carries its content_id.",
        composes=("writing_coach.persistence.reading_content_repository:ReadingContentRepository.list_published",),
    ),
    # --- listening ---------------------------------------------------------------
    PlannedTool(
        "get_current_listening_context",
        "adapter",
        "writing_coach.listening_catalog:catalog_lesson",
        "Curated lessons only. Not the lesson route: a meaning missing from the cache calls a translation "
        "provider and writes the cache.",
        composes=("writing_coach.listening_catalog:lesson_metadata",),
        evidence_source="listening.dictation",
    ),
    PlannedTool(
        "get_listening_attempt",
        "adapter",
        f"{_SPECIALIZED}.list_listening_progress_records",
        "Keyed by asset_id, which the contract's content_id must name. PostgreSQL only.",
        evidence_source="listening.dictation",
    ),
    PlannedTool(
        "get_listening_mistakes",
        "gap",
        None,
        "No server-side dictation comparison exists; it runs in the client.",
        evidence_source="listening.dictation",
    ),
)

PLANNED_TOOLS: Mapping[str, PlannedTool] = MappingProxyType({tool.name: tool for tool in _PLAN})
if len(PLANNED_TOOLS) != len(_PLAN):
    raise RuntimeError("the tool plan names a tool twice")


def gaps() -> tuple[PlannedTool, ...]:
    return tuple(tool for tool in _PLAN if tool.verdict == "gap")
