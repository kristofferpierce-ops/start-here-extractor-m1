from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
from start_here_extractor.source_control_pipeline import (
    SOURCE_CONTROL_PIPELINE_SCHEMA_VERSION,
    build_source_control_pipeline_artifacts,
)
from start_here_extractor.ringcentral_lacrm_migration import (
    RINGCENTRAL_LACRM_MIGRATION_SCHEMA_VERSION,
    build_ringcentral_lacrm_migration_artifacts,
)
from start_here_extractor.durable_lineage_replay import (
    DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION,
    build_durable_lineage_artifacts,
    build_lineage_replay_readiness_artifacts,
    build_replay_safe_ingestion_control_artifacts,
)
from start_here_extractor.source_replay_plans import (
    SOURCE_REPLAY_PLAN_SCHEMA_VERSION,
    build_source_replay_plan_artifacts,
)
from start_here_extractor.source_replay_compare import (
    SOURCE_REPLAY_COMPARE_SCHEMA_VERSION,
    build_source_replay_compare_artifacts,
)
from start_here_extractor.source_replay_approval import (
    SOURCE_REPLAY_APPROVAL_SCHEMA_VERSION,
    build_source_replay_approval_artifacts,
)
from start_here_extractor.source_replay_execution import (
    SOURCE_REPLAY_EXECUTION_SCHEMA_VERSION,
    build_source_replay_execution_artifacts,
)
from start_here_extractor.operator_console_alpha import (
    build_operator_console_alpha_artifacts,
)

def sample_ingestion_records() -> list[dict]:
    return [
        {
            "event_id": "ingest-001",
            "emitted_at": "2026-03-21T00:00:00+00:00",
            "source": {
                "source_type": "gdrive",
                "source_system": "gdrive",
                "source_entity_type": "evidence-artifact",
                "source_record_id": "file-001",
                "content_family": "start-here-evidence",
            },
            "pipeline": {
                "raw": {"status": "captured", "captured_at": "2026-03-21T00:00:00+00:00", "ref": "ingestion://one"},
                "normalized": {"status": "normalized", "normalized_at": "2026-03-21T00:00:00+00:00", "ref": "inventory://one"},
                "matched": {"status": "pending"},
                "approved": {"status": "pending"},
                "applied": {"status": "pending"},
            },
            "relationship_memory": {
                "candidates": [
                    {"entity_type": "contact", "entity_id": "contact-1", "confidence": 0.82, "reason": "same remote id"}
                ]
            },
            "governance": {"review_required": True},
            "evidence": {"zip_sha256": "abc", "start_here": "notes"},
            "warnings": [],
        },
        {
            "event_id": "ingest-002",
            "emitted_at": "2026-03-21T01:00:00+00:00",
            "source": {
                "source_type": "lacrm",
                "source_system": "lacrm",
                "source_entity_type": "crm-contact",
                "source_record_id": "contact-002",
                "content_family": "operating-core-event",
            },
            "pipeline": {
                "raw": {"status": "captured", "captured_at": "2026-03-21T01:00:00+00:00", "ref": "ingestion://two"},
                "normalized": {"status": "normalized", "normalized_at": "2026-03-21T01:00:00+00:00", "ref": "inventory://two"},
                "matched": {"status": "matched", "entity_type": "contact", "entity_id": "contact-002"},
                "approved": {"status": "approved", "approved_at": "2026-03-21T01:05:00+00:00", "approved_by": "operator-1", "reason": "validated"},
                "applied": {"status": "applied", "applied_at": "2026-03-21T01:10:00+00:00", "applied_ref": "lacrm://contact/002", "target_type": "crm-contact", "target_id": "contact-002"},
            },
            "relationship_memory": {"candidates": []},
            "governance": {"review_required": False},
            "evidence": {"zip_sha256": "def", "start_here": "summary"},
            "warnings": [],
        },
    ]
def test_build_source_control_pipeline_artifacts_counts() -> None:
    artifacts = build_source_control_pipeline_artifacts(sample_ingestion_records())
    assert artifacts["source_records_raw"]["record_count"] == 2
    assert artifacts["source_records_normalized"]["record_count"] == 2
    assert artifacts["candidate_matches"]["record_count"] == 1
    assert artifacts["review_items"]["record_count"] == 1
    assert artifacts["approved_deltas"]["record_count"] == 1
    assert artifacts["applied_state_transitions"]["record_count"] == 1
    assert artifacts["rollup"]["schema_version"] == SOURCE_CONTROL_PIPELINE_SCHEMA_VERSION
