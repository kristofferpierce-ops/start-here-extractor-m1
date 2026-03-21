from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .ingestion import utcnow_iso
from .security import redact_sensitive_fields

FAMILY_INTERFACE_TEMPLATES_SCHEMA_VERSION = "1.0"
FAMILY_INTERFACE_TEMPLATE_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
FAMILY_INTERFACE_TEMPLATE_ROLLUP_SCHEMA_VERSION = "1.0"
CANONICAL_RAW_PAYLOAD_CONTRACTS_SCHEMA_VERSION = "1.0"
CANONICAL_RAW_PAYLOAD_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
CANONICAL_RAW_PAYLOAD_ROLLUP_SCHEMA_VERSION = "1.0"

_DEFAULT_STATUS_MAP = {
    "success": "success",
    "failure": "failure",
    "defer": "defer",
    "skip": "skip",
}
_DEFAULT_REQUIRED_FIELDS = ["runner_job_id", "outcome_collection_key", "status", "raw_payload_ref"]
_DEFAULT_OPTIONAL_FIELDS = ["contract_id", "event_id", "external_id", "status_reason", "payload_digest"]


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


def _normalize_status_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return dict(_DEFAULT_STATUS_MAP)
    normalized: dict[str, str] = {}
    for raw_status, canonical_status in value.items():
        raw = _normalize_text(raw_status)
        canonical = _normalize_text(canonical_status)
        if raw and canonical:
            normalized[raw] = canonical
    return normalized or dict(_DEFAULT_STATUS_MAP)


def normalize_family_interface_template_catalog(value: object) -> list[dict]:
    if isinstance(value, dict):
        entries = value.get("family_interface_templates") if isinstance(value.get("family_interface_templates"), list) else []
    elif isinstance(value, list):
        entries = value
    else:
        entries = []

    normalized: list[dict] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        family_template_key = _normalize_text(item.get("family_template_key"))
        if not family_template_key:
            continue
        normalized.append(
            redact_sensitive_fields(
                {
                    "family_template_key": family_template_key,
                    "template_family": _normalize_text(item.get("template_family")) or family_template_key,
                    "template_version": _normalize_text(item.get("template_version")) or "1.0",
                    "raw_payload_kind": _normalize_text(item.get("raw_payload_kind")) or "runner-raw-payload-v1",
                    "canonical_payload_kind": _normalize_text(item.get("canonical_payload_kind")) or "normalized-runner-outcome-v1",
                    "supported_target_family_keys": _normalize_str_list(item.get("supported_target_family_keys")),
                    "supported_target_systems": _normalize_str_list(item.get("supported_target_systems")),
                    "supported_target_types": _normalize_str_list(item.get("supported_target_types")),
                    "supported_adapter_families": _normalize_str_list(item.get("supported_adapter_families")),
                    "supported_interface_keys": _normalize_str_list(item.get("supported_interface_keys")),
                    "supported_normalizer_keys": _normalize_str_list(item.get("supported_normalizer_keys")),
                    "supported_operations": _normalize_str_list(item.get("supported_operations")),
                    "required_fields": _normalize_str_list(item.get("required_fields")) or list(_DEFAULT_REQUIRED_FIELDS),
                    "optional_fields": _normalize_str_list(item.get("optional_fields")) or list(_DEFAULT_OPTIONAL_FIELDS),
                    "status_map": _normalize_status_map(item.get("status_map")),
                    "active": _normalize_bool(item.get("active"), default=True),
                }
            )
        )
    normalized.sort(key=lambda item: str(item.get("family_template_key") or ""))
    return normalized


def load_family_interface_template_catalog(path: str | Path) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    payload = json.loads(target.read_text(encoding="utf-8"))
    return normalize_family_interface_template_catalog(payload)


