from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .adapter_execution import load_adapter_execution_contracts
from .ingestion import utcnow_iso
from .security import redact_sensitive_fields

ADAPTER_RUNNER_JOBS_SCHEMA_VERSION = "1.0"
ADAPTER_RUNNER_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
ADAPTER_RUNNER_ROLLUP_SCHEMA_VERSION = "1.0"
EXTERNAL_OUTCOME_DECISIONS_SCHEMA_VERSION = "1.0"
EXTERNAL_OUTCOME_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
EXTERNAL_OUTCOME_ROLLUP_SCHEMA_VERSION = "1.0"

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


def normalize_runner_catalog(value: object) -> list[dict]:
    if isinstance(value, dict):
        entries = value.get("runners") if isinstance(value.get("runners"), list) else []
    elif isinstance(value, list):
        entries = value
    else:
        entries = []

    normalized: list[dict] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        runner_key = _normalize_text(item.get("runner_key"))
        if not runner_key:
            continue
        normalized.append(
            redact_sensitive_fields(
                {
                    "runner_key": runner_key,
                    "runner_family": _normalize_text(item.get("runner_family")) or "generic",
                    "runner_version": _normalize_text(item.get("runner_version")) or "1.0",
                    "stub_kind": _normalize_text(item.get("stub_kind")) or "job-envelope",
                    "dispatch_transport": _normalize_text(item.get("dispatch_transport")) or "json-envelope",
                    "supported_adapter_families": _normalize_str_list(item.get("supported_adapter_families")),
                    "supported_execution_modes": _normalize_str_list(item.get("supported_execution_modes")),
                    "supported_target_systems": _normalize_str_list(item.get("supported_target_systems")),
                    "supported_operations": _normalize_str_list(item.get("supported_operations")),
                    "active": _normalize_bool(item.get("active"), default=True),
                }
            )
        )
    normalized.sort(key=lambda item: str(item.get("runner_key") or ""))
    return normalized


def load_runner_catalog(path: str | Path) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    payload = json.loads(target.read_text(encoding="utf-8"))
    return normalize_runner_catalog(payload)


