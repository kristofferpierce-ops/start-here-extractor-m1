from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .ingestion import utcnow_iso
from .security import redact_sensitive_fields

DRY_RUN_HARNESS_RESULT_JOURNALS_SCHEMA_VERSION = "1.0"
DRY_RUN_HARNESS_RESULT_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
DRY_RUN_HARNESS_RESULT_ROLLUP_SCHEMA_VERSION = "1.0"
REPLAY_OUTCOME_COMPARISON_PACKS_SCHEMA_VERSION = "1.0"
REPLAY_OUTCOME_COMPARISON_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
REPLAY_OUTCOME_COMPARISON_ROLLUP_SCHEMA_VERSION = "1.0"

_FIXTURE_MODE_TO_EXECUTION_OUTCOME = {
    "success": "success",
    "failure": "failure",
    "defer": "deferred",
    "skip": "skipped",
}


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def load_target_group_adapter_execution_harnesses(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Target-group adapter execution harnesses payload must be a JSON object")


def load_replayable_dry_run_orchestration_packs(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Replayable dry-run orchestration packs payload must be a JSON object")


def load_dry_run_harness_result_journals(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Dry-run harness result journals payload must be a JSON object")


def derive_dry_run_harness_result_journal_id(harness_doc: dict) -> str:
    payload = {
        "target_group_adapter_execution_harness_id": _normalize_text(harness_doc.get("target_group_adapter_execution_harness_id")),
        "harness_group_key": _normalize_text(harness_doc.get("harness_group", {}).get("harness_group_key")) if isinstance(harness_doc.get("harness_group"), dict) else None,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"dry-run-harness-result-journal-{digest[:24]}"


def derive_replay_outcome_comparison_pack_id(orchestration_pack: dict) -> str:
    payload = {
        "replayable_dry_run_orchestration_pack_id": _normalize_text(orchestration_pack.get("replayable_dry_run_orchestration_pack_id")),
        "target_group_adapter_execution_harness_id": _normalize_text(orchestration_pack.get("target_group_adapter_execution_harness_id")),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"replay-outcome-comparison-pack-{digest[:24]}"


def _result_review_item_id(harness_doc: dict) -> str:
    harness_id = _normalize_text(harness_doc.get("target_group_adapter_execution_harness_id")) or "unknown"
    digest = hashlib.sha256(f"dry-run-result:{harness_id}".encode("utf-8")).hexdigest()
    return f"dry-run-result-review-{digest[:24]}"


def _comparison_review_item_id(pack_doc: dict) -> str:
    pack_id = _normalize_text(pack_doc.get("replayable_dry_run_orchestration_pack_id")) or "unknown"
    digest = hashlib.sha256(f"replay-comparison:{pack_id}".encode("utf-8")).hexdigest()
    return f"replay-comparison-review-{digest[:24]}"


def _journal_ref(journal_id: str) -> str:
    return f"dry-run-harness-result-journal://{journal_id}"


def _comparison_ref(pack_id: str) -> str:
    return f"replay-outcome-comparison-pack://{pack_id}"


def _orchestration_index(orchestration_doc: dict) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for item in orchestration_doc.get("packs") or []:
        if not isinstance(item, dict):
            continue
        harness_id = _normalize_text(item.get("target_group_adapter_execution_harness_id"))
        if harness_id:
            index[harness_id] = redact_sensitive_fields(dict(item))
    return index


def _journal_index(journals_doc: dict) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for item in journals_doc.get("journals") or []:
        if not isinstance(item, dict):
            continue
        pack_id = _normalize_text(item.get("replayable_dry_run_orchestration_pack_id"))
        if pack_id:
            index[pack_id] = redact_sensitive_fields(dict(item))
    return index


def _build_result_entry(journal_id: str, step: dict, index: int) -> dict:
    fixture_mode = _normalize_text(step.get("fixture_mode")) or "unknown"
    outcome = _FIXTURE_MODE_TO_EXECUTION_OUTCOME.get(fixture_mode, "unknown")
    return redact_sensitive_fields(
        {
            "result_entry_id": f"{journal_id}:entry:{index}",
            "step_id": step.get("step_id"),
            "roundtrip_normalization_case_id": step.get("roundtrip_normalization_case_id"),
            "fixture_mode": fixture_mode,
            "execution_outcome": outcome,
            "observed_response_payload": step.get("expected_response_payload"),
            "observed_normalized_result": step.get("expected_normalized_result"),
            "response_status_code": step.get("response_status_code"),
        }
    )


def _build_dry_run_harness_result_journal(harness_doc: dict, orchestration_pack: dict) -> dict:
    journal_id = derive_dry_run_harness_result_journal_id(harness_doc)
    steps = [item for item in orchestration_pack.get("steps") or [] if isinstance(item, dict)]
    results = [_build_result_entry(journal_id, step, index) for index, step in enumerate(steps, start=1)]
    return redact_sensitive_fields(
        {
            "schema_version": DRY_RUN_HARNESS_RESULT_JOURNALS_SCHEMA_VERSION,
            "dry_run_harness_result_journal_id": journal_id,
            "dry_run_harness_result_journal_ref": _journal_ref(journal_id),
            "state": "dry-run-result-journaled",
            "target_group_adapter_execution_harness_id": harness_doc.get("target_group_adapter_execution_harness_id"),
            "replayable_dry_run_orchestration_pack_id": orchestration_pack.get("replayable_dry_run_orchestration_pack_id"),
            "target_group": harness_doc.get("target_group"),
            "target": harness_doc.get("target"),
            "harness_group": harness_doc.get("harness_group"),
            "adapter_entrypoint": harness_doc.get("adapter_entrypoint"),
            "execution_context": harness_doc.get("execution_context"),
            "result_entries": results,
            "result_summary": {
                "entry_count": len(results),
                "fixture_modes": [item.get("fixture_mode") for item in results],
                "execution_outcomes": [item.get("execution_outcome") for item in results],
            },
            "audit": {
                "created_at": utcnow_iso(),
                "source_stage": "target-group-adapter-execution-harness",
            },
        }
    )


def build_dry_run_harness_result_journal_artifacts(harnesses_doc: dict, orchestration_doc: dict) -> tuple[dict, dict, dict]:
    orchestration_index = _orchestration_index(orchestration_doc)
    journals: list[dict] = []
    review_items: list[dict] = []

    for harness_doc in harnesses_doc.get("harnesses") or []:
        if not isinstance(harness_doc, dict):
            continue
        harness_id = _normalize_text(harness_doc.get("target_group_adapter_execution_harness_id"))
        pack_doc = orchestration_index.get(harness_id or "")
        if not pack_doc:
            review_items.append(
                redact_sensitive_fields(
                    {
                        "schema_version": DRY_RUN_HARNESS_RESULT_REVIEW_QUEUE_SCHEMA_VERSION,
                        "queue_item_id": _result_review_item_id(harness_doc),
                        "state": "open",
                        "priority": "high",
                        "review_type": "dry-run-harness-result-journal",
                        "target_group_adapter_execution_harness_id": harness_doc.get("target_group_adapter_execution_harness_id"),
                        "reason_codes": ["no_orchestration_pack_found"],
                        "harness_summary": redact_sensitive_fields(harness_doc),
                    }
                )
            )
            continue
        if not [item for item in pack_doc.get("steps") or [] if isinstance(item, dict)]:
            review_items.append(
                redact_sensitive_fields(
                    {
                        "schema_version": DRY_RUN_HARNESS_RESULT_REVIEW_QUEUE_SCHEMA_VERSION,
                        "queue_item_id": _result_review_item_id(harness_doc),
                        "state": "open",
                        "priority": "medium",
                        "review_type": "dry-run-harness-result-journal",
                        "target_group_adapter_execution_harness_id": harness_doc.get("target_group_adapter_execution_harness_id"),
                        "reason_codes": ["no_replay_steps_found"],
                        "harness_summary": redact_sensitive_fields(harness_doc),
                    }
                )
            )
            continue
        journals.append(_build_dry_run_harness_result_journal(harness_doc, pack_doc))

    journals_doc = redact_sensitive_fields(
        {
            "schema_version": DRY_RUN_HARNESS_RESULT_JOURNALS_SCHEMA_VERSION,
            "journal_count": len(journals),
            "journals": journals,
            "generated_at": utcnow_iso(),
        }
    )
    review_queue = redact_sensitive_fields(
        {
            "schema_version": DRY_RUN_HARNESS_RESULT_REVIEW_QUEUE_SCHEMA_VERSION,
            "item_count": len(review_items),
            "items": review_items,
            "generated_at": utcnow_iso(),
        }
    )
    outcome_counts: dict[str, int] = {}
    for journal in journals:
        for item in journal.get("result_entries") or []:
            if not isinstance(item, dict):
                continue
            key = _normalize_text(item.get("execution_outcome")) or "unknown"
            outcome_counts[key] = outcome_counts.get(key, 0) + 1
    rollup = redact_sensitive_fields(
        {
            "schema_version": DRY_RUN_HARNESS_RESULT_ROLLUP_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "journal_count": len(journals),
            "review_queue_count": len(review_items),
            "execution_outcome_counts": outcome_counts,
        }
    )
    return journals_doc, review_queue, rollup


def _build_comparison_item(pack_id: str, step: dict, result_entry: dict, index: int) -> dict:
    expected_response_payload = step.get("expected_response_payload")
    observed_response_payload = result_entry.get("observed_response_payload")
    expected_normalized_result = step.get("expected_normalized_result")
    observed_normalized_result = result_entry.get("observed_normalized_result")
    response_payload_match = observed_response_payload == expected_response_payload
    normalized_result_match = observed_normalized_result == expected_normalized_result
    comparison_outcome = "match" if response_payload_match and normalized_result_match else "mismatch"
    return redact_sensitive_fields(
        {
            "comparison_item_id": f"{pack_id}:comparison:{index}",
            "step_id": step.get("step_id"),
            "roundtrip_normalization_case_id": step.get("roundtrip_normalization_case_id"),
            "fixture_mode": step.get("fixture_mode"),
            "expected_response_payload": expected_response_payload,
            "observed_response_payload": observed_response_payload,
            "expected_normalized_result": expected_normalized_result,
            "observed_normalized_result": observed_normalized_result,
            "response_payload_match": response_payload_match,
            "normalized_result_match": normalized_result_match,
            "comparison_outcome": comparison_outcome,
        }
    )


def _build_replay_outcome_comparison_pack(orchestration_pack: dict, journal_doc: dict) -> dict:
    comparison_id = derive_replay_outcome_comparison_pack_id(orchestration_pack)
    result_index = {
        _normalize_text(item.get("step_id")): item
        for item in journal_doc.get("result_entries") or []
        if isinstance(item, dict) and _normalize_text(item.get("step_id"))
    }
    comparisons: list[dict] = []
    mismatched_step_ids: list[str] = []
    missing_result_step_ids: list[str] = []
    for index, step in enumerate(orchestration_pack.get("steps") or [], start=1):
        if not isinstance(step, dict):
            continue
        step_id = _normalize_text(step.get("step_id"))
        result_entry = result_index.get(step_id or "")
        if not result_entry:
            missing_result_step_ids.append(step_id or f"step-{index}")
            comparisons.append(
                redact_sensitive_fields(
                    {
                        "comparison_item_id": f"{comparison_id}:comparison:{index}",
                        "step_id": step.get("step_id"),
                        "roundtrip_normalization_case_id": step.get("roundtrip_normalization_case_id"),
                        "fixture_mode": step.get("fixture_mode"),
                        "comparison_outcome": "missing_result",
                    }
                )
            )
            continue
        comparison = _build_comparison_item(comparison_id, step, result_entry, index)
        if comparison.get("comparison_outcome") != "match":
            mismatched_step_ids.append(step_id or f"step-{index}")
        comparisons.append(comparison)
    return redact_sensitive_fields(
        {
            "schema_version": REPLAY_OUTCOME_COMPARISON_PACKS_SCHEMA_VERSION,
            "replay_outcome_comparison_pack_id": comparison_id,
            "replay_outcome_comparison_pack_ref": _comparison_ref(comparison_id),
            "state": "replay-compared",
            "replayable_dry_run_orchestration_pack_id": orchestration_pack.get("replayable_dry_run_orchestration_pack_id"),
            "dry_run_harness_result_journal_id": journal_doc.get("dry_run_harness_result_journal_id"),
            "target_group": orchestration_pack.get("target_group"),
            "target": orchestration_pack.get("target"),
            "harness_group": orchestration_pack.get("harness_group"),
            "comparison_items": comparisons,
            "comparison_summary": {
                "item_count": len(comparisons),
                "mismatched_step_ids": mismatched_step_ids,
                "missing_result_step_ids": missing_result_step_ids,
            },
            "audit": {
                "created_at": utcnow_iso(),
                "source_stage": "dry-run-harness-result-journal",
            },
        }
    )


def build_replay_outcome_comparison_pack_artifacts(journals_doc: dict, orchestration_doc: dict) -> tuple[dict, dict, dict]:
    journal_index = _journal_index(journals_doc)
    packs: list[dict] = []
    review_items: list[dict] = []

    for orchestration_pack in orchestration_doc.get("packs") or []:
        if not isinstance(orchestration_pack, dict):
            continue
        pack_id = _normalize_text(orchestration_pack.get("replayable_dry_run_orchestration_pack_id"))
        journal_doc = journal_index.get(pack_id or "")
        if not journal_doc:
            review_items.append(
                redact_sensitive_fields(
                    {
                        "schema_version": REPLAY_OUTCOME_COMPARISON_REVIEW_QUEUE_SCHEMA_VERSION,
                        "queue_item_id": _comparison_review_item_id(orchestration_pack),
                        "state": "open",
                        "priority": "high",
                        "review_type": "replay-outcome-comparison-pack",
                        "replayable_dry_run_orchestration_pack_id": orchestration_pack.get("replayable_dry_run_orchestration_pack_id"),
                        "reason_codes": ["no_result_journal_found"],
                        "orchestration_summary": redact_sensitive_fields(orchestration_pack),
                    }
                )
            )
            continue
        pack = _build_replay_outcome_comparison_pack(orchestration_pack, journal_doc)
        if pack.get("comparison_summary", {}).get("mismatched_step_ids") or pack.get("comparison_summary", {}).get("missing_result_step_ids"):
            review_items.append(
                redact_sensitive_fields(
                    {
                        "schema_version": REPLAY_OUTCOME_COMPARISON_REVIEW_QUEUE_SCHEMA_VERSION,
                        "queue_item_id": _comparison_review_item_id(orchestration_pack),
                        "state": "open",
                        "priority": "medium",
                        "review_type": "replay-outcome-comparison-pack",
                        "replayable_dry_run_orchestration_pack_id": orchestration_pack.get("replayable_dry_run_orchestration_pack_id"),
                        "reason_codes": ["comparison_requires_review"],
                        "comparison_summary": pack.get("comparison_summary"),
                    }
                )
            )
        packs.append(pack)

    packs_doc = redact_sensitive_fields(
        {
            "schema_version": REPLAY_OUTCOME_COMPARISON_PACKS_SCHEMA_VERSION,
            "pack_count": len(packs),
            "packs": packs,
            "generated_at": utcnow_iso(),
        }
    )
    review_queue = redact_sensitive_fields(
        {
            "schema_version": REPLAY_OUTCOME_COMPARISON_REVIEW_QUEUE_SCHEMA_VERSION,
            "item_count": len(review_items),
            "items": review_items,
            "generated_at": utcnow_iso(),
        }
    )
    comparison_outcome_counts: dict[str, int] = {}
    for pack in packs:
        for item in pack.get("comparison_items") or []:
            if not isinstance(item, dict):
                continue
            key = _normalize_text(item.get("comparison_outcome")) or "unknown"
            comparison_outcome_counts[key] = comparison_outcome_counts.get(key, 0) + 1
    rollup = redact_sensitive_fields(
        {
            "schema_version": REPLAY_OUTCOME_COMPARISON_ROLLUP_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "pack_count": len(packs),
            "review_queue_count": len(review_items),
            "comparison_outcome_counts": comparison_outcome_counts,
        }
    )
    return packs_doc, review_queue, rollup


def render_dry_run_harness_result_journals_markdown(journals_doc: dict) -> str:
    lines = ["# Dry-Run Harness Result Journals", ""]
    lines.append(f"Journal count: {journals_doc.get('journal_count', 0)}")
    lines.append("")
    for item in journals_doc.get("journals") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('dry_run_harness_result_journal_id')}` :: entries={len(item.get('result_entries') or [])}")
    return "\n".join(lines) + "\n"


def render_dry_run_harness_result_review_queue_markdown(review_queue: dict) -> str:
    lines = ["# Dry-Run Harness Result Review Queue", ""]
    lines.append(f"Open items: {review_queue.get('item_count', 0)}")
    lines.append("")
    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('queue_item_id')}` :: {', '.join(item.get('reason_codes') or [])}")
    return "\n".join(lines) + "\n"


def render_dry_run_harness_result_rollup_markdown(rollup: dict) -> str:
    lines = ["# Dry-Run Harness Result Rollup", ""]
    lines.append(f"Journal count: {rollup.get('journal_count', 0)}")
    lines.append(f"Review queue count: {rollup.get('review_queue_count', 0)}")
    lines.append("")
    for key, value in sorted((rollup.get("execution_outcome_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"


def render_replay_outcome_comparison_packs_markdown(packs_doc: dict) -> str:
    lines = ["# Replay Outcome Comparison Packs", ""]
    lines.append(f"Pack count: {packs_doc.get('pack_count', 0)}")
    lines.append("")
    for item in packs_doc.get("packs") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('replay_outcome_comparison_pack_id')}` :: comparisons={len(item.get('comparison_items') or [])}")
    return "\n".join(lines) + "\n"


def render_replay_outcome_comparison_review_queue_markdown(review_queue: dict) -> str:
    lines = ["# Replay Outcome Comparison Review Queue", ""]
    lines.append(f"Open items: {review_queue.get('item_count', 0)}")
    lines.append("")
    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('queue_item_id')}` :: {', '.join(item.get('reason_codes') or [])}")
    return "\n".join(lines) + "\n"


def render_replay_outcome_comparison_rollup_markdown(rollup: dict) -> str:
    lines = ["# Replay Outcome Comparison Rollup", ""]
    lines.append(f"Pack count: {rollup.get('pack_count', 0)}")
    lines.append(f"Review queue count: {rollup.get('review_queue_count', 0)}")
    lines.append("")
    for key, value in sorted((rollup.get("comparison_outcome_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"
