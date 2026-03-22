
from __future__ import annotations

import json
from pathlib import Path

from .durable_lineage_replay import (
    _normalize_text,
    _record_map,
    _records_by_source_key,
    _stable_digest,
    utcnow_iso,
)
from .security import redact_sensitive_fields
from .source_replay_plans import (
    SOURCE_REPLAY_PLAN_SCHEMA_VERSION,
)

SOURCE_REPLAY_COMPARE_SCHEMA_VERSION = SOURCE_REPLAY_PLAN_SCHEMA_VERSION

_SCOPE_BY_MODE = {
    "compare-only": "applied-state-vs-protected-lineage",
    "resume-from-approved": "approved-state-vs-apply-ready",
    "full-replay": "raw-state-vs-review-ready",
}

_TRANSITION_BY_MODE = {
    "compare-only": "compare-existing-state",
    "resume-from-approved": "resume-approved-state",
    "full-replay": "full-replay-derivation",
}


def load_plan_documents(plan_dir: str | Path) -> dict[str, dict]:
    path = Path(plan_dir)
    names = {
        "source_replay_plan_packs": "source_replay_plan_packs.json",
        "source_replay_plan_review_queue": "source_replay_plan_review_queue.json",
        "source_replay_plan_rollup": "source_replay_plan_rollup.json",
    }
    payloads: dict[str, dict] = {}
    for key, filename in names.items():
        file_path = path / filename
        if file_path.exists():
            payloads[key] = json.loads(file_path.read_text(encoding="utf-8"))
        else:
            payloads[key] = {"records": []}
    return payloads



def load_compare_documents(compare_dir: str | Path) -> dict[str, dict]:
    path = Path(compare_dir)
    names = {
        "source_replay_compare_packs": "source_replay_compare_packs.json",
        "source_replay_compare_review_queue": "source_replay_compare_review_queue.json",
        "source_replay_compare_rollup": "source_replay_compare_rollup.json",
    }
    payloads: dict[str, dict] = {}
    for key, filename in names.items():
        file_path = path / filename
        if file_path.exists():
            payloads[key] = json.loads(file_path.read_text(encoding="utf-8"))
        else:
            payloads[key] = {"records": []}
    return payloads

def _review_priority(reason_codes: list[str]) -> str:
    urgent = {
        "missing_source_key",
        "missing_replay_plan",
        "missing_readiness_pack",
        "missing_replay_control",
        "missing_durable_lineage",
        "missing_migration_pack",
        "upstream_replay_plan_review_required",
        "unrecognized_replay_mode",
    }
    return "high" if any(code in urgent for code in reason_codes) else "medium"


def _append_unique(target: list[str], value: str) -> None:
    if value not in target:
        target.append(value)


def _comparison_for_mode(
    replay_mode: str | None,
    readiness_state: str | None,
    replay_state: str | None,
    migration_state: str | None,
) -> tuple[str, dict]:
    readiness_state = readiness_state or "unknown"
    replay_state = replay_state or "unknown"
    migration_state = migration_state or "unknown"
    replay_mode = replay_mode or "unknown"

    if replay_mode == "compare-only":
        checks = {
            "readiness_protected": readiness_state == "protected-ready",
            "replay_protected": replay_state == "replay-protected",
            "migration_already_applied": migration_state == "already-applied",
        }
        satisfied = [key for key, matched in checks.items() if matched]
        unsatisfied = [key for key, matched in checks.items() if not matched]
        if satisfied:
            return "stable-match", {
                "comparison_requires_review": False,
                "comparison_message": "Protected or already-applied upstream state still supports compare-only replay.",
                "satisfied_conditions": satisfied,
                "unsatisfied_conditions": unsatisfied,
            }
        return "upstream-state-drift", {
            "comparison_requires_review": True,
            "comparison_message": "Compare-only replay no longer matches protected or already-applied upstream state.",
            "satisfied_conditions": satisfied,
            "unsatisfied_conditions": unsatisfied,
        }

    if replay_mode == "resume-from-approved":
        checks = {
            "migration_ready_for_apply": migration_state == "ready-for-apply",
            "replay_safe": replay_state in {"replay-safe", "replay-protected"},
        }
        satisfied = [key for key, matched in checks.items() if matched]
        unsatisfied = [key for key, matched in checks.items() if not matched]
        if checks["migration_ready_for_apply"] and checks["replay_safe"]:
            return "resume-required", {
                "comparison_requires_review": False,
                "comparison_message": "Approved replay can resume from the apply-ready state.",
                "satisfied_conditions": satisfied,
                "unsatisfied_conditions": unsatisfied,
            }
        return "upstream-state-drift", {
            "comparison_requires_review": True,
            "comparison_message": "Resume-from-approved replay no longer matches the apply-ready upstream state.",
            "satisfied_conditions": satisfied,
            "unsatisfied_conditions": unsatisfied,
        }

    if replay_mode == "full-replay":
        checks = {
            "readiness_ready_for_replay": readiness_state == "ready-for-replay",
            "migration_ready_for_review": migration_state == "ready-for-review",
            "replay_safe": replay_state in {"replay-safe", "replay-protected"},
        }
        satisfied = [key for key, matched in checks.items() if matched]
        unsatisfied = [key for key, matched in checks.items() if not matched]
        if (
            checks["readiness_ready_for_replay"]
            and checks["migration_ready_for_review"]
            and checks["replay_safe"]
        ):
            return "full-replay-required", {
                "comparison_requires_review": False,
                "comparison_message": "Full replay remains required from the replay-ready upstream state.",
                "satisfied_conditions": satisfied,
                "unsatisfied_conditions": unsatisfied,
            }
        return "upstream-state-drift", {
            "comparison_requires_review": True,
            "comparison_message": "Full-replay plan no longer matches the replay-ready upstream state.",
            "satisfied_conditions": satisfied,
            "unsatisfied_conditions": unsatisfied,
        }

    return "unrecognized-replay-mode", {
        "comparison_requires_review": True,
        "comparison_message": "Replay mode could not be mapped to a supported comparison flow.",
        "satisfied_conditions": [],
        "unsatisfied_conditions": ["replay_mode"],
    }


