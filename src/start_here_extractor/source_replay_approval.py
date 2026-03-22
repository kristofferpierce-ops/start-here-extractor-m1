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
from .source_replay_compare import SOURCE_REPLAY_COMPARE_SCHEMA_VERSION

SOURCE_REPLAY_APPROVAL_SCHEMA_VERSION = SOURCE_REPLAY_COMPARE_SCHEMA_VERSION


def _approval_priority(reason_codes: list[str]) -> str:
    urgent = {
        "missing_source_key",
        "missing_replay_compare",
        "missing_replay_plan",
        "missing_readiness_pack",
        "missing_replay_control",
        "missing_durable_lineage",
        "missing_migration_pack",
        "upstream_compare_review_required",
        "manual_full_replay_approval_required",
        "comparison_requires_review",
        "upstream_state_drift_requires_review",
        "unrecognized_compare_outcome",
    }
    return "high" if any(code in urgent for code in reason_codes) else "medium"


def _append_unique(target: list[str], value: str) -> None:
    if value not in target:
        target.append(value)


def _approval_policy(
    comparison_outcome: str | None,
    replay_mode: str | None,
    comparison_requires_review: bool,
) -> tuple[str, dict]:
    comparison_outcome = comparison_outcome or "unknown"
    replay_mode = replay_mode or "unknown"

    if comparison_requires_review or comparison_outcome in {"upstream-state-drift", "unrecognized-replay-mode"}:
        return "manual-review", {
            "approval_requires_review": True,
            "approval_message": "Replay comparison requires operator review before any approval decision can be recorded.",
            "reason_codes": ["comparison_requires_review"],
            "recommended_decision": "resolve-compare-review-first",
        }

    if comparison_outcome == "stable-match" and replay_mode == "compare-only":
        return "auto-approved", {
            "approval_requires_review": False,
            "approval_message": "Protected compare-only replay remained stable and is auto-approved as a no-op compare.",
            "approval_decision": "approved-no-op-compare",
            "approval_reason": "Protected compare-only replay remained stable; no downstream execution is required.",
            "execution_gate": "no-execution-required",
            "recommended_decision": "approved-no-op-compare",
        }

    if comparison_outcome == "resume-required" and replay_mode == "resume-from-approved":
        return "auto-approved", {
            "approval_requires_review": False,
            "approval_message": "Resume-from-approved replay can continue from an already-approved apply-ready state.",
            "approval_decision": "approved-resume-replay",
            "approval_reason": "Replay can resume from an already-approved apply-ready state.",
            "execution_gate": "execution-pack-eligible",
            "recommended_decision": "approved-resume-replay",
        }

    if comparison_outcome == "full-replay-required" and replay_mode == "full-replay":
        return "manual-review", {
            "approval_requires_review": True,
            "approval_message": "Full replay requires explicit operator approval before execution packaging.",
            "reason_codes": ["manual_full_replay_approval_required"],
            "recommended_decision": "operator-approve-full-replay-or-reject",
        }

    return "manual-review", {
        "approval_requires_review": True,
        "approval_message": "Replay comparison outcome could not be mapped to an auto-approval rule.",
        "reason_codes": ["unrecognized_compare_outcome"],
        "recommended_decision": "operator-review-required",
    }


