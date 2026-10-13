"""Suite-wide pytest configuration.

Signed-out "local developer" behaviour is decided from the connection's peer address (issue #137,
writing_coach/core/request_boundary.py). Starlette's TestClient names its peer "testclient", which is no address, so
without help every signed-out test would read as a remote caller. The suite's default caller is therefore the
developer's own loopback address, exactly what a developer's browser is. A test of the boundary itself passes its own
``client=(...)`` and is not affected."""

import inspect

import pytest

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
