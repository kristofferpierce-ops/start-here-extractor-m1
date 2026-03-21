from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .io.jsonl_writer import JsonlWriter
from .security import redact_sensitive_fields


INGESTION_SCHEMA_VERSION = "1.0"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def derive_source_record_id(record: dict) -> str | None:
    provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
    zip_file = record.get("zip_file") if isinstance(record.get("zip_file"), dict) else {}
    for value in (
        provenance.get("remote_id"),
        zip_file.get("sha256"),
        zip_file.get("md5"),
        record.get("zip_path"),
    ):
        normalized = _normalize_text(value)
        if normalized:
            return normalized
    return None


def derive_relationship_keys(record: dict) -> list[dict[str, str]]:
    provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
    zip_file = record.get("zip_file") if isinstance(record.get("zip_file"), dict) else {}
    keys: list[dict[str, str]] = []

    def add(kind: str, value: object, source: str) -> None:
        normalized = _normalize_text(value)
        if not normalized:
            return
        entry = {"kind": kind, "value": normalized, "source": source}
        if entry not in keys:
            keys.append(entry)

    add("source_type", provenance.get("source_type"), "provenance")
    add("remote_id", provenance.get("remote_id"), "provenance")
    add("etag", provenance.get("etag"), "provenance")
    add("zip_sha256", zip_file.get("sha256"), "zip_file")
    add("zip_md5", zip_file.get("md5"), "zip_file")
    add("zip_path", record.get("zip_path"), "inventory")
    add("start_here", record.get("start_here"), "inventory")
    return keys


