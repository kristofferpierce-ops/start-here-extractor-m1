from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .security import redact_sensitive_fields


APPLICATION_QUEUE_SCHEMA_VERSION = "1.0"
APPLICATION_DECISION_SCHEMA_VERSION = "1.0"
APPLICATION_TRANSITION_ROLLUP_SCHEMA_VERSION = "1.0"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _normalize_text_list(value: object) -> list[str]:
    if isinstance(value, list):
        values = [_normalize_text(item) for item in value]
    elif value is None:
        values = []
    else:
        values = [_normalize_text(value)]
    return sorted({item for item in values if item})


def normalize_target_catalog(value: object) -> list[dict]:
    if isinstance(value, dict):
        items = value.get("targets") if isinstance(value.get("targets"), list) else []
    elif isinstance(value, list):
        items = value
    else:
        items = []

    normalized: list[dict] = []
    seen: set[tuple[str, str, str, str | None]] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        target_key = _normalize_text(item.get("target_key")) or _normalize_text(item.get("name"))
        if not target_key:
            continue
        target_type = _normalize_text(item.get("target_type")) or target_key
        target_system = _normalize_text(item.get("target_system")) or "generic"
        target_id = _normalize_text(item.get("target_id"))
        marker = (target_key, target_type, target_system, target_id)
        if marker in seen:
            continue
        seen.add(marker)
        normalized.append(
            {
                "target_key": target_key,
                "target_type": target_type,
                "target_system": target_system,
                "target_id": target_id,
                "apply_mode": _normalize_text(item.get("apply_mode")) or "projection",
                "active": _normalize_bool(item.get("active"), default=True),
                "requires_approval": _normalize_bool(item.get("requires_approval"), default=True),
                "allowed_content_families": _normalize_text_list(item.get("allowed_content_families")),
                "allowed_source_types": _normalize_text_list(item.get("allowed_source_types")),
                "notes": _normalize_text(item.get("notes")),
            }
        )
    return sorted(
        normalized,
        key=lambda item: (
            item["target_key"],
            item["target_system"],
            item["target_type"],
            str(item.get("target_id") or ""),
        ),
    )


def load_target_catalog(path: str | Path) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return normalize_target_catalog(payload)


def _normalize_decisions(value: object) -> list[dict]:
    if isinstance(value, dict):
        items = value.get("decisions") if isinstance(value.get("decisions"), list) else []
        return [dict(item) for item in items if isinstance(item, dict)]
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


def load_application_decisions(path: str | Path) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return _normalize_decisions(payload)


def _approved_and_unapplied(record: dict) -> bool:
    pipeline = record.get("pipeline") if isinstance(record.get("pipeline"), dict) else {}
    approved_status = str((pipeline.get("approved") or {}).get("status") or "pending")
    applied_status = str((pipeline.get("applied") or {}).get("status") or "pending")
    return approved_status == "approved" and applied_status in {"pending", "needs_review", ""}


def _target_matches(record: dict, target: dict) -> bool:
    if not _normalize_bool(target.get("active"), default=True):
        return False
    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    content_family = _normalize_text(source.get("content_family"))
    source_type = _normalize_text(source.get("source_type"))
    allowed_families = target.get("allowed_content_families") if isinstance(target.get("allowed_content_families"), list) else []
    allowed_types = target.get("allowed_source_types") if isinstance(target.get("allowed_source_types"), list) else []
    if allowed_families and content_family not in allowed_families:
        return False
    if allowed_types and source_type not in allowed_types:
        return False
    return True


def _candidate_targets(record: dict, target_catalog: list[dict]) -> list[dict]:
    return [redact_sensitive_fields(dict(target)) for target in target_catalog if _target_matches(record, target)]


def _priority(reason_codes: list[str], candidate_count: int) -> str:
    if "no_target_candidates" in reason_codes or candidate_count != 1:
        return "high"
    return "normal"


def _queue_item_id(event_id: str) -> str:
    digest = hashlib.sha256(f"{event_id}:applied".encode("utf-8")).hexdigest()
    return f"apply-{digest[:24]}"


