"""A file handed to ffprobe cannot make the server fetch anything.

An upload or a direct media URL can deliver a playlist or a concat script under
a media name. FFmpeg's defaults refuse to follow network references from a
local file - HLS is detected only under its own extension and may then open
only file/crypto/data, and the concat demuxer refuses unsafe names - so the
importer, which probes every file it is given, does not become a way to reach
internal addresses. That is FFmpeg behaviour rather than Orena code, so it is
pinned here against a live listener: a build that changed it fails this test
instead of quietly fetching.
"""
from __future__ import annotations

import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from writing_coach.media_thumbnail import probe_media

pytestmark = pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe is not installed here")


def _playlist(port: int) -> str:
    return (
        "#EXTM3U\n#EXT-X-TARGETDURATION:10\n#EXT-X-MEDIA-SEQUENCE:0\n"
        f"#EXTINF:10.0,\nhttp://127.0.0.1:{port}/segment.ts\n#EXT-X-ENDLIST\n"
    )


def _concat(port: int) -> str:
    return f"ffconcat version 1.0\nfile 'http://127.0.0.1:{port}/segment.ts'\n"


@pytest.fixture()
def listener():
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - http.server's naming
            requests.append(self.path)
            self.send_response(404)
            self.end_headers()

        def log_message(self, *args):  # keep test output quiet
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1], requests
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize(
    "name, body",
    [("clip.m3u8", _playlist), ("clip.mp4", _playlist), ("clip.bin", _playlist), ("clip.ffconcat", _concat)],
)
def test_a_disguised_playlist_is_refused_without_a_request(tmp_path, listener, name, body):
    port, requests = listener
    path = tmp_path / name
    path.write_text(body(port), encoding="utf-8")
    with pytest.raises(ValueError):
        probe_media(path)
    assert requests == [], "ffprobe must not follow a reference out of a local file"
