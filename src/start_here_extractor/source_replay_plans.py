from __future__ import annotations

import json
from pathlib import Path

from .durable_lineage_replay import (
    DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION,
    _normalize_text,
    _record_map,
    _records_by_source_key,
    _stable_digest,
    utcnow_iso,
)
from .security import redact_sensitive_fields

SOURCE_REPLAY_PLAN_SCHEMA_VERSION = DURABLE_LINEAGE_REPLAY_SCHEMA_VERSION

_MODE_CONFIG = {
    "compare-only": {
        "resume_from_stage": "applied",
        "planned_actions": ["replay-compare"],
        "compare_first": True,
        "write_constraint": "no-downstream-writes",
    },
    "resume-from-approved": {
        "resume_from_stage": "approved",
        "planned_actions": ["replay-resume", "replay-compare"],
        "compare_first": False,
        "write_constraint": "offline-approved-resume-only",
    },
    "full-replay": {
        "resume_from_stage": "raw",
        "planned_actions": ["replay-full", "replay-compare"],
        "compare_first": False,
        "write_constraint": "offline-derived-only",
    },
}


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


def _choose_replay_mode(
    readiness_state: str | None,
    replay_state: str | None,
    migration_state: str | None,
) -> str | None:
    if readiness_state == "blocked-review":
        return None
    if (
        readiness_state == "protected-ready"
        or replay_state == "replay-protected"
        or migration_state == "already-applied"
    ):
        return "compare-only"
    if migration_state == "ready-for-apply":
        return "resume-from-approved"
    if readiness_state == "ready-for-replay":
        return "full-replay"
    return None


def _review_priority(reason_codes: list[str]) -> str:
    urgent = {
        "blocked_for_replay_planning",
        "missing_replay_control",
        "missing_durable_lineage",
        "missing_migration_pack",
        "unrecognized_replay_mode",
        "upstream_readiness_review_required",
    }
    return "high" if any(code in urgent for code in reason_codes) else "medium"


