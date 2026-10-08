"""Reconcile GRAMMAR_CONTENT_STORE.md (revision 3) with the Grammar Lab export contract at a pinned commit.

Read-only, by hand, not part of CI (the Grammar Lab branch is not on `main`). Every upstream file is read with
`git show <commit>:<path>` and nothing is copied into the application source; Grammar Lab's Python is parsed with `ast`,
never imported or executed. Needs the commit in the local object store (`git fetch origin feature/grammar-lab-pipeline`).

    python scripts/check_grammar_export_contract.py [--commit 3579ece887c226b31d03b759b720261b8fa1d31d]

Requires `jsonschema` and `PyYAML`, which `requirements.txt` does not declare (install them in a throwaway virtualenv).
A missing one is a FAIL row, never a skipped PASS: the run cannot report success without executing every check.

Checks (each a PASS/FAIL row; non-zero exit on any FAIL):
 1. canonical JSON: the proposal's rule (section 11) reproduces the golden vector's exact bytes and SHA-256.
 2. export profile 1 (`schema/export_profile.schema.json`): a valid Draft 2020-12 schema, closed at every object except the two documented maps, single version, `status` const `approved`,
    `target_lang` en|zh, locale keys vi|en|zh with vi and en required, no internal field in a point body; its
    `profile_schema_hash` is printed so the vendored copy can be pinned.
 3. package manifest (`pipeline/export_package.py`): the closed key set, provenance keys, profile id, schema version,
    app languages, and `package_hash` scope are what the proposal specifies.
 4. `r5_map` (`pipeline/r5_map.py`): the five dispositions equal the migration's, the row keys are exactly four.
 5. function labels: every label carries vi, en and zh-Hans (merged GCC "nhãn function đủ ba").
 6. the approved corpus is counted (not read into the app): the number of `status: approved` point files per language.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINNED = "3579ece887c226b31d03b759b720261b8fa1d31d"
MIGRATION = ROOT / "migrations" / "proposed" / "20261008_0030_grammar_content_store.py"
RESULTS: list[tuple[str, bool, str]] = []

# What revision 3 of the proposal specifies at the boundary (sections 5.1, 5.2, 9.2, 10, 11).
PROFILE_ID = "grammar-export-profile/1"
SCHEMA_VERSION = "0.4"
MANIFEST_KEYS = {
    "export_profile", "profile_schema_hash", "schema_version", "language", "set_version", "source_commit",
    "source_dirty", "exported_at", "package_hash", "external_references", "functions", "points", "r5_map",
    "validator", "rights",
}
POINT_PROVENANCE_KEYS = {
    "reviewer", "reviewed_at", "review_seconds", "run_id", "model", "prompt_version", "generated_at", "source_refs",
    "source_anchors",
}
PACKAGE_HASH_SCOPE = {"export_profile", "schema_version", "language", "functions", "points", "r5_map"}
FORBIDDEN_IN_BODY = {"provenance", "review", "flags", "source_anchors", "schema_version", "title", "summary", "blocks"}
OPEN_MAPS = {"#/$defs/grammar_point/properties/source_refs", "#/$defs/locale_map"}


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)


def show(commit: str, path: str) -> str:
    return subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, check=True, capture_output=True,
                          text=True, encoding="utf-8").stdout


def canonical(value) -> bytes:
    """Section 11: keys sorted by code point, (",", ":"), UTF-8, no ASCII escaping, no floats, no NaN, no normalisation."""
    def no_float(node):
        if isinstance(node, float):
            raise ValueError("floats are not canonical")
        if isinstance(node, dict):
            [no_float(item) for item in node.values()]
        if isinstance(node, list):
            [no_float(item) for item in node]
    no_float(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def module_constants(source: str) -> dict:
    constants = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                constants[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return constants


def open_objects(node, path="#") -> list[str]:
    found = []
    if isinstance(node, dict):
        is_object = node.get("type") == "object" or "properties" in node
        conditional = path.rsplit("/", 1)[-1] in {"if", "then"} or "/then/" in path or "/if/" in path
        if is_object and node.get("additionalProperties") is not False and not conditional:
            found.append(path)
        for key, value in node.items():
            found += open_objects(value, f"{path}/{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found += open_objects(value, f"{path}[{index}]")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--commit", default=PINNED)
    commit = parser.parse_args().commit
    print("Grammar Lab commit:", commit)

    # 1. canonical JSON ----------------------------------------------------------------------------------------------
    vector = json.loads(show(commit, "grammar_lab/fixtures/export/golden_vector.json"))
    produced = canonical(vector["value"])
    check("1 canonical JSON reproduces the golden vector's bytes", produced.decode("utf-8") == vector["canonical_json"])
    check("1 and its SHA-256", hashlib.sha256(produced).hexdigest() == vector["sha256"], vector["sha256"])
    try:
        canonical({"a": 1.0})
        check("1 a float is refused", False)
    except ValueError:
        check("1 a float is refused", True)

    # 2. the export profile ------------------------------------------------------------------------------------------------
    profile = json.loads(show(commit, "grammar_lab/schema/export_profile.schema.json"))
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        check("2 export profile is a valid Draft 2020-12 schema", False, "NOT RUN: jsonschema is not installed")
    else:
        Draft202012Validator.check_schema(profile)
        check("2 export profile is a valid Draft 2020-12 schema", True)
    point = profile["$defs"]["grammar_point"]
    check("2 profile id", profile["$id"] == "urn:orena:grammar_lab:export_profile:1", profile["$id"])
    opened = sorted(set(open_objects(profile)))
    check("2 closed at every object except the two documented maps", set(opened) == OPEN_MAPS, str(opened))
    check("2 source_refs is a map of snake_case codes to string arrays (catalogue codes, never text)",
          point["properties"]["source_refs"].get("propertyNames", {}).get("pattern") == "^[a-z][a-z0-9_]*$"
          and point["properties"]["source_refs"]["additionalProperties"]["items"]["type"] == "string")
    locale_map = profile["$defs"]["locale_map"]
    check("2 locale map keys vi|en|zh, vi and en required", profile["$defs"]["locale"]["enum"] == ["vi", "en", "zh"]
          and locale_map["required"] == ["vi", "en"], json.dumps(locale_map["required"]))
    check("2 target_lang en|zh (no zh-Hans at the boundary)", profile["$defs"]["target_lang"]["enum"] == ["en", "zh"])
    check("2 status is the constant approved", point["properties"]["status"] == {"const": "approved"})
    check("2 no internal or superseded field in a point body", not FORBIDDEN_IN_BODY & set(point["properties"]),
          str(sorted(FORBIDDEN_IN_BODY & set(point["properties"]))))
    check("2 point id pattern <en|zh>.<slug>", profile["$defs"]["point_id"]["pattern"] == r"^(en|zh)\.[a-z0-9_]+(\.[a-z0-9_]+)*$")
    check("2 level frameworks cefr|hsk3", profile["$defs"]["level"]["properties"]["framework"]["enum"] == ["cefr", "hsk3"])
    print("    profile_schema_hash =", hashlib.sha256(canonical(profile)).hexdigest())
    print("    point required =", ", ".join(point["required"]))

    # 3. the manifest ----------------------------------------------------------------------------------------------------
    exporter = show(commit, "grammar_lab/pipeline/export_package.py")
    constants = module_constants(exporter)
    profile_constants = module_constants(show(commit, "grammar_lab/pipeline/export_profile.py"))
    check("3 manifest keys are the closed set the proposal specifies", constants.get("MANIFEST_KEYS") == MANIFEST_KEYS,
          str(sorted(set(constants.get("MANIFEST_KEYS", ())) ^ MANIFEST_KEYS)))
    check("3 per-point provenance keys (+ optional r5_source)", constants.get("POINT_PROVENANCE_KEYS") == POINT_PROVENANCE_KEYS)
    check("3 profile id and content schema version", profile_constants.get("PROFILE_ID") == PROFILE_ID
          and profile_constants.get("CONTENT_SCHEMA_VERSION") == SCHEMA_VERSION,
          f"{profile_constants.get('PROFILE_ID')} / {profile_constants.get('CONTENT_SCHEMA_VERSION')}")
    check("3 app languages en|zh", constants.get("APP_LANGS") == ("en", "zh"))
    check("3 the package rights block is a policy, not an attestation",
          constants.get("RIGHTS", {}).get("attestation_required_at_import") is True
          and constants.get("RIGHTS", {}).get("external_text_included") is False)
    tree = ast.parse(exporter)
    scope = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "package_hash_of":
            for inner in ast.walk(node):
                if isinstance(inner, ast.Dict):
                    scope |= {key.value for key in inner.keys if isinstance(key, ast.Constant)}
    check("3 package_hash covers profile, schema version, language, functions, points (id, version, hash), r5_map"
          " and not the audit metadata", scope - {"id", "version", "content_hash"} == PACKAGE_HASH_SCOPE, str(sorted(scope)))

    # 4. r5_map ----------------------------------------------------------------------------------------------------------
    r5 = show(commit, "grammar_lab/pipeline/r5_map.py")
    migration_dispositions = module_constants(MIGRATION.read_text(encoding="utf-8")).get("DISPOSITIONS")
    check("4 r5_map dispositions equal the migration's", module_constants(r5).get("DISPOSITIONS") == migration_dispositions,
          str(module_constants(r5).get("DISPOSITIONS")))
    check("4 r5_map rows have exactly r5_id, point_id, is_primary, disposition",
          '{"r5_id", "point_id", "is_primary", "disposition"}' in r5)
    check("4 a secondary records the id in source_refs.r5_split, never in aliases (D-106.2)",
          "source_refs\", {}).get(\"r5_split\"" in r5 and "(primary only)" in r5)

    # 5. function labels -------------------------------------------------------------------------------------------------
    try:
        import yaml
    except ImportError:
        check("5 function labels carry vi, en and zh-Hans (GCC)", False, "NOT RUN: PyYAML is not installed")
    else:
        functions = yaml.safe_load(show(commit, "grammar_lab/functions/functions.yaml"))["functions"]
        missing = [f["id"] for f in functions if not all(f["title"].get(key) for key in ("vi", "en", "zh-Hans"))]
        check(f"5 all {len(functions)} function labels carry vi, en and zh-Hans (GCC); the exporter requires only vi"
              " and en, so the importer is the stricter side", not missing, str(missing))

    # 6. the corpus, counted only ----------------------------------------------------------------------------------------
    counts = {}
    for lang in ("en", "zh"):
        listing = subprocess.run(["git", "grep", "-l", '"status": "approved"', commit, "--", f"grammar_lab/content/{lang}/"],
                                 cwd=ROOT, capture_output=True, text=True).stdout.split()
        counts[lang] = len([path for path in listing if not path.endswith("/_set.json")])
    check("6 approved corpus at the pinned commit (counted, not copied)", sum(counts.values()) == 595, str(counts))

    failed = [row for row in RESULTS if not row[1]]
    print(f"\n{len(RESULTS) - len(failed)} PASS, {len(failed)} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
