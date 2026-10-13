"""Suite-wide pytest configuration.

Signed-out "local developer" behaviour is decided from the connection's peer address (issue #137,
writing_coach/core/request_boundary.py). Starlette's TestClient names its peer "testclient", which is no address, so
without help every signed-out test would read as a remote caller. The suite's default caller is therefore the
developer's own loopback address, exactly what a developer's browser is. A test of the boundary itself passes its own
``client=(...)`` and is not affected."""

import inspect
import os
import tempfile
from pathlib import Path

import pytest


def _isolate_databases_per_xdist_worker() -> None:
    """Give every pytest-xdist worker its own SQLite files.

    ``app``, ``auth_support`` and the product/platform repositories read their database paths from the
    environment at import time, and several test modules import ``app`` at collection. Workers sharing one
    path (the repository's ``data/`` defaults, or a path a caller exported) would migrate and write the same
    files concurrently. A serial run has no ``PYTEST_XDIST_WORKER`` and is untouched. This runs when conftest
    is imported, which precedes collection of every test module in that worker.
    """
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if not worker:
        return
    root = Path(tempfile.mkdtemp(prefix=f"orena-xdist-{worker}-"))
    for variable, name in (
        ("WRITING_DB", "writing.db"),
        ("AUTH_DB", "auth.db"),
        ("PLATFORM_DB", "platform.db"),
        ("PRODUCT_DB", "product.db"),
    ):
        os.environ[variable] = str(root / name)
    # A worker's own temp directory, too: tests that assert "nothing was left behind" in the temp directory
    # (test_speech_transcribe_guard) would otherwise see another worker's files.
    scratch = root / "tmp"
    scratch.mkdir()
    os.environ["TMPDIR"] = str(scratch)
    tempfile.tempdir = str(scratch)


_isolate_databases_per_xdist_worker()

LOOPBACK_PEER = ("127.0.0.1", 50000)


@pytest.fixture(autouse=True)
def _testclient_defaults_to_a_loopback_peer(monkeypatch):
    from starlette.testclient import TestClient

    original = TestClient.__init__
    if "client" not in inspect.signature(original).parameters:
        yield
        return

    def init(self, *args, **kwargs):
        kwargs.setdefault("client", LOOPBACK_PEER)
        original(self, *args, **kwargs)

    monkeypatch.setattr(TestClient, "__init__", init)
    yield
