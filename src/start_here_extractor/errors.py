class StartHereError(Exception):
    """Base package exception."""


class PathTraversalRisk(StartHereError):
    pass


class ZipBombRisk(StartHereError):
    pass


class MultipleMatchesError(StartHereError):
    pass


class NoMatchError(StartHereError):
    pass


class EntryLimitExceeded(StartHereError):
    pass


class ExtractionLimitExceeded(StartHereError):
    pass


class PolicyDecisionError(StartHereError):
    pass


class RetryableOperationError(StartHereError):
    def __init__(self, message: str, *, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class RemoteProviderError(StartHereError):
    def __init__(self, message: str, *, status_code: int | None = None, headers: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.headers = headers or {}


class RemoteAuthError(RemoteProviderError):
    pass


class RemoteNotFoundError(RemoteProviderError):
    pass


class RemoteRateLimitError(RetryableOperationError):
    def __init__(self, message: str, *, retry_after_seconds: float | None = None, status_code: int | None = None, headers: dict[str, str] | None = None) -> None:
        super().__init__(message, retry_after_seconds=retry_after_seconds)
        self.status_code = status_code
        self.headers = headers or {}