def load_family_interface_templates(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Family interface templates payload must be a JSON object")


def _compatible_target_stub(stub: dict, template: dict) -> bool:
    if not _normalize_bool(template.get("active"), default=True):
        return False
    target_family = stub.get("target_family") if isinstance(stub.get("target_family"), dict) else {}
    target = stub.get("target") if isinstance(stub.get("target"), dict) else {}
    adapter = stub.get("adapter") if isinstance(stub.get("adapter"), dict) else {}
    interface = stub.get("interface") if isinstance(stub.get("interface"), dict) else {}
    canonical_request = (
        stub.get("request_stub", {}).get("canonical_request")
        if isinstance(stub.get("request_stub"), dict) and isinstance(stub.get("request_stub", {}).get("canonical_request"), dict)
        else {}
    )

    target_family_key = _normalize_text(target_family.get("target_family_key"))
    target_system = _normalize_text(target.get("target_system"))
    target_type = _normalize_text(target.get("target_type"))
    adapter_family = _normalize_text(adapter.get("adapter_family"))
    interface_key = _normalize_text(interface.get("interface_key"))
    normalizer_key = _normalize_text(interface.get("normalizer_key"))
    operation = _normalize_text(canonical_request.get("operation"))

    if (supported := template.get("supported_target_family_keys")) and target_family_key not in supported:
        return False
    if (supported := template.get("supported_target_systems")) and target_system not in supported:
        return False
    if (supported := template.get("supported_target_types")) and target_type not in supported:
        return False
    if (supported := template.get("supported_adapter_families")) and adapter_family not in supported:
        return False
    if (supported := template.get("supported_interface_keys")) and interface_key not in supported:
        return False
    if (supported := template.get("supported_normalizer_keys")) and normalizer_key not in supported:
        return False
    if (supported := template.get("supported_operations")) and operation not in supported:
        return False
    return True


def _template_candidates(stub: dict, catalog: list[dict]) -> list[dict]:
    return [redact_sensitive_fields(dict(item)) for item in catalog if _compatible_target_stub(stub, item)]


def derive_family_interface_template_id(stub: dict, template: dict) -> str:
    payload = {
        "target_runner_stub_id": _normalize_text(stub.get("target_runner_stub_id")),
        "family_template_key": _normalize_text(template.get("family_template_key")),
        "template_family": _normalize_text(template.get("template_family")),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"family-iface-{digest[:24]}"


def derive_raw_payload_contract_id(template_doc: dict) -> str:
    payload = {
        "family_interface_template_id": _normalize_text(template_doc.get("family_interface_template_id")),
        "raw_payload_kind": _normalize_text(template_doc.get("template", {}).get("raw_payload_kind")),
        "canonical_payload_kind": _normalize_text(template_doc.get("template", {}).get("canonical_payload_kind")),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"raw-payload-{digest[:24]}"


def _template_review_item_id(stub: dict) -> str:
    stub_id = _normalize_text(stub.get("target_runner_stub_id")) or "unknown"
    digest = hashlib.sha256(f"family-template:{stub_id}".encode("utf-8")).hexdigest()
    return f"family-template-review-{digest[:24]}"


def _raw_payload_review_item_id(template_doc: dict) -> str:
    template_id = _normalize_text(template_doc.get("family_interface_template_id")) or "unknown"
    digest = hashlib.sha256(f"raw-payload:{template_id}".encode("utf-8")).hexdigest()
    return f"raw-payload-review-{digest[:24]}"


def _template_ref(template_id: str) -> str:
    return f"family-interface-template://{template_id}"


def _raw_payload_contract_ref(contract_id: str) -> str:
    return f"canonical-raw-payload://{contract_id}"


def _build_family_interface_template(stub: dict, template: dict) -> dict:
    template_id = derive_family_interface_template_id(stub, template)
    target_family = stub.get("target_family") if isinstance(stub.get("target_family"), dict) else {}
    target = stub.get("target") if isinstance(stub.get("target"), dict) else {}
    adapter = stub.get("adapter") if isinstance(stub.get("adapter"), dict) else {}
    interface = stub.get("interface") if isinstance(stub.get("interface"), dict) else {}
    request_stub = stub.get("request_stub") if isinstance(stub.get("request_stub"), dict) else {}
    canonical_request = request_stub.get("canonical_request") if isinstance(request_stub.get("canonical_request"), dict) else {}

    return redact_sensitive_fields(
        {
            "schema_version": FAMILY_INTERFACE_TEMPLATES_SCHEMA_VERSION,
            "family_interface_template_id": template_id,
            "family_interface_template_ref": _template_ref(template_id),
            "state": "templated",
            "target_runner_stub_id": stub.get("target_runner_stub_id"),
            "interface_contract_id": stub.get("interface_contract_id"),
            "runner_job_id": stub.get("runner_job_id"),
            "contract_id": stub.get("contract_id"),
            "event_id": stub.get("event_id"),
            "outcome_collection_key": stub.get("outcome_collection_key"),
            "target_family": target_family,
            "target": target,
            "adapter": adapter,
            "interface": interface,
            "template": {
                "family_template_key": template.get("family_template_key"),
                "template_family": template.get("template_family"),
                "template_version": template.get("template_version"),
                "raw_payload_kind": template.get("raw_payload_kind"),
                "canonical_payload_kind": template.get("canonical_payload_kind"),
                "required_fields": template.get("required_fields") or list(_DEFAULT_REQUIRED_FIELDS),
                "optional_fields": template.get("optional_fields") or list(_DEFAULT_OPTIONAL_FIELDS),
                "status_map": template.get("status_map") or dict(_DEFAULT_STATUS_MAP),
            },
            "canonical_request": {
                "runner_job_id": stub.get("runner_job_id"),
                "contract_id": stub.get("contract_id"),
                "event_id": stub.get("event_id"),
                "operation": canonical_request.get("operation"),
                "target_family_key": target_family.get("target_family_key"),
                "target_system": target.get("target_system"),
                "target_type": target.get("target_type"),
                "target_key": target.get("target_key"),
                "adapter_key": adapter.get("adapter_key"),
                "adapter_family": adapter.get("adapter_family"),
                "interface_key": interface.get("interface_key"),
                "normalizer_key": interface.get("normalizer_key"),
                "outcome_collection_key": stub.get("outcome_collection_key"),
            },
        }
    )


def build_family_interface_template_artifacts(target_runner_stubs_doc: dict, template_catalog: list[dict]) -> tuple[dict, dict, dict]:
    templates: list[dict] = []
    review_items: list[dict] = []

    for stub in target_runner_stubs_doc.get("stubs") or []:
        if not isinstance(stub, dict):
            continue
        candidates = _template_candidates(stub, template_catalog)
        reason_codes = ["target_runner_stub_ready_for_family_template"]
        if not candidates:
            reason_codes.append("no_family_interface_template_match")
        elif len(candidates) > 1:
            reason_codes.append("multiple_family_interface_template_matches")

        if len(candidates) == 1:
            templates.append(_build_family_interface_template(stub, candidates[0]))
            continue

        target_family = stub.get("target_family") if isinstance(stub.get("target_family"), dict) else {}
        target = stub.get("target") if isinstance(stub.get("target"), dict) else {}
        adapter = stub.get("adapter") if isinstance(stub.get("adapter"), dict) else {}
        interface = stub.get("interface") if isinstance(stub.get("interface"), dict) else {}
        review_items.append(
            redact_sensitive_fields(
                {
                    "schema_version": FAMILY_INTERFACE_TEMPLATE_REVIEW_QUEUE_SCHEMA_VERSION,
                    "queue_item_id": _template_review_item_id(stub),
                    "state": "open",
                    "priority": "high",
                    "review_type": "family-interface-template-routing",
                    "target_runner_stub_id": stub.get("target_runner_stub_id"),
                    "interface_contract_id": stub.get("interface_contract_id"),
                    "runner_job_id": stub.get("runner_job_id"),
                    "reason_codes": reason_codes,
                    "target_family": {
                        "target_family_key": target_family.get("target_family_key"),
                        "fixture_family_key": target_family.get("fixture_family_key"),
                    },
                    "target": {
                        "target_system": target.get("target_system"),
                        "target_type": target.get("target_type"),
                    },
                    "adapter": {
                        "adapter_family": adapter.get("adapter_family"),
                    },
                    "interface": {
                        "interface_key": interface.get("interface_key"),
                        "normalizer_key": interface.get("normalizer_key"),
                    },
                    "candidate_templates": [
                        {
                            "family_template_key": item.get("family_template_key"),
                            "template_family": item.get("template_family"),
                            "raw_payload_kind": item.get("raw_payload_kind"),
                        }
                        for item in candidates
                    ],
                }
            )
        )

    templates_doc = {
        "schema_version": FAMILY_INTERFACE_TEMPLATES_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "template_count": len(templates),
        "templates": sorted(templates, key=lambda item: str(item.get("family_interface_template_id") or "")),
    }
    review_queue = {
        "schema_version": FAMILY_INTERFACE_TEMPLATE_REVIEW_QUEUE_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "item_count": len(review_items),
        "items": sorted(review_items, key=lambda item: str(item.get("queue_item_id") or "")),
    }
    rollup = build_family_interface_template_rollup(templates_doc, review_queue)
    return redact_sensitive_fields(templates_doc), redact_sensitive_fields(review_queue), redact_sensitive_fields(rollup)


def build_family_interface_template_rollup(templates_doc: dict, review_queue: dict) -> dict:
    template_family_counts: dict[str, int] = {}
    target_family_counts: dict[str, int] = {}
    raw_payload_kind_counts: dict[str, int] = {}
    review_reason_counts: dict[str, int] = {}

    for item in templates_doc.get("templates") or []:
        if not isinstance(item, dict):
            continue
        template = item.get("template") if isinstance(item.get("template"), dict) else {}
        target_family = item.get("target_family") if isinstance(item.get("target_family"), dict) else {}
        template_family = _normalize_text(template.get("template_family")) or "unknown"
        target_family_key = _normalize_text(target_family.get("target_family_key")) or "unknown"
        raw_payload_kind = _normalize_text(template.get("raw_payload_kind")) or "unknown"
        template_family_counts[template_family] = template_family_counts.get(template_family, 0) + 1
        target_family_counts[target_family_key] = target_family_counts.get(target_family_key, 0) + 1
        raw_payload_kind_counts[raw_payload_kind] = raw_payload_kind_counts.get(raw_payload_kind, 0) + 1

    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        for reason in item.get("reason_codes") or []:
            normalized = _normalize_text(reason)
            if normalized:
                review_reason_counts[normalized] = review_reason_counts.get(normalized, 0) + 1

    return {
        "schema_version": FAMILY_INTERFACE_TEMPLATE_ROLLUP_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "template_count": int(templates_doc.get("template_count") or 0),
        "review_queue_count": int(review_queue.get("item_count") or 0),
        "template_family_counts": template_family_counts,
        "target_family_counts": target_family_counts,
        "raw_payload_kind_counts": raw_payload_kind_counts,
        "review_reason_counts": review_reason_counts,
    }


def _canonical_status_values(status_map: dict[str, str]) -> list[str]:
    values: list[str] = []
    for canonical in status_map.values():
        normalized = _normalize_text(canonical)
        if normalized and normalized not in values:
            values.append(normalized)
    return values or ["success", "failure", "defer", "skip"]


def _build_raw_payload_contract(template_doc: dict) -> dict:
    template = template_doc.get("template") if isinstance(template_doc.get("template"), dict) else {}
    target_family = template_doc.get("target_family") if isinstance(template_doc.get("target_family"), dict) else {}
    interface = template_doc.get("interface") if isinstance(template_doc.get("interface"), dict) else {}
    raw_payload_contract_id = derive_raw_payload_contract_id(template_doc)
    status_map = template.get("status_map") if isinstance(template.get("status_map"), dict) else dict(_DEFAULT_STATUS_MAP)
    required_fields = template.get("required_fields") if isinstance(template.get("required_fields"), list) else list(_DEFAULT_REQUIRED_FIELDS)
    optional_fields = template.get("optional_fields") if isinstance(template.get("optional_fields"), list) else list(_DEFAULT_OPTIONAL_FIELDS)

    return redact_sensitive_fields(
        {
            "schema_version": CANONICAL_RAW_PAYLOAD_CONTRACTS_SCHEMA_VERSION,
            "raw_payload_contract_id": raw_payload_contract_id,
            "raw_payload_contract_ref": _raw_payload_contract_ref(raw_payload_contract_id),
            "state": "defined",
            "family_interface_template_id": template_doc.get("family_interface_template_id"),
            "target_runner_stub_id": template_doc.get("target_runner_stub_id"),
            "runner_job_id": template_doc.get("runner_job_id"),
            "contract_id": template_doc.get("contract_id"),
            "event_id": template_doc.get("event_id"),
            "target_family": target_family,
            "interface": {
                "interface_key": interface.get("interface_key"),
                "normalizer_key": interface.get("normalizer_key"),
            },
            "raw_payload_contract": {
                "raw_payload_kind": template.get("raw_payload_kind"),
                "canonical_payload_kind": template.get("canonical_payload_kind"),
                "required_fields": required_fields,
                "optional_fields": optional_fields,
                "status_map": status_map,
                "accepted_canonical_statuses": _canonical_status_values(status_map),
                "correlation_keys": ["runner_job_id", "outcome_collection_key", "contract_id"],
                "canonical_output_ref": template_doc.get("family_interface_template_ref"),
            },
        }
    )


def build_canonical_raw_payload_contract_artifacts(templates_doc: dict) -> tuple[dict, dict, dict]:
    contracts: list[dict] = []
    review_items: list[dict] = []

    for template_doc in templates_doc.get("templates") or []:
        if not isinstance(template_doc, dict):
            continue
        template = template_doc.get("template") if isinstance(template_doc.get("template"), dict) else {}
        raw_payload_kind = _normalize_text(template.get("raw_payload_kind"))
        required_fields = template.get("required_fields") if isinstance(template.get("required_fields"), list) else []

        reason_codes = ["family_interface_template_ready_for_raw_payload_contract"]
        if not raw_payload_kind:
            reason_codes.append("missing_raw_payload_kind")
        if not required_fields:
            reason_codes.append("missing_required_fields")

        if reason_codes == ["family_interface_template_ready_for_raw_payload_contract"]:
            contracts.append(_build_raw_payload_contract(template_doc))
            continue

        review_items.append(
            redact_sensitive_fields(
                {
                    "schema_version": CANONICAL_RAW_PAYLOAD_REVIEW_QUEUE_SCHEMA_VERSION,
                    "queue_item_id": _raw_payload_review_item_id(template_doc),
                    "state": "open",
                    "priority": "high",
                    "review_type": "canonical-raw-payload-contract",
                    "family_interface_template_id": template_doc.get("family_interface_template_id"),
                    "target_runner_stub_id": template_doc.get("target_runner_stub_id"),
                    "reason_codes": reason_codes,
                    "template_summary": {
                        "family_template_key": template.get("family_template_key"),
                        "raw_payload_kind": template.get("raw_payload_kind"),
                        "canonical_payload_kind": template.get("canonical_payload_kind"),
                    },
                }
            )
        )

    contracts_doc = {
        "schema_version": CANONICAL_RAW_PAYLOAD_CONTRACTS_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "contract_count": len(contracts),
        "contracts": sorted(contracts, key=lambda item: str(item.get("raw_payload_contract_id") or "")),
    }
    review_queue = {
        "schema_version": CANONICAL_RAW_PAYLOAD_REVIEW_QUEUE_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "item_count": len(review_items),
        "items": sorted(review_items, key=lambda item: str(item.get("queue_item_id") or "")),
    }
    rollup = build_canonical_raw_payload_rollup(contracts_doc, review_queue)
    return redact_sensitive_fields(contracts_doc), redact_sensitive_fields(review_queue), redact_sensitive_fields(rollup)


def build_canonical_raw_payload_rollup(contracts_doc: dict, review_queue: dict) -> dict:
    raw_payload_kind_counts: dict[str, int] = {}
    target_family_counts: dict[str, int] = {}
    canonical_status_counts: dict[str, int] = {}
    review_reason_counts: dict[str, int] = {}

    for item in contracts_doc.get("contracts") or []:
        if not isinstance(item, dict):
            continue
        payload_contract = item.get("raw_payload_contract") if isinstance(item.get("raw_payload_contract"), dict) else {}
        target_family = item.get("target_family") if isinstance(item.get("target_family"), dict) else {}
        raw_payload_kind = _normalize_text(payload_contract.get("raw_payload_kind")) or "unknown"
        target_family_key = _normalize_text(target_family.get("target_family_key")) or "unknown"
        raw_payload_kind_counts[raw_payload_kind] = raw_payload_kind_counts.get(raw_payload_kind, 0) + 1
        target_family_counts[target_family_key] = target_family_counts.get(target_family_key, 0) + 1
        for status in payload_contract.get("accepted_canonical_statuses") or []:
            normalized = _normalize_text(status)
            if normalized:
                canonical_status_counts[normalized] = canonical_status_counts.get(normalized, 0) + 1

    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        for reason in item.get("reason_codes") or []:
            normalized = _normalize_text(reason)
            if normalized:
                review_reason_counts[normalized] = review_reason_counts.get(normalized, 0) + 1

    return {
        "schema_version": CANONICAL_RAW_PAYLOAD_ROLLUP_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "contract_count": int(contracts_doc.get("contract_count") or 0),
        "review_queue_count": int(review_queue.get("item_count") or 0),
        "raw_payload_kind_counts": raw_payload_kind_counts,
        "target_family_counts": target_family_counts,
        "canonical_status_counts": canonical_status_counts,
        "review_reason_counts": review_reason_counts,
    }


def render_family_interface_templates_markdown(templates_doc: dict) -> str:
    lines = ["# Family interface templates", "", f"Template count: {int(templates_doc.get('template_count') or 0)}"]
    for item in templates_doc.get("templates") or []:
        if not isinstance(item, dict):
            continue
        template = item.get("template") if isinstance(item.get("template"), dict) else {}
        lines.extend(
            [
                "",
                f"## {item.get('family_interface_template_id')}",
                f"- target_runner_stub_id: {item.get('target_runner_stub_id')}",
                f"- family_template_key: {template.get('family_template_key')}",
                f"- template_family: {template.get('template_family')}",
                f"- raw_payload_kind: {template.get('raw_payload_kind')}",
            ]
        )
    return "\n".join(lines) + "\n"


def render_family_interface_template_review_queue_markdown(review_queue: dict) -> str:
    lines = ["# Family interface template review queue", "", f"Item count: {int(review_queue.get('item_count') or 0)}"]
    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                "",
                f"## {item.get('queue_item_id')}",
                f"- target_runner_stub_id: {item.get('target_runner_stub_id')}",
                f"- reason_codes: {', '.join(item.get('reason_codes') or [])}",
            ]
        )
    return "\n".join(lines) + "\n"


def render_family_interface_template_rollup_markdown(rollup: dict) -> str:
    lines = ["# Family interface template rollup", ""]
    lines.append(f"Template count: {int(rollup.get('template_count') or 0)}")
    lines.append(f"Review queue count: {int(rollup.get('review_queue_count') or 0)}")
    return "\n".join(lines) + "\n"


def render_canonical_raw_payload_contracts_markdown(contracts_doc: dict) -> str:
    lines = ["# Canonical raw payload contracts", "", f"Contract count: {int(contracts_doc.get('contract_count') or 0)}"]
    for item in contracts_doc.get("contracts") or []:
        if not isinstance(item, dict):
            continue
        payload_contract = item.get("raw_payload_contract") if isinstance(item.get("raw_payload_contract"), dict) else {}
        lines.extend(
            [
                "",
                f"## {item.get('raw_payload_contract_id')}",
                f"- family_interface_template_id: {item.get('family_interface_template_id')}",
                f"- raw_payload_kind: {payload_contract.get('raw_payload_kind')}",
                f"- canonical_payload_kind: {payload_contract.get('canonical_payload_kind')}",
            ]
        )
    return "\n".join(lines) + "\n"


def render_canonical_raw_payload_review_queue_markdown(review_queue: dict) -> str:
    lines = ["# Canonical raw payload review queue", "", f"Item count: {int(review_queue.get('item_count') or 0)}"]
    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                "",
                f"## {item.get('queue_item_id')}",
                f"- family_interface_template_id: {item.get('family_interface_template_id')}",
                f"- reason_codes: {', '.join(item.get('reason_codes') or [])}",
            ]
        )
    return "\n".join(lines) + "\n"


def render_canonical_raw_payload_rollup_markdown(rollup: dict) -> str:
    lines = ["# Canonical raw payload rollup", ""]
    lines.append(f"Contract count: {int(rollup.get('contract_count') or 0)}")
    lines.append(f"Review queue count: {int(rollup.get('review_queue_count') or 0)}")
    return "\n".join(lines) + "\n"
