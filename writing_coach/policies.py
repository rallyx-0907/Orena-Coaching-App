"""Operational policies, edited in Platform Admin without a code change or a restart (D-172).

One settings document, `platform.policies` (a `platform_settings` row, exactly like the plan catalogue's
`product.plan_catalog`, D-153): `{"version": 1, "values": {<policy key>: <value>}}`. It holds only what an
administrator chose; a policy absent from it is at its default, so an empty or missing document changes nothing.

Precedence for every policy, highest first:

  1. an environment variable that is explicitly set (the policies that had one before keep it, so operations can
     pin production: the Admin page shows such a policy as "locked by environment" and refuses to change it);
  2. the administrator's stored value;
  3. the default, which is the value the code carried as a constant before this module existed.

Consumers call `value(key)` at the moment they act, never at import, so a saved change applies within
`CACHE_SECONDS` in every worker (at once in the worker that saved it). The read never raises: a store that cannot
be read keeps the last value read in this process (the defaults if none was ever read) and is logged - except the
quota enforcement switch, which is not a policy of this document and keeps its own fail-closed rule (D-161).

A save is a compare-and-set on the stored version with the audit row in the same transaction (the catalogue's
contract). Switches that delete data and spend caps raised past a sane maximum need an explicit confirmation, which
the audit row records.

What is NOT here, and why, is in docs/project/UI_BACKEND_GAPS.md "ADM-POL": protocol and safety internals (class B)
stay in code; keys, URLs and deployment gates (class C) stay in the environment.
"""

from __future__ import annotations

import logging
import math
import os
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

_log = logging.getLogger(__name__)

SETTING_KEY = "platform.policies"
VERSION = 1
CACHE_SECONDS = 5.0

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})
_INVALID = object()


class PolicyInvalid(ValueError):
    """An administrator's change that cannot be applied (HTTP 422)."""


class PolicyUnavailable(RuntimeError):
    """A policy whose safe value cannot be known right now (the settings store was never read, or the stored value no
    longer validates). Raised only by `value_strict`; a consumer that must fail closed catches it."""


class PolicyConfirmationRequired(PolicyInvalid):
    """A change that needs the administrator's explicit confirmation first (HTTP 422, code confirmation_required)."""

    def __init__(self, keys: list[str]) -> None:
        super().__init__("Confirm these changes first: " + ", ".join(keys))
        self.keys = keys


@dataclass(frozen=True)
class Policy:
    key: str
    group: str
    kind: str                       # int | float | bool | enum
    default: Any
    unit: str = ""                  # seconds | minutes | hours | days | count | tokens | usd | usd_per_hour | usd_per_mtok | ""
    low: float | int | None = None
    high: float | int | None = None
    env: str = ""                   # the environment variable that pins this policy when it is set
    env_min: float | int | None = None   # an environment number below this is ignored (the old behaviour)
    nullable: bool = False          # null means "off" (no cap)
    choices: tuple[str, ...] = ()
    danger: str = ""                # "delete": can delete learner data; "charging": changes what a learner is charged.
                                    # Any change to a policy with a danger is confirmed.
    confirm_above: float | int | None = None  # a value above this (or null) is confirmed


def _p(key: str, group: str, kind: str, default: Any, **extra: Any) -> Policy:
    return Policy(key=key, group=group, kind=kind, default=default, **extra)


GROUPS: tuple[str, ...] = ("quota", "agent", "voice", "speech", "media", "vocabulary", "rates", "feedback", "spend",
                           "billing")

