from __future__ import annotations

from typing import Mapping


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def summarize_inventory_preview(record: Mapping[str, object]) -> dict:
    preview = record.get("preview") if isinstance(record.get("preview"), Mapping) else {}
    inspection = record.get("inspection") if isinstance(record.get("inspection"), Mapping) else {}
    selected = record.get("selected_candidate") if isinstance(record.get("selected_candidate"), Mapping) else {}
    extracted = record.get("extracted_file") if isinstance(record.get("extracted_file"), Mapping) else {}
    outcome = str(record.get("outcome") or "unknown")
    preview_text = str((preview or {}).get("text") or "").strip()
    candidate_name = str((selected or {}).get("name") or record.get("start_here") or "")
    entry_count = (inspection or {}).get("entry_count")
    bytes_written = (extracted or {}).get("size_bytes")

    observations: list[str] = []
    limitations: list[str] = ["Summary uses inventory plus bounded preview only."]
    evidence_refs = ["inspection", "preview", "selected_candidate"]

    if entry_count is not None:
        observations.append(f"Archive inspection saw {entry_count} entr{'y' if entry_count == 1 else 'ies'}.")
    if candidate_name:
        observations.append(f"Matched START HERE candidate: {candidate_name}.")
    if bytes_written is not None and outcome == "extracted":
        observations.append(f"Extracted file size: {bytes_written} bytes.")

    if preview_text:
        lines = [line.strip() for line in preview_text.splitlines() if line.strip()]
        first_line = _truncate(lines[0], 120) if lines else _truncate(preview_text, 120)
        headline = f"{outcome.title()} START HERE content detected."
        observations.append(f"Preview begins: {first_line}")
        return {
            "status": "available",
            "source": "inventory+preview-only",
            "headline": headline,
            "brief": _truncate(preview_text.replace("\n", " "), 240),
            "observations": observations[:5],
            "limitations": limitations,
            "evidence_refs": evidence_refs,
        }

    limitations.append("No preview text was available for summarization.")
    headline = f"{outcome.title()} record without preview text."
    if outcome == "error":
        headline = "Error record with no preview available."
    return {
        "status": "unavailable",
        "source": "inventory+preview-only",
        "headline": headline,
        "brief": None,
        "observations": observations[:5],
        "limitations": limitations,
        "evidence_refs": evidence_refs,
    }
