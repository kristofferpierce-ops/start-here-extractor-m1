from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .ingestion import utcnow_iso
from .security import redact_sensitive_fields

TARGET_GROUP_ADAPTER_SKELETONS_SCHEMA_VERSION = "1.0"
TARGET_GROUP_ADAPTER_SKELETON_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
TARGET_GROUP_ADAPTER_SKELETON_ROLLUP_SCHEMA_VERSION = "1.0"
ROUNDTRIP_NORMALIZATION_CASES_SCHEMA_VERSION = "1.0"
ROUNDTRIP_NORMALIZATION_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
ROUNDTRIP_NORMALIZATION_ROLLUP_SCHEMA_VERSION = "1.0"

_DEFAULT_SUCCESS_STATUS_CODES = [200, 201]
_DEFAULT_FAILURE_STATUS_CODES = [400, 409, 500]
_DEFAULT_DEFER_STATUS_CODES = [202]
_DEFAULT_SKIP_STATUS_CODES = [204]
_ALLOWED_FIXTURE_MODES = {"success", "failure", "defer", "skip"}


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


def _normalize_int_list(value: object, default: list[int]) -> list[int]:
    if not isinstance(value, list):
        return list(default)
    items: list[int] = []
    for item in value:
        try:
            number = int(item)
        except (TypeError, ValueError):
            continue
        if number not in items:
            items.append(number)
    return items or list(default)


def normalize_target_group_adapter_skeleton_catalog(value: object) -> list[dict]:
    if isinstance(value, dict):
        entries = value.get("target_group_adapter_skeletons") if isinstance(value.get("target_group_adapter_skeletons"), list) else []
    elif isinstance(value, list):
        entries = value
    else:
        entries = []

    normalized: list[dict] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        target_group_key = _normalize_text(item.get("target_group_key"))
        adapter_group_key = _normalize_text(item.get("adapter_group_key"))
        if not target_group_key or not adapter_group_key:
            continue
        normalized.append(
            redact_sensitive_fields(
                {
                    "target_group_key": target_group_key,
                    "target_group_name": _normalize_text(item.get("target_group_name")) or target_group_key,
                    "adapter_group_key": adapter_group_key,
                    "adapter_group_name": _normalize_text(item.get("adapter_group_name")) or adapter_group_key,
                    "adapter_kind": _normalize_text(item.get("adapter_kind")) or f"{target_group_key}-adapter-stub",
                    "supported_target_group_keys": _normalize_str_list(item.get("supported_target_group_keys")) or [target_group_key],
                    "supported_package_families": _normalize_str_list(item.get("supported_package_families")),
                    "supported_request_template_kinds": _normalize_str_list(item.get("supported_request_template_kinds")),
                    "supported_response_template_kinds": _normalize_str_list(item.get("supported_response_template_kinds")),
                    "supported_raw_payload_kinds": _normalize_str_list(item.get("supported_raw_payload_kinds")),
                    "supported_target_systems": _normalize_str_list(item.get("supported_target_systems")),
                    "supported_target_types": _normalize_str_list(item.get("supported_target_types")),
                    "supported_operations": _normalize_str_list(item.get("supported_operations")),
                    "request_method": (_normalize_text(item.get("request_method")) or "POST").upper(),
                    "request_path_template": _normalize_text(item.get("request_path_template")) or f"/{target_group_key}/dispatch",
                    "success_status_codes": _normalize_int_list(item.get("success_status_codes"), _DEFAULT_SUCCESS_STATUS_CODES),
                    "failure_status_codes": _normalize_int_list(item.get("failure_status_codes"), _DEFAULT_FAILURE_STATUS_CODES),
                    "defer_status_codes": _normalize_int_list(item.get("defer_status_codes"), _DEFAULT_DEFER_STATUS_CODES),
                    "skip_status_codes": _normalize_int_list(item.get("skip_status_codes"), _DEFAULT_SKIP_STATUS_CODES),
                    "active": _normalize_bool(item.get("active"), default=True),
                }
            )
        )
    normalized.sort(key=lambda item: str(item.get("adapter_group_key") or ""))
    return normalized


def load_target_group_adapter_skeleton_catalog(path: str | Path) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    payload = json.loads(target.read_text(encoding="utf-8"))
    return normalize_target_group_adapter_skeleton_catalog(payload)