POLICIES: tuple[Policy, ...] = (
    # --- quota (the enforcement switch itself is product.quota_enforcement, D-161; this is what the reconciler decides)
    _p("quota.abandoned_settles", "quota", "enum", "admitted", choices=("admitted", "zero"), danger="charging"),
    # --- Orena (agent) limits (writing_coach/agent/limits.py)
    _p("agent.turns_per_window", "agent", "int", 12, unit="count", low=1, high=600),
    _p("agent.capability_reads_per_window", "agent", "int", 60, unit="count", low=1, high=6000),
    _p("agent.rate_window_seconds", "agent", "int", 60, unit="seconds", low=10, high=3600),
    _p("agent.max_input_tokens_per_turn", "agent", "int", 48_000, unit="tokens", low=4_000, high=200_000),
    _p("agent.model_openings_per_window", "agent", "int", 1, unit="count", low=1, high=20),
    _p("agent.opening_window_seconds", "agent", "int", 30 * 60, unit="seconds", low=60, high=86_400),
    _p("agent.opening_max_output_tokens", "agent", "int", 200, unit="tokens", low=50, high=1024),
    # --- live voice
    # `voice.enabled` is NOT a policy: turning on paid live voice is the human's activation gate (D-169 point 11), so it
    # stays the environment's (AGENT_VOICE_ENABLED, class C).
    _p("voice.resumption", "voice", "bool", True, env="AGENT_VOICE_RESUMPTION"),
    _p("voice.session_cap_seconds", "voice", "int", 15 * 60, unit="seconds", low=60, high=3600),
    _p("voice.chunk_units", "voice", "int", 2, unit="count", low=1, high=10, danger="charging"),
    # --- speech and pronunciation
    _p("speech.take_max_seconds", "speech", "int", 300, unit="seconds", low=10, high=900),
    _p("speech.asr_daily_seconds", "speech", "int", 60 * 60, unit="seconds", low=60, high=86_400,
       env="SPEECH_ASR_DAILY_SECONDS"),
    _p("speech.pronunciation_max_concurrent", "speech", "int", 8, unit="count", low=1, high=32,
       env="PRONUNCIATION_MAX_CONCURRENT"),
    _p("speech.no_speech_charged", "speech", "bool", True, danger="charging"),
    _p("rate.speech_ai_per_10min", "speech", "int", 60, unit="count", low=5, high=5000),
    # --- media import
    _p("media.asr_max_seconds", "media", "int", 5400, unit="seconds", low=60, high=43_200,
       env="MEDIA_ASR_MAX_SECONDS", env_min=1),
    _p("media.model_clips_enabled", "media", "bool", True, env="MEDIA_MODEL_CLIPS"),
    _p("media.model_clip_max_lines", "media", "int", 500, unit="count", low=10, high=5000,
       env="MEDIA_MODEL_CLIP_MAX_LINES", env_min=1),
    _p("rate.media_learning_per_hour", "media", "int", 30, unit="count", low=1, high=1000),
    # Where a YouTube item's captions come from (D-215): YouTube itself (the default), Supadata in its native mode only,
    # or YouTube first and Supadata native when YouTube gives none. Supadata is never asked to generate or translate.
    _p("media.caption_source", "media", "enum", "youtube", env="MEDIA_CAPTION_SOURCE",
       choices=("youtube", "supadata_native", "youtube_then_supadata_native")),
    # Which Chinese script a provider caption track may be in (D-218, owner decision 2026-10-15: "skip Traditional content;
    # for now only Simplified learning content is accepted"). `simplified` refuses a track tagged zh-Hant / zh-TW / zh-HK /
    # zh-MO with the stable reason `zh_traditional_not_accepted`; `any` takes the provider's track as it is. Speech
    # recognition output is not affected: it is converted to Simplified (D-208).
    _p("media.zh_scripts_accepted", "media", "enum", "simplified", choices=("simplified", "any")),
    # --- vocabulary (D-188): the operator's switch for the derived General catalogue; on by default
    _p("vocabulary.general_catalogue_enabled", "vocabulary", "bool", True),
    # --- request rates on the other paid routes (per account, per 10 minutes)
    _p("rate.writing_ai_per_10min", "rates", "int", 30, unit="count", low=1, high=5000),
    _p("rate.essay_ai_per_10min", "rates", "int", 30, unit="count", low=1, high=5000),
    _p("rate.dictionary_ai_per_10min", "rates", "int", 120, unit="count", low=1, high=5000),
    _p("rate.reading_ai_per_10min", "rates", "int", 300, unit="count", low=1, high=5000),
    # --- feedback and retention
    _p("feedback.daily_limit", "feedback", "int", 10, unit="count", low=1, high=100),
    _p("feedback.retention_sweep", "feedback", "bool", False, env="FEEDBACK_RETENTION_SWEEP", danger="delete"),
    # A retention period can only be shortened: the published legal text (docs/legal/public/facts.json, privacy) states
    # 24 months, 90 days and 13 months, so each maximum is that published value.
    _p("feedback.retention_days", "feedback", "int", 730, unit="days", low=30, high=730, danger="delete"),
    _p("agent.turn_retention_sweep", "feedback", "bool", False, env="AGENT_TURN_RETENTION_SWEEP", danger="delete"),
    _p("agent.turn_retention_days", "feedback", "int", 90, unit="days", low=7, high=90, danger="delete"),
    _p("ai_costs.retention_days", "feedback", "int", 396, unit="days", low=90, high=396, danger="delete"),
    # --- spend caps
    _p("agent.daily_spend_cap_usd", "spend", "float", None, unit="usd", low=0.01, high=10_000, nullable=True,
       env="AGENT_DAILY_SPEND_CAP_USD", env_min=0, confirm_above=50),
    _p("media.batch_cap_asr_usd", "spend", "float", 5.0, unit="usd", low=0, high=1000, env="MEDIA_ASR_BATCH_CAP_USD",
       env_min=0, confirm_above=50),
    _p("media.batch_cap_ai_usd", "spend", "float", 10.0, unit="usd", low=0, high=1000, env="MEDIA_AI_BATCH_CAP_USD",
       env_min=0, confirm_above=100),
    _p("media.daily_cap_usd", "spend", "float", 25.0, unit="usd", low=0, high=10_000, env="MEDIA_DAILY_CAP_USD",
       env_min=0, confirm_above=250),
    # A price estimate of 0 would make every media spend cap unreachable, so the minimum is above 0.
    # Supadata is paid in credits, not dollars: this is the most requests one UTC day may make (D-215). 0 turns it off.
    _p("media.supadata_daily_requests", "spend", "int", 20, unit="count", low=0, high=1000,
       env="MEDIA_SUPADATA_DAILY_REQUESTS", env_min=0),
    _p("media.asr_usd_per_hour", "spend", "float", 0.04, unit="usd_per_hour", low=0.001, high=100,
       env="MEDIA_ASR_USD_PER_HOUR", env_min=0),
    _p("media.ai_usd_per_million_tokens", "spend", "float", 1.0, unit="usd_per_mtok", low=0.001, high=1000,
       env="MEDIA_AI_USD_PER_MILLION_TOKENS", env_min=0),
    _p("word_tts.spend_cap_usd", "spend", "float", 5.0, unit="usd", low=0, high=1000, env="WORD_TTS_SPEND_CAP_USD",
       env_min=0, confirm_above=50),
    # The paid standby of `word_translation` (D-195 amendment 2026-10-14): the most it may spend in a UTC day. At the
    # cap, or at 0, the capability falls back to its free pool only; an unreadable ledger counts as the cap reached.
    _p("word_translation.daily_spend_cap_usd", "spend", "float", 0.5, unit="usd", low=0, high=100,
       env="WORD_TRANSLATION_DAILY_SPEND_CAP_USD", env_min=0, confirm_above=5),
    # PR-MON-7A-first: the daily cap of each routed capability's reviewed paid backup. 0 (the default) = no paid
    # backup: the chain stops at its reviewed primary. The numbers are the owner's (H7-8), never chosen here.
    _p("writing_evaluator.daily_spend_cap_usd", "spend", "float", 0.0, unit="usd", low=0, high=100,
       env="WRITING_EVALUATOR_DAILY_SPEND_CAP_USD", env_min=0, confirm_above=5),
    _p("writing_improver.daily_spend_cap_usd", "spend", "float", 0.0, unit="usd", low=0, high=100,
       env="WRITING_IMPROVER_DAILY_SPEND_CAP_USD", env_min=0, confirm_above=5),
    _p("text_discussion.daily_spend_cap_usd", "spend", "float", 0.0, unit="usd", low=0, high=100,
       env="TEXT_DISCUSSION_DAILY_SPEND_CAP_USD", env_min=0, confirm_above=5),
    # --- free-tier flags (D-219, owner decision 2026-10-16): the provider account is on a free plan. Each cost event is
    # stamped with the flag in force when it is recorded and reported apart from real spend; the flag never zeroes an
    # amount or a cap (writing_coach/cost_tier.py). Turn it off when the account moves to a paid plan.
    _p("cost.free_tier.groq", "spend", "bool", True),
    _p("cost.free_tier.supadata", "spend", "bool", True),
    _p("cost.free_tier.gemini", "spend", "bool", False),
    # --- billing (PR-MON-8 §4.1, owner decision: 1 hour). 0 is the UNCONFIGURED sentinel, never a grace of zero: SePay
    # checkout is not ready and every SePay payment fails closed (no grant) until an operator sets a value >= 1.
    _p("billing.domestic_late_payment_grace_hours", "billing", "int", 0, unit="hours", low=0, high=168,
       danger="charging"),
)


