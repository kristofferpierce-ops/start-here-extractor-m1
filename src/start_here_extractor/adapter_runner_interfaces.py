from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .ingestion import utcnow_iso
from .security import redact_sensitive_fields

ADAPTER_RUNNER_INTERFACE_CONTRACTS_SCHEMA_VERSION = "1.0"
ADAPTER_RUNNER_INTERFACE_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
ADAPTER_RUNNER_INTERFACE_ROLLUP_SCHEMA_VERSION = "1.0"
NORMALIZED_EXTERNAL_OUTCOMES_SCHEMA_VERSION = "1.0"
COLLECTOR_NORMALIZATION_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
COLLECTOR_NORMALIZATION_ROLLUP_SCHEMA_VERSION = "1.0"

SUCCESS_STATUSES = {"success", "succeeded", "ok", "completed", "complete"}
FAILURE_STATUSES = {"failure", "failed", "error", "errored"}
DEFERRED_STATUSES = {"defer", "deferred", "pending", "retry", "retryable"}
SKIPPED_STATUSES = {"skip", "skipped"}


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


def _normalize_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, item in value.items():
        normalized_key = _normalize_text(key)
        normalized_value = _normalize_text(item)
        if normalized_key and normalized_value:
            normalized[normalized_key] = normalized_value
    return normalized


def normalize_runner_interface_catalog(value: object) -> list[dict]:
    if isinstance(value, dict):
        entries = value.get("interfaces") if isinstance(value.get("interfaces"), list) else []
    elif isinstance(value, list):
        entries = value
    else:
        entries = []

    normalized: list[dict] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        interface_key = _normalize_text(item.get("interface_key"))
        if not interface_key:
            continue
        normalized.append(
            redact_sensitive_fields(
                {
                    "interface_key": interface_key,
                    "interface_family": _normalize_text(item.get("interface_family")) or "runner-interface",
                    "interface_version": _normalize_text(item.get("interface_version")) or "1.0",
                    "outbound_contract_kind": _normalize_text(item.get("outbound_contract_kind")) or "runner-job-envelope-v1",
                    "result_contract_kind": _normalize_text(item.get("result_contract_kind")) or "runner-json-envelope-v1",
                    "normalizer_key": _normalize_text(item.get("normalizer_key")) or "json-envelope-v1",
                    "supported_runner_families": _normalize_str_list(item.get("supported_runner_families")),
                    "supported_dispatch_transports": _normalize_str_list(item.get("supported_dispatch_transports")),
                    "supported_stub_kinds": _normalize_str_list(item.get("supported_stub_kinds")),
                    "supported_target_systems": _normalize_str_list(item.get("supported_target_systems")),
                    "supported_adapter_families": _normalize_str_list(item.get("supported_adapter_families")),
                    "supported_operations": _normalize_str_list(item.get("supported_operations")),
                    "status_aliases": _normalize_mapping(item.get("status_aliases")),
                    "active": _normalize_bool(item.get("active"), default=True),
                }
            )
        )
    normalized.sort(key=lambda item: str(item.get("interface_key") or ""))
    return normalized


def load_runner_interface_catalog(path: str | Path) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    payload = json.loads(target.read_text(encoding="utf-8"))
    return normalize_runner_interface_catalog(payload)


