from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from .ingestion import iter_ingestion_records
from .security import redact_sensitive_fields


SOURCE_CONTROL_PIPELINE_SCHEMA_VERSION = "1.0"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _stable_digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def derive_control_source_key(ingestion_record: dict) -> str:
    source = ingestion_record.get("source") if isinstance(ingestion_record.get("source"), dict) else {}
    payload = {
        "source_type": _normalize_text(source.get("source_type")) or "unknown",
        "source_system": _normalize_text(source.get("source_system")) or "unknown",
        "source_record_id": _normalize_text(source.get("source_record_id")) or _normalize_text(ingestion_record.get("event_id")) or "unknown",
    }
    return f"src-{_stable_digest(payload)[:24]}"


def _record_fingerprint(ingestion_record: dict) -> dict:
    source = ingestion_record.get("source") if isinstance(ingestion_record.get("source"), dict) else {}
    evidence = ingestion_record.get("evidence") if isinstance(ingestion_record.get("evidence"), dict) else {}
    return {
        "source_key": derive_control_source_key(ingestion_record),
        "event_id": _normalize_text(ingestion_record.get("event_id")),
        "source_record_id": _normalize_text(source.get("source_record_id")),
        "zip_sha256": _normalize_text(evidence.get("zip_sha256")),
        "start_here": _normalize_text(evidence.get("start_here")),
    }


def build_raw_source_record(ingestion_record: dict) -> dict:
    source = ingestion_record.get("source") if isinstance(ingestion_record.get("source"), dict) else {}
    pipeline = ingestion_record.get("pipeline") if isinstance(ingestion_record.get("pipeline"), dict) else {}
    raw = pipeline.get("raw") if isinstance(pipeline.get("raw"), dict) else {}
    payload = {
        "schema_version": SOURCE_CONTROL_PIPELINE_SCHEMA_VERSION,
        "raw_record_id": f"raw-{_stable_digest(_record_fingerprint(ingestion_record))[:24]}",
        "source_key": derive_control_source_key(ingestion_record),
        "captured_at": _normalize_text(raw.get("captured_at")) or _normalize_text(ingestion_record.get("emitted_at")) or utcnow_iso(),
        "status": _normalize_text(raw.get("status")) or "captured",
        "source": redact_sensitive_fields(source),
        "raw_ref": _normalize_text(raw.get("ref")),
        "evidence_ref": redact_sensitive_fields(_record_fingerprint(ingestion_record)),
    }
    return redact_sensitive_fields(payload)


def build_normalized_source_record(ingestion_record: dict) -> dict:
    source = ingestion_record.get("source") if isinstance(ingestion_record.get("source"), dict) else {}
    pipeline = ingestion_record.get("pipeline") if isinstance(ingestion_record.get("pipeline"), dict) else {}
    normalized = pipeline.get("normalized") if isinstance(pipeline.get("normalized"), dict) else {}
    evidence = ingestion_record.get("evidence") if isinstance(ingestion_record.get("evidence"), dict) else {}
    raw = build_raw_source_record(ingestion_record)
    payload = {
        "schema_version": SOURCE_CONTROL_PIPELINE_SCHEMA_VERSION,
        "normalized_record_id": f"norm-{_stable_digest(_record_fingerprint(ingestion_record))[:24]}",
        "source_key": raw.get("source_key"),
        "raw_record_id": raw.get("raw_record_id"),
        "normalized_at": _normalize_text(normalized.get("normalized_at")) or _normalize_text(ingestion_record.get("emitted_at")) or utcnow_iso(),
        "status": _normalize_text(normalized.get("status")) or "normalized",
        "source_system": _normalize_text(source.get("source_system")) or _normalize_text(source.get("source_type")) or "unknown",
        "source_entity_type": _normalize_text(source.get("source_entity_type")) or "unknown",
        "content_family": _normalize_text(source.get("content_family")) or "unknown",
        "normalized_ref": _normalize_text(normalized.get("ref")),
        "lineage": redact_sensitive_fields(_record_fingerprint(ingestion_record)),
        "summary": redact_sensitive_fields({
            "outcome": evidence.get("outcome"),
            "start_here": evidence.get("start_here"),
            "warnings": list(ingestion_record.get("warnings") or []),
        }),
    }
    return redact_sensitive_fields(payload)


