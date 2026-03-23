from __future__ import annotations

import html
import json
from pathlib import Path

from .source_replay_execution import (
    SOURCE_REPLAY_EXECUTION_SCHEMA_VERSION,
)

OPERATOR_CONSOLE_ALPHA_SCHEMA_VERSION = SOURCE_REPLAY_EXECUTION_SCHEMA_VERSION


def load_execution_documents(execution_dir: str | Path) -> dict[str, dict]:
    path = Path(execution_dir)
    names = {
        "source_replay_execution_packs": "source_replay_execution_packs.json",
        "source_replay_execution_review_queue": "source_replay_execution_review_queue.json",
        "source_replay_execution_rollup": "source_replay_execution_rollup.json",
    }
    payloads: dict[str, dict] = {}
    for key, filename in names.items():
        file_path = path / filename
        if file_path.exists():
            payloads[key] = json.loads(file_path.read_text(encoding="utf-8"))
        else:
            payloads[key] = {"records": []}
    return payloads


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
STAGE_ORDER = {
    "execution-review": 0,
    "approval-review": 1,
    "compare-review": 2,
    "execution-ready": 3,
    "approved": 4,
    "compared": 5,
    "planned": 6,
    "completed-no-op": 7,
    "rejected": 8,
    "unknown": 9,
}


def _safe_records(document: dict[str, dict], key: str) -> list[dict]:
    records = document.get(key, {}).get("records")
    return list(records) if isinstance(records, list) else []


def _map_by_source_key(records: list[dict]) -> dict[str, dict]:
    payload: dict[str, dict] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        source_key = _normalize_text(record.get("source_key"))
        if source_key:
            payload[source_key] = record
    return payload


