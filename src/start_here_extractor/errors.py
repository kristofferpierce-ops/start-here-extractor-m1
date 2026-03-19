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