def load_external_outcome_payloads(path: str | Path) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("outcomes"), list):
        return [redact_sensitive_fields(item) for item in payload["outcomes"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [redact_sensitive_fields(item) for item in payload if isinstance(item, dict)]
    raise ValueError("External outcomes must be a JSON object with an outcomes list or a JSON list")


def _runnable_contracts(contracts_doc: dict) -> list[dict]:
    runnable: list[dict] = []
    for item in contracts_doc.get("contracts") or []:
        if not isinstance(item, dict):
            continue
        contract = redact_sensitive_fields(dict(item))
        contract_state = _normalize_text(contract.get("contract_state")) or "planned"
        execution_status = _normalize_text(contract.get("execution_status")) or "not_started"
        if contract_state in {"completed", "skipped", "failed"}:
            continue
        if execution_status in {"succeeded", "failed", "skipped"}:
            continue
        runnable.append(contract)
    return runnable


def _runner_compatible(contract: dict, runner: dict) -> bool:
    if not _normalize_bool(runner.get("active"), default=True):
        return False
    adapter = contract.get("adapter") if isinstance(contract.get("adapter"), dict) else {}
    target = contract.get("target") if isinstance(contract.get("target"), dict) else {}
    execution_mode = _normalize_text(contract.get("execution_mode"))
    operation = _normalize_text(contract.get("operation"))
    adapter_family = _normalize_text(adapter.get("adapter_family"))
    target_system = _normalize_text(target.get("target_system"))

    supported_families = runner.get("supported_adapter_families") if isinstance(runner.get("supported_adapter_families"), list) else []
    supported_modes = runner.get("supported_execution_modes") if isinstance(runner.get("supported_execution_modes"), list) else []
    supported_targets = runner.get("supported_target_systems") if isinstance(runner.get("supported_target_systems"), list) else []
    supported_operations = runner.get("supported_operations") if isinstance(runner.get("supported_operations"), list) else []

    if supported_families and adapter_family not in supported_families:
        return False
    if supported_modes and execution_mode not in supported_modes:
        return False
    if supported_targets and target_system not in supported_targets:
        return False
    if supported_operations and operation not in supported_operations:
        return False
    return True


def _runner_candidates(contract: dict, runner_catalog: list[dict]) -> list[dict]:
    return [redact_sensitive_fields(dict(item)) for item in runner_catalog if _runner_compatible(contract, item)]


def derive_runner_job_id(contract: dict, runner: dict) -> str:
    payload = {
        "contract_id": _normalize_text(contract.get("contract_id")),
        "runner_key": _normalize_text(runner.get("runner_key")),
        "execution_mode": _normalize_text(contract.get("execution_mode")),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"runner-job-{digest[:24]}"


def derive_outcome_collection_key(runner_job_id: str) -> str:
    digest = hashlib.sha256(runner_job_id.encode("utf-8")).hexdigest()
    return f"outcome-{digest[:24]}"


def _job_idempotency_key(runner_job_id: str) -> str:
    digest = hashlib.sha256(f"idem:{runner_job_id}".encode("utf-8")).hexdigest()
    return f"runner-idem-{digest[:24]}"


def _runner_queue_item_id(contract: dict) -> str:
    contract_id = _normalize_text(contract.get("contract_id")) or "unknown"
    digest = hashlib.sha256(f"runner:{contract_id}".encode("utf-8")).hexdigest()
    return f"runner-review-{digest[:24]}"


def _outcome_queue_item_id(payload: dict) -> str:
    source_ref = (
        _normalize_text(payload.get("runner_job_id"))
        or _normalize_text(payload.get("outcome_collection_key"))
        or _normalize_text(payload.get("contract_id"))
        or json.dumps(payload, sort_keys=True, separators=(",", ":"))
    )
    digest = hashlib.sha256(f"external:{source_ref}".encode("utf-8")).hexdigest()
    return f"external-outcome-review-{digest[:24]}"


def _build_runner_job(contract: dict, runner: dict) -> dict:
    adapter = contract.get("adapter") if isinstance(contract.get("adapter"), dict) else {}
    target = contract.get("target") if isinstance(contract.get("target"), dict) else {}
    evidence = contract.get("evidence") if isinstance(contract.get("evidence"), dict) else {}
    governance = contract.get("governance") if isinstance(contract.get("governance"), dict) else {}
    provenance = contract.get("provenance") if isinstance(contract.get("provenance"), dict) else {}

    runner_job_id = derive_runner_job_id(contract, runner)
    outcome_collection_key = derive_outcome_collection_key(runner_job_id)
    return redact_sensitive_fields(
        {
            "schema_version": ADAPTER_RUNNER_JOBS_SCHEMA_VERSION,
            "runner_job_id": runner_job_id,
            "contract_id": contract.get("contract_id"),
            "event_id": contract.get("event_id"),
            "state": "pending_dispatch",
            "execution_mode": contract.get("execution_mode"),
            "operation": contract.get("operation"),
            "dispatch_ref": f"adapter-runner://{runner_job_id}",
            "outcome_collection_key": outcome_collection_key,
            "idempotency_key": _job_idempotency_key(runner_job_id),
            "runner": {
                "runner_key": runner.get("runner_key"),
                "runner_family": runner.get("runner_family"),
                "runner_version": runner.get("runner_version"),
                "stub_kind": runner.get("stub_kind"),
                "dispatch_transport": runner.get("dispatch_transport"),
            },
            "adapter": adapter,
            "target": target,
            "dispatch_stub": {
                "envelope_version": "1.0",
                "contract_ref": f"adapter-contract://{contract.get('contract_id')}",
                "transport": runner.get("dispatch_transport"),
                "stub_kind": runner.get("stub_kind"),
                "payload": {
                    "event_id": contract.get("event_id"),
                    "operation": contract.get("operation"),
                    "execution_mode": contract.get("execution_mode"),
                    "adapter_key": adapter.get("adapter_key"),
                    "adapter_family": adapter.get("adapter_family"),
                    "target_key": target.get("target_key"),
                    "target_system": target.get("target_system"),
                    "target_id": target.get("target_id"),
                    "inventory_ref": evidence.get("inventory_ref"),
                    "zip_sha256": evidence.get("zip_sha256"),
                },
            },
            "evidence": evidence,
            "governance": {
                "review_required": governance.get("review_required"),
                "review_state": governance.get("review_state"),
                "application_state": governance.get("application_state"),
                "execution_state": governance.get("execution_state"),
            },
            "provenance": provenance,
        }
    )


def build_adapter_runner_job_artifacts(contracts_doc: dict, runner_catalog: list[dict]) -> tuple[dict, dict, dict]:
    jobs: list[dict] = []
    review_items: list[dict] = []

    for contract in _runnable_contracts(contracts_doc):
        candidates = _runner_candidates(contract, runner_catalog)
        reason_codes = ["adapter_contract_ready_for_runner"]
        if not candidates:
            reason_codes.append("no_runner_match")
        elif len(candidates) > 1:
            reason_codes.append("multiple_runner_matches")

        if len(candidates) == 1:
            jobs.append(_build_runner_job(contract, candidates[0]))
            continue

        target = contract.get("target") if isinstance(contract.get("target"), dict) else {}
        adapter = contract.get("adapter") if isinstance(contract.get("adapter"), dict) else {}
        review_items.append(
            redact_sensitive_fields(
                {
                    "schema_version": ADAPTER_RUNNER_REVIEW_QUEUE_SCHEMA_VERSION,
                    "queue_item_id": _runner_queue_item_id(contract),
                    "state": "open",
                    "priority": "high",
                    "review_type": "adapter-runner-routing",
                    "contract_id": contract.get("contract_id"),
                    "event_id": contract.get("event_id"),
                    "reason_codes": reason_codes,
                    "adapter": {
                        "adapter_key": adapter.get("adapter_key"),
                        "adapter_family": adapter.get("adapter_family"),
                    },
                    "target": {
                        "target_key": target.get("target_key"),
                        "target_system": target.get("target_system"),
                    },
                    "candidate_runners": [
                        {
                            "runner_key": item.get("runner_key"),
                            "runner_family": item.get("runner_family"),
                            "dispatch_transport": item.get("dispatch_transport"),
                            "stub_kind": item.get("stub_kind"),
                        }
                        for item in candidates
                    ],
                }
            )
        )

    jobs_doc = {
        "schema_version": ADAPTER_RUNNER_JOBS_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "job_count": len(jobs),
        "jobs": sorted(jobs, key=lambda item: str(item.get("runner_job_id") or "")),
    }
    review_queue = {
        "schema_version": ADAPTER_RUNNER_REVIEW_QUEUE_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "item_count": len(review_items),
        "items": sorted(review_items, key=lambda item: str(item.get("queue_item_id") or "")),
    }
    rollup = build_adapter_runner_rollup(jobs_doc, review_queue)
    return redact_sensitive_fields(jobs_doc), redact_sensitive_fields(review_queue), redact_sensitive_fields(rollup)


def build_adapter_runner_rollup(jobs_doc: dict, review_queue: dict) -> dict:
    execution_mode_counts: dict[str, int] = {}
    runner_family_counts: dict[str, int] = {}
    dispatch_transport_counts: dict[str, int] = {}
    target_system_counts: dict[str, int] = {}
    review_reason_counts: dict[str, int] = {}

    for job in jobs_doc.get("jobs") or []:
        if not isinstance(job, dict):
            continue
        execution_mode = _normalize_text(job.get("execution_mode")) or "unknown"
        runner = job.get("runner") if isinstance(job.get("runner"), dict) else {}
        target = job.get("target") if isinstance(job.get("target"), dict) else {}
        runner_family = _normalize_text(runner.get("runner_family")) or "generic"
        dispatch_transport = _normalize_text(runner.get("dispatch_transport")) or "unknown"
        target_system = _normalize_text(target.get("target_system")) or "unknown"
        execution_mode_counts[execution_mode] = execution_mode_counts.get(execution_mode, 0) + 1
        runner_family_counts[runner_family] = runner_family_counts.get(runner_family, 0) + 1
        dispatch_transport_counts[dispatch_transport] = dispatch_transport_counts.get(dispatch_transport, 0) + 1
        target_system_counts[target_system] = target_system_counts.get(target_system, 0) + 1

    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        for reason in item.get("reason_codes") or []:
            normalized = _normalize_text(reason)
            if normalized:
                review_reason_counts[normalized] = review_reason_counts.get(normalized, 0) + 1

    return {
        "schema_version": ADAPTER_RUNNER_ROLLUP_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "job_count": int(jobs_doc.get("job_count") or 0),
        "review_queue_count": int(review_queue.get("item_count") or 0),
        "execution_mode_counts": execution_mode_counts,
        "runner_family_counts": runner_family_counts,
        "dispatch_transport_counts": dispatch_transport_counts,
        "target_system_counts": target_system_counts,
        "review_reason_counts": review_reason_counts,
    }


def load_runner_jobs(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Runner jobs payload must be a JSON object")


def _normalize_external_status(payload: dict, job: dict) -> str | None:
    raw_status = (
        _normalize_text(payload.get("outcome_status"))
        or _normalize_text(payload.get("status"))
        or _normalize_text(payload.get("result"))
        or _normalize_text(payload.get("outcome"))
    )
    if not raw_status:
        return None
    normalized = raw_status.lower().replace("-", "_").replace(" ", "_")
    if normalized in SUCCESS_STATUSES:
        execution_mode = _normalize_text(payload.get("execution_mode")) or _normalize_text(job.get("execution_mode"))
        return "dry_run_success" if execution_mode == "dry_run" else "execute_success"
    if normalized in FAILURE_STATUSES:
        return "execute_failure"
    if normalized in SKIPPED_STATUSES:
        return "skip"
    if normalized in DEFERRED_STATUSES:
        return "defer"
    return None


def _job_indexes(jobs_doc: dict) -> tuple[dict[str, dict], dict[str, dict], dict[str, list[dict]]]:
    by_job_id: dict[str, dict] = {}
    by_collection_key: dict[str, dict] = {}
    by_contract_id: dict[str, list[dict]] = {}
    for job in jobs_doc.get("jobs") or []:
        if not isinstance(job, dict):
            continue
        runner_job_id = _normalize_text(job.get("runner_job_id"))
        outcome_collection_key = _normalize_text(job.get("outcome_collection_key"))
        contract_id = _normalize_text(job.get("contract_id"))
        if runner_job_id:
            by_job_id[runner_job_id] = job
        if outcome_collection_key:
            by_collection_key[outcome_collection_key] = job
        if contract_id:
            by_contract_id.setdefault(contract_id, []).append(job)
    return by_job_id, by_collection_key, by_contract_id


def _build_external_review_item(payload: dict, reason_codes: list[str]) -> dict:
    return redact_sensitive_fields(
        {
            "schema_version": EXTERNAL_OUTCOME_REVIEW_QUEUE_SCHEMA_VERSION,
            "queue_item_id": _outcome_queue_item_id(payload),
            "state": "open",
            "priority": "high",
            "review_type": "external-execution-outcome",
            "runner_job_id": _normalize_text(payload.get("runner_job_id")),
            "outcome_collection_key": _normalize_text(payload.get("outcome_collection_key")),
            "contract_id": _normalize_text(payload.get("contract_id")),
            "reason_codes": reason_codes,
            "payload_summary": redact_sensitive_fields(payload),
        }
    )


def collect_adapter_execution_outcomes(
    runner_jobs_doc: dict,
    payloads: list[dict],
    *,
    actor_id: str | None = None,
) -> tuple[dict, dict, dict]:
    by_job_id, by_collection_key, by_contract_id = _job_indexes(runner_jobs_doc)
    decisions: list[dict] = []
    review_items: list[dict] = []
    used_jobs: set[str] = set()

    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        runner_job_id = _normalize_text(payload.get("runner_job_id"))
        outcome_collection_key = _normalize_text(payload.get("outcome_collection_key"))
        contract_id = _normalize_text(payload.get("contract_id"))

        job: dict | None = None
        if runner_job_id and runner_job_id in by_job_id:
            job = by_job_id[runner_job_id]
        elif outcome_collection_key and outcome_collection_key in by_collection_key:
            job = by_collection_key[outcome_collection_key]
        elif contract_id and len(by_contract_id.get(contract_id, [])) == 1:
            job = by_contract_id[contract_id][0]

        if job is None:
            review_items.append(_build_external_review_item(payload, ["no_matching_runner_job"]))
            continue

        normalized_action = _normalize_external_status(payload, job)
        if normalized_action is None:
            review_items.append(_build_external_review_item(payload, ["unsupported_outcome_status"]))
            continue

        canonical_job_id = _normalize_text(job.get("runner_job_id")) or "unknown"
        if canonical_job_id in used_jobs:
            review_items.append(_build_external_review_item(payload, ["duplicate_outcome_payload"]))
            continue
        used_jobs.add(canonical_job_id)

        collector_ref = _normalize_text(payload.get("collector_ref")) or f"external-outcome://{canonical_job_id}"
        decisions.append(
            redact_sensitive_fields(
                {
                    "contract_id": job.get("contract_id"),
                    "runner_job_id": canonical_job_id,
                    "outcome_collection_key": job.get("outcome_collection_key"),
                    "outcome_action": normalized_action,
                    "executed_by": _normalize_text(payload.get("executed_by")) or actor_id,
                    "executed_at": _normalize_text(payload.get("executed_at")) or utcnow_iso(),
                    "reason": _normalize_text(payload.get("reason")) or _normalize_text(payload.get("message")),
                    "external_ref": _normalize_text(payload.get("external_ref")) or canonical_job_id,
                    "status_code": _normalize_text(payload.get("status_code")),
                    "execution_ref": collector_ref,
                    "collected_from": {
                        "runner_job_id": canonical_job_id,
                        "outcome_collection_key": job.get("outcome_collection_key"),
                    },
                }
            )
        )

    decisions_doc = {
        "schema_version": EXTERNAL_OUTCOME_DECISIONS_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "decision_count": len(decisions),
        "decisions": sorted(decisions, key=lambda item: str(item.get("contract_id") or "")),
    }
    review_queue = {
        "schema_version": EXTERNAL_OUTCOME_REVIEW_QUEUE_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "item_count": len(review_items),
        "items": sorted(review_items, key=lambda item: str(item.get("queue_item_id") or "")),
    }
    rollup = build_external_outcome_rollup(decisions_doc, review_queue)
    return redact_sensitive_fields(decisions_doc), redact_sensitive_fields(review_queue), redact_sensitive_fields(rollup)


def build_external_outcome_rollup(decisions_doc: dict, review_queue: dict) -> dict:
    outcome_action_counts: dict[str, int] = {}
    review_reason_counts: dict[str, int] = {}
    for item in decisions_doc.get("decisions") or []:
        if not isinstance(item, dict):
            continue
        action = _normalize_text(item.get("outcome_action")) or "unknown"
        outcome_action_counts[action] = outcome_action_counts.get(action, 0) + 1
    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        for reason in item.get("reason_codes") or []:
            normalized = _normalize_text(reason)
            if normalized:
                review_reason_counts[normalized] = review_reason_counts.get(normalized, 0) + 1
    return {
        "schema_version": EXTERNAL_OUTCOME_ROLLUP_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "decision_count": int(decisions_doc.get("decision_count") or 0),
        "review_queue_count": int(review_queue.get("item_count") or 0),
        "outcome_action_counts": outcome_action_counts,
        "review_reason_counts": review_reason_counts,
    }


def render_adapter_runner_jobs_markdown(jobs_doc: dict) -> str:
    lines = [
        "# Adapter runner jobs",
        "",
        f"Generated at: {jobs_doc.get('generated_at')}",
        f"Job count: {jobs_doc.get('job_count', 0)}",
        "",
    ]
    jobs = jobs_doc.get("jobs") if isinstance(jobs_doc.get("jobs"), list) else []
    if not jobs:
        lines.append("No runner jobs were generated.")
        return "\n".join(lines).strip() + "\n"
    for job in jobs:
        runner = job.get("runner") if isinstance(job.get("runner"), dict) else {}
        lines.extend(
            [
                f"## {job.get('runner_job_id')}",
                f"- Contract: {job.get('contract_id')}",
                f"- Runner: {runner.get('runner_key')} ({runner.get('runner_family')})",
                f"- Execution mode: {job.get('execution_mode')}",
                f"- Outcome collection key: {job.get('outcome_collection_key')}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def render_adapter_runner_review_queue_markdown(review_queue: dict) -> str:
    lines = [
        "# Adapter runner review queue",
        "",
        f"Generated at: {review_queue.get('generated_at')}",
        f"Open items: {review_queue.get('item_count', 0)}",
        "",
    ]
    items = review_queue.get("items") if isinstance(review_queue.get("items"), list) else []
    if not items:
        lines.append("No adapter runner review items remain.")
        return "\n".join(lines).strip() + "\n"
    for item in items:
        lines.extend(
            [
                f"## {item.get('queue_item_id')}",
                f"- Contract: {item.get('contract_id')}",
                f"- Reasons: {', '.join(item.get('reason_codes') or [])}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def render_adapter_runner_rollup_markdown(rollup: dict) -> str:
    lines = [
        "# Adapter runner rollup",
        "",
        f"Generated at: {rollup.get('generated_at')}",
        f"Job count: {rollup.get('job_count', 0)}",
        f"Review queue count: {rollup.get('review_queue_count', 0)}",
        "",
        "## Runner family counts",
    ]
    for key, value in sorted((rollup.get("runner_family_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Dispatch transport counts"])
    for key, value in sorted((rollup.get("dispatch_transport_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).strip() + "\n"


def render_external_outcome_decisions_markdown(decisions_doc: dict) -> str:
    lines = [
        "# Collected adapter execution decisions",
        "",
        f"Generated at: {decisions_doc.get('generated_at')}",
        f"Decision count: {decisions_doc.get('decision_count', 0)}",
        "",
    ]
    decisions = decisions_doc.get("decisions") if isinstance(decisions_doc.get("decisions"), list) else []
    if not decisions:
        lines.append("No external outcomes were converted into execution decisions.")
        return "\n".join(lines).strip() + "\n"
    for decision in decisions:
        lines.extend(
            [
                f"## {decision.get('contract_id')}",
                f"- Runner job: {decision.get('runner_job_id')}",
                f"- Outcome action: {decision.get('outcome_action')}",
                f"- Execution ref: {decision.get('execution_ref')}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def render_external_outcome_review_queue_markdown(review_queue: dict) -> str:
    lines = [
        "# External outcome review queue",
        "",
        f"Generated at: {review_queue.get('generated_at')}",
        f"Open items: {review_queue.get('item_count', 0)}",
        "",
    ]
    items = review_queue.get("items") if isinstance(review_queue.get("items"), list) else []
    if not items:
        lines.append("No external outcome review items remain.")
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


def render_external_outcome_rollup_markdown(rollup: dict) -> str:
    lines = [
        "# External outcome rollup",
        "",
        f"Generated at: {rollup.get('generated_at')}",
        f"Decision count: {rollup.get('decision_count', 0)}",
        f"Review queue count: {rollup.get('review_queue_count', 0)}",
        "",
        "## Outcome action counts",
    ]
    for key, value in sorted((rollup.get("outcome_action_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Review reason counts"])
    for key, value in sorted((rollup.get("review_reason_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).strip() + "\n"


__all__ = [
    "ADAPTER_RUNNER_JOBS_SCHEMA_VERSION",
    "ADAPTER_RUNNER_REVIEW_QUEUE_SCHEMA_VERSION",
    "ADAPTER_RUNNER_ROLLUP_SCHEMA_VERSION",
    "EXTERNAL_OUTCOME_DECISIONS_SCHEMA_VERSION",
    "EXTERNAL_OUTCOME_REVIEW_QUEUE_SCHEMA_VERSION",
    "EXTERNAL_OUTCOME_ROLLUP_SCHEMA_VERSION",
    "build_adapter_runner_job_artifacts",
    "build_adapter_runner_rollup",
    "build_external_outcome_rollup",
    "collect_adapter_execution_outcomes",
    "derive_outcome_collection_key",
    "derive_runner_job_id",
    "load_adapter_execution_contracts",
    "load_external_outcome_payloads",
    "load_runner_catalog",
    "load_runner_jobs",
    "normalize_runner_catalog",
    "render_adapter_runner_jobs_markdown",
    "render_adapter_runner_review_queue_markdown",
    "render_adapter_runner_rollup_markdown",
    "render_external_outcome_decisions_markdown",
    "render_external_outcome_review_queue_markdown",
    "render_external_outcome_rollup_markdown",
]
