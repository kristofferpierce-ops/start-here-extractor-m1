from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from ..errors import RemoteAuthError, RemoteProviderError, RemoteRateLimitError, RetryableOperationError
from ..types import RetryDecision, RetryPolicy
from .auth import AccessTokenProvider


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class QuotaTelemetry:
    rate_limited: bool = False
    throttle_count: int = 0
    retry_after_seconds: float | None = None
    last_status_code: int | None = None
    last_reason: str | None = None
    last_event_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class RetryTelemetry:
    observed_retries: int = 0
    last_delay_seconds: float | None = None
    last_reason: str | None = None
    last_attempt: int | None = None
    exhausted: bool = False
    last_event_at: str | None = None
    policy: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class ProviderHealthTelemetry:
    provider: str
    auth_state: str = "unknown"
    auth_refresh_count: int = 0
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    last_operation: str | None = None
    last_status_code: int | None = None
    last_error: str | None = None
    last_event_at: str | None = None
    notes: list[str] = field(default_factory=list)
    quota: QuotaTelemetry = field(default_factory=QuotaTelemetry)
    retry: RetryTelemetry = field(default_factory=RetryTelemetry)

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "auth_state": self.auth_state,
            "auth_refresh_count": self.auth_refresh_count,
            "request_count": self.request_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "last_operation": self.last_operation,
            "last_status_code": self.last_status_code,
            "last_error": self.last_error,
            "last_event_at": self.last_event_at,
            "notes": list(self.notes),
            "quota": self.quota.to_dict(),
            "retry": self.retry.to_dict(),
        }


class CloudProviderRuntimeState:
    def __init__(self, provider: str, *, retry_policy: RetryPolicy | None = None) -> None:
        self._provider = provider
        effective_policy = retry_policy or RetryPolicy()
        self._state = ProviderHealthTelemetry(
            provider=provider,
            retry=RetryTelemetry(
                policy={
                    "max_attempts": effective_policy.max_attempts,
                    "base_delay_seconds": effective_policy.base_delay_seconds,
                    "max_delay_seconds": effective_policy.max_delay_seconds,
                    "jitter_seconds": effective_policy.jitter_seconds,
                }
            ),
        )

    def _touch(self, *, operation: str | None = None) -> None:
        self._state.last_event_at = _utcnow_iso()
        if operation is not None:
            self._state.last_operation = operation

    def _append_note(self, note: str) -> None:
        if note not in self._state.notes:
            self._state.notes.append(note)

    def sync_token_provider(self, provider: AccessTokenProvider | None) -> None:
        if provider is None:
            return
        state = provider.public_state()
        self._state.auth_state = str(state.get("status") or self._state.auth_state)
        refresh_count = state.get("refresh_count")
        if isinstance(refresh_count, int):
            self._state.auth_refresh_count = refresh_count

    def record_operation_start(self, operation: str, *, token_provider: AccessTokenProvider | None = None) -> None:
        self.sync_token_provider(token_provider)
        self._state.request_count += 1
        self._touch(operation=operation)

    def record_retry(self, operation: str, decision: RetryDecision, exc: Exception) -> None:
        self._touch(operation=operation)
        self._state.retry.observed_retries += 1
        self._state.retry.last_delay_seconds = decision.delay_seconds
        self._state.retry.last_reason = decision.reason
        self._state.retry.last_attempt = decision.attempt
        self._state.retry.last_event_at = self._state.last_event_at
        self._state.retry.exhausted = False
        if isinstance(exc, RemoteRateLimitError):
            self._state.quota.rate_limited = True
            self._state.quota.throttle_count += 1
            self._state.quota.retry_after_seconds = exc.retry_after_seconds
            self._state.quota.last_status_code = exc.status_code
            self._state.quota.last_reason = decision.reason
            self._state.quota.last_event_at = self._state.last_event_at
            self._state.last_status_code = exc.status_code
            self._append_note("provider-rate-limited")

    def record_auth_retry(self, operation: str, exc: RemoteAuthError, *, token_provider: AccessTokenProvider | None = None) -> None:
        self.sync_token_provider(token_provider)
        self._touch(operation=operation)
        self._state.last_status_code = exc.status_code
        self._state.auth_state = "refreshing"
        self._append_note("provider-auth-refresh")

    def record_success(self, operation: str, *, token_provider: AccessTokenProvider | None = None, status_code: int | None = None) -> None:
        self.sync_token_provider(token_provider)
        self._touch(operation=operation)
        self._state.success_count += 1
        self._state.last_status_code = status_code
        self._state.last_error = None
        if self._state.auth_state == "unknown":
            self._state.auth_state = "provided"

    def record_failure(self, operation: str, exc: Exception, *, token_provider: AccessTokenProvider | None = None) -> None:
        self.sync_token_provider(token_provider)
        self._touch(operation=operation)
        self._state.error_count += 1
        self._state.last_error = str(exc)
        status_code = getattr(exc, "status_code", None)
        if isinstance(status_code, int):
            self._state.last_status_code = status_code
        if isinstance(exc, RemoteAuthError):
            self._state.auth_state = "failed"
            self._append_note("provider-auth-failed")
        elif isinstance(exc, RemoteRateLimitError):
            self._state.quota.rate_limited = True
            self._state.quota.throttle_count += 1
            self._state.quota.retry_after_seconds = exc.retry_after_seconds
            self._state.quota.last_status_code = exc.status_code
            self._state.quota.last_reason = "exhausted"
            self._state.quota.last_event_at = self._state.last_event_at
            self._state.retry.exhausted = True
            self._state.retry.last_event_at = self._state.last_event_at
            self._append_note("provider-rate-limit-exhausted")
        elif isinstance(exc, RetryableOperationError):
            self._state.retry.exhausted = True
            self._state.retry.last_reason = "max-attempts-reached"
            self._state.retry.last_event_at = self._state.last_event_at
            self._append_note("provider-retry-exhausted")
        elif isinstance(exc, RemoteProviderError):
            self._append_note("provider-error")

    def public_state(self, *, token_provider: AccessTokenProvider | None = None) -> dict[str, object]:
        self.sync_token_provider(token_provider)
        return self._state.to_dict()