def derive_ingestion_event_id(record: dict) -> str:
    payload = {
        "source_type": ((record.get("provenance") or {}).get("source_type") if isinstance(record.get("provenance"), dict) else None),
        "source_record_id": derive_source_record_id(record),
        "zip_sha256": ((record.get("zip_file") or {}).get("sha256") if isinstance(record.get("zip_file"), dict) else None),
        "start_here": record.get("start_here"),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"ingest-{digest[:24]}"


def build_ingestion_record(
    inventory_record: dict,
    *,
    inventory_ref: str | None = None,
    source_system: str | None = None,
    matched_entity: dict | None = None,
    approval: dict | None = None,
    application: dict | None = None,
    relationship_candidates: list[dict] | None = None,
) -> dict:
    record = redact_sensitive_fields(dict(inventory_record))
    provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
    zip_file = record.get("zip_file") if isinstance(record.get("zip_file"), dict) else {}
    extracted = record.get("extracted_file") if isinstance(record.get("extracted_file"), dict) else {}
    monitoring = record.get("monitoring") if isinstance(record.get("monitoring"), dict) else {}
    governance = record.get("governance") if isinstance(record.get("governance"), dict) else {}
    policy_decision = record.get("policy_decision") if isinstance(record.get("policy_decision"), dict) else {}
    operational_policy = record.get("policy") if isinstance(record.get("policy"), dict) else {}
    event_id = derive_ingestion_event_id(record)
    emitted_at = _normalize_text(record.get("generated_at")) or utcnow_iso()
    source_type = _normalize_text(provenance.get("source_type")) or "unknown"
    source_record_id = derive_source_record_id(record)
    relationship_keys = derive_relationship_keys(record)
    matched_payload = redact_sensitive_fields(matched_entity or {})
    approval_payload = redact_sensitive_fields(approval or {})
    application_payload = redact_sensitive_fields(application or {})
    candidate_payload = redact_sensitive_fields(relationship_candidates or [])

    matched_status = "matched" if matched_payload.get("entity_id") else "pending"
    approved_status = "approved" if approval_payload.get("decision") == "approved" else "pending"
    applied_status = "applied" if application_payload.get("applied_ref") else "pending"

    ingestion_record = {
        "schema_version": INGESTION_SCHEMA_VERSION,
        "event_id": event_id,
        "emitted_at": emitted_at,
        "source": {
            "source_type": source_type,
            "source_system": _normalize_text(source_system) or source_type,
            "source_entity_type": "evidence-artifact",
            "source_record_id": source_record_id,
            "remote_id": _normalize_text(provenance.get("remote_id")),
            "etag": _normalize_text(provenance.get("etag")),
            "content_family": "start-here-evidence",
            "content_type": "application/zip",
        },
        "pipeline": {
            "raw": {
                "status": "captured",
                "captured_at": emitted_at,
                "ref": inventory_ref or record.get("audit_ref") or record.get("zip_path"),
            },
            "normalized": {
                "status": "normalized",
                "normalized_at": emitted_at,
                "ref": inventory_ref,
                "schema_version": record.get("schema_version"),
            },
            "matched": {
                "status": matched_status,
                "matched_at": matched_payload.get("matched_at"),
                "entity_type": matched_payload.get("entity_type"),
                "entity_id": matched_payload.get("entity_id"),
                "confidence": matched_payload.get("confidence"),
                "reason": matched_payload.get("reason"),
            },
            "approved": {
                "status": approved_status,
                "decision": approval_payload.get("decision"),
                "approved_at": approval_payload.get("approved_at"),
                "approved_by": approval_payload.get("approved_by"),
                "reason": approval_payload.get("reason"),
            },
            "applied": {
                "status": applied_status,
                "applied_at": application_payload.get("applied_at"),
                "applied_ref": application_payload.get("applied_ref"),
                "target_type": application_payload.get("target_type"),
                "target_id": application_payload.get("target_id"),
            },
        },
        "relationship_memory": {
            "keys": relationship_keys,
            "candidates": candidate_payload,
        },
        "evidence": {
            "inventory_ref": inventory_ref,
            "audit_ref": record.get("audit_ref"),
            "monitoring_ref": record.get("monitoring_ref"),
            "zip_path": record.get("zip_path"),
            "zip_sha256": zip_file.get("sha256"),
            "zip_md5": zip_file.get("md5"),
            "extracted_sha256": extracted.get("sha256"),
            "outcome": record.get("outcome"),
            "start_here": record.get("start_here"),
        },
        "governance": {
            "review_required": bool(monitoring.get("review_required")),
            "retention_status": record.get("retention_status"),
            "policy_decision": policy_decision.get("decision"),
            "policy_reason": policy_decision.get("reason") or operational_policy.get("reason"),
            "approval_gate": governance.get("approval_gate"),
            "operator_approval_required": governance.get("operator_approval_required"),
            "audit_stream_ref": governance.get("audit_stream_ref"),
            "monitoring_stream_ref": governance.get("monitoring_stream_ref"),
        },
        "provenance": provenance,
        "warnings": list(record.get("warnings") or []),
    }
    return redact_sensitive_fields(ingestion_record)


def append_ingestion_record(
    record: dict,
    ingestion_dir: Path,
    *,
    durable: bool = False,
    stream_name: str = "ingestion-events",
) -> str:
    ingestion_dir.mkdir(parents=True, exist_ok=True)
    path = ingestion_dir / f"{stream_name}.jsonl"
    payload = redact_sensitive_fields(dict(record))
    payload.setdefault("event_id", derive_ingestion_event_id(payload))
    payload.setdefault("emitted_at", utcnow_iso())
    with JsonlWriter(path, durable=durable) as writer:
        writer.write_record(payload)
    return f"ingestion://{path.as_posix()}#{payload['event_id']}"


def iter_ingestion_records(path: str | Path) -> Iterable[dict]:
    target = Path(path)
    if not target.exists():
        return
    with target.open("r", encoding="utf-8") as handle:
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


def build_ingestion_rollup(records: list[dict]) -> dict:
    source_types: dict[str, int] = {}
    outcomes: dict[str, int] = {}
    pipeline_status_counts = {
        "raw": {},
        "normalized": {},
        "matched": {},
        "approved": {},
        "applied": {},
    }
    review_required_count = 0
    for record in records:
        source_type = str(((record.get("source") or {}).get("source_type") if isinstance(record.get("source"), dict) else "unknown") or "unknown")
        source_types[source_type] = source_types.get(source_type, 0) + 1
        outcome = str(((record.get("evidence") or {}).get("outcome") if isinstance(record.get("evidence"), dict) else "unknown") or "unknown")
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        for stage in pipeline_status_counts:
            stage_block = record.get("pipeline", {}).get(stage, {}) if isinstance(record.get("pipeline"), dict) else {}
            status = str(stage_block.get("status") or "unknown")
            pipeline_status_counts[stage][status] = pipeline_status_counts[stage].get(status, 0) + 1
        if bool(((record.get("governance") or {}).get("review_required") if isinstance(record.get("governance"), dict) else False)):
            review_required_count += 1
    return {
        "schema_version": INGESTION_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "record_count": len(records),
        "source_types": source_types,
        "inventory_outcomes": outcomes,
        "pipeline_status_counts": pipeline_status_counts,
        "review_required_count": review_required_count,
    }