def build_source_replay_compare_artifacts(
    *args: dict[str, dict],
    plan_documents: dict[str, dict] | None = None,
    readiness_documents: dict[str, dict] | None = None,
    control_documents: dict[str, dict] | None = None,
    lineage_documents: dict[str, dict] | None = None,
    migration_documents: dict[str, dict] | None = None,
) -> dict[str, dict]:
    if args:
        if len(args) == 6:
            (
                _,
                migration_documents,
                lineage_documents,
                control_documents,
                readiness_documents,
                plan_documents,
            ) = args
        elif len(args) == 5:
            (
                plan_documents,
                readiness_documents,
                control_documents,
                lineage_documents,
                migration_documents,
            ) = args
        else:
            raise TypeError(
                "build_source_replay_compare_artifacts expected 5 document arguments, or "
                "6 positional arguments in pipeline/migration/lineage/control/readiness/plan order"
            )

    if (
        plan_documents is None
        or readiness_documents is None
        or control_documents is None
        or lineage_documents is None
        or migration_documents is None
    ):
        raise TypeError(
            "build_source_replay_compare_artifacts requires plan, readiness, control, lineage, and migration documents"
        )

    plan_records = plan_documents.get("source_replay_plan_packs", {}).get("records")
    plan_records = plan_records if isinstance(plan_records, list) else []
    plan_review_records = plan_documents.get("source_replay_plan_review_queue", {}).get("records")
    plan_review_records = plan_review_records if isinstance(plan_review_records, list) else []

    plan_review_map = _records_by_source_key(plan_documents.get("source_replay_plan_review_queue", {}))
    readiness_map = _record_map(readiness_documents.get("lineage_replay_readiness_packs", {}), "source_key")
    readiness_review_map = _records_by_source_key(
        readiness_documents.get("lineage_replay_readiness_review_queue", {})
    )
    control_map = _record_map(control_documents.get("replay_safe_ingestion_controls", {}), "source_key")
    control_review_map = _records_by_source_key(
        control_documents.get("replay_safe_ingestion_review_queue", {})
    )
    lineage_map = _record_map(lineage_documents.get("durable_lineage_packs", {}), "source_key")
    lineage_review_map = _records_by_source_key(lineage_documents.get("durable_lineage_review_queue", {}))
    migration_map = _record_map(migration_documents.get("migration_packs", {}), "source_key")
    migration_review_map = _records_by_source_key(migration_documents.get("migration_review_queue", {}))

    comparison_packs: list[dict] = []
    review_queue: list[dict] = []
    comparison_outcome_counts: dict[str, int] = {}
    replay_mode_counts: dict[str, int] = {}
    source_system_counts: dict[str, int] = {}

    for item in plan_review_records:
        if not isinstance(item, dict):
            continue
        source_key = _normalize_text(item.get("source_key"))
        source_ref = source_key or _normalize_text(item.get("review_item_id")) or "missing-source"
        reason_codes = list(item.get("reason_codes") or [])
        _append_unique(reason_codes, "upstream_replay_plan_review_required")
        review_queue.append(
            redact_sensitive_fields(
                {
                    "schema_version": SOURCE_REPLAY_COMPARE_SCHEMA_VERSION,
                    "review_item_id": f"source-replay-compare-review-{_stable_digest({'source_key': source_ref, 'reason_codes': reason_codes})[:24]}",
                    "source_key": source_key,
                    "state": "open",
                    "priority": _review_priority(reason_codes),
                    "review_type": "source-replay-compare",
                    "reason_codes": reason_codes,
                    "plan_summary": redact_sensitive_fields(item),
                }
            )
        )

    for index, plan_record in enumerate(plan_records, start=1):
        if not isinstance(plan_record, dict):
            continue

        source_key = _normalize_text(plan_record.get("source_key"))
        source_ref = source_key or f"missing-source-{index}"

        readiness = readiness_map.get(source_key or "")
        control = control_map.get(source_key or "")
        lineage = lineage_map.get(source_key or "")
        migration = migration_map.get(source_key or "")

        reasons: list[str] = []
        if source_key is None:
            reasons.append("missing_source_key")
        if readiness is None:
            reasons.append("missing_readiness_pack")
        if control is None:
            reasons.append("missing_replay_control")
        if lineage is None:
            reasons.append("missing_durable_lineage")
        if migration is None:
            reasons.append("missing_migration_pack")
        if plan_review_map.get(source_key or ""):
            reasons.append("upstream_replay_plan_review_required")
        if readiness_review_map.get(source_key or ""):
            reasons.append("upstream_readiness_review_required")
        if control_review_map.get(source_key or ""):
            reasons.append("upstream_control_review_required")
        if lineage_review_map.get(source_key or ""):
            reasons.append("upstream_lineage_review_required")
        if migration_review_map.get(source_key or ""):
            reasons.append("upstream_migration_review_required")

        if reasons:
            review_queue.append(
                redact_sensitive_fields(
                    {
                        "schema_version": SOURCE_REPLAY_COMPARE_SCHEMA_VERSION,
                        "review_item_id": f"source-replay-compare-review-{_stable_digest({'source_key': source_ref, 'reason_codes': reasons})[:24]}",
                        "source_key": source_key,
                        "state": "open",
                        "priority": _review_priority(reasons),
                        "review_type": "source-replay-compare",
                        "reason_codes": reasons,
                        "plan_summary": redact_sensitive_fields(
                            {
                                "source_replay_plan_id": _normalize_text(plan_record.get("source_replay_plan_id")),
                                "replay_mode": _normalize_text(plan_record.get("replay_mode")),
                                "replay_key": _normalize_text(plan_record.get("replay_key")),
                                "idempotency_key": _normalize_text(plan_record.get("idempotency_key")),
                            }
                        ),
                    }
                )
            )
            continue

        replay_mode = _normalize_text(plan_record.get("replay_mode")) or "unknown"
        source_system = (
            _normalize_text(plan_record.get("source_system"))
            or _normalize_text(lineage.get("source_system")) if isinstance(lineage, dict) else None
        ) or (
            _normalize_text(migration.get("source_system")) if isinstance(migration, dict) else None
        ) or "unknown"
        source_entity_type = (
            _normalize_text(plan_record.get("source_entity_type"))
            or _normalize_text(lineage.get("source_entity_type")) if isinstance(lineage, dict) else None
        ) or (
            _normalize_text(migration.get("source_entity_type")) if isinstance(migration, dict) else None
        ) or "unknown"
        migration_profile = (
            _normalize_text(plan_record.get("migration_profile"))
            or _normalize_text(lineage.get("migration_profile")) if isinstance(lineage, dict) else None
        ) or (
            _normalize_text(migration.get("migration_profile")) if isinstance(migration, dict) else None
        ) or "unknown"

        readiness_state = (
            _normalize_text(readiness.get("readiness_state")) if isinstance(readiness, dict) else None
        ) or _normalize_text(plan_record.get("readiness_state")) or "unknown"

        replay_state = (
            _normalize_text(control.get("replay_state")) if isinstance(control, dict) else None
        ) or _normalize_text(plan_record.get("replay_state")) or "unknown"

        migration_state = (
            _normalize_text(migration.get("readiness_state")) if isinstance(migration, dict) else None
        ) or _normalize_text(plan_record.get("migration_state")) or "unknown"

        comparison_outcome, comparison_summary = _comparison_for_mode(
            replay_mode,
            readiness_state,
            replay_state,
            migration_state,
        )

        pack = redact_sensitive_fields(
            {
                "schema_version": SOURCE_REPLAY_COMPARE_SCHEMA_VERSION,
                "source_replay_compare_id": f"source-replay-compare-{_stable_digest({'source_key': source_key, 'replay_mode': replay_mode, 'comparison_outcome': comparison_outcome})[:24]}",
                "source_replay_plan_id": _normalize_text(plan_record.get("source_replay_plan_id")),
                "source_key": source_key,
                "source_system": source_system,
                "source_entity_type": source_entity_type,
                "migration_profile": migration_profile,
                "replay_mode": replay_mode,
                "comparison_scope": _SCOPE_BY_MODE.get(replay_mode, "unknown"),
                "planned_transition": _TRANSITION_BY_MODE.get(replay_mode, "unknown"),
                "comparison_outcome": comparison_outcome,
                "comparison_requires_review": comparison_summary["comparison_requires_review"],
                "comparison_summary": comparison_summary,
                "upstream_state_snapshot": {
                    "readiness_state": readiness_state,
                    "replay_state": replay_state,
                    "migration_state": migration_state,
                },
                "expected_state_snapshot": {
                    "resume_from_stage": _normalize_text(plan_record.get("resume_from_stage")),
                    "planned_actions": plan_record.get("planned_actions") if isinstance(plan_record.get("planned_actions"), list) else [],
                    "compare_first": bool(plan_record.get("compare_first")),
                    "downstream_write_allowed": bool(plan_record.get("downstream_write_allowed")),
                    "write_constraint": _normalize_text(plan_record.get("write_constraint")),
                },
                "provenance_refs": redact_sensitive_fields(
                    plan_record.get("provenance_refs") if isinstance(plan_record.get("provenance_refs"), dict) else {}
                ),
            }
        )
        comparison_packs.append(pack)

        comparison_outcome_counts[comparison_outcome] = comparison_outcome_counts.get(comparison_outcome, 0) + 1
        replay_mode_counts[replay_mode] = replay_mode_counts.get(replay_mode, 0) + 1
        source_system_counts[source_system] = source_system_counts.get(source_system, 0) + 1

        if comparison_summary["comparison_requires_review"]:
            review_queue.append(
                redact_sensitive_fields(
                    {
                        "schema_version": SOURCE_REPLAY_COMPARE_SCHEMA_VERSION,
                        "review_item_id": f"source-replay-compare-review-{_stable_digest({'source_key': source_ref, 'comparison_outcome': comparison_outcome})[:24]}",
                        "source_key": source_key,
                        "state": "open",
                        "priority": _review_priority(["comparison_requires_review"]),
                        "review_type": "source-replay-compare",
                        "reason_codes": ["comparison_requires_review"],
                        "comparison_summary": comparison_summary,
                        "plan_summary": {
                            "source_replay_plan_id": _normalize_text(plan_record.get("source_replay_plan_id")),
                            "replay_mode": replay_mode,
                            "replay_key": _normalize_text(plan_record.get("replay_key")),
                        },
                    }
                )
            )

    return {
        "source_replay_compare_packs": {
            "schema_version": SOURCE_REPLAY_COMPARE_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(comparison_packs),
            "records": comparison_packs,
        },
        "source_replay_compare_review_queue": {
            "schema_version": SOURCE_REPLAY_COMPARE_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(review_queue),
            "records": review_queue,
        },
        "source_replay_compare_rollup": {
            "schema_version": SOURCE_REPLAY_COMPARE_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "comparison_pack_count": len(comparison_packs),
            "review_item_count": len(review_queue),
            "comparison_outcome_counts": comparison_outcome_counts,
            "replay_mode_counts": replay_mode_counts,
            "source_system_counts": source_system_counts,
        },
    }


def write_source_replay_compare_artifacts(out_dir: str | Path, artifacts: dict[str, dict]) -> None:
    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)
    filenames = {
        "source_replay_compare_packs": "source_replay_compare_packs.json",
        "source_replay_compare_review_queue": "source_replay_compare_review_queue.json",
        "source_replay_compare_rollup": "source_replay_compare_rollup.json",
    }
    for key, filename in filenames.items():
        if key not in artifacts:
            continue
        (path / filename).write_text(
            json.dumps(artifacts[key], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
