from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.live_smoke_summary import main as live_smoke_summary_main
from start_here_extractor.cloud.auth import build_access_token_provider, resolve_access_token
from start_here_extractor.cloud.base import RemoteSearchQuery
from start_here_extractor.cloud.gdrive import GoogleDriveAuthConfig, GoogleDriveLocator
from start_here_extractor.cloud.http import HttpResponse
from start_here_extractor.errors import RemoteAuthError, RemoteRateLimitError
from start_here_extractor.live_smoke import (
    LIVE_SMOKE_ARTIFACT_CONTRACT_VERSION,
    build_live_smoke_artifact_contract,
    build_live_smoke_summary,
    render_live_smoke_markdown,
)
from start_here_extractor.reporter import build_inventory_record
from start_here_extractor.types import RetryPolicy


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "live_smoke"


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


class RateLimitedThenSuccessRequestor:
    def __init__(self):
        self.calls = 0

    def __call__(self, method, url, headers=None, data=None, timeout=30.0):
        self.calls += 1
        if self.calls == 1:
            raise RemoteRateLimitError("too-many-requests", retry_after_seconds=0, status_code=429, headers={"Retry-After": "0"})
        return HttpResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=b'{"files": []}',
        )


def _stage_fixture(tmp_path: Path, case: str) -> Path:
    root = tmp_path / case
    shutil.copytree(FIXTURE_ROOT / case, root)
    return root


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
    runtime = locator.runtime_state()
    assert runtime["auth_refresh_count"] == 1
    assert runtime["auth_state"] == "fresh"
    assert "provider-auth-refresh" in runtime["notes"]


def test_gdrive_search_records_rate_limit_and_retry_telemetry():
    locator = GoogleDriveLocator(
        GoogleDriveAuthConfig(access_token="static-token"),
        requestor=RateLimitedThenSuccessRequestor(),
        retry_policy=RetryPolicy(max_attempts=2, base_delay_seconds=0.0, max_delay_seconds=0.0, jitter_seconds=0.0),
    )

    candidates, page_token = locator.search(RemoteSearchQuery(text="start here"))

    assert candidates == []
    assert page_token is None
    runtime = locator.runtime_state()
    assert runtime["request_count"] == 1
    assert runtime["success_count"] == 1
    assert runtime["quota"]["rate_limited"] is True
    assert runtime["quota"]["throttle_count"] == 1
    assert runtime["quota"]["last_status_code"] == 429
    assert runtime["retry"]["observed_retries"] == 1
    assert runtime["retry"]["last_reason"] == "retry-after"
    assert runtime["retry"]["policy"]["max_attempts"] == 2
    assert "provider-rate-limited" in runtime["notes"]


def test_inventory_monitoring_includes_provider_health_and_quota_state():
    record = build_inventory_record(
        {
            "zip_file": {"path": "C:/tmp/example.zip", "md5": "abc"},
            "selected_candidate": {"name": "START HERE.txt"},
            "extracted_file": {"path": "C:/tmp/out/START HERE.txt", "size_bytes": 12, "md5": "def"},
            "preview": {"text": "hello", "encoding": "utf-8"},
            "_runtime_cloud": {
                "token_health": {
                    "source": "command",
                    "status": "fresh",
                    "refresh_count": 1,
                    "notes": ["token-near-expiry"],
                },
                "provider_health": {
                    "provider": "gdrive",
                    "auth_state": "fresh",
                    "auth_refresh_count": 1,
                    "request_count": 2,
                    "success_count": 1,
                    "error_count": 0,
                    "last_operation": "download",
                    "last_status_code": 200,
                    "notes": ["provider-rate-limited"],
                    "quota": {
                        "rate_limited": True,
                        "throttle_count": 2,
                        "retry_after_seconds": 0.0,
                        "last_status_code": 429,
                        "last_reason": "retry-after",
                        "last_event_at": "2030-01-01T00:00:00+00:00",
                    },
                    "retry": {
                        "observed_retries": 2,
                        "last_delay_seconds": 0.0,
                        "last_reason": "retry-after",
                        "last_attempt": 2,
                        "exhausted": False,
                        "last_event_at": "2030-01-01T00:00:00+00:00",
                        "policy": {
                            "max_attempts": 3,
                            "base_delay_seconds": 0.25,
                            "max_delay_seconds": 5.0,
                            "jitter_seconds": 0.0,
                        },
                    },
                },
            },
        }
    )

    provider_state = record["monitoring"]["provider_state"]
    assert provider_state["auth_state"] == "fresh"
    assert provider_state["rate_limited"] is True
    assert provider_state["quota"]["throttle_count"] == 2
    assert provider_state["retry"]["observed_retries"] == 2
    assert record["monitoring"]["provider_health"]["provider"] == "gdrive"
    assert record["monitoring"]["review_required"] is True
    assert "provider-rate-limited" in record["warnings"]
    assert "token-near-expiry" in record["warnings"]


