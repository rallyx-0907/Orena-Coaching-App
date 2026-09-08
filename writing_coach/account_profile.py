"""Account scope and learner preferences, as decisions rather than storage.

I1 of the backbone integration gates, against ORENA_ACCOUNT_DATA_ARCHITECTURE
sections 1-3. Three things live here and nothing else:

  * the scope a request actually runs in, derived on the server from verified
    identity - never from a field the client sent;
  * what a preference currently *is*, as `{value, source, version}`, so a
    surface can tell a saved choice from a product default from a session
    override without re-deriving the precedence itself;
  * whether a patch may be applied, so an omitted field cannot be erased and a
    stale writer cannot overwrite a newer one.

No database, session, HTTP or transaction. Callers own authorization, locking
and the actual write; these functions decide, they do not persist. Scope is
`reference_backbone.Scope` rather than a second shape that means the same
thing.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from writing_coach.core.support_languages import (
    AVAILABLE_SUPPORT_LANGUAGES,
    configured_default,
    normalize_language_tag,
)
from writing_coach.reference_backbone import Scope

# Where a value came from, most authoritative first. A surface may show the
# difference; it must never have to work the order out again.
SOURCE_SESSION = 'session'
SOURCE_SAVED = 'saved'
SOURCE_DEFAULT = 'default'


@dataclass(frozen=True)
class Setting:
    """One supported preference: what it may be, and what it is when unset.

    `default` is the declared product default. It lives here so that a room
    cannot quietly introduce a different one - the architecture asks for
    defaults from the registry, not from scattered constants.
    """

    name: str
    default: str
    allowed: tuple[str, ...] | None = None
    validator: Callable[[str], bool] | None = None
    # Whether the account can persist this today. Two settings the contract
    # names - a declared target level and an account-wide interface language -
    # have no column yet, and adding one is a gated migration. They are still
    # declared here so a surface can read and override them; what they cannot
    # do is be saved and quietly dropped on the way to the repository.
    stored: bool = True

    def allows(self, value: object) -> bool:
        # Emptiness is the setting's own business: "no declared level yet" is a
        # real answer, while an empty support language is not one. The allowed
        # set or the validator decides, not a blanket rule here.
        if not isinstance(value, str):
            return False
        if self.allowed is not None:
            return value in self.allowed
        return bool(self.validator and self.validator(value))


def _supported_support_language(value: str) -> bool:
    return normalize_language_tag(value) in AVAILABLE_SUPPORT_LANGUAGES


# Account-wide: these follow the person, not the language being learned. Keying
# them by learning language is the mistake the architecture calls out by name.
ACCOUNT_SETTINGS: dict[str, Setting] = {
    'support_language': Setting(
        'support_language', configured_default(), validator=_supported_support_language
    ),
    'interface_language': Setting(
        'interface_language', 'en', allowed=('en', 'zh'), stored=False
    ),
}

# Language-scoped: keyed by account incarnation + learning language. Switching
# language loads that language's answers; it never copies one into the other.
LANGUAGE_SETTINGS: dict[str, Setting] = {
    'goal': Setting('goal', 'everyday', allowed=('everyday', 'work', 'exam', 'voice')),
    'style': Setting('style', 'guided', allowed=('guided', 'examples', 'concise', 'deep')),
    'pinyin': Setting('pinyin', 'auto', allowed=('auto', 'on', 'off')),
    # A declared level is what the learner is aiming at. It is never written by
    # a projection and never reported as measured proficiency.
    'declared_level': Setting(
        'declared_level', '', allowed=('', 'A1', 'A2', 'B1', 'B2', 'C1', 'C2'), stored=False
    ),
}

SUPPORTED_SETTINGS: dict[str, Setting] = {**ACCOUNT_SETTINGS, **LANGUAGE_SETTINGS}
# The subset a patch may actually write today.
STORED_SETTINGS: dict[str, Setting] = {
    name: setting for name, setting in SUPPORTED_SETTINGS.items() if setting.stored
}


def incarnation_of(account_row: Mapping[str, object]) -> str:
    """The account's access epoch, owned by the server.

    Deleting an account and signing in again produces a different account
    record, and everything scoped to the old one - commands, receipts, cursors,
    job scopes, caches - must stop matching. Until an authorized migration adds
    a durable incarnation column and its deletion barrier, the epoch is derived
    from facts the account row already carries and that a recreated row cannot
    reproduce. Derived, so it is stable for a given row and different for a new
    one; it is not a substitute for the barrier itself, which stays gated.
    """
    identifier = str(account_row.get('id') or '').strip()
    created = str(account_row.get('created_at') or '').strip()
    if not identifier:
        raise ValueError('An account incarnation needs a verified account record')
    return f'{identifier}@{created}' if created else identifier


def scope_of(account_row: Mapping[str, object], language: object) -> Scope:
    """The scope a request runs in.

    Both halves are required: language-scoped resources are authorized on
    account *and* learning language, so a missing language is refused rather
    than defaulted into someone's English work.
    """
    identifier = str(account_row.get('id') or '').strip()
    code = str(language or '').strip()
    if not identifier:
        raise ValueError('A verified account is required')
    if not code:
        raise ValueError('A learning language is required')
    return Scope(identifier, incarnation_of(account_row), code)


def result_admissible(captured: Scope, current: Scope) -> bool:
    """Whether work captured earlier may still be shown or written now.

    Signing out, switching account, deleting and re-registering, or changing
    learning language mid-flight all change the scope. A result that arrives
    afterwards belongs to the scope it was captured in and to no other.
    """
    return captured == current


def effective_settings(
    saved: Mapping[str, object],
    *,
    version: int,
    overrides: Mapping[str, object] | None = None,
) -> dict[str, dict[str, object]]:
    """Every supported setting as `{value, source, version}`.

    Precedence is temporary session override, then saved preference, then the
    declared default. A stored value that is no longer valid - a preset that
    was retired, a support language that is no longer available - falls back to
    the default and says so, rather than being served as though the learner had
    chosen it.
    """
    overrides = overrides or {}
    effective: dict[str, dict[str, object]] = {}
    for name, setting in SUPPORTED_SETTINGS.items():
        if setting.allows(overrides.get(name)):
            effective[name] = {
                'value': overrides[name],
                'source': SOURCE_SESSION,
                'version': version,
            }
            continue
        if setting.allows(saved.get(name)):
            effective[name] = {
                'value': saved[name],
                'source': SOURCE_SAVED,
                'version': version,
            }
            continue
        effective[name] = {
            'value': setting.default,
            'source': SOURCE_DEFAULT,
            'version': version,
        }
    return effective


class PatchRejected(Exception):
    """A patch that must not be applied, and why.

    `reason` is a stable key so a surface can say something true about it in
    either interface language rather than showing a sentence from the server.
    """

    def __init__(self, reason: str, *, current_version: int | None = None, field: str = ''):
        super().__init__(reason)
        self.reason = reason
        self.current_version = current_version
        self.field = field


def patch_profile(
    saved: Mapping[str, object],
    patch: Mapping[str, object],
    *,
    expected_version: object,
    current_version: object,
    next_version: object = None,
) -> tuple[dict[str, object], object]:
    """Merge named fields onto the saved profile, or refuse and change nothing.

    The endpoint this replaces accepted a whole profile with a default for
    every field, so a client that sent only the one setting it meant to change
    reset the rest to the product defaults. Here a field that is absent is
    absent: it keeps its saved value.

    Version 0 means the profile does not exist yet, matching the creation
    convention in `reference_backbone.mutation_decision`. Versions are compared
    for equality only, so an opaque token works as well as a counter - the
    learner profile has no version column and none is authorized yet, so the
    runtime uses its last-updated stamp.
    """
    if not patch:
        raise PatchRejected('empty_patch', current_version=current_version)
    for name, value in patch.items():
        setting = SUPPORTED_SETTINGS.get(name)
        if setting is None:
            raise PatchRejected('unsupported_field', current_version=current_version, field=name)
        if not setting.allows(value):
            raise PatchRejected('invalid_value', current_version=current_version, field=name)
        if not setting.stored:
            raise PatchRejected('not_yet_stored', current_version=current_version, field=name)
    if expected_version != current_version:
        raise PatchRejected('version_conflict', current_version=current_version)
    if next_version is None:
        # An integer version has an obvious successor. Anything else - the
        # learner profile's last-updated stamp, for one - is minted by whoever
        # holds the clock, so it has to be supplied rather than guessed at.
        if not isinstance(current_version, int) or isinstance(current_version, bool):
            raise ValueError('A non-integer version requires an explicit next_version')
        next_version = current_version + 1
    merged = {**dict(saved), **dict(patch)}
    return merged, next_version
