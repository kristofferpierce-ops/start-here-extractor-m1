from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .ingestion import utcnow_iso
from .security import redact_sensitive_fields

TARGET_GROUP_ADAPTER_EXECUTION_HARNESSES_SCHEMA_VERSION = "1.0"
TARGET_GROUP_ADAPTER_EXECUTION_HARNESS_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
TARGET_GROUP_ADAPTER_EXECUTION_HARNESS_ROLLUP_SCHEMA_VERSION = "1.0"
REPLAYABLE_DRY_RUN_ORCHESTRATION_PACKS_SCHEMA_VERSION = "1.0"
REPLAYABLE_DRY_RUN_ORCHESTRATION_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
REPLAYABLE_DRY_RUN_ORCHESTRATION_ROLLUP_SCHEMA_VERSION = "1.0"

DEFAULT_HARNESS_EXECUTION_MODES = ["dry_run", "fixture_execution", "replayable_dry_run"]
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


def normalize_target_group_execution_harness_catalog(value: object) -> list[dict]:
    if isinstance(value, dict):
        entries = value.get("target_group_execution_harnesses") if isinstance(value.get("target_group_execution_harnesses"), list) else []
    elif isinstance(value, list):
        entries = value
    else:
        entries = []

    normalized: list[dict] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        target_group_key = _normalize_text(item.get("target_group_key"))
        implementation_group_key = _normalize_text(item.get("implementation_group_key"))
        harness_group_key = _normalize_text(item.get("harness_group_key"))
        if not target_group_key or not implementation_group_key or not harness_group_key:
            continue
        supported_fixture_modes = [mode for mode in _normalize_str_list(item.get("supported_fixture_modes")) if mode in _ALLOWED_FIXTURE_MODES]
        normalized.append(
            redact_sensitive_fields(
                {
                    "target_group_key": target_group_key,
                    "implementation_group_key": implementation_group_key,
                    "harness_group_key": harness_group_key,
                    "harness_group_name": _normalize_text(item.get("harness_group_name")) or harness_group_key,
                    "harness_kind": _normalize_text(item.get("harness_kind")) or f"{target_group_key}-execution-harness",
                    "supported_target_group_keys": _normalize_str_list(item.get("supported_target_group_keys")) or [target_group_key],
                    "supported_implementation_group_keys": _normalize_str_list(item.get("supported_implementation_group_keys")) or [implementation_group_key],
                    "supported_target_systems": _normalize_str_list(item.get("supported_target_systems")),
                    "supported_target_types": _normalize_str_list(item.get("supported_target_types")),
                    "supported_operations": _normalize_str_list(item.get("supported_operations")),
                    "supported_fixture_modes": supported_fixture_modes or ["success", "failure", "defer", "skip"],
                    "execution_modes": _normalize_str_list(item.get("execution_modes")) or list(DEFAULT_HARNESS_EXECUTION_MODES),
                    "network_mode": _normalize_text(item.get("network_mode")) or "offline",
                    "replay_token_keys": _normalize_str_list(item.get("replay_token_keys")),
                    "correlation_keys": _normalize_str_list(item.get("correlation_keys")),
                    "supports_replayable_dry_run": _normalize_bool(item.get("supports_replayable_dry_run"), default=True),
                    "supports_fixture_execution": _normalize_bool(item.get("supports_fixture_execution"), default=True),
                    "supports_live_execute": _normalize_bool(item.get("supports_live_execute"), default=False),
                    "active": _normalize_bool(item.get("active"), default=True),
                }
            )
        )
    normalized.sort(key=lambda item: str(item.get("harness_group_key") or ""))
    return normalized


def load_target_group_execution_harness_catalog(path: str | Path) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    payload = json.loads(target.read_text(encoding="utf-8"))
    return normalize_target_group_execution_harness_catalog(payload)


