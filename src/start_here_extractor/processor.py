from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .av import run_advisory_scan
from .errors import StartHereError
from .extractor import extract_selected_member
from .inspector import inspect_zip
from .matcher import build_candidates, select_candidate
from .reader import read_preview
from .types import ExtractSettings, FileMeta, Limits, MatchPolicy, ProcessResult
from .utils import md5_file, sha256_file


def file_meta(path: Path) -> FileMeta:
    return FileMeta(path=str(path), size_bytes=path.stat().st_size, sha256=sha256_file(path), md5=md5_file(path))


def process_zip(zip_path: Path, output_dir: Path, limits: Limits, policy: MatchPolicy, settings: ExtractSettings) -> ProcessResult:
    zip_meta = file_meta(zip_path)
    entries, inspection_summary = inspect_zip(zip_path, limits)
    candidate_objects = build_candidates(entries, policy)

    result = ProcessResult(
        outcome="inspected",
        zip_file=zip_meta,
        settings={
            "limits": asdict(limits),
            "match_policy": asdict(policy),
            "extract_settings": asdict(settings),
        },
        inspection={
            "entry_count": inspection_summary["entry_count"],
            "risk_flags": inspection_summary["risk_flags"],
            "entries": [asdict(entry) for entry in entries],
            "candidates": [
                {
                    "name": candidate.name,
                    "extension": candidate.extension,
                    "priority": candidate.priority,
                    "score_reason": candidate.score_reason,
                }
                for candidate in candidate_objects
            ],
        },
        risk_flags=list(inspection_summary["risk_flags"]),
        av={"status": "not-run"},
    )

    try:
        candidate = select_candidate(candidate_objects, policy)
        result.selected_candidate = {
            "name": candidate.name,
            "extension": candidate.extension,
            "priority": candidate.priority,
            "score_reason": candidate.score_reason,
            "declared_file_size": candidate.entry.file_size,
            "declared_compressed_size": candidate.entry.compress_size,
            "declared_ratio": candidate.entry.ratio,
        }
        extracted = extract_selected_member(zip_path, candidate, output_dir, limits, settings)
        result.extracted_file = {
            "path": str(extracted),
            "size_bytes": extracted.stat().st_size,
            "sha256": sha256_file(extracted),
            "md5": md5_file(extracted),
        }
        preview = read_preview(extracted, limits.preview_bytes, limits.preview_lines)
        result.preview = asdict(preview)
        result.av = run_advisory_scan(extracted, settings.av_command)
        result.outcome = "extracted"
        return result
    except StartHereError as exc:
        result.errors.append({"type": type(exc).__name__, "message": str(exc)})
        result.outcome = "no_match" if type(exc).__name__ == "NoMatchError" else "error"
        return result
    except Exception as exc:  # pragma: no cover - defensive
        result.errors.append({"type": type(exc).__name__, "message": str(exc)})
        result.outcome = "error"
        return result
