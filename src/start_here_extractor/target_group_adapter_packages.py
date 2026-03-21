from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .ingestion import utcnow_iso
from .security import redact_sensitive_fields

TARGET_GROUP_ADAPTER_PACKAGES_SCHEMA_VERSION = "1.0"
TARGET_GROUP_ADAPTER_PACKAGE_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
TARGET_GROUP_ADAPTER_PACKAGE_ROLLUP_SCHEMA_VERSION = "1.0"
CANONICAL_REQUEST_RESPONSE_FIXTURE_PACKS_SCHEMA_VERSION = "1.0"
CANONICAL_REQUEST_RESPONSE_FIXTURE_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
CANONICAL_REQUEST_RESPONSE_FIXTURE_ROLLUP_SCHEMA_VERSION = "1.0"

DEFAULT_FIXTURE_MODES = ["success", "failure", "defer", "skip"]
_ALLOWED_FIXTURE_MODES = set(DEFAULT_FIXTURE_MODES)


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


def normalize_target_group_catalog(value: object) -> list[dict]:
    if isinstance(value, dict):
        entries = value.get("target_groups") if isinstance(value.get("target_groups"), list) else []
    elif isinstance(value, list):
        entries = value
    else:
        entries = []

    normalized: list[dict] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        target_group_key = _normalize_text(item.get("target_group_key"))
        if not target_group_key:
            continue
        fixture_modes = [mode for mode in _normalize_str_list(item.get("fixture_modes")) if mode in _ALLOWED_FIXTURE_MODES]
        normalized.append(
            redact_sensitive_fields(
                {
                    "target_group_key": target_group_key,
                    "target_group_name": _normalize_text(item.get("target_group_name")) or target_group_key,
                    "supported_target_family_keys": _normalize_str_list(item.get("supported_target_family_keys")),
                    "supported_template_families": _normalize_str_list(item.get("supported_template_families")),
                    "supported_target_systems": _normalize_str_list(item.get("supported_target_systems")),
                    "supported_target_types": _normalize_str_list(item.get("supported_target_types")),
                    "supported_operations": _normalize_str_list(item.get("supported_operations")),
                    "adapter_package_key": _normalize_text(item.get("adapter_package_key")) or f"{target_group_key}-package",
                    "package_family": _normalize_text(item.get("package_family")) or target_group_key,
                    "request_template_kind": _normalize_text(item.get("request_template_kind")) or f"{target_group_key}-request-v1",
                    "response_template_kind": _normalize_text(item.get("response_template_kind")) or f"{target_group_key}-response-v1",
                    "fixture_modes": fixture_modes or list(DEFAULT_FIXTURE_MODES),
                    "active": _normalize_bool(item.get("active"), default=True),
                }
            )
        )
    normalized.sort(key=lambda item: str(item.get("target_group_key") or ""))
    return normalized


def load_target_group_catalog(path: str | Path) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    payload = json.loads(target.read_text(encoding="utf-8"))
    return normalize_target_group_catalog(payload)


