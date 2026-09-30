"""Shared fixtures for the D4 tests (tests/d4_support.py): the real repositories on both backends."""
import pytest

from d4_support import backend, pg_engine  # noqa: F401  (fixtures for the D4 test modules)
from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX


@pytest.fixture(autouse=True)
def _request_context_does_not_leak_between_tests():
    """A test that acts as some account (`backend.use`) must not leave the request context set for the next."""
    user = USER_KEY_CTX.set(USER_KEY_CTX.get())
    language = LANGUAGE_CODE_CTX.set(LANGUAGE_CODE_CTX.get())
    yield
    LANGUAGE_CODE_CTX.reset(language)
    USER_KEY_CTX.reset(user)
