from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .relationship_memory import (
    build_operator_review_queue,
    build_relationship_memory_snapshot,
)
from .security import redact_sensitive_fields


REVIEW_DECISION_SCHEMA_VERSION = "1.0"
STATE_TRANSITION_ROLLUP_SCHEMA_VERSION = "1.0"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_decisions(value: object) -> list[dict]:
    if isinstance(value, dict):
        items = value.get("decisions") if isinstance(value.get("decisions"), list) else []
        return [dict(item) for item in items if isinstance(item, dict)]
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


def load_review_queue(path: str | Path) -> dict:
    target = Path(path)
    if target.is_dir():
        target = target / "operator_review_queue.json"
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_review_decisions(path: str | Path) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return _normalize_decisions(payload)


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


def _stable_decision_payload(queue_item: dict, decision: dict, actor_id: str | None) -> dict:
    return {
        "queue_item_id": _normalize_text(queue_item.get("queue_item_id")),
        "event_id": _normalize_text(decision.get("event_id"))
        or _normalize_text(queue_item.get("event_id")),
        "match_action": _normalize_text(decision.get("match_action")),
        "approval_action": _normalize_text(decision.get("approval_action")),
        "entity_id": _normalize_text(decision.get("entity_id")),
        "entity_type": _normalize_text(decision.get("entity_type")),
        "confidence": decision.get("confidence"),
        "reason": _normalize_text(decision.get("reason")),
        "decision_by": _normalize_text(decision.get("decision_by")) or actor_id,
    }



def derive_review_decision_id(queue_item: dict, decision: dict, actor_id: str | None = None) -> str:
    payload = _stable_decision_payload(queue_item, decision, actor_id)
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"review-decision-{digest[:24]}"


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _closed_review_state(record: dict) -> tuple[bool, str]:
    pipeline = record.get("pipeline") if isinstance(record.get("pipeline"), dict) else {}
    matched_status = str((pipeline.get("matched") or {}).get("status") or "pending")
    approved_status = str((pipeline.get("approved") or {}).get("status") or "pending")
    open_match = matched_status in {"pending", "needs_review"}
    open_approval = approved_status in {"pending", "needs_review"}
    review_required = open_match or open_approval
    return review_required, "open" if review_required else "resolved"


def _apply_match_action(record: dict, queue_item: dict, decision: dict, applied_at: str, decision_id: str) -> None:
    pipeline = record.setdefault("pipeline", {})
    matched = pipeline.setdefault("matched", {})
    approval = pipeline.setdefault("approved", {})
    suggestion = queue_item.get("suggested_match") if isinstance(queue_item.get("suggested_match"), dict) else {}
    action = _normalize_text(decision.get("match_action"))
    reason = _normalize_text(decision.get("reason")) or _normalize_text(suggestion.get("reason"))
    confidence = _float_or_none(decision.get("confidence"))
    if confidence is None:
        confidence = _float_or_none(suggestion.get("confidence"))
    if action == "accept_suggested":
        matched.update(
            {
                "status": "matched",
                "matched_at": applied_at,
                "entity_type": _normalize_text(suggestion.get("entity_type")) or "evidence-artifact",
                "entity_id": _normalize_text(suggestion.get("entity_id")),
                "confidence": confidence,
                "reason": reason,
                "decision_ref": decision_id,
            }
        )
    elif action == "override_match":
        matched.update(
            {
                "status": "matched",
                "matched_at": applied_at,
                "entity_type": _normalize_text(decision.get("entity_type")) or "evidence-artifact",
                "entity_id": _normalize_text(decision.get("entity_id")),
                "confidence": confidence,
                "reason": reason or "Operator override match",
                "decision_ref": decision_id,
            }
        )
    elif action == "no_match":
        matched.update(
            {
                "status": "no_match",
                "matched_at": applied_at,
                "entity_type": None,
                "entity_id": None,
                "confidence": confidence,
                "reason": reason or "Operator determined that no match should be applied",
                "decision_ref": decision_id,
            }
        )
        approval.update(
            {
                "status": "not_applicable",
                "decision": "not_applicable",
                "approved_at": applied_at,
                "approved_by": _normalize_text(decision.get("decision_by")),
                "reason": "Approval is not applicable because no match was selected",
                "decision_ref": decision_id,
            }
        )


def _apply_approval_action(record: dict, decision: dict, applied_at: str, decision_id: str, actor_id: str | None) -> None:
    pipeline = record.setdefault("pipeline", {})
    approved = pipeline.setdefault("approved", {})
    action = _normalize_text(decision.get("approval_action"))
    reason = _normalize_text(decision.get("reason"))
    approved_by = _normalize_text(decision.get("decision_by")) or actor_id
    if action == "approve":
        approved.update(
            {
                "status": "approved",
                "decision": "approved",
                "approved_at": applied_at,
                "approved_by": approved_by,
                "reason": reason or "Operator approved staged match",
                "decision_ref": decision_id,
            }
        )
    elif action == "reject":
        approved.update(
            {
                "status": "rejected",
                "decision": "rejected",
                "approved_at": applied_at,
                "approved_by": approved_by,
                "reason": reason or "Operator rejected staged match",
                "decision_ref": decision_id,
            }
        )


