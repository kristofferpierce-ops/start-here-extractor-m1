from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from start_here_extractor.cloud.auth import resolve_access_token
from start_here_extractor.monitoring import build_monitoring_block, iter_monitoring_records
from start_here_extractor.reporter import build_inventory_record


def _sample_record() -> dict:
    return {
        "outcome": "extracted",
        "zip_file": {"path": "sample.zip", "size_bytes": 10, "sha256": "x", "md5": "m"},
        "settings": {"extract_settings": {"retention_days": 10, "legal_hold": False, "cloud_require_operator_approval_for_abuse": True, "cloud_operator_approval_ref": None, "cloud_acknowledge_abuse": False, "sandbox_platform": "windows-sandbox"}},
        "inspection": {"entry_count": 1, "risk_flags": [], "entries": [], "candidates": []},
        "selected_candidate": {"name": "START HERE.TXT", "declared_file_size": 4},
        "extracted_file": {"path": "out/start_here.txt", "size_bytes": 4, "sha256": "y", "md5": "z"},
        "preview": {"encoding": "utf-8", "text": "hello", "bytes_read": 5, "lines": 1},
        "run": {"run_id": "r1", "ended_at": datetime.now(timezone.utc).isoformat()},
        "provenance": {"source_type": "gdrive"},
        "policy": {"decision": "sandbox", "reason": "needs-review", "notes": []},
        "scan": {"status": "not-run", "engine": None, "exit_code": None, "findings": [], "av": {"engine": None, "status": "not-run", "exit_code": None, "findings": []}, "yara": {"ruleset_id": None, "status": "not-run", "matches": [], "compiled_rules": False}},
        "sandbox": {"enabled": True, "platform": "windows-sandbox", "dry_run": True, "config_path": "out/job.wsb", "artifacts_dir": "out/results"},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def test_resolve_access_token_from_command_and_expiry_hint():
    exp = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
    resolved = resolve_access_token(access_token_command="python -c \"print('tok-cmd')\"", expires_at=exp, min_valid_seconds=300)
    assert resolved.token == "tok-cmd"
    assert resolved.source == "command"
    assert resolved.status == "stale"
    assert "token-near-expiry" in (resolved.notes or [])
    assert resolved.to_public_dict().get("token") is None


def test_monitoring_reader_ignores_truncated_tail(tmp_path: Path):
    p = tmp_path / "monitoring.jsonl"
    p.write_text('{"ok":1}\n{"partial":', encoding="utf-8")
    rows = list(iter_monitoring_records(p))
    assert rows == [{"ok": 1}]


def test_build_inventory_record_adds_monitoring_and_governance_refs(tmp_path: Path):
    rec = _sample_record()
    rec["_runtime_cloud"] = {"token_health": {"token": "secret-token", "status": "stale", "notes": ["token-near-expiry"], "source": "argument", "expires_at": None}}
    built = build_inventory_record(rec, audit_dir=tmp_path / "audit", monitoring_dir=tmp_path / "monitor", monitoring_stream_name="ops-monitor")
    assert built["monitoring_ref"].startswith("monitoring://")
    assert built["monitoring"]["review_required"] is True
    assert built["governance"]["monitoring_stream_ref"].endswith("ops-monitor.jsonl")
    assert built["governance"]["snapshot_ref"] == "out/job.wsb"
    assert built["governance"]["token_health"]["status"] == "stale"
    assert "token" not in built["governance"]["token_health"]
    assert "token" not in built["monitoring"]["token_health"]


def test_build_monitoring_block_marks_review_for_sandbox():
    rec = _sample_record()
    rec["policy_decision"] = {"decision": "sandbox", "reason": "heuristics-critical"}
    block = build_monitoring_block(rec, token_health={"status": "fresh", "notes": []})
    assert block["review_required"] is True
    assert block["sandbox_state"]["enabled"] is True
