"""The grammar content store (GRAMMAR_CONTENT_STORE.md rev 3a sections 3-11; migration 20261008_0030).

Shared content imported from Grammar Lab export packages, reviewed, rights-attested and published by an admin, and
read by learners. Portable SQLAlchemy Core (the Reading engine's pattern): the hermetic suite runs the same SQL on
SQLite built by `create_all`; PostgreSQL adds row locks and the 0030 triggers.

Invariants this module keeps on every backend (PostgreSQL also enforces the first two in the database):
- a version's content columns are never updated and no version is ever deleted (only `review_status`,
  `is_published`, `superseded_at`, `rights_status`, `reviewed_*` move);
- review events are only inserted, in the same transaction as the change they record;
- a point is published with exactly one published version, which is `accepted` and `cleared`;
- the R5 map is written by an import commit only and never touched by publish, unpublish or archive;
- no learner table is read or written here.
"""
from __future__ import annotations

import re
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, delete, func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from writing_coach.grammar_store import contract
from writing_coach.grammar_store.package import Package, Problem
from writing_coach.persistence.models import (
    GrammarCatalogState,
    GrammarFunction,
    GrammarImportBatch,
    GrammarPoint,
    GrammarPointErrorTag,
    GrammarPointVersion,
    GrammarR5Map,
    GrammarReviewEvent,
)

BATCHES = GrammarImportBatch.__table__
FUNCTIONS = GrammarFunction.__table__
POINTS = GrammarPoint.__table__
VERSIONS = GrammarPointVersion.__table__
R5 = GrammarR5Map.__table__
TAGS = GrammarPointErrorTag.__table__
EVENTS = GrammarReviewEvent.__table__
STATE = GrammarCatalogState.__table__

RIGHTS_BASES = ("orena_original", "licensed", "other")
MAX_BULK_PUBLISH = 1000
MAX_DIFF_ROWS = 2000
_COMPOSITE = re.compile(r"(en|zh):grammar:v(\d+):(.+)", re.DOTALL)


