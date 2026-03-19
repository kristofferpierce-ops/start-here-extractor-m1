from __future__ import annotations

from .base import RemoteLocator, RemoteSearchQuery, RemoteZipCandidate


class GoogleDriveLocatorStub(RemoteLocator):
    provider = "gdrive"

    def search(self, query: RemoteSearchQuery, *, page_token=None) -> tuple[list[RemoteZipCandidate], str | None]:
        """
        TODO(M2): Implement with Google Drive API v3 files.list and the q parameter.

        Official guidance to follow in the real implementation:
        - GET https://www.googleapis.com/drive/v3/files
        - Use q for search filters and drive-related flags such as supportsAllDrives,
          includeItemsFromAllDrives, corpora, and driveId where needed.
        - Use fields= to minimize payload size.
        - Preserve pagination tokens in the eventual runtime.
        """
        raise NotImplementedError("Google Drive API integration is not implemented in Milestone 2 kickoff stubs.")

    def download(self, candidate: RemoteZipCandidate, dest_dir: str) -> str:
        """
        TODO(M2): Implement files.get media download and handle acknowledgeAbuse for flagged files.
        """
        raise NotImplementedError("Google Drive downloads are not implemented in Milestone 2 kickoff stubs.")
