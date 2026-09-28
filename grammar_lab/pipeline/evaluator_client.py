"""Orena writing evaluator client, staging mode (SPEC §5.3). The lab never modifies the engine.

Staging mode calls the app's existing ``POST /api/evaluate`` route over plain HTTP.
grammar_lab adds no route of its own and imports no app code (SPEC principle 1); this
client only ever speaks the same JSON the app's own frontend sends.

There is no default ``base_url``. The one publicly reachable instance,
``https://orena.chillpickle.org``, tunnels straight into the production container
(``writing-coach:8000``) -- CLAUDE.md's Docker notes name port 8000 "off-limits" and
AGENTS.md's Safety section lists production as a human gate ("Stop for explicit human
authorization before any gate"). Point ``base_url`` at a sandbox you are allowed to
operate (for example ``orena-foundation-web`` on :8011) unless a human has explicitly
authorized calling production for this run.

"local" mode (import the engine as a library, SPEC §5.3's other option) is not
implemented: SPEC principle 1 says the lab does not import app code, and the phase 1
brief asked for staging mode first.

Rate limiting: pass ``rate_limit_key="gemini"`` (the CLI's ``verify`` command does) when
the target sandbox's engine is configured for the Gemini key llm_client.py's blind-solve
calls also use -- the two call sites then share ``rate_limit.limiter_for("gemini", ...)``,
so their combined rate stays under the account's real ceiling instead of each
independently budgeting the full amount. Off by default (``None``): a sandbox on a
different provider, or one with its own budget, should not pay a limiter it does not need.
Either way, a 429/503 response is retried with backoff rather than failing the whole run.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from grammar_lab.pipeline.rate_limit import GEMINI_MIN_INTERVAL_SECONDS, backoff_delay, limiter_for
from grammar_lab.pipeline.secrets_redact import redact

_RETRYABLE_STATUS_CODES = {429, 503}
_MAX_RETRIES = 5


class EvaluatorClientError(RuntimeError):
    """The evaluator could not be reached, or its response did not match the expected shape."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(redact(message))
        self.status_code = status_code


@dataclass(frozen=True)
class EvaluatorError:
    category: str
    fragment: str


@dataclass(frozen=True)
class EvaluatorResult:
    errors: list[EvaluatorError]
    raw: dict[str, Any]

    def categories(self) -> set[str]:
        return {error.category for error in self.errors}


class EvaluatorClient:
    """Staging client for ``POST {base_url}/api/evaluate``."""

    def __init__(
        self,
        base_url: str,
        *,
        learning_language: str | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 60.0,
        rate_limit_key: str | None = None,
        min_interval_seconds: float = GEMINI_MIN_INTERVAL_SECONDS,
    ) -> None:
        if not base_url:
            raise ValueError(
                "base_url is required; see module docstring -- production "
                "(orena.chillpickle.org) is a human gate, not a default"
            )
        self.base_url = base_url.rstrip("/")
        self.learning_language = learning_language
        self._rate_limit_key = rate_limit_key
        self._min_interval_seconds = min_interval_seconds
        self._client = httpx.Client(transport=transport, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> EvaluatorClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def evaluate(self, text: str, *, target_cefr: str | None = None) -> EvaluatorResult:
        """Send one sentence/paragraph for grammar-only evaluation.

        ``writing_mode: journal`` is used so the evaluator scores language
        accuracy only, never task achievement -- there is no task, only a
        pitfall/example sentence to check.
        """
        body: dict[str, Any] = {
            "text": text,
            "writing_mode": "journal",
            "writing_context": {"journal_context": "Grammar check."},
        }
        if target_cefr:
            body["target_cefr"] = target_cefr
        if self.learning_language:
            body["learning_language"] = self.learning_language
        response = self._post_with_retry(body)
        try:
            data = response.json()
        except ValueError as exc:
            raise EvaluatorClientError(f"response was not JSON: {response.text[:2000]}") from exc
        raw_errors = data.get("errors")
        if not isinstance(raw_errors, list):
            raise EvaluatorClientError(f"response had no 'errors' list: {data!r}")
        errors = [
            EvaluatorError(str(item.get("category", "")), str(item.get("fragment", "")))
            for item in raw_errors
            if isinstance(item, dict)
        ]
        return EvaluatorResult(errors, data)

    def _post_with_retry(self, body: dict[str, Any]) -> httpx.Response:
        url = f"{self.base_url}/api/evaluate"
        for attempt in range(_MAX_RETRIES):
            if self._rate_limit_key:
                limiter_for(self._rate_limit_key, self._min_interval_seconds).wait()
            try:
                response = self._client.post(url, json=body)
            except httpx.HTTPError as exc:
                raise EvaluatorClientError(f"request to {url} failed: {exc}") from exc
            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES - 1:
                time.sleep(backoff_delay(attempt))
                continue
            if response.status_code >= 400:
                raise EvaluatorClientError(
                    f"{url} returned {response.status_code}: {response.text[:2000]}",
                    status_code=response.status_code,
                )
            return response
        raise AssertionError("unreachable")  # loop always returns or raises