def build_candidate_matches(ingestion_record: dict) -> list[dict]:
    relationship_memory = ingestion_record.get("relationship_memory") if isinstance(ingestion_record.get("relationship_memory"), dict) else {}
    candidates = relationship_memory.get("candidates") if isinstance(relationship_memory.get("candidates"), list) else []
    payloads: list[dict] = []
    base = _record_fingerprint(ingestion_record)
    for idx, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            continue
        fingerprint = dict(base)
        fingerprint["candidate_index"] = idx
        fingerprint["candidate"] = candidate
        payloads.append(
            redact_sensitive_fields(
                {
                    "schema_version": SOURCE_CONTROL_PIPELINE_SCHEMA_VERSION,
                    "candidate_match_id": f"match-{_stable_digest(fingerprint)[:24]}",
                    "source_key": derive_control_source_key(ingestion_record),
                    "normalized_record_id": f"norm-{_stable_digest(base)[:24]}",
                    "entity_type": _normalize_text(candidate.get("entity_type")) or "unknown",
                    "entity_id": _normalize_text(candidate.get("entity_id")),
                    "confidence": candidate.get("confidence"),
                    "reason": _normalize_text(candidate.get("reason")),
                    "candidate": redact_sensitive_fields(candidate),
                }
            )
        )
    return payloads


def build_review_items(ingestion_record: dict) -> list[dict]:
    pipeline = ingestion_record.get("pipeline") if isinstance(ingestion_record.get("pipeline"), dict) else {}
    governance = ingestion_record.get("governance") if isinstance(ingestion_record.get("governance"), dict) else {}
    matched = pipeline.get("matched") if isinstance(pipeline.get("matched"), dict) else {}
    approved = pipeline.get("approved") if isinstance(pipeline.get("approved"), dict) else {}
    review_items: list[dict] = []
    reason_codes: list[str] = []
    if bool(governance.get("review_required")):
        reason_codes.append("governance_review_required")
    if _normalize_text(matched.get("status")) == "pending":
        reason_codes.append("match_pending")
    if _normalize_text(approved.get("status")) == "pending":
        reason_codes.append("approval_pending")
    if not reason_codes:
        return review_items
    payload = {
        "schema_version": SOURCE_CONTROL_PIPELINE_SCHEMA_VERSION,
        "review_item_id": f"review-{_stable_digest(_record_fingerprint(ingestion_record) | {'reasons': reason_codes})[:24]}",
        "source_key": derive_control_source_key(ingestion_record),
        "normalized_record_id": f"norm-{_stable_digest(_record_fingerprint(ingestion_record))[:24]}",
        "state": "open",
        "review_type": "source-control-pipeline",
        "priority": "high" if "governance_review_required" in reason_codes else "medium",
        "reason_codes": reason_codes,
        "matched_stage": redact_sensitive_fields(matched),
        "approved_stage": redact_sensitive_fields(approved),
    }
    review_items.append(redact_sensitive_fields(payload))
    return review_items