def load_runner_interface_contracts(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Runner interface contracts payload must be a JSON object")


def load_raw_external_runner_payloads(path: str | Path) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        if isinstance(payload.get("payloads"), list):
            return [redact_sensitive_fields(item) for item in payload["payloads"] if isinstance(item, dict)]
        if isinstance(payload.get("outcomes"), list):
            return [redact_sensitive_fields(item) for item in payload["outcomes"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [redact_sensitive_fields(item) for item in payload if isinstance(item, dict)]
    raise ValueError("Raw external runner payloads must be a JSON object with payloads/outcomes or a JSON list")


def _compatible_runner_job(job: dict, interface: dict) -> bool:
    if not _normalize_bool(interface.get("active"), default=True):
        return False
    runner = job.get("runner") if isinstance(job.get("runner"), dict) else {}
    adapter = job.get("adapter") if isinstance(job.get("adapter"), dict) else {}
    target = job.get("target") if isinstance(job.get("target"), dict) else {}
    dispatch_stub = job.get("dispatch_stub") if isinstance(job.get("dispatch_stub"), dict) else {}

    runner_family = _normalize_text(runner.get("runner_family"))
    dispatch_transport = _normalize_text(runner.get("dispatch_transport"))
    stub_kind = _normalize_text(dispatch_stub.get("stub_kind"))
    target_system = _normalize_text(target.get("target_system"))
    adapter_family = _normalize_text(adapter.get("adapter_family"))
    operation = _normalize_text(job.get("operation"))

    supported_runner_families = interface.get("supported_runner_families") if isinstance(interface.get("supported_runner_families"), list) else []
    supported_dispatch_transports = interface.get("supported_dispatch_transports") if isinstance(interface.get("supported_dispatch_transports"), list) else []
    supported_stub_kinds = interface.get("supported_stub_kinds") if isinstance(interface.get("supported_stub_kinds"), list) else []
    supported_target_systems = interface.get("supported_target_systems") if isinstance(interface.get("supported_target_systems"), list) else []
    supported_adapter_families = interface.get("supported_adapter_families") if isinstance(interface.get("supported_adapter_families"), list) else []
    supported_operations = interface.get("supported_operations") if isinstance(interface.get("supported_operations"), list) else []

    if supported_runner_families and runner_family not in supported_runner_families:
        return False
    if supported_dispatch_transports and dispatch_transport not in supported_dispatch_transports:
        return False
    if supported_stub_kinds and stub_kind not in supported_stub_kinds:
        return False
    if supported_target_systems and target_system not in supported_target_systems:
        return False
    if supported_adapter_families and adapter_family not in supported_adapter_families:
        return False
    if supported_operations and operation not in supported_operations:
        return False
    return True


def _runner_interface_candidates(job: dict, interface_catalog: list[dict]) -> list[dict]:
    return [redact_sensitive_fields(dict(item)) for item in interface_catalog if _compatible_runner_job(job, item)]


def derive_runner_interface_contract_id(job: dict, interface: dict) -> str:
    payload = {
        "runner_job_id": _normalize_text(job.get("runner_job_id")),
        "interface_key": _normalize_text(interface.get("interface_key")),
        "result_contract_kind": _normalize_text(interface.get("result_contract_kind")),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"runner-iface-{digest[:24]}"


def _runner_interface_review_item_id(job: dict) -> str:
    runner_job_id = _normalize_text(job.get("runner_job_id")) or "unknown"
    digest = hashlib.sha256(f"runner-iface:{runner_job_id}".encode("utf-8")).hexdigest()
    return f"runner-iface-review-{digest[:24]}"


def _collector_review_item_id(payload: dict) -> str:
    ref = (
        _normalize_text(payload.get("runner_job_id"))
        or _normalize_text(payload.get("job_id"))
        or _normalize_text(payload.get("outcome_collection_key"))
        or _normalize_text(payload.get("contract_id"))
        or json.dumps(payload, sort_keys=True, separators=(",", ":"))
    )
    digest = hashlib.sha256(f"collector:{ref}".encode("utf-8")).hexdigest()
    return f"collector-review-{digest[:24]}"


def _interface_ref(interface_contract_id: str) -> str:
    return f"adapter-runner-interface://{interface_contract_id}"


def _build_interface_contract(job: dict, interface: dict) -> dict:
    interface_contract_id = derive_runner_interface_contract_id(job, interface)
    runner = job.get("runner") if isinstance(job.get("runner"), dict) else {}
    adapter = job.get("adapter") if isinstance(job.get("adapter"), dict) else {}
    target = job.get("target") if isinstance(job.get("target"), dict) else {}
    dispatch_stub = job.get("dispatch_stub") if isinstance(job.get("dispatch_stub"), dict) else {}

    return redact_sensitive_fields(
        {
            "schema_version": ADAPTER_RUNNER_INTERFACE_CONTRACTS_SCHEMA_VERSION,
            "interface_contract_id": interface_contract_id,
            "interface_ref": _interface_ref(interface_contract_id),
            "state": "stubbed",
            "runner_job_id": job.get("runner_job_id"),
            "contract_id": job.get("contract_id"),
            "event_id": job.get("event_id"),
            "outcome_collection_key": job.get("outcome_collection_key"),
            "runner": runner,
            "adapter": adapter,
            "target": target,
            "interface": {
                "interface_key": interface.get("interface_key"),
                "interface_family": interface.get("interface_family"),
                "interface_version": interface.get("interface_version"),
                "outbound_contract_kind": interface.get("outbound_contract_kind"),
                "result_contract_kind": interface.get("result_contract_kind"),
                "normalizer_key": interface.get("normalizer_key"),
                "status_aliases": interface.get("status_aliases") or {},
            },
            "collector_contract": {
                "contract_version": "1.0",
                "raw_payload_kind": interface.get("result_contract_kind"),
                "canonical_output_kind": "external-runner-outcome-v1",
                "normalizer_key": interface.get("normalizer_key"),
                "correlation_keys": ["runner_job_id", "outcome_collection_key", "contract_id"],
            },
            "dispatch_stub": {
                "dispatch_ref": job.get("dispatch_ref"),
                "transport": runner.get("dispatch_transport"),
                "stub_kind": dispatch_stub.get("stub_kind"),
                "outbound_contract_kind": interface.get("outbound_contract_kind"),
                "payload": dispatch_stub.get("payload"),
            },
        }
    )


def build_runner_interface_artifacts(runner_jobs_doc: dict, interface_catalog: list[dict]) -> tuple[dict, dict, dict]:
    contracts: list[dict] = []
    review_items: list[dict] = []

    for job in runner_jobs_doc.get("jobs") or []:
        if not isinstance(job, dict):
            continue
        candidates = _runner_interface_candidates(job, interface_catalog)
        reason_codes = ["runner_job_ready_for_interface"]
        if not candidates:
            reason_codes.append("no_runner_interface_match")
        elif len(candidates) > 1:
            reason_codes.append("multiple_runner_interface_matches")

        if len(candidates) == 1:
            contracts.append(_build_interface_contract(job, candidates[0]))
            continue

        runner = job.get("runner") if isinstance(job.get("runner"), dict) else {}
        target = job.get("target") if isinstance(job.get("target"), dict) else {}
        adapter = job.get("adapter") if isinstance(job.get("adapter"), dict) else {}
        review_items.append(
            redact_sensitive_fields(
                {
                    "schema_version": ADAPTER_RUNNER_INTERFACE_REVIEW_QUEUE_SCHEMA_VERSION,
                    "queue_item_id": _runner_interface_review_item_id(job),
                    "state": "open",
                    "priority": "high",
                    "review_type": "runner-interface-routing",
                    "runner_job_id": job.get("runner_job_id"),
                    "contract_id": job.get("contract_id"),
                    "event_id": job.get("event_id"),
                    "reason_codes": reason_codes,
                    "runner": {
                        "runner_key": runner.get("runner_key"),
                        "runner_family": runner.get("runner_family"),
                        "dispatch_transport": runner.get("dispatch_transport"),
                    },
                    "adapter": {
                        "adapter_key": adapter.get("adapter_key"),
                        "adapter_family": adapter.get("adapter_family"),
                    },
                    "target": {
                        "target_key": target.get("target_key"),
                        "target_system": target.get("target_system"),
                    },
                    "candidate_interfaces": [
                        {
                            "interface_key": item.get("interface_key"),
                            "interface_family": item.get("interface_family"),
                            "result_contract_kind": item.get("result_contract_kind"),
                            "normalizer_key": item.get("normalizer_key"),
                        }
                        for item in candidates
                    ],
                }
            )
        )

    contracts_doc = {
        "schema_version": ADAPTER_RUNNER_INTERFACE_CONTRACTS_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "contract_count": len(contracts),
        "contracts": sorted(contracts, key=lambda item: str(item.get("interface_contract_id") or "")),
    }
    review_queue = {
        "schema_version": ADAPTER_RUNNER_INTERFACE_REVIEW_QUEUE_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "item_count": len(review_items),
        "items": sorted(review_items, key=lambda item: str(item.get("queue_item_id") or "")),
    }
    rollup = build_runner_interface_rollup(contracts_doc, review_queue)
    return redact_sensitive_fields(contracts_doc), redact_sensitive_fields(review_queue), redact_sensitive_fields(rollup)


def build_runner_interface_rollup(contracts_doc: dict, review_queue: dict) -> dict:
    interface_family_counts: dict[str, int] = {}
    result_contract_kind_counts: dict[str, int] = {}
    normalizer_key_counts: dict[str, int] = {}
    target_system_counts: dict[str, int] = {}
    review_reason_counts: dict[str, int] = {}

    for contract in contracts_doc.get("contracts") or []:
        if not isinstance(contract, dict):
            continue
        interface = contract.get("interface") if isinstance(contract.get("interface"), dict) else {}
        target = contract.get("target") if isinstance(contract.get("target"), dict) else {}
        interface_family = _normalize_text(interface.get("interface_family")) or "runner-interface"
        result_contract_kind = _normalize_text(interface.get("result_contract_kind")) or "unknown"
        normalizer_key = _normalize_text(interface.get("normalizer_key")) or "unknown"
        target_system = _normalize_text(target.get("target_system")) or "unknown"
        interface_family_counts[interface_family] = interface_family_counts.get(interface_family, 0) + 1
        result_contract_kind_counts[result_contract_kind] = result_contract_kind_counts.get(result_contract_kind, 0) + 1
        normalizer_key_counts[normalizer_key] = normalizer_key_counts.get(normalizer_key, 0) + 1
        target_system_counts[target_system] = target_system_counts.get(target_system, 0) + 1

    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        for reason in item.get("reason_codes") or []:
            normalized = _normalize_text(reason)
            if normalized:
                review_reason_counts[normalized] = review_reason_counts.get(normalized, 0) + 1

    return {
        "schema_version": ADAPTER_RUNNER_INTERFACE_ROLLUP_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "contract_count": int(contracts_doc.get("contract_count") or 0),
        "review_queue_count": int(review_queue.get("item_count") or 0),
        "interface_family_counts": interface_family_counts,
        "result_contract_kind_counts": result_contract_kind_counts,
        "normalizer_key_counts": normalizer_key_counts,
        "target_system_counts": target_system_counts,
        "review_reason_counts": review_reason_counts,
    }


def _interface_indexes(contracts_doc: dict) -> tuple[dict[str, dict], dict[str, dict], dict[str, list[dict]]]:
    by_job_id: dict[str, dict] = {}
    by_collection_key: dict[str, dict] = {}
    by_contract_id: dict[str, list[dict]] = {}
    for contract in contracts_doc.get("contracts") or []:
        if not isinstance(contract, dict):
            continue
        runner_job_id = _normalize_text(contract.get("runner_job_id"))
        outcome_collection_key = _normalize_text(contract.get("outcome_collection_key"))
        contract_id = _normalize_text(contract.get("contract_id"))
        if runner_job_id:
            by_job_id[runner_job_id] = contract
        if outcome_collection_key:
            by_collection_key[outcome_collection_key] = contract
        if contract_id:
            by_contract_id.setdefault(contract_id, []).append(contract)
    return by_job_id, by_collection_key, by_contract_id


def _nested(data: dict, *keys: str) -> object:
    current: object = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_correlation(payload: dict) -> tuple[str | None, str | None, str | None]:
    runner_job_id = (
        _normalize_text(payload.get("runner_job_id"))
        or _normalize_text(payload.get("job_id"))
        or _normalize_text(_nested(payload, "job", "id"))
        or _normalize_text(_nested(payload, "runner_job", "id"))
    )
    outcome_collection_key = (
        _normalize_text(payload.get("outcome_collection_key"))
        or _normalize_text(_nested(payload, "job", "outcome_collection_key"))
        or _normalize_text(_nested(payload, "result", "outcome_collection_key"))
    )
    contract_id = (
        _normalize_text(payload.get("contract_id"))
        or _normalize_text(_nested(payload, "contract", "id"))
        or _normalize_text(_nested(payload, "job", "contract_id"))
    )
    return runner_job_id, outcome_collection_key, contract_id


def _canonical_outcome_status(raw_status: str | None, status_aliases: dict[str, str]) -> str | None:
    normalized = _normalize_text(raw_status)
    if not normalized:
        return None
    lowered = normalized.lower().replace("-", "_").replace(" ", "_")
    if lowered in status_aliases:
        lowered = status_aliases[lowered]
    if lowered in SUCCESS_STATUSES:
        return "success"
    if lowered in FAILURE_STATUSES:
        return "failure"
    if lowered in DEFERRED_STATUSES:
        return "defer"
    if lowered in SKIPPED_STATUSES:
        return "skip"
    return None


def _normalize_payload_via_contract(payload: dict, contract: dict, actor_id: str | None) -> dict | None:
    interface = contract.get("interface") if isinstance(contract.get("interface"), dict) else {}
    collector_contract = contract.get("collector_contract") if isinstance(contract.get("collector_contract"), dict) else {}
    normalizer_key = _normalize_text(collector_contract.get("normalizer_key")) or _normalize_text(interface.get("normalizer_key")) or "json-envelope-v1"
    status_aliases = _normalize_mapping(interface.get("status_aliases"))

    if normalizer_key == "http-callback-v1":
        raw_status = _normalize_text(payload.get("status")) or _normalize_text(payload.get("outcome_status"))
        executed_by = _normalize_text(_nested(payload, "worker", "id")) or _normalize_text(payload.get("executed_by")) or actor_id
        executed_at = _normalize_text(payload.get("completed_at")) or _normalize_text(payload.get("finished_at")) or utcnow_iso()
        reason = _normalize_text(_nested(payload, "result", "message")) or _normalize_text(payload.get("message"))
        external_ref = _normalize_text(_nested(payload, "result", "ref")) or _normalize_text(payload.get("run_id"))
        status_code = _normalize_text(payload.get("code")) or _normalize_text(payload.get("http_status"))
    elif normalizer_key == "file-drop-v1":
        raw_status = _normalize_text(_nested(payload, "result", "status")) or _normalize_text(payload.get("status"))
        executed_by = _normalize_text(payload.get("producer")) or _normalize_text(payload.get("emitted_by")) or actor_id
        executed_at = _normalize_text(_nested(payload, "result", "finished_at")) or _normalize_text(payload.get("finished_at")) or utcnow_iso()
        reason = _normalize_text(_nested(payload, "result", "reason")) or _normalize_text(payload.get("message"))
        external_ref = _normalize_text(_nested(payload, "result", "ref")) or _normalize_text(payload.get("file_ref"))
        status_code = _normalize_text(_nested(payload, "result", "code")) or _normalize_text(payload.get("code"))
    else:
        raw_status = (
            _normalize_text(payload.get("outcome_status"))
            or _normalize_text(payload.get("status"))
            or _normalize_text(payload.get("result"))
            or _normalize_text(payload.get("outcome"))
        )
        executed_by = _normalize_text(payload.get("executed_by")) or _normalize_text(payload.get("worker_id")) or actor_id
        executed_at = _normalize_text(payload.get("executed_at")) or _normalize_text(payload.get("completed_at")) or utcnow_iso()
        reason = _normalize_text(payload.get("reason")) or _normalize_text(payload.get("message"))
        external_ref = _normalize_text(payload.get("external_ref")) or _normalize_text(payload.get("result_ref")) or _normalize_text(payload.get("run_id"))
        status_code = _normalize_text(payload.get("status_code")) or _normalize_text(payload.get("code"))

    outcome_status = _canonical_outcome_status(raw_status, status_aliases)
    if outcome_status is None:
        return None

    return redact_sensitive_fields(
        {
            "runner_job_id": contract.get("runner_job_id"),
            "outcome_collection_key": contract.get("outcome_collection_key"),
            "contract_id": contract.get("contract_id"),
            "outcome_status": outcome_status,
            "executed_by": executed_by,
            "executed_at": executed_at,
            "reason": reason,
            "external_ref": external_ref or contract.get("runner_job_id"),
            "status_code": status_code,
            "collector_ref": f"collector-normalized://{contract.get('interface_contract_id')}",
            "interface_contract_id": contract.get("interface_contract_id"),
            "normalizer_key": normalizer_key,
            "payload_source": {
                "runner_job_id": contract.get("runner_job_id"),
                "result_contract_kind": interface.get("result_contract_kind"),
                "interface_key": interface.get("interface_key"),
            },
        }
    )


def _build_collector_review_item(payload: dict, reason_codes: list[str]) -> dict:
    return redact_sensitive_fields(
        {
            "schema_version": COLLECTOR_NORMALIZATION_REVIEW_QUEUE_SCHEMA_VERSION,
            "queue_item_id": _collector_review_item_id(payload),
            "state": "open",
            "priority": "high",
            "review_type": "collector-normalization",
            "runner_job_id": _normalize_text(payload.get("runner_job_id")) or _normalize_text(payload.get("job_id")) or _normalize_text(_nested(payload, "job", "id")),
            "contract_id": _normalize_text(payload.get("contract_id")) or _normalize_text(_nested(payload, "contract", "id")),
            "reason_codes": reason_codes,
            "payload_summary": redact_sensitive_fields(payload),
        }
    )


def normalize_external_runner_outcomes(
    contracts_doc: dict,
    payloads: list[dict],
    *,
    actor_id: str | None = None,
) -> tuple[dict, dict, dict]:
    by_job_id, by_collection_key, by_contract_id = _interface_indexes(contracts_doc)
    outcomes: list[dict] = []
    review_items: list[dict] = []
    used_jobs: set[str] = set()

    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        runner_job_id, outcome_collection_key, contract_id = _extract_correlation(payload)
        contract: dict | None = None
        if runner_job_id and runner_job_id in by_job_id:
            contract = by_job_id[runner_job_id]
        elif outcome_collection_key and outcome_collection_key in by_collection_key:
            contract = by_collection_key[outcome_collection_key]
        elif contract_id and len(by_contract_id.get(contract_id, [])) == 1:
            contract = by_contract_id[contract_id][0]

        if contract is None:
            review_items.append(_build_collector_review_item(payload, ["no_matching_interface_contract"]))
            continue

        canonical_job_id = _normalize_text(contract.get("runner_job_id")) or "unknown"
        if canonical_job_id in used_jobs:
            review_items.append(_build_collector_review_item(payload, ["duplicate_normalized_outcome"]))
            continue

        normalized = _normalize_payload_via_contract(payload, contract, actor_id)
        if normalized is None:
            review_items.append(_build_collector_review_item(payload, ["unsupported_payload_status"]))
            continue

        used_jobs.add(canonical_job_id)
        outcomes.append(normalized)

    outcomes_doc = {
        "schema_version": NORMALIZED_EXTERNAL_OUTCOMES_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "outcome_count": len(outcomes),
        "outcomes": sorted(outcomes, key=lambda item: str(item.get("runner_job_id") or "")),
    }
    review_queue = {
        "schema_version": COLLECTOR_NORMALIZATION_REVIEW_QUEUE_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "item_count": len(review_items),
        "items": sorted(review_items, key=lambda item: str(item.get("queue_item_id") or "")),
    }
    rollup = build_collector_normalization_rollup(outcomes_doc, review_queue)
    return redact_sensitive_fields(outcomes_doc), redact_sensitive_fields(review_queue), redact_sensitive_fields(rollup)


def build_collector_normalization_rollup(outcomes_doc: dict, review_queue: dict) -> dict:
    outcome_status_counts: dict[str, int] = {}
    normalizer_key_counts: dict[str, int] = {}
    result_contract_kind_counts: dict[str, int] = {}
    review_reason_counts: dict[str, int] = {}

    for outcome in outcomes_doc.get("outcomes") or []:
        if not isinstance(outcome, dict):
            continue
        outcome_status = _normalize_text(outcome.get("outcome_status")) or "unknown"
        normalizer_key = _normalize_text(outcome.get("normalizer_key")) or "unknown"
        payload_source = outcome.get("payload_source") if isinstance(outcome.get("payload_source"), dict) else {}
        result_contract_kind = _normalize_text(payload_source.get("result_contract_kind")) or "unknown"
        outcome_status_counts[outcome_status] = outcome_status_counts.get(outcome_status, 0) + 1
        normalizer_key_counts[normalizer_key] = normalizer_key_counts.get(normalizer_key, 0) + 1
        result_contract_kind_counts[result_contract_kind] = result_contract_kind_counts.get(result_contract_kind, 0) + 1

    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        for reason in item.get("reason_codes") or []:
            normalized = _normalize_text(reason)
            if normalized:
                review_reason_counts[normalized] = review_reason_counts.get(normalized, 0) + 1

    return {
        "schema_version": COLLECTOR_NORMALIZATION_ROLLUP_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "outcome_count": int(outcomes_doc.get("outcome_count") or 0),
        "review_queue_count": int(review_queue.get("item_count") or 0),
        "outcome_status_counts": outcome_status_counts,
        "normalizer_key_counts": normalizer_key_counts,
        "result_contract_kind_counts": result_contract_kind_counts,
        "review_reason_counts": review_reason_counts,
    }


def render_runner_interface_contracts_markdown(contracts_doc: dict) -> str:
    lines = [
        "# Runner interface contracts",
        "",
        f"Generated at: {contracts_doc.get('generated_at')}",
        f"Contract count: {contracts_doc.get('contract_count', 0)}",
        "",
    ]
    contracts = contracts_doc.get("contracts") if isinstance(contracts_doc.get("contracts"), list) else []
    if not contracts:
        lines.append("No runner interface contracts were produced.")
        return "\n".join(lines).strip() + "\n"
    for contract in contracts:
        interface = contract.get("interface") if isinstance(contract.get("interface"), dict) else {}
        lines.extend(
            [
                f"## {contract.get('interface_contract_id')}",
                f"- Runner job: {contract.get('runner_job_id')}",
                f"- Interface key: {interface.get('interface_key')}",
                f"- Result contract kind: {interface.get('result_contract_kind')}",
                f"- Normalizer key: {interface.get('normalizer_key')}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def render_runner_interface_review_queue_markdown(review_queue: dict) -> str:
    lines = [
        "# Runner interface review queue",
        "",
        f"Generated at: {review_queue.get('generated_at')}",
        f"Item count: {review_queue.get('item_count', 0)}",
        "",
    ]
    items = review_queue.get("items") if isinstance(review_queue.get("items"), list) else []
    if not items:
        lines.append("No runner interface review items are open.")
        return "\n".join(lines).strip() + "\n"
    for item in items:
        lines.extend(
            [
                f"## {item.get('queue_item_id')}",
                f"- Runner job: {item.get('runner_job_id')}",
                f"- Reasons: {', '.join(item.get('reason_codes') or [])}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def render_runner_interface_rollup_markdown(rollup: dict) -> str:
    lines = [
        "# Runner interface rollup",
        "",
        f"Generated at: {rollup.get('generated_at')}",
        f"Contract count: {rollup.get('contract_count', 0)}",
        f"Review queue count: {rollup.get('review_queue_count', 0)}",
        "",
        "## Interface family counts",
    ]
    for key, value in sorted((rollup.get("interface_family_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Result contract kind counts"])
    for key, value in sorted((rollup.get("result_contract_kind_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).strip() + "\n"


def render_normalized_external_outcomes_markdown(outcomes_doc: dict) -> str:
    lines = [
        "# Normalized external runner outcomes",
        "",
        f"Generated at: {outcomes_doc.get('generated_at')}",
        f"Outcome count: {outcomes_doc.get('outcome_count', 0)}",
        "",
    ]
    outcomes = outcomes_doc.get("outcomes") if isinstance(outcomes_doc.get("outcomes"), list) else []
    if not outcomes:
        lines.append("No external payloads were normalized.")
        return "\n".join(lines).strip() + "\n"
    for outcome in outcomes:
        lines.extend(
            [
                f"## {outcome.get('runner_job_id')}",
                f"- Outcome status: {outcome.get('outcome_status')}",
                f"- Normalizer key: {outcome.get('normalizer_key')}",
                f"- Collector ref: {outcome.get('collector_ref')}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def render_collector_normalization_review_queue_markdown(review_queue: dict) -> str:
    lines = [
        "# Collector normalization review queue",
        "",
        f"Generated at: {review_queue.get('generated_at')}",
        f"Item count: {review_queue.get('item_count', 0)}",
        "",
    ]
    items = review_queue.get("items") if isinstance(review_queue.get("items"), list) else []
    if not items:
        lines.append("No collector normalization review items are open.")
        return "\n".join(lines).strip() + "\n"
    for item in items:
        lines.extend(
            [
                f"## {item.get('queue_item_id')}",
                f"- Runner job: {item.get('runner_job_id')}",
                f"- Reasons: {', '.join(item.get('reason_codes') or [])}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def render_collector_normalization_rollup_markdown(rollup: dict) -> str:
    lines = [
        "# Collector normalization rollup",
        "",
        f"Generated at: {rollup.get('generated_at')}",
        f"Outcome count: {rollup.get('outcome_count', 0)}",
        f"Review queue count: {rollup.get('review_queue_count', 0)}",
        "",
        "## Outcome status counts",
    ]
    for key, value in sorted((rollup.get("outcome_status_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Normalizer key counts"])
    for key, value in sorted((rollup.get("normalizer_key_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).strip() + "\n"
