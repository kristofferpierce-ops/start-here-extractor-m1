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
from start_here_extractor.adapter_runners import (
    ADAPTER_RUNNER_JOBS_SCHEMA_VERSION,
    ADAPTER_RUNNER_REVIEW_QUEUE_SCHEMA_VERSION,
    ADAPTER_RUNNER_ROLLUP_SCHEMA_VERSION,
    EXTERNAL_OUTCOME_DECISIONS_SCHEMA_VERSION,
    EXTERNAL_OUTCOME_REVIEW_QUEUE_SCHEMA_VERSION,
    EXTERNAL_OUTCOME_ROLLUP_SCHEMA_VERSION,
    build_adapter_runner_job_artifacts,
    collect_adapter_execution_outcomes,
)
from start_here_extractor.adapter_runner_interfaces import (
    ADAPTER_RUNNER_INTERFACE_CONTRACTS_SCHEMA_VERSION,
    ADAPTER_RUNNER_INTERFACE_REVIEW_QUEUE_SCHEMA_VERSION,
    ADAPTER_RUNNER_INTERFACE_ROLLUP_SCHEMA_VERSION,
    NORMALIZED_EXTERNAL_OUTCOMES_SCHEMA_VERSION,
    COLLECTOR_NORMALIZATION_REVIEW_QUEUE_SCHEMA_VERSION,
    COLLECTOR_NORMALIZATION_ROLLUP_SCHEMA_VERSION,
    build_runner_interface_artifacts,
    normalize_external_runner_outcomes,
)
from start_here_extractor.target_runner_families import (
    TARGET_FAMILY_RUNNER_STUBS_SCHEMA_VERSION,
    TARGET_FAMILY_RUNNER_REVIEW_QUEUE_SCHEMA_VERSION,
    TARGET_FAMILY_RUNNER_ROLLUP_SCHEMA_VERSION,
    TARGET_FAMILY_COLLECTOR_FIXTURES_SCHEMA_VERSION,
    TARGET_FAMILY_COLLECTOR_REVIEW_QUEUE_SCHEMA_VERSION,
    TARGET_FAMILY_COLLECTOR_ROLLUP_SCHEMA_VERSION,
    build_target_family_runner_stub_artifacts,
    build_target_family_collector_fixture_artifacts,
)
from start_here_extractor.family_interface_templates import (
    FAMILY_INTERFACE_TEMPLATES_SCHEMA_VERSION,
    FAMILY_INTERFACE_TEMPLATE_REVIEW_QUEUE_SCHEMA_VERSION,
    FAMILY_INTERFACE_TEMPLATE_ROLLUP_SCHEMA_VERSION,
    CANONICAL_RAW_PAYLOAD_CONTRACTS_SCHEMA_VERSION,
    CANONICAL_RAW_PAYLOAD_REVIEW_QUEUE_SCHEMA_VERSION,
    CANONICAL_RAW_PAYLOAD_ROLLUP_SCHEMA_VERSION,
    build_family_interface_template_artifacts,
    build_canonical_raw_payload_contract_artifacts,
)
from start_here_extractor.target_group_adapter_packages import (
    TARGET_GROUP_ADAPTER_PACKAGES_SCHEMA_VERSION,
    TARGET_GROUP_ADAPTER_PACKAGE_REVIEW_QUEUE_SCHEMA_VERSION,
    TARGET_GROUP_ADAPTER_PACKAGE_ROLLUP_SCHEMA_VERSION,
    CANONICAL_REQUEST_RESPONSE_FIXTURE_PACKS_SCHEMA_VERSION,
    CANONICAL_REQUEST_RESPONSE_FIXTURE_REVIEW_QUEUE_SCHEMA_VERSION,
    CANONICAL_REQUEST_RESPONSE_FIXTURE_ROLLUP_SCHEMA_VERSION,
    build_target_group_adapter_package_artifacts,
    build_canonical_request_response_fixture_pack_artifacts,
)
from start_here_extractor.target_group_adapter_implementation_shells import (
    TARGET_GROUP_ADAPTER_IMPLEMENTATION_SHELLS_SCHEMA_VERSION,
    TARGET_GROUP_ADAPTER_IMPLEMENTATION_SHELL_REVIEW_QUEUE_SCHEMA_VERSION,
    TARGET_GROUP_ADAPTER_IMPLEMENTATION_SHELL_ROLLUP_SCHEMA_VERSION,
    END_TO_END_ROUNDTRIP_FIXTURE_EXECUTION_PACKS_SCHEMA_VERSION,
    END_TO_END_ROUNDTRIP_FIXTURE_EXECUTION_REVIEW_QUEUE_SCHEMA_VERSION,
    END_TO_END_ROUNDTRIP_FIXTURE_EXECUTION_ROLLUP_SCHEMA_VERSION,
    build_target_group_adapter_implementation_shell_artifacts,
    build_end_to_end_roundtrip_fixture_execution_pack_artifacts,
)

from start_here_extractor.target_group_adapter_execution_harnesses import (
    TARGET_GROUP_ADAPTER_EXECUTION_HARNESSES_SCHEMA_VERSION,
    TARGET_GROUP_ADAPTER_EXECUTION_HARNESS_REVIEW_QUEUE_SCHEMA_VERSION,
    TARGET_GROUP_ADAPTER_EXECUTION_HARNESS_ROLLUP_SCHEMA_VERSION,
    REPLAYABLE_DRY_RUN_ORCHESTRATION_PACKS_SCHEMA_VERSION,
    REPLAYABLE_DRY_RUN_ORCHESTRATION_REVIEW_QUEUE_SCHEMA_VERSION,
    REPLAYABLE_DRY_RUN_ORCHESTRATION_ROLLUP_SCHEMA_VERSION,
    build_target_group_adapter_execution_harness_artifacts,
    build_replayable_dry_run_orchestration_pack_artifacts,
)

