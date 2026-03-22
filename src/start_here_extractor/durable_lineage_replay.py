from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .security import redact_sensitive_fields

DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION = "1.0"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _stable_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def load_source_control_pipeline_documents(pipeline_dir: str | Path) -> dict[str, dict]:
    path = Path(pipeline_dir)
    names = {
        "source_records_raw": "source_records_raw.json",
        "source_records_normalized": "source_records_normalized.json",
        "candidate_matches": "candidate_matches.json",
        "review_items": "review_items.json",
        "approved_deltas": "approved_deltas.json",
        "applied_state_transitions": "applied_state_transitions.json",
    }
    payloads: dict[str, dict] = {}
    for key, filename in names.items():
        file_path = path / filename
        if file_path.exists():
            payloads[key] = json.loads(file_path.read_text(encoding="utf-8"))
        else:
            payloads[key] = {"records": []}
    return payloads


def load_migration_documents(migration_dir: str | Path) -> dict[str, dict]:
    path = Path(migration_dir)
    names = {
        "migration_packs": "ringcentral_lacrm_migration_packs.json",
        "migration_review_queue": "ringcentral_lacrm_migration_review_queue.json",
        "rollup": "ringcentral_lacrm_migration_rollup.json",
    }
    payloads: dict[str, dict] = {}
    for key, filename in names.items():
        file_path = path / filename
        if file_path.exists():
            payloads[key] = json.loads(file_path.read_text(encoding="utf-8"))
        else:
            payloads[key] = {"records": []}
    return payloads


def load_lineage_documents(lineage_dir: str | Path) -> dict[str, dict]:
    path = Path(lineage_dir)
    names = {
        "durable_lineage_packs": "durable_lineage_packs.json",
        "durable_lineage_review_queue": "durable_lineage_review_queue.json",
        "durable_lineage_rollup": "durable_lineage_rollup.json",
    }
    payloads: dict[str, dict] = {}
    for key, filename in names.items():
        file_path = path / filename
        if file_path.exists():
            payloads[key] = json.loads(file_path.read_text(encoding="utf-8"))
        else:
            payloads[key] = {"records": []}
    return payloads


