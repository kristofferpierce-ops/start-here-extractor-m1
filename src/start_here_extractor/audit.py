from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Iterable

from .io.jsonl_writer import JsonlWriter
from .security import redact_sensitive_fields


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_audit_event(
    event: dict,
    audit_dir: Path,
    *,
    durable: bool = False,
    stream_name: str = "audit-events",
) -> str:
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = audit_dir / f"{stream_name}.jsonl"
    event_id = event.get("event_id") or str(uuid4())
    payload = {**event, "event_id": event_id, "created_at": event.get("created_at") or utcnow_iso()}
    payload = redact_sensitive_fields(payload)
    with JsonlWriter(audit_path, durable=durable) as writer:
        writer.write_record(payload)
    return f"audit://{audit_path.as_posix()}#{event_id}"


def audit_append(record: dict, audit_dir: Path, *, durable: bool = False, stream_name: str = "audit-events") -> str:
    event = {
        "event_type": "inventory-record-finalized",
        "record_outcome": record.get("outcome"),
        "zip_path": record.get("zip_path"),
        "start_here": record.get("start_here"),
        "schema_version": record.get("schema_version"),
        "source_type": ((record.get("provenance") or {}).get("source_type") if isinstance(record.get("provenance"), dict) else None),
        "run_id": ((record.get("run") or {}).get("run_id") if isinstance(record.get("run"), dict) else None),
        "policy_decision": ((record.get("policy_decision") or {}).get("decision") if isinstance(record.get("policy_decision"), dict) else None),
        "operational_policy": ((record.get("policy") or {}).get("decision") if isinstance(record.get("policy"), dict) else None),
        "retention_status": record.get("retention_status"),
    }
    return append_audit_event(event, audit_dir, durable=durable, stream_name=stream_name)


def iter_audit_records(audit_path: str | Path) -> Iterable[dict]:
    path = Path(audit_path)
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


def count_audit_records(audit_path: str | Path) -> int:
    return sum(1 for _ in iter_audit_records(audit_path))


def find_audit_events_by_idempotency_key(audit_path: str | Path, idempotency_key: str) -> list[dict]:
    return [event for event in iter_audit_records(audit_path) if event.get("idempotency_key") == idempotency_key]


def has_successful_action(audit_path: str | Path, idempotency_key: str) -> bool:
    for event in iter_audit_records(audit_path):
        if event.get("idempotency_key") != idempotency_key:
            continue
        if event.get("event_type") == "playbook-action-finished" and event.get("result") in {"applied", "already-applied", "skipped"}:
            return True
    return False
