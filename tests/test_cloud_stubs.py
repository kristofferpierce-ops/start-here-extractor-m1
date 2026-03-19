# ruff: noqa: E402
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from start_here_extractor.cloud import (
    PROVIDER_STUBS,
    DropboxLocatorStub,
    GoogleDriveLocatorStub,
    MicrosoftGraphOneDriveLocatorStub,
    RemoteSearchQuery,
    RemoteZipCandidate,
)


@pytest.mark.parametrize(
    ("provider_key", "stub_cls"),
    [
        ("gdrive", GoogleDriveLocatorStub),
        ("graph", MicrosoftGraphOneDriveLocatorStub),
        ("dropbox", DropboxLocatorStub),
    ],
)
def test_cloud_stubs_import_cleanly_and_raise_not_implemented(provider_key, stub_cls) -> None:
    assert PROVIDER_STUBS[provider_key] is stub_cls
    locator = stub_cls()
    query = RemoteSearchQuery(text="start here", extension="zip")
    candidate = RemoteZipCandidate(provider=provider_key, id="abc123", name="test.zip")

    with pytest.raises(NotImplementedError):
        locator.search(query)
    with pytest.raises(NotImplementedError):
        locator.download(candidate, dest_dir="/tmp")
