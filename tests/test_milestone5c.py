from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from start_here_extractor.ingestion import (
    INGESTION_SCHEMA_VERSION,
    append_ingestion_record,
    build_ingestion_record,
    build_ingestion_rollup,
    iter_ingestion_records,
)


def sample_inventory_record() -> dict:
    return {
        "schema_version": "4.2",
        "generated_at": "2026-03-21T00:00:00+00:00",
        "outcome": "extracted",
        "zip_path": "/tmp/example.zip",
        "start_here": "START HERE.txt",
        "zip_file": {
            "path": "/tmp/example.zip",
            "sha256": "zip-sha-123",
            "md5": "zip-md5-123",
        },
        "extracted_file": {
            "sha256": "file-sha-123",
        },
        "provenance": {
            "source_type": "gdrive",
            "remote_id": "drive-file-1",
            "etag": "etag-1",
            "fetched_at": "2026-03-21T00:00:00+00:00",
        },
        "policy_decision": {
            "decision": "allow",
            "reason": "ok",
        },
        "policy": {
            "decision": "allow",
            "reason": "ok",
        },
        "governance": {
            "approval_gate": "cloud-abuse-download",
            "operator_approval_required": False,
            "audit_stream_ref": "audit:///tmp/audit.jsonl",
            "monitoring_stream_ref": "monitoring:///tmp/monitoring.jsonl",
        },
        "monitoring": {
            "review_required": True,
        },
        "retention_status": "active",
        "audit_ref": "audit:///tmp/audit.jsonl#event-1",
        "monitoring_ref": "monitoring:///tmp/monitoring.jsonl#event-1",
        "warnings": ["provider-needs-review"],
    }


def test_build_ingestion_record_preserves_generic_backbone_fields():
    inventory = sample_inventory_record()
    record = build_ingestion_record(inventory, inventory_ref="file:///tmp/example.inventory.jsonl")

    assert record["schema_version"] == INGESTION_SCHEMA_VERSION
    assert record["source"]["source_type"] == "gdrive"
    assert record["source"]["source_record_id"] == "drive-file-1"
    assert record["pipeline"]["raw"]["status"] == "captured"
    assert record["pipeline"]["normalized"]["status"] == "normalized"
    assert record["pipeline"]["matched"]["status"] == "pending"
    assert record["pipeline"]["approved"]["status"] == "pending"
    assert record["pipeline"]["applied"]["status"] == "pending"
    assert record["governance"]["review_required"] is True
    assert record["evidence"]["inventory_ref"] == "file:///tmp/example.inventory.jsonl"


def test_build_ingestion_record_event_id_is_deterministic():
    inventory = sample_inventory_record()
    one = build_ingestion_record(inventory, inventory_ref="file:///tmp/a.jsonl")
    two = build_ingestion_record(inventory, inventory_ref="file:///tmp/b.jsonl")
    assert one["event_id"] == two["event_id"]


def test_append_and_iter_ingestion_records(tmp_path: Path):
    record = build_ingestion_record(sample_inventory_record(), inventory_ref="file:///tmp/example.inventory.jsonl")
    ref = append_ingestion_record(record, tmp_path)
    rows = list(iter_ingestion_records(tmp_path / "ingestion-events.jsonl"))

    assert ref.startswith("ingestion://")
    assert len(rows) == 1
    assert rows[0]["event_id"] == record["event_id"]


def test_build_ingestion_rollup_counts_review_and_pipeline_statuses():
    record = build_ingestion_record(sample_inventory_record(), inventory_ref="file:///tmp/example.inventory.jsonl")
    rollup = build_ingestion_rollup([record])

    assert rollup["record_count"] == 1
    assert rollup["source_types"] == {"gdrive": 1}
    assert rollup["pipeline_status_counts"]["matched"]["pending"] == 1
    assert rollup["review_required_count"] == 1


def test_build_ingestion_journal_script_writes_journal_and_rollup(tmp_path: Path):
    inventory_path = tmp_path / "sample.inventory.jsonl"
    inventory_path.write_text(json.dumps(sample_inventory_record()) + "\n", encoding="utf-8")
    out_dir = tmp_path / "out"

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_ingestion_journal.py",
            "--inventory-path",
            str(inventory_path),
            "--out-dir",
            str(out_dir),
            "--source-system",
            "gdrive",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    journal_path = out_dir / "ingestion-events.jsonl"
    rollup_path = out_dir / "ingestion_rollup.json"
    assert journal_path.exists()
    assert rollup_path.exists()
    rollup = json.loads(rollup_path.read_text(encoding="utf-8"))
    assert rollup["record_count"] == 1
    assert rollup["source_types"] == {"gdrive": 1}