def media_ai_model_rate(model: object) -> tuple[float, float] | None:
    """The public (list) rate of a model for the media AI ledger, or None. One source: `ai/pricing.py` (D-219 unified
    what D-218 kept here), so the ledger and the cost report agree on a model's price."""
    from writing_coach.ai.pricing import list_rate

    return list_rate("groq", model)


BY_KEY: dict[str, Policy] = {item.key: item for item in POLICIES}
assert len(BY_KEY) == len(POLICIES), "a policy key is declared twice"
assert all(item.group in GROUPS for item in POLICIES)


def default(key: str) -> Any:
    return BY_KEY[key].default


# --- one value -------------------------------------------------------------------------------------------------

def check(policy: Policy, raw: object) -> Any:
    """`raw` as this policy's value, or `PolicyInvalid` saying why not (strict: nothing is coerced from text)."""
    if raw is None:
        if policy.nullable:
            return None
        raise PolicyInvalid(f"{policy.key} needs a value.")
    if policy.kind == "bool":
        if type(raw) is not bool:
            raise PolicyInvalid(f"{policy.key} must be true or false.")
        return raw
    if policy.kind == "enum":
        if not isinstance(raw, str) or raw not in policy.choices:
            raise PolicyInvalid(f"{policy.key} must be one of: {', '.join(policy.choices)}.")
        return raw
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
        raise PolicyInvalid(f"{policy.key} must be a number.")
    if policy.kind == "int":
        if int(raw) != raw:
            raise PolicyInvalid(f"{policy.key} must be a whole number.")
        number: int | float = int(raw)
    else:
        number = round(float(raw), 4)
    if (policy.low is not None and number < policy.low) or (policy.high is not None and number > policy.high):
        raise PolicyInvalid(f"{policy.key} must be between {policy.low} and {policy.high}.")
    return number