def _decision_event(record: dict, queue_item: dict, decision: dict, applied_at: str, decision_id: str, actor_id: str | None) -> dict:
    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    evidence = record.get("evidence") if isinstance(record.get("evidence"), dict) else {}
    governance = record.get("governance") if isinstance(record.get("governance"), dict) else {}
    pipeline = record.get("pipeline") if isinstance(record.get("pipeline"), dict) else {}
    payload = {
        "schema_version": REVIEW_DECISION_SCHEMA_VERSION,
        "decision_id": decision_id,
        "applied_at": applied_at,
        "queue_item_id": queue_item.get("queue_item_id"),
        "event_id": record.get("event_id"),
        "decision_by": _normalize_text(decision.get("decision_by")) or actor_id,
        "match_action": _normalize_text(decision.get("match_action")),
        "approval_action": _normalize_text(decision.get("approval_action")),
        "reason": _normalize_text(decision.get("reason")),
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
            "matched_status": (pipeline.get("matched") or {}).get("status"),
            "approved_status": (pipeline.get("approved") or {}).get("status"),
            "review_state": governance.get("review_state"),
        },
    }
    return redact_sensitive_fields(payload)


def apply_review_decisions(
    records: list[dict],
    queue: dict,
    decisions: list[dict],
    *,
    actor_id: str | None = None,
) -> tuple[list[dict], list[dict], dict, dict, dict]:
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
    closed_queue_ids: set[str] = set()
    for original in [redact_sensitive_fields(dict(item)) for item in records if isinstance(item, dict)]:
        record = redact_sensitive_fields(dict(original))
        event_id = _normalize_text(record.get("event_id")) or ""
        queue_item = queue_by_event.get(event_id, {})
        for decision in decisions_by_event.get(event_id, []):
            applied_at = utcnow_iso()
            decision_id = derive_review_decision_id(queue_item, decision, actor_id)
            _apply_match_action(record, queue_item, decision, applied_at, decision_id)
            _apply_approval_action(record, decision, applied_at, decision_id, actor_id)
            review_required, review_state = _closed_review_state(record)
            governance = record.setdefault("governance", {})
            governance["review_required"] = review_required
            governance["review_state"] = review_state
            governance["last_review_decision_ref"] = f"review-decision://{decision_id}"
            if review_state == "resolved":
                queue_item_id = _normalize_text(queue_item.get("queue_item_id"))
                if queue_item_id:
                    closed_queue_ids.add(queue_item_id)
            decision_journal.append(
                _decision_event(record, queue_item, decision, applied_at, decision_id, actor_id)
            )
        updated_records.append(redact_sensitive_fields(record))

    post_snapshot, post_suggestions = build_relationship_memory_snapshot(updated_records)
    post_queue = build_operator_review_queue(updated_records, post_suggestions)
    rollup = build_state_transition_rollup(updated_records, decision_journal, queue, post_queue)
    return updated_records, decision_journal, rollup, post_snapshot, post_queue


def build_state_transition_rollup(
    records: list[dict], decision_journal: list[dict], before_queue: dict, after_queue: dict
) -> dict:
    matched_status_counts: dict[str, int] = {}
    approved_status_counts: dict[str, int] = {}
    review_state_counts: dict[str, int] = {}
    action_counts = {
        "match_action": {},
        "approval_action": {},
    }
    for record in records:
        pipeline = record.get("pipeline") if isinstance(record.get("pipeline"), dict) else {}
        governance = record.get("governance") if isinstance(record.get("governance"), dict) else {}
        matched_status = str((pipeline.get("matched") or {}).get("status") or "pending")
        approved_status = str((pipeline.get("approved") or {}).get("status") or "pending")
        review_state = str(governance.get("review_state") or ("open" if governance.get("review_required") else "resolved"))
        matched_status_counts[matched_status] = matched_status_counts.get(matched_status, 0) + 1
        approved_status_counts[approved_status] = approved_status_counts.get(approved_status, 0) + 1
        review_state_counts[review_state] = review_state_counts.get(review_state, 0) + 1
    for item in decision_journal:
        match_action = _normalize_text(item.get("match_action"))
        approval_action = _normalize_text(item.get("approval_action"))
        if match_action:
            action_counts["match_action"][match_action] = action_counts["match_action"].get(match_action, 0) + 1
        if approval_action:
            action_counts["approval_action"][approval_action] = action_counts["approval_action"].get(approval_action, 0) + 1
    before_count = int(before_queue.get("item_count") or 0)
    after_count = int(after_queue.get("item_count") or 0)
    return {
        "schema_version": STATE_TRANSITION_ROLLUP_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "record_count": len(records),
        "decision_count": len(decision_journal),
        "matched_status_counts": matched_status_counts,
        "approved_status_counts": approved_status_counts,
        "review_state_counts": review_state_counts,
        "review_queue": {
            "before_count": before_count,
            "after_count": after_count,
            "closed_count": max(before_count - after_count, 0),
        },
        "action_counts": action_counts,
    }


def render_state_transition_rollup_markdown(rollup: dict) -> str:
    queue = rollup.get("review_queue") if isinstance(rollup.get("review_queue"), dict) else {}
    lines = [
        "# Review state transition rollup",
        "",
        f"Generated at: {rollup.get('generated_at')}",
        f"Records evaluated: {rollup.get('record_count')}",
        f"Decisions applied: {rollup.get('decision_count')}",
        f"Queue before: {queue.get('before_count', 0)}",
        f"Queue after: {queue.get('after_count', 0)}",
        f"Queue closed: {queue.get('closed_count', 0)}",
        "",
        "## Matched status counts",
    ]
    for key, value in sorted((rollup.get("matched_status_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Approved status counts"])
    for key, value in sorted((rollup.get("approved_status_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Review state counts"])
    for key, value in sorted((rollup.get("review_state_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).strip() + "\n"


def write_jsonl(path: str | Path, records: Iterable[dict]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(redact_sensitive_fields(record), sort_keys=True) + "\n")
    return target
