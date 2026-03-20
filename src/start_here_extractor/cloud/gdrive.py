from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from ..errors import OperatorApprovalRequiredError, RemoteProviderError
from ..types import RetryPolicy
from .auth import AccessTokenProvider, run_with_auth_retry
from .base import RemoteLocator, RemoteSearchQuery, RemoteZipCandidate, decode_download_hint, encode_download_hint
from .http import Requestor, atomic_download, request_json, urllib_requestor


@dataclass(frozen=True)
class GoogleDriveAuthConfig:
    access_token: str
    access_token_provider: AccessTokenProvider | None = None
    drive_id: str | None = None
    supports_all_drives: bool = True
    include_items_from_all_drives: bool = True
    acknowledge_abuse: bool = False
    timeout_seconds: float = 30.0
    operator_approval_ref: str | None = None
    require_operator_approval_for_abuse: bool = True


class GoogleDriveLocator(RemoteLocator):
    provider = 'gdrive'

    def __init__(self, auth: GoogleDriveAuthConfig, *, requestor: Requestor = urllib_requestor, retry_policy: RetryPolicy | None = None):
        self._auth = auth
        self._requestor = requestor
        self._retry_policy = retry_policy

    def _auth_headers(self) -> dict[str, str]:
        token = self._auth.access_token_provider.get_token() if self._auth.access_token_provider else self._auth.access_token
        return {'Authorization': f'Bearer {token}'}

    def _query_string(self, query: RemoteSearchQuery, page_size: int, page_token: Optional[str]) -> str:
        parts = ["trashed=false", "mimeType='application/zip'"]
        if query.text:
            escaped = query.text.replace("'", "\'")
            parts.append(f"name contains '{escaped}'")
        if query.folder_id:
            escaped = query.folder_id.replace("'", "\'")
            parts.append(f"'{escaped}' in parents")
        params = {
            'q': ' and '.join(parts),
            'pageSize': page_size,
            'fields': 'nextPageToken,incompleteSearch,files(id,name,mimeType,size,modifiedTime,webViewLink,md5Checksum,capabilities/canDownload)',
            'supportsAllDrives': 'true' if self._auth.supports_all_drives else 'false',
            'includeItemsFromAllDrives': 'true' if self._auth.include_items_from_all_drives else 'false',
        }
        if self._auth.drive_id:
            params['driveId'] = self._auth.drive_id
            params['corpora'] = 'drive'
        if page_token:
            params['pageToken'] = page_token
        return urlencode(params)

    def search(self, query: RemoteSearchQuery, *, page_token: Optional[str] = None, page_size: int = 100) -> tuple[list[RemoteZipCandidate], Optional[str]]:
        url = 'https://www.googleapis.com/drive/v3/files?' + self._query_string(query, page_size, page_token)
        payload = run_with_auth_retry(
            lambda: request_json('GET', url, headers=self._auth_headers(), timeout=self._auth.timeout_seconds, requestor=self._requestor, retry_policy=self._retry_policy),
            self._auth.access_token_provider,
        )
        items = payload.get('files', [])
        if not isinstance(items, list):
            raise RemoteProviderError('gdrive-files-not-a-list')
        candidates: list[RemoteZipCandidate] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get('name') or '')
            if query.extension and not name.lower().endswith('.' + query.extension.lower().lstrip('.')):
                continue
            hint = encode_download_hint({
                'can_download': bool(((item.get('capabilities') or {}) if isinstance(item.get('capabilities'), dict) else {}).get('canDownload', True)),
                'md5': item.get('md5Checksum'),
                'abuse_acknowledge_requested': bool(self._auth.acknowledge_abuse),
                'operator_approval_ref': self._auth.operator_approval_ref,
            })
            candidates.append(
                RemoteZipCandidate(
                    provider=self.provider,
                    id=str(item.get('id') or ''),
                    name=name,
                    size_bytes=int(item['size']) if str(item.get('size') or '').isdigit() else None,
                    modified_time=item.get('modifiedTime'),
                    mime_type=item.get('mimeType'),
                    web_url=item.get('webViewLink'),
                    download_hint=hint,
                    etag=item.get('md5Checksum'),
                )
            )
        next_page = payload.get('nextPageToken')
        return candidates, str(next_page) if next_page else None

    def download(self, candidate: RemoteZipCandidate, dest_dir: str) -> str:
        hint = decode_download_hint(candidate.download_hint)
        if hint.get('can_download') is False:
            raise RemoteProviderError('gdrive-canDownload-false')
        if self._auth.acknowledge_abuse and self._auth.require_operator_approval_for_abuse and not self._auth.operator_approval_ref:
            raise OperatorApprovalRequiredError('gdrive-abuse-download-requires-operator-approval')
        params = {'alt': 'media'}
        if self._auth.acknowledge_abuse:
            params['acknowledgeAbuse'] = 'true'
        url = f'https://www.googleapis.com/drive/v3/files/{candidate.id}?' + urlencode(params)
        dest_path = Path(dest_dir) / candidate.name
        return run_with_auth_retry(
            lambda: atomic_download('GET', url, headers=self._auth_headers(), dest_path=dest_path, timeout=self._auth.timeout_seconds, requestor=self._requestor, retry_policy=self._retry_policy),
            self._auth.access_token_provider,
        )
