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
from start_here_extractor.review_decisions import (
    REVIEW_DECISION_SCHEMA_VERSION,
    STATE_TRANSITION_ROLLUP_SCHEMA_VERSION,
    apply_review_decisions,
)
from start_here_extractor.application_decisions import (
    APPLICATION_DECISION_SCHEMA_VERSION,
    APPLICATION_QUEUE_SCHEMA_VERSION,
    APPLICATION_TRANSITION_ROLLUP_SCHEMA_VERSION,
    apply_application_decisions,
    build_application_queue,
)
from start_here_extractor.adapter_contracts import (
    ADAPTER_CONTRACT_REVIEW_QUEUE_SCHEMA_VERSION,
    ADAPTER_CONTRACT_ROLLUP_SCHEMA_VERSION,
    ADAPTER_EXECUTION_CONTRACTS_SCHEMA_VERSION,
    build_adapter_execution_artifacts,
)
from start_here_extractor.adapter_execution import (
    ADAPTER_EXECUTION_JOURNAL_SCHEMA_VERSION,
    ADAPTER_EXECUTION_ROLLUP_SCHEMA_VERSION,
    apply_adapter_execution_outcomes,
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


def sample_dropbox_inventory_record() -> dict:
    record = sample_inventory_record()
    record["provenance"] = {
        "source_type": "dropbox",
        "remote_id": "dropbox-file-1",
        "etag": "etag-2",
        "fetched_at": "2026-03-21T00:01:00+00:00",
    }
    return record


def build_sample_ingestion_record(inventory_ref: str = "file:///tmp/example.inventory.jsonl") -> dict:
    return build_ingestion_record(sample_inventory_record(), inventory_ref=inventory_ref)


def build_sample_queue(record: dict | None = None) -> dict:
    target = record or build_sample_ingestion_record()
    _, suggestions = build_relationship_memory_snapshot([target])
    return build_operator_review_queue([target], suggestions)

def sample_target_catalog() -> list[dict]:
    return [
        {
            "target_key": "ops-evidence-ledger",
            "target_type": "evidence-ledger",
            "target_system": "ops-core",
            "target_id": "ledger-primary",
            "allowed_content_families": ["start-here-evidence"],
            "allowed_source_types": ["gdrive", "dropbox"],
            "apply_mode": "projection",
        },
        {
            "target_key": "triage-backlog",
            "target_type": "review-backlog",
            "target_system": "ops-core",
            "target_id": "backlog-1",
            "allowed_content_families": ["start-here-evidence"],
            "apply_mode": "projection",
        },
    ]


def sample_adapter_catalog() -> list[dict]:
    return [
        {
            "adapter_key": "ops-core-evidence-upsert",
            "adapter_family": "ledger",
            "adapter_version": "1.0",
            "contract_version": "1.0",
            "operation": "upsert-evidence-record",
            "execution_mode": "dry_run",
            "target_key": "ops-evidence-ledger",
            "target_system": "ops-core",
            "target_type": "evidence-ledger",
            "supported_content_families": ["start-here-evidence"],
            "supported_source_types": ["gdrive", "dropbox"],
            "required_fields": [
                "event_id",
                "source.source_record_id",
                "evidence.inventory_ref",
                "evidence.zip_sha256",
                "pipeline.applied.target_key",
            ],
        }
    ]


def build_sample_approved_record() -> dict:
    record = build_sample_ingestion_record()
    queue = build_sample_queue(record)
    item = queue["items"][0]
    decisions = [
        {
            "queue_item_id": item["queue_item_id"],
            "match_action": "accept_suggested",
            "approval_action": "approve",
            "decision_by": "operator-approved",
            "reason": "Approved for apply-stage tests",
        }
    ]
    updated_records, _, _, _, post_queue = apply_review_decisions(
        [record],
        queue,
        decisions,
        actor_id="operator-approved",
    )
    assert post_queue["item_count"] == 0
    return updated_records[0]


def build_sample_applied_record() -> dict:
    record = build_sample_approved_record()
    queue = build_application_queue([record], sample_target_catalog())
    item = queue["items"][0]
    decisions = [
        {
            "queue_item_id": item["queue_item_id"],
            "apply_action": "apply_suggested",
            "decision_by": "operator-apply-ready",
            "reason": "Prepare record for adapter contract tests",
        }
    ]
    updated_records, _, _, post_queue = apply_application_decisions(
        [record],
        queue,
        decisions,
        actor_id="operator-apply-ready",
    )
    assert post_queue["item_count"] == 0
    return updated_records[0]

def build_sample_contracts_doc() -> dict:
    record = build_sample_applied_record()
    contracts_doc, review_queue, _ = build_adapter_execution_artifacts([record], sample_adapter_catalog())
    assert review_queue["item_count"] == 0
    assert contracts_doc["contract_count"] == 1
    return contracts_doc


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
    record = build_sample_ingestion_record()
    ref = append_ingestion_record(record, tmp_path)
    rows = list(iter_ingestion_records(tmp_path / "ingestion-events.jsonl"))

    assert ref.startswith("ingestion://")
    assert len(rows) == 1
    assert rows[0]["event_id"] == record["event_id"]



def test_build_ingestion_rollup_counts_review_and_pipeline_statuses():
    record = build_sample_ingestion_record()
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



def test_build_relationship_memory_snapshot_groups_shared_fingerprints_across_sources():
    drive_record = build_sample_ingestion_record("file:///tmp/drive.inventory.jsonl")
    dropbox_record = build_ingestion_record(
        sample_dropbox_inventory_record(),
        inventory_ref="file:///tmp/dropbox.inventory.jsonl",
    )
    snapshot, suggestions = build_relationship_memory_snapshot([drive_record, dropbox_record])

    assert snapshot["schema_version"] == RELATIONSHIP_MEMORY_SCHEMA_VERSION
    assert snapshot["entity_count"] == 1
    entity = snapshot["entities"][0]
    assert entity["anchor_key"]["kind"] == "zip_sha256"
    assert {item["source_type"] for item in entity["evidence_refs"]} == {"gdrive", "dropbox"}
    assert suggestions[drive_record["event_id"]]["entity_id"] == suggestions[dropbox_record["event_id"]]["entity_id"]
    assert suggestions[drive_record["event_id"]]["confidence"] >= 0.9



def test_build_operator_review_queue_creates_high_priority_item_for_review_required_record():
    record = build_sample_ingestion_record()
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
    record = build_sample_ingestion_record()
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



def test_apply_review_decisions_accepts_suggested_match_and_advances_to_approval():
    record = build_sample_ingestion_record()
    queue = build_sample_queue(record)
    item = queue["items"][0]
    decisions = [
        {
            "queue_item_id": item["queue_item_id"],
            "match_action": "accept_suggested",
            "decision_by": "operator-1",
            "reason": "Accept strong fingerprint match",
        }
    ]

    updated_records, decision_journal, rollup, _, post_queue = apply_review_decisions(
        [record],
        queue,
        decisions,
        actor_id="operator-1",
    )

    assert decision_journal[0]["schema_version"] == REVIEW_DECISION_SCHEMA_VERSION
    updated = updated_records[0]
    assert updated["pipeline"]["matched"]["status"] == "matched"
    assert updated["pipeline"]["matched"]["entity_id"] == item["suggested_match"]["entity_id"]
    assert updated["pipeline"]["approved"]["status"] == "pending"
    assert updated["governance"]["review_state"] == "open"
    assert updated["governance"]["review_required"] is True
    assert rollup["schema_version"] == STATE_TRANSITION_ROLLUP_SCHEMA_VERSION
    assert rollup["matched_status_counts"]["matched"] == 1
    assert rollup["review_queue"]["after_count"] == 1
    assert post_queue["item_count"] == 1
    assert post_queue["items"][0]["next_pipeline_stage"] == "approved"



def test_apply_review_decisions_can_resolve_match_and_approval_together():
    record = build_sample_ingestion_record()
    queue = build_sample_queue(record)
    item = queue["items"][0]
    decisions = [
        {
            "queue_item_id": item["queue_item_id"],
            "match_action": "accept_suggested",
            "approval_action": "approve",
            "decision_by": "operator-2",
            "reason": "Approved after review",
        }
    ]

    updated_records, decision_journal, rollup, _, post_queue = apply_review_decisions(
        [record],
        queue,
        decisions,
        actor_id="operator-2",
    )

    updated = updated_records[0]
    assert updated["pipeline"]["matched"]["status"] == "matched"
    assert updated["pipeline"]["approved"]["status"] == "approved"
    assert updated["pipeline"]["approved"]["approved_by"] == "operator-2"
    assert updated["governance"]["review_state"] == "resolved"
    assert updated["governance"]["review_required"] is False
    assert decision_journal[0]["result"]["review_state"] == "resolved"
    assert rollup["review_state_counts"]["resolved"] == 1
    assert rollup["review_queue"]["after_count"] == 0
    assert post_queue["item_count"] == 0



def test_apply_review_decisions_supports_no_match_resolution():
    record = build_sample_ingestion_record()
    queue = build_sample_queue(record)
    item = queue["items"][0]
    decisions = [
        {
            "queue_item_id": item["queue_item_id"],
            "match_action": "no_match",
            "decision_by": "operator-3",
            "reason": "Source artifact should remain unmatched",
        }
    ]

    updated_records, decision_journal, rollup, _, post_queue = apply_review_decisions(
        [record],
        queue,
        decisions,
        actor_id="operator-3",
    )

    updated = updated_records[0]
    assert updated["pipeline"]["matched"]["status"] == "no_match"
    assert updated["pipeline"]["approved"]["status"] == "not_applicable"
    assert updated["governance"]["review_state"] == "resolved"
    assert decision_journal[0]["decision_by"] == "operator-3"
    assert rollup["approved_status_counts"]["not_applicable"] == 1
    assert post_queue["item_count"] == 0



def test_apply_review_decisions_script_writes_projection_and_post_review_queue(tmp_path: Path):
    inventory_path = tmp_path / "sample.inventory.jsonl"
    inventory_path.write_text(json.dumps(sample_inventory_record()) + "\n", encoding="utf-8")
    ingestion_dir = tmp_path / "ingestion"
    relationship_dir = tmp_path / "relationship"
    decision_dir = tmp_path / "decisions"
    decision_dir.mkdir(parents=True, exist_ok=True)
    out_dir = tmp_path / "reviewed"

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

    queue_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_relationship_memory.py",
            "--ingestion-path",
            str(ingestion_dir / "ingestion-events.jsonl"),
            "--out-dir",
            str(relationship_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert queue_proc.returncode == 0, queue_proc.stderr

    queue = json.loads((relationship_dir / "operator_review_queue.json").read_text(encoding="utf-8"))
    item = queue["items"][0]
    decisions_path = decision_dir / "review_decisions.json"
    decisions_path.write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "queue_item_id": item["queue_item_id"],
                        "match_action": "accept_suggested",
                        "approval_action": "approve",
                        "decision_by": "operator-4",
                        "reason": "Approved in fixture test",
                    }
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/apply_review_decisions.py",
            "--ingestion-path",
            str(ingestion_dir / "ingestion-events.jsonl"),
            "--queue-path",
            str(relationship_dir / "operator_review_queue.json"),
            "--decisions-path",
            str(decisions_path),
            "--out-dir",
            str(out_dir),
            "--actor-id",
            "operator-4",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    projection_path = out_dir / "ingestion_state_projection.jsonl"
    journal_path = out_dir / "review_decision_journal.jsonl"
    rollup_path = out_dir / "state_transition_rollup.json"
    post_queue_path = out_dir / "operator_review_queue_post_review.json"
    post_queue_md_path = out_dir / "operator_review_queue_post_review.md"
    assert projection_path.exists()
    assert journal_path.exists()
    assert rollup_path.exists()
    assert post_queue_path.exists()
    assert post_queue_md_path.exists()

    projected_records = [json.loads(line) for line in projection_path.read_text(encoding="utf-8").splitlines() if line]
    rollup = json.loads(rollup_path.read_text(encoding="utf-8"))
    post_queue = json.loads(post_queue_path.read_text(encoding="utf-8"))
    assert projected_records[0]["pipeline"]["approved"]["status"] == "approved"
    assert rollup["review_queue"]["after_count"] == 0
    assert post_queue["item_count"] == 0

def test_build_application_queue_for_approved_record_suggests_target():
    record = build_sample_approved_record()
    queue = build_application_queue([record], sample_target_catalog())

    assert queue["schema_version"] == APPLICATION_QUEUE_SCHEMA_VERSION
    assert queue["item_count"] == 1
    item = queue["items"][0]
    assert item["next_pipeline_stage"] == "applied"
    assert item["suggested_target"]["target_key"] == "ops-evidence-ledger"
    assert "approved_pending_application" in item["reason_codes"]



def test_apply_application_decisions_accepts_suggested_target_and_marks_applied():
    record = build_sample_approved_record()
    queue = build_application_queue([record], sample_target_catalog())
    item = queue["items"][0]
    decisions = [
        {
            "queue_item_id": item["queue_item_id"],
            "apply_action": "apply_suggested",
            "decision_by": "operator-apply-1",
            "reason": "Route to default ledger",
        }
    ]

    updated_records, decision_journal, rollup, post_queue = apply_application_decisions(
        [record],
        queue,
        decisions,
        actor_id="operator-apply-1",
    )

    updated = updated_records[0]
    assert decision_journal[0]["schema_version"] == APPLICATION_DECISION_SCHEMA_VERSION
    assert updated["pipeline"]["applied"]["status"] == "applied"
    assert updated["pipeline"]["applied"]["target_key"] == "ops-evidence-ledger"
    assert updated["pipeline"]["applied"]["apply_mode"] == "projection"
    assert updated["governance"]["application_state"] == "resolved"
    assert updated["governance"]["application_required"] is False
    assert rollup["schema_version"] == APPLICATION_TRANSITION_ROLLUP_SCHEMA_VERSION
    assert rollup["applied_status_counts"]["applied"] == 1
    assert post_queue["item_count"] == 0



def test_apply_application_decisions_can_mark_not_applicable():
    record = build_sample_approved_record()
    queue = build_application_queue([record], sample_target_catalog())
    item = queue["items"][0]
    decisions = [
        {
            "queue_item_id": item["queue_item_id"],
            "apply_action": "not_applicable",
            "decision_by": "operator-apply-2",
            "reason": "No downstream sync is required",
        }
    ]

    updated_records, _, rollup, post_queue = apply_application_decisions(
        [record],
        queue,
        decisions,
        actor_id="operator-apply-2",
    )

    updated = updated_records[0]
    assert updated["pipeline"]["applied"]["status"] == "not_applicable"
    assert updated["governance"]["application_state"] == "resolved"
    assert rollup["applied_status_counts"]["not_applicable"] == 1
    assert post_queue["item_count"] == 0



def test_apply_application_decisions_defer_keeps_queue_open():
    record = build_sample_approved_record()
    queue = build_application_queue([record], sample_target_catalog())
    item = queue["items"][0]
    decisions = [
        {
            "queue_item_id": item["queue_item_id"],
            "apply_action": "defer",
            "decision_by": "operator-apply-3",
            "reason": "Wait for downstream target readiness",
        }
    ]

    updated_records, _, rollup, post_queue = apply_application_decisions(
        [record],
        queue,
        decisions,
        actor_id="operator-apply-3",
    )

    updated = updated_records[0]
    assert updated["pipeline"]["applied"]["status"] == "pending"
    assert updated["governance"]["application_state"] == "open"
    assert rollup["queue"]["after_count"] == 1
    assert post_queue["item_count"] == 1



def test_apply_application_decisions_script_writes_projection_and_rollup(tmp_path: Path):
    inventory_path = tmp_path / "sample.inventory.jsonl"
    inventory_path.write_text(json.dumps(sample_inventory_record()) + "\n", encoding="utf-8")
    ingestion_dir = tmp_path / "ingestion"
    relationship_dir = tmp_path / "relationship"
    review_dir = tmp_path / "reviewed"
    apply_dir = tmp_path / "applied"
    decisions_dir = tmp_path / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)

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

    queue_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_relationship_memory.py",
            "--ingestion-path",
            str(ingestion_dir / "ingestion-events.jsonl"),
            "--out-dir",
            str(relationship_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert queue_proc.returncode == 0, queue_proc.stderr

    queue = json.loads((relationship_dir / "operator_review_queue.json").read_text(encoding="utf-8"))
    item = queue["items"][0]
    review_decisions_path = decisions_dir / "review_decisions.json"
    review_decisions_path.write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "queue_item_id": item["queue_item_id"],
                        "match_action": "accept_suggested",
                        "approval_action": "approve",
                        "decision_by": "operator-apply-4",
                        "reason": "Approved before apply test",
                    }
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    review_proc = subprocess.run(
        [
            sys.executable,
            "scripts/apply_review_decisions.py",
            "--ingestion-path",
            str(ingestion_dir / "ingestion-events.jsonl"),
            "--queue-path",
            str(relationship_dir / "operator_review_queue.json"),
            "--decisions-path",
            str(review_decisions_path),
            "--out-dir",
            str(review_dir),
            "--actor-id",
            "operator-apply-4",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert review_proc.returncode == 0, review_proc.stderr

    target_catalog_path = decisions_dir / "target_catalog.json"
    target_catalog_path.write_text(json.dumps({"targets": sample_target_catalog()}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    apply_decisions_path = decisions_dir / "application_decisions.json"
    apply_decisions_path.write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "event_id": build_sample_approved_record()["event_id"],
                        "apply_action": "apply_suggested",
                        "decision_by": "operator-apply-4",
                        "reason": "Route approved record to default target",
                    }
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/apply_application_decisions.py",
            "--ingestion-path",
            str(review_dir / "ingestion_state_projection.jsonl"),
            "--target-catalog-path",
            str(target_catalog_path),
            "--decisions-path",
            str(apply_decisions_path),
            "--out-dir",
            str(apply_dir),
            "--actor-id",
            "operator-apply-4",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    projection_path = apply_dir / "ingestion_state_applied_projection.jsonl"
    journal_path = apply_dir / "application_decision_journal.jsonl"
    rollup_path = apply_dir / "application_transition_rollup.json"
    post_queue_path = apply_dir / "application_queue_post_apply.json"
    assert projection_path.exists()
    assert journal_path.exists()
    assert rollup_path.exists()
    assert post_queue_path.exists()

    projected_records = [json.loads(line) for line in projection_path.read_text(encoding="utf-8").splitlines() if line]
    rollup = json.loads(rollup_path.read_text(encoding="utf-8"))
    post_queue = json.loads(post_queue_path.read_text(encoding="utf-8"))
    assert projected_records[0]["pipeline"]["applied"]["status"] == "applied"
    assert rollup["queue"]["after_count"] == 0
    assert post_queue["item_count"] == 0


def test_build_adapter_execution_artifacts_for_applied_record_creates_planned_contract():
    record = build_sample_applied_record()
    contracts_doc, review_queue, rollup = build_adapter_execution_artifacts([record], sample_adapter_catalog())

    assert contracts_doc["schema_version"] == ADAPTER_EXECUTION_CONTRACTS_SCHEMA_VERSION
    assert contracts_doc["contract_count"] == 1
    contract = contracts_doc["contracts"][0]
    assert contract["contract_state"] == "planned"
    assert contract["execution_mode"] == "dry_run"
    assert contract["adapter"]["adapter_key"] == "ops-core-evidence-upsert"
    assert contract["target"]["target_key"] == "ops-evidence-ledger"
    assert review_queue["schema_version"] == ADAPTER_CONTRACT_REVIEW_QUEUE_SCHEMA_VERSION
    assert review_queue["item_count"] == 0
    assert rollup["schema_version"] == ADAPTER_CONTRACT_ROLLUP_SCHEMA_VERSION
    assert rollup["contract_count"] == 1



def test_build_adapter_execution_artifacts_creates_review_queue_when_adapter_missing():
    record = build_sample_applied_record()
    contracts_doc, review_queue, rollup = build_adapter_execution_artifacts([record], [])

    assert contracts_doc["contract_count"] == 0
    assert review_queue["item_count"] == 1
    item = review_queue["items"][0]
    assert "no_adapter_match" in item["reason_codes"]
    assert rollup["review_queue_count"] == 1



def test_build_adapter_contracts_script_writes_contracts_and_rollup(tmp_path: Path):
    inventory_path = tmp_path / "sample.inventory.jsonl"
    inventory_path.write_text(json.dumps(sample_inventory_record()) + "\n", encoding="utf-8")
    ingestion_dir = tmp_path / "ingestion"
    relationship_dir = tmp_path / "relationship"
    review_dir = tmp_path / "reviewed"
    apply_dir = tmp_path / "applied"
    contract_dir = tmp_path / "contracts"
    decisions_dir = tmp_path / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)

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

    queue_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_relationship_memory.py",
            "--ingestion-path",
            str(ingestion_dir / "ingestion-events.jsonl"),
            "--out-dir",
            str(relationship_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert queue_proc.returncode == 0, queue_proc.stderr

    review_queue = json.loads((relationship_dir / "operator_review_queue.json").read_text(encoding="utf-8"))
    review_item = review_queue["items"][0]
    review_decisions_path = decisions_dir / "review_decisions.json"
    review_decisions_path.write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "queue_item_id": review_item["queue_item_id"],
                        "match_action": "accept_suggested",
                        "approval_action": "approve",
                        "decision_by": "operator-contract-1",
                        "reason": "Approved for adapter contract test",
                    }
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    review_proc = subprocess.run(
        [
            sys.executable,
            "scripts/apply_review_decisions.py",
            "--ingestion-path",
            str(ingestion_dir / "ingestion-events.jsonl"),
            "--queue-path",
            str(relationship_dir / "operator_review_queue.json"),
            "--decisions-path",
            str(review_decisions_path),
            "--out-dir",
            str(review_dir),
            "--actor-id",
            "operator-contract-1",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert review_proc.returncode == 0, review_proc.stderr

    target_catalog_path = decisions_dir / "target_catalog.json"
    target_catalog_path.write_text(json.dumps({"targets": sample_target_catalog()}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    apply_decisions_path = decisions_dir / "application_decisions.json"
    apply_decisions_path.write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "event_id": build_sample_approved_record()["event_id"],
                        "apply_action": "apply_suggested",
                        "decision_by": "operator-contract-1",
                        "reason": "Route approved record for adapter contract test",
                    }
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    apply_proc = subprocess.run(
        [
            sys.executable,
            "scripts/apply_application_decisions.py",
            "--ingestion-path",
            str(review_dir / "ingestion_state_projection.jsonl"),
            "--target-catalog-path",
            str(target_catalog_path),
            "--decisions-path",
            str(apply_decisions_path),
            "--out-dir",
            str(apply_dir),
            "--actor-id",
            "operator-contract-1",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert apply_proc.returncode == 0, apply_proc.stderr

    adapter_catalog_path = decisions_dir / "adapter_catalog.json"
    adapter_catalog_path.write_text(json.dumps({"adapters": sample_adapter_catalog()}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_adapter_contracts.py",
            "--ingestion-path",
            str(apply_dir / "ingestion_state_applied_projection.jsonl"),
            "--adapter-catalog-path",
            str(adapter_catalog_path),
            "--out-dir",
            str(contract_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    contracts_path = contract_dir / "adapter_execution_contracts.json"
    review_queue_path = contract_dir / "adapter_contract_review_queue.json"
    rollup_path = contract_dir / "adapter_contract_rollup.json"
    assert contracts_path.exists()
    assert review_queue_path.exists()
    assert rollup_path.exists()

    contracts_doc = json.loads(contracts_path.read_text(encoding="utf-8"))
    review_queue = json.loads(review_queue_path.read_text(encoding="utf-8"))
    rollup = json.loads(rollup_path.read_text(encoding="utf-8"))
    assert contracts_doc["contract_count"] == 1
    assert review_queue["item_count"] == 0
    assert rollup["contract_count"] == 1


def test_apply_adapter_execution_outcomes_updates_contract_and_ingests_dry_run_result():
    record = build_sample_applied_record()
    contracts_doc, _, _ = build_adapter_execution_artifacts([record], sample_adapter_catalog())
    contract = contracts_doc["contracts"][0]
    decisions = [
        {
            "contract_id": contract["contract_id"],
            "outcome_action": "dry_run_success",
            "executed_by": "adapter-runner-1",
            "reason": "Validated contract payload without external side effects",
            "external_ref": "dry-run-001",
        }
    ]

    updated_records, updated_contracts_doc, journal, rollup = apply_adapter_execution_outcomes(
        [record],
        contracts_doc,
        decisions,
        actor_id="adapter-runner-1",
    )

    assert updated_contracts_doc["contract_count"] == 1
    updated_contract = updated_contracts_doc["contracts"][0]
    assert updated_contract["contract_state"] == "validated"
    assert updated_contract["execution_status"] == "dry_run_succeeded"
    assert updated_contract["execution_ref"].startswith("adapter-execution://adapter-exec-")
    assert journal[0]["schema_version"] == ADAPTER_EXECUTION_JOURNAL_SCHEMA_VERSION
    assert journal[0]["execution_status"] == "dry_run_succeeded"
    updated_record = updated_records[0]
    assert updated_record["pipeline"]["applied"]["execution_status"] == "dry_run_succeeded"
    assert updated_record["pipeline"]["applied"]["adapter_contract_id"] == contract["contract_id"]
    assert updated_record["governance"]["execution_followup_required"] is False
    assert rollup["schema_version"] == ADAPTER_EXECUTION_ROLLUP_SCHEMA_VERSION
    assert rollup["execution_status_counts"]["dry_run_succeeded"] == 1



def test_apply_adapter_execution_outcomes_marks_failures_for_followup_review():
    record = build_sample_applied_record()
    contracts_doc, _, _ = build_adapter_execution_artifacts([record], sample_adapter_catalog())
    contract = contracts_doc["contracts"][0]
    decisions = [
        {
            "contract_id": contract["contract_id"],
            "outcome_action": "execute_failure",
            "executed_by": "adapter-runner-2",
            "reason": "Downstream endpoint returned a retryable failure",
            "status_code": "503",
        }
    ]

    updated_records, updated_contracts_doc, journal, rollup = apply_adapter_execution_outcomes(
        [record],
        contracts_doc,
        decisions,
        actor_id="adapter-runner-2",
    )

    updated_contract = updated_contracts_doc["contracts"][0]
    assert updated_contract["contract_state"] == "failed"
    assert updated_contract["execution_status"] == "failed"
    assert journal[0]["governance"]["followup_required"] is True
    updated_record = updated_records[0]
    assert updated_record["pipeline"]["applied"]["execution_status"] == "failed"
    assert updated_record["governance"]["execution_followup_required"] is True
    assert updated_record["governance"]["review_required"] is True
    assert rollup["followup_required_count"] == 1
    assert rollup["record_execution_status_counts"]["failed"] == 1



def test_apply_adapter_execution_outcomes_script_writes_projection_journal_and_rollup(tmp_path: Path):
    inventory_path = tmp_path / "sample.inventory.jsonl"
    inventory_path.write_text(json.dumps(sample_inventory_record()) + "\n", encoding="utf-8")
    ingestion_dir = tmp_path / "ingestion"
    relationship_dir = tmp_path / "relationship"
    review_dir = tmp_path / "reviewed"
    apply_dir = tmp_path / "applied"
    contract_dir = tmp_path / "contracts"
    execute_dir = tmp_path / "executed"
    decisions_dir = tmp_path / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)

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

    queue_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_relationship_memory.py",
            "--ingestion-path",
            str(ingestion_dir / "ingestion-events.jsonl"),
            "--out-dir",
            str(relationship_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert queue_proc.returncode == 0, queue_proc.stderr

    review_queue = json.loads((relationship_dir / "operator_review_queue.json").read_text(encoding="utf-8"))
    review_item = review_queue["items"][0]
    review_decisions_path = decisions_dir / "review_decisions.json"
    review_decisions_path.write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "queue_item_id": review_item["queue_item_id"],
                        "match_action": "accept_suggested",
                        "approval_action": "approve",
                        "decision_by": "operator-exec-1",
                        "reason": "Approve for execution outcome test",
                    }
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    review_proc = subprocess.run(
        [
            sys.executable,
            "scripts/apply_review_decisions.py",
            "--ingestion-path",
            str(ingestion_dir / "ingestion-events.jsonl"),
            "--queue-path",
            str(relationship_dir / "operator_review_queue.json"),
            "--decisions-path",
            str(review_decisions_path),
            "--out-dir",
            str(review_dir),
            "--actor-id",
            "operator-exec-1",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert review_proc.returncode == 0, review_proc.stderr

    target_catalog_path = decisions_dir / "target_catalog.json"
    target_catalog_path.write_text(json.dumps({"targets": sample_target_catalog()}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    apply_decisions_path = decisions_dir / "application_decisions.json"
    approved_event_id = json.loads((review_dir / "ingestion_state_projection.jsonl").read_text(encoding="utf-8").splitlines()[0])["event_id"]
    apply_decisions_path.write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "event_id": approved_event_id,
                        "apply_action": "apply_suggested",
                        "decision_by": "operator-exec-1",
                        "reason": "Route approved record for adapter execution test",
                    }
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    apply_proc = subprocess.run(
        [
            sys.executable,
            "scripts/apply_application_decisions.py",
            "--ingestion-path",
            str(review_dir / "ingestion_state_projection.jsonl"),
            "--target-catalog-path",
            str(target_catalog_path),
            "--decisions-path",
            str(apply_decisions_path),
            "--out-dir",
            str(apply_dir),
            "--actor-id",
            "operator-exec-1",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert apply_proc.returncode == 0, apply_proc.stderr

    adapter_catalog_path = decisions_dir / "adapter_catalog.json"
    adapter_catalog_path.write_text(json.dumps({"adapters": sample_adapter_catalog()}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    contract_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_adapter_contracts.py",
            "--ingestion-path",
            str(apply_dir / "ingestion_state_applied_projection.jsonl"),
            "--adapter-catalog-path",
            str(adapter_catalog_path),
            "--out-dir",
            str(contract_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert contract_proc.returncode == 0, contract_proc.stderr

    contracts_doc = json.loads((contract_dir / "adapter_execution_contracts.json").read_text(encoding="utf-8"))
    contract_id = contracts_doc["contracts"][0]["contract_id"]
    execution_decisions_path = decisions_dir / "adapter_execution_decisions.json"
    execution_decisions_path.write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "contract_id": contract_id,
                        "outcome_action": "dry_run_success",
                        "executed_by": "adapter-exec-1",
                        "reason": "Validated the adapter contract in dry-run mode",
                    }
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/apply_adapter_execution_outcomes.py",
            "--ingestion-path",
            str(apply_dir / "ingestion_state_applied_projection.jsonl"),
            "--contracts-path",
            str(contract_dir / "adapter_execution_contracts.json"),
            "--decisions-path",
            str(execution_decisions_path),
            "--out-dir",
            str(execute_dir),
            "--actor-id",
            "adapter-exec-1",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    projection_path = execute_dir / "ingestion_state_execution_projection.jsonl"
    journal_path = execute_dir / "adapter_execution_journal.jsonl"
    contracts_path = execute_dir / "adapter_execution_contracts_post_execute.json"
    rollup_path = execute_dir / "adapter_execution_rollup.json"
    assert projection_path.exists()
    assert journal_path.exists()
    assert contracts_path.exists()
    assert rollup_path.exists()

    projected_records = [json.loads(line) for line in projection_path.read_text(encoding="utf-8").splitlines() if line]
    journal_rows = [json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines() if line]
    contracts_doc = json.loads(contracts_path.read_text(encoding="utf-8"))
    rollup = json.loads(rollup_path.read_text(encoding="utf-8"))
    assert projected_records[0]["pipeline"]["applied"]["execution_status"] == "dry_run_succeeded"
    assert projected_records[0]["governance"]["execution_followup_required"] is False
    assert journal_rows[0]["execution_status"] == "dry_run_succeeded"
    assert contracts_doc["contracts"][0]["contract_state"] == "validated"
    assert rollup["execution_status_counts"]["dry_run_succeeded"] == 1
