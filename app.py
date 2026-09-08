import json
import hashlib
import random
import os
import re
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from writing_coach.languages.chinese import stroke_order as chinese_stroke_order
from writing_coach.languages.runtime import (
    active_error_categories,
    active_levels,
    active_profile,
    active_grammar_language_code,
    active_grammar_by_id,
    active_grammar_course,
    active_grammar_knowledge_by_id,
    grammar_level_names,
    active_rubric_weights,
    active_score_to_level,
    active_system_prompt,
    is_chinese,
    progress_bands,
    task_guidance,
    task_system_prompt,
    task_user_prompt,
    topic_instruction,
    validate_target_level,
    writing_unit_count,
)
from writing_coach.writing_evaluation import (
    calculate_weighted_overall,
    contains_cjk,
    normalize_writing_evaluation,
)
from writing_coach.writing_evaluator_contract import (
    build_writing_evaluator_request,
    build_writing_evaluator_schema,
)
from writing_coach.writing_grammar_transfer import grammar_links_for_issues
from writing_coach.writing_analytics import parse_persisted_error_events
from auth_support import APP_ENV, AUTH_ENABLED, current_db_path, install_auth, require_admin, AUTH_DB_PATH, configure_auth_repository
from writing_coach.product.api import router as product_router
from writing_coach.media_api import (
    configure_media_fallback,
    configure_media_ingestion,
    configure_media_timing,
    configure_media_translation,
    router as media_learning_router,
)
from writing_coach.media_fallback import SupadataMediaFallbackService
from writing_coach.media_ingestion import MediaIngestionService
from writing_coach.media_providers.supadata import SupadataTranscriptClient
from writing_coach.media_recovery_policy import build_youtube_adapter
from writing_coach.media_providers.youtube_audio import YtDlpYouTubeAudioUrlResolver
from writing_coach.listening_api import preview_visible
from writing_coach.world_api import router as world_router
from writing_coach.media_timing import MediaTimingService
from writing_coach.media_translation import (
    GroqTranslationProvider,
    LocalHttpTranslationProvider,
    MediaTranslationService,
    resolve_translation_provider_id,
)
from writing_coach.speech_api import (
    configure_speech_asr,
    configure_speech_pronunciation,
    configure_speaking_attempt_repository,
    router as speech_router,
)
from writing_coach.media_interaction import contextual_router as contextual_dictionary_router
from writing_coach.listening_api import (
    configure_listening_progress,
    configure_listening_translation_cache,
    router as listening_progress_router,
)
from writing_coach.speech_asr import GroqSpeechAsrProvider
from writing_coach.speech_pronunciation import build_speech_pronunciation_provider
from writing_coach.core.errors import orena_http_error
from writing_coach.core.platform_api import router as platform_router
from writing_coach.core.language_registry import is_enabled
from writing_coach.ai.base import AICapabilityError, AIProviderError, AIProviderUnavailable
from writing_coach.ai.platform import active_ai_label, active_ai_status, admin_ai_operations, generate_structured, install_platform_ai, configure_platform_repository
from writing_coach.ai.control_plane import AIControlPlane
from writing_coach.product.service import configure_product_repository
from writing_coach.persistence.runtime import build_runtime
from writing_coach.persistence.learning_repository import (
    SQLiteLearningCacheRepository,
    SQLiteLearningRepository,
)
from writing_coach.persistence.specialized_repository import SQLiteSpecializedLearningRepository
from writing_coach.becoming_memory import (LearnerProfileIn, configure_becoming_memory, get_learner_profile, get_learning_memory, get_review_cue, put_learner_profile)
from writing_coach.becoming_practice import PracticeNextIn, build_practice_recommendation, personalize_generated_task
from writing_coach.becoming_outcomes import PracticeContextIn, configure_becoming_outcomes, get_practice_outcome, list_practice_outcomes
from writing_coach.becoming_library import LibraryVocabularyIn, VocabularyReviewIn, configure_becoming_library, delete_library_vocabulary, list_library_vocabulary, review_library_vocabulary, save_library_vocabulary
from writing_coach.becoming_linguistics import configure_becoming_linguistics, linguistic_annotations_for_essay
from writing_coach.becoming_reading import ReadingAnswerIn, ReadingGenerateIn, configure_becoming_reading, create_reading_session, get_reading_session, list_reading_sessions, submit_reading_answers
from writing_coach.cross_skill_transfer import select_cross_skill_cue
from writing_coach.product_activity_api import product_activity_response
from writing_coach.readiness_summary import build_readiness_summary
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler as fastapi_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("WRITING_DB", ROOT / "data" / "writing.db"))
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
REQUEST_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))
ALLOW_FALLBACK = os.getenv("ALLOW_FALLBACK", "false").lower() in {"1", "true", "yes", "on"}
APP_VERSION = os.getenv(
    "APP_VERSION",
    (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if (ROOT / "VERSION").exists()
    else "dev",
)
SCHEMA_VERSION = 11

app = FastAPI(title="Orena", version=APP_VERSION)


@app.exception_handler(RequestValidationError)
async def validation_error_response(request: Request, exc: RequestValidationError) -> Response:
    """Preserve FastAPI validation bodies while marking mutable dictionary errors."""
    response = await fastapi_validation_exception_handler(request, exc)
    if request.url.path.rstrip("/") == "/api/dictionary":
        response.headers["Cache-Control"] = "no-store"
    return response
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

BECOMING_ASSET_ROOT = (ROOT / "static" / "becoming").resolve()

@app.get("/becoming-assets/{asset_path:path}", include_in_schema=False)
def becoming_asset(asset_path: str):
    # Dedicated BECOMING asset route, isolated from the legacy /static mount.
    candidate = (BECOMING_ASSET_ROOT / asset_path).resolve()
    try:
        candidate.relative_to(BECOMING_ASSET_ROOT)
    except ValueError as exc:
        raise HTTPException(404, "Asset not found") from exc

    if not candidate.is_file():
        raise HTTPException(404, "Asset not found")

    return FileResponse(candidate, headers={"Cache-Control": "no-store, max-age=0"})


class EssayIn(BaseModel):
    prompt: str = Field(default="", max_length=5000)
    text: str = Field(min_length=10, max_length=20000)
    target_cefr: str = Field(default="B2", min_length=2, max_length=12)
    parent_essay_id: int | None = Field(default=None, ge=1)
    practice_context: PracticeContextIn | None = None
    learning_language: str | None = Field(default=None, min_length=2, max_length=8)


class TaskGenerateIn(BaseModel):
    task_type: str = Field(
        default="opinion",
        pattern=r"^(opinion|email|review|story|toeic|hsk)$",
    )
    topic: str = Field(default="random", min_length=1, max_length=120)
    target_cefr: str = Field(default="B2", min_length=2, max_length=12)
    word_target: int = Field(default=150, ge=20, le=500)

class ImproveIn(BaseModel):
    text: str = Field(min_length=10, max_length=20000)
    target_cefr: str = Field(default="B2", min_length=2, max_length=12)
    mode: str = Field(default="polish", pattern=r"^(correct|grammar|vocabulary|polish)$")


class TranslateIn(BaseModel):
    text: str = Field(min_length=1, max_length=800)


class SaveWordIn(BaseModel):
    word: str = Field(min_length=1, max_length=80)
    phonetic: str = Field(default="", max_length=120)
    part_of_speech: str = Field(default="", max_length=80)
    definition: str = Field(default="", max_length=1200)
    translation_vi: str = Field(default="", max_length=1200)

_persistence_runtime = build_runtime(
    auth_db=AUTH_DB_PATH,
    platform_db=Path(os.getenv("PLATFORM_DB", ROOT / "data" / "platform.db")),
    product_db=Path(os.getenv("PRODUCT_DB", ROOT / "data" / "product.db")),
    learning_path=lambda: current_db_path(DB_PATH),
    backend=os.getenv("PERSISTENCE_BACKEND", "postgresql"),
)
configure_auth_repository(_persistence_runtime.auth_repository)
configure_platform_repository(_persistence_runtime.platform_repository)
configure_product_repository(_persistence_runtime.product_repository)

# PostgreSQL is the application runtime. In auth-disabled local development the
# request scope still uses the stable user key "legacy"; seed that scope once so
# learner data can be written without depending on a historical SQLite import.
if _persistence_runtime.backend == "postgresql" and not AUTH_ENABLED:
    if _persistence_runtime.auth_repository.get_user("legacy") is None:
        _persistence_runtime.auth_repository.upsert_user(
            {
                "sub": "legacy",
                "email": "local@localhost.invalid",
                "name": "Local developer",
                "picture": "",
            },
            set(),
        )

_learning_repository = _persistence_runtime.learning_repository
_learning_cache = SQLiteLearningCacheRepository(lambda: SQLiteLearningRepository(lambda: current_db_path(DB_PATH).with_name("learning_cache.db")).connect())
_specialized_learning_repository = _persistence_runtime.specialized_learning_repository


def init_db() -> None:
    if _persistence_runtime.backend == "sqlite":
        _learning_repository.initialize(schema_version=SCHEMA_VERSION)
        _specialized_learning_repository.initialize()
    _learning_cache.initialize()



install_auth(app, init_db)
_speech_asr_provider = GroqSpeechAsrProvider.from_env()
_media_fallback_mode = os.getenv("MEDIA_TRANSCRIPT_FALLBACK", "none").strip().casefold()
if _media_fallback_mode not in {"none", "supadata"}:
    raise RuntimeError("MEDIA_TRANSCRIPT_FALLBACK must be 'none' or 'supadata'.")
_supadata_fallback_client = (
    SupadataTranscriptClient.from_env()
    if _media_fallback_mode == "supadata"
    else None
)
if _media_fallback_mode == "supadata" and _supadata_fallback_client is None:
    raise RuntimeError(
        "MEDIA_TRANSCRIPT_FALLBACK=supadata requires SUPADATA_API_KEY."
    )

app.include_router(platform_router)
app.include_router(product_router)
configure_media_ingestion(
    MediaIngestionService(
        # One recovery policy, shared with the bulk importer, so a caption-less
        # video means the same thing in My Media and in the catalog pipeline.
        adapters=(build_youtube_adapter(),),
        source_language_supported=is_enabled,
    )
)
# Which engine translates shared media, resolved once here and never re-decided
# per request. Groq is the default because it answers in about a second where
# the local Marian service needed thirty-seven; the local service is kept as the
# backup for a deployment with no external dependency. Switching between them is
# an operator decision -- there is no automatic failover when one fails
# (ARCHITECTURE_INVARIANTS.md, AI Platform).
_GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
try:
    _media_translation_provider_id = resolve_translation_provider_id(
        os.getenv("MEDIA_TRANSLATION_PROVIDER", ""), groq_key=_GROQ_API_KEY
    )
except ValueError as exc:
    raise RuntimeError(str(exc)) from exc

_media_translation_provider = (
    GroqTranslationProvider(
        _GROQ_API_KEY,
        model=os.getenv("GROQ_TRANSLATION_MODEL", "openai/gpt-oss-120b"),
        base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
    )
    if _media_translation_provider_id == "groq"
    else LocalHttpTranslationProvider(
        os.getenv("LOCAL_TRANSLATION_URL", "http://local-translator:8090")
    )
)
configure_media_translation(MediaTranslationService(_media_translation_provider))
configure_media_timing(
    MediaTimingService(
        YtDlpYouTubeAudioUrlResolver(),
        _speech_asr_provider,
    )
    if _speech_asr_provider is not None
    else None
)
configure_media_fallback(
    SupadataMediaFallbackService(_supadata_fallback_client)
    if _supadata_fallback_client is not None
    else None
)
app.include_router(media_learning_router)
app.include_router(contextual_dictionary_router)
configure_speech_asr(_speech_asr_provider)
configure_speech_pronunciation(build_speech_pronunciation_provider())
configure_speaking_attempt_repository(
    _specialized_learning_repository
    if _persistence_runtime.backend == "postgresql"
    else None
)
app.include_router(speech_router)
configure_listening_progress(
    _specialized_learning_repository
    if _persistence_runtime.backend == "postgresql"
    else None
)
# Generated meanings persist in the local cache DB, so the second learner in a
# given support language costs no provider quota.
configure_listening_translation_cache(_learning_cache)
app.include_router(listening_progress_router)
# Worlds are the discovery layer above lessons; they read the same curated
# catalog and the same preview-visibility rule, so nothing new is authorised.
app.include_router(world_router)
install_platform_ai(app, require_admin)
configure_becoming_memory(_specialized_learning_repository)
configure_becoming_outcomes(_specialized_learning_repository)
configure_becoming_library(_specialized_learning_repository)
configure_becoming_reading(_specialized_learning_repository, generate_structured)
configure_becoming_linguistics(_specialized_learning_repository)

def weighted_overall(result: dict[str, Any]) -> float:
    return calculate_weighted_overall(result, active_rubric_weights())


def app_cefr(score: float) -> str:
    return active_score_to_level(score)

def extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for pos, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[pos:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value

    raise json.JSONDecodeError(
        "No complete JSON object found in Ollama response",
        text,
        0,
    )

def validate_result(raw: dict[str, Any]) -> dict[str, Any]:
    return normalize_writing_evaluation(
        raw,
        rubric_weights=active_rubric_weights(),
        allowed_levels=active_levels(),
        score_to_level=active_score_to_level,
        error_categories=active_error_categories(),
        allow_cjk=is_chinese(),
        learner_text=str(raw.get("__learner_text", "")),
    )

def evaluate_with_ai(payload: EssayIn) -> dict[str, Any]:
    target_level = validate_target_level(payload.target_cefr)
    free_writing_context = (
        "(Free Chinese writing — evaluate clarity, language control and naturalness.)"
        if is_chinese()
        else "(Free writing — evaluate clarity, language control and naturalness.)"
    )
    user_prompt = build_writing_evaluator_request(
        language_name=active_profile().name,
        target_level=target_level,
        task_prompt=payload.prompt,
        learner_text=payload.text,
        free_writing_context=free_writing_context,
    )
    evaluation_schema = build_writing_evaluator_schema(
        rubric_weights=active_rubric_weights(),
        allowed_levels=active_levels(),
        score_to_level=active_score_to_level,
        error_categories=active_error_categories(),
    )
    ai = generate_structured(
        messages=[
            {"role": "system", "content": active_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        schema=evaluation_schema,
        max_output_tokens=2200,
        temperature=0.0,
        seed=42,
        capability_key="writing_evaluator",
    )
    raw = dict(ai.data)
    raw["__learner_text"] = payload.text
    result = validate_result(raw)
    result["_runtime"] = ai.runtime
    result["_ai_provider"] = ai.provider
    result["_ai_model"] = ai.model
    return result

def heuristic_fallback(payload: EssayIn) -> dict[str, Any]:
    text = payload.text.strip()
    words = re.findall(r"\b[\w'-]+\b", text)
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    wc = max(1, len(words))
    unique_ratio = len({w.lower() for w in words}) / wc
    scores = {
        "grammar": 54.0,
        "vocabulary": round(min(76.0, 48 + unique_ratio * 34), 1),
        "coherence": 56.0 if len(sentences) >= 3 else 48.0,
        "task_achievement": 60.0 if payload.prompt else 58.0,
        "naturalness": 52.0,
    }
    overall = weighted_overall(scores)
    errors: list[dict[str, Any]] = []
    if not is_chinese():
        for pattern, suggestion, explanation, rule in (
            (r"\bI has\b", "I have", "The verb should agree with subject I.", "I goes with have."),
            (r"\bhe have\b", "he has", "The verb should agree with subject he.", "He goes with has."),
            (r"\bShe have\b", "She has", "The verb should agree with subject she.", "She goes with has."),
        ):
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                errors.append({
                    "category": "agreement", "fragment": match.group(0),
                    "suggestion": suggestion, "explanation_vi": explanation,
                    "mini_rule_vi": rule, "confidence": 0.99,
                })
    raw = {
        **scores,
        "cefr_estimate": app_cefr(overall),
        "summary_vi": "Đánh giá cục bộ tạm thời vì AI Coach chưa tạo được đánh giá đầy đủ có thể sử dụng. Phần điểm và bằng chứng này chỉ để kiểm tra luồng.",
        "strengths_vi": ["Bài viết có đủ nội dung để lưu vào hồ sơ tiến bộ."],
        "strength_evidence": [],
        "priorities_vi": ["Dùng phần bằng chứng này như bản xem thử; hãy chạy lại khi AI Coach tạo được đánh giá đầy đủ."],
        "errors": errors,
    }
    return validate_result({**raw, "__learner_text": text})


def evaluate(payload: EssayIn) -> tuple[dict[str, Any], str]:
    try:
        result = evaluate_with_ai(payload)
        evaluator = f"{result.pop('_ai_provider', 'ai')}:{result.pop('_ai_model', 'model')}"
        return result, evaluator
    except AIProviderUnavailable as exc:
        if ALLOW_FALLBACK:
            return heuristic_fallback(payload), "fallback-demo"
        raise orena_http_error(
            503,
            "evaluation_unavailable",
            "AI evaluation is temporarily unavailable. Please try again.",
        ) from exc
    except AIProviderError as exc:
        if ALLOW_FALLBACK:
            return heuristic_fallback(payload), "fallback-demo"
        raise orena_http_error(
            502,
            "evaluation_provider_failure",
            "AI evaluation could not produce a usable result.",
        ) from exc

def row_to_dict(row: dict[str, Any], detail: bool = False) -> dict[str, Any]:
    d = dict(row)
    if detail:
        d["strengths_vi"] = json.loads(d.pop("strengths_json"))
        d["strength_evidence"] = json.loads(d.pop("strength_evidence_json", "[]") or "[]")
        d["priorities_vi"] = json.loads(d.pop("priorities_json"))
        d["errors"] = json.loads(d.pop("errors_json"))
        module_data = json.loads(d.pop("module_data_json", "{}") or "{}")
        d["module_data"] = module_data if isinstance(module_data, dict) else {}
        d["practice_context"] = (
            d["module_data"].get("practice")
            if isinstance(d["module_data"].get("practice"), dict)
            else None
        )
        d["grammar_links"] = (
            d["module_data"].get("grammar_links")
            if isinstance(d["module_data"].get("grammar_links"), list)
            else []
        )
        d["schema_version"] = "writing-evaluation-v2"
        d["text_hash"] = hashlib.sha256(str(d.get("text", "")).encode("utf-8")).hexdigest()
        d["summary"] = {
            "headline": d["strengths_vi"][0] if d["strengths_vi"] else "",
            "interpretation": d.get("summary_vi", ""),
        }
        dimension_keys = tuple(active_rubric_weights())
        d["dimensions"] = {key: d[key] for key in dimension_keys if key in d}
        d["issues"] = [
            {
                "id": item.get("id", f"issue-{index + 1}"),
                "category": item.get("category", "other"),
                "priority": "high" if index == 0 else "medium",
                "span": item.get("span", {"start": 0, "end": 0}),
                "quote": item.get("quote", item.get("fragment", "")),
                "why": item.get("why", item.get("explanation_vi", "")),
                "how": item.get("how", item.get("mini_rule_vi", "")),
                "suggestion": item.get("suggestion", ""),
                "examples": item.get("examples", []),
            }
            for index, item in enumerate(d["errors"])
            if isinstance(item, dict)
        ]
        d["strengths"] = [
            {
                "id": item.get("id", f"strength-{index + 1}"),
                "category": item.get("category", "strength"),
                "span": item.get("span", {"start": 0, "end": 0}),
                "quote": item.get("quote", item.get("fragment", "")),
                "why": item.get("explanation_vi", ""),
            }
            for index, item in enumerate(d["strength_evidence"])
            if isinstance(item, dict)
        ]
        d["next_actions"] = d["priorities_vi"]
    else:
        d.pop("strengths_json", None)
        d.pop("priorities_json", None)
        d.pop("errors_json", None)
        d.pop("text", None)
        d.pop("summary_vi", None)
        d.pop("module_data_json", None)
        d.pop("strength_evidence_json", None)
    return d


def _issue_key(item: dict[str, Any]) -> tuple[str, str]:
    return (str(item.get("category", "other")), str(item.get("fragment", item.get("quote", ""))))


def revision_delta(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    if not previous:
        return {}
    out: dict[str, Any] = {}
    for key in [*active_rubric_weights().keys(), "overall"]:
        out[key] = round(float(current[key]) - float(previous[key]), 1)
    current_items = {
        _issue_key(item): item
        for item in current.get("errors", [])
        if isinstance(item, dict)
    }
    previous_items = {
        _issue_key(item): item
        for item in previous.get("errors", [])
        if isinstance(item, dict)
    }
    current_keys = set(current_items)
    previous_keys = set(previous_items)
    changed: list[dict[str, Any]] = []
    for category in sorted({key[0] for key in current_keys} & {key[0] for key in previous_keys}):
        old = next((key for key in previous_keys if key[0] == category), None)
        new = next((key for key in current_keys if key[0] == category), None)
        if old and new and old != new:
            changed.append({"before": previous_items[old], "after": current_items[new]})
            previous_keys.discard(old)
            current_keys.discard(new)
    out["issues"] = {
        "removed": [previous_items[key] for key in sorted(previous_keys - current_keys)],
        "persistent": [current_items[key] for key in sorted(current_keys & previous_keys)],
        "new": [current_items[key] for key in sorted(current_keys - previous_keys)],
        "changed": changed,
    }
    return out


def error_memory(
    rows: list[dict[str, Any]],
    error_categories: tuple[str, ...],
) -> list[dict[str, Any]]:
    if not rows:
        return []
    ordered = sorted(rows, key=lambda r: int(r["id"]))
    midpoint = max(1, len(ordered) // 2)
    older_ids = {int(r["id"]) for r in ordered[:midpoint]}
    newer_ids = {int(r["id"]) for r in ordered[midpoint:]}
    by_cat: dict[str, dict[str, Any]] = {}
    now = datetime.now().astimezone()
    weekly_labels = []
    for offset in range(5, -1, -1):
        d = (now - timedelta(weeks=offset)).date()
        monday = d - timedelta(days=d.weekday())
        weekly_labels.append(monday.isoformat())

    for r in ordered:
        rid = int(r["id"])
        created = datetime.fromisoformat(r["created_at"]).astimezone()
        monday = (created.date() - timedelta(days=created.date().weekday())).isoformat()
        for err in parse_persisted_error_events(
            r["errors_json"], error_categories=error_categories
        ):
            cat = err["category"]
            item = by_cat.setdefault(
                cat,
                {
                    "category": cat,
                    "total": 0,
                    "older": 0,
                    "newer": 0,
                    "first_seen": r["created_at"][:10],
                    "last_seen": r["created_at"][:10],
                    "weeks": {label: 0 for label in weekly_labels},
                },
            )
            item["total"] += 1
            item["last_seen"] = r["created_at"][:10]
            if rid in older_ids:
                item["older"] += 1
            if rid in newer_ids:
                item["newer"] += 1
            if monday in item["weeks"]:
                item["weeks"][monday] += 1

    output = []
    for item in by_cat.values():
        if item["total"] <= 1 and item["newer"] == 0:
            status = "historical"
        elif item["newer"] < item["older"]:
            status = "improving"
        elif item["older"] == 0 and item["newer"] > 0:
            status = "new"
        elif item["total"] >= 3:
            status = "recurring"
        else:
            status = "watch"
        item["status"] = status
        item["weekly"] = [{"week": k, "count": v} for k, v in item.pop("weeks").items()]
        output.append(item)
    return sorted(output, key=lambda x: (x["status"] == "improving", -x["total"]))


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def home(request: Request = None) -> HTMLResponse:  # type: ignore[assignment]
    # The shell carries the list of stylesheets and modules the app loads, so a
    # cached copy of it keeps loading yesterday's asset list - a stylesheet
    # added since is simply never requested, and the screen renders unstyled.
    # Every asset already answers `no-store`; the document that names them has
    # to as well.
    shell = (ROOT / "templates" / "becoming" / "index.html").read_text(encoding="utf-8")
    # The marker is scoped to the people who can actually see preview content,
    # not to the deployment. One runtime serves normal learners and admin
    # dogfooding at the same time, so a deployment-wide badge would tell every
    # learner they are using a preview when, for them, they are not: they see
    # the ordinary product. Server-rendered against the same admin check that
    # gates the content, so a client cannot summon it and the pinned session
    # contract is untouched.
    if preview_visible(request):
        shell = shell.replace(
            "</body>",
            '<div class="orena-preview-badge" role="status" aria-label="Preview deployment">'
            "Preview</div></body>",
            1,
        )
    return HTMLResponse(shell, headers={"Cache-Control": "no-store, max-age=0"})




@app.get("/becoming", response_class=HTMLResponse)
@app.get("/becoming/", response_class=HTMLResponse)
def becoming_preview() -> RedirectResponse:
    return RedirectResponse("/", status_code=302)
@app.get("/static/style.css")
def style() -> HTMLResponse:
    return HTMLResponse((ROOT / "static" / "style.css").read_text(encoding="utf-8"), media_type="text/css")


@app.get("/static/account.js")
def account_script() -> HTMLResponse:
    return HTMLResponse(
        (ROOT / "static" / "account.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


def model_family(model_name: str) -> str:
    name = (model_name or "").casefold()
    if "qwen" in name:
        return "qwen"
    if "llama" in name:
        return "llama"
    if "mistral" in name:
        return "mistral"
    if "gemma" in name:
        return "gemma"
    if "phi" in name:
        return "phi"
    return "generic"


def mascot_for_model(model_name: str) -> dict[str, str]:
    family = model_family(model_name)
    mascots = {
        "qwen": {
            "emoji": "🦉",
            "name": "Qwen Owl",
            "subtitle": "Calm reader and detail hunter",
            "mood": "Focused",
        },
        "llama": {
            "emoji": "🦙",
            "name": "Llama Scout",
            "subtitle": "Patient guide for long writing sessions",
            "mood": "Steady",
        },
        "mistral": {
            "emoji": "🌬️",
            "name": "Mistral Breeze",
            "subtitle": "Fast, light and idea-friendly",
            "mood": "Swift",
        },
        "gemma": {
            "emoji": "💎",
            "name": "Gemma Spark",
            "subtitle": "Compact helper with sharp feedback",
            "mood": "Bright",
        },
        "phi": {
            "emoji": "🧠",
            "name": "Phi Fox",
            "subtitle": "Small but clever problem-solver",
            "mood": "Clever",
        },
        "generic": {
            "emoji": "🤖",
            "name": "Coach Bot",
            "subtitle": "Your local writing companion",
            "mood": "Ready",
        },
    }
    return mascots[family]

@app.get("/api/health")
def health() -> dict[str, Any]:
    ai = active_ai_status()
    return {
        "ok": True,
        "platform_admin": True,
        "version": APP_VERSION,
        "schema_version": SCHEMA_VERSION,
        "ai_ready": ai["ready"],
        "auth_enabled": AUTH_ENABLED,
        "auth_provider": "google" if AUTH_ENABLED else "local",
    }


@app.get("/api/readiness")
def readiness() -> dict[str, Any]:
    """Non-sensitive configuration readiness for local and public operations."""
    return {
        "ready": True,
        "environment": APP_ENV,
        "auth_enabled": AUTH_ENABLED,
    }

TASK_TYPE_GUIDANCE = {
    "opinion": "opinion",
    "email": "email",
    "review": "review",
    "story": "story",
    "toeic": "toeic",
    "hsk": "hsk",
}

TASK_TOPICS = [
    "daily life", "work", "technology", "education", "travel",
    "environment", "culture and media", "shopping and services",
    "communication", "community",
]


def normalize_task_piece(value: Any, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def fallback_practice_task(payload: TaskGenerateIn) -> dict[str, Any]:
    topic = payload.topic.strip()
    if topic.casefold() == "random":
        topic = random.choice(TASK_TOPICS)
    task_type = payload.task_type

    if is_chinese():
        zh_topic = {
            "daily life": "日常生活",
            "work": "工作",
            "technology": "科技",
            "education": "教育",
            "travel": "旅行",
            "environment": "环境",
            "culture and media": "文化与媒体",
            "shopping and services": "购物与服务",
            "communication": "沟通",
            "community": "社区",
        }.get(topic, topic)
        templates = {
            "opinion": (
                f"关于{zh_topic}的观点",
                f"请围绕“{zh_topic}”写一篇短文。清楚表达你的观点，给出至少两个理由，并加入一个具体例子。",
                ["表达明确观点", "给出至少两个理由", "加入一个具体例子"],
            ),
            "email": (
                f"关于{zh_topic}的消息",
                f"请写一封简短中文邮件或消息，说明一个与“{zh_topic}”有关的情况、你的需求，以及下一步建议。",
                ["说明情况", "表达需求", "提出下一步建议", "使用合适的开头和结尾"],
            ),
            "review": (
                f"描述{zh_topic}",
                f"请描述一次与“{zh_topic}”有关的经历、人物、地点或事物。写出主要特点，并说明你的感受或评价。",
                ["描述主要信息", "加入具体细节", "表达感受或评价"],
            ),
            "story": (
                f"一个关于{zh_topic}的小故事",
                f"请写一个与“{zh_topic}”有关的短故事。先交代情况，再写发生的变化，最后给出清楚的结尾。",
                ["交代情境", "写出变化或问题", "说明后续发展", "有明确结尾"],
            ),
            "hsk": (
                "HSK 风格写作练习",
                f"请围绕“{zh_topic}”完成一项适合 {validate_target_level(payload.target_cefr)} 的中文写作练习。重点练习句子组织、词序和自然表达。这是练习题，不是官方真题。",
                ["使用完整中文句子", "注意词序和标点", "尽量使用目标水平的词汇和语法"],
            ),
        }
        title, instruction, checklist = templates.get(task_type, templates["opinion"])
    else:
        templates = {
            "opinion": (
                f"An opinion about {topic}",
                f"Some people believe that changes related to {topic} make everyday life better, while others disagree. "
                "Write an opinion response. State your position clearly, give at least two reasons, and support one reason with a specific example.",
                ["State a clear opinion", "Give at least two reasons", "Include one specific example"],
            ),
            "email": (
                f"An email about {topic}",
                f"You need to write an email about a recent situation involving {topic}. Explain what happened, describe what you need from the recipient, "
                "and suggest one practical next step. Use an appropriate opening and closing.",
                ["Explain the situation", "Make your request clear", "Suggest a next step", "Use an appropriate email tone"],
            ),
            "review": (
                f"A review related to {topic}",
                f"Write a review of a recent experience related to {topic}. Describe what you experienced, explain what you liked and disliked, "
                "and say whether you would recommend it to other people.",
                ["Describe the experience", "Give both a positive and a negative point", "Finish with a recommendation"],
            ),
            "story": (
                f"A short story about {topic}",
                f"Write a short story connected to {topic}. Begin with a situation where an ordinary plan suddenly changes. "
                "Show what happened next and finish with a clear ending.",
                ["Set the scene", "Describe a change or problem", "Show what happens next", "Give the story a clear ending"],
            ),
            "toeic": (
                f"A practical TOEIC-style task about {topic}",
                f"Your workplace or community is considering a change related to {topic}. Write a response explaining whether you support the change. "
                "Give two reasons and one practical example or consequence.",
                ["Give a clear position", "Provide two reasons", "Add a practical example or consequence"],
            ),
        }
        title, instruction, checklist = templates.get(task_type, templates["opinion"])

    return {
        "title": title,
        "instruction": instruction,
        "checklist": checklist,
        "word_target": payload.word_target,
        "task_type": task_type,
        "topic": topic,
        "source": "built-in",
    }


def generate_practice_task(payload: TaskGenerateIn) -> dict[str, Any]:
    requested_topic = payload.topic.strip()
    guidance = task_guidance(payload.task_type)
    topic_text = topic_instruction(requested_topic)
    target_level = validate_target_level(payload.target_cefr)

    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "instruction": {"type": "string"},
            "checklist": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 5,
            },
            "topic": {"type": "string"},
        },
        "required": ["title", "instruction", "checklist", "topic"],
    }

    try:
        ai = generate_structured(
            messages=[
                {"role": "system", "content": task_system_prompt()},
                {
                    "role": "user",
                    "content": task_user_prompt(
                        target_level,
                        guidance,
                        topic_text,
                        payload.word_target,
                    ),
                },
            ],
            schema=schema,
            max_output_tokens=500,
            temperature=0.75,
            capability_key="writing_task_generator",
        )
        raw = ai.data
        title = normalize_task_piece(raw.get("title"), 140)
        instruction = normalize_task_piece(raw.get("instruction"), 1600)
        topic = normalize_task_piece(raw.get("topic"), 120)
        checklist = [
            normalize_task_piece(item, 240)
            for item in raw.get("checklist", [])
            if normalize_task_piece(item, 240)
        ][:5]

        if not title or not instruction or len(checklist) < 2:
            raise ValueError("Task generator returned incomplete structured output")

        return {
            "title": title,
            "instruction": instruction,
            "checklist": checklist,
            "word_target": payload.word_target,
            "task_type": payload.task_type,
            "topic": topic or requested_topic,
            "source": ai.label,
        }
    except AICapabilityError:
        raise
    except Exception:
        return fallback_practice_task(payload)


def task_as_prompt(task: dict[str, Any], target_cefr: str) -> str:
    checklist = "\n".join(f"- {item}" for item in task["checklist"])
    target_level = validate_target_level(target_cefr)
    if is_chinese():
        return (
            f"任务: {task['title']}\n\n"
            f"{task['instruction']}\n\n"
            f"需要包含:\n{checklist}\n\n"
            f"目标水平: {target_level}\n"
            f"建议长度: 大约 {task['word_target']} 个汉字/书写单位"
        )
    return (
        f"TASK: {task['title']}\n\n"
        f"{task['instruction']}\n\n"
        f"WHAT TO INCLUDE:\n{checklist}\n\n"
        f"TARGET LEVEL: {target_level}\n"
        f"TARGET LENGTH: about {task['word_target']} words"
    )

@app.post("/api/tasks/generate")
def api_generate_task(payload: TaskGenerateIn) -> dict[str, Any]:
    task = generate_practice_task(payload)
    return {
        **task,
        "prompt": task_as_prompt(task, payload.target_cefr),
    }

IMPROVE_MODE_INSTRUCTIONS = {
    "correct": "Correct grammar, spelling and punctuation with the minimum necessary changes. Preserve the learner's voice.",
    "grammar": "First correct errors, then suggest a stronger version using more varied but natural grammar appropriate to the target CEFR level. Do not make the writing artificially complex.",
    "vocabulary": "First correct errors, then improve word choice, collocations and precision. Avoid rare words that a learner would not realistically use.",
    "polish": "Correct errors and produce a stronger version with both more natural grammar and better vocabulary while preserving the original meaning and tone.",
}


def ai_json(capability_key: str, messages: list[dict[str, str]], schema: dict[str, Any], num_predict: int = 1200, temperature: float = 0.1) -> dict[str, Any]:
    return generate_structured(
        messages=messages,
        schema=schema,
        max_output_tokens=num_predict,
        temperature=temperature,
        capability_key=capability_key,
    ).data

def improve_with_ai(payload: ImproveIn) -> dict[str, Any]:
    schema = {
        "type": "object",
        "properties": {
            "corrected_text": {"type": "string"},
            "upgraded_text": {"type": "string"},
            "summary_vi": {"type": "string"},
            "grammar_upgrades": {
                "type": "array",
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "properties": {
                        "original": {"type": "string"},
                        "improved": {"type": "string"},
                        "pattern": {"type": "string"},
                        "reason_vi": {"type": "string"},
                    },
                    "required": ["original", "improved", "pattern", "reason_vi"],
                },
            },
            "vocabulary_upgrades": {
                "type": "array",
                "maxItems": 10,
                "items": {
                    "type": "object",
                    "properties": {
                        "original": {"type": "string"},
                        "improved": {"type": "string"},
                        "example": {"type": "string"},
                        "note_vi": {"type": "string"},
                    },
                    "required": ["original", "improved", "example", "note_vi"],
                },
            },
        },
        "required": [
            "corrected_text", "upgraded_text", "summary_vi",
            "grammar_upgrades", "vocabulary_upgrades",
        ],
    }

    if is_chinese():
        instructions = {
            "correct": "Chỉ sửa các lỗi chữ, từ, trật tự từ, trợ từ, ngữ pháp và dấu câu cần thiết; giữ nguyên ý và giọng của người học.",
            "grammar": "Sửa lỗi rồi nâng cấp cấu trúc câu tiếng Trung một cách tự nhiên, phù hợp mức HSK mục tiêu; không làm câu phức tạp giả tạo.",
            "vocabulary": "Sửa lỗi rồi cải thiện chọn từ, kết hợp từ và độ tự nhiên; ưu tiên từ thực tế phù hợp mức HSK.",
            "polish": "Sửa lỗi và tạo một phiên bản tiếng Trung tự nhiên hơn về cả ngữ pháp lẫn từ vựng nhưng giữ nguyên ý.",
        }
        system = (
            "You are a Chinese writing improvement coach for a Vietnamese learner. "
            "Preserve the learner's intended meaning and do not invent facts. "
            "Corrected and upgraded writing must be in natural Simplified Chinese unless the learner consistently uses Traditional Chinese. "
            "Explanations must be primarily in Vietnamese; short Chinese examples are allowed when useful."
        )
        user = (
            f"TARGET HSK LEARNING BAND: {validate_target_level(payload.target_cefr)}\n"
            f"MODE: {payload.mode}\n"
            f"INSTRUCTION: {instructions[payload.mode]}\n\n"
            f"LEARNER TEXT:\n{payload.text}\n\n"
            "Return a corrected version and a realistic upgraded version. "
            "List only reusable grammar and vocabulary improvements."
        )
    else:
        system = (
            "You are an English writing improvement coach. Preserve the learner's intended meaning. "
            "Never invent facts. Never make the writing unnecessarily formal. "
            "Vietnamese explanations must use the Latin alphabet and contain no CJK characters."
        )
        user = (
            f"TARGET CEFR: {validate_target_level(payload.target_cefr)}\n"
            f"MODE: {payload.mode}\n"
            f"INSTRUCTION: {IMPROVE_MODE_INSTRUCTIONS[payload.mode]}\n\n"
            f"LEARNER TEXT:\n{payload.text}\n\n"
            "Return a corrected version and a realistic upgraded version. "
            "List only useful reusable grammar and vocabulary improvements."
        )

    result = ai_json(
        "writing_improver",
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        schema,
        num_predict=1800,
        temperature=0.1,
    )
    if not is_chinese() and contains_cjk(str(result.get("summary_vi", ""))):
        result["summary_vi"] = ""
    result["mode"] = payload.mode
    result["target_cefr"] = validate_target_level(payload.target_cefr)
    return result

def normalise_lookup_word(word: str) -> str:
    word = re.sub(r"\s+", " ", word.strip())
    if is_chinese():
        word = re.sub(r"^[^\u3400-\u4DBF\u4E00-\u9FFF]+|[^\u3400-\u4DBF\u4E00-\u9FFF]+$", "", word)
        if not word or len(word) > 20:
            raise HTTPException(400, "Hãy chọn tối đa 20 chữ Hán.")
        return word

    word = re.sub(r"^[^\w'-]+|[^\w'-]+$", "", word, flags=re.UNICODE)
    if not word or len(word) > 80:
        raise HTTPException(400, "Invalid word or phrase")
    if len(word.split()) > 4:
        raise HTTPException(400, "Select up to four words")
    return word


def cambridge_url_for(word: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", word.casefold()).strip("-")
    return f"https://dictionary.cambridge.org/dictionary/english/{quote(slug)}"


def dictionary_ai_fallback(word: str) -> dict[str, Any]:
    schema = {
        "type": "object",
        "properties": {
            "word": {"type": "string"},
            "phonetic": {"type": "string"},
            "definitions": {
                "type": "array",
                "minItems": 1,
                "maxItems": 4,
                "items": {
                    "type": "object",
                    "properties": {
                        "part_of_speech": {"type": "string"},
                        "definition": {"type": "string"},
                        "example": {"type": "string"},
                        "synonyms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 5,
                        },
                    },
                    "required": ["part_of_speech", "definition", "example", "synonyms"],
                },
            },
        },
        "required": ["word", "phonetic", "definitions"],
    }
    result = ai_json(
        "learner_dictionary",
        [
            {
                "role": "system",
                "content": (
                    "You are a compact English learner dictionary. Definitions must be short, clear English. "
                    "Examples must be original and natural. Do not claim an exact IPA if uncertain; use an empty "
                    "phonetic string instead. "
                    "When the entry is a multi-word lexical unit rather than a single word, name the unit in "
                    "part_of_speech using exactly one of: idiom, proverb, phrasal verb, collocation, phrase. Use the "
                    "ordinary word class (noun, verb, adjective, adverb) for single words. Never guess a "
                    "category to make an entry look richer."
                ),
            },
            {"role": "user", "content": f"Define this English word or short phrase: {word}"},
        ],
        schema,
        num_predict=650,
        temperature=0.0,
    )
    result["source"] = active_ai_label("learner_dictionary")
    result["audio"] = ""
    result["cambridge_url"] = cambridge_url_for(word)
    return result


def chinese_dictionary_ai(word: str) -> dict[str, Any]:
    schema = {
        "type": "object",
        "properties": {
            "word": {"type": "string"},
            "traditional": {"type": "string"},
            "phonetic": {"type": "string"},
            "part_of_speech": {"type": "string"},
            "translation_vi": {"type": "string"},
            "usage_note_vi": {"type": "string"},
            "definitions": {
                "type": "array",
                "minItems": 1,
                "maxItems": 4,
                "items": {
                    "type": "object",
                    "properties": {
                        "part_of_speech": {"type": "string"},
                        "definition": {"type": "string"},
                        "example": {"type": "string"},
                        "example_pinyin": {"type": "string"},
                        "example_vi": {"type": "string"},
                        "synonyms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 5,
                        },
                    },
                    "required": [
                        "part_of_speech", "definition", "example",
                        "example_pinyin", "example_vi", "synonyms",
                    ],
                },
            },
            "characters": {
                "type": "array",
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "properties": {
                        "hanzi": {"type": "string"},
                        "pinyin": {"type": "string"},
                        "meaning_vi": {"type": "string"},
                    },
                    "required": ["hanzi", "pinyin", "meaning_vi"],
                },
            },
            "collocations": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 6,
            },
        },
        "required": [
            "word", "traditional", "phonetic", "part_of_speech",
            "translation_vi", "usage_note_vi", "definitions",
            "characters", "collocations",
        ],
    }

    result = ai_json(
        "learner_dictionary",
        [
            {
                "role": "system",
                "content": (
                    "You are a compact Chinese learner dictionary for a Vietnamese learner. "
                    "Use Simplified Chinese as the main form. Give tone-mark pinyin (for example: xuéxí), "
                    "a concise Vietnamese meaning, practical usage notes, and original natural examples. "
                    "If a traditional form is identical or not useful, return an empty traditional string. "
                    "Do not invent etymology. Character breakdown is only a learning aid; give literal/common "
                    "character meanings, not false historical explanations. "
                    "Name the lexical category in part_of_speech using exactly one of the standard Chinese "
                    "terms: 成语 (four-character set idiom), 惯用语 (colloquial set expression), 谚语 "
                    "(proverb), 歇后语 (two-part allegorical saying), 搭配 (collocation), 离合词 "
                    "(separable verb), 量词 (measure word), 短语 (other multi-word phrase). For an ordinary "
                    "single word use its word class (名词, 动词, 形容词, 副词). "
                    "Never label an entry 成语 unless it really is one."
                ),
            },
            {
                "role": "user",
                "content": f"Explain this Chinese word or short phrase for a Vietnamese learner: {word}",
            },
        ],
        schema,
        num_predict=1100,
        temperature=0.0,
    )
    result["source"] = active_ai_label("learner_dictionary")
    result["audio"] = ""
    result["cambridge_url"] = ""
    return result


def lookup_dictionary(word: str) -> dict[str, Any]:
    clean = normalise_lookup_word(word)
    cache_key = clean.casefold()

    row = _learning_cache.get_dictionary(cache_key)
    if row:
        try:
            fetched = datetime.fromisoformat(row["fetched_at"])
            if datetime.now().astimezone() - fetched < timedelta(days=30):
                payload = json.loads(row["payload_json"])
                payload["cached"] = True
                return payload
        except Exception:
            pass

    payload = None

    if is_chinese():
        try:
            payload = chinese_dictionary_ai(clean)
            payload["cached"] = False
        except Exception as exc:
            raise HTTPException(
                503,
                "Chinese dictionary AI is unavailable.",
            ) from exc
    else:
        try:
            response = requests.get(
                f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote(clean)}",
                timeout=8,
            )
            if response.ok:
                data = response.json()
                if isinstance(data, list) and data:
                    entry = data[0]
                    phonetic = str(entry.get("phonetic") or "")
                    audio = ""
                    if not phonetic:
                        for p in entry.get("phonetics", []):
                            if p.get("text"):
                                phonetic = str(p["text"])
                                break
                    for p in entry.get("phonetics", []):
                        if p.get("audio"):
                            audio = str(p["audio"])
                            if audio.startswith("//"):
                                audio = "https:" + audio
                            break
                    definitions = []
                    for meaning in entry.get("meanings", []):
                        pos = str(meaning.get("partOfSpeech") or "")
                        for definition in meaning.get("definitions", [])[:2]:
                            definitions.append({
                                "part_of_speech": pos,
                                "definition": str(definition.get("definition") or ""),
                                "example": str(definition.get("example") or ""),
                                "synonyms": [str(x) for x in definition.get("synonyms", [])[:5]],
                            })
                            if len(definitions) >= 5:
                                break
                        if len(definitions) >= 5:
                            break
                    if definitions:
                        payload = {
                            "word": str(entry.get("word") or clean),
                            "phonetic": phonetic,
                            "audio": audio,
                            "definitions": definitions,
                            "source": "dictionaryapi.dev",
                            "cambridge_url": cambridge_url_for(clean),
                            "cached": False,
                        }
        except Exception:
            payload = None

        if payload is None:
            try:
                payload = dictionary_ai_fallback(clean)
                payload["cached"] = False
            except Exception as exc:
                raise HTTPException(
                    503,
                    "Dictionary service is unavailable and AI fallback failed.",
                ) from exc

    _learning_cache.put_dictionary(
        cache_key,
        payload,
        datetime.now().astimezone().isoformat(timespec="seconds"),
    )

    return payload

@app.post("/api/improve")
def api_improve(payload: ImproveIn) -> dict[str, Any]:
    try:
        return improve_with_ai(payload)
    except requests.RequestException as exc:
        raise HTTPException(503, "AI engine is unavailable for writing improvement.") from exc
    except Exception as exc:
        raise HTTPException(502, "The improvement model returned invalid structured output.") from exc


def _grammar_storage_key(lesson: dict[str, Any]) -> str:
    version = int(lesson.get("content_version") or 1)
    language = active_grammar_language_code()
    return f"{language}:grammar:v{version}:{lesson['id']}"


@app.get("/api/library/grammar")
def api_grammar_library() -> dict[str, Any]:
    course = active_grammar_course()
    completed = _learning_repository.completed_grammar_ids()
    lessons = []
    for item in course:
        row = dict(item)
        row["completed"] = _grammar_storage_key(row) in completed
        lessons.append(row)
    return {
        "lessons": lessons,
        "total": len(lessons),
        "completed": sum(1 for row in lessons if row["completed"]),
        "levels": list(grammar_level_names()),
        "level_names": grammar_level_names(),
        "language": active_grammar_language_code(),
        "curriculum_policy": {
            "completion_is_mastery": False,
            "official_one_to_one_mapping": False,
            "lesson_scope_is_locked": True,
            "content_version": 2,
            "storage_namespace": "language+content_version+lesson_id",
        },
    }



def _static_grammar_detail(lesson_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    lesson = active_grammar_by_id().get(lesson_id)
    if not lesson:
        raise HTTPException(404, "Grammar lesson not found")
    knowledge = active_grammar_knowledge_by_id().get(lesson_id)
    if not knowledge:
        raise HTTPException(503, "Static grammar content is unavailable for this lesson.")
    return lesson, knowledge


@app.get("/api/library/grammar/{lesson_id}/reference")
def api_grammar_reference(lesson_id: str) -> dict[str, Any]:
    lesson, knowledge = _static_grammar_detail(lesson_id)
    return {
        "grammar_id": lesson_id,
        "title": lesson["title"],
        "level": lesson["level"],
        "kind": lesson["kind"],
        **dict(knowledge["quick_reference"]),
        "content_status": knowledge["source"]["content_status"],
        "source": "static-grammar-kb",
        "language": active_grammar_language_code(),
        "official_mapping": False,
    }


@app.get("/api/library/grammar/{lesson_id}")
def api_grammar_lesson(lesson_id: str) -> dict[str, Any]:
    lesson, knowledge = _static_grammar_detail(lesson_id)
    detail = dict(knowledge["lesson"])
    examples = []
    for example in detail.get("examples", []):
        item = dict(example)
        item.setdefault("target", str(item.get("en") or ""))
        item.setdefault("pinyin", "")
        item.setdefault("vi", "")
        item.setdefault("note_vi", "")
        examples.append(item)
    detail["examples"] = examples

    storage_key = _grammar_storage_key(lesson)
    return {
        **lesson,
        **detail,
        "quick_reference": dict(knowledge["quick_reference"]),
        "cross_skill": dict(knowledge["cross_skill"]),
        "learning_model": dict(knowledge.get("learning_model") or {}),
        "content_status": knowledge["source"]["content_status"],
        "completed": _learning_repository.grammar_completed(storage_key),
        "source": "static-grammar-kb",
        "language": active_grammar_language_code(),
        "completion_claim": "activity_evidence_not_mastery",
    }


@app.post("/api/library/grammar/{lesson_id}/complete")
def api_complete_grammar(lesson_id: str) -> dict[str, Any]:
    lesson = active_grammar_by_id().get(lesson_id)
    if not lesson:
        raise HTTPException(404, "Grammar lesson not found")
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    _learning_repository.set_grammar_completed(_grammar_storage_key(lesson), now)
    return {
        "completed": True,
        "lesson_id": lesson_id,
        "claim": "activity_evidence_not_mastery",
    }


@app.delete("/api/library/grammar/{lesson_id}/complete")
def api_uncomplete_grammar(lesson_id: str) -> dict[str, Any]:
    lesson = active_grammar_by_id().get(lesson_id)
    if not lesson:
        raise HTTPException(404, "Grammar lesson not found")
    changed = _learning_repository.unset_grammar_completed(_grammar_storage_key(lesson))
    return {"completed": False, "changed": changed, "lesson_id": lesson_id}

@app.post("/api/translate")
def api_translate(payload: TranslateIn) -> dict[str, Any]:
    if is_chinese():
        schema = {
            "type": "object",
            "properties": {
                "translation_vi": {"type": "string"},
                "natural_meaning_vi": {"type": "string"},
                "part_of_speech": {"type": "string"},
                "note_vi": {"type": "string"},
                "pinyin": {"type": "string"},
            },
            "required": [
                "translation_vi", "natural_meaning_vi",
                "part_of_speech", "note_vi", "pinyin",
            ],
        }
        system = (
            "Translate Simplified Chinese into natural Vietnamese for a Vietnamese learner. "
            "For a short word or phrase, also provide accurate tone-mark pinyin. "
            "Translate by meaning, not word by word. Keep the note concise and useful for learning."
        )
    else:
        schema = {
            "type": "object",
            "properties": {
                "translation_vi": {"type": "string"},
                "natural_meaning_vi": {"type": "string"},
                "part_of_speech": {"type": "string"},
                "note_vi": {"type": "string"},
            },
            "required": [
                "translation_vi", "natural_meaning_vi",
                "part_of_speech", "note_vi",
            ],
        }
        system = (
            "Translate English into natural Vietnamese for a language learner. "
            "Translate phrases by meaning, not word by word. Keep notes concise."
        )

    try:
        result = ai_json(
            "learner_translation",
            [
                {"role": "system", "content": system},
                {"role": "user", "content": payload.text},
            ],
            schema,
            num_predict=550,
            temperature=0.0,
        )
        result["text"] = payload.text
        return result
    except Exception as exc:
        raise HTTPException(503, "AI translation is unavailable.") from exc

@app.get("/api/dictionary")
def api_dictionary(word: str, response: Response = None) -> dict[str, Any]:
    """Return mutable/provider-backed dictionary data without shared caching."""
    if response is not None:
        response.headers["Cache-Control"] = "no-store"
    try:
        return lookup_dictionary(word)
    except HTTPException as exc:
        headers = dict(exc.headers or {})
        headers["Cache-Control"] = "no-store"
        exc.headers = headers
        raise


@app.get("/api/chinese/stroke-order")
def api_chinese_stroke_order(word: str, request: Request = None, response: Response = None) -> dict[str, Any]:
    """Verified stroke order for the Han characters in `word`.

    Deterministic and offline: this reads the vendored Make Me a Hanzi pack and
    never calls a provider, so it needs no AI capability and cannot degrade. A
    character the pack does not carry comes back in `unavailable` rather than
    being invented (`UPGRADE_REGRESSION_RULES.md` §33).
    """
    try:
        payload = chinese_stroke_order.stroke_order_for(word)
        source_version = str(payload.get("source_version") or chinese_stroke_order.SOURCE_VERSION)
        etag_seed = f"{source_version}\x00{payload.get('word', '')}"
        etag = '"' + hashlib.sha256(etag_seed.encode("utf-8")).hexdigest()[:24] + '"'
        cache_headers = {
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": etag,
        }
        if request is not None and request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=cache_headers)
        if response is not None:
            for key, value in cache_headers.items():
                response.headers[key] = value
        return payload
    except chinese_stroke_order.StrokeDataUnavailable as exc:
        error = orena_http_error(
            503,
            "stroke_data_unavailable",
            "Stroke-order data is not installed on this server.",
        )
        error.headers = {**(error.headers or {}), "Cache-Control": "no-store"}
        raise error from exc


@app.get("/api/vocabulary")
def api_vocabulary() -> dict[str, Any]:
    return {"items": _learning_repository.list_saved_words()}


@app.post("/api/vocabulary")
def api_save_vocabulary(payload: SaveWordIn) -> dict[str, Any]:
    word = normalise_lookup_word(payload.word)
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    _learning_repository.upsert_saved_word({
        "word": word,
        "phonetic": payload.phonetic,
        "part_of_speech": payload.part_of_speech,
        "definition": payload.definition,
        "added_at": now,
        "translation_vi": payload.translation_vi,
    })
    return {"saved": True, "word": word, "added_at": now}


@app.delete("/api/vocabulary/{word}")
def api_delete_vocabulary(word: str) -> dict[str, Any]:
    clean = normalise_lookup_word(word)
    return {"deleted": _learning_repository.delete_saved_word(clean)}

@app.post("/api/evaluate")
def api_evaluate(payload: EssayIn) -> dict[str, Any]:
    active_language = active_grammar_language_code()
    if payload.learning_language:
        requested_language = payload.learning_language.casefold().replace("_", "-")
        active_scope = active_language.casefold().replace("_", "-")
        if requested_language != active_scope and requested_language.split("-", 1)[0] != active_scope.split("-", 1)[0]:
            raise orena_http_error(
                409,
                "language_scope_mismatch",
                "Writing language does not match the selected learning language.",
                context={"requested_language": requested_language, "active_language": active_language},
            )
    previous: dict[str, Any] | None = None
    series_id: int | None = None
    revision_no = 1

    if payload.parent_essay_id:
        previous = _learning_repository.get_essay(payload.parent_essay_id)
        if not previous:
            category = _learning_repository.classify_essay_scope(payload.parent_essay_id)
            raise orena_http_error(
                404,
                category,
                "The earlier writing version is unavailable in this learning scope.",
                context={"parent_essay_id": payload.parent_essay_id},
            )
        series_id = int(previous["series_id"] or previous["id"])
        revision_no = _learning_repository.next_revision_no(series_id)

    result, evaluator = evaluate(payload)
    result["grammar_links"] = grammar_links_for_issues(
        result.get("errors", []),
        active_grammar_knowledge_by_id(),
        target_level=payload.target_cefr,
    )
    overall = weighted_overall(result)
    word_count = writing_unit_count(payload.text)
    now = datetime.now().astimezone().isoformat(timespec="seconds")

    practice_context = None
    if payload.practice_context is not None:
        practice_context = (
            payload.practice_context.model_dump()
            if hasattr(payload.practice_context, "model_dump")
            else payload.practice_context.dict()
        )

    created = _learning_repository.create_essay({
        "created_at": now,
        "prompt": payload.prompt,
        "text": payload.text,
        "word_count": word_count,
        "target_cefr": payload.target_cefr,
        "grammar": result["grammar"],
        "vocabulary": result["vocabulary"],
        "coherence": result["coherence"],
        "task_achievement": result["task_achievement"],
        "naturalness": result["naturalness"],
        "overall": overall,
        "cefr_estimate": result["cefr_estimate"],
        "evaluator": evaluator,
        "summary_vi": result["summary_vi"],
        "strengths_json": json.dumps(result["strengths_vi"], ensure_ascii=False),
        "strength_evidence_json": json.dumps(result["strength_evidence"], ensure_ascii=False),
        "priorities_json": json.dumps(result["priorities_vi"], ensure_ascii=False),
        "errors_json": json.dumps(result["errors"], ensure_ascii=False),
        "series_id": series_id,
        "revision_no": revision_no,
        "parent_id": payload.parent_essay_id,
        "practice_context": practice_context,
        "grammar_links": result["grammar_links"],
    })
    essay_id = int(created["id"])
    series_id = int(created["series_id"])


    current_for_delta = {**result, "overall": overall}
    delta = revision_delta(current_for_delta, previous)
    return {
        "id": essay_id,
        "series_id": series_id,
        "revision_no": revision_no,
        "parent_id": payload.parent_essay_id,
        "overall": overall,
        "app_cefr": app_cefr(overall),
        "evaluator": evaluator,
        "delta": delta,
        **result,
    }


@app.get("/api/essays")
def essays(limit: int = 200) -> list[dict[str, Any]]:
    limit = min(max(1, limit), 500)
    rows = _learning_repository.list_essays(limit)
    return [row_to_dict(r) for r in rows]


@app.get("/api/essays/{essay_id}")
def essay_detail(essay_id: int) -> dict[str, Any]:
    row = _learning_repository.get_essay(essay_id)
    if not row:
        raise HTTPException(404, "Essay not found")
    series_id = int(row["series_id"] or row["id"])
    series_rows = _learning_repository.list_series_revisions(series_id)
    previous = _learning_repository.previous_revision(series_id, int(row["revision_no"] or 1))
    d = row_to_dict(row, detail=True)
    d["revisions"] = series_rows
    d["delta"] = revision_delta(d, previous)
    return d

@app.delete("/api/essays/{essay_id}")
def delete_essay(essay_id: int) -> dict[str, bool]:
    return {"deleted": _learning_repository.delete_series_for_essay(essay_id)}


@app.get("/api/error-memory")
def api_error_memory() -> dict[str, Any]:
    rows = _learning_repository.list_essays(0, ascending=True)
    return {
        "items": error_memory(rows, active_error_categories()),
        "revision_count": len(rows),
    }


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    all_revision_rows = _learning_repository.list_essays(0, ascending=True)
    rows = _learning_repository.list_latest_series()

    if not rows:
        return {
            "essay_count": 0,
            "revision_count": 0,
            "skill_score": 0,
            "cefr": "—",
            "streak": 0,
            "recent_average": 0,
            "trend": [],
            "metrics": {},
            "error_counts": {},
            "error_memory": [],
            "next_level": None,
            "version": APP_VERSION,
        }

    latest = [dict(r) for r in rows]
    recent = latest[-10:]
    weights = list(range(1, len(recent) + 1))
    skill_score = round(
        sum(float(r["overall"]) * w for r, w in zip(recent, weights)) / sum(weights), 1
    )

    metrics = {
        m: round(statistics.mean(float(r[m]) for r in recent), 1)
        for m in active_rubric_weights()
    }

    error_counts: dict[str, int] = {}
    error_categories = active_error_categories()
    for r in recent:
        for err in parse_persisted_error_events(
            r["errors_json"], error_categories=error_categories
        ):
            cat = err["category"]
            error_counts[cat] = error_counts.get(cat, 0) + 1
    error_counts = dict(sorted(error_counts.items(), key=lambda kv: kv[1], reverse=True))

    dates = sorted({datetime.fromisoformat(r["created_at"]).date() for r in latest})
    streak = 0
    if dates:
        d = dates[-1]
        today = datetime.now().astimezone().date()
        if d in {today, today - timedelta(days=1)}:
            streak = 1
            for prev in reversed(dates[:-1]):
                if prev == d - timedelta(days=1):
                    streak += 1
                    d = prev
                elif prev < d - timedelta(days=1):
                    break

    bands = progress_bands()
    next_level = None
    for threshold, level in bands:
        if skill_score < threshold:
            next_level = {
                "level": level,
                "threshold": threshold,
                "remaining": round(threshold - skill_score, 1),
            }
            break

    trend = [
        {
            "id": r["id"],
            "series_id": r["series_id"],
            "revision_no": r["revision_no"],
            "date": r["created_at"][:10],
            "overall": r["overall"],
        }
        for r in latest[-20:]
    ]

    return {
        "essay_count": len(latest),
        "revision_count": len(all_revision_rows),
        "skill_score": skill_score,
        "cefr": app_cefr(skill_score),
        "streak": streak,
        "recent_average": round(
            statistics.mean(float(r["overall"]) for r in recent), 1
        ),
        "trend": trend,
        "metrics": metrics,
        "error_counts": error_counts,
        "error_memory": error_memory(all_revision_rows, error_categories)[:8],
        "next_level": next_level,
        "version": APP_VERSION,
    }

# Register BECOMING memory routes explicitly after all application endpoints.
# This makes route availability deterministic in the final FastAPI app.

# === BECOMING MEMORY DIRECT ROUTES START ===
# Route ownership is explicit in app.py; service logic stays in becoming_memory.py.
@app.get("/api/learner-profile", name="becoming_learner_profile_get")
def becoming_learner_profile_get() -> dict[str, Any]:
    return get_learner_profile()

@app.put("/api/learner-profile", name="becoming_learner_profile_put")
def becoming_learner_profile_put(payload: LearnerProfileIn) -> dict[str, Any]:
    return put_learner_profile(payload)

@app.get("/api/learning-memory", name="becoming_learning_memory_get")
def becoming_learning_memory_get() -> dict[str, Any]:
    return get_learning_memory()

@app.get("/api/review-cue", name="becoming_review_cue_get")
def becoming_review_cue_get(essay_id: int | None = None) -> dict[str, Any]:
    return get_review_cue(essay_id)

@app.get("/api/admin/product-activity", name="admin_product_activity")
def admin_product_activity(request: Request, window_days: int = 7) -> dict[str, Any]:
    return product_activity_response(request, _specialized_learning_repository, require_admin, window_days=window_days, operations_loader=lambda: admin_ai_operations(request, limit=500))

@app.get("/api/admin/readiness-summary", name="admin_readiness_summary")
def admin_readiness_summary(request: Request) -> dict[str, Any]:
    require_admin(request)
    config = AIControlPlane(_persistence_runtime.platform_repository).inspect()
    operations = admin_ai_operations(request, limit=500)
    product_activity = product_activity_response(request, _specialized_learning_repository, require_admin, window_days=7, operations_loader=lambda: operations)
    return build_readiness_summary(config, operations, product_activity)

@app.get("/api/cross-skill-cue", name="becoming_cross_skill_cue_get")
def becoming_cross_skill_cue_get() -> dict[str, Any]:
    """Return one language-scoped, evidence-backed cue without persistence."""
    language = active_profile().code
    try:
        raw_writing = get_review_cue()
        writing = {**raw_writing, "language": language} if isinstance(raw_writing, dict) else None
    except Exception:
        writing = None
    try:
        reading_payload = list_reading_sessions(20)
        raw_reading = reading_payload.get("items", []) if isinstance(reading_payload, dict) else []
        reading = [{**item, "language": language} for item in raw_reading if isinstance(item, dict)]
    except Exception:
        reading = []
    try:
        listening = _specialized_learning_repository.list_recent_listening_progress_records(20)
    except Exception:
        listening = []
    try:
        speaking = _specialized_learning_repository.list_speaking_attempt_records(20)
    except Exception:
        speaking = []
    return select_cross_skill_cue(language=language, writing=writing, reading=reading, listening=listening, speaking=speaking)
# === BECOMING MEMORY DIRECT ROUTES END ===

# === BECOMING PERSONALIZED PRACTICE ROUTES START ===
def _recommendation_outcomes() -> list[dict[str, Any]]:
    try:
        payload = list_practice_outcomes(8)
    except Exception:
        return []
    items = payload.get("items") if isinstance(payload, dict) else None
    return items if isinstance(items, list) else []


@app.get("/api/practice-recommendation", name="becoming_practice_recommendation")
def becoming_practice_recommendation() -> dict[str, Any]:
    memory = get_learning_memory()
    return build_practice_recommendation(
        language=active_profile().code,
        profile=get_learner_profile(),
        memory=memory,
        outcomes=_recommendation_outcomes(),
    )

@app.post("/api/practice/next", name="becoming_practice_next")
def becoming_practice_next(payload: PracticeNextIn) -> dict[str, Any]:
    language = active_profile().code
    default_level = "HSK4" if language == "zh" else "B2"
    target_level = validate_target_level(payload.target_level or default_level)

    recommendation = build_practice_recommendation(
        language=language,
        profile=get_learner_profile(),
        memory=get_learning_memory(),
        target_level=target_level,
        outcomes=_recommendation_outcomes(),
    )

    task_payload = TaskGenerateIn(
        task_type=recommendation["task_type"],
        topic=recommendation["topic"],
        target_cefr=target_level,
        word_target=int(recommendation["word_target"]),
    )
    task = generate_practice_task(task_payload)
    personalized = personalize_generated_task(task, recommendation)
    personalized["prompt"] = task_as_prompt(personalized, target_level)
    personalized["target_level"] = target_level
    return personalized


@app.get("/api/grammar/{grammar_id}/practice", name="grammar_targeted_practice")
def grammar_targeted_practice(
    grammar_id: str,
    evidence: str = Query(default="", max_length=600),
) -> dict[str, Any]:
    """Build a small practice brief from one authoritative R5 lesson."""
    lesson = active_grammar_by_id().get(grammar_id)
    if not lesson:
        raise HTTPException(404, "Grammar lesson not found")
    language = active_profile().code
    title = str(lesson.get("title") or grammar_id)
    level = str(lesson.get("level") or ("HSK4" if language == "zh" else "B2"))
    blueprint = lesson.get("practice_blueprint") if isinstance(lesson.get("practice_blueprint"), dict) else {}
    evidence = evidence.strip() if isinstance(evidence, str) else ""
    base_target = "请写 3-5 句，使用本课的语法重点。" if language == "zh" else "Write 3–5 sentences using the grammar focus from this lesson."
    if evidence:
        target = (
            f"{base_target} 请特别留意你之前写过的这段表达：“{evidence}”。"
            if language == "zh"
            else f'{base_target} Pay special attention to this evidence from your writing: “{evidence}”.'
        )
    else:
        target = base_target
    if language == "zh":
        action_label = "练习这个语法"
        reason = "根据你的 Writing 发现和静态 Grammar 课程选择的针对性练习。"
        topic = "语法迁移练习"
    else:
        action_label = "Practice this grammar"
        reason = "Targeted practice selected from a Writing finding and the static Grammar curriculum."
        topic = "grammar transfer"
    context = {
        "intent": "repair",
        "focus_category": "grammar",
        "focus_label": title,
        "focus_family": "grammar",
        "task_type": "story",
        "topic": topic,
        "target_level": level,
        "action_label": action_label,
        "reason": reason,
        "evidence": evidence,
        "focus_instruction": target,
        "grammar_id": grammar_id,
        "grammar_title": title,
    }
    return {
        "grammar_id": grammar_id,
        "title": title,
        "level": level,
        "target_level": level,
        "prompt": target,
        "practice_blueprint": blueprint,
        "practice_context": context,
        "source": "static-grammar-kb",
    }
# === BECOMING PERSONALIZED PRACTICE ROUTES END ===

# === BECOMING PRACTICE OUTCOME ROUTES START ===
@app.get("/api/practice-outcome/{essay_id}", name="becoming_practice_outcome")
def becoming_practice_outcome(essay_id: int) -> dict[str, Any]:
    return get_practice_outcome(essay_id)


@app.get("/api/practice-outcomes", name="becoming_practice_outcomes")
def becoming_practice_outcomes(limit: int = 20) -> dict[str, Any]:
    return list_practice_outcomes(limit)
# === BECOMING PRACTICE OUTCOME ROUTES END ===

# === BECOMING VOCABULARY LIBRARY ROUTES START ===
@app.get("/api/library/vocabulary", name="becoming_library_vocabulary_list")
def becoming_library_vocabulary_list() -> dict[str, Any]:
    return list_library_vocabulary()

@app.post("/api/library/vocabulary", name="becoming_library_vocabulary_save")
def becoming_library_vocabulary_save(payload: LibraryVocabularyIn) -> dict[str, Any]:
    try:
        return save_library_vocabulary(payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@app.post("/api/library/vocabulary/{word}/review", name="becoming_library_vocabulary_review")
def becoming_library_vocabulary_review(
    word: str,
    payload: VocabularyReviewIn,
) -> dict[str, Any]:
    return review_library_vocabulary(word, payload)

@app.delete("/api/library/vocabulary/{word}", name="becoming_library_vocabulary_delete")
def becoming_library_vocabulary_delete(word: str) -> dict[str, Any]:
    return delete_library_vocabulary(word)
# === BECOMING VOCABULARY LIBRARY ROUTES END ===

# === BECOMING READING STUDIO ROUTES START ===
@app.get("/api/reading/sessions", name="becoming_reading_sessions")
def becoming_reading_sessions(limit: int = 8) -> dict[str, Any]:
    return list_reading_sessions(limit)

@app.get("/api/reading/session/{session_id}", name="becoming_reading_session")
def becoming_reading_session(session_id: int) -> dict[str, Any]:
    return get_reading_session(session_id)

@app.post("/api/reading/session", name="becoming_reading_create")
def becoming_reading_create(payload: ReadingGenerateIn) -> dict[str, Any]:
    language = active_profile().code
    default_level = "HSK4" if language == "zh" else "B2"
    target_level = validate_target_level(payload.target_level or default_level)
    return create_reading_session(
        payload,
        language_code=language,
        target_level=target_level,
        learner_profile=get_learner_profile(),
    )

@app.post("/api/reading/session/{session_id}/answer", name="becoming_reading_answer")
def becoming_reading_answer(
    session_id: int,
    payload: ReadingAnswerIn,
) -> dict[str, Any]:
    result = submit_reading_answers(session_id, payload)
    if not result.get("found", False):
        raise HTTPException(404, "Reading session not found.")
    if not result.get("valid", True):
        raise HTTPException(422, result.get("message") or "Invalid reading answers.")
    return result
# === BECOMING READING STUDIO ROUTES END ===

# === BECOMING LINGUISTIC LENS ROUTES START ===
@app.post("/api/essays/{essay_id}/linguistic-annotations", name="becoming_linguistic_annotations")
def becoming_linguistic_annotations(essay_id: int) -> dict[str, Any]:
    try:
        result = linguistic_annotations_for_essay(essay_id)
    except AIProviderUnavailable as exc:
        raise HTTPException(503, "Linguistic analysis is temporarily unavailable.") from exc
    except AIProviderError as exc:
        raise HTTPException(502, "Linguistic analysis returned invalid output.") from exc
    if not result.get("found", False):
        raise HTTPException(404, "Essay not found.")
    return result
# === BECOMING LINGUISTIC LENS ROUTES END ===
