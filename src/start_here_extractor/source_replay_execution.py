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
from .source_replay_approval import SOURCE_REPLAY_APPROVAL_SCHEMA_VERSION

SOURCE_REPLAY_EXECUTION_SCHEMA_VERSION = SOURCE_REPLAY_APPROVAL_SCHEMA_VERSION


def load_approval_documents(approval_dir: str | Path) -> dict[str, dict]:
    path = Path(approval_dir)
    queue_path = path / "source_replay_approval_queue.json"
    rollup_path = path / "source_replay_approval_rollup.json"
    journal_path = path / "source_replay_approval_journal.jsonl"

    queue_doc = (
        json.loads(queue_path.read_text(encoding="utf-8"))
        if queue_path.exists()
        else {"records": []}
    )
    rollup_doc = (
        json.loads(rollup_path.read_text(encoding="utf-8"))
        if rollup_path.exists()
        else {"records": []}
    )

    journal_records: list[dict] = []
    if journal_path.exists():
        for line in journal_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                journal_records.append(json.loads(line))

    return {
        "source_replay_approval_queue": queue_doc,
        "source_replay_approval_rollup": rollup_doc,
        "source_replay_approval_journal": {
            "schema_version": SOURCE_REPLAY_EXECUTION_SCHEMA_VERSION,
            "record_count": len(journal_records),
            "records": journal_records,
        },
    }


def _execution_priority(reason_codes: list[str]) -> str:
    urgent = {
        "missing_source_key",
        "missing_replay_approval",
        "missing_replay_compare",
        "missing_replay_plan",
        "missing_readiness_pack",
        "missing_replay_control",
        "missing_durable_lineage",
        "missing_migration_pack",
        "upstream_approval_review_required",
        "upstream_compare_review_required",
        "unrecognized_approval_decision",
    }
    return "high" if any(code in urgent for code in reason_codes) else "medium"


def _append_unique(target: list[str], value: str) -> None:
    if value not in target:
        target.append(value)


def _execution_policy(
    approval_decision: str | None,
    replay_mode: str | None,
    execution_gate: str | None,
) -> tuple[str, dict]:
    approval_decision = approval_decision or "unknown"
    replay_mode = replay_mode or "unknown"
    execution_gate = execution_gate or "unknown"

    if approval_decision == "approved-no-op-compare" or execution_gate == "no-execution-required":
        return "not-required", {
            "execution_requires_review": False,
            "execution_required": False,
            "execution_scope": "no-op-compare",
            "execution_transition": "record-approved-no-op",
            "execution_message": "Approved compare-only replay remains a no-op compare and requires no downstream execution.",
            "dry_run_supported": False,
            "dry_run_required": False,
            "downstream_write_allowed": False,
            "write_constraint": "no-downstream-execution-required",
        }

    if approval_decision == "approved-resume-replay" or (
        execution_gate == "execution-pack-eligible" and replay_mode == "resume-from-approved"
    ):
        return "ready-for-dry-run", {
            "execution_requires_review": False,
            "execution_required": True,
            "execution_scope": "resume-approved-state",
            "execution_transition": "resume-approved-state",
            "execution_message": "Approved resume replay is packaged and ready for a dry-run execution pass.",
            "dry_run_supported": True,
            "dry_run_required": True,
            "downstream_write_allowed": False,
            "write_constraint": "dry-run-only-until-operator-launch",
        }

    if approval_decision in {"approved-full-replay", "operator-approved-full-replay"} or (
        execution_gate == "execution-pack-eligible" and replay_mode == "full-replay"
    ):
        return "ready-for-dry-run", {
            "execution_requires_review": False,
            "execution_required": True,
            "execution_scope": "full-replay",
            "execution_transition": "full-replay",
            "execution_message": "Approved full replay is packaged and ready for a dry-run execution pass.",
            "dry_run_supported": True,
            "dry_run_required": True,
            "downstream_write_allowed": False,
            "write_constraint": "dry-run-only-until-operator-launch",
        }

    if approval_decision in {"rejected-full-replay", "rejected-replay", "rejected"}:
        return "not-required", {
            "execution_requires_review": False,
            "execution_required": False,
            "execution_scope": "rejected",
            "execution_transition": "rejected-no-execution",
            "execution_message": "Replay was rejected and no execution package will be prepared.",
            "dry_run_supported": False,
            "dry_run_required": False,
            "downstream_write_allowed": False,
            "write_constraint": "execution-blocked-by-rejection",
        }

    return "manual-review", {
        "execution_requires_review": True,
        "reason_codes": ["unrecognized_approval_decision"],
        "recommended_action": "operator-review-required",
        "execution_message": "Approval decision could not be mapped to an execution-pack rule.",
    }


