from .base import (
    RemoteDownloadResult,
    RemoteLocator,
    RemoteSearchQuery,
    RemoteZipCandidate,
    decode_download_hint,
    encode_download_hint,
    provenance_for_candidate,
)
from .dropbox import DropboxAuthConfig, DropboxLocator
from .dropbox_stub import DropboxLocatorStub
from .gdrive import GoogleDriveAuthConfig, GoogleDriveLocator
from .gdrive_stub import GoogleDriveLocatorStub
from .graph import MicrosoftGraphAuthConfig, MicrosoftGraphLocator
from .graph_stub import MicrosoftGraphOneDriveLocatorStub

PROVIDER_STUBS = {
    'gdrive': GoogleDriveLocatorStub,
    'graph': MicrosoftGraphOneDriveLocatorStub,
    'dropbox': DropboxLocatorStub,
}

PROVIDER_LOCATORS = {
    'gdrive': GoogleDriveLocator,
    'graph': MicrosoftGraphLocator,
    'dropbox': DropboxLocator,
}

__all__ = [
    'RemoteLocator',
    'RemoteSearchQuery',
    'RemoteZipCandidate',
    'RemoteDownloadResult',
    'encode_download_hint',
    'decode_download_hint',
    'provenance_for_candidate',
    'GoogleDriveAuthConfig',
    'GoogleDriveLocator',
    'GoogleDriveLocatorStub',
    'MicrosoftGraphAuthConfig',
    'MicrosoftGraphLocator',
    'MicrosoftGraphOneDriveLocatorStub',
    'DropboxAuthConfig',
    'DropboxLocator',
    'DropboxLocatorStub',
    'PROVIDER_STUBS',
    'PROVIDER_LOCATORS',
]
