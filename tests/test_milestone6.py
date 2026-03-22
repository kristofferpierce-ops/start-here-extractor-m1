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
