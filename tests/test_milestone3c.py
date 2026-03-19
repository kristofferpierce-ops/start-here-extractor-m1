from __future__ import annotations

from pathlib import Path

from start_here_extractor.cloud.base import RemoteSearchQuery, RemoteZipCandidate
from start_here_extractor.cloud.dropbox import DropboxAuthConfig, DropboxLocator
from start_here_extractor.cloud.gdrive import GoogleDriveAuthConfig, GoogleDriveLocator
from start_here_extractor.cloud.graph import MicrosoftGraphAuthConfig, MicrosoftGraphLocator
from start_here_extractor.cloud.http import HttpResponse
from start_here_extractor.errors import RemoteRateLimitError
from start_here_extractor.types import RetryPolicy


class SequenceRequestor:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def __call__(self, method, url, headers=None, data=None, timeout=30.0):
        self.calls.append(
            {
                'method': method,
                'url': url,
                'headers': dict(headers or {}),
                'data': data,
                'timeout': timeout,
            }
        )
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _json_response(payload: dict, *, status: int = 200, headers: dict[str, str] | None = None) -> HttpResponse:
    import json

    return HttpResponse(
        status_code=status,
        headers=headers or {'Content-Type': 'application/json'},
        body=json.dumps(payload).encode('utf-8'),
    )


def test_gdrive_search_builds_candidates_and_pages():
    requestor = SequenceRequestor(
        [
            _json_response(
                {
                    'files': [
                        {
                            'id': 'file-1',
                            'name': 'alpha.zip',
                            'size': '12',
                            'modifiedTime': '2026-01-01T00:00:00Z',
                            'mimeType': 'application/zip',
                            'webViewLink': 'https://example.test/a',
                            'md5Checksum': 'abc',
                            'capabilities': {'canDownload': True},
                        }
                    ],
                    'nextPageToken': 'next-1',
                }
            )
        ]
    )
    locator = GoogleDriveLocator(
        GoogleDriveAuthConfig(access_token='token', drive_id='drive123'),
        requestor=requestor,
    )
    candidates, token = locator.search(RemoteSearchQuery(text='start here'))
    assert token == 'next-1'
    assert len(candidates) == 1
    assert candidates[0].id == 'file-1'
    assert candidates[0].etag == 'abc'
    assert 'driveId=drive123' in requestor.calls[0]['url']
    assert requestor.calls[0]['headers']['Authorization'] == 'Bearer token'


def test_gdrive_download_writes_file(tmp_path: Path):
    requestor = SequenceRequestor([HttpResponse(status_code=200, headers={}, body=b'zip-bytes')])
    locator = GoogleDriveLocator(GoogleDriveAuthConfig(access_token='token'), requestor=requestor)
    candidate = RemoteZipCandidate(provider='gdrive', id='id1', name='doc.zip')
    path = locator.download(candidate, str(tmp_path))
    assert Path(path).read_bytes() == b'zip-bytes'


def test_dropbox_search_and_download_with_retry_after(tmp_path: Path):
    requestor = SequenceRequestor(
        [
            _json_response(
                {
                    'matches': [
                        {
                            'metadata': {
                                'metadata': {
                                    'name': 'beta.zip',
                                    'id': 'id:beta',
                                    'size': 99,
                                    'server_modified': '2026-01-02T00:00:00Z',
                                    'path_lower': '/beta.zip',
                                    'rev': 'rev1',
                                }
                            }
                        }
                    ],
                    'has_more': True,
                    'cursor': 'cursor-1',
                }
            ),
            RemoteRateLimitError('rate', retry_after_seconds=0),
            HttpResponse(status_code=200, headers={}, body=b'dbx-bytes'),
        ]
    )
    locator = DropboxLocator(
        DropboxAuthConfig(access_token='token'),
        requestor=requestor,
        retry_policy=RetryPolicy(max_attempts=2, base_delay_seconds=0, max_delay_seconds=0),
    )
    candidates, token = locator.search(RemoteSearchQuery(text='start'))
    assert token == 'cursor-1'
    path = locator.download(candidates[0], str(tmp_path))
    assert Path(path).read_bytes() == b'dbx-bytes'
    assert any(call['url'].endswith('/files/download') for call in requestor.calls)


def test_graph_search_pages_and_downloads(tmp_path: Path):
    requestor = SequenceRequestor(
        [
            _json_response(
                {
                    'value': [
                        {
                            'id': 'g1',
                            'name': 'gamma.zip',
                            'size': 321,
                            'lastModifiedDateTime': '2026-01-03T00:00:00Z',
                            'webUrl': 'https://example.test/gamma',
                            'eTag': 'etag1',
                            'parentReference': {'driveId': 'drive-9'},
                            'file': {'mimeType': 'application/zip'},
                        }
                    ],
                    '@odata.nextLink': 'https://graph.microsoft.com/v1.0/next?page=2',
                }
            ),
            HttpResponse(status_code=200, headers={}, body=b'graph-bytes'),
        ]
    )
    locator = MicrosoftGraphLocator(MicrosoftGraphAuthConfig(access_token='token'), requestor=requestor)
    candidates, token = locator.search(RemoteSearchQuery(text='start'))
    assert token == 'https://graph.microsoft.com/v1.0/next?page=2'
    path = locator.download(candidates[0], str(tmp_path))
    assert Path(path).read_bytes() == b'graph-bytes'
    assert any('/content' in call['url'] for call in requestor.calls)


def test_locator_modules_do_not_depend_on_project_root_name(tmp_path: Path):
    weird_root = tmp_path / 'renamed-root-folder'
    weird_root.mkdir()
    requestor = SequenceRequestor([HttpResponse(status_code=200, headers={}, body=b'zip-bytes')])
    locator = DropboxLocator(DropboxAuthConfig(access_token='token'), requestor=requestor)
    candidate = RemoteZipCandidate(provider='dropbox', id='id:demo', name='demo.zip')
    path = locator.download(candidate, str(weird_root))
    assert Path(path).parent == weird_root