@pytest.mark.parametrize(
    ("case", "provider", "query", "cli_exit_code", "expected_classification", "expected_success"),
    [
        ("success", "gdrive", "drive_smoke_test", 0, "success", True),
        ("no_remote_zip", "dropbox", "missing_test", 1, "no-remote-zip", False),
        ("token_resolution_failed", "graph", "auth_test", 1, "token-resolution-failed", False),
        ("auth_failed", "gdrive", "auth_test", 1, "auth-failed", False),
        ("rate_limited", "dropbox", "rate_limit_test", 1, "rate-limited", False),
    ],
)
def test_live_smoke_summary_classification_from_fixtures(tmp_path, case, provider, query, cli_exit_code, expected_classification, expected_success):
    root = _stage_fixture(tmp_path, case)
    summary = build_live_smoke_summary(
        provider=provider,
        query=query,
        cli_exit_code=cli_exit_code,
        report_dir=root / "reports",
        monitoring_dir=root / "monitoring",
        audit_dir=root / "audit",
        stdout_log=root / "logs" / "cli.stdout.log",
        stderr_log=root / "logs" / "cli.stderr.log",
    )

    assert summary.classification == expected_classification
    assert summary.success is expected_success
    if case == "success":
        assert summary.inventory_count == 1
        assert summary.monitoring_event_count == 1
        assert summary.audit_event_count == 1
        markdown = render_live_smoke_markdown(summary)
        assert "Classification: `success`" in markdown
    if case == "rate_limited":
        assert summary.reason == "Provider throttling exhausted the hosted smoke retry budget."


def test_live_smoke_artifact_contract_from_success_fixture(tmp_path):
    root = _stage_fixture(tmp_path, "success")
    out_dir = root / "out"
    out_dir.mkdir()
    summary_json_path = out_dir / "live_smoke_summary.json"
    summary_markdown_path = out_dir / "live_smoke_summary.md"
    summary_json_path.write_text("{}\n", encoding="utf-8")
    summary_markdown_path.write_text("# placeholder\n", encoding="utf-8")

    contract = build_live_smoke_artifact_contract(
        report_dir=root / "reports",
        monitoring_dir=root / "monitoring",
        audit_dir=root / "audit",
        stdout_log=root / "logs" / "cli.stdout.log",
        stderr_log=root / "logs" / "cli.stderr.log",
        summary_json_path=summary_json_path,
        summary_markdown_path=summary_markdown_path,
    )

    payload = contract.to_dict()
    assert payload["version"] == LIVE_SMOKE_ARTIFACT_CONTRACT_VERSION
    assert payload["valid"] is True
    assert payload["missing_required"] == []
    artifacts = {artifact["name"]: artifact for artifact in payload["artifacts"]}
    assert artifacts["summary_json"]["present"] is True
    assert artifacts["summary_markdown"]["present"] is True
    assert artifacts["stdout_log"]["present"] is True
    assert artifacts["stderr_log"]["present"] is True
    assert artifacts["inventory_jsonl"]["record_count"] == 1
    assert artifacts["monitoring_jsonl"]["record_count"] == 1
    assert artifacts["audit_jsonl"]["record_count"] == 1


def test_live_smoke_artifact_contract_flags_missing_required_log(tmp_path):
    root = _stage_fixture(tmp_path, "success")
    missing_log = root / "logs" / "cli.stderr.log"
    missing_log.unlink()

    contract = build_live_smoke_artifact_contract(
        report_dir=root / "reports",
        monitoring_dir=root / "monitoring",
        audit_dir=root / "audit",
        stdout_log=root / "logs" / "cli.stdout.log",
        stderr_log=missing_log,
    )

    assert contract.valid is False
    assert contract.missing_required == ["stderr_log"]


def test_live_smoke_summary_script_writes_summary_and_contract(tmp_path):
    root = _stage_fixture(tmp_path, "success")
    out_dir = tmp_path / "generated"

    exit_code = live_smoke_summary_main(
        [
            "--provider",
            "gdrive",
            "--query",
            "drive_smoke_test",
            "--cli-exit-code",
            "0",
            "--out-dir",
            str(out_dir),
            "--report-dir",
            str(root / "reports"),
            "--monitoring-dir",
            str(root / "monitoring"),
            "--audit-dir",
            str(root / "audit"),
            "--stdout-log",
            str(root / "logs" / "cli.stdout.log"),
            "--stderr-log",
            str(root / "logs" / "cli.stderr.log"),
        ]
    )

    assert exit_code == 0
    summary_payload = json.loads((out_dir / "live_smoke_summary.json").read_text(encoding="utf-8"))
    contract_payload = json.loads((out_dir / "live_smoke_artifact_contract.json").read_text(encoding="utf-8"))
    assert summary_payload["classification"] == "success"
    assert contract_payload["valid"] is True
    assert contract_payload["version"] == LIVE_SMOKE_ARTIFACT_CONTRACT_VERSION
    markdown = (out_dir / "live_smoke_summary.md").read_text(encoding="utf-8")
    assert "Artifact contract valid: `true`" in markdown