def _list_by_source_key(records: list[dict]) -> dict[str, list[dict]]:
    payload: dict[str, list[dict]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        source_key = _normalize_text(record.get("source_key"))
        if source_key:
            payload.setdefault(source_key, []).append(record)
    return payload


def _append_unique(target: list[str], value: str) -> None:
    if value not in target:
        target.append(value)


def _priority_rank(value: str | None) -> int:
    return PRIORITY_ORDER.get((value or "unknown").lower(), PRIORITY_ORDER["unknown"])


def _stage_rank(value: str | None) -> int:
    return STAGE_ORDER.get((value or "unknown").lower(), STAGE_ORDER["unknown"])


def _derive_current_stage(
    *,
    compare_review: list[dict],
    approval_queue: list[dict],
    execution_review: list[dict],
    execution_status: str | None,
    approval_status: str | None,
    compare_outcome: str | None,
    replay_mode: str | None,
    has_plan: bool,
) -> str:
    if execution_review:
        return "execution-review"
    if execution_status == "ready-for-dry-run":
        return "execution-ready"
    if execution_status == "not-required":
        return "completed-no-op"
    if approval_queue:
        return "approval-review"
    if approval_status == "approved":
        return "approved"
    if approval_status == "rejected":
        return "rejected"
    if compare_review:
        return "compare-review"
    if compare_outcome:
        return "compared"
    if replay_mode and has_plan:
        return "planned"
    return "unknown"


def _record_summary_line(*, stage: str, replay_mode: str, compare_outcome: str | None, approval_status: str | None, execution_status: str | None) -> str:
    parts = [f"Stage: {stage}", f"Replay Mode: {replay_mode}"]
    if compare_outcome:
        parts.append(f"Compare: {compare_outcome}")
    if approval_status:
        parts.append(f"Approval: {approval_status}")
    if execution_status:
        parts.append(f"Execution: {execution_status}")
    return " • ".join(parts)


def _select_summary(item: dict) -> str | None:
    for key in (
        "review_summary",
        "comparison_summary",
        "approval_summary",
        "execution_summary",
        "proposed_action",
        "decision_reason",
        "notes",
    ):
        value = _normalize_text(item.get(key))
        if value:
            return value
    return None


def _make_review_items(
    *,
    stage: str,
    records: list[dict],
    plan_map: dict[str, dict],
    compare_map: dict[str, dict],
    approval_map: dict[str, dict],
    execution_map: dict[str, dict],
) -> list[dict]:
    items: list[dict] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        source_key = (
            _normalize_text(record.get("source_key"))
            or _normalize_text(record.get("source_ref"))
            or "unknown"
        )
        plan = plan_map.get(source_key, {})
        compare = compare_map.get(source_key, {})
        approval = approval_map.get(source_key, {})
        execution = execution_map.get(source_key, {})
        replay_mode = (
            _normalize_text(record.get("replay_mode"))
            or _normalize_text(execution.get("replay_mode"))
            or _normalize_text(approval.get("replay_mode"))
            or _normalize_text(compare.get("replay_mode"))
            or _normalize_text(plan.get("replay_mode"))
            or "unknown"
        )
        source_system = (
            _normalize_text(record.get("source_system"))
            or _normalize_text(execution.get("source_system"))
            or _normalize_text(approval.get("source_system"))
            or _normalize_text(compare.get("source_system"))
            or _normalize_text(plan.get("source_system"))
            or "unknown"
        )
        reason_codes = []
        for reason in record.get("reason_codes") or []:
            if isinstance(reason, str):
                _append_unique(reason_codes, reason)
        items.append(
            {
                "review_stage": stage,
                "review_item_id": _normalize_text(record.get("review_item_id")) or f"{stage}-{source_key}",
                "source_key": source_key,
                "source_system": source_system,
                "replay_mode": replay_mode,
                "priority": _normalize_text(record.get("priority")) or "unknown",
                "reason_codes": reason_codes,
                "summary": _select_summary(record) or f"{stage} review required",
                "detail": record,
            }
        )
    return items



def _top_reason_counts(review_items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in review_items:
        for reason in item.get("reason_codes") or []:
            if isinstance(reason, str):
                counts[reason] = counts.get(reason, 0) + 1
    return counts


def _build_warnings(*, records: list[dict], review_items: list[dict]) -> list[dict]:
    warnings: list[dict] = []
    review_count = len(review_items)
    high_priority = sum(1 for item in review_items if (item.get("priority") or "unknown") == "high")
    unknown_stage = sum(1 for item in records if item.get("current_stage") == "unknown")
    missing_compare = sum(1 for item in records if not item.get("detail", {}).get("compare"))
    missing_execution = sum(1 for item in records if not item.get("detail", {}).get("execution"))

    if review_count:
        warnings.append(
            {
                "level": "warning",
                "code": "review_backlog_present",
                "title": "Review backlog present",
                "message": f"{review_count} review item(s) remain in plan, compare, approval, or execution queues.",
            }
        )
    if high_priority:
        warnings.append(
            {
                "level": "danger",
                "code": "high_priority_review_backlog",
                "title": "High-priority review items",
                "message": f"{high_priority} high-priority review item(s) need operator attention.",
            }
        )
    if unknown_stage:
        warnings.append(
            {
                "level": "warning",
                "code": "unknown_stage_records",
                "title": "Unknown workflow stage detected",
                "message": f"{unknown_stage} source record(s) could not be mapped to a known replay stage.",
            }
        )
    if missing_compare:
        warnings.append(
            {
                "level": "info",
                "code": "missing_compare_records",
                "title": "Comparison data missing for some sources",
                "message": f"{missing_compare} source record(s) have planning data but no comparison payload yet.",
            }
        )
    if missing_execution:
        warnings.append(
            {
                "level": "info",
                "code": "missing_execution_records",
                "title": "Execution data missing for some sources",
                "message": f"{missing_execution} source record(s) do not yet have execution pack data.",
            }
        )
    return warnings


def build_operator_console_alpha_artifacts(
    *args: dict[str, dict],
    plan_documents: dict[str, dict] | None = None,
    compare_documents: dict[str, dict] | None = None,
    approval_documents: dict[str, dict] | None = None,
    execution_documents: dict[str, dict] | None = None,
    title: str = "Source Replay Operator Console Alpha",
    subtitle: str = "Read-only operator console for replay planning, comparison, approval, and execution triage.",
) -> dict[str, dict]:
    if args:
        if len(args) == 4:
            plan_documents, compare_documents, approval_documents, execution_documents = args
        else:
            raise TypeError(
                "build_operator_console_alpha_artifacts expected 4 document arguments in plan/compare/approval/execution order"
            )

    if (
        plan_documents is None
        or compare_documents is None
        or approval_documents is None
        or execution_documents is None
    ):
        raise TypeError(
            "build_operator_console_alpha_artifacts requires plan, compare, approval, and execution documents"
        )

    plan_records = _safe_records(plan_documents, "source_replay_plan_packs")
    plan_review_records = _safe_records(plan_documents, "source_replay_plan_review_queue")
    compare_records = _safe_records(compare_documents, "source_replay_compare_packs")
    compare_review_records = _safe_records(compare_documents, "source_replay_compare_review_queue")
    approval_journal_records = _safe_records(approval_documents, "source_replay_approval_journal")
    approval_queue_records = _safe_records(approval_documents, "source_replay_approval_queue")
    execution_records = _safe_records(execution_documents, "source_replay_execution_packs")
    execution_review_records = _safe_records(execution_documents, "source_replay_execution_review_queue")

    plan_map = _map_by_source_key(plan_records)
    compare_map = _map_by_source_key(compare_records)
    approval_map = _map_by_source_key(approval_journal_records)
    execution_map = _map_by_source_key(execution_records)

    plan_review_map = _list_by_source_key(plan_review_records)
    compare_review_map = _list_by_source_key(compare_review_records)
    approval_queue_map = _list_by_source_key(approval_queue_records)
    execution_review_map = _list_by_source_key(execution_review_records)

    source_keys = sorted(
        {
            *plan_map.keys(),
            *compare_map.keys(),
            *approval_map.keys(),
            *execution_map.keys(),
            *plan_review_map.keys(),
            *compare_review_map.keys(),
            *approval_queue_map.keys(),
            *execution_review_map.keys(),
        }
    )

    review_items = []
    review_items.extend(
        _make_review_items(
            stage="plan-review",
            records=plan_review_records,
            plan_map=plan_map,
            compare_map=compare_map,
            approval_map=approval_map,
            execution_map=execution_map,
        )
    )
    review_items.extend(
        _make_review_items(
            stage="compare-review",
            records=compare_review_records,
            plan_map=plan_map,
            compare_map=compare_map,
            approval_map=approval_map,
            execution_map=execution_map,
        )
    )
    review_items.extend(
        _make_review_items(
            stage="approval-review",
            records=approval_queue_records,
            plan_map=plan_map,
            compare_map=compare_map,
            approval_map=approval_map,
            execution_map=execution_map,
        )
    )
    review_items.extend(
        _make_review_items(
            stage="execution-review",
            records=execution_review_records,
            plan_map=plan_map,
            compare_map=compare_map,
            approval_map=approval_map,
            execution_map=execution_map,
        )
    )
    review_items = sorted(
        review_items,
        key=lambda item: (
            _priority_rank(item.get("priority")),
            _stage_rank(item.get("review_stage")),
            str(item.get("source_key") or ""),
        ),
    )

    review_items_by_source: dict[str, list[dict]] = {}
    for item in review_items:
        source_key = item.get("source_key") or "unknown"
        review_items_by_source.setdefault(source_key, []).append(item)

    records: list[dict] = []
    current_stage_counts: dict[str, int] = {}
    replay_mode_counts: dict[str, int] = {}
    source_system_counts: dict[str, int] = {}
    source_entity_type_counts: dict[str, int] = {}
    migration_profile_counts: dict[str, int] = {}
    compare_outcome_counts: dict[str, int] = {}
    approval_status_counts: dict[str, int] = {}
    execution_status_counts: dict[str, int] = {}
    review_item_stage_counts: dict[str, int] = {}
    review_priority_counts: dict[str, int] = {}

    for source_key in source_keys:
        plan = plan_map.get(source_key, {})
        compare = compare_map.get(source_key, {})
        approval = approval_map.get(source_key, {})
        execution = execution_map.get(source_key, {})
        plan_review = plan_review_map.get(source_key, [])
        compare_review = compare_review_map.get(source_key, [])
        approval_queue = approval_queue_map.get(source_key, [])
        execution_review = execution_review_map.get(source_key, [])
        source_review_items = review_items_by_source.get(source_key, [])

        replay_mode = (
            _normalize_text(execution.get("replay_mode"))
            or _normalize_text(approval.get("replay_mode"))
            or _normalize_text(compare.get("replay_mode"))
            or _normalize_text(plan.get("replay_mode"))
            or "unknown"
        )
        source_system = (
            _normalize_text(execution.get("source_system"))
            or _normalize_text(approval.get("source_system"))
            or _normalize_text(compare.get("source_system"))
            or _normalize_text(plan.get("source_system"))
            or "unknown"
        )
        source_entity_type = (
            _normalize_text(execution.get("source_entity_type"))
            or _normalize_text(approval.get("source_entity_type"))
            or _normalize_text(compare.get("source_entity_type"))
            or _normalize_text(plan.get("source_entity_type"))
            or "unknown"
        )
        migration_profile = (
            _normalize_text(execution.get("migration_profile"))
            or _normalize_text(approval.get("migration_profile"))
            or _normalize_text(compare.get("migration_profile"))
            or _normalize_text(plan.get("migration_profile"))
            or "unknown"
        )
        compare_outcome = _normalize_text(compare.get("comparison_outcome"))
        approval_status = _normalize_text(approval.get("approval_status"))
        approval_decision = _normalize_text(approval.get("approval_decision"))
        execution_status = _normalize_text(execution.get("execution_status"))

        reason_codes: list[str] = []
        review_stages: list[str] = []
        for item in source_review_items:
            for reason in item.get("reason_codes") or []:
                if isinstance(reason, str):
                    _append_unique(reason_codes, reason)
            stage = _normalize_text(item.get("review_stage"))
            if stage:
                _append_unique(review_stages, stage)

        review_priority = source_review_items[0].get("priority") if source_review_items else None

        current_stage = _derive_current_stage(
            compare_review=compare_review,
            approval_queue=approval_queue,
            execution_review=execution_review,
            execution_status=execution_status,
            approval_status=approval_status,
            compare_outcome=compare_outcome,
            replay_mode=replay_mode,
            has_plan=bool(plan),
        )

        current_stage_counts[current_stage] = current_stage_counts.get(current_stage, 0) + 1
        replay_mode_counts[replay_mode] = replay_mode_counts.get(replay_mode, 0) + 1
        source_system_counts[source_system] = source_system_counts.get(source_system, 0) + 1
        source_entity_type_counts[source_entity_type] = source_entity_type_counts.get(source_entity_type, 0) + 1
        migration_profile_counts[migration_profile] = migration_profile_counts.get(migration_profile, 0) + 1
        if compare_outcome:
            compare_outcome_counts[compare_outcome] = compare_outcome_counts.get(compare_outcome, 0) + 1
        if approval_status:
            approval_status_counts[approval_status] = approval_status_counts.get(approval_status, 0) + 1
        if execution_status:
            execution_status_counts[execution_status] = execution_status_counts.get(execution_status, 0) + 1

        for stage in review_stages:
            review_item_stage_counts[stage] = review_item_stage_counts.get(stage, 0) + 1
        if review_priority:
            review_priority_counts[review_priority] = review_priority_counts.get(review_priority, 0) + 1

        records.append(
            {
                "source_key": source_key,
                "source_system": source_system,
                "source_entity_type": source_entity_type,
                "migration_profile": migration_profile,
                "replay_mode": replay_mode,
                "compare_outcome": compare_outcome,
                "approval_status": approval_status,
                "approval_decision": approval_decision,
                "execution_status": execution_status,
                "current_stage": current_stage,
                "review_priority": review_priority,
                "review_stages": review_stages,
                "review_item_count": len(source_review_items),
                "reason_codes": reason_codes,
                "summary_line": _record_summary_line(
                    stage=current_stage,
                    replay_mode=replay_mode,
                    compare_outcome=compare_outcome,
                    approval_status=approval_status,
                    execution_status=execution_status,
                ),
                "detail": {
                    "plan": plan,
                    "plan_review": plan_review,
                    "compare": compare,
                    "compare_review": compare_review,
                    "approval": approval,
                    "approval_queue": approval_queue,
                    "execution": execution,
                    "execution_review": execution_review,
                },
                "review_items": source_review_items,
            }
        )

    records = sorted(
        records,
        key=lambda item: (
            _priority_rank(item.get("review_priority")),
            _stage_rank(item.get("current_stage")),
            str(item.get("source_key") or ""),
        ),
    )

    reason_code_counts = _top_reason_counts(review_items)
    warnings = _build_warnings(records=records, review_items=review_items)

    filter_options = {
        "current_stage": sorted({str(item.get("current_stage") or "unknown") for item in records}, key=_stage_rank),
        "replay_mode": sorted({str(item.get("replay_mode") or "unknown") for item in records}),
        "source_system": sorted({str(item.get("source_system") or "unknown") for item in records}),
        "source_entity_type": sorted({str(item.get("source_entity_type") or "unknown") for item in records}),
        "migration_profile": sorted({str(item.get("migration_profile") or "unknown") for item in records}),
        "compare_outcome": sorted({str(item.get("compare_outcome")) for item in records if item.get("compare_outcome")}),
        "approval_status": sorted({str(item.get("approval_status")) for item in records if item.get("approval_status")}),
        "execution_status": sorted({str(item.get("execution_status")) for item in records if item.get("execution_status")}),
        "review_priority": sorted({str(item.get("priority") or "unknown") for item in review_items}, key=_priority_rank),
        "review_stage": sorted({str(item.get("review_stage") or "unknown") for item in review_items}, key=_stage_rank),
        "reason_code": sorted(reason_code_counts.keys()),
    }

    rollup = {
        "schema_version": OPERATOR_CONSOLE_ALPHA_SCHEMA_VERSION,
        "generated_at": execution_documents.get("source_replay_execution_rollup", {}).get("generated_at")
        or approval_documents.get("source_replay_approval_rollup", {}).get("generated_at")
        or compare_documents.get("source_replay_compare_rollup", {}).get("generated_at")
        or plan_documents.get("source_replay_plan_rollup", {}).get("generated_at"),
        "source_count": len(records),
        "review_item_count": len(review_items),
        "warning_count": len(warnings),
        "current_stage_counts": current_stage_counts,
        "replay_mode_counts": replay_mode_counts,
        "source_system_counts": source_system_counts,
        "source_entity_type_counts": source_entity_type_counts,
        "migration_profile_counts": migration_profile_counts,
        "compare_outcome_counts": compare_outcome_counts,
        "approval_status_counts": approval_status_counts,
        "execution_status_counts": execution_status_counts,
        "review_item_stage_counts": review_item_stage_counts,
        "review_priority_counts": review_priority_counts,
        "reason_code_counts": reason_code_counts,
        "review_queue_counts": {
            "plan_review": len(plan_review_records),
            "compare_review": len(compare_review_records),
            "approval_review": len(approval_queue_records),
            "execution_review": len(execution_review_records),
        },
    }

    model = {
        "schema_version": OPERATOR_CONSOLE_ALPHA_SCHEMA_VERSION,
        "title": title,
        "subtitle": subtitle,
        "generated_at": rollup.get("generated_at"),
        "summary": {
            "plan_count": len(plan_records),
            "compare_count": len(compare_records),
            "approval_journal_count": len(approval_journal_records),
            "execution_pack_count": len(execution_records),
            "compare_review_count": len(compare_review_records),
            "approval_review_count": len(approval_queue_records),
            "execution_review_count": len(execution_review_records),
            "review_item_count": len(review_items),
            "warning_count": len(warnings),
        },
        "rollup": rollup,
        "filter_options": filter_options,
        "warnings": warnings,
        "review_items": review_items,
        "records": records,
        "links": {
            "model_json": "operator_console_alpha_model.json",
            "rollup_json": "operator_console_alpha_rollup.json",
        },
    }

    html_text = render_operator_console_alpha_html(model)
    return {
        "operator_console_alpha_model": model,
        "operator_console_alpha_rollup": rollup,
        "operator_console_alpha_html": {
            "schema_version": OPERATOR_CONSOLE_ALPHA_SCHEMA_VERSION,
            "generated_at": rollup.get("generated_at"),
            "filename": "operator_console_alpha.html",
            "html": html_text,
        },
    }


def render_operator_console_alpha_html(model: dict) -> str:
    payload = json.dumps(model, sort_keys=True).replace("</", "<\\/")
    title = html.escape(str(model.get("title") or "Source Replay Operator Console Alpha"))
    template = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #0f172a;
      --panel: #111827;
      --panel2: #1f2937;
      --panel3: #0b1220;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --accent: #38bdf8;
      --accent-strong: #0ea5e9;
      --ok: #10b981;
      --warn: #f59e0b;
      --bad: #ef4444;
      --line: #334155;
      --shadow: 0 10px 30px rgba(0,0,0,.22);
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Arial, Helvetica, sans-serif; background: var(--bg); color: var(--text); }
    a { color: var(--accent); }
    .wrap { max-width: 1560px; margin: 0 auto; padding: 24px; }
    h1 { margin: 0 0 6px; font-size: 30px; }
    .sub { color: var(--muted); margin-bottom: 12px; }
    .stack { display: grid; gap: 16px; }
    .banner, .warning-list, .toolbar, .metrics, .board, .layout { display: grid; gap: 12px; }
    .banner {
      background: rgba(56, 189, 248, 0.08);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px 16px;
      align-items: start;
      grid-template-columns: auto 1fr;
    }
    .banner .icon { color: var(--accent); font-weight: 700; }
    .warning-list { grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }
    .warning-card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-left: 4px solid var(--warn);
      border-radius: 14px;
      padding: 12px 14px;
      box-shadow: var(--shadow);
    }
    .warning-card.level-danger { border-left-color: var(--bad); }
    .warning-card.level-info { border-left-color: var(--accent); }
    .toolbar {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px;
      box-shadow: var(--shadow);
    }
    .toolbar-grid {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(12, minmax(0, 1fr));
    }
    .control {
      display: grid;
      gap: 6px;
      min-width: 0;
    }
    .control.span-3 { grid-column: span 3; }
    .control.span-2 { grid-column: span 2; }
    .control.span-4 { grid-column: span 4; }
    .control.span-6 { grid-column: span 6; }
    .control-label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .08em;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    input, select, button {
      border-radius: 12px;
      border: 1px solid var(--line);
      background: var(--panel2);
      color: var(--text);
      padding: 10px 12px;
      font: inherit;
    }
    button {
      cursor: pointer;
      background: linear-gradient(180deg, rgba(56,189,248,.18), rgba(56,189,248,.08));
      border-color: rgba(56,189,248,.45);
    }
    button.secondary {
      background: rgba(148,163,184,.08);
      border-color: var(--line);
    }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .button-row {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
      margin-top: 4px;
    }
    .button-row .file-label {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      background: rgba(148,163,184,.08);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px 12px;
    }
    .button-row input[type=file] { display: none; }
    .metrics { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
    .metric-card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      box-shadow: var(--shadow);
    }
    .metric-card.clickable { cursor: pointer; }
    .metric-card.clickable:hover, .metric-card.active {
      border-color: rgba(56,189,248,.65);
      transform: translateY(-1px);
    }
    .metric-label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .08em;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .metric-value { margin-top: 8px; font-size: 28px; font-weight: 700; }
    .metric-meta { color: var(--muted); font-size: 12px; margin-top: 6px; }
    .section-card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px;
      box-shadow: var(--shadow);
    }
    .section-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }
    .section-title {
      display: flex;
      align-items: center;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .08em;
    }
    .section-meta { color: var(--muted); font-size: 12px; }
    .board-grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
    .pill-card {
      background: linear-gradient(180deg, rgba(30,41,59,.75), rgba(15,23,42,.9));
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      box-shadow: var(--shadow);
    }
    .pill-card.clickable { cursor: pointer; }
    .pill-card.clickable:hover, .pill-card.active { border-color: rgba(56,189,248,.65); }
    .pill-top { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
    .pill-name { font-weight: 700; }
    .pill-count { font-size: 20px; font-weight: 700; }
    .pill-meta { color: var(--muted); font-size: 12px; margin-top: 6px; }
    .layout-grid {
      display: grid;
      gap: 16px;
      grid-template-columns: minmax(0, 1.7fr) minmax(320px, 1fr);
      align-items: start;
    }
    .table-wrap { overflow: auto; max-height: 78vh; border-radius: 12px; }
    table { width: 100%; border-collapse: collapse; min-width: 980px; }
    thead th {
      position: sticky;
      top: 0;
      background: rgba(2, 6, 23, 0.98);
      text-align: left;
      font-size: 12px;
      color: var(--muted);
      padding: 10px 8px;
      border-bottom: 1px solid var(--line);
      z-index: 2;
    }
    thead th .th-wrap { display: inline-flex; align-items: center; gap: 6px; }
    tbody td { padding: 10px 8px; border-bottom: 1px solid rgba(51,65,85,.5); vertical-align: top; }
    tbody tr { cursor: pointer; }
    tbody tr:hover { background: rgba(56, 189, 248, 0.08); }
    tbody tr.selected { background: rgba(56, 189, 248, 0.16); }
    .badge, .chip {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }
    .chip-wrap { display: flex; flex-wrap: wrap; gap: 6px; }
    .chip { background: rgba(148,163,184,.14); color: var(--text); }
    .chip.high { background: rgba(239,68,68,.16); color: #fecaca; }
    .chip.medium { background: rgba(245,158,11,.18); color: #fde68a; }
    .chip.low { background: rgba(16,185,129,.18); color: #bbf7d0; }
    .stage-execution-ready { background: rgba(16,185,129,.18); color: #a7f3d0; }
    .stage-completed-no-op { background: rgba(56,189,248,.18); color: #bae6fd; }
    .stage-approval-review, .stage-compare-review, .stage-execution-review, .stage-plan-review { background: rgba(245,158,11,.18); color: #fde68a; }
    .stage-unknown, .stage-planned, .stage-compared, .stage-approved, .stage-rejected { background: rgba(156,163,175,.18); color: #e5e7eb; }
    .muted { color: var(--muted); }
    .help-tab {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 18px;
      height: 18px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(56, 189, 248, 0.12);
      color: var(--accent);
      font-size: 11px;
      font-weight: 700;
      cursor: help;
      position: relative;
      flex: 0 0 auto;
    }
    .help-tab:hover::after, .help-tab:focus::after {
      content: attr(data-help);
      position: absolute;
      left: 50%;
      top: calc(100% + 8px);
      transform: translateX(-50%);
      width: 280px;
      max-width: 40vw;
      background: #020617;
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px 12px;
      box-shadow: 0 10px 28px rgba(0,0,0,.35);
      font-size: 12px;
      line-height: 1.45;
      text-transform: none;
      letter-spacing: normal;
      z-index: 30;
      white-space: normal;
    }
    .help-tab:hover::before, .help-tab:focus::before {
      content: "";
      position: absolute;
      left: 50%;
      top: 100%;
      transform: translateX(-50%);
      border-left: 7px solid transparent;
      border-right: 7px solid transparent;
      border-bottom: 7px solid var(--line);
      z-index: 31;
    }
    .detail-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0 12px; }
    .tab-btn.active { border-color: rgba(56,189,248,.65); background: rgba(56,189,248,.16); }
    .detail-panel { display: none; }
    .detail-panel.active { display: block; }
    .overview-grid { display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
    .overview-item { background: var(--panel3); border: 1px solid var(--line); border-radius: 12px; padding: 10px; }
    .overview-item strong { display: block; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 6px; }
    pre {
      white-space: pre-wrap;
      word-break: break-word;
      background: #020617;
      border: 1px solid #1e293b;
      border-radius: 12px;
      padding: 12px;
      max-height: 62vh;
      overflow: auto;
      margin: 0;
    }
    .review-list { display: grid; gap: 8px; max-height: 30vh; overflow: auto; }
    .review-item-card {
      background: var(--panel3);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px;
      cursor: pointer;
    }
    .review-item-card:hover, .review-item-card.active { border-color: rgba(56,189,248,.65); }
    .review-item-top { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
    .empty { padding: 14px; border-radius: 12px; border: 1px dashed var(--line); color: var(--muted); background: rgba(15,23,42,.5); }
    @media (max-width: 1200px) {
      .layout-grid { grid-template-columns: 1fr; }
      .control.span-3, .control.span-2, .control.span-4, .control.span-6 { grid-column: span 12; }
    }
  </style>
</head>
<body>
  <div class="wrap stack">
    <div>
      <h1>__TITLE__</h1>
      <div class="sub" id="subtitle"></div>
    </div>

    <div class="banner">
      <div class="icon">ⓘ</div>
      <div>
        Hover any <strong>?</strong> help tab to learn what a control or metric does. Anything clickable includes hover guidance describing what the click will do. This console stays read-only and client-side so you can triage replay state without mutating backend data.
      </div>
    </div>

    <div id="warningList" class="warning-list"></div>

    <div class="toolbar">
      <div class="section-header">
        <div class="section-title">Operator Controls <span class="help-tab" tabindex="0" data-help="These controls only change what you see in the console. They do not write back to the replay system.">?</span></div>
        <div class="section-meta" id="filteredSummary"></div>
      </div>
      <div class="toolbar-grid">
        <label class="control span-4" for="search">
          <div class="control-label">Search Sources <span class="help-tab" tabindex="0" data-help="Filter the visible rows by source key, system, entity, migration profile, replay mode, outcomes, approval decisions, execution status, reason codes, or summaries.">?</span></div>
          <input id="search" type="search" placeholder="Search source key, system, entity, reason code" title="Type to filter visible rows. This does not change stored data.">
        </label>
        <label class="control span-2" for="stageFilter">
          <div class="control-label">Stage Filter <span class="help-tab" tabindex="0" data-help="Show only records currently in a selected workflow stage.">?</span></div>
          <select id="stageFilter" title="Choose a current stage to limit the visible rows."></select>
        </label>
        <label class="control span-2" for="modeFilter">
          <div class="control-label">Replay Mode Filter <span class="help-tab" tabindex="0" data-help="Show only records using a selected replay mode.">?</span></div>
          <select id="modeFilter" title="Choose a replay mode to limit visible rows."></select>
        </label>
        <label class="control span-2" for="systemFilter">
          <div class="control-label">System Filter <span class="help-tab" tabindex="0" data-help="Show only records from a specific source system.">?</span></div>
          <select id="systemFilter" title="Choose a source system to limit visible rows."></select>
        </label>
        <label class="control span-2" for="entityFilter">
          <div class="control-label">Entity Filter <span class="help-tab" tabindex="0" data-help="Show only records for a selected source entity type.">?</span></div>
          <select id="entityFilter" title="Choose an entity type to limit visible rows."></select>
        </label>

        <label class="control span-2" for="compareFilter">
          <div class="control-label">Compare Outcome Filter <span class="help-tab" tabindex="0" data-help="Filter rows by the replay comparison outcome.">?</span></div>
          <select id="compareFilter" title="Choose a comparison outcome to limit visible rows."></select>
        </label>
        <label class="control span-2" for="approvalFilter">
          <div class="control-label">Approval Status Filter <span class="help-tab" tabindex="0" data-help="Filter rows by the latest approval status.">?</span></div>
          <select id="approvalFilter" title="Choose an approval status to limit visible rows."></select>
        </label>
        <label class="control span-2" for="executionFilter">
          <div class="control-label">Execution Status Filter <span class="help-tab" tabindex="0" data-help="Filter rows by the latest execution status.">?</span></div>
          <select id="executionFilter" title="Choose an execution status to limit visible rows."></select>
        </label>
        <label class="control span-2" for="priorityFilter">
          <div class="control-label">Priority Filter <span class="help-tab" tabindex="0" data-help="Show only records that currently carry a selected review priority.">?</span></div>
          <select id="priorityFilter" title="Choose a review priority to limit visible rows."></select>
        </label>
        <label class="control span-2" for="reasonFilter">
          <div class="control-label">Reason Code Filter <span class="help-tab" tabindex="0" data-help="Show only rows carrying a selected reason code in any review queue.">?</span></div>
          <select id="reasonFilter" title="Choose a reason code to limit visible rows."></select>
        </label>
        <label class="control span-2" for="queueFilter">
          <div class="control-label">Review Queue Filter <span class="help-tab" tabindex="0" data-help="Show only rows that currently participate in a selected review queue stage.">?</span></div>
          <select id="queueFilter" title="Choose a review queue stage to limit visible rows."></select>
        </label>

        <label class="control span-2" for="sortFilter">
          <div class="control-label">Sort Rows <span class="help-tab" tabindex="0" data-help="Change the order of the visible rows without changing underlying data.">?</span></div>
          <select id="sortFilter" title="Choose how visible rows are sorted.">
            <option value="priority-stage-key">Priority, stage, source key</option>
            <option value="source-key">Source key</option>
            <option value="stage">Current stage</option>
            <option value="system">Source system</option>
            <option value="review-count">Review backlog size</option>
          </select>
        </label>
        <label class="control span-2" for="reviewOnlyToggle">
          <div class="control-label">Only Review Items <span class="help-tab" tabindex="0" data-help="Toggle this on to show only records that currently have one or more review items.">?</span></div>
          <button id="reviewOnlyToggle" type="button" class="secondary" title="Click to toggle showing only rows with review items.">Only Review Items: Off</button>
        </label>
        <div class="control span-6">
          <div class="control-label">Read-Only Utilities <span class="help-tab" tabindex="0" data-help="These buttons reset filters, export the currently visible rows, copy the selected record JSON, open generated JSON files, or load a different console model into the page for local testing. None of them mutate the replay pipeline.">?</span></div>
          <div class="button-row">
            <button id="resetFiltersBtn" type="button" class="secondary" title="Click to reset every filter and return the table to the default view.">Reset Filters</button>
            <button id="exportJsonBtn" type="button" title="Click to download the currently visible rows as a JSON file.">Export Filtered JSON</button>
            <button id="exportCsvBtn" type="button" title="Click to download the currently visible rows as a CSV file.">Export Filtered CSV</button>
            <button id="copySelectedBtn" type="button" class="secondary" title="Click to copy the currently selected record JSON to your clipboard.">Copy Selected JSON</button>
            <a id="openModelBtn" href="operator_console_alpha_model.json" target="_blank" rel="noopener" title="Click to open the generated operator console model JSON in a new browser tab."><button type="button" class="secondary">Open Model JSON</button></a>
            <a id="openRollupBtn" href="operator_console_alpha_rollup.json" target="_blank" rel="noopener" title="Click to open the generated operator console rollup JSON in a new browser tab."><button type="button" class="secondary">Open Rollup JSON</button></a>
            <label class="file-label" for="loadModelInput" title="Click to load a different operator console model JSON file into this page for local testing. This only changes the in-browser view.">
              Load Model JSON
              <input id="loadModelInput" type="file" accept="application/json,.json">
            </label>
          </div>
        </div>
      </div>
    </div>

    <div class="metrics" id="summaryCards"></div>

    <div class="board stack">
      <div class="section-card">
        <div class="section-header">
          <div class="section-title">Current Stage Board <span class="help-tab" tabindex="0" data-help="Click any stage card to apply or clear a current-stage filter.">?</span></div>
          <div class="section-meta">Click a stage card to focus the table.</div>
        </div>
        <div id="stageBoard" class="board-grid"></div>
      </div>
      <div class="section-card">
        <div class="section-header">
          <div class="section-title">Review Queue Board <span class="help-tab" tabindex="0" data-help="Click any review queue card to show only rows participating in that review stage.">?</span></div>
          <div class="section-meta">Queue filters help isolate triage work.</div>
        </div>
        <div id="queueBoard" class="board-grid"></div>
      </div>
    </div>

    <div class="layout-grid">
      <div class="section-card" title="This table merges the latest planning, comparison, approval, and execution state for each source key. Click any row to inspect that source in the detail panel.">
        <div class="section-header">
          <div class="section-title">Source Replay Records <span class="help-tab" tabindex="0" data-help="This table shows one operator-facing row per source key. Click a row to inspect overview data, review evidence, or raw JSON.">?</span></div>
          <div class="section-meta" id="tableMeta"></div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th><span class="th-wrap">Source Key <span class="help-tab" tabindex="0" data-help="The unique source key and entity type for this replay record.">?</span></span></th>
                <th><span class="th-wrap">Stage <span class="help-tab" tabindex="0" data-help="The current stage in the replay workflow.">?</span></span></th>
                <th><span class="th-wrap">Replay Mode <span class="help-tab" tabindex="0" data-help="Whether the source is compare-only, resume-from-approved, or full-replay.">?</span></span></th>
                <th><span class="th-wrap">System <span class="help-tab" tabindex="0" data-help="The originating source system.">?</span></span></th>
                <th><span class="th-wrap">Entity <span class="help-tab" tabindex="0" data-help="The source entity type carried by the record.">?</span></span></th>
                <th><span class="th-wrap">Priority <span class="help-tab" tabindex="0" data-help="The highest active review priority for this source, if any.">?</span></span></th>
                <th><span class="th-wrap">Compare <span class="help-tab" tabindex="0" data-help="The latest replay comparison outcome.">?</span></span></th>
                <th><span class="th-wrap">Approval <span class="help-tab" tabindex="0" data-help="The latest approval decision or approval status.">?</span></span></th>
                <th><span class="th-wrap">Execution <span class="help-tab" tabindex="0" data-help="The current execution status for the source.">?</span></span></th>
                <th><span class="th-wrap">Reasons <span class="help-tab" tabindex="0" data-help="The union of active reason codes across all review queues for this source.">?</span></span></th>
              </tr>
            </thead>
            <tbody id="rows"></tbody>
          </table>
        </div>
      </div>

      <div class="stack">
        <div class="section-card" title="This panel shows review queue items. Click an item to select its source in the main table and inspect details.">
          <div class="section-header">
            <div class="section-title">Review Inbox <span class="help-tab" tabindex="0" data-help="This list shows pending review items ordered by priority and review stage. Click an item to select its related source row.">?</span></div>
            <div class="section-meta" id="reviewMeta"></div>
          </div>
          <div id="reviewList" class="review-list"></div>
        </div>

        <div class="section-card" title="This panel updates when you click a source row or a review item.">
          <div class="section-header">
            <div class="section-title">Record Detail <span class="help-tab" tabindex="0" data-help="Inspect the selected source as an overview, the active review items, or the raw merged JSON payload.">?</span></div>
            <div class="section-meta" id="detailMeta"></div>
          </div>
          <div class="detail-tabs">
            <button id="tabOverview" type="button" class="tab-btn" title="Click to view a condensed overview of the selected record.">Overview</button>
            <button id="tabReviewItems" type="button" class="tab-btn" title="Click to view the selected record's review items and queue evidence.">Review Items</button>
            <button id="tabRawJson" type="button" class="tab-btn" title="Click to view the raw merged JSON for the selected record.">Raw JSON</button>
          </div>
          <div id="panelOverview" class="detail-panel"></div>
          <div id="panelReviewItems" class="detail-panel"></div>
          <pre id="panelRawJson" class="detail-panel"></pre>
        </div>
      </div>
    </div>
  </div>
  <script>
    const DEFAULT_MODEL = __PAYLOAD__;
    const STATE_KEY = 'operatorConsoleAlphaState';
    let model = DEFAULT_MODEL;
    let filteredRecords = [];
    let filteredReviewItems = [];

    const els = {
      subtitle: document.getElementById('subtitle'),
      warningList: document.getElementById('warningList'),
      filteredSummary: document.getElementById('filteredSummary'),
      summaryCards: document.getElementById('summaryCards'),
      stageBoard: document.getElementById('stageBoard'),
      queueBoard: document.getElementById('queueBoard'),
      tableMeta: document.getElementById('tableMeta'),
      reviewMeta: document.getElementById('reviewMeta'),
      rows: document.getElementById('rows'),
      reviewList: document.getElementById('reviewList'),
      detailMeta: document.getElementById('detailMeta'),
      panelOverview: document.getElementById('panelOverview'),
      panelReviewItems: document.getElementById('panelReviewItems'),
      panelRawJson: document.getElementById('panelRawJson'),
      search: document.getElementById('search'),
      stageFilter: document.getElementById('stageFilter'),
      modeFilter: document.getElementById('modeFilter'),
      systemFilter: document.getElementById('systemFilter'),
      entityFilter: document.getElementById('entityFilter'),
      compareFilter: document.getElementById('compareFilter'),
      approvalFilter: document.getElementById('approvalFilter'),
      executionFilter: document.getElementById('executionFilter'),
      priorityFilter: document.getElementById('priorityFilter'),
      reasonFilter: document.getElementById('reasonFilter'),
      queueFilter: document.getElementById('queueFilter'),
      sortFilter: document.getElementById('sortFilter'),
      reviewOnlyToggle: document.getElementById('reviewOnlyToggle'),
      resetFiltersBtn: document.getElementById('resetFiltersBtn'),
      exportJsonBtn: document.getElementById('exportJsonBtn'),
      exportCsvBtn: document.getElementById('exportCsvBtn'),
      copySelectedBtn: document.getElementById('copySelectedBtn'),
      loadModelInput: document.getElementById('loadModelInput'),
      tabOverview: document.getElementById('tabOverview'),
      tabReviewItems: document.getElementById('tabReviewItems'),
      tabRawJson: document.getElementById('tabRawJson'),
    };

    const state = Object.assign(
      {
        search: '',
        currentStage: 'all',
        replayMode: 'all',
        sourceSystem: 'all',
        sourceEntityType: 'all',
        compareOutcome: 'all',
        approvalStatus: 'all',
        executionStatus: 'all',
        reviewPriority: 'all',
        reasonCode: 'all',
        reviewStage: 'all',
        sortMode: 'priority-stage-key',
        reviewOnly: false,
        selectedSourceKey: null,
        detailTab: 'overview',
      },
      loadSavedState(),
    );

    function loadSavedState() {
      try {
        const raw = localStorage.getItem(STATE_KEY);
        return raw ? JSON.parse(raw) : {};
      } catch (error) {
        return {};
      }
    }

    function saveState() {
      try {
        localStorage.setItem(STATE_KEY, JSON.stringify(state));
      } catch (error) {
        // ignore storage failures
      }
    }

    function priorityRank(value) {
      return ({ high: 0, medium: 1, low: 2, unknown: 3 })[(value || 'unknown').toLowerCase()] ?? 3;
    }

    function stageRank(value) {
      return ({
        'execution-review': 0,
        'approval-review': 1,
        'compare-review': 2,
        'execution-ready': 3,
        approved: 4,
        compared: 5,
        planned: 6,
        'completed-no-op': 7,
        rejected: 8,
        unknown: 9,
        'plan-review': 10,
      })[(value || 'unknown').toLowerCase()] ?? 99;
    }

    function escapeHtml(value) {
      return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }

    function helpTab(text) {
      return '<span class="help-tab" tabindex="0" data-help="' + escapeHtml(text) + '">?</span>';
    }

    function populateSelect(selectEl, values, labelPrefix, currentValue) {
      const options = ['all', ...(values || [])];
      selectEl.innerHTML = options.map((value) => {
        const display = value === 'all' ? 'All' : value;
        const selected = value === currentValue ? ' selected' : '';
        return '<option value="' + escapeHtml(value) + '"' + selected + '>' + escapeHtml(labelPrefix + display) + '</option>';
      }).join('');
    }

    function setSubtitle() {
      const generated = model.generated_at || 'unknown';
      const subtitle = model.subtitle || 'Read-only operator console';
      els.subtitle.textContent = subtitle + ' Generated: ' + generated + ' • Sources: ' + model.rollup.source_count + ' • Review items: ' + model.rollup.review_item_count;
    }

    function renderWarnings() {
      const warnings = model.warnings || [];
      if (!warnings.length) {
        els.warningList.innerHTML = '';
        return;
      }
      els.warningList.innerHTML = warnings.map((warning) => (
        '<div class="warning-card level-' + escapeHtml(warning.level || 'warning') + '" title="This banner is informational only. It does not change replay state.">' +
          '<div class="metric-label">' + escapeHtml(warning.title || 'Warning') + helpTab(escapeHtml(warning.message || '')) + '</div>' +
          '<div style="margin-top:8px">' + escapeHtml(warning.message || '') + '</div>' +
        '</div>'
      )).join('');
    }

    function renderSummaryCards() {
      const specs = [
        ['Sources', model.rollup.source_count, 'Count of merged source rows in the console model.', null, null],
        ['Review Items', model.rollup.review_item_count, 'Count of all review queue entries merged into the console model.', 'reviewOnly', true],
        ['Warnings', model.rollup.warning_count, 'Derived data-health and backlog warnings based on the current replay artifacts.', null, null],
        ['Execution Ready', (model.rollup.current_stage_counts || {})['execution-ready'] || 0, 'Count of sources currently marked execution-ready.', 'currentStage', 'execution-ready'],
        ['Execution Review', (model.rollup.current_stage_counts || {})['execution-review'] || 0, 'Count of sources currently blocked in execution review.', 'currentStage', 'execution-review'],
        ['Approval Review', (model.rollup.current_stage_counts || {})['approval-review'] || 0, 'Count of sources currently blocked in approval review.', 'currentStage', 'approval-review'],
        ['Compare Review', (model.rollup.current_stage_counts || {})['compare-review'] || 0, 'Count of sources currently blocked in compare review.', 'currentStage', 'compare-review'],
        ['High Priority', (model.rollup.review_priority_counts || {}).high || 0, 'Count of active high-priority review items.', 'reviewPriority', 'high'],
      ];
      els.summaryCards.innerHTML = specs.map(([label, value, help, stateKey, stateValue]) => {
        const clickable = Boolean(stateKey);
        const active = clickable && ((stateKey === 'reviewOnly' && state.reviewOnly === stateValue) || state[stateKey] === stateValue);
        return '<div class="metric-card ' + (clickable ? 'clickable' : '') + ' ' + (active ? 'active' : '') + '" ' +
          (clickable ? 'data-state-key="' + stateKey + '" data-state-value="' + stateValue + '" ' : '') +
          'title="' + escapeHtml(clickable ? help + ' Click to apply or clear that filter.' : help) + '">' +
            '<div class="metric-label">' + escapeHtml(label) + helpTab(help) + '</div>' +
            '<div class="metric-value">' + escapeHtml(value) + '</div>' +
          '</div>';
      }).join('');
      els.summaryCards.querySelectorAll('.metric-card.clickable').forEach((card) => {
        card.addEventListener('click', () => {
          const key = card.dataset.stateKey;
          const value = card.dataset.stateValue;
          if (key === 'reviewOnly') {
            state.reviewOnly = !state.reviewOnly;
          } else {
            state[key] = state[key] === value ? 'all' : value;
          }
          syncControlsFromState();
          render();
        });
      });
    }

    function renderBoard(targetEl, counts, stateKey, helpText) {
      const entries = Object.entries(counts || {}).sort((a, b) => {
        if (stateKey.includes('Stage')) return stageRank(a[0]) - stageRank(b[0]);
        return String(a[0]).localeCompare(String(b[0]));
      });
      if (!entries.length) {
        targetEl.innerHTML = '<div class="empty">No data available for this board.</div>';
        return;
      }
      targetEl.innerHTML = entries.map(([name, count]) => {
        const active = state[stateKey] === name;
        return '<div class="pill-card clickable ' + (active ? 'active' : '') + '" data-state-key="' + stateKey + '" data-state-value="' + escapeHtml(name) + '" title="' + escapeHtml(helpText + ' Click to apply or clear this filter.') + '">' +
          '<div class="pill-top"><div class="pill-name">' + escapeHtml(name) + '</div><div class="pill-count">' + escapeHtml(count) + '</div></div>' +
          '<div class="pill-meta">Click to filter the console by ' + escapeHtml(name) + '.</div>' +
        '</div>';
      }).join('');
      targetEl.querySelectorAll('.pill-card.clickable').forEach((card) => {
        card.addEventListener('click', () => {
          const key = card.dataset.stateKey;
          const value = card.dataset.stateValue;
          state[key] = state[key] === value ? 'all' : value;
          syncControlsFromState();
          render();
        });
      });
    }

    function recordMatches(record) {
      const haystack = [
        record.source_key,
        record.source_system,
        record.source_entity_type,
        record.migration_profile,
        record.replay_mode,
        record.compare_outcome,
        record.approval_status,
        record.approval_decision,
        record.execution_status,
        record.summary_line,
        ...(record.reason_codes || []),
        ...(record.review_stages || []),
      ].join(' ').toLowerCase();
      const query = state.search.trim().toLowerCase();
      if (query && !haystack.includes(query)) return false;
      if (state.currentStage !== 'all' && record.current_stage !== state.currentStage) return false;
      if (state.replayMode !== 'all' && record.replay_mode !== state.replayMode) return false;
      if (state.sourceSystem !== 'all' && record.source_system !== state.sourceSystem) return false;
      if (state.sourceEntityType !== 'all' && record.source_entity_type !== state.sourceEntityType) return false;
      if (state.compareOutcome !== 'all' && record.compare_outcome !== state.compareOutcome) return false;
      if (state.approvalStatus !== 'all' && (record.approval_status || 'none') !== state.approvalStatus) return false;
      if (state.executionStatus !== 'all' && (record.execution_status || 'none') !== state.executionStatus) return false;
      if (state.reviewPriority !== 'all' && (record.review_priority || 'unknown') !== state.reviewPriority) return false;
      if (state.reasonCode !== 'all' && !(record.reason_codes || []).includes(state.reasonCode)) return false;
      if (state.reviewStage !== 'all' && !(record.review_stages || []).includes(state.reviewStage)) return false;
      if (state.reviewOnly && !(record.review_item_count > 0)) return false;
      return true;
    }

    function sortRecords(records) {
      const items = [...records];
      items.sort((a, b) => {
        switch (state.sortMode) {
          case 'source-key':
            return String(a.source_key).localeCompare(String(b.source_key));
          case 'stage':
            return stageRank(a.current_stage) - stageRank(b.current_stage) || String(a.source_key).localeCompare(String(b.source_key));
          case 'system':
            return String(a.source_system).localeCompare(String(b.source_system)) || String(a.source_key).localeCompare(String(b.source_key));
          case 'review-count':
            return (b.review_item_count || 0) - (a.review_item_count || 0) || priorityRank(a.review_priority) - priorityRank(b.review_priority) || String(a.source_key).localeCompare(String(b.source_key));
          case 'priority-stage-key':
          default:
            return priorityRank(a.review_priority) - priorityRank(b.review_priority) || stageRank(a.current_stage) - stageRank(b.current_stage) || String(a.source_key).localeCompare(String(b.source_key));
        }
      });
      return items;
    }

    function getSelectedRecord() {
      if (!state.selectedSourceKey) return null;
      return filteredRecords.find((item) => item.source_key === state.selectedSourceKey) || model.records.find((item) => item.source_key === state.selectedSourceKey) || null;
    }

    function renderRows() {
      filteredRecords = sortRecords((model.records || []).filter(recordMatches));
      els.tableMeta.textContent = filteredRecords.length + ' visible row(s)';
      if (!filteredRecords.length) {
        els.rows.innerHTML = '<tr><td colspan="10"><div class="empty">No rows match the current filters.</div></td></tr>';
        return;
      }
      els.rows.innerHTML = filteredRecords.map((row) => {
        const selected = state.selectedSourceKey === row.source_key;
        const reasons = (row.reason_codes || []).slice(0, 3).map((reason) => '<span class="chip" title="Reason code carried by one or more review items for this source.">' + escapeHtml(reason) + '</span>').join('');
        const moreReasons = (row.reason_codes || []).length > 3 ? '<span class="muted">+' + ((row.reason_codes || []).length - 3) + ' more</span>' : '';
        const priorityChip = row.review_priority ? '<span class="chip ' + escapeHtml(row.review_priority) + '" title="Highest active review priority for this source.">' + escapeHtml(row.review_priority) + '</span>' : '<span class="muted">none</span>';
        return '<tr data-source-key="' + escapeHtml(row.source_key) + '" class="' + (selected ? 'selected' : '') + '" title="Click to inspect overview, review evidence, and raw JSON for ' + escapeHtml(row.source_key) + '.">' +
          '<td><strong>' + escapeHtml(row.source_key) + '</strong><br><span class="muted">' + escapeHtml(row.source_entity_type || '') + '</span></td>' +
          '<td><span class="badge stage-' + escapeHtml((row.current_stage || 'unknown').replace(/[^a-z0-9-]/gi, '-').toLowerCase()) + '">' + escapeHtml(row.current_stage || 'unknown') + '</span></td>' +
          '<td>' + escapeHtml(row.replay_mode || '') + '</td>' +
          '<td>' + escapeHtml(row.source_system || '') + '</td>' +
          '<td>' + escapeHtml(row.source_entity_type || '') + '</td>' +
          '<td>' + priorityChip + '</td>' +
          '<td>' + escapeHtml(row.compare_outcome || '') + '</td>' +
          '<td>' + escapeHtml(row.approval_decision || row.approval_status || '') + '</td>' +
          '<td>' + escapeHtml(row.execution_status || '') + '</td>' +
          '<td><div class="chip-wrap">' + reasons + '</div>' + moreReasons + '</td>' +
        '</tr>';
      }).join('');
      els.rows.querySelectorAll('tr[data-source-key]').forEach((rowEl) => {
        rowEl.addEventListener('click', () => {
          state.selectedSourceKey = rowEl.dataset.sourceKey;
          state.detailTab = state.detailTab || 'overview';
          saveState();
          renderRows();
          renderDetail();
        });
      });
    }

    function renderReviewInbox() {
      filteredReviewItems = (model.review_items || []).filter((item) => {
        if (state.reviewStage !== 'all' && item.review_stage !== state.reviewStage) return false;
        if (state.reviewPriority !== 'all' && (item.priority || 'unknown') !== state.reviewPriority) return false;
        if (state.reasonCode !== 'all' && !(item.reason_codes || []).includes(state.reasonCode)) return false;
        if (state.currentStage !== 'all') {
          const linked = (model.records || []).find((record) => record.source_key === item.source_key);
          if (linked && linked.current_stage !== state.currentStage) return false;
        }
        if (state.replayMode !== 'all' && (item.replay_mode || 'unknown') !== state.replayMode) return false;
        const query = state.search.trim().toLowerCase();
        if (query) {
          const haystack = [item.source_key, item.source_system, item.review_stage, item.priority, item.summary, ...(item.reason_codes || [])].join(' ').toLowerCase();
          if (!haystack.includes(query)) return false;
        }
        return true;
      });
      els.reviewMeta.textContent = filteredReviewItems.length + ' visible review item(s)';
      if (!filteredReviewItems.length) {
        els.reviewList.innerHTML = '<div class="empty">No review items match the current filters.</div>';
        return;
      }
      els.reviewList.innerHTML = filteredReviewItems.map((item) => {
        const active = state.selectedSourceKey === item.source_key;
        const reasons = (item.reason_codes || []).map((reason) => '<span class="chip" title="Reason code carried by this review item.">' + escapeHtml(reason) + '</span>').join('');
        return '<div class="review-item-card ' + (active ? 'active' : '') + '" data-source-key="' + escapeHtml(item.source_key) + '" title="Click to select ' + escapeHtml(item.source_key) + ' in the main table and inspect its details.">' +
          '<div class="review-item-top"><strong>' + escapeHtml(item.source_key) + '</strong><span class="chip ' + escapeHtml(item.priority || 'unknown') + '">' + escapeHtml(item.priority || 'unknown') + '</span></div>' +
          '<div class="muted" style="margin:6px 0">' + escapeHtml(item.review_stage || '') + ' • ' + escapeHtml(item.replay_mode || '') + '</div>' +
          '<div>' + escapeHtml(item.summary || '') + '</div>' +
          '<div class="chip-wrap" style="margin-top:8px">' + reasons + '</div>' +
        '</div>';
      }).join('');
      els.reviewList.querySelectorAll('.review-item-card[data-source-key]').forEach((card) => {
        card.addEventListener('click', () => {
          state.selectedSourceKey = card.dataset.sourceKey;
          saveState();
          renderRows();
          renderDetail();
        });
      });
    }

    function renderDetail() {
      const record = getSelectedRecord() || filteredRecords[0] || model.records[0] || null;
      if (!record) {
        els.detailMeta.textContent = 'No selection';
        els.panelOverview.innerHTML = '<div class="empty">Select a row to inspect details.</div>';
        els.panelReviewItems.innerHTML = '<div class="empty">Select a row to inspect its review items.</div>';
        els.panelRawJson.textContent = 'Select a row to inspect details.';
        return;
      }
      state.selectedSourceKey = record.source_key;
      els.detailMeta.textContent = record.source_key + ' • ' + (record.summary_line || '');
      const overviewItems = [
        ['Source key', record.source_key],
        ['Current stage', record.current_stage],
        ['Replay mode', record.replay_mode],
        ['Source system', record.source_system],
        ['Entity type', record.source_entity_type],
        ['Migration profile', record.migration_profile],
        ['Compare outcome', record.compare_outcome || 'n/a'],
        ['Approval status', record.approval_status || 'n/a'],
        ['Approval decision', record.approval_decision || 'n/a'],
        ['Execution status', record.execution_status || 'n/a'],
        ['Review priority', record.review_priority || 'none'],
        ['Review item count', record.review_item_count || 0],
      ];
      els.panelOverview.innerHTML = '<div class="overview-grid">' + overviewItems.map(([label, value]) => (
        '<div class="overview-item"><strong>' + escapeHtml(label) + '</strong><div>' + escapeHtml(value) + '</div></div>'
      )).join('') + '</div>' +
      '<div style="margin-top:12px" class="overview-item"><strong>Reason Codes</strong><div class="chip-wrap">' + ((record.reason_codes || []).map((reason) => '<span class="chip" title="Reason code derived from one or more review queues for this source.">' + escapeHtml(reason) + '</span>').join('') || '<span class="muted">No active reason codes.</span>') + '</div></div>';

      const reviewItems = record.review_items || [];
      els.panelReviewItems.innerHTML = reviewItems.length ? reviewItems.map((item) => (
        '<div class="overview-item" style="margin-bottom:10px"><strong>' + escapeHtml(item.review_stage || 'review-item') + ' • ' + escapeHtml(item.priority || 'unknown') + '</strong>' +
        '<div style="margin-bottom:8px">' + escapeHtml(item.summary || '') + '</div>' +
        '<div class="chip-wrap" style="margin-bottom:8px">' + ((item.reason_codes || []).map((reason) => '<span class="chip" title="Reason code attached to this review item.">' + escapeHtml(reason) + '</span>').join('') || '<span class="muted">No reason codes.</span>') + '</div>' +
        '<pre>' + escapeHtml(JSON.stringify(item.detail || {}, null, 2)) + '</pre>' +
        '</div>'
      )).join('') : '<div class="empty">This record currently has no active review items.</div>';

      els.panelRawJson.textContent = JSON.stringify(record, null, 2);
      setActiveDetailTab(state.detailTab || 'overview');
      saveState();
    }

    function setActiveDetailTab(name) {
      state.detailTab = name;
      saveState();
      const tabs = {
        overview: els.tabOverview,
        review: els.tabReviewItems,
        raw: els.tabRawJson,
      };
      const panels = {
        overview: els.panelOverview,
        review: els.panelReviewItems,
        raw: els.panelRawJson,
      };
      Object.entries(tabs).forEach(([key, button]) => {
        button.classList.toggle('active', key === name);
      });
      Object.entries(panels).forEach(([key, panel]) => {
        panel.classList.toggle('active', key === name);
      });
    }

    function syncControlsFromState() {
      els.search.value = state.search;
      populateSelect(els.stageFilter, model.filter_options.current_stage || [], 'Stage: ', state.currentStage);
      populateSelect(els.modeFilter, model.filter_options.replay_mode || [], 'Mode: ', state.replayMode);
      populateSelect(els.systemFilter, model.filter_options.source_system || [], 'System: ', state.sourceSystem);
      populateSelect(els.entityFilter, model.filter_options.source_entity_type || [], 'Entity: ', state.sourceEntityType);
      populateSelect(els.compareFilter, model.filter_options.compare_outcome || [], 'Compare: ', state.compareOutcome);
      populateSelect(els.approvalFilter, ['none', ...(model.filter_options.approval_status || [])], 'Approval: ', state.approvalStatus);
      populateSelect(els.executionFilter, ['none', ...(model.filter_options.execution_status || [])], 'Execution: ', state.executionStatus);
      populateSelect(els.priorityFilter, model.filter_options.review_priority || [], 'Priority: ', state.reviewPriority);
      populateSelect(els.reasonFilter, model.filter_options.reason_code || [], 'Reason: ', state.reasonCode);
      populateSelect(els.queueFilter, model.filter_options.review_stage || [], 'Queue: ', state.reviewStage);
      els.sortFilter.value = state.sortMode;
      els.reviewOnlyToggle.textContent = 'Only Review Items: ' + (state.reviewOnly ? 'On' : 'Off');
      els.reviewOnlyToggle.classList.toggle('active', state.reviewOnly);
    }

    function renderFilteredSummary() {
      const filteredHighPriority = filteredReviewItems.filter((item) => (item.priority || 'unknown') === 'high').length;
      els.filteredSummary.textContent = filteredRecords.length + ' visible source row(s) • ' + filteredReviewItems.length + ' visible review item(s) • ' + filteredHighPriority + ' high-priority item(s)';
    }

    function exportFilteredJson() {
      const blob = new Blob([JSON.stringify(filteredRecords, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'operator_console_filtered_records.json';
      link.click();
      URL.revokeObjectURL(url);
    }

    function exportFilteredCsv() {
      const rows = [
        ['source_key', 'current_stage', 'replay_mode', 'source_system', 'source_entity_type', 'compare_outcome', 'approval_status', 'approval_decision', 'execution_status', 'review_priority', 'review_item_count', 'reason_codes'],
        ...filteredRecords.map((record) => [
          record.source_key,
          record.current_stage,
          record.replay_mode,
          record.source_system,
          record.source_entity_type,
          record.compare_outcome || '',
          record.approval_status || '',
          record.approval_decision || '',
          record.execution_status || '',
          record.review_priority || '',
          String(record.review_item_count || 0),
          (record.reason_codes || []).join('|'),
        ])
      ];
      const csv = rows.map((row) => row.map((value) => '"' + String(value ?? '').replaceAll('"', '""') + '"').join(',')).join('\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'operator_console_filtered_records.csv';
      link.click();
      URL.revokeObjectURL(url);
    }

    async function copySelectedJson() {
      const record = getSelectedRecord();
      if (!record) return;
      try {
        await navigator.clipboard.writeText(JSON.stringify(record, null, 2));
      } catch (error) {
        window.alert('Unable to copy the selected JSON.');
      }
    }

    function render() {
      setSubtitle();
      renderWarnings();
      renderSummaryCards();
      renderBoard(els.stageBoard, model.rollup.current_stage_counts || {}, 'currentStage', 'Filter the table by current workflow stage.');
      renderBoard(els.queueBoard, model.rollup.review_item_stage_counts || {}, 'reviewStage', 'Filter the table by review queue stage.');
      renderRows();
      renderReviewInbox();
      renderDetail();
      renderFilteredSummary();
    }

    function resetFilters() {
      state.search = '';
      state.currentStage = 'all';
      state.replayMode = 'all';
      state.sourceSystem = 'all';
      state.sourceEntityType = 'all';
      state.compareOutcome = 'all';
      state.approvalStatus = 'all';
      state.executionStatus = 'all';
      state.reviewPriority = 'all';
      state.reasonCode = 'all';
      state.reviewStage = 'all';
      state.sortMode = 'priority-stage-key';
      state.reviewOnly = false;
      syncControlsFromState();
      render();
    }

    function handleModelFile(event) {
      const file = event.target.files && event.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const parsed = JSON.parse(String(reader.result || '{}'));
          if (!parsed || !Array.isArray(parsed.records) || !parsed.rollup) {
            window.alert('The selected file does not look like an operator console model JSON file.');
            return;
          }
          model = parsed;
          state.selectedSourceKey = model.records[0] ? model.records[0].source_key : null;
          syncControlsFromState();
          render();
        } catch (error) {
          window.alert('Unable to parse that JSON file.');
        }
      };
      reader.readAsText(file);
    }

    els.search.addEventListener('input', () => { state.search = els.search.value; saveState(); render(); });
    els.stageFilter.addEventListener('change', () => { state.currentStage = els.stageFilter.value; saveState(); render(); });
    els.modeFilter.addEventListener('change', () => { state.replayMode = els.modeFilter.value; saveState(); render(); });
    els.systemFilter.addEventListener('change', () => { state.sourceSystem = els.systemFilter.value; saveState(); render(); });
    els.entityFilter.addEventListener('change', () => { state.sourceEntityType = els.entityFilter.value; saveState(); render(); });
    els.compareFilter.addEventListener('change', () => { state.compareOutcome = els.compareFilter.value; saveState(); render(); });
    els.approvalFilter.addEventListener('change', () => { state.approvalStatus = els.approvalFilter.value; saveState(); render(); });
    els.executionFilter.addEventListener('change', () => { state.executionStatus = els.executionFilter.value; saveState(); render(); });
    els.priorityFilter.addEventListener('change', () => { state.reviewPriority = els.priorityFilter.value; saveState(); render(); });
    els.reasonFilter.addEventListener('change', () => { state.reasonCode = els.reasonFilter.value; saveState(); render(); });
    els.queueFilter.addEventListener('change', () => { state.reviewStage = els.queueFilter.value; saveState(); render(); });
    els.sortFilter.addEventListener('change', () => { state.sortMode = els.sortFilter.value; saveState(); render(); });
    els.reviewOnlyToggle.addEventListener('click', () => { state.reviewOnly = !state.reviewOnly; saveState(); syncControlsFromState(); render(); });
    els.resetFiltersBtn.addEventListener('click', resetFilters);
    els.exportJsonBtn.addEventListener('click', exportFilteredJson);
    els.exportCsvBtn.addEventListener('click', exportFilteredCsv);
    els.copySelectedBtn.addEventListener('click', copySelectedJson);
    els.loadModelInput.addEventListener('change', handleModelFile);
    els.tabOverview.addEventListener('click', () => setActiveDetailTab('overview'));
    els.tabReviewItems.addEventListener('click', () => setActiveDetailTab('review'));
    els.tabRawJson.addEventListener('click', () => setActiveDetailTab('raw'));

    if (!state.selectedSourceKey && model.records && model.records.length) {
      state.selectedSourceKey = model.records[0].source_key;
    }
    syncControlsFromState();
    render();
  </script>
</body>
</html>
"""
    return template.replace("__TITLE__", title).replace("__PAYLOAD__", payload)



def write_operator_console_alpha_artifacts(out_dir: str | Path, artifacts: dict[str, dict]) -> None:
    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)

    (path / "operator_console_alpha_model.json").write_text(
        json.dumps(artifacts["operator_console_alpha_model"], indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (path / "operator_console_alpha_rollup.json").write_text(
        json.dumps(artifacts["operator_console_alpha_rollup"], indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (path / "operator_console_alpha.html").write_text(
        artifacts["operator_console_alpha_html"]["html"],
        encoding="utf-8",
    )
