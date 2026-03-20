from __future__ import annotations

import subprocess

from start_here_extractor.cloud.auth import build_access_token_provider, resolve_access_token
from start_here_extractor.cloud.base import RemoteSearchQuery
from start_here_extractor.cloud.gdrive import GoogleDriveAuthConfig, GoogleDriveLocator
from start_here_extractor.cloud.http import HttpResponse
from start_here_extractor.errors import RemoteAuthError


class CommandSequenceRunner:
    def __init__(self, payloads: list[str]):
        self._payloads = list(payloads)
        self.calls = 0

    def __call__(self, command: str) -> subprocess.CompletedProcess[str]:
        self.calls += 1
        payload = self._payloads.pop(0)
        return subprocess.CompletedProcess(args=command, returncode=0, stdout=payload, stderr="")


class AuthRefreshingRequestor:
    def __init__(self):
        self.calls: list[str] = []

    def __call__(self, method, url, headers=None, data=None, timeout=30.0):
        auth_header = dict(headers or {}).get("Authorization")
        self.calls.append(str(auth_header))
        if auth_header == "Bearer old-token":
            raise RemoteAuthError("expired", status_code=401, headers={})
        return HttpResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=b'{"files": []}',
        )


def test_resolve_access_token_accepts_json_command_payload():
    runner = CommandSequenceRunner(
        [
            '{"access_token":"json-token","expires_at":"2030-01-01T00:00:00+00:00","source":"oidc"}\n'
        ]
    )
    resolved = resolve_access_token(access_token_command="token-cmd", command_runner=runner)
    assert resolved.token == "json-token"
    assert resolved.source == "oidc"
    assert resolved.expires_at == "2030-01-01T00:00:00+00:00"
    assert resolved.status == "fresh"


def test_command_provider_public_state_stays_secret_safe():
    runner = CommandSequenceRunner(
        ['{"access_token":"json-token","expires_at":"2030-01-01T00:00:00+00:00"}\n']
    )
    provider = build_access_token_provider(access_token_command="token-cmd", command_runner=runner)
    assert provider.get_token() == "json-token"
    state = provider.public_state()
    assert "token" not in state
    assert state["resolution_mode"] == "command"
    assert state["refresh_count"] == 0
    assert state["status"] == "fresh"


def test_gdrive_search_refreshes_command_token_after_auth_failure():
    runner = CommandSequenceRunner(
        [
            '{"access_token":"old-token","expires_at":"2030-01-01T00:00:00+00:00"}\n',
            '{"access_token":"new-token","expires_at":"2030-01-01T00:00:00+00:00"}\n',
        ]
    )
    provider = build_access_token_provider(access_token_command="token-cmd", command_runner=runner)
    requestor = AuthRefreshingRequestor()
    locator = GoogleDriveLocator(
        GoogleDriveAuthConfig(access_token="", access_token_provider=provider),
        requestor=requestor,
    )

    candidates, page_token = locator.search(RemoteSearchQuery(text="start here"))

    assert candidates == []
    assert page_token is None
    assert requestor.calls == ["Bearer old-token", "Bearer new-token"]
    assert provider.public_state()["refresh_count"] == 1