def load_target_group_adapter_implementation_shells(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Target-group adapter implementation shells payload must be a JSON object")


def load_end_to_end_roundtrip_fixture_execution_packs(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("End-to-end round-trip fixture execution packs payload must be a JSON object")


def load_target_group_adapter_execution_harnesses(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Target-group adapter execution harnesses payload must be a JSON object")


def derive_target_group_adapter_execution_harness_id(shell_doc: dict, catalog_item: dict) -> str:
    payload = {
        "target_group_adapter_implementation_shell_id": _normalize_text(shell_doc.get("target_group_adapter_implementation_shell_id")),
        "harness_group_key": _normalize_text(catalog_item.get("harness_group_key")),
        "harness_kind": _normalize_text(catalog_item.get("harness_kind")),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"target-group-execution-harness-{digest[:24]}"


def derive_replayable_dry_run_orchestration_pack_id(harness_doc: dict) -> str:
    payload = {
        "target_group_adapter_execution_harness_id": _normalize_text(harness_doc.get("target_group_adapter_execution_harness_id")),
        "harness_group_key": _normalize_text(harness_doc.get("harness_group", {}).get("harness_group_key")) if isinstance(harness_doc.get("harness_group"), dict) else None,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"replayable-dry-run-pack-{digest[:24]}"


def _harness_review_item_id(shell_doc: dict) -> str:
    shell_id = _normalize_text(shell_doc.get("target_group_adapter_implementation_shell_id")) or "unknown"
    digest = hashlib.sha256(f"execution-harness:{shell_id}".encode("utf-8")).hexdigest()
    return f"execution-harness-review-{digest[:24]}"


def _orchestration_review_item_id(harness_doc: dict) -> str:
    harness_id = _normalize_text(harness_doc.get("target_group_adapter_execution_harness_id")) or "unknown"
    digest = hashlib.sha256(f"replayable-dry-run-pack:{harness_id}".encode("utf-8")).hexdigest()
    return f"replayable-dry-run-pack-review-{digest[:24]}"


def _harness_ref(harness_id: str) -> str:
    return f"target-group-adapter-execution-harness://{harness_id}"


def _orchestration_ref(pack_id: str) -> str:
    return f"replayable-dry-run-orchestration-pack://{pack_id}"


def _pack_index(packs_doc: dict) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for item in packs_doc.get("packs") or []:
        if not isinstance(item, dict):
            continue
        shell_id = _normalize_text(item.get("target_group_adapter_implementation_shell_id"))
        if shell_id:
            index[shell_id] = redact_sensitive_fields(dict(item))
    return index


def _compatible_catalog_item(shell_doc: dict, pack_doc: dict, catalog_item: dict) -> bool:
    if not _normalize_bool(catalog_item.get("active"), default=True):
        return False
    target_group = shell_doc.get("target_group") if isinstance(shell_doc.get("target_group"), dict) else {}
    target = shell_doc.get("target") if isinstance(shell_doc.get("target"), dict) else {}
    implementation_group = shell_doc.get("implementation_group") if isinstance(shell_doc.get("implementation_group"), dict) else {}
    request_contract = shell_doc.get("request_contract") if isinstance(shell_doc.get("request_contract"), dict) else {}

    target_group_key = _normalize_text(target_group.get("target_group_key"))
    implementation_group_key = _normalize_text(implementation_group.get("implementation_group_key"))
    target_system = _normalize_text(target.get("target_system"))
    target_type = _normalize_text(target.get("target_type"))
    operation = _normalize_text(request_contract.get("operation"))
    pack_modes = {
        _normalize_text(case.get("fixture_mode"))
        for case in pack_doc.get("cases") or []
        if isinstance(case, dict) and _normalize_text(case.get("fixture_mode"))
    }

    if (supported := catalog_item.get("supported_target_group_keys")) and target_group_key not in supported:
        return False
    if (supported := catalog_item.get("supported_implementation_group_keys")) and implementation_group_key not in supported:
        return False
    if (supported := catalog_item.get("supported_target_systems")) and target_system not in supported:
        return False
    if (supported := catalog_item.get("supported_target_types")) and target_type not in supported:
        return False
    if (supported := catalog_item.get("supported_operations")) and operation not in supported:
        return False
    if (supported := set(catalog_item.get("supported_fixture_modes") or [])) and pack_modes and not (pack_modes & supported):
        return False
    return True


def _catalog_candidates(shell_doc: dict, pack_doc: dict, catalog: list[dict]) -> list[dict]:
    return [redact_sensitive_fields(dict(item)) for item in catalog if _compatible_catalog_item(shell_doc, pack_doc, item)]


def _build_target_group_adapter_execution_harness(shell_doc: dict, pack_doc: dict, catalog_item: dict) -> dict:
    harness_id = derive_target_group_adapter_execution_harness_id(shell_doc, catalog_item)
    target_group = shell_doc.get("target_group") if isinstance(shell_doc.get("target_group"), dict) else {}
    target = shell_doc.get("target") if isinstance(shell_doc.get("target"), dict) else {}
    implementation_group = shell_doc.get("implementation_group") if isinstance(shell_doc.get("implementation_group"), dict) else {}
    adapter_entrypoint = shell_doc.get("adapter_entrypoint") if isinstance(shell_doc.get("adapter_entrypoint"), dict) else {}
    execution_capabilities = shell_doc.get("execution_capabilities") if isinstance(shell_doc.get("execution_capabilities"), dict) else {}
    request_contract = shell_doc.get("request_contract") if isinstance(shell_doc.get("request_contract"), dict) else {}
    response_contract = shell_doc.get("response_contract") if isinstance(shell_doc.get("response_contract"), dict) else {}

    case_ids = [item.get("roundtrip_normalization_case_id") for item in pack_doc.get("cases") or [] if isinstance(item, dict)]
    fixture_modes = [
        item.get("fixture_mode")
        for item in pack_doc.get("cases") or []
        if isinstance(item, dict) and _normalize_text(item.get("fixture_mode"))
    ]

    return redact_sensitive_fields(
        {
            "schema_version": TARGET_GROUP_ADAPTER_EXECUTION_HARNESSES_SCHEMA_VERSION,
            "target_group_adapter_execution_harness_id": harness_id,
            "target_group_adapter_execution_harness_ref": _harness_ref(harness_id),
            "state": "execution-harnessed",
            "target_group_adapter_implementation_shell_id": shell_doc.get("target_group_adapter_implementation_shell_id"),
            "end_to_end_roundtrip_fixture_execution_pack_id": pack_doc.get("end_to_end_roundtrip_fixture_execution_pack_id"),
            "target_group": target_group,
            "target": target,
            "implementation_group": implementation_group,
            "harness_group": {
                "harness_group_key": catalog_item.get("harness_group_key"),
                "harness_group_name": catalog_item.get("harness_group_name"),
                "harness_kind": catalog_item.get("harness_kind"),
            },
            "adapter_entrypoint": adapter_entrypoint,
            "execution_context": {
                "execution_modes": catalog_item.get("execution_modes") or list(DEFAULT_HARNESS_EXECUTION_MODES),
                "network_mode": catalog_item.get("network_mode") or "offline",
                "supports_replayable_dry_run": catalog_item.get("supports_replayable_dry_run"),
                "supports_fixture_execution": catalog_item.get("supports_fixture_execution"),
                "supports_live_execute": catalog_item.get("supports_live_execute"),
                "replay_token_keys": catalog_item.get("replay_token_keys") or [],
                "correlation_keys": catalog_item.get("correlation_keys") or request_contract.get("correlation_keys") or [],
            },
            "pack_summary": {
                "end_to_end_roundtrip_fixture_execution_pack_ref": pack_doc.get("end_to_end_roundtrip_fixture_execution_pack_ref"),
                "case_count": len(pack_doc.get("cases") or []),
                "roundtrip_case_ids": case_ids,
                "fixture_modes": fixture_modes,
            },
            "request_contract": request_contract,
            "response_contract": response_contract,
            "execution_capabilities": execution_capabilities,
            "audit": {
                "created_at": utcnow_iso(),
                "source_stage": "target-group-adapter-implementation-shell",
            },
        }
    )


def _build_replayable_dry_run_orchestration_pack(harness_doc: dict, pack_doc: dict) -> dict:
    pack_id = derive_replayable_dry_run_orchestration_pack_id(harness_doc)
    steps: list[dict] = []
    for index, case in enumerate(pack_doc.get("cases") or [], start=1):
        if not isinstance(case, dict):
            continue
        case_id = _normalize_text(case.get("roundtrip_normalization_case_id")) or f"case-{index}"
        fixture_mode = _normalize_text(case.get("fixture_mode")) or "unknown"
        steps.append(
            redact_sensitive_fields(
                {
                    "step_id": f"{pack_id}:step:{index}",
                    "roundtrip_normalization_case_id": case_id,
                    "fixture_mode": fixture_mode,
                    "execution_mode": "replayable_dry_run",
                    "request_payload": case.get("raw_request_payload"),
                    "expected_response_payload": case.get("expected_response_payload"),
                    "expected_normalized_result": case.get("expected_normalized_result"),
                    "response_status_code": case.get("response_status_code"),
                }
            )
        )
    return redact_sensitive_fields(
        {
            "schema_version": REPLAYABLE_DRY_RUN_ORCHESTRATION_PACKS_SCHEMA_VERSION,
            "replayable_dry_run_orchestration_pack_id": pack_id,
            "replayable_dry_run_orchestration_pack_ref": _orchestration_ref(pack_id),
            "state": "replay-packed",
            "target_group_adapter_execution_harness_id": harness_doc.get("target_group_adapter_execution_harness_id"),
            "target_group": harness_doc.get("target_group"),
            "target": harness_doc.get("target"),
            "harness_group": harness_doc.get("harness_group"),
            "adapter_entrypoint": harness_doc.get("adapter_entrypoint"),
            "execution_context": harness_doc.get("execution_context"),
            "fixture_pack_ref": pack_doc.get("end_to_end_roundtrip_fixture_execution_pack_ref"),
            "steps": steps,
            "audit": {
                "created_at": utcnow_iso(),
                "source_stage": "target-group-adapter-execution-harness",
            },
        }
    )


def build_target_group_adapter_execution_harness_artifacts(shells_doc: dict, packs_doc: dict, catalog: list[dict]) -> tuple[dict, dict, dict]:
    pack_index = _pack_index(packs_doc)
    harnesses: list[dict] = []
    review_items: list[dict] = []

    for shell_doc in shells_doc.get("shells") or []:
        if not isinstance(shell_doc, dict):
            continue
        shell_id = _normalize_text(shell_doc.get("target_group_adapter_implementation_shell_id"))
        pack_doc = pack_index.get(shell_id or "")
        if not pack_doc:
            review_items.append(
                redact_sensitive_fields(
                    {
                        "schema_version": TARGET_GROUP_ADAPTER_EXECUTION_HARNESS_REVIEW_QUEUE_SCHEMA_VERSION,
                        "queue_item_id": _harness_review_item_id(shell_doc),
                        "state": "open",
                        "priority": "medium",
                        "review_type": "target-group-adapter-execution-harness",
                        "target_group_adapter_implementation_shell_id": shell_doc.get("target_group_adapter_implementation_shell_id"),
                        "reason_codes": ["no_execution_pack_found"],
                        "shell_summary": redact_sensitive_fields(shell_doc),
                    }
                )
            )
            continue
        candidates = _catalog_candidates(shell_doc, pack_doc, catalog)
        if not candidates:
            review_items.append(
                redact_sensitive_fields(
                    {
                        "schema_version": TARGET_GROUP_ADAPTER_EXECUTION_HARNESS_REVIEW_QUEUE_SCHEMA_VERSION,
                        "queue_item_id": _harness_review_item_id(shell_doc),
                        "state": "open",
                        "priority": "high",
                        "review_type": "target-group-adapter-execution-harness",
                        "target_group_adapter_implementation_shell_id": shell_doc.get("target_group_adapter_implementation_shell_id"),
                        "reason_codes": ["no_execution_harness_match"],
                        "shell_summary": redact_sensitive_fields(shell_doc),
                    }
                )
            )
            continue
        if len(candidates) > 1:
            review_items.append(
                redact_sensitive_fields(
                    {
                        "schema_version": TARGET_GROUP_ADAPTER_EXECUTION_HARNESS_REVIEW_QUEUE_SCHEMA_VERSION,
                        "queue_item_id": _harness_review_item_id(shell_doc),
                        "state": "open",
                        "priority": "high",
                        "review_type": "target-group-adapter-execution-harness",
                        "target_group_adapter_implementation_shell_id": shell_doc.get("target_group_adapter_implementation_shell_id"),
                        "reason_codes": ["ambiguous_execution_harness_match"],
                        "candidate_count": len(candidates),
                        "candidate_summaries": candidates,
                        "shell_summary": redact_sensitive_fields(shell_doc),
                    }
                )
            )
            continue
        harnesses.append(_build_target_group_adapter_execution_harness(shell_doc, pack_doc, candidates[0]))

    harnesses_doc = redact_sensitive_fields(
        {
            "schema_version": TARGET_GROUP_ADAPTER_EXECUTION_HARNESSES_SCHEMA_VERSION,
            "harness_count": len(harnesses),
            "harnesses": harnesses,
            "generated_at": utcnow_iso(),
        }
    )
    review_queue = redact_sensitive_fields(
        {
            "schema_version": TARGET_GROUP_ADAPTER_EXECUTION_HARNESS_REVIEW_QUEUE_SCHEMA_VERSION,
            "item_count": len(review_items),
            "items": review_items,
            "generated_at": utcnow_iso(),
        }
    )
    group_counts: dict[str, int] = {}
    mode_counts: dict[str, int] = {}
    for item in harnesses:
        group = item.get("harness_group") if isinstance(item.get("harness_group"), dict) else {}
        key = _normalize_text(group.get("harness_group_key")) or "unknown"
        group_counts[key] = group_counts.get(key, 0) + 1
        for mode in item.get("pack_summary", {}).get("fixture_modes") or [] if isinstance(item.get("pack_summary"), dict) else []:
            mode_key = _normalize_text(mode) or "unknown"
            mode_counts[mode_key] = mode_counts.get(mode_key, 0) + 1
    rollup = redact_sensitive_fields(
        {
            "schema_version": TARGET_GROUP_ADAPTER_EXECUTION_HARNESS_ROLLUP_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "harness_count": len(harnesses),
            "review_queue_count": len(review_items),
            "harness_group_counts": group_counts,
            "fixture_mode_counts": mode_counts,
        }
    )
    return harnesses_doc, review_queue, rollup


def build_replayable_dry_run_orchestration_pack_artifacts(harnesses_doc: dict, packs_doc: dict) -> tuple[dict, dict, dict]:
    pack_index = _pack_index(packs_doc)
    packs: list[dict] = []
    review_items: list[dict] = []

    for harness_doc in harnesses_doc.get("harnesses") or []:
        if not isinstance(harness_doc, dict):
            continue
        shell_id = _normalize_text(harness_doc.get("target_group_adapter_implementation_shell_id"))
        pack_doc = pack_index.get(shell_id or "")
        if not pack_doc or not pack_doc.get("cases"):
            review_items.append(
                redact_sensitive_fields(
                    {
                        "schema_version": REPLAYABLE_DRY_RUN_ORCHESTRATION_REVIEW_QUEUE_SCHEMA_VERSION,
                        "queue_item_id": _orchestration_review_item_id(harness_doc),
                        "state": "open",
                        "priority": "medium",
                        "review_type": "replayable-dry-run-orchestration-pack",
                        "target_group_adapter_execution_harness_id": harness_doc.get("target_group_adapter_execution_harness_id"),
                        "reason_codes": ["no_fixture_cases_for_harness"],
                        "harness_summary": redact_sensitive_fields(harness_doc),
                    }
                )
            )
            continue
        packs.append(_build_replayable_dry_run_orchestration_pack(harness_doc, pack_doc))

    packs_doc = redact_sensitive_fields(
        {
            "schema_version": REPLAYABLE_DRY_RUN_ORCHESTRATION_PACKS_SCHEMA_VERSION,
            "pack_count": len(packs),
            "packs": packs,
            "generated_at": utcnow_iso(),
        }
    )
    review_queue = redact_sensitive_fields(
        {
            "schema_version": REPLAYABLE_DRY_RUN_ORCHESTRATION_REVIEW_QUEUE_SCHEMA_VERSION,
            "item_count": len(review_items),
            "items": review_items,
            "generated_at": utcnow_iso(),
        }
    )
    fixture_mode_counts: dict[str, int] = {}
    for pack in packs:
        for step in pack.get("steps") or []:
            if not isinstance(step, dict):
                continue
            mode = _normalize_text(step.get("fixture_mode")) or "unknown"
            fixture_mode_counts[mode] = fixture_mode_counts.get(mode, 0) + 1
    rollup = redact_sensitive_fields(
        {
            "schema_version": REPLAYABLE_DRY_RUN_ORCHESTRATION_ROLLUP_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "pack_count": len(packs),
            "review_queue_count": len(review_items),
            "fixture_mode_counts": fixture_mode_counts,
        }
    )
    return packs_doc, review_queue, rollup


def render_target_group_adapter_execution_harnesses_markdown(harnesses_doc: dict) -> str:
    lines = ["# Target-Group Adapter Execution Harnesses", ""]
    lines.append(f"Harness count: {harnesses_doc.get('harness_count', 0)}")
    lines.append("")
    for item in harnesses_doc.get("harnesses") or []:
        if not isinstance(item, dict):
            continue
        group = item.get("harness_group") if isinstance(item.get("harness_group"), dict) else {}
        lines.append(f"- `{item.get('target_group_adapter_execution_harness_id')}` :: {group.get('harness_group_key')}")
    return "\n".join(lines) + "\n"


def render_target_group_adapter_execution_harness_review_queue_markdown(review_queue: dict) -> str:
    lines = ["# Target-Group Adapter Execution Harness Review Queue", ""]
    lines.append(f"Open items: {review_queue.get('item_count', 0)}")
    lines.append("")
    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('queue_item_id')}` :: {', '.join(item.get('reason_codes') or [])}")
    return "\n".join(lines) + "\n"


def render_target_group_adapter_execution_harness_rollup_markdown(rollup: dict) -> str:
    lines = ["# Target-Group Adapter Execution Harness Rollup", ""]
    lines.append(f"Harness count: {rollup.get('harness_count', 0)}")
    lines.append(f"Review queue count: {rollup.get('review_queue_count', 0)}")
    return "\n".join(lines) + "\n"


def render_replayable_dry_run_orchestration_packs_markdown(packs_doc: dict) -> str:
    lines = ["# Replayable Dry-Run Orchestration Packs", ""]
    lines.append(f"Pack count: {packs_doc.get('pack_count', 0)}")
    lines.append("")
    for item in packs_doc.get("packs") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('replayable_dry_run_orchestration_pack_id')}` :: steps={len(item.get('steps') or [])}")
    return "\n".join(lines) + "\n"


def render_replayable_dry_run_orchestration_review_queue_markdown(review_queue: dict) -> str:
    lines = ["# Replayable Dry-Run Orchestration Review Queue", ""]
    lines.append(f"Open items: {review_queue.get('item_count', 0)}")
    lines.append("")
    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('queue_item_id')}` :: {', '.join(item.get('reason_codes') or [])}")
    return "\n".join(lines) + "\n"


def render_replayable_dry_run_orchestration_rollup_markdown(rollup: dict) -> str:
    lines = ["# Replayable Dry-Run Orchestration Rollup", ""]
    lines.append(f"Pack count: {rollup.get('pack_count', 0)}")
    lines.append(f"Review queue count: {rollup.get('review_queue_count', 0)}")
    return "\n".join(lines) + "\n"
