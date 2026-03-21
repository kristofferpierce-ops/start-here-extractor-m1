from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .ingestion import iter_ingestion_records
from .security import redact_sensitive_fields


RELATIONSHIP_MEMORY_SCHEMA_VERSION = "1.0"
REVIEW_QUEUE_SCHEMA_VERSION = "1.0"

KEY_WEIGHTS = {
    "zip_sha256": 100,
    "zip_md5": 95,
    "remote_id": 90,
    "etag": 70,
    "zip_path": 45,
    "start_here": 20,
    "source_type": 5,
}

SOURCE_SCOPED_KEYS = {"remote_id", "etag", "zip_path", "source_type"}


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _key_weight(kind: str) -> int:
    return KEY_WEIGHTS.get(kind, 0)


def _sort_keys(entries: Iterable[dict]) -> list[dict]:
    return sorted(
        [dict(entry) for entry in entries],
        key=lambda entry: (-_key_weight(str(entry.get("kind") or "")), str(entry.get("kind") or ""), str(entry.get("value") or ""), str(entry.get("source") or "")),
    )


def _relationship_keys(record: dict) -> list[dict]:
    block = record.get("relationship_memory") if isinstance(record.get("relationship_memory"), dict) else {}
    keys = block.get("keys") if isinstance(block.get("keys"), list) else []
    normalized: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for entry in keys:
        if not isinstance(entry, dict):
            continue
        kind = _normalize_text(entry.get("kind"))
        value = _normalize_text(entry.get("value"))
        source = _normalize_text(entry.get("source")) or "unknown"
        if not kind or not value:
            continue
        marker = (kind, value, source)
        if marker in seen:
            continue
        seen.add(marker)
        normalized.append({"kind": kind, "value": value, "source": source})
    return _sort_keys(normalized)


def _build_union_find(size: int) -> tuple[list[int], callable, callable]:
    parent = list(range(size))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left == root_right:
            return
        if root_left < root_right:
            parent[root_right] = root_left
        else:
            parent[root_left] = root_right

    return parent, find, union


def _anchor_payload(anchor_key: dict, source_types: list[str]) -> dict:
    payload = {"kind": anchor_key.get("kind"), "value": anchor_key.get("value")}
    if str(anchor_key.get("kind") or "") in SOURCE_SCOPED_KEYS:
        payload["source_types"] = source_types
    return payload


