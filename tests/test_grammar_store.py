"""The grammar content store: package reading and validation, import, review, rights, publish, learner reads, R5.

Hermetic (SQLite built by `create_all`, the CI backend); the PostgreSQL-specific guarantees (triggers, locks, the
lock-free migration) are in `scripts/rehearse_grammar_content_store.py` and `tests/test_grammar_store_postgres.py`.
Synthetic packages only (`tests/grammar_store_support.py`); the Grammar Lab corpus is never copied here.
"""
from __future__ import annotations

import copy
import io
import json
import stat
import zipfile

import pytest

from tests.grammar_store_support import FUNCTIONS, body, lm, manifest, package, sqlite_engine, zip_package
from writing_coach.grammar_store import contract
from writing_coach.grammar_store.package import PackageError, read_package, validate_package
from writing_coach.persistence.grammar_store_repository import (
    GrammarStoreRefusal,
    GrammarStoreRepository,
    parse_r5_key,
)

ADMIN = "admin@example.org"


def codes(data: bytes) -> set[str]:
    return {p.code for p in validate_package(read_package(data)).problems}


@pytest.fixture()
def repo(tmp_path):
    engine = sqlite_engine(tmp_path)
    yield GrammarStoreRepository(engine)
    engine.dispose()


def commit(repo, data: bytes, **kw):
    pkg = validate_package(read_package(data))
    return repo.commit_import(pkg, filename="p.zip", actor=ADMIN, echoed_hash=pkg.manifest.get("package_hash", ""),
                              **kw)


def accept_all(repo, outcome):
    repo.attest_batch(outcome.batch["id"], basis="orena_original", attestation="Orena's own text.", actor=ADMIN)
    for point in repo.list_points(review="imported"):
        for version in repo.admin_point(point["id"])["versions"]:
            if version["review_status"] == "imported":
                repo.review_version(version["id"], decision="accept", actor=ADMIN)


def version_id(repo, point_id: str, version: int = 1) -> str:
    return next(v["id"] for v in repo.admin_point(point_id)["versions"] if v["version"] == version)


# --- the boundary ------------------------------------------------------------------------------------------------------

def test_the_vendored_profile_is_pinned_and_canonical_json_reproduces_the_upstream_golden_vector():
    assert contract.content_hash(contract.profile_schema()) == contract.PROFILE_SCHEMA_HASH
    # Grammar Lab fixtures/export/golden_vector.json at 3579ece8: a synthetic vector, not corpus content.
    value = {"id": "zh.golden_vector", "version": 1, "status": "approved", "target_lang": "zh",
             "header": {"title": {"vi": "Trợ từ 了 (hoàn thành): hành động đã xong",
                                  "en": "The particle 了: completed action", "zh": "动态助词“了”"},
                        "native_title": "动态助词“了”", "native_title_pinyin": ["dòng", "tài", "zhù", "cí", "", "le", ""]},
             "examples": [{"text": "我昨天买了一本书。", "form": "affirmative",
                           "pinyin": ["wǒ", "zuó", "tiān", "mǎi", "le", "yī", "běn", "shū", ""],
                           "spans": [{"start": 0, "end": 1, "role": "subject"}, {"start": 3, "end": 4, "role": "verb"}],
                           "translation": {"vi": "Hôm qua tôi đã mua một cuốn sách.", "en": "I bought a book yesterday."}}],
             "sequence": 3, "optional": True, "note": None, "tags": ["ộ", "ữ", "ư"]}
    assert contract.content_hash(value) == "cf92888909aadba47cac25209a173fdf1fa9ee0f66dacd7e425b2326be19ee27"
    with pytest.raises(contract.CanonicalJSONError):
        contract.canonical_json({"a": 1.0})


def test_a_valid_package_reads_and_validates_clean():
    bodies = [body("en.past_simple", aliases=["a1-past-simple"])]
    data = package(bodies, r5_map=[{"r5_id": "a1-past-simple", "point_id": "en.past_simple", "disposition": "replaced",
                                    "is_primary": True}])
    assert codes(data) == set()


