from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from .audit import audit_append
from .governance import build_governance_block
from .heuristics import detect_dangerous_instructions
from .monitoring import build_monitoring_block, monitoring_append
from .policy import derive_governance_policy
from .retention import derive_retention_decision
from .security import redact_sensitive_fields
from .summary import summarize_inventory_preview
from .utils import ensure_dir, safe_slug


SCHEMA_VERSION = "4.2"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_inventory_record(
    payload: Dict[str, object],
    *,
    audit_dir: Path | None = None,
    durable_audit: bool = False,
    audit_stream_name: str = "audit-events",
    monitoring_dir: Path | None = None,
    durable_monitoring: bool = False,
    monitoring_stream_name: str = "monitoring-events",
) -> Dict[str, object]:
    record = dict(payload)
    record.setdefault("schema_version", SCHEMA_VERSION)
    record.setdefault("generated_at", utcnow_iso())
    runtime_cloud = record.pop("_runtime_cloud", {}) if isinstance(record.get("_runtime_cloud"), dict) else {}

    zip_file = record.get("zip_file") or {}
    selected = record.get("selected_candidate") or {}
    extracted = record.get("extracted_file") or {}
    preview = record.get("preview") or {}
    av = record.get("av") or {
        "status": "not-run",
        "engine": None,
        "exit_code": None,
        "findings": [],
        "av": {"engine": None, "status": "not-run", "exit_code": None, "findings": []},
        "yara": {"ruleset_id": None, "status": "not-run", "matches": [], "compiled_rules": False},
    }
    risk_flags = list(record.get("risk_flags") or [])
    policy = record.get("policy") or {}

    record.setdefault("zip_path", zip_file.get("path"))
    record.setdefault("start_here", selected.get("name"))
    record.setdefault("size_bytes", extracted.get("size_bytes") or selected.get("declared_file_size"))
    record.setdefault("md5", extracted.get("md5") or zip_file.get("md5"))
    record.setdefault("encoding", preview.get("encoding"))
    record.setdefault("preview_text", preview.get("text"))
    record.setdefault("scan", av)
    warnings = list(record.get("warnings") or [])
    warnings.extend(flag for flag in risk_flags if flag not in warnings)
    if policy.get("decision") in {"warn", "sandbox"}:
        for note in [policy.get("reason"), *(policy.get("notes") or [])]:
            if note and note not in warnings:
                warnings.append(str(note))
    token_health = runtime_cloud.get("token_health") if isinstance(runtime_cloud, dict) else None
    provider_health = runtime_cloud.get("provider_health") if isinstance(runtime_cloud, dict) else None
    if isinstance(token_health, dict):
        token_health = redact_sensitive_fields(token_health)
    if isinstance(provider_health, dict):
        provider_health = redact_sensitive_fields(provider_health)
    if isinstance(token_health, dict):
        for note in token_health.get("notes") or []:
            if note not in warnings:
                warnings.append(str(note))
    if isinstance(provider_health, dict):
        for note in provider_health.get("notes") or []:
            if note not in warnings:
                warnings.append(str(note))
    record["warnings"] = warnings
    record.setdefault("errors", [])

    record.setdefault(
        "text_summary",
        {
            "preview": preview.get("text"),
            "encoding": preview.get("encoding"),
            "truncated": False,
        }
        if preview
        else None,
    )
    record.setdefault(
        "match",
        {
            "candidate_names": [candidate.get("name") for candidate in (record.get("inspection") or {}).get("candidates", [])],
            "selected": selected.get("name"),
        },
    )
    record.setdefault(
        "extraction",
        {
            "mode": "single-member" if extracted else None,
            "output_path": extracted.get("path"),
            "bytes_written": extracted.get("size_bytes"),
        },
    )
    record.setdefault("run", None)
    record.setdefault("provenance", None)
    record.setdefault("sandbox", None)
    record.setdefault("zip_hardening", None)
    record.setdefault("policy", None)
    record.setdefault("batch", None)

    preview_text = str(record.get("preview_text") or "")
    heuristics_findings = record.get("heuristics_findings") or detect_dangerous_instructions(preview_text)
    record["heuristics_findings"] = heuristics_findings
    record["summary"] = record.get("summary") or summarize_inventory_preview(record)

    settings = record.get("settings") if isinstance(record.get("settings"), dict) else {}
    extract_settings = settings.get("extract_settings") if isinstance(settings.get("extract_settings"), dict) else {}
    sandbox_available = bool(extract_settings.get("sandbox_platform"))
    policy_decision = record.get("policy_decision") or derive_governance_policy(
        operational_policy=record.get("policy") if isinstance(record.get("policy"), dict) else {},
        heuristics_findings=heuristics_findings,
        scan=record.get("scan") if isinstance(record.get("scan"), dict) else {},
        sandbox_available=sandbox_available,
    )
    record["policy_decision"] = policy_decision

    retention = derive_retention_decision(
        record,
        retention_days=int(extract_settings.get("retention_days") or 30),
        legal_hold=bool(extract_settings.get("legal_hold")),
    ).to_dict()
    record["retention_status"] = retention["status"]

    audit_stream_ref = None
    if audit_dir is not None:
        record["audit_ref"] = audit_append(record, audit_dir, durable=durable_audit, stream_name=audit_stream_name)
        audit_stream_ref = f"audit://{(audit_dir / f'{audit_stream_name}.jsonl').as_posix()}"
    else:
        record.setdefault("audit_ref", None)

    monitoring_stream_ref = None
    record["governance"] = record.get("governance") or build_governance_block(
        record,
        operator_approval_ref=extract_settings.get("cloud_operator_approval_ref"),
        require_operator_approval_for_abuse=bool(extract_settings.get("cloud_require_operator_approval_for_abuse", True)),
        acknowledge_abuse=bool(extract_settings.get("cloud_acknowledge_abuse", False)),
        audit_stream_ref=audit_stream_ref,
        retention=retention,
        monitoring_stream_ref=monitoring_stream_ref,
        token_health=token_health,
    )
    record["monitoring"] = record.get("monitoring") or build_monitoring_block(record, token_health=token_health, provider_health=provider_health)
    if monitoring_dir is not None:
        record["monitoring_ref"] = monitoring_append(record, monitoring_dir, durable=durable_monitoring, stream_name=monitoring_stream_name)
        monitoring_stream_ref = f"monitoring://{(monitoring_dir / f'{monitoring_stream_name}.jsonl').as_posix()}"
        record["governance"] = build_governance_block(
            record,
            operator_approval_ref=extract_settings.get("cloud_operator_approval_ref"),
            require_operator_approval_for_abuse=bool(extract_settings.get("cloud_require_operator_approval_for_abuse", True)),
            acknowledge_abuse=bool(extract_settings.get("cloud_acknowledge_abuse", False)),
            audit_stream_ref=audit_stream_ref,
            retention=retention,
            monitoring_stream_ref=monitoring_stream_ref,
            token_health=token_health,
        )
    else:
        record.setdefault("monitoring_ref", None)
    return redact_sensitive_fields(record)


def write_inventory(
    report_dir: Path,
    zip_path: Path,
    payload: Dict[str, object],
    *,
    durable_audit: bool = False,
    audit_stream_name: str = "audit-events",
    monitoring_dir: Path | None = None,
    durable_monitoring: bool = False,
    monitoring_stream_name: str = "monitoring-events",
) -> Path:
    ensure_dir(report_dir)
    name = safe_slug(zip_path.stem) + ".inventory.jsonl"
    out_path = report_dir / name
    record = build_inventory_record(
        payload,
        audit_dir=report_dir / "_audit",
        durable_audit=durable_audit,
        audit_stream_name=audit_stream_name,
        monitoring_dir=monitoring_dir or (report_dir / "_monitoring"),
        durable_monitoring=durable_monitoring,
        monitoring_stream_name=monitoring_stream_name,
    )
    line = json.dumps(record, ensure_ascii=False)
    out_path.write_text(line + "\n", encoding="utf-8", newline="\n")
    return out_path
