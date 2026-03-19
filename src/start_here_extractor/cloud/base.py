from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
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
    etag: str | None = None


@dataclass(frozen=True)
class RemoteSearchQuery:
    text: str = ""
    extension: str = "zip"
    folder_id: str | None = None


@dataclass(frozen=True)
class RemoteDownloadResult:
    local_path: str
    provenance: dict[str, object]


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


def encode_download_hint(payload: dict[str, object]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def decode_download_hint(raw: str | None) -> dict[str, object]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def provenance_for_candidate(candidate: RemoteZipCandidate, local_path: str | Path, *, fetched_at: str, source_path: str | None = None) -> dict[str, object]:
    return {
        "source_type": candidate.provider,
        "local_path": source_path,
        "remote_id": candidate.id,
        "etag": candidate.etag,
        "modified": candidate.modified_time,
        "fetched_at": fetched_at,
        "staging_path": str(local_path),
    }


def candidate_to_dict(candidate: RemoteZipCandidate) -> dict[str, object]:
    return asdict(candidate)