def build_approved_delta(ingestion_record: dict) -> dict | None:
    pipeline = ingestion_record.get("pipeline") if isinstance(ingestion_record.get("pipeline"), dict) else {}
    approved = pipeline.get("approved") if isinstance(pipeline.get("approved"), dict) else {}
    matched = pipeline.get("matched") if isinstance(pipeline.get("matched"), dict) else {}
    if _normalize_text(approved.get("status")) != "approved":
        return None
    payload = {
        "schema_version": SOURCE_CONTROL_PIPELINE_SCHEMA_VERSION,
        "approved_delta_id": f"approved-{_stable_digest(_record_fingerprint(ingestion_record))[:24]}",
        "source_key": derive_control_source_key(ingestion_record),
        "entity_type": _normalize_text(matched.get("entity_type")) or "unknown",
        "entity_id": _normalize_text(matched.get("entity_id")),
        "approved_at": _normalize_text(approved.get("approved_at")) or utcnow_iso(),
        "approved_by": _normalize_text(approved.get("approved_by")),
        "reason": _normalize_text(approved.get("reason")),
        "delta": redact_sensitive_fields({
            "source_ref": _record_fingerprint(ingestion_record),
            "matched": matched,
            "approved": approved,
        }),
    }
    return redact_sensitive_fields(payload)


def build_applied_state_transition(ingestion_record: dict) -> dict | None:
    pipeline = ingestion_record.get("pipeline") if isinstance(ingestion_record.get("pipeline"), dict) else {}
    applied = pipeline.get("applied") if isinstance(pipeline.get("applied"), dict) else {}
    if _normalize_text(applied.get("status")) != "applied":
        return None
    payload = {
        "schema_version": SOURCE_CONTROL_PIPELINE_SCHEMA_VERSION,
        "applied_state_transition_id": f"applied-{_stable_digest(_record_fingerprint(ingestion_record))[:24]}",
        "source_key": derive_control_source_key(ingestion_record),
        "target_type": _normalize_text(applied.get("target_type")) or "unknown",
        "target_id": _normalize_text(applied.get("target_id")),
        "applied_at": _normalize_text(applied.get("applied_at")) or utcnow_iso(),
        "applied_ref": _normalize_text(applied.get("applied_ref")),
        "lineage": redact_sensitive_fields(_record_fingerprint(ingestion_record)),
    }
    return redact_sensitive_fields(payload)


def build_source_control_pipeline_artifacts(ingestion_records: list[dict]) -> dict[str, dict]:
    raw_records = [build_raw_source_record(record) for record in ingestion_records]
    normalized_records = [build_normalized_source_record(record) for record in ingestion_records]
    candidate_matches = [item for record in ingestion_records for item in build_candidate_matches(record)]
    review_items = [item for record in ingestion_records for item in build_review_items(record)]
    approved_deltas = [item for record in ingestion_records if (item := build_approved_delta(record)) is not None]
    applied_state_transitions = [item for record in ingestion_records if (item := build_applied_state_transition(record)) is not None]

    return {
        "source_records_raw": {
            "schema_version": SOURCE_CONTROL_PIPELINE_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(raw_records),
            "records": raw_records,
        },
        "source_records_normalized": {
            "schema_version": SOURCE_CONTROL_PIPELINE_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(normalized_records),
            "records": normalized_records,
        },
        "candidate_matches": {
            "schema_version": SOURCE_CONTROL_PIPELINE_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(candidate_matches),
            "records": candidate_matches,
        },
        "review_items": {
            "schema_version": SOURCE_CONTROL_PIPELINE_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(review_items),
            "records": review_items,
        },
        "approved_deltas": {
            "schema_version": SOURCE_CONTROL_PIPELINE_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(approved_deltas),
            "records": approved_deltas,
        },
        "applied_state_transitions": {
            "schema_version": SOURCE_CONTROL_PIPELINE_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(applied_state_transitions),
            "records": applied_state_transitions,
        },
        "rollup": {
            "schema_version": SOURCE_CONTROL_PIPELINE_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "raw_record_count": len(raw_records),
            "normalized_record_count": len(normalized_records),
            "candidate_match_count": len(candidate_matches),
            "review_item_count": len(review_items),
            "approved_delta_count": len(approved_deltas),
            "applied_state_transition_count": len(applied_state_transitions),
        },
    }


def iter_source_control_ingestion_records(path: str | Path) -> list[dict]:
    return list(iter_ingestion_records(path))
