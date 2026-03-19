from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from .utils import ensure_dir, safe_slug


SCHEMA_VERSION = "3.2"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_inventory_record(payload: Dict[str, object]) -> Dict[str, object]:
    record = dict(payload)
    record.setdefault("schema_version", SCHEMA_VERSION)
    record.setdefault("generated_at", utcnow_iso())

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
    return record


def write_inventory(report_dir: Path, zip_path: Path, payload: Dict[str, object]) -> Path:
    ensure_dir(report_dir)
    name = safe_slug(zip_path.stem) + ".inventory.jsonl"
    out_path = report_dir / name
    record = build_inventory_record(payload)
    line = json.dumps(record, ensure_ascii=False)
    out_path.write_text(line + "\n", encoding="utf-8", newline="\n")
    return out_path