def build_source_replay_execution_artifacts(
    *args: dict[str, dict],
    approval_documents: dict[str, dict] | None = None,
    compare_documents: dict[str, dict] | None = None,
    plan_documents: dict[str, dict] | None = None,
    readiness_documents: dict[str, dict] | None = None,
    control_documents: dict[str, dict] | None = None,
    lineage_documents: dict[str, dict] | None = None,
    migration_documents: dict[str, dict] | None = None,
) -> dict[str, dict]:
    if args:
        if len(args) == 8:
            (
                _,
                migration_documents,
                lineage_documents,
                control_documents,
                readiness_documents,
                plan_documents,
                compare_documents,
                approval_documents,
            ) = args
        elif len(args) == 7:
            (
                approval_documents,
                compare_documents,
                plan_documents,
                readiness_documents,
                control_documents,
                lineage_documents,
                migration_documents,
            ) = args
        else:
            raise TypeError(
                "build_source_replay_execution_artifacts expected 7 document arguments, or "
                "8 positional arguments in pipeline/migration/lineage/control/readiness/plan/compare/approval order"
            )

    if (
        approval_documents is None
        or compare_documents is None
        or plan_documents is None
        or readiness_documents is None
        or control_documents is None
        or lineage_documents is None
        or migration_documents is None
    ):
        raise TypeError(
            "build_source_replay_execution_artifacts requires approval, compare, plan, readiness, control, lineage, and migration documents"
        )

    approval_records = approval_documents.get("source_replay_approval_journal", {}).get("records")
    approval_records = approval_records if isinstance(approval_records, list) else []
    approval_queue_records = approval_documents.get("source_replay_approval_queue", {}).get("records")
    approval_queue_records = approval_queue_records if isinstance(approval_queue_records, list) else []

    compare_map = _record_map(compare_documents.get("source_replay_compare_packs", {}), "source_key")
    compare_review_map = _records_by_source_key(compare_documents.get("source_replay_compare_review_queue", {}))
    plan_map = _record_map(plan_documents.get("source_replay_plan_packs", {}), "source_key")
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

    execution_packs: list[dict] = []
    review_queue: list[dict] = []
    execution_status_counts: dict[str, int] = {}
    approval_decision_counts: dict[str, int] = {}
    replay_mode_counts: dict[str, int] = {}
    source_system_counts: dict[str, int] = {}
    comparison_outcome_counts: dict[str, int] = {}
    dry_run_ready_count = 0
    no_execution_required_count = 0

    for item in approval_queue_records:
        if not isinstance(item, dict):
            continue
        source_key = _normalize_text(item.get("source_key"))
        source_ref = source_key or _normalize_text(item.get("review_item_id")) or "missing-source"
        reason_codes = list(item.get("reason_codes") or [])
        _append_unique(reason_codes, "upstream_approval_review_required")
        review_queue.append(
            redact_sensitive_fields(
                {
                    "schema_version": SOURCE_REPLAY_EXECUTION_SCHEMA_VERSION,
                    "review_item_id": f"source-replay-execution-review-{_stable_digest({'source_key': source_ref, 'reason_codes': reason_codes})[:24]}",
                    "source_key": source_key,
                    "state": "open",
                    "priority": _execution_priority(reason_codes),
                    "review_type": "source-replay-execution",
                    "reason_codes": reason_codes,
                    "recommended_action": "resolve-approval-review-first",
                    "approval_review_summary": redact_sensitive_fields(item),
                }
            )
        )

    for index, approval_record in enumerate(approval_records, start=1):
        if not isinstance(approval_record, dict):
            continue

        source_key = _normalize_text(approval_record.get("source_key"))
        source_ref = source_key or f"missing-source-{index}"

        compare_record = compare_map.get(source_key or "")
        plan_record = plan_map.get(source_key or "")
        readiness_record = readiness_map.get(source_key or "")
        control_record = control_map.get(source_key or "")
        lineage_record = lineage_map.get(source_key or "")
        migration_record = migration_map.get(source_key or "")

        reason_codes: list[str] = []
        if source_key is None:
            reason_codes.append("missing_source_key")
        if compare_record is None:
            reason_codes.append("missing_replay_compare")
        if plan_record is None:
            reason_codes.append("missing_replay_plan")
        if readiness_record is None:
            reason_codes.append("missing_readiness_pack")
        if control_record is None:
            reason_codes.append("missing_replay_control")
        if lineage_record is None:
            reason_codes.append("missing_durable_lineage")
        if migration_record is None:
            reason_codes.append("missing_migration_pack")
        if compare_review_map.get(source_key or ""):
            reason_codes.append("upstream_compare_review_required")
        if plan_review_map.get(source_key or ""):
            reason_codes.append("upstream_replay_plan_review_required")
        if readiness_review_map.get(source_key or ""):
            reason_codes.append("upstream_readiness_review_required")
        if control_review_map.get(source_key or ""):
            reason_codes.append("upstream_control_review_required")
        if lineage_review_map.get(source_key or ""):
            reason_codes.append("upstream_lineage_review_required")
        if migration_review_map.get(source_key or ""):
            reason_codes.append("upstream_migration_review_required")

        replay_mode = (
            _normalize_text(approval_record.get("replay_mode"))
            or (_normalize_text(compare_record.get("replay_mode")) if isinstance(compare_record, dict) else None)
            or "unknown"
        )
        approval_decision = _normalize_text(approval_record.get("approval_decision")) or "unknown"
        comparison_outcome = (
            _normalize_text(approval_record.get("comparison_outcome"))
            or (_normalize_text(compare_record.get("comparison_outcome")) if isinstance(compare_record, dict) else None)
            or "unknown"
        )
        source_system = (
            _normalize_text(approval_record.get("source_system"))
            or (_normalize_text(lineage_record.get("source_system")) if isinstance(lineage_record, dict) else None)
            or (_normalize_text(migration_record.get("source_system")) if isinstance(migration_record, dict) else None)
            or "unknown"
        )
        source_entity_type = (
            _normalize_text(approval_record.get("source_entity_type"))
            or (_normalize_text(lineage_record.get("source_entity_type")) if isinstance(lineage_record, dict) else None)
            or (_normalize_text(migration_record.get("source_entity_type")) if isinstance(migration_record, dict) else None)
            or "unknown"
        )
        migration_profile = (
            _normalize_text(approval_record.get("migration_profile"))
            or (_normalize_text(lineage_record.get("migration_profile")) if isinstance(lineage_record, dict) else None)
            or (_normalize_text(migration_record.get("migration_profile")) if isinstance(migration_record, dict) else None)
            or "unknown"
        )

        approval_decision_counts[approval_decision] = approval_decision_counts.get(approval_decision, 0) + 1
        replay_mode_counts[replay_mode] = replay_mode_counts.get(replay_mode, 0) + 1
        source_system_counts[source_system] = source_system_counts.get(source_system, 0) + 1
        comparison_outcome_counts[comparison_outcome] = comparison_outcome_counts.get(comparison_outcome, 0) + 1

        if reason_codes:
            review_queue.append(
                redact_sensitive_fields(
                    {
                        "schema_version": SOURCE_REPLAY_EXECUTION_SCHEMA_VERSION,
                        "review_item_id": f"source-replay-execution-review-{_stable_digest({'source_key': source_ref, 'reason_codes': reason_codes})[:24]}",
                        "source_key": source_key,
                        "source_replay_approval_id": _normalize_text(approval_record.get("source_replay_approval_id")),
                        "source_replay_compare_id": _normalize_text(approval_record.get("source_replay_compare_id")),
                        "source_replay_plan_id": _normalize_text(approval_record.get("source_replay_plan_id")),
                        "state": "open",
                        "priority": _execution_priority(reason_codes),
                        "review_type": "source-replay-execution",
                        "reason_codes": reason_codes,
                        "recommended_action": "fix-execution-dependencies",
                        "approval_summary": {
                            "approval_decision": approval_decision,
                            "comparison_outcome": comparison_outcome,
                            "replay_mode": replay_mode,
                            "execution_gate": _normalize_text(approval_record.get("execution_gate")),
                        },
                    }
                )
            )
            continue

        status, policy = _execution_policy(
            approval_decision,
            replay_mode,
            _normalize_text(approval_record.get("execution_gate")),
        )

        if policy.get("execution_requires_review"):
            policy_reason_codes = list(policy.get("reason_codes") or [])
            review_queue.append(
                redact_sensitive_fields(
                    {
                        "schema_version": SOURCE_REPLAY_EXECUTION_SCHEMA_VERSION,
                        "review_item_id": f"source-replay-execution-review-{_stable_digest({'source_key': source_ref, 'reason_codes': policy_reason_codes or [approval_decision]})[:24]}",
                        "source_key": source_key,
                        "source_replay_approval_id": _normalize_text(approval_record.get("source_replay_approval_id")),
                        "source_replay_compare_id": _normalize_text(approval_record.get("source_replay_compare_id")),
                        "source_replay_plan_id": _normalize_text(approval_record.get("source_replay_plan_id")),
                        "state": "open",
                        "priority": _execution_priority(policy_reason_codes),
                        "review_type": "source-replay-execution",
                        "reason_codes": policy_reason_codes,
                        "recommended_action": policy.get("recommended_action"),
                        "execution_message": policy.get("execution_message"),
                    }
                )
            )
            continue

        planned_actions = approval_record.get("planned_actions")
        planned_actions = list(planned_actions) if isinstance(planned_actions, list) else []
        if not planned_actions and policy["execution_required"]:
            if replay_mode == "resume-from-approved":
                planned_actions = ["resume-approved-state", "prepare-dry-run"]
            elif replay_mode == "full-replay":
                planned_actions = ["full-replay", "prepare-dry-run"]
            else:
                planned_actions = ["prepare-dry-run"]

        entry = redact_sensitive_fields(
            {
                "schema_version": SOURCE_REPLAY_EXECUTION_SCHEMA_VERSION,
                "source_replay_execution_id": f"source-replay-execution-{_stable_digest({'source_key': source_ref, 'approval_decision': approval_decision})[:24]}",
                "source_replay_approval_id": _normalize_text(approval_record.get("source_replay_approval_id")),
                "source_replay_compare_id": _normalize_text(approval_record.get("source_replay_compare_id")),
                "source_replay_plan_id": _normalize_text(approval_record.get("source_replay_plan_id")),
                "source_key": source_key,
                "source_system": source_system,
                "source_entity_type": source_entity_type,
                "migration_profile": migration_profile,
                "replay_mode": replay_mode,
                "comparison_outcome": comparison_outcome,
                "approval_status": _normalize_text(approval_record.get("approval_status")) or "approved",
                "approval_decision": approval_decision,
                "execution_status": status,
                "execution_required": bool(policy["execution_required"]),
                "execution_scope": policy["execution_scope"],
                "execution_transition": policy["execution_transition"],
                "execution_message": policy["execution_message"],
                "dry_run_supported": bool(policy["dry_run_supported"]),
                "dry_run_required": bool(policy["dry_run_required"]),
                "compare_first": bool(approval_record.get("compare_first")),
                "downstream_write_allowed": bool(policy["downstream_write_allowed"]),
                "write_constraint": policy["write_constraint"],
                "resume_from_stage": _normalize_text(approval_record.get("resume_from_stage")),
                "planned_actions": planned_actions,
                "replay_key": _normalize_text(approval_record.get("replay_key")),
                "idempotency_key": _normalize_text(approval_record.get("idempotency_key")),
                "dry_run_cursor": {
                    "execution_scope": policy["execution_scope"],
                    "resume_from_stage": _normalize_text(approval_record.get("resume_from_stage")),
                    "planned_actions": planned_actions,
                },
                "provenance_refs": redact_sensitive_fields(
                    approval_record.get("provenance_refs")
                    if isinstance(approval_record.get("provenance_refs"), dict)
                    else {}
                ),
                "upstream_state_snapshot": redact_sensitive_fields(
                    approval_record.get("upstream_state_snapshot")
                    if isinstance(approval_record.get("upstream_state_snapshot"), dict)
                    else {}
                ),
            }
        )
        execution_packs.append(entry)
        execution_status_counts[status] = execution_status_counts.get(status, 0) + 1
        if status == "ready-for-dry-run":
            dry_run_ready_count += 1
        if status == "not-required":
            no_execution_required_count += 1

    return {
        "source_replay_execution_packs": {
            "schema_version": SOURCE_REPLAY_EXECUTION_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(execution_packs),
            "records": execution_packs,
        },
        "source_replay_execution_review_queue": {
            "schema_version": SOURCE_REPLAY_EXECUTION_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(review_queue),
            "records": review_queue,
        },
        "source_replay_execution_rollup": {
            "schema_version": SOURCE_REPLAY_EXECUTION_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "execution_pack_count": len(execution_packs),
            "review_item_count": len(review_queue),
            "execution_status_counts": execution_status_counts,
            "approval_decision_counts": approval_decision_counts,
            "comparison_outcome_counts": comparison_outcome_counts,
            "replay_mode_counts": replay_mode_counts,
            "source_system_counts": source_system_counts,
            "dry_run_ready_count": dry_run_ready_count,
            "no_execution_required_count": no_execution_required_count,
        },
    }


def write_source_replay_execution_artifacts(out_dir: str | Path, artifacts: dict[str, dict]) -> None:
    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)

    packs_doc = artifacts.get("source_replay_execution_packs", {})
    if packs_doc:
        (path / "source_replay_execution_packs.json").write_text(
            json.dumps(packs_doc, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    queue_doc = artifacts.get("source_replay_execution_review_queue", {})
    if queue_doc:
        (path / "source_replay_execution_review_queue.json").write_text(
            json.dumps(queue_doc, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    rollup_doc = artifacts.get("source_replay_execution_rollup", {})
    if rollup_doc:
        (path / "source_replay_execution_rollup.json").write_text(
            json.dumps(rollup_doc, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
