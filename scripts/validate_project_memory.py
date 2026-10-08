"""Validate Orena's repository-backed project memory and drift boundaries.

CURRENT_PRODUCT_STATE.yaml intentionally uses the JSON-compatible subset of
YAML 1.2. This keeps parsing deterministic with Python's standard library and
avoids implicit YAML types, tags, anchors, or environment-dependent loaders.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path("docs/project")
STATE_PATH = PROJECT / "CURRENT_PRODUCT_STATE.yaml"
SCHEMA_PATH = PROJECT / "CURRENT_PRODUCT_STATE.schema.json"

CORE_MEMORY_FILES = (
    PROJECT / "PROJECT_MEMORY.md",
    PROJECT / "PRODUCT_CONSTITUTION.md",
    STATE_PATH,
    SCHEMA_PATH,
    PROJECT / "LEGACY_TOMBSTONES.md",
    PROJECT / "CURRENT_HANDOFF.md",
    PROJECT / "PRODUCT_MAP.md",
    PROJECT / "DESIGN_CONTRACT.md",
)

STARTUP_ORDER = (
    "docs/project/PROJECT_MEMORY.md",
    "docs/project/PRODUCT_CONSTITUTION.md",
    "docs/project/CURRENT_PRODUCT_STATE.yaml",
    "docs/project/LEGACY_TOMBSTONES.md",
    "docs/project/CURRENT_HANDOFF.md",
    "docs/project/PRODUCT_MAP.md",
    "docs/project/ROADMAP.md",
)

REQUIRED_GATES = {
    "production_authentication",
    "live_ai_provider_validation",
    "production_ai_activation",
    "production_postgresql_migration_or_mutation",
    "backup_restore_and_rollback",
    "secrets_credentials_cloudflare_dns",
    "billing_subscription_enforcement",
    "mobile_signing_store_release",
    "learner_skill_or_catalog_publication",
}

# Vendored, generated, and build-output trees are not Orena product source.
# Walking them costs minutes on a developer machine and can only produce
# findings about third-party code.
EXCLUDED_DIRECTORIES = {
    ".git",
    ".gradle",
    "__pycache__",
    "android",
    "build",
    "coverage",
    "dist",
    "ios",
    "node_modules",
    "vendor",
}

LEGACY_NAMESPACES = {
    "static/becoming/**",
    "templates/becoming/**",
    "writing_coach/becoming_*",
}


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def validate_schema(value: Any, schema: dict[str, Any], path: str = "state") -> list[str]:
    """Validate the JSON-Schema subset used by CURRENT_PRODUCT_STATE."""

    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type and not _type_matches(value, expected_type):
        return [f"{path}: expected {expected_type}, got {type(value).__name__}"]

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: unsupported value {value!r}")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: string is shorter than minLength")
        pattern = schema.get("pattern")
        if pattern and re.fullmatch(pattern, value) is None:
            errors.append(f"{path}: value {value!r} does not match {pattern!r}")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: list is shorter than minItems")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                errors.extend(validate_schema(item, item_schema, f"{path}[{index}]"))

    if isinstance(value, dict):
        required = set(schema.get("required", ()))
        for key in sorted(required - value.keys()):
            errors.append(f"{path}: missing required field {key!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in sorted(value.keys() - properties.keys()):
                errors.append(f"{path}: unsupported field {key!r}")
        for key, child_schema in properties.items():
            if key in value:
                errors.extend(validate_schema(value[key], child_schema, f"{path}.{key}"))

    return errors


def validate_state_semantics(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    deprecated = {item.get("route"): item for item in state.get("deprecated_routes", [])}
    becoming = deprecated.get("/becoming")
    if becoming != {
        "route": "/becoming",
        "status": "compatibility_only",
        "replacement": "/",
        "new_development_allowed": False,
    }:
        errors.append("state: /becoming must be compatibility-only, replaced by /, with new development forbidden")

    namespaces = {item.get("path") for item in state.get("legacy_namespaces", [])}
    if namespaces != LEGACY_NAMESPACES:
        errors.append("state: legacy namespace allowlist must contain exactly the three canonical historical namespaces")

    languages = state.get("languages", {}).get("first_class", [])
    if set(languages) != {"en", "zh"} or len(languages) != 2:
        errors.append("state: first-class languages must be exactly EN and ZH")
    listening_languages = state.get("listening", {}).get("first_class_languages", [])
    if set(listening_languages) != {"en", "zh"} or len(listening_languages) != 2:
        errors.append("state: Listening must preserve EN/ZH first-class parity")
    core_skills = state.get("skills", {}).get("core", [])
    if set(core_skills) != {"listening", "speaking", "reading", "writing"} or len(core_skills) != 4:
        errors.append("state: connected learning core must contain Listening, Speaking, Reading, and Writing exactly once")

    release = state.get("release_state", {})
    public_skills = set(release.get("public_skills", []))
    skill_state = state.get("skills", {}).get("state", {})
    declared_public = {
        skill for skill, facts in skill_state.items()
        if facts.get("learner_visibility") == "public"
    }
    if public_skills != declared_public:
        errors.append("state: public_skills must exactly match the skills whose learner_visibility is public")
    if release.get("public_release_approved") is False and public_skills:
        errors.append("state: skills cannot be public without public release approval")
    if release.get("overall") == "public" and not release.get("public_release_approved"):
        errors.append("state: overall public state requires explicit public release approval")

    errors.extend(_validate_skill_dimensions(skill_state, release))
    errors.extend(_validate_real_media_catalog(state, skill_state))

    gates = {item.get("id"): item.get("status") for item in state.get("human_gates", [])}
    if set(gates) != REQUIRED_GATES:
        errors.append("state: human gate set is incomplete or contains unsupported gates")
    if release.get("production_ready"):
        if not release.get("public_release_approved"):
            errors.append("state: production_ready requires public_release_approved")
        if any(status == "approval_required" for status in gates.values()):
            errors.append("state: production_ready contradicts pending human gates")

    return errors


def _walk_product_files(base: Path) -> list[Path]:
    """Yield product source files under base, pruning vendored/build trees."""

    files: list[Path] = []
    if not base.is_dir():
        return files
    stack = [base]
    while stack:
        directory = stack.pop()
        for entry in directory.iterdir():
            if entry.is_dir():
                if entry.name not in EXCLUDED_DIRECTORIES:
                    stack.append(entry)
            elif entry.is_file():
                files.append(entry)
    return files


def _validate_skill_dimensions(skill_state: dict[str, Any], release: dict[str, Any]) -> list[str]:
    """Keep the seven skill truths independent and mutually consistent.

    Implementation and local acceptance are deliberately NOT allowed to imply
    visibility or release, and release is never allowed to imply content. A
    fresh agent must be able to read "complete_local, internal" without
    concluding the work is missing, and "pre_public_matrix complete" without
    concluding the content is real.
    """

    errors: list[str] = []
    for skill, facts in sorted(skill_state.items()):
        visibility = facts.get("learner_visibility")
        public_release = facts.get("public_release")
        human = facts.get("human_acceptance")
        content = facts.get("content_readiness")

        if visibility == "public" and public_release != "approved":
            errors.append(f"state: {skill} is learner-visible as public without an approved public release")
        if public_release == "approved":
            if human != "approved":
                errors.append(f"state: {skill} public release is approved without human acceptance")
            if not release.get("public_release_approved"):
                errors.append(f"state: {skill} public release contradicts release_state.public_release_approved")

        # Seed and mock content are never completion evidence.
        if content == "seed_or_mock_only":
            if public_release == "approved":
                errors.append(f"state: {skill} cannot be publicly released on seed/mock content")
            if human == "approved":
                errors.append(f"state: {skill} cannot hold human acceptance on seed/mock content")
        if content == "real_content_complete" and facts.get("implementation") != "complete_local":
            errors.append(f"state: {skill} claims complete real content without a complete implementation")

    return errors


def _validate_real_media_catalog(state: dict[str, Any], skill_state: dict[str, Any]) -> list[str]:
    """The Listening engine and the real media catalog are separate truths.

    Human QA confirmed the built-in lessons are still seed/synthetic, so the
    catalog carries its own readiness, its own per-language playable evidence,
    and its own acceptance and publication gates. Behavioural acceptance
    completion says nothing about any of them.
    """

    errors: list[str] = []
    catalog = state.get("listening", {}).get("real_media_catalog", {})
    if not catalog:
        return errors

    status = catalog.get("status")
    english = catalog.get("real_playable_en_evidence")
    chinese = catalog.get("real_playable_zh_evidence")
    acceptance = catalog.get("human_playback_acceptance")
    publication = catalog.get("public_catalog_publication")

    listening_content = skill_state.get("listening", {}).get("content_readiness")
    if listening_content != status:
        errors.append("state: listening content_readiness must match listening.real_media_catalog.status")

    if status == "seed_or_mock_only":
        if english or chinese:
            errors.append("state: seed/mock catalog cannot carry real playable EN/ZH evidence")
        if acceptance == "approved":
            errors.append("state: seed/mock catalog cannot hold human playback acceptance")
        if publication == "approved":
            errors.append("state: seed/mock catalog cannot be published")
    if status == "real_content_complete":
        if not (english and chinese):
            errors.append("state: complete real catalog requires real playable EN and ZH evidence")
        if acceptance != "approved":
            errors.append("state: complete real catalog requires human playback acceptance")
    if status == "real_content_partial" and not (english or chinese):
        errors.append("state: partial real catalog requires at least one real playable language")
    if publication == "approved" and acceptance != "approved":
        errors.append("state: catalog publication requires human playback acceptance")

    return errors


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def validate_memory_documents(root: Path) -> list[str]:
    errors: list[str] = []
    for path in CORE_MEMORY_FILES:
        if not (root / path).is_file():
            errors.append(f"missing core project-memory file: {path.as_posix()}")
    if errors:
        return errors

    memory = _read(root, "docs/project/PROJECT_MEMORY.md")
    positions = [memory.find(f"`{path}`") for path in STARTUP_ORDER]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        errors.append("PROJECT_MEMORY: canonical startup files are missing or out of order")

    for relative in (
        "docs/project/PROJECT_MEMORY.md",
        "docs/project/PRODUCT_CONSTITUTION.md",
        "docs/project/LEGACY_TOMBSTONES.md",
        "docs/project/CURRENT_HANDOFF.md",
        "docs/project/PRODUCT_MAP.md",
        "docs/project/DESIGN_CONTRACT.md",
    ):
        # Markdown hard-wraps prose, so a marker may straddle a line break.
        # Compare on whitespace-normalised text instead of the raw file.
        text = " ".join(_read(root, relative).casefold().split())
        for marker in ("purpose", "authority", "change when", "do not store"):
            if marker not in text:
                errors.append(f"{relative}: missing memory ownership marker {marker!r}")

    constitution = _read(root, "docs/project/PRODUCT_CONSTITUTION.md")
    for required in (
        "active product name and learner-facing identity is **Orena**",
        "canonical Orena web route is `/`",
        "`/becoming` is deprecated and compatibility-only",
        "full native port",
        "English and Chinese are equally first-class",
        "experience-centered, not discovery-only",
        "Follow is first-class",
        "PostgreSQL is authoritative",
    ):
        if required not in constitution:
            errors.append(f"PRODUCT_CONSTITUTION: missing durable rule {required!r}")

    tombstones = _read(root, "docs/project/LEGACY_TOMBSTONES.md")
    for required in ("## `/becoming`", "Historical BECOMING user-facing product identity", *LEGACY_NAMESPACES):
        if required not in tombstones:
            errors.append(f"LEGACY_TOMBSTONES: missing {required!r}")

    handoff = _read(root, "docs/project/CURRENT_HANDOFF.md")
    for heading in (
        "## Current branch / lane",
        "## Last verified batch",
        "## DONE",
        "## IN PROGRESS",
        "## PENDING",
        "## BLOCKED",
        "## OPEN P0",
        "## OPEN P1",
        "## HUMAN GATES",
        "## NEXT EXACT TASK",
    ):
        if heading not in handoff:
            errors.append(f"CURRENT_HANDOFF: missing {heading}")
    if len(handoff.encode("utf-8")) > 8_000:
        errors.append("CURRENT_HANDOFF: exceeds compact 8 KB limit")

    resume = root / ".claude/commands/resume-orena.md"
    if not resume.is_file():
        errors.append("missing /resume-orena workflow")

    return errors


def scan_active_regressions(root: Path) -> list[str]:
    errors: list[str] = []

    # Decorators carry keyword arguments (response_class=...), so match the
    # route literal rather than an exact decorator spelling.
    app_source = _read(root, "app.py")
    if re.search(r'@app\.get\(\s*"/"\s*[,)]', app_source) is None:
        errors.append("routing: root / is no longer registered")
    compatibility = re.search(r'@app\.get\(\s*"/becoming/?"\s*[,)]', app_source)
    if compatibility is None or 'RedirectResponse("/", status_code=302)' not in app_source[compatibility.end():compatibility.end() + 500]:
        errors.append("routing: /becoming is not a bounded compatibility redirect to /")

    nav_patterns = (
        re.compile(r"href\s*=\s*[\"']/becoming(?:[/#?\"'])", re.IGNORECASE),
        re.compile(r"(?:router\.)?(?:push|replace|navigate)\s*\(\s*[\"']/becoming(?:[/#?\"'])", re.IGNORECASE),
        re.compile(r"\bto\s*=\s*[\"']/becoming(?:[/#?\"'])", re.IGNORECASE),
    )
    active_extensions = {".html", ".js", ".mjs", ".ts", ".tsx"}
    for base in (root / "templates", root / "static", root / "mobile"):
        for path in _walk_product_files(base):
            if path.suffix.lower() not in active_extensions:
                continue
            relative = path.relative_to(root).as_posix()
            if "/__snapshots__/" in f"/{relative}/" or relative.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in nav_patterns:
                if pattern.search(text):
                    errors.append(f"tombstone regression: active navigation to /becoming in {relative}")
                    break

    identity_patterns = (
        re.compile(r"<title>\s*BECOMING\s*</title>", re.IGNORECASE),
        re.compile(r"aria-label\s*=\s*[\"']BECOMING(?:\s+(?:navigation|home))?[\"']", re.IGNORECASE),
        re.compile(r">\s*BECOMING\s*<", re.IGNORECASE),
        re.compile(r"[\"']BECOMING(?:\s+(?:navigation|home))?[\"']", re.IGNORECASE),
    )
    product_sources = [root / "templates/orena/index.html"]
    product_sources.extend(
        path for path in _walk_product_files(root / "static/orena")
        if path.suffix == ".js"
    )
    product_sources.extend(
        path for path in _walk_product_files(root / "mobile")
        if path.suffix == ".tsx"
    )
    for path in product_sources:
        if not path.is_file() or path.name.endswith((".test.tsx", ".spec.tsx")):
            continue
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(pattern.search(text) for pattern in identity_patterns):
            errors.append(f"identity regression: learner-facing BECOMING branding in {relative}")

    current_docs = (
        "AGENTS.md",
        "CLAUDE.md",
        "docs/project/README.md",
        "docs/project/PROJECT_MEMORY.md",
        "docs/project/PRODUCT_CONSTITUTION.md",
        "docs/project/CURRENT_PRODUCT_STATE.yaml",
        "docs/project/CURRENT_HANDOFF.md",
        "docs/project/PRODUCT_MAP.md",
        "docs/project/DESIGN_CONTRACT.md",
    )
    current_claim = re.compile(r"^(?:#\s+)?(?:product|application|app|project)(?:\s+name|\s+identity)?\s*(?::|is)\s*(?:\*\*)?BECOMING\b", re.IGNORECASE | re.MULTILINE)
    for relative in current_docs:
        path = root / relative
        if path.is_file() and current_claim.search(path.read_text(encoding="utf-8")):
            errors.append(f"identity regression: current document claims BECOMING is active in {relative}")

    return errors


def validate_repository(root: Path = ROOT) -> list[str]:
    errors = validate_memory_documents(root)
    if (root / STATE_PATH).is_file() and (root / SCHEMA_PATH).is_file():
        try:
            state = _json(root / STATE_PATH)
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"CURRENT_PRODUCT_STATE: deterministic YAML/JSON parse failed: {exc}")
        else:
            try:
                schema = _json(root / SCHEMA_PATH)
            except (json.JSONDecodeError, OSError) as exc:
                errors.append(f"CURRENT_PRODUCT_STATE schema parse failed: {exc}")
            else:
                errors.extend(validate_schema(state, schema))
                errors.extend(validate_state_semantics(state))
                commit = state.get("last_verified_application_commit", "")
                if (root / ".git").exists() and re.fullmatch(r"[0-9a-f]{40}", commit):
                    # The application container has no git binary. A missing
                    # tool is an execution-environment limit, not a memory
                    # defect, so the check is skipped rather than failed.
                    try:
                        check = subprocess.run(
                            ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
                            cwd=root,
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                    except (FileNotFoundError, OSError):
                        check = None
                    if check is not None and check.returncode != 0:
                        errors.append("state: last_verified_application_commit is not present in Git history")
    errors.extend(scan_active_regressions(root))
    return errors


def main() -> int:
    errors = validate_repository()
    if errors:
        print("Project memory validation FAILED:")
        for error in errors:
            print(" -", error)
        return 1
    print("Project memory validation OK")
    print("Product: Orena")
    print("Canonical route: /")
    print("Deprecated compatibility route: /becoming")
    print("Languages: en, zh")
    print("Native strategy: full_native_port")

    # Print the two truths most often collapsed, so anyone running the gate
    # sees them without opening the state file.
    try:
        state = _json(ROOT / STATE_PATH)
    except (json.JSONDecodeError, OSError):
        return 0
    catalog = state.get("listening", {}).get("real_media_catalog", {})
    print(f"Listening engine: {state['skills']['state']['listening']['implementation']}"
          f" (local acceptance {state['skills']['state']['listening']['local_acceptance']})")
    print(f"Listening real media catalog: {catalog.get('status')}"
          f" (EN playable {catalog.get('real_playable_en_evidence')},"
          f" ZH playable {catalog.get('real_playable_zh_evidence')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
