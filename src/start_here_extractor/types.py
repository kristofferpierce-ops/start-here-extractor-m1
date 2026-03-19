from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class Limits:
    max_entries: int = 10_000
    max_member_bytes: int = 5 * 1024 * 1024
    max_ratio: float = 100.0
    preview_bytes: int = 4096
    preview_lines: int = 40


@dataclass(slots=True)
class MatchPolicy:
    allowed_basenames: List[str] = field(default_factory=lambda: ["starthere"])
    allowed_extensions: List[str] = field(default_factory=lambda: [".txt", ".md"])
    tie_policy: str = "prefer"
    preferred_extensions: List[str] = field(default_factory=lambda: [".txt", ".md"])


@dataclass(slots=True)
class ExtractSettings:
    flatten_output: bool = True
    strict_verify: bool = False
    allow_symlink_traversal: bool = False
    av_command: Optional[str] = None
    strict_zip_validation: bool = True
    sandbox_platform: Optional[str] = None
    sandbox_dry_run: bool = False
    sandbox_timeout_seconds: int = 120
    sandbox_root: Optional[str] = None
    sandbox_command: Optional[str] = None
    sandbox_network_enabled: bool = False
    sandbox_clipboard_enabled: bool = False
    sandbox_vgpu_enabled: bool = False


@dataclass(slots=True)
class EntryInfo:
    name: str
    is_dir: bool
    file_size: int
    compress_size: int
    compression_type: int
    ratio: Optional[float]
    suspicious_path: bool
    suspicious_reasons: List[str] = field(default_factory=list)


@dataclass(slots=True)
class Candidate:
    name: str
    extension: str
    priority: int
    score_reason: str
    entry: EntryInfo


@dataclass(slots=True)
class PreviewResult:
    encoding: str
    text: str
    bytes_read: int
    lines: int


@dataclass(slots=True)
class FileMeta:
    path: str
    size_bytes: int
    sha256: str
    md5: str


@dataclass(slots=True)
class ProcessResult:
    outcome: str
    zip_file: FileMeta
    settings: Dict[str, Any]
    inspection: Dict[str, Any]
    selected_candidate: Optional[Dict[str, Any]] = None
    extracted_file: Optional[Dict[str, Any]] = None
    preview: Optional[Dict[str, Any]] = None
    av: Optional[Dict[str, Any]] = None
    errors: List[Dict[str, str]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    run: Optional[Dict[str, Any]] = None
    provenance: Optional[Dict[str, Any]] = None
    sandbox: Optional[Dict[str, Any]] = None
    zip_hardening: Optional[Dict[str, Any]] = None
    policy: Optional[Dict[str, Any]] = None
    batch: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BatchContext:
    job_id: str
    attempt: int = 1
    max_attempts: int = 1
    retry_reason: str | None = None


@dataclass(slots=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 5.0
    jitter_seconds: float = 0.0


@dataclass(slots=True)
class RetryDecision:
    should_retry: bool
    delay_seconds: float
    reason: str
    attempt: int


@dataclass(slots=True)
class StrictZipValidationResult:
    strict_mode: bool
    ok: bool
    suspicious: bool
    flags: List[str] = field(default_factory=list)
    reason: str = "ok"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PolicyDecision:
    decision: str
    reason: str
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RunContext:
    run_id: str
    started_at: str
    ended_at: str | None = None
    host: str | None = None
    version: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def ensure_path(path: str | Path) -> Path:
    return path if isinstance(path, Path) else Path(path)
