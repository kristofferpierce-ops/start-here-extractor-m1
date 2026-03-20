from __future__ import annotations

from typing import Any, Dict

from .security import redact_sensitive_fields


def build_governance_block(record: dict, *, operator_approval_ref: str | None, require_operator_approval_for_abuse: bool, acknowledge_abuse: bool, audit_stream_ref: str | None, retention: dict | None, monitoring_stream_ref: str | None = None, token_health: dict | None = None) -> Dict[str, Any]:
    source_type = None
    prov = record.get("provenance")
    if isinstance(prov, dict):
        source_type = prov.get("source_type")

    sandbox = record.get("sandbox") if isinstance(record.get("sandbox"), dict) else {}
    policy_decision = record.get("policy_decision") if isinstance(record.get("policy_decision"), dict) else {}
    approval_required = bool(source_type == "gdrive" and acknowledge_abuse and require_operator_approval_for_abuse)
    review_required = bool(approval_required or sandbox.get("enabled") or policy_decision.get("decision") in {"warn", "sandbox", "reject"})
    return {
        "evidence_kind": "zip-inventory",
        "source_type": source_type,
        "approval_gate": "cloud-abuse-download" if approval_required else None,
        "operator_approval_required": approval_required,
        "operator_approval_ref": operator_approval_ref,
        "review_required": review_required,
        "review_reason": policy_decision.get("reason") if review_required else None,
        "audit_stream_ref": audit_stream_ref,
        "monitoring_stream_ref": monitoring_stream_ref,
        "retention": retention,
        "token_health": redact_sensitive_fields(token_health) if token_health else None,
        "snapshot_ref": sandbox.get("config_path") or sandbox.get("artifacts_dir"),
        "monitoring_channels": ["inventory-jsonl", "audit-jsonl", "monitoring-jsonl"],
    }
