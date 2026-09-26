"""I1 account/profile adapter contract. Pure decisions; no database or session.

Counterexamples for ORENA_ACCOUNT_DATA_ARCHITECTURE sections 1-3: server-owned
scope, effective settings as {value, source, version}, patch semantics that
cannot silently erase, and results that cannot cross an account, a language or
an incarnation.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from writing_coach.reference_backbone import Scope  # noqa: E402
from writing_coach.account_profile import (  # noqa: E402
    ACCOUNT_SETTINGS,
    STORED_SETTINGS,
    LANGUAGE_SETTINGS,
    PatchRejected,
    effective_settings,
    patch_profile,
    result_admissible,
    scope_of,
)


class ScopeIsServerOwned(unittest.TestCase):
    """Scope is assembled from three server-verified facts and no client field.

    The incarnation is one of them, and it is *resolved* elsewhere - by the
    persistence adapter that owns the incarnation row - and passed in. This
    module used to derive it from the account's id and created_at, which made a
    pure decision layer the authority on an identity fact it could not see.
    """

    def test_scope_is_built_from_verified_identity_not_a_client_field(self):
        scope = scope_of('acct-1', 'inc-7f3a', 'en')
        self.assertEqual(scope.account, 'acct-1')
        self.assertEqual(scope.incarnation, 'inc-7f3a')
        self.assertEqual(scope.language, 'en')

    def test_an_account_without_verified_identity_has_no_scope(self):
        for account in ('', None, '   '):
            with self.assertRaises(ValueError):
                scope_of(account, 'inc-1', 'en')

    def test_an_unresolved_incarnation_is_refused_rather_than_derived(self):
        # No fallback: a caller that has not resolved the incarnation cannot
        # have one invented for it out of the account row.
        for incarnation in ('', None, '   '):
            with self.assertRaises(ValueError):
                scope_of('acct-1', incarnation, 'en')

    def test_a_missing_learning_language_is_not_guessed(self):
        with self.assertRaises(ValueError):
            scope_of('acct-1', 'inc-1', '')

    def test_this_module_cannot_reach_a_database(self):
        # Checked on imports rather than on words: "session" is also the name of
        # a preference source here, and a substring search would fail on the
        # product's own vocabulary rather than on a storage dependency.
        import ast

        source = (Path(__file__).resolve().parents[1]
                  / 'writing_coach' / 'account_profile.py').read_text(encoding='utf-8')
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        for name in imported:
            self.assertFalse(
                name.startswith(('sqlalchemy', 'alembic', 'psycopg'))
                or '.persistence' in name,
                f'the decision layer imported {name!r}; storage lives in the adapter',
            )


class ResultsCannotCrossAScope(unittest.TestCase):
    def setUp(self):
        self.en = Scope('acct-1', 'inc-1', 'en')

    def test_a_result_from_the_previous_account_cannot_enter_the_new_one(self):
        self.assertFalse(result_admissible(self.en, Scope('acct-2', 'inc-1', 'en')))

    def test_a_result_from_the_previous_incarnation_cannot_enter_the_new_one(self):
        self.assertFalse(result_admissible(self.en, Scope('acct-1', 'inc-2', 'en')))

    def test_an_english_result_cannot_enter_the_chinese_session(self):
        self.assertFalse(result_admissible(self.en, Scope('acct-1', 'inc-1', 'zh')))

    def test_the_same_scope_still_admits_its_own_result(self):
        self.assertTrue(result_admissible(self.en, Scope('acct-1', 'inc-1', 'en')))


class EffectiveSettings(unittest.TestCase):
    def test_every_supported_setting_declares_a_product_default(self):
        for name, setting in {**ACCOUNT_SETTINGS, **LANGUAGE_SETTINGS}.items():
            self.assertIsNotNone(setting.default, f'{name} has no declared default')
            self.assertTrue(setting.allows(setting.default), f'{name} default is not valid')

    def test_an_unsaved_setting_reports_the_declared_default_as_its_source(self):
        effective = effective_settings({}, version=0)
        self.assertEqual(effective['goal']['value'], LANGUAGE_SETTINGS['goal'].default)
        self.assertEqual(effective['goal']['source'], 'default')
        self.assertEqual(effective['goal']['version'], 0)

    def test_a_saved_preference_beats_the_default_and_carries_the_version(self):
        effective = effective_settings({'goal': 'exam'}, version=7)
        self.assertEqual(effective['goal']['value'], 'exam')
        self.assertEqual(effective['goal']['source'], 'saved')
        self.assertEqual(effective['goal']['version'], 7)

    def test_a_session_override_beats_a_saved_preference_and_is_marked_ephemeral(self):
        effective = effective_settings({'goal': 'exam'}, version=7, overrides={'goal': 'voice'})
        self.assertEqual(effective['goal']['value'], 'voice')
        self.assertEqual(effective['goal']['source'], 'session')

    def test_an_invalid_saved_value_falls_back_to_the_default_rather_than_serving_it(self):
        effective = effective_settings({'goal': 'not-a-goal'}, version=3)
        self.assertEqual(effective['goal']['value'], LANGUAGE_SETTINGS['goal'].default)
        self.assertEqual(effective['goal']['source'], 'default')

    def test_an_invalid_session_override_does_not_override(self):
        effective = effective_settings({'goal': 'exam'}, version=3, overrides={'goal': 'nonsense'})
        self.assertEqual(effective['goal']['value'], 'exam')
        self.assertEqual(effective['goal']['source'], 'saved')

    def test_a_declared_level_is_a_goal_and_never_reports_itself_as_measured(self):
        effective = effective_settings({'declared_level': 'B2'}, version=2)
        self.assertEqual(effective['declared_level']['value'], 'B2')
        self.assertIn(effective['declared_level']['source'], {'saved', 'default'})

    def test_support_language_and_interface_language_are_independent_settings(self):
        self.assertIn('support_language', ACCOUNT_SETTINGS)
        self.assertIn('interface_language', ACCOUNT_SETTINGS)
        effective = effective_settings(
            {'support_language': 'vi', 'interface_language': 'zh'}, version=1
        )
        self.assertEqual(effective['support_language']['value'], 'vi')
        self.assertEqual(effective['interface_language']['value'], 'zh')

    def test_account_wide_settings_are_not_keyed_by_the_learning_language(self):
        # Interface and support language follow the person, not the language
        # they happen to be learning this session.
        for name in ('support_language', 'interface_language'):
            self.assertIn(name, ACCOUNT_SETTINGS)
            self.assertNotIn(name, LANGUAGE_SETTINGS)
        for name in ('goal', 'style', 'pinyin', 'declared_level'):
            self.assertIn(name, LANGUAGE_SETTINGS)
            self.assertNotIn(name, ACCOUNT_SETTINGS)


class SettingsWithoutStorageAreHonestAboutIt(unittest.TestCase):
    """Two settings the contract names have no column in the current schema.

    A declared target level and an account-wide interface language are both
    part of the profile contract, and neither can be persisted until an
    authorized additive migration exists. Accepting a patch for one and
    dropping it on the way to the repository would be the worst of the three
    available behaviours, so the refusal says which problem it is.
    """

    def test_a_setting_with_no_column_is_marked_unstored(self):
        self.assertNotIn('declared_level', STORED_SETTINGS)
        self.assertNotIn('interface_language', STORED_SETTINGS)

    def test_the_settings_that_do_have_columns_are_still_writable(self):
        for name in ('goal', 'style', 'pinyin', 'support_language'):
            self.assertIn(name, STORED_SETTINGS)

    def test_patching_an_unstored_setting_is_refused_as_such(self):
        with self.assertRaises(PatchRejected) as caught:
            patch_profile({'goal': 'exam'}, {'declared_level': 'B2'},
                          expected_version=1, current_version=1)
        self.assertEqual(caught.exception.reason, 'not_yet_stored')
        self.assertEqual(caught.exception.field, 'declared_level')

    def test_an_unstored_setting_still_reads_as_a_declared_default(self):
        # The learner is told what it currently is, which is "not set", rather
        # than the setting vanishing from the profile.
        effective = effective_settings({}, version=0)
        self.assertIn('declared_level', effective)
        self.assertEqual(effective['declared_level']['source'], 'default')

    def test_an_unstored_setting_can_still_be_overridden_for_the_session(self):
        # The interface language lives on the device today, so the device
        # supplies it as an override and the profile reports it truthfully.
        effective = effective_settings({}, version=0, overrides={'interface_language': 'zh'})
        self.assertEqual(effective['interface_language']['value'], 'zh')
        self.assertEqual(effective['interface_language']['source'], 'session')

    def test_every_written_interface_language_is_allowed_and_none_is_the_support_language(self):
        # D-079: the interface is chosen on its own - Vietnamese chrome with English support, or
        # English chrome with Vietnamese support - and choosing it never touches the support language.
        for code in ('en', 'zh', 'vi'):
            effective = effective_settings(
                {'support_language': 'en' if code != 'en' else 'vi'}, version=1,
                overrides={'interface_language': code},
            )
            self.assertEqual(effective['interface_language']['value'], code)
            self.assertNotEqual(effective['support_language']['value'], code)
        self.assertNotIn('interface_language', STORED_SETTINGS)


class PatchCannotSilentlyErase(unittest.TestCase):
    def setUp(self):
        self.saved = {'goal': 'exam', 'style': 'deep', 'pinyin': 'off'}

    def test_a_patch_that_omits_a_field_preserves_it(self):
        merged, version = patch_profile(self.saved, {'pinyin': 'on'}, expected_version=4, current_version=4)
        self.assertEqual(merged['goal'], 'exam', 'an omitted field was erased')
        self.assertEqual(merged['style'], 'deep')
        self.assertEqual(merged['pinyin'], 'on')
        self.assertEqual(version, 5, 'a committed patch advances the version')

    def test_an_unsupported_field_is_refused_and_nothing_is_written(self):
        with self.assertRaises(PatchRejected) as caught:
            patch_profile(self.saved, {'role': 'admin'}, expected_version=4, current_version=4)
        self.assertEqual(caught.exception.reason, 'unsupported_field')

    def test_an_invalid_value_is_refused_rather_than_stored(self):
        with self.assertRaises(PatchRejected) as caught:
            patch_profile(self.saved, {'goal': 'whatever'}, expected_version=4, current_version=4)
        self.assertEqual(caught.exception.reason, 'invalid_value')

    def test_a_stale_expected_version_is_a_conflict_and_writes_nothing(self):
        with self.assertRaises(PatchRejected) as caught:
            patch_profile(self.saved, {'goal': 'work'}, expected_version=3, current_version=4)
        self.assertEqual(caught.exception.reason, 'version_conflict')
        self.assertEqual(caught.exception.current_version, 4)
        self.assertEqual(self.saved['goal'], 'exam', 'a rejected patch must not mutate state')

    def test_creating_a_profile_expects_the_absent_version(self):
        merged, version = patch_profile({}, {'goal': 'work'}, expected_version=0, current_version=0)
        self.assertEqual(merged['goal'], 'work')
        self.assertEqual(version, 1)

    def test_an_opaque_version_token_is_compared_and_minted_by_the_caller(self):
        # The learner profile has no version column and none is authorized yet,
        # so the runtime uses its last-updated stamp as the concurrency token.
        # The module compares tokens; it cannot invent the next one, because
        # only the caller holds the clock.
        merged, version = patch_profile(
            self.saved,
            {'goal': 'work'},
            expected_version='2026-09-08T10:00:00+07:00',
            current_version='2026-09-08T10:00:00+07:00',
            next_version='2026-09-08T11:30:00+07:00',
        )
        self.assertEqual(merged['goal'], 'work')
        self.assertEqual(merged['style'], 'deep', 'the omitted field survived')
        self.assertEqual(version, '2026-09-08T11:30:00+07:00')

    def test_a_stale_opaque_token_is_a_conflict(self):
        with self.assertRaises(PatchRejected) as caught:
            patch_profile(
                self.saved,
                {'goal': 'work'},
                expected_version='2026-09-08T09:00:00+07:00',
                current_version='2026-09-08T10:00:00+07:00',
                next_version='2026-09-08T11:30:00+07:00',
            )
        self.assertEqual(caught.exception.reason, 'version_conflict')
        self.assertEqual(caught.exception.current_version, '2026-09-08T10:00:00+07:00')

    def test_a_non_integer_version_without_a_successor_is_a_programming_error(self):
        with self.assertRaises(ValueError):
            patch_profile(
                self.saved, {'goal': 'work'},
                expected_version='2026-09-08T10:00:00+07:00',
                current_version='2026-09-08T10:00:00+07:00',
            )

    def test_an_empty_patch_is_refused_rather_than_bumping_the_version(self):
        with self.assertRaises(PatchRejected) as caught:
            patch_profile(self.saved, {}, expected_version=4, current_version=4)
        self.assertEqual(caught.exception.reason, 'empty_patch')


if __name__ == '__main__':
    unittest.main(verbosity=2)
