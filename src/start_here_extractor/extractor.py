from __future__ import annotations

import zipfile
from pathlib import Path

from .errors import ExtractionLimitExceeded, PathTraversalRisk
from .inspector import enforce_candidate_limits
from .types import Candidate, ExtractSettings, Limits
from .utils import ensure_dir


def extract_selected_member(zip_path: Path, candidate: Candidate, output_dir: Path, limits: Limits, settings: ExtractSettings) -> Path:
    entry = candidate.entry
    if entry.suspicious_path:
        reasons = ", ".join(entry.suspicious_reasons) or "suspicious path"
        raise PathTraversalRisk(f"Rejected suspicious archive path {entry.name!r}: {reasons}")

    enforce_candidate_limits(entry, limits)
    ensure_dir(output_dir)

    ext = candidate.extension.lower() or ".txt"
    dest = output_dir / f"start_here{ext}"

    with zipfile.ZipFile(zip_path, "r") as archive:
        if settings.strict_verify:
            bad = archive.testzip()
            if bad is not None:
                raise zipfile.BadZipFile(f"CRC/header verification failed on member {bad!r}")

        with archive.open(entry.name, "r") as source, dest.open("wb") as target:
            copied = 0
            while True:
                chunk = source.read(64 * 1024)
                if not chunk:
                    break
                copied += len(chunk)
                if copied > limits.max_member_bytes:
                    target.close()
                    dest.unlink(missing_ok=True)
                    raise ExtractionLimitExceeded(
                        f"Streamed bytes exceeded cap {limits.max_member_bytes} while extracting {entry.name!r}"
                    )
                target.write(chunk)

    return dest
