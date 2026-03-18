from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from .utils import ensure_dir, safe_slug


SCHEMA_VERSION = "1.1"


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
    av = record.get("av") or {"status": "not-run"}
    risk_flags = list(record.get("risk_flags") or [])

    record.setdefault("zip_path", zip_file.get("path"))
    record.setdefault("start_here", selected.get("name"))
    record.setdefault("size_bytes", extracted.get("size_bytes") or selected.get("declared_file_size"))
    record.setdefault("md5", extracted.get("md5") or zip_file.get("md5"))
    record.setdefault("encoding", preview.get("encoding"))
    record.setdefault("preview_text", preview.get("text"))
    record.setdefault("scan", av)
    record.setdefault("warnings", risk_flags)
    record.setdefault("errors", [])

    return record


def write_inventory(report_dir: Path, zip_path: Path, payload: Dict[str, object]) -> Path:
    ensure_dir(report_dir)
    name = safe_slug(zip_path.stem) + ".inventory.jsonl"
    out_path = report_dir / name
    record = build_inventory_record(payload)
    line = json.dumps(record, ensure_ascii=False)
    out_path.write_text(line + "\n", encoding="utf-8", newline="\n")
    return out_path
