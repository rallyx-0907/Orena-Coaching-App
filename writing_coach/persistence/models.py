from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), default="", nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    picture: Mapped[str] = mapped_column(Text, default="", nullable=False)
    role: Mapped[str] = mapped_column(String(40), default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserLanguageProfile(Base):
    __tablename__ = "user_language_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", "language_code", name="uq_user_language_profile"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    language_code: Mapped[str] = mapped_column(String(20), nullable=False)
    goal: Mapped[str] = mapped_column(String(40), default="everyday", nullable=False)
    style: Mapped[str] = mapped_column(String(40), default="guided", nullable=False)
    pinyin: Mapped[str] = mapped_column(String(20), default="auto", nullable=False)
    native_language: Mapped[str] = mapped_column(String(20), default="vi", nullable=False)
    theme_preset: Mapped[str] = mapped_column(String(40), default="editorial", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Essay(Base):
    __tablename__ = "essays"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "language_code", "legacy_id", name="uq_essay_legacy_scope"
        ),
        Index("ix_essays_user_language_created", "user_id", "language_code", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    language_code: Mapped[str] = mapped_column(String(20), nullable=False)
    legacy_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_level: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    grammar: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    vocabulary: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    coherence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    task_achievement: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    naturalness: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    overall: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    level_estimate: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    evaluator: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    summary_vi: Mapped[str] = mapped_column(Text, default="", nullable=False)
    strengths: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    priorities: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    errors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    module_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    strength_evidence: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # D-072.1: the learner kept this review to read again. NULL is "not kept",
    # which is the truth for every row written before the column existed.
    review_kept_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class EssayRevision(Base):
    __tablename__ = "essay_revisions"
    __table_args__ = (
        UniqueConstraint("essay_id", name="uq_essay_revision_essay"),
        Index("ix_essay_revisions_series", "user_id", "language_code", "series_legacy_id", "revision_no"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    essay_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("essays.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    language_code: Mapped[str] = mapped_column(String(20), nullable=False)
    series_legacy_id: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parent_essay_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("essays.id", ondelete="SET NULL"), nullable=True
    )
    parent_legacy_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class WritingError(Base):
    __tablename__ = "writing_errors"
    __table_args__ = (UniqueConstraint("essay_id", "ordinal", name="uq_writing_error_ordinal"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    essay_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("essays.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(120), default="other", nullable=False)
    fragment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    suggestion: Mapped[str] = mapped_column(Text, default="", nullable=False)
    explanation_vi: Mapped[str] = mapped_column(Text, default="", nullable=False)
    mini_rule_vi: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class SavedWord(Base):
    __tablename__ = "saved_words"
    __table_args__ = (
        UniqueConstraint("user_id", "language_code", "normalized_word", name="uq_saved_word_scope"),
        Index("ix_saved_words_due", "user_id", "language_code", "next_review_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    language_code: Mapped[str] = mapped_column(String(20), nullable=False)
    word: Mapped[str] = mapped_column(String(180), nullable=False)
    normalized_word: Mapped[str] = mapped_column(String(180), nullable=False)
    phonetic: Mapped[str] = mapped_column(String(180), default="", nullable=False)
    part_of_speech: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    definition: Mapped[str] = mapped_column(Text, default="", nullable=False)
    translation_vi: Mapped[str] = mapped_column(Text, default="", nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_essay_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("essays.id", ondelete="SET NULL"), nullable=True
    )
    source_fragment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_kind: Mapped[str] = mapped_column(String(40), default="manual", nullable=False)
    focus_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    review_stage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_recalls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lapse_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GrammarProgress(Base):
    __tablename__ = "grammar_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "language_code", "lesson_id", name="uq_grammar_progress_scope"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    language_code: Mapped[str] = mapped_column(String(20), nullable=False)
    lesson_id: Mapped[str] = mapped_column(String(255), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReadingSession(Base):
    __tablename__ = "reading_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "language_code", "legacy_id", name="uq_reading_session_legacy_scope"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    language_code: Mapped[str] = mapped_column(String(20), nullable=False)
    legacy_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    target_level: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    topic: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    learner_goal: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    passage: Mapped[str] = mapped_column(Text, default="", nullable=False)
    questions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    recycled_words: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    generation_mode: Mapped[str] = mapped_column(String(40), default="practice", nullable=False)


class ReadingAttempt(Base):
    __tablename__ = "reading_attempts"
    __table_args__ = (UniqueConstraint("session_id", "legacy_id", name="uq_reading_attempt_legacy"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reading_sessions.id", ondelete="CASCADE"), nullable=False
    )
    legacy_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    answers: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ListeningProgress(Base):
    """Bounded, audio-free Active Listening progress for one segment."""

    __tablename__ = "listening_progress"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "language_code", "asset_id", "segment_id",
            name="uq_listening_progress_scope_segment",
        ),
        Index(
            "ix_listening_progress_user_language_asset",
            "user_id", "language_code", "asset_id",
        ),
        CheckConstraint("last_hint_level BETWEEN 0 AND 3", name="ck_listening_progress_hint_level"),
        CheckConstraint("last_used_hint = (last_hint_level > 0)", name="ck_listening_progress_hint_flag"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    language_code: Mapped[str] = mapped_column(String(20), nullable=False)
    asset_id: Mapped[str] = mapped_column(String(255), nullable=False)
    segment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    presentation: Mapped[str] = mapped_column(String(20), default="prompt", nullable=False)
    revealed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    checked_attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    best_accuracy_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_exact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_answer: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # The last checked attempt: whether a hint was used, and how far it went (0-3). A fact about the
    # attempt, like last_answer; no scoring rule is inferred from it (D-068, DC-5).
    last_used_hint: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    last_hint_level: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ShadowingProgress(Base):
    """Bounded, audio-free completed Shadowing rounds for one segment."""

    __tablename__ = "shadowing_progress"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "language_code", "asset_id", "segment_id",
            name="uq_shadowing_progress_scope_segment",
        ),
        Index(
            "ix_shadowing_progress_user_language_asset",
            "user_id", "language_code", "asset_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    language_code: Mapped[str] = mapped_column(String(20), nullable=False)
    asset_id: Mapped[str] = mapped_column(String(255), nullable=False)
    segment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    completed_rounds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SpeakingAttempt(Base):
    """Privacy-bounded evaluator evidence for one completed Speaking take.

    Raw audio is intentionally absent.  The JSON fields contain only the
    already-normalized evaluator evidence needed to explain this take later.
    """

    __tablename__ = "speaking_attempts"
    __table_args__ = (
        UniqueConstraint("user_id", "language_code", "take_id", name="uq_speaking_attempt_scope_take"),
        Index("ix_speaking_attempts_user_language_created", "user_id", "language_code", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    language_code: Mapped[str] = mapped_column(String(20), nullable=False)
    take_id: Mapped[str] = mapped_column(String(120), nullable=False)
    asset_id: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    segment_id: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    reference_text: Mapped[str] = mapped_column(Text, nullable=False)
    transcript_text: Mapped[str] = mapped_column(Text, nullable=False)
    dimensions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PlanRecord(Base):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    price_label: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PlanEntitlement(Base):
    __tablename__ = "plan_entitlements"
    __table_args__ = (UniqueConstraint("plan_id", "feature_key", name="uq_plan_entitlement"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    feature_key: Mapped[str] = mapped_column(String(160), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    monthly_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    provider: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    external_customer_id: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    external_subscription_id: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (Index("ix_usage_user_feature_time", "user_id", "feature", "occurred_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    feature: Mapped[str] = mapped_column(String(160), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    request_id: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(255), default="", nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_created", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    entity_id: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class VocabularyCollection(Base):
    """A shared, learner-facing vocabulary pack.

    Collections are content, not learner state.  A collection can be imported
    once and read by many learners; saved/review relationships remain in the
    existing learner vocabulary tables.
    """

    __tablename__ = "vocabulary_collections"
    __table_args__ = (
        Index("ix_vocabulary_collections_language_status", "language_code", "catalog_status"),
    )

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    language_code: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    framework: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    level: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    level_range: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    topic: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    catalog_status: Mapped[str] = mapped_column(String(30), default="pending_review", nullable=False)
    origin: Mapped[str] = mapped_column(String(40), default="imported", nullable=False)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class VocabularyEntry(Base):
    """A language-neutral lexical item shared across collection memberships."""

    __tablename__ = "vocabulary_entries"
    __table_args__ = (
        UniqueConstraint("identity_key", name="uq_vocabulary_entry_identity"),
        Index("ix_vocabulary_entries_language_term", "language_code", "normalized_term"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    language_code: Mapped[str] = mapped_column(String(20), nullable=False)
    term: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_term: Mapped[str] = mapped_column(String(500), nullable=False)
    identity_key: Mapped[str] = mapped_column(String(900), nullable=False)
    sense_key: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    pronunciations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    readings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    short_meanings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    detailed_definitions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    part_of_speech: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    examples: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    usage_notes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    orthography: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    level: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    framework: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    topic: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    content_origins: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class VocabularySourceImport(Base):
    """One source attempt, retained for auditability and batch reporting."""

    __tablename__ = "vocabulary_source_imports"
    __table_args__ = (
        Index("ix_vocabulary_source_imports_collection_created", "collection_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    collection_id: Mapped[str | None] = mapped_column(
        ForeignKey("vocabulary_collections.id", ondelete="SET NULL"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    source_format: Mapped[str] = mapped_column(String(20), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    mapping: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    imported_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warnings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    errors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    imported_by: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class VocabularyCollectionMembership(Base):
    """Many-to-many placement of shared entries inside curated collections."""

    __tablename__ = "vocabulary_collection_memberships"
    __table_args__ = (
        UniqueConstraint(
            "collection_id", "entry_id", name="uq_vocabulary_collection_membership"
        ),
        Index("ix_vocabulary_memberships_collection_position", "collection_id", "position"),
        Index("ix_vocabulary_memberships_entry", "entry_id"),
        Index("ix_vocabulary_memberships_source_import", "source_import_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    collection_id: Mapped[str] = mapped_column(
        ForeignKey("vocabulary_collections.id", ondelete="CASCADE"), nullable=False
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vocabulary_entries.id", ondelete="CASCADE"), nullable=False
    )
    source_import_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("vocabulary_source_imports.id", ondelete="SET NULL"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    membership_metadata: Mapped[dict] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )


# ---------------------------------------------------------------------------
# Reading Content Engine - shared, admin-curated article content.
#
# These six mirror `migrations/proposed/20260922_0010_reading_content_engine.py`
# and exist so the hermetic suite can create the same tables from metadata, the
# way the vocabulary catalog already does. Two rules when either side changes:
# the migration is the authority for the runtime, and every partial index is
# declared for *both* dialects - a `postgresql_where` alone silently becomes a
# full index on SQLite, which would let a test pass against a constraint the
# runtime does not have and, for the native-id key, forbid a second manual
# paste the runtime allows.
#
# Nothing here is learner-owned: no account column, no foreign key into
# `users`, no reading position or progress.
# ---------------------------------------------------------------------------


class ReadingSource(Base):
    """Where content comes from, with its rights answers and polling state."""

    __tablename__ = "reading_sources"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_reading_source_slug"),
        Index("ix_reading_sources_state", "state", "source_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    base_url: Mapped[str] = mapped_column(String(600), default="", nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="needs_review", nullable=False)
    languages: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    topic_hints: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    automation_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_republish: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_adapt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attribution_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    license_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    polling_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    polling_policy: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    polling_cursor: Mapped[str] = mapped_column(String(600), default="", nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    approved_by: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
class TextDiscussion(Base):
    """One learner's thread about one whole text (D-072.2).

    Keyed to the content identity the app routes on, not to a catalogue row:
    Orena owns no table for every kind of text. `turn_count` is the atomic
    reservation counter the turn endpoint takes its ordinals from, not a
    cached aggregate to read for display.
    """

    __tablename__ = "text_discussions"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "language_code", "source_kind", "source_id", name="uq_text_discussion_scope"
        ),
        CheckConstraint(
            "source_kind IN ('story','media','reading_session','book_chapter')",
            name="ck_text_discussion_source_kind",
        ),
        # One-directional: a non-session kind may never carry a session id, but
        # a session thread whose session was deleted (ON DELETE SET NULL) is a
        # legitimate state. The biconditional would make that deletion fail.
        CheckConstraint(
            "source_kind = 'reading_session' OR reading_session_id IS NULL",
            name="ck_text_discussion_session_kind",
        ),
        CheckConstraint(
            "turn_count >= 0 AND turn_count <= 200", name="ck_text_discussion_turn_cap"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    language_code: Mapped[str] = mapped_column(String(20), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    reading_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reading_sessions.id", ondelete="SET NULL"), nullable=True
    )
    turn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReadingSourceItem(Base):
    """The immutable original snapshot a candidate article is built from."""

    __tablename__ = "reading_source_items"
    __table_args__ = (
        Index(
            "uq_reading_source_items_native",
            "source_id",
            "source_native_id",
            unique=True,
            postgresql_where=text("source_native_id <> '' AND superseded_at IS NULL"),
            sqlite_where=text("source_native_id <> '' AND superseded_at IS NULL"),
        ),
        Index("uq_reading_source_items_hash", "source_id", "content_hash", unique=True),
        Index(
            "ix_reading_source_items_canonical",
            "canonical_url",
            postgresql_where=text("canonical_url <> ''"),
            sqlite_where=text("canonical_url <> ''"),
        ),
        Index("ix_reading_source_items_hash_any", "content_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reading_sources.id", ondelete="RESTRICT"), nullable=False
    )
    source_native_id: Mapped[str] = mapped_column(String(400), default="", nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    original_title: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    original_author: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    original_published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    original_language: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    original_content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    rights_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reading_source_items.id", ondelete="RESTRICT"), nullable=True
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReadingArticle(Base):
    """The learner-oriented processed version, and its review lifecycle."""

    __tablename__ = "reading_articles"
    __table_args__ = (
        UniqueConstraint("source_item_id", name="uq_reading_article_source_item"),
        Index(
            "ix_reading_articles_published",
            "language",
            "published_at",
            "id",
            postgresql_where=text("status = 'published'"),
            sqlite_where=text("status = 'published'"),
        ),
        Index(
            "ix_reading_articles_published_level",
            "language",
            "effective_level",
            "published_at",
            "id",
            postgresql_where=text("status = 'published'"),
            sqlite_where=text("status = 'published'"),
        ),
        Index(
            "ix_reading_articles_published_topic",
            "language",
            "topic",
            "published_at",
            "id",
            postgresql_where=text("status = 'published'"),
            sqlite_where=text("status = 'published'"),
        ),
        Index("ix_reading_articles_queue", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    source_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reading_source_items.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[str] = mapped_column(String(400), default="", nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    topic: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    subtopic: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    estimated_level: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    estimated_level_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reviewed_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    effective_level: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reading_time_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_adapted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    adaptation_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    analysis_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    rejection_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unpublished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReadingArticleTarget(Base):
    """One learning target: suggested by the machine, decided by an admin."""

    __tablename__ = "reading_article_targets"
    __table_args__ = (
        Index(
            "uq_reading_target_form",
            "article_id",
            "canonical_form",
            unique=True,
            postgresql_where=text("canonical_form <> ''"),
            sqlite_where=text("canonical_form <> ''"),
        ),
        Index("ix_reading_targets_article", "article_id", "rank"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reading_articles.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(String(300), nullable=False)
    canonical_form: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    context: Mapped[str] = mapped_column(Text, default="", nullable=False)
    meaning: Mapped[str] = mapped_column(Text, default="", nullable=False)
    estimated_level: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    machine_suggested: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    admin_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    admin_rejected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReadingReviewEvent(Base):
    """What an admin did to an article, as the Review Queue renders it."""

    __tablename__ = "reading_review_events"
    __table_args__ = (Index("ix_reading_review_events_article", "article_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reading_articles.id", ondelete="CASCADE"), nullable=False
    )
    actor: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    changes_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReadingIngestionJob(Base):
    """One durable unit of ingestion work, claimed by a worker."""

    __tablename__ = "reading_ingestion_jobs"
    __table_args__ = (
        Index(
            "uq_reading_job_request_hash",
            "request_hash",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
            sqlite_where=text("status IN ('queued', 'running')"),
        ),
        Index(
            "ix_reading_jobs_claim",
            "created_at",
            "id",
            postgresql_where=text("status = 'queued'"),
            sqlite_where=text("status = 'queued'"),
        ),
        Index(
            "ix_reading_jobs_stale",
            "heartbeat_at",
            postgresql_where=text("status = 'running'"),
            sqlite_where=text("status = 'running'"),
        ),
        Index("ix_reading_jobs_recent", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reading_sources.id", ondelete="RESTRICT"), nullable=False
    )
    input_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    input_asset_key: Mapped[str] = mapped_column(String(400), default="", nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    stage: Mapped[str] = mapped_column(String(30), default="queued", nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    last_error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    last_error_code: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    next_retry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claimed_by: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    result_source_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reading_source_items.id", ondelete="SET NULL"), nullable=True
    )
    result_article_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reading_articles.id", ondelete="SET NULL"), nullable=True
    )
    result_kind: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    submitted_by: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
class TextDiscussionTurn(Base):
    """One turn of that thread, ordered by `ordinal` and never by `created_at`,
    which ties when both turns of an exchange are written in one request.

    `request_id` is the client's idempotency key, carried by the learner turn
    only; a partial unique index over the non-empty values is the endpoint's
    dedup contract. Ordinals are not contiguous: a failed provider call or a
    raced duplicate leaves its reserved pair unused, by design.
    """

    __tablename__ = "text_discussion_turns"
    __table_args__ = (
        UniqueConstraint("discussion_id", "ordinal", name="uq_text_discussion_turn_ordinal"),
        CheckConstraint("role IN ('learner','assistant')", name="ck_text_discussion_turn_role"),
        CheckConstraint("length(body) <= 4000", name="ck_text_discussion_turn_body"),
        CheckConstraint("ordinal >= 1", name="ck_text_discussion_turn_ordinal_positive"),
        Index("ix_text_discussion_turns_order", "discussion_id", "ordinal"),
        Index(
            "ux_text_discussion_turns_request",
            "discussion_id",
            "request_id",
            unique=True,
            postgresql_where=text("request_id <> ''"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    discussion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("text_discussions.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str] = mapped_column(Text, default="", nullable=False)
    provider: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    model: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    request_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