def build_source_replay_plan_artifacts(
    *args: dict[str, dict],
    readiness_documents: dict[str, dict] | None = None,
    control_documents: dict[str, dict] | None = None,
    lineage_documents: dict[str, dict] | None = None,
    migration_documents: dict[str, dict] | None = None,
) -> dict[str, dict]:
    if args:
        if len(args) == 5:
            _, migration_documents, lineage_documents, control_documents, readiness_documents = args
        elif len(args) == 4:
            readiness_documents, control_documents, lineage_documents, migration_documents = args
        else:
            raise TypeError(
                "build_source_replay_plan_artifacts expected 4 document arguments, or "
                "5 positional arguments in pipeline/migration/lineage/control/readiness order"
            )

    if (
        readiness_documents is None
        or control_documents is None
        or lineage_documents is None
        or migration_documents is None
    ):
        raise TypeError(
            "build_source_replay_plan_artifacts requires readiness, control, lineage, and migration documents"
        )

    readiness_records = readiness_documents.get("lineage_replay_readiness_packs", {}).get("records")
    readiness_records = readiness_records if isinstance(readiness_records, list) else []

    readiness_review_map = _records_by_source_key(
        readiness_documents.get("lineage_replay_readiness_review_queue", {})
    )
    control_map = _record_map(
        control_documents.get("replay_safe_ingestion_controls", {}), "source_key"
    )
    control_review_map = _records_by_source_key(
        control_documents.get("replay_safe_ingestion_review_queue", {})
    )
    lineage_map = _record_map(lineage_documents.get("durable_lineage_packs", {}), "source_key")
    lineage_review_map = _records_by_source_key(
        lineage_documents.get("durable_lineage_review_queue", {})
    )
    migration_map = _record_map(migration_documents.get("migration_packs", {}), "source_key")
    migration_review_map = _records_by_source_key(
        migration_documents.get("migration_review_queue", {})
    )

    replay_plans: list[dict] = []
    review_queue: list[dict] = []
    replay_mode_counts: dict[str, int] = {}
    readiness_state_counts: dict[str, int] = {}
    source_system_counts: dict[str, int] = {}

    for index, readiness_record in enumerate(readiness_records, start=1):
        if not isinstance(readiness_record, dict):
            continue

        source_key = _normalize_text(readiness_record.get("source_key"))
        source_ref = source_key or f"missing-source-{index}"

        control = control_map.get(source_key or "")
        lineage = lineage_map.get(source_key or "")
        migration_pack = migration_map.get(source_key or "")

        readiness_state = _normalize_text(readiness_record.get("readiness_state")) or "unknown"
        replay_state = _normalize_text(readiness_record.get("replay_state"))
        if replay_state is None and isinstance(control, dict):
            replay_state = _normalize_text(control.get("replay_state"))
        replay_state = replay_state or "unknown"

        migration_state = _normalize_text(readiness_record.get("migration_state"))
        if migration_state is None and isinstance(migration_pack, dict):
            migration_state = _normalize_text(migration_pack.get("readiness_state"))
        migration_state = migration_state or "unknown"

        reasons: list[str] = []
        if source_key is None:
            reasons.append("missing_source_key")
        if control is None:
            reasons.append("missing_replay_control")
        if lineage is None:
            reasons.append("missing_durable_lineage")
        if migration_pack is None:
            reasons.append("missing_migration_pack")
        if readiness_review_map.get(source_key or ""):
            reasons.append("upstream_readiness_review_required")
        if control_review_map.get(source_key or ""):
            reasons.append("upstream_control_review_required")
        if lineage_review_map.get(source_key or ""):
            reasons.append("upstream_lineage_review_required")
        if migration_review_map.get(source_key or ""):
            reasons.append("upstream_migration_review_required")
        if readiness_state == "blocked-review":
            reasons.append("blocked_for_replay_planning")

        replay_mode = _choose_replay_mode(readiness_state, replay_state, migration_state)
        if replay_mode is None and "blocked_for_replay_planning" not in reasons:
            reasons.append("unrecognized_replay_mode")

        if reasons:
            review_queue.append(
                redact_sensitive_fields(
                    {
                        "schema_version": SOURCE_REPLAY_PLAN_SCHEMA_VERSION,
                        "review_item_id": f"source-replay-plan-review-{_stable_digest({'source_key': source_ref, 'reasons': reasons})[:24]}",
                        "source_key": source_key,
                        "state": "open",
                        "priority": _review_priority(reasons),
                        "review_type": "source-replay-plan",
                        "reason_codes": reasons,
                        "readiness": {
                            "lineage_replay_readiness_id": _normalize_text(
                                readiness_record.get("lineage_replay_readiness_id")
                            ),
                            "readiness_state": readiness_state,
                            "replay_state": replay_state,
                            "migration_state": migration_state,
                        },
                        "control_summary": redact_sensitive_fields(
                            {
                                "replay_safe_ingestion_control_id": _normalize_text(
                                    control.get("replay_safe_ingestion_control_id")
                                ) if isinstance(control, dict) else None,
                                "replay_key": _normalize_text(control.get("replay_key")) if isinstance(control, dict) else None,
                                "idempotency_key": _normalize_text(control.get("idempotency_key")) if isinstance(control, dict) else None,
                            }
                        ),
                        "lineage_summary": redact_sensitive_fields(
                            {
                                "durable_lineage_id": _normalize_text(lineage.get("durable_lineage_id")) if isinstance(lineage, dict) else None,
                                "durable_entity_id": _normalize_text(lineage.get("durable_entity_id")) if isinstance(lineage, dict) else None,
                            }
                        ),
                        "migration_summary": redact_sensitive_fields(
                            {
                                "migration_pack_id": _normalize_text(migration_pack.get("migration_pack_id")) if isinstance(migration_pack, dict) else None,
                                "migration_profile": _normalize_text(migration_pack.get("migration_profile")) if isinstance(migration_pack, dict) else None,
                                "migration_state": migration_state,
                            }
                        ),
                    }
                )
            )
            continue

        config = _MODE_CONFIG[replay_mode]
        durable_lineage_id = _normalize_text(lineage.get("durable_lineage_id")) if isinstance(lineage, dict) else None
        replay_control_id = _normalize_text(control.get("replay_safe_ingestion_control_id")) if isinstance(control, dict) else None
        replay_key = (
            _normalize_text(control.get("replay_key")) if isinstance(control, dict) else None
        ) or (_normalize_text(lineage.get("replay_key")) if isinstance(lineage, dict) else None)
        idempotency_key = _normalize_text(control.get("idempotency_key")) if isinstance(control, dict) else None
        migration_pack_id = _normalize_text(migration_pack.get("migration_pack_id")) if isinstance(migration_pack, dict) else None
        source_system = (
            _normalize_text(lineage.get("source_system")) if isinstance(lineage, dict) else None
        ) or (
            _normalize_text(migration_pack.get("source_system")) if isinstance(migration_pack, dict) else None
        ) or "unknown"
        source_entity_type = (
            _normalize_text(lineage.get("source_entity_type")) if isinstance(lineage, dict) else None
        ) or (
            _normalize_text(migration_pack.get("source_entity_type")) if isinstance(migration_pack, dict) else None
        ) or "unknown"
        migration_profile = (
            _normalize_text(lineage.get("migration_profile")) if isinstance(lineage, dict) else None
        ) or (
            _normalize_text(migration_pack.get("migration_profile")) if isinstance(migration_pack, dict) else None
        ) or "unknown"

        replay_mode_counts[replay_mode] = replay_mode_counts.get(replay_mode, 0) + 1
        readiness_state_counts[readiness_state] = readiness_state_counts.get(readiness_state, 0) + 1
        source_system_counts[source_system] = source_system_counts.get(source_system, 0) + 1

        replay_plans.append(
            redact_sensitive_fields(
                {
                    "schema_version": SOURCE_REPLAY_PLAN_SCHEMA_VERSION,
                    "source_replay_plan_id": f"source-replay-plan-{_stable_digest({'source_key': source_key, 'replay_mode': replay_mode, 'replay_key': replay_key})[:24]}",
                    "source_key": source_key,
                    "source_system": source_system,
                    "source_entity_type": source_entity_type,
                    "migration_profile": migration_profile,
                    "durable_entity_id": _normalize_text(lineage.get("durable_entity_id")) if isinstance(lineage, dict) else None,
                    "durable_lineage_id": durable_lineage_id,
                    "lineage_replay_readiness_id": _normalize_text(readiness_record.get("lineage_replay_readiness_id")),
                    "replay_safe_ingestion_control_id": replay_control_id,
                    "migration_pack_id": migration_pack_id,
                    "replay_key": replay_key,
                    "idempotency_key": idempotency_key,
                    "readiness_state": readiness_state,
                    "replay_state": replay_state,
                    "migration_state": migration_state,
                    "replay_mode": replay_mode,
                    "resume_from_stage": config["resume_from_stage"],
                    "planned_actions": config["planned_actions"],
                    "compare_first": config["compare_first"],
                    "downstream_write_allowed": False,
                    "write_constraint": config["write_constraint"],
                    "provenance_refs": {
                        "durable_lineage_id": durable_lineage_id,
                        "replay_safe_ingestion_control_id": replay_control_id,
                        "lineage_replay_readiness_id": _normalize_text(
                            readiness_record.get("lineage_replay_readiness_id")
                        ),
                        "migration_pack_id": migration_pack_id,
                    },
                }
            )
        )

    return {
        "source_replay_plan_packs": {
            "schema_version": SOURCE_REPLAY_PLAN_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(replay_plans),
            "records": replay_plans,
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
            "replay_plan_count": len(replay_plans),
            "review_item_count": len(review_queue),
            "replay_mode_counts": replay_mode_counts,
            "planned_readiness_state_counts": readiness_state_counts,
            "source_system_counts": source_system_counts,
        },
    }


def write_source_replay_plan_artifacts(out_dir: str | Path, artifacts: dict[str, dict]) -> None:
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
        (path / filename).write_text(
            json.dumps(artifacts[key], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
