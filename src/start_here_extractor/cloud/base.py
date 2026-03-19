from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class RemoteZipCandidate:
    provider: str
    id: str
    name: str
    size_bytes: int | None = None
    modified_time: str | None = None
    mime_type: str | None = None
    web_url: str | None = None
    download_hint: str | None = None


@dataclass(frozen=True)
class RemoteSearchQuery:
    text: str = ""
    extension: str = "zip"
    folder_id: str | None = None


class RemoteLocator(Protocol):
    provider: str

    def search(
        self, query: RemoteSearchQuery, *, page_token: Optional[str] = None
    ) -> tuple[list[RemoteZipCandidate], Optional[str]]:
        """Return (candidates, next_page_token)."""
        raise NotImplementedError

    def download(self, candidate: RemoteZipCandidate, dest_dir: str) -> str:
        """Download a remote ZIP to dest_dir and return a local file path."""
        raise NotImplementedError
