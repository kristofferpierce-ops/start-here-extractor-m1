from __future__ import annotations

import hashlib
import json
from pathlib import Path
from .adapter_contracts import render_adapter_execution_contracts_markdown
from .ingestion import utcnow_iso
from .security import redact_sensitive_fields


ADAPTER_EXECUTION_JOURNAL_SCHEMA_VERSION = "1.0"
ADAPTER_EXECUTION_ROLLUP_SCHEMA_VERSION = "1.0"
ADAPTER_EXECUTION_OUTCOME_ACTIONS = {
    "dry_run_success": {"contract_state": "validated", "execution_status": "dry_run_succeeded", "followup_required": False},
    "execute_success": {"contract_state": "completed", "execution_status": "succeeded", "followup_required": False},
    "execute_failure": {"contract_state": "failed", "execution_status": "failed", "followup_required": True},
    "skip": {"contract_state": "skipped", "execution_status": "skipped", "followup_required": False},
    "defer": {"contract_state": "deferred", "execution_status": "deferred", "followup_required": True},
}


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def load_adapter_execution_contracts(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Adapter execution contracts must be a JSON object")


def load_execution_decisions(path: str | Path) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("decisions"), list):
        return [redact_sensitive_fields(item) for item in payload["decisions"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [redact_sensitive_fields(item) for item in payload if isinstance(item, dict)]
    raise ValueError("Execution decisions must be a JSON object with a decisions list or a JSON list")


def derive_execution_event_id(contract_id: str, action: str, executed_at: str) -> str:
    payload = {"contract_id": contract_id, "action": action, "executed_at": executed_at}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"adapter-exec-{digest[:24]}"


def _decision_ref(execution_event_id: str) -> str:
    return f"adapter-execution://{execution_event_id}"


def _contract_index(contracts_doc: dict) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for contract in contracts_doc.get("contracts") or []:
        if not isinstance(contract, dict):
            continue
        contract_id = _normalize_text(contract.get("contract_id"))
        if contract_id:
            index[contract_id] = contract
    return index


def _record_index(records: list[dict]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        event_id = _normalize_text(record.get("event_id"))
        if not event_id:
            continue
        index.setdefault(event_id, []).append(record)
    return index


def _apply_contract_outcome(contract: dict, decision: dict, actor_id: str | None) -> tuple[dict, dict]:
    action = _normalize_text(decision.get("outcome_action")) or "defer"
    mapping = ADAPTER_EXECUTION_OUTCOME_ACTIONS.get(action)
    if mapping is None:
        raise ValueError(f"Unsupported outcome_action: {action}")

    executed_at = _normalize_text(decision.get("executed_at")) or utcnow_iso()
    contract_id = _normalize_text(contract.get("contract_id")) or "unknown"
    execution_event_id = derive_execution_event_id(contract_id, action, executed_at)
    execution_ref = _normalize_text(decision.get("execution_ref")) or _decision_ref(execution_event_id)
    executed_by = _normalize_text(decision.get("executed_by")) or _normalize_text(decision.get("decision_by")) or actor_id
    reason = _normalize_text(decision.get("reason"))
    external_ref = _normalize_text(decision.get("external_ref"))
    status_code = _normalize_text(decision.get("status_code"))

    contract.update(
        redact_sensitive_fields(
            {
                "contract_state": mapping["contract_state"],
                "execution_status": mapping["execution_status"],
                "executed_at": executed_at,
                "execution_ref": execution_ref,
                "executed_by": executed_by,
                "execution_reason": reason,
                "external_ref": external_ref,
                "status_code": status_code,
                "result": {
                    "outcome_action": action,
                    "execution_status": mapping["execution_status"],
                    "reason": reason,
                    "external_ref": external_ref,
                    "status_code": status_code,
                },
            }
        )
    )

    event = redact_sensitive_fields(
        {
            "schema_version": ADAPTER_EXECUTION_JOURNAL_SCHEMA_VERSION,
            "execution_event_id": execution_event_id,
            "recorded_at": executed_at,
            "decision_ref": execution_ref,
            "actor_id": executed_by,
            "contract_id": contract_id,
            "event_id": contract.get("event_id"),
            "outcome_action": action,
            "contract_state": mapping["contract_state"],
            "execution_status": mapping["execution_status"],
            "reason": reason,
            "external_ref": external_ref,
            "status_code": status_code,
            "adapter": contract.get("adapter"),
            "target": contract.get("target"),
            "evidence": contract.get("evidence"),
            "governance": {
                "followup_required": mapping["followup_required"],
                "review_required": mapping["followup_required"],
            },
        }
    )
    return contract, event


def _ingest_outcome(record: dict, contract: dict, event: dict) -> dict:
    pipeline = record.setdefault("pipeline", {})
    applied = pipeline.setdefault("applied", {})
    governance = record.setdefault("governance", {})
    execution_status = event.get("execution_status")
    followup_required = bool(((event.get("governance") or {}).get("followup_required") if isinstance(event.get("governance"), dict) else False))

    applied.update(
        redact_sensitive_fields(
            {
                "execution_status": execution_status,
                "executed_at": event.get("recorded_at"),
                "execution_ref": event.get("decision_ref"),
                "adapter_contract_id": contract.get("contract_id"),
                "adapter_key": ((contract.get("adapter") or {}).get("adapter_key") if isinstance(contract.get("adapter"), dict) else None),
                "execution_mode": contract.get("execution_mode"),
                "external_ref": event.get("external_ref"),
            }
        )
    )
    governance.update(
        redact_sensitive_fields(
            {
                "last_execution_ref": event.get("decision_ref"),
                "execution_state": execution_status,
                "execution_followup_required": followup_required,
                "last_adapter_contract_id": contract.get("contract_id"),
                "review_required": bool(governance.get("review_required")) or followup_required,
                "review_state": "execution_followup_required" if followup_required else governance.get("review_state"),
            }
        )
    )
    return redact_sensitive_fields(record)


def apply_adapter_execution_outcomes(
    records: list[dict],
    contracts_doc: dict,
    decisions: list[dict],
    *,
    actor_id: str | None = None,
) -> tuple[list[dict], dict, list[dict], dict]:
    updated_records = [redact_sensitive_fields(json.loads(json.dumps(record))) for record in records]
    updated_contracts_doc = redact_sensitive_fields(json.loads(json.dumps(contracts_doc)))
    contract_index = _contract_index(updated_contracts_doc)
    record_index = _record_index(updated_records)
    journal: list[dict] = []
    ignored_decisions = 0

    for decision in decisions:
        contract_id = _normalize_text(decision.get("contract_id"))
        if not contract_id or contract_id not in contract_index:
            ignored_decisions += 1
            continue
        contract = contract_index[contract_id]
        contract, event = _apply_contract_outcome(contract, decision, actor_id)
        journal.append(event)
        for record in record_index.get(_normalize_text(contract.get("event_id")) or "", []):
            _ingest_outcome(record, contract, event)

    updated_contracts_doc["contracts"] = sorted(
        [redact_sensitive_fields(contract) for contract in contract_index.values()],
        key=lambda item: str(item.get("contract_id") or ""),
    )
    updated_contracts_doc["contract_count"] = len(updated_contracts_doc["contracts"])
    rollup = build_adapter_execution_rollup(updated_records, updated_contracts_doc, journal, ignored_decisions=ignored_decisions)
    return updated_records, updated_contracts_doc, [redact_sensitive_fields(item) for item in journal], redact_sensitive_fields(rollup)


def build_adapter_execution_rollup(
    records: list[dict],
    contracts_doc: dict,
    journal: list[dict],
    *,
    ignored_decisions: int = 0,
) -> dict:
    contract_state_counts: dict[str, int] = {}
    execution_status_counts: dict[str, int] = {}
    adapter_family_counts: dict[str, int] = {}
    target_system_counts: dict[str, int] = {}
    record_execution_status_counts: dict[str, int] = {}
    followup_required_count = 0

    for contract in contracts_doc.get("contracts") or []:
        if not isinstance(contract, dict):
            continue
        contract_state = _normalize_text(contract.get("contract_state")) or "planned"
        execution_status = _normalize_text(contract.get("execution_status")) or "not_started"
        adapter = contract.get("adapter") if isinstance(contract.get("adapter"), dict) else {}
        target = contract.get("target") if isinstance(contract.get("target"), dict) else {}
        adapter_family = _normalize_text(adapter.get("adapter_family")) or "generic"
        target_system = _normalize_text(target.get("target_system")) or "unknown"
        contract_state_counts[contract_state] = contract_state_counts.get(contract_state, 0) + 1
        execution_status_counts[execution_status] = execution_status_counts.get(execution_status, 0) + 1
        adapter_family_counts[adapter_family] = adapter_family_counts.get(adapter_family, 0) + 1
        target_system_counts[target_system] = target_system_counts.get(target_system, 0) + 1

    for record in records:
        if not isinstance(record, dict):
            continue
        pipeline = record.get("pipeline") if isinstance(record.get("pipeline"), dict) else {}
        applied = pipeline.get("applied") if isinstance(pipeline.get("applied"), dict) else {}
        execution_status = _normalize_text(applied.get("execution_status")) or "not_started"
        record_execution_status_counts[execution_status] = record_execution_status_counts.get(execution_status, 0) + 1
        governance = record.get("governance") if isinstance(record.get("governance"), dict) else {}
        if bool(governance.get("execution_followup_required")):
            followup_required_count += 1

    return {
        "schema_version": ADAPTER_EXECUTION_ROLLUP_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "record_count": len(records),
        "contract_count": int(contracts_doc.get("contract_count") or 0),
        "journal_count": len(journal),
        "ignored_decision_count": ignored_decisions,
        "followup_required_count": followup_required_count,
        "contract_state_counts": contract_state_counts,
        "execution_status_counts": execution_status_counts,
        "record_execution_status_counts": record_execution_status_counts,
        "adapter_family_counts": adapter_family_counts,
        "target_system_counts": target_system_counts,
    }


def render_adapter_execution_rollup_markdown(rollup: dict) -> str:
    lines = [
        "# Adapter execution rollup",
        "",
        f"Generated at: {rollup.get('generated_at')}",
        f"Record count: {rollup.get('record_count', 0)}",
        f"Contract count: {rollup.get('contract_count', 0)}",
        f"Journal entries: {rollup.get('journal_count', 0)}",
        f"Ignored decisions: {rollup.get('ignored_decision_count', 0)}",
        f"Follow-up required: {rollup.get('followup_required_count', 0)}",
        "",
        "## Contract state counts",
    ]
    for key, value in sorted((rollup.get("contract_state_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Execution status counts"])
    for key, value in sorted((rollup.get("execution_status_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Record execution status counts"])
    for key, value in sorted((rollup.get("record_execution_status_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Target system counts"])
    for key, value in sorted((rollup.get("target_system_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).strip() + "\n"


def render_adapter_execution_journal_markdown(journal: list[dict]) -> str:
    lines = [
        "# Adapter execution journal",
        "",
        f"Entries: {len(journal)}",
        "",
    ]
    if not journal:
        lines.append("No adapter execution outcomes were recorded.")
        return "\n".join(lines).strip() + "\n"
    for item in journal:
        target = item.get("target") if isinstance(item.get("target"), dict) else {}
        adapter = item.get("adapter") if isinstance(item.get("adapter"), dict) else {}
        lines.extend(
            [
                f"## {item.get('execution_event_id')}",
                f"- Contract: {item.get('contract_id')}",
                f"- Event: {item.get('event_id')}",
                f"- Outcome: {item.get('outcome_action')} -> {item.get('execution_status')}",
                f"- Adapter: {adapter.get('adapter_key')}",
                f"- Target: {target.get('target_key')} ({target.get('target_system')})",
                f"- Recorded at: {item.get('recorded_at')}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def render_adapter_execution_contracts_post_execute_markdown(contracts_doc: dict) -> str:
    lines = [render_adapter_execution_contracts_markdown(contracts_doc).rstrip(), "", "## Execution outcomes", ""]
    contracts = contracts_doc.get("contracts") if isinstance(contracts_doc.get("contracts"), list) else []
    if not contracts:
        lines.append("No contracts remain.")
        return "\n".join(lines).strip() + "\n"
    for contract in contracts:
        lines.extend(
            [
                f"- {contract.get('contract_id')}: {contract.get('contract_state')} / {contract.get('execution_status') or 'not_started'}",
            ]
        )
    return "\n".join(lines).strip() + "\n"


__all__ = [
    "ADAPTER_EXECUTION_JOURNAL_SCHEMA_VERSION",
    "ADAPTER_EXECUTION_OUTCOME_ACTIONS",
    "ADAPTER_EXECUTION_ROLLUP_SCHEMA_VERSION",
    "apply_adapter_execution_outcomes",
    "build_adapter_execution_rollup",
    "derive_execution_event_id",
    "load_adapter_execution_contracts",
    "load_execution_decisions",
    "render_adapter_execution_contracts_post_execute_markdown",
    "render_adapter_execution_journal_markdown",
    "render_adapter_execution_rollup_markdown",
]
