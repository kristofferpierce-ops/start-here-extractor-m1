from __future__ import annotations

from .base import RemoteLocator, RemoteSearchQuery, RemoteZipCandidate


class MicrosoftGraphOneDriveLocatorStub(RemoteLocator):
    provider = "graph"

    def search(self, query: RemoteSearchQuery, *, page_token=None) -> tuple[list[RemoteZipCandidate], str | None]:
        """
        TODO(M2): Implement with Microsoft Graph OneDrive search endpoints.

        Official guidance to follow in the real implementation:
        - GET /me/drive/root/search(q='{search-text}')
        - Page through results using @odata.nextLink or skip token patterns.
        - Constrain returned fields to the minimal descriptor needed for RemoteZipCandidate.
        """
        raise NotImplementedError("Microsoft Graph / OneDrive integration is not implemented in Milestone 2 kickoff stubs.")

    def download(self, candidate: RemoteZipCandidate, dest_dir: str) -> str:
        """
        TODO(M2): Implement driveItem content download flow in the real connector.
        """
        raise NotImplementedError("Microsoft Graph / OneDrive downloads are not implemented in Milestone 2 kickoff stubs.")
