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


def _derive_current_stage(*, compare_review: list[dict], approval_queue: list[dict], execution_review: list[dict], execution_status: str | None, approval_status: str | None, compare_outcome: str | None, replay_mode: str | None, has_plan: bool) -> str:
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


def build_operator_console_alpha_artifacts(
    *args: dict[str, dict],
    plan_documents: dict[str, dict] | None = None,
    compare_documents: dict[str, dict] | None = None,
    approval_documents: dict[str, dict] | None = None,
    execution_documents: dict[str, dict] | None = None,
    title: str = "Source Replay Operator Console Alpha",
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

    records: list[dict] = []
    current_stage_counts: dict[str, int] = {}
    replay_mode_counts: dict[str, int] = {}
    source_system_counts: dict[str, int] = {}
    compare_outcome_counts: dict[str, int] = {}
    approval_status_counts: dict[str, int] = {}
    execution_status_counts: dict[str, int] = {}

    for source_key in source_keys:
        plan = plan_map.get(source_key, {})
        compare = compare_map.get(source_key, {})
        approval = approval_map.get(source_key, {})
        execution = execution_map.get(source_key, {})
        plan_review = plan_review_map.get(source_key, [])
        compare_review = compare_review_map.get(source_key, [])
        approval_queue = approval_queue_map.get(source_key, [])
        execution_review = execution_review_map.get(source_key, [])

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
        for collection in (plan_review, compare_review, approval_queue, execution_review):
            for item in collection:
                for reason in item.get("reason_codes") or []:
                    if isinstance(reason, str):
                        _append_unique(reason_codes, reason)

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
        if compare_outcome:
            compare_outcome_counts[compare_outcome] = compare_outcome_counts.get(compare_outcome, 0) + 1
        if approval_status:
            approval_status_counts[approval_status] = approval_status_counts.get(approval_status, 0) + 1
        if execution_status:
            execution_status_counts[execution_status] = execution_status_counts.get(execution_status, 0) + 1

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
                "review_priority": (
                    _normalize_text((execution_review or approval_queue or compare_review or plan_review or [{}])[0].get("priority"))
                    if (execution_review or approval_queue or compare_review or plan_review)
                    else None
                ),
                "reason_codes": reason_codes,
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
            }
        )

    rollup = {
        "schema_version": OPERATOR_CONSOLE_ALPHA_SCHEMA_VERSION,
        "generated_at": execution_documents.get("source_replay_execution_rollup", {}).get("generated_at")
        or approval_documents.get("source_replay_approval_rollup", {}).get("generated_at")
        or compare_documents.get("source_replay_compare_rollup", {}).get("generated_at")
        or plan_documents.get("source_replay_plan_rollup", {}).get("generated_at"),
        "source_count": len(records),
        "current_stage_counts": current_stage_counts,
        "replay_mode_counts": replay_mode_counts,
        "source_system_counts": source_system_counts,
        "compare_outcome_counts": compare_outcome_counts,
        "approval_status_counts": approval_status_counts,
        "execution_status_counts": execution_status_counts,
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
        "generated_at": rollup.get("generated_at"),
        "summary": {
            "plan_count": len(plan_records),
            "compare_count": len(compare_records),
            "approval_journal_count": len(approval_journal_records),
            "execution_pack_count": len(execution_records),
            "compare_review_count": len(compare_review_records),
            "approval_review_count": len(approval_queue_records),
            "execution_review_count": len(execution_review_records),
        },
        "rollup": rollup,
        "records": records,
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
    :root { color-scheme: light dark; --bg: #0f172a; --panel: #111827; --panel2: #1f2937; --text: #e5e7eb; --muted: #9ca3af; --accent: #38bdf8; --ok: #10b981; --warn: #f59e0b; --bad: #ef4444; }
    body { margin: 0; font-family: Arial, Helvetica, sans-serif; background: var(--bg); color: var(--text); }
    .wrap { max-width: 1400px; margin: 0 auto; padding: 24px; }
    h1 { margin: 0 0 8px; font-size: 30px; }
    .sub { color: var(--muted); margin-bottom: 10px; }
    .info-banner { display: flex; gap: 10px; align-items: flex-start; background: rgba(56, 189, 248, 0.08); border: 1px solid #334155; border-radius: 14px; padding: 12px 14px; margin-bottom: 18px; color: var(--text); }
    .info-banner .icon { color: var(--accent); font-weight: 700; }
    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 18px; }
    .card { background: var(--panel); border: 1px solid #334155; border-radius: 14px; padding: 14px; box-shadow: 0 4px 20px rgba(0,0,0,.18); }
    .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; display: flex; align-items: center; gap: 6px; }
    .value { margin-top: 8px; font-size: 28px; font-weight: 700; }
    .filters { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 12px; margin-bottom: 16px; }
    .control { display: block; }
    .control-label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
    input, select { width: 100%; box-sizing: border-box; padding: 11px 12px; border-radius: 10px; border: 1px solid #334155; background: var(--panel2); color: var(--text); }
    .layout { display: grid; grid-template-columns: 1.3fr .9fr; gap: 16px; }
    table { width: 100%; border-collapse: collapse; }
    thead th { text-align: left; font-size: 12px; color: var(--muted); padding: 10px 8px; border-bottom: 1px solid #334155; }
    thead th .th-wrap { display: inline-flex; align-items: center; gap: 6px; }
    tbody td { padding: 10px 8px; border-bottom: 1px solid #1f2937; vertical-align: top; }
    tbody tr { cursor: pointer; }
    tbody tr:hover { background: rgba(56, 189, 248, 0.08); }
    .badge { display: inline-block; padding: 4px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; }
    .stage-execution-ready { background: rgba(16,185,129,.18); color: #a7f3d0; }
    .stage-completed-no-op { background: rgba(56,189,248,.18); color: #bae6fd; }
    .stage-approval-review, .stage-compare-review, .stage-execution-review { background: rgba(245,158,11,.18); color: #fde68a; }
    .stage-unknown, .stage-planned, .stage-compared, .stage-approved, .stage-rejected { background: rgba(156,163,175,.18); color: #e5e7eb; }
    pre { white-space: pre-wrap; word-break: break-word; background: #020617; border: 1px solid #1e293b; border-radius: 12px; padding: 12px; max-height: 70vh; overflow: auto; }
    .muted { color: var(--muted); }
    .help-tab { display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px; border-radius: 999px; border: 1px solid #334155; background: rgba(56, 189, 248, 0.12); color: var(--accent); font-size: 11px; font-weight: 700; cursor: help; position: relative; flex: 0 0 auto; }
    .help-tab:hover::after, .help-tab:focus::after {
      content: attr(data-help);
      position: absolute;
      left: 50%;
      top: calc(100% + 8px);
      transform: translateX(-50%);
      width: 260px;
      max-width: 40vw;
      background: #020617;
      color: var(--text);
      border: 1px solid #334155;
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
      border-bottom: 7px solid #334155;
      z-index: 31;
    }
    @media (max-width: 1100px) { .layout { grid-template-columns: 1fr; } .filters { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>__TITLE__</h1>
    <div class="sub" id="subtitle"></div>
    <div class="info-banner">
      <div class="icon">ⓘ</div>
      <div>
        Hover any <strong>?</strong> help tab to learn what a control or metric does.
        Anything clickable also includes hover guidance explaining what happens when you click it.
      </div>
    </div>
    <div class="cards" id="cards"></div>
    <div class="filters">
      <label class="control" for="search">
        <div class="control-label">
          Search Sources
          <span class="help-tab" tabindex="0" data-help="Type here to filter the visible rows by source key, source system, entity type, replay mode, compare outcome, approval decision, or execution status. This only changes what is shown on screen.">?</span>
        </div>
        <input id="search" type="search" title="Type to filter the visible rows. This does not change underlying data." placeholder="Search source key, system, entity, replay mode">
      </label>
      <label class="control" for="stageFilter">
        <div class="control-label">
          Current Stage Filter
          <span class="help-tab" tabindex="0" data-help="Choose a current stage to narrow the visible rows. This helps you focus on records that are planned, under review, approved, or ready for execution.">?</span>
        </div>
        <select id="stageFilter" title="Choose a stage to limit the visible rows without changing any data."></select>
      </label>
      <label class="control" for="modeFilter">
        <div class="control-label">
          Replay Mode Filter
          <span class="help-tab" tabindex="0" data-help="Choose a replay mode to narrow the visible rows. Use this to isolate compare-only, resume-from-approved, or full-replay records.">?</span>
        </div>
        <select id="modeFilter" title="Choose a replay mode to limit the visible rows without changing any data."></select>
      </label>
    </div>
    <div class="layout">
      <div class="card" title="This table shows one merged operator-facing row per source record across planning, comparison, approval, and execution. Click any row to inspect the full payload and review evidence.">
        <div class="label" style="margin-bottom: 8px;">
          Source Replay Records
          <span class="help-tab" tabindex="0" data-help="This table merges the latest planning, comparison, approval, and execution state for each source key. Click any row to inspect the full payload and review evidence for that source.">?</span>
        </div>
        <table>
          <thead>
            <tr>
              <th title="The unique source key and source entity type for this replay record."><span class="th-wrap">Source Key <span class="help-tab" tabindex="0" data-help="The source key identifies the replay record and is paired with the source entity type shown underneath it.">?</span></span></th>
              <th title="The current stage in the replay workflow for this source."><span class="th-wrap">Stage <span class="help-tab" tabindex="0" data-help="The current stage shows where the source sits in the replay workflow, such as planned, compare review, approval review, execution ready, or execution review.">?</span></span></th>
              <th title="The replay mode selected for this source."><span class="th-wrap">Replay Mode <span class="help-tab" tabindex="0" data-help="Replay mode shows whether the source is compare-only, resume-from-approved, or full-replay.">?</span></span></th>
              <th title="The source system that produced this record."><span class="th-wrap">System <span class="help-tab" tabindex="0" data-help="System identifies the originating system, such as RingCentral or Less Annoying CRM.">?</span></span></th>
              <th title="The comparison outcome generated for this source."><span class="th-wrap">Compare <span class="help-tab" tabindex="0" data-help="Compare shows the replay comparison outcome, such as match, drift, blocked, or review-required.">?</span></span></th>
              <th title="The latest approval status or decision for this source."><span class="th-wrap">Approval <span class="help-tab" tabindex="0" data-help="Approval shows the latest journaled decision or approval status for this source.">?</span></span></th>
              <th title="The current execution pack status for this source."><span class="th-wrap">Execution <span class="help-tab" tabindex="0" data-help="Execution shows whether a source is ready for dry run, requires review, or resolves as a no-op.">?</span></span></th>
            </tr>
          </thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
      <div class="card">
        <div class="label">
          Record Detail
          <span class="help-tab" tabindex="0" data-help="This panel shows the merged record payload and related review evidence for the currently selected source row.">?</span>
        </div>
        <div class="muted" style="margin: 8px 0 12px">Click a row to inspect the full merged record payload.</div>
        <pre id="detail" title="This panel updates when you click a row in the table.">Select a row to inspect details.</pre>
      </div>
    </div>
  </div>
  <script>
    const MODEL = __PAYLOAD__;
    const rowsEl = document.getElementById('rows');
    const cardsEl = document.getElementById('cards');
    const detailEl = document.getElementById('detail');
    const searchEl = document.getElementById('search');
    const stageFilterEl = document.getElementById('stageFilter');
    const modeFilterEl = document.getElementById('modeFilter');
    const subtitleEl = document.getElementById('subtitle');

    function helpTab(helpText) {
      return '<span class="help-tab" tabindex="0" data-help="' + helpText + '">?</span>';
    }

    subtitleEl.textContent = 'Generated: ' + (MODEL.generated_at || 'unknown') + ' · Sources: ' + MODEL.rollup.source_count;

    const cardSpecs = [
      ['Plans', MODEL.summary.plan_count, 'Number of replay plan records generated from readiness packs. This is the planning baseline feeding the rest of the workflow.'],
      ['Compare', MODEL.summary.compare_count, 'Number of comparison records generated from replay plans. These show whether a source matches, drifts, or needs review.'],
      ['Approvals', MODEL.summary.approval_journal_count, 'Number of journaled approval decisions recorded so far. These decisions feed execution eligibility.'],
      ['Execution Packs', MODEL.summary.execution_pack_count, 'Number of execution packs prepared for dry run or downstream replay handling.'],
      ['Compare Review', MODEL.summary.compare_review_count, 'Count of sources that still need human review after comparison.'],
      ['Approval Review', MODEL.summary.approval_review_count, 'Count of sources waiting on an approval decision before execution can proceed.'],
      ['Execution Review', MODEL.summary.execution_review_count, 'Count of sources blocked for execution review instead of being marked ready.'],
    ];
    cardsEl.innerHTML = cardSpecs.map(([label, value, help]) =>
      '<div class="card" title="' + help + '">' +
        '<div class="label">' + label + helpTab(help) + '</div>' +
        '<div class="value">' + value + '</div>' +
      '</div>'
    ).join('');

    const stages = ['all', ...new Set(MODEL.records.map((row) => row.current_stage).filter(Boolean))];
    const modes = ['all', ...new Set(MODEL.records.map((row) => row.replay_mode).filter(Boolean))];
    stageFilterEl.innerHTML = stages.map((value) => '<option value="' + value + '">Stage: ' + value + '</option>').join('');
    modeFilterEl.innerHTML = modes.map((value) => '<option value="' + value + '">Mode: ' + value + '</option>').join('');

    function stageBadge(stage) {
      const safe = (stage || 'unknown').replace(/[^a-z0-9-]/gi, '-').toLowerCase();
      return '<span class="badge stage-' + safe + '">' + (stage || 'unknown') + '</span>';
    }

    function renderRows() {
      const q = searchEl.value.trim().toLowerCase();
      const stage = stageFilterEl.value;
      const mode = modeFilterEl.value;
      const filtered = MODEL.records.filter((row) => {
        const haystack = [row.source_key, row.source_system, row.source_entity_type, row.migration_profile, row.replay_mode, row.compare_outcome, row.approval_decision, row.execution_status].join(' ').toLowerCase();
        if (q && !haystack.includes(q)) return false;
        if (stage !== 'all' && row.current_stage !== stage) return false;
        if (mode !== 'all' && row.replay_mode !== mode) return false;
        return true;
      });
      rowsEl.innerHTML = filtered.map((row) =>
        '<tr data-index="' + MODEL.records.indexOf(row) + '" title="Click to inspect the full merged payload, review queue entries, and execution evidence for this source.">' +
          '<td><strong>' + row.source_key + '</strong><br><span class="muted">' + row.source_entity_type + '</span></td>' +
          '<td>' + stageBadge(row.current_stage) + '</td>' +
          '<td>' + (row.replay_mode || '') + '</td>' +
          '<td>' + (row.source_system || '') + '</td>' +
          '<td>' + (row.compare_outcome || '') + '</td>' +
          '<td>' + (row.approval_decision || row.approval_status || '') + '</td>' +
          '<td>' + (row.execution_status || '') + '</td>' +
        '</tr>'
      ).join('');
      if (!filtered.length) {
        rowsEl.innerHTML = '<tr><td colspan="7" class="muted">No rows match the current filters.</td></tr>';
      }
      rowsEl.querySelectorAll('tr[data-index]').forEach((rowEl) => {
        rowEl.addEventListener('click', () => {
          const item = MODEL.records[Number(rowEl.dataset.index)];
          detailEl.textContent = JSON.stringify(item, null, 2);
        });
      });
    }

    searchEl.addEventListener('input', renderRows);
    stageFilterEl.addEventListener('change', renderRows);
    modeFilterEl.addEventListener('change', renderRows);
    renderRows();
    if (MODEL.records.length) {
      detailEl.textContent = JSON.stringify(MODEL.records[0], null, 2);
    }
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