def load_family_interface_templates(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Family interface templates payload must be a JSON object")


def load_canonical_raw_payload_contracts(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Canonical raw payload contracts payload must be a JSON object")


def derive_target_group_adapter_package_id(template_doc: dict, group: dict) -> str:
    payload = {
        "family_interface_template_id": _normalize_text(template_doc.get("family_interface_template_id")),
        "target_group_key": _normalize_text(group.get("target_group_key")),
        "adapter_package_key": _normalize_text(group.get("adapter_package_key")),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"target-group-pkg-{digest[:24]}"


def derive_request_response_fixture_pack_id(package_doc: dict) -> str:
    payload = {
        "target_group_adapter_package_id": _normalize_text(package_doc.get("target_group_adapter_package_id")),
        "adapter_package_key": _normalize_text(package_doc.get("target_group", {}).get("adapter_package_key")) if isinstance(package_doc.get("target_group"), dict) else None,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"rr-fixture-pack-{digest[:24]}"


def _target_group_review_item_id(template_doc: dict) -> str:
    template_id = _normalize_text(template_doc.get("family_interface_template_id")) or "unknown"
    digest = hashlib.sha256(f"target-group:{template_id}".encode("utf-8")).hexdigest()
    return f"target-group-review-{digest[:24]}"


def _fixture_pack_review_item_id(package_doc: dict) -> str:
    package_id = _normalize_text(package_doc.get("target_group_adapter_package_id")) or "unknown"
    digest = hashlib.sha256(f"fixture-pack:{package_id}".encode("utf-8")).hexdigest()
    return f"fixture-pack-review-{digest[:24]}"


def _package_ref(package_id: str) -> str:
    return f"target-group-package://{package_id}"


def _fixture_pack_ref(pack_id: str) -> str:
    return f"request-response-fixture-pack://{pack_id}"


def _raw_payload_contract_index(contracts_doc: dict) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for item in contracts_doc.get("contracts") or []:
        if not isinstance(item, dict):
            continue
        template_id = _normalize_text(item.get("family_interface_template_id"))
        if template_id:
            index[template_id] = redact_sensitive_fields(dict(item))
    return index


def _compatible_target_group(template_doc: dict, contract_doc: dict | None, group: dict) -> bool:
    if not _normalize_bool(group.get("active"), default=True):
        return False
    template = template_doc.get("template") if isinstance(template_doc.get("template"), dict) else {}
    target_family = template_doc.get("target_family") if isinstance(template_doc.get("target_family"), dict) else {}
    target = template_doc.get("target") if isinstance(template_doc.get("target"), dict) else {}
    canonical_request = template_doc.get("canonical_request") if isinstance(template_doc.get("canonical_request"), dict) else {}

    target_family_key = _normalize_text(target_family.get("target_family_key"))
    target_system = _normalize_text(target.get("target_system"))
    target_type = _normalize_text(target.get("target_type"))
    template_family = _normalize_text(template.get("template_family"))
    operation = _normalize_text(canonical_request.get("operation"))

    if (supported := group.get("supported_target_family_keys")) and target_family_key not in supported:
        return False
    if (supported := group.get("supported_template_families")) and template_family not in supported:
        return False
    if (supported := group.get("supported_target_systems")) and target_system not in supported:
        return False
    if (supported := group.get("supported_target_types")) and target_type not in supported:
        return False
    if (supported := group.get("supported_operations")) and operation not in supported:
        return False
    if contract_doc is None:
        return False
    return True


def _target_group_candidates(template_doc: dict, contract_doc: dict | None, catalog: list[dict]) -> list[dict]:
    return [redact_sensitive_fields(dict(item)) for item in catalog if _compatible_target_group(template_doc, contract_doc, item)]


def _build_target_group_adapter_package(template_doc: dict, contract_doc: dict, group: dict) -> dict:
    package_id = derive_target_group_adapter_package_id(template_doc, group)
    template = template_doc.get("template") if isinstance(template_doc.get("template"), dict) else {}
    target_family = template_doc.get("target_family") if isinstance(template_doc.get("target_family"), dict) else {}
    target = template_doc.get("target") if isinstance(template_doc.get("target"), dict) else {}
    canonical_request = template_doc.get("canonical_request") if isinstance(template_doc.get("canonical_request"), dict) else {}
    payload_contract = contract_doc.get("raw_payload_contract") if isinstance(contract_doc.get("raw_payload_contract"), dict) else {}

    return redact_sensitive_fields(
        {
            "schema_version": TARGET_GROUP_ADAPTER_PACKAGES_SCHEMA_VERSION,
            "target_group_adapter_package_id": package_id,
            "target_group_adapter_package_ref": _package_ref(package_id),
            "state": "packaged",
            "family_interface_template_id": template_doc.get("family_interface_template_id"),
            "raw_payload_contract_id": contract_doc.get("raw_payload_contract_id"),
            "target_runner_stub_id": template_doc.get("target_runner_stub_id"),
            "runner_job_id": template_doc.get("runner_job_id"),
            "contract_id": template_doc.get("contract_id"),
            "event_id": template_doc.get("event_id"),
            "target_family": target_family,
            "target": target,
            "target_group": {
                "target_group_key": group.get("target_group_key"),
                "target_group_name": group.get("target_group_name"),
                "adapter_package_key": group.get("adapter_package_key"),
                "package_family": group.get("package_family"),
                "request_template_kind": group.get("request_template_kind"),
                "response_template_kind": group.get("response_template_kind"),
                "fixture_modes": group.get("fixture_modes") or list(DEFAULT_FIXTURE_MODES),
            },
            "template_summary": {
                "family_template_key": template.get("family_template_key"),
                "template_family": template.get("template_family"),
                "raw_payload_kind": template.get("raw_payload_kind"),
                "canonical_payload_kind": template.get("canonical_payload_kind"),
            },
            "package_scaffold": {
                "package_family": group.get("package_family"),
                "request_template": {
                    "template_kind": group.get("request_template_kind"),
                    "required_fields": payload_contract.get("required_fields") or [],
                    "correlation_keys": payload_contract.get("correlation_keys") or [],
                    "operation": canonical_request.get("operation"),
                },
                "response_template": {
                    "template_kind": group.get("response_template_kind"),
                    "accepted_canonical_statuses": payload_contract.get("accepted_canonical_statuses") or [],
                    "status_map": payload_contract.get("status_map") or {},
                },
            },
        }
    )


def build_target_group_adapter_package_artifacts(templates_doc: dict, contracts_doc: dict, target_group_catalog: list[dict]) -> tuple[dict, dict, dict]:
    packages: list[dict] = []
    review_items: list[dict] = []
    contract_index = _raw_payload_contract_index(contracts_doc)

    for template_doc in templates_doc.get("templates") or []:
        if not isinstance(template_doc, dict):
            continue
        contract_doc = contract_index.get(_normalize_text(template_doc.get("family_interface_template_id")) or "")
        candidates = _target_group_candidates(template_doc, contract_doc, target_group_catalog)
        reason_codes = ["family_interface_template_ready_for_target_group_package"]
        if contract_doc is None:
            reason_codes.append("missing_raw_payload_contract")
        if not candidates:
            reason_codes.append("no_target_group_match")
        elif len(candidates) > 1:
            reason_codes.append("multiple_target_group_matches")

        if contract_doc is not None and len(candidates) == 1:
            packages.append(_build_target_group_adapter_package(template_doc, contract_doc, candidates[0]))
            continue

        target_family = template_doc.get("target_family") if isinstance(template_doc.get("target_family"), dict) else {}
        target = template_doc.get("target") if isinstance(template_doc.get("target"), dict) else {}
        template = template_doc.get("template") if isinstance(template_doc.get("template"), dict) else {}
        review_items.append(
            redact_sensitive_fields(
                {
                    "schema_version": TARGET_GROUP_ADAPTER_PACKAGE_REVIEW_QUEUE_SCHEMA_VERSION,
                    "queue_item_id": _target_group_review_item_id(template_doc),
                    "state": "open",
                    "priority": "high",
                    "review_type": "target-group-package-routing",
                    "family_interface_template_id": template_doc.get("family_interface_template_id"),
                    "target_runner_stub_id": template_doc.get("target_runner_stub_id"),
                    "reason_codes": reason_codes,
                    "target_family": {
                        "target_family_key": target_family.get("target_family_key"),
                        "fixture_family_key": target_family.get("fixture_family_key"),
                    },
                    "target": {
                        "target_system": target.get("target_system"),
                        "target_type": target.get("target_type"),
                    },
                    "template_summary": {
                        "family_template_key": template.get("family_template_key"),
                        "template_family": template.get("template_family"),
                    },
                    "candidate_target_groups": [
                        {
                            "target_group_key": item.get("target_group_key"),
                            "adapter_package_key": item.get("adapter_package_key"),
                            "package_family": item.get("package_family"),
                        }
                        for item in candidates
                    ],
                }
            )
        )

    packages_doc = {
        "schema_version": TARGET_GROUP_ADAPTER_PACKAGES_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "package_count": len(packages),
        "packages": sorted(packages, key=lambda item: str(item.get("target_group_adapter_package_id") or "")),
    }
    review_queue = {
        "schema_version": TARGET_GROUP_ADAPTER_PACKAGE_REVIEW_QUEUE_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "item_count": len(review_items),
        "items": sorted(review_items, key=lambda item: str(item.get("queue_item_id") or "")),
    }
    rollup = build_target_group_adapter_package_rollup(packages_doc, review_queue)
    return redact_sensitive_fields(packages_doc), redact_sensitive_fields(review_queue), redact_sensitive_fields(rollup)


def build_target_group_adapter_package_rollup(packages_doc: dict, review_queue: dict) -> dict:
    package_family_counts: dict[str, int] = {}
    target_group_counts: dict[str, int] = {}
    request_template_kind_counts: dict[str, int] = {}
    review_reason_counts: dict[str, int] = {}

    for item in packages_doc.get("packages") or []:
        if not isinstance(item, dict):
            continue
        target_group = item.get("target_group") if isinstance(item.get("target_group"), dict) else {}
        package_scaffold = item.get("package_scaffold") if isinstance(item.get("package_scaffold"), dict) else {}
        request_template = package_scaffold.get("request_template") if isinstance(package_scaffold.get("request_template"), dict) else {}
        package_family = _normalize_text(target_group.get("package_family")) or "unknown"
        target_group_key = _normalize_text(target_group.get("target_group_key")) or "unknown"
        request_template_kind = _normalize_text(request_template.get("template_kind")) or "unknown"
        package_family_counts[package_family] = package_family_counts.get(package_family, 0) + 1
        target_group_counts[target_group_key] = target_group_counts.get(target_group_key, 0) + 1
        request_template_kind_counts[request_template_kind] = request_template_kind_counts.get(request_template_kind, 0) + 1

    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        for reason in item.get("reason_codes") or []:
            normalized = _normalize_text(reason)
            if normalized:
                review_reason_counts[normalized] = review_reason_counts.get(normalized, 0) + 1

    return {
        "schema_version": TARGET_GROUP_ADAPTER_PACKAGE_ROLLUP_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "package_count": int(packages_doc.get("package_count") or 0),
        "review_queue_count": int(review_queue.get("item_count") or 0),
        "package_family_counts": package_family_counts,
        "target_group_counts": target_group_counts,
        "request_template_kind_counts": request_template_kind_counts,
        "review_reason_counts": review_reason_counts,
    }


def _build_fixture_pack(package_doc: dict) -> dict:
    pack_id = derive_request_response_fixture_pack_id(package_doc)
    target_group = package_doc.get("target_group") if isinstance(package_doc.get("target_group"), dict) else {}
    package_scaffold = package_doc.get("package_scaffold") if isinstance(package_doc.get("package_scaffold"), dict) else {}
    request_template = package_scaffold.get("request_template") if isinstance(package_scaffold.get("request_template"), dict) else {}
    response_template = package_scaffold.get("response_template") if isinstance(package_scaffold.get("response_template"), dict) else {}
    modes = [mode for mode in target_group.get("fixture_modes") or [] if _normalize_text(mode) in _ALLOWED_FIXTURE_MODES] or list(DEFAULT_FIXTURE_MODES)

    request_fixtures = []
    response_fixtures = []
    for mode in modes:
        request_fixtures.append(
            redact_sensitive_fields(
                {
                    "fixture_mode": mode,
                    "request_template_kind": request_template.get("template_kind"),
                    "canonical_request": {
                        "runner_job_id": package_doc.get("runner_job_id"),
                        "contract_id": package_doc.get("contract_id"),
                        "event_id": package_doc.get("event_id"),
                        "operation": request_template.get("operation"),
                        "target_group_key": target_group.get("target_group_key"),
                        "package_family": target_group.get("package_family"),
                    },
                }
            )
        )
        response_fixtures.append(
            redact_sensitive_fields(
                {
                    "fixture_mode": mode,
                    "response_template_kind": response_template.get("template_kind"),
                    "canonical_response": {
                        "runner_job_id": package_doc.get("runner_job_id"),
                        "outcome_status": "success" if mode == "success" else ("failure" if mode == "failure" else mode),
                        "status_reason": f"fixture-{mode}",
                        "target_group_key": target_group.get("target_group_key"),
                    },
                }
            )
        )

    return redact_sensitive_fields(
        {
            "schema_version": CANONICAL_REQUEST_RESPONSE_FIXTURE_PACKS_SCHEMA_VERSION,
            "request_response_fixture_pack_id": pack_id,
            "request_response_fixture_pack_ref": _fixture_pack_ref(pack_id),
            "state": "defined",
            "target_group_adapter_package_id": package_doc.get("target_group_adapter_package_id"),
            "family_interface_template_id": package_doc.get("family_interface_template_id"),
            "raw_payload_contract_id": package_doc.get("raw_payload_contract_id"),
            "target_group": target_group,
            "fixture_modes": modes,
            "request_fixtures": request_fixtures,
            "response_fixtures": response_fixtures,
        }
    )


def build_canonical_request_response_fixture_pack_artifacts(packages_doc: dict) -> tuple[dict, dict, dict]:
    packs: list[dict] = []
    review_items: list[dict] = []

    for package_doc in packages_doc.get("packages") or []:
        if not isinstance(package_doc, dict):
            continue
        target_group = package_doc.get("target_group") if isinstance(package_doc.get("target_group"), dict) else {}
        modes = [mode for mode in target_group.get("fixture_modes") or [] if _normalize_text(mode) in _ALLOWED_FIXTURE_MODES]
        reason_codes = ["target_group_package_ready_for_fixture_pack"]
        if not modes:
            reason_codes.append("missing_fixture_modes")

        if reason_codes == ["target_group_package_ready_for_fixture_pack"]:
            packs.append(_build_fixture_pack(package_doc))
            continue

        review_items.append(
            redact_sensitive_fields(
                {
                    "schema_version": CANONICAL_REQUEST_RESPONSE_FIXTURE_REVIEW_QUEUE_SCHEMA_VERSION,
                    "queue_item_id": _fixture_pack_review_item_id(package_doc),
                    "state": "open",
                    "priority": "medium",
                    "review_type": "request-response-fixture-pack",
                    "target_group_adapter_package_id": package_doc.get("target_group_adapter_package_id"),
                    "family_interface_template_id": package_doc.get("family_interface_template_id"),
                    "reason_codes": reason_codes,
                    "target_group": {
                        "target_group_key": target_group.get("target_group_key"),
                        "package_family": target_group.get("package_family"),
                    },
                }
            )
        )

    packs_doc = {
        "schema_version": CANONICAL_REQUEST_RESPONSE_FIXTURE_PACKS_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "pack_count": len(packs),
        "packs": sorted(packs, key=lambda item: str(item.get("request_response_fixture_pack_id") or "")),
    }
    review_queue = {
        "schema_version": CANONICAL_REQUEST_RESPONSE_FIXTURE_REVIEW_QUEUE_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "item_count": len(review_items),
        "items": sorted(review_items, key=lambda item: str(item.get("queue_item_id") or "")),
    }
    rollup = build_canonical_request_response_fixture_rollup(packs_doc, review_queue)
    return redact_sensitive_fields(packs_doc), redact_sensitive_fields(review_queue), redact_sensitive_fields(rollup)


def build_canonical_request_response_fixture_rollup(packs_doc: dict, review_queue: dict) -> dict:
    target_group_counts: dict[str, int] = {}
    fixture_mode_counts: dict[str, int] = {}
    request_template_kind_counts: dict[str, int] = {}
    review_reason_counts: dict[str, int] = {}

    for item in packs_doc.get("packs") or []:
        if not isinstance(item, dict):
            continue
        target_group = item.get("target_group") if isinstance(item.get("target_group"), dict) else {}
        request_fixtures = item.get("request_fixtures") if isinstance(item.get("request_fixtures"), list) else []
        target_group_key = _normalize_text(target_group.get("target_group_key")) or "unknown"
        target_group_counts[target_group_key] = target_group_counts.get(target_group_key, 0) + 1
        for fixture in request_fixtures:
            if not isinstance(fixture, dict):
                continue
            mode = _normalize_text(fixture.get("fixture_mode")) or "unknown"
            request_template_kind = _normalize_text(fixture.get("request_template_kind")) or "unknown"
            fixture_mode_counts[mode] = fixture_mode_counts.get(mode, 0) + 1
            request_template_kind_counts[request_template_kind] = request_template_kind_counts.get(request_template_kind, 0) + 1

    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        for reason in item.get("reason_codes") or []:
            normalized = _normalize_text(reason)
            if normalized:
                review_reason_counts[normalized] = review_reason_counts.get(normalized, 0) + 1

    return {
        "schema_version": CANONICAL_REQUEST_RESPONSE_FIXTURE_ROLLUP_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "pack_count": int(packs_doc.get("pack_count") or 0),
        "review_queue_count": int(review_queue.get("item_count") or 0),
        "target_group_counts": target_group_counts,
        "fixture_mode_counts": fixture_mode_counts,
        "request_template_kind_counts": request_template_kind_counts,
        "review_reason_counts": review_reason_counts,
    }


def render_target_group_adapter_packages_markdown(packages_doc: dict) -> str:
    lines = ["# Target-group adapter packages", "", f"Package count: {int(packages_doc.get('package_count') or 0)}"]
    for item in packages_doc.get("packages") or []:
        if not isinstance(item, dict):
            continue
        group = item.get("target_group") if isinstance(item.get("target_group"), dict) else {}
        lines.extend([
            "",
            f"## {item.get('target_group_adapter_package_id')}",
            f"- family_interface_template_id: {item.get('family_interface_template_id')}",
            f"- target_group_key: {group.get('target_group_key')}",
            f"- adapter_package_key: {group.get('adapter_package_key')}",
        ])
    return "\n".join(lines) + "\n"


def render_target_group_adapter_package_review_queue_markdown(review_queue: dict) -> str:
    lines = ["# Target-group adapter package review queue", "", f"Item count: {int(review_queue.get('item_count') or 0)}"]
    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.extend([
            "",
            f"## {item.get('queue_item_id')}",
            f"- family_interface_template_id: {item.get('family_interface_template_id')}",
            f"- reason_codes: {', '.join(item.get('reason_codes') or [])}",
        ])
    return "\n".join(lines) + "\n"


def render_target_group_adapter_package_rollup_markdown(rollup: dict) -> str:
    lines = ["# Target-group adapter package rollup", ""]
    lines.append(f"Package count: {int(rollup.get('package_count') or 0)}")
    lines.append(f"Review queue count: {int(rollup.get('review_queue_count') or 0)}")
    return "\n".join(lines) + "\n"


def render_canonical_request_response_fixture_packs_markdown(packs_doc: dict) -> str:
    lines = ["# Canonical request/response fixture packs", "", f"Pack count: {int(packs_doc.get('pack_count') or 0)}"]
    for item in packs_doc.get("packs") or []:
        if not isinstance(item, dict):
            continue
        group = item.get("target_group") if isinstance(item.get("target_group"), dict) else {}
        lines.extend([
            "",
            f"## {item.get('request_response_fixture_pack_id')}",
            f"- target_group_adapter_package_id: {item.get('target_group_adapter_package_id')}",
            f"- target_group_key: {group.get('target_group_key')}",
        ])
    return "\n".join(lines) + "\n"


def render_canonical_request_response_fixture_review_queue_markdown(review_queue: dict) -> str:
    lines = ["# Canonical request/response fixture review queue", "", f"Item count: {int(review_queue.get('item_count') or 0)}"]
    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.extend([
            "",
            f"## {item.get('queue_item_id')}",
            f"- target_group_adapter_package_id: {item.get('target_group_adapter_package_id')}",
            f"- reason_codes: {', '.join(item.get('reason_codes') or [])}",
        ])
    return "\n".join(lines) + "\n"


def render_canonical_request_response_fixture_rollup_markdown(rollup: dict) -> str:
    lines = ["# Canonical request/response fixture rollup", ""]
    lines.append(f"Pack count: {int(rollup.get('pack_count') or 0)}")
    lines.append(f"Review queue count: {int(rollup.get('review_queue_count') or 0)}")
    return "\n".join(lines) + "\n"
