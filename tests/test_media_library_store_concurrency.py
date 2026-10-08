"""Two writes that land at the same moment both stay in the shared media index.

The index is one JSON file rewritten whole on every change. FastAPI runs a
plain `def` route in a thread pool, so two imports (or an import and a
learner's upload) can each read the same index, add their own entry and write
back - and the second write silently erases the first. The barrier below holds
both writers between their read and their write, which is exactly that race.
"""
import threading

from writing_coach.media_library_store import FileMediaLibraryStore, MediaLibraryEntry


def _entry(media_id: str) -> MediaLibraryEntry:
    return MediaLibraryEntry(
        media_id=media_id, media_type="audio", provider="upload", provider_media_id=media_id,
        canonical_url="", playback={"provider": "orena", "kind": "audio", "url": f"/api/media/files/media/{media_id}/original.wav"},
        title=media_id, thumbnail={"kind": "none", "ref": ""}, duration_ms=1000, language="en", level="", creator="",
        source={"provider": "upload", "type": "upload", "provenance_url": "", "license": "", "review_status": "",
                "imported_by": "admin"},
        library="shared", created_at="2026-09-18T00:00:00+00:00", lesson=None,
    )


def _race(store: FileMediaLibraryStore, monkeypatch, *operations) -> None:
    barrier = threading.Barrier(len(operations), timeout=0.5)
    original = FileMediaLibraryStore._read

    def read_then_wait(self):
        entries = original(self)
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            # A serialized writer waits alone and is released by the timeout.
            pass
        return entries

    monkeypatch.setattr(FileMediaLibraryStore, "_read", read_then_wait)
    threads = [threading.Thread(target=operation) for operation in operations]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    monkeypatch.setattr(FileMediaLibraryStore, "_read", original)


def test_concurrent_upserts_keep_every_entry(tmp_path, monkeypatch):
    store = FileMediaLibraryStore(tmp_path)
    _race(store, monkeypatch, lambda: store.upsert(_entry("upload-a")), lambda: store.upsert(_entry("upload-b")))
    assert {item.media_id for item in store.list()} == {"upload-a", "upload-b"}
    assert store.last_read_issue == ""


def test_a_delete_racing_an_upsert_loses_neither_change(tmp_path, monkeypatch):
    store = FileMediaLibraryStore(tmp_path)
    store.upsert(_entry("upload-old"))
    _race(store, monkeypatch, lambda: store.delete("upload-old"), lambda: store.upsert(_entry("upload-new")))
    assert {item.media_id for item in store.list()} == {"upload-new"}


def test_two_store_objects_on_one_index_share_the_writer(tmp_path, monkeypatch):
    first, second = FileMediaLibraryStore(tmp_path), FileMediaLibraryStore(tmp_path)
    _race(first, monkeypatch, lambda: first.upsert(_entry("upload-a")), lambda: second.upsert(_entry("upload-b")))
    assert {item.media_id for item in first.list()} == {"upload-a", "upload-b"}
