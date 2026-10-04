"""Content-addressed key/value asset storage for the Reading Library.

`BookAssetStore` is the abstraction ORENA_CONTENT_EXECUTION_ARCHITECTURE.md's
storage-abstraction requirement asks for: the catalog/repository layer stores
only a `key` string, never a filesystem path or provider URL, so swapping the
concrete backend (filesystem here; an S3-compatible object store later) never
touches the domain model or callers. `FilesystemBookAssetStore` is the only
concrete implementation this round - local/dev/sandbox only, no credentials,
no paid provider.

Keys are always caller-chosen, forward-slash-separated, ASCII identifiers -
never a raw filename - so a malicious original filename cannot influence
where bytes land. `_validate_key` is backend-independent: it protects a future
S3-compatible backend from key-traversal the same way it protects the
filesystem backend today.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

_KEY_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]+$")


class InvalidAssetKey(ValueError):
    """A key that is not a safe, backend-independent relative path."""


class AssetNotFound(KeyError):
    """No bytes are stored under this key."""


def _validate_key(key: str) -> tuple[str, ...]:
    if not key or key != key.strip():
        raise InvalidAssetKey(f"Asset key must be non-empty and untrimmed: {key!r}")
    segments = key.split("/")
    for segment in segments:
        if segment in ("", ".", "..") or not _KEY_SEGMENT.fullmatch(segment):
            raise InvalidAssetKey(f"Asset key segment is not safe: {key!r}")
    return tuple(segments)


class BookAssetStore(Protocol):
    """put/get/exists/delete over opaque keys. No path, URL or provider leaks
    through this boundary - `url_for` is deliberately absent; a caller that
    needs a servable URL builds one from the key via its own route, not from
    anything the store returns."""

    def put(self, key: str, data: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None: ...

    def delete_prefix(self, prefix: str) -> int: ...


class FilesystemBookAssetStore:
    """Local/dev/sandbox `BookAssetStore`. One file per key under `root`.

    `delete` is idempotent (missing key is not an error) so best-effort
    cleanup after a partial import never raises on an asset that was never
    written or was already removed.

    The constructor never touches the filesystem - `root` is created lazily
    by `put()`, the same way every existing `*_DB` path in this codebase is
    created lazily by its own writer rather than at startup. Constructing
    this store (which `app.py` does unconditionally, including when the
    backend is SQLite and the feature goes unused) must stay safe under a
    read-only repository mount such as the documented test/CI container.
    """

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _path_for(self, key: str) -> Path:
        segments = _validate_key(key)
        candidate = self._root.joinpath(*segments).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:
            raise InvalidAssetKey(f"Asset key escapes the storage root: {key!r}") from exc
        return candidate

    def put(self, key: str, data: bytes) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp-{id(data)}")
        tmp.write_bytes(data)
        tmp.replace(path)

    def get(self, key: str) -> bytes:
        path = self._path_for(key)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise AssetNotFound(key) from exc

    def exists(self, key: str) -> bool:
        return self._path_for(key).is_file()

    def delete(self, key: str) -> None:
        path = self._path_for(key)
        path.unlink(missing_ok=True)

    def list_prefix(self, prefix: str) -> list[str]:
        """Every key stored directly under `prefix/`, sorted. Read-only; the prefix is
        validated like a key, so it can never name anything outside the root."""
        directory = self._path_for(prefix)
        if not directory.is_dir():
            return []
        return sorted(
            f"{prefix.rstrip('/')}/{path.name}" for path in directory.iterdir() if path.is_file()
        )

    def delete_prefix(self, prefix: str) -> int:
        """Remove every file stored under `prefix/` and return how many went. Idempotent; the prefix is validated
        like a key, so it can never name anything outside the root."""
        directory = self._path_for(prefix)
        if not directory.is_dir():
            return 0
        removed = 0
        for path in sorted(directory.rglob('*'), reverse=True):
            if path.is_file():
                path.unlink(missing_ok=True)
                removed += 1
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        try:
            directory.rmdir()
        except OSError:
            pass
        return removed
