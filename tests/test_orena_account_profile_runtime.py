"""I1 runtime adapter: the learner profile a surface actually reads and patches.

The pure decisions live in `writing_coach/account_profile.py` and are covered by
`scripts/test_orena_account_profile.py`. These hold the seam between those
decisions and the repository the product already has - in particular that a
patch naming one setting cannot reset the others, which is what the previous
whole-profile PUT did to any client that sent less than everything.
"""
import pytest

from writing_coach.becoming_memory import (
    ProfilePatchIn,
    configure_becoming_memory,
    get_learner_profile,
    patch_learner_profile,
)


class FakeProfileRepository:
    """Only the two profile methods; nothing here needs a database."""

    def __init__(self, record=None):
        self.record = dict(record) if record else None
        self.writes = []

    def get_profile_record(self):
        return dict(self.record) if self.record else None

    def upsert_profile_record(self, values):
        self.writes.append(dict(values))
        self.record = dict(values)


SAVED = {
    "goal": "exam",
    "style": "deep",
    "pinyin": "off",
    "native_language": "vi",
    "theme_preset": "editorial",
    "created_at": "2026-01-01T00:00:00+07:00",
    "updated_at": "2026-09-01T10:00:00+07:00",
}


@pytest.fixture
def repository():
    repo = FakeProfileRepository(SAVED)
    configure_becoming_memory(repo)
    return repo


def test_read_reports_each_setting_with_its_value_source_and_version(repository):
    profile = get_learner_profile()
    settings = profile["settings"]
    assert settings["goal"] == {
        "value": "exam",
        "source": "saved",
        "version": SAVED["updated_at"],
    }
    # An unsaved setting says it is a product default rather than pretending
    # the learner chose it.
    assert settings["declared_level"]["source"] == "default"
    assert profile["version"] == SAVED["updated_at"]


def test_read_keeps_the_flat_shape_existing_surfaces_already_consume(repository):
    profile = get_learner_profile()
    for key in ("goal", "style", "pinyin", "native_language", "support_language", "theme_preset"):
        assert key in profile, f"{key} disappeared from the profile contract"
    assert profile["goal"] == "exam"


def test_patching_one_setting_leaves_the_others_alone(repository):
    before = get_learner_profile()
    patch_learner_profile(ProfilePatchIn(pinyin="on", expected_version=before["version"]))
    after = get_learner_profile()
    assert after["pinyin"] == "on"
    assert after["goal"] == "exam", "a setting nobody mentioned was reset"
    assert after["style"] == "deep"
    assert after["theme_preset"] == "editorial", "the theme preset is not this domain's to change"


def test_a_patch_advances_the_version_so_the_next_writer_sees_it(repository):
    before = get_learner_profile()
    patch_learner_profile(ProfilePatchIn(goal="work", expected_version=before["version"]))
    after = get_learner_profile()
    assert after["version"] != before["version"]


def test_a_second_writer_holding_the_old_version_is_refused(repository):
    stale = get_learner_profile()["version"]
    patch_learner_profile(ProfilePatchIn(goal="work", expected_version=stale))
    with pytest.raises(Exception) as caught:
        patch_learner_profile(ProfilePatchIn(style="concise", expected_version=stale))
    assert getattr(caught.value, "status_code", None) == 409
    assert get_learner_profile()["style"] == "deep", "a refused patch still wrote"


def test_an_unsupported_setting_is_refused_rather_than_stored(repository):
    version = get_learner_profile()["version"]
    with pytest.raises(Exception) as caught:
        patch_learner_profile(ProfilePatchIn(theme_preset="sage", expected_version=version))
    assert getattr(caught.value, "status_code", None) in (400, 422)


def test_an_empty_patch_is_refused_rather_than_touching_the_record(repository):
    version = get_learner_profile()["version"]
    with pytest.raises(Exception):
        patch_learner_profile(ProfilePatchIn(expected_version=version))
    assert repository.writes == []


def test_a_profile_that_does_not_exist_yet_is_created_from_the_absent_version():
    repo = FakeProfileRepository(None)
    configure_becoming_memory(repo)
    profile = get_learner_profile()
    assert profile["version"] == ""
    patch_learner_profile(ProfilePatchIn(goal="work", expected_version=""))
    assert get_learner_profile()["goal"] == "work"


def test_support_language_resolves_through_its_own_contract(repository):
    profile = get_learner_profile()
    assert profile["support_language"], "a support language must always resolve"
    assert profile["settings"]["support_language"]["value"] == "vi"
