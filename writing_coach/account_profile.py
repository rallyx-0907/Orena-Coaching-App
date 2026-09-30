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
    # True when the allowed set depends on the request's learning language and is supplied by the
    # caller from the language registry (declared_level). It fails closed: with no set supplied only
    # '' is allowed, and there is never an English fallback.
    dynamic: bool = False
    # True when the value lives on the account row (`users`), not on the per-language profile row.
    account_scoped: bool = False

    def allows(self, value: object, *, levels: tuple[str, ...] | None = None) -> bool:
        # Emptiness is the setting's own business: "no declared level yet" is a
        # real answer, while an empty support language is not one. The allowed
        # set or the validator decides, not a blanket rule here.
        if not isinstance(value, str):
            return False
        if self.dynamic:
            return value == '' or value in (levels or ())
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
    # The interface languages Orena is written in (static/orena/ui/copy.js, supportedLocales).
    # Independent of the support language (D-079); still not stored - its column is a gated migration.
    # D4 I3: stored on the account row (`users.interface_language`), written through the account
    # settings route with its own version token, never through the per-language profile PATCH.
    'interface_language': Setting(
        'interface_language', 'en', allowed=('en', 'zh', 'vi'), account_scoped=True
    ),
}

# Language-scoped: keyed by account incarnation + learning language. Switching
# language loads that language's answers; it never copies one into the other.
LANGUAGE_SETTINGS: dict[str, Setting] = {
    'goal': Setting('goal', 'everyday', allowed=('everyday', 'work', 'exam', 'voice')),
    'style': Setting('style', 'guided', allowed=('guided', 'examples', 'concise', 'deep')),
    'pinyin': Setting('pinyin', 'auto', allowed=('auto', 'on', 'off')),
    # The learner's self-declared current level for this learning language (D4 I1). Never written
    # by a projection and never reported as measured proficiency. The allowed set is the language
    # registry's list for the scope language, supplied by the caller (fails closed).
    'declared_level': Setting('declared_level', '', dynamic=True),
}

SUPPORTED_SETTINGS: dict[str, Setting] = {**ACCOUNT_SETTINGS, **LANGUAGE_SETTINGS}
# The subset a patch may actually write today.
STORED_SETTINGS: dict[str, Setting] = {
    name: setting for name, setting in SUPPORTED_SETTINGS.items() if setting.stored
}


def scope_of(account: object, incarnation: object, language: object) -> Scope:
    """The scope a request runs in, from three server-verified facts.

    All three are required and none is inferred. The incarnation in particular
    is *resolved* by the persistence adapter that owns the incarnation row and
    passed in here; this module used to derive it from the account's id and
    created_at, which made a pure decision layer the authority on an identity
    fact it cannot see - and it could not express the deletion barrier at all,
    because a barrier is a stored row.

    Language is required for the same reason as the account: language-scoped
    resources are authorized on both, so a missing one is refused rather than
    defaulted into somebody's English work.
    """
    identifier = str(account or '').strip()
    epoch = str(incarnation or '').strip()
    code = str(language or '').strip()
    if not identifier:
        raise ValueError('A verified account is required')
    if not epoch:
        raise ValueError('A resolved account incarnation is required')
    if not code:
        raise ValueError('A learning language is required')
    return Scope(identifier, epoch, code)


def result_admissible(captured: Scope, current: Scope) -> bool:
    """Whether work captured earlier may still be shown or written now.

    Signing out, switching account, deleting and re-registering, or changing
    learning language mid-flight all change the scope. A result that arrives
    afterwards belongs to the scope it was captured in and to no other.
    """
    return captured == current


# Review settings (D4 I13): per learning language, named columns, NULL = the client defaults.
# `target` and `cloze` are the modes the design's Review frame draws; `typing`/`dictation` are the
# keys the Settings screen toggles today. The registry is one place: any other key is dropped.
REVIEW_MODE_KEYS = ('typing', 'cloze', 'dictation')
REVIEW_NEW_PER_DAY = (0, 50)
REVIEW_LIMIT_PER_DAY = (20, 600)


def clamp_review_number(value: object, bounds: tuple[int, int]) -> int | None:
    """A review limit clamped to the bounds the client uses, or None when it is not a number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or value in (float('inf'), float('-inf')):
        return None
    return min(bounds[1], max(bounds[0], round(value)))


def clean_review_modes(value: object) -> dict[str, bool] | None:
    """Only registered mode keys with boolean values survive; nothing left means NULL (defaults)."""
    if not isinstance(value, Mapping):
        return None
    kept = {name: value[name] for name in REVIEW_MODE_KEYS if isinstance(value.get(name), bool)}
    return kept or None


def effective_settings(
    saved: Mapping[str, object],
    *,
    version: int,
    overrides: Mapping[str, object] | None = None,
    allowed_levels: tuple[str, ...] | None = None,
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
        if setting.allows(overrides.get(name), levels=allowed_levels):
            effective[name] = {
                'value': overrides[name],
                'source': SOURCE_SESSION,
                'version': version,
            }
            continue
        if setting.allows(saved.get(name), levels=allowed_levels):
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
    allowed_levels: tuple[str, ...] | None = None,
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
        if setting.account_scoped:
            # It has its own route and its own version token; a profile PATCH cannot carry it.
            raise PatchRejected('wrong_scope', current_version=current_version, field=name)
        if not setting.allows(value, levels=allowed_levels):
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