def load_target_group_adapter_packages(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Target-group adapter packages payload must be a JSON object")


def load_canonical_request_response_fixture_packs(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Canonical request/response fixture packs payload must be a JSON object")


def derive_target_group_adapter_skeleton_id(package_doc: dict, catalog_item: dict) -> str:
    payload = {
        "target_group_adapter_package_id": _normalize_text(package_doc.get("target_group_adapter_package_id")),
        "adapter_group_key": _normalize_text(catalog_item.get("adapter_group_key")),
        "adapter_kind": _normalize_text(catalog_item.get("adapter_kind")),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"target-group-skel-{digest[:24]}"


def derive_roundtrip_normalization_case_id(skeleton_doc: dict, fixture_mode: str) -> str:
    payload = {
        "target_group_adapter_skeleton_id": _normalize_text(skeleton_doc.get("target_group_adapter_skeleton_id")),
        "fixture_mode": fixture_mode,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"roundtrip-case-{digest[:24]}"


def _skeleton_review_item_id(package_doc: dict) -> str:
    package_id = _normalize_text(package_doc.get("target_group_adapter_package_id")) or "unknown"
    digest = hashlib.sha256(f"target-group-skeleton:{package_id}".encode("utf-8")).hexdigest()
    return f"target-group-skeleton-review-{digest[:24]}"


def _roundtrip_review_item_id(skeleton_doc: dict) -> str:
    skeleton_id = _normalize_text(skeleton_doc.get("target_group_adapter_skeleton_id")) or "unknown"
    digest = hashlib.sha256(f"roundtrip-normalization:{skeleton_id}".encode("utf-8")).hexdigest()
    return f"roundtrip-normalization-review-{digest[:24]}"


def _skeleton_ref(skeleton_id: str) -> str:
    return f"target-group-adapter-skeleton://{skeleton_id}"


def _roundtrip_ref(case_id: str) -> str:
    return f"roundtrip-normalization://{case_id}"


def _fixture_pack_index(packs_doc: dict) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for item in packs_doc.get("packs") or []:
        if not isinstance(item, dict):
            continue
        package_id = _normalize_text(item.get("target_group_adapter_package_id"))
        if package_id:
            index[package_id] = redact_sensitive_fields(dict(item))
    return index


def _compatible_catalog_item(package_doc: dict, catalog_item: dict) -> bool:
    if not _normalize_bool(catalog_item.get("active"), default=True):
        return False
    target_group = package_doc.get("target_group") if isinstance(package_doc.get("target_group"), dict) else {}
    target = package_doc.get("target") if isinstance(package_doc.get("target"), dict) else {}
    template_summary = package_doc.get("template_summary") if isinstance(package_doc.get("template_summary"), dict) else {}
    package_scaffold = package_doc.get("package_scaffold") if isinstance(package_doc.get("package_scaffold"), dict) else {}
    request_template = package_scaffold.get("request_template") if isinstance(package_scaffold.get("request_template"), dict) else {}
    response_template = package_scaffold.get("response_template") if isinstance(package_scaffold.get("response_template"), dict) else {}

    target_group_key = _normalize_text(target_group.get("target_group_key"))
    package_family = _normalize_text(target_group.get("package_family"))
    request_template_kind = _normalize_text(request_template.get("template_kind"))
    response_template_kind = _normalize_text(response_template.get("template_kind"))
    raw_payload_kind = _normalize_text(template_summary.get("raw_payload_kind"))
    target_system = _normalize_text(target.get("target_system"))
    target_type = _normalize_text(target.get("target_type"))
    operation = _normalize_text(request_template.get("operation"))

    if (supported := catalog_item.get("supported_target_group_keys")) and target_group_key not in supported:
        return False
    if (supported := catalog_item.get("supported_package_families")) and package_family not in supported:
        return False
    if (supported := catalog_item.get("supported_request_template_kinds")) and request_template_kind not in supported:
        return False
    if (supported := catalog_item.get("supported_response_template_kinds")) and response_template_kind not in supported:
        return False
    if (supported := catalog_item.get("supported_raw_payload_kinds")) and raw_payload_kind not in supported:
        return False
    if (supported := catalog_item.get("supported_target_systems")) and target_system not in supported:
        return False
    if (supported := catalog_item.get("supported_target_types")) and target_type not in supported:
        return False
    if (supported := catalog_item.get("supported_operations")) and operation not in supported:
        return False
    return True


def _catalog_candidates(package_doc: dict, catalog: list[dict]) -> list[dict]:
    return [redact_sensitive_fields(dict(item)) for item in catalog if _compatible_catalog_item(package_doc, item)]


def _build_target_group_adapter_skeleton(package_doc: dict, fixture_pack: dict, catalog_item: dict) -> dict:
    skeleton_id = derive_target_group_adapter_skeleton_id(package_doc, catalog_item)
    target_group = package_doc.get("target_group") if isinstance(package_doc.get("target_group"), dict) else {}
    target = package_doc.get("target") if isinstance(package_doc.get("target"), dict) else {}
    package_scaffold = package_doc.get("package_scaffold") if isinstance(package_doc.get("package_scaffold"), dict) else {}
    request_template = package_scaffold.get("request_template") if isinstance(package_scaffold.get("request_template"), dict) else {}
    response_template = package_scaffold.get("response_template") if isinstance(package_scaffold.get("response_template"), dict) else {}
    request_fixtures = fixture_pack.get("request_fixtures") if isinstance(fixture_pack.get("request_fixtures"), list) else []
    response_fixtures = fixture_pack.get("response_fixtures") if isinstance(fixture_pack.get("response_fixtures"), list) else []

    response_status_codes = {
        "success": catalog_item.get("success_status_codes") or list(_DEFAULT_SUCCESS_STATUS_CODES),
        "failure": catalog_item.get("failure_status_codes") or list(_DEFAULT_FAILURE_STATUS_CODES),
        "defer": catalog_item.get("defer_status_codes") or list(_DEFAULT_DEFER_STATUS_CODES),
        "skip": catalog_item.get("skip_status_codes") or list(_DEFAULT_SKIP_STATUS_CODES),
    }

    return redact_sensitive_fields(
        {
            "schema_version": TARGET_GROUP_ADAPTER_SKELETONS_SCHEMA_VERSION,
            "target_group_adapter_skeleton_id": skeleton_id,
            "target_group_adapter_skeleton_ref": _skeleton_ref(skeleton_id),
            "state": "skeletonized",
            "target_group_adapter_package_id": package_doc.get("target_group_adapter_package_id"),
            "request_response_fixture_pack_id": fixture_pack.get("request_response_fixture_pack_id"),
            "family_interface_template_id": package_doc.get("family_interface_template_id"),
            "raw_payload_contract_id": package_doc.get("raw_payload_contract_id"),
            "runner_job_id": package_doc.get("runner_job_id"),
            "contract_id": package_doc.get("contract_id"),
            "event_id": package_doc.get("event_id"),
            "target_group": target_group,
            "target": target,
            "adapter_group": {
                "adapter_group_key": catalog_item.get("adapter_group_key"),
                "adapter_group_name": catalog_item.get("adapter_group_name"),
                "adapter_kind": catalog_item.get("adapter_kind"),
            },
            "request_skeleton": {
                "request_method": catalog_item.get("request_method"),
                "request_path_template": catalog_item.get("request_path_template"),
                "template_kind": request_template.get("template_kind"),
                "operation": request_template.get("operation"),
                "required_fields": request_template.get("required_fields") or [],
                "correlation_keys": request_template.get("correlation_keys") or [],
                "sample_fixture_modes": [item.get("fixture_mode") for item in request_fixtures if isinstance(item, dict)],
            },
            "response_skeleton": {
                "template_kind": response_template.get("template_kind"),
                "accepted_canonical_statuses": response_template.get("accepted_canonical_statuses") or [],
                "status_map": response_template.get("status_map") or {},
                "status_code_map": response_status_codes,
                "sample_fixture_modes": [item.get("fixture_mode") for item in response_fixtures if isinstance(item, dict)],
            },
        }
    )


def build_target_group_adapter_skeleton_artifacts(packages_doc: dict, fixture_packs_doc: dict, catalog: list[dict]) -> tuple[dict, dict, dict]:
    skeletons: list[dict] = []
    review_items: list[dict] = []
    fixture_index = _fixture_pack_index(fixture_packs_doc)

    for package_doc in packages_doc.get("packages") or []:
        if not isinstance(package_doc, dict):
            continue
        fixture_pack = fixture_index.get(_normalize_text(package_doc.get("target_group_adapter_package_id")) or "")
        candidates = _catalog_candidates(package_doc, catalog)
        reason_codes = ["target_group_package_ready_for_skeleton"]
        if fixture_pack is None:
            reason_codes.append("missing_request_response_fixture_pack")
        if not candidates:
            reason_codes.append("no_target_group_skeleton_match")
        elif len(candidates) > 1:
            reason_codes.append("multiple_target_group_skeleton_matches")

        if fixture_pack is not None and len(candidates) == 1:
            skeletons.append(_build_target_group_adapter_skeleton(package_doc, fixture_pack, candidates[0]))
            continue

        target_group = package_doc.get("target_group") if isinstance(package_doc.get("target_group"), dict) else {}
        review_items.append(
            redact_sensitive_fields(
                {
                    "schema_version": TARGET_GROUP_ADAPTER_SKELETON_REVIEW_QUEUE_SCHEMA_VERSION,
                    "queue_item_id": _skeleton_review_item_id(package_doc),
                    "state": "open",
                    "priority": "high",
                    "review_type": "target-group-adapter-skeleton",
                    "target_group_adapter_package_id": package_doc.get("target_group_adapter_package_id"),
                    "family_interface_template_id": package_doc.get("family_interface_template_id"),
                    "raw_payload_contract_id": package_doc.get("raw_payload_contract_id"),
                    "reason_codes": reason_codes,
                    "target_group": {
                        "target_group_key": target_group.get("target_group_key"),
                        "package_family": target_group.get("package_family"),
                    },
                    "candidate_adapter_groups": [
                        {
                            "adapter_group_key": item.get("adapter_group_key"),
                            "adapter_kind": item.get("adapter_kind"),
                        }
                        for item in candidates
                    ],
                }
            )
        )

    skeletons_doc = {
        "schema_version": TARGET_GROUP_ADAPTER_SKELETONS_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "skeleton_count": len(skeletons),
        "skeletons": sorted(skeletons, key=lambda item: str(item.get("target_group_adapter_skeleton_id") or "")),
    }
    review_queue = {
        "schema_version": TARGET_GROUP_ADAPTER_SKELETON_REVIEW_QUEUE_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "item_count": len(review_items),
        "items": sorted(review_items, key=lambda item: str(item.get("queue_item_id") or "")),
    }
    rollup = build_target_group_adapter_skeleton_rollup(skeletons_doc, review_queue)
    return redact_sensitive_fields(skeletons_doc), redact_sensitive_fields(review_queue), redact_sensitive_fields(rollup)


def build_target_group_adapter_skeleton_rollup(skeletons_doc: dict, review_queue: dict) -> dict:
    adapter_group_counts: dict[str, int] = {}
    request_method_counts: dict[str, int] = {}
    target_group_counts: dict[str, int] = {}
    review_reason_counts: dict[str, int] = {}

    for item in skeletons_doc.get("skeletons") or []:
        if not isinstance(item, dict):
            continue
        adapter_group = item.get("adapter_group") if isinstance(item.get("adapter_group"), dict) else {}
        request_skeleton = item.get("request_skeleton") if isinstance(item.get("request_skeleton"), dict) else {}
        target_group = item.get("target_group") if isinstance(item.get("target_group"), dict) else {}
        adapter_group_key = _normalize_text(adapter_group.get("adapter_group_key")) or "unknown"
        request_method = _normalize_text(request_skeleton.get("request_method")) or "unknown"
        target_group_key = _normalize_text(target_group.get("target_group_key")) or "unknown"
        adapter_group_counts[adapter_group_key] = adapter_group_counts.get(adapter_group_key, 0) + 1
        request_method_counts[request_method] = request_method_counts.get(request_method, 0) + 1
        target_group_counts[target_group_key] = target_group_counts.get(target_group_key, 0) + 1

    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        for reason in item.get("reason_codes") or []:
            normalized = _normalize_text(reason)
            if normalized:
                review_reason_counts[normalized] = review_reason_counts.get(normalized, 0) + 1

    return {
        "schema_version": TARGET_GROUP_ADAPTER_SKELETON_ROLLUP_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "skeleton_count": int(skeletons_doc.get("skeleton_count") or 0),
        "review_queue_count": int(review_queue.get("item_count") or 0),
        "adapter_group_counts": adapter_group_counts,
        "request_method_counts": request_method_counts,
        "target_group_counts": target_group_counts,
        "review_reason_counts": review_reason_counts,
    }


def _status_code_for_mode(status_code_map: dict, fixture_mode: str) -> int:
    codes = status_code_map.get(fixture_mode) if isinstance(status_code_map, dict) else None
    if isinstance(codes, list) and codes:
        try:
            return int(codes[0])
        except (TypeError, ValueError):
            pass
    return {
        "success": 200,
        "failure": 500,
        "defer": 202,
        "skip": 204,
    }.get(fixture_mode, 500)


def _fixture_pairs(pack: dict) -> dict[str, tuple[dict, dict]]:
    request_index: dict[str, dict] = {}
    response_index: dict[str, dict] = {}
    for item in pack.get("request_fixtures") or []:
        if isinstance(item, dict):
            mode = _normalize_text(item.get("fixture_mode"))
            if mode:
                request_index[mode] = item
    for item in pack.get("response_fixtures") or []:
        if isinstance(item, dict):
            mode = _normalize_text(item.get("fixture_mode"))
            if mode:
                response_index[mode] = item
    modes = sorted(set(request_index) & set(response_index))
    return {mode: (request_index[mode], response_index[mode]) for mode in modes}


def _build_roundtrip_case(skeleton_doc: dict, fixture_pack: dict, request_fixture: dict, response_fixture: dict) -> dict:
    fixture_mode = _normalize_text(request_fixture.get("fixture_mode")) or "unknown"
    case_id = derive_roundtrip_normalization_case_id(skeleton_doc, fixture_mode)
    request_skeleton = skeleton_doc.get("request_skeleton") if isinstance(skeleton_doc.get("request_skeleton"), dict) else {}
    response_skeleton = skeleton_doc.get("response_skeleton") if isinstance(skeleton_doc.get("response_skeleton"), dict) else {}
    adapter_group = skeleton_doc.get("adapter_group") if isinstance(skeleton_doc.get("adapter_group"), dict) else {}
    canonical_request = request_fixture.get("canonical_request") if isinstance(request_fixture.get("canonical_request"), dict) else {}
    canonical_response = response_fixture.get("canonical_response") if isinstance(response_fixture.get("canonical_response"), dict) else {}

    raw_request_payload = {
        "request_method": request_skeleton.get("request_method"),
        "request_path": request_skeleton.get("request_path_template"),
        "request_template_kind": request_skeleton.get("template_kind"),
        "adapter_group_key": adapter_group.get("adapter_group_key"),
        "body": {
            "runner_job_id": canonical_request.get("runner_job_id"),
            "contract_id": canonical_request.get("contract_id"),
            "event_id": canonical_request.get("event_id"),
            "operation": canonical_request.get("operation"),
            "target_group_key": canonical_request.get("target_group_key"),
            "package_family": canonical_request.get("package_family"),
        },
    }

    raw_response_payload = {
        "status_code": _status_code_for_mode(response_skeleton.get("status_code_map") if isinstance(response_skeleton.get("status_code_map"), dict) else {}, fixture_mode),
        "response_template_kind": response_skeleton.get("template_kind"),
        "body": {
            "runner_job_id": canonical_response.get("runner_job_id"),
            "status": canonical_response.get("outcome_status"),
            "status_reason": canonical_response.get("status_reason"),
            "target_group_key": canonical_response.get("target_group_key"),
        },
    }

    return redact_sensitive_fields(
        {
            "schema_version": ROUNDTRIP_NORMALIZATION_CASES_SCHEMA_VERSION,
            "roundtrip_normalization_case_id": case_id,
            "roundtrip_normalization_case_ref": _roundtrip_ref(case_id),
            "state": "defined",
            "target_group_adapter_skeleton_id": skeleton_doc.get("target_group_adapter_skeleton_id"),
            "target_group_adapter_package_id": skeleton_doc.get("target_group_adapter_package_id"),
            "request_response_fixture_pack_id": fixture_pack.get("request_response_fixture_pack_id"),
            "fixture_mode": fixture_mode,
            "raw_request_payload": raw_request_payload,
            "raw_response_payload": raw_response_payload,
            "expected_normalized_result": {
                "runner_job_id": canonical_response.get("runner_job_id"),
                "outcome_status": canonical_response.get("outcome_status"),
                "status_reason": canonical_response.get("status_reason"),
                "target_group_key": canonical_response.get("target_group_key"),
            },
        }
    )


def build_roundtrip_normalization_case_artifacts(skeletons_doc: dict, fixture_packs_doc: dict) -> tuple[dict, dict, dict]:
    cases: list[dict] = []
    review_items: list[dict] = []
    fixture_index = _fixture_pack_index(fixture_packs_doc)

    for skeleton_doc in skeletons_doc.get("skeletons") or []:
        if not isinstance(skeleton_doc, dict):
            continue
        fixture_pack = fixture_index.get(_normalize_text(skeleton_doc.get("target_group_adapter_package_id")) or "")
        reason_codes = ["target_group_skeleton_ready_for_roundtrip_case"]
        if fixture_pack is None:
            reason_codes.append("missing_request_response_fixture_pack")
            review_items.append(
                redact_sensitive_fields(
                    {
                        "schema_version": ROUNDTRIP_NORMALIZATION_REVIEW_QUEUE_SCHEMA_VERSION,
                        "queue_item_id": _roundtrip_review_item_id(skeleton_doc),
                        "state": "open",
                        "priority": "high",
                        "review_type": "roundtrip-normalization",
                        "target_group_adapter_skeleton_id": skeleton_doc.get("target_group_adapter_skeleton_id"),
                        "target_group_adapter_package_id": skeleton_doc.get("target_group_adapter_package_id"),
                        "reason_codes": reason_codes,
                    }
                )
            )
            continue

        pairs = _fixture_pairs(fixture_pack)
        if not pairs:
            review_items.append(
                redact_sensitive_fields(
                    {
                        "schema_version": ROUNDTRIP_NORMALIZATION_REVIEW_QUEUE_SCHEMA_VERSION,
                        "queue_item_id": _roundtrip_review_item_id(skeleton_doc),
                        "state": "open",
                        "priority": "medium",
                        "review_type": "roundtrip-normalization",
                        "target_group_adapter_skeleton_id": skeleton_doc.get("target_group_adapter_skeleton_id"),
                        "target_group_adapter_package_id": skeleton_doc.get("target_group_adapter_package_id"),
                        "reason_codes": ["no_fixture_pairs_available"],
                    }
                )
            )
            continue

        for _, (request_fixture, response_fixture) in sorted(pairs.items()):
            cases.append(_build_roundtrip_case(skeleton_doc, fixture_pack, request_fixture, response_fixture))

    cases_doc = {
        "schema_version": ROUNDTRIP_NORMALIZATION_CASES_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "case_count": len(cases),
        "cases": sorted(cases, key=lambda item: str(item.get("roundtrip_normalization_case_id") or "")),
    }
    review_queue = {
        "schema_version": ROUNDTRIP_NORMALIZATION_REVIEW_QUEUE_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "item_count": len(review_items),
        "items": sorted(review_items, key=lambda item: str(item.get("queue_item_id") or "")),
    }
    rollup = build_roundtrip_normalization_rollup(cases_doc, review_queue)
    return redact_sensitive_fields(cases_doc), redact_sensitive_fields(review_queue), redact_sensitive_fields(rollup)


def build_roundtrip_normalization_rollup(cases_doc: dict, review_queue: dict) -> dict:
    fixture_mode_counts: dict[str, int] = {}
    outcome_status_counts: dict[str, int] = {}
    adapter_group_counts: dict[str, int] = {}
    review_reason_counts: dict[str, int] = {}

    for item in cases_doc.get("cases") or []:
        if not isinstance(item, dict):
            continue
        mode = _normalize_text(item.get("fixture_mode")) or "unknown"
        expected = item.get("expected_normalized_result") if isinstance(item.get("expected_normalized_result"), dict) else {}
        raw_request = item.get("raw_request_payload") if isinstance(item.get("raw_request_payload"), dict) else {}
        adapter_group_key = _normalize_text(raw_request.get("adapter_group_key")) or "unknown"
        outcome_status = _normalize_text(expected.get("outcome_status")) or "unknown"
        fixture_mode_counts[mode] = fixture_mode_counts.get(mode, 0) + 1
        outcome_status_counts[outcome_status] = outcome_status_counts.get(outcome_status, 0) + 1
        adapter_group_counts[adapter_group_key] = adapter_group_counts.get(adapter_group_key, 0) + 1

    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        for reason in item.get("reason_codes") or []:
            normalized = _normalize_text(reason)
            if normalized:
                review_reason_counts[normalized] = review_reason_counts.get(normalized, 0) + 1

    return {
        "schema_version": ROUNDTRIP_NORMALIZATION_ROLLUP_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "case_count": int(cases_doc.get("case_count") or 0),
        "review_queue_count": int(review_queue.get("item_count") or 0),
        "fixture_mode_counts": fixture_mode_counts,
        "outcome_status_counts": outcome_status_counts,
        "adapter_group_counts": adapter_group_counts,
        "review_reason_counts": review_reason_counts,
    }


def render_target_group_adapter_skeletons_markdown(skeletons_doc: dict) -> str:
    lines = ["# Target-group adapter skeletons", "", f"Skeleton count: {int(skeletons_doc.get('skeleton_count') or 0)}"]
    for item in skeletons_doc.get("skeletons") or []:
        if not isinstance(item, dict):
            continue
        adapter_group = item.get("adapter_group") if isinstance(item.get("adapter_group"), dict) else {}
        target_group = item.get("target_group") if isinstance(item.get("target_group"), dict) else {}
        lines.extend([
            "",
            f"## {item.get('target_group_adapter_skeleton_id')}",
            f"- target_group_adapter_package_id: {item.get('target_group_adapter_package_id')}",
            f"- target_group_key: {target_group.get('target_group_key')}",
            f"- adapter_group_key: {adapter_group.get('adapter_group_key')}",
        ])
    return "\n".join(lines) + "\n"


def render_target_group_adapter_skeleton_review_queue_markdown(review_queue: dict) -> str:
    lines = ["# Target-group adapter skeleton review queue", "", f"Item count: {int(review_queue.get('item_count') or 0)}"]
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


def render_target_group_adapter_skeleton_rollup_markdown(rollup: dict) -> str:
    lines = ["# Target-group adapter skeleton rollup", ""]
    lines.append(f"Skeleton count: {int(rollup.get('skeleton_count') or 0)}")
    lines.append(f"Review queue count: {int(rollup.get('review_queue_count') or 0)}")
    return "\n".join(lines) + "\n"


def render_roundtrip_normalization_cases_markdown(cases_doc: dict) -> str:
    lines = ["# Round-trip normalization cases", "", f"Case count: {int(cases_doc.get('case_count') or 0)}"]
    for item in cases_doc.get("cases") or []:
        if not isinstance(item, dict):
            continue
        expected = item.get("expected_normalized_result") if isinstance(item.get("expected_normalized_result"), dict) else {}
        lines.extend([
            "",
            f"## {item.get('roundtrip_normalization_case_id')}",
            f"- target_group_adapter_skeleton_id: {item.get('target_group_adapter_skeleton_id')}",
            f"- fixture_mode: {item.get('fixture_mode')}",
            f"- expected_outcome_status: {expected.get('outcome_status')}",
        ])
    return "\n".join(lines) + "\n"


def render_roundtrip_normalization_review_queue_markdown(review_queue: dict) -> str:
    lines = ["# Round-trip normalization review queue", "", f"Item count: {int(review_queue.get('item_count') or 0)}"]
    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.extend([
            "",
            f"## {item.get('queue_item_id')}",
            f"- target_group_adapter_skeleton_id: {item.get('target_group_adapter_skeleton_id')}",
            f"- reason_codes: {', '.join(item.get('reason_codes') or [])}",
        ])
    return "\n".join(lines) + "\n"


def render_roundtrip_normalization_rollup_markdown(rollup: dict) -> str:
    lines = ["# Round-trip normalization rollup", ""]
    lines.append(f"Case count: {int(rollup.get('case_count') or 0)}")
    lines.append(f"Review queue count: {int(rollup.get('review_queue_count') or 0)}")
    return "\n".join(lines) + "\n"
