from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from start_here_extractor.source_control_pipeline import (
    SOURCE_CONTROL_PIPELINE_SCHEMA_VERSION,
    build_source_control_pipeline_artifacts,
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