def build_application_queue(records: list[dict], target_catalog: list[dict]) -> dict:
    items: list[dict] = []
    for original in [redact_sensitive_fields(dict(item)) for item in records if isinstance(item, dict)]:
        if not _approved_and_unapplied(original):
            continue
        source = original.get("source") if isinstance(original.get("source"), dict) else {}
        evidence = original.get("evidence") if isinstance(original.get("evidence"), dict) else {}
        pipeline = original.get("pipeline") if isinstance(original.get("pipeline"), dict) else {}
        governance = original.get("governance") if isinstance(original.get("governance"), dict) else {}
        event_id = _normalize_text(original.get("event_id"))
        if not event_id:
            continue
        candidates = _candidate_targets(original, target_catalog)
        suggested_target = candidates[0] if candidates else None
        reason_codes = ["approved_pending_application"]
        if not candidates:
            reason_codes.append("no_target_candidates")
        elif len(candidates) == 1:
            reason_codes.append("single_target_candidate")
        else:
            reason_codes.append("multiple_target_candidates")
        if bool(governance.get("review_required")):
            reason_codes.append("source_review_flag_present")
        item = {
            "schema_version": APPLICATION_QUEUE_SCHEMA_VERSION,
            "queue_item_id": _queue_item_id(event_id),
            "state": "open",
            "priority": _priority(reason_codes, len(candidates)),
            "review_type": "application-routing",
            "event_id": event_id,
            "next_pipeline_stage": "applied",
            "reason_codes": reason_codes,
            "source": {
                "source_type": source.get("source_type"),
                "source_record_id": source.get("source_record_id"),
                "content_family": source.get("content_family"),
            },
            "matched": {
                "entity_type": (pipeline.get("matched") or {}).get("entity_type"),
                "entity_id": (pipeline.get("matched") or {}).get("entity_id"),
            },
            "approved": {
                "approved_at": (pipeline.get("approved") or {}).get("approved_at"),
                "approved_by": (pipeline.get("approved") or {}).get("approved_by"),
                "decision_ref": (pipeline.get("approved") or {}).get("decision_ref"),
            },
            "evidence": {
                "inventory_ref": evidence.get("inventory_ref"),
                "audit_ref": evidence.get("audit_ref"),
                "monitoring_ref": evidence.get("monitoring_ref"),
                "zip_sha256": evidence.get("zip_sha256"),
            },
            "candidate_targets": candidates,
            "suggested_target": suggested_target,
        }
        items.append(redact_sensitive_fields(item))

    queue = {
        "schema_version": APPLICATION_QUEUE_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "item_count": len(items),
        "items": sorted(
            items,
            key=lambda item: (str(item.get("priority") != "high"), str(item.get("queue_item_id") or "")),
        ),
    }
    return redact_sensitive_fields(queue)


