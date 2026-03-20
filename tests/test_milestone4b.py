from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from start_here_extractor.audit import count_audit_records, iter_audit_records
from start_here_extractor.cloud.base import RemoteZipCandidate, encode_download_hint
from start_here_extractor.cloud.gdrive import GoogleDriveAuthConfig, GoogleDriveLocator
from start_here_extractor.errors import OperatorApprovalRequiredError
from start_here_extractor.reporter import build_inventory_record
from start_here_extractor.retention import derive_retention_decision


def _sample_record() -> dict:
    return {
        "outcome": "extracted",
        "zip_file": {"path": "sample.zip", "size_bytes": 10, "sha256": "x", "md5": "m"},
        "settings": {"extract_settings": {"retention_days": 10, "legal_hold": False, "cloud_require_operator_approval_for_abuse": True, "cloud_operator_approval_ref": None, "cloud_acknowledge_abuse": False}},
        "inspection": {"entry_count": 1, "risk_flags": [], "entries": [], "candidates": []},
        "selected_candidate": {"name": "START HERE.TXT", "declared_file_size": 4},
        "extracted_file": {"path": "out/start_here.txt", "size_bytes": 4, "sha256": "y", "md5": "z"},
        "preview": {"encoding": "utf-8", "text": "hello", "bytes_read": 5, "lines": 1},
        "run": {"run_id": "r1", "ended_at": datetime.now(timezone.utc).isoformat()},
        "provenance": {"source_type": "local"},
        "policy": {"decision": "allow", "reason": "ok", "notes": []},
        "scan": {"status": "not-run", "engine": None, "exit_code": None, "findings": [], "av": {"engine": None, "status": "not-run", "exit_code": None, "findings": []}, "yara": {"ruleset_id": None, "status": "not-run", "matches": [], "compiled_rules": False}},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def test_gdrive_abuse_acknowledge_requires_operator_approval(tmp_path: Path):
    locator = GoogleDriveLocator(GoogleDriveAuthConfig(access_token="tok", acknowledge_abuse=True, operator_approval_ref=None, require_operator_approval_for_abuse=True))
    candidate = RemoteZipCandidate(provider="gdrive", id="1", name="x.zip", download_hint=encode_download_hint({"can_download": True}))
    try:
        locator.download(candidate, str(tmp_path))
    except OperatorApprovalRequiredError:
        pass
    else:
        raise AssertionError("expected operator approval gate")


def test_retention_decision_honors_legal_hold():
    rec = {"generated_at": datetime.now(timezone.utc).isoformat()}
    decision = derive_retention_decision(rec, retention_days=30, legal_hold=True)
    assert decision.status == "held"
    assert decision.reason == "legal-hold"


def test_retention_decision_review_due_when_expired():
    ts = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    rec = {"generated_at": ts}
    decision = derive_retention_decision(rec, retention_days=30, legal_hold=False)
    assert decision.status == "review-due"


def test_audit_reader_ignores_truncated_tail(tmp_path: Path):
    p = tmp_path / "audit.jsonl"
    p.write_text('{\"ok\":1}\n{\"partial\":', encoding='utf-8')
    rows = list(iter_audit_records(p))
    assert rows == [{"ok": 1}]
    assert count_audit_records(p) == 1


def test_build_inventory_record_adds_governance_block(tmp_path: Path):
    rec = _sample_record()
    rec["settings"]["extract_settings"]["cloud_acknowledge_abuse"] = True
    rec["provenance"]["source_type"] = "gdrive"
    built = build_inventory_record(rec, audit_dir=tmp_path / "audit", audit_stream_name="governance-audit")
    assert built["retention_status"] in {"active", "review-due", "held"}
    assert built["governance"]["approval_gate"] == "cloud-abuse-download"
    assert built["governance"]["audit_stream_ref"].endswith("governance-audit.jsonl")
