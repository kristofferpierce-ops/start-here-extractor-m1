from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .ingestion import utcnow_iso
from .security import redact_sensitive_fields

TARGET_FAMILY_RUNNER_STUBS_SCHEMA_VERSION = "1.0"
TARGET_FAMILY_RUNNER_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
TARGET_FAMILY_RUNNER_ROLLUP_SCHEMA_VERSION = "1.0"
TARGET_FAMILY_COLLECTOR_FIXTURES_SCHEMA_VERSION = "1.0"
TARGET_FAMILY_COLLECTOR_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
TARGET_FAMILY_COLLECTOR_ROLLUP_SCHEMA_VERSION = "1.0"

DEFAULT_FIXTURE_STATUSES = ["success", "failure", "defer", "skip"]
_ALLOWED_FIXTURE_STATUSES = {"success", "failure", "defer", "skip"}


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


def _normalize_fixture_statuses(value: object) -> list[str]:
    raw = _normalize_str_list(value)
    statuses = [item for item in raw if item in _ALLOWED_FIXTURE_STATUSES]
    return statuses or list(DEFAULT_FIXTURE_STATUSES)


def normalize_target_family_catalog(value: object) -> list[dict]:
    if isinstance(value, dict):
        entries = value.get("target_families") if isinstance(value.get("target_families"), list) else []
    elif isinstance(value, list):
        entries = value
    else:
        entries = []

    normalized: list[dict] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        target_family_key = _normalize_text(item.get("target_family_key"))
        if not target_family_key:
            continue
        normalized.append(
            redact_sensitive_fields(
                {
                    "target_family_key": target_family_key,
                    "target_family_name": _normalize_text(item.get("target_family_name")) or target_family_key,
                    "runner_stub_family": _normalize_text(item.get("runner_stub_family")) or "target-runner-stub",
                    "stub_version": _normalize_text(item.get("stub_version")) or "1.0",
                    "fixture_family_key": _normalize_text(item.get("fixture_family_key")) or target_family_key,
                    "request_template_kind": _normalize_text(item.get("request_template_kind")) or "target-runner-request-v1",
                    "normalized_outcome_kind": _normalize_text(item.get("normalized_outcome_kind")) or "normalized-external-runner-outcome-v1",
                    "supported_interface_keys": _normalize_str_list(item.get("supported_interface_keys")),
                    "supported_target_systems": _normalize_str_list(item.get("supported_target_systems")),
                    "supported_target_types": _normalize_str_list(item.get("supported_target_types")),
                    "supported_adapter_families": _normalize_str_list(item.get("supported_adapter_families")),
                    "supported_runner_families": _normalize_str_list(item.get("supported_runner_families")),
                    "supported_operations": _normalize_str_list(item.get("supported_operations")),
                    "supported_normalizer_keys": _normalize_str_list(item.get("supported_normalizer_keys")),
                    "default_fixture_statuses": _normalize_fixture_statuses(item.get("default_fixture_statuses")),
                    "active": _normalize_bool(item.get("active"), default=True),
                }
            )
        )
    normalized.sort(key=lambda item: str(item.get("target_family_key") or ""))
    return normalized


def load_target_family_catalog(path: str | Path) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    payload = json.loads(target.read_text(encoding="utf-8"))
    return normalize_target_family_catalog(payload)


