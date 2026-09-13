from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
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
