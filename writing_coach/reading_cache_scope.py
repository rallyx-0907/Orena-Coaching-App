"""Who may reuse an on-demand Reading answer (PR-MON-7D1, H7-5 / D-MON-025).

The server alone decides a cache scope; nothing the client sends establishes one:

    server-verified public/published  -> the shared scope: shared in-process cache, shared persistent store
    learner/private                   -> the learner's account incarnation: in-process only, never persisted
    no incarnation available          -> no learner caching at all (never a global learner cache)

A client `content_id` such as `article:<id>`, a `published` flag, a content type or a source id is only a claim. It
becomes the shared scope when the published article it names exists in the server's own repository and every text
the request derives from is part of that article.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from writing_coach.reading_derived import normalize_text

_log = logging.getLogger(__name__)

ARTICLE_PREFIX = "article:"


@dataclass(frozen=True)
class CacheScope:
    """`namespace` "" is the shared scope, `inc:<id>` one account incarnation, None no caching scope at all."""

    namespace: str | None

    @property
    def shared(self) -> bool:
        return self.namespace == ""


SHARED = CacheScope("")
UNSCOPED = CacheScope(None)

_incarnation_of: Callable[[str], str | None] | None = None
_published_article: Callable[[str], Mapping[str, Any] | None] | None = None


def configure(
    *,
    incarnation_of: Callable[[str], str | None] | None,
    published_article: Callable[[str], Mapping[str, Any] | None] | None,
) -> None:
    """`incarnation_of(user_key)`: the account's active incarnation or None (never creates one).
    `published_article(article_id)`: the article from the server's repository, only when it is published."""

    global _incarnation_of, _published_article
    _incarnation_of = incarnation_of
    _published_article = published_article


def learner_scope(user_key: str | None = None) -> CacheScope:
    """The current learner's incarnation scope, or `UNSCOPED` when no incarnation can be read safely."""

    from writing_coach.core.request_context import current_user_key

    if _incarnation_of is None:
        return UNSCOPED
    key = current_user_key() if user_key is None else user_key
    try:
        incarnation = _incarnation_of(key)
    except Exception:  # noqa: BLE001 - an unreadable account backbone means no learner cache, never a global one
        _log.warning("reading cache: no incarnation for the request; learner caching skipped", exc_info=True)
        return UNSCOPED
    return CacheScope(f"inc:{incarnation}") if incarnation else UNSCOPED


def published_text(content_id: str | None) -> str | None:
    """The normalized title and body of the published article `content_id` names, from the server's repository;
    None for anything else (no prefix, an unknown or unpublished id, a learner's own content, an unreadable store)."""

    value = str(content_id or "")
    if not value.startswith(ARTICLE_PREFIX) or _published_article is None:
        return None
    article_id = value[len(ARTICLE_PREFIX):]
    if not article_id:
        return None
    try:
        article = _published_article(article_id)
    except Exception:  # noqa: BLE001 - unverifiable is not published
        _log.warning("reading cache: published article could not be read; treated as learner text", exc_info=True)
        return None
    if not article:
        return None
    return normalize_text(f"{article.get('title') or ''}\n{article.get('body') or ''}")


def scope_for(content_id: str | None, texts: Iterable[str]) -> CacheScope:
    """The shared scope only when `content_id` is a published article that contains every one of `texts`;
    otherwise the learner's incarnation scope (or `UNSCOPED`)."""

    published = published_text(content_id)
    if published is not None:
        wanted = [normalize_text(text) for text in texts]
        if wanted and all(text and text in published for text in wanted):
            return SHARED
    return learner_scope()
