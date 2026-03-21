from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from ..errors import RemoteProviderError
from ..types import RetryDecision, RetryPolicy
from .auth import AccessTokenProvider, run_with_auth_retry
from .base import RemoteLocator, RemoteSearchQuery, RemoteZipCandidate, decode_download_hint, encode_download_hint
from .http import Requestor, atomic_download, request_json, urllib_requestor
from .telemetry import CloudProviderRuntimeState


@dataclass(frozen=True)
class MicrosoftGraphAuthConfig:
    access_token: str
    access_token_provider: AccessTokenProvider | None = None
    drive_scope: str = 'me/drive/root'
    timeout_seconds: float = 30.0


class MicrosoftGraphLocator(RemoteLocator):
    provider = 'graph'

    def __init__(self, auth: MicrosoftGraphAuthConfig, *, requestor: Requestor = urllib_requestor, retry_policy: RetryPolicy | None = None):
        self._auth = auth
        self._requestor = requestor
        self._retry_policy = retry_policy
        self._runtime = CloudProviderRuntimeState(self.provider, retry_policy=retry_policy)

    def runtime_state(self) -> dict[str, object]:
        return self._runtime.public_state(token_provider=self._auth.access_token_provider)

    def _auth_headers(self) -> dict[str, str]:
        token = self._auth.access_token_provider.get_token() if self._auth.access_token_provider else self._auth.access_token
        return {'Authorization': f'Bearer {token}'}

    def _record_retry(self, operation: str, decision: RetryDecision, exc: Exception) -> None:
        self._runtime.record_retry(operation, decision, exc)

    def search(self, query: RemoteSearchQuery, *, page_token: Optional[str] = None, page_size: int = 100) -> tuple[list[RemoteZipCandidate], Optional[str]]:
        operation = 'search'
        self._runtime.record_operation_start(operation, token_provider=self._auth.access_token_provider)
        if page_token:
            url = page_token
        else:
            text = quote(query.text or '', safe='')
            url = f"https://graph.microsoft.com/v1.0/{self._auth.drive_scope}/search(q='{text}')?$top={page_size}"
        try:
            payload = run_with_auth_retry(
                lambda: request_json(
                    'GET',
                    url,
                    headers=self._auth_headers(),
                    timeout=self._auth.timeout_seconds,
                    requestor=self._requestor,
                    retry_policy=self._retry_policy,
                    on_retry=lambda decision, exc: self._record_retry(operation, decision, exc),
                ),
                self._auth.access_token_provider,
                on_auth_retry=lambda exc: self._runtime.record_auth_retry(operation, exc, token_provider=self._auth.access_token_provider),
            )
        except Exception as exc:
            self._runtime.record_failure(operation, exc, token_provider=self._auth.access_token_provider)
            raise
        items = payload.get('value', [])
        if not isinstance(items, list):
            raise RemoteProviderError('graph-value-not-a-list')
        candidates: list[RemoteZipCandidate] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get('name') or '')
            if query.extension and not name.lower().endswith('.' + query.extension.lower().lstrip('.')):
                continue
            parent_ref = item.get('parentReference') if isinstance(item.get('parentReference'), dict) else {}
            hint = encode_download_hint({
                'drive_id': parent_ref.get('driveId'),
                'item_id': item.get('id'),
            })
            candidates.append(
                RemoteZipCandidate(
                    provider=self.provider,
                    id=str(item.get('id') or ''),
                    name=name,
                    size_bytes=int(item['size']) if str(item.get('size') or '').isdigit() else None,
                    modified_time=item.get('lastModifiedDateTime'),
                    mime_type=item.get('file', {}).get('mimeType') if isinstance(item.get('file'), dict) else None,
                    web_url=item.get('webUrl'),
                    download_hint=hint,
                    etag=item.get('eTag'),
                )
            )
        self._runtime.record_success(operation, token_provider=self._auth.access_token_provider, status_code=200)
        next_link = payload.get('@odata.nextLink')
        return candidates, str(next_link) if next_link else None

    def download(self, candidate: RemoteZipCandidate, dest_dir: str) -> str:
        operation = 'download'
        self._runtime.record_operation_start(operation, token_provider=self._auth.access_token_provider)
        hint = decode_download_hint(candidate.download_hint)
        drive_id = hint.get('drive_id')
        item_id = hint.get('item_id') or candidate.id
        if drive_id:
            url = f'https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/content'
        else:
            url = f'https://graph.microsoft.com/v1.0/{self._auth.drive_scope}/items/{item_id}/content'
        dest_path = Path(dest_dir) / candidate.name
        try:
            local_path = run_with_auth_retry(
                lambda: atomic_download(
                    'GET',
                    url,
                    headers=self._auth_headers(),
                    dest_path=dest_path,
                    timeout=self._auth.timeout_seconds,
                    requestor=self._requestor,
                    retry_policy=self._retry_policy,
                    on_retry=lambda decision, exc: self._record_retry(operation, decision, exc),
                ),
                self._auth.access_token_provider,
                on_auth_retry=lambda exc: self._runtime.record_auth_retry(operation, exc, token_provider=self._auth.access_token_provider),
            )
        except Exception as exc:
            self._runtime.record_failure(operation, exc, token_provider=self._auth.access_token_provider)
            raise
        self._runtime.record_success(operation, token_provider=self._auth.access_token_provider, status_code=200)
        return local_path
