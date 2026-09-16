"""FilesystemBookAssetStore: put/get/exists/delete plus the key-traversal
guard that must hold regardless of which concrete backend is installed."""
from __future__ import annotations

import pytest

from writing_coach.book_asset_store import (
    AssetNotFound,
    FilesystemBookAssetStore,
    InvalidAssetKey,
)


@pytest.fixture()
def store(tmp_path):
    return FilesystemBookAssetStore(tmp_path / "assets")


def test_put_then_get_round_trips_bytes(store):
    store.put("books/abc/original.epub", b"epub-bytes")
    assert store.get("books/abc/original.epub") == b"epub-bytes"


def test_exists_reflects_writes_and_deletes(store):
    assert store.exists("books/abc/cover.jpg") is False
    store.put("books/abc/cover.jpg", b"jpeg-bytes")
    assert store.exists("books/abc/cover.jpg") is True
    store.delete("books/abc/cover.jpg")
    assert store.exists("books/abc/cover.jpg") is False


def test_get_missing_key_raises_asset_not_found(store):
    with pytest.raises(AssetNotFound):
        store.get("books/does-not-exist/original.epub")


def test_delete_missing_key_is_idempotent(store):
    store.delete("books/never-written/original.epub")  # must not raise


@pytest.mark.parametrize(
    "key",
    [
        "../escape/original.epub",
        "books/../../escape.epub",
        "/absolute/path.epub",
        "books//double-slash.epub",
        "books/abc/",
        "",
        "books/abc/ trailing-space.epub ",
    ],
)
def test_unsafe_keys_are_rejected(store, key):
    with pytest.raises(InvalidAssetKey):
        store.put(key, b"data")


def test_nested_keys_create_parent_directories_automatically(store):
    store.put("books/abc/chapters/0.json", b"{}")
    assert store.get("books/abc/chapters/0.json") == b"{}"