def load_control_documents(control_dir: str | Path) -> dict[str, dict]:
    path = Path(control_dir)
    names = {
        "replay_safe_ingestion_controls": "replay_safe_ingestion_controls.json",
        "replay_safe_ingestion_review_queue": "replay_safe_ingestion_review_queue.json",
        "replay_safe_ingestion_rollup": "replay_safe_ingestion_rollup.json",
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


def build_durable_lineage_artifacts(pipeline_documents: dict[str, dict], migration_documents: dict[str, dict]) -> dict[str, dict]:
    raw_map = _record_map(pipeline_documents.get("source_records_raw", {}), "source_key")
    normalized_map = _record_map(pipeline_documents.get("source_records_normalized", {}), "source_key")
    migration_records = migration_documents.get("migration_packs", {}).get("records")
    migration_records = migration_records if isinstance(migration_records, list) else []
    migration_reviews = _records_by_source_key(migration_documents.get("migration_review_queue", {}))

    lineage_packs: list[dict] = []
    review_queue: list[dict] = []
    lineage_states: dict[str, int] = {}

    for migration_pack in migration_records:
        if not isinstance(migration_pack, dict):
            continue
        source_key = _normalize_text(migration_pack.get("source_key"))
        raw_record = raw_map.get(source_key or "")
        normalized_record = normalized_map.get(source_key or "")
        lineage = migration_pack.get("lineage") if isinstance(migration_pack.get("lineage"), dict) else {}
        source_summary = migration_pack.get("source_summary") if isinstance(migration_pack.get("source_summary"), dict) else {}
        reasons: list[str] = []
        if not source_key:
            reasons.append("missing_source_key")
        if not _normalize_text(lineage.get("normalized_record_id")):
            reasons.append("missing_normalized_record_id")
        if raw_record is None:
            reasons.append("missing_raw_record")
        if normalized_record is None:
            reasons.append("missing_normalized_record")

        durable_entity_payload = {
            "source_key": source_key,
            "source_system": _normalize_text(migration_pack.get("source_system")) or _normalize_text(source_summary.get("source_system")) or "unknown",
            "migration_profile": _normalize_text(migration_pack.get("migration_profile")) or "unknown",
            "source_entity_type": _normalize_text(migration_pack.get("source_entity_type")) or "unknown",
        }
        durable_entity_id = f"entity-{_stable_digest(durable_entity_payload)[:24]}"
        replay_key = f"replay-{_stable_digest({'source_key': source_key, 'migration_profile': durable_entity_payload['migration_profile']})[:24]}"

        if reasons:
            review_queue.append(
                redact_sensitive_fields(
                    {
                        "schema_version": DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION,
                        "review_item_id": f"lineage-review-{_stable_digest({'source_key': source_key, 'reasons': reasons})[:24]}",
                        "source_key": source_key,
                        "state": "open",
                        "priority": "high",
                        "review_type": "durable-lineage",
                        "reason_codes": reasons,
                        "migration_pack": redact_sensitive_fields(migration_pack),
                    }
                )
            )
            continue

        lineage_state = "lineage-established"
        lineage_states[lineage_state] = lineage_states.get(lineage_state, 0) + 1
        payload = {
            "schema_version": DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION,
            "durable_lineage_id": f"lineage-{_stable_digest({'source_key': source_key, 'entity': durable_entity_id})[:24]}",
            "source_key": source_key,
            "durable_entity_id": durable_entity_id,
            "replay_key": replay_key,
            "source_system": durable_entity_payload["source_system"],
            "source_entity_type": durable_entity_payload["source_entity_type"],
            "migration_profile": durable_entity_payload["migration_profile"],
            "lineage_state": lineage_state,
            "readiness_state": _normalize_text(migration_pack.get("readiness_state")) or "unknown",
            "raw_record_id": _normalize_text(lineage.get("raw_record_id")),
            "normalized_record_id": _normalize_text(lineage.get("normalized_record_id")),
            "approved_delta_id": _normalize_text(lineage.get("approved_delta_id")),
            "applied_state_transition_id": _normalize_text(lineage.get("applied_state_transition_id")),
            "migration_pack_id": _normalize_text(migration_pack.get("migration_pack_id")),
            "open_migration_review_count": len(migration_reviews.get(source_key or "", [])),
        }
        lineage_packs.append(redact_sensitive_fields(payload))

    return {
        "durable_lineage_packs": {
            "schema_version": DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(lineage_packs),
            "records": lineage_packs,
        },
        "durable_lineage_review_queue": {
            "schema_version": DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(review_queue),
            "records": review_queue,
        },
        "durable_lineage_rollup": {
            "schema_version": DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "durable_lineage_count": len(lineage_packs),
            "review_item_count": len(review_queue),
            "lineage_state_counts": lineage_states,
        },
    }


def build_replay_safe_ingestion_control_artifacts(lineage_documents: dict[str, dict], migration_documents: dict[str, dict]) -> dict[str, dict]:
    lineage_records = lineage_documents.get("durable_lineage_packs", {}).get("records")
    lineage_records = lineage_records if isinstance(lineage_records, list) else []
    lineage_review_map = _records_by_source_key(lineage_documents.get("durable_lineage_review_queue", {}))
    migration_map = _record_map(migration_documents.get("migration_packs", {}), "source_key")
    review_queue: list[dict] = []
    controls: list[dict] = []
    replay_states: dict[str, int] = {}
    seen_replay_keys: dict[str, str] = {}

    for lineage_record in lineage_records:
        if not isinstance(lineage_record, dict):
            continue
        source_key = _normalize_text(lineage_record.get("source_key"))
        replay_key = _normalize_text(lineage_record.get("replay_key"))
        reasons: list[str] = []
        migration_pack = migration_map.get(source_key or "")
        readiness_state = _normalize_text(migration_pack.get("readiness_state")) if isinstance(migration_pack, dict) else None
        if not replay_key:
            reasons.append("missing_replay_key")
        if replay_key and replay_key in seen_replay_keys and seen_replay_keys[replay_key] != source_key:
            reasons.append("duplicate_replay_key")
        if replay_key and replay_key not in seen_replay_keys:
            seen_replay_keys[replay_key] = source_key or replay_key
        if lineage_review_map.get(source_key or ""):
            reasons.append("lineage_review_required")

        if reasons:
            review_queue.append(
                redact_sensitive_fields(
                    {
                        "schema_version": DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION,
                        "review_item_id": f"replay-control-review-{_stable_digest({'source_key': source_key, 'reasons': reasons})[:24]}",
                        "source_key": source_key,
                        "state": "open",
                        "priority": "high",
                        "review_type": "replay-safe-ingestion",
                        "reason_codes": reasons,
                        "lineage": redact_sensitive_fields(lineage_record),
                    }
                )
            )
            continue

        replay_state = "replay-protected" if readiness_state == "already-applied" else "replay-safe"
        replay_states[replay_state] = replay_states.get(replay_state, 0) + 1
        controls.append(
            redact_sensitive_fields(
                {
                    "schema_version": DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION,
                    "replay_safe_ingestion_control_id": f"control-{_stable_digest({'source_key': source_key, 'replay_key': replay_key})[:24]}",
                    "source_key": source_key,
                    "durable_lineage_id": _normalize_text(lineage_record.get("durable_lineage_id")),
                    "replay_key": replay_key,
                    "idempotency_key": f"idem-{_stable_digest({'replay_key': replay_key, 'entity': lineage_record.get('durable_entity_id')})[:24]}",
                    "replay_state": replay_state,
                    "allowed_actions": ["replay-compare", "review"] if replay_state == "replay-protected" else ["review", "approve", "apply", "replay-compare"],
                    "readiness_state": readiness_state,
                }
            )
        )

    return {
        "replay_safe_ingestion_controls": {
            "schema_version": DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(controls),
            "records": controls,
        },
        "replay_safe_ingestion_review_queue": {
            "schema_version": DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(review_queue),
            "records": review_queue,
        },
        "replay_safe_ingestion_rollup": {
            "schema_version": DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "control_count": len(controls),
            "review_item_count": len(review_queue),
            "replay_state_counts": replay_states,
        },
    }


def build_lineage_replay_readiness_artifacts(lineage_documents: dict[str, dict], control_documents: dict[str, dict], migration_documents: dict[str, dict]) -> dict[str, dict]:
    lineage_records = lineage_documents.get("durable_lineage_packs", {}).get("records")
    lineage_records = lineage_records if isinstance(lineage_records, list) else []
    control_map = _record_map(control_documents.get("replay_safe_ingestion_controls", {}), "source_key")
    control_reviews = _records_by_source_key(control_documents.get("replay_safe_ingestion_review_queue", {}))
    migration_map = _record_map(migration_documents.get("migration_packs", {}), "source_key")
    readiness_records: list[dict] = []
    review_queue: list[dict] = []
    readiness_counts: dict[str, int] = {}

    for lineage_record in lineage_records:
        if not isinstance(lineage_record, dict):
            continue
        source_key = _normalize_text(lineage_record.get("source_key"))
        control = control_map.get(source_key or "")
        migration_pack = migration_map.get(source_key or "")
        reasons: list[str] = []
        if control is None:
            reasons.append("missing_replay_control")
        if migration_pack is None:
            reasons.append("missing_migration_pack")
        if control_reviews.get(source_key or ""):
            reasons.append("replay_review_required")

        migration_state = _normalize_text(migration_pack.get("readiness_state")) if isinstance(migration_pack, dict) else None
        replay_state = _normalize_text(control.get("replay_state")) if isinstance(control, dict) else None

        if reasons:
            review_queue.append(
                redact_sensitive_fields(
                    {
                        "schema_version": DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION,
                        "review_item_id": f"readiness-review-{_stable_digest({'source_key': source_key, 'reasons': reasons})[:24]}",
                        "source_key": source_key,
                        "state": "open",
                        "priority": "high",
                        "review_type": "lineage-replay-readiness",
                        "reason_codes": reasons,
                    }
                )
            )
            continue

        if migration_state == "blocked-review":
            readiness_state = "blocked-review"
        elif replay_state == "replay-protected":
            readiness_state = "protected-ready"
        else:
            readiness_state = "ready-for-replay"
        readiness_counts[readiness_state] = readiness_counts.get(readiness_state, 0) + 1
        readiness_records.append(
            redact_sensitive_fields(
                {
                    "schema_version": DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION,
                    "lineage_replay_readiness_id": f"readiness-{_stable_digest({'source_key': source_key, 'state': readiness_state})[:24]}",
                    "source_key": source_key,
                    "durable_lineage_id": _normalize_text(lineage_record.get("durable_lineage_id")),
                    "replay_safe_ingestion_control_id": _normalize_text(control.get("replay_safe_ingestion_control_id")),
                    "migration_pack_id": _normalize_text(migration_pack.get("migration_pack_id")),
                    "readiness_state": readiness_state,
                    "replay_state": replay_state,
                    "migration_state": migration_state,
                }
            )
        )

    return {
        "lineage_replay_readiness_packs": {
            "schema_version": DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(readiness_records),
            "records": readiness_records,
        },
        "lineage_replay_readiness_review_queue": {
            "schema_version": DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(review_queue),
            "records": review_queue,
        },
        "lineage_replay_readiness_rollup": {
            "schema_version": DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "readiness_pack_count": len(readiness_records),
            "review_item_count": len(review_queue),
            "readiness_state_counts": readiness_counts,
        },
    }


def write_json_artifacts(out_dir: str | Path, artifacts: dict[str, dict]) -> None:
    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)
    filenames = {
        "durable_lineage_packs": "durable_lineage_packs.json",
        "durable_lineage_review_queue": "durable_lineage_review_queue.json",
        "durable_lineage_rollup": "durable_lineage_rollup.json",
        "replay_safe_ingestion_controls": "replay_safe_ingestion_controls.json",
        "replay_safe_ingestion_review_queue": "replay_safe_ingestion_review_queue.json",
        "replay_safe_ingestion_rollup": "replay_safe_ingestion_rollup.json",
        "lineage_replay_readiness_packs": "lineage_replay_readiness_packs.json",
        "lineage_replay_readiness_review_queue": "lineage_replay_readiness_review_queue.json",
        "lineage_replay_readiness_rollup": "lineage_replay_readiness_rollup.json",
    }
    for key, filename in filenames.items():
        if key not in artifacts:
            continue
        (path / filename).write_text(json.dumps(artifacts[key], indent=2, sort_keys=True) + "\n", encoding="utf-8")