def _env_mapping(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


_WARNED_ENV: set[str] = set()   # one warning per variable, not one per read


def _env_value(policy: Policy, env: Mapping[str, str] | None) -> Any:
    """`_INVALID` when the variable is unset or empty (the policy is not pinned); else its parsed value, or
    `policy.default` when it is set but cannot be read (the old behaviour of each variable)."""
    if not policy.env:
        return _INVALID
    text = str(_env_mapping(env).get(policy.env, "") or "").strip()
    if not text:
        return _INVALID
    if policy.kind == "bool":
        lowered = text.casefold()
        return True if lowered in _TRUE else False if lowered in _FALSE else policy.default
    if policy.kind == "enum":
        if text in policy.choices:
            return text
        if policy.env not in _WARNED_ENV:
            _WARNED_ENV.add(policy.env)
            _log.warning("platform.policies: %s=%r is not one of %s; using the default %r", policy.env, text,
                         ", ".join(policy.choices), policy.default)
        return policy.default
    try:
        number = float(text)
    except ValueError:
        return policy.default
    if not math.isfinite(number) or (policy.env_min is not None and number < policy.env_min):
        return policy.default
    return int(number) if policy.kind == "int" else number


# --- the stored document ---------------------------------------------------------------------------------------

class SettingStore(Protocol):
    def get_setting(self, key: str) -> dict | None: ...
    def set_setting(self, key: str, value: dict, *, updated_by: str = "", expected_updated_at: object = ...,
                    audit: dict | None = None) -> dict: ...


@dataclass(frozen=True)
class _Loaded:
    values: Mapping[str, Any] = field(default_factory=dict)
    updated_at: str | None = None
    updated_by: str | None = None
    state: str = "default"          # default (nothing stored) | stored | stale (read failed; last value kept) | unreadable
    rejected: frozenset = frozenset()   # stored keys whose value does not validate now (the default applies to them)


_store: SettingStore | None = None
_env: Mapping[str, str] | None = None
_lock = threading.Lock()
_cache: tuple[float, _Loaded] | None = None
_last_good: _Loaded | None = None


def configure(store: SettingStore | None, *, env: Mapping[str, str] | None = None) -> None:
    """Install the settings store (the platform repository) and, for tests, the environment the pins are read from."""
    global _store, _env, _cache, _last_good
    with _lock:
        _store, _env, _cache, _last_good = store, env, None, None


def is_pinned(key: str, env: Mapping[str, str] | None = None) -> bool:
    """Whether the environment fixes this policy, so its stored history says nothing about its value."""
    return _env_value(BY_KEY[key], env if env is not None else _env) is not _INVALID


def has_admin_value(key: str) -> bool:
    """Whether an administrator has stored a value for this policy (it is not just the default)."""
    return key in _loaded().values


def clear_cache() -> None:
    global _cache
    with _lock:
        _cache = None


def _parse(record: Mapping[str, Any]) -> _Loaded:
    document = record.get("value")
    values: dict[str, Any] = {}
    rejected: set[str] = set()
    if isinstance(document, Mapping) and isinstance(document.get("values"), Mapping):
        for key, raw in document["values"].items():
            policy = BY_KEY.get(str(key))
            if policy is None:
                _log.warning("platform.policies: ignoring unknown policy %r (a newer build wrote it)", key)
                continue
            try:
                values[policy.key] = check(policy, raw)
            except PolicyInvalid as error:
                rejected.add(policy.key)
                _log.warning("platform.policies: ignoring a stored value that is not valid now: %s", error)
    elif document not in (None, {}):
        _log.warning("platform.policies: the stored document is not readable; the defaults apply")
    return _Loaded(values, str(record.get("updated_at") or "") or None, str(record.get("updated_by") or "") or None,
                   "stored", frozenset(rejected))


def _loaded() -> _Loaded:
    global _cache, _last_good
    now = time.monotonic()
    with _lock:
        if _cache is not None and _cache[0] > now:
            return _cache[1]
        store, previous = _store, _last_good
    if store is None:
        loaded = _Loaded()
    else:
        try:
            record = store.get_setting(SETTING_KEY)
            loaded = _parse(record) if record else _Loaded()
        except Exception:
            # The settings store cannot be read: keep what this process last knew (the defaults if it never knew
            # anything) and say so. A failure is cached as briefly as a success so a down store is not asked on
            # every request.
            _log.warning("platform.policies unreadable; keeping the last values read", exc_info=True)
            loaded = replace(previous, state="stale") if previous is not None else _Loaded(state="unreadable")
            with _lock:
                _cache = (now + CACHE_SECONDS, loaded)
            return loaded
    with _lock:
        _cache = (now + CACHE_SECONDS, loaded)
        _last_good = loaded
    return loaded


def value(key: str, *, env: Mapping[str, str] | None = None) -> Any:
    """The effective value of one policy now: environment pin, else the administrator's value, else the default.
    Never raises for a known key; an unknown key is a programming error."""
    policy = BY_KEY[key]
    try:
        pinned = _env_value(policy, env if env is not None else _env)
        if pinned is not _INVALID:
            return pinned
        stored = _loaded().values
        return stored[key] if key in stored else policy.default
    except Exception:  # noqa: BLE001 - a policy read never costs a learner a request
        _log.warning("platform.policies: reading %s failed; using its default", key, exc_info=True)
        return policy.default


def value_strict(key: str, *, env: Mapping[str, str] | None = None) -> Any:
    """Like `value`, for a policy whose default is NOT safe to fall back to (the agent's daily spend cap: "no cap").
    Raises `PolicyUnavailable` when the environment does not pin the policy and either this process has never read
    the settings store successfully, or the stored value for it does not validate now. A process that has read the
    store once keeps its last values on a later failure, as `value` does."""
    policy = BY_KEY[key]
    pinned = _env_value(policy, env if env is not None else _env)
    if pinned is not _INVALID:
        return pinned
    loaded = _loaded()
    if loaded.state == "unreadable":
        raise PolicyUnavailable(f"{key}: the settings store has never been read in this process")
    if key in loaded.rejected:
        raise PolicyUnavailable(f"{key}: the stored value is not valid")
    return loaded.values[key] if key in loaded.values else policy.default


AGENT_LIMIT_FIELDS: tuple[str, ...] = (
    "turns_per_window", "capability_reads_per_window", "rate_window_seconds", "max_input_tokens_per_turn",
    "model_openings_per_window", "opening_window_seconds", "opening_max_output_tokens",
)


def effective_agent_limits() -> dict[str, Any]:
    """The operator-tunable `AgentLimits` fields as they stand now (agent/limits.py `LiveAgentLimits`)."""
    return {name: value(f"agent.{name}") for name in AGENT_LIMIT_FIELDS}


def effective(keys: tuple[str, ...] | None = None) -> dict[str, Any]:
    return {item.key: value(item.key) for item in POLICIES if keys is None or item.key in keys}


def snapshot() -> dict[str, Any]:
    """Every policy with where its value comes from, for the Admin page."""
    loaded = _loaded()
    env = _env
    rows = []
    for item in POLICIES:
        pinned = _env_value(item, env)
        locked = pinned is not _INVALID
        has_admin = item.key in loaded.values
        rows.append({
            "key": item.key, "group": item.group, "kind": item.kind, "unit": item.unit, "default": item.default,
            "low": item.low, "high": item.high, "nullable": item.nullable, "choices": list(item.choices),
            "danger": item.danger, "confirm_above": item.confirm_above,
            "env": item.env, "locked": locked,
            "source": "env" if locked else "admin" if has_admin else "default",
            "value": pinned if locked else loaded.values[item.key] if has_admin else item.default,
            "admin": loaded.values.get(item.key), "has_admin": has_admin,
        })
    return {
        "version": VERSION, "groups": list(GROUPS), "policies": rows,
        "source": "stored" if loaded.updated_at else "default",
        "state": loaded.state, "updated_at": loaded.updated_at, "updated_by": loaded.updated_by,
    }


# --- saving ----------------------------------------------------------------------------------------------------

def _needs_confirmation(policy: Policy, old: Any, new: Any) -> bool:
    if new == old:
        return False
    if policy.danger:
        return True
    if policy.confirm_above is not None and (new is None or new > policy.confirm_above):
        return True
    return False


def save(change: object, *, updated_by: str = "", actor: str = "", expected_updated_at: object = ...,
         confirm: object = None) -> dict[str, Any]:
    """Apply `{"set": {key: value}, "reset": [key, ...]}` to the stored document.

    `reset` returns a policy to its default; `set` stores a value. Unknown keys, bad values and a policy pinned by
    the environment are refused. A dangerous change (a switch or period that deletes data, a spend cap past its
    sane maximum) needs `confirm[key] is True`. The stored version the editor loaded (`expected_updated_at`) is
    compared inside the write transaction and the audit row commits with the change."""
    if _store is None:
        raise RuntimeError("The policies store has not been installed by the persistence runtime.")
    if not isinstance(change, Mapping):
        raise PolicyInvalid("The change must be an object.")
    unknown_top = set(change) - {"set", "reset", "expected_updated_at", "confirm"}
    if unknown_top:
        raise PolicyInvalid(f"Unknown field {sorted(unknown_top)[0]!r}.")
    to_set = {} if change.get("set") is None else change["set"]
    to_reset = [] if change.get("reset") is None else change["reset"]
    if not isinstance(to_set, Mapping) or not isinstance(to_reset, list):
        raise PolicyInvalid("`set` must be an object and `reset` a list.")
    # The version the editor loaded and its confirmations may travel in the change itself or as arguments.
    if expected_updated_at is ... and "expected_updated_at" in change:
        expected_updated_at = change["expected_updated_at"]
    if confirm is None:
        confirm = change.get("confirm")
    confirmed = confirm if isinstance(confirm, Mapping) else {}
    unknown = sorted((set(map(str, to_set)) | set(map(str, to_reset))) - set(BY_KEY))
    if unknown:
        raise PolicyInvalid(f"Unknown policy {unknown[0]!r}.")
    clean: dict[str, Any] = {}
    for key, raw in to_set.items():
        policy = BY_KEY[str(key)]
        if _env_value(policy, _env) is not _INVALID:
            raise PolicyInvalid(f"{policy.key} is locked by the environment ({policy.env}); change it there.")
        clean[policy.key] = check(policy, raw)
    resets = [str(key) for key in to_reset]
    try:
        base = _store.get_setting(SETTING_KEY)
    except Exception as error:
        raise RuntimeError("The policies store could not be read.") from error
    base_values = dict(_parse(base).values) if base else {}
    if expected_updated_at is ...:
        # This write merges onto what was just read, so it is always a compare-and-set against that version (None when
        # nothing is stored yet): a concurrent change is a conflict, never silently overwritten.
        expected_updated_at = base.get("updated_at") if base else None
    new_values = {**base_values, **clean}
    for key in resets:
        new_values.pop(key, None)
    changes: dict[str, dict[str, Any]] = {}
    needing: list[str] = []
    for key in sorted(set(clean) | set(resets)):
        policy = BY_KEY[key]
        before = base_values.get(key, policy.default)
        after = new_values.get(key, policy.default)
        if before == after and (key in base_values) == (key in new_values):
            continue
        changes[key] = {"from": before, "to": after, "reset": key not in new_values}
        if _needs_confirmation(policy, before, after):
            needing.append(key)
    if not changes:
        return snapshot()
    missing = [key for key in needing if confirmed.get(key) is not True]
    if missing:
        raise PolicyConfirmationRequired(missing)
    document = {"version": VERSION, "values": {key: new_values[key] for key in sorted(new_values)}}
    audit = {
        "action": "platform.policies.update", "actor": actor, "entity_type": "platform_setting",
        "entity_id": SETTING_KEY, "payload": {"changes": changes, "confirmed": sorted(needing)},
    }
    _store.set_setting(SETTING_KEY, document, updated_by=updated_by, expected_updated_at=expected_updated_at,
                       audit=audit)
    clear_cache()
    return snapshot()
