"""Which target languages an account holds, read from what the server already stores (D-16R).

There is no table of "languages this account adopted", and none is added here (a new table or column is a schema
decision reserved to the human; see UI_BACKEND_GAPS QTA-7). What the server does keep, per account, is

  * the account's learning language (`users.learning_language`) - the one it chose last, so it holds that one even
    before it has written anything in it;
  * every row the learner owns that is scoped to a learning language: its profile (`user_language_profiles`: declared
    level, goals), its essays, progress, saved words, library, decks, discussions and reading attempts - every ORM
    table with both `user_id` (a foreign key to `users`) and `language_code`, found from the mapped metadata so that a
    table added later is counted without anyone remembering to list it; and
  * its works (drafts, conversations, notes) of the account's ACTIVE incarnation, which are scoped to a language too.

The union of their language codes is what the account HOLDS. It is derived from server data only - a client never
declares it - and it grows as the account uses a language. It is not a record of adoption: a learner who deletes
everything they wrote in a language and is not learning it any more no longer holds it. A recreated account (a new
incarnation, `users` row reset, learner rows deleted by the deletion workflow in `deletion_enumeration.py`) holds
nothing until it uses a language again.

This module reads; it does not decide. The limit is `writing_coach.product.language_limit`.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Table, select, text, union
from sqlalchemy.orm import Session

from writing_coach.persistence.ids import stable_uuid
from writing_coach.persistence.models import Base, User


def language_scoped_tables() -> tuple[Table, ...]:
    """Every mapped table that holds a learner's rows for one learning language: `user_id` -> `users.id` plus
    `language_code`. Content catalogues (grammar, vocabulary collections) have no `user_id` and are not here."""
    found: list[Table] = []
    for table in Base.metadata.sorted_tables:
        if table.name == User.__tablename__ or "language_code" not in table.c or "user_id" not in table.c:
            continue
        if any(fk.column.table.name == User.__tablename__ for fk in table.c.user_id.foreign_keys):
            found.append(table)
    return tuple(found)


_WORKS = text(
    "SELECT w.language_code FROM works w JOIN account_incarnations i ON i.id = w.incarnation_id "
    "WHERE i.user_id = :uid AND i.status = 'active' AND w.lifecycle <> 'deleted'"
)


def owned_languages(session: Session, user_id: uuid.UUID, *, with_works: bool = True) -> set[str]:
    """The language codes the account holds, casefolded; '' (never chosen) is not a language."""
    parts: list[Any] = [select(User.learning_language).where(User.id == user_id)]
    parts += [select(table.c.language_code).where(table.c.user_id == user_id).distinct()
              for table in language_scoped_tables()]
    codes = set(session.execute(union(*parts)).scalars())
    if with_works:
        codes |= set(session.execute(_WORKS, {"uid": user_id}).scalars())
    return {str(code).strip().casefold() for code in codes if str(code or "").strip()}


class PostgresLanguageOwnership:
    """The unlocked read (Plan & usage, the pre-check of a language switch); the write path reads inside the
    account's own transaction (`PostgresAuthRepository.update_account_settings`)."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def held(self, user_key: str) -> set[str]:
        with Session(self.engine) as session:
            return owned_languages(session, stable_uuid("user", user_key))
