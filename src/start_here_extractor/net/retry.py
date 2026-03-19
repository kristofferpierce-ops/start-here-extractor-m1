from __future__ import annotations

import random
import time
from email.utils import parsedate_to_datetime
from typing import Callable, TypeVar

from ..errors import RetryableOperationError
from ..types import RetryDecision, RetryPolicy

T = TypeVar("T")


def _retry_after_from_value(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    text = str(value).strip()
    if not text:
        return None
    try:
        return max(0.0, float(text))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    return max(0.0, dt.timestamp() - time.time())


def _retry_after_from_exception(exc: Exception) -> float | None:
    if hasattr(exc, "retry_after_seconds"):
        value = getattr(exc, "retry_after_seconds")
        parsed = _retry_after_from_value(value)
        if parsed is not None:
            return parsed
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers and hasattr(headers, "get"):
        return _retry_after_from_value(headers.get("Retry-After"))
    return None


def compute_retry_decision(exc: Exception, attempt: int, policy: RetryPolicy) -> RetryDecision:
    if attempt >= policy.max_attempts:
        return RetryDecision(False, 0.0, "max-attempts-reached", attempt)

    retry_after = _retry_after_from_exception(exc)
    if retry_after is not None:
        return RetryDecision(True, retry_after, "retry-after", attempt)

    delay = min(policy.max_delay_seconds, policy.base_delay_seconds * (2 ** (attempt - 1)))
    if policy.jitter_seconds > 0:
        delay += random.uniform(0.0, policy.jitter_seconds)
    return RetryDecision(True, delay, "exponential-backoff", attempt)


def with_retries(
    func: Callable[[], T],
    *,
    policy: RetryPolicy | None = None,
    should_retry: Callable[[Exception], bool] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> T:
    retry_policy = policy or RetryPolicy()
    retry_filter = should_retry or (lambda exc: isinstance(exc, RetryableOperationError))

    attempt = 1
    while True:
        try:
            return func()
        except Exception as exc:
            if not retry_filter(exc):
                raise
            decision = compute_retry_decision(exc, attempt, retry_policy)
            if not decision.should_retry:
                raise
            sleep_fn(decision.delay_seconds)
            attempt += 1
