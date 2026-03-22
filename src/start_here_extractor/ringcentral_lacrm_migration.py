from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .security import redact_sensitive_fields

RINGCENTRAL_LACRM_MIGRATION_SCHEMA_VERSION = "1.0"
SUPPORTED_SOURCE_SYSTEMS = {"ringcentral", "lacrm"}


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _stable_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _record_map(document: dict) -> dict[str, dict]:
    records = document.get("records") if isinstance(document.get("records"), list) else []
    mapping: dict[str, dict] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        source_key = _normalize_text(record.get("source_key"))
        if source_key:
            mapping[source_key] = record
    return mapping


def _records_by_source_key(document: dict) -> dict[str, list[dict]]:
    records = document.get("records") if isinstance(document.get("records"), list) else []
    mapping: dict[str, list[dict]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        source_key = _normalize_text(record.get("source_key"))
        if not source_key:
            continue
        mapping.setdefault(source_key, []).append(record)
    return mapping


def _migration_profile(source_system: str | None, source_entity_type: str | None, content_family: str | None) -> tuple[str | None, str | None]:
    system = _normalize_text(source_system)
    entity_type = _normalize_text(source_entity_type)
    family = _normalize_text(content_family)

    if system == "ringcentral":
        if entity_type in {"call-log", "voice-call", "sms-message", "communication-event"} or family in {"communication-event", "call-log", "message"}:
            return "communications", "ringcentral-communication"
        if entity_type in {"contact", "phone-contact"}:
            return "contacts", "ringcentral-contact"
        return None, None

    if system == "lacrm":
        if entity_type in {"crm-contact", "contact", "customer-contact"} or family in {"operating-core-event", "crm-contact", "contact"}:
            return "crm-contacts", "lacrm-contact"
        if entity_type in {"crm-activity", "note", "timeline-entry", "activity"} or family in {"crm-activity", "activity", "timeline"}:
            return "crm-activity", "lacrm-activity"
        return None, None

    return None, None


def load_source_control_pipeline_documents(pipeline_dir: str | Path) -> dict[str, dict]:
    path = Path(pipeline_dir)
    names = {
        "source_records_raw": "source_records_raw.json",
        "source_records_normalized": "source_records_normalized.json",
        "candidate_matches": "candidate_matches.json",
        "review_items": "review_items.json",
        "approved_deltas": "approved_deltas.json",
        "applied_state_transitions": "applied_state_transitions.json",
    }
    payloads: dict[str, dict] = {}
    for key, filename in names.items():
        file_path = path / filename
        if file_path.exists():
            payloads[key] = json.loads(file_path.read_text(encoding="utf-8"))
        else:
            payloads[key] = {"records": []}
    return payloads


def build_ringcentral_lacrm_migration_artifacts(pipeline_documents: dict[str, dict]) -> dict[str, dict]:
    raw_map = _record_map(pipeline_documents.get("source_records_raw", {}))
    normalized_records = pipeline_documents.get("source_records_normalized", {}).get("records")
    normalized_records = normalized_records if isinstance(normalized_records, list) else []
    candidate_matches = _records_by_source_key(pipeline_documents.get("candidate_matches", {}))
    review_items = _records_by_source_key(pipeline_documents.get("review_items", {}))
    approved_deltas = _record_map(pipeline_documents.get("approved_deltas", {}))
    applied_transitions = _record_map(pipeline_documents.get("applied_state_transitions", {}))

    migration_packs: list[dict] = []
    migration_review_queue: list[dict] = []
    system_counts: dict[str, int] = {"ringcentral": 0, "lacrm": 0}
    profile_counts: dict[str, int] = {}

    for normalized_record in normalized_records:
        if not isinstance(normalized_record, dict):
            continue
        source_system = _normalize_text(normalized_record.get("source_system"))
        if source_system not in SUPPORTED_SOURCE_SYSTEMS:
            continue
        system_counts[source_system] += 1

        source_key = _normalize_text(normalized_record.get("source_key"))
        raw_record = raw_map.get(source_key or "")
        entity_type = _normalize_text(normalized_record.get("source_entity_type"))
        content_family = _normalize_text(normalized_record.get("content_family"))
        if content_family is None:
            summary = normalized_record.get("summary") if isinstance(normalized_record.get("summary"), dict) else {}
            content_family = _normalize_text(summary.get("content_family"))
        migration_family, migration_profile = _migration_profile(source_system, entity_type, content_family)

        reasons: list[str] = []
        if raw_record is None:
            reasons.append("missing_raw_record")
        if migration_profile is None:
            reasons.append("unclassified_migration_profile")

        source_candidates = candidate_matches.get(source_key or "", [])
        source_reviews = review_items.get(source_key or "", [])
        approved_delta = approved_deltas.get(source_key or "")
        applied_transition = applied_transitions.get(source_key or "")

        if reasons:
            review_payload = {
                "schema_version": RINGCENTRAL_LACRM_MIGRATION_SCHEMA_VERSION,
                "review_item_id": f"m6b-review-{_stable_digest({'source_key': source_key, 'reasons': reasons})[:24]}",
                "source_key": source_key,
                "source_system": source_system,
                "state": "open",
                "priority": "high" if "missing_raw_record" in reasons else "medium",
                "review_type": "ringcentral-lacrm-migration",
                "reason_codes": reasons,
                "normalized_summary": redact_sensitive_fields(normalized_record),
            }
            migration_review_queue.append(redact_sensitive_fields(review_payload))
            continue

        if applied_transition is not None:
            readiness_state = "already-applied"
        elif approved_delta is not None:
            readiness_state = "ready-for-apply"
        elif source_reviews:
            readiness_state = "blocked-review"
        else:
            readiness_state = "ready-for-review"

        lineage = {
            "source_key": source_key,
            "raw_record_id": _normalize_text(raw_record.get("raw_record_id")) if isinstance(raw_record, dict) else None,
            "normalized_record_id": _normalize_text(normalized_record.get("normalized_record_id")),
            "approved_delta_id": _normalize_text(approved_delta.get("approved_delta_id")) if isinstance(approved_delta, dict) else None,
            "applied_state_transition_id": _normalize_text(applied_transition.get("applied_state_transition_id")) if isinstance(applied_transition, dict) else None,
        }
        pack_id = f"m6b-pack-{_stable_digest({'source_key': source_key, 'profile': migration_profile})[:24]}"
        profile_counts[migration_profile] = profile_counts.get(migration_profile, 0) + 1
        payload = {
            "schema_version": RINGCENTRAL_LACRM_MIGRATION_SCHEMA_VERSION,
            "migration_pack_id": pack_id,
            "source_key": source_key,
            "source_system": source_system,
            "source_entity_type": entity_type,
            "content_family": content_family,
            "migration_family": migration_family,
            "migration_profile": migration_profile,
            "readiness_state": readiness_state,
            "candidate_match_count": len(source_candidates),
            "review_item_count": len(source_reviews),
            "lineage": redact_sensitive_fields(lineage),
            "candidate_matches": redact_sensitive_fields(source_candidates),
            "review_items": redact_sensitive_fields(source_reviews),
            "approved_delta": redact_sensitive_fields(approved_delta),
            "applied_state_transition": redact_sensitive_fields(applied_transition),
            "source_summary": redact_sensitive_fields(
                {
                    "raw_status": _normalize_text(raw_record.get("status")) if isinstance(raw_record, dict) else None,
                    "normalized_status": _normalize_text(normalized_record.get("status")),
                    "source_system": source_system,
                    "source_entity_type": entity_type,
                }
            ),
        }
        migration_packs.append(redact_sensitive_fields(payload))

    return {
        "migration_packs": {
            "schema_version": RINGCENTRAL_LACRM_MIGRATION_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(migration_packs),
            "records": migration_packs,
        },
        "migration_review_queue": {
            "schema_version": RINGCENTRAL_LACRM_MIGRATION_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "record_count": len(migration_review_queue),
            "records": migration_review_queue,
        },
        "rollup": {
            "schema_version": RINGCENTRAL_LACRM_MIGRATION_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "migration_pack_count": len(migration_packs),
            "migration_review_item_count": len(migration_review_queue),
            "source_system_counts": system_counts,
            "migration_profile_counts": profile_counts,
        },
    }