def _derive_entity_id(anchor_key: dict, source_types: list[str]) -> str:
    digest = hashlib.sha256(
        json.dumps(_anchor_payload(anchor_key, source_types), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"entity-{digest[:24]}"


def _component_source_types(records: list[dict]) -> list[str]:
    values = {
        str(((record.get("source") or {}).get("source_type") if isinstance(record.get("source"), dict) else "unknown") or "unknown")
        for record in records
    }
    return sorted(values)


def _component_anchor_key(records: list[dict]) -> dict:
    keys: list[dict] = []
    for record in records:
        keys.extend(_relationship_keys(record))
    if not keys:
        return {"kind": "event_id", "value": str(records[0].get("event_id") or "unknown"), "source": "ingestion"}
    return _sort_keys(keys)[0]


def _shared_supporting_keys(record: dict, component_records: list[dict]) -> list[dict]:
    record_markers = {(entry["kind"], entry["value"]) for entry in _relationship_keys(record)}
    markers: dict[tuple[str, str], dict] = {}
    counts: dict[tuple[str, str], int] = {}
    for item in component_records:
        for entry in _relationship_keys(item):
            marker = (entry["kind"], entry["value"])
            if marker in record_markers:
                markers.setdefault(marker, {"kind": entry["kind"], "value": entry["value"], "source": entry.get("source")})
                counts[marker] = counts.get(marker, 0) + 1
    shared = []
    for marker, entry in markers.items():
        enriched = dict(entry)
        enriched["shared_record_count"] = counts.get(marker, 0)
        shared.append(enriched)
    return _sort_keys(shared)


def _match_confidence(record: dict, component_records: list[dict]) -> float:
    supporting = _shared_supporting_keys(record, component_records)
    if not supporting:
        return 0.25
    best = _key_weight(str(supporting[0].get("kind") or "")) / 100.0
    if len(component_records) > 1:
        best = min(0.99, best + 0.04)
    else:
        best = max(0.35, best - 0.08)
    return round(best, 2)


def _match_reason(component_records: list[dict], confidence: float, supporting_keys: list[dict]) -> str:
    if not supporting_keys:
        return "No reusable relationship keys were available; created a standalone candidate entity"
    strongest = supporting_keys[0]
    kind = strongest.get("kind")
    count = len(component_records)
    if kind in {"zip_sha256", "zip_md5"} and count > 1:
        return f"Matched by shared content fingerprint ({kind}) across {count} records"
    if kind == "remote_id" and count > 1:
        return f"Matched by repeated provider record identity across {count} records"
    if confidence >= 0.9:
        return f"Strong candidate match derived from {kind}"
    if confidence >= 0.7:
        return f"Moderate candidate match derived from {kind}"
    return f"Low-confidence standalone candidate derived from {kind}"


def _reason_codes(record: dict, confidence: float, component_records: list[dict]) -> list[str]:
    codes: list[str] = []
    governance = record.get("governance") if isinstance(record.get("governance"), dict) else {}
    pipeline = record.get("pipeline") if isinstance(record.get("pipeline"), dict) else {}
    if bool(governance.get("review_required")):
        codes.append("review_required")
    if bool(governance.get("operator_approval_required")):
        codes.append("operator_approval_required")
    if str((pipeline.get("matched") or {}).get("status") or "pending") != "matched":
        codes.append("match_pending")
    if str((pipeline.get("approved") or {}).get("status") or "pending") != "approved":
        codes.append("approval_pending")
    if len(component_records) > 1:
        codes.append("candidate_match_available")
    else:
        codes.append("standalone_candidate")
    if confidence < 0.85:
        codes.append("low_confidence_match")
    return codes


def build_relationship_memory_snapshot(records: list[dict]) -> tuple[dict, dict[str, dict]]:
    cleaned_records = [redact_sensitive_fields(dict(record)) for record in records if isinstance(record, dict)]
    if not cleaned_records:
        return {
            "schema_version": RELATIONSHIP_MEMORY_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "entity_count": 0,
            "entities": [],
        }, {}

    _, find, union = _build_union_find(len(cleaned_records))
    key_index: dict[tuple[str, str], list[int]] = {}
    for index, record in enumerate(cleaned_records):
        for entry in _relationship_keys(record):
            key_index.setdefault((entry["kind"], entry["value"]), []).append(index)
    for indices in key_index.values():
        if len(indices) < 2:
            continue
        base = indices[0]
        for other in indices[1:]:
            union(base, other)

    components: dict[int, list[int]] = {}
    for index in range(len(cleaned_records)):
        components.setdefault(find(index), []).append(index)

    entities: list[dict] = []
    suggestions: dict[str, dict] = {}
    for root in sorted(components):
        component_indices = sorted(components[root])
        component_records = [cleaned_records[index] for index in component_indices]
        source_types = _component_source_types(component_records)
        anchor_key = _component_anchor_key(component_records)
        entity_id = _derive_entity_id(anchor_key, source_types)
        aggregated_keys = _sort_keys(
            [entry for record in component_records for entry in _relationship_keys(record)]
        )
        evidence_refs = []
        for record in component_records:
            source = record.get("source") if isinstance(record.get("source"), dict) else {}
            evidence = record.get("evidence") if isinstance(record.get("evidence"), dict) else {}
            event_id = str(record.get("event_id") or "")
            supporting_keys = _shared_supporting_keys(record, component_records)
            confidence = _match_confidence(record, component_records)
            suggestion = {
                "entity_id": entity_id,
                "entity_type": "evidence-artifact",
                "anchor_key": anchor_key,
                "confidence": confidence,
                "supporting_keys": supporting_keys,
                "component_record_count": len(component_records),
                "reason": _match_reason(component_records, confidence, supporting_keys),
                "matched_at": utcnow_iso(),
            }
            if event_id:
                suggestions[event_id] = suggestion
            evidence_refs.append(
                {
                    "event_id": event_id,
                    "inventory_ref": evidence.get("inventory_ref"),
                    "audit_ref": evidence.get("audit_ref"),
                    "monitoring_ref": evidence.get("monitoring_ref"),
                    "source_record_id": source.get("source_record_id"),
                    "source_type": source.get("source_type"),
                }
            )
        entity = {
            "entity_id": entity_id,
            "entity_type": "evidence-artifact",
            "anchor_key": anchor_key,
            "source_types": source_types,
            "record_count": len(component_records),
            "relationship_keys": aggregated_keys,
            "evidence_refs": evidence_refs,
            "review_recommended": any(bool((record.get("governance") or {}).get("review_required")) for record in component_records),
        }
        entities.append(redact_sensitive_fields(entity))

    snapshot = {
        "schema_version": RELATIONSHIP_MEMORY_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "entity_count": len(entities),
        "entities": entities,
    }
    return redact_sensitive_fields(snapshot), redact_sensitive_fields(suggestions)


def _priority(reason_codes: list[str], confidence: float) -> str:
    if "review_required" in reason_codes or "operator_approval_required" in reason_codes or confidence < 0.75:
        return "high"
    return "normal"


def _queue_item_id(event_id: str, stage: str) -> str:
    digest = hashlib.sha256(f"{event_id}:{stage}".encode("utf-8")).hexdigest()
    return f"review-{digest[:24]}"


def build_operator_review_queue(records: list[dict], suggestions: dict[str, dict]) -> dict:
    items: list[dict] = []
    for record in [redact_sensitive_fields(dict(item)) for item in records if isinstance(item, dict)]:
        event_id = str(record.get("event_id") or "")
        if not event_id:
            continue
        pipeline = record.get("pipeline") if isinstance(record.get("pipeline"), dict) else {}
        matched_status = str((pipeline.get("matched") or {}).get("status") or "pending")
        approved_status = str((pipeline.get("approved") or {}).get("status") or "pending")
        governance = record.get("governance") if isinstance(record.get("governance"), dict) else {}
        suggestion = redact_sensitive_fields(dict(suggestions.get(event_id) or {}))
        confidence = float(suggestion.get("confidence") or 0.0)
        reason_codes = _reason_codes(record, confidence, [record] * int(suggestion.get("component_record_count") or 1))
        unresolved_match = matched_status in {"pending", "needs_review"}
        unresolved_approval = approved_status in {"pending", "needs_review"}
        should_queue = bool(governance.get("review_required")) or unresolved_match or unresolved_approval
        if not should_queue:
            continue
        next_stage = "matched" if unresolved_match else "approved"
        source = record.get("source") if isinstance(record.get("source"), dict) else {}
        evidence = record.get("evidence") if isinstance(record.get("evidence"), dict) else {}
        item = {
            "schema_version": REVIEW_QUEUE_SCHEMA_VERSION,
            "queue_item_id": _queue_item_id(event_id, next_stage),
            "state": "open",
            "priority": _priority(reason_codes, confidence),
            "review_type": "match-and-approval",
            "event_id": event_id,
            "next_pipeline_stage": next_stage,
            "reason_codes": reason_codes,
            "suggested_match": suggestion,
            "source": {
                "source_type": source.get("source_type"),
                "source_record_id": source.get("source_record_id"),
            },
            "evidence": {
                "inventory_ref": evidence.get("inventory_ref"),
                "audit_ref": evidence.get("audit_ref"),
                "monitoring_ref": evidence.get("monitoring_ref"),
                "zip_sha256": evidence.get("zip_sha256"),
                "zip_path": evidence.get("zip_path"),
                "start_here": evidence.get("start_here"),
                "outcome": evidence.get("outcome"),
            },
            "governance": {
                "review_required": governance.get("review_required"),
                "operator_approval_required": governance.get("operator_approval_required"),
                "approval_gate": governance.get("approval_gate"),
                "policy_decision": governance.get("policy_decision"),
                "policy_reason": governance.get("policy_reason"),
            },
        }
        items.append(redact_sensitive_fields(item))

    items.sort(key=lambda entry: (0 if entry.get("priority") == "high" else 1, str(entry.get("queue_item_id") or "")))
    counts = {
        "priority": {
            "high": sum(1 for item in items if item.get("priority") == "high"),
            "normal": sum(1 for item in items if item.get("priority") == "normal"),
        },
        "next_pipeline_stage": {
            "matched": sum(1 for item in items if item.get("next_pipeline_stage") == "matched"),
            "approved": sum(1 for item in items if item.get("next_pipeline_stage") == "approved"),
        },
    }
    return {
        "schema_version": REVIEW_QUEUE_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "item_count": len(items),
        "counts": counts,
        "items": items,
    }


def render_operator_review_queue_markdown(queue: dict) -> str:
    lines = [
        "# Operator review queue",
        "",
        f"Generated at: {queue.get('generated_at')}",
        f"Open items: {queue.get('item_count')}",
        "",
    ]
    counts = queue.get("counts") if isinstance(queue.get("counts"), dict) else {}
    priority = counts.get("priority") if isinstance(counts.get("priority"), dict) else {}
    next_stage = counts.get("next_pipeline_stage") if isinstance(counts.get("next_pipeline_stage"), dict) else {}
    lines.extend(
        [
            f"- High priority: {priority.get('high', 0)}",
            f"- Normal priority: {priority.get('normal', 0)}",
            f"- Awaiting match review: {next_stage.get('matched', 0)}",
            f"- Awaiting approval review: {next_stage.get('approved', 0)}",
            "",
        ]
    )
    for item in queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        suggestion = item.get("suggested_match") if isinstance(item.get("suggested_match"), dict) else {}
        lines.extend(
            [
                f"## {item.get('queue_item_id')}",
                f"- Priority: {item.get('priority')}",
                f"- Event: {item.get('event_id')}",
                f"- Next stage: {item.get('next_pipeline_stage')}",
                f"- Suggested entity: {suggestion.get('entity_id')}",
                f"- Confidence: {suggestion.get('confidence')}",
                f"- Reason codes: {', '.join(item.get('reason_codes') or [])}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"

def load_ingestion_records(path: str | Path) -> list[dict]:
    target = Path(path)
    if target.is_dir():
        candidate = target / "ingestion-events.jsonl"
        if candidate.exists():
            target = candidate
        else:
            matches = sorted(target.glob("*.jsonl"))
            if not matches:
                return []
            target = matches[0]
    return list(iter_ingestion_records(target))