def load_target_family_runner_stubs(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Target family runner stubs payload must be a JSON object")


def _compatible_target_family(contract: dict, family: dict) -> bool:
    if not _normalize_bool(family.get("active"), default=True):
        return False
    interface = contract.get("interface") if isinstance(contract.get("interface"), dict) else {}
    runner = contract.get("runner") if isinstance(contract.get("runner"), dict) else {}
    target = contract.get("target") if isinstance(contract.get("target"), dict) else {}
    adapter = contract.get("adapter") if isinstance(contract.get("adapter"), dict) else {}
    collector_contract = contract.get("collector_contract") if isinstance(contract.get("collector_contract"), dict) else {}

    interface_key = _normalize_text(interface.get("interface_key"))
    target_system = _normalize_text(target.get("target_system"))
    target_type = _normalize_text(target.get("target_type"))
    adapter_family = _normalize_text(adapter.get("adapter_family"))
    runner_family = _normalize_text(runner.get("runner_family")) or _normalize_text(runner.get("runner_key"))
    dispatch_stub = contract.get("dispatch_stub") if isinstance(contract.get("dispatch_stub"), dict) else {}
    dispatch_payload = dispatch_stub.get("payload") if isinstance(dispatch_stub.get("payload"), dict) else {}
    operation = _normalize_text(contract.get("operation")) or _normalize_text(dispatch_payload.get("operation"))
    normalizer_key = _normalize_text(collector_contract.get("normalizer_key")) or _normalize_text(interface.get("normalizer_key"))

    supported_interface_keys = family.get("supported_interface_keys") if isinstance(family.get("supported_interface_keys"), list) else []
    supported_target_systems = family.get("supported_target_systems") if isinstance(family.get("supported_target_systems"), list) else []
    supported_target_types = family.get("supported_target_types") if isinstance(family.get("supported_target_types"), list) else []
    supported_adapter_families = family.get("supported_adapter_families") if isinstance(family.get("supported_adapter_families"), list) else []
    supported_runner_families = family.get("supported_runner_families") if isinstance(family.get("supported_runner_families"), list) else []
    supported_operations = family.get("supported_operations") if isinstance(family.get("supported_operations"), list) else []
    supported_normalizer_keys = family.get("supported_normalizer_keys") if isinstance(family.get("supported_normalizer_keys"), list) else []

    if supported_interface_keys and interface_key not in supported_interface_keys:
        return False
    if supported_target_systems and target_system not in supported_target_systems:
        return False
    if supported_target_types and target_type not in supported_target_types:
        return False
    if supported_adapter_families and adapter_family not in supported_adapter_families:
        return False
    if supported_runner_families and runner_family not in supported_runner_families:
        return False
    if supported_operations and operation not in supported_operations:
        return False
    if supported_normalizer_keys and normalizer_key not in supported_normalizer_keys:
        return False
    return True


def _target_family_candidates(contract: dict, catalog: list[dict]) -> list[dict]:
    return [redact_sensitive_fields(dict(item)) for item in catalog if _compatible_target_family(contract, item)]


def derive_target_runner_stub_id(contract: dict, family: dict) -> str:
    payload = {
        "interface_contract_id": _normalize_text(contract.get("interface_contract_id")),
        "target_family_key": _normalize_text(family.get("target_family_key")),
        "fixture_family_key": _normalize_text(family.get("fixture_family_key")),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"target-runner-{digest[:24]}"


def _target_stub_ref(target_runner_stub_id: str) -> str:
    return f"target-runner://{target_runner_stub_id}"


def _target_family_review_item_id(contract: dict) -> str:
    interface_contract_id = _normalize_text(contract.get("interface_contract_id")) or "unknown"
    digest = hashlib.sha256(f"target-family:{interface_contract_id}".encode("utf-8")).hexdigest()
    return f"target-family-review-{digest[:24]}"


def _collector_fixture_review_item_id(stub: dict) -> str:
    target_runner_stub_id = _normalize_text(stub.get("target_runner_stub_id")) or "unknown"
    digest = hashlib.sha256(f"collector-fixture:{target_runner_stub_id}".encode("utf-8")).hexdigest()
    return f"collector-fixture-review-{digest[:24]}"


def _fixture_ref(fixture_id: str) -> str:
    return f"collector-fixture://{fixture_id}"


def _status_code(status: str) -> str:
    return {
        "success": "200",
        "failure": "500",
        "defer": "202",
        "skip": "204",
    }.get(status, "200")


def _status_reason(status: str, family_name: str) -> str:
    return {
        "success": f"{family_name} fixture success outcome",
        "failure": f"{family_name} fixture failure outcome",
        "defer": f"{family_name} fixture deferred outcome",
        "skip": f"{family_name} fixture skipped outcome",
    }.get(status, f"{family_name} fixture outcome")


def _build_target_runner_stub(contract: dict, family: dict) -> dict:
    target_runner_stub_id = derive_target_runner_stub_id(contract, family)
    interface = contract.get("interface") if isinstance(contract.get("interface"), dict) else {}
    runner = contract.get("runner") if isinstance(contract.get("runner"), dict) else {}
    target = contract.get("target") if isinstance(contract.get("target"), dict) else {}
    adapter = contract.get("adapter") if isinstance(contract.get("adapter"), dict) else {}
    collector_contract = contract.get("collector_contract") if isinstance(contract.get("collector_contract"), dict) else {}
    dispatch_stub = contract.get("dispatch_stub") if isinstance(contract.get("dispatch_stub"), dict) else {}
    dispatch_payload = dispatch_stub.get("payload") if isinstance(dispatch_stub.get("payload"), dict) else {}

    return redact_sensitive_fields(
        {
            "schema_version": TARGET_FAMILY_RUNNER_STUBS_SCHEMA_VERSION,
            "target_runner_stub_id": target_runner_stub_id,
            "target_runner_stub_ref": _target_stub_ref(target_runner_stub_id),
            "state": "stubbed",
            "interface_contract_id": contract.get("interface_contract_id"),
            "runner_job_id": contract.get("runner_job_id"),
            "contract_id": contract.get("contract_id"),
            "event_id": contract.get("event_id"),
            "outcome_collection_key": contract.get("outcome_collection_key"),
            "target_family": {
                "target_family_key": family.get("target_family_key"),
                "target_family_name": family.get("target_family_name"),
                "runner_stub_family": family.get("runner_stub_family"),
                "stub_version": family.get("stub_version"),
                "fixture_family_key": family.get("fixture_family_key"),
            },
            "runner": runner,
            "adapter": adapter,
            "target": target,
            "interface": {
                "interface_key": interface.get("interface_key"),
                "interface_family": interface.get("interface_family"),
                "interface_version": interface.get("interface_version"),
                "normalizer_key": collector_contract.get("normalizer_key") or interface.get("normalizer_key"),
                "result_contract_kind": interface.get("result_contract_kind"),
            },
            "request_stub": {
                "template_kind": family.get("request_template_kind"),
                "dispatch_ref": dispatch_stub.get("dispatch_ref"),
                "transport": dispatch_stub.get("transport"),
                "canonical_request": {
                    "runner_job_id": contract.get("runner_job_id"),
                    "interface_contract_id": contract.get("interface_contract_id"),
                    "contract_id": contract.get("contract_id"),
                    "event_id": contract.get("event_id"),
                    "operation": contract.get("operation") or dispatch_payload.get("operation"),
                    "target_family_key": family.get("target_family_key"),
                    "target_system": target.get("target_system"),
                    "target_type": target.get("target_type"),
                    "target_key": target.get("target_key"),
                    "target_id": target.get("target_id"),
                    "adapter_key": adapter.get("adapter_key"),
                    "adapter_family": adapter.get("adapter_family"),
                    "normalizer_key": collector_contract.get("normalizer_key") or interface.get("normalizer_key"),
                    "outcome_collection_key": contract.get("outcome_collection_key"),
                },
            },
            "fixture_plan": {
                "fixture_family_key": family.get("fixture_family_key"),
                "normalized_outcome_kind": family.get("normalized_outcome_kind"),
                "default_statuses": family.get("default_fixture_statuses") or list(DEFAULT_FIXTURE_STATUSES),
            },
        }
    )


def build_target_family_runner_stub_artifacts(interface_contracts_doc: dict, target_family_catalog: list[dict]) -> tuple[dict, dict, dict]:
    stubs: list[dict] = []
    review_items: list[dict] = []

    for contract in interface_contracts_doc.get("contracts") or []:
        if not isinstance(contract, dict):
            continue
        candidates = _target_family_candidates(contract, target_family_catalog)
        reason_codes = ["interface_contract_ready_for_target_family"]
        if not candidates:
            reason_codes.append("no_target_family_match")
        elif len(candidates) > 1:
            reason_codes.append("multiple_target_family_matches")

        if len(candidates) == 1:
            stubs.append(_build_target_runner_stub(contract, candidates[0]))
            continue

        target = contract.get("target") if isinstance(contract.get("target"), dict) else {}
        adapter = contract.get("adapter") if isinstance(contract.get("adapter"), dict) else {}
        interface = contract.get("interface") if isinstance(contract.get("interface"), dict) else {}
        review_items.append(
            redact_sensitive_fields(
                {
                    "schema_version": TARGET_FAMILY_RUNNER_REVIEW_QUEUE_SCHEMA_VERSION,
                    "queue_item_id": _target_family_review_item_id(contract),
                    "state": "open",
                    "priority": "high",
                    "review_type": "target-family-routing",
                    "interface_contract_id": contract.get("interface_contract_id"),
                    "runner_job_id": contract.get("runner_job_id"),
                    "contract_id": contract.get("contract_id"),
                    "event_id": contract.get("event_id"),
                    "reason_codes": reason_codes,
                    "interface": {
                        "interface_key": interface.get("interface_key"),
                        "interface_family": interface.get("interface_family"),
                        "normalizer_key": interface.get("normalizer_key"),
                    },
                    "adapter": {
                        "adapter_key": adapter.get("adapter_key"),
                        "adapter_family": adapter.get("adapter_family"),
                        "operation": contract.get("operation"),
                    },
                    "target": {
                        "target_key": target.get("target_key"),
                        "target_system": target.get("target_system"),
                        "target_type": target.get("target_type"),
                    },
                    "candidate_target_families": [
                        {
                            "target_family_key": item.get("target_family_key"),
                            "target_family_name": item.get("target_family_name"),
                            "fixture_family_key": item.get("fixture_family_key"),
                        }
                        for item in candidates
                    ],
                }
            )
        )

    stubs_doc = {
        "schema_version": TARGET_FAMILY_RUNNER_STUBS_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "stub_count": len(stubs),
        "stubs": sorted(stubs, key=lambda item: str(item.get("target_runner_stub_id") or "")),
    }
    review_queue = {
        "schema_version": TARGET_FAMILY_RUNNER_REVIEW_QUEUE_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "item_count": len(review_items),
        "items": sorted(review_items, key=lambda item: str(item.get("queue_item_id") or "")),
    }
    rollup = build_target_family_runner_rollup(stubs_doc, review_queue)
    return redact_sensitive_fields(stubs_doc), redact_sensitive_fields(review_queue), redact_sensitive_fields(rollup)


def build_target_family_runner_rollup(stubs_doc: dict, review_queue: dict) -> dict:
    family_counts: dict[str, int] = {}
    fixture_family_counts: dict[str, int] = {}
    target_system_counts: dict[str, int] = {}
    review_reason_counts: dict[str, int] = {}

    for stub in stubs_doc.get("stubs") or []:
        if not isinstance(stub, dict):
            continue
        family = stub.get("target_family") if isinstance(stub.get("target_family"), dict) else {}
        target = stub.get("target") if isinstance(stub.get("target"), dict) else {}
        family_key = _normalize_text(family.get("target_family_key")) or "unknown"
        fixture_family_key = _normalize_text(family.get("fixture_family_key")) or "unknown"
        target_system = _normalize_text(target.get("target_system")) or "unknown"
        family_counts[family_key] = family_counts.get(family_key, 0) + 1
        fixture_family_counts[fixture_family_key] = fixture_family_counts.get(fixture_family_key, 0) + 1
        target_system_counts[target_system] = target_system_counts.get(target_system, 0) + 1

    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        for reason in item.get("reason_codes") or []:
            normalized = _normalize_text(reason)
            if normalized:
                review_reason_counts[normalized] = review_reason_counts.get(normalized, 0) + 1

    return {
        "schema_version": TARGET_FAMILY_RUNNER_ROLLUP_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "stub_count": int(stubs_doc.get("stub_count") or 0),
        "review_queue_count": int(review_queue.get("item_count") or 0),
        "target_family_counts": family_counts,
        "fixture_family_counts": fixture_family_counts,
        "target_system_counts": target_system_counts,
        "review_reason_counts": review_reason_counts,
    }


def derive_target_family_fixture_id(stub: dict, outcome_status: str) -> str:
    payload = {
        "target_runner_stub_id": _normalize_text(stub.get("target_runner_stub_id")),
        "outcome_status": outcome_status,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"collector-fixture-{digest[:24]}"


def _build_collector_fixture(stub: dict, outcome_status: str) -> dict:
    target_family = stub.get("target_family") if isinstance(stub.get("target_family"), dict) else {}
    interface = stub.get("interface") if isinstance(stub.get("interface"), dict) else {}
    fixture_plan = stub.get("fixture_plan") if isinstance(stub.get("fixture_plan"), dict) else {}
    fixture_id = derive_target_family_fixture_id(stub, outcome_status)
    target_family_name = _normalize_text(target_family.get("target_family_name")) or "target-family"
    return redact_sensitive_fields(
        {
            "schema_version": TARGET_FAMILY_COLLECTOR_FIXTURES_SCHEMA_VERSION,
            "fixture_id": fixture_id,
            "fixture_ref": _fixture_ref(fixture_id),
            "state": "fixture_defined",
            "target_runner_stub_id": stub.get("target_runner_stub_id"),
            "interface_contract_id": stub.get("interface_contract_id"),
            "runner_job_id": stub.get("runner_job_id"),
            "contract_id": stub.get("contract_id"),
            "event_id": stub.get("event_id"),
            "target_family_key": target_family.get("target_family_key"),
            "fixture_family_key": fixture_plan.get("fixture_family_key"),
            "normalized_outcome_kind": fixture_plan.get("normalized_outcome_kind"),
            "outcome_status": outcome_status,
            "canonical_fixture": {
                "runner_job_id": stub.get("runner_job_id"),
                "outcome_collection_key": stub.get("outcome_collection_key"),
                "contract_id": stub.get("contract_id"),
                "interface_contract_id": stub.get("interface_contract_id"),
                "outcome_status": outcome_status,
                "executed_by": f"fixture-{target_family.get('target_family_key')}",
                "executed_at": utcnow_iso(),
                "reason": _status_reason(outcome_status, target_family_name),
                "external_ref": f"{target_family.get('target_family_key')}-{outcome_status}-{fixture_id[-6:]}",
                "status_code": _status_code(outcome_status),
                "collector_ref": _fixture_ref(fixture_id),
                "normalizer_key": interface.get("normalizer_key"),
                "target_family_key": target_family.get("target_family_key"),
                "fixture_family_key": fixture_plan.get("fixture_family_key"),
            },
        }
    )


def build_target_family_collector_fixture_artifacts(stubs_doc: dict) -> tuple[dict, dict, dict]:
    fixtures: list[dict] = []
    review_items: list[dict] = []

    for stub in stubs_doc.get("stubs") or []:
        if not isinstance(stub, dict):
            continue
        fixture_plan = stub.get("fixture_plan") if isinstance(stub.get("fixture_plan"), dict) else {}
        statuses = fixture_plan.get("default_statuses") if isinstance(fixture_plan.get("default_statuses"), list) else []
        normalized_statuses = [status for status in statuses if _normalize_text(status) in _ALLOWED_FIXTURE_STATUSES]
        if not normalized_statuses:
            normalized_statuses = list(DEFAULT_FIXTURE_STATUSES)
        for status in normalized_statuses:
            fixtures.append(_build_collector_fixture(stub, status))

    fixtures_doc = {
        "schema_version": TARGET_FAMILY_COLLECTOR_FIXTURES_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "fixture_count": len(fixtures),
        "fixtures": sorted(fixtures, key=lambda item: str(item.get("fixture_id") or "")),
    }
    review_queue = {
        "schema_version": TARGET_FAMILY_COLLECTOR_REVIEW_QUEUE_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "item_count": len(review_items),
        "items": sorted(review_items, key=lambda item: str(item.get("queue_item_id") or "")),
    }
    rollup = build_target_family_collector_rollup(fixtures_doc, review_queue)
    return redact_sensitive_fields(fixtures_doc), redact_sensitive_fields(review_queue), redact_sensitive_fields(rollup)


def build_target_family_collector_rollup(fixtures_doc: dict, review_queue: dict) -> dict:
    fixture_family_counts: dict[str, int] = {}
    outcome_status_counts: dict[str, int] = {}
    target_family_counts: dict[str, int] = {}
    review_reason_counts: dict[str, int] = {}

    for fixture in fixtures_doc.get("fixtures") or []:
        if not isinstance(fixture, dict):
            continue
        fixture_family_key = _normalize_text(fixture.get("fixture_family_key")) or "unknown"
        outcome_status = _normalize_text(fixture.get("outcome_status")) or "unknown"
        target_family_key = _normalize_text(fixture.get("target_family_key")) or "unknown"
        fixture_family_counts[fixture_family_key] = fixture_family_counts.get(fixture_family_key, 0) + 1
        outcome_status_counts[outcome_status] = outcome_status_counts.get(outcome_status, 0) + 1
        target_family_counts[target_family_key] = target_family_counts.get(target_family_key, 0) + 1

    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        for reason in item.get("reason_codes") or []:
            normalized = _normalize_text(reason)
            if normalized:
                review_reason_counts[normalized] = review_reason_counts.get(normalized, 0) + 1

    return {
        "schema_version": TARGET_FAMILY_COLLECTOR_ROLLUP_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "fixture_count": int(fixtures_doc.get("fixture_count") or 0),
        "review_queue_count": int(review_queue.get("item_count") or 0),
        "fixture_family_counts": fixture_family_counts,
        "outcome_status_counts": outcome_status_counts,
        "target_family_counts": target_family_counts,
        "review_reason_counts": review_reason_counts,
    }


def render_target_family_runner_stubs_markdown(stubs_doc: dict) -> str:
    lines = ["# Target family runner stubs", ""]
    lines.append(f"Stub count: {int(stubs_doc.get('stub_count') or 0)}")
    for stub in stubs_doc.get("stubs") or []:
        if not isinstance(stub, dict):
            continue
        target_family = stub.get("target_family") if isinstance(stub.get("target_family"), dict) else {}
        lines.extend(
            [
                "",
                f"## {stub.get('target_runner_stub_id')}",
                f"- interface_contract_id: {stub.get('interface_contract_id')}",
                f"- target_family_key: {target_family.get('target_family_key')}",
                f"- fixture_family_key: {target_family.get('fixture_family_key')}",
                f"- runner_job_id: {stub.get('runner_job_id')}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_target_family_runner_review_queue_markdown(review_queue: dict) -> str:
    lines = ["# Target family runner review queue", ""]
    lines.append(f"Open items: {int(review_queue.get('item_count') or 0)}")
    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                "",
                f"## {item.get('queue_item_id')}",
                f"- interface_contract_id: {item.get('interface_contract_id')}",
                f"- reason_codes: {', '.join(item.get('reason_codes') or [])}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_target_family_runner_rollup_markdown(rollup: dict) -> str:
    lines = ["# Target family runner rollup", ""]
    lines.append(f"Stub count: {int(rollup.get('stub_count') or 0)}")
    lines.append(f"Review queue count: {int(rollup.get('review_queue_count') or 0)}")
    for key, value in sorted((rollup.get("target_family_counts") or {}).items()):
        lines.append(f"- target_family_counts[{key}] = {value}")
    return "\n".join(lines).rstrip() + "\n"


def render_target_family_collector_fixtures_markdown(fixtures_doc: dict) -> str:
    lines = ["# Target family collector fixtures", ""]
    lines.append(f"Fixture count: {int(fixtures_doc.get('fixture_count') or 0)}")
    for fixture in fixtures_doc.get("fixtures") or []:
        if not isinstance(fixture, dict):
            continue
        lines.extend(
            [
                "",
                f"## {fixture.get('fixture_id')}",
                f"- target_runner_stub_id: {fixture.get('target_runner_stub_id')}",
                f"- outcome_status: {fixture.get('outcome_status')}",
                f"- fixture_family_key: {fixture.get('fixture_family_key')}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_target_family_collector_review_queue_markdown(review_queue: dict) -> str:
    lines = ["# Target family collector fixture review queue", ""]
    lines.append(f"Open items: {int(review_queue.get('item_count') or 0)}")
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
    return "\n".join(lines).rstrip() + "\n"


def render_target_family_collector_rollup_markdown(rollup: dict) -> str:
    lines = ["# Target family collector fixture rollup", ""]
    lines.append(f"Fixture count: {int(rollup.get('fixture_count') or 0)}")
    lines.append(f"Review queue count: {int(rollup.get('review_queue_count') or 0)}")
    for key, value in sorted((rollup.get("outcome_status_counts") or {}).items()):
        lines.append(f"- outcome_status_counts[{key}] = {value}")
    return "\n".join(lines).rstrip() + "\n"