@pytest.mark.parametrize("mutate, code", [
    (lambda b: b.update(extra=1), "profile.schema"),
    (lambda b: b["header"].update(extra="x"), "profile.schema"),
    (lambda b: b.update(provenance={"model": "m"}), "profile.schema"),
    (lambda b: b.update(review={"reviewer": "x"}), "profile.schema"),
    (lambda b: b["header"]["title"].update({"zh-Hans": "x"}), "profile.schema"),
    (lambda b: b.update(target_lang="zh-Hans"), "profile.schema"),
    (lambda b: b.update(status="draft_ai"), "profile.schema"),
    (lambda b: b["header"].update(title={"vi": "Thử nghiệm", "en": "Thử nghiệm"}), "locale.en_placeholder"),
    (lambda b: b["quick_practice"][0].update(answer=5), "quick_practice.answer_out_of_range"),
    (lambda b: b["examples"][0]["spans"].append({"start": 3, "end": 99, "role": "object"}), "example.span_invalid"),
    (lambda b: b["header"].update(level={"framework": "cefr", "value": "B2", "rank": 4}), "header.level_mismatch"),
    (lambda b: b.update(prereqs=["en.unknown"]), "ref.unresolved"),
])
def test_each_mutated_body_is_rejected_with_its_own_code(mutate, code):
    b = body("en.past_simple")
    mutate(b)
    assert code in codes(package([b]))


@pytest.mark.parametrize("overrides, code", [
    ({"export_profile": "grammar-export-profile/2"}, "profile.unsupported"),
    ({"schema_version": "0.5"}, "profile.unsupported"),
    ({"profile_schema_hash": "0" * 64}, "profile.unsupported"),
    ({"source_dirty": True}, "source.dirty"),
    ({"validator": {"passed": False}}, "validator.not_passed"),
    ({"language": "ja"}, "language.unsupported"),
    ({"package_hash": "f" * 64}, "package.hash_mismatch"),
    ({"unexpected": 1}, "manifest.keys"),
])
def test_manifest_failures_reject_the_whole_batch(overrides, code):
    b = body("en.past_simple")
    assert code in codes(zip_package(manifest([b], **overrides), [b]))


def test_cross_point_rules():
    a = body("en.a", contrasts=["en.b"], prereqs=["en.b"])
    b = body("en.b", prereqs=["en.a"], sequence=2)
    assert {"contrasts.asymmetric", "prereqs.cycle"} <= codes(package([a, b]))
    lonely = body("en.c", function="fn.unknown")
    assert "function.missing" in codes(package([lonely]))
    no_zh = [{"id": "fn.talk_past", "title": {"vi": "Quá khứ thử", "en": "Past"}}]
    assert "function.label_incomplete" in codes(package([body("en.d")], functions=no_zh))


def test_files_hashes_and_listing_are_checked():
    a, b = body("en.a"), body("en.b", sequence=2)
    m = manifest([a])
    assert "points.unlisted_file" in codes(zip_package(m, [a, b]))
    assert "points.missing_file" in codes(zip_package(manifest([a, b]), [a]))
    tampered = copy.deepcopy(a)
    tampered["header"]["native_title"] = "changed after export"
    assert "point.hash_mismatch" in codes(zip_package(m, [tampered]))
    assert "functions.mismatch" in codes(zip_package(m, [a], functions=[]))


def test_r5_map_rules_follow_the_settled_contract():
    def r(rid, pid, disp, primary):
        return {"r5_id": rid, "point_id": pid, "disposition": disp, "is_primary": primary}
    primary = body("en.p", aliases=["r5-x"])
    secondary = body("en.s", r5_split=["r5-x"], sequence=2)
    ok = [r("r5-x", "en.p", "split_primary", True), r("r5-x", "en.s", "split_secondary", False)]
    assert codes(package([primary, secondary], r5_map=ok)) == set()
    assert "r5_map.split" in codes(package([primary, secondary], r5_map=ok[:1]))
    assert "r5_map.dropped_and_mapped" in codes(package([primary, secondary], r5_map=ok + [r("r5-x", None, "dropped", False)]))
    aliased_secondary = body("en.s", r5_split=["r5-x"], aliases=["r5-x"], sequence=2)
    assert "r5_map.alias" in codes(package([primary, aliased_secondary], r5_map=ok))
    assert "r5_map.missing" in codes(package([body("en.q", aliases=["r5-y"])]))
    assert "r5_map.alias" in codes(package([body("en.q")], r5_map=[r("r5-z", "en.q", "replaced", True)]))


def _zip(members: dict[str, bytes], *, symlink: str = "") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in members.items():
            info = zipfile.ZipInfo(name)
            if name == symlink:
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, raw)
    return buffer.getvalue()


