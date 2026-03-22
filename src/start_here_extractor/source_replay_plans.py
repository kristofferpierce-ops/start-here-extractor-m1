from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .durable_lineage_replay import (
    load_control_documents,
    load_lineage_documents,
    load_migration_documents,
    load_source_control_pipeline_documents,
)
from .security import redact_sensitive_fields

SOURCE_REPLAY_PLAN_SCHEMA_VERSION = "1.0"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _stable_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def load_readiness_documents(readiness_dir: str | Path) -> dict[str, dict]:
    path = Path(readiness_dir)
    names = {
        "lineage_replay_readiness_packs": "lineage_replay_readiness_packs.json",
        "lineage_replay_readiness_review_queue": "lineage_replay_readiness_review_queue.json",
        "lineage_replay_readiness_rollup": "lineage_replay_readiness_rollup.json",
    }
    payloads: dict[str, dict] = {}
    for key, filename in names.items():
        file_path = path / filename
        if file_path.exists():
            payloads[key] = json.loads(file_path.read_text(encoding="utf-8"))
        else:
            payloads[key] = {"records": []}
    return payloads


def _record_map(document: dict, key_name: str) -> dict[str, dict]:
    records = document.get("records") if isinstance(document.get("records"), list) else []
    mapping: dict[str, dict] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        key = _normalize_text(record.get(key_name))
        if key:
            mapping[key] = record
    return mapping


