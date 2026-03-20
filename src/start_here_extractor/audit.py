from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .io.jsonl_writer import JsonlWriter


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def audit_append(record: dict, audit_dir: Path, *, durable: bool = False, stream_name: str = "audit-events") -> str:
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = audit_dir / f"{stream_name}.jsonl"
    event_id = str(uuid4())
    event = {
        "event_id": event_id,
        "event_type": "inventory-record-finalized",
        "record_outcome": record.get("outcome"),
        "zip_path": record.get("zip_path"),
        "start_here": record.get("start_here"),
        "schema_version": record.get("schema_version"),
        "created_at": utcnow_iso(),
        "source_type": ((record.get("provenance") or {}).get("source_type") if isinstance(record.get("provenance"), dict) else None),
        "run_id": ((record.get("run") or {}).get("run_id") if isinstance(record.get("run"), dict) else None),
        "policy_decision": ((record.get("policy_decision") or {}).get("decision") if isinstance(record.get("policy_decision"), dict) else None),
        "operational_policy": ((record.get("policy") or {}).get("decision") if isinstance(record.get("policy"), dict) else None),
        "retention_status": record.get("retention_status"),
    }
    with JsonlWriter(audit_path, durable=durable) as writer:
        writer.write_record(event)
    return f"audit://{audit_path.as_posix()}#{event_id}"


def iter_audit_records(audit_path: str | Path):
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