@pytest.mark.parametrize("members, symlink, code", [
    ({"package.json": b"{}", "functions.json": b"[]", "../evil.json": b"{}"}, "", "package.member_refused"),
    ({"package.json": b"{}", "functions.json": b"[]", "points/a.json": b"{}", "notes.txt": b"x"}, "", "package.member_refused"),
    ({"package.json": b"{}", "functions.json": b"[]", "points/link.json": b"/etc/passwd"}, "points/link.json",
     "package.member_refused"),
    ({"package.json": b"{}", "functions.json": b"[]", "points/bomb.json": b" " * (2 * 1024 * 1024)}, "",
     "package.member_too_large"),
    ({"functions.json": b"[]"}, "", "package.member_missing"),
])
def test_hostile_zips_are_refused_while_reading(members, symlink, code):
    with pytest.raises(PackageError) as error:
        read_package(_zip(members, symlink=symlink))
    assert error.value.problems[0].code == code


def test_not_a_zip_and_too_many_members_and_deep_json():
    with pytest.raises(PackageError):
        read_package(b"plain text")
    many = {"package.json": b"{}", "functions.json": b"[]", **{f"points/p{i}.json": b"{}" for i in range(2001)}}
    with pytest.raises(PackageError) as error:
        read_package(_zip(many))
    assert error.value.problems[0].code == "package.too_many_members"
    with pytest.raises(PackageError) as error:  # deeper than the decoder can follow, still a clean refusal
        read_package(_zip({"package.json": b"[" * 200_000 + b"]" * 200_000, "functions.json": b"[]"}))
    assert error.value.problems[0].code == "package.json_too_deep"
    deep = b"[" * 70 + b"]" * 70
    with pytest.raises(PackageError) as error:
        read_package(_zip({"package.json": deep, "functions.json": b"[]"}))
    assert error.value.problems[0].code == "package.json_too_deep"


# --- import ------------------------------------------------------------------------------------------------------------

def test_import_commits_unpublished_unknown_rights_versions_and_is_idempotent(repo):
    data = package([body("en.a"), body("en.b", sequence=2)])
    dry = repo.validate_import(validate_package(read_package(data)))
    assert dry["ok"] and dry["diff"]["counts"]["new"] == 2 and repo.list_batches() == []  # a dry run writes nothing
    first = commit(repo, data)
    assert first.status == "imported" and first.batch["counts"]["new"] == 2
    point = repo.admin_point("en.a")
    assert point["lifecycle"] == "unpublished" and point["versions"][0]["rights_status"] == "unknown"
    assert point["versions"][0]["review_status"] == "imported"
    assert repo.catalog("en")["points"] == []  # imported content is never visible
    again = commit(repo, data)
    assert again.status == "already_imported" and again.batch["id"] == first.batch["id"]
    assert len(repo.list_batches()) == 1


def test_a_hard_failure_writes_a_rejected_receipt_and_no_content_and_a_corrected_upload_is_a_fresh_attempt(repo):
    b = body("en.a")
    bad = zip_package(manifest([b], validator={"passed": False}), [b])
    outcome = commit(repo, bad)
    assert outcome.status == "rejected" and outcome.batch["status"] == "rejected"
    assert outcome.batch["refusals"][0]["code"] == "validator.not_passed"
    with pytest.raises(GrammarStoreRefusal):
        repo.admin_point("en.a")
    assert commit(repo, package([b])).status == "imported"


def test_the_echoed_hash_must_match(repo):
    pkg = validate_package(read_package(package([body("en.a")])))
    with pytest.raises(GrammarStoreRefusal) as error:
        repo.commit_import(pkg, filename="p.zip", actor=ADMIN, echoed_hash="0" * 64)
    assert error.value.code == "grammar_package_hash_mismatch"


