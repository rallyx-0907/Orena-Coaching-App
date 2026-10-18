"""What the account-deletion workflow (D-055 precondition b) must remove or reset for the D4 records.

Data only: no runtime deletion path exists and this adds none (D-055). The workflow, when it is built, reads
this. The `users` row SURVIVES deletion (the incarnation barrier and the journal anchor on it), so its new
columns are RESET, not deleted; rows keyed by the account are deleted explicitly; rows keyed by the kept
incarnation are NOT removed by any cascade and are deleted explicitly too (proposal 2.6).
"""
from __future__ import annotations

# Columns on the surviving `users` row, and the value each returns to.
USER_COLUMNS_TO_RESET = {
    "learning_language": "",
    "interface_language": "",
    "weekly_goal_days": None,
    "settings_updated_at": None,
}

# Owner tables keyed by the account (users.id): deleted for the deleted account.
ACCOUNT_KEYED_TABLES = (
    "user_language_profiles",  # declared_level, review settings, goal, style, support language
    "grammar_progress",  # completions and the last quiz result
    "listening_progress",
    "shadowing_progress",
    "speaking_attempts",
    "essays",  # and, through ON DELETE CASCADE, essay_review_history
    "library_items",  # including the saved place
    "saved_words",
    # Every other table keyed by `user_id` with a `language_code` (D-170: they decide which target languages the account
    # holds, so a recreated account must not inherit them). `users.id` survives deletion, so no cascade fires for them.
    "essay_revisions",
    "library_collections",
    "reading_ability_projections",
    "reading_attempts",
    "reading_legacy_sessions",
    "text_discussions",
    "vocabulary_decks",
)

# Owner tables keyed by the account through `account_id` (users.id): deleted for the deleted account. Their
# ON DELETE CASCADE never fires, because the `users` row survives deletion (review of migration 0026, finding 1).
ACCOUNT_ID_KEYED_TABLES = (
    "ai_cost_records",  # AI cost per account (AC-2): a recreated account must not inherit the deleted one's spend
)

# Deleted through their essay's cascade; listed so the enumeration is complete.
CASCADED_TABLES = {"essay_review_history": "essays"}

# Keyed by the account's incarnation, which is KEPT as the barrier: its cascade never fires.
INCARNATION_KEYED_TABLES = (
    "works",  # drafts, conversations, notes and highlights, private imports, typed responses
    "work_turns",
    "mutation_receipts",
    "change_records",
    "language_provenance",
    # Orena Memory (0035, ORENA_MEMORY.md §4.1, §4.4): items, the memory switch and version, and the suppression keys
    # a deleted item leaves. The suppressions hold no text and are deleted with the rest; they are never exported.
    "learner_memories",
    "learner_memory_suppressions",
    "learner_memory_state",
)

# File-based stores that hold learner-owned content outside PostgreSQL. A SQL deletion never reaches them, so the
# workflow must call the named remover for each (D-107: deleting an uploaded import removes its files too).
FILE_STORES = (
    {
        "name": "media_library",  # data/media_library/index.json (MEDIA_LIBRARY_ROOT) and the asset files it points at
        "owned": "entries with library='personal' and provider in ('upload', 'youtube') whose source.owner == owner_token(user_key), "
                 "in every learning language; their files under media/<provider_media_id>/ (original, thumbnail)",
        "remove_one": "writing_coach.media_library_api.delete_owned_media",
        "remove_account": "writing_coach.media_library_api.delete_all_owned_media",
    },
)
