"""D-111 deterministic admission at the shared Reading content boundary.

Internal validation result stored in the existing article analysis, not a new
content model. No provider, confidence score or learner request can grant rights.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

from writing_coach.reading_processing import normalize_url

ADMISSION_VERSION = "reading-admission/1"


def source_origin_matches(source: Mapping[str, Any], canonical_url: str) -> bool:
    """A registry policy may cover fetched URLs only on its explicit origin.

    Both sides are compared in the one canonical spelling `normalize_url` gives a
    document address (lower-case host, no `www.`): a canonical URL is stored in
    that spelling, so a base URL left as typed (`https://www.gutenberg.org`)
    would otherwise never match its own texts."""
    try:
        origin = urlsplit(normalize_url(str(source.get("base_url") or "")))
        url = urlsplit(normalize_url(canonical_url))
        return bool(origin.hostname and url.hostname and origin.scheme in {"http", "https"}
                    and (origin.scheme, origin.hostname.casefold(), origin.port or (443 if origin.scheme == "https" else 80))
                    == (url.scheme, url.hostname.casefold(), url.port or (443 if url.scheme == "https" else 80)))
    except ValueError:
        return False


def automatic_admission(
    *, source: Mapping[str, Any], snapshot: Mapping[str, Any], language: str,
    body: str, analysis: Mapping[str, Any], targets: Sequence[Any],
    min_targets: int, max_targets: int,
) -> dict[str, Any]:
    reasons: list[str] = []
    policy = source.get("rights") or {}
    rights = snapshot.get("rights") or {}
    if source.get("state") != "active":
        reasons.append("source_not_active")
    if policy.get("automation_allowed") is not True:
        reasons.append("automation_not_allowed")
    if policy.get("can_republish") is not True or rights.get("can_republish") is not True:
        reasons.append("rights_not_cleared")
    if language not in {"en", "zh"} or language not in (source.get("languages") or []):
        reasons.append("source_language_mismatch")
    if snapshot.get("superseded_at"):
        reasons.append("source_superseded")
    if snapshot.get("body") != body or snapshot.get("language") != language:
        reasons.append("source_snapshot_mismatch")
    if "attribution_required" not in rights:
        reasons.append("attribution_unknown")
    elif rights["attribution_required"] and not (
        snapshot.get("author") or snapshot.get("canonical_url")
    ):
        reasons.append("attribution_missing")
    canonical_url = str(snapshot.get("canonical_url") or "")
    fetched_url = (snapshot.get("metadata") or {}).get("input_kind") == "url"
    if (fetched_url or (source.get("base_url") and canonical_url)) and not source_origin_matches(source, canonical_url):
        reasons.append("source_origin_mismatch")
    issues = analysis.get("quality_issues")
    if not isinstance(issues, list):
        reasons.append("analysis_missing")
    else:
        reasons.extend(issues)
    normalized = body.casefold()
    forms: set[str] = set()
    if not min_targets <= len(targets) <= max_targets:
        reasons.append("target_count_invalid")
    for target in targets:
        form = target.canonical_form.strip().casefold()
        context = target.context.strip().casefold()
        if (not form or form in forms or not target.text.strip() or not context or context not in normalized
                or target.text.strip().casefold() not in context
                or target.target_type not in {"word", "phrase", "phrasal_verb", "collocation", "grammar"}):
            reasons.append("targets_invalid")
            break
        forms.add(form)
    reasons = list(dict.fromkeys(reasons))
    return {"version": ADMISSION_VERSION, "decision": "review" if reasons else "published", "reasons": reasons}