class GrammarStoreRefusal(ValueError):
    """A domain refusal the routes map to an HTTP status (`status`) and an error category (`code`)."""

    def __init__(self, code: str, message: str, *, status: int = 422, context: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.context = dict(context or {})


@dataclass
class ImportOutcome:
    status: str  # "imported" | "rejected" | "already_imported" | "dry_run"
    batch: dict[str, Any] | None
    report: dict[str, Any] = field(default_factory=dict)


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:  # SQLite returns naive datetimes for timezone-aware columns
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _uuid(value: Any) -> uuid.UUID:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise GrammarStoreRefusal("grammar_not_found", "unknown id", status=404) from exc


def _exported_at(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return _now()
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _references(body: Mapping[str, Any]) -> set[str]:
    return {*body.get("prereqs", []), *body.get("contrasts", []), *(c["with"] for c in body.get("compare", []))}


def _label_complete(title: Any) -> bool:
    return isinstance(title, dict) and all(isinstance(title.get(k), str) and title.get(k)
                                           for k in contract.FUNCTION_LABEL_LOCALES)


def content_fingerprint(body: Mapping[str, Any]) -> str:
    """The content of a point body without its `version` number: what "the same content" means for the
    `content_already_stored` and `content_previously_rejected` refusals."""
    return contract.content_hash({key: value for key, value in body.items() if key != "version"})


def parse_r5_key(key: str, language: str) -> str | None:
    """The bare R5 id of `key`: the key itself when bare, or the tail of the stored composite `{lang}:grammar:v{n}:{id}`
    parsed with the strict whole-string pattern (the id may contain ':'; `{lang}` must be `language`). None for a Grammar
    Lab point id, a composite of another language, or a look-alike (section 9.4)."""
    if not key or key.startswith(f"{language}."):
        return None
    if ":grammar:" in key:
        match = _COMPOSITE.fullmatch(key)
        return match.group(3) if match and match.group(1) == language else None
    return key


class GrammarStoreRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    # --- helpers -------------------------------------------------------------------------------------------------

    def _lock(self, statement, connection: Connection):
        return statement.with_for_update() if connection.dialect.name == "postgresql" else statement

    def _event(self, connection: Connection, *, action: str, actor: str, point_id: str | None = None,
               version_id: uuid.UUID | None = None, batch_id: uuid.UUID | None = None, reason: str = "",
               changes: Mapping[str, Any] | None = None, now: datetime | None = None) -> None:
        connection.execute(insert(EVENTS).values(
            id=uuid.uuid4(), point_id=point_id, version_id=version_id, batch_id=batch_id, actor=actor[:255],
            action=action, reason=reason, changes=dict(changes) if changes is not None else None,
            created_at=now or _now(),
        ))

    def _bump(self, connection: Connection, languages: Iterable[str], now: datetime) -> None:
        for language in sorted(set(languages)):
            maker = pg_insert if connection.dialect.name == "postgresql" else sqlite_insert
            statement = maker(STATE).values(language_code=language, revision=1, updated_at=now)
            connection.execute(statement.on_conflict_do_update(
                index_elements=[STATE.c.language_code],
                set_={"revision": STATE.c.revision + 1, "updated_at": statement.excluded.updated_at},
            ))

    @staticmethod
    def revision(connection: Connection, language: str) -> int:
        value = connection.execute(select(STATE.c.revision).where(STATE.c.language_code == language)).scalar()
        return int(value or 0)

    @staticmethod
    def _batch_dict(row) -> dict[str, Any]:
        return {
            "id": str(row.id), "status": row.status, "language": row.language_code, "package_hash": row.package_hash,
            "export_profile": row.export_profile, "schema_version": row.schema_version, "set_version": row.set_version,
            "source_commit": row.source_commit, "exported_at": _iso(row.exported_at), "filename": row.filename,
            "counts": {"new": row.new_count, "changed": row.changed_count, "unchanged": row.unchanged_count,
                       "refused": row.refused_count, "unlisted": row.unlisted_count},
            "diff": row.diff, "refusals": row.refusals or [],
            "rights": None if row.rights_basis is None else {
                "basis": row.rights_basis, "attestation": row.rights_attestation, "attested_by": row.rights_attested_by,
                "attested_at": _iso(row.rights_attested_at)},
            "imported_by": row.imported_by, "created_at": _iso(row.created_at),
        }

    # --- import (section 5) --------------------------------------------------------------------------------------

    def _stored_versions(self, connection: Connection, point_ids: list[str]) -> dict[str, list]:
        rows = connection.execute(select(
            VERSIONS.c.point_id, VERSIONS.c.version, VERSIONS.c.content_hash, VERSIONS.c.review_status,
            VERSIONS.c.is_published, VERSIONS.c.content,
        ).where(VERSIONS.c.point_id.in_(point_ids))).all() if point_ids else []
        out: dict[str, list] = {}
        for row in rows:
            out.setdefault(row.point_id, []).append(row)
        return out

    def _plan(self, connection: Connection, pkg: Package) -> tuple[list[Problem], dict[str, Any]]:
        """DB-dependent checks and the diff (section 5.3-5.4). Returns (hard failures, plan)."""
        manifest = pkg.manifest
        language = manifest["language"]
        entries = {entry["id"]: entry for entry in manifest["points"]}
        failures: list[Problem] = []
        external = sorted(set(manifest["external_references"]))
        if external:
            resolvable = set(connection.execute(
                select(VERSIONS.c.point_id).where(VERSIONS.c.point_id.in_(external),
                                                   or_(VERSIONS.c.review_status == "accepted", VERSIONS.c.is_published))
            ).scalars())
            failures += [Problem("ref.external_unresolved", "external_references",
                                 f"{ref} is not stored with an accepted or published version")
                         for ref in external if ref not in resolvable]
        stored = self._stored_versions(connection, sorted(entries))
        points: dict[str, str] = {}  # point id -> new | changed | unchanged | refused:<code>
        refusals: list[dict[str, str]] = []
        for point_id, entry in sorted(entries.items()):
            rows = stored.get(point_id, [])
            same_version = [r for r in rows if r.version == entry["version"]]
            # `version` is inside the hashed body, so "the same content again" is judged without it (D-106.10).
            fingerprint = content_fingerprint(pkg.bodies[point_id])
            same_hash = [r for r in rows if content_fingerprint(r.content) == fingerprint]
            highest = max((r.version for r in rows), default=0)
            code = ""
            if same_version and same_version[0].content_hash == entry["content_hash"]:
                points[point_id] = "unchanged"
                continue
            if same_version:
                code = "version_not_bumped"
            elif entry["version"] < highest:
                code = "version_lower_than_stored"
            elif same_hash and same_hash[0].review_status == "rejected":
                code = "content_previously_rejected"
            elif same_hash:
                code = "content_already_stored"
            if code:
                points[point_id] = f"refused:{code}"
                refusals.append({"code": code, "point_id": point_id, "path": "version", "message": code.replace("_", " ")})
            else:
                points[point_id] = "changed" if rows else "new"
        published = set(connection.execute(select(POINTS.c.id).where(
            POINTS.c.language_code == language, POINTS.c.lifecycle == "published")).scalars())
        unlisted = sorted(published - set(entries))
        labels = {row.id: row.title for row in connection.execute(select(FUNCTIONS.c.id, FUNCTIONS.c.title)
                  .where(FUNCTIONS.c.id.in_([f["id"] for f in pkg.functions])))}
        function_changes = [{"id": f["id"], "before": labels[f["id"]], "after": f["title"]}
                            for f in pkg.functions if f["id"] in labels and labels[f["id"]] != f["title"]]
        r5_ids = sorted({row["r5_id"] for row in manifest["r5_map"]})
        stored_r5: dict[str, set] = {}
        if r5_ids:
            for row in connection.execute(select(R5.c.r5_id, R5.c.point_id, R5.c.disposition, R5.c.is_primary)
                                          .where(R5.c.language_code == language, R5.c.r5_id.in_(r5_ids))):
                stored_r5.setdefault(row.r5_id, set()).add((row.point_id, row.disposition, row.is_primary))
        incoming_r5: dict[str, set] = {}
        for row in manifest["r5_map"]:
            incoming_r5.setdefault(row["r5_id"], set()).add((row["point_id"], row["disposition"], row["is_primary"]))
        r5_changes = [{"r5_id": rid, "before": sorted(map(list, stored_r5[rid]), key=str),
                       "after": sorted(map(list, incoming_r5[rid]), key=str)}
                      for rid in r5_ids if rid in stored_r5 and stored_r5[rid] != incoming_r5[rid]]
        # Every primary/secondary target must exist after this commit: in the package (and not refused) or stored.
        for rid, rows in incoming_r5.items():
            for point_id, _, _ in rows:
                if point_id is not None and point_id not in entries and point_id not in stored:
                    failures.append(Problem("r5_map.unknown_point", "r5_map", f"{rid} -> {point_id} is not stored"))
        counts = {"new": 0, "changed": 0, "unchanged": 0, "refused": 0}
        for state in points.values():
            counts["refused" if state.startswith("refused") else state] += 1
        plan = {
            "language": language, "points": points, "refusals": refusals, "unlisted": unlisted,
            "function_changes": function_changes, "r5_changes": r5_changes, "counts": counts,
        }
        return failures, plan

    @staticmethod
    def _report(pkg: Package, plan: dict[str, Any] | None, problems: list[Problem]) -> dict[str, Any]:
        manifest = pkg.manifest if isinstance(pkg.manifest, dict) else {}
        report = {
            "language": manifest.get("language"), "set_version": manifest.get("set_version"),
            "package_hash": manifest.get("package_hash"), "point_count": len(manifest.get("points") or []),
            "validator": manifest.get("validator"), "ok": not problems,
            "problems": [p.to_dict() for p in problems[:500]], "problem_count": len(problems),
        }
        if plan is not None:
            points = plan["points"]
            report["diff"] = {
                "points": [{"id": pid, "state": state} for pid, state in sorted(points.items())][:MAX_DIFF_ROWS],
                "unlisted": plan["unlisted"][:MAX_DIFF_ROWS], "function_changes": plan["function_changes"],
                "r5_changes": plan["r5_changes"][:MAX_DIFF_ROWS], "counts": {**plan["counts"],
                                                                              "unlisted": len(plan["unlisted"])},
            }
            report["refusals"] = plan["refusals"]
        return report

    def _existing_import(self, connection: Connection, package_hash: str) -> dict[str, Any] | None:
        row = connection.execute(select(BATCHES).where(BATCHES.c.package_hash == package_hash,
                                                       BATCHES.c.status == "imported")).first()
        return self._batch_dict(row) if row else None

    def _write_rejected(self, pkg: Package, problems: list[Problem], *, filename: str, actor: str) -> dict[str, Any]:
        manifest = pkg.manifest if isinstance(pkg.manifest, dict) else {}

        def text(key: str, limit: int) -> str | None:
            value = manifest.get(key)
            return value[:limit] if isinstance(value, str) else None

        now = _now()
        batch_id = uuid.uuid4()
        with self.engine.begin() as connection:
            connection.execute(insert(BATCHES).values(
                id=batch_id, status="rejected", language_code=text("language", 20), package_hash=text("package_hash", 64),
                export_profile=text("export_profile", 60), profile_schema_hash=text("profile_schema_hash", 64),
                schema_version=text("schema_version", 20), set_version=text("set_version", 120),
                source_commit=text("source_commit", 64), exported_at=None, filename=filename[:255],
                refused_count=len(problems), refusals=[p.to_dict() for p in problems[:500]], manifest=None,
                imported_by=actor[:255], created_at=now,
            ))
            row = connection.execute(select(BATCHES).where(BATCHES.c.id == batch_id)).one()
        return self._batch_dict(row)

    def validate_import(self, pkg: Package) -> dict[str, Any]:
        """The dry run: the full report and diff. Writes nothing."""
        if pkg.problems:
            return self._report(pkg, None, pkg.problems)
        with self.engine.connect() as connection:
            failures, plan = self._plan(connection, pkg)
            existing = self._existing_import(connection, pkg.manifest["package_hash"])
        report = self._report(pkg, plan, failures)
        report["already_imported"] = existing
        return report

    def commit_import(self, pkg: Package, *, filename: str, actor: str, echoed_hash: str,
                      rights: Mapping[str, str] | None = None) -> ImportOutcome:
        """Commit one validated package in one transaction (section 5.3). A hard failure writes a rejected receipt."""
        manifest = pkg.manifest
        if pkg.problems:
            batch = self._write_rejected(pkg, pkg.problems, filename=filename, actor=actor)
            return ImportOutcome("rejected", batch, self._report(pkg, None, pkg.problems))
        if echoed_hash != manifest["package_hash"]:
            raise GrammarStoreRefusal("grammar_package_hash_mismatch",
                                      "the echoed package hash is not the uploaded package's", status=409)
        if rights is not None and rights.get("basis") not in RIGHTS_BASES:
            raise GrammarStoreRefusal("grammar_rights_invalid", "rights basis must be one of " + ", ".join(RIGHTS_BASES))
        try:
            with self.engine.begin() as connection:
                existing = self._existing_import(connection, manifest["package_hash"])
                if existing:
                    return ImportOutcome("already_imported", existing)
                failures, plan = self._plan(connection, pkg)
                if failures:
                    raise _Rejected(failures, plan)
                return self._commit(connection, pkg, plan, filename=filename, actor=actor, rights=rights)
        except _Rejected as rejected:
            batch = self._write_rejected(pkg, rejected.failures, filename=filename, actor=actor)
            return ImportOutcome("rejected", batch, self._report(pkg, rejected.plan, rejected.failures))
        except IntegrityError:
            with self.engine.connect() as connection:  # a concurrent commit of the same package won the race
                existing = self._existing_import(connection, manifest["package_hash"])
            if existing:
                return ImportOutcome("already_imported", existing)
            raise

    def _commit(self, connection: Connection, pkg: Package, plan: dict[str, Any], *, filename: str, actor: str,
                rights: Mapping[str, str] | None) -> ImportOutcome:
        manifest = pkg.manifest
        language = manifest["language"]
        now = _now()
        batch_id = uuid.uuid4()
        report = self._report(pkg, plan, [])
        attested = rights is not None
        connection.execute(insert(BATCHES).values(
            id=batch_id, status="imported", language_code=language, package_hash=manifest["package_hash"],
            export_profile=manifest["export_profile"], profile_schema_hash=manifest["profile_schema_hash"],
            schema_version=manifest["schema_version"], set_version=manifest["set_version"][:120],
            source_commit=manifest["source_commit"][:64], exported_at=_exported_at(manifest["exported_at"]),
            filename=filename[:255], new_count=plan["counts"]["new"], changed_count=plan["counts"]["changed"],
            unchanged_count=plan["counts"]["unchanged"], refused_count=plan["counts"]["refused"],
            unlisted_count=len(plan["unlisted"]), diff=report["diff"], refusals=plan["refusals"],
            manifest=manifest,  # the manifest carries no point body; bodies live only in the version rows
            rights_basis=rights["basis"] if attested else None,
            rights_attestation=rights["attestation"] if attested else None,
            rights_attested_by=actor[:255] if attested else None, rights_attested_at=now if attested else None,
            imported_by=actor[:255], created_at=now,
        ))
        # Function labels: the later batch wins; a change that affects published points bumps their languages (N-2).
        stored_labels = {row.id for row in connection.execute(select(FUNCTIONS.c.id).where(
            FUNCTIONS.c.id.in_([f["id"] for f in pkg.functions])))}
        bump_languages: set[str] = set()
        for function in pkg.functions:
            if function["id"] in stored_labels:
                change = next((c for c in plan["function_changes"] if c["id"] == function["id"]), None)
                if change is None:
                    continue
                connection.execute(update(FUNCTIONS).where(FUNCTIONS.c.id == function["id"]).values(
                    title=function["title"], batch_id=batch_id, updated_at=now))
                self._event(connection, action="function_label_changed", actor=actor, batch_id=batch_id,
                            changes=change, now=now)
                bump_languages |= set(connection.execute(select(POINTS.c.language_code).where(
                    POINTS.c.function_id == function["id"], POINTS.c.lifecycle == "published")).scalars())
            else:
                connection.execute(insert(FUNCTIONS).values(id=function["id"], title=function["title"],
                                                            batch_id=batch_id, updated_at=now))
        entries = {entry["id"]: entry for entry in manifest["points"]}
        existing_points = set(connection.execute(select(POINTS.c.id).where(POINTS.c.id.in_(sorted(entries)))).scalars())
        new_points = [pid for pid in sorted(entries) if pid not in existing_points
                      and plan["points"][pid] in {"new", "changed"}]
        if new_points:
            connection.execute(insert(POINTS), [{"id": pid, "language_code": language, "lifecycle": "unpublished",
                                                 "created_at": now, "updated_at": now} for pid in new_points])
        version_rows = []
        for point_id in sorted(entries):
            if plan["points"][point_id] not in {"new", "changed"}:
                continue
            entry = entries[point_id]
            version_rows.append({
                "id": uuid.uuid4(), "point_id": point_id, "version": entry["version"],
                "content": pkg.bodies[point_id], "content_hash": entry["content_hash"], "source_status": "approved",
                "review_status": "imported", "is_published": False,
                "rights_status": "cleared" if attested else "unknown", "provenance": entry["provenance"],
                "batch_id": batch_id, "imported_at": now,
            })
        if version_rows:
            connection.execute(insert(VERSIONS), version_rows)
            connection.execute(insert(EVENTS), [{
                "id": uuid.uuid4(), "point_id": row["point_id"], "version_id": row["id"], "batch_id": batch_id,
                "actor": actor[:255], "action": "imported", "reason": "", "changes": None, "created_at": now,
            } for row in version_rows])
        # The R5 map: this batch's rows replace every earlier row for each R5 id it lists (section 9.2). Never by
        # publish. A row whose point the batch refused still targets an already stored point (checked in _plan).
        rows_by_id: dict[str, list[dict[str, Any]]] = {}
        for row in manifest["r5_map"]:
            rows_by_id.setdefault(row["r5_id"], []).append(row)
        if rows_by_id:
            connection.execute(delete(R5).where(R5.c.language_code == language,
                                                R5.c.r5_id.in_(sorted(rows_by_id))))
            connection.execute(insert(R5), [{
                "id": uuid.uuid4(), "language_code": language, "r5_id": row["r5_id"], "point_id": row["point_id"],
                "disposition": row["disposition"], "is_primary": row["is_primary"], "batch_id": batch_id,
                "created_at": now,
            } for rows in rows_by_id.values() for row in rows])
            for change in plan["r5_changes"]:
                self._event(connection, action="r5_map_changed", actor=actor, batch_id=batch_id, changes=change,
                            now=now)
        if attested:
            self._event(connection, action="rights_attested", actor=actor, batch_id=batch_id,
                        changes={"basis": rights["basis"]}, reason=rights["attestation"][:2000], now=now)
        if bump_languages:
            self._bump(connection, bump_languages, now)
        row = connection.execute(select(BATCHES).where(BATCHES.c.id == batch_id)).one()
        return ImportOutcome("imported", self._batch_dict(row), report)

    # --- rights and review (section 6) -----------------------------------------------------------------------------

    def attest_batch(self, batch_id: Any, *, basis: str, attestation: str, actor: str) -> dict[str, Any]:
        if basis not in RIGHTS_BASES or not attestation.strip():
            raise GrammarStoreRefusal("grammar_rights_invalid", "a basis and an attestation text are required")
        batch_uuid = _uuid(batch_id)
        now = _now()
        with self.engine.begin() as connection:
            row = connection.execute(self._lock(select(BATCHES).where(BATCHES.c.id == batch_uuid), connection)).first()
            if row is None:
                raise GrammarStoreRefusal("grammar_batch_not_found", "no such import batch", status=404)
            if row.status != "imported":
                raise GrammarStoreRefusal("grammar_batch_rejected", "a rejected batch has no content to attest", status=409)
            if row.rights_basis is not None:
                raise GrammarStoreRefusal("grammar_rights_already_attested", "this batch is already attested", status=409)
            connection.execute(update(BATCHES).where(BATCHES.c.id == batch_uuid).values(
                rights_basis=basis, rights_attestation=attestation.strip(), rights_attested_by=actor[:255],
                rights_attested_at=now))
            cleared = connection.execute(update(VERSIONS).where(
                VERSIONS.c.batch_id == batch_uuid, VERSIONS.c.rights_status == "unknown").values(rights_status="cleared"))
            self._event(connection, action="rights_attested", actor=actor, batch_id=batch_uuid,
                        reason=attestation.strip()[:2000], changes={"basis": basis, "versions": cleared.rowcount},
                        now=now)
            row = connection.execute(select(BATCHES).where(BATCHES.c.id == batch_uuid)).one()
        return self._batch_dict(row)

    def _version_row(self, connection: Connection, version_id: Any, *, lock: bool = False):
        statement = select(VERSIONS).where(VERSIONS.c.id == _uuid(version_id))
        row = connection.execute(self._lock(statement, connection) if lock else statement).first()
        if row is None:
            raise GrammarStoreRefusal("grammar_version_not_found", "no such version", status=404)
        return row

    def review_version(self, version_id: Any, *, decision: str, actor: str, reason: str = "") -> dict[str, Any]:
        if decision not in {"accept", "reject"}:
            raise GrammarStoreRefusal("grammar_review_invalid", "decision must be accept or reject")
        if decision == "reject" and not reason.strip():
            raise GrammarStoreRefusal("grammar_review_reason_required", "a rejection needs a reason")
        now = _now()
        with self.engine.begin() as connection:
            row = self._version_row(connection, version_id, lock=True)
            if row.review_status != "imported":
                raise GrammarStoreRefusal("grammar_review_closed", f"the version is already {row.review_status}",
                                          status=409)
            status = "accepted" if decision == "accept" else "rejected"
            connection.execute(update(VERSIONS).where(VERSIONS.c.id == row.id).values(
                review_status=status, reviewed_by=actor[:255], reviewed_at=now, review_note=reason.strip() or None))
            self._event(connection, action=status, actor=actor, point_id=row.point_id, version_id=row.id,
                        reason=reason.strip(), now=now)
        return self.version_summary(row.id)

    def set_version_rights(self, version_id: Any, *, status: str, actor: str, reason: str) -> dict[str, Any]:
        """`restricted` blocks publishing (and unpublishes the version if it is served); `cleared` needs an attested
        batch."""
        if status not in {"restricted", "cleared"} or not reason.strip():
            raise GrammarStoreRefusal("grammar_rights_invalid", "status restricted or cleared, with a reason")
        now = _now()
        with self.engine.begin() as connection:
            row = self._version_row(connection, version_id, lock=True)
            if status == "cleared":
                attested = connection.execute(select(BATCHES.c.rights_basis).where(BATCHES.c.id == row.batch_id)).scalar()
                if attested is None:
                    raise GrammarStoreRefusal("grammar_rights_unattested", "attest the batch first", status=409)
            if row.is_published and status == "restricted":
                self._unpublish(connection, row.point_id, actor=actor, reason=f"rights restricted: {reason}", now=now)
            connection.execute(update(VERSIONS).where(VERSIONS.c.id == row.id).values(rights_status=status))
            self._event(connection, action="rights_set", actor=actor, point_id=row.point_id, version_id=row.id,
                        reason=reason.strip(), changes={"before": row.rights_status, "after": status}, now=now)
        return self.version_summary(row.id)

    # --- publish, unpublish, archive (section 6) --------------------------------------------------------------------

    def publish(self, pairs: list[tuple[str, Any]], *, actor: str, override_references: bool = False,
                reason: str = "") -> dict[str, Any]:
        """All-or-nothing. Every check runs against the state the transaction will leave (section 6)."""
        if not pairs or len(pairs) > MAX_BULK_PUBLISH:
            raise GrammarStoreRefusal("grammar_publish_invalid", f"between 1 and {MAX_BULK_PUBLISH} versions")
        if len({point for point, _ in pairs}) != len(pairs):
            raise GrammarStoreRefusal("grammar_publish_invalid", "a point appears twice")
        if override_references and len(pairs) != 1:
            raise GrammarStoreRefusal("grammar_publish_invalid", "the reference override is for a single point only")
        now = _now()
        with self.engine.begin() as connection:
            point_ids = sorted(point for point, _ in pairs)
            points = {row.id: row for row in connection.execute(
                self._lock(select(POINTS).where(POINTS.c.id.in_(point_ids)).order_by(POINTS.c.id), connection))}
            versions = {}
            for point_id, version_id in pairs:
                if point_id not in points:
                    raise GrammarStoreRefusal("grammar_point_not_found", f"{point_id} is not stored", status=404)
                row = self._version_row(connection, version_id, lock=True)
                if row.point_id != point_id:
                    raise GrammarStoreRefusal("grammar_publish_invalid", f"that version is not {point_id}'s")
                if points[point_id].lifecycle == "archived":
                    raise GrammarStoreRefusal("grammar_point_archived", f"restore {point_id} first", status=409)
                if row.review_status != "accepted":
                    raise GrammarStoreRefusal("grammar_not_accepted", f"{point_id} v{row.version} is {row.review_status}",
                                              status=409)
                if row.rights_status != "cleared":
                    raise GrammarStoreRefusal("grammar_rights_not_cleared", f"{point_id} v{row.version} rights are"
                                              f" {row.rights_status}", status=409)
                versions[point_id] = row
            functions = {row.id: row.title for row in connection.execute(select(FUNCTIONS.c.id, FUNCTIONS.c.title)
                         .where(FUNCTIONS.c.id.in_(sorted({v.content["function"] for v in versions.values()}))))}
            for row in versions.values():
                if not _label_complete(functions.get(row.content["function"])):
                    raise GrammarStoreRefusal("grammar_function_label_incomplete",
                                              f"{row.content['function']} has no complete label", status=409)
            published_after = set(connection.execute(select(POINTS.c.id).where(POINTS.c.lifecycle == "published"))
                                  .scalars()) | set(versions)
            dangling = {pid: sorted(_references(row.content) - published_after) for pid, row in versions.items()}
            dangling = {pid: refs for pid, refs in dangling.items() if refs}
            if dangling and not override_references:
                raise GrammarStoreRefusal("grammar_references_unpublished", "published references would dangle",
                                          status=409, context={"dangling": dangling})
            connection.execute(update(VERSIONS).where(
                VERSIONS.c.point_id.in_(point_ids), VERSIONS.c.is_published,
                VERSIONS.c.id.notin_([row.id for row in versions.values()]),
            ).values(is_published=False, superseded_at=now))
            for point_id, row in versions.items():
                body = row.content
                connection.execute(update(VERSIONS).where(VERSIONS.c.id == row.id).values(
                    is_published=True, superseded_at=None))
                connection.execute(update(POINTS).where(POINTS.c.id == point_id).values(
                    lifecycle="published", published_at=now, updated_at=now, function_id=body["function"],
                    level_framework=body["level"]["framework"], level_value=body["level"]["value"],
                    level_rank=body["level"]["rank"], sequence=body["sequence"], point_type=body["point_type"],
                    native_title=body["header"]["native_title"],
                    native_title_pinyin=body["header"].get("native_title_pinyin")))
                connection.execute(delete(TAGS).where(TAGS.c.point_id == point_id))
                mistakes = {m["error_tag"] for m in body.get("common_mistakes", [])}
                tags = [{"point_id": point_id, "error_tag": tag, "has_mistake": tag in mistakes}
                        for tag in body.get("error_tags", [])]
                if tags:
                    connection.execute(insert(TAGS), tags)
                changes = {"version": row.version}
                if point_id in dangling:
                    changes["override_references"] = dangling[point_id]
                self._event(connection, action="published", actor=actor, point_id=point_id, version_id=row.id,
                            reason=reason, changes=changes, now=now)
            self._bump(connection, {points[pid].language_code for pid in versions}, now)
        return {"published": [{"point_id": pid, "version_id": str(row.id), "version": row.version}
                              for pid, row in sorted(versions.items())]}

    def _unpublish(self, connection: Connection, point_id: str, *, actor: str, reason: str, now: datetime) -> None:
        connection.execute(update(VERSIONS).where(VERSIONS.c.point_id == point_id, VERSIONS.c.is_published)
                           .values(is_published=False))
        language = connection.execute(select(POINTS.c.language_code).where(POINTS.c.id == point_id)).scalar()
        connection.execute(update(POINTS).where(POINTS.c.id == point_id).values(
            lifecycle="unpublished", unpublished_at=now, updated_at=now))
        connection.execute(delete(TAGS).where(TAGS.c.point_id == point_id))
        self._event(connection, action="unpublished", actor=actor, point_id=point_id, reason=reason, now=now)
        self._bump(connection, [language], now)

    def set_point_status(self, point_id: str, *, action: str, actor: str, reason: str = "") -> dict[str, Any]:
        if action not in {"unpublish", "archive", "restore"}:
            raise GrammarStoreRefusal("grammar_status_invalid", "action must be unpublish, archive or restore")
        now = _now()
        with self.engine.begin() as connection:
            row = connection.execute(self._lock(select(POINTS).where(POINTS.c.id == point_id), connection)).first()
            if row is None:
                raise GrammarStoreRefusal("grammar_point_not_found", f"{point_id} is not stored", status=404)
            if action == "unpublish":
                if row.lifecycle != "published":
                    raise GrammarStoreRefusal("grammar_status_invalid", f"{point_id} is {row.lifecycle}", status=409)
                self._unpublish(connection, point_id, actor=actor, reason=reason, now=now)
            elif action == "archive":
                if row.lifecycle == "archived":
                    raise GrammarStoreRefusal("grammar_status_invalid", f"{point_id} is already archived", status=409)
                if row.lifecycle == "published":
                    self._unpublish(connection, point_id, actor=actor, reason=reason, now=now)
                connection.execute(update(POINTS).where(POINTS.c.id == point_id).values(lifecycle="archived",
                                                                                         updated_at=now))
                self._event(connection, action="archived", actor=actor, point_id=point_id, reason=reason, now=now)
            else:
                if row.lifecycle != "archived":
                    raise GrammarStoreRefusal("grammar_status_invalid", f"{point_id} is not archived", status=409)
                connection.execute(update(POINTS).where(POINTS.c.id == point_id).values(lifecycle="unpublished",
                                                                                         updated_at=now))
                self._event(connection, action="restored", actor=actor, point_id=point_id, reason=reason, now=now)
        return self.admin_point(point_id)

    # --- admin reads -------------------------------------------------------------------------------------------------

    def list_batches(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(BATCHES).order_by(BATCHES.c.created_at.desc(), BATCHES.c.id.desc())
                                      .limit(max(1, min(limit, 200)))).all()
        return [self._batch_dict(row) for row in rows]

    def get_batch(self, batch_id: Any) -> dict[str, Any]:
        with self.engine.connect() as connection:
            row = connection.execute(select(BATCHES).where(BATCHES.c.id == _uuid(batch_id))).first()
        if row is None:
            raise GrammarStoreRefusal("grammar_batch_not_found", "no such import batch", status=404)
        out = self._batch_dict(row)
        out["manifest"] = row.manifest
        return out

    def version_summary(self, version_id: Any) -> dict[str, Any]:
        with self.engine.connect() as connection:
            row = self._version_row(connection, version_id)
        return self._version_dict(row)

    @staticmethod
    def _version_dict(row) -> dict[str, Any]:
        return {
            "id": str(row.id), "point_id": row.point_id, "version": row.version, "content_hash": row.content_hash,
            "review_status": row.review_status, "is_published": bool(row.is_published),
            "superseded_at": _iso(row.superseded_at), "rights_status": row.rights_status, "batch_id": str(row.batch_id),
            "imported_at": _iso(row.imported_at), "reviewed_by": row.reviewed_by, "reviewed_at": _iso(row.reviewed_at),
            "review_note": row.review_note,
        }

    def list_points(self, *, language: str | None = None, lifecycle: str | None = None, review: str | None = None,
                    limit: int = 200) -> list[dict[str, Any]]:
        statement = select(POINTS).order_by(POINTS.c.language_code, POINTS.c.level_rank, POINTS.c.function_id,
                                            POINTS.c.sequence, POINTS.c.id).limit(max(1, min(limit, 1000)))
        if language:
            statement = statement.where(POINTS.c.language_code == language)
        if lifecycle:
            statement = statement.where(POINTS.c.lifecycle == lifecycle)
        if review:
            statement = statement.where(POINTS.c.id.in_(select(VERSIONS.c.point_id).where(VERSIONS.c.review_status == review)))
        with self.engine.connect() as connection:
            rows = connection.execute(statement).all()
        return [{"id": r.id, "language": r.language_code, "lifecycle": r.lifecycle, "function": r.function_id,
                 "level": None if r.level_rank is None else {"framework": r.level_framework, "value": r.level_value,
                                                              "rank": r.level_rank},
                 "sequence": r.sequence, "published_at": _iso(r.published_at)} for r in rows]

    def admin_point(self, point_id: str) -> dict[str, Any]:
        with self.engine.connect() as connection:
            row = connection.execute(select(POINTS).where(POINTS.c.id == point_id)).first()
            if row is None:
                raise GrammarStoreRefusal("grammar_point_not_found", f"{point_id} is not stored", status=404)
            versions = connection.execute(select(VERSIONS).where(VERSIONS.c.point_id == point_id)
                                          .order_by(VERSIONS.c.version)).all()
            events = connection.execute(select(EVENTS).where(EVENTS.c.point_id == point_id)
                                        .order_by(EVENTS.c.created_at, EVENTS.c.id)).all()
        return {
            "id": row.id, "language": row.language_code, "lifecycle": row.lifecycle,
            "published_at": _iso(row.published_at), "unpublished_at": _iso(row.unpublished_at),
            "versions": [self._version_dict(v) for v in versions],
            "events": [{"action": e.action, "actor": e.actor, "version_id": str(e.version_id) if e.version_id else None,
                        "reason": e.reason, "changes": e.changes, "created_at": _iso(e.created_at)} for e in events],
        }

    def preview(self, version_id: Any) -> dict[str, Any]:
        with self.engine.connect() as connection:
            row = self._version_row(connection, version_id)
        return {"version": self._version_dict(row), "point": contract.served_point(row.content)}

    def r5_rows(self, language: str) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(R5).where(R5.c.language_code == language)
                                      .order_by(R5.c.r5_id, R5.c.is_primary.desc(), R5.c.point_id)).all()
        return [{"r5_id": r.r5_id, "point_id": r.point_id, "disposition": r.disposition, "is_primary": bool(r.is_primary)}
                for r in rows]

    def coverage(self, language: str) -> list[str]:
        """R5 ids with neither a published primary nor a dropped row: what must be empty before R5 removal (step 9)."""
        with self.engine.connect() as connection:
            rows = connection.execute(select(R5.c.r5_id, R5.c.disposition, POINTS.c.lifecycle)
                                      .select_from(R5.outerjoin(POINTS, POINTS.c.id == R5.c.point_id))
                                      .where(R5.c.language_code == language,
                                             or_(R5.c.is_primary, R5.c.disposition == "dropped"))).all()
            all_ids = set(connection.execute(select(R5.c.r5_id).where(R5.c.language_code == language)).scalars())
        resolved = {r.r5_id for r in rows if r.disposition == "dropped" or r.lifecycle == "published"}
        return sorted(all_ids - resolved)

    # --- learner reads (sections 7, 9, 11) ---------------------------------------------------------------------------

    def catalog(self, language: str, *, level: str | None = None) -> dict[str, Any]:
        """Revision read FIRST, then the points (section 11): content may be newer than its label, never older."""
        with self.engine.connect() as connection:
            revision = self.revision(connection, language)
            statement = (select(POINTS, VERSIONS.c.content, VERSIONS.c.content_hash)
                         .select_from(POINTS.join(VERSIONS, and_(VERSIONS.c.point_id == POINTS.c.id,
                                                                 VERSIONS.c.is_published)))
                         .where(POINTS.c.language_code == language, POINTS.c.lifecycle == "published")
                         .order_by(POINTS.c.level_rank, POINTS.c.function_id, POINTS.c.sequence, POINTS.c.id))
            if level:
                statement = statement.where(POINTS.c.level_value == level)
            rows = connection.execute(statement).all()
            function_ids = sorted({row.function_id for row in rows})
            labels = {row.id: row.title for row in connection.execute(
                select(FUNCTIONS.c.id, FUNCTIONS.c.title).where(FUNCTIONS.c.id.in_(function_ids)))}
            level_rows = connection.execute(
                select(POINTS.c.level_framework, POINTS.c.level_value, POINTS.c.level_rank).distinct()
                .where(POINTS.c.language_code == language, POINTS.c.lifecycle == "published")
                .order_by(POINTS.c.level_rank)).all()
        points = []
        for row in rows:
            header = row.content["header"]
            points.append({
                "id": row.id,
                "header": {key: header[key] for key in ("native_title", "native_title_pinyin", "title", "sub")
                           if key in header},
                "level": {"framework": row.level_framework, "value": row.level_value, "rank": row.level_rank},
                "function": row.function_id, "sequence": row.sequence, "point_type": row.point_type,
                "error_tags": row.content.get("error_tags", []), "aliases": row.content.get("aliases", []),
                "content_hash": row.content_hash,
            })
        return {
            "language": language, "catalog_revision": revision,
            "functions": [{"id": fid, "title": labels.get(fid)} for fid in function_ids],
            "levels": [{"framework": r.level_framework, "value": r.level_value, "rank": r.level_rank} for r in level_rows],
            "points": points,
        }

    def published(self, language: str, point_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(VERSIONS.c.version, VERSIONS.c.content_hash, VERSIONS.c.content)
                .select_from(VERSIONS.join(POINTS, POINTS.c.id == VERSIONS.c.point_id))
                .where(VERSIONS.c.point_id == point_id, VERSIONS.c.is_published, POINTS.c.lifecycle == "published",
                       POINTS.c.language_code == language)).first()
        if row is None:
            return None
        return {"version": row.version, "content_hash": row.content_hash, "point": contract.served_point(row.content)}

    def resolve_r5(self, language: str, key: str) -> dict[str, Any] | None:
        """An old R5 id (bare or composite) -> redirect / unavailable / dropped; None when the map does not know it or
        its target has no accepted or published version yet (section 9.3)."""
        r5_id = parse_r5_key(key, language)
        if not r5_id:
            return None
        with self.engine.connect() as connection:
            row = connection.execute(select(R5.c.point_id, R5.c.disposition).where(
                R5.c.language_code == language, R5.c.r5_id == r5_id,
                or_(R5.c.is_primary, R5.c.point_id.is_(None)))).first()
            if row is None:
                return None
            if row.disposition == "dropped":
                return {"point": None, "dropped": True}
            lifecycle = connection.execute(select(POINTS.c.lifecycle).where(POINTS.c.id == row.point_id)).scalar()
            if lifecycle == "published":
                return {"point": None, "redirect": row.point_id}
            usable = connection.execute(select(func.count()).select_from(VERSIONS).where(
                VERSIONS.c.point_id == row.point_id, VERSIONS.c.review_status == "accepted")).scalar()
        return {"point": None, "unavailable": True, "point_id": row.point_id} if usable else None

    def by_error(self, language: str, error_tag: str, *, level_rank: int | None = None, limit: int = 5) -> list[dict]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(POINTS.c.id, POINTS.c.level_framework, POINTS.c.level_value, POINTS.c.level_rank,
                       TAGS.c.has_mistake, VERSIONS.c.content)
                .select_from(TAGS.join(POINTS, POINTS.c.id == TAGS.c.point_id)
                             .join(VERSIONS, and_(VERSIONS.c.point_id == POINTS.c.id, VERSIONS.c.is_published)))
                .where(TAGS.c.error_tag == error_tag, POINTS.c.language_code == language,
                       POINTS.c.lifecycle == "published")).all()

        def rank(row) -> tuple:
            distance = abs((row.level_rank or 0) - level_rank) if level_rank is not None else 0
            return (distance, not row.has_mistake, row.id)

        out = []
        for row in sorted(rows, key=rank)[:max(1, min(limit, 20))]:
            mistake = next((m for m in row.content.get("common_mistakes", []) if m["error_tag"] == error_tag), None)
            out.append({"grammar_id": row.id, "title": row.content["header"]["title"],
                        "level": {"framework": row.level_framework, "value": row.level_value, "rank": row.level_rank},
                        "reason": mistake["reason"] if mistake else None})
        return out

    def progress_map(self, language: str, point_ids: Iterable[str] | None = None) -> dict[str, list[str]]:
        """Published point -> the R5 ids whose PRIMARY row targets it (split secondaries inherit nothing)."""
        statement = (select(R5.c.point_id, R5.c.r5_id)
                     .select_from(R5.join(POINTS, POINTS.c.id == R5.c.point_id))
                     .where(R5.c.language_code == language, R5.c.is_primary, POINTS.c.lifecycle == "published"))
        if point_ids is not None:
            statement = statement.where(R5.c.point_id.in_(sorted(set(point_ids))))
        out: dict[str, list[str]] = {}
        with self.engine.connect() as connection:
            for row in connection.execute(statement):
                out.setdefault(row.point_id, []).append(row.r5_id)
        return {k: sorted(v) for k, v in out.items()}

    def published_ids(self, language: str) -> set[str]:
        with self.engine.connect() as connection:
            return set(connection.execute(select(POINTS.c.id).where(
                POINTS.c.language_code == language, POINTS.c.lifecycle == "published")).scalars())


class _Rejected(Exception):
    def __init__(self, failures: list[Problem], plan: dict[str, Any]) -> None:
        super().__init__("rejected")
        self.failures = failures
        self.plan = plan
