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
from start_here_extractor.relationship_memory import (
    RELATIONSHIP_MEMORY_SCHEMA_VERSION,
    REVIEW_QUEUE_SCHEMA_VERSION,
    build_operator_review_queue,
    build_relationship_memory_snapshot,
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
def sample_dropbox_inventory_record() -> dict:
    record = sample_inventory_record()
    record["provenance"] = {
        "source_type": "dropbox",
        "remote_id": "dropbox-file-1",
        "etag": "etag-2",
        "fetched_at": "2026-03-21T00:01:00+00:00",
    }
    return record
def test_build_relationship_memory_snapshot_groups_shared_fingerprints_across_sources():
    drive_record = build_ingestion_record(sample_inventory_record(), inventory_ref="file:///tmp/drive.inventory.jsonl")
    dropbox_record = build_ingestion_record(sample_dropbox_inventory_record(), inventory_ref="file:///tmp/dropbox.inventory.jsonl")
    snapshot, suggestions = build_relationship_memory_snapshot([drive_record, dropbox_record])
    assert snapshot["schema_version"] == RELATIONSHIP_MEMORY_SCHEMA_VERSION
    assert snapshot["entity_count"] == 1
    entity = snapshot["entities"][0]
    assert entity["anchor_key"]["kind"] == "zip_sha256"
    assert {item["source_type"] for item in entity["evidence_refs"]} == {"gdrive", "dropbox"}
    assert suggestions[drive_record["event_id"]]["entity_id"] == suggestions[dropbox_record["event_id"]]["entity_id"]
    assert suggestions[drive_record["event_id"]]["confidence"] >= 0.9
def test_build_operator_review_queue_creates_high_priority_item_for_review_required_record():
    record = build_ingestion_record(sample_inventory_record(), inventory_ref="file:///tmp/example.inventory.jsonl")
    _, suggestions = build_relationship_memory_snapshot([record])
    queue = build_operator_review_queue([record], suggestions)
    assert queue["schema_version"] == REVIEW_QUEUE_SCHEMA_VERSION
    assert queue["item_count"] == 1
    item = queue["items"][0]
    assert item["priority"] == "high"
    assert "review_required" in item["reason_codes"]
    assert "match_pending" in item["reason_codes"]
    assert "approval_pending" in item["reason_codes"]
    assert item["next_pipeline_stage"] == "matched"
    assert item["suggested_match"]["entity_id"].startswith("entity-")
def test_relationship_memory_snapshot_redacts_secret_bearing_fields():
    record = build_ingestion_record(sample_inventory_record(), inventory_ref="file:///tmp/example.inventory.jsonl")
    record["relationship_memory"]["candidates"] = [{"access_token": "secret", "label": "candidate"}]
    snapshot, suggestions = build_relationship_memory_snapshot([record])
    queue = build_operator_review_queue([record], suggestions)
    payload = json.dumps({"snapshot": snapshot, "queue": queue}, sort_keys=True)
    assert "access_token" not in payload
    assert "secret" not in payload
def test_build_relationship_memory_script_writes_snapshot_and_queue(tmp_path: Path):
    inventory_path = tmp_path / "sample.inventory.jsonl"
    inventory_path.write_text(json.dumps(sample_inventory_record()) + "\n", encoding="utf-8")
    ingestion_dir = tmp_path / "ingestion"
    out_dir = tmp_path / "relationship"
    journal_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_ingestion_journal.py",
            "--inventory-path",
            str(inventory_path),
            "--out-dir",
            str(ingestion_dir),
            "--source-system",
            "gdrive",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert journal_proc.returncode == 0, journal_proc.stderr
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_relationship_memory.py",
            "--ingestion-path",
            str(ingestion_dir / "ingestion-events.jsonl"),
            "--out-dir",
            str(out_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    snapshot_path = out_dir / "relationship_memory.json"
    queue_path = out_dir / "operator_review_queue.json"
    queue_md_path = out_dir / "operator_review_queue.md"
    assert snapshot_path.exists()
    assert queue_path.exists()
    assert queue_md_path.exists()
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    assert snapshot["entity_count"] == 1
    assert queue["item_count"] == 1
