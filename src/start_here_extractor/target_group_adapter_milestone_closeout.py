from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .ingestion import utcnow_iso
from .security import redact_sensitive_fields

M5C_CLOSEOUT_PACKS_SCHEMA_VERSION = "1.0"
M5C_CLOSEOUT_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
M5C_CLOSEOUT_ROLLUP_SCHEMA_VERSION = "1.0"
MILESTONE5_COMPLETION_PACKS_SCHEMA_VERSION = "1.0"
MILESTONE5_COMPLETION_REVIEW_QUEUE_SCHEMA_VERSION = "1.0"
MILESTONE5_COMPLETION_ROLLUP_SCHEMA_VERSION = "1.0"


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def load_target_group_promotion_readiness_packs(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Target-group promotion readiness packs payload must be a JSON object")


def load_live_integration_candidate_packs(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("Live integration candidate packs payload must be a JSON object")


def load_m5c_closeout_packs(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("M5C closeout packs payload must be a JSON object")


def load_m5c_closeout_review_queue(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return redact_sensitive_fields(payload)
    raise ValueError("M5C closeout review queue payload must be a JSON object")


def derive_m5c_closeout_pack_id(readiness_pack: dict, candidate_pack: dict) -> str:
    payload = {
        "target_group_promotion_readiness_pack_id": _normalize_text(readiness_pack.get("target_group_promotion_readiness_pack_id")),
        "live_integration_candidate_pack_id": _normalize_text(candidate_pack.get("live_integration_candidate_pack_id")),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"m5c-closeout-pack-{digest[:24]}"


def derive_milestone5_completion_pack_id(closeout_doc: dict) -> str:
    payload = {
        "pack_ids": sorted(
            _normalize_text(item.get("m5c_closeout_pack_id"))
            for item in closeout_doc.get("packs") or []
            if isinstance(item, dict) and _normalize_text(item.get("m5c_closeout_pack_id"))
        )
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"milestone5-completion-pack-{digest[:24]}"


def _closeout_review_item_id(readiness_pack: dict) -> str:
    pack_id = _normalize_text(readiness_pack.get("target_group_promotion_readiness_pack_id")) or "unknown"
    digest = hashlib.sha256(f"m5c-closeout:{pack_id}".encode("utf-8")).hexdigest()
    return f"m5c-closeout-review-{digest[:24]}"


def _completion_review_item_id(closeout_doc: dict) -> str:
    digest = hashlib.sha256(derive_milestone5_completion_pack_id(closeout_doc).encode("utf-8")).hexdigest()
    return f"milestone5-completion-review-{digest[:24]}"


def _closeout_ref(pack_id: str) -> str:
    return f"m5c-closeout-pack://{pack_id}"


def _completion_ref(pack_id: str) -> str:
    return f"milestone5-completion-pack://{pack_id}"


def _candidate_index(candidate_doc: dict) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for item in candidate_doc.get("packs") or []:
        if not isinstance(item, dict):
            continue
        key = _normalize_text(item.get("target_group_promotion_readiness_pack_id"))
        if key:
            index[key] = redact_sensitive_fields(dict(item))
    return index


def _build_m5c_closeout_pack(readiness_pack: dict, candidate_pack: dict) -> dict:
    pack_id = derive_m5c_closeout_pack_id(readiness_pack, candidate_pack)
    promotion_gate = readiness_pack.get("promotion_gate") if isinstance(readiness_pack.get("promotion_gate"), dict) else {}
    comparison_clean = bool(promotion_gate.get("comparison_clean"))
    candidate_ready = _normalize_text(candidate_pack.get("candidate_status")) == "ready_for_live_integration"
    closeout_complete = _normalize_text(readiness_pack.get("readiness_status")) == "promotion_ready" and candidate_ready and comparison_clean
    closeout_status = "m5c_complete" if closeout_complete else "review_required"
    return redact_sensitive_fields(
        {
            "schema_version": M5C_CLOSEOUT_PACKS_SCHEMA_VERSION,
            "m5c_closeout_pack_id": pack_id,
            "m5c_closeout_pack_ref": _closeout_ref(pack_id),
            "state": "m5c-closeout-packaged",
            "closeout_status": closeout_status,
            "target_group_promotion_readiness_pack_id": readiness_pack.get("target_group_promotion_readiness_pack_id"),
            "live_integration_candidate_pack_id": candidate_pack.get("live_integration_candidate_pack_id"),
            "target_group": readiness_pack.get("target_group"),
            "target": readiness_pack.get("target"),
            "promotion_gate": promotion_gate,
            "candidate_controls": candidate_pack.get("candidate_controls"),
            "closeout_gate": {
                "promotion_ready": _normalize_text(readiness_pack.get("readiness_status")) == "promotion_ready",
                "candidate_ready": candidate_ready,
                "comparison_clean": comparison_clean,
                "ready_for_m5c_completion": closeout_complete,
            },
            "milestone_controls": {
                "m5a_complete": True,
                "m5b_complete": True,
                "m5c_complete": closeout_complete,
                "allows_live_execute": False,
            },
            "audit": {
                "created_at": utcnow_iso(),
                "source_stage": "live-integration-candidate-pack",
            },
        }
    )


def build_m5c_closeout_pack_artifacts(readiness_doc: dict, candidate_doc: dict) -> tuple[dict, dict, dict]:
    candidate_index = _candidate_index(candidate_doc)
    packs: list[dict] = []
    review_items: list[dict] = []

    for readiness_pack in readiness_doc.get("packs") or []:
        if not isinstance(readiness_pack, dict):
            continue
        readiness_id = _normalize_text(readiness_pack.get("target_group_promotion_readiness_pack_id"))
        candidate_pack = candidate_index.get(readiness_id or "")
        if not candidate_pack:
            review_items.append(
                redact_sensitive_fields(
                    {
                        "schema_version": M5C_CLOSEOUT_REVIEW_QUEUE_SCHEMA_VERSION,
                        "queue_item_id": _closeout_review_item_id(readiness_pack),
                        "state": "open",
                        "priority": "high",
                        "review_type": "m5c-closeout",
                        "target_group_promotion_readiness_pack_id": readiness_pack.get("target_group_promotion_readiness_pack_id"),
                        "reason_codes": ["no_live_integration_candidate_pack_found"],
                        "readiness_summary": redact_sensitive_fields(readiness_pack),
                    }
                )
            )
            continue
        pack = _build_m5c_closeout_pack(readiness_pack, candidate_pack)
        if pack.get("closeout_status") != "m5c_complete":
            review_items.append(
                redact_sensitive_fields(
                    {
                        "schema_version": M5C_CLOSEOUT_REVIEW_QUEUE_SCHEMA_VERSION,
                        "queue_item_id": _closeout_review_item_id(readiness_pack),
                        "state": "open",
                        "priority": "medium",
                        "review_type": "m5c-closeout",
                        "target_group_promotion_readiness_pack_id": readiness_pack.get("target_group_promotion_readiness_pack_id"),
                        "reason_codes": ["m5c_closeout_gate_not_clean"],
                        "closeout_gate": pack.get("closeout_gate"),
                    }
                )
            )
        packs.append(pack)

    packs_doc = redact_sensitive_fields(
        {
            "schema_version": M5C_CLOSEOUT_PACKS_SCHEMA_VERSION,
            "pack_count": len(packs),
            "packs": packs,
            "generated_at": utcnow_iso(),
        }
    )
    review_queue = redact_sensitive_fields(
        {
            "schema_version": M5C_CLOSEOUT_REVIEW_QUEUE_SCHEMA_VERSION,
            "item_count": len(review_items),
            "items": review_items,
            "generated_at": utcnow_iso(),
        }
    )
    closeout_status_counts: dict[str, int] = {}
    for pack in packs:
        key = _normalize_text(pack.get("closeout_status")) or "unknown"
        closeout_status_counts[key] = closeout_status_counts.get(key, 0) + 1
    rollup = redact_sensitive_fields(
        {
            "schema_version": M5C_CLOSEOUT_ROLLUP_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "pack_count": len(packs),
            "review_queue_count": len(review_items),
            "closeout_status_counts": closeout_status_counts,
        }
    )
    return packs_doc, review_queue, rollup


def _build_milestone5_completion_pack(closeout_doc: dict, closeout_review_queue: dict) -> dict:
    pack_id = derive_milestone5_completion_pack_id(closeout_doc)
    closeout_packs = [item for item in closeout_doc.get("packs") or [] if isinstance(item, dict)]
    closeout_status_counts: dict[str, int] = {}
    for item in closeout_packs:
        key = _normalize_text(item.get("closeout_status")) or "unknown"
        closeout_status_counts[key] = closeout_status_counts.get(key, 0) + 1
    completion_ready = bool(closeout_packs) and closeout_review_queue.get("item_count", 0) == 0 and set(closeout_status_counts) <= {"m5c_complete"}
    completion_status = "milestone5_complete" if completion_ready else "review_required"
    return redact_sensitive_fields(
        {
            "schema_version": MILESTONE5_COMPLETION_PACKS_SCHEMA_VERSION,
            "milestone5_completion_pack_id": pack_id,
            "milestone5_completion_pack_ref": _completion_ref(pack_id),
            "state": "milestone5-completion-assessed",
            "completion_status": completion_status,
            "milestone_status": {
                "m5a_complete": True,
                "m5b_complete": True,
                "m5c_complete": completion_ready,
                "closeout_pack_count": len(closeout_packs),
                "closeout_review_queue_count": closeout_review_queue.get("item_count", 0),
            },
            "closeout_status_counts": closeout_status_counts,
            "completion_controls": {
                "ready_for_milestone5_closeout": completion_ready,
                "requires_manual_live_enablement": True,
                "allows_live_execute": False,
            },
            "audit": {
                "created_at": utcnow_iso(),
                "source_stage": "m5c-closeout-pack",
            },
        }
    )


def build_milestone5_completion_pack_artifacts(closeout_doc: dict, closeout_review_queue: dict) -> tuple[dict, dict, dict]:
    pack = _build_milestone5_completion_pack(closeout_doc, closeout_review_queue)
    review_items: list[dict] = []
    if pack.get("completion_status") != "milestone5_complete":
        review_items.append(
            redact_sensitive_fields(
                {
                    "schema_version": MILESTONE5_COMPLETION_REVIEW_QUEUE_SCHEMA_VERSION,
                    "queue_item_id": _completion_review_item_id(closeout_doc),
                    "state": "open",
                    "priority": "high",
                    "review_type": "milestone5-completion",
                    "reason_codes": ["milestone5_completion_gate_not_clean"],
                    "milestone_status": pack.get("milestone_status"),
                }
            )
        )
    packs_doc = redact_sensitive_fields(
        {
            "schema_version": MILESTONE5_COMPLETION_PACKS_SCHEMA_VERSION,
            "pack_count": 1,
            "packs": [pack],
            "generated_at": utcnow_iso(),
        }
    )
    review_queue = redact_sensitive_fields(
        {
            "schema_version": MILESTONE5_COMPLETION_REVIEW_QUEUE_SCHEMA_VERSION,
            "item_count": len(review_items),
            "items": review_items,
            "generated_at": utcnow_iso(),
        }
    )
    completion_status = _normalize_text(pack.get("completion_status")) or "unknown"
    rollup = redact_sensitive_fields(
        {
            "schema_version": MILESTONE5_COMPLETION_ROLLUP_SCHEMA_VERSION,
            "generated_at": utcnow_iso(),
            "pack_count": 1,
            "review_queue_count": len(review_items),
            "completion_status_counts": {completion_status: 1},
        }
    )
    return packs_doc, review_queue, rollup


def render_m5c_closeout_packs_markdown(packs_doc: dict) -> str:
    lines = ["# M5C Closeout Packs", ""]
    lines.append(f"Pack count: {packs_doc.get('pack_count', 0)}")
    lines.append("")
    for item in packs_doc.get("packs") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('m5c_closeout_pack_id')}` :: {item.get('closeout_status')}")
    return "\n".join(lines) + "\n"


def render_m5c_closeout_review_queue_markdown(review_queue: dict) -> str:
    lines = ["# M5C Closeout Review Queue", ""]
    lines.append(f"Open items: {review_queue.get('item_count', 0)}")
    lines.append("")
    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('queue_item_id')}` :: {', '.join(item.get('reason_codes') or [])}")
    return "\n".join(lines) + "\n"


def render_m5c_closeout_rollup_markdown(rollup: dict) -> str:
    lines = ["# M5C Closeout Rollup", ""]
    lines.append(f"Pack count: {rollup.get('pack_count', 0)}")
    lines.append(f"Review queue count: {rollup.get('review_queue_count', 0)}")
    lines.append("")
    for key, value in sorted((rollup.get("closeout_status_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"


def render_milestone5_completion_packs_markdown(packs_doc: dict) -> str:
    lines = ["# Milestone 5 Completion Packs", ""]
    lines.append(f"Pack count: {packs_doc.get('pack_count', 0)}")
    lines.append("")
    for item in packs_doc.get("packs") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('milestone5_completion_pack_id')}` :: {item.get('completion_status')}")
    return "\n".join(lines) + "\n"


def render_milestone5_completion_review_queue_markdown(review_queue: dict) -> str:
    lines = ["# Milestone 5 Completion Review Queue", ""]
    lines.append(f"Open items: {review_queue.get('item_count', 0)}")
    lines.append("")
    for item in review_queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('queue_item_id')}` :: {', '.join(item.get('reason_codes') or [])}")
    return "\n".join(lines) + "\n"


def render_milestone5_completion_rollup_markdown(rollup: dict) -> str:
    lines = ["# Milestone 5 Completion Rollup", ""]
    lines.append(f"Pack count: {rollup.get('pack_count', 0)}")
    lines.append(f"Review queue count: {rollup.get('review_queue_count', 0)}")
    lines.append("")
    for key, value in sorted((rollup.get("completion_status_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"
