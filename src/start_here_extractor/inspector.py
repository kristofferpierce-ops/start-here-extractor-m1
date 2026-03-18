from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

from .errors import EntryLimitExceeded, ZipBombRisk
from .types import EntryInfo, Limits
from .utils import suspicious_zip_member


def inspect_zip(zip_path: Path, limits: Limits) -> Tuple[List[EntryInfo], Dict[str, object]]:
    with zipfile.ZipFile(zip_path, "r") as archive:
        infos = archive.infolist()
        if len(infos) > limits.max_entries:
            raise EntryLimitExceeded(f"ZIP contains {len(infos)} entries which exceeds cap {limits.max_entries}")

        entries: List[EntryInfo] = []
        risk_flags: List[str] = []
        for info in infos:
            suspicious, reasons = suspicious_zip_member(info.filename)
            ratio = None
            if not info.is_dir():
                if info.compress_size == 0 and info.file_size > 0:
                    ratio = float("inf")
                elif info.compress_size > 0:
                    ratio = round(info.file_size / info.compress_size, 4)

                if info.file_size > limits.max_member_bytes:
                    risk_flags.append(f"declared-size-cap:{info.filename}")
                if ratio is not None and ratio > limits.max_ratio:
                    risk_flags.append(f"compression-ratio-cap:{info.filename}")

            entries.append(
                EntryInfo(
                    name=info.filename,
                    is_dir=info.is_dir(),
                    file_size=info.file_size,
                    compress_size=info.compress_size,
                    compression_type=info.compress_type,
                    ratio=ratio,
                    suspicious_path=suspicious,
                    suspicious_reasons=reasons,
                )
            )

        summary = {
            "entry_count": len(entries),
            "risk_flags": sorted(set(risk_flags)),
        }
        return entries, summary


def enforce_candidate_limits(entry: EntryInfo, limits: Limits) -> None:
    if entry.file_size > limits.max_member_bytes:
        raise ZipBombRisk(
            f"Entry {entry.name!r} declares {entry.file_size} bytes which exceeds cap {limits.max_member_bytes}"
        )
    if entry.ratio is not None and entry.ratio > limits.max_ratio:
        raise ZipBombRisk(
            f"Entry {entry.name!r} declares compression ratio {entry.ratio} which exceeds cap {limits.max_ratio}"
        )
