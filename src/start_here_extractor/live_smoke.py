from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .security import redact_sensitive_fields


@dataclass(slots=True)
class LiveSmokeSummary:
    provider: str
    query: str
    cli_exit_code: int
    classification: str
    success: bool
    reason: str | None = None
    inventory_count: int = 0
    monitoring_event_count: int = 0
    audit_event_count: int = 0
    source_type: str | None = None
    zip_path: str | None = None
    outcome: str | None = None
    auth_state: str | None = None
    rate_limited: bool = False
    review_required: bool = False
    retry_count: int | None = None
    throttle_count: int | None = None
    policy_decision: str | None = None
    inventory_path: str | None = None
    monitoring_path: str | None = None
    audit_path: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_text(path: str | Path | None) -> str:
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _read_jsonl(path: str | Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    file_path = Path(path)
    if not file_path.exists():
        return []
    records: list[dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                break
            if isinstance(value, dict):
                records.append(redact_sensitive_fields(value))
    return records


def _find_inventory_paths(report_dir: str | Path | None) -> list[Path]:
    if not report_dir:
        return []
    root = Path(report_dir)
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.inventory.jsonl") if path.is_file())


def _first_jsonl_path(directory: str | Path | None) -> Path | None:
    if not directory:
        return None
    root = Path(directory)
    if not root.exists():
        return None
    matches = sorted(path for path in root.rglob("*.jsonl") if path.is_file())
    return matches[0] if matches else None


def _contains_any(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def _unique_notes(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        note = str(value).strip()
        if note and note not in result:
            result.append(note)
    return result


def classify_live_smoke_run(
    *,
    provider: str,
    query: str,
    cli_exit_code: int,
    inventory_records: list[dict[str, Any]] | None = None,
    monitoring_records: list[dict[str, Any]] | None = None,
    audit_records: list[dict[str, Any]] | None = None,
    stderr_text: str = "",
    stdout_text: str = "",
    inventory_path: str | None = None,
    monitoring_path: str | None = None,
    audit_path: str | None = None,
) -> LiveSmokeSummary:
    inventories = list(inventory_records or [])
    monitoring = list(monitoring_records or [])
    audits = list(audit_records or [])
    record = inventories[0] if inventories else {}
    monitoring_block = record.get("monitoring") if isinstance(record.get("monitoring"), dict) else {}
    provider_state = monitoring_block.get("provider_state") if isinstance(monitoring_block.get("provider_state"), dict) else {}
    quota = provider_state.get("quota") if isinstance(provider_state.get("quota"), dict) else {}
    retry = provider_state.get("retry") if isinstance(provider_state.get("retry"), dict) else {}
    provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
    errors = record.get("errors") if isinstance(record.get("errors"), list) else []
    warnings = record.get("warnings") if isinstance(record.get("warnings"), list) else []

    notes = _unique_notes(
        [*(provider_state.get("notes") or []), *(warnings or []), *(error.get("message") for error in errors if isinstance(error, dict))]
    )
    combined_logs = "\n".join(part for part in [stderr_text, stdout_text] if part).lower()

    classification = "unknown"
    reason: str | None = None
    success = False

    if inventories:
        outcome = str(record.get("outcome") or "")
        source_type = provenance.get("source_type") or provider
        if cli_exit_code == 0 and outcome and outcome != "error":
            classification = "success"
            reason = "Remote discovery, download, and ZIP processing completed successfully."
            success = True
            if monitoring_block.get("review_required"):
                notes = _unique_notes([*notes, "review-required"])
        elif provider_state.get("auth_state") == "failed":
            classification = "auth-failed"
            reason = "Provider authentication failed during the hosted smoke run."
        elif provider_state.get("rate_limited") or quota.get("rate_limited"):
            classification = "rate-limited"
            reason = "Provider rate limiting affected the hosted smoke run."
        elif _contains_any("\n".join(notes), ["operator approval"]):
            classification = "operator-approval-required"
            reason = "Hosted smoke run requires an operator approval reference."
        elif outcome == "error":
            classification = "processing-failed"
            reason = "ZIP discovery succeeded but downstream processing finished in error."
        else:
            classification = "provider-failed" if cli_exit_code else "incomplete-success"
            reason = "Hosted smoke run produced inventory output but did not satisfy the normal success shape."
        return LiveSmokeSummary(
            provider=provider,
            query=query,
            cli_exit_code=cli_exit_code,
            classification=classification,
            success=success,
            reason=reason,
            inventory_count=len(inventories),
            monitoring_event_count=len(monitoring),
            audit_event_count=len(audits),
            source_type=str(source_type) if source_type else None,
            zip_path=str(record.get("zip_path") or "") or None,
            outcome=outcome or None,
            auth_state=str(provider_state.get("auth_state") or "") or None,
            rate_limited=bool(provider_state.get("rate_limited") or quota.get("rate_limited")),
            review_required=bool(monitoring_block.get("review_required")),
            retry_count=int(retry.get("observed_retries")) if isinstance(retry.get("observed_retries"), int) else None,
            throttle_count=int(quota.get("throttle_count")) if isinstance(quota.get("throttle_count"), int) else None,
            policy_decision=str((record.get("policy_decision") or {}).get("decision") or "") or None,
            inventory_path=inventory_path,
            monitoring_path=monitoring_path,
            audit_path=audit_path,
            notes=notes,
        )

    if cli_exit_code == 0:
        classification = "incomplete-success"
        reason = "CLI exited successfully but no inventory artifact was produced."
    elif _contains_any(combined_logs, ["no remote zip files found"]):
        classification = "no-remote-zip"
        reason = "No remote ZIP files matched the hosted smoke query."
    elif _contains_any(
        combined_logs,
        [
            "missing-cloud-access-token",
            "missing-live-smoke-access-token",
            "token-command-failed",
            "missing token secret",
        ],
    ):
        classification = "token-resolution-failed"
        reason = "Hosted smoke token resolution failed before provider operations began."
    elif _contains_any(
        combined_logs,
        [
            "operatorapprovalrequirederror",
            "operator approval required",
            "operator-approval-required",
        ],
    ):
        classification = "operator-approval-required"
        reason = "Hosted smoke run requires an operator approval reference."
    elif _contains_any(
        combined_logs,
        [
            "http-auth-error:401",
            "http-auth-error:403",
            "provider-auth-failed",
            "remoteautherror",
            "unauthorized",
            "forbidden",
            "token-expired",
        ],
    ):
        classification = "auth-failed"
        reason = "Provider authentication failed during remote discovery or download."
    elif _contains_any(
        combined_logs,
        [
            "http-retryable-error:429",
            "too-many-requests",
            "rate limit",
            "provider-rate-limit-exhausted",
            "retry-after",
        ],
    ):
        classification = "rate-limited"
        reason = "Provider throttling exhausted the hosted smoke retry budget."
    else:
        classification = "provider-failed"
        reason = "Hosted smoke run failed before inventory output was produced."

    return LiveSmokeSummary(
        provider=provider,
        query=query,
        cli_exit_code=cli_exit_code,
        classification=classification,
        success=False,
        reason=reason,
        inventory_count=0,
        monitoring_event_count=len(monitoring),
        audit_event_count=len(audits),
        inventory_path=inventory_path,
        monitoring_path=monitoring_path,
        audit_path=audit_path,
        notes=notes,
    )


def build_live_smoke_summary(
    *,
    provider: str,
    query: str,
    cli_exit_code: int,
    report_dir: str | Path | None,
    monitoring_dir: str | Path | None = None,
    audit_dir: str | Path | None = None,
    stdout_log: str | Path | None = None,
    stderr_log: str | Path | None = None,
) -> LiveSmokeSummary:
    inventory_paths = _find_inventory_paths(report_dir)
    inventory_path = str(inventory_paths[0]) if inventory_paths else None
    monitoring_path = str(_first_jsonl_path(monitoring_dir)) if monitoring_dir else None
    audit_path = str(_first_jsonl_path(audit_dir)) if audit_dir else None
    return classify_live_smoke_run(
        provider=provider,
        query=query,
        cli_exit_code=cli_exit_code,
        inventory_records=_read_jsonl(inventory_path),
        monitoring_records=_read_jsonl(monitoring_path),
        audit_records=_read_jsonl(audit_path),
        stderr_text=_read_text(stderr_log),
        stdout_text=_read_text(stdout_log),
        inventory_path=inventory_path,
        monitoring_path=monitoring_path,
        audit_path=audit_path,
    )


def render_live_smoke_markdown(summary: LiveSmokeSummary) -> str:
    success_text = "yes" if summary.success else "no"
    lines = [
        "# Live smoke summary",
        "",
        f"- Provider: `{summary.provider}`",
        f"- Query: `{summary.query}`",
        f"- Success: **{success_text}**",
        f"- Classification: `{summary.classification}`",
        f"- CLI exit code: `{summary.cli_exit_code}`",
        f"- Inventory records: `{summary.inventory_count}`",
        f"- Monitoring events: `{summary.monitoring_event_count}`",
        f"- Audit events: `{summary.audit_event_count}`",
    ]
    optional_rows = [
        ("Source type", summary.source_type),
        ("ZIP path", summary.zip_path),
        ("Outcome", summary.outcome),
        ("Auth state", summary.auth_state),
        ("Rate limited", str(summary.rate_limited).lower() if summary.rate_limited else None),
        ("Retry count", str(summary.retry_count) if summary.retry_count is not None else None),
        ("Throttle count", str(summary.throttle_count) if summary.throttle_count is not None else None),
        ("Policy decision", summary.policy_decision),
        ("Review required", str(summary.review_required).lower() if summary.review_required else None),
        ("Reason", summary.reason),
        ("Inventory artifact", summary.inventory_path),
        ("Monitoring artifact", summary.monitoring_path),
        ("Audit artifact", summary.audit_path),
    ]
    for label, value in optional_rows:
        if value:
            lines.append(f"- {label}: `{value}`" if label.endswith("artifact") or label in {"Source type", "ZIP path", "Outcome", "Auth state", "Policy decision"} else f"- {label}: {value}")
    if summary.notes:
        lines.extend(["- Notes:"])
        for note in summary.notes:
            lines.append(f"  - `{note}`")
    return "\n".join(lines) + "\n"
