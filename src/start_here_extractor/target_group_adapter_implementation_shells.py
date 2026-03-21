from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .ingestion import utcnow_iso
from .security import redact_sensitive_fields

TARGET_GROUP_ADAPTER_IMPLEMENTATION_SHELLS_SCHEMA_VERSION = "1.0"
TARGET_GROUP_ADAPTER_IMPLEMENTATION_SHELL_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
TARGET_GROUP_ADAPTER_IMPLEMENTATION_SHELL_ROLLUP_SCHEMA_VERSION = "1.0"
END_TO_END_ROUNDTRIP_FIXTURE_EXECUTION_PACKS_SCHEMA_VERSION = "1.0"
END_TO_END_ROUNDTRIP_FIXTURE_EXECUTION_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
END_TO_END_ROUNDTRIP_FIXTURE_EXECUTION_ROLLUP_SCHEMA_VERSION = "1.0"

DEFAULT_EXECUTION_MODES = ["dry_run", "fixture_execution"]
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


def normalize_target_group_adapter_implementation_catalog(value: object) -> list[dict]:
    if isinstance(value, dict):
        entries = value.get("target_group_adapter_implementations") if isinstance(value.get("target_group_adapter_implementations"), list) else []
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
        implementation_group_key = _normalize_text(item.get("implementation_group_key"))
        if not target_group_key or not adapter_group_key or not implementation_group_key:
            continue
        normalized.append(
            redact_sensitive_fields(
                {
                    "target_group_key": target_group_key,
                    "adapter_group_key": adapter_group_key,
                    "implementation_group_key": implementation_group_key,
                    "implementation_group_name": _normalize_text(item.get("implementation_group_name")) or implementation_group_key,
                    "implementation_shell_kind": _normalize_text(item.get("implementation_shell_kind")) or f"{target_group_key}-implementation-shell",
                    "supported_target_group_keys": _normalize_str_list(item.get("supported_target_group_keys")) or [target_group_key],
                    "supported_adapter_group_keys": _normalize_str_list(item.get("supported_adapter_group_keys")) or [adapter_group_key],
                    "supported_target_systems": _normalize_str_list(item.get("supported_target_systems")),
                    "supported_target_types": _normalize_str_list(item.get("supported_target_types")),
                    "supported_operations": _normalize_str_list(item.get("supported_operations")),
                    "supported_request_methods": [m.upper() for m in _normalize_str_list(item.get("supported_request_methods"))],
                    "supported_fixture_modes": [m for m in _normalize_str_list(item.get("supported_fixture_modes")) if m in _ALLOWED_FIXTURE_MODES] or ["success", "failure", "defer", "skip"],
                    "adapter_module": _normalize_text(item.get("adapter_module")) or f"start_here_extractor.adapters.{target_group_key.replace('-', '_')}",
                    "adapter_class": _normalize_text(item.get("adapter_class")) or ''.join(part.capitalize() for part in target_group_key.replace('-', '_').split('_')) + 'Adapter',
                    "entrypoint": _normalize_text(item.get("entrypoint")) or "execute",
                    "supports_live_execute": _normalize_bool(item.get("supports_live_execute"), default=False),
                    "supports_dry_run": _normalize_bool(item.get("supports_dry_run"), default=True),
                    "active": _normalize_bool(item.get("active"), default=True),
                }
            )
        )
    normalized.sort(key=lambda item: str(item.get("implementation_group_key") or ""))
    return normalized


def load_target_group_adapter_implementation_catalog(path: str | Path) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    payload = json.loads(target.read_text(encoding="utf-8"))
    return normalize_target_group_adapter_implementation_catalog(payload)


