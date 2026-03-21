from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .ingestion import utcnow_iso
from .security import redact_sensitive_fields

TARGET_GROUP_PROMOTION_READINESS_PACKS_SCHEMA_VERSION = "1.0"
TARGET_GROUP_PROMOTION_READINESS_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
TARGET_GROUP_PROMOTION_READINESS_ROLLUP_SCHEMA_VERSION = "1.0"
LIVE_INTEGRATION_CANDIDATE_PACKS_SCHEMA_VERSION = "1.0"
LIVE_INTEGRATION_CANDIDATE_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
LIVE_INTEGRATION_CANDIDATE_ROLLUP_SCHEMA_VERSION = "1.0"


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None



def load_dry_run_harness_result_journals(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Dry-run harness result journals payload must be a JSON object")



def load_replay_outcome_comparison_packs(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Replay outcome comparison packs payload must be a JSON object")



def load_target_group_promotion_readiness_packs(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Target-group promotion readiness packs payload must be a JSON object")



def derive_target_group_promotion_readiness_pack_id(journal_doc: dict) -> str:
    payload = {
        "dry_run_harness_result_journal_id": _normalize_text(journal_doc.get("dry_run_harness_result_journal_id")),
        "replayable_dry_run_orchestration_pack_id": _normalize_text(journal_doc.get("replayable_dry_run_orchestration_pack_id")),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"target-group-promotion-readiness-pack-{digest[:24]}"



def derive_live_integration_candidate_pack_id(readiness_pack: dict) -> str:
    payload = {
        "target_group_promotion_readiness_pack_id": _normalize_text(readiness_pack.get("target_group_promotion_readiness_pack_id")),
        "target_group_key": _normalize_text(readiness_pack.get("target_group", {}).get("target_group_key")) if isinstance(readiness_pack.get("target_group"), dict) else None,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"live-integration-candidate-pack-{digest[:24]}"



def _readiness_review_item_id(journal_doc: dict) -> str:
    journal_id = _normalize_text(journal_doc.get("dry_run_harness_result_journal_id")) or "unknown"
    digest = hashlib.sha256(f"promotion-readiness:{journal_id}".encode("utf-8")).hexdigest()
    return f"promotion-readiness-review-{digest[:24]}"



def _candidate_review_item_id(readiness_pack: dict) -> str:
    readiness_id = _normalize_text(readiness_pack.get("target_group_promotion_readiness_pack_id")) or "unknown"
    digest = hashlib.sha256(f"live-integration-candidate:{readiness_id}".encode("utf-8")).hexdigest()
    return f"live-integration-candidate-review-{digest[:24]}"



def _readiness_ref(pack_id: str) -> str:
    return f"target-group-promotion-readiness-pack://{pack_id}"



def _candidate_ref(pack_id: str) -> str:
    return f"live-integration-candidate-pack://{pack_id}"



def _comparison_index(comparison_doc: dict) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for item in comparison_doc.get("packs") or []:
        if not isinstance(item, dict):
            continue
        key = _normalize_text(item.get("replayable_dry_run_orchestration_pack_id"))
        if key:
            index[key] = redact_sensitive_fields(dict(item))
    return index



def _build_target_group_promotion_readiness_pack(journal_doc: dict, comparison_pack: dict) -> dict:
    pack_id = derive_target_group_promotion_readiness_pack_id(journal_doc)
    result_entries = [item for item in journal_doc.get("result_entries") or [] if isinstance(item, dict)]
    comparison_items = [item for item in comparison_pack.get("comparison_items") or [] if isinstance(item, dict)]
    execution_outcome_counts: dict[str, int] = {}
    for item in result_entries:
        key = _normalize_text(item.get("execution_outcome")) or "unknown"
        execution_outcome_counts[key] = execution_outcome_counts.get(key, 0) + 1
    comparison_outcome_counts: dict[str, int] = {}
    for item in comparison_items:
        key = _normalize_text(item.get("comparison_outcome")) or "unknown"
        comparison_outcome_counts[key] = comparison_outcome_counts.get(key, 0) + 1
    mismatched_step_ids = comparison_pack.get("comparison_summary", {}).get("mismatched_step_ids") or []
    missing_result_step_ids = comparison_pack.get("comparison_summary", {}).get("missing_result_step_ids") or []
    ready = bool(result_entries) and not mismatched_step_ids and not missing_result_step_ids
    readiness_status = "promotion_ready" if ready else "review_required"
    return redact_sensitive_fields(
        {
            "schema_version": TARGET_GROUP_PROMOTION_READINESS_PACKS_SCHEMA_VERSION,
            "target_group_promotion_readiness_pack_id": pack_id,
            "target_group_promotion_readiness_pack_ref": _readiness_ref(pack_id),
            "state": "promotion-readiness-assessed",
            "readiness_status": readiness_status,
            "dry_run_harness_result_journal_id": journal_doc.get("dry_run_harness_result_journal_id"),
            "replay_outcome_comparison_pack_id": comparison_pack.get("replay_outcome_comparison_pack_id"),
            "replayable_dry_run_orchestration_pack_id": journal_doc.get("replayable_dry_run_orchestration_pack_id"),
            "target_group": journal_doc.get("target_group"),
            "target": journal_doc.get("target"),
            "harness_group": journal_doc.get("harness_group"),
            "adapter_entrypoint": journal_doc.get("adapter_entrypoint"),
            "promotion_gate": {
                "comparison_clean": not mismatched_step_ids and not missing_result_step_ids,
                "result_entry_count": len(result_entries),
                "comparison_item_count": len(comparison_items),
                "execution_outcome_counts": execution_outcome_counts,
                "comparison_outcome_counts": comparison_outcome_counts,
                "mismatched_step_ids": mismatched_step_ids,
                "missing_result_step_ids": missing_result_step_ids,
            },
            "promotion_controls": {
                "requires_manual_live_enablement": True,
                "allows_live_execute": False,
                "ready_for_live_integration_candidate": ready,
            },
            "audit": {
                "created_at": utcnow_iso(),
                "source_stage": "replay-outcome-comparison-pack",
            },
        }
    )



def build_target_group_promotion_readiness_pack_artifacts(journals_doc: dict, comparison_doc: dict) -> tuple[dict, dict, dict]:
    comparison_index = _comparison_index(comparison_doc)
    packs: list[dict] = []
    review_items: list[dict] = []

    for journal_doc in journals_doc.get("journals") or []:
        if not isinstance(journal_doc, dict):
            continue
        pack_key = _normalize_text(journal_doc.get("replayable_dry_run_orchestration_pack_id"))
        comparison_pack = comparison_index.get(pack_key or "")
        if not comparison_pack:
            review_items.append(
                redact_sensitive_fields(
                    {
                        "schema_version": TARGET_GROUP_PROMOTION_READINESS_REVIEW_QUEUE_SCHEMA_VERSION,
                        "queue_item_id": _readiness_review_item_id(journal_doc),
                        "state": "open",
                        "priority": "high",
                        "review_type": "target-group-promotion-readiness",
                        "dry_run_harness_result_journal_id": journal_doc.get("dry_run_harness_result_journal_id"),
                        "reason_codes": ["no_replay_outcome_comparison_pack_found"],
                        "journal_summary": redact_sensitive_fields(journal_doc),
                    }
                )
            )
            continue
        pack = _build_target_group_promotion_readiness_pack(journal_doc, comparison_pack)
        if pack.get("readiness_status") != "promotion_ready":
            review_items.append(
                redact_sensitive_fields(
                    {
                        "schema_version": TARGET_GROUP_PROMOTION_READINESS_REVIEW_QUEUE_SCHEMA_VERSION,
                        "queue_item_id": _readiness_review_item_id(journal_doc),
                        "state": "open",
                        "priority": "medium",
                        "review_type": "target-group-promotion-readiness",
                        "dry_run_harness_result_journal_id": journal_doc.get("dry_run_harness_result_journal_id"),
                        "reason_codes": ["promotion_gate_not_clean"],
                        "promotion_gate": pack.get("promotion_gate"),
                    }
                )
            )
        packs.append(pack)

    packs_doc = redact_sensitive_fields(
        {
            "schema_version": TARGET_GROUP_PROMOTION_READINESS_PACKS_SCHEMA_VERSION,
            "pack_count": len(packs),
            "packs": packs,
            "generated_at": utcnow_iso(),
        }
    )
    review_queue = redact_sensitive_fields(
        {
            "schema_version": TARGET_GROUP_PROMOTION_READINESS_REVIEW_QUEUE_SCHEMA_VERSION,
            "item_count": len(review_items),
            "items": review_items,
            "generated_at": utcnow_iso(),
        }
    )
    readiness_status_counts: dict[str, int] = {}
    for pack in packs:
        key = _normalize_text(pack.get("readiness_status")) or "unknown"
        readiness_status_counts[key] = readiness_status_counts.get(key, 0) + 1
    rollup = redact_sensitive_fields(
        {
            "schema_version": TARGET_GROUP_PROMOTION_READINESS_ROLLUP_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "pack_count": len(packs),
            "review_queue_count": len(review_items),
            "readiness_status_counts": readiness_status_counts,
        }
    )
    return packs_doc, review_queue, rollup



def _build_live_integration_candidate_pack(readiness_pack: dict) -> dict:
    pack_id = derive_live_integration_candidate_pack_id(readiness_pack)
    target_group = readiness_pack.get("target_group") if isinstance(readiness_pack.get("target_group"), dict) else {}
    target = readiness_pack.get("target") if isinstance(readiness_pack.get("target"), dict) else {}
    return redact_sensitive_fields(
        {
            "schema_version": LIVE_INTEGRATION_CANDIDATE_PACKS_SCHEMA_VERSION,
            "live_integration_candidate_pack_id": pack_id,
            "live_integration_candidate_pack_ref": _candidate_ref(pack_id),
            "state": "candidate-prepared",
            "candidate_status": "ready_for_live_integration",
            "target_group_promotion_readiness_pack_id": readiness_pack.get("target_group_promotion_readiness_pack_id"),
            "target_group": target_group,
            "target": target,
            "candidate_controls": {
                "requires_manual_enablement": True,
                "live_execute_enabled": False,
                "approved_for_offline_replay": True,
                "approved_for_live_system_calls": False,
            },
            "candidate_checklist": [
                "review promotion gate summary",
                "confirm downstream credentials and access separately",
                "enable live execution only through an explicit future milestone gate",
            ],
            "audit": {
                "created_at": utcnow_iso(),
                "source_stage": "target-group-promotion-readiness-pack",
            },
        }
    )



def build_live_integration_candidate_pack_artifacts(readiness_doc: dict) -> tuple[dict, dict, dict]:
    packs: list[dict] = []
    review_items: list[dict] = []

    for readiness_pack in readiness_doc.get("packs") or []:
        if not isinstance(readiness_pack, dict):
            continue
        if _normalize_text(readiness_pack.get("readiness_status")) != "promotion_ready":
            review_items.append(
                redact_sensitive_fields(
                    {
                        "schema_version": LIVE_INTEGRATION_CANDIDATE_REVIEW_QUEUE_SCHEMA_VERSION,
                        "queue_item_id": _candidate_review_item_id(readiness_pack),
                        "state": "open",
                        "priority": "medium",
                        "review_type": "live-integration-candidate-pack",
                        "target_group_promotion_readiness_pack_id": readiness_pack.get("target_group_promotion_readiness_pack_id"),
                        "reason_codes": ["promotion_readiness_not_met"],
                        "readiness_summary": readiness_pack.get("promotion_gate"),
                    }
                )
            )
            continue
        packs.append(_build_live_integration_candidate_pack(readiness_pack))

    packs_doc = redact_sensitive_fields(
        {
            "schema_version": LIVE_INTEGRATION_CANDIDATE_PACKS_SCHEMA_VERSION,
            "pack_count": len(packs),
            "packs": packs,
            "generated_at": utcnow_iso(),
        }
    )
    review_queue = redact_sensitive_fields(
        {
            "schema_version": LIVE_INTEGRATION_CANDIDATE_REVIEW_QUEUE_SCHEMA_VERSION,
            "item_count": len(review_items),
            "items": review_items,
            "generated_at": utcnow_iso(),
        }
    )
    candidate_status_counts: dict[str, int] = {}
    for pack in packs:
        key = _normalize_text(pack.get("candidate_status")) or "unknown"
        candidate_status_counts[key] = candidate_status_counts.get(key, 0) + 1
    rollup = redact_sensitive_fields(
        {
            "schema_version": LIVE_INTEGRATION_CANDIDATE_ROLLUP_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "pack_count": len(packs),
            "review_queue_count": len(review_items),
            "candidate_status_counts": candidate_status_counts,
        }
    )
    return packs_doc, review_queue, rollup



def render_target_group_promotion_readiness_packs_markdown(packs_doc: dict) -> str:
    lines = ["# Target-Group Promotion Readiness Packs", ""]
    lines.append(f"Pack count: {packs_doc.get('pack_count', 0)}")
    lines.append("")
    for item in packs_doc.get("packs") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('target_group_promotion_readiness_pack_id')}` :: {item.get('readiness_status')}")
    return "\n".join(lines) + "\n"



def render_target_group_promotion_readiness_review_queue_markdown(review_queue: dict) -> str:
    lines = ["# Target-Group Promotion Readiness Review Queue", ""]
    lines.append(f"Open items: {review_queue.get('item_count', 0)}")
    lines.append("")
    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('queue_item_id')}` :: {', '.join(item.get('reason_codes') or [])}")
    return "\n".join(lines) + "\n"



def render_target_group_promotion_readiness_rollup_markdown(rollup: dict) -> str:
    lines = ["# Target-Group Promotion Readiness Rollup", ""]
    lines.append(f"Pack count: {rollup.get('pack_count', 0)}")
    lines.append(f"Review queue count: {rollup.get('review_queue_count', 0)}")
    lines.append("")
    for key, value in sorted((rollup.get("readiness_status_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"



def render_live_integration_candidate_packs_markdown(packs_doc: dict) -> str:
    lines = ["# Live Integration Candidate Packs", ""]
    lines.append(f"Pack count: {packs_doc.get('pack_count', 0)}")
    lines.append("")
    for item in packs_doc.get("packs") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('live_integration_candidate_pack_id')}` :: {item.get('candidate_status')}")
    return "\n".join(lines) + "\n"



def render_live_integration_candidate_review_queue_markdown(review_queue: dict) -> str:
    lines = ["# Live Integration Candidate Review Queue", ""]
    lines.append(f"Open items: {review_queue.get('item_count', 0)}")
    lines.append("")
    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('queue_item_id')}` :: {', '.join(item.get('reason_codes') or [])}")
    return "\n".join(lines) + "\n"



def render_live_integration_candidate_rollup_markdown(rollup: dict) -> str:
    lines = ["# Live Integration Candidate Rollup", ""]
    lines.append(f"Pack count: {rollup.get('pack_count', 0)}")
    lines.append(f"Review queue count: {rollup.get('review_queue_count', 0)}")
    lines.append("")
    for key, value in sorted((rollup.get("candidate_status_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"
