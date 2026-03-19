from .base import RemoteLocator, RemoteSearchQuery, RemoteZipCandidate
from .dropbox_stub import DropboxLocatorStub
from .gdrive_stub import GoogleDriveLocatorStub
from .graph_stub import MicrosoftGraphOneDriveLocatorStub

PROVIDER_STUBS = {
    "gdrive": GoogleDriveLocatorStub,
    "graph": MicrosoftGraphOneDriveLocatorStub,
    "dropbox": DropboxLocatorStub,
}

__all__ = [
    "RemoteLocator",
    "RemoteSearchQuery",
    "RemoteZipCandidate",
    "GoogleDriveLocatorStub",
    "MicrosoftGraphOneDriveLocatorStub",
    "DropboxLocatorStub",
    "PROVIDER_STUBS",
]