def test_source_control_pipeline_script_writes_expected_artifacts(tmp_path: Path) -> None:
    ingestion_path = tmp_path / "ingestion-events.jsonl"
    with ingestion_path.open("w", encoding="utf-8") as handle:
        for record in sample_ingestion_records():
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    out_dir = tmp_path / "out"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_source_control_pipeline.py",
            "--ingestion-path",
            str(ingestion_path),
            "--out-dir",
            str(out_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    rollup = json.loads((out_dir / "source_control_pipeline_rollup.json").read_text(encoding="utf-8"))
    assert rollup["approved_delta_count"] == 1
    assert rollup["review_item_count"] == 1
def sample_m6b_ingestion_records() -> list[dict]:
    return [
        {
            "event_id": "rc-001",
            "emitted_at": "2026-03-21T02:00:00+00:00",
            "source": {
                "source_type": "ringcentral",
                "source_system": "ringcentral",
                "source_entity_type": "call-log",
                "source_record_id": "call-001",
                "content_family": "communication-event",
            },
            "pipeline": {
                "raw": {"status": "captured", "captured_at": "2026-03-21T02:00:00+00:00", "ref": "ingestion://rc-001"},
                "normalized": {"status": "normalized", "normalized_at": "2026-03-21T02:01:00+00:00", "ref": "inventory://rc-001"},
                "matched": {"status": "pending"},
                "approved": {"status": "pending"},
                "applied": {"status": "pending"},
            },
            "relationship_memory": {
                "candidates": [
                    {"entity_type": "contact", "entity_id": "contact-rc-1", "confidence": 0.74, "reason": "same caller id"}
                ]
            },
            "governance": {"review_required": True},
            "evidence": {"zip_sha256": "ringcentralsha", "start_here": "Call transcript"},
            "warnings": [],
        },
        {
            "event_id": "lacrm-001",
            "emitted_at": "2026-03-21T03:00:00+00:00",
            "source": {
                "source_type": "lacrm",
                "source_system": "lacrm",
                "source_entity_type": "crm-contact",
                "source_record_id": "contact-123",
                "content_family": "operating-core-event",
            },
            "pipeline": {
                "raw": {"status": "captured", "captured_at": "2026-03-21T03:00:00+00:00", "ref": "ingestion://lacrm-001"},
                "normalized": {"status": "normalized", "normalized_at": "2026-03-21T03:01:00+00:00", "ref": "inventory://lacrm-001"},
                "matched": {"status": "matched", "entity_type": "contact", "entity_id": "contact-123"},
                "approved": {"status": "approved", "approved_at": "2026-03-21T03:05:00+00:00", "approved_by": "operator-2", "reason": "crm validated"},
                "applied": {"status": "applied", "applied_at": "2026-03-21T03:10:00+00:00", "applied_ref": "lacrm://contact/contact-123", "target_type": "crm-contact", "target_id": "contact-123"},
            },
            "relationship_memory": {"candidates": []},
            "governance": {"review_required": False},
            "evidence": {"zip_sha256": "lacrmsha", "start_here": "CRM contact export"},
            "warnings": [],
        },
        {
            "event_id": "gdrive-003",
            "emitted_at": "2026-03-21T04:00:00+00:00",
            "source": {
                "source_type": "gdrive",
                "source_system": "gdrive",
                "source_entity_type": "evidence-artifact",
                "source_record_id": "file-003",
                "content_family": "start-here-evidence",
            },
            "pipeline": {
                "raw": {"status": "captured", "captured_at": "2026-03-21T04:00:00+00:00", "ref": "ingestion://gdrive-003"},
                "normalized": {"status": "normalized", "normalized_at": "2026-03-21T04:01:00+00:00", "ref": "inventory://gdrive-003"},
                "matched": {"status": "pending"},
                "approved": {"status": "pending"},
                "applied": {"status": "pending"},
            },
            "relationship_memory": {"candidates": []},
            "governance": {"review_required": False},
            "evidence": {"zip_sha256": "other", "start_here": "Other"},
            "warnings": [],
        },
    ]
def test_build_ringcentral_lacrm_migration_artifacts_counts() -> None:
    pipeline = build_source_control_pipeline_artifacts(sample_m6b_ingestion_records())
    artifacts = build_ringcentral_lacrm_migration_artifacts(pipeline)
    assert artifacts["migration_packs"]["record_count"] == 2
    assert artifacts["migration_review_queue"]["record_count"] == 0
    assert artifacts["rollup"]["schema_version"] == RINGCENTRAL_LACRM_MIGRATION_SCHEMA_VERSION
    assert artifacts["rollup"]["source_system_counts"]["ringcentral"] == 1
    assert artifacts["rollup"]["source_system_counts"]["lacrm"] == 1
def test_ringcentral_lacrm_migration_script_writes_expected_artifacts(tmp_path: Path) -> None:
    ingestion_path = tmp_path / "ingestion-events.jsonl"
    with ingestion_path.open("w", encoding="utf-8") as handle:
        for record in sample_m6b_ingestion_records():
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    pipeline_dir = tmp_path / "pipeline"
    pipeline_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_source_control_pipeline.py",
            "--ingestion-path",
            str(ingestion_path),
            "--out-dir",
            str(pipeline_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert pipeline_proc.returncode == 0, pipeline_proc.stderr
    out_dir = tmp_path / "m6b"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_ringcentral_lacrm_migration_packs.py",
            "--pipeline-dir",
            str(pipeline_dir),
            "--out-dir",
            str(out_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    rollup = json.loads((out_dir / "ringcentral_lacrm_migration_rollup.json").read_text(encoding="utf-8"))
    packs = json.loads((out_dir / "ringcentral_lacrm_migration_packs.json").read_text(encoding="utf-8"))
    assert rollup["migration_pack_count"] == 2
    assert packs["record_count"] == 2
    readiness_states = {record["readiness_state"] for record in packs["records"]}
    assert readiness_states == {"blocked-review", "already-applied"}
def test_build_durable_lineage_artifacts_counts() -> None:
    pipeline = build_source_control_pipeline_artifacts(sample_m6b_ingestion_records())
    migration = build_ringcentral_lacrm_migration_artifacts(pipeline)
    artifacts = build_durable_lineage_artifacts(pipeline, migration)
    assert artifacts["durable_lineage_packs"]["record_count"] == 2
    assert artifacts["durable_lineage_review_queue"]["record_count"] == 0
    assert artifacts["durable_lineage_rollup"]["schema_version"] == DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION
def test_build_replay_safe_ingestion_control_artifacts_counts() -> None:
    pipeline = build_source_control_pipeline_artifacts(sample_m6b_ingestion_records())
    migration = build_ringcentral_lacrm_migration_artifacts(pipeline)
    lineage = build_durable_lineage_artifacts(pipeline, migration)
    artifacts = build_replay_safe_ingestion_control_artifacts(lineage, migration)
    assert artifacts["replay_safe_ingestion_controls"]["record_count"] == 2
    assert artifacts["replay_safe_ingestion_review_queue"]["record_count"] == 0
    assert artifacts["replay_safe_ingestion_rollup"]["schema_version"] == DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION
def test_build_lineage_replay_readiness_artifacts_counts() -> None:
    pipeline = build_source_control_pipeline_artifacts(sample_m6b_ingestion_records())
    migration = build_ringcentral_lacrm_migration_artifacts(pipeline)
    lineage = build_durable_lineage_artifacts(pipeline, migration)
    controls = build_replay_safe_ingestion_control_artifacts(lineage, migration)
    artifacts = build_lineage_replay_readiness_artifacts(lineage, controls, migration)
    assert artifacts["lineage_replay_readiness_packs"]["record_count"] == 2
    assert artifacts["lineage_replay_readiness_review_queue"]["record_count"] == 0
    assert artifacts["lineage_replay_readiness_rollup"]["schema_version"] == DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION
    states = {record["readiness_state"] for record in artifacts["lineage_replay_readiness_packs"]["records"]}
    assert states == {"blocked-review", "protected-ready"}
def test_durable_lineage_bundle_scripts_write_expected_artifacts(tmp_path: Path) -> None:
    ingestion_path = tmp_path / "ingestion-events.jsonl"
    with ingestion_path.open("w", encoding="utf-8") as handle:
        for record in sample_m6b_ingestion_records():
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    pipeline_dir = tmp_path / "pipeline"
    migration_dir = tmp_path / "migration"
    lineage_dir = tmp_path / "lineage"
    control_dir = tmp_path / "controls"
    readiness_dir = tmp_path / "readiness"
    pipeline_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_source_control_pipeline.py",
            "--ingestion-path",
            str(ingestion_path),
            "--out-dir",
            str(pipeline_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert pipeline_proc.returncode == 0, pipeline_proc.stderr
    migration_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_ringcentral_lacrm_migration_packs.py",
            "--pipeline-dir",
            str(pipeline_dir),
            "--out-dir",
            str(migration_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert migration_proc.returncode == 0, migration_proc.stderr
    lineage_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_durable_lineage_packs.py",
            "--pipeline-dir",
            str(pipeline_dir),
            "--migration-dir",
            str(migration_dir),
            "--out-dir",
            str(lineage_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert lineage_proc.returncode == 0, lineage_proc.stderr
    control_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_replay_safe_ingestion_controls.py",
            "--lineage-dir",
            str(lineage_dir),
            "--migration-dir",
            str(migration_dir),
            "--out-dir",
            str(control_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert control_proc.returncode == 0, control_proc.stderr
    readiness_proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_lineage_replay_readiness_packs.py",
            "--lineage-dir",
            str(lineage_dir),
            "--control-dir",
            str(control_dir),
            "--migration-dir",
            str(migration_dir),
            "--out-dir",
            str(readiness_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert readiness_proc.returncode == 0, readiness_proc.stderr
    rollup = json.loads((readiness_dir / "lineage_replay_readiness_rollup.json").read_text(encoding="utf-8"))
    lineage_doc = json.loads((lineage_dir / "durable_lineage_packs.json").read_text(encoding="utf-8"))
    control_doc = json.loads((control_dir / "replay_safe_ingestion_controls.json").read_text(encoding="utf-8"))
    assert lineage_doc["record_count"] == 2
    assert control_doc["record_count"] == 2
    assert rollup["readiness_pack_count"] == 2


def sample_m6d_ingestion_records() -> list[dict]:
    return [
        {
            "event_id": "rc-blocked-001",
            "emitted_at": "2026-03-21T05:00:00+00:00",
            "source": {
                "source_type": "ringcentral",
                "source_system": "ringcentral",
                "source_entity_type": "call-log",
                "source_record_id": "call-blocked-001",
                "content_family": "communication-event",
            },
            "pipeline": {
                "raw": {"status": "captured", "captured_at": "2026-03-21T05:00:00+00:00", "ref": "ingestion://rc-blocked-001"},
                "normalized": {"status": "normalized", "normalized_at": "2026-03-21T05:01:00+00:00", "ref": "inventory://rc-blocked-001"},
                "matched": {"status": "pending"},
                "approved": {"status": "pending"},
                "applied": {"status": "pending"},
            },
            "relationship_memory": {
                "candidates": [
                    {"entity_type": "contact", "entity_id": "contact-blocked-1", "confidence": 0.77, "reason": "same caller id"}
                ]
            },
            "governance": {"review_required": True},
            "evidence": {"zip_sha256": "sha-blocked", "start_here": "Blocked call transcript"},
            "warnings": [],
        },
        {
            "event_id": "rc-ready-apply-001",
            "emitted_at": "2026-03-21T06:00:00+00:00",
            "source": {
                "source_type": "ringcentral",
                "source_system": "ringcentral",
                "source_entity_type": "call-log",
                "source_record_id": "call-ready-apply-001",
                "content_family": "communication-event",
            },
            "pipeline": {
                "raw": {"status": "captured", "captured_at": "2026-03-21T06:00:00+00:00", "ref": "ingestion://rc-ready-apply-001"},
                "normalized": {"status": "normalized", "normalized_at": "2026-03-21T06:01:00+00:00", "ref": "inventory://rc-ready-apply-001"},
                "matched": {"status": "matched", "entity_type": "contact", "entity_id": "contact-ready-apply-1"},
                "approved": {"status": "approved", "approved_at": "2026-03-21T06:05:00+00:00", "approved_by": "operator-3", "reason": "validated"},
                "applied": {"status": "pending"},
            },
            "relationship_memory": {"candidates": []},
            "governance": {"review_required": False},
            "evidence": {"zip_sha256": "sha-ready-apply", "start_here": "Ready apply transcript"},
            "warnings": [],
        },
        {
            "event_id": "lacrm-protected-001",
            "emitted_at": "2026-03-21T07:00:00+00:00",
            "source": {
                "source_type": "lacrm",
                "source_system": "lacrm",
                "source_entity_type": "crm-contact",
                "source_record_id": "contact-protected-001",
                "content_family": "operating-core-event",
            },
            "pipeline": {
                "raw": {"status": "captured", "captured_at": "2026-03-21T07:00:00+00:00", "ref": "ingestion://lacrm-protected-001"},
                "normalized": {"status": "normalized", "normalized_at": "2026-03-21T07:01:00+00:00", "ref": "inventory://lacrm-protected-001"},
                "matched": {"status": "matched", "entity_type": "contact", "entity_id": "contact-protected-001"},
                "approved": {"status": "approved", "approved_at": "2026-03-21T07:05:00+00:00", "approved_by": "operator-4", "reason": "validated"},
                "applied": {"status": "applied", "applied_at": "2026-03-21T07:10:00+00:00", "applied_ref": "lacrm://contact/contact-protected-001", "target_type": "crm-contact", "target_id": "contact-protected-001"},
            },
            "relationship_memory": {"candidates": []},
            "governance": {"review_required": False},
            "evidence": {"zip_sha256": "sha-protected", "start_here": "Protected CRM contact export"},
            "warnings": [],
        },
        {
            "event_id": "rc-full-001",
            "emitted_at": "2026-03-21T08:00:00+00:00",
            "source": {
                "source_type": "ringcentral",
                "source_system": "ringcentral",
                "source_entity_type": "contact",
                "source_record_id": "contact-full-001",
                "content_family": "communication-event",
            },
            "pipeline": {
                "raw": {"status": "captured", "captured_at": "2026-03-21T08:00:00+00:00", "ref": "ingestion://rc-full-001"},
                "normalized": {"status": "normalized", "normalized_at": "2026-03-21T08:01:00+00:00", "ref": "inventory://rc-full-001"},
                "matched": {"status": "matched", "entity_type": "contact", "entity_id": "contact-full-001"},
                "approved": {"status": "not_applicable"},
                "applied": {"status": "pending"},
            },
            "relationship_memory": {"candidates": []},
            "governance": {"review_required": False},
            "evidence": {"zip_sha256": "sha-full", "start_here": "Full replay contact export"},
            "warnings": [],
        },
    ]


def build_m6d_documents() -> tuple[dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict]]:
    pipeline = build_source_control_pipeline_artifacts(sample_m6d_ingestion_records())
    migration = build_ringcentral_lacrm_migration_artifacts(pipeline)
    lineage = build_durable_lineage_artifacts(pipeline, migration)
    controls = build_replay_safe_ingestion_control_artifacts(lineage, migration)
    readiness = build_lineage_replay_readiness_artifacts(lineage, controls, migration)
    return pipeline, migration, lineage, controls, readiness


def test_build_source_replay_plan_artifacts_counts() -> None:
    pipeline, migration, lineage, controls, readiness = build_m6d_documents()
    artifacts = build_source_replay_plan_artifacts(pipeline, migration, lineage, controls, readiness)
    assert artifacts["source_replay_plan_packs"]["record_count"] == 3
    assert artifacts["source_replay_plan_review_queue"]["record_count"] == 1
    assert artifacts["source_replay_plan_rollup"]["schema_version"] == SOURCE_REPLAY_PLAN_SCHEMA_VERSION
    modes = {record["replay_mode"] for record in artifacts["source_replay_plan_packs"]["records"]}
    assert modes == {"compare-only", "resume-from-approved", "full-replay"}


def test_source_replay_plan_script_writes_expected_artifacts(tmp_path: Path) -> None:
    ingestion_path = tmp_path / "ingestion-events.jsonl"
    with ingestion_path.open("w", encoding="utf-8") as handle:
        for record in sample_m6d_ingestion_records():
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    pipeline_dir = tmp_path / "pipeline"
    migration_dir = tmp_path / "migration"
    lineage_dir = tmp_path / "lineage"
    control_dir = tmp_path / "controls"
    readiness_dir = tmp_path / "readiness"
    replay_plan_dir = tmp_path / "replay-plan"

    commands = [
        [sys.executable, "scripts/build_source_control_pipeline.py", "--ingestion-path", str(ingestion_path), "--out-dir", str(pipeline_dir)],
        [sys.executable, "scripts/build_ringcentral_lacrm_migration_packs.py", "--pipeline-dir", str(pipeline_dir), "--out-dir", str(migration_dir)],
        [sys.executable, "scripts/build_durable_lineage_packs.py", "--pipeline-dir", str(pipeline_dir), "--migration-dir", str(migration_dir), "--out-dir", str(lineage_dir)],
        [sys.executable, "scripts/build_replay_safe_ingestion_controls.py", "--lineage-dir", str(lineage_dir), "--migration-dir", str(migration_dir), "--out-dir", str(control_dir)],
        [sys.executable, "scripts/build_lineage_replay_readiness_packs.py", "--lineage-dir", str(lineage_dir), "--control-dir", str(control_dir), "--migration-dir", str(migration_dir), "--out-dir", str(readiness_dir)],
        [
            sys.executable,
            "scripts/build_source_replay_plan_packs.py",
            "--pipeline-dir",
            str(pipeline_dir),
            "--migration-dir",
            str(migration_dir),
            "--lineage-dir",
            str(lineage_dir),
            "--control-dir",
            str(control_dir),
            "--readiness-dir",
            str(readiness_dir),
            "--out-dir",
            str(replay_plan_dir),
        ],
    ]

    for command in commands:
        proc = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr

    rollup = json.loads((replay_plan_dir / "source_replay_plan_rollup.json").read_text(encoding="utf-8"))
    packs_doc = json.loads((replay_plan_dir / "source_replay_plan_packs.json").read_text(encoding="utf-8"))
    assert rollup["replay_plan_count"] == 3
    assert rollup["review_item_count"] == 1
    assert rollup["replay_mode_counts"]["compare-only"] == 1
    assert rollup["replay_mode_counts"]["resume-from-approved"] == 1
    assert rollup["replay_mode_counts"]["full-replay"] == 1
    assert packs_doc["record_count"] == 3


def test_build_source_replay_plan_artifacts_distinguishes_replay_modes() -> None:
    readiness_documents = {
        "lineage_replay_readiness_packs": {
            "records": [
                {
                    "lineage_replay_readiness_id": "readiness-compare",
                    "source_key": "source-compare",
                    "durable_lineage_id": "lineage-compare",
                    "replay_safe_ingestion_control_id": "control-compare",
                    "migration_pack_id": "pack-compare",
                    "readiness_state": "protected-ready",
                    "replay_state": "replay-protected",
                    "migration_state": "already-applied",
                },
                {
                    "lineage_replay_readiness_id": "readiness-resume",
                    "source_key": "source-resume",
                    "durable_lineage_id": "lineage-resume",
                    "replay_safe_ingestion_control_id": "control-resume",
                    "migration_pack_id": "pack-resume",
                    "readiness_state": "ready-for-replay",
                    "replay_state": "replay-safe",
                    "migration_state": "ready-for-apply",
                },
                {
                    "lineage_replay_readiness_id": "readiness-full",
                    "source_key": "source-full",
                    "durable_lineage_id": "lineage-full",
                    "replay_safe_ingestion_control_id": "control-full",
                    "migration_pack_id": "pack-full",
                    "readiness_state": "ready-for-replay",
                    "replay_state": "replay-safe",
                    "migration_state": "ready-for-review",
                },
            ]
        },
        "lineage_replay_readiness_review_queue": {"records": []},
    }
    control_documents = {
        "replay_safe_ingestion_controls": {
            "records": [
                {
                    "source_key": "source-compare",
                    "replay_safe_ingestion_control_id": "control-compare",
                    "replay_key": "replay-compare",
                    "idempotency_key": "idem-compare",
                    "replay_state": "replay-protected",
                },
                {
                    "source_key": "source-resume",
                    "replay_safe_ingestion_control_id": "control-resume",
                    "replay_key": "replay-resume",
                    "idempotency_key": "idem-resume",
                    "replay_state": "replay-safe",
                },
                {
                    "source_key": "source-full",
                    "replay_safe_ingestion_control_id": "control-full",
                    "replay_key": "replay-full",
                    "idempotency_key": "idem-full",
                    "replay_state": "replay-safe",
                },
            ]
        },
        "replay_safe_ingestion_review_queue": {"records": []},
    }
    lineage_documents = {
        "durable_lineage_packs": {
            "records": [
                {
                    "source_key": "source-compare",
                    "durable_lineage_id": "lineage-compare",
                    "durable_entity_id": "entity-compare",
                    "replay_key": "replay-compare",
                    "source_system": "ringcentral",
                    "source_entity_type": "call-log",
                    "migration_profile": "ringcentral-call-log",
                },
                {
                    "source_key": "source-resume",
                    "durable_lineage_id": "lineage-resume",
                    "durable_entity_id": "entity-resume",
                    "replay_key": "replay-resume",
                    "source_system": "lacrm",
                    "source_entity_type": "crm-contact",
                    "migration_profile": "lacrm-contact",
                },
                {
                    "source_key": "source-full",
                    "durable_lineage_id": "lineage-full",
                    "durable_entity_id": "entity-full",
                    "replay_key": "replay-full",
                    "source_system": "ringcentral",
                    "source_entity_type": "message-thread",
                    "migration_profile": "ringcentral-message-thread",
                },
            ]
        },
        "durable_lineage_review_queue": {"records": []},
    }
    migration_documents = {
        "migration_packs": {
            "records": [
                {
                    "source_key": "source-compare",
                    "migration_pack_id": "pack-compare",
                    "source_system": "ringcentral",
                    "source_entity_type": "call-log",
                    "migration_profile": "ringcentral-call-log",
                    "readiness_state": "already-applied",
                },
                {
                    "source_key": "source-resume",
                    "migration_pack_id": "pack-resume",
                    "source_system": "lacrm",
                    "source_entity_type": "crm-contact",
                    "migration_profile": "lacrm-contact",
                    "readiness_state": "ready-for-apply",
                },
                {
                    "source_key": "source-full",
                    "migration_pack_id": "pack-full",
                    "source_system": "ringcentral",
                    "source_entity_type": "message-thread",
                    "migration_profile": "ringcentral-message-thread",
                    "readiness_state": "ready-for-review",
                },
            ]
        },
        "migration_review_queue": {"records": []},
    }

    artifacts = build_source_replay_plan_artifacts(
        readiness_documents=readiness_documents,
        control_documents=control_documents,
        lineage_documents=lineage_documents,
        migration_documents=migration_documents,
    )

    assert artifacts["source_replay_plan_packs"]["record_count"] == 3
    assert artifacts["source_replay_plan_review_queue"]["record_count"] == 0
    assert artifacts["source_replay_plan_rollup"]["schema_version"] == SOURCE_REPLAY_PLAN_SCHEMA_VERSION

    modes = {
        record["source_key"]: record["replay_mode"]
        for record in artifacts["source_replay_plan_packs"]["records"]
    }
    assert modes == {
        "source-compare": "compare-only",
        "source-resume": "resume-from-approved",
        "source-full": "full-replay",
    }


def test_build_source_replay_plan_artifacts_from_m6c_outputs() -> None:
    pipeline = build_source_control_pipeline_artifacts(sample_m6b_ingestion_records())
    migration = build_ringcentral_lacrm_migration_artifacts(pipeline)
    lineage = build_durable_lineage_artifacts(pipeline, migration)
    controls = build_replay_safe_ingestion_control_artifacts(lineage, migration)
    readiness = build_lineage_replay_readiness_artifacts(lineage, controls, migration)

    artifacts = build_source_replay_plan_artifacts(
        readiness_documents=readiness,
        control_documents=controls,
        lineage_documents=lineage,
        migration_documents=migration,
    )

    assert artifacts["source_replay_plan_packs"]["record_count"] == 1
    assert artifacts["source_replay_plan_review_queue"]["record_count"] == 1
    assert artifacts["source_replay_plan_rollup"]["schema_version"] == SOURCE_REPLAY_PLAN_SCHEMA_VERSION
    assert {record["replay_mode"] for record in artifacts["source_replay_plan_packs"]["records"]} == {
        "compare-only"
    }
    review_reasons = artifacts["source_replay_plan_review_queue"]["records"][0]["reason_codes"]
    assert "blocked_for_replay_planning" in review_reasons



def build_m6d_block2_documents() -> tuple[dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict]]:
    pipeline, migration, lineage, controls, readiness = build_m6d_documents()
    plans = build_source_replay_plan_artifacts(pipeline, migration, lineage, controls, readiness)
    return pipeline, migration, lineage, controls, readiness, plans


def test_build_source_replay_compare_artifacts_counts() -> None:
    pipeline, migration, lineage, controls, readiness, plans = build_m6d_block2_documents()
    artifacts = build_source_replay_compare_artifacts(
        pipeline,
        migration,
        lineage,
        controls,
        readiness,
        plans,
    )
    assert artifacts["source_replay_compare_packs"]["record_count"] == 3
    assert artifacts["source_replay_compare_review_queue"]["record_count"] == 1
    assert artifacts["source_replay_compare_rollup"]["schema_version"] == SOURCE_REPLAY_COMPARE_SCHEMA_VERSION
    outcomes = {record["comparison_outcome"] for record in artifacts["source_replay_compare_packs"]["records"]}
    assert outcomes == {"stable-match", "resume-required", "full-replay-required"}


def test_build_source_replay_compare_artifacts_flags_state_drift() -> None:
    plan_documents = {
        "source_replay_plan_packs": {
            "records": [
                {
                    "source_replay_plan_id": "plan-compare",
                    "source_key": "source-compare",
                    "source_system": "ringcentral",
                    "source_entity_type": "call-log",
                    "migration_profile": "ringcentral-call-log",
                    "readiness_state": "protected-ready",
                    "replay_state": "replay-protected",
                    "migration_state": "already-applied",
                    "replay_mode": "compare-only",
                    "resume_from_stage": "applied",
                    "planned_actions": ["replay-compare"],
                    "compare_first": True,
                    "downstream_write_allowed": False,
                    "write_constraint": "no-downstream-writes",
                }
            ]
        },
        "source_replay_plan_review_queue": {"records": []},
    }
    readiness_documents = {
        "lineage_replay_readiness_packs": {
            "records": [
                {
                    "source_key": "source-compare",
                    "readiness_state": "ready-for-replay",
                }
            ]
        },
        "lineage_replay_readiness_review_queue": {"records": []},
    }
    control_documents = {
        "replay_safe_ingestion_controls": {
            "records": [
                {
                    "source_key": "source-compare",
                    "replay_state": "replay-safe",
                }
            ]
        },
        "replay_safe_ingestion_review_queue": {"records": []},
    }
    lineage_documents = {
        "durable_lineage_packs": {
            "records": [
                {
                    "source_key": "source-compare",
                    "source_system": "ringcentral",
                    "source_entity_type": "call-log",
                    "migration_profile": "ringcentral-call-log",
                }
            ]
        },
        "durable_lineage_review_queue": {"records": []},
    }
    migration_documents = {
        "migration_packs": {
            "records": [
                {
                    "source_key": "source-compare",
                    "source_system": "ringcentral",
                    "source_entity_type": "call-log",
                    "migration_profile": "ringcentral-call-log",
                    "readiness_state": "ready-for-review",
                }
            ]
        },
        "migration_review_queue": {"records": []},
    }

    artifacts = build_source_replay_compare_artifacts(
        plan_documents=plan_documents,
        readiness_documents=readiness_documents,
        control_documents=control_documents,
        lineage_documents=lineage_documents,
        migration_documents=migration_documents,
    )
    assert artifacts["source_replay_compare_packs"]["record_count"] == 1
    pack = artifacts["source_replay_compare_packs"]["records"][0]
    assert pack["comparison_outcome"] == "upstream-state-drift"
    assert pack["comparison_requires_review"] is True
    assert artifacts["source_replay_compare_review_queue"]["record_count"] == 1
    assert "comparison_requires_review" in artifacts["source_replay_compare_review_queue"]["records"][0]["reason_codes"]


def test_source_replay_compare_script_writes_expected_artifacts(tmp_path: Path) -> None:
    ingestion_path = tmp_path / "ingestion-events.jsonl"
    with ingestion_path.open("w", encoding="utf-8") as handle:
        for record in sample_m6d_ingestion_records():
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    pipeline_dir = tmp_path / "pipeline"
    migration_dir = tmp_path / "migration"
    lineage_dir = tmp_path / "lineage"
    control_dir = tmp_path / "controls"
    readiness_dir = tmp_path / "readiness"
    replay_plan_dir = tmp_path / "replay-plan"
    replay_compare_dir = tmp_path / "replay-compare"

    commands = [
        [sys.executable, "scripts/build_source_control_pipeline.py", "--ingestion-path", str(ingestion_path), "--out-dir", str(pipeline_dir)],
        [sys.executable, "scripts/build_ringcentral_lacrm_migration_packs.py", "--pipeline-dir", str(pipeline_dir), "--out-dir", str(migration_dir)],
        [sys.executable, "scripts/build_durable_lineage_packs.py", "--pipeline-dir", str(pipeline_dir), "--migration-dir", str(migration_dir), "--out-dir", str(lineage_dir)],
        [sys.executable, "scripts/build_replay_safe_ingestion_controls.py", "--lineage-dir", str(lineage_dir), "--migration-dir", str(migration_dir), "--out-dir", str(control_dir)],
        [sys.executable, "scripts/build_lineage_replay_readiness_packs.py", "--lineage-dir", str(lineage_dir), "--control-dir", str(control_dir), "--migration-dir", str(migration_dir), "--out-dir", str(readiness_dir)],
        [
            sys.executable,
            "scripts/build_source_replay_plan_packs.py",
            "--pipeline-dir",
            str(pipeline_dir),
            "--migration-dir",
            str(migration_dir),
            "--lineage-dir",
            str(lineage_dir),
            "--control-dir",
            str(control_dir),
            "--readiness-dir",
            str(readiness_dir),
            "--out-dir",
            str(replay_plan_dir),
        ],
        [
            sys.executable,
            "scripts/build_source_replay_compare_packs.py",
            "--pipeline-dir",
            str(pipeline_dir),
            "--plan-dir",
            str(replay_plan_dir),
            "--migration-dir",
            str(migration_dir),
            "--lineage-dir",
            str(lineage_dir),
            "--control-dir",
            str(control_dir),
            "--readiness-dir",
            str(readiness_dir),
            "--out-dir",
            str(replay_compare_dir),
        ],
    ]

    for command in commands:
        proc = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr

    rollup = json.loads((replay_compare_dir / "source_replay_compare_rollup.json").read_text(encoding="utf-8"))
    packs_doc = json.loads((replay_compare_dir / "source_replay_compare_packs.json").read_text(encoding="utf-8"))

    assert rollup["comparison_pack_count"] == 3
    assert rollup["review_item_count"] == 1
    assert rollup["comparison_outcome_counts"]["stable-match"] == 1
    assert rollup["comparison_outcome_counts"]["resume-required"] == 1
    assert rollup["comparison_outcome_counts"]["full-replay-required"] == 1
    assert packs_doc["record_count"] == 3

def build_m6d_block3_documents() -> tuple[dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict]]:
    pipeline, migration, lineage, controls, readiness, plans = build_m6d_block2_documents()
    compare = build_source_replay_compare_artifacts(
        pipeline,
        migration,
        lineage,
        controls,
        readiness,
        plans,
    )
    return pipeline, migration, lineage, controls, readiness, plans, compare


def test_build_source_replay_approval_artifacts_counts() -> None:
    pipeline, migration, lineage, controls, readiness, plans, compare = build_m6d_block3_documents()
    artifacts = build_source_replay_approval_artifacts(
        pipeline,
        migration,
        lineage,
        controls,
        readiness,
        plans,
        compare,
    )
    assert artifacts["source_replay_approval_journal"]["record_count"] == 2
    assert artifacts["source_replay_approval_queue"]["record_count"] == 2
    assert artifacts["source_replay_approval_rollup"]["schema_version"] == SOURCE_REPLAY_APPROVAL_SCHEMA_VERSION
    decisions = {record["approval_decision"] for record in artifacts["source_replay_approval_journal"]["records"]}
    assert decisions == {"approved-no-op-compare", "approved-resume-replay"}


def test_build_source_replay_approval_artifacts_requires_manual_full_replay() -> None:
    compare_documents = {
        "source_replay_compare_packs": {
            "records": [
                {
                    "source_replay_compare_id": "compare-full",
                    "source_replay_plan_id": "plan-full",
                    "source_key": "source-full",
                    "source_system": "lacrm",
                    "source_entity_type": "contact",
                    "migration_profile": "lacrm-contact",
                    "replay_mode": "full-replay",
                    "comparison_outcome": "full-replay-required",
                    "comparison_requires_review": False,
                    "expected_state_snapshot": {
                        "compare_first": True,
                        "downstream_write_allowed": False,
                        "write_constraint": "no-downstream-writes",
                        "resume_from_stage": "raw",
                        "planned_actions": ["rebuild", "recompare"],
                    },
                    "provenance_refs": {},
                }
            ]
        },
        "source_replay_compare_review_queue": {"records": []},
    }
    plan_documents = {
        "source_replay_plan_packs": {
            "records": [
                {
                    "source_replay_plan_id": "plan-full",
                    "source_key": "source-full",
                    "replay_key": "replay-full",
                    "idempotency_key": "idem-full",
                }
            ]
        },
        "source_replay_plan_review_queue": {"records": []},
    }
    readiness_documents = {
        "lineage_replay_readiness_packs": {"records": [{"source_key": "source-full"}]},
        "lineage_replay_readiness_review_queue": {"records": []},
    }
    control_documents = {
        "replay_safe_ingestion_controls": {"records": [{"source_key": "source-full"}]},
        "replay_safe_ingestion_review_queue": {"records": []},
    }
    lineage_documents = {
        "durable_lineage_packs": {
            "records": [
                {
                    "source_key": "source-full",
                    "source_system": "lacrm",
                    "source_entity_type": "contact",
                    "migration_profile": "lacrm-contact",
                }
            ]
        },
        "durable_lineage_review_queue": {"records": []},
    }
    migration_documents = {
        "migration_packs": {
            "records": [
                {
                    "source_key": "source-full",
                    "source_system": "lacrm",
                    "source_entity_type": "contact",
                    "migration_profile": "lacrm-contact",
                }
            ]
        },
        "migration_review_queue": {"records": []},
    }

    artifacts = build_source_replay_approval_artifacts(
        compare_documents=compare_documents,
        plan_documents=plan_documents,
        readiness_documents=readiness_documents,
        control_documents=control_documents,
        lineage_documents=lineage_documents,
        migration_documents=migration_documents,
    )
    assert artifacts["source_replay_approval_journal"]["record_count"] == 0
    assert artifacts["source_replay_approval_queue"]["record_count"] == 1
    assert "manual_full_replay_approval_required" in artifacts["source_replay_approval_queue"]["records"][0]["reason_codes"]


def test_source_replay_approval_script_writes_expected_artifacts(tmp_path: Path) -> None:
    ingestion_path = tmp_path / "ingestion-events.jsonl"
    with ingestion_path.open("w", encoding="utf-8") as handle:
        for record in sample_m6d_ingestion_records():
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    pipeline_dir = tmp_path / "pipeline"
    migration_dir = tmp_path / "migration"
    lineage_dir = tmp_path / "lineage"
    control_dir = tmp_path / "controls"
    readiness_dir = tmp_path / "readiness"
    replay_plan_dir = tmp_path / "replay-plan"
    replay_compare_dir = tmp_path / "replay-compare"
    replay_approval_dir = tmp_path / "replay-approval"

    commands = [
        [sys.executable, "scripts/build_source_control_pipeline.py", "--ingestion-path", str(ingestion_path), "--out-dir", str(pipeline_dir)],
        [sys.executable, "scripts/build_ringcentral_lacrm_migration_packs.py", "--pipeline-dir", str(pipeline_dir), "--out-dir", str(migration_dir)],
        [sys.executable, "scripts/build_durable_lineage_packs.py", "--pipeline-dir", str(pipeline_dir), "--migration-dir", str(migration_dir), "--out-dir", str(lineage_dir)],
        [sys.executable, "scripts/build_replay_safe_ingestion_controls.py", "--lineage-dir", str(lineage_dir), "--migration-dir", str(migration_dir), "--out-dir", str(control_dir)],
        [sys.executable, "scripts/build_lineage_replay_readiness_packs.py", "--lineage-dir", str(lineage_dir), "--control-dir", str(control_dir), "--migration-dir", str(migration_dir), "--out-dir", str(readiness_dir)],
        [
            sys.executable,
            "scripts/build_source_replay_plan_packs.py",
            "--pipeline-dir",
            str(pipeline_dir),
            "--migration-dir",
            str(migration_dir),
            "--lineage-dir",
            str(lineage_dir),
            "--control-dir",
            str(control_dir),
            "--readiness-dir",
            str(readiness_dir),
            "--out-dir",
            str(replay_plan_dir),
        ],
        [
            sys.executable,
            "scripts/build_source_replay_compare_packs.py",
            "--pipeline-dir",
            str(pipeline_dir),
            "--plan-dir",
            str(replay_plan_dir),
            "--migration-dir",
            str(migration_dir),
            "--lineage-dir",
            str(lineage_dir),
            "--control-dir",
            str(control_dir),
            "--readiness-dir",
            str(readiness_dir),
            "--out-dir",
            str(replay_compare_dir),
        ],
        [
            sys.executable,
            "scripts/build_source_replay_approval_journals.py",
            "--pipeline-dir",
            str(pipeline_dir),
            "--compare-dir",
            str(replay_compare_dir),
            "--plan-dir",
            str(replay_plan_dir),
            "--migration-dir",
            str(migration_dir),
            "--lineage-dir",
            str(lineage_dir),
            "--control-dir",
            str(control_dir),
            "--readiness-dir",
            str(readiness_dir),
            "--out-dir",
            str(replay_approval_dir),
        ],
    ]

    for command in commands:
        proc = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr

    rollup = json.loads((replay_approval_dir / "source_replay_approval_rollup.json").read_text(encoding="utf-8"))
    queue_doc = json.loads((replay_approval_dir / "source_replay_approval_queue.json").read_text(encoding="utf-8"))
    journal_lines = [
        json.loads(line)
        for line in (replay_approval_dir / "source_replay_approval_journal.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert rollup["approval_journal_count"] == 2
    assert rollup["review_item_count"] == 2
    assert rollup["approval_decision_counts"]["approved-no-op-compare"] == 1
    assert rollup["approval_decision_counts"]["approved-resume-replay"] == 1
    assert queue_doc["record_count"] == 2
    assert len(journal_lines) == 2

def build_m6d_block4_documents() -> tuple[dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict]]:
    pipeline, migration, lineage, controls, readiness, plans, compare = build_m6d_block3_documents()
    approval = build_source_replay_approval_artifacts(
        pipeline,
        migration,
        lineage,
        controls,
        readiness,
        plans,
        compare,
    )
    return pipeline, migration, lineage, controls, readiness, plans, compare, approval


def test_build_source_replay_execution_artifacts_counts() -> None:
    pipeline, migration, lineage, controls, readiness, plans, compare, approval = build_m6d_block4_documents()
    artifacts = build_source_replay_execution_artifacts(
        pipeline,
        migration,
        lineage,
        controls,
        readiness,
        plans,
        compare,
        approval,
    )
    assert artifacts["source_replay_execution_packs"]["record_count"] == 2
    assert artifacts["source_replay_execution_review_queue"]["record_count"] == 2
    assert artifacts["source_replay_execution_rollup"]["schema_version"] == SOURCE_REPLAY_EXECUTION_SCHEMA_VERSION
    statuses = {record["execution_status"] for record in artifacts["source_replay_execution_packs"]["records"]}
    assert statuses == {"not-required", "ready-for-dry-run"}


def test_build_source_replay_execution_artifacts_supports_full_replay_execution() -> None:
    approval_documents = {
        "source_replay_approval_journal": {
            "records": [
                {
                    "source_replay_approval_id": "approval-full",
                    "source_replay_compare_id": "compare-full",
                    "source_replay_plan_id": "plan-full",
                    "source_key": "source-full",
                    "source_system": "lacrm",
                    "source_entity_type": "contact",
                    "migration_profile": "lacrm-contact",
                    "replay_mode": "full-replay",
                    "comparison_outcome": "full-replay-required",
                    "approval_status": "approved",
                    "approval_decision": "approved-full-replay",
                    "execution_gate": "execution-pack-eligible",
                    "compare_first": True,
                    "downstream_write_allowed": False,
                    "write_constraint": "no-downstream-writes",
                    "resume_from_stage": "raw",
                    "planned_actions": ["rebuild", "recompare"],
                    "replay_key": "replay-full",
                    "idempotency_key": "idem-full",
                    "provenance_refs": {},
                    "upstream_state_snapshot": {},
                }
            ]
        },
        "source_replay_approval_queue": {"records": []},
    }
    compare_documents = {
        "source_replay_compare_packs": {
            "records": [
                {
                    "source_replay_compare_id": "compare-full",
                    "source_replay_plan_id": "plan-full",
                    "source_key": "source-full",
                    "source_system": "lacrm",
                    "source_entity_type": "contact",
                    "migration_profile": "lacrm-contact",
                    "replay_mode": "full-replay",
                    "comparison_outcome": "full-replay-required",
                }
            ]
        },
        "source_replay_compare_review_queue": {"records": []},
    }
    plan_documents = {
        "source_replay_plan_packs": {
            "records": [
                {
                    "source_replay_plan_id": "plan-full",
                    "source_key": "source-full",
                    "replay_key": "replay-full",
                    "idempotency_key": "idem-full",
                }
            ]
        },
        "source_replay_plan_review_queue": {"records": []},
    }
    readiness_documents = {
        "lineage_replay_readiness_packs": {"records": [{"source_key": "source-full"}]},
        "lineage_replay_readiness_review_queue": {"records": []},
    }
    control_documents = {
        "replay_safe_ingestion_controls": {"records": [{"source_key": "source-full"}]},
        "replay_safe_ingestion_review_queue": {"records": []},
    }
    lineage_documents = {
        "durable_lineage_packs": {
            "records": [
                {
                    "source_key": "source-full",
                    "source_system": "lacrm",
                    "source_entity_type": "contact",
                    "migration_profile": "lacrm-contact",
                }
            ]
        },
        "durable_lineage_review_queue": {"records": []},
    }
    migration_documents = {
        "migration_packs": {
            "records": [
                {
                    "source_key": "source-full",
                    "source_system": "lacrm",
                    "source_entity_type": "contact",
                    "migration_profile": "lacrm-contact",
                }
            ]
        },
        "migration_review_queue": {"records": []},
    }

    artifacts = build_source_replay_execution_artifacts(
        approval_documents=approval_documents,
        compare_documents=compare_documents,
        plan_documents=plan_documents,
        readiness_documents=readiness_documents,
        control_documents=control_documents,
        lineage_documents=lineage_documents,
        migration_documents=migration_documents,
    )
    assert artifacts["source_replay_execution_packs"]["record_count"] == 1
    pack = artifacts["source_replay_execution_packs"]["records"][0]
    assert pack["execution_status"] == "ready-for-dry-run"
    assert pack["execution_scope"] == "full-replay"


def test_source_replay_execution_script_writes_expected_artifacts(tmp_path: Path) -> None:
    ingestion_path = tmp_path / "ingestion-events.jsonl"
    with ingestion_path.open("w", encoding="utf-8") as handle:
        for record in sample_m6d_ingestion_records():
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    pipeline_dir = tmp_path / "pipeline"
    migration_dir = tmp_path / "migration"
    lineage_dir = tmp_path / "lineage"
    control_dir = tmp_path / "controls"
    readiness_dir = tmp_path / "readiness"
    replay_plan_dir = tmp_path / "replay-plan"
    replay_compare_dir = tmp_path / "replay-compare"
    replay_approval_dir = tmp_path / "replay-approval"
    replay_execution_dir = tmp_path / "replay-execution"

    commands = [
        [sys.executable, "scripts/build_source_control_pipeline.py", "--ingestion-path", str(ingestion_path), "--out-dir", str(pipeline_dir)],
        [sys.executable, "scripts/build_ringcentral_lacrm_migration_packs.py", "--pipeline-dir", str(pipeline_dir), "--out-dir", str(migration_dir)],
        [sys.executable, "scripts/build_durable_lineage_packs.py", "--pipeline-dir", str(pipeline_dir), "--migration-dir", str(migration_dir), "--out-dir", str(lineage_dir)],
        [sys.executable, "scripts/build_replay_safe_ingestion_controls.py", "--lineage-dir", str(lineage_dir), "--migration-dir", str(migration_dir), "--out-dir", str(control_dir)],
        [sys.executable, "scripts/build_lineage_replay_readiness_packs.py", "--lineage-dir", str(lineage_dir), "--control-dir", str(control_dir), "--migration-dir", str(migration_dir), "--out-dir", str(readiness_dir)],
        [
            sys.executable,
            "scripts/build_source_replay_plan_packs.py",
            "--pipeline-dir",
            str(pipeline_dir),
            "--migration-dir",
            str(migration_dir),
            "--lineage-dir",
            str(lineage_dir),
            "--control-dir",
            str(control_dir),
            "--readiness-dir",
            str(readiness_dir),
            "--out-dir",
            str(replay_plan_dir),
        ],
        [
            sys.executable,
            "scripts/build_source_replay_compare_packs.py",
            "--pipeline-dir",
            str(pipeline_dir),
            "--plan-dir",
            str(replay_plan_dir),
            "--migration-dir",
            str(migration_dir),
            "--lineage-dir",
            str(lineage_dir),
            "--control-dir",
            str(control_dir),
            "--readiness-dir",
            str(readiness_dir),
            "--out-dir",
            str(replay_compare_dir),
        ],
        [
            sys.executable,
            "scripts/build_source_replay_approval_journals.py",
            "--pipeline-dir",
            str(pipeline_dir),
            "--compare-dir",
            str(replay_compare_dir),
            "--plan-dir",
            str(replay_plan_dir),
            "--migration-dir",
            str(migration_dir),
            "--lineage-dir",
            str(lineage_dir),
            "--control-dir",
            str(control_dir),
            "--readiness-dir",
            str(readiness_dir),
            "--out-dir",
            str(replay_approval_dir),
        ],
        [
            sys.executable,
            "scripts/build_source_replay_execution_packs.py",
            "--pipeline-dir",
            str(pipeline_dir),
            "--approval-dir",
            str(replay_approval_dir),
            "--compare-dir",
            str(replay_compare_dir),
            "--plan-dir",
            str(replay_plan_dir),
            "--migration-dir",
            str(migration_dir),
            "--lineage-dir",
            str(lineage_dir),
            "--control-dir",
            str(control_dir),
            "--readiness-dir",
            str(readiness_dir),
            "--out-dir",
            str(replay_execution_dir),
        ],
    ]

    for command in commands:
        proc = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr

    rollup = json.loads((replay_execution_dir / "source_replay_execution_rollup.json").read_text(encoding="utf-8"))
    packs_doc = json.loads((replay_execution_dir / "source_replay_execution_packs.json").read_text(encoding="utf-8"))

    assert rollup["execution_pack_count"] == 2
    assert rollup["review_item_count"] == 2
    assert rollup["execution_status_counts"]["not-required"] == 1
    assert rollup["execution_status_counts"]["ready-for-dry-run"] == 1
    assert packs_doc["record_count"] == 2

def build_m6e_block1_documents() -> tuple[dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict]]:
    pipeline, migration, lineage, controls, readiness, plans, compare, approval = build_m6d_block4_documents()
    execution = build_source_replay_execution_artifacts(
        pipeline,
        migration,
        lineage,
        controls,
        readiness,
        plans,
        compare,
        approval,
    )
    console = build_operator_console_alpha_artifacts(plans, compare, approval, execution)
    return plans, compare, approval, execution, console


def test_build_operator_console_alpha_artifacts_counts() -> None:
    plans, compare, approval, execution, console = build_m6e_block1_documents()
    assert console["operator_console_alpha_model"]["summary"]["plan_count"] == 3
    assert console["operator_console_alpha_model"]["summary"]["execution_pack_count"] == 2
    assert console["operator_console_alpha_rollup"]["source_count"] == 4
    assert console["operator_console_alpha_rollup"]["current_stage_counts"]["completed-no-op"] == 1
    assert console["operator_console_alpha_rollup"]["current_stage_counts"]["execution-ready"] == 1
    assert console["operator_console_alpha_rollup"]["current_stage_counts"]["execution-review"] == 2


def test_operator_console_alpha_html_contains_stage_and_source_key() -> None:
    _, _, _, _, console = build_m6e_block1_documents()
    html_doc = console["operator_console_alpha_html"]["html"]
    assert "Source Replay Operator Console Alpha" in html_doc
    assert "execution-ready" in html_doc
    assert "src-" in html_doc


def test_operator_console_alpha_scripts_write_expected_artifacts(tmp_path: Path) -> None:
    ingestion_path = tmp_path / "ingestion-events.jsonl"
    with ingestion_path.open("w", encoding="utf-8") as handle:
        for record in sample_m6d_ingestion_records():
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    pipeline_dir = tmp_path / "pipeline"
    migration_dir = tmp_path / "migration"
    lineage_dir = tmp_path / "lineage"
    control_dir = tmp_path / "controls"
    readiness_dir = tmp_path / "readiness"
    replay_plan_dir = tmp_path / "replay-plan"
    replay_compare_dir = tmp_path / "replay-compare"
    replay_approval_dir = tmp_path / "replay-approval"
    replay_execution_dir = tmp_path / "replay-execution"
    console_dir = tmp_path / "operator-console"

    commands = [
        [sys.executable, "scripts/build_source_control_pipeline.py", "--ingestion-path", str(ingestion_path), "--out-dir", str(pipeline_dir)],
        [sys.executable, "scripts/build_ringcentral_lacrm_migration_packs.py", "--pipeline-dir", str(pipeline_dir), "--out-dir", str(migration_dir)],
        [sys.executable, "scripts/build_durable_lineage_packs.py", "--pipeline-dir", str(pipeline_dir), "--migration-dir", str(migration_dir), "--out-dir", str(lineage_dir)],
        [sys.executable, "scripts/build_replay_safe_ingestion_controls.py", "--lineage-dir", str(lineage_dir), "--migration-dir", str(migration_dir), "--out-dir", str(control_dir)],
        [sys.executable, "scripts/build_lineage_replay_readiness_packs.py", "--lineage-dir", str(lineage_dir), "--control-dir", str(control_dir), "--migration-dir", str(migration_dir), "--out-dir", str(readiness_dir)],
        [
            sys.executable,
            "scripts/build_source_replay_plan_packs.py",
            "--pipeline-dir",
            str(pipeline_dir),
            "--migration-dir",
            str(migration_dir),
            "--lineage-dir",
            str(lineage_dir),
            "--control-dir",
            str(control_dir),
            "--readiness-dir",
            str(readiness_dir),
            "--out-dir",
            str(replay_plan_dir),
        ],
        [
            sys.executable,
            "scripts/build_source_replay_compare_packs.py",
            "--pipeline-dir",
            str(pipeline_dir),
            "--plan-dir",
            str(replay_plan_dir),
            "--migration-dir",
            str(migration_dir),
            "--lineage-dir",
            str(lineage_dir),
            "--control-dir",
            str(control_dir),
            "--readiness-dir",
            str(readiness_dir),
            "--out-dir",
            str(replay_compare_dir),
        ],
        [
            sys.executable,
            "scripts/build_source_replay_approval_journals.py",
            "--pipeline-dir",
            str(pipeline_dir),
            "--compare-dir",
            str(replay_compare_dir),
            "--plan-dir",
            str(replay_plan_dir),
            "--migration-dir",
            str(migration_dir),
            "--lineage-dir",
            str(lineage_dir),
            "--control-dir",
            str(control_dir),
            "--readiness-dir",
            str(readiness_dir),
            "--out-dir",
            str(replay_approval_dir),
        ],
        [
            sys.executable,
            "scripts/build_source_replay_execution_packs.py",
            "--pipeline-dir",
            str(pipeline_dir),
            "--approval-dir",
            str(replay_approval_dir),
            "--compare-dir",
            str(replay_compare_dir),
            "--plan-dir",
            str(replay_plan_dir),
            "--migration-dir",
            str(migration_dir),
            "--lineage-dir",
            str(lineage_dir),
            "--control-dir",
            str(control_dir),
            "--readiness-dir",
            str(readiness_dir),
            "--out-dir",
            str(replay_execution_dir),
        ],
        [
            sys.executable,
            "scripts/build_operator_console_alpha.py",
            "--plan-dir",
            str(replay_plan_dir),
            "--compare-dir",
            str(replay_compare_dir),
            "--approval-dir",
            str(replay_approval_dir),
            "--execution-dir",
            str(replay_execution_dir),
            "--out-dir",
            str(console_dir),
        ],
    ]

    for command in commands:
        proc = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr

    rollup = json.loads((console_dir / "operator_console_alpha_rollup.json").read_text(encoding="utf-8"))
    model = json.loads((console_dir / "operator_console_alpha_model.json").read_text(encoding="utf-8"))
    html_text = (console_dir / "operator_console_alpha.html").read_text(encoding="utf-8")

    assert rollup["source_count"] == 4
    assert model["summary"]["execution_pack_count"] == 2
    assert "Source Replay Operator Console Alpha" in html_text

def test_operator_console_alpha_artifacts_include_review_inbox_and_filter_options() -> None:
    _, _, _, _, console = build_m6e_block1_documents()
    model = console["operator_console_alpha_model"]
    rollup = console["operator_console_alpha_rollup"]

    assert model["summary"]["review_item_count"] == rollup["review_item_count"]
    assert model["review_items"]
    assert "current_stage" in model["filter_options"]
    assert "review_priority" in model["filter_options"]
    assert "reason_code" in model["filter_options"]
    assert "execution-review" in model["filter_options"]["current_stage"]
    assert rollup["review_item_stage_counts"]["execution-review"] >= 1
    assert rollup["review_priority_counts"]
    assert rollup["warning_count"] == len(model["warnings"])


def test_operator_console_alpha_html_contains_triage_controls_and_tooltips() -> None:
    _, _, _, _, console = build_m6e_block1_documents()
    html_doc = console["operator_console_alpha_html"]["html"]

    assert "Only Review Items" in html_doc
    assert "Export Filtered JSON" in html_doc
    assert "Export Filtered CSV" in html_doc
    assert "Load Model JSON" in html_doc
    assert "Review Inbox" in html_doc
    assert "Reason Code Filter" in html_doc
    assert "Copy Selected JSON" in html_doc
    assert "Current Stage Board" in html_doc
    assert "Review Queue Board" in html_doc
    assert "data-help=" in html_doc

def test_operator_console_alpha_artifacts_include_workbench_spec() -> None:
    _, _, _, _, console = build_m6e_block1_documents()
    model = console["operator_console_alpha_model"]
    rollup = console["operator_console_alpha_rollup"]

    assert model["workbench"]["mode"] == "draft-only-local"
    assert model["workbench"]["client_side_only"] is True
    assert model["workbench"]["mutates_backend"] is False
    assert "draft-decisions" in model["workbench"]["capabilities"]
    assert "draft-preview" in model["workbench"]["capabilities"]
    assert rollup["workbench_capability_count"] == len(model["workbench"]["capabilities"])
    assert model["summary"]["draft_action_count"] == len(model["workbench"]["decision_actions"])


def test_operator_console_alpha_html_contains_operator_workbench_controls() -> None:
    _, _, _, _, console = build_m6e_block1_documents()
    html_doc = console["operator_console_alpha_html"]["html"]

    assert "Operator Workbench" in html_doc
    assert "Select Filtered Rows" in html_doc
    assert "Only Selected" in html_doc
    assert "Draft Action" in html_doc
    assert "Apply Draft to Selected" in html_doc
    assert "Apply Draft to Active Row" in html_doc
    assert "Export Draft JSONL" in html_doc
    assert "Export Draft Summary JSON" in html_doc
    assert "Copy Draft Preview" in html_doc
    assert "Load Draft Decisions" in html_doc
    assert "Draft Decision Queue" in html_doc
    assert "Draft Preview" in html_doc
    assert "data-help=" in html_doc

def test_operator_console_alpha_artifacts_include_session_package_spec() -> None:
    _, _, _, _, console = build_m6e_block1_documents()
    model = console["operator_console_alpha_model"]
    rollup = console["operator_console_alpha_rollup"]

    assert "session-packages" in model["workbench"]["capabilities"]
    assert "undo-redo-history" in model["workbench"]["capabilities"]
    assert "local-audit-timeline" in model["workbench"]["capabilities"]
    assert model["workbench"]["session_formats"] == ["json"]
    assert model["workbench"]["history_limit"] >= 20
    assert model["summary"]["session_format_count"] == len(model["workbench"]["session_formats"])
    assert rollup["session_format_count"] == len(model["workbench"]["session_formats"])


def test_operator_console_alpha_html_contains_session_package_controls() -> None:
    _, _, _, _, console = build_m6e_block1_documents()
    html_doc = console["operator_console_alpha_html"]["html"]

    assert "Save Session Package" in html_doc
    assert "Load Session Package" in html_doc
    assert "Undo Draft Change" in html_doc
    assert "Redo Draft Change" in html_doc
    assert "Copy Session Summary" in html_doc
    assert "Session Notes" in html_doc
    assert "Session Timeline" in html_doc
    assert "Select Review Inbox" in html_doc
    assert "Select High Priority" in html_doc

def test_operator_console_alpha_artifacts_include_decision_package_and_runner_specs() -> None:
    _, _, _, _, console = build_m6e_block1_documents()
    model = console["operator_console_alpha_model"]
    rollup = console["operator_console_alpha_rollup"]

    assert "decision-packages" in model["workbench"]["capabilities"]
    assert "decision-package-validation" in model["workbench"]["capabilities"]
    assert "dry-run-preflight" in model["workbench"]["capabilities"]
    assert "runner-spec-export" in model["workbench"]["capabilities"]
    assert model["workbench"]["package_formats"] == ["json", "jsonl"]
    assert model["workbench"]["runner_formats"] == ["json"]
    assert model["summary"]["package_format_count"] == len(model["workbench"]["package_formats"])
    assert model["summary"]["runner_format_count"] == len(model["workbench"]["runner_formats"])
    assert rollup["package_format_count"] == len(model["workbench"]["package_formats"])
    assert rollup["runner_format_count"] == len(model["workbench"]["runner_formats"])


def test_operator_console_alpha_html_contains_decision_package_and_runner_controls() -> None:
    _, _, _, _, console = build_m6e_block1_documents()
    html_doc = console["operator_console_alpha_html"]["html"]

    assert "Decision Package Preview" in html_doc
    assert "Execution Preflight" in html_doc
    assert "Export Decision Package JSON" in html_doc
    assert "Export Decision Package JSONL" in html_doc
    assert "Copy Decision Package Preview" in html_doc
    assert "Load Decision Package" in html_doc
    assert "Validate Decision Package" in html_doc
    assert "Export Runner Spec JSON" in html_doc
    assert "Copy Runner Spec" in html_doc
    assert "data-help=" in html_doc
