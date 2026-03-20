from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .io.jsonl_writer import JsonlWriter
from .security import redact_sensitive_fields


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_monitoring_block(record: dict, *, token_health: dict | None = None) -> dict:
    provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
    policy_decision = record.get("policy_decision") if isinstance(record.get("policy_decision"), dict) else {}
    operational_policy = record.get("policy") if isinstance(record.get("policy"), dict) else {}
    sandbox = record.get("sandbox") if isinstance(record.get("sandbox"), dict) else {}
    scan = record.get("scan") if isinstance(record.get("scan"), dict) else {}

    provider_state = {
        "source_type": provenance.get("source_type"),
        "auth_state": "unknown",
        "rate_limited": False,
        "operator_approval_required": bool(((record.get("governance") or {}) if isinstance(record.get("governance"), dict) else {}).get("operator_approval_required")),
    }
    if provenance.get("source_type") in {"gdrive", "dropbox", "graph"}:
        provider_state["auth_state"] = str((token_health or {}).get("status") or "provided")

    if scan.get("status") == "inconclusive":
        provider_state["auth_state"] = provider_state["auth_state"] if provider_state["auth_state"] != "unknown" else "indeterminate"

    review_required = bool(
        sandbox.get("enabled")
        or policy_decision.get("decision") in {"warn", "sandbox", "reject"}
        or operational_policy.get("decision") in {"warn", "sandbox", "reject"}
        or provider_state["operator_approval_required"]
    )

    block = {
        "status": "active",
        "severity": ("high" if policy_decision.get("decision") == "reject" else "medium" if review_required else "low"),
        "review_required": review_required,
        "review_reason": policy_decision.get("reason") or operational_policy.get("reason"),
        "provider_state": provider_state,
        "sandbox_state": {
            "enabled": bool(sandbox.get("enabled")),
            "platform": sandbox.get("platform"),
            "dry_run": sandbox.get("dry_run"),
            "snapshot_ref": sandbox.get("config_path") or sandbox.get("artifacts_dir"),
        },
        "scan_state": {
            "status": scan.get("status"),
            "engine": scan.get("engine"),
        },
        "token_health": redact_sensitive_fields(token_health) if token_health else None,
        "emitted_at": utcnow_iso(),
    }
    return block


def monitoring_append(record: dict, monitoring_dir: Path, *, durable: bool = False, stream_name: str = "monitoring-events") -> str:
    monitoring_dir.mkdir(parents=True, exist_ok=True)
    monitoring_path = monitoring_dir / f"{stream_name}.jsonl"
    event_id = str(uuid4())
    event = {
        "event_id": event_id,
        "event_type": "inventory-record-monitored",
        "created_at": utcnow_iso(),
        "zip_path": record.get("zip_path"),
        "source_type": ((record.get("provenance") or {}).get("source_type") if isinstance(record.get("provenance"), dict) else None),
        "review_required": ((record.get("monitoring") or {}).get("review_required") if isinstance(record.get("monitoring"), dict) else None),
        "policy_decision": ((record.get("policy_decision") or {}).get("decision") if isinstance(record.get("policy_decision"), dict) else None),
        "operational_policy": ((record.get("policy") or {}).get("decision") if isinstance(record.get("policy"), dict) else None),
        "retention_status": record.get("retention_status"),
        "sandbox_enabled": ((record.get("sandbox") or {}).get("enabled") if isinstance(record.get("sandbox"), dict) else None),
    }
    with JsonlWriter(monitoring_path, durable=durable) as writer:
        writer.write_record(event)
    return f"monitoring://{monitoring_path.as_posix()}#{event_id}"


def iter_monitoring_records(monitoring_path: str | Path):
    path = Path(monitoring_path)
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                break
            if isinstance(value, dict):
                yield value
