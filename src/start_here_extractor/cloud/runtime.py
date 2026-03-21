from __future__ import annotations

from dataclasses import dataclass

from ..types import RetryPolicy
from .auth import AccessTokenProvider
from .base import RemoteLocator, RemoteSearchQuery, RemoteZipCandidate
from .dropbox import DropboxAuthConfig, DropboxLocator
from .gdrive import GoogleDriveAuthConfig, GoogleDriveLocator
from .graph import MicrosoftGraphAuthConfig, MicrosoftGraphLocator


@dataclass(frozen=True)
class CloudRunConfig:
    provider: str
    access_token: str | None = None
    access_token_provider: AccessTokenProvider | None = None
    query_text: str = 'start here'
    folder_id: str | None = None
    page_size: int = 100
    max_pages: int = 10
    drive_id: str | None = None
    graph_drive_scope: str = 'me/drive/root'
    acknowledge_abuse: bool = False
    operator_approval_ref: str | None = None
    require_operator_approval_for_abuse: bool = True
    retry_policy: RetryPolicy | None = None


def build_locator(config: CloudRunConfig) -> RemoteLocator:
    if config.provider == 'gdrive':
        return GoogleDriveLocator(
            GoogleDriveAuthConfig(
                access_token=config.access_token or '',
                access_token_provider=config.access_token_provider,
                drive_id=config.drive_id,
                acknowledge_abuse=config.acknowledge_abuse,
                operator_approval_ref=config.operator_approval_ref,
                require_operator_approval_for_abuse=config.require_operator_approval_for_abuse,
            ),
            retry_policy=config.retry_policy,
        )
    if config.provider == 'dropbox':
        return DropboxLocator(
            DropboxAuthConfig(access_token=config.access_token or '', access_token_provider=config.access_token_provider),
            retry_policy=config.retry_policy,
        )
    if config.provider == 'graph':
        return MicrosoftGraphLocator(
            MicrosoftGraphAuthConfig(
                access_token=config.access_token or '',
                access_token_provider=config.access_token_provider,
                drive_scope=config.graph_drive_scope,
            ),
            retry_policy=config.retry_policy,
        )
    raise ValueError(f'unsupported-cloud-provider:{config.provider}')


def search_remote_candidates(locator: RemoteLocator, config: CloudRunConfig) -> list[RemoteZipCandidate]:
    query = RemoteSearchQuery(text=config.query_text, extension='zip', folder_id=config.folder_id)
    page_token: str | None = None
    all_candidates: list[RemoteZipCandidate] = []
    pages = 0
    while True:
        candidates, page_token = locator.search(query, page_token=page_token, page_size=config.page_size)
        all_candidates.extend(candidates)
        pages += 1
        if not page_token or pages >= config.max_pages:
            break
    all_candidates.sort(key=lambda c: (c.name.lower(), c.id))
    return all_candidates
