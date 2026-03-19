from __future__ import annotations

import socket
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from . import __version__
from .errors import PolicyDecisionError, StartHereError
from .extractor import extract_selected_member
from .inspector import inspect_zip
from .matcher import build_candidates, select_candidate
from .policy import choose_policy_decision
from .reader import read_preview
from .sandbox import SandboxJobRequest, WindowsSandboxRunner
from .scan import ScanConfig, scan_extracted_path
from .types import BatchContext, ExtractSettings, FileMeta, Limits, MatchPolicy, ProcessResult, RunContext
from .utils import md5_file, sha256_file
from .zip_hardening import strict_validate_zip


SUPPORTED_SANDBOX_PLATFORMS = {"windows-sandbox"}


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_meta(path: Path) -> FileMeta:
    return FileMeta(path=str(path), size_bytes=path.stat().st_size, sha256=sha256_file(path), md5=md5_file(path))


def _sandbox_available(settings: ExtractSettings) -> bool:
    return bool(settings.sandbox_platform and settings.sandbox_platform in SUPPORTED_SANDBOX_PLATFORMS)


def _build_windows_sandbox_request(zip_path: Path, output_dir: Path, settings: ExtractSettings, run_id: str) -> SandboxJobRequest:
    sandbox_root = Path(settings.sandbox_root) if settings.sandbox_root else output_dir / "_sandbox"
    host_staging_dir = sandbox_root / run_id / "staging"
    host_results_dir = sandbox_root / run_id / "results"
    return SandboxJobRequest(
        job_id=run_id,
        zip_path=zip_path,
        host_staging_dir=host_staging_dir,
        host_results_dir=host_results_dir,
        command_line=settings.sandbox_command,
        timeout_seconds=int(settings.sandbox_timeout_seconds),
        networking_enabled=bool(settings.sandbox_network_enabled),
        clipboard_enabled=bool(settings.sandbox_clipboard_enabled),
        vgpu_enabled=bool(settings.sandbox_vgpu_enabled),
    )


def _run_windows_sandbox(zip_path: Path, output_dir: Path, settings: ExtractSettings, run_id: str) -> dict:
    request = _build_windows_sandbox_request(zip_path, output_dir, settings, run_id)
    runner = WindowsSandboxRunner()
    sandbox_result = runner.run(request, dry_run=bool(settings.sandbox_dry_run))
    return sandbox_result.to_dict()


def _default_scan() -> dict:
    return {
        "status": "not-run",
        "engine": None,
        "exit_code": None,
        "findings": [],
        "av": {"engine": None, "status": "not-run", "exit_code": None, "findings": []},
        "yara": {"ruleset_id": None, "status": "not-run", "matches": [], "compiled_rules": False},
    }


def _scan_config_from_settings(settings: ExtractSettings) -> ScanConfig:
    return ScanConfig(
        av_engine=settings.av_engine,
        av_command=settings.av_command,
        yara_command=settings.yara_command,
        yara_rules=settings.yara_rules,
        yara_ruleset_id=settings.yara_ruleset_id,
        yara_compiled_rules=settings.yara_compiled_rules,
        yara_allow_compiled_rules=settings.yara_allow_compiled_rules,
        timeout_seconds=settings.scan_timeout_seconds,
    )


def process_zip(
    zip_path: Path,
    output_dir: Path,
    limits: Limits,
    policy: MatchPolicy,
    settings: ExtractSettings,
    *,
    batch_context: BatchContext | None = None,
) -> ProcessResult:
    run = RunContext(run_id=str(uuid4()), started_at=utcnow_iso(), host=socket.gethostname(), version=__version__)
    zip_meta = file_meta(zip_path)
    default_scan = _default_scan()
    result = ProcessResult(
        outcome="inspected",
        zip_file=zip_meta,
        settings={
            "limits": asdict(limits),
            "match_policy": asdict(policy),
            "extract_settings": asdict(settings),
        },
        inspection={
            "entry_count": 0,
            "risk_flags": [],
            "entries": [],
            "candidates": [],
        },
        risk_flags=[],
        av=default_scan,
        run=run.to_dict(),
        provenance={
            "source_type": "local",
            "local_path": str(zip_path),
            "fetched_at": run.started_at,
            "staging_path": str(zip_path),
        },
        sandbox={"enabled": False, "platform": None, "notes": []},
        zip_hardening={"strict_mode": settings.strict_zip_validation, "ok": True, "suspicious": False, "flags": [], "reason": "ok"},
        policy={"decision": "allow", "reason": "ok", "notes": []},
        batch=asdict(batch_context) if batch_context else None,
    )

    try:
        entries, inspection_summary = inspect_zip(zip_path, limits)
        candidate_objects = build_candidates(entries, policy)
        result.inspection = {
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
        }

        strict_result = strict_validate_zip(zip_path, strict_mode=settings.strict_zip_validation)
        result.zip_hardening = strict_result.to_dict()
        result.risk_flags = sorted(set(list(inspection_summary["risk_flags"]) + list(strict_result.flags)))

        pre_policy = choose_policy_decision(
            inspection_risk_flags=inspection_summary["risk_flags"],
            zip_hardening=strict_result,
            scan=result.av or {},
            sandbox_available=_sandbox_available(settings),
        )
        result.policy = pre_policy.to_dict()
        if pre_policy.decision == "reject":
            raise PolicyDecisionError(pre_policy.reason)

        if pre_policy.decision == "sandbox":
            if settings.sandbox_platform == "windows-sandbox":
                result.sandbox = _run_windows_sandbox(zip_path, output_dir, settings, run.run_id)
                result.outcome = "inspected"
                result.warnings = [pre_policy.reason, *(pre_policy.notes or [])]
                return result
            raise PolicyDecisionError("sandbox-platform-not-supported")

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

        scan_result = scan_extracted_path(extracted, _scan_config_from_settings(settings))
        result.av = scan_result
        post_policy = choose_policy_decision(
            inspection_risk_flags=inspection_summary["risk_flags"],
            zip_hardening=strict_result,
            scan=scan_result,
            sandbox_available=_sandbox_available(settings),
        )
        result.policy = post_policy.to_dict()
        if post_policy.decision == "reject":
            result.errors.append({"type": "PolicyDecisionError", "message": post_policy.reason})
            result.outcome = "error"
            return result
        if post_policy.decision == "warn" and post_policy.reason not in result.warnings:
            result.warnings.append(post_policy.reason)

        preview = read_preview(extracted, limits.preview_bytes, limits.preview_lines)
        result.preview = asdict(preview)
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
    finally:
        run.ended_at = utcnow_iso()
        result.run = run.to_dict()