def load_target_group_adapter_skeletons(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Target-group adapter skeletons payload must be a JSON object")


def load_roundtrip_normalization_cases(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Round-trip normalization cases payload must be a JSON object")




def load_target_group_adapter_implementation_shells(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Target-group adapter implementation shells payload must be a JSON object")


def derive_target_group_adapter_implementation_shell_id(skeleton_doc: dict, catalog_item: dict) -> str:
    payload = {
        "target_group_adapter_skeleton_id": _normalize_text(skeleton_doc.get("target_group_adapter_skeleton_id")),
        "implementation_group_key": _normalize_text(catalog_item.get("implementation_group_key")),
        "implementation_shell_kind": _normalize_text(catalog_item.get("implementation_shell_kind")),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"target-group-impl-shell-{digest[:24]}"


def derive_end_to_end_roundtrip_fixture_execution_pack_id(shell_doc: dict) -> str:
    payload = {
        "target_group_adapter_implementation_shell_id": _normalize_text(shell_doc.get("target_group_adapter_implementation_shell_id")),
        "implementation_group_key": _normalize_text(shell_doc.get("implementation_group", {}).get("implementation_group_key")) if isinstance(shell_doc.get("implementation_group"), dict) else None,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"e2e-roundtrip-pack-{digest[:24]}"


def _implementation_review_item_id(skeleton_doc: dict) -> str:
    skeleton_id = _normalize_text(skeleton_doc.get("target_group_adapter_skeleton_id")) or "unknown"
    digest = hashlib.sha256(f"implementation-shell:{skeleton_id}".encode("utf-8")).hexdigest()
    return f"implementation-shell-review-{digest[:24]}"


def _execution_pack_review_item_id(shell_doc: dict) -> str:
    shell_id = _normalize_text(shell_doc.get("target_group_adapter_implementation_shell_id")) or "unknown"
    digest = hashlib.sha256(f"execution-pack:{shell_id}".encode("utf-8")).hexdigest()
    return f"execution-pack-review-{digest[:24]}"


def _shell_ref(shell_id: str) -> str:
    return f"target-group-adapter-implementation-shell://{shell_id}"


def _pack_ref(pack_id: str) -> str:
    return f"end-to-end-roundtrip-fixture-execution-pack://{pack_id}"


def _roundtrip_case_index(cases_doc: dict) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for item in cases_doc.get("cases") or []:
        if not isinstance(item, dict):
            continue
        skeleton_id = _normalize_text(item.get("target_group_adapter_skeleton_id"))
        if not skeleton_id:
            continue
        index.setdefault(skeleton_id, []).append(redact_sensitive_fields(dict(item)))
    return index


def _compatible_catalog_item(skeleton_doc: dict, catalog_item: dict) -> bool:
    if not _normalize_bool(catalog_item.get("active"), default=True):
        return False
    target_group = skeleton_doc.get("target_group") if isinstance(skeleton_doc.get("target_group"), dict) else {}
    target = skeleton_doc.get("target") if isinstance(skeleton_doc.get("target"), dict) else {}
    adapter_group = skeleton_doc.get("adapter_group") if isinstance(skeleton_doc.get("adapter_group"), dict) else {}
    request_skeleton = skeleton_doc.get("request_skeleton") if isinstance(skeleton_doc.get("request_skeleton"), dict) else {}

    target_group_key = _normalize_text(target_group.get("target_group_key"))
    adapter_group_key = _normalize_text(adapter_group.get("adapter_group_key"))
    target_system = _normalize_text(target.get("target_system"))
    target_type = _normalize_text(target.get("target_type"))
    request_method = _normalize_text(request_skeleton.get("request_method"))
    operation = _normalize_text(request_skeleton.get("operation"))

    if (supported := catalog_item.get("supported_target_group_keys")) and target_group_key not in supported:
        return False
    if (supported := catalog_item.get("supported_adapter_group_keys")) and adapter_group_key not in supported:
        return False
    if (supported := catalog_item.get("supported_target_systems")) and target_system not in supported:
        return False
    if (supported := catalog_item.get("supported_target_types")) and target_type not in supported:
        return False
    if (supported := catalog_item.get("supported_request_methods")) and request_method and request_method.upper() not in supported:
        return False
    if (supported := catalog_item.get("supported_operations")) and operation not in supported:
        return False
    return True


def _catalog_candidates(skeleton_doc: dict, catalog: list[dict]) -> list[dict]:
    return [redact_sensitive_fields(dict(item)) for item in catalog if _compatible_catalog_item(skeleton_doc, item)]


def _build_target_group_adapter_implementation_shell(skeleton_doc: dict, cases: list[dict], catalog_item: dict) -> dict:
    shell_id = derive_target_group_adapter_implementation_shell_id(skeleton_doc, catalog_item)
    target_group = skeleton_doc.get("target_group") if isinstance(skeleton_doc.get("target_group"), dict) else {}
    target = skeleton_doc.get("target") if isinstance(skeleton_doc.get("target"), dict) else {}
    adapter_group = skeleton_doc.get("adapter_group") if isinstance(skeleton_doc.get("adapter_group"), dict) else {}
    request_skeleton = skeleton_doc.get("request_skeleton") if isinstance(skeleton_doc.get("request_skeleton"), dict) else {}
    response_skeleton = skeleton_doc.get("response_skeleton") if isinstance(skeleton_doc.get("response_skeleton"), dict) else {}
    fixture_modes = [item.get("fixture_mode") for item in cases if isinstance(item, dict) and _normalize_text(item.get("fixture_mode"))]

    return redact_sensitive_fields(
        {
            "schema_version": TARGET_GROUP_ADAPTER_IMPLEMENTATION_SHELLS_SCHEMA_VERSION,
            "target_group_adapter_implementation_shell_id": shell_id,
            "target_group_adapter_implementation_shell_ref": _shell_ref(shell_id),
            "state": "implementation-shelled",
            "target_group_adapter_skeleton_id": skeleton_doc.get("target_group_adapter_skeleton_id"),
            "roundtrip_case_ids": [item.get("roundtrip_normalization_case_id") for item in cases if isinstance(item, dict)],
            "runner_job_id": skeleton_doc.get("runner_job_id"),
            "contract_id": skeleton_doc.get("contract_id"),
            "event_id": skeleton_doc.get("event_id"),
            "target_group": target_group,
            "target": target,
            "adapter_group": adapter_group,
            "implementation_group": {
                "implementation_group_key": catalog_item.get("implementation_group_key"),
                "implementation_group_name": catalog_item.get("implementation_group_name"),
                "implementation_shell_kind": catalog_item.get("implementation_shell_kind"),
            },
            "adapter_entrypoint": {
                "module": catalog_item.get("adapter_module"),
                "class": catalog_item.get("adapter_class"),
                "entrypoint": catalog_item.get("entrypoint"),
            },
            "execution_capabilities": {
                "supports_live_execute": catalog_item.get("supports_live_execute"),
                "supports_dry_run": catalog_item.get("supports_dry_run"),
                "supported_fixture_modes": fixture_modes or list(catalog_item.get("supported_fixture_modes") or []),
                "execution_modes": list(DEFAULT_EXECUTION_MODES),
            },
            "request_contract": {
                "request_method": request_skeleton.get("request_method"),
                "request_path_template": request_skeleton.get("request_path_template"),
                "operation": request_skeleton.get("operation"),
                "required_fields": request_skeleton.get("required_fields") or [],
                "correlation_keys": request_skeleton.get("correlation_keys") or [],
            },
            "response_contract": {
                "template_kind": response_skeleton.get("template_kind"),
                "accepted_canonical_statuses": response_skeleton.get("accepted_canonical_statuses") or [],
                "status_map": response_skeleton.get("status_map") or {},
                "status_code_map": response_skeleton.get("status_code_map") or {},
            },
            "audit": {
                "created_at": utcnow_iso(),
                "source_stage": "target-group-adapter-skeleton",
            },
        }
    )


def _build_end_to_end_roundtrip_fixture_execution_pack(shell_doc: dict, cases: list[dict]) -> dict:
    pack_id = derive_end_to_end_roundtrip_fixture_execution_pack_id(shell_doc)
    execution_cases: list[dict] = []
    for item in cases:
        if not isinstance(item, dict):
            continue
        execution_cases.append(
            redact_sensitive_fields(
                {
                    "roundtrip_normalization_case_id": item.get("roundtrip_normalization_case_id"),
                    "fixture_mode": item.get("fixture_mode"),
                    "raw_request_payload": item.get("raw_request_payload"),
                    "expected_response_payload": item.get("expected_response_payload"),
                    "expected_normalized_result": item.get("expected_normalized_result"),
                    "response_status_code": item.get("response_status_code"),
                }
            )
        )
    return redact_sensitive_fields(
        {
            "schema_version": END_TO_END_ROUNDTRIP_FIXTURE_EXECUTION_PACKS_SCHEMA_VERSION,
            "end_to_end_roundtrip_fixture_execution_pack_id": pack_id,
            "end_to_end_roundtrip_fixture_execution_pack_ref": _pack_ref(pack_id),
            "state": "fixture-packed",
            "target_group_adapter_implementation_shell_id": shell_doc.get("target_group_adapter_implementation_shell_id"),
            "target_group": shell_doc.get("target_group"),
            "target": shell_doc.get("target"),
            "implementation_group": shell_doc.get("implementation_group"),
            "adapter_entrypoint": shell_doc.get("adapter_entrypoint"),
            "execution_modes": shell_doc.get("execution_capabilities", {}).get("execution_modes") if isinstance(shell_doc.get("execution_capabilities"), dict) else list(DEFAULT_EXECUTION_MODES),
            "cases": execution_cases,
            "audit": {
                "created_at": utcnow_iso(),
                "source_stage": "target-group-adapter-implementation-shell",
            },
        }
    )


def build_target_group_adapter_implementation_shell_artifacts(skeletons_doc: dict, cases_doc: dict, catalog: list[dict]) -> tuple[dict, dict, dict]:
    case_index = _roundtrip_case_index(cases_doc)
    shells: list[dict] = []
    review_items: list[dict] = []

    for skeleton_doc in skeletons_doc.get("skeletons") or []:
        if not isinstance(skeleton_doc, dict):
            continue
        skeleton_id = _normalize_text(skeleton_doc.get("target_group_adapter_skeleton_id"))
        matching_cases = case_index.get(skeleton_id or "", [])
        if not matching_cases:
            review_items.append(
                redact_sensitive_fields(
                    {
                        "schema_version": TARGET_GROUP_ADAPTER_IMPLEMENTATION_SHELL_REVIEW_QUEUE_SCHEMA_VERSION,
                        "queue_item_id": _implementation_review_item_id(skeleton_doc),
                        "state": "open",
                        "priority": "medium",
                        "review_type": "target-group-adapter-implementation-shell",
                        "target_group_adapter_skeleton_id": skeleton_doc.get("target_group_adapter_skeleton_id"),
                        "reason_codes": ["no_roundtrip_cases_found"],
                        "skeleton_summary": redact_sensitive_fields(skeleton_doc),
                    }
                )
            )
            continue
        candidates = _catalog_candidates(skeleton_doc, catalog)
        if not candidates:
            review_items.append(
                redact_sensitive_fields(
                    {
                        "schema_version": TARGET_GROUP_ADAPTER_IMPLEMENTATION_SHELL_REVIEW_QUEUE_SCHEMA_VERSION,
                        "queue_item_id": _implementation_review_item_id(skeleton_doc),
                        "state": "open",
                        "priority": "high",
                        "review_type": "target-group-adapter-implementation-shell",
                        "target_group_adapter_skeleton_id": skeleton_doc.get("target_group_adapter_skeleton_id"),
                        "reason_codes": ["no_target_group_implementation_match"],
                        "skeleton_summary": redact_sensitive_fields(skeleton_doc),
                    }
                )
            )
            continue
        if len(candidates) > 1:
            review_items.append(
                redact_sensitive_fields(
                    {
                        "schema_version": TARGET_GROUP_ADAPTER_IMPLEMENTATION_SHELL_REVIEW_QUEUE_SCHEMA_VERSION,
                        "queue_item_id": _implementation_review_item_id(skeleton_doc),
                        "state": "open",
                        "priority": "high",
                        "review_type": "target-group-adapter-implementation-shell",
                        "target_group_adapter_skeleton_id": skeleton_doc.get("target_group_adapter_skeleton_id"),
                        "reason_codes": ["ambiguous_target_group_implementation_match"],
                        "candidate_count": len(candidates),
                        "candidate_summaries": candidates,
                        "skeleton_summary": redact_sensitive_fields(skeleton_doc),
                    }
                )
            )
            continue
        shells.append(_build_target_group_adapter_implementation_shell(skeleton_doc, matching_cases, candidates[0]))

    shells_doc = redact_sensitive_fields(
        {
            "schema_version": TARGET_GROUP_ADAPTER_IMPLEMENTATION_SHELLS_SCHEMA_VERSION,
            "shell_count": len(shells),
            "shells": shells,
            "generated_at": utcnow_iso(),
        }
    )
    review_queue = redact_sensitive_fields(
        {
            "schema_version": TARGET_GROUP_ADAPTER_IMPLEMENTATION_SHELL_REVIEW_QUEUE_SCHEMA_VERSION,
            "item_count": len(review_items),
            "items": review_items,
            "generated_at": utcnow_iso(),
        }
    )
    group_counts: dict[str, int] = {}
    for item in shells:
        group = item.get("implementation_group") if isinstance(item.get("implementation_group"), dict) else {}
        key = _normalize_text(group.get("implementation_group_key")) or "unknown"
        group_counts[key] = group_counts.get(key, 0) + 1
    rollup = redact_sensitive_fields(
        {
            "schema_version": TARGET_GROUP_ADAPTER_IMPLEMENTATION_SHELL_ROLLUP_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "shell_count": len(shells),
            "review_queue_count": len(review_items),
            "implementation_group_counts": group_counts,
        }
    )
    return shells_doc, review_queue, rollup


def build_end_to_end_roundtrip_fixture_execution_pack_artifacts(shells_doc: dict, cases_doc: dict) -> tuple[dict, dict, dict]:
    case_index = _roundtrip_case_index(cases_doc)
    packs: list[dict] = []
    review_items: list[dict] = []

    for shell_doc in shells_doc.get("shells") or []:
        if not isinstance(shell_doc, dict):
            continue
        case_ids = {str(case_id) for case_id in shell_doc.get("roundtrip_case_ids") or [] if _normalize_text(case_id)}
        matching_cases = [item for item in case_index.get(_normalize_text(shell_doc.get("target_group_adapter_skeleton_id")) or "", []) if str(item.get("roundtrip_normalization_case_id")) in case_ids]
        if not matching_cases:
            review_items.append(
                redact_sensitive_fields(
                    {
                        "schema_version": END_TO_END_ROUNDTRIP_FIXTURE_EXECUTION_REVIEW_QUEUE_SCHEMA_VERSION,
                        "queue_item_id": _execution_pack_review_item_id(shell_doc),
                        "state": "open",
                        "priority": "medium",
                        "review_type": "end-to-end-roundtrip-fixture-execution-pack",
                        "target_group_adapter_implementation_shell_id": shell_doc.get("target_group_adapter_implementation_shell_id"),
                        "reason_codes": ["no_roundtrip_cases_for_shell"],
                        "shell_summary": redact_sensitive_fields(shell_doc),
                    }
                )
            )
            continue
        packs.append(_build_end_to_end_roundtrip_fixture_execution_pack(shell_doc, matching_cases))

    packs_doc = redact_sensitive_fields(
        {
            "schema_version": END_TO_END_ROUNDTRIP_FIXTURE_EXECUTION_PACKS_SCHEMA_VERSION,
            "pack_count": len(packs),
            "packs": packs,
            "generated_at": utcnow_iso(),
        }
    )
    review_queue = redact_sensitive_fields(
        {
            "schema_version": END_TO_END_ROUNDTRIP_FIXTURE_EXECUTION_REVIEW_QUEUE_SCHEMA_VERSION,
            "item_count": len(review_items),
            "items": review_items,
            "generated_at": utcnow_iso(),
        }
    )
    mode_counts: dict[str, int] = {}
    for pack in packs:
        for case in pack.get("cases") or []:
            if not isinstance(case, dict):
                continue
            mode = _normalize_text(case.get("fixture_mode")) or "unknown"
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
    rollup = redact_sensitive_fields(
        {
            "schema_version": END_TO_END_ROUNDTRIP_FIXTURE_EXECUTION_ROLLUP_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "pack_count": len(packs),
            "review_queue_count": len(review_items),
            "fixture_mode_counts": mode_counts,
        }
    )
    return packs_doc, review_queue, rollup


def render_target_group_adapter_implementation_shells_markdown(shells_doc: dict) -> str:
    lines = ["# Target-Group Adapter Implementation Shells", ""]
    lines.append(f"Shell count: {shells_doc.get('shell_count', 0)}")
    lines.append("")
    for item in shells_doc.get("shells") or []:
        if not isinstance(item, dict):
            continue
        group = item.get("implementation_group") if isinstance(item.get("implementation_group"), dict) else {}
        lines.append(f"- `{item.get('target_group_adapter_implementation_shell_id')}` :: {group.get('implementation_group_key')}")
    return "\n".join(lines) + "\n"


def render_target_group_adapter_implementation_shell_review_queue_markdown(review_queue: dict) -> str:
    lines = ["# Target-Group Adapter Implementation Shell Review Queue", ""]
    lines.append(f"Open items: {review_queue.get('item_count', 0)}")
    lines.append("")
    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('queue_item_id')}` :: {', '.join(item.get('reason_codes') or [])}")
    return "\n".join(lines) + "\n"


def render_target_group_adapter_implementation_shell_rollup_markdown(rollup: dict) -> str:
    lines = ["# Target-Group Adapter Implementation Shell Rollup", ""]
    lines.append(f"Shell count: {rollup.get('shell_count', 0)}")
    lines.append(f"Review queue count: {rollup.get('review_queue_count', 0)}")
    return "\n".join(lines) + "\n"


def render_end_to_end_roundtrip_fixture_execution_packs_markdown(packs_doc: dict) -> str:
    lines = ["# End-to-End Round-Trip Fixture Execution Packs", ""]
    lines.append(f"Pack count: {packs_doc.get('pack_count', 0)}")
    lines.append("")
    for item in packs_doc.get("packs") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('end_to_end_roundtrip_fixture_execution_pack_id')}` :: cases={len(item.get('cases') or [])}")
    return "\n".join(lines) + "\n"


def render_end_to_end_roundtrip_fixture_execution_review_queue_markdown(review_queue: dict) -> str:
    lines = ["# End-to-End Round-Trip Fixture Execution Review Queue", ""]
    lines.append(f"Open items: {review_queue.get('item_count', 0)}")
    lines.append("")
    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('queue_item_id')}` :: {', '.join(item.get('reason_codes') or [])}")
    return "\n".join(lines) + "\n"


def render_end_to_end_roundtrip_fixture_execution_rollup_markdown(rollup: dict) -> str:
    lines = ["# End-to-End Round-Trip Fixture Execution Rollup", ""]
    lines.append(f"Pack count: {rollup.get('pack_count', 0)}")
    lines.append(f"Review queue count: {rollup.get('review_queue_count', 0)}")
    return "\n".join(lines) + "\n"
