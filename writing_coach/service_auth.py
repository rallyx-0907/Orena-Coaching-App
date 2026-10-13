"""A scoped machine credential for unattended vocabulary ingestion (issue #145).

Orena's admin guard is session-based: a person signs in with Google. An unattended client (the n8n Vocabulary
Generator, a cron job) has no browser and no session. This module is the whole of what it is given instead, and
deliberately nothing more:

- ONE capability: `POST /api/admin/vocabulary/preview` and `POST /api/admin/vocabulary/import`. Not "admin": no
  other `/api/admin/*` route, no learner route, no sign-in, no other method or path ever accepts it
  (`VOCABULARY_INGEST_PATHS` is the only place the scope is written, and `tests/test_vocabulary_ingest_token.py`
  walks every route to prove it).
- The server stores no secret. The operator sets `VOCAB_INGEST_TOKEN_SHA256` to the SHA-256 (hex) of the token,
  one value or several separated by commas (rotation: add the new hash, move the client, remove the old one).
  A token is compared by its digest, in constant time, against every configured hash.
- Revocable: remove a hash from the variable and restart. Nothing configured means the feature is off: every
  request carrying a bearer token to those two paths is refused, and the session guard is unchanged.
- Never logged: this module logs nothing, and the middleware that calls it logs no header.
- A valid token does not make the caller a signed-in user. The caller is the fixed service principal below;
  authored vocabulary it imports lands in a set that is `pending_review` (D-178) like any admin import, so a
  human still decides what learners see.

Architecture note: this changes authentication. It needs independent architecture review before it is merged
(AGENTS.md "Architecture review authority"; DECISION_LOG D-18X placeholder).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from collections.abc import Mapping

ENV_NAME = "VOCAB_INGEST_TOKEN_SHA256"
VOCABULARY_INGEST_PATHS = frozenset({"/api/admin/vocabulary/preview", "/api/admin/vocabulary/import"})
VOCABULARY_INGEST_METHOD = "POST"
SERVICE_PRINCIPAL = {
    "google_sub": "service:vocabulary-ingest",
    "email": "service:vocabulary-ingest",
    "name": "Vocabulary ingest service",
    "role": "service",
}
# The request-context user key of a service request: not an account, and not the shared "legacy" learner scope.
SERVICE_USER_KEY = "service-vocabulary-ingest"
_SHA256_HEX =re.compile(r"[0-9a-f]{64}")


def configured_hashes(environ: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """The SHA-256 digests the operator allows. A value that is not 64 hex characters is ignored (fail closed)."""

    raw = str((os.environ if environ is None else environ).get(ENV_NAME, "") or "")
    return tuple(part for part in re.split(r"[,\s]+", raw.strip().lower()) if _SHA256_HEX.fullmatch(part))


def bearer_token(headers: Mapping[str, str]) -> str:
    """The token of an `Authorization: Bearer <token>` header, or '' when the request carries none."""

    scheme, _, token = str(headers.get("authorization", "") or "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


def token_matches(token: str, hashes: tuple[str, ...]) -> bool:
    """Constant-time: the token's digest is compared with every configured digest, without stopping early."""

    if not token or not hashes:
        return False
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    matched = False
    for allowed in hashes:
        matched |= hmac.compare_digest(digest, allowed)
    return matched


def is_vocabulary_ingest_request(method: str, path: str, headers: Mapping[str, str]) -> bool:
    """A request that presents a bearer token to exactly one of the two scoped routes."""

    return method.upper() == VOCABULARY_INGEST_METHOD and path in VOCABULARY_INGEST_PATHS and bool(bearer_token(headers))