def render_application_queue_markdown(queue: dict) -> str:
    lines = [
        "# Application queue",
        "",
        f"Generated at: {queue.get('generated_at')}",
        f"Open items: {queue.get('item_count', 0)}",
        "",
    ]
    items = queue.get("items") if isinstance(queue.get("items"), list) else []
    if not items:
        lines.append("No open application items.")
        return "\n".join(lines).strip() + "\n"
    for item in items:
        lines.extend(
            [
                f"## {item.get('queue_item_id')}",
                f"- Event: {item.get('event_id')}",
                f"- Priority: {item.get('priority')}",
                f"- Next stage: {item.get('next_pipeline_stage')}",
                f"- Reasons: {', '.join(item.get('reason_codes') or [])}",
                f"- Suggested target: {((item.get('suggested_target') or {}).get('target_key') if isinstance(item.get('suggested_target'), dict) else 'none')}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _queue_index(queue: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    by_queue_item_id: dict[str, dict] = {}
    by_event_id: dict[str, dict] = {}
    for item in queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        queue_item_id = _normalize_text(item.get("queue_item_id"))
        event_id = _normalize_text(item.get("event_id"))
        if queue_item_id:
            by_queue_item_id[queue_item_id] = item
        if event_id and event_id not in by_event_id:
            by_event_id[event_id] = item
    return by_queue_item_id, by_event_id


def _candidate_target_index(queue_item: dict) -> dict[str, dict]:
    items = queue_item.get("candidate_targets") if isinstance(queue_item.get("candidate_targets"), list) else []
    return {
        str(item.get("target_key") or ""): item
        for item in items
        if isinstance(item, dict) and _normalize_text(item.get("target_key"))
    }


def _stable_decision_payload(queue_item: dict, decision: dict, actor_id: str | None) -> dict:
    return {
        "queue_item_id": _normalize_text(queue_item.get("queue_item_id")),
        "event_id": _normalize_text(decision.get("event_id")) or _normalize_text(queue_item.get("event_id")),
        "apply_action": _normalize_text(decision.get("apply_action")),
        "target_key": _normalize_text(decision.get("target_key")),
        "target_type": _normalize_text(decision.get("target_type")),
        "target_system": _normalize_text(decision.get("target_system")),
        "target_id": _normalize_text(decision.get("target_id")),
        "reason": _normalize_text(decision.get("reason")),
        "decision_by": _normalize_text(decision.get("decision_by")) or actor_id,
    }


def derive_application_decision_id(queue_item: dict, decision: dict, actor_id: str | None = None) -> str:
    digest = hashlib.sha256(
        json.dumps(_stable_decision_payload(queue_item, decision, actor_id), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"application-decision-{digest[:24]}"


def _resolve_target(queue_item: dict, decision: dict) -> dict:
    action = _normalize_text(decision.get("apply_action"))
    candidate_index = _candidate_target_index(queue_item)
    if action == "apply_suggested":
        target = queue_item.get("suggested_target") if isinstance(queue_item.get("suggested_target"), dict) else {}
        return redact_sensitive_fields(dict(target))
    if action == "apply_selected":
        target_key = _normalize_text(decision.get("target_key"))
        if target_key and target_key in candidate_index:
            return redact_sensitive_fields(dict(candidate_index[target_key]))
        return redact_sensitive_fields(
            {
                "target_key": target_key,
                "target_type": _normalize_text(decision.get("target_type")) or target_key,
                "target_system": _normalize_text(decision.get("target_system")) or "generic",
                "target_id": _normalize_text(decision.get("target_id")),
                "apply_mode": "projection",
            }
        )
    return {}


def _application_state(record: dict) -> tuple[bool, str]:
    pipeline = record.get("pipeline") if isinstance(record.get("pipeline"), dict) else {}
    approved_status = str((pipeline.get("approved") or {}).get("status") or "pending")
    applied_status = str((pipeline.get("applied") or {}).get("status") or "pending")
    application_required = approved_status == "approved" and applied_status in {"pending", "needs_review", ""}
    return application_required, "open" if application_required else "resolved"


def _apply_action(record: dict, queue_item: dict, decision: dict, applied_at: str, decision_id: str, actor_id: str | None) -> None:
    pipeline = record.setdefault("pipeline", {})
    applied = pipeline.setdefault("applied", {})
    governance = record.setdefault("governance", {})
    action = _normalize_text(decision.get("apply_action"))
    reason = _normalize_text(decision.get("reason"))
    decision_by = _normalize_text(decision.get("decision_by")) or actor_id

    if action in {"apply_suggested", "apply_selected"}:
        target = _resolve_target(queue_item, decision)
        applied.update(
            {
                "status": "applied",
                "applied_at": applied_at,
                "applied_ref": _normalize_text(decision.get("applied_ref")) or f"application://{decision_id}",
                "target_type": _normalize_text(target.get("target_type")),
                "target_id": _normalize_text(target.get("target_id")),
                "target_system": _normalize_text(target.get("target_system")),
                "target_key": _normalize_text(target.get("target_key")),
                "apply_mode": _normalize_text(target.get("apply_mode")) or "projection",
                "applied_by": decision_by,
                "reason": reason or "Operator routed approved record to target system",
                "decision_ref": decision_id,
            }
        )
    elif action == "not_applicable":
        applied.update(
            {
                "status": "not_applicable",
                "applied_at": applied_at,
                "applied_ref": None,
                "target_type": None,
                "target_id": None,
                "target_system": None,
                "target_key": None,
                "apply_mode": None,
                "applied_by": decision_by,
                "reason": reason or "Operator determined no downstream application is required",
                "decision_ref": decision_id,
            }
        )
    elif action == "defer":
        governance["application_deferred_at"] = applied_at
        governance["application_deferred_by"] = decision_by
        governance["application_deferred_reason"] = reason or "Operator deferred application routing"

    application_required, application_state = _application_state(record)
    governance["application_required"] = application_required
    governance["application_state"] = application_state
    governance["last_application_decision_ref"] = f"application-decision://{decision_id}"


def _decision_event(record: dict, queue_item: dict, decision: dict, applied_at: str, decision_id: str, actor_id: str | None) -> dict:
    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    evidence = record.get("evidence") if isinstance(record.get("evidence"), dict) else {}
    governance = record.get("governance") if isinstance(record.get("governance"), dict) else {}
    pipeline = record.get("pipeline") if isinstance(record.get("pipeline"), dict) else {}
    payload = {
        "schema_version": APPLICATION_DECISION_SCHEMA_VERSION,
        "decision_id": decision_id,
        "applied_at": applied_at,
        "queue_item_id": queue_item.get("queue_item_id"),
        "event_id": record.get("event_id"),
        "decision_by": _normalize_text(decision.get("decision_by")) or actor_id,
        "apply_action": _normalize_text(decision.get("apply_action")),
        "reason": _normalize_text(decision.get("reason")),
        "target": {
            "target_key": (pipeline.get("applied") or {}).get("target_key"),
            "target_type": (pipeline.get("applied") or {}).get("target_type"),
            "target_system": (pipeline.get("applied") or {}).get("target_system"),
            "target_id": (pipeline.get("applied") or {}).get("target_id"),
            "apply_mode": (pipeline.get("applied") or {}).get("apply_mode"),
        },
        "source": {
            "source_type": source.get("source_type"),
            "source_record_id": source.get("source_record_id"),
        },
        "evidence": {
            "inventory_ref": evidence.get("inventory_ref"),
            "audit_ref": evidence.get("audit_ref"),
            "monitoring_ref": evidence.get("monitoring_ref"),
            "zip_sha256": evidence.get("zip_sha256"),
        },
        "result": {
            "applied_status": (pipeline.get("applied") or {}).get("status"),
            "application_state": governance.get("application_state"),
        },
    }
    return redact_sensitive_fields(payload)


def apply_application_decisions(
    records: list[dict],
    queue: dict,
    decisions: list[dict],
    *,
    actor_id: str | None = None,
) -> tuple[list[dict], list[dict], dict, dict]:
    queue_by_id, queue_by_event = _queue_index(queue)
    normalized_decisions = _normalize_decisions(decisions)
    decisions_by_event: dict[str, list[dict]] = {}
    for decision in normalized_decisions:
        queue_item = None
        queue_item_id = _normalize_text(decision.get("queue_item_id"))
        event_id = _normalize_text(decision.get("event_id"))
        if queue_item_id:
            queue_item = queue_by_id.get(queue_item_id)
            if queue_item and not event_id:
                event_id = _normalize_text(queue_item.get("event_id"))
        elif event_id:
            queue_item = queue_by_event.get(event_id)
            if queue_item:
                queue_item_id = _normalize_text(queue_item.get("queue_item_id"))
        if not event_id or not queue_item_id:
            continue
        entry = redact_sensitive_fields(dict(decision))
        entry["event_id"] = event_id
        entry["queue_item_id"] = queue_item_id
        decisions_by_event.setdefault(event_id, []).append(entry)

    updated_records: list[dict] = []
    decision_journal: list[dict] = []
    for original in [redact_sensitive_fields(dict(item)) for item in records if isinstance(item, dict)]:
        record = redact_sensitive_fields(dict(original))
        event_id = _normalize_text(record.get("event_id")) or ""
        queue_item = queue_by_event.get(event_id, {})
        for decision in decisions_by_event.get(event_id, []):
            applied_at = utcnow_iso()
            decision_id = derive_application_decision_id(queue_item, decision, actor_id)
            _apply_action(record, queue_item, decision, applied_at, decision_id, actor_id)
            decision_journal.append(_decision_event(record, queue_item, decision, applied_at, decision_id, actor_id))
        updated_records.append(redact_sensitive_fields(record))

    target_catalog: list[dict] = []
    for item in queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        for target in item.get("candidate_targets") or []:
            if isinstance(target, dict):
                target_catalog.append(target)
    post_queue = build_application_queue(updated_records, normalize_target_catalog(target_catalog))
    rollup = build_application_transition_rollup(updated_records, decision_journal, queue, post_queue)
    return updated_records, decision_journal, rollup, post_queue


def build_application_transition_rollup(records: list[dict], decision_journal: list[dict], before_queue: dict, after_queue: dict) -> dict:
    applied_status_counts: dict[str, int] = {}
    application_state_counts: dict[str, int] = {}
    target_system_counts: dict[str, int] = {}
    action_counts = {"apply_action": {}}
    for record in records:
        pipeline = record.get("pipeline") if isinstance(record.get("pipeline"), dict) else {}
        governance = record.get("governance") if isinstance(record.get("governance"), dict) else {}
        applied_status = str((pipeline.get("applied") or {}).get("status") or "pending")
        application_state = str(governance.get("application_state") or ("open" if governance.get("application_required") else "resolved"))
        target_system = _normalize_text((pipeline.get("applied") or {}).get("target_system")) or "unassigned"
        applied_status_counts[applied_status] = applied_status_counts.get(applied_status, 0) + 1
        application_state_counts[application_state] = application_state_counts.get(application_state, 0) + 1
        target_system_counts[target_system] = target_system_counts.get(target_system, 0) + 1
    for item in decision_journal:
        apply_action = _normalize_text(item.get("apply_action"))
        if apply_action:
            action_counts["apply_action"][apply_action] = action_counts["apply_action"].get(apply_action, 0) + 1
    before_count = int(before_queue.get("item_count") or 0)
    after_count = int(after_queue.get("item_count") or 0)
    return {
        "schema_version": APPLICATION_TRANSITION_ROLLUP_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "record_count": len(records),
        "decision_count": len(decision_journal),
        "applied_status_counts": applied_status_counts,
        "application_state_counts": application_state_counts,
        "target_system_counts": target_system_counts,
        "queue": {
            "before_count": before_count,
            "after_count": after_count,
            "closed_count": max(before_count - after_count, 0),
        },
        "action_counts": action_counts,
    }


def render_application_transition_rollup_markdown(rollup: dict) -> str:
    queue = rollup.get("queue") if isinstance(rollup.get("queue"), dict) else {}
    lines = [
        "# Application transition rollup",
        "",
        f"Generated at: {rollup.get('generated_at')}",
        f"Records evaluated: {rollup.get('record_count')}",
        f"Decisions applied: {rollup.get('decision_count')}",
        f"Queue before: {queue.get('before_count', 0)}",
        f"Queue after: {queue.get('after_count', 0)}",
        f"Queue closed: {queue.get('closed_count', 0)}",
        "",
        "## Applied status counts",
    ]
    for key, value in sorted((rollup.get("applied_status_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Application state counts"])
    for key, value in sorted((rollup.get("application_state_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Target system counts"])
    for key, value in sorted((rollup.get("target_system_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).strip() + "\n"


def write_jsonl(path: str | Path, records: Iterable[dict]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(redact_sensitive_fields(record), sort_keys=True) + "\n")
    return target
