from __future__ import annotations

import subprocess

from start_here_extractor.cloud.auth import build_access_token_provider, resolve_access_token
from start_here_extractor.cloud.base import RemoteSearchQuery
from start_here_extractor.cloud.gdrive import GoogleDriveAuthConfig, GoogleDriveLocator
from start_here_extractor.cloud.http import HttpResponse
from start_here_extractor.errors import RemoteAuthError, RemoteRateLimitError
from start_here_extractor.live_smoke import build_live_smoke_summary, render_live_smoke_markdown
from start_here_extractor.reporter import build_inventory_record
from start_here_extractor.types import RetryPolicy


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


def test_live_smoke_summary_classifies_success_from_inventory(tmp_path):
    report_dir = tmp_path / "reports"
    monitoring_dir = tmp_path / "monitoring"
    audit_dir = tmp_path / "audit"
    logs_dir = tmp_path / "logs"
    report_dir.mkdir()
    monitoring_dir.mkdir()
    audit_dir.mkdir()
    logs_dir.mkdir()

    record = build_inventory_record(
        {
            "outcome": "success",
            "zip_file": {"path": "C:/tmp/example.zip", "md5": "abc"},
            "selected_candidate": {"name": "START HERE.txt"},
            "extracted_file": {"path": "C:/tmp/out/START HERE.txt", "size_bytes": 12, "md5": "def"},
            "preview": {"text": "hello", "encoding": "utf-8"},
            "provenance": {"source_type": "gdrive"},
            "_runtime_cloud": {
                "token_health": {"source": "command", "status": "fresh", "refresh_count": 1},
                "provider_health": {
                    "provider": "gdrive",
                    "auth_state": "fresh",
                    "auth_refresh_count": 1,
                    "request_count": 2,
                    "success_count": 2,
                    "error_count": 0,
                    "last_operation": "download",
                    "last_status_code": 200,
                    "notes": [],
                    "quota": {
                        "rate_limited": False,
                        "throttle_count": 0,
                        "retry_after_seconds": None,
                        "last_status_code": None,
                        "last_reason": None,
                        "last_event_at": "2030-01-01T00:00:00+00:00",
                    },
                    "retry": {
                        "observed_retries": 0,
                        "last_delay_seconds": None,
                        "last_reason": None,
                        "last_attempt": None,
                        "exhausted": False,
                        "last_event_at": "2030-01-01T00:00:00+00:00",
                        "policy": {
                            "max_attempts": 4,
                            "base_delay_seconds": 0.25,
                            "max_delay_seconds": 5.0,
                            "jitter_seconds": 0.0,
                        },
                    },
                },
            },
        },
        monitoring_dir=monitoring_dir,
        audit_dir=audit_dir,
    )
    inventory_path = report_dir / "example.inventory.jsonl"
    inventory_path.write_text(__import__("json").dumps(record) + "\n", encoding="utf-8")
    (logs_dir / "cli.stdout.log").write_text("[success] smoke\n", encoding="utf-8")
    (logs_dir / "cli.stderr.log").write_text("", encoding="utf-8")

    summary = build_live_smoke_summary(
        provider="gdrive",
        query="drive_smoke_test",
        cli_exit_code=0,
        report_dir=report_dir,
        monitoring_dir=monitoring_dir,
        audit_dir=audit_dir,
        stdout_log=logs_dir / "cli.stdout.log",
        stderr_log=logs_dir / "cli.stderr.log",
    )

    assert summary.success is True
    assert summary.classification == "success"
    assert summary.inventory_count == 1
    assert summary.monitoring_event_count == 1
    assert summary.audit_event_count == 1
    markdown = render_live_smoke_markdown(summary)
    assert "Classification: `success`" in markdown


def test_live_smoke_summary_classifies_no_remote_zip_from_logs(tmp_path):
    report_dir = tmp_path / "reports"
    logs_dir = tmp_path / "logs"
    report_dir.mkdir()
    logs_dir.mkdir()
    (logs_dir / "cli.stdout.log").write_text("", encoding="utf-8")
    (logs_dir / "cli.stderr.log").write_text("No remote ZIP files found from the provided cloud provider/query\n", encoding="utf-8")

    summary = build_live_smoke_summary(
        provider="dropbox",
        query="missing_test",
        cli_exit_code=1,
        report_dir=report_dir,
        monitoring_dir=tmp_path / "monitoring",
        audit_dir=tmp_path / "audit",
        stdout_log=logs_dir / "cli.stdout.log",
        stderr_log=logs_dir / "cli.stderr.log",
    )

    assert summary.success is False
    assert summary.classification == "no-remote-zip"
    assert summary.reason == "No remote ZIP files matched the hosted smoke query."


def test_live_smoke_summary_classifies_token_resolution_failure_from_logs(tmp_path):
    report_dir = tmp_path / "reports"
    logs_dir = tmp_path / "logs"
    report_dir.mkdir()
    logs_dir.mkdir()
    (logs_dir / "cli.stdout.log").write_text("", encoding="utf-8")
    (logs_dir / "cli.stderr.log").write_text("TokenResolutionError: token-command-failed:1\n", encoding="utf-8")

    summary = build_live_smoke_summary(
        provider="graph",
        query="auth_test",
        cli_exit_code=1,
        report_dir=report_dir,
        monitoring_dir=tmp_path / "monitoring",
        audit_dir=tmp_path / "audit",
        stdout_log=logs_dir / "cli.stdout.log",
        stderr_log=logs_dir / "cli.stderr.log",
    )

    assert summary.success is False
    assert summary.classification == "token-resolution-failed"


def test_live_smoke_summary_classifies_auth_failure_from_logs(tmp_path):
    report_dir = tmp_path / "reports"
    logs_dir = tmp_path / "logs"
    report_dir.mkdir()
    logs_dir.mkdir()
    (logs_dir / "cli.stdout.log").write_text("", encoding="utf-8")
    (logs_dir / "cli.stderr.log").write_text("RemoteAuthError: http-auth-error:401\n", encoding="utf-8")

    summary = build_live_smoke_summary(
        provider="gdrive",
        query="auth_test",
        cli_exit_code=1,
        report_dir=report_dir,
        monitoring_dir=tmp_path / "monitoring",
        audit_dir=tmp_path / "audit",
        stdout_log=logs_dir / "cli.stdout.log",
        stderr_log=logs_dir / "cli.stderr.log",
    )

    assert summary.success is False
    assert summary.classification == "auth-failed"