def test_per_point_refusals(repo):
    outcome = commit(repo, package([body("en.a"), body("en.b", sequence=2)]))
    repo.attest_batch(outcome.batch["id"], basis="orena_original", attestation="Orena's own.", actor=ADMIN)
    repo.review_version(version_id(repo, "en.a"), decision="accept", actor=ADMIN)
    repo.review_version(version_id(repo, "en.b"), decision="reject", actor=ADMIN, reason="wrong example")
    with pytest.raises(GrammarStoreRefusal) as error:
        repo.review_version(version_id(repo, "en.b"), decision="accept", actor=ADMIN)
    assert error.value.code == "grammar_review_closed"

    def states(data):
        result = commit(repo, data)
        assert result.status == "imported", result.report
        return {row["id"]: row["state"] for row in result.report["diff"]["points"]}

    assert states(package([body("en.a", title="Changed"), body("en.c", sequence=3)], set_version="t2")) == {
        "en.a": "refused:version_not_bumped", "en.c": "new"}
    assert states(package([body("en.a", version=2)], set_version="t3")) == {"en.a": "refused:content_already_stored"}
    assert states(package([body("en.b", version=2, sequence=2)], set_version="t4")) == {
        "en.b": "refused:content_previously_rejected"}
    assert states(package([body("en.b", version=3, sequence=2, title="Fixed")], set_version="t5")) == {"en.b": "changed"}
    assert states(package([body("en.b", version=2, sequence=2, title="Older")], set_version="t6")) == {
        "en.b": "refused:version_lower_than_stored"}
    assert states(package([body("en.a"), body("en.c", sequence=3)], set_version="t7")) == {
        "en.a": "unchanged", "en.c": "unchanged"}


def test_external_references_must_resolve_in_the_store(repo):
    child = body("en.child", prereqs=["en.parent"])
    outcome = commit(repo, package([child], external=["en.parent"]))
    assert outcome.status == "rejected"
    assert outcome.batch["refusals"][0]["code"] == "ref.external_unresolved"
    accept_all(repo, commit(repo, package([body("en.parent")], set_version="p")))
    assert commit(repo, package([child], external=["en.parent"], set_version="c")).status == "imported"


# --- review, rights, publish -------------------------------------------------------------------------------------------

def test_the_publish_gate_needs_accept_and_cleared_and_the_attestation_may_come_after_import(repo):
    outcome = commit(repo, package([body("en.a")]))
    vid = version_id(repo, "en.a")
    with pytest.raises(GrammarStoreRefusal) as error:
        repo.publish([("en.a", vid)], actor=ADMIN)
    assert error.value.code == "grammar_not_accepted"
    repo.review_version(vid, decision="accept", actor=ADMIN)
    with pytest.raises(GrammarStoreRefusal) as error:
        repo.publish([("en.a", vid)], actor=ADMIN)
    assert error.value.code == "grammar_rights_not_cleared"
    repo.attest_batch(outcome.batch["id"], basis="orena_original", attestation="Written by Orena.", actor=ADMIN)
    repo.publish([("en.a", vid)], actor=ADMIN)
    catalog = repo.catalog("en")
    assert [p["id"] for p in catalog["points"]] == ["en.a"] and catalog["catalog_revision"] == 1
    assert catalog["functions"][0]["title"]["zh"] == "谈论过去"
    with pytest.raises(GrammarStoreRefusal):
        repo.attest_batch(outcome.batch["id"], basis="licensed", attestation="again", actor=ADMIN)


def test_the_served_body_is_whitelisted_and_published_only(repo):
    accept_all(repo, commit(repo, package([body("en.a")])))
    assert repo.published("en", "en.a") is None
    repo.publish([("en.a", version_id(repo, "en.a"))], actor=ADMIN)
    served = repo.published("en", "en.a")
    assert "source_refs" not in served["point"] and served["point"]["id"] == "en.a"
    assert set(served["point"]) <= contract.SERVED_KEYS
    assert repo.published("zh", "en.a") is None  # language-scoped


def test_rollback_republishes_the_superseded_version(repo):
    accept_all(repo, commit(repo, package([body("en.a")])))
    v1 = version_id(repo, "en.a")
    repo.publish([("en.a", v1)], actor=ADMIN)
    accept_all(repo, commit(repo, package([body("en.a", version=2, title="Two")], set_version="t2")))
    v2 = version_id(repo, "en.a", 2)
    repo.publish([("en.a", v2)], actor=ADMIN)
    versions = {v["version"]: v for v in repo.admin_point("en.a")["versions"]}
    assert versions[1]["review_status"] == "accepted" and versions[1]["superseded_at"] and not versions[1]["is_published"]
    repo.publish([("en.a", v1)], actor=ADMIN, reason="rollback")
    versions = {v["version"]: v for v in repo.admin_point("en.a")["versions"]}
    assert versions[1]["is_published"] and versions[1]["superseded_at"] is None
    assert versions[2]["superseded_at"] and versions[2]["review_status"] == "accepted"
    assert repo.published("en", "en.a")["version"] == 1
    assert repo.catalog("en")["catalog_revision"] == 3


