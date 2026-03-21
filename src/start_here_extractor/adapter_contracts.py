from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .security import redact_sensitive_fields


ADAPTER_EXECUTION_CONTRACTS_SCHEMA_VERSION = "1.0"
ADAPTER_CONTRACT_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
ADAPTER_CONTRACT_ROLLUP_SCHEMA_VERSION = "1.0"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_bool(value: object, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        normalized = _normalize_text(item)
        if normalized and normalized not in items:
            items.append(normalized)
    return items


def normalize_adapter_catalog(value: object) -> list[dict]:
    if isinstance(value, dict):
        entries = value.get("adapters") if isinstance(value.get("adapters"), list) else []
    elif isinstance(value, list):
        entries = value
    else:
        entries = []

    normalized: list[dict] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        adapter_key = _normalize_text(item.get("adapter_key"))
        if not adapter_key:
            continue
        target_key = _normalize_text(item.get("target_key"))
        target_system = _normalize_text(item.get("target_system"))
        target_type = _normalize_text(item.get("target_type"))
        normalized.append(
            redact_sensitive_fields(
                {
                    "adapter_key": adapter_key,
                    "adapter_family": _normalize_text(item.get("adapter_family")) or "generic",
                    "adapter_version": _normalize_text(item.get("adapter_version")) or "1.0",
                    "contract_version": _normalize_text(item.get("contract_version")) or "1.0",
                    "operation": _normalize_text(item.get("operation")) or "upsert-record",
                    "execution_mode": _normalize_text(item.get("execution_mode")) or "dry_run",
                    "target_key": target_key,
                    "target_system": target_system,
                    "target_type": target_type,
                    "supported_content_families": _normalize_str_list(item.get("supported_content_families")),
                    "supported_source_types": _normalize_str_list(item.get("supported_source_types")),
                    "required_fields": _normalize_str_list(item.get("required_fields")),
                    "active": _normalize_bool(item.get("active"), default=True),
                }
            )
        )
    normalized.sort(key=lambda item: str(item.get("adapter_key") or ""))
    return normalized


def load_adapter_catalog(path: str | Path) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return normalize_adapter_catalog(payload)


def _applied_records(records: Iterable[dict]) -> list[dict]:
    result: list[dict] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        record = redact_sensitive_fields(dict(item))
        pipeline = record.get("pipeline") if isinstance(record.get("pipeline"), dict) else {}
        applied = pipeline.get("applied") if isinstance(pipeline.get("applied"), dict) else {}
        if str(applied.get("status") or "pending") == "applied":
            result.append(record)
    return result


def _get_path(record: dict, dotted_path: str) -> object:
    value: object = record
    for part in dotted_path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _compatible(record: dict, adapter: dict) -> bool:
    if not _normalize_bool(adapter.get("active"), default=True):
        return False
    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    pipeline = record.get("pipeline") if isinstance(record.get("pipeline"), dict) else {}
    applied = pipeline.get("applied") if isinstance(pipeline.get("applied"), dict) else {}
    target_key = _normalize_text(applied.get("target_key"))
    target_system = _normalize_text(applied.get("target_system"))
    target_type = _normalize_text(applied.get("target_type"))
    content_family = _normalize_text(source.get("content_family"))
    source_type = _normalize_text(source.get("source_type"))

    adapter_target_key = _normalize_text(adapter.get("target_key"))
    adapter_target_system = _normalize_text(adapter.get("target_system"))
    adapter_target_type = _normalize_text(adapter.get("target_type"))
    if adapter_target_key and adapter_target_key != target_key:
        return False
    if adapter_target_system and adapter_target_system != target_system:
        return False
    if adapter_target_type and adapter_target_type != target_type:
        return False

    supported_families = adapter.get("supported_content_families") if isinstance(adapter.get("supported_content_families"), list) else []
    supported_sources = adapter.get("supported_source_types") if isinstance(adapter.get("supported_source_types"), list) else []
    if supported_families and content_family not in supported_families:
        return False
    if supported_sources and source_type not in supported_sources:
        return False
    return True


def _adapter_candidates(record: dict, adapter_catalog: list[dict]) -> list[dict]:
    return [redact_sensitive_fields(dict(item)) for item in adapter_catalog if _compatible(record, item)]


def _missing_required_fields(record: dict, adapter: dict) -> list[str]:
    required_fields = adapter.get("required_fields") if isinstance(adapter.get("required_fields"), list) else []
    missing: list[str] = []
    for field in required_fields:
        value = _get_path(record, str(field))
        if value is None or value == "" or value == [] or value == {}:
            missing.append(str(field))
    return missing


def derive_adapter_contract_id(record: dict, adapter: dict) -> str:
    stable_payload = {
        "event_id": _normalize_text(record.get("event_id")),
        "adapter_key": _normalize_text(adapter.get("adapter_key")),
        "operation": _normalize_text(adapter.get("operation")),
        "target_key": _normalize_text(((record.get("pipeline") or {}).get("applied") or {}).get("target_key")),
    }
    digest = hashlib.sha256(json.dumps(stable_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"adapter-contract-{digest[:24]}"


def _idempotency_key(record: dict, adapter: dict) -> str:
    contract_id = derive_adapter_contract_id(record, adapter)
    digest = hashlib.sha256(contract_id.encode("utf-8")).hexdigest()
    return f"idem-{digest[:24]}"


def _queue_item_id(record: dict) -> str:
    event_id = _normalize_text(record.get("event_id")) or "unknown"
    digest = hashlib.sha256(f"{event_id}:adapter".encode("utf-8")).hexdigest()
    return f"adapter-review-{digest[:24]}"


def _contract_payload(record: dict, adapter: dict) -> dict:
    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    evidence = record.get("evidence") if isinstance(record.get("evidence"), dict) else {}
    pipeline = record.get("pipeline") if isinstance(record.get("pipeline"), dict) else {}
    matched = pipeline.get("matched") if isinstance(pipeline.get("matched"), dict) else {}
    approved = pipeline.get("approved") if isinstance(pipeline.get("approved"), dict) else {}
    applied = pipeline.get("applied") if isinstance(pipeline.get("applied"), dict) else {}
    return redact_sensitive_fields(
        {
            "event_id": record.get("event_id"),
            "source_record_id": source.get("source_record_id"),
            "content_family": source.get("content_family"),
            "entity_type": matched.get("entity_type"),
            "entity_id": matched.get("entity_id"),
            "approval_decision_ref": approved.get("decision_ref"),
            "application_decision_ref": applied.get("decision_ref"),
            "inventory_ref": evidence.get("inventory_ref"),
            "audit_ref": evidence.get("audit_ref"),
            "monitoring_ref": evidence.get("monitoring_ref"),
            "zip_sha256": evidence.get("zip_sha256"),
            "start_here": evidence.get("start_here"),
            "target_key": applied.get("target_key"),
            "target_system": applied.get("target_system"),
            "target_id": applied.get("target_id"),
            "adapter_key": adapter.get("adapter_key"),
            "operation": adapter.get("operation"),
        }
    )


def _build_contract(record: dict, adapter: dict) -> dict:
    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    evidence = record.get("evidence") if isinstance(record.get("evidence"), dict) else {}
    governance = record.get("governance") if isinstance(record.get("governance"), dict) else {}
    provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
    pipeline = record.get("pipeline") if isinstance(record.get("pipeline"), dict) else {}
    applied = pipeline.get("applied") if isinstance(pipeline.get("applied"), dict) else {}
    matched = pipeline.get("matched") if isinstance(pipeline.get("matched"), dict) else {}
    contract_id = derive_adapter_contract_id(record, adapter)
    return redact_sensitive_fields(
        {
            "schema_version": ADAPTER_EXECUTION_CONTRACTS_SCHEMA_VERSION,
            "contract_id": contract_id,
            "contract_state": "planned",
            "execution_status": "not_started",
            "created_at": utcnow_iso(),
            "contract_version": adapter.get("contract_version"),
            "execution_mode": adapter.get("execution_mode"),
            "idempotency_key": _idempotency_key(record, adapter),
            "event_id": record.get("event_id"),
            "operation": adapter.get("operation"),
            "source": {
                "source_type": source.get("source_type"),
                "source_record_id": source.get("source_record_id"),
                "content_family": source.get("content_family"),
            },
            "target": {
                "target_key": applied.get("target_key"),
                "target_type": applied.get("target_type"),
                "target_system": applied.get("target_system"),
                "target_id": applied.get("target_id"),
            },
            "adapter": {
                "adapter_key": adapter.get("adapter_key"),
                "adapter_family": adapter.get("adapter_family"),
                "adapter_version": adapter.get("adapter_version"),
                "required_fields": adapter.get("required_fields"),
            },
            "matched": {
                "entity_type": matched.get("entity_type"),
                "entity_id": matched.get("entity_id"),
            },
            "payload": _contract_payload(record, adapter),
            "evidence": {
                "inventory_ref": evidence.get("inventory_ref"),
                "audit_ref": evidence.get("audit_ref"),
                "monitoring_ref": evidence.get("monitoring_ref"),
                "zip_sha256": evidence.get("zip_sha256"),
                "start_here": evidence.get("start_here"),
            },
            "governance": {
                "retention_status": governance.get("retention_status"),
                "review_required": governance.get("review_required"),
                "review_state": governance.get("review_state"),
                "application_state": governance.get("application_state"),
            },
            "provenance": provenance,
        }
    )


def build_adapter_execution_artifacts(records: list[dict], adapter_catalog: list[dict]) -> tuple[dict, dict, dict]:
    applied_records = _applied_records(records)
    contracts: list[dict] = []
    review_items: list[dict] = []

    for record in applied_records:
        candidates = _adapter_candidates(record, adapter_catalog)
        event_id = _normalize_text(record.get("event_id"))
        pipeline = record.get("pipeline") if isinstance(record.get("pipeline"), dict) else {}
        applied = pipeline.get("applied") if isinstance(pipeline.get("applied"), dict) else {}
        reason_codes = ["applied_pending_adapter_contract"]
        if not candidates:
            reason_codes.append("no_adapter_match")
        elif len(candidates) > 1:
            reason_codes.append("multiple_adapter_matches")
        else:
            missing_fields = _missing_required_fields(record, candidates[0])
            if missing_fields:
                reason_codes.extend(["adapter_missing_required_fields", *[f"missing:{field}" for field in missing_fields]])

        if len(candidates) == 1 and "adapter_missing_required_fields" not in reason_codes:
            contracts.append(_build_contract(record, candidates[0]))
            continue

        review_items.append(
            redact_sensitive_fields(
                {
                    "schema_version": ADAPTER_CONTRACT_REVIEW_QUEUE_SCHEMA_VERSION,
                    "queue_item_id": _queue_item_id(record),
                    "state": "open",
                    "priority": "high",
                    "review_type": "adapter-contract-routing",
                    "event_id": event_id,
                    "reason_codes": reason_codes,
                    "target": {
                        "target_key": applied.get("target_key"),
                        "target_type": applied.get("target_type"),
                        "target_system": applied.get("target_system"),
                        "target_id": applied.get("target_id"),
                    },
                    "candidate_adapters": [
                        {
                            "adapter_key": item.get("adapter_key"),
                            "adapter_family": item.get("adapter_family"),
                            "adapter_version": item.get("adapter_version"),
                            "operation": item.get("operation"),
                            "execution_mode": item.get("execution_mode"),
                        }
                        for item in candidates
                    ],
                }
            )
        )

    contracts_doc = {
        "schema_version": ADAPTER_EXECUTION_CONTRACTS_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "contract_count": len(contracts),
        "contracts": sorted(contracts, key=lambda item: str(item.get("contract_id") or "")),
    }
    review_queue = {
        "schema_version": ADAPTER_CONTRACT_REVIEW_QUEUE_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "item_count": len(review_items),
        "items": sorted(review_items, key=lambda item: str(item.get("queue_item_id") or "")),
    }
    rollup = build_adapter_contract_rollup(contracts_doc, review_queue)
    return redact_sensitive_fields(contracts_doc), redact_sensitive_fields(review_queue), redact_sensitive_fields(rollup)


def build_adapter_contract_rollup(contracts_doc: dict, review_queue: dict) -> dict:
    contract_state_counts: dict[str, int] = {}
    execution_mode_counts: dict[str, int] = {}
    operation_counts: dict[str, int] = {}
    target_system_counts: dict[str, int] = {}
    adapter_family_counts: dict[str, int] = {}
    for contract in contracts_doc.get("contracts") or []:
        if not isinstance(contract, dict):
            continue
        contract_state = _normalize_text(contract.get("contract_state")) or "planned"
        execution_mode = _normalize_text(contract.get("execution_mode")) or "dry_run"
        operation = _normalize_text(contract.get("operation")) or "unknown"
        target_system = _normalize_text(((contract.get("target") or {}).get("target_system") if isinstance(contract.get("target"), dict) else None)) or "unknown"
        adapter_family = _normalize_text(((contract.get("adapter") or {}).get("adapter_family") if isinstance(contract.get("adapter"), dict) else None)) or "generic"
        contract_state_counts[contract_state] = contract_state_counts.get(contract_state, 0) + 1
        execution_mode_counts[execution_mode] = execution_mode_counts.get(execution_mode, 0) + 1
        operation_counts[operation] = operation_counts.get(operation, 0) + 1
        target_system_counts[target_system] = target_system_counts.get(target_system, 0) + 1
        adapter_family_counts[adapter_family] = adapter_family_counts.get(adapter_family, 0) + 1

    queue_reason_counts: dict[str, int] = {}
    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        for reason in item.get("reason_codes") or []:
            normalized = _normalize_text(reason)
            if normalized:
                queue_reason_counts[normalized] = queue_reason_counts.get(normalized, 0) + 1

    return {
        "schema_version": ADAPTER_CONTRACT_ROLLUP_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "contract_count": int(contracts_doc.get("contract_count") or 0),
        "review_queue_count": int(review_queue.get("item_count") or 0),
        "contract_state_counts": contract_state_counts,
        "execution_mode_counts": execution_mode_counts,
        "operation_counts": operation_counts,
        "target_system_counts": target_system_counts,
        "adapter_family_counts": adapter_family_counts,
        "review_reason_counts": queue_reason_counts,
    }


def render_adapter_execution_contracts_markdown(contracts_doc: dict) -> str:
    lines = [
        "# Adapter execution contracts",
        "",
        f"Generated at: {contracts_doc.get('generated_at')}",
        f"Contract count: {contracts_doc.get('contract_count', 0)}",
        "",
    ]
    contracts = contracts_doc.get("contracts") if isinstance(contracts_doc.get("contracts"), list) else []
    if not contracts:
        lines.append("No adapter execution contracts were generated.")
        return "\n".join(lines).strip() + "\n"
    for contract in contracts:
        target = contract.get("target") if isinstance(contract.get("target"), dict) else {}
        adapter = contract.get("adapter") if isinstance(contract.get("adapter"), dict) else {}
        lines.extend(
            [
                f"## {contract.get('contract_id')}",
                f"- Event: {contract.get('event_id')}",
                f"- Target: {target.get('target_key')} ({target.get('target_system')})",
                f"- Adapter: {adapter.get('adapter_key')} ({adapter.get('adapter_family')})",
                f"- Operation: {contract.get('operation')}",
                f"- Execution mode: {contract.get('execution_mode')}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def render_adapter_contract_review_queue_markdown(review_queue: dict) -> str:
    lines = [
        "# Adapter contract review queue",
        "",
        f"Generated at: {review_queue.get('generated_at')}",
        f"Open items: {review_queue.get('item_count', 0)}",
        "",
    ]
    items = review_queue.get("items") if isinstance(review_queue.get("items"), list) else []
    if not items:
        lines.append("No adapter contract review items remain.")
        return "\n".join(lines).strip() + "\n"
    for item in items:
        lines.extend(
            [
                f"## {item.get('queue_item_id')}",
                f"- Event: {item.get('event_id')}",
                f"- Reasons: {', '.join(item.get('reason_codes') or [])}",
                f"- Candidate adapters: {', '.join([str((candidate or {}).get('adapter_key') or '') for candidate in (item.get('candidate_adapters') or [])]) or 'none'}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def render_adapter_contract_rollup_markdown(rollup: dict) -> str:
    lines = [
        "# Adapter contract rollup",
        "",
        f"Generated at: {rollup.get('generated_at')}",
        f"Contract count: {rollup.get('contract_count', 0)}",
        f"Review queue count: {rollup.get('review_queue_count', 0)}",
        "",
        "## Contract state counts",
    ]
    for key, value in sorted((rollup.get("contract_state_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Execution mode counts"])
    for key, value in sorted((rollup.get("execution_mode_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Adapter family counts"])
    for key, value in sorted((rollup.get("adapter_family_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Review reason counts"])
    for key, value in sorted((rollup.get("review_reason_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).strip() + "\n"
