"""Integrity stamping for the generated development Listening catalog.

Deliberately dependency-free. The catalog loader, the importer and the CLI all
need this, and the CLI must be able to verify a committed artifact offline in CI
without pulling in a provider adapter or the network stack it depends on.

The artifact is committed rather than gitignored, so a clean checkout or a
container rebuild still has the development catalog without regenerating it from
a provider at startup. Because it is committed it also has to be tamper-evident:
humans edit the source CSV, never the generated JSON, and this hash is what
turns that rule from a comment into something the loader can enforce.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

GENERATOR = "scripts/build_listening_dev_catalog.py"
GENERATOR_VERSION = "1"

# The source lists a committed snapshot must have been generated from.
EXPECTED_SOURCE_LISTS = (
    "listening_sources_en_dev_100.csv",
    "listening_sources_zh_dev_100.csv",
)

# Whether a committed snapshot is REQUIRED to exist.
#
# False today: L2 built the strategy but deliberately did not run the full
# candidate pack, so no snapshot has been committed yet. While this is False the
# offline check reports honestly that there is nothing to verify, and never
# reports integrity PASS for a file that does not exist.
#
# L3 sets this True in the same commit that adds the first real snapshot. From
# then on a missing or stale artifact is a CI failure.
SNAPSHOT_REQUIRED = False


# Everything the fingerprint covers. Only the hash field itself is excluded,
# because it cannot cover itself.
FINGERPRINTED_FIELDS = (
    "schema_version",
    "generated_by",
    "generator_version",
    "source_lists",
    "sources",
    "lessons",
)
CONTENT_HASH_FIELD = "content_hash"


def manifest_content_hash(manifest: Mapping[str, Any]) -> str:
    """Fingerprint the snapshot: provenance header and catalog body together.

    Hashing only sources and lessons left a gap. The provenance header was
    verified separately, so a stale catalog body could be paired with
    hand-updated source-list digests and the content hash would not move. Both
    halves are bound into one value instead, which closes that pairing.

    This is defence against ordinary drift - an agent or a person editing the
    generated file - not a cryptographic boundary. Sorted keys and fixed
    separators keep it stable across Python versions and across whatever order
    the generator happened to build its dictionaries in.
    """

    body = {field: manifest.get(field) for field in FINGERPRINTED_FIELDS}
    return hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def file_digest(path) -> str:
    """Digest of one input source list, so a snapshot records what produced it."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest_integrity(
    manifest: Mapping[str, Any],
    content_dir=None,
) -> str:
    """Why this artifact is not trustworthy, or an empty string when intact.

    Four things are checked, and the last is what makes the snapshot genuinely
    reproducible rather than merely tamper-evident: a content hash proves the
    generated JSON was not hand-edited, but only re-digesting the CURRENT source
    CSVs catches the other stale case — someone edits a source list and forgets
    to regenerate, leaving a snapshot that no longer matches its own inputs.

    `content_dir` is optional so a caller with a manifest in memory, and no repo
    on disk, can still check the parts that do not need the input files.
    """

    generated_by = str(manifest.get("generated_by") or "")
    if generated_by != GENERATOR:
        return f"generated catalog names an unexpected generator {generated_by!r}"
    version = str(manifest.get("generator_version") or "")
    if version != GENERATOR_VERSION:
        return (f"generated catalog was built by generator version {version!r}, "
                f"expected {GENERATOR_VERSION!r}; regenerate it")

    recorded = str(manifest.get("content_hash") or "")
    if not recorded:
        return "generated catalog has no content_hash; regenerate it"
    if recorded != manifest_content_hash(manifest):
        return "generated catalog was edited by hand; edit the source CSV and regenerate"

    entries = manifest.get("source_lists") or []
    names = [str(entry.get("name") or "") for entry in entries]
    missing = [name for name in EXPECTED_SOURCE_LISTS if name not in names]
    if missing:
        return f"generated catalog does not record source lists {missing}; regenerate it"

    if content_dir is None:
        return ""
    for entry in entries:
        name = str(entry.get("name") or "")
        path = content_dir / name
        if not path.is_file():
            return f"source list {name} recorded by the catalog no longer exists"
        if file_digest(path) != str(entry.get("sha256") or ""):
            return (f"source list {name} changed since the catalog was generated; "
                    "regenerate the development catalog")
    return ""