def build_source_replay_approval_artifacts(
    *args: dict[str, dict],
    compare_documents: dict[str, dict] | None = None,
    plan_documents: dict[str, dict] | None = None,
    readiness_documents: dict[str, dict] | None = None,
    control_documents: dict[str, dict] | None = None,
    lineage_documents: dict[str, dict] | None = None,
    migration_documents: dict[str, dict] | None = None,
) -> dict[str, dict]:
    if args:
        if len(args) == 7:
            (
                _,
                migration_documents,
                lineage_documents,
                control_documents,
                readiness_documents,
                plan_documents,
                compare_documents,
            ) = args
        elif len(args) == 6:
            (
                compare_documents,
                plan_documents,
                readiness_documents,
                control_documents,
                lineage_documents,
                migration_documents,
            ) = args
        else:
            raise TypeError(
                "build_source_replay_approval_artifacts expected 6 document arguments, or "
                "7 positional arguments in pipeline/migration/lineage/control/readiness/plan/compare order"
            )

    if (
        compare_documents is None
        or plan_documents is None
        or readiness_documents is None
        or control_documents is None
        or lineage_documents is None
        or migration_documents is None
    ):
        raise TypeError(
            "build_source_replay_approval_artifacts requires compare, plan, readiness, control, lineage, and migration documents"
        )

    compare_records = compare_documents.get("source_replay_compare_packs", {}).get("records")
    compare_records = compare_records if isinstance(compare_records, list) else []
    compare_review_records = compare_documents.get("source_replay_compare_review_queue", {}).get("records")
    compare_review_records = compare_review_records if isinstance(compare_review_records, list) else []

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

    approval_journal: list[dict] = []
    approval_queue: list[dict] = []
    approval_decision_counts: dict[str, int] = {}
    comparison_outcome_counts: dict[str, int] = {}
    replay_mode_counts: dict[str, int] = {}
    source_system_counts: dict[str, int] = {}

    for item in compare_review_records:
        if not isinstance(item, dict):
            continue
        source_key = _normalize_text(item.get("source_key"))
        source_ref = source_key or _normalize_text(item.get("review_item_id")) or "missing-source"
        reason_codes = list(item.get("reason_codes") or [])
        _append_unique(reason_codes, "upstream_compare_review_required")
        approval_queue.append(
            redact_sensitive_fields(
                {
                    "schema_version": SOURCE_REPLAY_APPROVAL_SCHEMA_VERSION,
                    "review_item_id": f"source-replay-approval-review-{_stable_digest({'source_key': source_ref, 'reason_codes': reason_codes})[:24]}",
                    "source_key": source_key,
                    "state": "open",
                    "priority": _approval_priority(reason_codes),
                    "review_type": "source-replay-approval",
                    "reason_codes": reason_codes,
                    "recommended_decision": "resolve-compare-review-first",
                    "compare_review_summary": redact_sensitive_fields(item),
                }
            )
        )

    for index, compare_record in enumerate(compare_records, start=1):
        if not isinstance(compare_record, dict):
            continue

        source_key = _normalize_text(compare_record.get("source_key"))
        source_ref = source_key or f"missing-source-{index}"

        plan = plan_map.get(source_key or "")
        readiness = readiness_map.get(source_key or "")
        control = control_map.get(source_key or "")
        lineage = lineage_map.get(source_key or "")
        migration = migration_map.get(source_key or "")

        reasons: list[str] = []
        if source_key is None:
            reasons.append("missing_source_key")
        if plan is None:
            reasons.append("missing_replay_plan")
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

        replay_mode = _normalize_text(compare_record.get("replay_mode")) or "unknown"
        comparison_outcome = _normalize_text(compare_record.get("comparison_outcome")) or "unknown"
        source_system = (
            _normalize_text(compare_record.get("source_system"))
            or (_normalize_text(lineage.get("source_system")) if isinstance(lineage, dict) else None)
            or (_normalize_text(migration.get("source_system")) if isinstance(migration, dict) else None)
            or "unknown"
        )
        source_entity_type = (
            _normalize_text(compare_record.get("source_entity_type"))
            or (_normalize_text(lineage.get("source_entity_type")) if isinstance(lineage, dict) else None)
            or (_normalize_text(migration.get("source_entity_type")) if isinstance(migration, dict) else None)
            or "unknown"
        )
        migration_profile = (
            _normalize_text(compare_record.get("migration_profile"))
            or (_normalize_text(lineage.get("migration_profile")) if isinstance(lineage, dict) else None)
            or (_normalize_text(migration.get("migration_profile")) if isinstance(migration, dict) else None)
            or "unknown"
        )

        comparison_outcome_counts[comparison_outcome] = comparison_outcome_counts.get(comparison_outcome, 0) + 1
        replay_mode_counts[replay_mode] = replay_mode_counts.get(replay_mode, 0) + 1
        source_system_counts[source_system] = source_system_counts.get(source_system, 0) + 1

        if reasons:
            approval_queue.append(
                redact_sensitive_fields(
                    {
                        "schema_version": SOURCE_REPLAY_APPROVAL_SCHEMA_VERSION,
                        "review_item_id": f"source-replay-approval-review-{_stable_digest({'source_key': source_ref, 'reason_codes': reasons})[:24]}",
                        "source_key": source_key,
                        "source_replay_compare_id": _normalize_text(compare_record.get("source_replay_compare_id")),
                        "source_replay_plan_id": _normalize_text(compare_record.get("source_replay_plan_id")),
                        "state": "open",
                        "priority": _approval_priority(reasons),
                        "review_type": "source-replay-approval",
                        "reason_codes": reasons,
                        "recommended_decision": "resolve-upstream-review-first",
                        "plan_summary": {
                            "source_replay_plan_id": _normalize_text(compare_record.get("source_replay_plan_id")),
                            "replay_mode": replay_mode,
                            "comparison_outcome": comparison_outcome,
                        },
                    }
                )
            )
            continue

        comparison_requires_review = bool(compare_record.get("comparison_requires_review"))
        policy_kind, policy = _approval_policy(
            comparison_outcome=comparison_outcome,
            replay_mode=replay_mode,
            comparison_requires_review=comparison_requires_review,
        )

        plan_record = plan if isinstance(plan, dict) else {}
        expected_state_snapshot = (
            compare_record.get("expected_state_snapshot")
            if isinstance(compare_record.get("expected_state_snapshot"), dict)
            else {}
        )
        provenance_refs = (
            compare_record.get("provenance_refs")
            if isinstance(compare_record.get("provenance_refs"), dict)
            else {}
        )

        if policy_kind == "auto-approved":
            decision = policy["approval_decision"]
            entry = redact_sensitive_fields(
                {
                    "schema_version": SOURCE_REPLAY_APPROVAL_SCHEMA_VERSION,
                    "approval_journal_id": f"source-replay-approval-{_stable_digest({'source_key': source_ref, 'approval_decision': decision})[:24]}",
                    "source_replay_compare_id": _normalize_text(compare_record.get("source_replay_compare_id")),
                    "source_replay_plan_id": _normalize_text(compare_record.get("source_replay_plan_id")),
                    "source_key": source_key,
                    "source_system": source_system,
                    "source_entity_type": source_entity_type,
                    "migration_profile": migration_profile,
                    "replay_mode": replay_mode,
                    "comparison_outcome": comparison_outcome,
                    "approval_status": "approved",
                    "approval_decision": decision,
                    "approval_reason": policy["approval_reason"],
                    "approval_message": policy["approval_message"],
                    "approver_type": "system-auto",
                    "approved_at": utcnow_iso(),
                    "operator_review_required": False,
                    "execution_gate": policy["execution_gate"],
                    "compare_first": bool(expected_state_snapshot.get("compare_first")),
                    "downstream_write_allowed": bool(expected_state_snapshot.get("downstream_write_allowed")),
                    "write_constraint": _normalize_text(expected_state_snapshot.get("write_constraint")),
                    "resume_from_stage": _normalize_text(expected_state_snapshot.get("resume_from_stage")),
                    "planned_actions": expected_state_snapshot.get("planned_actions")
                    if isinstance(expected_state_snapshot.get("planned_actions"), list)
                    else [],
                    "replay_key": _normalize_text(plan_record.get("replay_key")),
                    "idempotency_key": _normalize_text(plan_record.get("idempotency_key")),
                    "provenance_refs": redact_sensitive_fields(provenance_refs),
                    "upstream_state_snapshot": redact_sensitive_fields(
                        compare_record.get("upstream_state_snapshot")
                        if isinstance(compare_record.get("upstream_state_snapshot"), dict)
                        else {}
                    ),
                }
            )
            approval_journal.append(entry)
            approval_decision_counts[decision] = approval_decision_counts.get(decision, 0) + 1
            continue

        reason_codes = list(policy.get("reason_codes") or [])
        approval_queue.append(
            redact_sensitive_fields(
                {
                    "schema_version": SOURCE_REPLAY_APPROVAL_SCHEMA_VERSION,
                    "review_item_id": f"source-replay-approval-review-{_stable_digest({'source_key': source_ref, 'reason_codes': reason_codes or [comparison_outcome]})[:24]}",
                    "source_key": source_key,
                    "source_replay_compare_id": _normalize_text(compare_record.get("source_replay_compare_id")),
                    "source_replay_plan_id": _normalize_text(compare_record.get("source_replay_plan_id")),
                    "state": "open",
                    "priority": _approval_priority(reason_codes),
                    "review_type": "source-replay-approval",
                    "reason_codes": reason_codes,
                    "recommended_decision": policy.get("recommended_decision"),
                    "approval_message": policy.get("approval_message"),
                    "plan_summary": {
                        "source_replay_plan_id": _normalize_text(compare_record.get("source_replay_plan_id")),
                        "replay_mode": replay_mode,
                        "comparison_outcome": comparison_outcome,
                        "replay_key": _normalize_text(plan_record.get("replay_key")),
                        "idempotency_key": _normalize_text(plan_record.get("idempotency_key")),
                    },
                    "compare_summary": {
                        "source_replay_compare_id": _normalize_text(compare_record.get("source_replay_compare_id")),
                        "comparison_outcome": comparison_outcome,
                        "comparison_requires_review": comparison_requires_review,
                    },
                }
            )
        )

    return {
        "source_replay_approval_queue": {
            "schema_version": SOURCE_REPLAY_APPROVAL_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(approval_queue),
            "records": approval_queue,
        },
        "source_replay_approval_journal": {
            "schema_version": SOURCE_REPLAY_APPROVAL_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(approval_journal),
            "records": approval_journal,
        },
        "source_replay_approval_rollup": {
            "schema_version": SOURCE_REPLAY_APPROVAL_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "approval_journal_count": len(approval_journal),
            "review_item_count": len(approval_queue),
            "approval_decision_counts": approval_decision_counts,
            "comparison_outcome_counts": comparison_outcome_counts,
            "replay_mode_counts": replay_mode_counts,
            "source_system_counts": source_system_counts,
            "auto_approved_count": len(approval_journal),
            "manual_review_count": len(approval_queue),
        },
    }


def write_source_replay_approval_artifacts(out_dir: str | Path, artifacts: dict[str, dict]) -> None:
    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)

    queue_doc = artifacts.get("source_replay_approval_queue", {})
    if queue_doc:
        (path / "source_replay_approval_queue.json").write_text(
            json.dumps(queue_doc, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    rollup_doc = artifacts.get("source_replay_approval_rollup", {})
    if rollup_doc:
        (path / "source_replay_approval_rollup.json").write_text(
            json.dumps(rollup_doc, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    journal_doc = artifacts.get("source_replay_approval_journal", {})
    journal_records = journal_doc.get("records") if isinstance(journal_doc, dict) else []
    journal_records = journal_records if isinstance(journal_records, list) else []
    journal_path = path / "source_replay_approval_journal.jsonl"
    with journal_path.open("w", encoding="utf-8") as handle:
        for record in journal_records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
