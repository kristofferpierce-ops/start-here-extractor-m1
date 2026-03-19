from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..errors import RemoteProviderError
from ..types import RetryPolicy
from .base import RemoteLocator, RemoteSearchQuery, RemoteZipCandidate, encode_download_hint
from .http import Requestor, atomic_download, request_json, urllib_requestor


@dataclass(frozen=True)
class DropboxAuthConfig:
    access_token: str
    timeout_seconds: float = 30.0


class DropboxLocator(RemoteLocator):
    provider = 'dropbox'

    def __init__(self, auth: DropboxAuthConfig, *, requestor: Requestor = urllib_requestor, retry_policy: RetryPolicy | None = None):
        self._auth = auth
        self._requestor = requestor
        self._retry_policy = retry_policy

    def _auth_headers(self) -> dict[str, str]:
        return {'Authorization': f'Bearer {self._auth.access_token}'}

    def search(self, query: RemoteSearchQuery, *, page_token: Optional[str] = None, page_size: int = 100) -> tuple[list[RemoteZipCandidate], Optional[str]]:
        if page_token:
            url = 'https://api.dropboxapi.com/2/files/search/continue_v2'
            payload = {'cursor': page_token}
        else:
            url = 'https://api.dropboxapi.com/2/files/search_v2'
            options: dict[str, object] = {
                'max_results': page_size,
                'file_extensions': [query.extension.lstrip('.')],
                'filename_only': False,
            }
            if query.folder_id:
                options['path'] = query.folder_id
            payload = {'query': query.text or '', 'options': options}
        response = request_json('POST', url, headers=self._auth_headers(), payload=payload, timeout=self._auth.timeout_seconds, requestor=self._requestor, retry_policy=self._retry_policy)
        matches = response.get('matches', [])
        if not isinstance(matches, list):
            raise RemoteProviderError('dropbox-matches-not-a-list')
        candidates: list[RemoteZipCandidate] = []
        for match in matches:
            if not isinstance(match, dict):
                continue
            metadata = match.get('metadata')
            if isinstance(metadata, dict) and 'metadata' in metadata and isinstance(metadata.get('metadata'), dict):
                metadata = metadata['metadata']
            if not isinstance(metadata, dict):
                continue
            name = str(metadata.get('name') or '')
            if query.extension and not name.lower().endswith('.' + query.extension.lower().lstrip('.')):
                continue
            file_id = metadata.get('id') or metadata.get('path_lower') or metadata.get('path_display')
            candidates.append(
                RemoteZipCandidate(
                    provider=self.provider,
                    id=str(file_id or ''),
                    name=name,
                    size_bytes=int(metadata['size']) if str(metadata.get('size') or '').isdigit() else None,
                    modified_time=metadata.get('server_modified') or metadata.get('client_modified'),
                    mime_type=None,
                    web_url=None,
                    download_hint=encode_download_hint({
                        'path': metadata.get('path_lower') or metadata.get('path_display'),
                        'id': metadata.get('id'),
                    }),
                    etag=metadata.get('rev'),
                )
            )
        next_cursor = None
        if bool(response.get('has_more')):
            cursor = response.get('cursor')
            next_cursor = str(cursor) if cursor else None
        return candidates, next_cursor

    def download(self, candidate: RemoteZipCandidate, dest_dir: str) -> str:
        arg = {'path': candidate.id if candidate.id.startswith('id:') else candidate.id}
        headers = self._auth_headers()
        headers['Dropbox-API-Arg'] = __import__('json').dumps(arg, separators=(',', ':'))
        dest_path = Path(dest_dir) / candidate.name
        return atomic_download('POST', 'https://content.dropboxapi.com/2/files/download', headers=headers, dest_path=dest_path, timeout=self._auth.timeout_seconds, requestor=self._requestor, retry_policy=self._retry_policy)
