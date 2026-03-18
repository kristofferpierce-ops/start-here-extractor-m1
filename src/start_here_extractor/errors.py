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