def _records_by_source_key(document: dict) -> dict[str, list[dict]]:
    records = document.get("records") if isinstance(document.get("records"), list) else []
    mapping: dict[str, list[dict]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        source_key = _normalize_text(record.get("source_key"))
        if not source_key:
            continue
        mapping.setdefault(source_key, []).append(record)
    return mapping


def _normalize_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    for value in values:
        item = _normalize_text(value)
        if item:
            normalized.append(item)
    return normalized


def _derive_replay_mode(readiness_state: str | None, replay_state: str | None, migration_state: str | None) -> tuple[str, str, list[str]]:
    readiness = _normalize_text(readiness_state)
    replay = _normalize_text(replay_state)
    migration = _normalize_text(migration_state)

    if readiness == "protected-ready" or replay == "replay-protected" or migration == "already-applied":
        return (
            "compare-only",
            "compare-against-existing-applied-state",
            ["raw", "normalized", "replay-compare"],
        )
    if migration == "ready-for-apply":
        return (
            "resume-from-approved",
            "resume-approved-delta-through-apply",
            ["approved", "applied", "replay-compare"],
        )
    return (
        "full-replay",
        "rebuild-review-candidate-and-compare",
        ["raw", "normalized", "matched", "approved", "replay-compare"],
    )


def build_source_replay_plan_artifacts(
    pipeline_documents: dict[str, dict],
    migration_documents: dict[str, dict],
    lineage_documents: dict[str, dict],
    control_documents: dict[str, dict],
    readiness_documents: dict[str, dict],
) -> dict[str, dict]:
    raw_map = _record_map(pipeline_documents.get("source_records_raw", {}), "source_key")
    normalized_map = _record_map(pipeline_documents.get("source_records_normalized", {}), "source_key")
    approved_map = _record_map(pipeline_documents.get("approved_deltas", {}), "source_key")
    applied_map = _record_map(pipeline_documents.get("applied_state_transitions", {}), "source_key")
    migration_map = _record_map(migration_documents.get("migration_packs", {}), "source_key")
    lineage_map = _record_map(lineage_documents.get("durable_lineage_packs", {}), "source_key")
    control_map = _record_map(control_documents.get("replay_safe_ingestion_controls", {}), "source_key")
    readiness_records = readiness_documents.get("lineage_replay_readiness_packs", {}).get("records")
    readiness_records = readiness_records if isinstance(readiness_records, list) else []
    readiness_reviews = _records_by_source_key(readiness_documents.get("lineage_replay_readiness_review_queue", {}))

    plan_packs: list[dict] = []
    review_queue: list[dict] = []
    replay_mode_counts: dict[str, int] = {}
    readiness_state_counts: dict[str, int] = {}
    migration_state_counts: dict[str, int] = {}

    for readiness_record in readiness_records:
        if not isinstance(readiness_record, dict):
            continue
        source_key = _normalize_text(readiness_record.get("source_key"))
        lineage_record = lineage_map.get(source_key or "")
        control_record = control_map.get(source_key or "")
        migration_pack = migration_map.get(source_key or "")
        raw_record = raw_map.get(source_key or "")
        normalized_record = normalized_map.get(source_key or "")
        approved_delta = approved_map.get(source_key or "")
        applied_transition = applied_map.get(source_key or "")
        readiness_state = _normalize_text(readiness_record.get("readiness_state"))
        replay_state = _normalize_text(readiness_record.get("replay_state")) or _normalize_text(control_record.get("replay_state")) if isinstance(control_record, dict) else None
        migration_state = _normalize_text(readiness_record.get("migration_state")) or _normalize_text(migration_pack.get("readiness_state")) if isinstance(migration_pack, dict) else None
        allowed_actions = _normalize_list(control_record.get("allowed_actions")) if isinstance(control_record, dict) else []
        reasons: list[str] = []

        if not source_key:
            reasons.append("missing_source_key")
        if lineage_record is None:
            reasons.append("missing_durable_lineage")
        if control_record is None:
            reasons.append("missing_replay_control")
        if migration_pack is None:
            reasons.append("missing_migration_pack")
        if raw_record is None:
            reasons.append("missing_raw_record")
        if normalized_record is None:
            reasons.append("missing_normalized_record")
        if readiness_reviews.get(source_key or ""):
            reasons.append("readiness_review_required")
        if readiness_state == "blocked-review":
            reasons.append("source_blocked_review")
        if not allowed_actions:
            reasons.append("missing_allowed_actions")
        if isinstance(control_record, dict):
            if not _normalize_text(control_record.get("replay_key")):
                reasons.append("missing_replay_key")
            if not _normalize_text(control_record.get("idempotency_key")):
                reasons.append("missing_idempotency_key")

        if reasons:
            review_queue.append(
                redact_sensitive_fields(
                    {
                        "schema_version": SOURCE_REPLAY_PLAN_SCHEMA_VERSION,
                        "review_item_id": f"source-replay-plan-review-{_stable_digest({'source_key': source_key, 'reasons': reasons})[:24]}",
                        "source_key": source_key,
                        "state": "open",
                        "priority": "high" if "source_blocked_review" in reasons else "medium",
                        "review_type": "source-replay-plan",
                        "reason_codes": reasons,
                        "readiness": redact_sensitive_fields(readiness_record),
                    }
                )
            )
            continue

        replay_mode, replay_goal, stage_window = _derive_replay_mode(readiness_state, replay_state, migration_state)
        replay_mode_counts[replay_mode] = replay_mode_counts.get(replay_mode, 0) + 1
        readiness_state_counts[readiness_state or "unknown"] = readiness_state_counts.get(readiness_state or "unknown", 0) + 1
        migration_state_counts[migration_state or "unknown"] = migration_state_counts.get(migration_state or "unknown", 0) + 1

        guardrails = [
            "offline-derived-plan-only",
            "idempotency-key-required",
            "no-live-write-without-explicit-operator-approval",
        ]
        if replay_mode == "compare-only":
            guardrails.append("apply-prohibited-until-compare-clears")
        if replay_mode == "resume-from-approved":
            guardrails.append("resume-only-from-approved-delta")
        if replay_mode == "full-replay":
            guardrails.append("rebuild-from-source-control-lineage")

        plan_payload = {
            "schema_version": SOURCE_REPLAY_PLAN_SCHEMA_VERSION,
            "source_replay_plan_id": f"replay-plan-{_stable_digest({'source_key': source_key, 'mode': replay_mode, 'goal': replay_goal})[:24]}",
            "source_key": source_key,
            "durable_lineage_id": _normalize_text(lineage_record.get("durable_lineage_id")) if isinstance(lineage_record, dict) else None,
            "replay_safe_ingestion_control_id": _normalize_text(control_record.get("replay_safe_ingestion_control_id")) if isinstance(control_record, dict) else None,
            "lineage_replay_readiness_id": _normalize_text(readiness_record.get("lineage_replay_readiness_id")),
            "migration_pack_id": _normalize_text(migration_pack.get("migration_pack_id")) if isinstance(migration_pack, dict) else None,
            "replay_key": _normalize_text(control_record.get("replay_key")) if isinstance(control_record, dict) else None,
            "idempotency_key": _normalize_text(control_record.get("idempotency_key")) if isinstance(control_record, dict) else None,
            "plan_state": "planned",
            "readiness_state": readiness_state,
            "replay_state": replay_state,
            "migration_state": migration_state,
            "replay_mode": replay_mode,
            "replay_goal": replay_goal,
            "planned_stage_window": stage_window,
            "operator_actions_allowed": allowed_actions,
            "guardrails": guardrails,
            "source_summary": redact_sensitive_fields(
                {
                    "source_system": _normalize_text(migration_pack.get("source_system")) if isinstance(migration_pack, dict) else None,
                    "source_entity_type": _normalize_text(migration_pack.get("source_entity_type")) if isinstance(migration_pack, dict) else None,
                    "migration_profile": _normalize_text(migration_pack.get("migration_profile")) if isinstance(migration_pack, dict) else None,
                    "content_family": _normalize_text(migration_pack.get("content_family")) if isinstance(migration_pack, dict) else None,
                }
            ),
            "lineage_refs": redact_sensitive_fields(
                {
                    "raw_record_id": _normalize_text(raw_record.get("raw_record_id")) if isinstance(raw_record, dict) else None,
                    "normalized_record_id": _normalize_text(normalized_record.get("normalized_record_id")) if isinstance(normalized_record, dict) else None,
                    "approved_delta_id": _normalize_text(approved_delta.get("approved_delta_id")) if isinstance(approved_delta, dict) else None,
                    "applied_state_transition_id": _normalize_text(applied_transition.get("applied_state_transition_id")) if isinstance(applied_transition, dict) else None,
                    "durable_entity_id": _normalize_text(lineage_record.get("durable_entity_id")) if isinstance(lineage_record, dict) else None,
                }
            ),
        }
        plan_packs.append(redact_sensitive_fields(plan_payload))

    return {
        "source_replay_plan_packs": {
            "schema_version": SOURCE_REPLAY_PLAN_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(plan_packs),
            "records": plan_packs,
        },
        "source_replay_plan_review_queue": {
            "schema_version": SOURCE_REPLAY_PLAN_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(review_queue),
            "records": review_queue,
        },
        "source_replay_plan_rollup": {
            "schema_version": SOURCE_REPLAY_PLAN_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "replay_plan_count": len(plan_packs),
            "review_item_count": len(review_queue),
            "replay_mode_counts": replay_mode_counts,
            "readiness_state_counts": readiness_state_counts,
            "migration_state_counts": migration_state_counts,
        },
    }


def write_json_artifacts(out_dir: str | Path, artifacts: dict[str, dict]) -> None:
    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)
    filenames = {
        "source_replay_plan_packs": "source_replay_plan_packs.json",
        "source_replay_plan_review_queue": "source_replay_plan_review_queue.json",
        "source_replay_plan_rollup": "source_replay_plan_rollup.json",
    }
    for key, filename in filenames.items():
        if key not in artifacts:
            continue
        (path / filename).write_text(json.dumps(artifacts[key], indent=2, sort_keys=True) + "\n", encoding="utf-8")


__all__ = [
    "SOURCE_REPLAY_PLAN_SCHEMA_VERSION",
    "build_source_replay_plan_artifacts",
    "load_control_documents",
    "load_lineage_documents",
    "load_migration_documents",
    "load_readiness_documents",
    "load_source_control_pipeline_documents",
    "write_json_artifacts",
]