from start_here_extractor.target_group_adapter_skeletons import (
    TARGET_GROUP_ADAPTER_SKELETONS_SCHEMA_VERSION,
    TARGET_GROUP_ADAPTER_SKELETON_REVIEW_QUEUE_SCHEMA_VERSION,
    TARGET_GROUP_ADAPTER_SKELETON_ROLLUP_SCHEMA_VERSION,
    ROUNDTRIP_NORMALIZATION_CASES_SCHEMA_VERSION,
    ROUNDTRIP_NORMALIZATION_REVIEW_QUEUE_SCHEMA_VERSION,
    ROUNDTRIP_NORMALIZATION_ROLLUP_SCHEMA_VERSION,
    build_target_group_adapter_skeleton_artifacts,
    build_roundtrip_normalization_case_artifacts,
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


def sample_runner_catalog() -> list[dict]:
    return [
        {
            "runner_key": "ops-core-dry-run-stub",
            "runner_family": "job-stub",
            "runner_version": "1.0",
            "stub_kind": "json-envelope",
            "dispatch_transport": "json-envelope",
            "supported_adapter_families": ["ledger"],
            "supported_execution_modes": ["dry_run", "execute"],
            "supported_target_systems": ["ops-core"],
            "supported_operations": ["upsert-evidence-record"],
        }
    ]


def sample_runner_interface_catalog() -> list[dict]:
    return [
        {
            "interface_key": "ops-core-json-envelope-interface",
            "interface_family": "runner-interface-stub",
            "interface_version": "1.0",
            "outbound_contract_kind": "runner-job-envelope-v1",
            "result_contract_kind": "runner-json-envelope-v1",
            "normalizer_key": "json-envelope-v1",
            "supported_runner_families": ["job-stub"],
            "supported_dispatch_transports": ["json-envelope"],
            "supported_stub_kinds": ["json-envelope"],
            "supported_target_systems": ["ops-core"],
            "supported_adapter_families": ["ledger"],
            "supported_operations": ["upsert-evidence-record"],
        }
    ]


def sample_target_family_catalog() -> list[dict]:
    return [
        {
            "target_family_key": "ops-core-ledger-family",
            "target_family_name": "Ops Core Ledger Family",
            "runner_stub_family": "ops-core-ledger-stub",
            "fixture_family_key": "ops-core-ledger-fixtures",
            "request_template_kind": "ops-core-ledger-request-v1",
            "normalized_outcome_kind": "ops-core-ledger-outcome-v1",
            "supported_interface_keys": ["ops-core-json-envelope-interface"],
            "supported_target_systems": ["ops-core"],
            "supported_target_types": ["evidence-ledger"],
            "supported_adapter_families": ["ledger"],
            "supported_runner_families": ["job-stub"],
            "supported_operations": ["upsert-evidence-record"],
            "supported_normalizer_keys": ["json-envelope-v1"],
            "default_fixture_statuses": ["success", "failure", "defer", "skip"],
        }
    ]


def sample_family_interface_template_catalog() -> list[dict]:
    return [
        {
            "family_template_key": "ops-core-ledger-template",
            "template_family": "ops-core-ledger-template-family",
            "template_version": "1.0",
            "raw_payload_kind": "ops-core-ledger-raw-payload-v1",
            "canonical_payload_kind": "ops-core-ledger-normalized-payload-v1",
            "supported_target_family_keys": ["ops-core-ledger-family"],
            "supported_target_systems": ["ops-core"],
            "supported_target_types": ["evidence-ledger"],
            "supported_adapter_families": ["ledger"],
            "supported_interface_keys": ["ops-core-json-envelope-interface"],
            "supported_normalizer_keys": ["json-envelope-v1"],
            "supported_operations": ["upsert-evidence-record"],
            "required_fields": ["runner_job_id", "outcome_collection_key", "status", "raw_payload_ref"],
            "optional_fields": ["contract_id", "event_id", "status_reason", "payload_digest"],
            "status_map": {"ok": "success", "failed": "failure", "retry": "defer", "skipped": "skip"},
        }
    ]


def sample_target_group_catalog() -> list[dict]:
    return [
        {
            "target_group_key": "ops-core-ledger-group",
            "target_group_name": "Ops Core Ledger Group",
            "supported_target_family_keys": ["ops-core-ledger-family"],
            "supported_template_families": ["ops-core-ledger-template-family"],
            "supported_target_systems": ["ops-core"],
            "supported_target_types": ["evidence-ledger"],
            "supported_operations": ["upsert-evidence-record"],
            "adapter_package_key": "ops-core-ledger-adapter-package",
            "package_family": "ops-core-ledger-package-family",
            "request_template_kind": "ops-core-ledger-request-fixture-v1",
            "response_template_kind": "ops-core-ledger-response-fixture-v1",
            "fixture_modes": ["success", "failure", "defer", "skip"],
        }
    ]


def sample_target_group_adapter_skeleton_catalog() -> list[dict]:
    return [
        {
            "target_group_key": "ops-core-ledger-group",
            "target_group_name": "Ops Core Ledger Group",
            "adapter_group_key": "ops-core-ledger-adapter-group",
            "adapter_group_name": "Ops Core Ledger Adapter Group",
            "adapter_kind": "ops-core-ledger-http-stub",
            "supported_target_group_keys": ["ops-core-ledger-group"],
            "supported_package_families": ["ops-core-ledger-package-family"],
            "supported_request_template_kinds": ["ops-core-ledger-request-fixture-v1"],
            "supported_response_template_kinds": ["ops-core-ledger-response-fixture-v1"],
            "supported_raw_payload_kinds": ["ops-core-ledger-raw-payload-v1"],
            "supported_target_systems": ["ops-core"],
            "supported_target_types": ["evidence-ledger"],
            "supported_operations": ["upsert-evidence-record"],
            "request_method": "POST",
            "request_path_template": "/ops-core/ledger/upsert",
            "success_status_codes": [200, 201],
            "failure_status_codes": [400, 409, 500],
            "defer_status_codes": [202],
            "skip_status_codes": [204],
        }
    ]




def sample_target_group_adapter_implementation_catalog() -> list[dict]:
    return [
        {
            "target_group_key": "ops-core-ledger-group",
            "adapter_group_key": "ops-core-ledger-adapter-group",
            "implementation_group_key": "ops-core-ledger-implementation-group",
            "implementation_group_name": "Ops Core Ledger Implementation Group",
            "implementation_shell_kind": "ops-core-ledger-implementation-shell",
            "supported_target_group_keys": ["ops-core-ledger-group"],
            "supported_adapter_group_keys": ["ops-core-ledger-adapter-group"],
            "supported_target_systems": ["ops-core"],
            "supported_target_types": ["evidence-ledger"],
            "supported_operations": ["upsert-evidence-record"],
            "supported_request_methods": ["POST"],
            "supported_fixture_modes": ["success", "failure", "defer", "skip"],
            "adapter_module": "start_here_extractor.adapters.ops_core_ledger",
            "adapter_class": "OpsCoreLedgerAdapter",
            "entrypoint": "execute",
            "supports_live_execute": False,
            "supports_dry_run": True,
        }
    ]



def sample_target_group_execution_harness_catalog() -> list[dict]:
    return [
        {
            "target_group_key": "ops-core-ledger-group",
            "implementation_group_key": "ops-core-ledger-implementation-group",
            "harness_group_key": "ops-core-ledger-harness-group",
            "harness_group_name": "Ops Core Ledger Harness Group",
            "harness_kind": "ops-core-ledger-replayable-dry-run-harness",
            "supported_target_group_keys": ["ops-core-ledger-group"],
            "supported_implementation_group_keys": ["ops-core-ledger-implementation-group"],
            "supported_target_systems": ["ops-core"],
            "supported_target_types": ["evidence-ledger"],
            "supported_operations": ["upsert-evidence-record"],
            "supported_fixture_modes": ["success", "failure", "defer", "skip"],
            "execution_modes": ["dry_run", "fixture_execution", "replayable_dry_run"],
            "network_mode": "offline",
            "replay_token_keys": ["event_id", "contract_id"],
            "correlation_keys": ["event_id", "contract_id", "runner_job_id"],
            "supports_replayable_dry_run": True,
            "supports_fixture_execution": True,
            "supports_live_execute": False,
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


def build_sample_runner_jobs_doc() -> dict:
    contracts_doc = build_sample_contracts_doc()
    jobs_doc, review_queue, _ = build_adapter_runner_job_artifacts(contracts_doc, sample_runner_catalog())
    assert review_queue["item_count"] == 0
    assert jobs_doc["job_count"] == 1
    return jobs_doc


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


def test_build_adapter_runner_job_artifacts_creates_pending_dispatch_job():
    contracts_doc = build_sample_contracts_doc()
    jobs_doc, review_queue, rollup = build_adapter_runner_job_artifacts(contracts_doc, sample_runner_catalog())

    assert jobs_doc["schema_version"] == ADAPTER_RUNNER_JOBS_SCHEMA_VERSION
    assert jobs_doc["job_count"] == 1
    job = jobs_doc["jobs"][0]
    assert job["state"] == "pending_dispatch"
    assert job["dispatch_ref"].startswith("adapter-runner://runner-job-")
    assert job["runner"]["runner_key"] == "ops-core-dry-run-stub"
    assert job["outcome_collection_key"].startswith("outcome-")
    assert review_queue["schema_version"] == ADAPTER_RUNNER_REVIEW_QUEUE_SCHEMA_VERSION
    assert review_queue["item_count"] == 0
    assert rollup["schema_version"] == ADAPTER_RUNNER_ROLLUP_SCHEMA_VERSION
    assert rollup["job_count"] == 1
    assert rollup["runner_family_counts"]["job-stub"] == 1



def test_build_adapter_runner_job_artifacts_creates_review_queue_when_runner_missing():
    contracts_doc = build_sample_contracts_doc()
    jobs_doc, review_queue, rollup = build_adapter_runner_job_artifacts(contracts_doc, [])

    assert jobs_doc["job_count"] == 0
    assert review_queue["item_count"] == 1
    item = review_queue["items"][0]
    assert "no_runner_match" in item["reason_codes"]
    assert rollup["review_queue_count"] == 1



def test_collect_adapter_execution_outcomes_builds_decision_for_successful_payload():
    jobs_doc = build_sample_runner_jobs_doc()
    job = jobs_doc["jobs"][0]
    payloads = [
        {
            "runner_job_id": job["runner_job_id"],
            "outcome_status": "success",
            "executed_by": "runner-worker-1",
            "reason": "External dry-run stub completed successfully",
            "external_ref": "stub-run-001",
        }
    ]

    decisions_doc, review_queue, rollup = collect_adapter_execution_outcomes(jobs_doc, payloads, actor_id="collector-1")

    assert decisions_doc["schema_version"] == EXTERNAL_OUTCOME_DECISIONS_SCHEMA_VERSION
    assert decisions_doc["decision_count"] == 1
    decision = decisions_doc["decisions"][0]
    assert decision["outcome_action"] == "dry_run_success"
    assert decision["executed_by"] == "runner-worker-1"
    assert decision["runner_job_id"] == job["runner_job_id"]
    assert review_queue["schema_version"] == EXTERNAL_OUTCOME_REVIEW_QUEUE_SCHEMA_VERSION
    assert review_queue["item_count"] == 0
    assert rollup["schema_version"] == EXTERNAL_OUTCOME_ROLLUP_SCHEMA_VERSION
    assert rollup["outcome_action_counts"]["dry_run_success"] == 1



def test_collect_adapter_execution_outcomes_queues_unmatched_payload():
    jobs_doc = build_sample_runner_jobs_doc()
    payloads = [{"runner_job_id": "runner-job-missing", "outcome_status": "success"}]

    decisions_doc, review_queue, rollup = collect_adapter_execution_outcomes(jobs_doc, payloads, actor_id="collector-2")

    assert decisions_doc["decision_count"] == 0
    assert review_queue["item_count"] == 1
    item = review_queue["items"][0]
    assert "no_matching_runner_job" in item["reason_codes"]
    assert rollup["review_queue_count"] == 1



def test_adapter_runner_and_external_outcome_scripts_write_expected_artifacts(tmp_path: Path):
    contracts_path = tmp_path / "adapter_execution_contracts.json"
    contracts_path.write_text(json.dumps(build_sample_contracts_doc(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    runner_catalog_path = tmp_path / "runner_catalog.json"
    runner_catalog_path.write_text(json.dumps({"runners": sample_runner_catalog()}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    jobs_dir = tmp_path / "runner_jobs"
    outcomes_dir = tmp_path / "outcomes"

    jobs_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_adapter_runner_jobs.py",
            "--contracts-path",
            str(contracts_path),
            "--runner-catalog-path",
            str(runner_catalog_path),
            "--out-dir",
            str(jobs_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert jobs_proc.returncode == 0, jobs_proc.stderr

    jobs_doc = json.loads((jobs_dir / "adapter_runner_jobs.json").read_text(encoding="utf-8"))
    payloads_path = tmp_path / "external_outcomes.json"
    payloads_path.write_text(
        json.dumps(
            {
                "outcomes": [
                    {
                        "runner_job_id": jobs_doc["jobs"][0]["runner_job_id"],
                        "outcome_status": "success",
                        "executed_by": "runner-worker-script",
                        "reason": "Dry-run stub completed",
                    }
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    collect_proc = subprocess.run(
        [
            sys.executable,
            "scripts/collect_adapter_execution_outcomes.py",
            "--runner-jobs-path",
            str(jobs_dir / "adapter_runner_jobs.json"),
            "--payloads-path",
            str(payloads_path),
            "--out-dir",
            str(outcomes_dir),
            "--actor-id",
            "collector-script-1",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert collect_proc.returncode == 0, collect_proc.stderr
    decisions_path = outcomes_dir / "collected_adapter_execution_decisions.json"
    review_queue_path = outcomes_dir / "external_outcome_review_queue.json"
    rollup_path = outcomes_dir / "external_outcome_rollup.json"
    assert decisions_path.exists()
    assert review_queue_path.exists()
    assert rollup_path.exists()

    decisions_doc = json.loads(decisions_path.read_text(encoding="utf-8"))
    review_queue = json.loads(review_queue_path.read_text(encoding="utf-8"))
    rollup = json.loads(rollup_path.read_text(encoding="utf-8"))
    assert decisions_doc["decision_count"] == 1
    assert decisions_doc["decisions"][0]["outcome_action"] == "dry_run_success"
    assert review_queue["item_count"] == 0
    assert rollup["outcome_action_counts"]["dry_run_success"] == 1


def build_sample_runner_interface_contracts_doc() -> dict:
    jobs_doc = build_sample_runner_jobs_doc()
    contracts_doc, review_queue, _ = build_runner_interface_artifacts(jobs_doc, sample_runner_interface_catalog())
    assert review_queue["item_count"] == 0
    assert contracts_doc["contract_count"] == 1
    return contracts_doc


def build_sample_target_family_runner_stubs_doc() -> dict:
    interface_contracts = build_sample_runner_interface_contracts_doc()
    stubs_doc, review_queue, _ = build_target_family_runner_stub_artifacts(interface_contracts, sample_target_family_catalog())
    assert review_queue["item_count"] == 0
    assert stubs_doc["stub_count"] == 1
    return stubs_doc


def build_sample_family_interface_templates_doc() -> dict:
    stubs_doc = build_sample_target_family_runner_stubs_doc()
    templates_doc, review_queue, _ = build_family_interface_template_artifacts(stubs_doc, sample_family_interface_template_catalog())
    assert review_queue["item_count"] == 0
    assert templates_doc["template_count"] == 1
    return templates_doc


def build_sample_canonical_raw_payload_contracts_doc() -> dict:
    templates_doc = build_sample_family_interface_templates_doc()
    contracts_doc, review_queue, _ = build_canonical_raw_payload_contract_artifacts(templates_doc)
    assert review_queue["item_count"] == 0
    assert contracts_doc["contract_count"] == 1
    return contracts_doc


def test_build_runner_interface_artifacts_creates_stubbed_interface_contract():
    jobs_doc = build_sample_runner_jobs_doc()
    contracts_doc, review_queue, rollup = build_runner_interface_artifacts(jobs_doc, sample_runner_interface_catalog())

    assert contracts_doc["schema_version"] == ADAPTER_RUNNER_INTERFACE_CONTRACTS_SCHEMA_VERSION
    assert contracts_doc["contract_count"] == 1
    contract = contracts_doc["contracts"][0]
    assert contract["state"] == "stubbed"
    assert contract["interface"]["interface_key"] == "ops-core-json-envelope-interface"
    assert contract["collector_contract"]["normalizer_key"] == "json-envelope-v1"
    assert review_queue["schema_version"] == ADAPTER_RUNNER_INTERFACE_REVIEW_QUEUE_SCHEMA_VERSION
    assert review_queue["item_count"] == 0
    assert rollup["schema_version"] == ADAPTER_RUNNER_INTERFACE_ROLLUP_SCHEMA_VERSION
    assert rollup["interface_family_counts"]["runner-interface-stub"] == 1



def test_build_runner_interface_artifacts_creates_review_queue_when_interface_missing():
    jobs_doc = build_sample_runner_jobs_doc()
    contracts_doc, review_queue, rollup = build_runner_interface_artifacts(jobs_doc, [])

    assert contracts_doc["contract_count"] == 0
    assert review_queue["item_count"] == 1
    item = review_queue["items"][0]
    assert "no_runner_interface_match" in item["reason_codes"]
    assert rollup["review_queue_count"] == 1



def test_normalize_external_runner_outcomes_creates_canonical_outcome():
    contracts_doc = build_sample_runner_interface_contracts_doc()
    contract = contracts_doc["contracts"][0]
    payloads = [
        {
            "runner_job_id": contract["runner_job_id"],
            "status": "completed",
            "executed_by": "runner-worker-8",
            "completed_at": "2026-03-21T11:00:00+00:00",
            "message": "Runner interface stub completed",
            "result_ref": "job-result-001",
        }
    ]

    outcomes_doc, review_queue, rollup = normalize_external_runner_outcomes(contracts_doc, payloads, actor_id="collector-8")

    assert outcomes_doc["schema_version"] == NORMALIZED_EXTERNAL_OUTCOMES_SCHEMA_VERSION
    assert outcomes_doc["outcome_count"] == 1
    outcome = outcomes_doc["outcomes"][0]
    assert outcome["outcome_status"] == "success"
    assert outcome["normalizer_key"] == "json-envelope-v1"
    assert outcome["runner_job_id"] == contract["runner_job_id"]
    assert review_queue["schema_version"] == COLLECTOR_NORMALIZATION_REVIEW_QUEUE_SCHEMA_VERSION
    assert review_queue["item_count"] == 0
    assert rollup["schema_version"] == COLLECTOR_NORMALIZATION_ROLLUP_SCHEMA_VERSION
    assert rollup["outcome_status_counts"]["success"] == 1



def test_normalize_external_runner_outcomes_queues_unmatched_payload():
    contracts_doc = build_sample_runner_interface_contracts_doc()
    payloads = [{"runner_job_id": "runner-job-missing", "status": "completed"}]

    outcomes_doc, review_queue, rollup = normalize_external_runner_outcomes(contracts_doc, payloads, actor_id="collector-9")

    assert outcomes_doc["outcome_count"] == 0
    assert review_queue["item_count"] == 1
    item = review_queue["items"][0]
    assert "no_matching_interface_contract" in item["reason_codes"]
    assert rollup["review_queue_count"] == 1



def test_runner_interface_and_normalization_scripts_write_expected_artifacts(tmp_path: Path):
    jobs_path = tmp_path / "adapter_runner_jobs.json"
    jobs_path.write_text(json.dumps(build_sample_runner_jobs_doc(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    interface_catalog_path = tmp_path / "runner_interface_catalog.json"
    interface_catalog_path.write_text(
        json.dumps({"interfaces": sample_runner_interface_catalog()}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    interface_dir = tmp_path / "runner_interface"
    normalized_dir = tmp_path / "normalized_outcomes"

    iface_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_runner_interface_contracts.py",
            "--runner-jobs-path",
            str(jobs_path),
            "--interface-catalog-path",
            str(interface_catalog_path),
            "--out-dir",
            str(interface_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert iface_proc.returncode == 0, iface_proc.stderr

    interface_doc = json.loads((interface_dir / "adapter_runner_interface_contracts.json").read_text(encoding="utf-8"))
    payloads_path = tmp_path / "raw_external_payloads.json"
    payloads_path.write_text(
        json.dumps(
            {
                "payloads": [
                    {
                        "runner_job_id": interface_doc["contracts"][0]["runner_job_id"],
                        "status": "completed",
                        "executed_by": "runner-worker-script",
                        "completed_at": "2026-03-21T11:05:00+00:00",
                        "message": "Runner stub completed",
                    }
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    normalize_proc = subprocess.run(
        [
            sys.executable,
            "scripts/normalize_external_runner_outcomes.py",
            "--interface-contracts-path",
            str(interface_dir / "adapter_runner_interface_contracts.json"),
            "--payloads-path",
            str(payloads_path),
            "--out-dir",
            str(normalized_dir),
            "--actor-id",
            "collector-script-8",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert normalize_proc.returncode == 0, normalize_proc.stderr
    outcomes_path = normalized_dir / "normalized_external_runner_outcomes.json"
    review_queue_path = normalized_dir / "collector_normalization_review_queue.json"
    rollup_path = normalized_dir / "collector_normalization_rollup.json"
    assert outcomes_path.exists()
    assert review_queue_path.exists()
    assert rollup_path.exists()

    outcomes_doc = json.loads(outcomes_path.read_text(encoding="utf-8"))
    review_queue = json.loads(review_queue_path.read_text(encoding="utf-8"))
    rollup = json.loads(rollup_path.read_text(encoding="utf-8"))
    assert outcomes_doc["outcome_count"] == 1
    assert outcomes_doc["outcomes"][0]["outcome_status"] == "success"
    assert review_queue["item_count"] == 0
    assert rollup["outcome_status_counts"]["success"] == 1


def test_build_target_family_runner_stub_artifacts_creates_concrete_stub():
    interface_contracts = build_sample_runner_interface_contracts_doc()
    stubs_doc, review_queue, rollup = build_target_family_runner_stub_artifacts(interface_contracts, sample_target_family_catalog())

    assert stubs_doc["schema_version"] == TARGET_FAMILY_RUNNER_STUBS_SCHEMA_VERSION
    assert stubs_doc["stub_count"] == 1
    stub = stubs_doc["stubs"][0]
    assert stub["state"] == "stubbed"
    assert stub["target_family"]["target_family_key"] == "ops-core-ledger-family"
    assert stub["request_stub"]["template_kind"] == "ops-core-ledger-request-v1"
    assert review_queue["schema_version"] == TARGET_FAMILY_RUNNER_REVIEW_QUEUE_SCHEMA_VERSION
    assert review_queue["item_count"] == 0
    assert rollup["schema_version"] == TARGET_FAMILY_RUNNER_ROLLUP_SCHEMA_VERSION
    assert rollup["target_family_counts"]["ops-core-ledger-family"] == 1



def test_build_target_family_runner_stub_artifacts_queues_missing_family():
    interface_contracts = build_sample_runner_interface_contracts_doc()
    stubs_doc, review_queue, rollup = build_target_family_runner_stub_artifacts(interface_contracts, [])

    assert stubs_doc["stub_count"] == 0
    assert review_queue["item_count"] == 1
    assert "no_target_family_match" in review_queue["items"][0]["reason_codes"]
    assert rollup["review_queue_count"] == 1



def test_build_target_family_collector_fixture_artifacts_creates_family_fixtures():
    stubs_doc = build_sample_target_family_runner_stubs_doc()
    fixtures_doc, review_queue, rollup = build_target_family_collector_fixture_artifacts(stubs_doc)

    assert fixtures_doc["schema_version"] == TARGET_FAMILY_COLLECTOR_FIXTURES_SCHEMA_VERSION
    assert fixtures_doc["fixture_count"] == 4
    assert {item["outcome_status"] for item in fixtures_doc["fixtures"]} == {"success", "failure", "defer", "skip"}
    assert review_queue["schema_version"] == TARGET_FAMILY_COLLECTOR_REVIEW_QUEUE_SCHEMA_VERSION
    assert review_queue["item_count"] == 0
    assert rollup["schema_version"] == TARGET_FAMILY_COLLECTOR_ROLLUP_SCHEMA_VERSION
    assert rollup["outcome_status_counts"]["success"] == 1



def test_target_family_stub_and_fixture_scripts_write_expected_artifacts(tmp_path: Path):
    interface_contracts_path = tmp_path / "adapter_runner_interface_contracts.json"
    interface_contracts_path.write_text(
        json.dumps(build_sample_runner_interface_contracts_doc(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    target_family_catalog_path = tmp_path / "target_family_catalog.json"
    target_family_catalog_path.write_text(
        json.dumps({"target_families": sample_target_family_catalog()}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    stubs_dir = tmp_path / "target_family_stubs"
    fixtures_dir = tmp_path / "target_family_fixtures"

    stubs_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_target_family_runner_stubs.py",
            "--interface-contracts-path",
            str(interface_contracts_path),
            "--target-family-catalog-path",
            str(target_family_catalog_path),
            "--out-dir",
            str(stubs_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert stubs_proc.returncode == 0, stubs_proc.stderr

    fixtures_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_target_family_collector_fixtures.py",
            "--target-runner-stubs-path",
            str(stubs_dir / "target_family_runner_stubs.json"),
            "--out-dir",
            str(fixtures_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert fixtures_proc.returncode == 0, fixtures_proc.stderr

    stubs_doc = json.loads((stubs_dir / "target_family_runner_stubs.json").read_text(encoding="utf-8"))
    rollup = json.loads((fixtures_dir / "target_family_collector_fixture_rollup.json").read_text(encoding="utf-8"))
    assert stubs_doc["stub_count"] == 1
    assert rollup["outcome_status_counts"]["success"] == 1




def test_build_family_interface_template_artifacts_creates_concrete_template():
    stubs_doc = build_sample_target_family_runner_stubs_doc()
    templates_doc, review_queue, rollup = build_family_interface_template_artifacts(stubs_doc, sample_family_interface_template_catalog())

    assert templates_doc["schema_version"] == FAMILY_INTERFACE_TEMPLATES_SCHEMA_VERSION
    assert templates_doc["template_count"] == 1
    template_doc = templates_doc["templates"][0]
    assert template_doc["template"]["family_template_key"] == "ops-core-ledger-template"
    assert template_doc["template"]["raw_payload_kind"] == "ops-core-ledger-raw-payload-v1"
    assert review_queue["schema_version"] == FAMILY_INTERFACE_TEMPLATE_REVIEW_QUEUE_SCHEMA_VERSION
    assert review_queue["item_count"] == 0
    assert rollup["schema_version"] == FAMILY_INTERFACE_TEMPLATE_ROLLUP_SCHEMA_VERSION
    assert rollup["template_family_counts"]["ops-core-ledger-template-family"] == 1



def test_build_family_interface_template_artifacts_queues_missing_template():
    stubs_doc = build_sample_target_family_runner_stubs_doc()
    templates_doc, review_queue, rollup = build_family_interface_template_artifacts(stubs_doc, [])

    assert templates_doc["template_count"] == 0
    assert review_queue["item_count"] == 1
    assert "no_family_interface_template_match" in review_queue["items"][0]["reason_codes"]
    assert rollup["review_queue_count"] == 1



def test_build_canonical_raw_payload_contract_artifacts_creates_contract():
    templates_doc = build_sample_family_interface_templates_doc()
    contracts_doc, review_queue, rollup = build_canonical_raw_payload_contract_artifacts(templates_doc)

    assert contracts_doc["schema_version"] == CANONICAL_RAW_PAYLOAD_CONTRACTS_SCHEMA_VERSION
    assert contracts_doc["contract_count"] == 1
    contract_doc = contracts_doc["contracts"][0]
    assert contract_doc["raw_payload_contract"]["raw_payload_kind"] == "ops-core-ledger-raw-payload-v1"
    assert "success" in contract_doc["raw_payload_contract"]["accepted_canonical_statuses"]
    assert review_queue["schema_version"] == CANONICAL_RAW_PAYLOAD_REVIEW_QUEUE_SCHEMA_VERSION
    assert review_queue["item_count"] == 0
    assert rollup["schema_version"] == CANONICAL_RAW_PAYLOAD_ROLLUP_SCHEMA_VERSION
    assert rollup["raw_payload_kind_counts"]["ops-core-ledger-raw-payload-v1"] == 1



def test_family_interface_template_and_raw_payload_scripts_write_expected_artifacts(tmp_path: Path):
    stubs_path = tmp_path / "target_family_runner_stubs.json"
    stubs_path.write_text(
        json.dumps(build_sample_target_family_runner_stubs_doc(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    catalog_path = tmp_path / "family_interface_catalog.json"
    catalog_path.write_text(
        json.dumps({"family_interface_templates": sample_family_interface_template_catalog()}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    templates_dir = tmp_path / "family_templates"
    contracts_dir = tmp_path / "raw_payload_contracts"

    templates_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_family_interface_templates.py",
            "--target-runner-stubs-path",
            str(stubs_path),
            "--family-interface-catalog-path",
            str(catalog_path),
            "--out-dir",
            str(templates_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert templates_proc.returncode == 0, templates_proc.stderr

    contracts_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_canonical_raw_payload_contracts.py",
            "--family-interface-templates-path",
            str(templates_dir / "family_interface_templates.json"),
            "--out-dir",
            str(contracts_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert contracts_proc.returncode == 0, contracts_proc.stderr

    templates_doc = json.loads((templates_dir / "family_interface_templates.json").read_text(encoding="utf-8"))
    rollup = json.loads((contracts_dir / "canonical_raw_payload_rollup.json").read_text(encoding="utf-8"))
    assert templates_doc["template_count"] == 1
    assert rollup["raw_payload_kind_counts"]["ops-core-ledger-raw-payload-v1"] == 1


def test_build_target_group_adapter_package_artifacts_creates_package():
    templates_doc = build_sample_family_interface_templates_doc()
    contracts_doc = build_sample_canonical_raw_payload_contracts_doc()
    packages_doc, review_queue, rollup = build_target_group_adapter_package_artifacts(templates_doc, contracts_doc, sample_target_group_catalog())

    assert packages_doc["schema_version"] == TARGET_GROUP_ADAPTER_PACKAGES_SCHEMA_VERSION
    assert packages_doc["package_count"] == 1
    package = packages_doc["packages"][0]
    assert package["state"] == "packaged"
    assert package["target_group"]["target_group_key"] == "ops-core-ledger-group"
    assert package["package_scaffold"]["request_template"]["template_kind"] == "ops-core-ledger-request-fixture-v1"
    assert review_queue["schema_version"] == TARGET_GROUP_ADAPTER_PACKAGE_REVIEW_QUEUE_SCHEMA_VERSION
    assert review_queue["item_count"] == 0
    assert rollup["schema_version"] == TARGET_GROUP_ADAPTER_PACKAGE_ROLLUP_SCHEMA_VERSION
    assert rollup["target_group_counts"]["ops-core-ledger-group"] == 1



def test_build_target_group_adapter_package_artifacts_queues_missing_target_group():
    templates_doc = build_sample_family_interface_templates_doc()
    contracts_doc = build_sample_canonical_raw_payload_contracts_doc()
    packages_doc, review_queue, rollup = build_target_group_adapter_package_artifacts(templates_doc, contracts_doc, [])

    assert packages_doc["package_count"] == 0
    assert review_queue["item_count"] == 1
    assert "no_target_group_match" in review_queue["items"][0]["reason_codes"]
    assert rollup["review_queue_count"] == 1



def build_sample_target_group_packages_doc() -> dict:
    templates_doc = build_sample_family_interface_templates_doc()
    contracts_doc = build_sample_canonical_raw_payload_contracts_doc()
    packages_doc, review_queue, _ = build_target_group_adapter_package_artifacts(templates_doc, contracts_doc, sample_target_group_catalog())
    assert review_queue["item_count"] == 0
    assert packages_doc["package_count"] == 1
    return packages_doc



def test_build_canonical_request_response_fixture_pack_artifacts_creates_pack():
    packages_doc = build_sample_target_group_packages_doc()
    packs_doc, review_queue, rollup = build_canonical_request_response_fixture_pack_artifacts(packages_doc)

    assert packs_doc["schema_version"] == CANONICAL_REQUEST_RESPONSE_FIXTURE_PACKS_SCHEMA_VERSION
    assert packs_doc["pack_count"] == 1
    pack = packs_doc["packs"][0]
    assert len(pack["request_fixtures"]) == 4
    assert {item["fixture_mode"] for item in pack["request_fixtures"]} == {"success", "failure", "defer", "skip"}
    assert review_queue["schema_version"] == CANONICAL_REQUEST_RESPONSE_FIXTURE_REVIEW_QUEUE_SCHEMA_VERSION
    assert review_queue["item_count"] == 0
    assert rollup["schema_version"] == CANONICAL_REQUEST_RESPONSE_FIXTURE_ROLLUP_SCHEMA_VERSION
    assert rollup["fixture_mode_counts"]["success"] == 1



def test_target_group_package_and_fixture_scripts_write_expected_artifacts(tmp_path: Path):
    templates_path = tmp_path / "family_interface_templates.json"
    templates_path.write_text(
        json.dumps(build_sample_family_interface_templates_doc(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    contracts_path = tmp_path / "canonical_raw_payload_contracts.json"
    contracts_path.write_text(
        json.dumps(build_sample_canonical_raw_payload_contracts_doc(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    target_group_catalog_path = tmp_path / "target_group_catalog.json"
    target_group_catalog_path.write_text(
        json.dumps({"target_groups": sample_target_group_catalog()}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    packages_dir = tmp_path / "target_group_packages"
    packs_dir = tmp_path / "request_response_fixtures"

    packages_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_target_group_adapter_packages.py",
            "--family-interface-templates-path",
            str(templates_path),
            "--raw-payload-contracts-path",
            str(contracts_path),
            "--target-group-catalog-path",
            str(target_group_catalog_path),
            "--out-dir",
            str(packages_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert packages_proc.returncode == 0, packages_proc.stderr

    packs_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_canonical_request_response_fixture_packs.py",
            "--target-group-packages-path",
            str(packages_dir / "target_group_adapter_packages.json"),
            "--out-dir",
            str(packs_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert packs_proc.returncode == 0, packs_proc.stderr

    packages_doc = json.loads((packages_dir / "target_group_adapter_packages.json").read_text(encoding="utf-8"))
    rollup = json.loads((packs_dir / "canonical_request_response_fixture_rollup.json").read_text(encoding="utf-8"))
    assert packages_doc["package_count"] == 1
    assert rollup["fixture_mode_counts"]["success"] == 1


def build_sample_target_group_adapter_skeletons_doc() -> dict:
    packages_doc = build_sample_target_group_packages_doc()
    fixture_packs_doc, review_queue, _ = build_canonical_request_response_fixture_pack_artifacts(packages_doc)
    assert review_queue["item_count"] == 0
    skeletons_doc, skeleton_review_queue, _ = build_target_group_adapter_skeleton_artifacts(packages_doc, fixture_packs_doc, sample_target_group_adapter_skeleton_catalog())
    assert skeleton_review_queue["item_count"] == 0
    assert skeletons_doc["skeleton_count"] == 1
    return skeletons_doc



def test_build_target_group_adapter_skeleton_artifacts_creates_skeleton():
    packages_doc = build_sample_target_group_packages_doc()
    fixture_packs_doc, fixture_review_queue, _ = build_canonical_request_response_fixture_pack_artifacts(packages_doc)
    assert fixture_review_queue["item_count"] == 0
    skeletons_doc, review_queue, rollup = build_target_group_adapter_skeleton_artifacts(packages_doc, fixture_packs_doc, sample_target_group_adapter_skeleton_catalog())

    assert skeletons_doc["schema_version"] == TARGET_GROUP_ADAPTER_SKELETONS_SCHEMA_VERSION
    assert skeletons_doc["skeleton_count"] == 1
    skeleton = skeletons_doc["skeletons"][0]
    assert skeleton["state"] == "skeletonized"
    assert skeleton["adapter_group"]["adapter_group_key"] == "ops-core-ledger-adapter-group"
    assert skeleton["request_skeleton"]["request_method"] == "POST"
    assert review_queue["schema_version"] == TARGET_GROUP_ADAPTER_SKELETON_REVIEW_QUEUE_SCHEMA_VERSION
    assert review_queue["item_count"] == 0
    assert rollup["schema_version"] == TARGET_GROUP_ADAPTER_SKELETON_ROLLUP_SCHEMA_VERSION
    assert rollup["adapter_group_counts"]["ops-core-ledger-adapter-group"] == 1



def test_build_target_group_adapter_skeleton_artifacts_queues_missing_catalog_match():
    packages_doc = build_sample_target_group_packages_doc()
    fixture_packs_doc, fixture_review_queue, _ = build_canonical_request_response_fixture_pack_artifacts(packages_doc)
    assert fixture_review_queue["item_count"] == 0
    skeletons_doc, review_queue, rollup = build_target_group_adapter_skeleton_artifacts(packages_doc, fixture_packs_doc, [])

    assert skeletons_doc["skeleton_count"] == 0
    assert review_queue["item_count"] == 1
    assert "no_target_group_skeleton_match" in review_queue["items"][0]["reason_codes"]
    assert rollup["review_queue_count"] == 1



def test_build_roundtrip_normalization_case_artifacts_creates_cases():
    packages_doc = build_sample_target_group_packages_doc()
    fixture_packs_doc, fixture_review_queue, _ = build_canonical_request_response_fixture_pack_artifacts(packages_doc)
    assert fixture_review_queue["item_count"] == 0
    skeletons_doc, skeleton_review_queue, _ = build_target_group_adapter_skeleton_artifacts(packages_doc, fixture_packs_doc, sample_target_group_adapter_skeleton_catalog())
    assert skeleton_review_queue["item_count"] == 0

    cases_doc, review_queue, rollup = build_roundtrip_normalization_case_artifacts(skeletons_doc, fixture_packs_doc)

    assert cases_doc["schema_version"] == ROUNDTRIP_NORMALIZATION_CASES_SCHEMA_VERSION
    assert cases_doc["case_count"] == 4
    case = cases_doc["cases"][0]
    assert case["raw_request_payload"]["request_method"] == "POST"
    assert case["expected_normalized_result"]["outcome_status"] in {"success", "failure", "defer", "skip"}
    assert review_queue["schema_version"] == ROUNDTRIP_NORMALIZATION_REVIEW_QUEUE_SCHEMA_VERSION
    assert review_queue["item_count"] == 0
    assert rollup["schema_version"] == ROUNDTRIP_NORMALIZATION_ROLLUP_SCHEMA_VERSION
    assert rollup["fixture_mode_counts"]["success"] == 1



def test_target_group_skeleton_and_roundtrip_scripts_write_expected_artifacts(tmp_path: Path):
    packages_path = tmp_path / "target_group_adapter_packages.json"
    packages_path.write_text(
        json.dumps(build_sample_target_group_packages_doc(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    fixture_packs_path = tmp_path / "canonical_request_response_fixture_packs.json"
    fixture_packs_doc, fixture_review_queue, _ = build_canonical_request_response_fixture_pack_artifacts(build_sample_target_group_packages_doc())
    assert fixture_review_queue["item_count"] == 0
    fixture_packs_path.write_text(
        json.dumps(fixture_packs_doc, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    skeleton_catalog_path = tmp_path / "target_group_adapter_skeleton_catalog.json"
    skeleton_catalog_path.write_text(
        json.dumps({"target_group_adapter_skeletons": sample_target_group_adapter_skeleton_catalog()}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    skeletons_dir = tmp_path / "target_group_skeletons"
    roundtrip_dir = tmp_path / "roundtrip_cases"

    skeletons_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_target_group_adapter_skeletons.py",
            "--target-group-packages-path",
            str(packages_path),
            "--request-response-fixture-packs-path",
            str(fixture_packs_path),
            "--target-group-skeleton-catalog-path",
            str(skeleton_catalog_path),
            "--out-dir",
            str(skeletons_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert skeletons_proc.returncode == 0, skeletons_proc.stderr

    roundtrip_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_roundtrip_normalization_cases.py",
            "--target-group-adapter-skeletons-path",
            str(skeletons_dir / "target_group_adapter_skeletons.json"),
            "--request-response-fixture-packs-path",
            str(fixture_packs_path),
            "--out-dir",
            str(roundtrip_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert roundtrip_proc.returncode == 0, roundtrip_proc.stderr

    skeletons_doc = json.loads((skeletons_dir / "target_group_adapter_skeletons.json").read_text(encoding="utf-8"))
    rollup = json.loads((roundtrip_dir / "roundtrip_normalization_rollup.json").read_text(encoding="utf-8"))
    assert skeletons_doc["skeleton_count"] == 1
    assert rollup["fixture_mode_counts"]["success"] == 1



def build_sample_target_group_adapter_implementation_shells_doc() -> dict:
    skeletons_doc = build_sample_target_group_adapter_skeletons_doc()
    packages_doc = build_sample_target_group_packages_doc()
    fixture_packs_doc, fixture_review_queue, _ = build_canonical_request_response_fixture_pack_artifacts(packages_doc)
    assert fixture_review_queue["item_count"] == 0
    cases_doc, case_review_queue, _ = build_roundtrip_normalization_case_artifacts(skeletons_doc, fixture_packs_doc)
    assert case_review_queue["item_count"] == 0
    shells_doc, shell_review_queue, _ = build_target_group_adapter_implementation_shell_artifacts(
        skeletons_doc,
        cases_doc,
        sample_target_group_adapter_implementation_catalog(),
    )
    assert shell_review_queue["item_count"] == 0
    assert shells_doc["shell_count"] == 1
    return shells_doc


def test_build_target_group_adapter_implementation_shell_artifacts_creates_shell():
    skeletons_doc = build_sample_target_group_adapter_skeletons_doc()
    packages_doc = build_sample_target_group_packages_doc()
    fixture_packs_doc, fixture_review_queue, _ = build_canonical_request_response_fixture_pack_artifacts(packages_doc)
    assert fixture_review_queue["item_count"] == 0
    cases_doc, case_review_queue, _ = build_roundtrip_normalization_case_artifacts(skeletons_doc, fixture_packs_doc)
    assert case_review_queue["item_count"] == 0

    shells_doc, review_queue, rollup = build_target_group_adapter_implementation_shell_artifacts(
        skeletons_doc,
        cases_doc,
        sample_target_group_adapter_implementation_catalog(),
    )

    assert shells_doc["schema_version"] == TARGET_GROUP_ADAPTER_IMPLEMENTATION_SHELLS_SCHEMA_VERSION
    assert shells_doc["shell_count"] == 1
    shell = shells_doc["shells"][0]
    assert shell["state"] == "implementation-shelled"
    assert shell["implementation_group"]["implementation_group_key"] == "ops-core-ledger-implementation-group"
    assert shell["adapter_entrypoint"]["module"] == "start_here_extractor.adapters.ops_core_ledger"
    assert review_queue["schema_version"] == TARGET_GROUP_ADAPTER_IMPLEMENTATION_SHELL_REVIEW_QUEUE_SCHEMA_VERSION
    assert review_queue["item_count"] == 0
    assert rollup["schema_version"] == TARGET_GROUP_ADAPTER_IMPLEMENTATION_SHELL_ROLLUP_SCHEMA_VERSION
    assert rollup["implementation_group_counts"]["ops-core-ledger-implementation-group"] == 1


def test_build_end_to_end_roundtrip_fixture_execution_pack_artifacts_creates_pack():
    shells_doc = build_sample_target_group_adapter_implementation_shells_doc()
    packages_doc = build_sample_target_group_packages_doc()
    fixture_packs_doc, fixture_review_queue, _ = build_canonical_request_response_fixture_pack_artifacts(packages_doc)
    assert fixture_review_queue["item_count"] == 0
    skeletons_doc = build_sample_target_group_adapter_skeletons_doc()
    cases_doc, case_review_queue, _ = build_roundtrip_normalization_case_artifacts(skeletons_doc, fixture_packs_doc)
    assert case_review_queue["item_count"] == 0

    packs_doc, review_queue, rollup = build_end_to_end_roundtrip_fixture_execution_pack_artifacts(shells_doc, cases_doc)

    assert packs_doc["schema_version"] == END_TO_END_ROUNDTRIP_FIXTURE_EXECUTION_PACKS_SCHEMA_VERSION
    assert packs_doc["pack_count"] == 1
    pack = packs_doc["packs"][0]
    assert len(pack["cases"]) == 4
    assert {item["fixture_mode"] for item in pack["cases"]} == {"success", "failure", "defer", "skip"}
    assert review_queue["schema_version"] == END_TO_END_ROUNDTRIP_FIXTURE_EXECUTION_REVIEW_QUEUE_SCHEMA_VERSION
    assert review_queue["item_count"] == 0
    assert rollup["schema_version"] == END_TO_END_ROUNDTRIP_FIXTURE_EXECUTION_ROLLUP_SCHEMA_VERSION
    assert rollup["fixture_mode_counts"]["success"] == 1


def test_target_group_implementation_shell_and_execution_pack_scripts_write_expected_artifacts(tmp_path: Path):
    packages_doc = build_sample_target_group_packages_doc()
    fixture_packs_doc, fixture_review_queue, _ = build_canonical_request_response_fixture_pack_artifacts(packages_doc)
    assert fixture_review_queue["item_count"] == 0
    skeletons_doc, skeleton_review_queue, _ = build_target_group_adapter_skeleton_artifacts(packages_doc, fixture_packs_doc, sample_target_group_adapter_skeleton_catalog())
    assert skeleton_review_queue["item_count"] == 0
    cases_doc, case_review_queue, _ = build_roundtrip_normalization_case_artifacts(skeletons_doc, fixture_packs_doc)
    assert case_review_queue["item_count"] == 0

    skeletons_path = tmp_path / "target_group_adapter_skeletons.json"
    skeletons_path.write_text(json.dumps(skeletons_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    cases_path = tmp_path / "roundtrip_normalization_cases.json"
    cases_path.write_text(json.dumps(cases_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    catalog_path = tmp_path / "target_group_adapter_implementation_catalog.json"
    catalog_path.write_text(json.dumps({"target_group_adapter_implementations": sample_target_group_adapter_implementation_catalog()}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    shells_dir = tmp_path / "implementation_shells"
    packs_dir = tmp_path / "execution_packs"

    shells_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_target_group_adapter_implementation_shells.py",
            "--target-group-adapter-skeletons-path",
            str(skeletons_path),
            "--roundtrip-normalization-cases-path",
            str(cases_path),
            "--target-group-implementation-catalog-path",
            str(catalog_path),
            "--out-dir",
            str(shells_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert shells_proc.returncode == 0, shells_proc.stderr

    packs_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_end_to_end_roundtrip_fixture_execution_packs.py",
            "--target-group-adapter-implementation-shells-path",
            str(shells_dir / "target_group_adapter_implementation_shells.json"),
            "--roundtrip-normalization-cases-path",
            str(cases_path),
            "--out-dir",
            str(packs_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert packs_proc.returncode == 0, packs_proc.stderr

    shells_doc = json.loads((shells_dir / "target_group_adapter_implementation_shells.json").read_text(encoding="utf-8"))
    rollup = json.loads((packs_dir / "end_to_end_roundtrip_fixture_execution_rollup.json").read_text(encoding="utf-8"))
    assert shells_doc["shell_count"] == 1
    assert rollup["fixture_mode_counts"]["success"] == 1



def build_sample_target_group_adapter_execution_harnesses_doc() -> dict:
    shells_doc = build_sample_target_group_adapter_implementation_shells_doc()
    packages_doc = build_sample_target_group_packages_doc()
    fixture_packs_doc, fixture_review_queue, _ = build_canonical_request_response_fixture_pack_artifacts(packages_doc)
    assert fixture_review_queue["item_count"] == 0
    skeletons_doc = build_sample_target_group_adapter_skeletons_doc()
    cases_doc, case_review_queue, _ = build_roundtrip_normalization_case_artifacts(skeletons_doc, fixture_packs_doc)
    assert case_review_queue["item_count"] == 0
    execution_packs_doc, execution_pack_review_queue, _ = build_end_to_end_roundtrip_fixture_execution_pack_artifacts(shells_doc, cases_doc)
    assert execution_pack_review_queue["item_count"] == 0
    harnesses_doc, harness_review_queue, _ = build_target_group_adapter_execution_harness_artifacts(
        shells_doc,
        execution_packs_doc,
        sample_target_group_execution_harness_catalog(),
    )
    assert harness_review_queue["item_count"] == 0
    assert harnesses_doc["harness_count"] == 1
    return harnesses_doc


def test_build_target_group_adapter_execution_harness_artifacts_creates_harness():
    shells_doc = build_sample_target_group_adapter_implementation_shells_doc()
    packages_doc = build_sample_target_group_packages_doc()
    fixture_packs_doc, fixture_review_queue, _ = build_canonical_request_response_fixture_pack_artifacts(packages_doc)
    assert fixture_review_queue["item_count"] == 0
    skeletons_doc = build_sample_target_group_adapter_skeletons_doc()
    cases_doc, case_review_queue, _ = build_roundtrip_normalization_case_artifacts(skeletons_doc, fixture_packs_doc)
    assert case_review_queue["item_count"] == 0
    execution_packs_doc, execution_pack_review_queue, _ = build_end_to_end_roundtrip_fixture_execution_pack_artifacts(shells_doc, cases_doc)
    assert execution_pack_review_queue["item_count"] == 0

    harnesses_doc, review_queue, rollup = build_target_group_adapter_execution_harness_artifacts(
        shells_doc,
        execution_packs_doc,
        sample_target_group_execution_harness_catalog(),
    )

    assert harnesses_doc["schema_version"] == TARGET_GROUP_ADAPTER_EXECUTION_HARNESSES_SCHEMA_VERSION
    assert harnesses_doc["harness_count"] == 1
    harness = harnesses_doc["harnesses"][0]
    assert harness["state"] == "execution-harnessed"
    assert harness["harness_group"]["harness_group_key"] == "ops-core-ledger-harness-group"
    assert harness["execution_context"]["network_mode"] == "offline"
    assert review_queue["schema_version"] == TARGET_GROUP_ADAPTER_EXECUTION_HARNESS_REVIEW_QUEUE_SCHEMA_VERSION
    assert review_queue["item_count"] == 0
    assert rollup["schema_version"] == TARGET_GROUP_ADAPTER_EXECUTION_HARNESS_ROLLUP_SCHEMA_VERSION
    assert rollup["harness_group_counts"]["ops-core-ledger-harness-group"] == 1
    assert rollup["fixture_mode_counts"]["success"] == 1


def test_build_replayable_dry_run_orchestration_pack_artifacts_creates_pack():
    harnesses_doc = build_sample_target_group_adapter_execution_harnesses_doc()
    shells_doc = build_sample_target_group_adapter_implementation_shells_doc()
    packages_doc = build_sample_target_group_packages_doc()
    fixture_packs_doc, fixture_review_queue, _ = build_canonical_request_response_fixture_pack_artifacts(packages_doc)
    assert fixture_review_queue["item_count"] == 0
    skeletons_doc = build_sample_target_group_adapter_skeletons_doc()
    cases_doc, case_review_queue, _ = build_roundtrip_normalization_case_artifacts(skeletons_doc, fixture_packs_doc)
    assert case_review_queue["item_count"] == 0
    execution_packs_doc, execution_pack_review_queue, _ = build_end_to_end_roundtrip_fixture_execution_pack_artifacts(shells_doc, cases_doc)
    assert execution_pack_review_queue["item_count"] == 0

    packs_doc, review_queue, rollup = build_replayable_dry_run_orchestration_pack_artifacts(harnesses_doc, execution_packs_doc)

    assert packs_doc["schema_version"] == REPLAYABLE_DRY_RUN_ORCHESTRATION_PACKS_SCHEMA_VERSION
    assert packs_doc["pack_count"] == 1
    pack = packs_doc["packs"][0]
    assert len(pack["steps"]) == 4
    assert {item["fixture_mode"] for item in pack["steps"]} == {"success", "failure", "defer", "skip"}
    assert review_queue["schema_version"] == REPLAYABLE_DRY_RUN_ORCHESTRATION_REVIEW_QUEUE_SCHEMA_VERSION
    assert review_queue["item_count"] == 0
    assert rollup["schema_version"] == REPLAYABLE_DRY_RUN_ORCHESTRATION_ROLLUP_SCHEMA_VERSION
    assert rollup["fixture_mode_counts"]["success"] == 1


def test_target_group_execution_harness_and_replayable_dry_run_scripts_write_expected_artifacts(tmp_path: Path):
    packages_doc = build_sample_target_group_packages_doc()
    fixture_packs_doc, fixture_review_queue, _ = build_canonical_request_response_fixture_pack_artifacts(packages_doc)
    assert fixture_review_queue["item_count"] == 0
    skeletons_doc, skeleton_review_queue, _ = build_target_group_adapter_skeleton_artifacts(packages_doc, fixture_packs_doc, sample_target_group_adapter_skeleton_catalog())
    assert skeleton_review_queue["item_count"] == 0
    cases_doc, case_review_queue, _ = build_roundtrip_normalization_case_artifacts(skeletons_doc, fixture_packs_doc)
    assert case_review_queue["item_count"] == 0
    shells_doc, shell_review_queue, _ = build_target_group_adapter_implementation_shell_artifacts(
        skeletons_doc,
        cases_doc,
        sample_target_group_adapter_implementation_catalog(),
    )
    assert shell_review_queue["item_count"] == 0
    execution_packs_doc, execution_pack_review_queue, _ = build_end_to_end_roundtrip_fixture_execution_pack_artifacts(shells_doc, cases_doc)
    assert execution_pack_review_queue["item_count"] == 0

    shells_path = tmp_path / "target_group_adapter_implementation_shells.json"
    shells_path.write_text(json.dumps(shells_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    execution_packs_path = tmp_path / "end_to_end_roundtrip_fixture_execution_packs.json"
    execution_packs_path.write_text(json.dumps(execution_packs_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    catalog_path = tmp_path / "target_group_execution_harness_catalog.json"
    catalog_path.write_text(json.dumps({"target_group_execution_harnesses": sample_target_group_execution_harness_catalog()}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    harnesses_dir = tmp_path / "execution_harnesses"
    orchestration_dir = tmp_path / "orchestration_packs"

    harness_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_target_group_adapter_execution_harnesses.py",
            "--target-group-adapter-implementation-shells-path",
            str(shells_path),
            "--end-to-end-roundtrip-fixture-execution-packs-path",
            str(execution_packs_path),
            "--target-group-execution-harness-catalog-path",
            str(catalog_path),
            "--out-dir",
            str(harnesses_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert harness_proc.returncode == 0, harness_proc.stderr

    orchestration_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_replayable_dry_run_orchestration_packs.py",
            "--target-group-adapter-execution-harnesses-path",
            str(harnesses_dir / "target_group_adapter_execution_harnesses.json"),
            "--end-to-end-roundtrip-fixture-execution-packs-path",
            str(execution_packs_path),
            "--out-dir",
            str(orchestration_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert orchestration_proc.returncode == 0, orchestration_proc.stderr

    harnesses_doc = json.loads((harnesses_dir / "target_group_adapter_execution_harnesses.json").read_text(encoding="utf-8"))
    rollup = json.loads((orchestration_dir / "replayable_dry_run_orchestration_rollup.json").read_text(encoding="utf-8"))
    assert harnesses_doc["harness_count"] == 1
    assert rollup["fixture_mode_counts"]["success"] == 1