def test_dangling_references_block_publish_unless_a_bulk_publish_satisfies_them_or_one_point_overrides(repo):
    a = body("en.a", contrasts=["en.b"])
    b = body("en.b", contrasts=["en.a"], sequence=2)
    accept_all(repo, commit(repo, package([a, b])))
    va, vb = version_id(repo, "en.a"), version_id(repo, "en.b")
    with pytest.raises(GrammarStoreRefusal) as error:
        repo.publish([("en.a", va)], actor=ADMIN)
    assert error.value.code == "grammar_references_unpublished" and error.value.context["dangling"] == {"en.a": ["en.b"]}
    repo.publish([("en.a", va)], actor=ADMIN, override_references=True)
    assert repo.admin_point("en.a")["events"][-1]["changes"]["override_references"] == ["en.b"]
    repo.set_point_status("en.a", action="unpublish", actor=ADMIN)
    repo.publish([("en.a", va), ("en.b", vb)], actor=ADMIN)
    assert {p["id"] for p in repo.catalog("en")["points"]} == {"en.a", "en.b"}


def test_restricting_a_served_version_unpublishes_it_and_blocks_publish(repo):
    accept_all(repo, commit(repo, package([body("en.a")])))
    vid = version_id(repo, "en.a")
    repo.publish([("en.a", vid)], actor=ADMIN)
    repo.set_version_rights(vid, status="restricted", actor=ADMIN, reason="licence withdrawn")
    assert repo.published("en", "en.a") is None
    with pytest.raises(GrammarStoreRefusal) as error:
        repo.publish([("en.a", vid)], actor=ADMIN)
    assert error.value.code == "grammar_rights_not_cleared"


def test_unpublish_archive_restore(repo):
    accept_all(repo, commit(repo, package([body("en.a")])))
    vid = version_id(repo, "en.a")
    repo.publish([("en.a", vid)], actor=ADMIN)
    repo.set_point_status("en.a", action="archive", actor=ADMIN)
    assert repo.published("en", "en.a") is None and repo.by_error("en", "tense_choice") == []
    with pytest.raises(GrammarStoreRefusal) as error:
        repo.publish([("en.a", vid)], actor=ADMIN)
    assert error.value.code == "grammar_point_archived"
    repo.set_point_status("en.a", action="restore", actor=ADMIN)
    repo.publish([("en.a", vid)], actor=ADMIN)
    assert repo.by_error("en", "tense_choice")[0]["grammar_id"] == "en.a"


def test_a_function_label_change_bumps_the_revision_of_published_points(repo):
    accept_all(repo, commit(repo, package([body("en.a")])))
    repo.publish([("en.a", version_id(repo, "en.a"))], actor=ADMIN)
    before = repo.catalog("en")["catalog_revision"]
    renamed = [{"id": "fn.talk_past", "title": {"vi": f"{FUNCTIONS[0]['title']['vi']} mới", "en": "Past events",
                                                "zh": "过去的事"}}]
    commit(repo, package([body("en.b", sequence=2)], functions=renamed, set_version="t2"))
    catalog = repo.catalog("en")
    assert catalog["catalog_revision"] == before + 1 and catalog["functions"][0]["title"]["en"] == "Past events"


def test_content_columns_never_change(repo):
    accept_all(repo, commit(repo, package([body("en.a")])))
    before = {(v["id"], v["content_hash"]) for v in repo.admin_point("en.a")["versions"]}
    vid = version_id(repo, "en.a")
    repo.publish([("en.a", vid)], actor=ADMIN)
    repo.set_point_status("en.a", action="archive", actor=ADMIN)
    repo.set_point_status("en.a", action="restore", actor=ADMIN)
    assert {(v["id"], v["content_hash"]) for v in repo.admin_point("en.a")["versions"]} == before
    assert repo.preview(vid)["point"]["header"]["title"] == lm("Point")


# --- R5 ----------------------------------------------------------------------------------------------------------------

def _r5(rid, pid, disp, primary):
    return {"r5_id": rid, "point_id": pid, "disposition": disp, "is_primary": primary}


