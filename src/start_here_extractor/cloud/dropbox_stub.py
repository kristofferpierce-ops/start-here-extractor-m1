from __future__ import annotations

from .base import RemoteLocator, RemoteSearchQuery, RemoteZipCandidate


class DropboxLocatorStub(RemoteLocator):
    provider = "dropbox"

    def search(self, query: RemoteSearchQuery, *, page_token=None) -> tuple[list[RemoteZipCandidate], str | None]:
        """
        TODO(M2): Implement with Dropbox /files/search_v2 and /files/search/continue_v2.

        Official guidance to follow in the real implementation:
        - Use file_extensions=['zip'] for ZIP discovery.
        - Continue pagination with cursor-based follow-up calls.
        - Keep the implementation dependency-free unless optional extras are introduced later.
        """
        raise NotImplementedError("Dropbox integration is not implemented in Milestone 2 kickoff stubs.")

    def download(self, candidate: RemoteZipCandidate, dest_dir: str) -> str:
        """
        TODO(M2): Implement Dropbox file download endpoints in the real connector.
        """
        raise NotImplementedError("Dropbox downloads are not implemented in Milestone 2 kickoff stubs.")