def test_r5_resolution_is_independent_of_publish_and_survives_unpublish(repo):
    merged = body("en.m", aliases=["a1-be", "a1-be-questions"])
    primary = body("en.p", aliases=["a2-past"], sequence=2)
    secondary = body("en.s", r5_split=["a2-past"], sequence=3)
    rows = [_r5("a1-be", "en.m", "merged", True), _r5("a1-be-questions", "en.m", "merged", True),
            _r5("a2-past", "en.p", "split_primary", True), _r5("a2-past", "en.s", "split_secondary", False),
            _r5("a1-review", None, "dropped", False)]
    outcome = commit(repo, package([merged, primary, secondary], r5_map=rows))
    assert repo.resolve_r5("en", "a1-be") is None  # nothing accepted yet: unresolved
    accept_all(repo, outcome)
    assert repo.resolve_r5("en", "a1-be") == {"point": None, "unavailable": True, "point_id": "en.m"}
    repo.publish([("en.m", version_id(repo, "en.m")), ("en.p", version_id(repo, "en.p")),
                  ("en.s", version_id(repo, "en.s"))], actor=ADMIN)
    assert repo.resolve_r5("en", "a1-be") == {"point": None, "redirect": "en.m"}
    assert repo.resolve_r5("en", "en:grammar:v2:a1-be-questions") == {"point": None, "redirect": "en.m"}
    assert repo.resolve_r5("en", "a2-past") == {"point": None, "redirect": "en.p"}
    assert repo.resolve_r5("en", "a1-review") == {"point": None, "dropped": True}
    assert repo.resolve_r5("en", "zh:grammar:v2:a1-be") is None  # another language's composite
    assert repo.resolve_r5("en", "never-heard-of") is None
    assert repo.progress_map("en") == {"en.m": ["a1-be", "a1-be-questions"], "en.p": ["a2-past"]}  # no secondary
    repo.set_point_status("en.m", action="archive", actor=ADMIN)
    assert repo.resolve_r5("en", "a1-be") == {"point": None, "unavailable": True, "point_id": "en.m"}
    assert repo.r5_rows("en")  # the map is untouched by archive
    assert repo.coverage("en") == ["a1-be", "a1-be-questions"]


def test_a_later_batch_replaces_an_r5_ids_rows_and_records_the_change(repo):
    accept_all(repo, commit(repo, package([body("en.a", aliases=["r5-1"])],
                                          r5_map=[_r5("r5-1", "en.a", "replaced", True)])))
    outcome = commit(repo, package([body("en.b", aliases=["r5-1"], sequence=2)],
                                   r5_map=[_r5("r5-1", "en.b", "replaced", True)], set_version="t2"))
    assert outcome.report["diff"]["r5_changes"][0]["r5_id"] == "r5-1"
    assert repo.r5_rows("en") == [{"r5_id": "r5-1", "point_id": "en.b", "disposition": "replaced", "is_primary": True}]


@pytest.mark.parametrize("key, expected", [
    ("a1-present-simple", "a1-present-simple"),
    ("en:grammar:v2:a1-present-simple", "a1-present-simple"),
    ("en:grammar:v10:odd:id:with:colons", "odd:id:with:colons"),
    ("zh:grammar:v2:a1-present-simple", None),
    ("en:grammar:vX:a1", None),
    ("xen:grammar:v2:a1", None),
    ("en.present_perfect", None),
    ("", None),
])
def test_the_composite_key_parse_is_strict(key, expected):
    assert parse_r5_key(key, "en") == expected


def test_chinese_packages_are_first_class(repo):
    zh = body("zh.le_completion", aliases=["hsk1-le"])
    accept_all(repo, commit(repo, package([zh], language="zh",
                                          r5_map=[_r5("hsk1-le", "zh.le_completion", "replaced", True)])))
    repo.publish([("zh.le_completion", version_id(repo, "zh.le_completion"))], actor=ADMIN)
    catalog = repo.catalog("zh")
    assert catalog["points"][0]["level"] == {"framework": "hsk3", "value": "1", "rank": 1}
    assert repo.catalog("en")["points"] == [] and repo.resolve_r5("zh", "hsk1-le") == {"point": None,
                                                                                     "redirect": "zh.le_completion"}
    assert json.dumps(repo.published("zh", "zh.le_completion"), ensure_ascii=False).count("我昨天买了一本书。") >= 1
